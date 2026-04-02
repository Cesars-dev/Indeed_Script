# Implementation Plan: Indeed Auto-Apply Pipeline (FINAL)

## Context
N8N handles scraping (Apify), qualification (GPT-4.1-nano), proposal generation (Claude 3.5 Haiku via OpenRouter), Google Docs creation, and Google Sheets logging. Python handles: (1) cron orchestration — queries Supabase for fresh combos, triggers N8N webhook; (2) apply automation — downloads DOCX from Google Drive, runs Nodriver to apply on Indeed; (3) Supabase state tracking + deduplication.

Proxies: 100 Webshare datacenter proxies, US-based, shared creds (lehavxel / 4lzagcbkv7t9), different IPs/ports. Fetched live from Webshare API.

---

## Full Trigger Chain

```
9 AM cron → python orchestrator.py
  └─ Query Supabase search_combinations (last_used < 7 days ago)
  └─ POST to N8N webhook with {state, search_term, max_items}
       │
       [N8N: Apify → qualify → proposals → Google Docs → CSV to Google Sheets]
       │
  └─ N8N final node: POST http://<VPS_IP>:8080/apply {sheet_id or csv_url}
       │                   ↑ VPS public IP, NOT localhost
python webhook_server.py receives (running on VPS) → spawns apply_runner.py
  └─ Read CSV rows (job_id, url, account_id, google_doc_id, ...)
  └─ Skip job_ids already in Supabase applied_jobs
  └─ Fetch proxy from Webshare API (rotate by index)
  └─ Download Google Doc as DOCX via Drive API
  └─ Nodriver: navigate Indeed → upload DOCX → submit
  └─ Upsert result to Supabase applied_jobs
  └─ Update state_term_status.last_used
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/orchestrator.py` | Cron entry point: fetch combos from Supabase → trigger N8N |
| `src/webhook_server.py` | HTTP server on :8080, receives N8N callback → spawns apply_runner |
| `src/apply_runner.py` | Reads CSV, dedupes, loops apply logic |
| `src/nodriver_indeed.py` | Nodriver session: cookies + proxy → navigate → upload → submit |
| `src/proxy_manager.py` | Fetch proxy list from Webshare API, rotate by job index |
| `src/gdrive_client.py` | Download Google Doc as DOCX using service account |
| `src/supabase_client.py` | Thin wrapper: query combos, upsert applied_jobs, update last_used |
| `config/cookies/account_{1..10}.json` | Indeed session cookies per account (user provides) |
| `config/phones.json` | 10 phone numbers [{id, number}] (user provides) |
| `.env` | All secrets |
| `requirements.txt` | All deps |
| `supabase_schema.sql` | Schema to run once in Supabase dashboard |

---

## Supabase Schema

```sql
CREATE TABLE search_combinations (
  id SERIAL PRIMARY KEY,
  state TEXT NOT NULL,
  search_term TEXT NOT NULL,
  last_used TIMESTAMPTZ,
  results_found INTEGER DEFAULT 0,
  active BOOLEAN DEFAULT TRUE,
  UNIQUE(state, search_term)
);

CREATE TABLE applied_jobs (
  job_id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  state TEXT,
  search_term TEXT,
  status TEXT,   -- 'success' | 'failed' | 'skipped'
  reason TEXT,
  applied_date TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Proxy Strategy
- Fetch all 100 proxies from Webshare API on startup
- Assign by round-robin index: `proxy = proxies[i % len(proxies)]`
- Format: `http://lehavxel:4lzagcbkv7t9@{ip}:{port}`
- Rotate every job (not every account) for max spread

## Google Doc → DOCX Download
```python
# Uses service account credentials (user must provide google_service_account.json)
url = f"https://www.googleapis.com/drive/v3/files/{doc_id}/export"
params = {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
# Save to /tmp/proposal_{job_id}.docx
```

---

## .env Variables Needed

```
WEBSHARE_API_KEY=fs4y2sxrfijbqr7apbyr1l9vt4i9gday1sp4t0ve
SUPABASE_URL=                    # still needed
SUPABASE_KEY=                    # still needed
N8N_WEBHOOK_URL=https://n8n.hvactechpulse.online/webhook/ba283c1f-9daa-4b98-a01c-ac1a1b1707dc
GOOGLE_SERVICE_ACCOUNT_JSON=     # path to JSON file
LISTEN_PORT=8080
```

---

## Implementation Order

1. `requirements.txt` + `.env` + `.env.example`
2. `supabase_schema.sql`
3. `src/proxy_manager.py` (fetch + rotate from Webshare)
4. `src/supabase_client.py` (query combos, upsert results)
5. `src/gdrive_client.py` (download DOCX)
6. `src/orchestrator.py` (cron entry: combos → N8N trigger)
7. `src/webhook_server.py` (receive N8N callback)
8. `src/nodriver_indeed.py` (browser automation core)
9. `src/apply_runner.py` (orchestrate apply loop)
10. Crontab entry: `0 9 * * * python /path/to/src/orchestrator.py`

---

## Still Needed from User
- Supabase URL + service key
- N8N webhook trigger URL
- Google Service Account JSON (for Drive download)
- Indeed cookie files (10 accounts)
- Phone numbers list

---

## Verification
1. Run `python src/proxy_manager.py` → prints 100 proxies fetched
2. Run `python src/orchestrator.py --dry-run` → prints combos without triggering N8N
3. POST test payload to `localhost:8080/apply` → confirm DOCX downloaded + Nodriver opens
4. Full run: trigger N8N manually → confirm CSV arrives → apply loop runs → Supabase updated
