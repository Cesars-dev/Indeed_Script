# VPS AdsPower Debug Session — 2026-03-13

> Full debug log: SunBrowser kernel → CF stealth bypass → first successful VPS application

---

## Phase 1: SunBrowser Kernel Issue

### Problem
All 19 profiles returned: `"SunBrowser 142 is not ready, please to download!"`

### Root Cause
- Profiles were configured for Chrome **142** (macOS-only kernel)
- VPS has Chrome **134** at `/root/.config/adspower_global/cwd_global/chrome_134/`
- Directory is root-owned — `julio` user couldn't see it (`sudo ls` required)
- Chrome 134 was auto-installed when AdsPower was first set up (~Feb 2026)

### What Didn't Work
| Approach | Result |
|----------|--------|
| `--remote-debugging-port` launch arg | Breaks Chrome 142 — "not ready" error |
| Mac tunnel with fixed/dynamic port | Random CDP ports break the tunnel every restart |
| VNC into Xvfb to download 142 via GUI | `--headless=true` renders nothing (black screen) |
| CDN URL from binary `strings` | No kernel download URLs in the binary |
| `/api/v1/env/download-sun-browser` | Endpoint does not exist (404) |
| `ua_auto` kernel version | Still resolves to 142 |
| Extracting Electron app.asar for CDN URLs | Obfuscated, no clear URLs found |

### Fix
```bash
# Update profile to Chrome 134 via API
curl -s -X POST "http://127.0.0.1:30025/api/v1/user/update?api_key=KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"PROFILE_ID","fingerprint_config":{"browser_kernel_config":{"version":"134","type":"chrome"}}}'

# Batch all 19 profiles (rate limit: 1 req/sec)
```

---

## Phase 2: Cloudflare Turnstile Block

### Problem
After fixing the kernel, profiles launched but CF challenged every request with "Additional Verification Required" + Turnstile checkbox.

### Gemini CF Solver
Built `_solve_cf()` — Gemini-powered:
1. Takes screenshot → sends to Gemini
2. Gemini returns `{"action": "click", "x": 348, "y": 218}`
3. Playwright clicks with human-like Bezier mouse movement
4. Retries up to 6 times

**Result:** Gemini correctly found and clicked the checkbox 6 times — but CF kept re-challenging. The checkbox click worked; the IP reputation was the issue.

### RAG Research: The Real Blockers
Perplexity RAG identified two fixable issues beyond IP:

1. **CDP `Runtime.enable` leak** — Playwright auto-fires `Runtime.enable` on connect, which wraps `console` methods. Cloudflare detects this wrapper as automation signal.
2. **Xvfb display fingerprints** — `devicePixelRatio=1`, wrong screen sizes, no GPU, no battery API. All detectable by CF's JS probes.

### Fix: Stealth Init Script
Added comprehensive anti-detection patches to `context.add_init_script()`:

```javascript
// Xvfb display fingerprint spoofing
devicePixelRatio = 2           // Xvfb returns 1
screen 1920x1080               // Xvfb defaults wrong
availHeight = 1040             // matches real browser
outerWidth/outerHeight         // Xvfb defaults wrong

// VPS hardware spoofing 
hardwareConcurrency = 8        // VPS shows 1-2 vCPUs
deviceMemory = 8               // VPS shows low values

// GPU renderer (hide llvmpipe/SwiftShader)
WebGL UNMASKED_VENDOR = "Google Inc. (NVIDIA)"
WebGL UNMASKED_RENDERER = "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060, OpenGL 4.5)"

// CDP Runtime.enable leak protection
console methods locked with Object.defineProperty (set: () => {})
Prevents CDP from wrapping console.log/warn/error

// Battery API (VPS returns null → dead giveaway)
navigator.getBattery() → faked charging response

// Permissions API patch
// navigator.webdriver = undefined (was already there)
```

Also added CDP-level `Runtime.disable` call after connect.

### Result: ✅ CF BYPASS SUCCESSFUL
With stealth patches applied, the clean profile `k19td50a`:
- **No Turnstile challenge appeared**
- Job page loaded normally
- Apply button clicked
- SmartApply opened → filled 9 steps before timeout

---

## Phase 3: Application Test Run (Profile k19td50a)

### Run Log
```
step 00 → profile-location → Continue (pre-filled) ✅
step 01 → resume-selection → Uploaded resume_oswaldo.pdf ✅
step 02 → resume-selection → Scroll down ✅
step 03 → resume-selection → Continue (Pro escalation) ✅
step 04 → questions/1 → "authorized to work? Yes" ❌ element not found
step 05 → questions/1 → same retry ❌ element not found
step 06 → questions/1 → fill "Customer service: 4 years" ✅ (Pro)
step 07 → questions/1 → fill "Medical terminology: 3 years" ✅ (Pro)
step 08 → questions/1 → fill "Computer skills: 4 years" ✅ (Pro)
step 09 → questions/1 → (timeout at 300s)
```

### Performance Issue: ~33s per step
- **Pro model overuse** — escalated at step 3, stayed on Pro for steps 6–9 because URL never changed (`questions/1` is the same for all questions)
- **Failed clicks wasted 2 steps** — Gemini tried clicking text labels instead of radio buttons
- **Fix needed:** Pro should reset after each successful action, not only on URL change

---

## Code Changes This Session

### `src/playwright_indeed.py`
1. **`_solve_cf()`** — Gemini-powered Turnstile solver (screenshot → find checkbox → Bezier click)
2. **Stealth init script** — 70+ lines of anti-detection JS patches
3. **CDP `Runtime.disable`** — sent after connect to undo Playwright's auto-enable
4. **Replaced 3 manual CF wait blocks** with `_solve_cf()` calls
5. **Previous session changes still in place:** dual-model Flash/Pro, simplified `_start_profile()`, removed `ADSPOWER_FIXED_PORT`

### Files Created
- `docs/adspower_kernel_prompt.md` — RAG prompt for kernel resolution
- `docs/DOE_FRAMEWORK.md` — copied from archive for reference
- `memory/06_adspower_kernel_debug.md` — this file

---

## VPS AdsPower Facts (Updated)

| Fact | Value |
|------|-------|
| API port | **30025** |
| Binary | `/opt/AdsPower Global/adspower_global` |
| Kernel path | `/root/.config/adspower_global/cwd_global/chrome_134/` |
| Available kernel | **134 only** (142 = macOS only) |
| Process | `--headless=true --api-key=KEY --api-port=30025 --no-sandbox --disable-gpu` |
| Profile count | 19 (all updated to Chrome 134) |
| ADSPOWER_BASE | `http://127.0.0.1:30025` |

---

## Next Steps

- [ ] Fix Pro model escalation — reset after successful action, not just URL change
- [ ] Reduce per-step delays for faster application
- [ ] Re-run with longer timeout (600s) to complete full application
- [ ] Enable residential proxies on profiles for extra IP safety
- [ ] Test with multiple profiles to confirm stealth patches work broadly
- [ ] Deploy to production orchestrator
