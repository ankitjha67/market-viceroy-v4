"use client";

import { useState } from "react";
import { useJournal } from "@/lib/hooks";
import { formatTime } from "@/lib/format";
import { StatePanel } from "./StatePanel";
import styles from "./screen.module.css";

const KINDS = [
  "",
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
  const journal = useJournal(kind, q);

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Journal Explorer</h1>
        <p className={styles.sub}>Search the tamper-evident decision journal.</p>
      </header>

      <div className={styles.toolbar}>
        <select className={styles.select} value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Filter by kind">
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
              <th className={styles.num}>Seq</th>
              <th>Kind</th>
              <th>Time</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {journal.data?.map((e) => (
              <tr key={e.seq}>
                <td className={`${styles.num} mono`}>{e.seq}</td>
                <td className="mono">{e.kind}</td>
                <td className="mono">{formatTime(e.ts)}</td>
                <td className="mono">{JSON.stringify(e.payload)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </StatePanel>
    </div>
  );
}
