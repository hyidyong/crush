#!/usr/bin/env python3
"""Exercise actual local inference and two isolated private browser identities.

Uses invented QA characters and prompts only. Prints counts and assertions, never
model settings, credentials, full prompts, or user data. No mock response path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import httpx
from unsent.backend.app import create_app
from unsent.backend.config import load_local_settings
from unsent.backend.providers import make_provider


class RecordingProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = []

    async def health(self):
        return await self.delegate.health()

    async def reply(self, messages, **kwargs):
        self.calls.append(json.loads(json.dumps(messages)))
        return await self.delegate.reply(messages, **kwargs)


async def bootstrap(client):
    response = await client.get("/api/identity", headers={"X-Unsent-Client": "1"})
    assert response.status_code == 200, "Private identity bootstrap failed"
    identity = response.json()
    client.headers["X-Unsent-CSRF"] = identity["csrf_token"]
    return identity


async def send(client, card, text, mid, language="en"):
    response = await client.post("/api/chat", json={
        "session_id": "deliberately-identical-local-session",
        "conversation_id": "custom_" + "e" * 32,
        "epoch": 0, "client_message_id": mid, "text": text,
        "language": language, "custom_persona": card,
    })
    assert response.status_code == 200, "Private chat HTTP request failed"
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert not any(e["kind"] == "error" for e in events), "Actual local model returned an error"
    bubbles = [e["payload"]["text"] for e in events if e["kind"] == "bubble"]
    assert bubbles and all(0 < len(b) <= 280 for b in bubbles), "No valid actual inference reply"
    return " ".join(bubbles), response.text


async def run(config: Path):
    settings = load_local_settings(config)
    delegate = make_provider(settings)
    if delegate is None or not await delegate.health():
        raise RuntimeError("Configured model is unavailable; no live check was substituted")
    provider = RecordingProvider(delegate)
    with tempfile.TemporaryDirectory(prefix="unsent-live-private-") as data:
        settings.data_dir = data
        app = create_app(settings, provider)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost", timeout=300) as a, \
                httpx.AsyncClient(transport=transport, base_url="http://localhost", timeout=300) as b:
            identity_a = await bootstrap(a)
            identity_b = await bootstrap(b)
            assert identity_a["storage_scope"] != identity_b["storage_scope"], "Private storage scopes collided"
            card_a = {"name": "Mika", "bio": "A fictional adult friend.",
                      "personality": "Calm, concise and friendly. Enjoys sketching old buildings. A_STYLE_741.",
                      "examples": "What are you doing? → Sketching a crooked little house."}
            card_b = {"name": "June", "bio": "A different fictional adult friend.",
                      "personality": "Warm, concise and direct. Enjoys making ceramics. B_STYLE_836.",
                      "examples": "What are you doing? → Trying not to turn this mug into a bowl."}
            first, replay = await send(a, card_a, "My weekend hobby is origami. Please remember that.", "same-message")
            second, _ = await send(b, card_b, "What have I told you about my weekend hobby?", "same-message")
            assert "A_STYLE_741" not in str(provider.calls[-1])
            assert "origami" not in str(provider.calls[-1]).lower(), "Other owner's history entered the prompt"
            assert "origami" not in second.lower(), "Other owner's synthetic private fact appeared in the reply"
            before = len(provider.calls)
            _, repeated = await send(a, card_a, "My weekend hobby is origami. Please remember that.", "same-message")
            assert repeated == replay and len(provider.calls) == before, "Idempotent retry ran inference again"
            recall, _ = await send(a, card_a, "What weekend hobby did I tell you I enjoy?", "follow-up")
            assert "origami" in str(provider.calls[-1]).lower(), "Own context was lost"
            assert "B_STYLE_836" not in str(provider.calls[-1]), "Other owner's card entered the prompt"
            korean_card = {"name": "하루", "bio": "가상의 성인 친구", "personality": "조용하고 다정하며 짧은 반말을 쓴다. 산책을 좋아한다.", "examples": "뭐 해? → 잠깐 동네 걷는 중"}
            korean, _ = await send(b, korean_card, "오늘 할 일이 많아서 조금 피곤해. 너는 뭐 해?", "korean", "ko")
            assert re.search("[가-힣]", korean), "Korean setting did not produce Korean"
            for reply in (first, second, recall):
                assert re.search("[A-Za-z]", reply) and not re.search("[가-힣]", reply), "English setting did not produce English"
            catalog = await a.get("/api/catalog")
            assert "custom_" not in catalog.text and "A_STYLE_741" not in catalog.text
            # Source files, cards and messages have no persistence writer on this backend.
            assert {p.name for p in Path(data).iterdir()} == {"identity.key"}, "Private prompt material was written to disk"
            assert len(app.state.service.store.sessions) == 2
            app.state.service.close()
            return {"actual_model_calls": len(provider.calls), "owners_isolated": True,
                    "private_cards_not_published": True, "source_material_not_persisted": True,
                    "idempotent_retry": True, "korean_reply": True, "english_replies": True,
                    "own_fact_recalled": "origami" in recall.lower()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / ".local" / "config.toml")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args.config)), indent=2))
        return 0
    except (AssertionError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print("Live model check failed; inspect the local model status privately.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
