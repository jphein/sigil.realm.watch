/**
 * HTTP handler helpers for Node.js servers (Express, Next.js, Vercel).
 */

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { versionObject, DESCRIBE_ARGS } = require('./index');

const startTime = Date.now();
const startISO = new Date().toISOString();

/**
 * Read git state from a `.git_info` JSON file if present at `cwd`. This
 * is the artifact `realm_sigil_git_info` (in deploy-banner.sh) bakes
 * before rsync, so production servers can recover hash/branch/dirty
 * even when `.git` is excluded from the deploy.
 */
function readGitInfoFile(cwd) {
  const dir = cwd || process.cwd();
  const file = path.join(dir, '.git_info');
  try {
    const raw = fs.readFileSync(file, 'utf8');
    const parsed = JSON.parse(raw);
    if (typeof parsed.hash !== 'string') return null;
    return {
      hash: parsed.hash,
      branch: typeof parsed.branch === 'string' ? parsed.branch : 'unknown',
      dirty: parsed.dirty === true,
      // undefined (not '') when the file predates "describe" (issue #3), so gitInfo can ask live git instead
      describe: typeof parsed.describe === 'string' ? parsed.describe : undefined,
    };
  } catch {
    return null;
  }
}

// Every git call is synchronous on the request path, so each is time-bounded (as python's GIT_TIMEOUT, issue #12)
// and never reads stdin; a stale index.lock or a credential prompt must not stall the event loop.
const GIT_OPTS = { encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'ignore'] };

function liveDescribe(cwd) {
  try {
    // no version tag is the normal case (git exits 128): describe stays '' (issue #3)
    return execFileSync('git', DESCRIBE_ARGS, { ...GIT_OPTS, cwd }).trim();
  } catch {
    return '';
  }
}

function gitInfo(cwd) {
  // Prefer the baked .git_info file — it's the canonical source on
  // deployed hosts where `.git` was excluded from rsync. Symmetric with
  // the shell helper realm_sigil_git_info that wrote it.
  const baked = readGitInfoFile(cwd);
  if (baked) {
    if (baked.describe === undefined) {
      // An older .git_info (before issue #3): ask live git, but only trust it for the SAME commit. A file baked at
      // commit A beside a checkout at B would otherwise pair A's hash with B's semver/build (xreview 11-13).
      const live = liveDescribe(cwd);
      const hex = live.slice(live.lastIndexOf('-g') + 2);
      const same = live !== '' && hex !== '' && (hex.startsWith(baked.hash) || baked.hash.startsWith(hex));
      baked.describe = same && baked.hash !== 'dev' ? live : '';
    }
    return baked;
  }

  const info = { hash: 'dev', branch: 'unknown', dirty: false, describe: '' };
  try {
    info.hash = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { ...GIT_OPTS, cwd }).trim() || 'dev';
    info.branch = execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { ...GIT_OPTS, cwd }).trim() || 'unknown';
    // `status --porcelain` sees staged and untracked changes; `git diff --quiet` saw neither. Same rule as
    // python's handler, so the two report the same "dirty" and the same build for one tree (xreview 11-13).
    info.dirty = execFileSync('git', ['status', '--porcelain', '--untracked-files=normal'], { ...GIT_OPTS, cwd }).trim() !== '';
    info.describe = liveDescribe(cwd);
  } catch {
    // git not available
  }
  return info;
}

/**
 * Detect the JS runtime label for the version response. Bun, Deno, and
 * Node each expose themselves differently; we pick a stable short string.
 */
function runtimeLabel() {
  if (typeof Bun !== 'undefined' && Bun.version) return `bun${Bun.version}`;
  if (typeof Deno !== 'undefined' && Deno.version && Deno.version.deno) return `deno${Deno.version.deno}`;
  if (typeof process !== 'undefined' && process.version) return `node${process.version}`;
  return 'unknown';
}

/**
 * Build a complete version response with live system info.
 */
function makeVersionResponse(name, description, realm, repo, cwd) {
  const git = gitInfo(cwd);
  return versionObject({
    name,
    description,
    realm,
    repo,
    hash: git.hash,
    branch: git.branch,
    dirty: git.dirty,
    describe: git.describe,
    built: startISO,
    started: startISO,
    uptime: Math.floor((Date.now() - startTime) / 1000),
    runtime: runtimeLabel(),
    os: `${process.platform}/${process.arch}`,
    host: os.hostname(),
    pid: process.pid,
  });
}

/**
 * Next.js API route handler.
 * Usage: export default nextHandler('myapp', 'My app', 'forge', 'https://github.com/jphein/myapp')
 */
function nextHandler(name, description, realm, repo, cwd) {
  return (req, res) => {
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json(makeVersionResponse(name, description, realm, repo, cwd));
  };
}

/**
 * Vercel serverless handler.
 * Usage: export default vercelHandler('myapp', 'My app', 'tarot', 'https://github.com/jphein/myapp')
 */
function vercelHandler(name, description, realm, repo, cwd) {
  return (req, res) => {
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.status(200).json(makeVersionResponse(name, description, realm, repo, cwd));
  };
}

/**
 * Express middleware.
 * Usage: app.get('/api/version', expressHandler('myapp', 'My app', 'forge', 'https://...'))
 */
function expressHandler(name, description, realm, repo, cwd) {
  return (req, res) => {
    res.set('Cache-Control', 'no-cache');
    res.set('Access-Control-Allow-Origin', '*');
    res.json(makeVersionResponse(name, description, realm, repo, cwd));
  };
}

/**
 * Bun.serve-shaped handler. Returns a function that takes a `Request`
 * and returns a `Response` directly — drop into a Bun.serve route:
 *
 *   import { bunHandler } from "realm-sigil/handler";
 *   const versionRoute = bunHandler("familiar", "...", "fantasy", "https://github.com/jphein/familiar.realm.watch");
 *   Bun.serve({
 *     fetch(req) {
 *       const url = new URL(req.url);
 *       if (url.pathname === "/api/version") return versionRoute(req);
 *       ...
 *     }
 *   });
 *
 * Works with any runtime that supplies the global Request/Response Fetch
 * API constructors — Bun, Deno, Cloudflare Workers, modern Node.
 */
function bunHandler(name, description, realm, repo, cwd) {
  return (_req) => {
    const body = JSON.stringify(makeVersionResponse(name, description, realm, repo, cwd));
    return new Response(body, {
      status: 200,
      headers: {
        'content-type': 'application/json',
        'cache-control': 'no-cache',
        'access-control-allow-origin': '*',
      },
    });
  };
}

module.exports = { makeVersionResponse, nextHandler, vercelHandler, expressHandler, bunHandler, gitInfo };
