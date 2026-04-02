# Task: AdsPower Fingerprint Sync + Dynamic Injection

> Priority: P0 — blocks all CF bypass testing
> Prereq: `rebrowser-playwright` already installed (see `memory/10_smartapply_v2_rebrowser.md`)

---

## Problem

`playwright_indeed.py` L960-997 hardcodes fingerprint values in `add_init_script`:

```javascript
devicePixelRatio: 2
screen.width: 1920
screen.height: 1080
hardwareConcurrency: 8
deviceMemory: 8
WebGL: "NVIDIA GeForce GTX 1060"
```

But AdsPower generates **different** fingerprint values per profile. Each of the 19 profiles has its own screen resolution, GPU renderer, hardware specs, etc. Our hardcoded overrides **conflict** with AdsPower's fingerprint → inconsistency is a detection vector.

---

## Goal

1. Read each AdsPower profile's REAL browser fingerprint
2. Store it in Supabase (`adspower_profiles` table — already exists)
3. `playwright_indeed.py` reads the fingerprint from the profile row and injects it dynamically

---

## Step 1: Build a fingerprint reader script

Create `scripts/read_fingerprints.py` that:

1. Iterates all 19 profiles from Supabase `adspower_profiles` table
2. For each profile:
   - Starts the AdsPower browser via API (`/api/v1/browser/start`)
   - Connects via rebrowser-playwright CDP
   - Runs `page.evaluate()` to read the **real** values AdsPower set:
     ```javascript
     {
       devicePixelRatio: window.devicePixelRatio,
       screenWidth: screen.width,
       screenHeight: screen.height,
       availWidth: screen.availWidth,
       availHeight: screen.availHeight,
       colorDepth: screen.colorDepth,
       pixelDepth: screen.pixelDepth,
       outerWidth: window.outerWidth,
       outerHeight: window.outerHeight,
       hardwareConcurrency: navigator.hardwareConcurrency,
       deviceMemory: navigator.deviceMemory,
       maxTouchPoints: navigator.maxTouchPoints,
       userAgent: navigator.userAgent,
       platform: navigator.platform,
       webglVendor: <read from WEBGL_debug_renderer_info>,
       webglRenderer: <read from WEBGL_debug_renderer_info>,
     }
     ```
   - Stops the browser
   - Patches the Supabase row with the fingerprint data
3. **IMPORTANT:** Do NOT inject any init_script when reading — we want AdsPower's RAW values

### Supabase Schema Update

**Database:** `supabase_indeed` (the one with `adspower_profiles` table)

Add these columns to `adspower_profiles` (use ALTER TABLE, all nullable text/jsonb):

```sql
ALTER TABLE adspower_profiles ADD COLUMN IF NOT EXISTS fingerprint jsonb DEFAULT '{}';
```

The `fingerprint` column stores the full dict from the evaluate result above. Example:
```json
{
  "devicePixelRatio": 1.5,
  "screenWidth": 1440,
  "screenHeight": 900,
  "availWidth": 1440,
  "availHeight": 860,
  "colorDepth": 24,
  "pixelDepth": 24,
  "outerWidth": 1440,
  "outerHeight": 860,
  "hardwareConcurrency": 4,
  "deviceMemory": 4,
  "maxTouchPoints": 0,
  "userAgent": "Mozilla/5.0 ...",
  "platform": "Win32",
  "webglVendor": "Google Inc. (Intel)",
  "webglRenderer": "ANGLE (Intel, Intel HD Graphics 620, OpenGL 4.5)"
}
```

---

## Step 2: Update `playwright_indeed.py` to use dynamic fingerprint

Replace the hardcoded `add_init_script` block (L960-997) with dynamic values from the profile.

**Current (hardcoded):**
```javascript
Object.defineProperty(window, 'devicePixelRatio', { get: () => 2, configurable: true });
Object.defineProperty(screen, 'width', { get: () => 1920, configurable: true });
// ... etc
```

