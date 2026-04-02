# Memory: Browser Automation — What We Tried & Why

## The Core Rule (never forget)

**Indeed detects bots at the TLS/JA3 fingerprint level — before any JS runs.**
No amount of `navigator.webdriver = false`, stealth plugins, or header spoofing fixes this.
The ONLY solution: **AdsPower** (spoofs the full fingerprint stack at the browser profile level).

---

## Approach 1: Headless Chrome on VPS (DEAD — M1-M6)
- Launched nodriver's own headless Chromium on VPS
- **Killed at**: TLS handshake level — Cloudflare blocks it before the page loads
- Archived: `archive/nodriver/`

## Approach 2: Cookie Injection + Headless (DEAD — M1-M6)
- Exported cookies from Mac AdsPower → injected into VPS headless Chrome
- **Killed by**: Same fingerprint problem. Cookies help with session but not TLS.
- Also: macOS Keychain encrypts Chrome cookies → can't just copy sqlite file

## Approach 3: AdsPower + nodriver (RETIRED — M7-M22)
- **What it did right**: AdsPower profile started (fingerprint + proxy + session), nodriver attached via debug_port
- **Why it failed**:
  - `browser/start` is GET not POST (took 3ms+ to discover)
  - `connection_url` kwarg in nodriver is **silently ignored** — nodriver launches its own Chrome instead of attaching
  - Correct attach: `Browser.create(host="127.0.0.1", port=debug_port)`
  - `best_match=True` fuzzy-matched wrong elements (clicked nav bar instead of Apply button)
  - WebSocket 500 crashes mid-session (CDP disconnects under load)
  - 15-step hardcoded state machine broke every time Indeed changed a layout
- Archived: `archive/nodriver/nodriver_indeed.py`

## Approach 4: AdsPower + Playwright + Gemini Vision (CURRENT — M24+)
- **Same AdsPower attach** — proven working
- `playwright.connect_over_cdp(f"http://127.0.0.1:{debug_port}")` — battle-tested CDP
- `browser.contexts[0].pages[1]` — tab[1] for work, tab[0] (AdsPower health page) untouched
- **Gemini 2.5 Flash** sees screenshot → returns JSON action → playwright executes
- Zero hardcoded selectors → resilient to DOM changes
- File: `src/playwright_indeed.py`

---

## Critical CDP Rules

```python
# 1. Start profile (GET, not POST)
resp = requests.get(
    f"{ADSPOWER_BASE}/api/v1/browser/start",
    params={"user_id": user_id, "api_key": API_KEY}
)
debug_port = resp.json()["data"]["debug_port"]

# 2. Attach playwright (NOT nodriver, NOT connection_url)
from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
    context = browser.contexts[0]
    page = context.pages[1]   # tab[0] = AdsPower health, NEVER touch

# 3. Stop profile
requests.get(f"{ADSPOWER_BASE}/api/v1/browser/stop",
             params={"user_id": user_id, "api_key": API_KEY})
```

## Tab Management Rule
- `tab[0]` = AdsPower's internal health/proxy status page — **NEVER navigate or close it**
- `tab[1]` = your working tab
- After every session: navigate tab[1] back to `indeed.com` before stopping (keeps session warm)

## Cloudflare Rules
- **Never jump straight to a search URL** — land on `indeed.com` homepage first, idle 15–25s
- If Turnstile fires → `_bypass_cf()` attempts auto-solve + click, then rotates if still blocked
- Valid `JSESSIONID` in profile = returning human = lower CF risk score

### CF Bypass Architecture (March 2026 findings)
- `_is_cf(page)` — detects CF via title patterns + DOM script src check
- `_bypass_cf(page)` — 8-attempt loop: find Turnstile iframe → Bezier mouse → click → wait → reload
- **Critical:** `document.querySelectorAll('iframe')` returns 0 for Turnstile — it uses shadow DOM. Use `page.frames` instead.
- **Datacenter IP blocker:** CF Enterprise on Indeed re-challenges datacenter IPs infinitely even after Turnstile passes and `cf_clearance` cookie is issued. Residential proxy required for VPS.
- Bypass code is correct for residential IPs where CF shows interactive Turnstile checkbox
- Stone-wall spots in `playwright_indeed.py` now try bypass before marking profile as stone-walled

## What pyppeteer Is (and why we don't use it)
- pyppeteer = Python port of Puppeteer (Chromium CDP)  
- **Last release: Oct 2022 — effectively abandoned**
- Has same CDP mechanism but unmaintained Python async quirks
- Playwright is its maintained successor — same API pattern, actively developed by Microsoft
- Use Playwright. Not pyppeteer.

---

## Behavioral Stealth Rules (March 2026 — from Perplexity Deep Research)

> Full implementation plan: `indeed-pipeline/deep_search_eval.md`

### What Indeed's detector actually scores (NDSS PRISM 2026 paper)
Indeed runs its own in-house 6-feature ML model on top of Cloudflare + HUMAN/PerimeterX:

| Feature | Our status | Rule |
|---------|-----------|------|
| `isTrusted` | ✅ CDP events are already trusted | Always use Playwright input APIs, never JS `dispatchEvent` |
| Honeypot triggered | ❌ Not guarded | Gemini prompt must say: never click hidden/zero-size/disabled elements |
| reCAPTCHA score | ⚠️ Fed by behavioral signals | Fix behaviors below |
| Velocity per minute | ❌ Too fast | 3–12s delays between major actions |
| Velocity per hour | ❌ Unknown | Limit applies per profile per hour |
| `timeToPreview` | ❌ Jump straight to job URL | Wait 4–10s on results before previewing, 10–30s before Apply |

### Banned patterns
- **`window.scrollBy()`** — generates zero WheelEvents, trivially detectable. Use `page.mouse.wheel()` instead.
- **`page.hover()`** for behavioral actions — single-point teleport, no trajectory. Use Bezier `human_move_mouse()` + manual click.
- **`element.click()` / `window.dispatchEvent()`** — `isTrusted=false`. Always go through Playwright input APIs.

### Playwright globals to neutralize (CDP attach mode)
Playwright injects these even when attaching to an existing browser via `connect_over_cdp()`:
- `window.__playwright__binding__`
- `window.__pwInitScripts`
- `navigator.webdriver = true`

Fix immediately after `connect_over_cdp()`:
```python
await context.add_init_script("""
(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
  try { delete window.__playwright__binding__; } catch(e) {}
  try { delete window.__pwInitScripts; } catch(e) {}
})();
""")
```

### Recommended libraries
- `humancursor-playwright` — Bezier mouse movement, `cursor.click_on(locator)`
- `playwright-stealth` — JS property patching via `add_init_script`

### nodriver conclusion (final)
nodriver in **attach mode** adds zero fingerprint protection — AdsPower handles all of that.
Its only advantage was behavioral helpers, which can be replicated in Playwright.
**Do not add nodriver to the hot path.** Approach B (Playwright-only) is confirmed.
