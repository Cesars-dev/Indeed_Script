#!/bin/bash
# =============================================================================
# keyhound.sh — Full project-wide secret hunt
# Usage: ./agent_os/scripts/keyhound.sh
#
# Sniffs out exposed API keys and secrets across the entire project.
# Run on-demand anytime. Use gatekeeper.sh for pre-push scanning.
#
# ✅ Works on Mac (BSD grep) and VPS (GNU grep) — POSIX ERE only, no PCRE.
# =============================================================================

# ─── Config ───────────────────────────────────────────────────────────────────

EXCLUDE_DIRS=(
  ".venv"
  "venv_local"
  "archive"
  "node_modules"
  "@supabase"
  ".git"
)

INCLUDE_EXT=(
  "*.py" "*.js" "*.ts" "*.sh"
  "*.md" "*.txt" "*.json" "*.toml"
  "*.yaml" "*.yml" "*.env.*"
)

SKIP_FILES=(
  ".env"
  "keyhound.sh"
  "gatekeeper.sh"
  "tunnel_env.sh"   # contains SSH key path as default fallback — not a real secret
  "vps.sh"          # contains SSH key path as default fallback — not a real secret
  "package-lock.json"
  "package.json"
  # mcp.json is NOT skipped — MCP servers can have exposed keys, always scan them
)

# ─── Per-project exceptions (.keyhound-ignore) ────────────────────────────────
# Add a .keyhound-ignore file to your project root to exempt specific files.
# One filename (basename only) per line. Comments (#) and blank lines ok.
# Example:
#   # this MCP config uses env var refs, confirmed no raw keys
#   my-mcp-config.json
#
# This file CAN be committed — it's an audit exception, not a secret.
# keyhound.sh (the shared script) stays generic. Exceptions stay per-project.
#
# ⛔ AGENT RULE: Never create or modify .keyhound-ignore without a direct, explicit
#   user instruction (e.g. "keyhound ignore this file").
#   Do NOT suggest it. Do NOT offer it. Do NOT ask about it.
#   If keyhound flags something → report it and stop. That's it.

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
IGNORE_FILE="$PROJECT_ROOT/.keyhound-ignore"

if [ -f "$IGNORE_FILE" ]; then
  while IFS= read -r line; do
    # strip comments and blank lines
    line=$(echo "$line" | sed 's/#.*//' | xargs)
    [ -n "$line" ] && SKIP_FILES+=("$line")
  done < "$IGNORE_FILE"
  echo "  📋 Loaded $(grep -cv '^\s*#\|^\s*$' "$IGNORE_FILE" 2>/dev/null || echo 0) project-specific exception(s) from .keyhound-ignore"
fi

# ─── Build grep args ──────────────────────────────────────────────────────────

EXCLUDE_ARGS=()
for dir in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_ARGS+=("--exclude-dir=$dir")
done

INCLUDE_ARGS=()
for ext in "${INCLUDE_EXT[@]}"; do
  INCLUDE_ARGS+=("--include=$ext")
done

# ─── Pass 1: Known vendor prefixes ───────────────────────────────────────────
# Explicit recognizable formats. Adding a new vendor = add one line to this array.

VENDOR_PREFIXES=(
  "sk-proj-[a-zA-Z0-9_-]{20,}"          # OpenAI
  "sk-ant-api[a-zA-Z0-9_-]{20,}"        # Anthropic
  "sk-or-v1-[a-zA-Z0-9_-]{20,}"         # OpenRouter
  "apify_api_[a-zA-Z0-9_-]{15,}"        # Apify
  "ghp_[a-zA-Z0-9]{36,}"                # GitHub PAT classic
  "github_pat_[a-zA-Z0-9_]{80,}"        # GitHub PAT fine-grained
  "nfp_[a-zA-Z0-9]{30,}"                # Netlify
  "fc-[a-zA-Z0-9]{15,}"                 # Firecrawl (15+ chars required — avoids false positives)
  "dop_v1_[a-zA-Z0-9]{64,}"             # DigitalOcean
  "AIzaSy[a-zA-Z0-9_-]{33}"             # Google / Gemini
  "sbp_[a-zA-Z0-9]{40,}"                # Supabase personal token
  "eyJ[a-zA-Z0-9_-]{40,}\.eyJ"          # JWT / Supabase anon key
  "xoxb-[a-zA-Z0-9_-]{20,}"             # Slack bot token
  "xoxp-[a-zA-Z0-9_-]{20,}"             # Slack user token
  "pk_live_[a-zA-Z0-9]{20,}"            # Stripe publishable key
  "sk_live_[a-zA-Z0-9]{20,}"            # Stripe secret key
  "whsec_[a-zA-Z0-9]{20,}"              # Stripe webhook secret
  "Bearer [a-zA-Z0-9_.\-]{20,}"         # Generic Bearer token
)

