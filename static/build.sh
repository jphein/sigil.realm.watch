#!/usr/bin/env bash
# Generate version.json and inject meta tag for static sites.
#
# Usage:
#   ./build.sh --name opus --description "Claude Opus 4.6 info page" \
#              --realm stellar --repo https://github.com/jphein/opus \
#              --html index.html [--dir /path/to/site]
#
# Outputs:
#   - version.json in the site directory
#   - Injects/updates <meta name="realm-version"> in the HTML file
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REALMS_JSON="$SCRIPT_DIR/../words/realms.json"

# Parse args
NAME="" DESCRIPTION="" REALM="" REPO="" HTML="" DIR="."
while [[ $# -gt 0 ]]; do
  case $1 in
    --name) NAME="$2"; shift 2;;
    --description) DESCRIPTION="$2"; shift 2;;
    --realm) REALM="$2"; shift 2;;
    --repo) REPO="$2"; shift 2;;
    --html) HTML="$2"; shift 2;;
    --dir) DIR="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

if [[ -z "$NAME" || -z "$DESCRIPTION" || -z "$REALM" || -z "$REPO" ]]; then
  echo "Required: --name, --description, --realm, --repo"
  exit 1
fi

cd "$DIR"

# Gather git info
HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
DIRTY=$(git diff --quiet 2>/dev/null && echo "false" || echo "true")
BUILT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Generate magical name
VERSION_NAME=$(python3 -c "
import json, sys
with open('$REALMS_JSON') as f:
    realms = json.load(f)
r = realms.get('$REALM', realms['fantasy'])
seed = int('$HASH', 16) if '$HASH' != 'dev' else 0
adj = r['adjectives'][seed % len(r['adjectives'])]
noun = r['nouns'][(seed >> 8) % len(r['nouns'])]
print(f'{adj} {noun} · $HASH')
")

COMMIT_URL=""
if [[ "$HASH" != "dev" ]]; then
  COMMIT_URL="$REPO/commit/$HASH"
fi

# Magical sigil declaration — printed FIRST so it lands at top of terminal output
RESET="\033[0m"
GOLD="\033[38;5;220m"
VIOLET="\033[38;5;141m"
DIM="\033[2;37m"
BOLD="\033[1m"
SPARK="\033[38;5;213m"

echo ""
echo -e "    ${SPARK}✦${RESET}   ${DIM}── ── ── ── ── ── ── ──${RESET}   ${SPARK}✦${RESET}"
echo -e "          ${BOLD}${GOLD}${VERSION_NAME}${RESET}"
echo -e "          ${DIM}realm${RESET} ${VIOLET}${REALM}${RESET}    ${DIM}·${RESET}    ${DIM}sigil bound${RESET}"
echo -e "    ${SPARK}✦${RESET}   ${DIM}── ── ── ── ── ── ── ──${RESET}   ${SPARK}✦${RESET}"
echo ""

# Write version.json
python3 -c "
import json
data = {
    'name': '$NAME',
    'description': '$DESCRIPTION',
    'version': '''$VERSION_NAME''',
    'hash': '$HASH',
    'branch': '$BRANCH',
    'dirty': $([ "$DIRTY" = "true" ] && echo True || echo False),
    'built': '$BUILT',
    'realm': '$REALM',
    'repo': '$REPO',
    'commit_url': '$COMMIT_URL',
}
with open('version.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

echo -e "  ${DIM}✓ version.json written${RESET}"

# Inject/update meta tag in HTML if specified
if [[ -n "$HTML" && -f "$HTML" ]]; then
  META_CONTENT=$(python3 -c "
import json
with open('version.json') as f:
    d = json.load(f)
# HTML-safe JSON in single attribute
print(json.dumps(d))
")

  # Escape for sed
  META_ESCAPED=$(printf '%s' "$META_CONTENT" | sed 's/[&/\]/\\&/g')
  META_TAG="<meta name=\"realm-version\" content='${META_ESCAPED}'>"

  # Anchor on the OPENING TAG, not the bare attribute. A page that reads its own
  # sigil contains the string `name="realm-version"` in JS —
  #     document.querySelector('meta[name="realm-version"]')
  # — so a bare-attribute grep matched, the update branch ran, and the
  # `<meta ...>` sed found nothing to replace. Result: no tag injected, and
  # "✓ Updated meta tag" printed anyway. Silent no-op, and self-version-checking
  # pages are exactly the ones that need the tag most (jphein/sconce, 2026-08-04).
  if grep -q '<meta[[:space:]]\+name="realm-version"' "$HTML"; then
    # Update existing
    sed -i "s|<meta name=\"realm-version\"[^>]*>|${META_TAG}|" "$HTML"
    echo -e "  ${DIM}✓ Updated meta tag in $HTML${RESET}"
  elif grep -q '</head>' "$HTML"; then
    # Insert before </head>
    sed -i "s|</head>|  ${META_TAG}\n</head>|" "$HTML"
    echo -e "  ${DIM}✓ Injected meta tag into $HTML${RESET}"
  else
    echo -e "  ${DIM}⚠ No </head> found in $HTML — skipping meta injection${RESET}"
  fi

  # Never report success on a page that ends up unstamped — the whole point is
  # that a consumer can trust the tag is there.
  if ! grep -q '<meta[[:space:]]\+name="realm-version"' "$HTML"; then
    echo -e "  ⚠ ERROR: $HTML has no realm-version tag after injection" >&2
    exit 1
  fi
fi

