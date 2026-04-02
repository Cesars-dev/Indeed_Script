# Directive: Infrastructure

> Development happens ON the VPS. Mac AdsPower is accessible via reverse SSH tunnel for GUI management.

## Credentials & Endpoints

| Service | Value |
|---------|-------|
| VPS | `root@45.55.90.156` (SSH key, no password) |
| AdsPower API key | `6690380481d7de70c40230dca72e9403005bda7f364e3e6f` |
| AdsPower VPS | `http://localhost:30025` — headless, systemd |
| AdsPower Mac | `http://localhost:50325` — desktop GUI, via SSH tunnel |
| Supabase URL | `https://uckkgnqlehprbpypcgjc.supabase.co` |
| N8N webhook | `https://n8n.hvactechpulse.online/webhook/ba283c1f-9daa-4b98-a01c-ac1a1b1707dc` |
| Webshare proxies | `lehavxel` / `4lzagcbkv7t9` — datacenter; `lehavxelstaticresidential` / `4lzagcbkv7t9` — residential |
| Google Drive SA | `admin-639@n8n-conection-470104.iam.gserviceaccount.com` |
| Gemini model | `gemini-2.5-flash` — API key in `.env` |

## VPS Services (always-on)

| Service | Command | Notes |
|---------|---------|-------|
| Webhook server | `systemctl status indeed-webhook` | port 8080, auto-restart |
| Cron | `crontab -l` | `0 9 * * *` → orchestrator.py |
| AdsPower (headless) | `systemctl status adspower.service` | port **30025**, `--api-key` auth |
| Xvfb | `systemctl status xvfb.service` | Virtual display :99 — required for AdsPower GTK |

**Deploy path:** `/root/indeed-pipeline/`
**Dev path:** `/home/julio/projects/Indeed_Script/indeed-pipeline/`

## AdsPower — Dual Instance

The same AdsPower account is accessible from two locations. Both share all profiles and configuration changes sync automatically.

| Instance | Port | Purpose |
|----------|------|---------|
| **VPS** (headless) | `30025` | Pipeline execution. Always on via systemd. |
| **Mac** (desktop GUI) | `50325` | Profile management, visual debugging. Requires tunnel. |

### Mac Tunnel Setup

Run on **Mac terminal** to make Mac AdsPower reachable from VPS:

```bash
# Simple (manual — dies on sleep)
ssh -R 50325:localhost:50325 -N root@45.55.90.156

# Robust (survives sleep/disconnects)
autossh -M 0 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -fN -R 50325:localhost:50325 root@45.55.90.156
```

### Port Map

| Port | What | Status |
|------|------|--------|
| `30025` | AdsPower API (VPS-native, systemd) | ✅ Always on |
| `50325` | Mac AdsPower (via reverse SSH tunnel) | ✅ When tunnel is up |
| `20725` | Ghost-locked by AdsPower internal JS | ❌ NEVER use |

### Health Check

```bash
# VPS
curl -s "http://localhost:30025/api/v1/status?api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"

# Mac (requires tunnel)
curl -s "http://localhost:50325/api/v1/status?api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
```

### Binary & Paths
- Binary: `/opt/AdsPower Global/adspower_global` (space in path)
- Symlink: `/usr/local/bin/adspower_global` → binary (for systemd)
- SunBrowser kernel: `chrome_134` at `~/.config/adspower_global/cwd_global/chrome_134/`
- Profile data: `~/.config/adspower_global/`
- Singleton locks: `rm -f /root/.config/adspower_global/Singleton*` before restart

### Control

```bash
# All run locally on VPS
systemctl start xvfb && systemctl start adspower   # start
systemctl stop adspower && systemctl stop xvfb      # stop
systemctl status adspower xvfb                      # check
bash scripts/vps_adspower.sh diagnose               # full dump
```

### ⚠️ Pre-Pipeline: Restart AdsPower

**Before running the pipeline**, restart AdsPower to clear stale browser state:

```bash
sudo systemctl stop adspower
sleep 2
sudo rm -f /root/.config/adspower_global/Singleton*
sudo systemctl start adspower
sleep 15
# Verify it's up:
curl -s "http://localhost:30025/api/v1/user/list?api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f&page=1&page_size=1"
```