# ─── Pass 2: Variable name triggers ──────────────────────────────────────────
# If this word appears in a variable name AND the value is 15+ chars → flag it.
# Catches Webshare, AdsPower, and any future unknown service — broad by design.

KEY_INDICATORS=(
  "_KEY"        "_TOKEN"       "_SECRET"      "_PASSWORD"
  "_PASSWD"     "_CREDENTIAL"  "_AUTH"        "_ACCESS"
  "_PRIVATE"    "_BEARER"      "_HASH"        "_PROXY"
  "_PASS"       "_SID"         "_PWD"         "_CERT"
  "_SIGNING"    "_WEBHOOK"     "_SIGNATURE"   "_HMAC"
  "API_"        "SECRET_"      "TOKEN_"       "AUTH_"
  "ACCESS_"     "PRIVATE_"     "PROXY_"       "SIGNING_"
)

# ─── Pass 3: Unknown format catch ────────────────────────────────────────────
# Catches brand new / unknown vendor key formats we've never seen before.
# Heuristic: any assignment where the value starts with a short prefix,
# a separator (- or _), then 20+ chars of alphanumeric random string.
# ONLY fires on lines with = (assignment context) — filters out git logs etc.

UNKNOWN_FORMAT="=[[:space:]]*['\"]?[a-zA-Z]{1,8}[-_][a-zA-Z0-9_-]{20,}"

# ─── Build single grep patterns from arrays (runs once, fast) ────────────────
# Arrays above are readable/editable. These join them into 3 total grep calls.

VENDOR_PATTERN="("
for i in "${!VENDOR_PREFIXES[@]}"; do
  [ $i -gt 0 ] && VENDOR_PATTERN+="|"
  VENDOR_PATTERN+="${VENDOR_PREFIXES[$i]}"
done
VENDOR_PATTERN+=")"

INDICATOR_PATTERN="("
for i in "${!KEY_INDICATORS[@]}"; do
  [ $i -gt 0 ] && INDICATOR_PATTERN+="|"
  INDICATOR_PATTERN+="${KEY_INDICATORS[$i]}"
done
INDICATOR_PATTERN+=")[a-zA-Z0-9_]*[[:space:]]*=[[:space:]]*[^[:space:]]{15,}"

# ─── Header ───────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          🐕  KEYHOUND — SECRET HUNT                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Root: $(pwd)"
echo ""

# ─── Helper: filter skip files ───────────────────────────────────────────────

filter_skips() {
  while IFS= read -r line; do
    skip=false
    for skipfile in "${SKIP_FILES[@]}"; do
      if [[ "$line" == "./$skipfile:"* ]] || [[ "$line" == *"/$skipfile:"* ]]; then
        skip=true
        break
      fi
    done
    [ "$skip" = false ] && [ -n "$line" ] && echo "$line"
  done
}

# ─── Run all 3 passes ─────────────────────────────────────────────────────────

ALL_RESULTS=""

# Pass 1 — Known vendor prefixes (1 grep call)
echo "  🔎 Pass 1: Known vendor patterns..."
RAW=$(grep -rn "${INCLUDE_ARGS[@]}" "${EXCLUDE_ARGS[@]}" -E "$VENDOR_PATTERN" . 2>/dev/null)
FILTERED=$(echo "$RAW" | filter_skips)
[ -n "$FILTERED" ] && ALL_RESULTS+="$FILTERED"$'\n'

# Pass 2 — Variable name triggers (1 grep call)
echo "  🔎 Pass 2: Secret-named variables..."
RAW=$(grep -rn "${INCLUDE_ARGS[@]}" "${EXCLUDE_ARGS[@]}" -E "$INDICATOR_PATTERN" . 2>/dev/null)
FILTERED=$(echo "$RAW" | filter_skips)
[ -n "$FILTERED" ] && ALL_RESULTS+="$FILTERED"$'\n'

# Pass 3 — Unknown vendor formats (1 grep call)
echo "  🔎 Pass 3: Unknown vendor formats..."
RAW=$(grep -rn "${INCLUDE_ARGS[@]}" "${EXCLUDE_ARGS[@]}" -E "$UNKNOWN_FORMAT" . 2>/dev/null)
FILTERED=$(echo "$RAW" | filter_skips)
[ -n "$FILTERED" ] && ALL_RESULTS+="$FILTERED"$'\n'

