// Package sigil provides deterministic magical version name generation
// and a standardized /api/version endpoint for Go services.
package sigil

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"time"
)

// Build-time variables injected via ldflags.
// Example Makefile:
//
//	LDFLAGS := -X 'github.com/jphein/sigil.realm.watch/go.Hash=$(shell git rev-parse --short HEAD)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Branch=$(shell git rev-parse --abbrev-ref HEAD)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Dirty=$(shell git diff --quiet && echo false || echo true)' \
//	           -X 'github.com/jphein/sigil.realm.watch/go.Built=$(shell date -u +%Y-%m-%dT%H:%M:%SZ)'
var (
	Hash   = "dev"
	Branch = "unknown"
	Dirty  = "false"
	Built  = "unknown"
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
	dirty, _ := strconv.ParseBool(Dirty)

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
