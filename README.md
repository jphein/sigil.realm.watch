# realm-sigil

Deterministic magical version name generation. One library, three languages (Go, Python, JS), seven themed realms.

**Same git hash + realm = same name, every time, in every language.**

```
e4f5a6b  →  "Primal Sigil · e4f5a6b"     (fantasy)
a1b2c3d  →  "Relayed Qubit · a1b2c3d"    (signal)
f0f0f0f  →  "Pulsating Pulsar · f0f0f0f" (stellar)
```

## What It Does

- Generates magical version names from git commit hashes
- Provides a standardized `/api/version` JSON endpoint for all services
- Builds `version.json` + meta tags for static sites
- Ships a React `<Sigil />` component that renders the live build name as a corner badge
- Works identically across Go, Python, and JavaScript

## Quick Start

### Go

```go
import sigil "github.com/jphein/realm-sigil/go"

// One-liner HTTP handler
http.Handle("/api/version", sigil.Handler("myapp", "My Application", "fantasy", "https://github.com/jphein/myapp"))
```

Inject build info via ldflags in your Makefile:

```makefile
LDFLAGS := -X 'github.com/jphein/realm-sigil/go.Hash=$(shell git rev-parse --short HEAD)' \
           -X 'github.com/jphein/realm-sigil/go.Branch=$(shell git rev-parse --abbrev-ref HEAD)' \
           -X 'github.com/jphein/realm-sigil/go.Dirty=$(shell git diff --quiet && echo false || echo true)' \
           -X 'github.com/jphein/realm-sigil/go.Built=$(shell date -u +%Y-%m-%dT%H:%M:%SZ)'

build:
	go build -ldflags "$(LDFLAGS)" -o myapp .
```

### Python

```python
from realm_sigil.handler import version_handler

# Returns (status_code, headers, body_bytes)
handler = version_handler("myapp", "My Application", "fantasy", "https://github.com/jphein/myapp")
```

Or just generate a name:

```python
from realm_sigil import generate_name

generate_name("e4f5a6b", "fantasy")  # → "Primal Sigil · e4f5a6b"
```

### JavaScript (Node.js / Next.js / Express / Vercel)

```js
// Next.js API route
const { nextHandler } = require('realm-sigil/handler');
export default nextHandler('myapp', 'My Application', 'forge', 'https://github.com/jphein/myapp');

// Express
const { expressHandler } = require('realm-sigil/handler');
app.get('/api/version', expressHandler('myapp', 'My Application', 'forge', 'https://github.com/jphein/myapp'));

// Vercel serverless
const { vercelHandler } = require('realm-sigil/handler');
export default vercelHandler('myapp', 'My Application', 'forge', 'https://github.com/jphein/myapp');
```

### Static HTML Sites

```bash
./static/build.sh --name mysite --description "My Site" \
    --realm stellar --repo https://github.com/jphein/mysite \
    --html index.html
```

This generates `version.json` and injects a `<meta name="realm-version">` tag into your HTML.

### React component (visible in-app sigil)

A small badge mounted at the app shell that renders the realm-sigil
name + hash in the corner of every screen. Idle pill, hover-expand
panel, GitHub-commit link.

```tsx
import { Sigil } from "realm-sigil/react";
import "realm-sigil/react/style.css";

export function App() {
  return (
    <>
      <Routes>{/* … */}</Routes>
      <Sigil />
    </>
  );
}
```

The component is shipped as TSX source; `realm-sigil/react/style.css`
is the only CSS subpath the package exports. Most modern bundlers
(Vite, Next.js, CRA, Remix) handle CSS-module compilation
automatically — drop the import in `main.tsx`/`_app.tsx`/equivalent
and the styles wire up.

By default the Sigil fetches `/version.json` (which the static
`build.sh` or your own writer produces). Themed via CSS custom
properties — override `--rs-bg`, `--rs-fg`, `--rs-accent`,
`--rs-serif`, etc. on `:root` to match your project palette.

Props (all optional):

| prop | default | description |
|---|---|---|
| `versionUrl` | `/version.json` | Where to fetch the version JSON. |
| `versionInfo` | — | Pre-fetched object; skips the fetch (useful for SSR). |
| `position` | `"bottom-left"` | Or `"bottom-right"`. Bottom-left is the default to dodge common dev-tools UIs. |
| `glyph` | `"✦"` | Single character or short string before the magic name. |
| `hideHashOnPill` | `false` | Show only the magic name on the resting pill. |

