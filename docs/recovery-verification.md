# Recovery verification

The old workspace became unavailable and is not available in this execution environment. Its prior source/archive and local commits could not be recovered from accessible workspace/download/snapshot locations; the remote repository contained only its initial README. This implementation is being reconstructed from the conversation's recorded source/contracts. Prior test counts are historical evidence, not test results for this reconstruction.

Browser plugin is not available. Browser validation uses regular Python Playwright with installed Chromium and the exact local app URL `http://127.0.0.1:8765`. Screenshots and temporary evidence go to `/tmp/unsent-browser-qa`.

The flows under test are:

- Inbox → Korean IME composition and Enter/Shift+Enter → separate room drafts and failed delivery.
- Pending room reply → another room → unread notification → seen status → profile → photo post/carousel.
- New message → private bot library → local UTF-8 import → edited active persona → private profile and DM.
- Reload/edit/revision/source view → delete → no data resurrection; separate browser identity never receives the profile/source.
- Private bot save when browser quota fails → draft retained and no false save → successful retry.
- English preference → preserved private bot/profile → English locale on outgoing request; reload preserves preference.
- Failed initial identity bootstrap → no storage overwrite → explicit retry restores settings.
- Simultaneous first tabs, Web Locks and IndexedDB fallback → one identity → fresh-session clearing across tabs.

Use `uv run python tools/qa/browser_check.py` after starting the app server. The browser suite uses deterministic synthetic SSE responses for interaction checks. Genuine local-model inference and backend ownership tests are separate checks and must be reported separately.

Current verification (2026-10-23):

- `uv sync --locked --all-extras` with a workspace-local UV cache: resolved32packages, checked31installedpackages; no repository dependency change.
- `.venv/bin/python -m pytest -q`:28passed; browser tests excluded here and executed separately.
- `.venv/bin/python -m pytest -m browser tests/browser -q`:13passed in99.01seconds using system Chromium, including actual WASM rendering and isolated bridge boundary checks. Replies in UI tests are synthetic transport fixtures; actual model check is separate.
- Native Pygame smoke with SDL dummy, `--no-backend --frames2`: exit0 and rendered screenshot.
- Public source audit:72trackedfiles, no matching credential values or private paths; allowlisted appZIP excludes backend/configuration.
- Backend identity keys are0600; `.local` and per-user/profile directories are0700.
- Real-model check was executed and failed with `Configured model is unavailable; no live check was substituted`. Pinned llama.cpp runtime was downloaded and verified, but the pinned Kanana weights request failed at the network proxy with403; direct DNS was also unavailable. Genuine AI conversation is not verified in this environment.

Review fixes verified during recovery: CSRF field contract, raw-source import separated from active prompt, native identity-bound persistence and mutation continuity, fresh-session generation barrier, truncated SSE failure, queued DOM edit ordering, and browser-compatible UTF-8 BOM handling. Two-tab bridge tests cover both Web Locks and IndexedDB fallback; their isolated harness tests do not imply model inference.

Public source was first preserved on `recovery/unsent-app`. After the user reported that the default repository page still showed no code, remote `main` was fast-forwarded to the same source, preserving its existing history. Runtime caches, identity keys, models, local bot sources and chat records are excluded. Environment setup/start instructions and public model-download domains were saved as a configuration draft; saving a draft does not apply it to this machine or publish an environment snapshot.

The HTTP and Chromium checks above ran inside the cloud execution environment. They do not prove that the user's browser can reach the cloud loopback address. `127.0.0.1` on a user's own computer refers to that computer. This session has no usable user-facing browser-preview connection; browser activation reports a missing platform-provisioned credential. No public tunnel or third-party deployment was created. For a browser on the user's computer, run the repository's local launcher on that computer and use its local URL.
