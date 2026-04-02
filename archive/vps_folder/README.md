# VPS Operations & Deployment

> Scripts and docs for managing the VPS, SSH tunnels, and git safety.

---

## Files

| File | Purpose | Run from |
|------|---------|----------|
| `AGENT_VPS_FRAMEWORK.md` | Full guide for running AI agent swarms on VPS (tmux, SSH, parallel git) | Reference doc |
| `ads power on vps.md` | Step-by-step headless AdsPower install on VPS (systemd + Xvfb) | Reference doc |
| `recover_session.md` | How to resume a Claude Code session from terminal | Reference doc |
| `safe_push.sh` | Git push with automatic credential leak scan — blocks push if keys found | Mac terminal |
| `tunnel_env.sh` | Syncs `.env` from Mac to VPS securely | Mac terminal |

---

## AdsPower on VPS

The pipeline scripts for controlling AdsPower live in `indeed-pipeline/scripts/`:

```bash
# From Mac — controls VPS AdsPower remotely via SSH
bash indeed-pipeline/scripts/vps_adspower.sh start     # Xvfb + AdsPower (~70s)
bash indeed-pipeline/scripts/vps_adspower.sh stop      # kills both, frees ~400MB RAM
bash indeed-pipeline/scripts/vps_adspower.sh status    # service state + API health
bash indeed-pipeline/scripts/vps_adspower.sh restart   # stop then start
bash indeed-pipeline/scripts/vps_adspower.sh diagnose  # full process/log/port dump
```

**Port 20725** (VPS-native) always returns `Forbidden` — this is **expected** (device-bound auth).
**Port 50325** (Mac tunnel) is what all scripts use.

---

## SSH Tunnel

Must be running before any pipeline work:

```bash
bash indeed-pipeline/scripts/tunnel.sh
```

Forwards:
- `Mac:3001-3003 → VPS` — GitHub MCP servers
- `VPS:50325 → Mac:50325` — reverse tunnel so VPS reaches Mac's AdsPower

---

## Git Safety

**Always use `safe_push.sh` instead of raw `git push`:**

```bash
bash vps_folder/safe_push.sh "your commit message"
```

It scans all staged changes for leaked API keys (GitHub PATs, Supabase, Netlify, Gemini, etc.) and blocks the push if anything is found.

For a deeper scan of the entire project:
```bash
bash indeed-pipeline/scripts/audit_keys.sh
```

---

## Sync .env to VPS

```bash
bash vps_folder/tunnel_env.sh
```

Copies the local `.env` to the VPS pipeline directory, ensuring credentials are in sync.
