# Session: SmartApply v2 Router + Rebrowser CDP Fix
> Date: 2026-03-13

---

## What Was Built

### 1. SmartApply v2 Router (`src/smartapply/`)
Replaced the monolithic `_gemini_loop` with a modular 6-shot decision engine:

| File | Purpose |
|------|---------|
| `router.py` | 6-shot engine: 2 deterministic → 2 Flash → 2 Pro → fail |
| `dom_scanner.py` | Fast DOM extraction via `page.evaluate()` |
| `handlers.py` | 7 deterministic form handlers (file upload, radio, text, dropdown, checkbox, continue) |
| `patterns.py` | 40+ Yes/No patterns, 15+ range patterns, 15+ text input → profile mappings |
| `gemini_fallback.py` | Targeted Gemini prompts built from DOM data (not generic "look at screenshot") |
| `logger.py` | Fire-and-forget async Supabase logging |
| `__init__.py` | Exports `apply_smartapply` |

**Toggle:** `SMARTAPPLY_V2=1` (default) uses new router. `SMARTAPPLY_V2=0` falls back to old `_gemini_loop`.

**Entry point:** `playwright_indeed.py` L1132-1137

### 2. Rebrowser CDP Fix
**Problem:** Playwright's `Runtime.enable` CDP command leaks into main browser context. Cloudflare detects this and triggers challenges.

**Solution:** Replaced `playwright` with `rebrowser-playwright` — a pre-patched drop-in that isolates `Runtime.enable` into a separate world CF can't see.

**Changes to `playwright_indeed.py`:**
- Import: `playwright.async_api` → `rebrowser_playwright.async_api`
- Env var: `REBROWSER_PATCHES_RUNTIME_FIX_MODE=alwaysIsolated` set before import
- Added `slow_mo=50` to `connect_over_cdp()` for behavioral scoring
- Removed 20 lines of band-aid code (console freeze + Runtime.disable)

**Install:** `pip install --break-system-packages rebrowser-playwright`

### 3. Bugs Fixed
| Bug | Location | Fix |
|-----|----------|-----|
| Relative import crash | `router.py` L53 | `from ..playwright_indeed` → `from playwright_indeed` |
| API key empty at runtime | `gemini_fallback.py` L11 | Moved `os.getenv` from module level to function |
| Supabase env empty at runtime | `logger.py` L9-10 | Same — deferred to function call time |

---

## Known Issue: Fingerprint Mismatch

**Critical:** Our `add_init_script` hardcodes fingerprint values (screen 1920x1080, devicePixelRatio 2, NVIDIA GTX 1060, hardwareConcurrency 8). But AdsPower generates its OWN fingerprint per profile. These values may NOT match → inconsistency is itself a detection signal.

**Fix needed:** Read AdsPower's fingerprint per profile, store in Supabase, inject dynamically instead of hardcoding. See `tasks/fingerprint_sync/` for the next-agent task.

---

## Files Changed
- `src/playwright_indeed.py` — rebrowser import, slow_mo, removed band-aids
- `src/smartapply/*` — all 7 new files
- `tasks/rebrowser_cdp_fix/` — 5 surgeon docs

## Dependencies Added
- `rebrowser-playwright` (pip, v1.52.0) — drop-in replacement for `playwright`
- `rebrowser-patches` (npm, v1.0.19) — installed but patch didn't apply (version mismatch)

## VPS Deploy Required
```bash
pip install --break-system-packages rebrowser-playwright
scp -r indeed-pipeline/src/ root@45.55.90.156:/root/indeed-pipeline/
```
