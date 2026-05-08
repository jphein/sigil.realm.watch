# sigil.realm.watch

Deterministic magical version name generation for JP's projects. One library, three languages (Go, Python, JS), seven themed realms.

## What This Is

A shared versioning library that:
1. Generates magical names from git hashes (same hash → same name, always)
2. Provides a standardized `/api/version` JSON endpoint for all projects
3. Builds `version.json` + meta tags for static sites

## Structure

- `words/realms.json` — canonical word lists (single source of truth)
- `sync-words.sh` — generates `go/realms.go`, `python/realm_sigil/realms.py`, `js/realms.js`
- `go/` — Go module (`github.com/jphein/sigil.realm.watch/go`)
- `python/` — Python package
- `js/` — Node.js/npm package
- `static/build.sh` — version.json + meta tag generator for static sites

## Workflow

1. Edit `words/realms.json` to add words or realms
2. Run `./sync-words.sh` to regenerate language-specific files
3. Never edit `realms.go`, `realms.py`, or `realms.js` directly — they're generated

## Adding to a Project

### Go
```go
http.Handle("/api/version", sigil.Handler("name", "description", "realm", "repo"))
```
Makefile must inject ldflags: Hash, Branch, Dirty, Built.

### Python
```python
from realm_sigil.handler import version_handler
handler = version_handler("name", "description", "realm", "repo")
```

### JS (Next.js / Vercel / Express)
```js
const { nextHandler } = require('sigil.realm.watch/handler');
export default nextHandler('name', 'description', 'realm', 'repo');
```

### Static HTML
```bash
./static/build.sh --name X --description "..." --realm Y --repo URL --html index.html
```

## Realms

| Realm | Projects |
|-------|----------|
| fantasy | realmwatch, realm-portal, realmcoin, os.realm.watch |
| tarot | artcardsv5 |
| oracle | oracle, the-oracle |
| void | dreamspace |
| forge | techempower |
| signal | speech-to-cli, cloud-chat-assistant |
| stellar | opus |

## Testing

- Python: `python3 -c "from python.realm_sigil import generate_name; print(generate_name('abc1234', 'fantasy'))"`
- JS: `node -e "const {generateName} = require('./js'); console.log(generateName('abc1234', 'fantasy'))"`
- Go: `cd go && go test -v ./...` (requires Go installed)

## Cross-Language Consistency

All three implementations must produce identical names for the same hash+realm. The algorithm:
```
seed = parseInt(hash, 16)
adjective = realm.adjectives[seed % len(adjectives)]
noun = realm.nouns[(seed >> 8) % len(nouns)]
name = "{adjective} {noun} · {hash}"
```
