# Supabase MCP Config

Everything a new agent needs to connect to **Supabase** via MCP. Read this file, connect in 3 seconds.

> **Project Ref:** `rvjuymgbarospuwkkxhc`  
> **Schema:** `linkedin_hunter`  
> **Auth:** `SUPABASE_ACCESS_TOKEN` from `.env`

---

## Quick Start

### Option A: Stdio (direct — for scripts & agents)

```bash
# Start the MCP server over stdio
node supabase-mcp-kit/dist/transports/stdio.js --project-ref rvjuymgbarospuwkkxhc
```

Requires `SUPABASE_ACCESS_TOKEN` in environment.

### Option B: SSE Bridge (REST — for services & dashboards)

```bash
# Start the SSE bridge (runs on localhost:3100)
node supabase-mcp-kit/supabase_sse_bridge.mjs
```

Endpoints:
| Endpoint | Method | Purpose |
|---|---|---|
| `/sse` | GET | MCP SSE stream (MCP clients connect here) |
| `/messages?sessionId=X` | POST | JSON-RPC messages |
| `/query` | POST | Simple REST: `{ "sql": "..." }` → `{ "rows": [...] }` |
| `/health` | GET | Health check |

### Option C: In-Memory Stream (programmatic — for Node.js apps)

```js
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamTransport } from '@supabase/mcp-utils';

const clientTransport = new StreamTransport();
const serverTransport = new StreamTransport();

// Wire them together
clientTransport.readable.pipeTo(serverTransport.writable);
serverTransport.readable.pipeTo(clientTransport.writable);

const client = new Client(
  { name: 'MyAgent', version: '1.0' },
  { capabilities: {} }
);

await server.connect(serverTransport);
await client.connect(clientTransport);
```

---

## MCP Config (for IDE / agent setup)

Drop this into your agent's `mcp.json` or equivalent:

```json
{
  "mcpServers": {
    "supabase_linkedin": {
      "command": "node",
      "args": [
        "<path-to>/supabase-mcp-kit/dist/transports/stdio.js",
        "--project-ref",
        "rvjuymgbarospuwkkxhc"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "${SUPABASE_ACCESS_TOKEN}"
      }
    }
  }
}
```

---

## Available Tools

### `execute_sql`
Run SELECT / INSERT / UPDATE / DELETE queries.

```js
arguments: {
  query: "SELECT * FROM linkedin_hunter.qualified_leads LIMIT 5;"
}
```

- Always prefix tables with `linkedin_hunter.`
- Returns JSON wrapped in XML-like tags (see Parsing below)
- **NOT** for DDL (CREATE/DROP/ALTER) — use `apply_migration`

### `apply_migration`
Run DDL operations (CREATE TABLE, ALTER TABLE, DROP TABLE).

```js
arguments: {
  name: "add_column_20260309",  // MUST be globally unique — use timestamps
  query: "ALTER TABLE linkedin_hunter.qualified_leads ADD COLUMN IF NOT EXISTS my_col TEXT DEFAULT ''; NOTIFY pgrst, 'reload schema';"
}
```

- `name` must be **globally unique** across ALL migrations ever
- Always end with `NOTIFY pgrst, 'reload schema';`
- Multi-statement SQL is fine — semicolon-separated in one string

### `list_tables`
List all tables with columns, types, and row counts.

```js
arguments: {
  schemas: ["linkedin_hunter"]
}
```

### `list_migrations`
List all applied migrations.

```js
arguments: {}
```

---

## Parsing Responses

`execute_sql` wraps results in XML-like tags:

```
"Below is the result... <untrusted-data-UUID>[{"col":"val"}]</untrusted-data-UUID>..."
```

Parse with:
```js
const text = response.result?.content?.[0]?.text || '';
const unescaped = text.replace(/\\n/g, '\n').replace(/\\"/g, '"');
const match = unescaped.match(/\[.*?\]/s);
const rows = match ? JSON.parse(match[0]) : [];
```

---

## Node.js Boilerplate (stdio RPC)

```js
import { readFileSync } from 'fs';
import { spawn } from 'child_process';
import { createInterface } from 'readline';
import path from 'path';

const envFile = readFileSync(path.join(process.cwd(), '.env'), 'utf-8');
const token = envFile.match(/SUPABASE_ACCESS_TOKEN=(.*)/)?.[1]?.trim();

const server = spawn('node', [
  path.join(__dirname, 'dist/transports/stdio.js'),
  '--project-ref', 'rvjuymgbarospuwkkxhc'
], {
  env: { ...process.env, SUPABASE_ACCESS_TOKEN: token },
  stdio: ['pipe', 'pipe', 'pipe']
});

let msgId = 1;
const pending = new Map();
createInterface({ input: server.stdout }).on('line', l => {
  try { const m = JSON.parse(l); if (m.id && pending.has(m.id)) pending.get(m.id)(m); } catch {}
});

function rpc(method, params) {
  return new Promise(r => {
    const id = msgId++;
    pending.set(id, r);
    server.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
    setTimeout(() => { pending.delete(id); r({ error: 'timeout' }); }, 30000);
  });
}

// Always initialize first
await rpc('initialize', {
  protocolVersion: '2024-11-05',
  capabilities: {},
  clientInfo: { name: 'my-agent', version: '1.0' }
});

// Query
const r = await rpc('tools/call', {
  name: 'execute_sql',
  arguments: { query: "SELECT count(*) FROM linkedin_hunter.qualified_leads;" }
});
console.log(r.result?.content?.[0]?.text);

server.kill();
```

---

## Schema: `linkedin_hunter`

| Table | Purpose | Upsert Key |
|---|---|---|
| `qualified_leads` (75 cols) | Final enriched leads | `linkedin_url` |
| `discovery_evaluations` (33 cols) | ICP gate audit trail | `linkedin_url` |
| `raw_job_postings` (29 cols) | Phase 1A raw jobs | `job_url` |
| `pipeline_runs` (23 cols) | Run tracking | — |
| `raw_social` (18 cols) | Social post storage | — |
| `search_keywords` (11 cols) | Keyword rotation | — |
| `search_locations` (9 cols) | Location rotation | — |

---

## Common Gotchas

1. **Migration names must be unique.** Reusing a name silently fails (duplicate key error). Use timestamps: `add_columns_20260309`.
2. **PostgREST schema cache.** After DDL changes, always include `NOTIFY pgrst, 'reload schema';` or new columns won't be visible.
3. **`execute_sql` is for DML only.** Use `apply_migration` for DDL.
4. **Multi-statement SQL works in `apply_migration`** — put everything in one `query` string.
5. **Don't use `apply_migration` for DML** (INSERT/UPDATE/DELETE). Use `execute_sql`.

---

## What's in This Kit

| File | Purpose |
|---|---|
| `supabase_mcp_config.md` | This guide — Supabase connection reference |
| `connection_config.json` | Full MCP config with tools, schema, and examples |
| `supabase_sse_bridge.mjs` | SSE bridge — REST wrapper at `localhost:3100` |
| `dist/` | Supabase MCP server binary (stdio transport) |
| `package.json` | Dependencies for `@supabase/mcp-server-supabase` |


