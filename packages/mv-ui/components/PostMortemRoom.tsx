"use client";

import { useImprovements, useMistakes } from "@/lib/hooks";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

export function PostMortemRoom() {
  const mistakes = useMistakes();
  const improvements = useImprovements();
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Post-Mortem Room</h1>
        <p className={styles.sub}>Mistake taxonomy + the governed improvement ledger.</p>
      </header>

      <section>
        <h2 className={styles.sub}>Mistake taxonomy</h2>
        <StatePanel state={mistakes.state} error="Mistake taxonomy unavailable." emptyMessage="No mistakes classified yet.">
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Category</th>
                <th className={styles.num}>Count</th>
                <th className={styles.num}>Cumulative cost</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(mistakes.data ?? {}).map(([category, stat]) => (
                <tr key={category}>
                  <td className="mono">{category}</td>
                  <td className={`${styles.num} mono`}>{stat.count}</td>
                  <td className={`${styles.num} mono neg`}>{stat.cost}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </StatePanel>
      </section>

      <section>
        <h2 className={styles.sub}>Improvement ledger</h2>
        <StatePanel state={improvements.state} error="Improvement ledger unavailable." emptyMessage="No improvements logged yet.">
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Change</th>
                <th>Targets</th>
                <th className={styles.num}>Before</th>
                <th className={styles.num}>After</th>
                <th>Adopted</th>
              </tr>
            </thead>
            <tbody>
              {improvements.data?.map((imp, i) => (
                <tr key={i}>
                  <td>
                    <span className="mono">{imp.change_kind}</span> — {imp.change_desc}
                  </td>
                  <td>{imp.mistake_category ?? "—"}</td>
                  <td className={`${styles.num} mono`}>{imp.before_metric ?? "—"}</td>
                  <td className={`${styles.num} mono`}>{imp.after_metric ?? "—"}</td>
                  <td>{imp.adopted ? "yes" : "proposed"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </StatePanel>
      </section>
    </div>
  );
}
