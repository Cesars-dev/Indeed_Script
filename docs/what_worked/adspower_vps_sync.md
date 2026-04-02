# AdsPower: Sync Local (Mac) Session to VPS

## Problem
VPS AdsPower requires a cloud account login before the headless API works.
The GUI login screen is inaccessible on headless VPS (Electron/Xvfb rendering blocked).
`--api-key` flag only authenticates API requests — does NOT log in the AdsPower account.

## Solution
Copy Mac's AdsPower LocalStorage + IndexedDB to VPS.
AdsPower's auth token lives in these as a standard web token — NOT Keychain-encrypted.
VPS AdsPower wakes up already authenticated, all cloud profiles sync immediately.

## Procedure

### Step 1 — On Mac (tar the session data)
```bash
cd ~/Library/Application\ Support/adspower_global/
tar czf /tmp/ads_session.tar.gz "Local Storage" "IndexedDB"
scp /tmp/ads_session.tar.gz root@45.55.90.156:/tmp/
```

### Step 2 — On VPS (inject and restart)
```bash
systemctl stop adspower
cd /root/.config/adspower_global/

# Backup existing (in case rollback needed)
[ -d 'Local Storage' ] && mv 'Local Storage' 'Local Storage.bak'
[ -d 'IndexedDB' ] && mv 'IndexedDB' 'IndexedDB.bak'

# Inject Mac session
tar xzf /tmp/ads_session.tar.gz
chown -R root:root "Local Storage" "IndexedDB"

systemctl start adspower
sleep 8
```

### Step 3 — Verify
```bash
# API key from .env → ADSPOWER_API_KEY
curl "http://localhost:20725/api/v1/user/list?api_key=${ADSPOWER_API_KEY}&page=1&page_size=10"
# Expected: {"code":0,"msg":"Success","data":{"list":[...profiles...]}}
```

## Key Facts
- VPS AdsPower always binds to port **20725** (`--api-port` flag is ignored)
- Port 50325 on VPS = autossh `-R` tunnel to Mac's AdsPower — separate, optional
- VPS service file: `/etc/systemd/system/adspower.service` → `/opt/start-adspower.sh`
- VPS config data: `/root/.config/adspower_global/`
- Mac source data: `~/Library/Application Support/adspower_global/`

## When to Re-run
Re-run this procedure if:
- AdsPower account session expires (profiles list returns empty or 403)
- Mac AdsPower account password is changed
- VPS is rebuilt from scratch

## Confirmed Working
- Date: 2026-02-21
- AdsPower version: 7.3.26
- Result: all 10 Indeed profiles visible via `localhost:20725` API on VPS
- Mac was subsequently able to go offline without affecting VPS API
