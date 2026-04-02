# 🤖 AGENTS.md — Single Source of Truth

> Read this file first. Every session. Every agent.
> This is everything you need: setup, security, and how to work.

---

## FIRST — Ask: "Where are we at?"

> Do not assume. Do not guess. Ask the user.

```
┌─────────────────────────────────────────────────────┐
│  "Where are we at?"                                 │
│                                                     │
│  LOCAL MACHINE?  → Phase 1: Bootstrap               │
│    • Create repo, preflight, push, VPS setup        │
│    • See: PHASE 1 below                             │
│                                                     │
│  VPS?            → Phase 2: DOE (get to work)       │
│    • Place DOE AGENTS.md + README at project root   │
│    • Read tasks/ → start building                   │
│    • See: PHASE 2 below                             │
└─────────────────────────────────────────────────────┘
```

## ⚠️ Confirmation Rule — Non-Negotiable

- **Never auto-chain steps.** Report output, wait for user sign-off.
- **Never commit or push without user confirmation.** Always ask first.
- If a step fails → stop, report, wait for instructions.
- If output looks unexpected → stop, report, ask.

---

# PHASE 1 — BOOTSTRAP (Local Machine)

> You are on the local machine. Set up the project workspace.
> Run this once per project. After this, all work happens on VPS (Phase 2).

## 1. Preflight Check (before EVERY push — not just bootstrap)

```
PREFLIGHT SEQUENCE (agent-driven — not a script):

1. KEYHOUND SCAN
   → Run: ./agent_os/scripts/keyhound.sh
   → If secrets found → STOP. Report. Fix them. Do NOT proceed.

2. GITIGNORE VERIFICATION
   → Verify .env is in .gitignore:  grep "^\.env" .gitignore
   → If missing or no .gitignore exists → fix it FIRST, then re-scan

3. USER CONFIRMATION (mandatory gate)
   → Report scan results to user
   → Say: "✅ Preflight clean. Ready to push. Confirm?"
   → ⛔ DO NOT push until user explicitly says "go" / "yes" / "confirmed"

4. SAFE PUSH
   → Only after user confirms:
     ./agent_os/scripts/gatekeeper.sh "your commit message"

5. VPS SYNC
   → Pull latest on VPS:
     ./agent_os/scripts/vps.sh pull
```

## 2. Bootstrap (new project setup)

```
BOOTSTRAP SEQUENCE:

1. CREATE REPO (MCP — repo creation only)
   → MCP: create_repository("<project-name>", private=true)
   → Note the repo URL

2. LOCAL GIT SETUP
   → git init
   → git remote add origin <repo-url>
   → Verify: git remote -v

3. GITIGNORE CHECK
   → Must contain at minimum: .env, *.env, .env.*
   → Copy from agent_os/.gitignore if needed

4. PREFLIGHT (non-negotiable)
   → Run keyhound → report → wait for user confirmation
   → ⛔ DO NOT proceed if secrets detected

5. FIRST PUSH (user must confirm)
   → ./agent_os/scripts/gatekeeper.sh "Initial commit"

6. VPS SETUP
   → ./agent_os/scripts/vps.sh "mkdir -p /home/julio/projects/<project-name>"
   → ./agent_os/scripts/vps.sh "cd /home/julio/projects && git clone <repo-url>"
   → ./agent_os/scripts/vps.sh pull

7. SYNC .ENV TO VPS
   → ./agent_os/scripts/tunnel_env.sh
   → Verify: ./agent_os/scripts/vps.sh "ls -la /home/julio/projects/<project-name>/.env"

8. SCAFFOLD DOE STRUCTURE (the handoff)
   → Create at project root:

     tasks/                         ← drop task .md files here — the goals
     directives/memory.md          ← current state, what happened, what's next
     directives/execution_map.md   ← decision tree: when user says "go", run THIS
     execution/                    ← empty — scripts go here as you build

   → Create project-root AGENTS.md:
     • Copy ONLY Phase 2 (DOE) from this file — strip all bootstrap/preflight
     • This is the agent's primary operating file on VPS
     • Infrastructure (scripts, security) stays in agent_os/
     • Reference agent_os/ for pushes, VPS sync, keyhound — nothing else

   → Create project-root README.md:
     • Describe the project (what it does, how it works)
     • Document the folder structure (directives/, execution/, agent_os/)
     • This is the project's public-facing doc

   → Push scaffold: preflight → gatekeeper → vps pull
```

### Naming Convention
**GitHub repo name = VPS folder name.** Always `-` or `_`, never spaces.

```
GitHub repo:  my-new-project
VPS folder:   /home/julio/projects/my-new-project
```

### Bootstrap Rules
- Steps 1-3: agent does these (safe local ops)
- Step 4: ALWAYS wait for user confirmation
- Step 5: NEVER push without user green light
- Steps 6-8: agent does these after push

