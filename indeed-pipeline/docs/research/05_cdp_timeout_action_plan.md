# CDP Timeout — Action Plan
> Source: Perplexity deep search on `04_cdp_timeout_deep_search.md`
> Created: 2026-03-16 02:51

---

## Key Findings from Deep Search

1. **Playwright 1.52.0 has a fragile `connect_over_cdp` attach sequence** that can hang after WS connects, especially with Chrome's newer remote-debugging behavior.
2. **rebrowser-patches `addBinding` mode injects CDP commands during the attach** — these may conflict with the handshake when connecting to an already-running browser (vs launching one).
3. **AdsPower extensions/policies can interfere** — Chrome extensions loaded by AdsPower profiles fire CDP events during startup that can race with Playwright's initialization.
4. **Chrome 134 may have changed remote debugging behavior** — Google has been tightening `--remote-debugging-port` behavior. Playwright 1.52.0 may not fully account for these changes.

---

## Experiments — Run in Order (fastest → slowest)

### Experiment 1: Vanilla Playwright (isolate rebrowser)

**Goal:** Does vanilla `playwright` connect? If yes → rebrowser patches are the problem.

```bash
cd /home/julio/projects/Indeed_Script/indeed-pipeline
pip install --target=/tmp/pw_test playwright==1.52.0

PYTHONPATH=/tmp/pw_test python3.13 -c "
import os, requests, time, asyncio
from dotenv import load_dotenv
load_dotenv(override=True)

base = os.getenv('ADSPOWER_BASE')
key = os.getenv('ADSPOWER_API_KEY')

r = requests.get(f'{base}/api/v1/browser/start', params={'user_id': 'k1a2vun1', 'api_key': key}, timeout=60)
port = r.json()['data']['debug_port']
print(f'Port: {port}')
time.sleep(3)

async def test():
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        print('Connecting vanilla playwright...')
        t = time.time()
        try:
            browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=20000)
            print(f'✅ CONNECTED in {time.time()-t:.1f}s')
            print(f'Pages: {len(browser.contexts[0].pages)}')
            await browser.close()
        except Exception as e:
            print(f'❌ FAILED after {time.time()-t:.1f}s: {e}')

asyncio.run(test())
requests.get(f'{base}/api/v1/browser/stop', params={'user_id': 'k1a2vun1', 'api_key': key}, timeout=10)
"
```

**If vanilla connects:** Problem is in rebrowser patches → go to Experiment 2.
**If vanilla also fails:** Problem is deeper (Chrome/system) → skip to Experiment 4.

---

### Experiment 2: Disable rebrowser patches entirely

**Goal:** Does rebrowser work with patches OFF?

```bash
cd /home/julio/projects/Indeed_Script/indeed-pipeline
PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -c "
import os
os.environ['REBROWSER_PATCHES_RUNTIME_FIX_MODE'] = '0'  # DISABLE all patches
import requests, time, asyncio
from dotenv import load_dotenv
load_dotenv(override=True)

base = os.getenv('ADSPOWER_BASE')
key = os.getenv('ADSPOWER_API_KEY')

r = requests.get(f'{base}/api/v1/browser/start', params={'user_id': 'k1a2vun1', 'api_key': key}, timeout=60)
port = r.json()['data']['debug_port']
print(f'Port: {port}')
time.sleep(3)

async def test():
    from rebrowser_playwright.async_api import async_playwright
    async with async_playwright() as pw:
        print('Connecting rebrowser (patches=0)...')
        t = time.time()
        try:
            browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=20000)
            print(f'✅ CONNECTED in {time.time()-t:.1f}s')
            await browser.close()
        except Exception as e:
            print(f'❌ FAILED after {time.time()-t:.1f}s: {e}')

asyncio.run(test())
requests.get(f'{base}/api/v1/browser/stop', params={'user_id': 'k1a2vun1', 'api_key': key}, timeout=10)
"
```

**If patches=0 connects:** → `addBinding` mode is the culprit. Solution: disable patches for `connect_over_cdp`, re-enable after connection.
**If patches=0 also fails:** → Issue is in rebrowser-playwright-core itself, not the patches.

---

### Experiment 3: Minimal AdsPower profile (no extensions)

**Goal:** Do AdsPower profile extensions interfere?

