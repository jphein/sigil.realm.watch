// Package sigil provides deterministic magical version name generation
// and a standardized /api/version endpoint for Go services.
package sigil

import (
	"fmt"
	"os"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// Build-time variables injected via ldflags.
// Example Makefile:
//
//	LDFLAGS := -X 'github.com/jphein/sigil.realm.watch/go.Hash=$(shell git rev-parse --short HEAD)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Branch=$(shell git rev-parse --abbrev-ref HEAD)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Dirty=$(shell test -z "$$(git status --porcelain)" && echo false || echo true)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Built=$(shell date -u +%Y-%m-%dT%H:%M:%SZ)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Describe=$(shell git describe --tags --match "v[0-9]*.[0-9]*.[0-9]*" --long 2>/dev/null)'
//
// Describe is optional: without it (or without a version tag) semver and build are "" (issue #3). Dirty uses
// `git status --porcelain` (staged and untracked changes count), as every other emitter does; `git diff --quiet`
// would call such a tree clean and stamp it with the bare tag.
var (
	Hash     = "dev"
	Branch   = "unknown"
	Dirty    = "false"
	Built    = "unknown"
	Describe = ""
)

var startedAt = time.Now()

// Version holds the full version response for a service.
type Version struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	VersionStr  string `json:"version"`
	Hash        string `json:"hash"`
	Branch      string `json:"branch"`
	Dirty       bool   `json:"dirty"`
	Built       string `json:"built"`
	Started     string `json:"started"`
	Uptime      int64  `json:"uptime"`
	Realm       string `json:"realm"`
	Runtime     string `json:"runtime"`
	OS          string `json:"os"`
	Host        string `json:"host"`
	PID         int    `json:"pid"`
	Repo        string `json:"repo"`
	CommitURL   string `json:"commit_url"`
	Semver      string `json:"semver"` // nearest version tag, "" without one (issue #3)
	Build       string `json:"build"`  // semver on a clean tag, else semver+<hash>[.dirty]; "" without a tag
}

var (
	preID     = `(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)` // semver 2.0: no leading zero in a numeric id
	semverTag = regexp.MustCompile(`^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-` + preID + `(\.` + preID + `)*)?$`)
	distance  = regexp.MustCompile(`^[0-9]+$`)
	gHash     = regexp.MustCompile(`^g([0-9a-f]{4,64})$`) // 64: a SHA-256 repository's full hash
)

// ParseDescribe returns (semver, build) from `git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]*' --long` output (issue #3).
//
// The output is <tag>-<distance>-g<hex>, split at the LAST two '-' (neither the distance nor g<hex> can
// contain one, so a prerelease tag like v1.2.3-rc.1 survives). The tag must be
// v<MAJOR>.<MINOR>.<PATCH>[-<prerelease>] per semver 2.0 (no leading zeros, no '+'); anything else is ("", "").
// build is the semver when HEAD is exactly on the tag and the tree is clean, else <semver>+<hex>[.dirty]:
// semver BUILD METADATA, because describe's own v1.2.3-5-gabc form parses as a PRERELEASE and sorts before
// v1.2.3. The distance is zero iff all its digits are 0 (never parsed as an integer, so it cannot overflow).
// Same contract as Python's parse_describe and JS parseDescribe; tools/describe-vectors.json is the truth.
func ParseDescribe(describe string, dirty bool) (semver, build string) {
	b := strings.LastIndex(describe, "-")
	if b <= 0 {
		return "", ""
	}
	a := strings.LastIndex(describe[:b], "-")
	if a < 0 {
		return "", ""
	}
	tag, dist := describe[:a], describe[a+1:b]
	m := gHash.FindStringSubmatch(describe[b+1:])
	if m == nil || !semverTag.MatchString(tag) || !distance.MatchString(dist) {
		return "", ""
	}
	if strings.Trim(dist, "0") == "" && !dirty {
		return tag, tag
	}
	build = tag + "+" + m[1]
	if dirty {
		build += ".dirty"
	}
	return tag, build
}

// Semver is the running build's nearest version tag, from the Describe ldflag; "" without one.
func Semver() string {
	s, _ := ParseDescribe(Describe, parseDirty())
	return s
}

// Build is the running build's semver-compatible identity, e.g. "v1.2.3" or "v1.2.3+abc1234.dirty"; "" without a tag.
func Build() string {
	_, b := ParseDescribe(Describe, parseDirty())
	return b
}

func parseDirty() bool {
	d, _ := strconv.ParseBool(Dirty)
	return d
}

// GenerateName produces a deterministic magical name from a git hash and realm.
// Same hash + realm always produces the same name.
func GenerateName(hash, realm string) string {
	r, ok := Realms[realm]
	if !ok {
		r = Realms["fantasy"]
	}

	seed := parseHex(hash)
	adj := r.Adjectives[seed%uint64(len(r.Adjectives))]
	noun := r.Nouns[(seed>>8)%uint64(len(r.Nouns))]

	return fmt.Sprintf("%s %s · %s", adj, noun, hash)
}

// NewVersion creates a fully populated Version struct for the running service.
func NewVersion(name, description, realm, repo string) Version {
	hostname, _ := os.Hostname()
	dirty := parseDirty()
	semver, build := ParseDescribe(Describe, dirty)

	commitURL := ""
	if repo != "" && Hash != "dev" {
		commitURL = repo + "/commit/" + Hash
	}

	return Version{
		Name:        name,
		Description: description,
		VersionStr:  GenerateName(Hash, realm),
		Hash:        Hash,
		Branch:      Branch,
		Dirty:       dirty,
		Built:       Built,
		Started:     startedAt.UTC().Format(time.RFC3339),
		Uptime:      int64(time.Since(startedAt).Seconds()),
		Realm:       realm,
		Runtime:     runtime.Version(),
		OS:          runtime.GOOS + "/" + runtime.GOARCH,
		Host:        hostname,
		PID:         os.Getpid(),
		Repo:        repo,
		CommitURL:   commitURL,
		Semver:      semver,
		Build:       build,
	}
}

func parseHex(s string) uint64 {
	// Parse up to 7 hex chars
	var result uint64
	for _, c := range s {
		var v uint64
		switch {
		case c >= '0' && c <= '9':
			v = uint64(c - '0')
		case c >= 'a' && c <= 'f':
			v = uint64(c-'a') + 10
		case c >= 'A' && c <= 'F':
			v = uint64(c-'A') + 10
		default:
			continue
		}
		result = result*16 + v
	}
	return result
}
