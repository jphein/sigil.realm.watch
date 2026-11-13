"""Tests for realm_sigil.handler._git_info (issue #12).

Run: python3 -m unittest discover -s python/tests
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from realm_sigil import handler  # noqa: E402

GIT = shutil.which("git")


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _ok_run(status_rc=0, status_out=""):
    def run(cmd, **kw):
        if cmd[1] == "status":
            return subprocess.CompletedProcess(cmd, status_rc, stdout=status_out, stderr="")
        out = {"--short": "abc1234\n", "--abbrev-ref": "main\n"}[cmd[2]]
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
    return run


@unittest.skipUnless(GIT, "git not installed")
class GitInfoTests(unittest.TestCase):
    def setUp(self):
        handler._reset_git_cache()
        self.repo = tempfile.mkdtemp(prefix="sigil-handler-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(handler._reset_git_cache)
        _git(self.repo, "init", "-q", "-b", "main")
        with open(os.path.join(self.repo, "a.txt"), "w") as f:
            f.write("a\n")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")

    def test_clean_repo(self):
        info = handler._git_info(self.repo)
        self.assertRegex(info["hash"], r"^[0-9a-f]{7,}$")
        self.assertEqual(info["branch"], "main")
        self.assertFalse(info["dirty"])

    def test_untracked_file_is_dirty(self):
        # `git diff --quiet` misses untracked files; `status --porcelain` sees them.
        with open(os.path.join(self.repo, "new.txt"), "w") as f:
            f.write("x\n")
        self.assertTrue(handler._git_info(self.repo)["dirty"])

    def test_untracked_is_dirty_even_when_config_hides_it(self):
        _git(self.repo, "config", "status.showUntrackedFiles", "no")
        with open(os.path.join(self.repo, "new.txt"), "w") as f:
            f.write("x\n")
        self.assertTrue(handler._git_info(self.repo)["dirty"])

    def test_non_utf8_branch_name_degrades_instead_of_crashing(self):
        subprocess.run([b"git", b"switch", b"-q", b"-c", b"bad-\xff"], cwd=self.repo, check=True)
        info = handler._git_info(self.repo)
        self.assertTrue(info["branch"].startswith("bad-"))

    def test_modified_tracked_file_is_dirty(self):
        with open(os.path.join(self.repo, "a.txt"), "w") as f:
            f.write("changed\n")
        self.assertTrue(handler._git_info(self.repo)["dirty"])

    def test_result_is_memoized_per_project_dir(self):
        first = handler._git_info(self.repo)
        with mock.patch.object(handler.subprocess, "run") as run:
            second = handler._git_info(self.repo)
            run.assert_not_called()
        self.assertEqual(first, second)

    def test_callers_cannot_mutate_the_cache(self):
        handler._git_info(self.repo)["hash"] = "tampered"
        self.assertNotEqual(handler._git_info(self.repo)["hash"], "tampered")

    def test_concurrent_first_calls_fork_git_once(self):
        real_run = subprocess.run
        calls = []

        def counting_run(*a, **kw):
            calls.append(a[0])
            return real_run(*a, **kw)

        with mock.patch.object(handler.subprocess, "run", side_effect=counting_run):
            threads = [threading.Thread(target=handler._git_info, args=(self.repo,)) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(len(calls), 3)  # one probe set, not eight

    def test_not_a_repo_gives_unknowns(self):
        plain = tempfile.mkdtemp(prefix="sigil-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        info = handler._git_info(plain)
        self.assertEqual(info, {"hash": "dev", "branch": "unknown", "dirty": False})


class GitInfoFailureTests(unittest.TestCase):
    def setUp(self):
        handler._reset_git_cache()
        self.addCleanup(handler._reset_git_cache)

    def test_every_git_call_has_a_timeout(self):
        seen = []

        def fake_run(cmd, **kw):
            seen.append(kw.get("timeout"))
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with mock.patch.object(handler.subprocess, "run", side_effect=fake_run):
            handler._git_info("/nonexistent-sigil-test")
        self.assertTrue(seen)
        self.assertTrue(all(t is not None and t > 0 for t in seen), seen)

    def test_timeout_degrades_then_retries_after_cooldown(self):
        def hang(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

        clock = [1000.0]
        with mock.patch.object(handler.time, "monotonic", side_effect=lambda: clock[0]):
            with mock.patch.object(handler.subprocess, "run", side_effect=hang) as run:
                info = handler._git_info("/nonexistent-sigil-test")
                self.assertEqual(info, {"hash": "dev", "branch": "unknown", "dirty": False})
                # Inside the cooldown a hanging git is not asked again.
                handler._git_info("/nonexistent-sigil-test")
                self.assertEqual(run.call_count, 1)

            # A transient hang (stale index.lock) must not pin "dev" for the process lifetime.
            clock[0] += handler.GIT_RETRY_AFTER + 1
            with mock.patch.object(handler.subprocess, "run", side_effect=_ok_run()):
                info = handler._git_info("/nonexistent-sigil-test")
        self.assertEqual(info["hash"], "abc1234")

    def test_failed_status_is_not_pinned_clean(self):
        # rev-parse works, `status` fails (e.g. index.lock): dirty=False must not stick.
        clock = [1000.0]
        with mock.patch.object(handler.time, "monotonic", side_effect=lambda: clock[0]):
            with mock.patch.object(handler.subprocess, "run", side_effect=_ok_run(status_rc=128)):
                handler._git_info("/nonexistent-sigil-test")
            clock[0] += handler.GIT_RETRY_AFTER + 1
            with mock.patch.object(handler.subprocess, "run", side_effect=_ok_run(status_out=" M a\n")):
                self.assertTrue(handler._git_info("/nonexistent-sigil-test")["dirty"])

    def test_head_failure_is_retried_not_pinned(self):
        # HEAD failing is usually "no .git" (an rsync deploy) but can be transient: within the
        # cooldown it costs no fork per request, after it git is asked again.
        not_repo = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal")
        clock = [1000.0]
        with mock.patch.object(handler.time, "monotonic", side_effect=lambda: clock[0]):
            with mock.patch.object(handler.subprocess, "run", side_effect=not_repo) as run:
                handler._git_info("/nonexistent-sigil-test")
                handler._git_info("/nonexistent-sigil-test")
            self.assertEqual(run.call_count, 1)
            clock[0] += handler.GIT_RETRY_AFTER + 1
            with mock.patch.object(handler.subprocess, "run", side_effect=_ok_run()):
                self.assertEqual(handler._git_info("/nonexistent-sigil-test")["hash"], "abc1234")

    def test_reset_during_a_probe_discards_its_result(self):
        entered, release = threading.Event(), threading.Event()
        ok = _ok_run()

        def run(cmd, **kw):
            entered.set()
            release.wait(10)
            return ok(cmd, **kw)

        with mock.patch.object(handler.subprocess, "run", side_effect=run):
            t = threading.Thread(target=handler._git_info, args=("/nonexistent-sigil-test",))
            t.start()
            self.assertTrue(entered.wait(5))
            handler._reset_git_cache()  # e.g. a hot reload while git is still running
            release.set()
            t.join(timeout=10)
        self.assertNotIn(os.path.abspath("/nonexistent-sigil-test"), handler._git_cache)

    def test_a_slow_directory_does_not_block_another(self):
        entered, release = threading.Event(), threading.Event()
        fast_ok = _ok_run()

        def run(cmd, **kw):
            if kw.get("cwd", "").endswith("slow"):
                entered.set()
                release.wait(10)  # a git call hanging on a stale index.lock
            return fast_ok(cmd, **kw)

        result = {}
        with mock.patch.object(handler.subprocess, "run", side_effect=run):
            slow = threading.Thread(target=handler._git_info, args=("/nonexistent-sigil-slow",))
            slow.start()
            self.assertTrue(entered.wait(5))
            fast = threading.Thread(target=lambda: result.update(handler._git_info("/nonexistent-sigil-fast")))
            fast.start()
            fast.join(timeout=3)
            blocked = fast.is_alive()
            release.set()
            slow.join(timeout=10)
            fast.join(timeout=10)
        self.assertFalse(blocked, "a probe of one directory blocked another")
        self.assertEqual(result["hash"], "abc1234")

    def test_missing_git_binary_degrades(self):
        with mock.patch.object(handler.subprocess, "run", side_effect=FileNotFoundError("git")):
            info = handler._git_info("/nonexistent-sigil-test")
        self.assertEqual(info, {"hash": "dev", "branch": "unknown", "dirty": False})


if __name__ == "__main__":
    unittest.main()
