"""pytest's basetemp lives under ~/.cache/pytest/sigil.realm.watch (root conftest.py), never in /tmp (2026-11-13).

Named *_test.py so CI's `unittest discover` (pattern test*.py, no pytest installed) does not import it.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NAME = "sigil.realm.watch"


def _root():
    return Path(os.environ.get("PYTEST_BASETEMP_ROOT") or os.path.expanduser("~/.cache/pytest")).resolve()


def _under(p, base):
    try:
        Path(p).resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


def test_tmp_path_is_under_the_cache_root_not_tmp(tmp_path, request):
    cfg = request.config
    if getattr(cfg, "_basetemp_caller", False):
        if _under(cfg.option.basetemp, "/tmp"):
            pytest.skip("the caller chose a --basetemp under /tmp")
    else:
        assert getattr(cfg, "_basetemp_run", None), "root conftest pytest_configure did not set the basetemp"
        assert _under(tmp_path, _root() / NAME), f"{tmp_path} is not under {_root() / NAME}"
    assert not _under(tmp_path, "/tmp"), f"{tmp_path} is under /tmp"
    assert not _under(tmp_path, tempfile.gettempdir()), f"{tmp_path} is under {tempfile.gettempdir()}"


def _inner(tmp_path, *args, keep=False):
    """Run test 1 in a fresh pytest process with its basetemp root inside tmp_path."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTEST_ADDOPTS", "PYTEST_KEEP_BASETEMP")}
    env["PYTEST_BASETEMP_ROOT"] = str(tmp_path / "root")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if keep:
        env["PYTEST_KEEP_BASETEMP"] = "1"
    node = f"{Path(__file__).resolve().relative_to(REPO)}::test_tmp_path_is_under_the_cache_root_not_tmp"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", node, *args],
                       cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return tmp_path / "root" / NAME


def test_inner_run_leaves_no_run_dir(tmp_path):
    parent = _inner(tmp_path)
    assert parent.is_dir(), "the hook did not create its root"
    assert not list(parent.glob("run-*")), "a run dir was left behind"
    assert oct(parent.stat().st_mode & 0o777) == "0o700"


def test_keep_env_keeps_the_run_dir(tmp_path):
    parent = _inner(tmp_path, keep=True)
    assert len(list(parent.glob("run-*"))) == 1


def test_explicit_basetemp_wins(tmp_path):
    explicit = tmp_path / "explicit"
    parent = _inner(tmp_path, f"--basetemp={explicit}")
    assert explicit.is_dir(), "--basetemp was not used"
    assert not parent.exists(), "the hook created its own dir despite --basetemp"
