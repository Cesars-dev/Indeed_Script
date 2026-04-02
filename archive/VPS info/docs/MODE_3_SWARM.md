# 🤖 Agent Execution Guide — VPS Agent Swarm

## Purpose

This document tells an AI agent exactly how to set up, launch, and manage the multi-agent tmux swarm on the remote VPS. Follow each step precisely. Do not skip steps.

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

All VPS commands must be executed via SSH. Use `./agent_os/scripts/vps.sh` which reads credentials from `.env` automatically:

```bash
# Single command
./agent_os/scripts/vps.sh "<your command here>"

# Multi-line via heredoc
./agent_os/scripts/vps.sh bash << 'EOF'
# commands here
EOF
```

> **Never hardcode** the VPS IP, SSH user, key path, or passphrase. All credentials live in root `.env` under `VPS_IP`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_SSH_PASSPHRASE`.

---

## Pre-Flight Checks (Run Before Anything)

> ⚠️ **One step at a time. Report output. Wait for user confirmation before next step.**

```bash
# Step 1 — Local: scan for exposed keys
bash ./agent_os/scripts/keyhound.sh
```
→ Report output. Say: **"✅ Step 1 done. Proceed to Step 2?"** Wait for confirmation.

```bash
# Step 2 — Safe push: commit local pending work to GitHub
bash ./agent_os/scripts/gatekeeper.sh "WIP before swarm session"
```
→ Report output. Say: **"✅ Step 2 done. Proceed to Step 3?"** Wait for confirmation.

```bash
# Step 3 — VPS pull: get latest from GitHub onto VPS
bash ./agent_os/scripts/vps.sh "cd /home/julio/projects/YOUR_PROJECT && git pull origin main"
```
→ Report output. Say: **"✅ Step 3 done. Proceed to Step 4?"** Wait for confirmation.

```bash
# Step 4 — Tunnel env: sync .env to VPS (agents need credentials)
bash ./agent_os/scripts/tunnel_env.sh
```
→ Report output. Say: **"✅ Step 4 done. Proceed to Step 5?"** Wait for confirmation.

```bash
# Step 5 — Read GEMINI_KEY and verify VPS is ready
# Prefer already-exported env var; fall back to reading from .env file
GEMINI_KEY="${GEMINI_API_KEY:-$(grep GEMINI_API_KEY agent_os/.env | cut -d= -f2 | tr -d ' ')}"
echo "GEMINI_KEY loaded: ${GEMINI_KEY:0:10}..."  # confirm not empty

bash ./agent_os/scripts/vps.sh "
source ~/.bashrc
echo '--- Node ---' && node -v
echo '--- Gemini CLI ---' && GEMINI_API_KEY=$GEMINI_KEY npx @google/gemini-cli --model gemini-3.1-pro-preview -p 'Say PONG' 2>&1 | tail -1
echo '--- Disk ---' && df -h /dev/vda1 | tail -1
echo '--- Agents dir ---' && ls ~/agents/ 2>/dev/null || mkdir ~/agents && echo 'agents dir created'
echo '--- tmux sessions ---' && tmux ls 2>/dev/null || echo 'no sessions — clean'
"
```
→ Gemini must return `PONG`. Report output. Say: **"✅ Step 5 done. Ready to launch swarm — confirm?"**

> Claude is **not** checked by default — only verify if explicitly instructed.


---

## Architecture

```
Pre-flight always runs on Mac (Phase 1 above).
Orchestrator can run on Mac OR VPS — your call each session.

Mac orchestrator                   VPS orchestrator
────────────────────────────       ────────────────────────────
uses vps.sh to reach VPS           already on VPS, runs directly
bash ./agent_os/scripts/           tmux / cat / npx commands
  vps.sh "command"                 run natively, no SSH wrapper
