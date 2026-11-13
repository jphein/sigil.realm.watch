"""pytest's basetemp (tmp_path, tmp_path_factory) in a per-run cache dir, never /tmp (2026-11-13).

familiar's /tmp is a 512 MB RAM tmpfs; concurrent pytest runs filled it to 100% on 11-13 (264 MB in
/tmp/pytest-of-jp). This root conftest (pytest.ini pins the rootdir here, so it loads however pytest is
started) sets the basetemp to ~/.cache/pytest/sigil.realm.watch/run-<pid>-<epoch> and removes that dir
at the end of the run.
- The caller wins: --basetemp, PYTEST_ADDOPTS=--basetemp=… or an ini addopts are left untouched.
- xdist workers are left alone; the controller's dir is enough.
- PYTEST_BASETEMP_ROOT moves the root (default ~/.cache/pytest); PYTEST_KEEP_BASETEMP=1 keeps the run dir.
python/tests/basetemp_test.py fails if tmp_path is not under that root. CI runs the suite with unittest,
which neither loads this file nor collects that test.
"""
import os
import shutil
import time
from pathlib import Path

import pytest

_BASETEMP_REPO = "sigil.realm.watch"


def _mkdirs_0700(path):
    """Create path and any missing parents with mode 0700 (existing ones are left as they are)."""
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for d in reversed(missing):
        d.mkdir(mode=0o700, exist_ok=True)


@pytest.hookimpl(tryfirst=True)  # before pytest's tmpdir plugin reads option.basetemp in its own pytest_configure
def pytest_configure(config):
    if hasattr(config, "workerinput"):
        return
    if config.option.basetemp:
        config._basetemp_caller = True
        return
    root = Path(os.environ.get("PYTEST_BASETEMP_ROOT") or os.path.expanduser("~/.cache/pytest"))
    parent = root / _BASETEMP_REPO
    _mkdirs_0700(parent)
    run = parent / f"run-{os.getpid()}-{int(time.time())}"
    config.option.basetemp = str(run)
    config._basetemp_run = run


def pytest_unconfigure(config):
    run = getattr(config, "_basetemp_run", None)
    if run is None or os.environ.get("PYTEST_KEEP_BASETEMP") == "1":
        return
    shutil.rmtree(run, ignore_errors=True)  # only the dir this session created
