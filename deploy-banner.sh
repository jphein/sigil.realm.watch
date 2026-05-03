#!/usr/bin/env bash
# realm-sigil deploy helpers — source this in any project's deploy script
#
# Usage:
#   source ~/Projects/realm-sigil/deploy-banner.sh
#
#   # At the TOP of deploy (before rsync):
#   realm_sigil_git_info .git_info
#   realm_sigil_pre "signal"                    # prints bold sigil name
#
#   # ... rsync, restart, etc ...
#
#   # At the END of deploy (after service is up):
#   realm_sigil_post "http://host:port/api/version"  # prints live version

REALM_SIGIL_PYTHON="$HOME/Projects/realm-sigil/python"

# Realm → ANSI color mapping (matches Treasure Hoard palette)
_realm_color() {
    case "$1" in
        fantasy)  echo "32" ;;  # green (emerald)
        tarot)    echo "35" ;;  # magenta (amethyst)
        oracle)   echo "35" ;;  # magenta (amethyst)
        void)     echo "37" ;;  # white (dim)
        forge)    echo "33" ;;  # yellow (gold)
        signal)   echo "36" ;;  # cyan (sapphire)
        stellar)  echo "35" ;;  # magenta (pink)
        *)        echo "33" ;;  # yellow default
    esac
}

# Generate .git_info JSON for projects that don't have git on the server
realm_sigil_git_info() {
    local outfile="${1:-.git_info}"
    local HASH BRANCH DIRTY BUILT
    HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "dev")
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    DIRTY=$(git diff --quiet 2>/dev/null && echo "false" || echo "true")
    BUILT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    cat > "$outfile" << EOF
{"hash":"$HASH","branch":"$BRANCH","dirty":$DIRTY,"built":"$BUILT"}
EOF
}

# Pre-deploy banner: bold gold sigil name from local git state
# Args: realm (e.g. "signal", "fantasy", "forge")
realm_sigil_pre() {
    local realm="${1:-fantasy}"
    local git_info="${2:-.git_info}"
    if [ ! -f "$git_info" ]; then
        realm_sigil_git_info "$git_info"
    fi
    local SIGIL
    SIGIL=$(python3 -c "
import sys; sys.path.insert(0, '$REALM_SIGIL_PYTHON')
import json; from realm_sigil import generate_name
gi = json.load(open('$git_info'))
dirty = ' (dirty)' if gi['dirty'] else ''
print(f'{generate_name(gi[\"hash\"], \"$realm\")}{dirty}')
" 2>/dev/null || echo "?")
    local color=$(_realm_color "$realm")
    echo -e "\033[1;${color}m✦ $SIGIL\033[0m"
}

# Post-deploy banner: fetch live version from running service
# Args: version_url (e.g. "http://10.0.6.138:8080/api/version")
realm_sigil_post() {
    local version_url="$1"
    if [ -z "$version_url" ]; then return; fi

    local VERSION
    VERSION=$(curl -s --connect-timeout 3 "$version_url" 2>/dev/null) || return 0

    local VER_NAME VER_HASH VER_DIRTY VER_REALM
    VER_NAME=$(echo "$VERSION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null)
    VER_HASH=$(echo "$VERSION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('hash','?'))" 2>/dev/null)
    VER_DIRTY=$(echo "$VERSION" | python3 -c "import sys,json; d=json.load(sys.stdin); print('(dirty)' if d.get('dirty') else '')" 2>/dev/null)
    VER_REALM=$(echo "$VERSION" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('realm','?'))" 2>/dev/null)

    local color=$(_realm_color "$VER_REALM")
    echo ""
    echo -e "  \033[1;${color}m✦ $VER_NAME $VER_DIRTY\033[0m"
    echo -e "    \033[2mhash: $VER_HASH · realm: $VER_REALM\033[0m"
}

# Backwards compat alias
realm_sigil_banner() { realm_sigil_post "$@"; }