**✅ Bootstrap complete → proceed to Phase 2.**

---

# PHASE 2 — DOE (VPS — Get to Work)

> You are on the VPS. This is where ALL work happens.

## VPS Landing Sequence

```
1. CLEAN UP AGENTS.md (first time only):
   → Delete Phase 1 (bootstrap/preflight) from this file — it's done, you're on VPS
   → DOE framework is already here — it stays

2. REORGANIZE agent_os/ (first time only):
   → Create agent_os/vps/ and move VPS-related files into it:
       scripts/vps.sh             → vps/vps.sh
       scripts/tunnel_env.sh      → vps/tunnel_env.sh
       docs/MODE_1_IDE_REMOTE.md  → vps/MODE_1_IDE_REMOTE.md
       docs/MODE_2_CLI_AGENTS.md  → vps/MODE_2_CLI_AGENTS.md
       docs/MODE_3_SWARM.md       → vps/MODE_3_SWARM.md
   → Security scripts STAY in scripts/:
       scripts/gatekeeper.sh      ← stays (used everywhere)
       scripts/keyhound.sh        ← stays (used everywhere)
   → Update all script paths in AGENTS.md and README.md to reflect new locations
   → Create DOE folders if not present (tasks/ already exists from bootstrap):
       directives/       ← D layer (memory.md, execution_map.md)
       orchestration/    ← O layer (decision logs, routing notes)
       execution/        ← E layer (deterministic scripts)
   → Update README.md to cover the project folder structure
   → Commit + push (with preflight + user confirmation)

3. ASK MODE:
   → "Which mode are we using?"
     (1) IDE Remote   — Cursor/VS Code connected to VPS
     (2) CLI Agent    — Claude or Gemini CLI on VPS
     (3) Swarm        — multi-agent parallel tmux
   → Read the matching doc in agent_os/vps/

4. READ TASKS:
   → List .md files in tasks/
   → Ask user: "Which task?" or "What's the goal?"

5. DOE — start working (see below)
```

## The 3 Layers

```
┌─────────────────────────────────────────────────────────┐
│  D — Directive       What to do (written by human/agent)│
│      directives/     Goals, rules, edge cases, SOPs     │
└─────────────────────────────────┬───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────┐
│  O — Orchestration   You. Decision making.              │
│      (this agent)    Read → Route → Handle → Update     │
└─────────────────────────────────┬───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────┐
│  E — Execution       Deterministic scripts              │
│      execution/      Python, bash — do the actual work  │
└─────────────────────────────────────────────────────────┘
```

## D — Directive (What to do)

- Written in Markdown, lives in `directives/`
- Defines: goals, inputs, tools to use, outputs, edge cases, constraints
- Think of it as an SOP — what you'd give a competent mid-level employee
- **Directives are living documents.** Update them when you learn something new
- Do NOT overwrite directives without asking

**Key files:**
```
directives/
├── memory.md          ← current project state, what broke, what's next
├── execution_map.md   ← decision tree: when user says "go", run THIS
└── *.md               ← task-specific SOPs
```

## O — Orchestration (Your role)

You are the O layer. Your job:

1. **Read** the relevant directive(s) first — always
2. **Route** — decide which script to call, in which order, with which inputs
3. **Handle errors** — read stack trace, fix script, test, move on
4. **Update** — write what you learned back into the directive

**Rules:**
- Never do manually what a script can do deterministically
- Never run paid API calls (Apify, OpenAI, Anthropic) without explicit user confirmation
- Never create new directives without asking first
- Be the decision layer. Not the execution layer.

## E — Execution (The work)

- Deterministic scripts in `execution/` (Python, bash)
- Handles: API calls, data processing, database writes, file ops
- Reliable and testable — if you'd do something more than once, it must be a script
- Scripts receive inputs via args or `.env`. Never inline credentials.

**Key rule:** If you catch yourself doing something repetitive manually — stop. Write a script, put it in `execution/`, then call it.

## Self-Annealing Loop

When something breaks — don't escalate. Fix it and make the system stronger:

```
Error occurs → read stack trace → fix the script → test it → update the directive
→ System is now stronger than before ✅
```

> **Exception:** If the fix requires re-running paid API calls → **confirm with user first**.

## Session Flow (every session)

```
1. Read tasks/                       ← what needs to be done (the goals)
2. Read directives/memory.md        ← what happened last session
3. Read directives/execution_map.md ← what "go" means right now
4. Pick a task or ask the user      ← or pick up from memory.md
5. Route to scripts in execution/   ← you orchestrate, scripts execute
6. Handle any errors                ← self-anneal
7. Update directives with learnings ← memory.md, execution_map.md
8. Preflight + safe push            ← keyhound → user confirm → gatekeeper
9. VPS sync                         ← ./agent_os/scripts/vps.sh pull
```