**New (dynamic):**
```python
# Inside apply_to_job(), after connecting via CDP:
fp = profile.get("fingerprint", {})
if fp:
    init_js = f"""(() => {{
  // ── Stealth: hide Playwright markers ──
  Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined, configurable: true }});
  try {{ delete window.__playwright__binding__; }} catch(e) {{}}
  try {{ delete window.__pwInitScripts; }} catch(e) {{}}

  // ── Fingerprint: match AdsPower values ──
  Object.defineProperty(window, 'devicePixelRatio', {{ get: () => {fp.get('devicePixelRatio', 2)}, configurable: true }});
  Object.defineProperty(screen, 'width', {{ get: () => {fp.get('screenWidth', 1920)}, configurable: true }});
  Object.defineProperty(screen, 'height', {{ get: () => {fp.get('screenHeight', 1080)}, configurable: true }});
  Object.defineProperty(screen, 'availWidth', {{ get: () => {fp.get('availWidth', 1920)}, configurable: true }});
  Object.defineProperty(screen, 'availHeight', {{ get: () => {fp.get('availHeight', 1040)}, configurable: true }});
  Object.defineProperty(screen, 'colorDepth', {{ get: () => {fp.get('colorDepth', 24)}, configurable: true }});
  Object.defineProperty(screen, 'pixelDepth', {{ get: () => {fp.get('pixelDepth', 24)}, configurable: true }});
  Object.defineProperty(window, 'outerWidth', {{ get: () => {fp.get('outerWidth', 1920)}, configurable: true }});
  Object.defineProperty(window, 'outerHeight', {{ get: () => {fp.get('outerHeight', 1040)}, configurable: true }});
  Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {fp.get('hardwareConcurrency', 8)}, configurable: true }});
  Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {fp.get('deviceMemory', 8)}, configurable: true }});
  Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => {fp.get('maxTouchPoints', 0)}, configurable: true }});

  // GPU — use AdsPower's values
  const getParameter = WebGLRenderingContext.prototype.getParameter;
  WebGLRenderingContext.prototype.getParameter = function(param) {{
    if (param === 37445) return '{fp.get('webglVendor', 'Google Inc. (NVIDIA)')}';
    if (param === 37446) return '{fp.get('webglRenderer', 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060, OpenGL 4.5)')}';
    return getParameter.call(this, param);
  }};
  // ... same for WebGL2
}})();"""
```

**Key:** If `fingerprint` is empty in the DB row (hasn't been read yet), fall back to the current hardcoded defaults. This ensures backward compatibility.

---

## Step 3: Test

1. Run `scripts/read_fingerprints.py` on the Mac (where AdsPower runs locally)
2. Verify fingerprints appear in Supabase `adspower_profiles.fingerprint` column
3. Run a test apply on VPS — confirm `add_init_script` uses the DB values
4. Check that the injected values match what AdsPower would report natively

---

## Cross-Reference Checklist

- [ ] All 19 profiles have fingerprint data in Supabase
- [ ] `playwright_indeed.py` reads `profile["fingerprint"]` and injects dynamically
- [ ] Hardcoded defaults remain as fallback for empty/missing fingerprint
- [ ] WebGL vendor/renderer match AdsPower's generated values (not hardcoded NVIDIA)
- [ ] Battery API and Permissions API patches are KEPT (AdsPower doesn't handle those)
- [ ] `navigator.webdriver = undefined` patch is KEPT (AdsPower doesn't handle this)

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `scripts/read_fingerprints.py` | **CREATE** — reads fingerprints from all 19 profiles |
| `src/playwright_indeed.py` | **MODIFY** — dynamic init_script from profile.fingerprint |
| Supabase `adspower_profiles` | **ALTER** — add `fingerprint jsonb` column |

---

## Important Notes

- Run `read_fingerprints.py` from **Mac only** (AdsPower desktop app needed)
- VPS AdsPower is headless — fingerprint values may differ from Mac
- After reading fingerprints, the VPS script reads them from Supabase, so it works anywhere
- Re-run `read_fingerprints.py` if you create new profiles or change AdsPower settings
