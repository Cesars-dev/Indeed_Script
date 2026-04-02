#!/bin/bash
# =============================================================================
# safe_push.sh — Pre-flight check before git push
# Usage: ./safe_push.sh "your commit message"
# =============================================================================

COMMIT_MSG="${1:-"Auto-commit — $(date '+%Y-%m-%d %H:%M')"}"

echo ""
echo "🔍 PRE-FLIGHT: Scanning for API keys in changed files..."
echo "─────────────────────────────────────────────────────────"

# Scan all changes that would be committed (staged + unstaged tracked files)
# grep returns lines added (starting with +) in the diff — excludes .env file itself
FOUND=$(git diff HEAD --unified=0 2>/dev/null | grep "^+" \
  | grep -Ev "^\+\+\+" \
  | grep -E "(sk-proj-[a-zA-Z0-9_-]{20,}|sk-ant-api[a-zA-Z0-9_-]{20,}|sk-or-v1-[a-zA-Z0-9_-]{20,}|apify_api_[a-zA-Z0-9_-]{15,}|eyJ[a-zA-Z0-9_-]{40,}\.eyJ)")

# Also scan untracked new files (not yet in git diff HEAD)
FOUND_NEW=$(git ls-files --others --exclude-standard 2>/dev/null \
  | xargs grep -lE "(sk-proj-[a-zA-Z0-9_-]{20,}|sk-ant-api[a-zA-Z0-9_-]{20,}|sk-or-v1-[a-zA-Z0-9_-]{20,}|apify_api_[a-zA-Z0-9_-]{15,}|eyJ[a-zA-Z0-9_-]{40,}\.eyJ)" 2>/dev/null)

# ─── DECISION ────────────────────────────────────────────────────────────────

if [ -z "$FOUND" ] && [ -z "$FOUND_NEW" ]; then
  echo "✅ Clean — no API keys detected in changes."
  echo ""
  echo "📦 Proceeding with git push..."
  echo "   Message: \"$COMMIT_MSG\""
  echo "─────────────────────────────────────────────────────────"
  git add .
  git status
  git commit -m "$COMMIT_MSG"
  git push origin main
  echo ""
  echo "✅ DONE — pushed to GitHub."

else
  echo "🚨 BLOCKED — API keys detected. Push aborted."
  echo "─────────────────────────────────────────────────────────"

  if [ -n "$FOUND" ]; then
    echo ""
    echo "Found in staged/tracked changes:"
    echo "$FOUND" | head -20
  fi

  if [ -n "$FOUND_NEW" ]; then
    echo ""
    echo "Found in new untracked files:"
    echo "$FOUND_NEW"
  fi

  echo ""
  echo "─────────────────────────────────────────────────────────"
  echo "FIX:"
  echo "  1. Move the key(s) above into .env"
  echo "  2. Replace inline value with: os.getenv('KEY_NAME')"
  echo "  3. Confirm .env is in .gitignore"
  echo "  4. Run ./safe_push.sh again"
  echo ""
  exit 1
fi
