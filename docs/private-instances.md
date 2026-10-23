# Private local instances

Use Python3.12 and `uv sync --locked --all-extras`. If your home cache is read-only, prefix commands with `UV_CACHE_DIR=.local/uv-cache`. Start `uv run python tools/launch_local.py --open`; it serves the Pygame browser app and API together at http://127.0.0.1:8765. Native UI: `uv run python -m unsent` while the backend is running.

Each OS user and named `--profile alice` has a separate `.local/users/<uid>/<profile>` backend identity key and configuration. Directories use0700 and private identity files0600. A named profile does not inherit the default model configuration. `--config` and `--data-dir` are explicit overrides. Keep personal directories private and out of Git.

Each browser profile receives a signed HttpOnly SameSite identity cookie. Server conversation memory is keyed by its verified owner plus the client session ID; choosing another session ID does not grant access to another owner. Browser records use an owner-specific storage scope. Separate browsers/OS profiles are needed for separate people sharing a computer: same-origin tabs deliberately share their device identity. Setting **Start a new private session** clears the old device namespaces, revokes the old server session and refreshes other tabs. Cookie isolation is by hostname, not port; use separate browser profiles for unrelated applications sharing a hostname.

Chats stay in server memory with a bounded lifetime and disappear on server restart. Save chats on this device is off by default; bot profiles and unfinished authoring drafts are saved independently. Local source TXT/MD files (UTF-8,64KB,12,000characters) and at most5revision snapshots are device-only. Sending a custom-bot message transmits only the current name,bio,personality and examples to the chosen backend. The profile is prompt context, not model-weight training or a real person's identity.

## AI configuration

The public source starts without a configured model. It never substitutes scripted messages for model replies. To install the pinned bilingual local model and CPU runtime:

```bash
uv run python tools/provision_local_ai.py
uv run python tools/launch_local.py
```

The tool verifies immutable SHA-256 hashes, keeps downloads in ignored `.local/`, writes the default `.local/config.toml`, and binds inference to127.0.0.1:8081. It needs about1.8GB for weights plus runtime space. A network allowing the public HuggingFace model and GitHub release downloads is required. It stops on a blocked download or hash mismatch. No API key is needed for this local model. `tools/qa/live_custom_bots.py` checks actual configured inference and fails if no model is reachable.

Alternatively create your own ignored configuration, for example:

```toml
[model]
provider = "openai_compatible" # or "ollama"
base_url = "http://127.0.0.1:8081/v1"
name = "your-model-id"
response_mode = "text"
timeout_s = 120
# api_key_env = "UNSENT_MODEL_API_KEY"
```

If a provider requires a key, set it directly in your server environment. Do not enter it in browser code, screenshots, chat, Git or the public README. Provider credentials are never returned by the API or bundled in the client. With a remote model, its operator processes the conversation and active personality; use a local model to keep inference on your machine.

The default bind is loopback. Explicit non-loopback hosting requires an access token of at least32characters (`--access-token-env` avoids shell argument history) and explicit `--allowed-host`. Open the local URL with `#access_token=...` only on the intended client; the bridge removes the fragment and keeps the connection token in that tab's sessionStorage. Each browser still receives its own identity. Use HTTPS and your own access controls for access beyond a trusted local machine. No public cloud deployment or account system is configured.

## Verification and source preservation

`uv run pytest` checks state, contracts, private APIs, transports and packaging. With the local server running, `uv run pytest -m browser tests/browser` uses system Chromium; these tests mock reply transport to verify UI mechanics and are separate from genuine model QA. Test files create synthetic markers, not personal records.

Commit only public source, fixtures and fictional assets. `.local/`, `.env*`, identities, model weights, source imports and conversation data are ignored. Use a remote source branch or Git bundle outside an ephemeral cloud environment to preserve commits. Browser app ZIPs contain only allowlisted client/domain/shared modules and fictional assets, never backend configuration.
