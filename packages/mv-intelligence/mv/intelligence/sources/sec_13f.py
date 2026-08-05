"""SEC 13F-HR institutional holdings: parse + quarter-over-quarter diff.

Adopted from the Vibe-Trading review: 13F information tables are a free primary
source for institutional positioning, and the quarter-over-quarter *diff* (new,
exited, resized positions) is the readable signal. The XML information-table
parse and the diff are pure and unit-tested; fetching a filing (by its EDGAR
accession URL, with the descriptive User-Agent EDGAR requires) is offline-
gated. Values are reported by filers in USD thousands and kept as reported.
Point-in-time rule: a 13F is knowable at its FILING date, never the quarter
end it describes.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True, slots=True)
class Holding:
    """One information-table row (value in USD thousands, as filed)."""

    issuer: str
    cusip: str
    value_kusd: int
    shares: int


@dataclass(frozen=True, slots=True)
class HoldingChange:
    """One quarter-over-quarter position change (by CUSIP)."""

    issuer: str
    cusip: str
    kind: str  # "new" | "exited" | "increased" | "decreased"
    value_kusd_before: int
    value_kusd_after: int


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_information_table(xml_text: str) -> list[Holding]:
    """Parse a 13F information table (namespace-tolerant); malformed rows drop."""
    root = ElementTree.fromstring(xml_text)
    out: list[Holding] = []
    for element in root.iter():
        if _local(element.tag) != "infoTable":
            continue
        fields: dict[str, str] = {}
        for child in element.iter():
            name = _local(child.tag)
            if child.text and name in ("nameOfIssuer", "cusip", "value", "sshPrnamt"):
                fields.setdefault(name, child.text.strip())
        try:
            out.append(
                Holding(
                    issuer=fields["nameOfIssuer"],
                    cusip=fields["cusip"],
                    value_kusd=int(float(fields["value"])),
                    shares=int(float(fields["sshPrnamt"])),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def aggregate_by_cusip(holdings: list[Holding]) -> dict[str, Holding]:
    """Sum multi-row positions (filers split lots) into one row per CUSIP."""
    merged: dict[str, Holding] = {}
    for h in holdings:
        prev = merged.get(h.cusip)
        if prev is None:
            merged[h.cusip] = h
        else:
            merged[h.cusip] = Holding(
                issuer=prev.issuer,
                cusip=h.cusip,
                value_kusd=prev.value_kusd + h.value_kusd,
                shares=prev.shares + h.shares,
            )
    return merged


def holdings_diff(previous: list[Holding], current: list[Holding]) -> list[HoldingChange]:
    """Quarter-over-quarter position changes, largest absolute value move first."""
    prev = aggregate_by_cusip(previous)
    cur = aggregate_by_cusip(current)
    changes: list[HoldingChange] = []
    for cusip, holding in cur.items():
        before = prev.get(cusip)
        if before is None:
            changes.append(HoldingChange(holding.issuer, cusip, "new", 0, holding.value_kusd))
        elif holding.value_kusd != before.value_kusd:
            kind = "increased" if holding.value_kusd > before.value_kusd else "decreased"
            changes.append(
                HoldingChange(holding.issuer, cusip, kind, before.value_kusd, holding.value_kusd)
            )
    for cusip, holding in prev.items():
        if cusip not in cur:
            changes.append(HoldingChange(holding.issuer, cusip, "exited", holding.value_kusd, 0))
    return sorted(
        changes, key=lambda c: abs(c.value_kusd_after - c.value_kusd_before), reverse=True
    )


def fetch_information_table(
    accession_url: str, *, user_agent: str
) -> list[Holding]:  # pragma: no cover - network
    """Fetch + parse one filing's information-table XML from an EDGAR URL."""
    import requests

    response = requests.get(accession_url, headers={"User-Agent": user_agent}, timeout=30)
    response.raise_for_status()
    return parse_information_table(response.text)


__all__ = [
    "Holding",
    "HoldingChange",
    "aggregate_by_cusip",
    "fetch_information_table",
    "holdings_diff",
    "parse_information_table",
]
