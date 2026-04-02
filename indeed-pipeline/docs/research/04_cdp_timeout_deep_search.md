# CDP connect_over_cdp Timeout — Deep Search Prompt

## The Problem

`rebrowser_playwright.connect_over_cdp()` hangs indefinitely on the WebSocket handshake phase when connecting to AdsPower's headless Chrome browser. The connection never completes — it times out at 15s, 25s, even 35s.

## Environment (exact versions)

| Component | Version | Notes |
|-----------|---------|-------|
| **OS** | Ubuntu 24.04 LTS | VPS (DigitalOcean droplet) |
| **Python** | 3.13 | via `venv_local/` |
| **rebrowser-playwright** | 1.52.0 | `pip install rebrowser-playwright` |
| **rebrowser-playwright-core** | 1.52.0 | bundled Playwright server binary |
| **AdsPower** | Headless (systemd service) | Port 30025, `xvfb` display :99 |
| **Chrome** | 134.0.6998.36 | Managed by AdsPower (NOT system Chrome) |
| **Display** | Xvfb :99 (headless) | `systemctl start xvfb` before `adspower` |
| **REBROWSER_PATCHES_RUNTIME_FIX_MODE** | `addBinding` | Set before import, line 15 of script |

## Exact Failure Behavior

### What works ✅
1. AdsPower API responds on port 30025 → `browser/start` returns `debug_port` + WebSocket URL
2. `_cdp_alive(port)` passes → `GET http://127.0.0.1:{port}/json/version` returns HTTP 200 with Chrome version
3. **Raw Python websockets library connects instantly** (0.0s) and can send/receive CDP commands:
```python
async with websockets.connect(ws_url, open_timeout=10) as w:
    await w.send(json.dumps({'id': 1, 'method': 'Browser.getVersion'}))
    resp = await w.recv()  # returns immediately
    # result: Chrome/134.0.6998.36
```
4. On March 14 (~20 hours ago), `connect_over_cdp()` worked fine with the same library, same Chrome, same AdsPower.

### What fails ❌
```python
from rebrowser_playwright.async_api import async_playwright
async with async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        f"http://127.0.0.1:{debug_port}", timeout=30000
    )
    # ^^^ HANGS HERE — never returns, times out
```

### Playwright's own call log:
```
- <ws preparing> retrieving websocket url from http://127.0.0.1:{port}
- <ws connecting> ws://127.0.0.1:{port}/devtools/browser/{uuid}
- <ws connected> ws://127.0.0.1:{port}/devtools/browser/{uuid}
```
Note: It says `<ws connected>` but then **never proceeds to browser attachment**. The WebSocket TCP connection is established, but the Playwright server process never completes its internal CDP protocol handshake with the browser.

### What I've tested (all fail identically):
1. ❌ `connect_over_cdp(http_url, timeout=35000, slow_mo=50)` — original call
2. ❌ `connect_over_cdp(http_url, timeout=30000)` — without slow_mo
3. ❌ `connect_over_cdp(ws_url, timeout=30000)` — direct WS URL
4. ❌ With `REBROWSER_PATCHES_RUNTIME_FIX_MODE=addBinding`
5. ❌ Without any REBROWSER_PATCHES env var
6. ❌ Fresh AdsPower restart (stop → remove Singleton locks → start → wait 15s)
7. ❌ Multiple different AdsPower profiles
8. ❌ Retry loop (stop browser, start fresh, retry up to 3 times)

### What DID work in one test:
In a single diagnostic script, the **first** attempt via direct WS URL failed (30s timeout), but the **second** attempt via HTTP URL on the **same browser port** succeeded. This suggests the Playwright server process might need a "warmup" or has a bug with the first connection attempt.

## Architecture

```
Python script (async)
    └─ rebrowser_playwright 1.52.0
        └─ Playwright Server (node binary at driver/node)
            └─ WebSocket → AdsPower's Chrome 134 debug port
```

`rebrowser_playwright` bundles its own Playwright Server (`driver/node`, 120MB binary). When `async_playwright()` is called, it spawns this Node.js server process. The server then handles CDP WebSocket connections to the browser.

## Key Questions for Deep Search

1. **Is there a known issue with `rebrowser-playwright` 1.52.0 and Chrome 134.x where `connect_over_cdp` hangs after the WebSocket connects?** The WS connects (confirmed by Playwright's own log) but the browser object never resolves.

2. **Is there a Playwright Server ↔ Chrome CDP version incompatibility?** Playwright 1.52.0 expects a specific Chromium version. AdsPower ships Chrome 134.0.6998.36. If Playwright's CDP protocol version doesn't match Chrome 134's, the handshake could stall silently.

3. **Does `rebrowser-playwright` have a known bug where the first `connect_over_cdp` call always hangs but subsequent calls on the same `async_playwright()` context succeed?** I observed this behavior once — first WS attempt failed, second HTTP attempt on same port succeeded.

4. **Is there a conflict between `rebrowser-patches` (addBinding mode) and connecting to an already-running browser vs launching one?** The `connect_over_cdp` attach path is different from `browser.launch()` — do rebrowser patches interfere with the CDP attach handshake?

5. **Does `Xvfb` headless display affect CDP WebSocket handshake timing?** The browser renders to `DISPLAY=:99` (virtual framebuffer). Could Xvfb being slow to allocate shared memory cause the CDP handshake to stall?

6. **Is there a system-level limit (file descriptors, connection tracking, WebSocket buffer) that was fine yesterday but hit today?** The VPS has been running for days. Are there leaked sockets or zombie processes from previous runs blocking new connections?

7. **Has AdsPower's Chrome 134 recently auto-updated its CDP protocol version?** AdsPower may have silently updated Chrome from a version compatible with Playwright 1.52.0's CDP to one that isn't.

## What Changed Between Working (March 14) and Broken (March 16)

| Factor | March 14 (WORKED) | March 16 (BROKEN) |
|--------|-------------------|-------------------|
| Profile used | `k1a2vuov` (Maria Conchita) | `k1a2vun1`, `k1a2vupc` |
| rebrowser-playwright | 1.52.0 | 1.52.0 (unchanged) |
| Chrome | 134.0.6998.36 | 134.0.6998.36 (same) |
| AdsPower uptime | ~hours | ~1.5 days (but restarted fresh — still fails) |
| VPS uptime | ~2 days | ~4 days |
| REBROWSER_PATCHES_MODE | `addBinding` | `addBinding` |

## Potential solutions to investigate

1. **Try `playwright` instead of `rebrowser_playwright`** — does vanilla Playwright connect? If yes, the issue is in rebrowser's patches.
2. **Try an older rebrowser-playwright version** (e.g., 1.49.x) — version regression?
3. **Install `rebrowser-patches` npm package alongside** — the `.md` files mention it was installed but "patch didn't apply (version mismatch)". Maybe it's now needed?
4. **Use `browser.connect()` instead of `connect_over_cdp()`** — Playwright has two attach methods.
5. **Increase the Playwright server process timeout** — maybe the Node.js process is slow to initialize.
6. **Check VPS system state** — `ulimit -n`, `ss -s`, zombie processes, memory pressure.
