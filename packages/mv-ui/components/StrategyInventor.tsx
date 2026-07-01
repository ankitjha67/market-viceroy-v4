"use client";

import { useState } from "react";
import { adoptCandidate } from "@/lib/api";
import { useCandidates } from "@/lib/hooks";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

/**
 * The Strategy Inventor: watch it search strategies, grade each through the
 * validation gate, and adopt the survivors into the paper roster. Most candidates
 * are (correctly) rejected — an inventor that "finds a winner every day" is
 * overfitting. Adoption is Operator-authed; nothing trades paper without a click.
 */
export function StrategyInventor() {
  const candidates = useCandidates();
  const [token, setToken] = useState("");
  const [note, setNote] = useState("");

  const rows = candidates.data ?? [];
  const survived = rows.filter((c) => c.adoptable).length;

  const adopt = async (name: string) => {
    if (!token) {
      setNote("Enter the Operator token to adopt.");
      return;
    }
    try {
      const res = await adoptCandidate(name, token);
      setNote(
        res.adopted
          ? `Adopted ${name} into the paper roster.`
          : `Adopt failed: ${res.reason ?? "unknown"}`,
      );
    } catch (err) {
      setNote(`Adopt error: ${(err as Error).message}`);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Strategy Inventor</h1>
        <p className={styles.sub}>
          Search strategies → grade through the validation gate → adopt the survivors.
          {rows.length > 0 ? ` ${rows.length} tested, ${survived} survived.` : ""}
        </p>
      </header>

      <div className={styles.toolbar}>
        <input
          className={styles.input}
          type="password"
          placeholder="Operator token (to adopt)"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          aria-label="Operator token"
        />
        {note && <span className={styles.sub}>{note}</span>}
      </div>

      <StatePanel
        state={candidates.state}
        error="Inventor unavailable."
        emptyMessage="No inventor run yet — it grades candidates in the background."
      >
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>From</th>
              <th>Status</th>
              <th className={styles.num}>Deflated Sharpe</th>
              <th className={styles.num}>OOS Sharpe</th>
              <th className={styles.num}>WF +frac</th>
              <th>Verdict</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.name}>
                <td className="mono">{c.name}</td>
                <td>{c.provenance}</td>
                <td>
                  <span className={styles.badge} data-tone={c.status}>
                    {c.status}
                  </span>
                </td>
                <td className={`${styles.num} mono`}>{fmt(c.metrics.deflated_sharpe)}</td>
                <td className={`${styles.num} mono`}>{fmt(c.metrics.oos_sharpe)}</td>
                <td className={`${styles.num} mono`}>
                  {fmt(c.metrics.walk_forward_positive_fraction)}
                </td>
                <td className={styles.sub}>{c.reasons.join("; ")}</td>
                <td>
                  {c.adoptable && (
                    <button type="button" className={styles.input} onClick={() => adopt(c.name)}>
                      Adopt
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </StatePanel>
    </div>
  );
}

function fmt(value: number | undefined): string {
  return value === undefined ? "—" : value.toFixed(2);
}
