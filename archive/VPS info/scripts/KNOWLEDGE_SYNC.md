# Knowledge Sync — Mac ↔ VPS

Bidirectional sync of Antigravity knowledge items between local Mac and VPS.  
Runs permanently in the background via macOS `launchd`.

---

## What It Does

Keeps `~/.gemini/antigravity/knowledge/` in sync on both machines so VPS-side Antigravity agents can access the same distilled knowledge (API creds, pipeline architecture, VPS patterns, etc.) as the local Mac instance — and vice versa.

- **Newer files always win** (`rsync --update`)
- **Pull first, push second** — VPS changes arrive before local changes overwrite
- **Excludes `knowledge.lock`** to avoid conflicts

---

## Files

| File | Path | Purpose |
|---|---|---|
| **Sync script** | `agent_os/scripts/sync-knowledge.sh` | Bidirectional rsync wrapper |
| **launchd plist** | `~/Library/LaunchAgents/com.antigravity.knowledge-sync.plist` | macOS background service |
| **Sync log** | `~/.gemini/antigravity/knowledge-sync.log` | Timestamped sync activity |

---

## How It Runs

| Trigger | Detail |
|---|---|
| **On file change** | `WatchPaths` monitors `~/.gemini/antigravity/knowledge` — any file change triggers a sync |
| **Every 5 min** | `StartInterval: 300` as a fallback periodic sync |
| **On reboot** | `launchd` auto-loads from `~/Library/LaunchAgents/` on login |

---

## Manual Commands

```bash
# From project root
./agent_os/scripts/sync-knowledge.sh push    # local → VPS only
./agent_os/scripts/sync-knowledge.sh pull    # VPS → local only
./agent_os/scripts/sync-knowledge.sh both    # bidirectional (default)
./agent_os/scripts/sync-knowledge.sh watch   # continuous fswatch mode (requires: brew install fswatch)
```

---

## Service Management

```bash
# Check if running
launchctl list | grep knowledge-sync

# Stop the service
launchctl unload ~/Library/LaunchAgents/com.antigravity.knowledge-sync.plist

# Start the service
launchctl load ~/Library/LaunchAgents/com.antigravity.knowledge-sync.plist

# View recent sync activity
tail -20 ~/.gemini/antigravity/knowledge-sync.log
```

---

## How It Was Set Up

1. Created `scripts/sync-knowledge.sh` — rsync wrapper that reuses the existing SSH master connection from `vps.sh` (`ControlPath: ~/.ssh/ctrl-julio@45.55.90.156:22`)
2. Created `~/Library/LaunchAgents/com.antigravity.knowledge-sync.plist` — macOS launchd service with `WatchPaths` + `StartInterval`
3. Loaded with `launchctl load`
4. Initial sync pushed 4 local KIs to VPS and pulled 1 VPS KI to local

---

## Synced Knowledge Items

| Item | Origin |
|---|---|
| `api_and_credential_management` | Mac → VPS |
| `indeed_pipeline_architecture_and_status` | Mac → VPS |
| `supabase_mcp_standard_configuration` | Mac → VPS |
| `vps_deployment_and_management_patterns` | Mac → VPS |
| `linkedin_job_hunter_pipeline_architecture` | VPS → Mac |

---

## Dependencies

- SSH master connection alive (auto-reconnects via `vps.sh reconnect`)
- `rsync` (pre-installed on macOS)
- Optional: `fswatch` for `watch` mode (`brew install fswatch`)
