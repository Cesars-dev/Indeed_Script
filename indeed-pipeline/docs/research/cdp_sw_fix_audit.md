# CDP Service Worker Fix — AUDIT

## What EXISTS

1. **`playwright_indeed.py` line 15**: `os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "addBinding"` — sets the patch mode globally before importing rebrowser_playwright.

2. **`playwright_indeed.py` lines 1131-1161**: CDP connect retry loop. 3 attempts with increasing timeouts (15s, 25s, 35s). Attempt 0 retries same port, attempt 1+ restarts the browser. **This retry logic is useless** because the hang is caused by service workers — restarting the browser re-loads the same profile with the same SWs.

3. **`_start_profile()` (lines 110-149)**: Starts AdsPower, returns `data` dict containing `debug_port` AND `ws.puppeteer` WebSocket URL. The WS URL is available but never used.

4. **`websockets` 15.0.1**: Already installed in venv_local.

5. **`_cdp_alive()` (lines 101-107)**: Checks HTTP `/json/version` endpoint. Works fine — not the issue.

## What's MISSING

1. **No service worker cleanup before `connect_over_cdp()`**. This is the root cause of the 15s+ timeout on profiles with active browser sessions.

2. **No use of raw WebSocket connection at all**. The `ws.puppeteer` URL from `_start_profile()` is available in `profile_data` but discarded.

## Root Cause (Proven)

- AdsPower profiles with browsing history have **Chrome extension service workers** active
- `connect_over_cdp()` enumerates ALL browser targets including SWs
- rebrowser's `addBinding` patch tries to inject `Runtime.addBinding` into SW targets
- SW targets lack `window` object → **infinite deadlock**
- Raw CDP `Target.closeTarget` kills SWs, then Playwright connects in 0.1s

## Dependencies

- `websockets` (15.0.1) — already installed
- `json` — stdlib
- `asyncio` — stdlib
- No new dependencies needed

## Risks

- **None** — killing extension SWs before Playwright connects has zero impact on browsing functionality. SWs restart automatically when needed.
- The open pages are navigated to `about:blank` — but Playwright immediately navigates to the job URL anyway.