```

> When launch steps show `vps.sh "..."` — that's Mac-side.
> If you're already on VPS, strip `vps.sh` and run the inner command directly.

---

## Launching the Swarm

### Step 1 — Full scope report (ALWAYS before anything)

> 🚨 **Do not kill, modify, or launch anything until user reviews this report and gives authorization.**

Run on VPS (if orchestrator is there) or via `vps.sh "..."` wrapper from Mac:

```bash
# On VPS — run directly
echo '══════════════════════════════════════════'
echo '  SWARM SCOPE REPORT'
echo '══════════════════════════════════════════'
echo ''
echo '── Active tmux sessions ──────────────────'
tmux ls 2>/dev/null || echo 'No sessions running'
echo ''
echo '── Panes in each session ─────────────────'
tmux list-panes -a -F '#{session_name} | pane #{pane_index} | #{pane_current_command} | #{pane_current_path}' 2>/dev/null || echo 'No panes'
echo ''
echo '── Agent status logs (last 5 lines each) ─'
for log in ~/agents/status-*.log; do
  [ -f "$log" ] && echo "--- $(basename $log) ---" && tail -5 "$log" || true
done
echo ''
echo '── Disk usage ────────────────────────────'
df -h /dev/vda1 | tail -1
echo ''
echo '── Running node/python processes ─────────'
ps aux | grep -E 'node|python|gemini|claude' | grep -v grep || echo 'None'
echo '══════════════════════════════════════════'
```

→ Present the full report to the user.
→ Say: **"Here is the current VPS state. What would you like to do?"**

Options:
- **"Kill session X and start fresh"** → only then kill, and only the named session
- **"Attach to session X"** → `tmux attach -t SESSION_NAME`
- **"Start new swarm with session name Y"** → proceed to Step 2 with a custom session name
- **"Abort"** → stop

> ⛔ Never auto-kill any session. Never assume a session is abandoned.

### Step 2 — Read tasks, design and launch the swarm autonomously

> The orchestrator has **full autonomy** here. Efficiency is priority, accuracy is mandatory.
> No approval needed — read, plan, decide, execute.

#### First — check available RAM and set max_agents

```bash
AVAIL_MB=$(free -m | awk '/^Mem:/ {print $7}')
AGENT_COST_MB=150   # ~120MB peak + 30MB buffer per Gemini CLI instance
RESERVE_MB=400      # reserve for OS + orchestrator + logs
MAX_AGENTS=$(( (AVAIL_MB - RESERVE_MB) / AGENT_COST_MB ))
[ $MAX_AGENTS -lt 1 ] && MAX_AGENTS=1
[ $MAX_AGENTS -gt 7 ] && MAX_AGENTS=7   # hard cap — 7 if RAM allows
echo "Available RAM: ${AVAIL_MB}MB | Max agents: $MAX_AGENTS"
```

> Gemini CLI uses ~120MB RSS per instance (measured on this VPS). Hard cap is 7 (requires ~1.45GB free for agents alone).

---

#### Check the tasks folder

```bash
TASK_FILES=$(ls ~/projects/YOUR_PROJECT/agent_os/tasks/*.md 2>/dev/null)
echo "${TASK_FILES:-EMPTY}"
```

---

#### IF tasks found → Read, decompose, auto-launch

```bash
# Read all task files
cat ~/projects/YOUR_PROJECT/agent_os/tasks/*.md
```

Orchestrator does the following **without asking for approval**:

1. **Read every task file** — understand full scope of the project
2. **Apply DOE framework** — decompose into parallel workstreams, each with clear deliverable
3. **Assign branches** — since all tasks are on the same project, each agent gets its own branch:
   ```
   agent-a/[task-slug]
   agent-b/[task-slug]
   ...
   ```
4. **Decide agent count** — min(workstreams, MAX_AGENTS). Write the plan to `~/agents/swarm-plan.md`:
   ```
   SWARM PLAN — [timestamp]
   ─────────────────────────────────────────────────────
   Project:  /home/julio/projects/YOUR_PROJECT
   Agents:   N (capped by RAM: MAX_AGENTS available)

   Agent A: [task name] → branch: agent-a/task-slug
   Agent B: [task name] → branch: agent-b/task-slug
   ...
   Merge agent: YES — launches after all workers done
   Done plan: notify user + optional Sonnet debug session
   ─────────────────────────────────────────────────────
   ```
5. **Each agent must on start:**
   ```bash
   echo $$ > ~/agents/pid-X.txt          # register PID immediately
   git pull origin main
   git checkout -b agent-X/task-slug
   # ... do work ...
   git add . && git commit -m "Agent X: [task] — $(date '+%Y-%m-%d %H:%M')"
   # ⛔ DO NOT push — commit locally only
   echo "DONE" > ~/agents/status-X.log
   exit 0                                  # clean exit — frees RAM
   ```
6. **Orchestrator monitors agents continuously** (runs in its own loop):

   When an agent writes `DONE` to its status file, orchestrator does NOT kill immediately.
   It verifies first:

   ```
   Agent X signals DONE
       ↓
   Orchestrator reads:
     - DOE task file for Agent X
     - git diff main...agent-X/task-slug
       ↓
   ┌─── Work matches DOE? ───────────────────────────────┐
   │                                                      │
   │  YES — confirmed complete                            │
   │    → kill process cleanly (SIGTERM, wait, SIGKILL   │
   │      only if still alive after 5s)                  │
   │    → mark slot free                                  │
   │    → pop next task from queue                        │
   │                                                      │
   │  NO — incomplete or wrong                            │
   │    → do NOT kill                                     │
   │    → re-prompt agent with exactly what's missing:   │
   │      "DOE requires [X]. Your diff shows [Y].        │
   │       Complete [specific missing item] and signal    │
   │       DONE again when truly finished."               │
   │    → agent continues working                         │
   └──────────────────────────────────────────────────────┘
   ```

   ```bash
   # Orchestrator watch loop (simplified)
   while true; do
     for status_file in ~/agents/status-*.log; do
       AGENT_ID=$(basename $status_file .log | sed 's/status-//')
       STATUS=$(tail -1 $status_file 2>/dev/null)
       PID=$(cat ~/agents/pid-$AGENT_ID.txt 2>/dev/null)

       if echo "$STATUS" | grep -qx "DONE"; then
         # Step 1: review diff vs DOE
         DOE_FILE=~/projects/YOUR_PROJECT/agent_os/tasks/task-$AGENT_ID.md
         BRANCH=$(cat ~/agents/branch-$AGENT_ID.txt 2>/dev/null)
         DIFF=$(git -C ~/projects/YOUR_PROJECT diff main...$BRANCH 2>/dev/null)

         # Step 2: orchestrator evaluates — model hardcoded to 3.1-pro-preview, always
         VERDICT=$(GEMINI_API_KEY=$GEMINI_KEY npx @google/gemini-cli \
           --model gemini-3.1-pro-preview \
           -p "DOE task: $(cat $DOE_FILE). Git diff: $DIFF. Is this task complete? Answer COMPLETE or INCOMPLETE:[reason]" \
           2>/dev/null)

         if echo "$VERDICT" | grep -q "^COMPLETE"; then
           echo "Agent $AGENT_ID: verified complete — terminating"
           kill $PID 2>/dev/null
           sleep 5
           kill -9 $PID 2>/dev/null   # only if still alive after 5s
           echo "VERIFIED_DONE" >> $status_file
           # wave execution: pop next task when slot frees
            NEXT_TASK=$(sed -n "${NEXT_QUEUE_LINE}p" ~/agents/swarm-queue.txt)
            NEXT_QUEUE_LINE=$((NEXT_QUEUE_LINE + 1))
            if [ -n "$NEXT_TASK" ]; then
              NEXT_NUM=$((AGENT_NUM + 1))
              NEXT_ID="agent-$NEXT_NUM"
              NEXT_BRANCH="$NEXT_ID/task-$(echo $NEXT_TASK | md5sum | cut -c1-6)"
              echo "$NEXT_BRANCH" > ~/agents/branch-$NEXT_ID.txt
              echo "Launching replacement: $NEXT_ID"
              tmux new-window -t "$SESSION_NAME" -n "$NEXT_ID"                 "bash ~/agents/run-agent.sh $NEXT_ID $PROJECT_DIR $GEMINI_KEY"
            else
              echo "Queue exhausted. No more tasks."
            fi
         else
           REASON=$(echo "$VERDICT" | sed 's/^INCOMPLETE://')
           echo "Agent $AGENT_ID: incomplete — re-prompting"
           echo "REPROMPT" >> $status_file
           # Re-prompt agent with what's missing (via tmux send-keys)
           tmux send-keys -t "$SESSION_NAME:$AGENT_ID" \
             "echo 'DOE review: $REASON — complete this and signal DONE again'" Enter
         fi
       fi
     done
     sleep 10
   done
   ```


7. **Wave execution** — with agent cleanup, tasks exceed MAX_AGENTS concurrently:
   ```
   Total tasks: 12  |  MAX_AGENTS (concurrent): up to 7
   ─────────────────────────────────────────────────
   Wave 1: Agents A B C D E  → launch 5 concurrently
           Agent B finishes   → killed, RAM freed → Agent F launched
           Agent D finishes   → killed, RAM freed → Agent G launched
           ...
   Wave N: Always ≤ MAX_AGENTS alive at once
   ─────────────────────────────────────────────────
   Queue file: ~/agents/swarm-queue.txt (one task per line)
   Orchestrator pops tasks from queue as slots free up
   ```

8. **Orchestrator audit** — after ALL tasks in queue are done:
   - Reads each agent's git diff (`git diff main...$(cat ~/agents/branch-$AGENT_ID.txt)`)
   - Compares output against original DOE task file
   - Checks: completeness, accuracy, missing steps, unintended changes
   - Writes audit report to `~/agents/swarm-audit.md`:
   ```
   SWARM AUDIT REPORT — [timestamp]
   ─────────────────────────────────────────────────────
   Agent A: [task name]
     ✅ Completed: [what was done]
     ⚠️  Gaps: [anything missing vs DOE plan]
     📋 Files changed: [list]

   Agent B: [task name]
     ...
   ─────────────────────────────────────────────────────
   RECOMMENDED NEXT STEPS:
   - [ ] Fix: [specific issue if any]
   - [ ] Push branch agent-a/task-slug (pending your approval)
   - [ ] Push branch agent-b/task-slug (pending your approval)
   ─────────────────────────────────────────────────────
   ```
9. **Notify user — full stop:**
   ```
   ✅ All agents done. Audit complete.

   Review: ~/agents/swarm-audit.md

   Nothing has been pushed. Awaiting your instructions:
   - Approve specific branches to push
   - Request fixes before push
   - Merge branches (only on your command)
   ```
   > ⛔ No git push, no merge, no further action until user explicitly instructs.


---

#### IF tasks empty → Ask directive, apply DOE, auto-plan

Orchestrator asks user **one question only**:

```
No tasks found in agent_os/tasks/.
What is the main directive for this swarm?
```

Wait for response, then — **full autonomy**:

1. Apply DOE framework to decompose directive into parallel workstreams
2. Write task files to `~/projects/YOUR_PROJECT/agent_os/tasks/`
3. Check RAM → calculate MAX_AGENTS
4. Decide agent count and branch strategy
5. Write swarm plan to `~/agents/swarm-plan.md`
6. Proceed directly to Step 3 — no further approval needed

### Permanent Gemini Auth on VPS (one-time setup)

So `GEMINI_API_KEY` is always available in every shell without inline passing:

```bash
# Run once on VPS — then it's permanent across all sessions
echo 'export GEMINI_API_KEY=$(grep GEMINI_API_KEY ~/projects/YOUR_PROJECT/agent_os/.env | cut -d= -f2 | tr -d " " 2>/dev/null)' >> ~/.bashrc
source ~/.bashrc
echo "Gemini key loaded: ${GEMINI_API_KEY:0:10}..."  # confirm
```

> Re-run `source ~/.bashrc` after any `tunnel_env.sh` sync to pick up key changes.

---

### Step 3 — Write the swarm launcher

The launcher is generated dynamically from the swarm plan written in Step 2.
It reads `swarm-queue.txt`, calculates live MAX_AGENTS, and spawns workers + orchestrator watch.

```bash
# On VPS (or via vps.sh wrapper from Mac)
PROJECT_DIR="/home/julio/projects/YOUR_PROJECT"

cat > ~/agents/swarm-launcher.sh << 'SCRIPT'
#!/bin/bash
# ── Swarm Launcher — Dynamic, queue-driven ───────────────────────────────────
set -e

PROJECT_DIR="/home/julio/projects/YOUR_PROJECT"

# Dual-source key: env var first (set by Mac or ~/.bashrc), fallback to .env file
GEMINI_KEY="${GEMINI_API_KEY:-$(grep GEMINI_API_KEY $PROJECT_DIR/agent_os/.env | cut -d= -f2 | tr -d ' ' 2>/dev/null)}"
# Model is hardcoded — swarm always uses 3.1-pro-preview, no env lookup
GEMINI_MODEL="gemini-3.1-pro-preview"

SESSION_NAME="swarm-$(date +%Y%m%d-%H%M)"
QUEUE=~/agents/swarm-queue.txt
AGENTS_DIR=~/agents

# Sanity checks
[ -z "$GEMINI_KEY" ] && echo "❌ GEMINI_KEY not found in $PROJECT_DIR/agent_os/.env" && exit 1
[ ! -f "$QUEUE" ]    && echo "❌ Queue file missing: $QUEUE" && exit 1

# Calculate max concurrent agents from live RAM
AVAIL_MB=$(free -m | awk '/^Mem:/ {print $7}')
MAX_AGENTS=$(( (AVAIL_MB - 400) / 150 ))
[ $MAX_AGENTS -lt 1 ] && MAX_AGENTS=1
[ $MAX_AGENTS -gt 7 ] && MAX_AGENTS=7

echo "Session:     $SESSION_NAME"
echo "Queue tasks: $(wc -l < $QUEUE)"
echo "Max agents:  $MAX_AGENTS (RAM: ${AVAIL_MB}MB available)"

# Start tmux session with orchestrator watch in first pane
tmux new-session -d -s "$SESSION_NAME" -n "orchestrator" \
  "bash $AGENTS_DIR/orchestrator-watch.sh $SESSION_NAME $PROJECT_DIR 2>&1 | tee $AGENTS_DIR/orchestrator.log"

# Launch first batch of workers up to MAX_AGENTS
AGENT_NUM=0
while IFS= read -r TASK_LINE && [ $AGENT_NUM -lt $MAX_AGENTS ]; do
  AGENT_NUM=$((AGENT_NUM + 1))
  AGENT_ID="agent-$AGENT_NUM"
  BRANCH="$AGENT_ID/task-$(echo $TASK_LINE | md5sum | cut -c1-6)"
  LOG="$AGENTS_DIR/status-$AGENT_ID.log"
  > $LOG  # reset log
  echo "$BRANCH" > $AGENTS_DIR/branch-$AGENT_ID.txt  # store branch for watch loop

  FULL_CMD="echo \$\$ > $AGENTS_DIR/pid-$AGENT_ID.txt && \
    source ~/.bashrc && \
    cd $PROJECT_DIR && \
    git pull origin main && \
    git checkout -b $BRANCH && \
    GEMINI_API_KEY=$GEMINI_KEY npx @google/gemini-cli \
      --model gemini-3.1-pro-preview \
      -p '$(cat $AGENTS_DIR/task-$AGENT_NUM.md)' \
      2>&1 | tee $LOG && \
    git add . && git commit -m '$AGENT_ID: task done — \$(date +%Y-%m-%d)' && \
    echo DONE >> $LOG && exit 0"

  tmux new-window -t "$SESSION_NAME" -n "$AGENT_ID" "bash -c \"$FULL_CMD\""
  echo "Launched $AGENT_ID"
done < "$QUEUE"

echo ""
echo "✅ Swarm launched: $SESSION_NAME"
echo "   Workers: $AGENT_NUM / $(wc -l < $QUEUE) tasks"
echo "   Attach:  tmux attach -t $SESSION_NAME"
SCRIPT

chmod +x ~/agents/swarm-launcher.sh
echo "Launcher written:"
cat ~/agents/swarm-launcher.sh
```

→ Show launcher to user. Say: **"✅ Step 3 done. Launcher ready — session will be named `swarm-[timestamp]`. Confirm to launch?"** Wait for confirmation.

### Step 4 — Launch the swarm

> 🚨 **This starts real agent processes. Confirm user has authorized launch before running.**

```bash
# On VPS directly — or via vps.sh from Mac:
# bash scripts/vps.sh "cd ~/agents && bash swarm-launcher.sh"

cd ~/agents && bash swarm-launcher.sh
```

The launcher will print:
```
Session:     swarm-20260303-0009
Queue tasks: 8
Max agents:  5 (RAM: 2100MB available)
Launched agent-1
Launched agent-2
...
✅ Swarm launched: swarm-20260303-0009
   Workers: 5 / 8 tasks
   Attach:  tmux attach -t swarm-20260303-0009
```

→ Copy the session name from output. Report it to user. Say: **"✅ Step 4 done. Swarm is live — session: `[SESSION_NAME]`. Proceeding to verify?"** Wait for confirmation.

### Step 5 — Verify it's running

```bash
# On VPS directly — or via vps.sh from Mac
SESSION=$(tmux ls | grep swarm | awk -F: '{print $1}' | tail -1)

echo "── Active swarm session ──────────────────"
tmux ls | grep swarm

echo ""
echo "── Panes and commands ────────────────────"
tmux list-panes -a -F '#{session_name} | #{window_name} | #{pane_current_command}' | grep $SESSION

echo ""
echo "── Agent status (live) ───────────────────"
for log in ~/agents/status-*.log; do
  [ -f "$log" ] && echo "$(basename $log): $(tail -1 $log)"
done

echo ""
echo "── RAM after launch ──────────────────────"
free -h | grep Mem

echo ""
echo "── Orchestrator log (last 10 lines) ──────"
tail -10 ~/agents/orchestrator.log 2>/dev/null || echo "No orchestrator log yet"
```

→ Report full output. Confirm panes are running `node` (Gemini CLI) and orchestrator pane is active.

→ Say: **"✅ Step 5 done. Swarm verified: [N] agents running in session `[SESSION_NAME]`. Orchestrator watching. Nothing will be pushed without your instruction."**

---

## Monitoring Agents

### Check status logs (non-interactive)

```bash
./agent_os/scripts/vps.sh "for log in ~/agents/status-*.log; do echo \"=== \$log ==="; cat \"\$log\"; done"
```

### Check if swarm is still running

```bash
./agent_os/scripts/vps.sh "tmux ls 2>/dev/null || echo 'SWARM NOT RUNNING'"
```

---

## ⚠️ Security Rules (Read Before Anything)

1. **Never hardcode API keys.** All secrets live in `.env` only. Reference via `os.getenv("KEY_NAME")`. Never paste raw key values into `.py`, `.sh`, `.md`, or any other file.
2. **`.env` is never in git.** It's in `.gitignore`. Use `./agent_os/scripts/tunnel_env.sh` from Mac project root to sync it to VPS.
3. **Always use `./agent_os/scripts/gatekeeper.sh`** — never raw `git push`. Scans for exposed secrets before every push.
4. **Run `./agent_os/scripts/keyhound.sh`** anytime you want a full project-wide deep scan (on-demand).

---

## ⚠️ MANDATORY: Git Push Rule

**Every time work is completed on the VPS — push to GitHub via `./agent_os/scripts/gatekeeper.sh`. No exceptions.**

---

## 🚨 Parallel Git Protocol (Multi-Agent Running at Once)

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

**Always use `gatekeeper.sh` — never raw `git push`.**

```bash
./agent_os/scripts/vps.sh bash << 'EOF'
PROJECT_DIR="/home/julio/projects/YOUR_PROJECT"
cd "$PROJECT_DIR"
git pull origin main
./agent_os/scripts/gatekeeper.sh "Completed: YOUR_TASK_DESCRIPTION"
EOF
```

The script scans all changes for hardcoded API keys before pushing:
- ✅ Clean → commits and pushes automatically
- 🚨 Key found → blocks push, shows exact file and line to fix

This is not optional. If you skip this, the user loses the work when the VPS is resized, rebooted, or the session is killed.

---

## Killing the Swarm

```bash
# Kill by exact name (get it from tmux ls first)
bash ./agent_os/scripts/vps.sh "tmux ls"   # find exact session name e.g. swarm-20260303-0009
bash ./agent_os/scripts/vps.sh "tmux kill-session -t swarm-20260303-0009 && echo 'swarm killed'"
```

---

## Tool Availability on VPS

| Tool | Command | Notes |
|---|---|---|
| **Gemini CLI** | `GEMINI_API_KEY=... npx @google/gemini-cli --model gemini-3.1-pro-preview` | **Default coding agent** |
| Claude Code | `source ~/.bashrc && claude` | Only if explicitly instructed by user |
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
| `tmux: no sessions` | Swarm not started — run `cd ~/agents && ./swarm-launcher.sh` |
| `No space left on device` | Check `df -h /dev/vda1`. VPS has 77GB, should have ~54GB free. Delete old logs if needed. |
| `git push` rejected | Check `git remote -v` and token in `~/.git-credentials` |
| SSH timeout | VPS may be off. Check DigitalOcean dashboard. |
