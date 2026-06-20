"use client";

import type { ReactNode } from "react";
import styles from "./StatePanel.module.css";

export type LoadState = "loading" | "empty" | "error" | "loaded";

export interface StatePanelProps {
  state: LoadState;
  /** Shown in the error state — names the failed subsystem (PRD degraded-mode banner). */
  error?: string;
  /** Shown in the empty state. */
  emptyMessage?: string;
  children: ReactNode;
}

/**
 * Renders one of the four screen states explicitly (PRD §8.1). Every data
 * surface wraps its content in a StatePanel so Loading / Empty / Error / Loaded
 * are first-class, not afterthoughts.
 */
export function StatePanel({ state, error, emptyMessage, children }: StatePanelProps) {
  if (state === "loading") {
    return (
      <div className={styles.skeleton} role="status" aria-live="polite" aria-busy="true">
        <span className={styles.srOnly}>Loading…</span>
        <div className={styles.bar} />
        <div className={styles.bar} />
        <div className={styles.bar} />
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className={styles.error} role="alert">
        <strong>Degraded.</strong> {error ?? "A subsystem is unavailable."}
      </div>
    );
  }
  if (state === "empty") {
    return <div className={styles.empty}>{emptyMessage ?? "Nothing to show yet."}</div>;
  }
  return <>{children}</>;
}
