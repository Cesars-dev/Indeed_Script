# Preflight / Master Plan: Init Script Fix

## Verified Against Actual Code

### Change 1 — L15: env var
- **Current (L15):** `os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"`
- **Target:** `os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "addBinding"`
- **Import order verified:** L23 `from rebrowser_playwright.async_api import ...` comes AFTER L15 ✅
- **No other files set this var** ✅

### Change 2 — L1014-L1025: init script
- **Current:** 12-line webdriver-only script
- **Target:** ~35-line script with webdriver + Battery + Permissions
- **Verified:** `add_init_script` is called exactly once at L1017 ✅
- **Verified:** No `f"""` needed (no Python variables interpolated — all values are static JS) ✅
- **Verified:** No `{{` escaping needed (not an f-string) ✅

### Change 3 — L1027: comment
- **Current:** `# ── Runtime.enable leak: FIXED by rebrowser-patches (isolated world) ──`
- **Target:** `# ── Runtime.enable leak: FIXED by rebrowser-patches (addBinding mode) ──`
- **Trivial change** ✅

## Open Issues: ZERO

All claims verified against real line numbers. All changes are minimal and non-destructive.

## Approval Checklist
- [x] Audit complete — every file and line traced
- [x] Action plan written — exact diffs specified
- [x] Cross-reference — audit ↔ plan aligned, no contradictions
- [x] Preflight — all line numbers verified against actual code
- [x] No dangerous overrides reintroduced (no __pw*, no WebGL, no screen)
- [x] Import order preserved (env var before import)

## Status: READY TO EXECUTE
Awaiting user approval.
