# Script Overview — Indeed Auto-Apply Pipeline

## Where Things Live

```
antigravity-workspace-template/
├── scripts/          ← YOU ARE HERE — all runnable scripts
│   ├── tunnel.sh           Mac ↔ VPS SSH tunnel
│   ├── export_cookies.py   Automated Google login + cookie grab (all 10 profiles)
│   ├── grab_cookies_manual.py  Manual fallback: 90s window to log in by hand
│   └── test_local.py       Full Indeed session stress test (no form submit)
│
└── src/              ← VPS-side modules (run via cron/systemd on VPS)
    ├── orchestrator.py     Cron entry point — triggers N8N daily
    ├── webhook_server.py   HTTP :8080 — receives CSV URL from N8N
    ├── apply_runner.py     Loads CSV, dedupes, calls apply_to_job() per job
    ├── nodriver_indeed.py  Browser automation — clicks Apply, uploads DOCX, submits
    ├── supabase_client.py  Supabase REST helpers (search combos, applied jobs)
    └── gdrive_client.py    Google Drive — downloads proposal DOCX per job
```

---

## Full System Flow

```
[DAILY CRON — 9 AM on VPS]
        │
        ▼
 orchestrator.py
  └─ reads Supabase: search_combinations (not used in 7+ days)
  └─ POSTs to N8N webhook with {position, location, maxItems, ...}
        │
        ▼
    N8N Cloud
  └─ scrapes Indeed jobs matching combo
  └─ filters out already-applied (Supabase check)
  └─ generates proposal/cover letter → saves to Google Drive
  └─ POSTs CSV URL → VPS :8080/apply
        │
        ▼
 webhook_server.py  (always-on systemd service on VPS)
  └─ receives POST /apply with {"csv_url": "..."}
  └─ spawns apply_runner.py as subprocess
        │
        ▼
 apply_runner.py
  └─ downloads CSV from N8N
  └─ for each job:
       ├─ check Supabase applied_jobs (skip if already done)
       ├─ download proposal DOCX from Google Drive via gdrive_client.py
       ├─ pick AdsPower profile (round-robin across 10 profiles)
       └─ call apply_to_job() in nodriver_indeed.py
              │
              ▼
       nodriver_indeed.py
        └─ AdsPower API → start profile (fingerprint + proxy + session)
        └─ nodriver attaches via debug_port
        └─ indeed.com warmup → job page → click Apply → upload DOCX → Submit
        └─ writes result back to apply_runner
              │
              ▼
       apply_runner.py
        └─ upsert result to Supabase applied_jobs
        └─ cleanup /tmp DOCX
```

---

## Local Scripts — What to Run and When

### `tunnel.sh`
**Run once at session start (or on reconnect)**
```bash
bash scripts/tunnel.sh
```
- Keeps VPS:50325 → Mac AdsPower API bridged via autossh
- Without this, VPS scripts cannot reach AdsPower
- Also bridges MCP servers (localhost:3001-3003)

---

### `export_cookies.py` ← **run this to refresh sessions**
**Run when profiles show `login_required` during test**
```bash
# All 10 profiles (automated Google login):
venv_local/bin/python3.13 -u scripts/export_cookies.py

# Single slot to test first:
venv_local/bin/python3.13 -u scripts/export_cookies.py --slot 1
```
- Opens each AdsPower profile browser
- Navigates to indeed.com → clicks Sign in → clicks Google → types email + password
- Waits 60s for Cloudflare + session to settle
- Grabs `indeed_sess`, `CTK`, `INDEED_CSRF_TOKEN`, `LC` cookies
- Saves to `config/cookies/account_N.json`
- Profiles + passwords sourced from **Supabase** + **config/accounts.json**

---

### `grab_cookies_manual.py` ← **fallback if automated login breaks**
**Run when Google login flow changes or 2FA triggers**
```bash
venv_local/bin/python3.13 -u scripts/grab_cookies_manual.py --slot 1
```
- Same as export_cookies.py but gives you 90s to log in yourself
- Use when Google blocks the automated typing (SMS 2FA, captcha, etc.)

---

### `test_local.py` ← **main stress test**
**Run to verify end-to-end flow without submitting any application**
```bash
venv_local/bin/python3.13 -u scripts/test_local.py
```
- Fetches all 10 profiles from Supabase
- For each profile: starts AdsPower → navigates Indeed like a human → searches jobs → reads job page
- Detects page state at every step: `cloudflare` / `login_required` / `search_results` / `job_page`
- Rotates to next profile on Cloudflare or login wall
- Stops BEFORE submitting any form — safe to run at any time
- Goal: reach Apply button with zero manual steps

---

## Data Sources

```
Supabase (cloud DB)
├── adspower_profiles   10 profiles: user_id, email, cookie_status, proxy
├── search_combinations Job search queries: position + state + last_used
└── applied_jobs        Dedup log: job_id, status, company, title, account_id

config/accounts.json    email → password for all 10 Google accounts
config/cookies/         indeed_sess cookies per profile (written by export_cookies.py)
config/google_service_account.json  Google Drive API credentials
```

---

## External Services

| Service | Role |
|---|---|
| **AdsPower** (Mac, port 50325) | Anti-detect browser: fingerprint spoofing + residential proxy + cookie persistence |
| **N8N** (cloud) | Job scraper + proposal generator + pipeline orchestrator |
| **Supabase** | Database for profiles, combos, dedup |
| **Google Drive** | Stores generated proposal DOCX per job |
| **VPS** (45.55.90.156) | Always-on host for orchestrator cron + webhook server |

---

## Dependency Map

```
tunnel.sh
  └─ enables all VPS → AdsPower communication

export_cookies.py
  ├─ reads  Supabase (adspower_profiles)
  ├─ reads  config/accounts.json
  ├─ calls  AdsPower API (browser/start, browser/stop)
  └─ writes config/cookies/account_N.json

grab_cookies_manual.py
  ├─ reads  Supabase (adspower_profiles)
  ├─ reads  config/accounts.json
  ├─ calls  AdsPower API
  └─ writes config/cookies/account_N.json

test_local.py
  ├─ reads  Supabase (adspower_profiles)
  └─ calls  AdsPower API → nodriver attaches

orchestrator.py  [VPS]
  ├─ reads  Supabase (search_combinations)
  └─ calls  N8N webhook

webhook_server.py  [VPS]
  └─ spawns apply_runner.py

apply_runner.py  [VPS]
  ├─ reads  Supabase (applied_jobs)
  ├─ writes Supabase (applied_jobs)
  ├─ calls  gdrive_client.py → Google Drive
  └─ calls  nodriver_indeed.py → AdsPower (via tunnel)

nodriver_indeed.py  [VPS]
  └─ calls  AdsPower API via tunnel → nodriver CDP

supabase_client.py  [VPS lib]
  └─ imported by orchestrator.py + apply_runner.py

gdrive_client.py  [VPS lib]
  └─ imported by apply_runner.py
```

---

## Typical Workflow

```
1. bash scripts/tunnel.sh                       # ensure tunnel is up

2. venv_local/bin/python3.13 -u \
   scripts/export_cookies.py --slot 1           # test one profile login

3. venv_local/bin/python3.13 -u \
   scripts/export_cookies.py                    # login all 10 profiles

4. venv_local/bin/python3.13 -u \
   scripts/test_local.py                        # stress test full flow

5. (VPS) python src/orchestrator.py --dry-run   # verify cron trigger
```
