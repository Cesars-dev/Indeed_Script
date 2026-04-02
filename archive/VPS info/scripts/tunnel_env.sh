#!/bin/bash
# =============================================================================
# tunnel_env.sh — Find, inspect, and sync .env files to VPS
# Usage:
#   ./agent_os/scripts/tunnel_env.sh           → scan + prompt to send
#   ./agent_os/scripts/tunnel_env.sh --dry-run → scan only, no transfer
#
# Convention: repo name = VPS folder name (no spaces — use - or _)
# VPS_PROJECT_PATH in .env only needed if you break this convention.
# =============================================================================

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Auto-derive VPS project path from git repo name
REPO_NAME=$(git remote get-url origin 2>/dev/null | sed 's/.*\///' | sed 's/\.git//')

# Load VPS config from .env (overrides defaults if set)
if [ -f "$PROJECT_ROOT/.env" ]; then
  export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep -v '^$' | xargs 2>/dev/null)
fi

VPS_KEY="${VPS_SSH_KEY:-/Users/Cesar_1/.ssh/mcpssh_accesskey.admin_only}"
VPS_USER_HOST="${VPS_USER:-julio}@${VPS_IP:-45.55.90.156}"
VPS_PROJECT="${VPS_PROJECT_PATH:-/home/julio/projects/$REPO_NAME}"

DRY_RUN=false
[ "$1" = "--dry-run" ] && DRY_RUN=true

echo ""
echo "🔍 Scanning for .env files..."
echo "   Project root: $PROJECT_ROOT"
echo "   VPS target:   $VPS_USER_HOST:$VPS_PROJECT"
echo "─────────────────────────────────────────────────────────"

# Find all .env files (exclude .git, archive, example files)
ENV_FILES=$(find "$PROJECT_ROOT" -name ".env" -not -path "*/.git/*" -not -path "*/archive/*" | sort)

if [ -z "$ENV_FILES" ]; then
  echo "⚠️  No .env files found."
  exit 0
fi

SAFE_FILES=()
EXPOSED_FILES=()

while IFS= read -r file; do
  REL_PATH="${file#$PROJECT_ROOT/}"
  echo ""
  echo "📄 $REL_PATH"

  if git -C "$PROJECT_ROOT" check-ignore -q "$file" 2>/dev/null; then
    echo "   ✅ Gitignored — safe"
    SAFE_FILES+=("$file")
  else
    echo "   🚨 NOT gitignored — skipping (fix this first)"
    EXPOSED_FILES+=("$file")
  fi

  echo "   Keys:"
  grep -v "^#" "$file" | grep -v "^$" | while IFS= read -r line; do
    KEY=$(echo "$line" | cut -d'=' -f1)
    VALUE=$(echo "$line" | cut -d'=' -f2-)
    PREVIEW="${VALUE:0:8}***"
    echo "     • $KEY = $PREVIEW"
  done

done <<< "$ENV_FILES"

echo ""
echo "─────────────────────────────────────────────────────────"
echo "📊 ${#SAFE_FILES[@]} safe  |  ${#EXPOSED_FILES[@]} exposed (skipped)"

if [ "${#EXPOSED_FILES[@]}" -gt 0 ]; then
  echo "⚠️  Fix exposed files before syncing: add them to .gitignore"
fi

if [ "${#SAFE_FILES[@]}" -eq 0 ]; then
  echo "Nothing safe to send."
  exit 0
fi

# ─── DRY RUN ─────────────────────────────────────────────────────────────────
if $DRY_RUN; then
  echo ""
  echo "🔎 Dry run — would send:"
  for file in "${SAFE_FILES[@]}"; do
    REL_PATH="${file#$PROJECT_ROOT/}"
    echo "   $REL_PATH → $VPS_USER_HOST:$VPS_PROJECT/$REL_PATH"
  done
  echo ""
  exit 0
fi

# ─── CONFIRM & SEND ──────────────────────────────────────────────────────────
echo ""
echo "📦 Ready to send ${#SAFE_FILES[@]} file(s) to VPS:"
for file in "${SAFE_FILES[@]}"; do
  REL_PATH="${file#$PROJECT_ROOT/}"
  echo "   → $VPS_USER_HOST:$VPS_PROJECT/$REL_PATH"
done

echo ""
read -p "Send now? (y/N) " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "⬆️  Sending..."
SUCCESS=0
FAIL=0

for file in "${SAFE_FILES[@]}"; do
  REL_PATH="${file#$PROJECT_ROOT/}"
  REMOTE_DIR="$VPS_PROJECT/$(dirname "$REL_PATH")"
  REMOTE_PATH="$VPS_PROJECT/$REL_PATH"

  # Ensure remote directory exists
  ssh -i "$VPS_KEY" -o StrictHostKeyChecking=no "$VPS_USER_HOST" "mkdir -p '$REMOTE_DIR'" 2>/dev/null

  # Send the file
  if scp -i "$VPS_KEY" -o StrictHostKeyChecking=no "$file" "$VPS_USER_HOST:'$REMOTE_PATH'" 2>/dev/null; then
    echo "   ✅ $REL_PATH"
    SUCCESS=$((SUCCESS + 1))
  else
    echo "   ❌ $REL_PATH — failed"
    FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "─────────────────────────────────────────────────────────"
echo "✅ $SUCCESS sent  |  ❌ $FAIL failed"
echo ""