# Extra file scan (e.g. master .env passed as arg)
if [ -n "$1" ] && [ -f "$1" ]; then
  echo "  🔎 Extra: Scanning $1..."
  RAW=$(grep -nE "$VENDOR_PATTERN|$INDICATOR_PATTERN" "$1" 2>/dev/null | sed "s|^|$1:|")
  [ -n "$RAW" ] && ALL_RESULTS+="$RAW"$'\n'
fi

# Deduplicate and clean
RESULTS=$(echo "$ALL_RESULTS" | sort -u | grep .)

# ─── Output ───────────────────────────────────────────────────────────────────

echo ""

if [ -z "$RESULTS" ]; then
  echo "  ✅  CLEAN — No exposed secrets found."
  echo ""
  echo "  Scanned:  .py .js .ts .sh .md .txt .json .toml .yaml .yml"
  echo "  Skipped:  .venv/ venv_local/ archive/ node_modules/ .git/"
  echo "  Excluded: .env (by design — secrets live there)"
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  ✅  Project is clean. Safe to push via gatekeeper.sh"
  echo "══════════════════════════════════════════════════════════"
  echo ""
  exit 0

else
  COUNT=$(echo "$RESULTS" | wc -l | tr -d ' ')
  echo "  🚨  SECRETS FOUND — $COUNT hit(s)"
  echo ""
  echo "──────────────────────────────────────────────────────────"

  CURRENT_FILE=""
  while IFS= read -r hit; do
    [ -z "$hit" ] && continue
    FILE=$(echo "$hit" | cut -d: -f1)
    LINE=$(echo "$hit" | cut -d: -f2)
    CONTENT=$(echo "$hit" | cut -d: -f3-)

    if [ "$FILE" != "$CURRENT_FILE" ]; then
      echo ""
      echo "  📄 $FILE"
      CURRENT_FILE="$FILE"
    fi

    # Identify key type where possible
    TYPE="unknown format — review manually"
    [[ "$CONTENT" =~ sk-proj-        ]] && TYPE="OpenAI key"
    [[ "$CONTENT" =~ sk-ant-api      ]] && TYPE="Anthropic key"
    [[ "$CONTENT" =~ sk-or-v1-       ]] && TYPE="OpenRouter key"
    [[ "$CONTENT" =~ apify_api_      ]] && TYPE="Apify token"
    [[ "$CONTENT" =~ eyJ.*\.eyJ      ]] && TYPE="JWT / Supabase key"
    [[ "$CONTENT" =~ ghp_            ]] && TYPE="GitHub PAT (classic)"
    [[ "$CONTENT" =~ github_pat_     ]] && TYPE="GitHub PAT (fine-grained)"
    [[ "$CONTENT" =~ nfp_            ]] && TYPE="Netlify token"
    [[ "$CONTENT" =~ ^.*fc-          ]] && TYPE="Firecrawl key"
    [[ "$CONTENT" =~ dop_v1_         ]] && TYPE="DigitalOcean token"
    [[ "$CONTENT" =~ AIzaSy          ]] && TYPE="Google / Gemini key"
    [[ "$CONTENT" =~ sbp_            ]] && TYPE="Supabase personal token"
    [[ "$CONTENT" =~ xoxb-           ]] && TYPE="Slack bot token"
    [[ "$CONTENT" =~ sk_live_        ]] && TYPE="Stripe secret key"
    [[ "$CONTENT" =~ pk_live_        ]] && TYPE="Stripe publishable key"
    [[ "$CONTENT" =~ whsec_          ]] && TYPE="Stripe webhook secret"
    [[ "$CONTENT" =~ Bearer          ]] && TYPE="Bearer token"

    echo "     Line $LINE — [$TYPE]"
    echo "     $(echo "$CONTENT" | tr -d '\n' | cut -c1-120)"
    echo ""

  done <<< "$RESULTS"

  echo ""
  echo "──────────────────────────────────────────────────────────"
  echo ""
  echo "  FIX CHECKLIST:"
  echo "  1. Open each file listed above"
  echo "  2. Move the raw key value into .env"
  echo "     Example:  MY_SERVICE_API_KEY=<value>"
  echo "  3. Replace inline value with: os.getenv('MY_SERVICE_API_KEY')"
  echo "  4. Confirm .env is in .gitignore"
  echo "  5. Run ./agent_os/scripts/keyhound.sh again to confirm clean"
  echo "  6. Then push via: ./agent_os/scripts/gatekeeper.sh 'your message'"
  echo ""
  echo "  💡 If a hit is a confirmed false positive, report it to the user."
  echo "     Do NOT add exceptions without explicit user instruction."
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  🚨  DO NOT PUSH until this audit shows CLEAN."
  echo "══════════════════════════════════════════════════════════"
  echo ""
  exit 1
fi
