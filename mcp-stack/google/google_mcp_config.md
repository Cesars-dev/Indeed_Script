# Google API Config — Indeed Pipeline

Two authentication methods available for Google APIs. Both use the same GCP project (`n8n-keys-471903`).

---

## 🔑 Credentials (in this folder, gitignored)

| File | Type | Use Case |
|------|------|----------|
| `oauth_client.json` | OAuth 2.0 (installed app) | User-context access: Sheets, Docs, Drive |
| `oauth_token.json` | OAuth refresh token | Auto-refreshes; scopes: Drive, Sheets, Docs |
| `google_service_account.json` | Service Account | Server-to-server: `pipeline-sheets@n8n-keys-471903.iam.gserviceaccount.com` |

> **All 3 files are gitignored.** Source of truth: `/home/julio/projects/Indeed_proposal_gen/config/`

---

## Which Auth to Use

| Scenario | Method | File |
|----------|--------|------|
| Download cover letter DOCX from Google Drive | **OAuth** or **Service Account** | `oauth_token.json` or `google_service_account.json` |
| Read Google Sheet (CSV export) | **Public link** (no auth needed) | None — just append `/export?format=csv` to sheet URL |
| Read Google Sheet (private) | **OAuth** | `oauth_token.json` |
| Create/edit Google Docs | **OAuth** | `oauth_token.json` |

### Public Google Sheet CSV (no auth required)

If the sheet is shared as "Anyone with the link can view":
```
https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv
```
No credentials needed. `apply_runner.py` uses this to fetch the job list.

### OAuth Token (user-context, auto-refresh)

```python
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_PATH = "mcp-stack/google/oauth_token.json"

with open(TOKEN_PATH) as f:
    token_data = json.load(f)

creds = Credentials(
    token=token_data["token"],
    refresh_token=token_data["refresh_token"],
    token_uri=token_data["token_uri"],
    client_id=token_data["client_id"],
    client_secret=token_data["client_secret"],
    scopes=token_data["scopes"]
)

# Auto-refresh if expired
if creds.expired:
    creds.refresh(Request())
    # Save refreshed token back
    token_data["token"] = creds.token
    with open(TOKEN_PATH, "w") as f:
        json.dump(token_data, f, indent=2)

# Use in requests
headers = {"Authorization": f"Bearer {creds.token}"}
```

**Scopes:** `drive`, `spreadsheets`, `documents`

### Service Account (server-to-server)

```python
from google.oauth2 import service_account
from google.auth.transport.requests import Request

SA_PATH = "mcp-stack/google/google_service_account.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
creds.refresh(Request())

headers = {"Authorization": f"Bearer {creds.token}"}
```

**Email:** `pipeline-sheets@n8n-keys-471903.iam.gserviceaccount.com`

> ⚠️ **The Google Doc/Sheet must be shared with this email** for the service account to access it. For OAuth, it uses the user's own account so no sharing needed.

---

## 📥 Download Cover Letter (DOCX from Google Drive)

The Indeed pipeline's `gdrive_client.py` already handles this:

```python
from src.gdrive_client import download_doc_as_docx

# doc_id can be a bare ID or a full Google Docs URL
download_doc_as_docx("1abc2def3ghi...", "/tmp/proposal_123.docx")
```

**Current state:** `gdrive_client.py` uses the **service account** method. The SA JSON needs to be at the path set by `GOOGLE_SERVICE_ACCOUNT_JSON` env var (defaults to `config/google_service_account.json`).

To use the copy in this folder:
```bash
# Add to indeed-pipeline/.env:
GOOGLE_SERVICE_ACCOUNT_JSON=/home/julio/projects/Indeed_Script/mcp-stack/google/google_service_account.json
```

Or symlink:
```bash
mkdir -p /home/julio/projects/Indeed_Script/indeed-pipeline/config
ln -sf /home/julio/projects/Indeed_Script/mcp-stack/google/google_service_account.json \
  /home/julio/projects/Indeed_Script/indeed-pipeline/config/google_service_account.json
```

---

## 🔗 Trigger Apply Pipeline

After the proposal agent creates all proposals and logs them to a Google Sheet:

```bash
# From VPS — fire and forget
curl -X POST http://localhost:8080/apply \
  -H "Content-Type: application/json" \
  -d '{"csv_url": "https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv"}'
```

The webhook server spawns `apply_runner.py` which:
1. Downloads CSV from the Google Sheet
2. For each row: downloads DOCX cover letter via `gdrive_client.py`
3. Converts DOCX → PDF (LibreOffice, already installed)
4. Calls `apply_to_job(apply_url, pdf_path, user_id)`
5. Round-robins across all 19 profiles

### Expected CSV Columns

| Column | Required | Description |
|--------|----------|-------------|
| `job_id` / `jobId` / `id` | ✅ | Unique job identifier (for dedup) |
| `apply_url` / `applyUrl` / `url` | ✅ | Indeed apply URL |
| `google_doc_id` / `docId` / `doc_id` | Optional | Google Doc ID for cover letter |
| `company` | Optional | Company name (logging) |
| `title` | Optional | Job title (logging) |
| `state` | Optional | State (logging) |
| `search_term` | Optional | Search term used (logging) |

---

## GCP Project Reference

| Field | Value |
|-------|-------|
| Project ID | `n8n-keys-471903` |
| OAuth Client ID | `671493995028-q3j2m5r6op0nobnkrfavvt6bf7giq432.apps.googleusercontent.com` |
| Service Account Email | `pipeline-sheets@n8n-keys-471903.iam.gserviceaccount.com` |
