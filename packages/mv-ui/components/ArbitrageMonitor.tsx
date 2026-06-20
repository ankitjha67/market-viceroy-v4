"use client";

import { useArbitrage } from "@/lib/hooks";
import { signClass } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

export function ArbitrageMonitor() {
  const arb = useArbitrage();
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Arbitrage Monitor</h1>
        <p className={styles.sub}>
          After-cost edges with Red/Amber/Green executability. Gross spreads are never shown as
          profit; cross-border is monitor-only.
        </p>
      </header>
      <StatePanel state={arb.state} error="Arbitrage feed unavailable." emptyMessage="No opportunities surfaced.">
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Legs</th>
              <th className={styles.num}>Gross bps</th>
              <th className={styles.num}>After-cost bps</th>
              <th>Exec</th>
            </tr>
          </thead>
          <tbody>
            {arb.data?.map((o, i) => (
              <tr key={`${o.kind}-${i}`}>
                <td className="mono">{o.kind}</td>
                <td>{o.legs}</td>
                <td className={`${styles.num} mono`}>{o.gross_edge_bps}</td>
                <td className={`${styles.num} mono ${signClass(o.after_cost_edge_bps)}`}>
                  {o.after_cost_edge_bps}
                </td>
                <td>
                  <span className={styles.badge} data-tone={o.executability}>
                    {o.executability}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </StatePanel>
    </div>
  );
}