**Why:** Stale browser sessions (old tabs from previous runs) cause `Page.goto` timeouts and CDP hangs. A fresh AdsPower start ensures clean profile launches.

### ⚠️ Proxy Diagnostics — DO NOT use curl/nc

**NEVER test Webshare SOCKS5 proxies with `curl --proxy` or `nc` from the VPS.**
These give **false negatives** — the VPS OS network stack cannot reach certain residential IPs directly, but AdsPower's internal Chrome network layer routes through them fine.

**Correct way to test a proxy:**
1. Launch the profile via AdsPower API (`/api/v1/browser/start`)
2. Check `/api/v1/browser/active` for a valid `debug_port`
3. Connect via raw CDP websocket → `Target.getTargets` → check loaded pages

If the browser has pages loaded → proxy works. If `debug_port` is empty → proxy is actually dead.

## Profile Data — Source of Truth

Profiles are loaded **from Supabase at runtime** by `playwright_indeed.py` → `_load_profiles()`.
There is no JSON file. Supabase is the single source of truth for all profile data.

```python
# How profiles load (playwright_indeed.py line 50-70)
def _load_profiles():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/adspower_profiles", params={"select": "*"}, headers=HEADERS)
    return {row["user_id"]: row for row in r.json()}
```

## Proxies — All Residential

As of 2026-03-16, **all 19 profiles use residential SOCKS5 proxies** from Webshare.

### Residential Proxy List URL (Webshare)

> **Download all 20 static residential proxies:**
> ```
> https://proxy.webshare.io/api/v2/proxy/list/download/nzufhidpezowsiiusylyitasjbbxxzjpjkakrryg/-/any/username/direct/-/?plan_id=12968926
> ```
> Format: `ip:port:username:password` — all use `lehavxelstaticresidential` / `4lzagcbkv7t9`

### Health Check (2026-03-17)

**10 alive / 10 dead** from VPS. Dead proxies are NOT reachable via TCP from VPS.

| IP:Port | Status | Assigned To |
|---------|--------|-------------|
| 130.180.232.135:8573 | ✅ | Slot 17 |
| 199.187.189.141:6932 | ✅ | Slot 15 |
| 216.98.254.195:6505 | ✅ | Slot 14 |
| 192.53.142.104:5801 | ✅ | Slot 1 |
| 72.1.154.5:7896 | ✅ | Slot 3 |
| 198.145.103.182:6439 | ✅ | Slot 6 |
| 72.1.154.232:8123 | ✅ | Slot 8 |
| 103.130.178.44:5708 | ✅ | Slot 10 (active) |
| 192.145.71.197:6834 | ✅ | Slot 18 |
| 130.180.236.19:6024 | ✅ | unassigned |
| 9.142.46.112:6781 | ❌ | **Slot 9 (active)** |
| 9.142.198.212:5879 | ❌ | **Slot 11 (active)** |
| 138.226.88.247:7935 | ❌ | **Slot 12 (active)** |
| 9.142.10.173:5829 | ❌ | **Slot 19 (active)** |
| 9.142.41.178:6348 | ❌ | Slot 16 |
| 45.58.228.186:5858 | ❌ | Slot 13 |
| 9.142.210.118:5783 | ❌ | Slot 2 |
| 138.226.77.104:7293 | ❌ | Slot 4 |
| 138.226.71.59:7249 | ❌ | Slot 5 |
| 9.142.47.5:6174 | ❌ | Slot 7 |

**Action needed:** Reassign dead-proxy profiles (slots 9, 11, 12, 19) to alive proxies from the pool above. Update in AdsPower (Mac GUI) + Supabase.

### Proxy Tables

| Table | Count | Type | Status |
|-------|-------|------|--------|
| `residential_proxies` | 20 | Webshare residential SOCKS5 | 19 in use, 1 spare |
| `proxies` | 100 | Webshare datacenter SOCKS5 | **Not assigned** — kept as backup |

### Proxy Credentials

| Type | Username | Password | Protocol |
|------|----------|----------|----------|
| Datacenter | `lehavxel` | `4lzagcbkv7t9` | SOCKS5 |
| Residential | `lehavxelstaticresidential` | `4lzagcbkv7t9` | SOCKS5 |

