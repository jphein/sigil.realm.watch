"""realm-sigil: Deterministic magical version name generation."""

__version__ = "1.0.0"

from .realms import REALMS


def generate_name(hash: str, realm: str = "fantasy") -> str:
    """Generate a deterministic magical name from a git hash and realm.

    Same hash + realm always produces the same name.
    """
    r = REALMS.get(realm, REALMS["fantasy"])
    seed = _parse_hex(hash)

    adj = r["adjectives"][seed % len(r["adjectives"])]
    noun = r["nouns"][(seed >> 8) % len(r["nouns"])]

    return f"{adj} {noun} · {hash}"


_HEX = {c: int(c, 16) for c in "0123456789abcdefABCDEF"}
_U64 = (1 << 64) - 1


def _parse_hex(s: str) -> int:
    """Tolerant hex parse, identical to Go's `parseHex`, JS `parseHex` and Rust `parse_hex`.

    Hex digits (ASCII 0-9, a-f, A-F) accumulate; every other character is skipped; the
    value wraps at 64 bits like Go's uint64. So the unstamped-build sentinel "dev" is seed
    0xde and "" is seed 0: the two names differ, and no input raises.

    This used to be `int(hash, 16) if hash != "dev" else 0` (issue #9): "dev" got seed 0
    where the other three bindings give 0xde, "" raised ValueError, any other non-hex stamp
    (a branch name, "unknown") raised, and hashes longer than 16 hex chars did not wrap.
    """
    seed = 0
    for c in s or "":
        v = _HEX.get(c)
        if v is not None:
            seed = ((seed << 4) | v) & _U64
    return seed


def version_dict(
    name: str,
    description: str,
    realm: str,
    repo: str,
    *,
    hash: str = "dev",
    branch: str = "unknown",
    dirty: bool = False,
    built: str = "unknown",
    started: str | None = None,
    uptime: int | None = None,
    runtime: str | None = None,
    os_info: str | None = None,
    host: str | None = None,
    pid: int | None = None,
) -> dict:
    """Build a version response dict conforming to the realm-sigil contract."""
    commit_url = f"{repo}/commit/{hash}" if repo and hash != "dev" else ""

    d = {
        "name": name,
        "description": description,
        "version": generate_name(hash, realm),
        "hash": hash,
        "branch": branch,
        "dirty": dirty,
        "built": built,
        "realm": realm,
        "repo": repo,
        "commit_url": commit_url,
    }

    # Optional server-only fields
    if started is not None:
        d["started"] = started
    if uptime is not None:
        d["uptime"] = uptime
    if runtime is not None:
        d["runtime"] = runtime
    if os_info is not None:
        d["os"] = os_info
    if host is not None:
        d["host"] = host
    if pid is not None:
        d["pid"] = pid

    return d
