# 🤖 Agent Execution Guide — VPS Agent Swarm

## Purpose

This document tells an AI agent exactly how to set up, launch, and manage the 3-agent tmux swarm on the remote VPS. Follow each step precisely. Do not skip steps.

---

## System Context

| Item | Value |
|---|---|
| VPS IP | see `VPS_IP` in root `.env` |
| SSH User | see `VPS_USER` in root `.env` |
| SSH Key | see `VPS_SSH_KEY` in root `.env` |
| Passphrase | see `VPS_SSH_PASSPHRASE` in root `.env` |
| Projects dir | `/home/julio/projects/` |
| Agents dir | `/home/julio/agents/` |
| GitHub user | `Cesars-dev` |
| Git credentials | Stored in `~/.git-credentials` on VPS |

---

## SSH Access Pattern

All VPS commands must be executed via SSH. Use `./agent_os/vps.sh "command"` for single commands, or connect directly:

```bash
ssh vps-julio "<command>"
```

For multi-line scripts use a heredoc:

```bash
ssh vps-julio bash << 'EOF'
# commands here
EOF
```

> VPS credentials (IP, user, key) are read from `.env` by `vps.sh`. Never hardcode them in scripts.

---

## Pre-Flight Checks (Run Before Anything)

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 "
echo '--- Node ---' && node -v
echo '--- Claude ---' && source ~/.bashrc && claude --version
echo '--- Gemini ---' && gemini --version 2>/dev/null || echo 'gemini: use npx @google/gemini-cli'
echo '--- Disk ---' && df -h /dev/vda1 | tail -1
echo '--- Agents dir ---' && ls ~/agents/
echo '--- tmux sessions ---' && tmux ls 2>/dev/null || echo 'no sessions'
"
```

Expected: Node v20+, Claude 2.x, disk < 70% used, agents dir exists.

---

## How the Swarm Works

```
Mac Terminal
    │
    └─► SSH into VPS
              │
              └─► ./agent-swarm.sh
                        │
                        └─► tmux new-session "swarm"
                                  │
                                  ├─► Pane 0: Agent A (left)
                                  ├─► Pane 1: Agent B (right)
                                  └─► Pane 2: Agent C (bottom)
```

Each agent runs independently. They can all write to `/home/julio/agents/` and read each other's status files. The session persists after SSH disconnects.

---

## Launching the Swarm

### Step 1 — Kill any existing swarm session

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux kill-session -t swarm 2>/dev/null; echo 'cleared'"
```

### Step 2 — Write the task plan files

