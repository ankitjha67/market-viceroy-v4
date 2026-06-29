"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import {
  useDecisions,
  useHealth,
  useHistory,
  useImprovements,
  useMetrics,
  useMistakes,
  useOhlcv,
  usePortfolio,
  usePositions,
  useRiskLimits,
  useSettings,
  useSourceHealth,
  useStrategies,
  useTrades,
} from "@/lib/hooks";
import { formatMoney, formatNum, formatPct, formatTime, signClass } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import { KillSwitch } from "./KillSwitch";
import { EquityChart } from "./EquityChart";
import { PriceChart } from "./PriceChart";
import styles from "./LiveDashboard.module.css";

/**
 * The unified live dashboard (the home screen): everything in one place — equity
 * curve, P&L, Buy/Sell/Hold, positions, models/strategies, risk, learning, source
 * health — each tile drilling down into its detailed screen. Values are INR; the
 * polling hooks keep it updating continuously while the loop runs.
 */
export function LiveDashboard() {
  const health = useHealth();
  const portfolio = usePortfolio();
  const history = useHistory();
  const ohlcv = useOhlcv();
  const metrics = useMetrics();
  const trades = useTrades();
  const positions = usePositions();
  const decisions = useDecisions();
  const sources = useSourceHealth();
  const strategies = useStrategies();
  const risk = useRiskLimits();
  const mistakes = useMistakes();
  const improvements = useImprovements();
  const settings = useSettings();

  const p = portfolio.data;
  const s = settings.data ?? {};
  const ddSeverity = p ? Math.min(1, Number(p.drawdown) / 0.2) : 0;
  const engine = String(s.decision_engine ?? "ensemble");
  const symbol = String(s.symbol ?? "—");
  const timeframe = String(s.timeframe ?? "—");
  const fx = s.fx_usd_inr ? `₹${String(s.fx_usd_inr)}/USD` : "";
  const weighting = String(s.weighting ?? "equal-weight");
  const regime = (s.regime ?? null) as {
    label: string;
    trend_score: string;
    trend_weight: string;
    meanrev_weight: string;
  } | null;
  const m = metrics.data ?? {};

  const active = strategies.data?.filter((x) => x.gate_status === "active").length ?? 0;
  const observe = strategies.data?.filter((x) => x.gate_status === "observe").length ?? 0;

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1>Command Deck</h1>
          <p className={styles.sub}>The fund in a glass box — live, paper, INR.</p>
          <div className={styles.modeStrip}>
            <span>paper</span>
            <span>{engine}</span>
            <span className="mono">{symbol}</span>
            <span className="mono">{timeframe}</span>
            {fx && <span className="mono">{fx}</span>}
            {regime && <span>regime: {regime.label}</span>}
          </div>
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

      <section className={styles.panel} aria-label="Price chart">
        <div className={styles.tileHead}>
          <h2 className={styles.panelTitle}>Price &amp; trades — {symbol}</h2>
          <span className={styles.note}>candles · EMA12 · EMA26 · volume · ▲ buy / ▼ sell</span>
        </div>
        <StatePanel
          state={ohlcv.state}
          error="Price feed unavailable."
          emptyMessage="Waiting for bars…"
        >
          <PriceChart data={ohlcv.data ?? { bars: [], markers: [] }} />
        </StatePanel>
      </section>

      <section className={styles.panel} aria-label="Equity curve">
        <h2 className={styles.panelTitle}>Equity curve</h2>
        <StatePanel
          state={history.state}
          error="Equity history unavailable."
          emptyMessage="Waiting for the first tick…"
        >
          <EquityChart points={history.data ?? []} />
        </StatePanel>
      </section>

      <section className={styles.panel} aria-label="Performance metrics">
        <h2 className={styles.panelTitle}>Performance</h2>
        <StatePanel state={metrics.state} error="Metrics unavailable." emptyMessage="No closed trades yet.">
          <div className={styles.metricGrid}>
            <Stat label="Sharpe" value={formatNum(m.sharpe ?? "0", 2)} />
            <Stat label="Sortino" value={formatNum(m.sortino ?? "0", 2)} />
            <Stat label="Win rate" value={formatPct(m.win_rate ?? "0")} />
            <Stat label="Profit factor" value={formatNum(m.profit_factor ?? "0", 2)} />
            <Stat label="Expectancy" value={formatMoney(m.expectancy ?? "0")} sign={m.expectancy} />
            <Stat label="Total P&L" value={formatMoney(m.total_pnl ?? "0")} sign={m.total_pnl} />
            <Stat label="Max DD" value={formatPct(m.max_drawdown ?? "0")} />
            <Stat label="Trades" value={m.n_trades ?? "0"} />
            <Stat label="Avg win" value={formatMoney(m.avg_win ?? "0")} sign={m.avg_win} />
            <Stat label="Avg loss" value={formatMoney(m.avg_loss ?? "0")} sign={m.avg_loss} />
          </div>
        </StatePanel>
      </section>

      <section className={styles.panel} aria-label="Closed trades">
        <h2 className={styles.panelTitle}>Closed trades</h2>
        <StatePanel state={trades.state} error="Blotter unavailable." emptyMessage="No closed trades yet.">
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Closed</th>
                <th>Instrument</th>
                <th>Side</th>
                <th className={styles.num}>Entry</th>
                <th className={styles.num}>Exit</th>
                <th className={styles.num}>P&amp;L</th>
                <th className={styles.num}>Return</th>
                <th className={styles.num}>Held</th>
              </tr>
            </thead>
            <tbody>
              {trades.data
                ?.slice()
                .reverse()
                .slice(0, 10)
                .map((t) => (
                  <tr key={t.id}>
                    <td className="mono">{formatTime(t.closed_at)}</td>
                    <td>{t.instrument}</td>
                    <td className={t.side === "LONG" ? "pos" : "neg"}>{t.side}</td>
                    <td className={`${styles.num} mono`}>{formatMoney(t.entry)}</td>
                    <td className={`${styles.num} mono`}>{formatMoney(t.exit)}</td>
                    <td className={`${styles.num} mono ${signClass(t.pnl)}`}>{formatMoney(t.pnl)}</td>
                    <td className={`${styles.num} mono ${signClass(t.return_pct)}`}>
                      {formatPct(t.return_pct)}
                    </td>
                    <td className={`${styles.num} mono`}>{fmtDuration(t.duration_s)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </StatePanel>
      </section>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Open positions</h2>
          <StatePanel
            state={positions.state}
            error="Positions feed unavailable."
            emptyMessage={`No positions; ${decisions.data?.length ?? 0} decisions, paper mode.`}
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
                    <td className={`${styles.num} mono`}>{formatMoney(pos.entry)}</td>
                    <td className={`${styles.num} mono`}>{formatMoney(pos.mark)}</td>
                    <td className={`${styles.num} mono ${signClass(pos.pnl)}`}>{formatMoney(pos.pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </StatePanel>
        </section>

        <section className={styles.panel}>
          <TileTitle href="/agents">Buy / Sell / Hold</TileTitle>
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
                      <Link
                        className={styles.link}
                        href={`/agents?s=${encodeURIComponent(d.payload.snapshot_id)}`}
                      >
                        pipeline →
                      </Link>
                    )}
                  </li>
                ))}
            </ul>
          </StatePanel>
        </section>
      </div>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <TileTitle href="/strategies">Models &amp; strategies</TileTitle>
          <StatePanel state={strategies.state} error="Strategy catalog unavailable." emptyMessage="No strategies yet.">
            <p className={styles.note}>
              Decision engine: <strong>{engine}</strong> ({weighting}) — trading{" "}
              <strong>{String(s.live_strategies ?? "—")}</strong>.
            </p>
            {regime && (
              <p className={styles.note}>
                Regime: <strong>{regime.label}</strong> (ER {Number(regime.trend_score).toFixed(2)}) —
                weighting <strong>{(Number(regime.trend_weight) * 100).toFixed(0)}%</strong> trend /{" "}
                <strong>{(Number(regime.meanrev_weight) * 100).toFixed(0)}%</strong> mean-rev, live.
              </p>
            )}
            <p className={styles.note}>
              Catalog: <strong>{active}</strong> gate-active · <strong>{observe}</strong> observing of{" "}
              {strategies.data?.length ?? 0}.
            </p>
            <ul className={styles.chips}>
              {strategies.data?.slice(0, 8).map((x) => (
                <li key={x.slug} className={styles.chip} data-gate={x.gate_status}>
                  {x.slug}
                </li>
              ))}
            </ul>
          </StatePanel>
        </section>

        <section className={styles.panel}>
          <TileTitle href="/risk">Risk &amp; exposure</TileTitle>
          <StatePanel state={risk.state} error="Risk limits unavailable." emptyMessage="No limits reported.">
            <ul className={styles.kv}>
              {Object.entries(risk.data ?? {})
                .slice(0, 6)
                .map(([k, v]) => (
                  <li key={k}>
                    <span>{k}</span>
                    <span className="mono">{String(v)}</span>
                  </li>
                ))}
            </ul>
          </StatePanel>
        </section>
      </div>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <TileTitle href="/postmortem">Learning</TileTitle>
          <StatePanel
            state={improvements.state}
            error="Post-mortem unavailable."
            emptyMessage="No improvements proposed yet."
          >
            <p className={styles.note}>
              {Object.keys(mistakes.data ?? {}).length} mistake categories ·{" "}
              {improvements.data?.length ?? 0} improvement proposals (propose-only).
            </p>
          </StatePanel>
        </section>

        <section className={styles.panel}>
          <TileTitle href="/health">Source health</TileTitle>
          <StatePanel state={sources.state} error="Source health unavailable." emptyMessage="No sources reporting.">
            <ul className={styles.sourceRow}>
              {sources.data?.map((src) => (
                <li key={src.source} className={styles.sourceChip}>
                  <span className={styles.dot} data-status={src.status} aria-hidden="true" />
                  <span>{src.source}</span>
                  {src.last_failover && (
                    <span className={styles.failover} title={formatTime(src.last_failover)}>
                      failover
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </StatePanel>
        </section>
      </div>
    </div>
  );
}

function TileTitle({ href, children }: { href: string; children: ReactNode }) {
  return (
    <div className={styles.tileHead}>
      <h2 className={styles.panelTitle}>{children}</h2>
      <Link className={styles.drill} href={href}>
        open →
      </Link>
    </div>
  );
}

function fmtDuration(seconds: string): string {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return "—";
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  const h = Math.floor(s / 3600);
  const min = Math.round((s % 3600) / 60);
  return min ? `${h}h ${min}m` : `${h}h`;
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
  const color =
    severity > 0.75 ? "var(--status-red)" : severity > 0.4 ? "var(--status-amber)" : "var(--status-green)";
  return (
    <svg viewBox="0 0 100 8" className={styles.gauge} role="img" aria-label="Drawdown vs breaker">
      <rect x="0" y="2" width="100" height="4" rx="2" fill="var(--surface-sunk)" />
      <rect x="0" y="2" width={width} height="4" rx="2" fill={color} />
    </svg>
  );
}
