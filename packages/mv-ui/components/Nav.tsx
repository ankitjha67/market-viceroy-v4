"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Nav.module.css";

const LINKS: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/", label: "Live Dashboard" },
  { href: "/agents", label: "Agent Room" },
  { href: "/strategies", label: "Strategy Lab" },
  { href: "/postmortem", label: "Post-Mortem Room" },
  { href: "/arbitrage", label: "Arbitrage Monitor" },
  { href: "/risk", label: "Risk Console" },
  { href: "/journal", label: "Journal Explorer" },
  { href: "/health", label: "Source Health" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Primary">
      <div className={styles.brand}>
        <Monogram />
        <div>
          <div className={styles.title}>Market Viceroy</div>
          <div className={styles.sub}>Command Deck</div>
        </div>
      </div>
      <ul className={styles.list}>
        {LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                className={active ? `${styles.link} ${styles.active}` : styles.link}
                aria-current={active ? "page" : undefined}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className={styles.footer}>Paper mode</div>
    </nav>
  );
}

/* A hand-drawn monogram (a sightline through a portcullis) — not an icon-font glyph. */
function Monogram() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true" className={styles.mark}>
      <rect x="1.5" y="1.5" width="23" height="23" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M6 19 L13 7 L20 19" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <line x1="6" y1="19" x2="20" y2="19" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