A11y: the closed panel uses `inert`, so its GitHub-commit link is
out of the tab order while collapsed. The pulsing ✦ honors
`prefers-reduced-motion`.

#### Generating `/version.json` in dev too

Most projects only run the version writer at build time, so
`npm run dev` ships a stale or missing `version.json` and the Sigil
either lies or stays empty. Add a `predev` script that runs the
same writer:

```json
{
  "scripts": {
    "predev":  "node scripts/version.mjs",
    "dev":     "vite",
    "prebuild":"node scripts/version.mjs",
    "build":   "vite build"
  }
}
```

`npm run dev` will then write a fresh `version.json` before the dev
server starts. The Sigil's idle pill becomes a useful "you are
currently editing commit X" affordance during local development.

## Version Response

All handlers return the same JSON shape:

```json
{
  "name": "myapp",
  "description": "My Application",
  "version": "Blazing Crown · e4f5a6b",
  "hash": "e4f5a6b",
  "branch": "main",
  "dirty": false,
  "built": "2025-01-15T12:00:00Z",
  "started": "2025-01-15T12:00:05Z",
  "uptime": 3600,
  "realm": "fantasy",
  "runtime": "go1.24.0",
  "os": "linux/amd64",
  "host": "myserver",
  "pid": 12345,
  "repo": "https://github.com/jphein/myapp",
  "commit_url": "https://github.com/jphein/myapp/commit/e4f5a6b"
}
```

Static sites omit server-only fields (`started`, `uptime`, `runtime`, `os`, `host`, `pid`).

## Realms

Each realm has 20 adjectives and 20 nouns, giving 400 unique combinations per realm.

| Realm | Flavor | Example |
|-------|--------|---------|
| `fantasy` | Swords & sorcery | Arcane Sigil, Mythic Beacon |
| `tarot` | Cards & divination | Charmed Pentacle, Moonlit Tower |
| `oracle` | Prophecy & vision | Delphic Mirror, Veiled Omen |
| `void` | Cosmic emptiness | Abyssal Rift, Entropic Lattice |
| `forge` | Metalwork & craft | Molten Crucible, Tempered Anvil |
| `signal` | Radio & comms | Amplified Beacon, Synced Relay |
| `stellar` | Stars & space | Cosmic Nova, Nebular Pulsar |

## Algorithm

All three implementations use the same deterministic algorithm:

```
seed = parseInt(hash, 16)
adjective = realm.adjectives[seed % 20]
noun = realm.nouns[(seed >> 8) % 20]
name = "{adjective} {noun} · {hash}"
```

This guarantees cross-language consistency — the same hash and realm produce the same name in Go, Python, and JavaScript.

## Project Structure

```
words/realms.json          # Canonical word lists (single source of truth)
sync-words.sh              # Generates language-specific files from realms.json
go/
  sigil.go                 # Core library + GenerateName
  handler.go               # HTTP handler
  realms.go                # Generated — do not edit
  sigil_test.go            # Tests
python/realm_sigil/
  __init__.py              # Core library + generate_name
  handler.py               # HTTP handler helpers
  realms.py                # Generated — do not edit
js/
  index.js                 # Core library + generateName
  handler.js               # Express/Next.js/Vercel handlers
  realms.js                # Generated — do not edit
  Sigil.tsx                # React component — visible in-app sigil badge
  Sigil.module.css         # Styles, themed via --rs-* CSS variables
static/
  build.sh                 # version.json + meta tag generator
```

## Development

### Editing Word Lists

1. Edit `words/realms.json`
2. Run `./sync-words.sh` to regenerate `go/realms.go`, `python/realm_sigil/realms.py`, and `js/realms.js`
3. Never edit the generated files directly

### Testing

```bash
# Go
cd go && go test -v ./...

# Python
python3 -c "from python.realm_sigil import generate_name; print(generate_name('abc1234', 'fantasy'))"

# JavaScript
node -e "const {generateName} = require('./js'); console.log(generateName('abc1234', 'fantasy'))"
```

## License

[GPLv3](LICENSE)
