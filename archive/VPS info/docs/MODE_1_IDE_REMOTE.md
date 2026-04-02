# 🪞 The Mirror — IDE Remote Workflow

> **Concept:** Your IDE (Cursor / VS Code) connects to the VPS over SSH.
> You see the same UI you always use — but every file, terminal, and process runs on the VPS.
> Your Mac only renders the screen. All the heavy lifting happens remotely.

---

## Mental Model

```
┌──────────────────────────────────────────────────────────────────┐
│                         YOUR MAC                                 │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              Cursor / VS Code (IDE UI)                  │    │
│   │                                                         │    │
│   │   File Explorer │ Editor │ Terminal │ Extensions        │    │
│   │        ↕               ↕              ↕                 │    │
│   │   [everything you see runs on the VPS, not Mac]         │    │
│   └──────────────────────────┬──────────────────────────────┘    │
│                              │ SSH (Remote - SSH Extension)      │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                           VPS                                    │
│   /home/julio/projects/                                          │
│   ├── cold-linkedin-outreach/     ← open this in IDE            │
│   ├── Site scan project/          ← or this                     │
│   ├── MCP servers/                ← or any other                │
│   └── ... (22+ projects)                                        │
│                                                                  │
│   Python runs here. Files live here. Terminal runs here.         │
│   Mac just displays the pixels.                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Setup (One-Time)

### Step 1 — Install the Remote - SSH extension in Cursor / VS Code

- Open Cursor or VS Code
- Go to Extensions (`Cmd+Shift+X`)
- Search: **Remote - SSH** (by Microsoft)
- Install it

### Step 2 — Add the VPS as an SSH host

Open the Command Palette (`Cmd+Shift+P`) → **Remote-SSH: Open SSH Configuration File** → add:

```
Host vps-julio
  HostName 45.55.90.156
  User julio
  IdentityFile ~/.ssh/mcpssh_accesskey.admin_only
  StrictHostKeyChecking no
```

Save the file.

### Step 3 — Connect

- Command Palette → **Remote-SSH: Connect to Host** → select `vps-julio`
- A new IDE window opens — everything inside it is running on the VPS
- Open any folder: `/home/julio/projects/cold-linkedin-outreach` (or any other project)

That's it. You're now working directly on the VPS using your full IDE.

---

## Day-to-Day Usage

### Opening a project on the VPS

1. `Cmd+Shift+P` → **Remote-SSH: Connect to Host** → `vps-julio`
2. `File > Open Folder` → navigate to `/home/julio/projects/YOUR_PROJECT`
3. Work normally — edit files, use the integrated terminal, run scripts

### Running scripts (in the IDE terminal — runs on VPS)

```bash
# The terminal inside the remote IDE is a VPS terminal
cd /home/julio/projects/cold-linkedin-outreach
python3 execution/streaming_pipeline.py
```

### Switching projects (no reconnect needed)

- `File > Open Folder` → pick a different project under `/home/julio/projects/`
- You can also open multiple IDE windows, each pointing to a different VPS project

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
# Step 4 — Tunnel env: sync .env to VPS
bash ./agent_os/scripts/tunnel_env.sh
```
→ Report output. Say: **"✅ Step 4 done. Ready to start work — what's the task?"**

---

## Git — Backup & Sync from within the IDE

Since you're already working directly on the VPS, git is used purely as a **backup and versioning tool** — not as a sync bridge.

### Save your work to GitHub (from the VPS terminal inside the IDE)

**Always use `gatekeeper.sh` — never raw `git push`.**

```bash
# From the project root (IDE integrated terminal on VPS)
./agent_os/scripts/gatekeeper.sh "describe what was done"
```

The script will:
- ✅ Scan all changed files for hardcoded API keys
- ✅ If clean → `git add . && git commit && git push` automatically
- 🚨 If keys found → **block the push** and tell you exactly which file/line to fix

### If you want to pull a change made locally on Mac

```bash
git pull origin main
```

### Pull the project to Mac for local review (optional)

```bash
# On your Mac terminal (outside the IDE)
git pull origin main
```

---

## Managing the .env (Secrets)

`.env` is never committed to git. Use `tunnel_env.sh` to push it to the VPS when secrets change:

```bash
# From Mac project root — scans all .env files and sends only safe (gitignored) ones
./agent_os/scripts/tunnel_env.sh
```

---

## First Time — Cloning a Project on the VPS

If the project isn't on the VPS yet, run this from the IDE terminal (or Mac terminal via SSH):

```bash
cd /home/julio/projects/
git clone https://github.com/Cesars-dev/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
# Then sync .env from Mac:
./agent_os/scripts/tunnel_env.sh
```

---

## Security Rules

1. **Never hardcode API keys.** All secrets live in `.env` only. Reference via `os.getenv("KEY_NAME")`. Never paste raw key values into `.py`, `.sh`, `.md`, or any other file.
2. **`.env` is never in git.** It's in `.gitignore`. Sync to VPS via `./agent_os/scripts/tunnel_env.sh` (scans + sends all .env files safely).
3. **Always use `./agent_os/scripts/gatekeeper.sh`** — never raw `git push`. Scans for exposed keys before every push.
4. **Run `./agent_os/scripts/keyhound.sh`** anytime you want a full project-wide deep scan (on-demand).

---

## Why This Works

| Concern | How it's handled |
|---|---|
| Mac CPU / RAM overload | Everything runs on VPS — Mac just renders pixels |
| File access | All project files live on VPS, browsed via IDE as normal |
| Terminal | Integrated terminal = VPS shell. Full access. |
| Multiple projects | Open folder → switch project. No reconnect. |
| Extensions | Most extensions install on the remote side — run on VPS |
| Disconnect | VPS keeps running. Reconnect and continue. |
| Secrets (.env) | `./agent_os/scripts/tunnel_env.sh` from Mac. Never in git. |
| Backup | `git push` from VPS terminal. GitHub is the safety net. |

---

## Common Errors and Fixes

| Error | Fix |
|---|---|
| `Remote-SSH: Could not establish connection` | Check VPS is on (DigitalOcean dashboard). Verify SSH key path in config. |
| `Permission denied (publickey)` | Confirm `IdentityFile` path in SSH config matches actual key location |
| Extension won't install on remote | Some extensions require manual install on remote — check extension settings → "Install on SSH: vps-julio" |
| `python3: No module named X` | `pip3 install -r requirements.txt` in the VPS terminal inside the IDE |
| `.env` not found on VPS | Run `./agent_os/scripts/tunnel_env.sh` from project root |
| Changes not saved after VPS reboot | Always `git push` before closing the IDE session |