---

# SECURITY RULES (Non-Negotiable)

1. **Never hardcode secrets.** API keys, tokens, passwords → `.env` only. Reference via `os.getenv("KEY_NAME")`.
2. **`.env` is never in git.** Use `./agent_os/scripts/tunnel_env.sh` to sync to VPS.
3. **Every push goes through the Preflight Check + `gatekeeper.sh`.** No exceptions.
4. **Run `keyhound.sh`** before pushing to a new repo, or anytime something feels off.
5. **Never create or modify `.keyhound-ignore`** without a direct, explicit instruction from the user. If keyhound flags something → report it and stop.
6. **Never push code via MCP.** Do NOT use `push_files`, `create_or_update_file`, or any GitHub MCP tool that writes file content to a repository. MCP is for **repo creation and reading only**. ALL code pushes go through `gatekeeper.sh`.
7. **Never auto-push.** Always run the Preflight Check (keyhound → gitignore → user confirmation) before calling `gatekeeper.sh`.

---

# INFRASTRUCTURE REFERENCE

## Scripts

| Script | What it does |
|---|---|
| `gatekeeper.sh` | Pre-push 3-pass secret scan. Wraps `git push`. Clean → auto commits + pushes. Dirty → blocks. |
| `keyhound.sh` | Full project-wide secret audit. Same 3-pass logic. Use before pushes or after major changes. |
| `tunnel_env.sh` | Syncs `.env` to VPS via SCP. Scans for exposed files first. |
| `vps.sh` | SSH tunnel + VPS control: `pull`, `push`, `status`, `attach`, or any command. |

### Quick Commands

```bash
./agent_os/scripts/keyhound.sh                     # preflight scan
./agent_os/scripts/gatekeeper.sh "message"          # safe push
./agent_os/scripts/vps.sh pull                      # sync VPS
./agent_os/scripts/vps.sh "python3 execution/x.py"  # run on VPS
./agent_os/scripts/vps.sh status                    # check VPS
./agent_os/scripts/tunnel_env.sh                    # sync .env to VPS
```

## MCP Connections

> MCP is for service access and repo creation only — **NEVER for pushing code.**

### Supabase — Database Access

| | |
|---|---|
| **Config** | `mcp-stack/supabase/supabase_mcp_config.md` |
| **Projects** | Indeed (`uckkgnqlehprbpypcgjc`), LinkedIn Leads (`rvjuymgbarospuwkkxhc`) |
| **Auth** | `SUPABASE_ACCESS_TOKEN` from `.env` |
| **Tools** | `execute_sql` (DML), `apply_migration` (DDL), `list_tables`, `list_migrations` |

### Firecrawl — Web Scraping

| | |
|---|---|
| **Config** | `mcp-stack/firecrawl/firecrawl_mcp_config.md` |
| **API** | `https://api.firecrawl.dev/v1` |
| **Auth** | `SUGARPIXELS_FIRECRAWL_API_KEY` from `.env` |
| **Tools** | `firecrawl_scrape`, `firecrawl_crawl`, `firecrawl_search`, `firecrawl_map`, `firecrawl_extract` |

### GitHub — Repo Management (MCP)

| | |
|---|---|
| **Auth** | `GITHUB_TOKEN` from `.env` |
| **Allowed** | `create_repository`, `get_file_contents`, `search_repositories`, read operations |
| **⛔ NEVER** | `push_files`, `create_or_update_file` — bypasses all security scans |

## Execution Modes

| Mode | When to use | Details |
|---|---|---|
| **1 — IDE Remote** | Long sessions, full IDE | `docs/MODE_1_IDE_REMOTE.md` |
| **2 — CLI Agents** | Quick tasks, autonomous runs | `docs/MODE_2_CLI_AGENTS.md` |
| **3 — Swarm** | Parallel independent tasks | `docs/MODE_3_SWARM.md` |

Default: Mode 1. Escalate only if too slow.

---

# FILE MAP

```
agent_os/
├── AGENTS.md              ← you are here (single source of truth)
├── README.md              ← reference archive
│
├── scripts/
│   ├── gatekeeper.sh      ← safe push (pre-push secret scan)
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
│   ├── supabase/          ← Supabase MCP kit
│   └── firecrawl/         ← Firecrawl config
│
└── tasks/                 ← drop task .md files here

PROJECT ROOT (after bootstrap):
├── AGENTS.md              ← this file (copied via agent_os)
├── directives/
│   ├── memory.md          ← current state + learnings
│   └── execution_map.md   ← what to run and when
└── execution/             ← deterministic scripts
```

---

> _Last updated: 2026-03-09_
