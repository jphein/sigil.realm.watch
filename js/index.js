/**
 * realm-sigil: Deterministic magical version name generation.
 *
 * Usage:
 *   const { generateName, versionObject } = require('realm-sigil');
 *   generateName('e4f5a6b', 'fantasy') // → "Blazing Crown · e4f5a6b"
 */

const { REALMS } = require('./realms');

/**
 * Generate a deterministic magical name from a git hash and realm.
 * Same hash + realm always produces the same name.
 */
function generateName(hash, realm = 'fantasy') {
  const r = REALMS[realm] || REALMS.fantasy;
  const seed = parseHex(hash);

  const adj = r.adjectives[Number(seed % BigInt(r.adjectives.length))];
  const noun = r.nouns[Number((seed >> 8n) % BigInt(r.nouns.length))];

  return `${adj} ${noun} · ${hash}`;
}

/**
 * Parse a hex string to a 64-bit seed, matching Go's `parseHex` exactly: accumulate hex
 * digits, skip anything else, wrap at 64 bits.
 *
 * ⚠️ This used to be `parseInt(hash, 16) || 0` followed by `seed >> 8`, and that was BROKEN for
 * any seed >= 2^31. JS `>>` coerces its operand to **int32**, so the shift went negative, and
 * JS `%` keeps the dividend's sign — yielding a negative array index and an `undefined` noun.
 * `generateName('9e3779b1', 'fantasy')` returned literally "Blazing undefined · 9e3779b1".
 *
 * It stayed invisible because sigil's own use is 7-hex-char git hashes (< 2^28), where the sign
 * bit is never set. It bites any consumer seeding with a full u32 — which is exactly what smol
 * does (`id * 2654435761`), and 8 of 10 of its node ids produced `undefined` here while Go,
 * Python and the Rust binding all agreed on the right answer.
 *
 * BigInt rather than `>>> 8`: an unsigned shift would fix the sign bug but still truncate to 32
 * bits, so a hash longer than 8 hex chars would diverge from Go's uint64. `BigInt.asUintN(64,…)`
 * reproduces Go's overflow semantics precisely.
 *
 * (Note Python's `int(hash, 16)` instead THROWS on a non-hex character — it special-cases only
 * the literal "dev" — so Go/Rust/JS are tolerant here and Python is not. Pre-existing, and out
 * of scope for this fix, but it means "all four agree" holds for hex input, not for garbage.)
 */
function parseHex(s) {
  let result = 0n;
  for (const c of String(s ?? '')) {
    let v;
    if (c >= '0' && c <= '9') v = BigInt(c.charCodeAt(0) - 48);
    else if (c >= 'a' && c <= 'f') v = BigInt(c.charCodeAt(0) - 87);
    else if (c >= 'A' && c <= 'F') v = BigInt(c.charCodeAt(0) - 55);
    else continue;
    result = BigInt.asUintN(64, result * 16n + v);
  }
  return result;
}

/**
 * Build a version response object conforming to the realm-sigil contract.
 * For static/build-time use. Server handlers add runtime fields automatically.
 */
function versionObject(opts) {
  const {
    name, description, realm, repo,
    hash = 'dev', branch = 'unknown', dirty = false, built = 'unknown',
    started, uptime, runtime, os, host, pid,
  } = opts;

  const commitUrl = repo && hash !== 'dev' ? `${repo}/commit/${hash}` : '';

  const obj = {
    name,
    description,
    version: generateName(hash, realm),
    hash,
    branch,
    dirty,
    built,
    realm,
    repo,
    commit_url: commitUrl,
  };

  // Optional server-only fields
  if (started !== undefined) obj.started = started;
  if (uptime !== undefined) obj.uptime = uptime;
  if (runtime !== undefined) obj.runtime = runtime;
  if (os !== undefined) obj.os = os;
  if (host !== undefined) obj.host = host;
  if (pid !== undefined) obj.pid = pid;

  return obj;
}

module.exports = { generateName, versionObject, REALMS };
