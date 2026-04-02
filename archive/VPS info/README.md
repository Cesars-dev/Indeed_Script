# 🤖 Agent OS — Reference Manual

> **For the agent's operating instructions, read `AGENTS.md`.**
> This file is the reference archive — detailed docs on scripts, VPS setup, MCP connections, and framework philosophy.

---

## Philosophy

1. **VPS is the compute engine. Mac is the control panel.** Heavy work runs on the remote VPS — your local machine stays light and fast.
2. **GitHub is the mirror.** All code flows through git. Nothing is lost, nothing is out of sync.
3. **Security is non-negotiable.** API keys never touch source files. Every push is scanned before it leaves.

---

## System Architecture

```
Mac (architecture, deployment & debug only)
   │
   ├─► GitHub ──────────────► VPS (all coding & execution)
   │   (mirror)                /home/julio/projects/<repo>/
   │
   └─► SSH tunnel (scripts/vps.sh)
```

### Sync Cycle

```
[Mac] preflight → gatekeeper → GitHub → [VPS] vps.sh pull → work → gatekeeper → [Mac] git pull
```

---

## Scripts Reference

### gatekeeper.sh — Safe Push Protocol

```bash
./agent_os/scripts/gatekeeper.sh "your commit message"
```

3-pass secret scanner that wraps every `git push`:
- **Pass 1:** Known vendor prefixes (OpenAI, Anthropic, GitHub PAT, Supabase JWT, Stripe, etc.)
- **Pass 2:** Variable name triggers (`_KEY`, `_TOKEN`, `_SECRET` + 15-char value)
- **Pass 3:** Unknown vendor format catch (short prefix + separator + 20+ alphanum)
- ✅ Clean → `git add . && git commit && git push origin main`
- 🚨 Dirty → blocks push, shows exact file + line

### keyhound.sh — Full Project Audit

```bash
./agent_os/scripts/keyhound.sh
```

Same 3-pass logic as gatekeeper, but scans the **entire project** (not just diffs).
- Scans: `.py .js .ts .sh .md .txt .json .toml .yaml .yml`
- Skips: `.venv/ node_modules/ archive/ .git/`
- Excludes: `.env` (by design — secrets live there)
- Supports `.keyhound-ignore` for per-project exceptions

### tunnel_env.sh — Secure .env Sync

```bash
./agent_os/scripts/tunnel_env.sh           # scan + send
./agent_os/scripts/tunnel_env.sh --dry-run # scan only
```

- Finds all `.env` files in the project
- Checks each is gitignored (skips exposed ones)
- Shows key preview (first 8 chars + `***`)
- Sends via SCP to matching VPS path
- Auto-derives VPS path from git remote URL

### vps.sh — VPS Control

```bash
./agent_os/scripts/vps.sh              # attach to tmux session
./agent_os/scripts/vps.sh "command"    # run command on VPS
./agent_os/scripts/vps.sh pull         # git pull on VPS
./agent_os/scripts/vps.sh push "msg"   # safe push from VPS
./agent_os/scripts/vps.sh status       # connection + git status
./agent_os/scripts/vps.sh reconnect    # re-open SSH master
```

- Uses SSH multiplexing (ControlMaster) for persistent connections
- Auto-reconnects if session drops
- Derives project path from git remote URL (convention: repo name = VPS folder name)

---

## MCP Connections (Detailed)

### Supabase

| | |
|---|---|
| **Config doc** | `mcp-stack/supabase/supabase_mcp_config.md` |
| **Projects** | Indeed Auto-Apply (`uckkgnqlehprbpypcgjc`), LinkedIn Leads (`rvjuymgbarospuwkkxhc`) |
| **Auth** | `SUPABASE_ACCESS_TOKEN` from `.env` |
| **Key tools** | `execute_sql` (DML), `apply_migration` (DDL), `list_tables`, `list_migrations` |
| **Transports** | Stdio (scripts/agents), SSE bridge (`localhost:3100`), In-memory stream (Node.js) |
| **Gotchas** | Migration names must be unique (use timestamps). After DDL → `NOTIFY pgrst, 'reload schema';` |

