"use client";

import { useSourceHealth } from "@/lib/hooks";
import type { SourceHealthRow } from "@/lib/types";
import { formatPct, formatTime } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import styles from "./SourceHealth.module.css";

export function SourceHealth() {
  const sources = useSourceHealth();
  const reconciles = (sources.data ?? []).filter((s) => s.reconcile_flag);

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Source Health</h1>
        <p className={styles.sub}>Per-source status, quota burn, latency, and last failover.</p>
      </header>

      <StatePanel
        state={sources.state}
        error="Source-health feed unavailable."
        emptyMessage="No sources reporting."
      >
        <div className={styles.grid}>
          {sources.data?.map((s) => (
            <SourceCard key={s.source} source={s} />
          ))}
        </div>

        <section className={styles.reconcile}>
          <h2 className={styles.panelTitle}>Reconciliation</h2>
          {reconciles.length === 0 ? (
            <p className={styles.clean}>No cross-source discrepancies flagged.</p>
          ) : (
            <ul className={styles.reconcileList}>
              {reconciles.map((s) => (
                <li key={s.source}>
                  <span className={styles.dot} data-status="red" aria-hidden="true" />
                  {s.source} — {s.domain}
                </li>
              ))}
            </ul>
          )}
        </section>
      </StatePanel>
    </div>
  );
}

function SourceCard({ source }: { source: SourceHealthRow }) {
  return (
    <article className={styles.card} data-status={source.status}>
      <div className={styles.cardHead}>
        <span className={styles.dot} data-status={source.status} aria-hidden="true" />
        <span className={styles.name}>{source.source}</span>
      </div>
      <div className={styles.domain}>{source.domain}</div>
      <dl className={styles.metrics}>
        <Metric label="Quota burn" value={formatPct(source.quota_burn_pct / 100, 0)} />
        <Metric label="Latency p50" value={`${source.latency_p50_ms} ms`} />
        <Metric label="Latency p95" value={`${source.latency_p95_ms} ms`} />
        <Metric label="Last failover" value={source.last_failover ? formatTime(source.last_failover) : "—"} />
      </dl>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metric}>
      <dt>{label}</dt>
      <dd className="mono">{value}</dd>
    </div>
  );
}
