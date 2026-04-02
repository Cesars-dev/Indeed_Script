# Supabase MCP Config — Indeed Auto-Apply

Everything a new agent needs to connect to **Supabase** via MCP. Read this file, connect in 3 seconds.

> **Project Ref:** `uckkgnqlehprbpypcgjc`  
> **Schema:** `public`  
> **Auth:** `SUPABASE_ACCESS_TOKEN` from `mcp-stack/supabase/.env`

---

## ⚡ Quick Start — Two Methods

### Method 1: REST API (for reads + writes — PREFERRED)

This is the **fastest, most reliable** method. Uses `SUPABASE_SERVICE_KEY` from `indeed-pipeline/.env`.

```python
import os, requests
from dotenv import load_dotenv
load_dotenv(dotenv_path='/home/julio/projects/Indeed_Script/indeed-pipeline/.env', override=True)

url = os.getenv('SUPABASE_URL')    # https://uckkgnqlehprbpypcgjc.supabase.co
skey = os.getenv('SUPABASE_SERVICE_KEY')
HEADERS = {'apikey': skey, 'Authorization': f'Bearer {skey}', 'Content-Type': 'application/json'}

# SELECT
r = requests.get(f'{url}/rest/v1/adspower_profiles?select=*&order=account_slot.asc', headers=HEADERS, timeout=10)
rows = r.json()

# INSERT
requests.post(f'{url}/rest/v1/apply_patterns', json={"question_text": "authorized", "answer_value": "Yes"},
              headers={**HEADERS, 'Prefer': 'return=minimal'}, timeout=10)

# UPDATE (PATCH)
requests.patch(f'{url}/rest/v1/adspower_profiles?user_id=eq.k1a2vuom',
               json={"proxy_address": "130.180.232.135", "proxy_port": 8573},
               headers={**HEADERS, 'Prefer': 'return=representation'}, timeout=10)

# COUNT
r = requests.get(f'{url}/rest/v1/proxies?select=id', headers={**HEADERS, 'Prefer': 'count=exact'}, timeout=10)
total = r.headers.get('content-range')  # "0-99/100"
```

**Use this for:** SELECT, INSERT, UPDATE, DELETE — all DML operations.

### Method 2: MCP Stdio via npx (for DDL migrations ONLY)

Use this **only** for `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`, etc.

```python
import os, subprocess, json
from dotenv import load_dotenv

# CRITICAL: Load token from the CLEAN .env (no special chars)
load_dotenv(dotenv_path='/home/julio/projects/Indeed_Script/mcp-stack/supabase/.env', override=True)
token = os.getenv('SUPABASE_ACCESS_TOKEN')

proc = subprocess.Popen(
    ['npx', '-y', '@supabase/mcp-server-supabase', '--project-ref', 'uckkgnqlehprbpypcgjc'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, env={**os.environ, 'SUPABASE_ACCESS_TOKEN': token}
)

msg = json.dumps({
    'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
    'params': {
        'name': 'apply_migration',
        'arguments': {
            'name': 'add_my_column_20260316',   # MUST be globally unique — use timestamps
            'query': "ALTER TABLE my_table ADD COLUMN IF NOT EXISTS my_col TEXT DEFAULT ''; NOTIFY pgrst, 'reload schema';"
        }
    }
})

stdout, stderr = proc.communicate(input=msg + '\n', timeout=60)
# Expected stdout: {"result":{"content":[{"type":"text","text":"{\"success\":true}"}]},...}
```

---

## 🚨 Gotchas That Wasted Time (Read This)

### 1. Token location
`SUPABASE_ACCESS_TOKEN` lives in the **parent** `.env` (`Indeed_Script/.env`), NOT in `indeed-pipeline/.env`. The parent `.env` has passwords with special characters that break bash `source` / `export`. **Solution:** A clean copy lives at `mcp-stack/supabase/.env` — always load from there.

### 2. REST vs MCP — use the right tool
| Operation | Method | Why |
|-----------|--------|-----|
| SELECT / INSERT / UPDATE / DELETE | **REST API** (Method 1) | Zero setup, uses `SUPABASE_SERVICE_KEY`, instant |
| CREATE TABLE / ALTER TABLE / DROP | **MCP stdio** (Method 2) | PostgREST can't run DDL — must use `apply_migration` |

### 3. Migration names must be unique
`apply_migration` requires a globally unique `name`. Reusing a name silently fails. Always use timestamps: `add_column_20260316`.

