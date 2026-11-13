package sigil

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestGenerateName_Deterministic(t *testing.T) {
	name1 := GenerateName("e4f5a6b", "fantasy")
	name2 := GenerateName("e4f5a6b", "fantasy")
	if name1 != name2 {
		t.Errorf("same hash+realm produced different names: %q vs %q", name1, name2)
	}
}

func TestGenerateName_DifferentRealms(t *testing.T) {
	fantasy := GenerateName("e4f5a6b", "fantasy")
	oracle := GenerateName("e4f5a6b", "oracle")
	if fantasy == oracle {
		t.Errorf("different realms produced same name: %q", fantasy)
	}
}

func TestGenerateName_DifferentHashes(t *testing.T) {
	a := GenerateName("aaaaaaa", "fantasy")
	b := GenerateName("bbbbbbb", "fantasy")
	if a == b {
		t.Errorf("different hashes produced same name: %q", a)
	}
}

func TestGenerateName_ContainsHash(t *testing.T) {
	name := GenerateName("abc1234", "void")
	if !contains(name, "abc1234") {
		t.Errorf("name %q does not contain hash", name)
	}
}

func TestGenerateName_UnknownRealmFallsBack(t *testing.T) {
	name := GenerateName("abc1234", "nonexistent")
	if name == "" {
		t.Error("unknown realm returned empty name")
	}
	// Should fall back to fantasy
	fantasy := GenerateName("abc1234", "fantasy")
	if name != fantasy {
		t.Errorf("unknown realm didn't fall back to fantasy: got %q, want %q", name, fantasy)
	}
}

func TestHandler_ReturnsJSON(t *testing.T) {
	Hash = "abc1234"
	Branch = "main"
	Dirty = "false"
	Built = "2026-04-05T12:00:00Z"

	handler := Handler("test-svc", "A test service", "fantasy", "https://github.com/jphein/test")
	req := httptest.NewRequest(http.MethodGet, "/api/version", nil)
	rec := httptest.NewRecorder()

	handler(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "application/json" {
		t.Errorf("Content-Type = %q, want application/json", ct)
	}

	var v Version
	if err := json.NewDecoder(rec.Body).Decode(&v); err != nil {
		t.Fatalf("decode: %v", err)
	}

	if v.Name != "test-svc" {
		t.Errorf("name = %q, want test-svc", v.Name)
	}
	if v.Hash != "abc1234" {
		t.Errorf("hash = %q, want abc1234", v.Hash)
	}
	if v.Branch != "main" {
		t.Errorf("branch = %q, want main", v.Branch)
	}
	if v.Realm != "fantasy" {
		t.Errorf("realm = %q, want fantasy", v.Realm)
	}
	if v.CommitURL != "https://github.com/jphein/test/commit/abc1234" {
		t.Errorf("commit_url = %q", v.CommitURL)
	}
	if v.Uptime < 0 {
		t.Errorf("uptime = %d, want >= 0", v.Uptime)
	}
	if v.PID == 0 {
		t.Error("pid should not be 0")
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsStr(s, substr))
}

func containsStr(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

// TestParseDescribe_Vectors holds Go to the shared semver/build contract (issue #3); python and js are held to the
// same file by python/tests/test_describe.py.
func TestParseDescribe_Vectors(t *testing.T) {
	raw, err := os.ReadFile("../tools/describe-vectors.json")
	if err != nil {
		t.Fatal(err)
	}
	var doc struct {
		Cases []struct {
			Describe string `json:"describe"`
			Dirty    bool   `json:"dirty"`
			Semver   string `json:"semver"`
			Build    string `json:"build"`
		} `json:"cases"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if len(doc.Cases) < 30 {
		t.Fatalf("only %d vectors: the file did not load as expected", len(doc.Cases))
	}
	for _, c := range doc.Cases {
		s, b := ParseDescribe(c.Describe, c.Dirty)
		if s != c.Semver || b != c.Build {
			t.Errorf("ParseDescribe(%q, %v) = (%q, %q), want (%q, %q)", c.Describe, c.Dirty, s, b, c.Semver, c.Build)
		}
	}
}

func TestNewVersion_SemverAndBuild(t *testing.T) {
	oldD, oldDirty := Describe, Dirty
	defer func() { Describe, Dirty = oldD, oldDirty }()

	Describe, Dirty = "v1.4.0-2-gabc1234", "false"
	v := NewVersion("svc", "d", "fantasy", "")
	if v.Semver != "v1.4.0" || v.Build != "v1.4.0+abc1234" || Semver() != "v1.4.0" || Build() != "v1.4.0+abc1234" {
		t.Errorf("tagged: semver=%q build=%q Semver()=%q Build()=%q", v.Semver, v.Build, Semver(), Build())
	}
	out, _ := json.Marshal(v)
	if !strings.Contains(string(out), `"semver":"v1.4.0"`) || !strings.Contains(string(out), `"build":"v1.4.0+abc1234"`) {
		t.Errorf("json lacks semver/build: %s", out)
	}

	Describe = "" // no version tag: both fields present and empty
	v = NewVersion("svc", "d", "fantasy", "")
	out, _ = json.Marshal(v)
	if v.Semver != "" || v.Build != "" || !strings.Contains(string(out), `"semver":""`) {
		t.Errorf("untagged: %s", out)
	}
}
