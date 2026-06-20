"use client";

import { useHealth, useRiskLimits } from "@/lib/hooks";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

export function RiskConsole() {
  const limits = useRiskLimits();
  const health = useHealth();
  const tripped = health.data?.kill_switch_tripped ?? false;
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Risk Console</h1>
        <p className={styles.sub}>The inviolable limits, live exposures, and kill-switch state.</p>
      </header>

      <div className={styles.toolbar}>
        <span className={styles.badge} data-tone={tripped ? "red" : "green"}>
          {tripped ? "kill-switch tripped" : "trading enabled"}
        </span>
      </div>

      <StatePanel state={limits.state} error="Risk limits unavailable." emptyMessage="No risk limits reported.">
        <dl className={styles.cards}>
          {Object.entries(limits.data ?? {}).map(([key, value]) => (
            <div className={styles.card} key={key}>
              <div className={styles.sub}>{key.replace(/_/g, " ")}</div>
              <div className="mono" style={{ fontSize: 22 }}>
                {value}
              </div>
            </div>
          ))}
        </dl>
      </StatePanel>
    </div>
  );
}
