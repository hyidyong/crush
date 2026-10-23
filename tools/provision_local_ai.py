#!/usr/bin/env python3
"""Install the pinned CPU-only local model without sending any user data out.

Only public release artifacts are downloaded. Conversation data, keys, and private
profiles never enter this command. All generated state stays in ignored .local/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import tarfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "kakaocorp.kanana-1.5-2.1b-instruct-2505.Q5_K_M.gguf"
MODEL_URL = (
    "https://huggingface.co/DevQuasar/kakaocorp.kanana-1.5-2.1b-instruct-2505-GGUF/"
    "resolve/4d3b6203857d893ebfcaca6c51901e3ea1d00d00/" + MODEL_NAME + "?download=true"
)
MODEL_SHA = "04754ded7b3fc1773620a93b5c88c1e58016d7b2568c02398a9195a83962f2b9"
RUNTIME_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11669/llama-b11669-bin-ubuntu-x64.tar.gz"
RUNTIME_SHA = "cf07c1c112d709bd67e522017471de57ed0ec8bea031d732c5422351c07f65ac"
TOKENIZER_URL = (
    "https://huggingface.co/kakaocorp/kanana-1.5-2.1b-instruct-2505/"
    "resolve/7df4bc35ccd610e451809d7106e1c3cf82bfd44c/tokenizer_config.json"
)
TOKENIZER_SHA = "b91085d61a2d8df5b774c8e607afce6bc7e01b1139fa95769f118be5bf2c7db6"
TEMPLATE_SHA = "42745fb34df3e367eb6ba9e11e18475bef40f4f51270484a5cab7a42db6e6ebc"
TEMPLATE_NAME = "kanana-1.5-2.1b-instruct-2505-official.jinja"


def private_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Use a real private local directory")
    path.chmod(0o700)
    return path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(url: str, target: Path, sha256: str) -> Path:
    if target.is_symlink():
        raise ValueError("Refusing a symbolic link in local artifacts")
    if target.is_file() and digest(target) == sha256:
        print(f"Verified cached {target.name}", flush=True)
        return target
    partial = target.with_suffix(target.suffix + ".partial")
    if partial.is_symlink():
        raise ValueError("Refusing a symbolic link in local artifacts")
    print(f"Downloading pinned {target.name}", flush=True)
    # Do not persist redirects, headers, proxy credentials, or signed CDN URLs.
    request = urllib.request.Request(url, headers={"User-Agent": "Unsent-local-model-setup/0.2"})
    try:
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=60) as response:
            fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
            received = 0
            next_progress = 128 * 1024 * 1024
            with os.fdopen(fd, "wb") as output:
                while block := response.read(1024 * 1024):
                    output.write(block)
                    received += len(block)
                    if received >= next_progress:
                        print(f"  {received // (1024 * 1024)} MiB downloaded", flush=True)
                        next_progress += 128 * 1024 * 1024
        if digest(partial) != sha256:
            raise ValueError(f"Checksum mismatch for {target.name}; cached file was not used")
        partial.replace(target)
        target.chmod(0o600)
        print(f"Verified {target.name}", flush=True)
        return target
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def install_runtime(archive: Path, runtime: Path) -> Path:
    destination = private_directory(runtime / "llama")
    # Verify and extract only regular release files. Never follow archive links.
    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            if not member.isfile():
                continue
            name = Path(member.name).name
            if not (name == "llama-server" or name.startswith(("libggml", "libllama", "libmtmd"))):
                continue
            target = destination / name
            if target.is_symlink():
                raise ValueError("Refusing a symbolic link in local runtime")
            payload = source.extractfile(member)
            if payload is None:
                continue
            with payload, target.open("wb") as output:
                shutil.copyfileobj(payload, output)
            target.chmod(0o700 if name == "llama-server" else 0o600)
        # The pinned Linux release uses versioned library aliases. Materialize
        # only aliases to an extracted sibling; never create archive symlinks.
        aliases = {}
        for member in source.getmembers():
            if member.issym():
                name = Path(member.name).name
                linked = Path(member.linkname)
                if not name.startswith(("libggml", "libllama", "libmtmd")) or linked.name != member.linkname:
                    raise ValueError("Unexpected link in pinned runtime archive")
                aliases[name] = linked.name
        for name, linked in aliases.items():
            seen = {name}
            while linked in aliases:
                if linked in seen:
                    raise ValueError("Cyclic runtime library alias")
                seen.add(linked)
                linked = aliases[linked]
            target, real = destination / name, destination / linked
            if target.is_symlink() or not real.is_file() or real.is_symlink():
                raise ValueError("Unsafe runtime library alias")
            shutil.copyfile(real, target)
            target.chmod(0o600)
    binary = destination / "llama-server"
    if not binary.is_file():
        raise ValueError("Pinned release did not contain llama-server")
    return binary


def install_template(tokenizer: Path, runtime: Path) -> Path:
    template = json.loads(tokenizer.read_text(encoding="utf-8"))["chat_template"]
    if not isinstance(template, str) or hashlib.sha256(template.encode()).hexdigest() != TEMPLATE_SHA:
        raise ValueError("Pinned official chat template did not match")
    target = runtime / TEMPLATE_NAME
    if target.is_symlink():
        raise ValueError("Refusing a symbolic link in local template")
    target.write_text(template, encoding="utf-8")
    target.chmod(0o600)
    return target


def write_config(local: Path, model: Path, port: int) -> Path:
    config = local / "config.toml"
    if config.exists() or config.is_symlink():
        print("Existing private config preserved", flush=True)
        return config
    # JSON string escaping is also valid for these TOML basic strings.
    contents = (
        '[model]\nprovider = "openai_compatible"\n'
        f'base_url = "http://127.0.0.1:{port}/v1"\n'
        f"name = {json.dumps(str(model))}\n"
        'response_mode = "text"\ntimeout_s = 120\n'
    )
    fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(contents)
    print("Created ignored private .local/config.toml (no API key needed)", flush=True)
    return config


def occupied(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


def launch(binary: Path, model: Path, template: Path, local: Path, port: int, threads: int) -> None:
    if occupied(port):
        print(f"Port {port} already has a service; no process was replaced", flush=True)
        return
    logs = private_directory(local / "logs")
    log_path = logs / "llama-server.log"
    if log_path.is_symlink():
        raise ValueError("Refusing a symbolic link in local logs")
    command = [str(binary), "--model", str(model), "--host", "127.0.0.1", "--port", str(port),
        "--threads", str(threads), "--threads-batch", str(threads), "--ctx-size", "8192", "--parallel", "1",
        "--jinja", "--chat-template-file", str(template), "--skip-chat-parsing", "--reasoning", "off",
        "--temp", "0.7", "--top-p", "0.8", "--top-k", "20", "--min-p", "0", "--offline"]
    # The runtime receives no cloud API keys or unrelated environment variables.
    child_env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(binary.parent), "LANG": "C.UTF-8"}
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "ab") as log:
        process = subprocess.Popen(command, cwd=binary.parent, env=child_env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    pid = local / "llama-server.pid"
    if pid.is_symlink():
        process.terminate()
        raise ValueError("Refusing a symbolic link in local PID file")
    pid.write_text(str(process.pid) + "\n")
    pid.chmod(0o600)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Local model process exited; review the private .local/logs/llama-server.log")
        try:
            with opener.open(f"http://127.0.0.1:{port}/health", timeout=3) as response:
                if response.status == 200:
                    print(f"Pinned Kanana is ready on http://127.0.0.1:{port}/v1", flush=True)
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError("Model is still loading; its private PID/log were preserved")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-only", action="store_true", help="verify public artifacts without writing config or starting inference")
    parser.add_argument("--no-start", action="store_true", help="install and write config without starting inference")
    parser.add_argument("--runtime-only", action="store_true", help="verify/install the pinned runtime; no model fallback")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not 1 <= args.threads <= 64:
        parser.error("Use an unprivileged port and 1–64 CPU threads")
    try:
        local = private_directory(ROOT / ".local")
        runtime = private_directory(local / "runtime")
        cache = private_directory(local / "downloads")
        archive = download(RUNTIME_URL, cache / "llama-b11669-bin-ubuntu-x64.tar.gz", RUNTIME_SHA)
        binary = install_runtime(archive, runtime)
        if args.runtime_only:
            return 0
        model = download(MODEL_URL, private_directory(local / "models") / MODEL_NAME, MODEL_SHA)
        tokenizer = download(TOKENIZER_URL, cache / "kanana-official-tokenizer_config.json", TOKENIZER_SHA)
        template = install_template(tokenizer, runtime)
        if args.download_only:
            return 0
        write_config(local, model, args.port)
        if not args.no_start:
            launch(binary, model, template, local, args.port, args.threads)
        return 0
    except urllib.error.HTTPError as error:
        print(f"Public artifact download blocked (HTTP {error.code}); no fallback model or fake replies were installed.")
    except urllib.error.URLError as error:
        reason = str(error.reason)
        detail = "HTTP tunnel 403 Forbidden" if "403" in reason else type(error.reason).__name__
        print(f"Public artifact network connection failed ({detail}); no fallback model or fake replies were installed.")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        # These messages are entirely local and never include upstream response bodies.
        print(f"Local model setup stopped: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
