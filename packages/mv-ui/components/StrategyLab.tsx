"use client";

import { useStrategies } from "@/lib/hooks";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

export function StrategyLab() {
  const strategies = useStrategies();
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Strategy Lab</h1>
        <p className={styles.sub}>The catalog with its validation-gate verdict and provenance.</p>
      </header>
      <StatePanel state={strategies.state} error="Strategy catalog unavailable." emptyMessage="No strategies in the catalog.">
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Strategy</th>
              <th>Family</th>
              <th>Gate</th>
              <th>Data source</th>
              <th>Live</th>
            </tr>
          </thead>
          <tbody>
            {strategies.data?.map((s) => (
              <tr key={s.slug}>
                <td className="mono">{s.slug}</td>
                <td>{s.family}</td>
                <td>
                  <span className={styles.badge} data-tone={s.gate_status}>
                    {s.gate_status}
                  </span>
                </td>
                <td>{s.data_source}</td>
                <td className="mono">{s.live_status ?? "paper"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </StatePanel>
    </div>
  );
}
