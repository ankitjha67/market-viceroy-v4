"""Rule-based financial sentiment (PRD FR-I3) — local, date-gated, deterministic.

A compact local lexicon scorer (no external NLP, no torch, no remote/LLM call) —
so it is trivially point-in-time (a headline is scored from its own text) and
CI-friendly. FinBERT-local is deferred. Returns a score in [-1, 1].
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z']+")

POSITIVE: frozenset[str] = frozenset(
    {
        "beat",
        "beats",
        "surge",
        "surges",
        "soar",
        "soars",
        "gain",
        "gains",
        "profit",
        "profitable",
        "upgrade",
        "upgraded",
        "growth",
        "strong",
        "record",
        "rally",
        "rallies",
        "outperform",
        "bullish",
        "rebound",
        "jump",
        "jumps",
        "rise",
        "rises",
        "boost",
        "optimistic",
        "win",
        "wins",
    }
)

NEGATIVE: frozenset[str] = frozenset(
    {
        "miss",
        "misses",
        "plunge",
        "plunges",
        "fall",
        "falls",
        "loss",
        "losses",
        "downgrade",
        "downgraded",
        "decline",
        "declines",
        "weak",
        "slump",
        "bearish",
        "cut",
        "cuts",
        "lawsuit",
        "fraud",
        "bankruptcy",
        "plummet",
        "plummets",
        "drop",
        "drops",
        "warn",
        "warning",
        "fear",
        "fears",
        "risk",
    }
)


def score_text(text: str) -> float:
    """Sentiment of ``text`` in [-1, 1] (positive minus negative, normalized)."""
    tokens = _TOKEN_RE.findall(text.lower())
    positive = sum(1 for token in tokens if token in POSITIVE)
    negative = sum(1 for token in tokens if token in NEGATIVE)
    total = positive + negative
    if total == 0:
        return 0.0
    return (positive - negative) / total
