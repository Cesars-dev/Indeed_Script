# Action Plan: Init Script Fix

## Change 1 — Switch runtime mode (L15)

**File:** `src/playwright_indeed.py` line 15

```python
# FROM:
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"
# TO:
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "addBinding"
```

**Why:** `addBinding` runs init scripts in main world where CF operates. Still hides Runtime.enable CDP leak. Is rebrowser's default and most-tested mode.

## Change 2 — Replace init script (L1014-L1025)

**File:** `src/playwright_indeed.py` lines 1014-1025

Replace the current webdriver-only block with:

```python
            # ── Minimal stealth: main-world overrides (addBinding mode) ──────
            # AdsPower handles screen, hardware, WebGL at C++ level.
            # We only patch what AdsPower does NOT: webdriver, Battery, Permissions.
            await context.add_init_script("""(() => {
  // 1. Hide webdriver (CF checks this first — strongest bot signal)
  try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto && Object.getOwnPropertyDescriptor(proto, 'webdriver')) {
      delete proto.webdriver;
    }
  } catch(e) {}
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });

  // 2. Battery API — VPS has no battery hardware, returns null.
  //    Bot detectors check this — null = headless/VPS giveaway.
  try {
    if (!navigator.getBattery) {
      navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1.0,
        addEventListener: () => {}, removeEventListener: () => {}
      });
    }
  } catch(e) {}

  // 3. Permissions API — normalize notifications query.
  //    Headless Chrome returns different values than headed.
  try {
    const origQuery = window.Permissions?.prototype?.query;
    if (origQuery) {
      window.Permissions.prototype.query = (params) => {
        if (params.name === 'notifications') {
          return Promise.resolve({ state: Notification.permission });
        }
        return origQuery.call(navigator.permissions, params);
      };
    }
  } catch(e) {}
})();""")
```

## Change 3 — Update comment (L1027)

**File:** `src/playwright_indeed.py` line 1027

```python
# FROM:
# ── Runtime.enable leak: FIXED by rebrowser-patches (isolated world) ──
# TO:
# ── Runtime.enable leak: FIXED by rebrowser-patches (addBinding mode) ──
```

## What we are NOT changing
- Lines 988-1007 (fingerprint variable extraction) — still used for logging
- `fp_vendor_esc` / `fp_renderer_esc` — dead code, cosmetic cleanup only, skip for now
- No other files need changes

## Total diff: 3 changes, 1 file, ~25 net lines changed
