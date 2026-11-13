"""semver + build beside the sigil name (issue #3), held to one contract in every binding.

tools/describe-vectors.json is the truth for parse_describe (python), parseDescribe (js) and ParseDescribe (go,
in go/sigil_test.go). Then, against a REAL temp git repository, every emitter that reads git is run end to end:
python's handler, js's handler (live git, and the .git_info that deploy-banner.sh bakes), and static/build.sh.

js needs node: skipped locally without it, a failure under CI (GitHub sets CI=true) so it cannot silently not run.

Run: python3 -m unittest discover -s python/tests
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))

from realm_sigil import parse_describe, version_dict  # noqa: E402
from realm_sigil import handler  # noqa: E402

with open(os.path.join(ROOT, "tools", "describe-vectors.json")) as _f:
    VECTORS = json.load(_f)["cases"]
NODE = shutil.which("node")
GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")


def need_node(test):
    if NODE:
        return
    if os.environ.get("CI"):
        test.fail("no node under CI: the js half of this contract would silently not run")
    test.skipTest("node not installed")


class Vectors(unittest.TestCase):
    def test_enough_vectors(self):
        self.assertGreaterEqual(len(VECTORS), 30)

    def test_python(self):
        for c in VECTORS:
            with self.subTest(describe=c["describe"], dirty=c["dirty"]):
                self.assertEqual(parse_describe(c["describe"], c["dirty"]), (c["semver"], c["build"]))

    def test_js(self):
        need_node(self)
        script = ("const {parseDescribe}=require(process.argv[1]);"
                  "const v=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                  "process.stdout.write(JSON.stringify(v.map(c=>parseDescribe(c.describe,c.dirty))));")
        r = subprocess.run([NODE, "-e", script, os.path.join(ROOT, "js", "index.js")],
                           input=json.dumps(VECTORS), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(r.stdout)
        bad = [(c["describe"], c["dirty"], g) for c, g in zip(VECTORS, got) if g != [c["semver"], c["build"]]]
        self.assertFalse(bad)

    def test_version_dict_always_has_both_fields(self):
        self.assertEqual({k: version_dict("n", "d", "fantasy", "")[k] for k in ("semver", "build")},
                         {"semver": "", "build": ""})
        d = version_dict("n", "d", "fantasy", "", describe="v2.0.0-0-gabc1234", dirty=False)
        self.assertEqual((d["semver"], d["build"]), ("v2.0.0", "v2.0.0"))


class RealRepo(unittest.TestCase):
    """Each emitter against a real repository, through no tag, on a tag, past it, dirty, and hostile tags."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="sigil-describe-")
        self.git("init", "-q", "-b", "main")
        self.write("a.txt", "1")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "one")
        # this test's own outputs must not make the tree dirty (python counts untracked files as dirty)
        with open(os.path.join(self.d, ".git", "info", "exclude"), "a") as f:
            f.write("site/\n.git_info\n")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                              cwd=self.d, env=GIT_ENV, capture_output=True, text=True, check=True).stdout.strip()

    def write(self, name, text):
        with open(os.path.join(self.d, name), "w") as f:
            f.write(text)

    def short(self):
        # describe abbreviates on its own; read the hex it actually used rather than assuming rev-parse's length
        return self.git("describe", "--tags", "--match", "v[0-9]*", "--long").rsplit("-g", 1)[1]

    def python_fields(self):
        handler._reset_git_cache()
        v = handler.make_version_response("n", "d", "fantasy", "", project_dir=self.d)
        return v["semver"], v["build"]

    def js_fields(self, baked=False):
        need_node(self)
        script = ("const h=require(process.argv[1]);"
                  "const v=h.makeVersionResponse('n','d','fantasy','',process.argv[2]);"
                  "process.stdout.write(JSON.stringify([v.semver,v.build,h.gitInfo(process.argv[2]).describe]));")
        r = subprocess.run([NODE, "-e", script, os.path.join(ROOT, "js", "handler.js"), self.d],
                           capture_output=True, text=True, timeout=60, env=GIT_ENV)
        self.assertEqual(r.returncode, 0, r.stderr)
        return tuple(json.loads(r.stdout))

    def baked_git_info(self):
        out = os.path.join(self.d, ".git_info")
        subprocess.run(["bash", "-c", 'source "$1" && realm_sigil_git_info "$2"', "_",
                        os.path.join(ROOT, "deploy-banner.sh"), out], cwd=self.d, env=GIT_ENV, check=True,
                       capture_output=True, timeout=60)
        with open(out) as f:
            raw = f.read()
        return json.loads(raw)  # must stay valid JSON whatever the tag is called

    def static_fields(self):
        site = os.path.join(self.d, "site")
        os.makedirs(site, exist_ok=True)
        r = subprocess.run(["bash", os.path.join(ROOT, "static", "build.sh"), "--name", "n", "--description", "d",
                            "--realm", "fantasy", "--repo", "https://example.invalid/r", "--dir", site],
                           cwd=self.d, env=GIT_ENV, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(site, "version.json")) as f:
            v = json.load(f)
        return v["semver"], v["build"]

    def assert_all(self, semver, build):
        self.assertEqual(self.python_fields(), (semver, build), "python handler")
        self.assertEqual(self.static_fields(), (semver, build), "static/build.sh")
        if NODE or os.environ.get("CI"):
            self.assertEqual(self.js_fields()[:2], (semver, build), "js handler (live git)")

    def test_no_version_tag(self):
        self.git("tag", "release-9")  # not v<digit>: ignored by --match
        self.assert_all("", "")
        self.assertEqual(self.baked_git_info()["describe"], "")

    def test_on_a_clean_tag_then_past_it_then_dirty(self):
        self.git("tag", "v1.2.3")
        self.assert_all("v1.2.3", "v1.2.3")
        self.write("a.txt", "2")
        self.git("commit", "-q", "-am", "two")
        self.git("tag", "release-10")  # a newer non-version tag does not displace v1.2.3
        self.assert_all("v1.2.3", "v1.2.3+%s" % self.short())
        self.write("a.txt", "3")  # tracked change, uncommitted
        self.assert_all("v1.2.3", "v1.2.3+%s.dirty" % self.short())

    def test_baked_git_info_is_read_by_js(self):
        self.git("tag", "v0.4.0-rc.2")
        info = self.baked_git_info()
        self.assertEqual(info["describe"], "v0.4.0-rc.2-0-g%s" % self.short())
        if NODE or os.environ.get("CI"):
            # .git_info wins over live git in js: change the repo after baking and the baked value still answers
            self.write("a.txt", "x")
            self.git("commit", "-q", "-am", "after bake")
            self.assertEqual(self.js_fields(), ("v0.4.0-rc.2", "v0.4.0-rc.2", info["describe"]))

    def test_hostile_tag_and_branch_names_keep_git_info_valid_json(self):
        # git accepts a double quote in both (it refuses a backslash); the old heredoc JSON broke on either
        self.git("tag", 'v9.9.9"x')
        self.git("checkout", "-q", "-b", 'feature"x')
        info = self.baked_git_info()  # json.loads inside: a raw quote would fail here
        self.assertEqual(info["branch"], 'feature"x')
        self.assertTrue(info["describe"].startswith('v9.9.9"x-0-g'), info)  # recorded faithfully...
        self.assertEqual(parse_describe(info["describe"]), ("", ""))  # ...and refused as semver
        self.assertEqual(self.python_fields(), ("", ""))
        self.assertEqual(self.static_fields(), ("", ""))

    def test_untracked_and_staged_changes_are_dirty_in_every_emitter(self):
        self.git("tag", "v1.2.3")
        self.write("new.txt", "untracked")
        want = ("v1.2.3", "v1.2.3+%s.dirty" % self.short())
        self.assert_all(*want)
        self.assertTrue(self.baked_git_info()["dirty"])
        os.remove(os.path.join(self.d, "new.txt"))
        self.write("a.txt", "staged")
        self.git("add", "a.txt")
        self.assert_all(*want)
        self.assertTrue(self.baked_git_info()["dirty"])

    def test_a_newer_tag_that_only_looks_like_a_version_does_not_displace_one(self):
        self.git("tag", "v1.2.3")
        self.write("a.txt", "2")
        self.git("commit", "-q", "-am", "two")
        self.git("tag", "v9-beta")  # not v*.*.*: the glob skips it rather than letting it blank the fields
        self.assert_all("v1.2.3", "v1.2.3+%s" % self.short())

    def test_js_asks_git_when_an_older_git_info_has_no_describe(self):
        need_node(self)
        self.git("tag", "v3.0.0")
        info = self.baked_git_info()
        del info["describe"]  # a .git_info baked before issue #3
        with open(os.path.join(self.d, ".git_info"), "w") as f:
            json.dump(info, f)
        self.assertEqual(self.js_fields()[:2], ("v3.0.0", "v3.0.0"))
        # ...but never across commits: baked at this commit, checkout moved on and tagged -> no semver, not v4's
        self.write("a.txt", "moved")
        self.git("commit", "-q", "-am", "moved on")
        self.git("tag", "v4.0.0")
        self.assertEqual(self.js_fields()[:2], ("", ""))

    def test_static_names_like_the_bindings_outside_a_repo(self):
        # build.sh used its own int(hash, 16) with "dev" -> 0; it now calls generate_name (issue #9 contract)
        plain = tempfile.mkdtemp(prefix="sigil-static-")
        self.addCleanup(shutil.rmtree, plain, True)
        r = subprocess.run(["bash", os.path.join(ROOT, "static", "build.sh"), "--name", "n", "--description", "d",
                            "--realm", "forge", "--repo", "https://example.invalid/r", "--dir", plain],
                           env=dict(GIT_ENV, GIT_CEILING_DIRECTORIES=os.path.dirname(plain)),
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(plain, "version.json")) as f:
            v = json.load(f)
        from realm_sigil import generate_name
        self.assertEqual((v["hash"], v["version"], v["semver"]), ("dev", generate_name("dev", "forge"), ""))


if __name__ == "__main__":
    unittest.main()
