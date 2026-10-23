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

Status: 10 browser cases collect successfully. The first browser runs reached the local server and exposed missing runtime resources (`vtx.js`, then `browserfs.min.js`) and a corrupted WASM-side synchronous ZIP download. Runtime restoration is being corrected before running the interaction suite. No restored-app browser pass is claimed yet.
