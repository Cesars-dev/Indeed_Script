# AdsPower SunBrowser Kernel — Headless VPS Resolution

## Role

You are an AdsPower infrastructure specialist. You have deep knowledge of AdsPower Global's headless deployment, SunBrowser kernel management, API internals, and cross-platform synchronization between Mac and Linux instances.

## Context

I operate an AdsPower Global instance on a **headless Ubuntu 22.04 VPS** (DigitalOcean). The instance manages 19 browser profiles used for automated job applications. A second AdsPower instance runs on a **macOS workstation** (same license/account). Both share profile data.

## Current State

### VPS Instance (production — broken)
```
Binary:       /usr/local/bin/adspower_global
Process:      PID 1236
Launch cmd:   adspower_global --headless=true --api-key=<KEY> --api-port=30025 --no-sandbox --disable-gpu
Display:      Xvfb :99 (active)
OS:           Ubuntu 22.04 x86_64
Kernel dir:   ~/.config/adspower_global/cwd_global/ → EMPTY (no browser kernels)
API status:   ✅ responds on http://127.0.0.1:30025
Profiles:     ✅ 19 profiles visible via /api/v1/user/list
```

### Mac Instance (development — working)
```
Kernel path:  ~/Library/Application Support/adspower_global/cwd_global/chrome_142/
Chrome 142:   ✅ downloaded and working
All 19 profiles: ✅ launch successfully from GUI and API
```

## The Problem

Every call to start a browser profile on the **VPS** fails:

```bash
GET http://127.0.0.1:30025/api/v1/browser/start?user_id=k1a2vupc&api_key=<KEY>

Response: {"code": -1, "msg": "SunBrowser 142 is not ready, please to download!"}
```

This happens because:
1. Profiles are configured to use **SunBrowser (Chrome) 142**
2. The VPS has **zero browser kernels** in its `cwd_global/` directory
3. Previously, `chrome_134` existed on the VPS and worked — it was lost (likely after an AdsPower update or reinstall)

## What I Need — Prioritized

### Priority 1: Install SunBrowser on VPS

Provide the **exact steps** to get a working SunBrowser kernel onto the headless VPS. Explore these approaches in order:

**Option A — API-based download**
- Is there an AdsPower REST API endpoint to trigger a kernel download? (e.g., `/api/v1/env/download-sun-browser`, `/api/v1/browser/download`, or similar)
- If yes: provide the exact `curl` command with required parameters
- Note: I already tried `GET /api/v1/env/download-sun-browser?version=142` → returned 404

**Option B — Cross-platform kernel transfer**
- Can I `scp` the kernel directory from Mac → VPS?
  - Mac source: `~/Library/Application Support/adspower_global/cwd_global/chrome_142/`
  - VPS target: `~/.config/adspower_global/cwd_global/chrome_142/`
- Will a macOS-compiled Chromium binary work on Linux x86_64? (likely NO — need Linux build)
- If not: where does AdsPower download Linux kernels from? Can I wget them directly?

**Option C — Use system Chromium as fallback**
- Can AdsPower be configured to use the system's `/usr/bin/chromium-browser` or a standalone Chrome binary instead of SunBrowser?
- If yes: what config file or API parameter controls this?

### Priority 2: Version alignment

- How do I change all 19 profiles to use a **specific kernel version** (e.g., 134 instead of 142) via the API?
- Relevant endpoint: `POST /api/v1/user/update` with `fingerprint_config.browser_kernel_config.version`?
- Provide the exact `curl` command to batch-update all profiles

### Priority 3: Prevention

- How do I prevent this from happening again after AdsPower updates?
- Is there an auto-download setting for headless mode?
- Does `--headless=true` disable auto-download of new kernels?

## Constraints

- **No GUI access** — VPS is headless, Xvfb provides virtual display but AdsPower GUI is not usable interactively
- **API-only operations** — all management must be via REST API or CLI
- **Linux x86_64 binaries only** — macOS binaries won't work on VPS
- **Same license/account** — both Mac and VPS AdsPower instances share the same credential

## Expected Output Format

For each option, provide:
1. **Feasibility** — will this work? yes/no/maybe
2. **Exact commands** — copy-paste ready `curl` or `bash` commands
3. **Verification** — how to confirm the kernel is installed and working
4. **Caveats** — any risks or side effects
