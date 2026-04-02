# Audit: Init Script Fix — alwaysIsolated → addBinding + Main-World Stealth

## Files Involved

| File | Lines | What |
|------|-------|------|
| `src/playwright_indeed.py` | L15 | `os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"` |
| `src/playwright_indeed.py` | L1014-L1025 | Current init script (webdriver-only, runs in isolated world) |

No other files reference the env var in live code. Archive docs reference it in 6 places (all historical, no action needed).

## What EXISTS (current state)

### Line 15 — Runtime mode
```python
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"
```
- Set BEFORE `import rebrowser_playwright` (correct placement)
- Forces ALL Playwright code into isolated JS world
- **Problem:** init script overrides are INVISIBLE to Cloudflare's main-world detection

### Lines 1014-1025 — Init script
```python
await context.add_init_script("""(() => {
  try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto && Object.getOwnPropertyDescriptor(proto, 'webdriver')) {
      delete proto.webdriver;
    }
  } catch(e) {}
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
})();""")
```
- Only patches `navigator.webdriver`
- **Problem:** runs in isolated world → CF still sees `webdriver === true`
- Missing Battery API shim (VPS giveaway)
- Missing Permissions API normalization

### Lines 988-1007 — Fingerprint variables (still extracted, used for logging)
```python
fp = db_row.get("fingerprint") or {}
fp_screen_w   = fp.get("screenWidth", 1440)
# ... 16 more variables extracted from Supabase
fp_vendor_esc = str(fp_vendor).replace("'", "\\'")
fp_renderer_esc = str(fp_renderer).replace("'", "\\'")
```
- These variables are extracted but NO LONGER INJECTED (correct — AdsPower handles at C++)
- `fp_vendor_esc` and `fp_renderer_esc` are now dead code (only used by old WebGL override)
- Logging on L1010 still uses them for the fingerprint print line (fine to keep)

### Line 1027 — Comment
```python
# ── Runtime.enable leak: FIXED by rebrowser-patches (isolated world) ──
```
- Will need updating — rebrowser still fixes the leak in `addBinding` mode too, just differently

## What's MISSING

1. `addBinding` mode — init scripts need to run in main world for CF
2. Battery API shim — VPS returns null, CF detects as headless/server
3. Permissions API normalization — headless Chrome has different permission responses

## Risks / Conflicts

1. **Will `addBinding` mode cause the same crash we fixed?**
   - NO. The crash was caused by `delete __playwright__binding__`, `delete __pwInitScripts`, and WebGL double-patching. We are NOT adding any of those back.
   - `addBinding` is rebrowser's DEFAULT mode — it's the most tested path.

2. **Dead code: `fp_vendor_esc` and `fp_renderer_esc`**
   - Safe to leave — only used in the logging print. Removing would be cleanup, not a fix.

3. **Comment on L1027 references "isolated world"**
   - Minor — should update to reflect `addBinding` mode.

## Dependencies
- `rebrowser-playwright 1.52.0` supports `addBinding` mode (it's the default)
- No other files import or reference the runtime mode env var
- No `.env` file sets this (it's hardcoded in source)
