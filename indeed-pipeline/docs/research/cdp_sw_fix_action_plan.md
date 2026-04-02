# CDP Service Worker Fix — ACTION PLAN

## Change Summary

Add a new async helper `_kill_service_workers()` that uses raw CDP via WebSocket to:
1. Kill all `service_worker` type targets
2. Navigate all `page` type targets to `about:blank`
3. Sleep 1s to let Chrome settle

Then call it in `apply_to_job()` BEFORE `connect_over_cdp()`.

## File Changes

### 1. `playwright_indeed.py` — Add import (line ~17)

```python
import websockets
```

### 2. `playwright_indeed.py` — New helper function (after `_stop_profile`, ~line 161)

```python
async def _kill_service_workers(ws_url: str):
    """Kill extension service workers & blank open tabs before Playwright attaches.
    
    AdsPower profiles with browsing history have Chrome extension SWs that
    deadlock rebrowser_playwright's addBinding patch during connect_over_cdp.
    Raw CDP can kill them safely — SWs auto-restart when needed later.
    """
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            cmd_id = 1
            async def _send(method, params={}):
                nonlocal cmd_id
                await ws.send(json.dumps({"id": cmd_id, "method": method, "params": params}))
                cmd_id += 1
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("id") == cmd_id - 1:
                        return msg.get("result", {})

            result = await _send("Target.getTargets")
            targets = result.get("targetInfos", [])

            # Kill service workers
            sw_killed = 0
            for t in targets:
                if t["type"] == "service_worker":
                    await _send("Target.closeTarget", {"targetId": t["targetId"]})
                    sw_killed += 1

            # Navigate pages to about:blank (clears pending JS)
            for t in targets:
                if t["type"] == "page":
                    try:
                        r = await _send("Target.attachToTarget",
                                        {"targetId": t["targetId"], "flatten": True})
                        sid = r.get("sessionId")
                        if sid:
                            await ws.send(json.dumps({
                                "id": cmd_id, "method": "Page.navigate",
                                "params": {"url": "about:blank"}, "sessionId": sid
                            }))
                            cmd_id += 1
                    except Exception:
                        pass

            if sw_killed:
                print(f"[playwright] Killed {sw_killed} service worker(s) before CDP connect")
            await asyncio.sleep(1.0)
    except Exception as e:
        print(f"[playwright] ⚠️  SW cleanup skipped: {e}")
```

### 3. `playwright_indeed.py` — Modify CDP connect block (lines 1131-1161)

Replace the existing retry loop with:
1. Get the WebSocket URL from `profile_data`
2. Call `_kill_service_workers(ws_url)` ONCE before connecting
3. Keep a simplified retry (1 retry only, no browser restart needed since SWs are dead)
4. Remove `slow_mo=50` (not needed, adds latency)

```python
    page = None
    try:
        async with async_playwright() as pw:
            # ── Kill service workers before CDP connect ───────────────
            ws_url = profile_data.get("ws", {}).get("puppeteer", "")
            if ws_url:
                await _kill_service_workers(ws_url)

            # ── CDP connect (with one retry) ──────────────────────────
            browser = None
            for cdp_attempt in range(2):
                try:
                    browser = await pw.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{debug_port}",
                        timeout=15000
                    )
                    break
                except Exception as cdp_err:
                    if cdp_attempt == 1:
                        raise cdp_err
                    print(f"[playwright] ⚠️  CDP connect attempt 1/2 timed out — retrying...")
                    await asyncio.sleep(2)
```

## What This Does NOT Change

- No change to fingerprint config, stealth scripts, or form handling
- No change to `_start_profile()` or `_stop_profile()`
- No change to environment variable (`addBinding` mode stays)
- No new dependencies (websockets already installed)
