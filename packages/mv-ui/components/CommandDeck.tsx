"use client";

import Link from "next/link";
import { useDecisions, useHealth, usePortfolio, usePositions, useSourceHealth } from "@/lib/hooks";
import { formatMoney, formatPct, formatTime, signClass } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import { KillSwitch } from "./KillSwitch";
import styles from "./CommandDeck.module.css";

export function CommandDeck() {
  const health = useHealth();
  const portfolio = usePortfolio();
  const positions = usePositions();
  const decisions = useDecisions();
  const sources = useSourceHealth();

  const p = portfolio.data;
  const ddSeverity = p ? Math.min(1, Number(p.drawdown) / 0.2) : 0; // scale vs a 20% breaker

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1>Command Deck</h1>
          <p className={styles.sub}>The fund in a glass box.</p>
        </div>
        <KillSwitch tripped={health.data?.kill_switch_tripped ?? false} />
      </header>

      <section className={styles.stats} aria-label="Portfolio summary">
        <StatePanel state={portfolio.state} error="Portfolio summary unavailable." emptyMessage="No portfolio yet.">
          <Stat label="Equity" value={p ? formatMoney(p.equity) : ""} />
          <Stat label="Day P&L" value={p ? formatMoney(p.day_pnl) : ""} sign={p?.day_pnl} />
          <div className={styles.gaugeWrap}>
            <div className={styles.statLabel}>Drawdown</div>
            <div className={`${styles.statValue} mono`}>{p ? formatPct(p.drawdown) : ""}</div>
            <DrawdownGauge severity={ddSeverity} />
          </div>
        </StatePanel>
      </section>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Open positions</h2>
          <StatePanel
            state={positions.state}
            error="Positions feed unavailable."
            emptyMessage={`No positions; ${decisions.data?.length ?? 0} decisions today, paper mode.`}
          >
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th className={styles.num}>Size</th>
                  <th className={styles.num}>Entry</th>
                  <th className={styles.num}>Mark</th>
                  <th className={styles.num}>P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.data?.map((pos) => (
                  <tr key={pos.instrument}>
                    <td>{pos.instrument}</td>
                    <td className={`${styles.num} mono`}>{pos.size}</td>
                    <td className={`${styles.num} mono`}>{pos.entry}</td>
                    <td className={`${styles.num} mono`}>{pos.mark}</td>
                    <td className={`${styles.num} mono ${signClass(pos.pnl)}`}>{formatMoney(pos.pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </StatePanel>
        </section>

        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Latest decisions</h2>
          <StatePanel state={decisions.state} error="Decision feed unavailable." emptyMessage="No decisions yet.">
            <ul className={styles.feed}>
              {decisions.data
                ?.slice()
                .reverse()
                .slice(0, 8)
                .map((d) => (
                  <li key={d.seq} className={styles.feedItem}>
                    <span className={`${styles.action} ${styles[d.payload.action ?? "HOLD"]}`}>
                      {d.payload.action ?? "HOLD"}
                    </span>
                    <span className={styles.instrument}>{d.payload.instrument ?? "—"}</span>
                    <span className={styles.rationale}>{d.payload.rationale ?? ""}</span>
                    {d.payload.snapshot_id && (
                      <Link className={styles.link} href={`/agents?s=${encodeURIComponent(d.payload.snapshot_id)}`}>
                        pipeline →
                      </Link>
                    )}
                  </li>
                ))}
            </ul>
          </StatePanel>
        </section>
      </div>

      <section className={styles.panel}>
        <h2 className={styles.panelTitle}>Source health</h2>
        <StatePanel state={sources.state} error="Source health unavailable." emptyMessage="No sources reporting.">
          <ul className={styles.sourceRow}>
            {sources.data?.map((s) => (
              <li key={s.source} className={styles.sourceChip}>
                <span className={styles.dot} data-status={s.status} aria-hidden="true" />
                <span>{s.source}</span>
                {s.last_failover && (
                  <span className={styles.failover} title={formatTime(s.last_failover)}>
                    failover
                  </span>
                )}
              </li>
            ))}
          </ul>
        </StatePanel>
      </section>
    </div>
  );
}

function Stat({ label, value, sign }: { label: string; value: string; sign?: string }) {
  return (
    <div className={styles.stat}>
      <div className={styles.statLabel}>{label}</div>
      <div className={`${styles.statValue} mono ${sign ? signClass(sign) : ""}`}>{value}</div>
    </div>
  );
}

function DrawdownGauge({ severity }: { severity: number }) {
  const width = Math.max(0, Math.min(1, severity)) * 100;
  const color = severity > 0.75 ? "var(--status-red)" : severity > 0.4 ? "var(--status-amber)" : "var(--status-green)";
  return (
    <svg viewBox="0 0 100 8" className={styles.gauge} role="img" aria-label="Drawdown vs breaker">
      <rect x="0" y="2" width="100" height="4" rx="2" fill="var(--surface-sunk)" />
      <rect x="0" y="2" width={width} height="4" rx="2" fill={color} />
    </svg>
  );
}