```bash
cd /home/julio/projects/Indeed_Script/indeed-pipeline
PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -c "
import os, requests, time, asyncio
os.environ['REBROWSER_PATCHES_RUNTIME_FIX_MODE'] = 'addBinding'
from rebrowser_playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv(override=True)

base = os.getenv('ADSPOWER_BASE')
key = os.getenv('ADSPOWER_API_KEY')

# Create a temporary blank profile
r = requests.post(f'{base}/api/v1/user/create', json={
    'api_key': key,
    'group_id': os.getenv('ADSPOWER_GROUP_ID', '0'),
    'name': 'test_blank_cdp',
    'user_proxy_config': {'proxy_soft': 'no_proxy'}
}, timeout=30)
user_id = r.json()['data']['id']
print(f'Created temp profile: {user_id}')

r = requests.get(f'{base}/api/v1/browser/start', params={'user_id': user_id, 'api_key': key}, timeout=60)
port = r.json()['data']['debug_port']
print(f'Port: {port}')
time.sleep(3)

async def test():
    async with async_playwright() as pw:
        print('Connecting to blank profile...')
        t = time.time()
        try:
            browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=20000)
            print(f'✅ CONNECTED in {time.time()-t:.1f}s')
            await browser.close()
        except Exception as e:
            print(f'❌ FAILED after {time.time()-t:.1f}s: {e}')

asyncio.run(test())
requests.get(f'{base}/api/v1/browser/stop', params={'user_id': user_id, 'api_key': key}, timeout=10)
# Cleanup: delete temp profile
requests.post(f'{base}/api/v1/user/delete', json={'api_key': key, 'user_ids': [user_id]}, timeout=10)
print('Cleaned up')
"
```

---

### Experiment 4: System-level checks

**Goal:** Is the VPS in a degraded state?

```bash
# File descriptors
ulimit -n
cat /proc/sys/fs/file-nr

# Zombie processes  
ps aux | grep -c defunct
ps aux | grep -i chrome | wc -l

# WebSocket / TCP state
ss -s
ss -tnp | grep -c ESTABLISHED

# Memory pressure
free -h
cat /proc/meminfo | grep -i available

# Xvfb health
DISPLAY=:99 xdpyinfo 2>&1 | head -5

# Stale AdsPower browser processes
pgrep -a SunBrowser || echo "No SunBrowser processes"
pgrep -a chrome | head -10
```

---

### Experiment 5: Profile that worked before

**Goal:** Does the March 14 profile (`k1a2vuov`) still work?

```bash
cd /home/julio/projects/Indeed_Script/indeed-pipeline
PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -c "
import os, requests, time, asyncio
os.environ['REBROWSER_PATCHES_RUNTIME_FIX_MODE'] = 'addBinding'
from rebrowser_playwright.async_api import async_playwright
from dotenv import load_dotenv
load_dotenv(override=True)

base = os.getenv('ADSPOWER_BASE')
key = os.getenv('ADSPOWER_API_KEY')

r = requests.get(f'{base}/api/v1/browser/start', params={'user_id': 'k1a2vuov', 'api_key': key}, timeout=60)
port = r.json()['data']['debug_port']
print(f'Port: {port}')
time.sleep(3)

async def test():
    async with async_playwright() as pw:
        print('Connecting k1a2vuov (worked March 14)...')
        t = time.time()
        try:
            browser = await pw.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=20000)
            print(f'✅ CONNECTED in {time.time()-t:.1f}s')
            await browser.close()
        except Exception as e:
            print(f'❌ FAILED after {time.time()-t:.1f}s: {e}')

asyncio.run(test())
requests.get(f'{base}/api/v1/browser/stop', params={'user_id': 'k1a2vuov', 'api_key': key}, timeout=10)
"
```

---

## Decision Tree

```
Exp 1: Vanilla playwright connects?
  ├─ YES → rebrowser patches are the problem
  │    └─ Exp 2: patches=0 connects?
  │         ├─ YES → addBinding mode breaks connect_over_cdp
  │         │    └─ FIX: set REBROWSER_PATCHES_RUNTIME_FIX_MODE=0
  │         │       before connect, re-enable after (or just use vanilla
  │         │       playwright for connect, rebrowser for everything else)
  │         └─ NO → rebrowser-playwright-core itself is broken
  │              └─ FIX: downgrade to rebrowser-playwright 1.49.x
  │                 or use vanilla playwright + manual stealth
  │
  └─ NO → Problem is Chrome/AdsPower/system level
       └─ Exp 4: System checks clean?
            ├─ YES → Chrome 134 CDP protocol mismatch
            │    └─ FIX: pin AdsPower Chrome version or downgrade
            │       Playwright to match
            └─ NO → Fix system issues (kill zombies, raise ulimits)
```

---

## Fastest Possible Fix (if Exp 1 confirms rebrowser is the issue)

```python
# In playwright_indeed.py, replace the connect block:

# Use vanilla playwright just for the CDP connection
import playwright.async_api as vanilla_pw

async with vanilla_pw.async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        f"http://127.0.0.1:{debug_port}", timeout=20000
    )
    # ... rest of the code works with the browser object
```

This bypasses rebrowser's patched connect_over_cdp while keeping AdsPower's fingerprint protection (which is at the browser level, not the Playwright level).
