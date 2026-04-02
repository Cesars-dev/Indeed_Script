# Action Plan — Fix Init Script + CF Detection

> Based on Perplexity Research #1 and #2
> Date: 2026-03-14

## The Problem
Under `alwaysIsolated` mode, NONE of our JavaScript overrides reach the main world where Cloudflare operates. CF still sees:
- `navigator.webdriver === true` (instant bot flag)
- No Battery API (VPS giveaway)
- Abnormal Permissions responses

## The Fix (2 changes)

### Change 1: Switch runtime mode
```python
# File: src/playwright_indeed.py, line 15
# FROM:
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"
# TO:
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "addBinding"
```

**Why:** `addBinding` is rebrowser's default and recommended mode. It still hides `Runtime.enable` CDP leak but runs init scripts in the **main world** where CF can see our overrides.

### Change 2: Use the middle-ground init script
```js
(() => {
  // 1. Hide webdriver (CRITICAL — CF checks this first)
  try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto && Object.getOwnPropertyDescriptor(proto, 'webdriver')) {
      delete proto.webdriver;
    }
  } catch(e) {}
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });

  // 2. Battery API (VPS has no battery — dead giveaway)
  try {
    if (!navigator.getBattery) {
      navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1.0,
        addEventListener: () => {}, removeEventListener: () => {}
      });
    }
  } catch(e) {}

  // 3. Permissions API (normalize notifications)
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
})();
```

### What we are NOT doing (confirmed dangerous):
- ❌ `delete window.__playwright__binding__` — corrupts rebrowser internals
- ❌ `delete window.__pwInitScripts` — corrupts rebrowser internals
- ❌ WebGL prototype override — crashes Chrome with AdsPower
- ❌ Screen/hardware Object.defineProperty — redundant (AdsPower C++)

## Validation Steps
1. Apply both changes
2. Test on fresh profile (not k19td50a — already burned tonight)
3. Run rebrowser-bot-detector to verify navigator.webdriver is hidden
4. Hit indeed.com and check if CF Turnstile still appears
5. If CF appears, solve once — verify it doesn't re-challenge on next navigation

## Risk Assessment
- `addBinding` mode is the DEFAULT for rebrowser-patches — it's the most tested path
- Our init script is minimal (3 safe overrides) — no double-spoofing risk
- AdsPower still handles all heavy fingerprinting at C++ level
