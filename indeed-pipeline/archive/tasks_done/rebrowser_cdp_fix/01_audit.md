# Rebrowser CDP Fix — Step 1: AUDIT

> Traces the exact CDP leak, maps affected code, identifies the fix surface.

---

## The Problem

Cloudflare detects Playwright via `Runtime.enable` — a CDP command Playwright sends automatically when connecting to a browser. CF's detection script checks if `console.log` (and similar methods) were overwritten by CDP's Runtime domain. When they are → bot flagged → challenge triggered.

**Current defenses (L959-1038 of playwright_indeed.py):**

1. `add_init_script` — hides `navigator.webdriver`, spoofs screen/GPU/battery
2. Console method freezing — prevents CDP from overwriting `console.log`
3. `Runtime.disable` CDP call — tries to undo the damage

**Why they fail:** `Runtime.enable` fires when Playwright **connects** — before `add_init_script` has a chance to run on the page. The console freeze in init_script runs on new pages, but the damage on first connect is already done. `Runtime.disable` is a band-aid that doesn't fully undo the leak.

---

## Affected Files

| File | Lines | What's There |
|------|-------|-------------|
| `playwright_indeed.py` | L953-956 | `connect_over_cdp()` — no `slow_mo` |
| `playwright_indeed.py` | L959-1028 | `add_init_script()` — stealth patches |
| `playwright_indeed.py` | L1030-1038 | `Runtime.disable` band-aid |
| Playwright internal | `crPage.js` | `Runtime.enable` called per-page |
| Playwright internal | `crServiceWorker.js` | `Runtime.enable` for SW |
| Playwright internal | `crDevTools.js` | `Runtime.enable` for devtools |

---

## Current Flow (what happens today)

```
1. _start_profile(user_id)          → AdsPower starts browser
2. pw.chromium.connect_over_cdp()   → Playwright connects
   ↳ Playwright internals:
     ↳ crBrowser.js → creates CRPage
     ↳ crPage.js → sends Runtime.enable    ← THE LEAK
     ↳ CF detection sees Runtime-wrapped console methods
3. context.add_init_script(...)     → patches navigator, screen, console
   ↳ Only runs on NEXT navigation, not retroactively
4. Runtime.disable via cdp session  → tries to undo, doesn't fully work
5. _human_warmup(page, url)         → navigates to indeed.com
   ↳ CF already knows we're automated → challenge
```

---

## The Fix: rebrowser-patches

**What it does:** Patches Playwright's internal `crPage.js` to run `Runtime.enable` in an **isolated world** instead of the main page context. CF's detection script runs in main context — it never sees the leak.

**Environment variable:** `REBROWSER_PATCHES_RUNTIME_FIX_MODE=alwaysIsolated`

**Steps needed:**
1. Install `rebrowser-patches` npm package
2. Run `npx rebrowser-patches patch` against the Playwright driver directory
3. Set env var `REBROWSER_PATCHES_RUNTIME_FIX_MODE=alwaysIsolated` before Playwright imports
4. Add `slow_mo=50` to `connect_over_cdp()` for behavioral scoring

---

## Dependencies

| Dependency | Location | Version |
|-----------|----------|---------|
| Playwright (Python) | `/usr/local/lib/python3.12/dist-packages/playwright` | 1.58.0 |
| Playwright driver (Node) | `/usr/local/lib/python3.12/dist-packages/playwright/driver/package/` | Bundled |
| rebrowser-patches | Not installed | Need 1.0.19+ |

**Playwright driver path (must patch here):**
```
/usr/local/lib/python3.12/dist-packages/playwright/driver/package/
```

**Files to verify after patching:**
```
lib/server/chromium/crPage.js
lib/server/chromium/crServiceWorker.js
lib/server/chromium/crDevTools.js
```

---

## Risks

1. **Patch may break on Playwright update** — pip upgrade would overwrite the patched files. Need to re-run patch after any Playwright update.
2. **`slow_mo=50` adds ~50ms per CDP command** — minimal impact on overall speed, but worth noting.
3. **Init script console freeze may conflict** — the current console freeze in `add_init_script` might interact weirdly with the isolated world. May need to remove it after patching.
4. **VPS also needs patching** — this fix must be deployed to the VPS too.
