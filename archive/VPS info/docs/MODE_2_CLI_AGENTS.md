# 🛠️ VPS Remote Toolkit — Offload Mac, Work Remotely

> **Main goal:** Stop running heavy processes on your Mac.
> Use the VPS for compute, storage, and AI execution — across any combination of modes.
> Your Mac stays light. The VPS does the work.

---

## The Three Modes

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR MAC                                 │
│                    (render + control only)                      │
└───────────┬──────────────────┬──────────────────┬──────────────┘
            │                  │                  │
            │ SSH + IDE UI     │ SSH + Terminal   │ SSH + Terminal
            ▼                  ▼                  ▼
    ┌────────────────┐ ┌───────────────┐ ┌────────────────┐
    │  MODE 1        │ │  MODE 2       │ │  MODE 3        │
    │  IDE Remote    │ │  Claude CLI   │ │  Gemini CLI    │
    │  (GUI vibe)    │ │  (agentic)    │ │  (agentic)     │
    └────────────────┘ └───────────────┘ └────────────────┘
            │                  │                  │
            └──────────────────┴──────────────────┘
                               │
                        VPS — all compute
                   /home/julio/projects/...
```

---

## VPS Context

| Item | Value |
|---|---|
| VPS IP | see `VPS_IP` in project `.env` |
| SSH User | see `VPS_USER` in project `.env` |
| SSH Key | see `VPS_SSH_KEY` in project `.env` |
| Projects dir | `/home/julio/projects/` |
| Agents/logs dir | `/home/julio/agents/` |
| Python | `python3` (3.12 — stable) |
| Claude Code | `source ~/.bashrc && claude` |
| Gemini CLI | `npx @google/gemini-cli` |
| Node | `node` v20.20.0 via nvm |

---

## Session Start Protocol (Every Session)

> ⚠️ Run one step at a time. Report output. Wait for user to confirm before next step.

```bash
# Step 1 — Local: scan for exposed keys
bash ./agent_os/scripts/keyhound.sh
```
→ Report output. Say: **"✅ Step 1 done. Proceed to Step 2?"** Wait for confirmation.

```bash
# Step 2 — Safe push: commit local pending work to GitHub
bash ./agent_os/scripts/gatekeeper.sh "WIP before session start"
```
→ Report output. Say: **"✅ Step 2 done. Proceed to Step 3?"** Wait for confirmation.

```bash
# Step 3 — VPS pull: get latest from GitHub onto VPS
bash ./agent_os/scripts/vps.sh "cd /home/julio/projects/YOUR_PROJECT && git pull origin main"
```
→ Report output. Say: **"✅ Step 3 done. Proceed to Step 4?"** Wait for confirmation.

```bash
# Step 4 — Tunnel env: sync .env to VPS (credentials must be on VPS before any agent work)
bash ./agent_os/scripts/tunnel_env.sh
```
→ Report output. Say: **"✅ Step 4 done. Ready to start work — what's the task?"**

---

## Mode 1 — IDE Remote (GUI, no CLI)

> Same as `docs/MODE_1_IDE_REMOTE.md`. Full IDE experience, GUI intact, everything runs on VPS.

### Setup (one-time)

Install **Remote - SSH** extension in Cursor or VS Code. Add to SSH config (`~/.ssh/config`):

```
Host vps-julio
  HostName <VPS_IP from .env>
  User <VPS_USER from .env>
  IdentityFile <VPS_SSH_KEY from .env>
  StrictHostKeyChecking no
