"use client";

import { useState } from "react";
import { killSwitch, resetKillSwitch } from "@/lib/api";
import { getToken, setToken } from "@/lib/token";
import styles from "./KillSwitch.module.css";

/**
 * The inviolable kill-switch, always reachable at the top of the deck (PRD §8.2).
 * Tripping/resetting is Operator-token-authed and journaled server-side; the UI
 * never re-enables limits itself — it only relays the Operator's authed action.
 */
export function KillSwitch({ tripped }: { tripped: boolean }) {
  const [open, setOpen] = useState(false);
  const [token, setLocalToken] = useState(getToken());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function act() {
    setBusy(true);
    setErr(null);
    try {
      setToken(token);
      if (tripped) {
        await resetKillSwitch(token, "operator");
      } else {
        await killSwitch(token, "operator halt from deck");
      }
      setOpen(false);
    } catch {
      setErr("Action rejected — check the Operator token.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={tripped ? `${styles.button} ${styles.halted}` : styles.button}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={styles.dot} aria-hidden="true" />
        {tripped ? "Trading halted — reset" : "Halt trading"}
      </button>

      {open && (
        <div className={styles.confirm} role="dialog" aria-label="Confirm kill-switch action">
          <label className={styles.label}>
            Operator token
            <input
              type="password"
              className={styles.input}
              value={token}
              onChange={(e) => setLocalToken(e.target.value)}
              autoComplete="off"
            />
          </label>
          {err && <div className={styles.err}>{err}</div>}
          <div className={styles.actions}>
            <button type="button" className={styles.ghost} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="button" className={styles.danger} disabled={busy || !token} onClick={act}>
              {tripped ? "Confirm reset" : "Confirm halt"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
