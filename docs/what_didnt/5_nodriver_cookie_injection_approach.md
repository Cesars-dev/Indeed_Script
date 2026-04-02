# SUPERSEDED: nodriver + Cookie Injection Approach

## What It Was
`src/nodriver_indeed.py` — launches fresh headless Chrome, loads a cookie file, injects cookies
via CDP, then navigates to Indeed job pages and tries to apply.

## Why It Was Built
Before we understood AdsPower's full capability, the plan was:
1. Export Indeed session cookies from an AdsPower profile
2. Store them as JSON files
3. Load into a fresh headless browser per run

## Why It's No Longer Needed
AdsPower profiles ARE persistent browser sessions. The profile is already:
- Logged into Indeed (session never expires as long as profile exists)
- Configured with its proxy (baked in at profile creation)
- Fingerprint-spoofed (AdsPower handles canvas, WebGL, TLS, plugins)

The correct flow is:
1. `POST /api/v1/browser/start?user_id={profile_id}&api_key={key}` → AdsPower opens a real browser, returns `data.debug_port`
2. **nodriver attaches** to the existing browser via that debug port (does NOT launch its own Chrome)
3. nodriver handles human-like behavior: mouse movement, natural typing, scroll before click
4. Navigate directly to job URL — already authenticated, correct fingerprint, correct proxy
5. Fill and submit
6. Stop the profile

**No cookie export. No cookie injection. No fresh Chrome launch. No proxy config in code.**
nodriver's role is behavior only — AdsPower handles the fingerprint.

## File to Deprecate
`src/nodriver_indeed.py` — mark DEPRECATED or delete.
`scripts/export_cookies.py` — no longer needed if profiles stay logged in.
`config/cookies/` — can be cleaned up when ready.

## Scaling
To handle more volume: just create more AdsPower profiles.
Each profile = one persistent Indeed session + one proxy.
No cookie refresh cycle. No re-login automation needed.
