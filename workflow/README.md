# N8N Workflow Backup

> Export of the Indeed proposal generation workflow from N8N.

---

## File

| File | Size | What it is |
|------|------|------------|
| `Indeed Proposal generator copy.json` | ~1MB | Full N8N workflow export |

---

## What the workflow does

1. **Scrapes Indeed** — Apify actor searches for job listings by keyword + location
2. **Filters** — GPT-4 evaluates relevance against target criteria
3. **Generates proposals** — Claude writes tailored cover letters per job
4. **Saves to Google Drive** — proposals stored as DOCX files
5. **Triggers pipeline** — POSTs CSV URL to VPS webhook (`webhook_server.py` on port 8080)

---

## How to import

1. Open your N8N instance
2. Go to **Workflows → Import from File**
3. Select `Indeed Proposal generator copy.json`
4. Update any webhook URLs, API keys, or Google Drive references to match your environment

---

## Notes

- This is a **backup copy** — the live workflow runs on `https://n8n.hvactechpulse.online`
- The workflow connects to the pipeline via HTTP POST → `VPS:8080/apply`
- Search terms and locations are driven by Supabase `search_combinations` table
