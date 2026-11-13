"""HTTP handler helpers for Python web servers."""

import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from . import generate_name, version_dict

_start_time = time.time()
_start_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Seconds any one git call may take. A stale index.lock, a network filesystem or a
# credential/gpg prompt must not hang the /api/version request handler (issue #12).
GIT_TIMEOUT = 5

# After a failed probe, serve the unknowns for this long before trying git again, so a
# hanging git costs one request a timeout instead of serializing every request behind it.
GIT_RETRY_AFTER = 30

_UNKNOWN = {"hash": "dev", "branch": "unknown", "dirty": False}

# abs project_dir -> (info, retry_at). retry_at is None for a good probe: it is kept for the
# life of the process. This is a PROCESS-START SNAPSHOT, not live repository status: the code
# a server is running cannot change without a restart, so the commit it was started from is
# the honest answer. A server that hot-reloads code calls _reset_git_cache() when it does.
_git_cache: dict[str, tuple[dict, float | None]] = {}
_dir_locks: dict[str, threading.Lock] = {}
_git_generation = 0  # bumped by _reset_git_cache(); a probe started before a reset is discarded
_git_lock = threading.Lock()  # guards the state above; never held across a git call


def _reset_git_cache() -> None:
    """Forget memoized git info (tests, or a server that hot-reloads its code)."""
    global _git_generation
    with _git_lock:
        _git_cache.clear()
        _git_generation += 1


def _probe_git(cwd: str) -> tuple[dict, bool]:
    """Run the three git probes. Returns (info, complete); incomplete results are retried."""

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, errors="replace", cwd=cwd,
            timeout=GIT_TIMEOUT, stdin=subprocess.DEVNULL,
        )

    try:
        head = run("rev-parse", "--short", "HEAD")
        if head.returncode != 0:
            # Not a repository (an rsync deploy), no commit yet, or a transient read error.
            # Telling those apart means parsing localized stderr; retrying after the cooldown
            # costs a non-repo deploy one fork per GIT_RETRY_AFTER instead.
            return dict(_UNKNOWN), False
        branch = run("rev-parse", "--abbrev-ref", "HEAD")
        # `status --porcelain` sees untracked files; `git diff --quiet` did not.
        status = run("status", "--porcelain", "--untracked-files=normal")
    except (OSError, subprocess.SubprocessError):
        # git missing, cwd gone, or a call timed out.
        return dict(_UNKNOWN), False

    info = {
        "hash": head.stdout.strip() or "dev",
        "branch": branch.stdout.strip() or "unknown",
        "dirty": bool(status.stdout.strip()),
    }
    # A repo whose branch or status probe failed is a transient state (e.g. index.lock):
    # report what we have, but never pin dirty=False for the process lifetime.
    return info, branch.returncode == 0 and status.returncode == 0


def _git_info(project_dir: str | None = None) -> dict:
    """Gather git info for project_dir (default: cwd), memoized per directory."""
    cwd = os.path.abspath(project_dir or os.getcwd())

    def lookup() -> dict | None:
        with _git_lock:
            hit = _git_cache.get(cwd)
        if hit is not None and (hit[1] is None or time.monotonic() < hit[1]):
            return dict(hit[0])
        return None

    found = lookup()
    if found is not None:
        return found

    with _git_lock:
        dir_lock = _dir_locks.setdefault(cwd, threading.Lock())
    with dir_lock:  # one probe per directory at a time; other directories are not blocked
        found = lookup()  # another thread may have probed while we waited
        if found is not None:
            return found
        with _git_lock:
            generation = _git_generation
        info, complete = _probe_git(cwd)
        retry_at = None if complete else time.monotonic() + GIT_RETRY_AFTER
        with _git_lock:
            if generation == _git_generation:  # no reset happened while git ran
                _git_cache[cwd] = (info, retry_at)
        return dict(info)


def make_version_response(
    name: str,
    description: str,
    realm: str,
    repo: str,
    project_dir: str | None = None,
) -> dict:
    """Build a complete version response with live system info."""
    git = _git_info(project_dir)

    return version_dict(
        name=name,
        description=description,
        realm=realm,
        repo=repo,
        hash=git["hash"],
        branch=git["branch"],
        dirty=git["dirty"],
        built=_start_iso,  # For Python, built ≈ started (no compilation)
        started=_start_iso,
        uptime=int(time.time() - _start_time),
        runtime=f"python{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        os_info=f"{sys.platform}/{platform.machine()}",
        host=socket.gethostname(),
        pid=os.getpid(),
    )


def version_handler(
    name: str,
    description: str,
    realm: str,
    repo: str,
    project_dir: str | None = None,
):
    """Return a handler function suitable for Python HTTP servers.

    Works with http.server.BaseHTTPRequestHandler-style servers.
    Returns a callable that produces (status_code, headers, body_bytes).
    """
    def handle():
        body = json.dumps(
            make_version_response(name, description, realm, repo, project_dir),
            indent=2,
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        }
        return 200, headers, body

    return handle
