"""Parity of python's generate_name with the go/js/rust bindings (issue #9).

The contract, stated for all four bindings: the seed is a tolerant hex parse. Hex digits
(0-9, a-f, A-F) accumulate, every other character is skipped, and the value wraps at 64 bits.
So "dev" is seed 0xde and "" is seed 0: the two "no identity" sentinels must NOT collide.

Run: python3 -m unittest discover -s python/tests
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "python"))

from realm_sigil import REALMS, _parse_hex, generate_name  # noqa: E402

U64 = 2**64


def _domain():
    """The 164-input domain from issue #9: u32/u64 edges, all-f strings, powers of 16,
    real build hashes, deterministic LCG values, plus the non-hex sentinels."""
    out = ["7fffffff", "80000000", "ffffffff", "100000000",
           "6e6d48c00079", "a7af54e4b004", "34b12f9a", "9e3779b1"]
    out += ["f" * n for n in range(1, 17)]
    out += [format(16**k, "x") for k in range(0, 16)]
    x = 0x9E3779B97F4A7C15
    for _ in range(120):
        x = (x * 6364136223846793005 + 1442695040888963407) % U64
        out.append(format(x, "016x")[:12])
    # non-hex input, where python used to raise or special-case
    out += ["dev", "", "DEV", "v1.2.3", "main", "abc1234-dirty", "0x1f", "ab_cd", " ab ",
            "unknown", "f" * 17, "1" + "0" * 16, "ＡＢ", "ß"]
    return out


class ParseHexTests(unittest.TestCase):
    def test_sentinels(self):
        self.assertEqual(_parse_hex("dev"), 0xDE)  # 'd','e' parsed, 'v' skipped
        self.assertEqual(_parse_hex(""), 0)

    def test_dev_and_empty_do_not_collide(self):
        for realm in REALMS:
            self.assertNotEqual(generate_name("dev", realm).split(" · ")[0],
                                generate_name("", realm).split(" · ")[0], realm)

    def test_non_hex_never_raises(self):
        for s in ["", "dev", "main", "v1.2.3", "ab_cd", " ab ", "ＡＢ", "ß"]:
            generate_name(s, "fantasy")

    def test_skips_what_int_would_accept(self):
        # int(s, 16) accepts underscores, surrounding whitespace and fullwidth digits; Go does not.
        self.assertEqual(_parse_hex("ab_cd"), 0xABCD)
        self.assertEqual(_parse_hex("ＡＢ"), 0)
        self.assertEqual(_parse_hex("0x1f"), 0x1F)  # '0' then 'x' skipped then '1f'

    def test_wraps_at_64_bits_like_go_uint64(self):
        self.assertEqual(_parse_hex("1" + "0" * 16), 0)
        self.assertEqual(_parse_hex("f" * 17), U64 - 1)

    def test_hex_unchanged(self):
        for h in ["abc1234", "9e3779b1", "6e6d48c00079", "ffffffffffffffff", "ABCDEF"]:
            self.assertEqual(_parse_hex(h), int(h, 16))


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node not installed: js parity not checked")
class JsParityTests(unittest.TestCase):
    def test_python_matches_js_over_the_domain(self):
        domain = _domain()
        script = (
            "const {generateName}=require(process.argv[1]);"
            "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
            "const out={};for(const r of d.realms){out[r]=d.inputs.map(h=>generateName(h,r));}"
            "process.stdout.write(JSON.stringify(out));"
        )
        res = subprocess.run(
            [NODE, "-e", script, os.path.abspath(os.path.join(ROOT, "js"))],
            input=json.dumps({"realms": list(REALMS), "inputs": domain}),
            capture_output=True, text=True, check=True,
        )
        js = json.loads(res.stdout)
        mismatches = [
            (r, h, js[r][i], generate_name(h, r))
            for r in REALMS for i, h in enumerate(domain)
            if js[r][i] != generate_name(h, r)
        ]
        self.assertEqual(mismatches, [], f"{len(mismatches)} of {len(REALMS) * len(domain)} differ")


if __name__ == "__main__":
    unittest.main()
