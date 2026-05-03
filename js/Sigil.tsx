// Realm sigil — visible, magical version badge for React apps.
//
//   import { Sigil } from "realm-sigil/react";
//
//   <App />
//   <Sigil />          // reads /version.json, mounts in the corner
//
// Idle state: a tiny gold ✦ + the realm-sigil two-word magic name +
// the short hash. Always rendered, so the deployed build is
// identifiable at a glance.
//
// Hover/tap: the badge expands into a panel listing realm, commit,
// branch, build time, and a link to the GitHub commit. The ✦ pulses
// gently as a "live" cue; the pulse is suppressed under
// `prefers-reduced-motion`. The closed panel uses `inert` so its
// link doesn't catch keyboard tab focus while collapsed.
//
// Theming: every visual property is a CSS custom property prefixed
// `--rs-`. Override them on a parent (or `:root`) to make the sigil
// match your palette without forking the component:
//
//   :root {
//     --rs-bg:        rgba(20,24,52,0.72);
//     --rs-fg:        #f4f1e6;
//     --rs-fg-muted:  rgba(244,241,230,0.62);
//     --rs-accent:    #f3c46b;
//     --rs-stroke:    rgba(244,241,230,0.14);
//     --rs-serif:     "Cormorant Garamond", Georgia, serif;
//     --rs-sans:      "Inter", system-ui, sans-serif;
//   }

import { useEffect, useState } from "react";
import styles from "./Sigil.module.css";

export interface VersionInfo {
  name?: string;
  /** Per realm-sigil contract: "<adjective> <noun> · <hash>". */
  version?: string;
  hash?: string;
  branch?: string;
  dirty?: boolean;
  built?: string;
  realm?: string;
  repo?: string;
  commit_url?: string;
}

export interface SigilProps {
  /**
   * URL to fetch the realm-sigil version JSON from. Defaults to
   * `/version.json` (resolved against the page origin).
   */
  versionUrl?: string;

  /**
   * Pre-fetched version info. If provided the component skips the
   * fetch — useful for SSR or when the version is bundled into the
   * page already.
   */
  versionInfo?: VersionInfo;

  /**
   * Which viewport corner to anchor in. Defaults to `bottom-left`,
   * which avoids common dev-tools placements (Cloudflare/InstantDB/
   * etc.) on the right.
   */
  position?: "bottom-left" | "bottom-right";

  /**
   * Glyph to render in front of the magic name. Defaults to ✦. Pass
   * any single character or short string — emoji, runes, an asterisk.
   */
  glyph?: string;

  /**
   * Hide the short hash on the idle pill (the panel still shows it).
   * The magic name encodes the hash via realm-sigil's algorithm, so
   * the hash is informational rather than essential.
   */
  hideHashOnPill?: boolean;
}

const DEFAULT_VERSION_URL =
  typeof document !== "undefined"
    ? // Resolve against <base href> if present, else origin root.
      new URL("version.json", document.baseURI).toString()
    : "/version.json";

export function Sigil(props: SigilProps = {}) {
  const {
    versionUrl,
    versionInfo: prefetched,
    position = "bottom-left",
    glyph = "✦",
    hideHashOnPill = false,
  } = props;

  const [info, setInfo] = useState<VersionInfo | null>(prefetched ?? null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (prefetched) return;
    let alive = true;
    const url = versionUrl ?? DEFAULT_VERSION_URL;
    fetch(url, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((v: VersionInfo | null) => {
        if (alive) setInfo(v ?? FALLBACK);
      })
      .catch(() => {
        if (alive) setInfo(FALLBACK);
      });
    return () => {
      alive = false;
    };
  }, [versionUrl, prefetched]);

  if (!info) return null;

  const { name: magicName, hash: nameHash } = splitMagicName(info.version);
  const hash = info.hash ?? nameHash ?? "";
  const built = formatBuiltDate(info.built);
  const commitUrl =
    info.commit_url ||
    (info.repo && hash
      ? `${info.repo.replace(/\/+$/, "")}/commit/${hash}`
      : null);

  const ariaLabel = `Build sigil — ${info.version ?? hash}${info.dirty ? " (dirty)" : ""}`;

  return (
    <aside
      className={[
        styles.sigil,
        styles[`pos_${position}`],
        open ? styles.open : "",
      ]
        .filter(Boolean)
        .join(" ")}
      aria-label={ariaLabel}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <button
        type="button"
        className={styles.handle}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className={styles.glyph} aria-hidden="true">
          {glyph}
        </span>
        {magicName && <span className={styles.magicName}>{magicName}</span>}
        {!hideHashOnPill && hash && (
          <>
            <span className={styles.divider} aria-hidden="true">
              ·
            </span>
            <span className={styles.hash}>
              {hash}
              {info.dirty && (
                <span
                  className={styles.dirty}
                  title="working tree was dirty at build time"
                >
                  {" ·"}
                </span>
              )}
            </span>
          </>
        )}
      </button>

      <div
        className={styles.panel}
        role="group"
        aria-hidden={!open}
        // `inert` removes the panel's children (notably the GitHub
        // link) from the tab order and accessibility tree while
        // collapsed — matches the visual hidden state.
        inert={!open}
      >
        {magicName && (
          <p className={styles.line}>
            <span className={styles.label}>name</span>
            <span className={styles.value}>{magicName}</span>
          </p>
        )}
        {info.realm && (
          <p className={styles.line}>
            <span className={styles.label}>realm</span>
            <span className={styles.value}>{info.realm}</span>
          </p>
        )}
        {hash && (
          <p className={styles.line}>
            <span className={styles.label}>commit</span>
            <span className={styles.valueMono}>
              {hash}
              {info.dirty ? " · dirty" : ""}
            </span>
          </p>
        )}
        {info.branch && (
          <p className={styles.line}>
            <span className={styles.label}>branch</span>
            <span className={styles.value}>{info.branch}</span>
          </p>
        )}
        {built && (
          <p className={styles.line}>
            <span className={styles.label}>built</span>
            <span className={styles.value}>{built}</span>
          </p>
        )}
        {commitUrl && (
          <a
            href={commitUrl}
            className={styles.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            view on github ↗
          </a>
        )}
      </div>
    </aside>
  );
}

const FALLBACK: VersionInfo = {
  name: "app",
  version: "Local Sigil · dev",
  hash: "dev",
  branch: "?",
  dirty: true,
  built: new Date().toISOString(),
  realm: "fantasy",
};

function splitMagicName(version: string | undefined): {
  name: string;
  hash: string | null;
} {
  if (!version) return { name: "", hash: null };
  const idx = version.lastIndexOf(" · ");
  if (idx < 0) return { name: version, hash: null };
  return {
    name: version.slice(0, idx),
    hash: version.slice(idx + 3),
  };
}

function formatBuiltDate(iso: string | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const date = d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    const time = d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
    return `${date}, ${time}`;
  } catch {
    return iso;
  }
}