## AdsPower Groups

| Group | group_id | Profiles | Proxy Type |
|-------|----------|----------|------------|
| `indeed` | `8765960` | 13 (slots 1–12, 19) | Residential |
| `residential_indeed` | `8945747` | 6 (slots 13–18) | Residential |

## Supabase Tables

| Table | Purpose |
|-------|---------|
| `adspower_profiles` | 19 profiles: user_id, email, proxy, phone, applicant data, proxy_type, fingerprint |
| `executions` | Pipeline execution log (1 row per apply_to_job call) |
| `test_run_logs` | Dev/batch test results |
| `applied_jobs` | Dedup log: job_id, status, company, title |
| `apply_runs` | Apply run summaries |
| `apply_step_log` | Step-by-step execution log |
| `apply_patterns` | P8 learning loop: Gemini Q&A patterns |
| `search_combinations` | 10 rows: position × state, drives N8N daily scrape |
| `proxies` | 100 datacenter proxies (backup — not currently assigned) |
| `residential_proxies` | 20 residential proxies, `in_use` boolean, `assigned_to` = user_id |
| `gmail_accounts` | 23 Gmail accounts: email, password, adspower_user_id, status |

## AdsPower Profile Map (19 profiles — all residential)

| Slot | user_id | Email | Residential Proxy | Group |
|------|---------|-------|-------------------|-------|
| 1 | k19td4st | gabrielalopezgomez80@gmail.com | 192.53.142.104:5801 | indeed |
| 2 | k19td4tu | alexeishon2@gmail.com | 9.142.210.118:5783 | indeed |
| 3 | k19td4uh | garciaramosjonathan8@gmail.com | 72.1.154.5:7896 | indeed |
| 4 | k19td4v5 | yoshiporfirioyoshio@gmail.com | 138.226.77.104:7293 | indeed |
| 5 | k19td4vp | gutierrezramirezhectormanuel6@gmail.com | 138.226.71.59:7249 | indeed |
| 6 | k19td4wc | martinezmedinajonathan975@gmail.com | 198.145.103.182:6439 | indeed |
| 7 | k19td4x8 | clarasanchezvillela@gmail.com | 9.142.47.5:6174 | indeed |
| 8 | k19td4xs | alisfleet@gmail.com | 72.1.154.232:8123 | indeed |
| 9 | k1a2vu6e | abrahamibarrapadilla297@gmail.com | 9.142.46.112:6781 | indeed |
| 10 | k19td50a | oswaldin.lara@gmail.com | 103.130.178.44:5708 | indeed |
| 11 | k1a2vul9 | alejandralizzete@gmail.com | 9.142.198.212:5879 | indeed |
| 12 | k1a2vun1 | angelivanlopez72@gmail.com | 138.226.88.247:7935 | indeed |
| 13 | k1a2vuna | ellukistrike@gmail.com | 45.58.228.186:5858 | residential_indeed |
| 14 | k1a2vuni | erickssson528@gmail.com | 216.98.254.195:6505 | residential_indeed |
| 15 | k1a2vuno | fmgutierrez123@gmail.com | 199.187.189.141:6932 | residential_indeed |
| 16 | k1a2vuny | jonathanjonadidi@gmail.com | 9.142.41.178:6348 | residential_indeed |
| 17 | k1a2vuom | limonrangel308@gmail.com | 130.180.232.135:8573 (**New York**) | residential_indeed |
| 18 | k1a2vuov | mconchita521@gmail.com | 192.145.71.197:6834 | residential_indeed |
| 19 | k1a2vupc | rodriguesmurillogabriela@gmail.com | 9.142.10.173:5829 | indeed |

Password all: `Simonala123` (some: `simonala123`)

## MCP Connections

> **Before querying Supabase or Firecrawl, read the corresponding MD file in `mcp-stack/`.**

| Service | Config MD | Quick Reference |
|---------|-----------|-----------------|
| **Supabase** | `mcp-stack/supabase/supabase_mcp_config.md` | REST for DML, npx MCP for DDL |
| **Firecrawl** | `mcp-stack/firecrawl/firecrawl_mcp_config.md` | npx stdio or REST API |
