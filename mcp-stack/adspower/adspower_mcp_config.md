# AdsPower API Config — Indeed Auto-Apply

Two instances of AdsPower share the same account. Same API key, same profiles, same groups.

> **API Key:** `6690380481d7de70c40230dca72e9403005bda7f364e3e6f`

---

## ⚡ Quick Reference — Which Port to Use

| You are on… | Port | Endpoint |
|-------------|------|----------|
| **VPS** (`root@45.55.90.156`) | `30025` | `http://localhost:30025` |
| **Mac** (local desktop) | `50325` | `http://localhost:50325` |
| **VPS → Mac** (via reverse tunnel) | `50325` | `http://localhost:50325` |

### Key Difference

- **Port `30025`** — AdsPower runs **natively on the VPS** via systemd (headless, `xvfb`). Always on. The pipeline uses this port.
- **Port `50325`** — AdsPower runs **natively on Mac** (desktop GUI). Reachable from VPS only when the **reverse SSH tunnel** is active.

---

## 🔗 Tunnel Status — ALWAYS ON

The Mac → VPS reverse tunnel is **persistent** via `autossh` running on the Mac. It auto-reconnects on sleep/wake, network changes, and SSH drops.

> **🟢 Assume the tunnel is UP.** Don't try to create new tunnels or workarounds. Just verify and use it.

### Verify (from VPS)

```bash
# Should return {"code":0, "data":{...}, "msg":"Success"}
curl -s "http://localhost:50325/api/v1/user/list?page=1&page_size=1&api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
```

If `Connection refused` → the tunnel is down. **Do NOT create workarounds.** Ask the user to re-run on their Mac:

```bash
autossh -M 0 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -fN -R 50325:localhost:50325 root@45.55.90.156
```

> `autossh` is already installed on Mac (`brew install autossh` — done). The `-f` flag backgrounds it so it survives terminal close. For full reboot survival, use a macOS LaunchAgent (see `infrastructure.md`).

---

## 📡 API Endpoints

All endpoints use GET. Append `api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f` to every request.

### Status Check

```bash
curl -s "http://localhost:30025/api/v1/status?api_key=API_KEY"
# {"code":0,"msg":"success"}
```

### List Profiles

```bash
# All profiles
curl -s "http://localhost:30025/api/v1/user/list?page=1&page_size=50&api_key=API_KEY"

# Filter by group
curl -s "http://localhost:30025/api/v1/user/list?group_id=8765960&page=1&page_size=50&api_key=API_KEY"
```

### List Groups

```bash
curl -s "http://localhost:30025/api/v1/group/list?page=1&page_size=50&api_key=API_KEY"
```

### Start / Stop Browser

```bash
# Start (GET, not POST!)
curl -s "http://localhost:30025/api/v1/browser/start?user_id=USER_ID&api_key=API_KEY"
# Returns: {"code":0,"data":{"debug_port":"XXXXX","webdriver":"..."}}

# Stop
curl -s "http://localhost:30025/api/v1/browser/stop?user_id=USER_ID&api_key=API_KEY"

# Check if active
curl -s "http://localhost:30025/api/v1/browser/active?user_id=USER_ID&api_key=API_KEY"
```

### Update Profile (POST)

```bash
# Update proxy
curl -s -X POST "http://localhost:30025/api/v1/user/update?api_key=API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER_ID",
    "user_proxy_config": {
      "proxy_soft": "other",
      "proxy_type": "socks5",
      "proxy_host": "130.180.232.135",
      "proxy_port": "8573",
      "proxy_user": "lehavxelstaticresidential",
      "proxy_password": "4lzagcbkv7t9"
    }
  }'
```

### Move Profile to Group (POST)

```bash
# NOTE: /user/update does NOT change group — use /user/regroup
curl -s -X POST "http://localhost:30025/api/v1/user/regroup?api_key=API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["USER_ID"], "group_id": "8945747"}'
```

---

## 🚨 Gotchas

### 1. `browser/start` is GET, not POST
```bash
# ✅ Correct
curl "http://localhost:30025/api/v1/browser/start?user_id=ID&api_key=KEY"
# ❌ Wrong — will fail
curl -X POST "http://localhost:30025/api/v1/browser/start" -d '{"user_id":"ID"}'
```

### 2. `/user/update` does NOT change group
The `group_id` field in `/user/update` is silently ignored. Use `/user/regroup` to move profiles between groups.

### 3. CDP port is dynamic
`browser/start` returns a `debug_port` that changes each time. Always read it from the response:
```python
data = requests.get(f"{BASE}/api/v1/browser/start?user_id={uid}&api_key={key}").json()
debug_port = data["data"]["debug_port"]
# Connect Playwright: rebrowser_playwright.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
```

### 4. `tab[0]` is AdsPower internal
Never interact with `tab[0]` — it's AdsPower's internal page. Always work on `tab[1]` or later.

### 5. Verify CDP is alive before connecting
AdsPower sometimes returns a debug port that isn't responding. Always verify:
```python
requests.get(f"http://127.0.0.1:{debug_port}/json/version", timeout=5)
```

