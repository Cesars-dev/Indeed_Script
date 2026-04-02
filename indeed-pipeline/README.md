# Indeed Auto-Apply Pipeline

> Automated job application system — AdsPower + Playwright + Gemini Vision
> **Last updated:** 2026-03-13 (session 4)

---

## What This Does

Scrapes Indeed job listings via N8N + Apify, then automatically applies using 19 rotating anti-detect browser profiles. SmartApply v2 router uses DOM scanning + Gemini Vision to fill forms — zero hardcoded selectors.

**Stack:** AdsPower (fingerprint spoofing) → rebrowser-playwright CDP → SmartApply v2 (deterministic → Flash → Pro) → Supabase fire-and-forget log

---

## Frameworks

| Framework | File | When to use |
|-----------|------|-------------|
| **DOE** | [`../DOE_FRAMEWORK.md`](../DOE_FRAMEWORK.md) | Task routing: Directive → Orchestration → Execution |
| **Surgeon** | [`../SURGEON_FRAMEWORK.md`](../SURGEON_FRAMEWORK.md) | Code changes: Audit → Plan → Cross-ref → Execute |

---

## Reading Order (For Agents)

1. **[`NEXT_STEPS.md`](NEXT_STEPS.md)** — your task list (P5–P7 remaining)
2. **[`directives/memory.md`](directives/memory.md)** — current state, what's done
3. **[`directives/execution_map.md`](directives/execution_map.md)** — what "go" means
4. **Relevant [`directives/`](directives/) files** — deep knowledge per topic
5. **[`../docs/what_didnt/`](../docs/what_didnt/)** — dead ends, NEVER retry

---

## Current State

| Stage | Status |
|-------|--------|
| VPS AdsPower headless (port 30025) | ✅ systemd |
| rebrowser-playwright CDP | ✅ fixes `Runtime.enable` leak |
| SmartApply v2 (6-shot router) | ✅ deterministic → Flash → Pro |
| CF Turnstile bypass (Gemini visual) | ✅ `_solve_cf()` |
| Fingerprint sync (19 profiles) | ✅ dynamic injection |
| Per-profile applicant data | ✅ from Supabase |
| Execution logging | ✅ fire-and-forget async |
| Warmups (10-15s max) | ✅ optimized |
| Session activation (18 profiles) | ❌ P5 — manual |
| Search page warmup | ❌ P6 — not started |
| Per-profile resume download | ❌ P7 — blocked on Docs URLs |

---

## Folder Structure (DOE-aligned)

```
indeed-pipeline/
├── README.md                ← this file
├── NEXT_STEPS.md            ← live task list
│
├── directives/              ← D LAYER — goals, memory, SOPs
│   ├── memory.md            ← current state, session log
│   ├── execution_map.md     ← "go" decision tree
│   ├── infrastructure.md    ← VPS, AdsPower, Supabase, ports
│   ├── browser_automation.md ← CDP rules, stealth, why Playwright
│   ├── sessions_accounts.md ← profiles, sessions, accounts
│   ├── smartapply_form.md   ← form flow, Gemini loop
│   ├── stealth.md           ← fingerprint/CF stealth decisions
│   └── fingerprint_sync.md  ← fingerprint → Supabase flow
│
├── src/                     ← E LAYER — application code
│   ├── playwright_indeed.py ← 🔥 browser engine
│   ├── smartapply/          ← SmartApply v2 router
│   │   ├── router.py        ← 6-shot engine
│   │   ├── logger.py        ← fire-and-forget Supabase logger
│   │   ├── dom_scanner.py   ← DOM scan (<100ms)
│   │   ├── handlers.py      ← deterministic form handlers
│   │   └── gemini_fallback.py
│   ├── supabase_client.py   ← DB helpers
│   ├── apply_runner.py      ← job loop
│   ├── orchestrator.py      ← cron entry point
│   ├── webhook_server.py    ← HTTP receiver
│   └── gdrive_client.py     ← Google Drive download
│
├── scripts/                 ← E LAYER — utility scripts
│   ├── batch_test.py        ← primary test runner (stdin URLs)
│   ├── vps_adspower.sh      ← AdsPower lifecycle
│   ├── audit_keys.sh        ← credential leak scanner
│   └── ...
│
├── docs/                    ← reference docs
│   ├── gemini_prompt.md
│   └── adspower_kernel_prompt.md
│
├── archive/                 ← completed work (read-only)
│
├── supabase_schema.sql      ← DB schema reference
├── requirements.txt         ← Python deps
└── resume_oswaldo.pdf       ← shared resume
```

