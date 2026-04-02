# Pipeline Status — Indeed Auto-Apply
> Last updated: 2026-03-06 — VPS pipeline working, blocked by CF on datacenter IP

---

## ⚡ TL;DR

**The pipeline works end-to-end on VPS.** Only blocker: Cloudflare re-challenges datacenter IPs infinitely. Need residential proxy.

| Layer | Status |
|-------|--------|
| VPS AdsPower headless (port 30025, systemd) | ✅ Running |
| Playwright CDP on VPS | ✅ Confirmed |
| Screenshots in headless | ✅ Skia renderer, no display needed |
| Gemini API | ✅ `gemini-2.5-flash` key working |
| CF Turnstile bypass code | ✅ Ported to Playwright |
| **CF on datacenter IP** | ❌ **BLOCKER** — re-challenges infinitely |
| Browser engine (Playwright + Gemini Vision) | ✅ Built, CDP confirmed |
| Indeed sessions (AdsPower profiles) | ❌ 18/19 profiles need session |
| First full apply test | ❌ Blocked by CF |
| LibreOffice on VPS (PDF conversion) | ❌ Not installed |

**One account ready: `k19td50a`** — kernel updated to 134, browser launches, DOM accessible.

---

## VPS AdsPower Control

```bash
# From Mac — controls VPS AdsPower remotely
bash scripts/vps_adspower.sh start     # SSH → systemctl start xvfb + adspower (~70s)
bash scripts/vps_adspower.sh stop      # SSH → systemctl stop + pkill
bash scripts/vps_adspower.sh status    # service state + API health + RAM
bash scripts/vps_adspower.sh diagnose  # full dump when something breaks
```

**Port map:**
| Port | What | Status |
|------|------|--------|
| **30025** | VPS-native AdsPower API | ✅ Primary — use this |
| 20725 | Ghost-locked by internal JS | ❌ NEVER use |
| 50325 | Mac tunnel (legacy) | ✅ Works if Mac is on |

```
[9AM Cron — VPS]
      │
      ▼
orchestrator.py ──▶ N8N webhook
                          │
               Apify scrapes Indeed
               GPT-4 filters jobs
               Claude writes proposals
               Google Drive stores DOCX
                          │
                  POST CSV URL → VPS:8080
                          │
      ┌───────────────────┘
      ▼
webhook_server.py  (systemd, always on)
      │
      ▼
apply_runner.py
  ├─ Load CSV, dedup via Supabase
  ├─ Google Drive → DOCX → LibreOffice → PDF
  ├─ Round-robin across 9 AdsPower profiles
  └─ playwright_indeed.apply_to_job()
          │
          ├─ AdsPower API → start profile → debug_port
          ├─ playwright.connect_over_cdp(port)
          ├─ indeed.com warmup (15–25s)
          ├─ navigate to job → click Apply (CSS selectors)
          └─ Gemini Vision loop (max 20 steps):
                screenshot → Gemini JSON → execute
                until: done / failed / disqualified
                          │
          apply_runner ◀──┘
          └─ upsert result → Supabase applied_jobs
```

---

## Profile Status

| Slot | user_id | Email | Session | Profile Setup |
|------|---------|-------|---------|---------------|
| 1 | k19td4st | gabrielalopezgomez80@gmail.com | ❌ | ❌ |
| 2 | k19td4tu | alexeishon2@gmail.com | ❌ | ❌ |
| 3 | k19td4uh | garciaramosjonathan8@gmail.com | ❌ | ❌ |
| 4 | k19td4v5 | yoshiporfirioyoshio@gmail.com | ❌ | ❌ |
| 5 | k19td4vp | gutierrezramirezhectormanuel6@gmail.com | ❌ | ❌ |
| 6 | k19td4wc | martinezmedinajonathan975@gmail.com | ❌ | ❌ |
| 7 | k19td4x8 | clarasanchezvillela@gmail.com | ❌ | ❌ |
| 8 | k19td4xs | alisfleet@gmail.com | ❌ | ❌ |
| 10 | k19td50a | oswaldin.lara@gmail.com | ✅ | ✅ Ready |

---

## Blockers (ordered)

### 🔴 1 — `APPLICANT_NAME` blank in `.env`
Gemini sends empty name to all job forms. Fill it before running any test.
```bash
nano indeed-pipeline/.env
# APPLICANT_NAME=<applicant full name>
```

### 🔴 2 — First apply test never run
Run with the one ready account before fixing others:
```bash
cd indeed-pipeline
venv_local/bin/python3.13 -c "
import asyncio, sys
sys.path.insert(0, '.')
from src.playwright_indeed import apply_to_job
result = asyncio.run(apply_to_job(
    'https://www.indeed.com/viewjob?jk=58446c601423ff56',
    None, 'k19td50a'
))
print(result)
"
open /tmp/playwright_debug/   # review step screenshots
```

### 🟡 3 — 8 profiles need Firefox cookie injection
```bash
# Per account:
# 1. Firefox → Gmail login → indeed.com login
# 2. Run:
venv_local/bin/python3.13 scripts/inject_firefox_cookies.py --user-id <id>
# 3. Wait 24h. Then manually open AdsPower profile, click Apply on any job
#    → complete the one-time Indeed setup wizard (resume, visibility)
```

**Account → user_id:**
| Email | user_id |
|-------|---------|
| gutierrezramirezhectormanuel6@gmail.com | k19td4vp |
| alexeishon2@gmail.com | k19td4tu |
| alisfleet@gmail.com | k19td4xs |
| clarasanchezvillela@gmail.com | k19td4x8 |
| gabrielalopezgomez80@gmail.com | k19td4st |
| garciaramosjonathan8@gmail.com | k19td4uh |
| martinezmedinajonathan975@gmail.com | k19td4wc |
| yoshiporfirioyoshio@gmail.com | k19td4v5 |

### 🟡 4 — LibreOffice not installed on VPS
```bash
ssh root@45.55.90.156 "apt install -y libreoffice"
```

---

## Known Gaps in Gemini Form Handling

| Form element | Behavior today |
|---|---|
| `<textarea>` (free text, cover letter) | Left empty |
| Salary / wage inputs | Skipped |
| Date inputs (start date) | Left empty |
| Checkboxes (multi-select) | Not handled |

**Fix**: Run with screenshots. Review `/tmp/playwright_debug/`. Update Gemini system prompt in `src/playwright_indeed.py`.

---

## Supabase Quick Checks

```sql
-- Application results
SELECT status, COUNT(*) FROM applied_jobs GROUP BY status;

-- Failed details
SELECT job_id, title, company, reason FROM applied_jobs
WHERE status = 'failed' ORDER BY applied_date DESC LIMIT 20;

-- Profile health
SELECT account_slot, email, cookie_status FROM adspower_profiles ORDER BY account_slot;
```