Before launching, write what each agent should do:

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 bash << 'EOF'
cat > ~/agents/agent-plan-A.md << 'PLAN'
# Agent A Task
[Write Agent A's specific task here]
PLAN

cat > ~/agents/agent-plan-B.md << 'PLAN'
# Agent B Task
[Write Agent B's specific task here]
PLAN

cat > ~/agents/agent-plan-C.md << 'PLAN'
# Agent C Task
[Write Agent C's specific task here]
PLAN
EOF
```

### Step 3 — Write a custom swarm-launcher.sh with real agent commands

Replace the dummy commands with actual AI agent calls:

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 bash << 'EOF'
cat > ~/agents/swarm-launcher.sh << 'SCRIPT'
#!/bin/bash
SESSION_NAME="swarm"

# Agent A command — customize this
CMD_A="source ~/.bashrc && cd /home/julio/projects/YOUR_PROJECT_A && claude --print 'YOUR_TASK_HERE' 2>&1 | tee /home/julio/agents/status-A.log"

# Agent B command — customize this
CMD_B="source ~/.bashrc && cd /home/julio/projects/YOUR_PROJECT_B && claude --print 'YOUR_TASK_HERE' 2>&1 | tee /home/julio/agents/status-B.log"

# Agent C command — customize this
CMD_C="source ~/.bashrc && cd /home/julio/projects/YOUR_PROJECT_C && claude --print 'YOUR_TASK_HERE' 2>&1 | tee /home/julio/agents/status-C.log"

tmux new-session -d -s $SESSION_NAME -n agents "$CMD_A"
tmux split-window -h -t $SESSION_NAME:agents "$CMD_B"
tmux split-window -v -t $SESSION_NAME:agents "$CMD_C"
tmux select-layout -t $SESSION_NAME:agents tiled
echo "Swarm launched. Attach with: tmux attach -t swarm"
SCRIPT
chmod +x ~/agents/swarm-launcher.sh
echo "Launcher updated"
EOF
```

### Step 4 — Launch the swarm

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "cd ~/agents && ./agent-swarm.sh"
```

### Step 5 — Verify it's running

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux ls && echo 'swarm is live'"
```

Expected output: `swarm: 1 windows (created ...) swarm is live`

---

## Monitoring Agents

### Check status logs (non-interactive)

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "cat ~/agents/status-A.log; echo '---B---'; cat ~/agents/status-B.log; echo '---C---'; cat ~/agents/status-C.log"
```

### Check if swarm is still running

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux ls 2>/dev/null || echo 'SWARM NOT RUNNING'"
```

---

## ⚠️ Security Rules (Read Before Anything)

1. **Never hardcode API keys.** All secrets live in `.env` only. Reference via `os.getenv("KEY_NAME")`. Never paste raw key values into `.py`, `.sh`, `.md`, or any other file.
2. **`.env` is never in git.** It's in `.gitignore`. Use `./agent_os/tunnel_env.sh` from Mac project root to sync it to VPS.
3. **Always use `./safe_push.sh`** — never raw `git push`. Scans for exposed keys before every push.
4. **Run `./audit_keys.sh`** anytime you want a full project-wide deep scan (on-demand last resort).

---

## ⚠️ MANDATORY: Git Push Rule

**Every time work is completed on the VPS — push to GitHub via `./safe_push.sh`. No exceptions.**

---

## 🚨 Parallel Git Protocol (3 Agents Running at Once)

This is the most critical section. If multiple agents push to the same `main` branch simultaneously, commits will collide and work will be lost.

### Scenario A — Agents on DIFFERENT projects (recommended)

Each agent works on a completely separate project folder → they can each push to their own `main` freely:

```
Agent A → /home/julio/projects/Site scan project/   → git push origin main ✅
Agent B → /home/julio/projects/MCP servers/         → git push origin main ✅
Agent C → /home/julio/projects/N8N Workflows/       → git push origin main ✅
```

No conflict. Each repo is independent.

### Scenario B — Agents on the SAME project (branch required)

If agents share a project, **each agent MUST work on its own branch**. Never push to `main` directly.

#### Step 1 — Each agent creates its own branch before touching anything:
```bash
cd /home/julio/projects/YOUR_PROJECT
git pull origin main          # always pull first
git checkout -b agent-a/my-task   # or agent-b/, agent-c/
```

#### Step 2 — Agent commits and pushes its branch:
```bash
git add .
git commit -m "Agent A: completed task — $(date '+%Y-%m-%d %H:%M')"
git push origin agent-a/my-task
echo "✅ Branch pushed"
```

#### Step 3 — After ALL agents finish, merge to main:
```bash
git checkout main
git pull origin main
git merge agent-a/my-task
git merge agent-b/my-task
git merge agent-c/my-task
git push origin main
echo "✅ All branches merged to main"
```

### ALWAYS pull before starting:
```bash
cd /home/julio/projects/YOUR_PROJECT
git pull origin main
# NOW start working
```

### Conflict resolution (if git merge fails):
```bash
git status                          # see conflicting files
git diff                            # see exact conflicts

# Option 1: keep the incoming (remote) version
git checkout --theirs path/to/file

# Option 2: keep your local version
git checkout --ours path/to/file

# After resolving all conflicts:
git add .
git commit -m "Resolved merge conflict — $(date '+%Y-%m-%d %H:%M')"
git push
```

---

### Standard single-agent push template:

**Always use `safe_push.sh` — never raw `git push`.**

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 bash << 'EOF'
PROJECT_DIR="/home/julio/projects/YOUR_PROJECT"
cd "$PROJECT_DIR"
git pull origin main
./safe_push.sh "Completed: YOUR_TASK_DESCRIPTION"
EOF
```

The script scans all changes for hardcoded API keys before pushing:
- ✅ Clean → commits and pushes automatically
- 🚨 Key found → blocks push, shows exact file and line to fix

This is not optional. If you skip this, the user loses the work when the VPS is resized, rebooted, or the session is killed.

---

## Killing the Swarm

```bash
ssh -i ~/.ssh/mcpssh_accesskey.admin_only -o StrictHostKeyChecking=no julio@45.55.90.156 \
  "tmux kill-session -t swarm && echo 'swarm killed'"
```

---

## Tool Availability on VPS

| Tool | Command | Notes |
|---|---|---|
| Claude Code | `source ~/.bashrc && claude` | PATH set in ~/.bashrc |
| Gemini CLI | `npx @google/gemini-cli` | Global npm install |
| Node.js | `node` | v20.20.0 via nvm |
| Python | `python3` | System Python 3.12 |
| Docker | `docker` | v29.2.1 |
| tmux | `tmux` | v3.4, mouse ON |
| git | `git` | Credentials in ~/.git-credentials |

---

## Projects Directory Map

```
/home/julio/projects/
├── AI website/
├── Antigravity-AdsPower Login Helper/
├── Claude code proxy/
├── Experiments/
├── MCP debug/
├── MCP generation/
├── MCP servers/
├── Migration to vps/
├── N8N Workflows/
├── Personal/
├── Quota watcher/
├── Site scan project/
├── Upwork/
├── Working product/
└── ... (22 total)
```

Every project has a matching private GitHub repo under `Cesars-dev`.

---

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `claude: command not found` | Run `source ~/.bashrc` first |
| `tmux: no sessions` | Swarm not started — run `./agent-swarm.sh` |
| `No space left on device` | Check `df -h /dev/vda1`. VPS has 77GB, should have ~54GB free. Delete old logs if needed. |
| `git push` rejected | Check `git remote -v` and token in `~/.git-credentials` |
| SSH timeout | VPS may be off. Check DigitalOcean dashboard. |
