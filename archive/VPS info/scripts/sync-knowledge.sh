#!/bin/bash
# =============================================================================
# sync-knowledge.sh — Bidirectional knowledge sync (Mac ↔ VPS)
#
# Keeps ~/.gemini/antigravity/knowledge/ in sync between local and VPS.
# Uses the existing SSH master connection from vps.sh.
#
# Usage:
#   ./sync-knowledge.sh          → full bidirectional sync
#   ./sync-knowledge.sh push     → local → VPS only
#   ./sync-knowledge.sh pull     → VPS → local only
#   ./sync-knowledge.sh watch    → continuous watch mode (fswatch)
# =============================================================================

LOCAL_KNOWLEDGE="$HOME/.gemini/antigravity/knowledge/"
REMOTE_KNOWLEDGE="~/.gemini/antigravity/knowledge/"
VPS_HOST="vps-julio"
CONTROL_PATH="$HOME/.ssh/ctrl-julio@45.55.90.156:22"
VPS_KEY="${VPS_SSH_PASSPHRASE:+}" # uses agent if loaded
LOG="$HOME/.gemini/antigravity/knowledge-sync.log"

SSH_OPTS="-o ControlPath=$CONTROL_PATH -o ConnectTimeout=5"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(timestamp)] $*" | tee -a "$LOG"; }

# Check SSH connection, try reconnect if down
ensure_connection() {
  if ! ssh -O check -o ControlPath="$CONTROL_PATH" $VPS_HOST 2>/dev/null; then
    log "⚠️  SSH not connected — attempting reconnect..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    bash "$SCRIPT_DIR/vps.sh" reconnect 2>/dev/null
    sleep 2
    if ! ssh -O check -o ControlPath="$CONTROL_PATH" $VPS_HOST 2>/dev/null; then
      log "❌ Cannot connect to VPS — skipping sync"
      return 1
    fi
  fi
  return 0
}

sync_push() {
  log "⬆️  Pushing local → VPS..."
  rsync -az --update --delete-after \
    -e "ssh $SSH_OPTS" \
    --exclude='knowledge.lock' \
    "$LOCAL_KNOWLEDGE" "$VPS_HOST:$REMOTE_KNOWLEDGE" 2>>"$LOG"
  [ $? -eq 0 ] && log "✅ Push complete" || log "❌ Push failed"
}

sync_pull() {
  log "⬇️  Pulling VPS → local..."
  rsync -az --update \
    -e "ssh $SSH_OPTS" \
    --exclude='knowledge.lock' \
    "$VPS_HOST:$REMOTE_KNOWLEDGE" "$LOCAL_KNOWLEDGE" 2>>"$LOG"
  [ $? -eq 0 ] && log "✅ Pull complete" || log "❌ Pull failed"
}

sync_both() {
  # Pull first (get VPS changes), then push (send local changes)
  # --update ensures only newer files win
  sync_pull
  sync_push
}

# ─── Main ─────────────────────────────────────────────────────────────────────

CMD="${1:-both}"

case "$CMD" in
  push)
    ensure_connection && sync_push
    ;;
  pull)
    ensure_connection && sync_pull
    ;;
  both)
    ensure_connection && sync_both
    ;;
  watch)
    log "👁️  Watching $LOCAL_KNOWLEDGE for changes..."
    if ! command -v fswatch &>/dev/null; then
      log "❌ fswatch not installed. Run: brew install fswatch"
      exit 1
    fi
    # Debounce: wait 5s after last change before syncing
    fswatch -o --latency 5 "$LOCAL_KNOWLEDGE" | while read _; do
      log "🔄 Change detected — syncing..."
      ensure_connection && sync_both
    done
    ;;
  *)
    echo "Usage: $0 [push|pull|both|watch]"
    exit 1
    ;;
esac
