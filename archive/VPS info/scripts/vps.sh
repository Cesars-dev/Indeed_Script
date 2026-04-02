#!/bin/bash
# =============================================================================
# vps.sh — One-command VPS control
# Usage:
#   ./vps.sh              → attach to bridge tmux session (interactive)
#   ./vps.sh "command"    → run a single command and return output
#   ./vps.sh status       → check connection + tmux session status
#   ./vps.sh pull         → git pull latest code on VPS
#   ./vps.sh push "msg"   → safe push (gatekeeper.sh) from VPS back to GitHub
#   ./vps.sh reconnect    → re-open master SSH connection
# =============================================================================

VPS_HOST="vps-julio"  # matches ~/.ssh/config
CONTROL_PATH="$HOME/.ssh/ctrl-julio@45.55.90.156:22"

# Auto-derive VPS project path from git repo name
# Convention: repo name = VPS folder name (no spaces, use - or _)
REPO_NAME=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')

# Load .env overrides
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
  export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep -v '^$' | xargs 2>/dev/null)
fi

VPS_KEY="${VPS_SSH_KEY:-/Users/Cesar_1/.ssh/mcpssh_accesskey.admin_only}"
VPS_PROJECT="${VPS_PROJECT_PATH:-/home/julio/projects/$REPO_NAME}"

# ─── Check if master connection is alive ──────────────────────────────────────
is_connected() {
  ssh -O check -o ControlPath="$CONTROL_PATH" $VPS_HOST 2>/dev/null
}

# ─── Re-open master connection ────────────────────────────────────────────────
reconnect() {
  echo "🔌 Opening SSH master connection..."
  PASSPHRASE="${VPS_SSH_PASSPHRASE:-}"
  if [ -z "$PASSPHRASE" ]; then
    echo "⚠️  VPS_SSH_PASSPHRASE not set in .env — SSH key must be passphrase-free or already added to agent"
  fi
  expect << EXPECT
spawn ssh-add $VPS_KEY
expect {
  "Enter passphrase" { send "$PASSPHRASE\r"; exp_continue }
  "Identity added"   { }
  eof                { }
}
EXPECT
  ssh -i "$VPS_KEY" -o StrictHostKeyChecking=no \
    -o ControlMaster=auto \
    -o ControlPath="$CONTROL_PATH" \
    -o ControlPersist=8h \
    -fN $VPS_HOST && echo "✅ Connected"
}

# ─── Main logic ───────────────────────────────────────────────────────────────

CMD="${1:-attach}"

# Auto-reconnect if not connected
if ! is_connected 2>/dev/null; then
  reconnect
fi

case "$CMD" in

  attach|"")
    echo "🖥️  Attaching to bridge session on VPS..."
    ssh -t $VPS_HOST "tmux attach -t bridge 2>/dev/null || tmux new-session -s bridge"
    ;;

  status)
    echo "=== SSH Connection ==="
    is_connected && echo "✅ Master connection alive" || echo "❌ Not connected"
    echo ""
    echo "=== VPS tmux sessions ==="
    ssh $VPS_HOST "tmux ls 2>/dev/null || echo 'No sessions'"
    echo ""
    echo "=== Project git status ==="
    ssh $VPS_HOST "cd '$VPS_PROJECT' && git log --oneline -3"
    ;;

  pull)
    echo "⬇️  Pulling latest from GitHub on VPS..."
    ssh $VPS_HOST "cd '$VPS_PROJECT' && git pull && echo '✅ VPS synced'"
    ;;

  push)
    MSG="${2:-"VPS push — $(date '+%Y-%m-%d %H:%M')"}"
    echo "⬆️  Safe push from VPS..."
    ssh $VPS_HOST "cd '$VPS_PROJECT' && ./agent_os/scripts/gatekeeper.sh '$MSG'"
    ;;

  reconnect)
    reconnect
    ;;

  *)
    # Run any arbitrary command on VPS
    echo "▶️  Running: $*"
    ssh $VPS_HOST "cd '$VPS_PROJECT' && $*"
    ;;

esac