```

### Connect

`Cmd+Shift+P` → **Remote-SSH: Connect to Host** → `vps-julio` → `Open Folder` → pick project.

### When to use
- You want full IDE experience (file tree, syntax highlighting, debugger, extensions)
- Long coding sessions
- Working across multiple projects
- You want to feel like nothing changed — just faster and offloaded

---

## Mode 2 — Claude Code CLI

> Claude runs as an autonomous coding agent directly on the VPS via SSH.
> You give it a task — it reads files, edits code, runs commands, writes output.

> ⚠️ **Auth rule — non-negotiable:**
> Claude Code CLI authenticates via **OAuth login only** — browser-based, session token stored on VPS.
> **Never** pass `ANTHROPIC_API_KEY` to `claude`. Never set it as an env var for the CLI.
> The API key in `.env` is for Python/SDK scripts only. If the token expires → user must re-login.
> **If Anthropic's auth service is down or login fails → switch to Gemini CLI (Mode 3).**

### Re-authenticate (when token expires)

```bash
# Attach to VPS interactively, then run claude to trigger re-auth
bash ./agent_os/scripts/vps.sh attach
# Inside VPS:
source ~/.bashrc
claude   # prints a URL → open in browser → login → token refreshed
```

### Non-interactive (fire and forget)

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 bash << 'EOF'
source ~/.bashrc
cd /home/julio/projects/cold-linkedin-outreach
claude --print "Read AGENTS.md first. Your task: [describe task precisely]. 
Write output to execution/output.json when done. Do not ask questions." \
  2>&1 | tee ~/agents/claude-session.log
echo "✅ Claude done"
EOF
```

### Background (survives SSH disconnect)

```bash
# Launch in detached tmux — safe to close terminal
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux new-session -d -s claude-task 'source ~/.bashrc && cd /home/julio/projects/cold-linkedin-outreach && claude --print \"YOUR TASK\" 2>&1 | tee ~/agents/claude-session.log'"

# Check progress (any time)
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tail -40 ~/agents/claude-session.log"

# Check if still running
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux ls 2>/dev/null || echo 'Task complete'"
```

### Interactive session (you guide it live)

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only julio@45.55.90.156
source ~/.bashrc
cd /home/julio/projects/cold-linkedin-outreach
claude
# Now you're in Claude's interactive REPL on the VPS
```

### When to use Claude CLI
- You need agentic coding — Claude reads files, makes edits, runs tests
- Implementing features or refactors on the VPS project
- You want the agent to work autonomously while you do other things
- Can't or don't want to open the full IDE

---

## Mode 3 — Gemini CLI

> Primary coding agent when Claude is unavailable. Verified working on VPS as of 2026-03-02.
> Uses `GEMINI_API_KEY` from `.env` — no OAuth, no browser login needed.

### Model setup (confirmed working)

| Variable | Value | Use |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | General / fast tasks |
| `GEMINI_MODEL_CODING` | `gemini-3.1-pro-preview` | All coding sessions |

> **Always use `gemini-3.1-pro-preview` for coding tasks.** Do not use flash for code.
> `gemini-pro-latest` alias also points here as of March 6, 2026.

### One-shot (fire and get result)

```bash
# From Mac — runs on VPS, prints output, exits cleanly
bash ./agent_os/scripts/vps.sh "source ~/.bashrc && cd /home/julio/projects/YOUR_PROJECT && GEMINI_API_KEY=\$(grep GEMINI_API_KEY agent_os/.env | cut -d= -f2 | tr -d ' ') npx @google/gemini-cli --model gemini-3.1-pro-preview -p 'YOUR TASK' 2>&1"
```

### Background (survives SSH disconnect)

```bash
# Launch in tmux — safe to close terminal
bash ./agent_os/scripts/vps.sh "tmux new-session -d -s gemini-task 'source ~/.bashrc && cd /home/julio/projects/YOUR_PROJECT && GEMINI_API_KEY=\$(grep GEMINI_API_KEY agent_os/.env | cut -d= -f2 | tr -d " ") npx @google/gemini-cli --model gemini-3.1-pro-preview -p \"YOUR TASK\" 2>&1 | tee ~/agents/gemini-session.log'"

# Check progress
bash ./agent_os/scripts/vps.sh "tail -40 ~/agents/gemini-session.log"

# Check if still running
bash ./agent_os/scripts/vps.sh "tmux ls 2>/dev/null || echo 'Task complete'"
```

### Interactive session (you guide it live)

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only julio@45.55.90.156
source ~/.bashrc
cd /home/julio/projects/YOUR_PROJECT
GEMINI_API_KEY=$(grep GEMINI_API_KEY /home/julio/projects/YOUR_PROJECT/agent_os/.env | cut -d= -f2 | tr -d ' ') npx @google/gemini-cli --model gemini-3.1-pro-preview
```

