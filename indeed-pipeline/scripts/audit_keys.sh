#!/bin/bash
# =============================================================================
# audit_keys.sh — Full project-wide API key scan
# Usage: ./audit_keys.sh
# Run anytime to check if any secrets are exposed in the project.
# =============================================================================

# ─── Config ──────────────────────────────────────────────────────────────────

# Directories to skip entirely
EXCLUDE_DIRS=(
  ".venv"
  "archive"
  "node_modules"
  "@supabase"
  ".git"
)

# File extensions to scan
INCLUDE_EXT=(
  "*.py" "*.js" "*.ts" "*.sh"
  "*.md" "*.txt" "*.json" "*.toml"
  "*.yaml" "*.yml" "*.env.*"
)

# Files to always skip (even if extension matches)
SKIP_FILES=(
  ".env"
  "audit_keys.sh"
  "safe_push.sh"
  "package-lock.json"
)

# ─── Build grep excludes ──────────────────────────────────────────────────────

EXCLUDE_ARGS=()
for dir in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_ARGS+=("--exclude-dir=$dir")
done

INCLUDE_ARGS=()
for ext in "${INCLUDE_EXT[@]}"; do
  INCLUDE_ARGS+=("--include=$ext")
done

# ─── Patterns ────────────────────────────────────────────────────────────────

PATTERN='(sk-proj-[a-zA-Z0-9_-]{20,}|sk-ant-api[a-zA-Z0-9_-]{20,}|sk-or-v1-[a-zA-Z0-9_-]{20,}|apify_api_[a-zA-Z0-9_-]{15,}|eyJ[a-zA-Z0-9_-]{40,}\.eyJ|AIzaSy[a-zA-Z0-9_-]{30,})'

# ─── Header ──────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           🔍  API KEY AUDIT — FULL PROJECT SCAN          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Root: $(pwd)"
echo ""

# ─── Run scan ────────────────────────────────────────────────────────────────

RAW=$(grep -rn "${INCLUDE_ARGS[@]}" "${EXCLUDE_ARGS[@]}" -E "$PATTERN" . 2>/dev/null)

# Filter out skip files
RESULTS=""
while IFS= read -r line; do
  skip=false
  for skipfile in "${SKIP_FILES[@]}"; do
    if [[ "$line" == "./$skipfile:"* ]] || [[ "$line" == *"/$skipfile:"* ]]; then
      skip=true
      break
    fi
  done
  if [ "$skip" = false ] && [ -n "$line" ]; then
    RESULTS+="$line"$'\n'
  fi
done <<< "$RAW"

# ─── Output ──────────────────────────────────────────────────────────────────

LAYER1_EXIT=0

if [ -z "$RESULTS" ]; then
  echo "  ✅  LAYER 1 CLEAN — No known key formats found."
  echo ""
  echo "  Scanned: .py .js .ts .sh .md .txt .json .toml .yaml"
  echo "  Skipped: .venv/ archive/ node_modules/ @supabase/ .git/"
  echo "  Excluded: .env (by design — secrets live here)"
  echo ""

