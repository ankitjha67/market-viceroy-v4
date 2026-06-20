"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useAgentPipeline, useDecisions } from "@/lib/hooks";
import type { AgentRecord } from "@/lib/types";
import { StatePanel } from "./StatePanel";
import styles from "./AgentRoom.module.css";

export function AgentRoom() {
  const params = useSearchParams();
  const snapshot = params.get("s");
  return snapshot ? <Pipeline snapshot={snapshot} /> : <Picker />;
}

function Picker() {
  const decisions = useDecisions();
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <h1>Agent Room</h1>
        <p className={styles.sub}>Select a decision to open its research-to-PM pipeline.</p>
      </header>
      <StatePanel state={decisions.state} error="Decision feed unavailable." emptyMessage="No decisions yet.">
        <ul className={styles.pickList}>
          {decisions.data
            ?.slice()
            .reverse()
            .slice(0, 20)
            .map((d) => (
              <li key={d.seq}>
                <Link href={`/agents?s=${encodeURIComponent(String(d.payload.snapshot_id ?? ""))}`}>
                  <span className={styles.pickAction} data-action={d.payload.action ?? "HOLD"}>
                    {d.payload.action ?? "HOLD"}
                  </span>
                  <span className={styles.pickInstrument}>{d.payload.instrument ?? "—"}</span>
                  <span className={styles.pickRationale}>{d.payload.rationale ?? ""}</span>
                </Link>
              </li>
            ))}
        </ul>
      </StatePanel>
    </div>
  );
}

function Pipeline({ snapshot }: { snapshot: string }) {
  const pipeline = useAgentPipeline(snapshot);
  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1>Agent Room</h1>
          <p className={styles.sub}>
            <span className="mono">{snapshot}</span>
          </p>
        </div>
        <Link href="/agents" className={styles.back}>
          ← all decisions
        </Link>
      </header>
      <StatePanel
        state={pipeline.state}
        error="Pipeline unavailable."
        emptyMessage="No journaled records for this decision."
      >
        <ol className={styles.flow}>
          {pipeline.data?.pipeline.map((record) => (
            <Node key={record.seq} record={record} />
          ))}
        </ol>
      </StatePanel>
    </div>
  );
}

function Node({ record }: { record: AgentRecord }) {
  const [open, setOpen] = useState(false);
  const { title, line, tone } = summarize(record);
  return (
    <li className={styles.node} data-kind={record.kind}>
      <div className={styles.rail} aria-hidden="true">
        <span className={styles.bead} data-tone={tone} />
      </div>
      <div className={styles.card}>
        <button type="button" className={styles.cardHead} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          <span className={styles.kind}>{record.kind.replace(/_/g, " ")}</span>
          <span className={styles.title}>{title}</span>
          <span className={`${styles.line} ${tone === "veto" ? "neg" : ""}`}>{line}</span>
          <span className={styles.chev}>{open ? "−" : "+"}</span>
        </button>
        {open && (
          <dl className={styles.detail}>
            {Object.entries(record.payload).map(([k, v]) => (
              <div key={k} className={styles.row}>
                <dt>{k}</dt>
                <dd className="mono">{render(v)}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </li>
  );
}

function render(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

interface Summary {
  title: string;
  line: string;
  tone: "neutral" | "bull" | "bear" | "veto";
}

function summarize(record: AgentRecord): Summary {
  const p = record.payload as Record<string, unknown>;
  const agent = String(p.agent ?? record.kind);
  switch (record.kind) {
    case "analyst_view": {
      const stance = String(p.stance ?? "neutral");
      return { title: agent, line: `${stance} · score ${render(p.score)}`, tone: stance === "bullish" ? "bull" : stance === "bearish" ? "bear" : "neutral" };
    }
    case "debate_turn": {
      const side = String(p.side ?? "");
      return { title: `${side} researcher`, line: String(p.claim ?? ""), tone: side === "bull" ? "bull" : "bear" };
    }
    case "research_verdict":
      return { title: "Research Manager", line: `${render(p.net_stance)} — ${render(p.thesis)}`, tone: "neutral" };
    case "risk_assessment": {
      const approved = Boolean(p.approved);
      return {
        title: "Risk Manager",
        line: approved ? "approved" : `VETO — ${render(p.breached_limits)}`,
        tone: approved ? "neutral" : "veto",
      };
    }
    case "decision":
      return { title: "Portfolio Manager", line: `${render(p.action)} · conviction ${render(p.conviction)}`, tone: "neutral" };
    default:
      return { title: agent, line: String(p.rationale ?? ""), tone: "neutral" };
  }
}