### 4. Always NOTIFY after DDL
```sql
ALTER TABLE ... ; NOTIFY pgrst, 'reload schema';
```
Without this, PostgREST won't see the new column and REST queries will return 400.

### 5. The local `dist/` MCP server is broken
`mcp-stack/supabase/dist/transports/stdio.js` has a missing `common-tags` dependency. **Use `npx -y @supabase/mcp-server-supabase` instead** — it always works.

### 6. Don't use bash `source .env`
The parent `.env` has passwords with `!`, `@`, `$` characters. Bash `source` or `export $(grep ...)` will mangle them. **Always use Python `dotenv`.**

---

## Available MCP Tools (via stdio)

### `execute_sql`
Run SELECT / INSERT / UPDATE / DELETE queries.

```js
arguments: {
  query: "SELECT * FROM adspower_profiles ORDER BY account_slot ASC;"
}
```

- Tables are in the `public` schema — no prefix needed
- Returns JSON wrapped in XML-like tags (see Parsing below)
- **NOT** for DDL (CREATE/DROP/ALTER) — use `apply_migration`

### `apply_migration`
Run DDL operations (CREATE TABLE, ALTER TABLE, DROP TABLE).

```js
arguments: {
  name: "add_column_20260313",  // MUST be globally unique — use timestamps
  query: "ALTER TABLE adspower_profiles ADD COLUMN IF NOT EXISTS my_col TEXT DEFAULT ''; NOTIFY pgrst, 'reload schema';"
}
```

### `list_tables`
List all tables with columns, types, and row counts.

```js
arguments: {
  schemas: ["public"]
}
```

### `list_migrations`
List all applied migrations.

```js
arguments: {}
```

---

## Parsing MCP Responses

`execute_sql` wraps results in XML-like tags:

```
"Below is the result... <untrusted-data-UUID>[{"col":"val"}]</untrusted-data-UUID>..."
```

Parse with:
```python
import re, json
text = response.get('result',{}).get('content',[{}])[0].get('text','')
unescaped = text.replace('\\n', '\n').replace('\\"', '"')
match = re.search(r'\[.*?\]', unescaped, re.DOTALL)
rows = json.loads(match.group(0)) if match else []
```

---

## Schema: `public` (Indeed Auto-Apply)

| Table | Purpose | Key |
|---|---|---|
| `adspower_profiles` | 19 browser profiles — user_id, email, proxy, cookie_status, applicant data, proxy_type | `user_id` |
| `applied_jobs` | Dedup log — job_id, status, company, title, account_id | `job_id` (PK) |
| `apply_patterns` | P8 learning loop — Gemini Q&A patterns | `question_text + answer_value` (unique) |
| `apply_runs` | Apply run summaries | `id` (serial) |
| `apply_step_log` | Step-by-step execution log | `id` (serial) |
| `executions` | Full pipeline execution tracking — 1 row per apply call | `id` (serial) |
| `gmail_accounts` | 23 Gmail accounts — email, password, adspower_user_id | — |
| `proxies` | 100 Webshare datacenter SOCKS5 — `assigned_to` = user_id | — |
| `residential_proxies` | 20 Webshare residential SOCKS5 — `assigned_to` = user_id | — |
| `search_combinations` | 10 keyword × state combos for daily N8N scrape | `state + search_term` (unique) |
| `test_run_logs` | Dev/batch test run results | `id` (serial) |

---

## Env Files Reference

| File | Contains | Used By |
|---|---|---|
| `Indeed_Script/.env` | `SUPABASE_ACCESS_TOKEN` (+ other keys with special chars) | Parent — **do not bash-source** |
| `indeed-pipeline/.env` | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY` | REST API queries |
| `mcp-stack/supabase/.env` | `SUPABASE_ACCESS_TOKEN` (clean copy) | MCP stdio migrations |

---

## What's in This Kit

| File | Purpose |
|---|---|
| `supabase_mcp_config.md` | **This guide** — connection reference, proven methods, gotchas |
| `connection_config.json` | Full MCP config with tools, schema, and examples |
| `.env` | Clean `SUPABASE_ACCESS_TOKEN` (gitignored) |
| `supabase_sse_bridge.mjs` | SSE bridge — REST wrapper at `localhost:3100` |
| `dist/` | Local MCP binary (⚠️ broken — missing `common-tags` dep, use npx instead) |
| `package.json` | Dependencies for `@supabase/mcp-server-supabase` |
