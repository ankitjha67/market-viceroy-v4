"use client";

import { Fragment, useState } from "react";
import { useJournal } from "@/lib/hooks";
import { formatTime } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

// Every record kind the loop journals — the glass box, newest first. "signals"
// is the per-strategy vote behind each ensemble decision.
const KINDS = [
  "",
  "signals",
  "decision",
  "risk_assessment",
  "execution",
  "analyst_view",
  "debate_turn",
  "research_verdict",
  "graduation",
  "live_blocked",
];

export function JournalExplorer() {
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<number>>(new Set());
  const journal = useJournal(kind, q);

  const toggle = (seq: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(seq)) {
        next.delete(seq);
      } else {
        next.add(seq);
      }
      return next;
    });

  // Newest first — the freshest tool activity at the top of the log.
  const rows = (journal.data ?? []).slice().reverse();

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Journal Explorer</h1>
        <p className={styles.sub}>
          The tool&apos;s complete log — every signal, decision, risk check and fill, hash-chained.
          {journal.data ? ` ${journal.data.length} entries.` : ""} Click a row for the full record.
        </p>
      </header>

      <div className={styles.toolbar}>
        <select
          className={styles.select}
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          aria-label="Filter by kind"
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k || "all kinds"}
            </option>
          ))}
        </select>
        <input
          className={styles.input}
          placeholder="search text…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search text"
        />
      </div>

      <StatePanel state={journal.state} error="Journal unavailable." emptyMessage="No matching journal entries.">
        <table className={styles.table}>
          <thead>
            <tr>
              <th aria-label="expand" />
              <th className={styles.num}>Seq</th>
              <th>Kind</th>
              <th>Time</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => {
              const isOpen = open.has(e.seq);
              return (
                <Fragment key={e.seq}>
                  <tr className={styles.logRow} onClick={() => toggle(e.seq)}>
                    <td>
                      <button
                        type="button"
                        className={styles.disclose}
                        aria-expanded={isOpen}
                        aria-label={isOpen ? "Collapse record" : "Expand record"}
                        onClick={(ev) => {
                          ev.stopPropagation();
                          toggle(e.seq);
                        }}
                      >
                        {isOpen ? "▾" : "▸"}
                      </button>
                    </td>
                    <td className={`${styles.num} mono`}>{e.seq}</td>
                    <td className="mono">{e.kind}</td>
                    <td className="mono">{formatTime(e.ts)}</td>
                    <td>
                      <div className={`mono ${styles.summary}`}>{JSON.stringify(e.payload)}</div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr>
                      <td />
                      <td colSpan={4}>
                        <pre className={styles.record}>{JSON.stringify(e.payload, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </StatePanel>
    </div>
  );
}
