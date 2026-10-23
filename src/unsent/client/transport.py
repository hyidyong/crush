"""The same event contract over a browser bridge or a private native connection."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import queue
import stat
import threading
import uuid
from urllib.parse import urlsplit

from unsent.shared.contracts import ChatEvent


class BrowserTransport:
    def __init__(self, bridge):
        self.bridge = bridge
        self.session_id = ""

    def start_chat(self, request):
        # ASCII JSON avoids the JS/WASM string bridge's Unicode conversion path.
        self.session_id = request.session_id
        self.bridge.startChat(json.dumps(asdict(request), ensure_ascii=True))

    def reset(self, conversation_id, epoch):
        self.bridge.reset(conversation_id, epoch, self.session_id)

    def drain_events(self):
        try:
            return [ChatEvent(**event) for event in json.loads(str(self.bridge.drainEvents()))]
        except (ValueError, TypeError, KeyError):
            return []

    def get_health(self):
        try:
            return json.loads(str(self.bridge.health()))
        except (ValueError, TypeError, AttributeError):
            return {"app": "unavailable", "model": "unavailable"}

    @property
    def health(self):
        return self.get_health()

    def close(self):
        pass


class DesktopTransport:
    """HTTP/SSE on worker threads, with FIFO order within each conversation.

    A profile stores only its own signed identity cookie, never a bearer token.
    Reset uses a separate request so it can cancel an in-flight generation.
    """
    def __init__(self, url, token=None, identity_path=None, *, http_client=None):
        import httpx
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("Use an HTTP(S) application origin without credentials")
        self.url = url.rstrip("/")
        self.host = parsed.hostname
        self.identity_path = Path(identity_path) if identity_path else None
        self.session_id = uuid.uuid4().hex
        self.health = {"app": "connecting", "model": "unavailable"}
        self.storage_scope = None
        self.identity_status = "connecting"
        self.bootstrap_finished = False
        self.identity_changed = False
        self._events = queue.Queue()
        self._queues = {}
        self._epochs = {}
        self._session_ids = {}
        self._lock = threading.RLock()
        self._identity_lock = threading.Lock()
        self._ready = False
        self._closed = False
        self._client = http_client or httpx.Client(base_url=self.url, timeout=150, follow_redirects=False,
            trust_env=self.host not in ("localhost", "127.0.0.1", "::1"))
        if token:
            self._client.headers["Authorization"] = "Bearer " + token
        self._load_cookie()
        threading.Thread(target=self._initial_status, daemon=True, name="unsent-private-status").start()

    def _load_cookie(self):
        path = self.identity_path
        if path is None or not path.exists():
            return
        if path.is_symlink():
            raise ValueError("Identity must be a private regular file")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 4096:
            raise ValueError("Identity must be a private regular file (0600)")
        try:
            data = json.loads(path.read_text())
            if data.get("origin") != self.url:
                return
            for name, value in data.get("cookies", {}).items():
                if name.startswith("unsent_identity_") and isinstance(value, str) and len(value) == 113:
                    self._client.cookies.set(name, value, domain=self.host, path="/api/")
        except (ValueError, TypeError, AttributeError):
            return

    def _save_cookie(self):
        path = self.identity_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("Identity must use a private regular path")
        path.parent.chmod(0o700)
        cookies = {cookie.name: cookie.value for cookie in self._client.cookies.jar
                   if cookie.name.startswith("unsent_identity_") and cookie.path == "/api/"}
        # Atomic replacement keeps a partial write from rotating a user's identity.
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(fd, "w") as output:
                json.dump({"origin": self.url, "cookies": cookies}, output)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @property
    def identity_ready(self):
        return self._ready and not self.identity_changed and not self._closed

    def _bootstrap(self, *, refresh=False, expected_scope=None):
        with self._identity_lock:
            if self.identity_changed:
                raise RuntimeError("Private identity changed; initialize a separate private state")
            if not self._ready or refresh:
                try:
                    response = self._client.get("/api/identity", headers={"X-Unsent-Client": "1"})
                    response.raise_for_status()
                    identity = response.json()
                    scope, csrf = identity["storage_scope"], identity["csrf_token"]
                    if not isinstance(scope, str) or not scope or len(scope) > 160 or not isinstance(csrf, str) or not csrf.isascii():
                        raise ValueError("Invalid private identity response")
                    old_scope = self.storage_scope
                    self._client.headers["X-Unsent-CSRF"] = csrf
                    self.storage_scope = scope
                    self._save_cookie()
                    if old_scope is not None and old_scope != scope:
                        self.identity_changed = True
                        self.identity_status = "changed"
                        self._ready = False
                        raise RuntimeError("Private identity changed; old state was not sent")
                    self._ready = True
                    self.identity_status = "ready"
                except Exception:
                    self._ready = False
                    if not self.identity_changed:
                        self.identity_status = "unavailable"
                    raise
            if expected_scope is not None and self.storage_scope != expected_scope:
                raise RuntimeError("Queued state belongs to a different private identity")
            # Pin the verified cookie to this mutation. A concurrent bootstrap
            # must not switch its owner between verification and transmission.
            headers = {"X-Unsent-CSRF": self._client.headers["X-Unsent-CSRF"]}
            cookie = self._client.build_request("POST", "/api/chat").headers.get("Cookie")
            headers["Cookie"] = cookie or ""
            return headers

    def _initial_status(self):
        try:
            self._bootstrap()
            response = self._client.get("/api/health", timeout=8)
            response.raise_for_status()
            value = response.json()
            if isinstance(value, dict):
                self.health = value
        except Exception:
            self.health = {"app": "unavailable", "model": "unavailable"}
        finally:
            self.bootstrap_finished = True

    def get_health(self):
        return dict(self.health)

    def start_chat(self, request):
        with self._lock:
            if self._closed:
                return
            cid = request.conversation_id
            self._epochs[cid] = max(self._epochs.get(cid, 0), request.epoch)
            self._session_ids[cid] = request.session_id
            if not self.identity_ready:
                self._failure(request)
                return
            if cid not in self._queues:
                pending = self._queues[cid] = queue.Queue()
                threading.Thread(target=self._worker, args=(pending,), daemon=True, name="unsent-private-chat").start()
            self._queues[cid].put((request, self.storage_scope))

    def _current(self, request):
        return not self._closed and self._epochs.get(request.conversation_id, 0) == request.epoch

    def _failure(self, request):
        if not self._current(request):
            return
        if self.identity_changed:
            message = "Your private identity changed. Reopen the app to use its separate data." if request.language == "en" else "개인 세션이 바뀌었어요. 앱을 다시 열면 해당 세션의 별도 데이터를 사용할 수 있어요."
            code = "identity_changed"
        else:
            message = "Could not connect. Check the local backend and try again." if request.language == "en" else "연결하지 못했어요. 로컬 백엔드를 확인하고 다시 보내 주세요."
            code = "connection"
        self._events.put(ChatEvent("error", request.conversation_id, request.epoch, "", request.client_message_id, {"message": message, "code": code}))
        self._events.put(ChatEvent("done", request.conversation_id, request.epoch, "", request.client_message_id, {}))

    def _worker(self, pending):
        while (item := pending.get()) is not None:
            request, expected_scope = item
            if not self._current(request):
                continue
            try:
                headers = self._bootstrap(refresh=True, expected_scope=expected_scope)
                complete = False
                with self._client.stream("POST", "/api/chat", json=asdict(request), headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not self._current(request):
                            break
                        if line.startswith("data: "):
                            event = ChatEvent(**json.loads(line[6:]))
                            if event.conversation_id != request.conversation_id or event.epoch != request.epoch:
                                continue
                            self._events.put(event)
                            complete |= event.kind == "done"
                if not complete:
                    self._failure(request)
            except Exception:
                self._failure(request)

    def reset(self, conversation_id, epoch):
        with self._lock:
            self._epochs[conversation_id] = max(self._epochs.get(conversation_id, 0), epoch)
            sid = self._session_ids.get(conversation_id, self.session_id)
            expected_scope = self.storage_scope
            if not self.identity_ready:
                return
        def run():
            try:
                headers = self._bootstrap(refresh=True, expected_scope=expected_scope)
                response = self._client.post("/api/conversations/" + conversation_id + "/reset", json={"session_id": sid, "epoch": epoch}, headers=headers)
                response.raise_for_status()
            except Exception:
                # A new epoch in the next chat independently clears stale context.
                pass
        if not self._closed:
            threading.Thread(target=run, daemon=True, name="unsent-private-reset").start()

    def drain_events(self):
        events = []
        while True:
            try:
                event = self._events.get_nowait()
                if self._epochs.get(event.conversation_id, 0) == event.epoch:
                    events.append(event)
            except queue.Empty:
                return events

    def close(self):
        with self._lock:
            self._closed = True
            for pending in self._queues.values():
                pending.put(None)
        self._client.close()
