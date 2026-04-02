# Firecrawl MCP Config

Everything a new agent needs to connect to **Firecrawl** for web scraping. Read this file, connect in 3 seconds.

> **API:** `https://api.firecrawl.dev/v1`  
> **Auth:** `SUGARPIXELS_FIRECRAWL_API_KEY` from `.env`

---

## Quick Start

### Option A: MCP Server (Streamable HTTP — for agents)

```bash
# Start Firecrawl MCP on port 3020
PORT=3020 HTTP_STREAMABLE_SERVER=true \
  FIRECRAWL_API_KEY=$(grep SUGARPIXELS_FIRECRAWL_API_KEY .env | cut -d= -f2) \
  npx -y firecrawl-mcp > /tmp/firecrawl_mcp.log 2>&1 &
```

Test:
```bash
curl -s -X POST http://localhost:3020/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Option B: Direct REST (no MCP needed — for scripts)

```python
import os, requests
from dotenv import load_dotenv
load_dotenv()

KEY = os.getenv("SUGARPIXELS_FIRECRAWL_API_KEY")
HEADERS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def scrape(url: str) -> str:
    r = requests.post("https://api.firecrawl.dev/v1/scrape", headers=HEADERS, json={
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True
    })
    data = r.json()
    if data.get("success"):
        return data["data"]["markdown"]
    raise Exception(f"Scrape failed: {data}")
```

### Node.js One-Liner

```js
const key = require('fs').readFileSync('.env','utf8')
    .match(/SUGARPIXELS_FIRECRAWL_API_KEY=(.+)/)[1].trim();

fetch('https://api.firecrawl.dev/v1/scrape', {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: 'https://example.com', formats: ['markdown'], onlyMainContent: true })
}).then(r => r.json()).then(d => console.log(d.data?.markdown?.substring(0, 500)));
```

---

## MCP Config (for IDE / agent setup)

Drop this into your agent's `mcp.json`:

```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "${SUGARPIXELS_FIRECRAWL_API_KEY}"
      }
    }
  }
}
```

---

## Available Tools (12)

| Tool | Endpoint | Use For |
|---|---|---|
| `firecrawl_scrape` | `POST /v1/scrape` | Single page → markdown |
| `firecrawl_crawl` | `POST /v1/crawl` | Multi-page site crawl |
| `firecrawl_search` | `POST /v1/search` | Web search → top results as markdown |
| `firecrawl_map` | `POST /v1/map` | Discover all URLs on a site |
| `firecrawl_extract` | `POST /v1/extract` | Structured data extraction with LLM |
| `firecrawl_agent` | — | Autonomous web research agent |
| `firecrawl_browser_*` | — | Browser session control (CDP) |

---

## Gotchas

1. **Always use `onlyMainContent: true`** — strips nav/footer noise.
2. **Private/auth-gated pages fail** — Firecrawl doesn't handle login flows.
3. **Never hardcode the API key** — always `os.getenv("SUGARPIXELS_FIRECRAWL_API_KEY")`.
4. **REST fallback always works** — even if MCP server is down, the REST API at `https://api.firecrawl.dev/v1` is always available.