---

## 📋 Groups

| Group Name | group_id | Profiles | Notes |
|------------|----------|----------|-------|
| `indeed` | `8765960` | 13 (slots 1–12, 19) | Main pipeline profiles |
| `residential_indeed` | `8945747` | 6 (slots 13–18) | Originally separated, all residential |

---

## 🔑 Proxy Credentials

All profiles now use **residential** SOCKS5 proxies.

| Type | Username | Password | Port Format |
|------|----------|----------|-------------|
| Residential | `lehavxelstaticresidential` | `4lzagcbkv7t9` | Varies per IP |
| Datacenter (backup) | `lehavxel` | `4lzagcbkv7t9` | Varies per IP |

---

## 🖥️ VPS → Mac Interaction (Bulletproof Guide)

> **You are on the VPS** (`/home/julio/...`). Mac AdsPower is at `localhost:50325` via reverse tunnel.
> The tunnel must be active (user runs `ssh -R 50325:localhost:50325 -N root@45.55.90.156` on Mac).

### Step 1: Verify Tunnel is Alive

Always check before doing anything on port `50325`:

```python
import requests

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
MAC = "http://localhost:50325"
VPS = "http://localhost:30025"

# Quick tunnel health check
try:
    r = requests.get(f"{MAC}/api/v1/status?api_key={API_KEY}", timeout=5)
    if r.json().get("code") == 0:
        print("✅ Mac tunnel is UP")
    else:
        print("❌ Mac responded but with error")
except requests.exceptions.ConnectionError:
    print("❌ Tunnel is DOWN — ask user to run SSH tunnel on Mac")
except requests.exceptions.ReadTimeout:
    print("❌ Tunnel timeout — tunnel may be stale, ask user to restart")
```

If the tunnel is down, tell the user to run on their Mac:
```bash
ssh -R 50325:localhost:50325 -N root@45.55.90.156
```

### Step 2: Use Python `requests` (NOT curl)

The `.env` files have passwords with special characters (`!`, `@`, `$`). **Always use Python**, never bash `curl` with inline variables.

```python
# Use PYTHONPATH for the venv, and explicitly load .env via dotenv
# Command prefix for all scripts:
# cd /home/julio/projects/Indeed_Script/indeed-pipeline && PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -c "..."
```

### Step 3: Proven Patterns (copy-paste ready)

#### List All Profiles (Both Groups)

```python
import requests

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
BASE = "http://localhost:50325"  # Mac

# Don't filter by group — get ALL profiles
all_profiles = []
for page in range(1, 5):
    r = requests.get(f"{BASE}/api/v1/user/list?page={page}&page_size=50&api_key={API_KEY}", timeout=10)
    batch = r.json().get("data", {}).get("list", [])
    all_profiles.extend(batch)
    if len(batch) < 50:
        break

# Filter to Indeed-related
for p in sorted(all_profiles, key=lambda x: int(x.get('serial_number', '0'))):
    if 'indeed' in p.get('group_name', '').lower():
        proxy = p.get('user_proxy_config', {})
        print(f"  {p['serial_number']} | {p['user_id']} | {proxy.get('proxy_host','')}:{proxy.get('proxy_port','')} | {p['name']}")
```

> ⚠️ **Gotcha:** Filtering by `group_id` sometimes returns 0 for the `residential_indeed` group (API pagination bug). When listing profiles, **omit the group filter** and filter in Python instead.

#### Update Proxy on a Profile

```python
import requests

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
BASE = "http://localhost:50325"  # Mac

r = requests.post(f"{BASE}/api/v1/user/update?api_key={API_KEY}", json={
    "user_id": "k1a2vuom",
    "user_proxy_config": {
        "proxy_soft": "other",
        "proxy_type": "socks5",
        "proxy_host": "130.180.232.135",
        "proxy_port": "8573",           # STRING, not int
        "proxy_user": "lehavxelstaticresidential",
        "proxy_password": "4lzagcbkv7t9"
    }
}, timeout=10)

assert r.json().get("code") == 0, f"Update failed: {r.json()}"
```

> ⚠️ **Gotcha:** `proxy_port` must be a **string** in the AdsPower API payload, even though Supabase stores it as an int.

#### Move Profile Between Groups

```python
import requests

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
BASE = "http://localhost:50325"  # Mac

# ❌ WRONG — /user/update silently ignores group_id
# requests.post(f"{BASE}/api/v1/user/update?api_key={API_KEY}", json={"user_id": "ID", "group_id": "8945747"})

# ✅ CORRECT — use /user/regroup
r = requests.post(f"{BASE}/api/v1/user/regroup?api_key={API_KEY}", json={
    "user_ids": ["k1a2vuom"],
    "group_id": "8945747"       # residential_indeed
}, timeout=10)

assert r.json().get("code") == 0, f"Regroup failed: {r.json()}"
```

#### Batch: Assign Proxies to All Profiles

Proven pattern that updates AdsPower + Supabase + proxy table in one script:

