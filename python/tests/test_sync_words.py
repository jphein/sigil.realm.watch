"""A partial sync cannot leave bindings behind silently (issue #10).

`./sync-words.sh --only go` after a word edit used to rewrite go/realms.go and print "Done.", leaving
python/js/wordpress on the old words and rust's divergence `#[cfg]` markers saying what they said before the
edit: a stale marker reads exactly like a verified-clean one. Now every run ends with
`tools/audit_corpora.py --require-current` over ALL bindings, and one left behind is exit 3 unless the
caller says `--allow-behind`.

Runs the real sync-words.sh in a temp copy of the repo (it rewrites files). Needs python3 only.

Run: python3 -m unittest discover -s python/tests
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COPY = ["sync-words.sh", "words", "tools", "go/realms.go", "python/realm_sigil/realms.py", "js/realms.js",
        "rust/src/realms.rs", "rust/src/reserved.rs", "wordpress/realm-sigil-version.php"]


class PartialSync(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="sigil-sync-")
        for rel in COPY:
            src, dst = os.path.join(ROOT, rel), os.path.join(self.d, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def run_sync(self, *args):
        return subprocess.run(["bash", os.path.join(self.d, "sync-words.sh"), *args],
                              capture_output=True, text=True, timeout=120)

    def edit_words(self):
        """Swap fantasy's first two adjectives: same word SET, different ORDER, so every name moves."""
        p = os.path.join(self.d, "words", "realms.json")
        with open(p) as f:
            data = json.load(f)
        a = data["fantasy"]["adjectives"]
        a[0], a[1] = a[1], a[0]
        with open(p, "w") as f:  # closed (flushed) before sync-words.sh reads it
            json.dump(data, f, indent=2)
        return a[0]

    def test_clean_partial_sync_passes(self):
        r = self.run_sync("--only", "go")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("every binding current", r.stdout)

    def test_partial_sync_after_edit_fails_and_names_what_is_behind(self):
        first = self.edit_words()
        r = self.run_sync("--only", "go")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        for b in ("js", "python", "rust", "wordpress"):
            self.assertRegex(r.stderr, r"BEHIND\s+%s\s+fantasy=drift" % b)
        self.assertNotRegex(r.stderr, r"BEHIND\s+go\b")
        self.assertNotIn("Done.", r.stdout)
        # the requested binding WAS written (the message says so); only the verdict changed
        with open(os.path.join(self.d, "go", "realms.go")) as f:
            go = f.read()
        self.assertIn('"fantasy": {\n\t\tAdjectives: []string{"%s",' % first, go)

    def test_the_opposite_partial_sync_fails_too(self):
        # the invocation the rust gate was designed for: rust regenerated, go behind
        self.edit_words()
        r = self.run_sync("--only", "rust")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertRegex(r.stderr, r"BEHIND\s+go\s+fantasy=drift")

    def test_allow_behind_is_a_stated_choice(self):
        self.edit_words()
        r = self.run_sync("--only", "go", "--allow-behind")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--allow-behind", r.stderr)
        self.assertRegex(r.stderr, r"BEHIND\s+rust")
        self.assertIn("Done.", r.stdout)

    def test_full_sync_after_edit_converges(self):
        self.edit_words()
        r = self.run_sync("--all")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("every binding current", r.stdout)

    def test_missing_binding_file_is_behind_not_current(self):
        os.remove(os.path.join(self.d, "js", "realms.js"))
        r = subprocess.run(["python3", os.path.join(self.d, "tools", "audit_corpora.py"), "--require-current"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("(file missing)", r.stderr)


if __name__ == "__main__":
    unittest.main()
