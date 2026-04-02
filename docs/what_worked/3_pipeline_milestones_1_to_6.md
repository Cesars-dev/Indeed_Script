# Pipeline Milestones 1–6 — What Worked

## Overview
Full end-to-end Indeed auto-apply pipeline. All 6 milestones complete.

---

## M1 — Infrastructure (DONE)
- VPS: `root@45.55.90.156` (SSH key auth, no password)
- Supabase: `https://uckkgnqlehprbpypcgjc.supabase.co`
- N8N webhook: `https://n8n.hvactechpulse.online/webhook/ba283c1f-9daa-4b98-a01c-ac1a1b1707dc`
- AdsPower group "indeed", group_id: `8765960`
- Webshare: 100 datacenter proxies (user: `lehavxel` / pass: `4lzagcbkv7t9`)
- VPS webhook_server.py on port 8080, systemd managed

## M2 — Supabase MCP (DONE)
- `@supabase/mcp-server-supabase` installed, stdio transport
- Direct DB ops from Claude Code terminal

## M3 — Schema + Webhook (DONE)
- `search_combinations` table: 10 rows seeded (state + search_term combos)
- `applied_jobs` table: job_id PRIMARY KEY = deduplication
- N8N → VPS webhook → apply_runner.py chain verified

## M4 — AdsPower Profiles + Proxies (DONE)
- 10 profiles in AdsPower, 1 Webshare HTTP proxy baked into each
- Profile→account mapping confirmed (see project_report.md)

## M5 — Cookie Export (DONE)
- `scripts/export_cookies.py` — Playwright-based, via AdsPower CDP
- Exports: CTK, indeed_sess, INDEED_CSRF_TOKEN, LC
- Saved to `config/cookies/account_1.json` through `account_10.json`
- Valid for weeks; rerun when expired

## M6 — End-to-End Test (DONE)
- 10 fake jobs fired through full pipeline
- 7 failed "No apply button" (expected — fake job IDs)
- 3 skipped (no cookies at time of test → later fixed)
- Deduplication confirmed: 2nd run skipped all 10

---

## N8N Webhook Trigger Payload
```json
{ "csv_url": "https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv" }
```

## Apply Runner Account Rotation
```python
account_num = (index % NUM_ACCOUNTS) + 1   # 1-10, cycles
cookies_path = f"config/cookies/account_{account_num}.json"
```

## Proxy Rotation
```python
proxy = proxies[index % len(proxies)]   # round-robin across 100 Webshare proxies
```

## Supabase Deduplication
```python
if is_job_applied(job_id):
    return  # skip
upsert_applied_job(job_id, {...})
```