### MCP Stack (`../mcp-stack/`) — READ BEFORE QUERYING

MCP server configs and bridges live at the **project root** — `Indeed_Script/mcp-stack/`.

> **🚨 AGENT RULE:** Before running any Supabase, Firecrawl, AdsPower, or Google API query, **read the corresponding MD file** below. It contains the exact proven methods, env file paths, and gotchas that prevent wasted retries.

```
mcp-stack/
├── adspower/
│   └── adspower_mcp_config.md      ← 🔥 READ THIS FIRST — dual instance, API, tunnel setup
├── google/
│   ├── google_mcp_config.md        ← 🔥 READ THIS FIRST — OAuth, SA, Drive download, Sheet CSV
│   ├── oauth_client.json           ← OAuth client credentials (gitignored)
│   ├── oauth_token.json            ← OAuth refresh token (gitignored)
│   └── google_service_account.json ← Service account key (gitignored)
├── supabase/
│   ├── supabase_mcp_config.md      ← 🔥 READ THIS FIRST — proven query methods
│   ├── .env                        ← clean SUPABASE_ACCESS_TOKEN (gitignored)
│   ├── connection_config.json      ← drop-in MCP config for agents
│   └── supabase_sse_bridge.mjs     ← SSE bridge (localhost:3100)
└── firecrawl/
    └── firecrawl_mcp_config.md     ← 🔥 READ THIS FIRST — connection + REST fallback
```

| Service | How to Query | Config MD |
|---------|-------------|-----------|
| **AdsPower** | REST API (GET for reads, POST for updates) | `mcp-stack/adspower/adspower_mcp_config.md` |
| **Google** | OAuth token or Service Account (Drive, Sheets, Docs) | `mcp-stack/google/google_mcp_config.md` |
| **Supabase** | REST API for DML, `npx` MCP for DDL | `mcp-stack/supabase/supabase_mcp_config.md` |
| **Firecrawl** | npx stdio or REST API | `mcp-stack/firecrawl/firecrawl_mcp_config.md` |

### AdsPower — Dual Instance

> **Full docs:** `mcp-stack/adspower/adspower_mcp_config.md`

| Instance | Port | Purpose | Status |
|----------|------|---------|--------|
| **VPS** (headless, systemd) | `30025` | **Pipeline execution** — browser start/stop, apply jobs | ✅ Always on (systemd) |
| **Mac** (desktop GUI) | `50325` | **Management only** — profile config, proxy changes | ✅ Always on (`autossh` tunnel) |

**⚠️ Key rules:**
- The **pipeline only uses port `30025`** (VPS). Port `50325` is never referenced in pipeline code.
- The Mac tunnel (`50325`) is **persistent via `autossh`** — assume it's always up. If it's down, ask the user to re-run `autossh` on Mac (see `mcp-stack/adspower/adspower_mcp_config.md`). **Do NOT create alternative tunnels or workarounds.**
- Both instances share the same account, profiles, and groups. Changes on one sync to the other.
- Groups: `indeed` (13 profiles), `residential_indeed` (6 profiles). All on residential proxies.

---

## Critical Rules

1. **`rebrowser_playwright.connect_over_cdp(f"http://127.0.0.1:{debug_port}")`** — NOT `connection_url`
2. **AdsPower `browser/start` = GET**, not POST
3. **`tab[0]`** = AdsPower internal page — NEVER touch. Work on `tab[1]` only
4. **Port `30025`** = the only AdsPower port. Local on VPS. No tunnels.
5. **`window.scrollBy()` is banned** — use `page.mouse.wheel()` (trusted WheelEvent)
6. **`page.hover()` is banned** for behavioral actions — use Bezier `human_move_mouse()`
7. **Never hardcode credentials** — always from `.env` via `python-dotenv`
8. **Sessions need 24h aging** after fresh login before running scripts

---

## Quick Reference

```bash
# Run test
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py

# Deploy
cd /root/indeed-pipeline && git pull && systemctl restart indeed-webhook

# AdsPower
systemctl start xvfb && systemctl start adspower
systemctl status adspower xvfb
```

---

## What to do next

👉 **[`NEXT_STEPS.md`](NEXT_STEPS.md)** — updated every session.