```python
import os, requests
from dotenv import load_dotenv
load_dotenv(dotenv_path='/home/julio/projects/Indeed_Script/indeed-pipeline/.env', override=True)

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
MAC = "http://localhost:50325"
url = os.getenv("SUPABASE_URL")
skey = os.getenv("SUPABASE_SERVICE_KEY")
h = {"apikey": skey, "Authorization": f"Bearer {skey}", "Content-Type": "application/json"}

# 1. Get available proxies from Supabase
proxies = requests.get(f"{url}/rest/v1/residential_proxies?in_use=eq.false&select=*&order=id.asc",
                       headers=h, timeout=10).json()

# 2. Get profiles from AdsPower (Mac)
profiles = []
for page in range(1, 5):
    r = requests.get(f"{MAC}/api/v1/user/list?page={page}&page_size=50&api_key={API_KEY}", timeout=10)
    batch = r.json().get("data", {}).get("list", [])
    profiles.extend([p for p in batch if "indeed" in p.get("group_name", "").lower()])
    if len(batch) < 50: break

# 3. Assign one proxy per profile
for i, profile in enumerate(profiles):
    if i >= len(proxies): break
    proxy = proxies[i]
    uid = profile["user_id"]

    # Update AdsPower
    requests.post(f"{MAC}/api/v1/user/update?api_key={API_KEY}", json={
        "user_id": uid,
        "user_proxy_config": {
            "proxy_soft": "other", "proxy_type": "socks5",
            "proxy_host": proxy["proxy_address"],
            "proxy_port": str(proxy["port"]),        # STRING!
            "proxy_user": proxy["username"],
            "proxy_password": proxy["password"]
        }
    }, timeout=10)

    # Update Supabase adspower_profiles
    requests.patch(f"{url}/rest/v1/adspower_profiles?user_id=eq.{uid}",
        json={"proxy_address": proxy["proxy_address"], "proxy_port": proxy["port"], "proxy_type": "residential"},
        headers={**h, "Prefer": "return=minimal"}, timeout=10)

    # Mark proxy as in use
    requests.patch(f"{url}/rest/v1/residential_proxies?id=eq.{proxy['id']}",
        json={"in_use": True, "assigned_to": uid},
        headers={**h, "Prefer": "return=minimal"}, timeout=10)

    print(f"  ✅ {uid} → {proxy['proxy_address']}:{proxy['port']}")
```

### Step 4: Cross-Reference Verify (AdsPower ↔ Supabase)

After any bulk update, always verify both systems match:

```python
import os, requests
from dotenv import load_dotenv
load_dotenv(dotenv_path='/home/julio/projects/Indeed_Script/indeed-pipeline/.env', override=True)

API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
MAC = "http://localhost:50325"
url = os.getenv("SUPABASE_URL")
skey = os.getenv("SUPABASE_SERVICE_KEY")
h = {"apikey": skey, "Authorization": f"Bearer {skey}"}

# Get AdsPower state
ads = {}
for page in range(1, 5):
    r = requests.get(f"{MAC}/api/v1/user/list?page={page}&page_size=50&api_key={API_KEY}", timeout=10)
    for p in r.json().get("data", {}).get("list", []):
        if "indeed" in p.get("group_name", "").lower():
            proxy = p.get("user_proxy_config", {})
            ads[p["user_id"]] = (proxy.get("proxy_host", ""), proxy.get("proxy_port", ""))
    if len(r.json().get("data", {}).get("list", [])) < 50: break

# Get Supabase state
sb = requests.get(f"{url}/rest/v1/adspower_profiles?select=user_id,proxy_address,proxy_port&order=account_slot.asc",
                  headers=h, timeout=10).json()

# Compare
for sp in sb:
    uid = sp["user_id"]
    ap = ads.get(uid, ("?", "?"))
    match = (sp.get("proxy_address", "") == ap[0] and str(sp.get("proxy_port", "")) == str(ap[1]))
    icon = "✓" if match else "✗ MISMATCH"
    print(f"  {icon} {uid} | SB={sp.get('proxy_address','')}:{sp.get('proxy_port','')} | ADS={ap[0]}:{ap[1]}")
```

---

## 🔑 Summary — What Works, What Doesn't

| Action | Method | Port | Endpoint | Notes |
|--------|--------|------|----------|-------|
| List profiles | GET | 50325 | `/api/v1/user/list` | Omit `group_id` filter, filter in Python |
| Update proxy | POST | 50325 | `/api/v1/user/update` | `proxy_port` must be **string** |
| Move to group | POST | 50325 | `/api/v1/user/regroup` | NOT `/user/update` — that silently ignores `group_id` |
| List groups | GET | 50325 | `/api/v1/group/list` | Returns `group_id` + `group_name` |
| Start browser | GET | **30025** | `/api/v1/browser/start` | **VPS only** — can't launch Mac browsers via tunnel |
| Stop browser | GET | **30025** | `/api/v1/browser/stop` | **VPS only** |

> **Critical:** `browser/start` and `browser/stop` only work on port **30025** (VPS). You cannot start/stop Mac browsers from the VPS — the tunnel only proxies API calls, not GUI rendering.