else
  COUNT=$(echo "$RESULTS" | grep -c .)
  echo "  🚨  LAYER 1: EXPOSED KEYS FOUND — $COUNT hit(s)"
  echo ""
  echo "──────────────────────────────────────────────────────────"

  CURRENT_FILE=""
  while IFS= read -r hit; do
    FILE=$(echo "$hit" | cut -d: -f1)
    LINE=$(echo "$hit" | cut -d: -f2)
    CONTENT=$(echo "$hit" | cut -d: -f3-)

    if [ "$FILE" != "$CURRENT_FILE" ]; then
      echo ""
      echo "  📄 $FILE"
      CURRENT_FILE="$FILE"
    fi

    TYPE="unknown"
    [[ "$CONTENT" =~ sk-or-v1- ]]   && TYPE="OpenRouter key"
    [[ "$CONTENT" =~ sk-ant-api ]]   && TYPE="Anthropic key"
    [[ "$CONTENT" =~ sk-proj- ]]     && TYPE="OpenAI key"
    [[ "$CONTENT" =~ apify_api_ ]]   && TYPE="Apify token"
    [[ "$CONTENT" =~ eyJ.*\.eyJ ]]   && TYPE="JWT / Supabase anon key"
    [[ "$CONTENT" =~ AIzaSy ]]       && TYPE="Google / Gemini key"

    TRUNCATED=$(echo "$CONTENT" | sed -E 's/(sk-or-v1-[a-zA-Z0-9_-]{10})[a-zA-Z0-9_-]+/\1***/g' \
      | sed -E 's/(sk-ant-api[a-zA-Z0-9_-]{10})[a-zA-Z0-9_-]+/\1***/g' \
      | sed -E 's/(sk-proj-[a-zA-Z0-9_-]{10})[a-zA-Z0-9_-]+/\1***/g' \
      | sed -E 's/(apify_api_[a-zA-Z0-9_]{10})[a-zA-Z0-9_-]+/\1***/g' \
      | sed -E 's/(eyJ[a-zA-Z0-9_-]{15})[a-zA-Z0-9_.-]+/\1***/g' \
      | sed -E 's/(AIzaSy[a-zA-Z0-9_-]{8})[a-zA-Z0-9_-]+/\1***/g')

    echo "     Line $LINE — [$TYPE]"
    echo "     $TRUNCATED" | head -c 120
    echo ""
  done <<< "$RESULTS"

  echo ""
  echo "──────────────────────────────────────────────────────────"
  echo ""
  echo "  FIX CHECKLIST:"
  echo "  1. Move the raw key value into .env"
  echo "  2. Replace inline value with os.getenv('KEY_NAME')"
  echo "  3. Confirm .env is in .gitignore"
  echo "  4. Run ./audit_keys.sh again to confirm clean"
  echo ""
  echo "══════════════════════════════════════════════════════════"
  echo "  🚨  LAYER 1 FAILED. DO NOT PUSH."
  echo "══════════════════════════════════════════════════════════"
  echo ""
  LAYER1_EXIT=1
fi

# ─── Layer 2: Heuristic scan (variable-name based, advisory only) ─────────────
# Catches assignments like: API_KEY="abc123..." / TOKEN = 'xyz...' in .py and .sh
# Lower confidence — review manually. Does NOT block push.

echo "──────────────────────────────────────────────────────────"
echo "  🔍  LAYER 2: Heuristic scan (variable-name patterns)"
echo "──────────────────────────────────────────────────────────"

HEURISTIC=$(grep -rn "${INCLUDE_ARGS[@]}" "${EXCLUDE_ARGS[@]}" \
  -E '(API_KEY|_TOKEN|_SECRET|_PASSWORD)\s*=\s*[^$({<\047"#\n][a-zA-Z0-9_\-\.]{16,}' \
  . 2>/dev/null)

# Filter skip files + false positives (os.getenv, None, example placeholders)
H_RESULTS=""
while IFS= read -r line; do
  skip=false
  for skipfile in "${SKIP_FILES[@]}"; do
    if [[ "$line" == "./$skipfile:"* ]] || [[ "$line" == *"/$skipfile:"* ]]; then
      skip=true; break
    fi
  done
  # Exclude lines that are clearly safe
  if [[ "$line" =~ os\.getenv|getenv|sys\.exit|load_dotenv|\.env|None|example|placeholder|your_ ]]; then
    skip=true
  fi
  if [ "$skip" = false ] && [ -n "$line" ]; then
    H_RESULTS+="$line"$'\n'
  fi
done <<< "$HEURISTIC"

if [ -z "$H_RESULTS" ]; then
  echo "  ✅  No suspicious variable assignments found."
else
  H_COUNT=$(echo "$H_RESULTS" | grep -c .)
  echo "  ⚠️   $H_COUNT potential hit(s) — review manually:"
  echo ""
  while IFS= read -r hit; do
    [ -z "$hit" ] && continue
    FILE=$(echo "$hit" | cut -d: -f1)
    LINE=$(echo "$hit" | cut -d: -f2)
    SNIP=$(echo "$hit" | cut -d: -f3- | sed -E 's/([a-zA-Z0-9_-]{8})[a-zA-Z0-9_-]{8,}/\1***/g')
    echo "  📄 $FILE  line $LINE"
    echo "     $SNIP" | head -c 100
    echo ""
  done <<< "$H_RESULTS"
  echo "  ℹ️   These may be false positives. Move to .env if they are real credentials."
fi

echo ""
echo "══════════════════════════════════════════════════════════"
if [ "$LAYER1_EXIT" -eq 0 ]; then
  echo "  ✅  AUDIT PASSED. Safe to push."
else
  echo "  🚨  AUDIT FAILED (Layer 1). Fix above before pushing."
fi
echo "══════════════════════════════════════════════════════════"
echo ""
exit $LAYER1_EXIT
