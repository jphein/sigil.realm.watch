#!/usr/bin/env python3
"""Assert every language binding's word list still matches `words/realms.json`.

WHY A COMPARISON AND NOT A CONVENTION
`sync-words.sh` writes the bindings; nothing has ever checked them afterwards. That asymmetry
is how the 2026-07-28 audit found six consumer projects on a three-months-frozen vocabulary:
`words/realms.json` was cut over to lexicon-derived words on 2026-05-07 (be59e52), the Rust
binding followed, and go/python/js/wordpress did not. Nobody noticed because nothing could.
A hand-copied table cannot be checked; a comparison can. This is the comparison.

WHY ORDER, NOT JUST MEMBERSHIP
`generate_name` indexes with `seed % len(list)`. So a corpus can break in three ways, and only
the first is obvious:

  · different WORDS      — the name changes
  · different ORDER      — every name changes, though the word SET is identical
  · different LENGTH     — every name changes, and it is the easiest to introduce by accident

Hence the test is whether each canonical list appears as a CONTIGUOUS, ORDERED subsequence of
the quoted strings in the binding. A set-comparison would call a reordered list healthy while
every published version name silently moved.

WHY A BASELINE INSTEAD OF FAILING TODAY
Four bindings are knowingly behind, mid-migration. A gate that goes red immediately gets
disabled, so the known state is recorded in `tools/corpus-baseline.json` and this fails only on
a CHANGE to that state — in EITHER direction. New drift fails. Fixing a baselined binding also
fails, until the baseline is updated to say so. That is deliberate: the baseline is a claim
about reality that has to be re-asserted, not a mute suppression list. It is the migration debt,
written down where CI keeps it honest.

Usage:
    python3 tools/audit_corpora.py              # gate: compare against the baseline
    python3 tools/audit_corpora.py --report     # human-readable state, always exits 0
    python3 tools/audit_corpora.py --write-baseline
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "words" / "realms.json"
BASELINE = ROOT / "tools" / "corpus-baseline.json"

# Every in-repo binding. Language-agnostic on purpose: we compare quoted string sequences, so
# one extractor covers Go, Python, JS, PHP and Rust without parsing any of them.
BINDINGS = {
    "go":        "go/realms.go",
    "python":    "python/realm_sigil/realms.py",
    "js":        "js/realms.js",
    "wordpress": "wordpress/realm-sigil-version.php",
    "rust":      "rust/src/realms.rs",
}

QUOTED = re.compile(r'"([A-Za-z][A-Za-z\- ]{1,30})"' r"|'([A-Za-z][A-Za-z\- ]{1,30})'")


def quoted_words(text: str) -> list[str]:
    """Quoted strings in file order, single or double quoted."""
    return [a or b for a, b in QUOTED.findall(text)]


def contiguous(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    if not n:
        return False
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def audit() -> dict:
    """{binding: {realm: "ok" | "drift" | "absent"}} against words/realms.json."""
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    state: dict[str, dict[str, str]] = {}
    for name, rel in BINDINGS.items():
        path = ROOT / rel
        if not path.exists():
            state[name] = {"__file__": "missing"}
            continue
        words = quoted_words(path.read_text(encoding="utf-8", errors="replace"))
        present = set(words)
        realms: dict[str, str] = {}
        for realm, fields in reference.items():
            adjectives, nouns = fields["adjectives"], fields["nouns"]
            if contiguous(words, adjectives) and contiguous(words, nouns):
                realms[realm] = "ok"
            else:
                # Distinguish "carries this realm but it differs" from "does not ship it".
                overlap = len(present & set(adjectives)) + len(present & set(nouns))
                realms[realm] = "drift" if overlap >= 12 else "absent"
        state[name] = realms
    return state


def summarise(state: dict) -> str:
    out = []
    for binding, realms in sorted(state.items()):
        if realms.get("__file__") == "missing":
            out.append(f"  {binding:10s} FILE MISSING ({BINDINGS[binding]})")
            continue
        ok = sorted(r for r, v in realms.items() if v == "ok")
        drift = sorted(r for r, v in realms.items() if v == "drift")
        absent = sorted(r for r, v in realms.items() if v == "absent")
        out.append(f"  {binding:10s} ok={len(ok):<2} drift={len(drift):<2} absent={len(absent)}")
        if drift:
            out.append(f"             drift : {', '.join(drift)}")
        if absent:
            out.append(f"             absent: {', '.join(absent)}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true", help="print state, always exit 0")
    ap.add_argument("--write-baseline", action="store_true", help="record the current state")
    args = ap.parse_args()

    state = audit()
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    print(f"reference: words/realms.json ({len(reference)} realms: {', '.join(sorted(reference))})")
    print(summarise(state))

    if args.write_baseline:
        BASELINE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nwrote {BASELINE.relative_to(ROOT)}")
        return 0

    if args.report:
        return 0

    if not BASELINE.exists():
        print(f"\nERROR: no baseline at {BASELINE.relative_to(ROOT)}. "
              "Create it with --write-baseline.", file=sys.stderr)
        return 1

    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    if state == expected:
        print("\nCorpus state matches the baseline.")
        return 0

    # Report every difference in both directions — an improvement is a change too.
    print("\nCORPUS STATE CHANGED vs tools/corpus-baseline.json", file=sys.stderr)
    for binding in sorted(set(state) | set(expected)):
        was, now = expected.get(binding, {}), state.get(binding, {})
        if was == now:
            continue
        for realm in sorted(set(was) | set(now)):
            a, b = was.get(realm, "(absent from baseline)"), now.get(realm, "(no longer checked)")
            if a != b:
                arrow = "FIXED" if b == "ok" else "REGRESSED" if a == "ok" else "changed"
                print(f"  {binding}.{realm}: {a} -> {b}   [{arrow}]", file=sys.stderr)
    print("\nIf this is a real corpus change, re-run sync-words.sh for the affected language.\n"
          "If a binding was deliberately brought up to date, re-record the baseline:\n"
          "    python3 tools/audit_corpora.py --write-baseline\n"
          "The baseline is a claim about reality; update it consciously, never to silence this.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