### Firecrawl

| | |
|---|---|
| **Config doc** | `mcp-stack/firecrawl/firecrawl_mcp_config.md` |
| **API** | `https://api.firecrawl.dev/v1` |
| **Auth** | `SUGARPIXELS_FIRECRAWL_API_KEY` from `.env` |
| **Key tools** | `firecrawl_scrape`, `firecrawl_crawl`, `firecrawl_search`, `firecrawl_map`, `firecrawl_extract` |
| **Transports** | MCP stdio (`npx -y firecrawl-mcp`), direct REST API |
| **Gotchas** | Always `onlyMainContent: true`. Auth-gated pages fail. REST fallback always works. |

### GitHub (MCP)

| | |
|---|---|
| **Auth** | `GITHUB_TOKEN` from `.env` |
| **Allowed** | `create_repository`, `get_file_contents`, `search_repositories`, `list_commits`, read operations |
| **⛔ NEVER** | `push_files`, `create_or_update_file` — bypasses all local security scans |

---

## Execution Modes (Detailed)

### Mode 1 — IDE Remote (Default)

```
Mac IDE (Cursor/VS Code) ──SSH──► VPS
```
Full IDE experience. Code on Mac, execute on VPS. See `docs/MODE_1_IDE_REMOTE.md`.

### Mode 2 — CLI Agents

```
VPS terminal → Claude CLI or Gemini CLI
```
Quick autonomous tasks. See `docs/MODE_2_CLI_AGENTS.md`.

### Mode 3 — Swarm

```
VPS tmux: orchestrator + up to 7 parallel agents
```
Independent parallel tasks. See `docs/MODE_3_SWARM.md`.

**Default: Mode 1. Escalate only if too slow.**

---

## Security Rules Summary

1. Never hardcode secrets → `.env` only
2. `.env` never in git → `tunnel_env.sh` for VPS sync
3. Every push → Preflight + `gatekeeper.sh`
4. `keyhound.sh` for periodic full audits
5. Never modify `.keyhound-ignore` without explicit user instruction
6. Never push code via MCP → `gatekeeper.sh` only
7. Never auto-push → always wait for user confirmation

---

## Bootstrap Summary

> Full details in `AGENTS.md` Phase 1, section 2.

```
1. CREATE REPO       → MCP: create_repository (private)
2. LOCAL GIT         → git init → git remote add origin
3. GITIGNORE         → verify .env excluded
4. PREFLIGHT         → keyhound → user confirm
5. FIRST PUSH        → gatekeeper.sh "Initial commit"
6. VPS SETUP         → vps.sh mkdir → clone → pull
7. TUNNEL ENV        → tunnel_env.sh
8. DOE SCAFFOLD      → directives/ + execution/
```

### Naming Convention
**GitHub repo name = VPS folder name.** Always `-` or `_`, never spaces.

---

## File Map

```
agent_os/
├── AGENTS.md              ← operating instructions (Phase 1 + Phase 2 + security)
├── README.md              ← you are here (reference archive)
│
├── scripts/
│   ├── gatekeeper.sh      ← safe push (3-pass secret scan)
│   ├── keyhound.sh        ← full project key audit
│   ├── tunnel_env.sh      ← sync .env to VPS
│   └── vps.sh             ← SSH tunnel + VPS control
│
├── docs/
│   ├── DOE_FRAMEWORK.md   ← standalone DOE reference
│   ├── MODE_1_IDE_REMOTE.md
│   ├── MODE_2_CLI_AGENTS.md
│   └── MODE_3_SWARM.md
│
├── mcp-stack/
│   ├── supabase/          ← Supabase MCP kit (binary + bridge + config)
│   └── firecrawl/         ← Firecrawl connection config
│
└── tasks/                 ← drop task .md files here
```

---

> _Last updated: 2026-03-09_
