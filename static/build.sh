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
# porcelain, like the python and js handlers: staged and untracked changes count (git diff --quiet saw neither)
if [ -n "$(git status --porcelain --untracked-files=normal 2>/dev/null)" ]; then DIRTY=true; else DIRTY=false; fi
BUILT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Nearest version tag for semver/build (issue #3); "" when the project has none.
DESCRIBE=$(git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]*' --long 2>/dev/null || true)

# Every value reaches python through the environment, never spliced into its source: a branch, name or description
# holding a quote used to break (or run as) the python below (xreview 11-13). The name comes from the python
# binding itself, so static sites follow the same tolerant hex parse as every other binding (issue #9); this script
# used to carry its own int(hash, 16), which disagreed for "dev" and any non-hex input.
export SIGIL_PY="$SCRIPT_DIR/../python" SIGIL_REALM="$REALM" SIGIL_HASH="$HASH"
VERSION_NAME=$(python3 -c "
import os, sys
sys.path.insert(0, os.environ['SIGIL_PY'])
from realm_sigil import generate_name
print(generate_name(os.environ['SIGIL_HASH'], os.environ['SIGIL_REALM']))
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
SIGIL_NAME="$NAME" SIGIL_DESCRIPTION="$DESCRIPTION" SIGIL_VERSION="$VERSION_NAME" SIGIL_BRANCH="$BRANCH" \
SIGIL_DIRTY="$DIRTY" SIGIL_BUILT="$BUILT" SIGIL_REPO="$REPO" SIGIL_COMMIT_URL="$COMMIT_URL" \
SIGIL_DESCRIBE="$DESCRIBE" python3 -c "
import json, os, sys
e = os.environ
sys.path.insert(0, e['SIGIL_PY'])
from realm_sigil import parse_describe
data = {
    'name': e['SIGIL_NAME'],
    'description': e['SIGIL_DESCRIPTION'],
    'version': e['SIGIL_VERSION'],
    'hash': e['SIGIL_HASH'],
    'branch': e['SIGIL_BRANCH'],
    'dirty': e['SIGIL_DIRTY'] == 'true',
    'built': e['SIGIL_BUILT'],
    'realm': e['SIGIL_REALM'],
    'repo': e['SIGIL_REPO'],
    'commit_url': e['SIGIL_COMMIT_URL'],
}
data['semver'], data['build'] = parse_describe(e['SIGIL_DESCRIBE'], data['dirty'])
with open('version.json', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\\n')
"

echo -e "  ${DIM}✓ version.json written${RESET}"

# Inject/update meta tag in HTML if specified
if [[ -n "$HTML" && -f "$HTML" ]]; then
  META_CONTENT=$(python3 -c "
import json
with open('version.json') as f:
    d = json.load(f)
# JSON in a single-quoted attribute: & and ' must be entities, or a description like JP's page ends the
# attribute early (the browser decodes them back, so content= is still the exact JSON)
print(json.dumps(d).replace('&', '&amp;').replace(\"'\", '&#39;'))
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

