"use client";

import { useSettings } from "@/lib/hooks";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

export function Settings() {
  const settings = useSettings();
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Settings</h1>
        <p className={styles.sub}>
          Read-only configuration — sources, per-agent LLM routing, and mode. Secrets live in the
          vault and are never shown here.
        </p>
      </header>
      <StatePanel state={settings.state} error="Settings unavailable." emptyMessage="No configuration reported.">
        <dl className={styles.kv}>
          {Object.entries(settings.data ?? {}).map(([key, value]) => (
            <div className={styles.kvRow} key={key}>
              <dt>{key.replace(/_/g, " ")}</dt>
              <dd className="mono">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
            </div>
          ))}
        </dl>
      </StatePanel>
    </div>
  );
}
