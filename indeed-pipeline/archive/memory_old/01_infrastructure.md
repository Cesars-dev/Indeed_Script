# Memory: Infrastructure

## Credentials & Endpoints

| Service | Value |
|---------|-------|
| VPS | `root@45.55.90.156` (SSH key, no password) |
| AdsPower API (VPS native) | `http://localhost:30025` — **working port** |
| AdsPower API (Mac tunnel) | `http://localhost:50325` — legacy, needs Mac on |
| AdsPower API key | `6690380481d7de70c40230dca72e9403005bda7f364e3e6f` |
| AdsPower group | `indeed` — group_id: `8765960` |
| Supabase URL | `https://uckkgnqlehprbpypcgjc.supabase.co` |
| N8N webhook | `https://n8n.hvactechpulse.online/webhook/ba283c1f-9daa-4b98-a01c-ac1a1b1707dc` |
| Webshare proxies | `lehavxel` / `4lzagcbkv7t9` — 100 US residential SOCKS5 |
| Google Drive SA | `admin-639@n8n-conection-470104.iam.gserviceaccount.com` |
| Gemini model | `gemini-2.5-flash` — API key in `.env` |

## VPS Services (always-on)

| Service | Command | Notes |
|---------|---------|-------|
| Webhook server | `systemctl status indeed-webhook` | port 8080, auto-restart |
| Cron | `crontab -l` | `0 9 * * *` → orchestrator.py |
| AdsPower (headless) | `systemctl status adspower.service` | port **30025** (VPS-native, `--api-key` auth) |
| Xvfb | `systemctl status xvfb.service` | Virtual display :99 — required for AdsPower GTK dependency |

**Deploy path on VPS**: `/root/indeed-pipeline/`

## AdsPower Port Map (IMPORTANT)

| Port | What it is | Works? |
|------|-----------|--------|
| `30025` | VPS-native AdsPower API | ✅ **Primary port** — `--api-key` flag auth, systemd managed |
| `20725` | Ghost-locked by AdsPower internal JS | ❌ NEVER use — reports "occupied" even when nothing listens |
| `50325` | Mac AdsPower API, reverse-tunneled to VPS | ✅ Legacy — works but requires Mac to be on |

### ✅ VPS API test (use this)
```bash
# Run on VPS (or via SSH from Mac)
ssh root@45.55.90.156 'curl -s "http://localhost:30025/api/v1/user/list?page=1&page_size=3&api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"'
# Expected: {"code":0, "data":{"list":[...profiles...]}, "msg":"Success"}
```

### AdsPower binary details
- Binary: `/opt/AdsPower Global/adspower_global` (space in path)
- Symlink: `/usr/local/bin/adspower_global` → binary (for systemd)
- SunBrowser kernel: `chrome_134` at `~/.config/adspower_global/cwd_global/chrome_134/`
- Profile data: `~/.config/adspower_global/`
- Singleton locks: `rm -f /root/.config/adspower_global/Singleton*` before restart

## VPS AdsPower Control Scripts

From Mac (primary method):
```bash
bash scripts/vps_adspower.sh start     # SSH → clear singletons → systemctl start xvfb + adspower → wait 60s
bash scripts/vps_adspower.sh stop      # SSH → systemctl stop + pkill AdsPower processes
bash scripts/vps_adspower.sh status    # service state + API health + RAM
bash scripts/vps_adspower.sh diagnose  # full dump: systemctl, processes, ports, errors
bash scripts/vps_adspower.sh restart   # stop then start
```

On VPS directly:
```bash
bash /root/start_ads.sh   # manual launcher (same as systemctl start)
```

**Systemd services:**
- `xvfb.service` → virtual display :99 (must start first)
- `adspower.service` → AdsPower on port 30025 with `--api-key` auth (depends on xvfb)

## SSH Tunnel (MUST be running on Mac before any VPS script)

```bash
bash scripts/tunnel.sh
# Verifies tunnel, kills stale, start autossh if not running

# What it forwards:
# Mac:50325 ←── VPS:50325  (reverse: VPS calls Mac's AdsPower)
# Mac:3001 ──→  VPS:3001   (MCP servers)
```

**Check tunnel is up:**
```bash
lsof -i:3001 | grep LISTEN      # on Mac
curl -s "http://localhost:50325/api/v1/user/list?page=1&page_size=1&api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
```

## Supabase Tables

| Table | Purpose |
|-------|---------|
| `adspower_profiles` | 9 profiles: user_id, email, proxy, cookie_status, phone_number |
| `applied_jobs` | Dedup log: job_id, status, company, title, account_id, applied_date |
| `search_combinations` | 10 rows: position × state, drives N8N daily scrape |
| `proxies` | 100 Webshare entries, `assigned_to` = AdsPower user_id |
| `gmail_accounts` | 23 Gmail accounts: email, password, adspower_user_id, status |

## AdsPower Profile → Email Map (current)

| Slot | user_id | Email | SOCKS5 Proxy | Status |
|------|---------|-------|-------------|--------|
| 1 | k19td4st | gabrielalopezgomez80@gmail.com | 142.111.227.167:6362 | needs session |
| 2 | k19td4tu | alexeishon2@gmail.com | 104.232.209.101:6059 | needs session |
| 3 | k19td4uh | garciaramosjonathan8@gmail.com | 172.120.112.169:5848 | needs session |
| 4 | k19td4v5 | yoshiporfirioyoshio@gmail.com | 104.168.118.139:6095 | needs session |
| 5 | k19td4vp | gutierrezramirezhectormanuel6@gmail.com | 142.111.227.197:6392 | needs session |
| 6 | k19td4wc | martinezmedinajonathan975@gmail.com | 149.57.17.162:5630 | needs session |
| 7 | k19td4x8 | clarasanchezvillela@gmail.com | 136.0.207.16:6593 | needs session |
| 8 | k19td4xs | alisfleet@gmail.com | 69.58.12.159:8164 | needs session |
| 10 | k19td50a | oswaldin.lara@gmail.com | 107.172.163.82:6598 | ✅ session + profile set up |

Password all: `Simonala123` (some: `simonala123`)
