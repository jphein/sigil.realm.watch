# sigil.realm.watch

Deterministic magical version name generation for JP's projects. One library, three languages (Go, Python, JS), seven themed realms.

## What This Is

A shared versioning library that:
1. Generates magical names from git hashes (same hash → same name, always)
2. Provides a standardized `/api/version` JSON endpoint for all projects
3. Builds `version.json` + meta tags for static sites

## Structure

- `words/realms.json` — canonical word lists (single source of truth)
- `sync-words.sh` — generates `go/realms.go`, `python/realm_sigil/realms.py`, `js/realms.js`, `rust/src/realms.rs`, and the marked corpus block in `wordpress/realm-sigil-version.php` (`--all`, or `--only <langs>`; an unknown target is an error). Every run then checks ALL five against `words/realms.json` (`tools/audit_corpora.py --require-current`) and exits 3 if one is behind, because a partial sync leaves rust's divergence markers stale; `--allow-behind` makes a deliberate partial sync explicit (#10). `tools/audit_corpora.py` checks all five; `python/tests/test_wordpress_parity.py` runs the PHP against python (`SIGIL_PHP="docker run --rm -i php:8.3-cli php"` where php is not installed)
- `go/` — Go module (`github.com/jphein/sigil.realm.watch/go`)
- `python/` — Python package
- `js/` — Node.js/npm package
- `static/build.sh` — version.json + meta tag generator for static sites

## Workflow

1. Edit `words/realms.json` to add words or realms
2. Run `./sync-words.sh` to regenerate language-specific files
3. Never edit `realms.go`, `realms.py`, `realms.js`, `realms.rs` or the PHP corpus block directly — they're generated

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

## Semver beside the sigil name (issue #3)

Every `/api/version` response (go, python, js, static `version.json`; wordpress as `""`) carries two more fields,
always present:

- `semver` — the nearest version tag, e.g. `v1.2.3` or `v1.2.3-rc.1`; `""` when the project has none.
- `build` — `semver` when HEAD is exactly on that tag and the tree is clean, otherwise `<semver>+<hash>[.dirty]`
  (e.g. `v1.2.3+abc1234.dirty`); `""` without a tag.

Both come from ONE input, `git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]*' --long` (`<tag>-<distance>-g<hex>`), parsed
identically by `parse_describe` (python), `parseDescribe` (js) and `ParseDescribe` (go): split at the last two `-`;
the tag must be `v<MAJOR>.<MINOR>.<PATCH>[-<prerelease>]` per semver 2.0 (no leading zero in any numeric identifier,
prerelease ones included; no `+`), else both are `""`.
`build` is semver **build metadata** on purpose: describe's own `v1.2.3-5-gabc` shape parses as a *prerelease* and
sorts before `v1.2.3`. `tools/describe-vectors.json` is the shared truth (go test + `python/tests/test_describe.py`
for python and js). Go gets the input from the `Describe` ldflag (see `go/sigil.go`); `.git_info` (deploy-banner.sh)
carries it as `"describe"` for hosts deployed without `.git` (js asks live git when an older `.git_info` lacks it).
The glob skips tags that only look like versions (`v9-beta`); a tag that matches it but is not semver (`v1.2.3.4`)
gives `""` rather than a wrong answer. `dirty` is `git status --porcelain` (staged and untracked count) in every
emitter: python, js, `.git_info` and `static/build.sh`, which also names builds via `realm_sigil.generate_name` now.

## Cross-Language Consistency

All bindings (Go, Python, JS, Rust) must produce identical names for the same hash+realm, for ANY input string, not just hex. `python/tests/test_generate_name.py` checks Python against JS. The algorithm:
```
seed = tolerant hex parse of hash: hex digits accumulate, anything else is skipped, wraps at 64 bits
       ("dev" → 0xde, "" → 0; never raises — issue #9)
adjective = realm.adjectives[seed % len(adjectives)]
noun = realm.nouns[(seed >> 8) % len(nouns)]
name = "{adjective} {noun} · {hash}"
```
