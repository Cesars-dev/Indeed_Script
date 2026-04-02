#!/bin/bash
# =============================================================================
# gatekeeper.sh — Pre-flight secret scan before every git push
# Usage: ./agent_os/scripts/gatekeeper.sh "your commit message"
#
# Scans all changes (staged + unstaged + new files) before allowing a push.
# Clean → commits and pushes automatically.
# Dirty → blocks push, shows exactly what was found and where.
#
# ✅ Works on Mac (BSD grep) and VPS (GNU grep) — POSIX ERE only, no PCRE.
# =============================================================================

COMMIT_MSG="${1:-"Auto-commit — $(date '+%Y-%m-%d %H:%M')"}"

# ─── Pass 1: Known vendor prefixes ───────────────────────────────────────────
# Single-line alternation — same vendors as keyhound.sh, grep-safe.

VENDOR_PATTERN="(sk-proj-[a-zA-Z0-9_-]{20,}\
|sk-ant-api[a-zA-Z0-9_-]{20,}\
|sk-or-v1-[a-zA-Z0-9_-]{20,}\
|apify_api_[a-zA-Z0-9_-]{15,}\
|ghp_[a-zA-Z0-9]{36,}\
|github_pat_[a-zA-Z0-9_]{80,}\
|nfp_[a-zA-Z0-9]{30,}\
|fc-[a-zA-Z0-9]{15,}\
|dop_v1_[a-zA-Z0-9]{64,}\
|AIzaSy[a-zA-Z0-9_-]{33}\
|sbp_[a-zA-Z0-9]{40,}\
|eyJ[a-zA-Z0-9_-]{40,}\.eyJ\
|xoxb-[a-zA-Z0-9_-]{20,}\
|xoxp-[a-zA-Z0-9_-]{20,}\
|pk_live_[a-zA-Z0-9]{20,}\
|sk_live_[a-zA-Z0-9]{20,}\
|whsec_[a-zA-Z0-9]{20,}\
|Bearer [a-zA-Z0-9_.\-]{20,})"

# ─── Pass 2: Variable name triggers ──────────────────────────────────────────
# Catches any secret-named variable with a 15+ char value.
# Broad by design — covers Webshare, AdsPower, and unknown future services.

INDICATOR_PATTERN="(_KEY|_TOKEN|_SECRET|_PASSWORD|_PASSWD|_CREDENTIAL|_AUTH\
|_ACCESS|_PRIVATE|_BEARER|_HASH|_PROXY|_PASS|_SID|_PWD|_CERT\
|_SIGNING|_WEBHOOK|_SIGNATURE|_HMAC\
|API_|SECRET_|TOKEN_|AUTH_|ACCESS_|PRIVATE_|PROXY_|SIGNING_)[a-zA-Z0-9_]*[[:space:]]*=[[:space:]]*[^[:space:]]{15,}"

# ─── Pass 3: Unknown vendor format catch ─────────────────────────────────────
# Assignment where value is: short-prefix + separator + 20+ alphanumeric chars.
# Catches brand new vendors with formats we've never seen before.

UNKNOWN_PATTERN="=[[:space:]]*['\"]?[a-zA-Z]{1,8}[-_][a-zA-Z0-9_-]{20,}"

# ─── Header ───────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         🛡️  GATEKEEPER — PRE-PUSH SCAN                  ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ─── Collect changes ──────────────────────────────────────────────────────────

# All added/modified lines from tracked changes (staged + unstaged)
DIFF_LINES=$(
  { git diff HEAD --unified=0 2>/dev/null
    git diff --cached --unified=0 2>/dev/null
  } | grep "^+" | grep -Ev "^\+\+\+"
)

# Any brand-new untracked files being added
NEW_FILES=$(git ls-files --others --exclude-standard 2>/dev/null)

# ─── Run 3 passes ─────────────────────────────────────────────────────────────

# On diff content
FOUND_P1=$(echo "$DIFF_LINES" | grep -E "$VENDOR_PATTERN"    2>/dev/null)
FOUND_P2=$(echo "$DIFF_LINES" | grep -E "$INDICATOR_PATTERN" 2>/dev/null)
FOUND_P3=$(echo "$DIFF_LINES" | grep -E "$UNKNOWN_PATTERN"   2>/dev/null)

# On new untracked files (list files containing matches, not line content)
FOUND_NEW=""
if [ -n "$NEW_FILES" ]; then
  FOUND_NEW=$(echo "$NEW_FILES" \
    | xargs grep -lE "$VENDOR_PATTERN|$INDICATOR_PATTERN" 2>/dev/null \
    | sed 's/^/  New file: /')
fi

# Combine all findings
FOUND_ALL=$(printf "%s\n%s\n%s\n%s" \
  "$FOUND_P1" "$FOUND_P2" "$FOUND_P3" "$FOUND_NEW" \
  | grep .)

# ─── Decision ─────────────────────────────────────────────────────────────────

if [ -z "$FOUND_ALL" ]; then
  echo "  ✅  Clean — no secrets detected in changes."
  echo ""
  echo "  📦  Committing and pushing..."
  echo "      Message: \"$COMMIT_MSG\""
  echo "──────────────────────────────────────────────────────────"
  git add .
  git status
  git commit -m "$COMMIT_MSG"
  git push origin main
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  ✅  DONE — pushed to GitHub."
  echo "══════════════════════════════════════════════════════════"
  echo ""

else
  COUNT=$(echo "$FOUND_ALL" | wc -l | tr -d ' ')
  echo "  🚨  BLOCKED — $COUNT secret(s) detected. Push aborted."
  echo "──────────────────────────────────────────────────────────"
  echo ""
  echo "  Detected in changes:"
  echo ""
  echo "$FOUND_ALL" | head -30 | while IFS= read -r line; do
    echo "    $line"
  done
  echo ""
  echo "──────────────────────────────────────────────────────────"
  echo ""
  echo "  FIX:"
  echo "  1. Move the value(s) above into .env"
  echo "     Example:  MY_SERVICE_API_KEY=<value>"
  echo "  2. Replace inline with: os.getenv('MY_SERVICE_API_KEY')"
  echo "  3. Confirm .env is in .gitignore"
  echo "  4. Run ./agent_os/scripts/gatekeeper.sh again"
  echo ""
  echo "  💡 For a full project scan: ./agent_os/scripts/keyhound.sh"
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  🚨  DO NOT PUSH until scan is clean."
  echo "══════════════════════════════════════════════════════════"
  echo ""
  exit 1
fi