### Verified ping test

```bash
# Confirmed working 2026-03-02 — should return "PONG"
bash ./agent_os/scripts/vps.sh "source ~/.bashrc && GEMINI_API_KEY=\$GEMINI_API_KEY npx @google/gemini-cli --model gemini-3.1-pro-preview -p 'Say PONG and nothing else.' 2>&1"
```

### When to use Gemini CLI
- Claude auth service is down or token expired → use Gemini as the primary coding agent
- Heavy coding tasks (Gemini 3.1 Pro has strong agentic + code capabilities)
- Running in parallel alongside Claude in separate tmux panes
- Analysis, research, summarization tasks

---


## Mixing Modes

You can use all three in the same session without conflict:

```
Open IDE Remote → browse and plan the project (Mode 1)
     ↓
Kick off Claude CLI in background for heavy edits (Mode 2, tmux)
     ↓
Monitor progress in IDE terminal while Claude works
     ↓
If Claude quota hits limit, kick off Gemini CLI for next task (Mode 3)
     ↓
Review all results in IDE before committing
```

---

## Git — Every Mode, Same Rule

Regardless of which mode you used, always push when done.

**Always use the safe push protocol — never raw `git push`.**

```bash
# From any terminal on VPS (IDE terminal, SSH session, CLI session)
cd /home/julio/projects/YOUR_PROJECT
./agent_os/scripts/gatekeeper.sh "Completed: describe what was done"
```

The script scans all changes for hardcoded API keys before pushing:
- ✅ Clean → commits and pushes automatically
- 🚨 Key found → blocks push, shows exact file and line to fix

To pull results to Mac for local review:

```bash
# On Mac terminal
cd "/path/to/local/project"
git pull origin main
```

---

## Security Rules (Apply to All Modes)

1. **Never hardcode API keys.** All secrets live in `.env` only. Reference via `os.getenv("KEY_NAME")`. Never paste raw key values into `.py`, `.sh`, `.md`, or any other file.
2. **`ANTHROPIC_API_KEY` is for SDK/scripts only.** Never pass it to `claude` CLI — Claude Code uses OAuth login only.
3. **`.env` is never in git.** It's in `.gitignore`. Use `./agent_os/scripts/tunnel_env.sh` — scans + syncs all .env files.
4. **Always use the safe push protocol** (`./agent_os/scripts/gatekeeper.sh`) — never raw `git push`.
5. **Run `./agent_os/scripts/keyhound.sh`** anytime you want a full project-wide deep scan.

---

## Syncing .env (Secrets — Never in Git)

```bash
# From Mac project root — scans all .env files, confirms gitignored, sends to VPS
./agent_os/scripts/tunnel_env.sh
```

---

## Mode Selector — Quick Reference

| Situation | Use |
|---|---|
| Long coding session, need file explorer + editor | Mode 1 — IDE Remote |
| Short focused task, don't want to open IDE | Mode 2 — Claude CLI |
| Analysis, research, or summarization task | Mode 3 — Gemini CLI |
| Agentic coding, Claude quota exhausted | Mode 3 — Gemini CLI |
| Want agent running in background while you do other things | Mode 2 or 3 — tmux background |
| Running two tasks in parallel | Mode 2 + Mode 3 — separate tmux panes |

---

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `claude: command not found` | Run `source ~/.bashrc` first |
| `OAuth token expired` / 401 error | User must re-login: `bash ./agent_os/scripts/vps.sh attach` → `claude` → follow URL |
| **Never** use `ANTHROPIC_API_KEY` with `claude` | Claude Code CLI = OAuth only. API key = SDK/scripts only. |
| `npx: command not found` | Run `source ~/.bashrc` — nvm sets PATH |
| IDE Remote can't connect | Check DigitalOcean dashboard. Verify SSH key path. |
| `git push` rejected | Run `git pull origin main` first — resolve any conflicts |
| `.env` missing on VPS | Run `./agent_os/scripts/tunnel_env.sh` from project root |
| tmux session already exists | `tmux kill-session -t SESSION_NAME` then relaunch |
| `No space left on device` | `df -h /dev/vda1` — VPS has 77GB, delete old logs if needed |
