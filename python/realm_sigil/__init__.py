"""realm-sigil: Deterministic magical version name generation."""

__version__ = "1.1.0"

import re

from .realms import REALMS

# git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]*' --long, as passed to parse_describe (issue #3). ASCII only, on purpose:
# [0-9] and [a-f], never \d, which matches every Unicode digit.
# The glob keeps tags that only LOOK like versions (v9-beta) from displacing a real one; a tag that matches it and
# is still not semver (v1.2.3.4, v01.2.3) gives "" rather than a wrong answer.
DESCRIBE_ARGS = ("describe", "--tags", "--match", "v[0-9]*.[0-9]*.[0-9]*", "--long")
_PRE_ID = r"(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"  # semver 2.0: a numeric identifier has no leading zero
_SEMVER_TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-%s(\.%s)*)?" % (_PRE_ID, _PRE_ID))
_DISTANCE = re.compile(r"[0-9]+")
_GHASH = re.compile(r"g([0-9a-f]{4,64})")  # 64: a SHA-256 repository's full hash


def parse_describe(describe: str, dirty: bool = False) -> tuple[str, str]:
    """(semver, build) from `git describe --tags --match 'v[0-9]*.[0-9]*.[0-9]*' --long` output (issue #3).

    The output is <tag>-<distance>-g<hex>; it is split at the LAST two '-', because neither the distance nor
    g<hex> can contain one, so a prerelease tag like v1.2.3-rc.1 survives. The tag must be semver-shaped:
    v<MAJOR>.<MINOR>.<PATCH>[-<prerelease>] per semver 2.0 (no leading zeros, numeric prerelease identifiers
    included; no '+'). Anything else is ("", ""): a project
    with no version tag simply has no semver.

    build is the semver itself when HEAD is exactly on the tag and the tree is clean; otherwise it is
    <semver>+<hex>[.dirty], which is semver BUILD METADATA. (describe's own v1.2.3-5-gabc form would parse as
    a PRERELEASE, which sorts BEFORE v1.2.3, the opposite of what it means.) The distance is zero iff all its
    digits are 0, never an integer parse, so a huge one cannot overflow a binding's integer type.

    Same contract in go (ParseDescribe) and js (parseDescribe); tools/describe-vectors.json is the shared truth.
    """
    if not isinstance(describe, str):
        return "", ""
    parts = describe.rsplit("-", 2)
    if len(parts) != 3:
        return "", ""
    tag, distance, ghash = parts
    m = _GHASH.fullmatch(ghash)
    if not (_SEMVER_TAG.fullmatch(tag) and _DISTANCE.fullmatch(distance) and m):
        return "", ""
    if distance.strip("0") == "" and not dirty:
        return tag, tag
    return tag, f"{tag}+{m.group(1)}" + (".dirty" if dirty else "")


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
    describe: str = "",
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
    # Always present, "" when the project has no version tag (issue #3); see parse_describe.
    d["semver"], d["build"] = parse_describe(describe, dirty)

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
