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
    put_call: str = ""  # "", "Put" or "Call" -- an option line is not the stock


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
            if child.text and name in ("nameOfIssuer", "cusip", "value", "sshPrnamt", "putCall"):
                fields.setdefault(name, child.text.strip())
        try:
            out.append(
                Holding(
                    issuer=fields["nameOfIssuer"],
                    cusip=fields["cusip"],
                    value_kusd=int(float(fields["value"])),
                    shares=int(float(fields["sshPrnamt"])),
                    put_call=fields.get("putCall", ""),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def aggregate_by_cusip(holdings: list[Holding]) -> dict[tuple[str, str], Holding]:
    """Sum a filer's split lots into one row per (CUSIP, put/call).

    Keyed on the security TYPE as well as the issuer: a protective put and the
    common stock share a CUSIP, so merging on CUSIP alone added an option line
    into the share count and inverted the read for any filer that hedges.
    """
    merged: dict[tuple[str, str], Holding] = {}
    for h in holdings:
        key = (h.cusip, h.put_call)
        prev = merged.get(key)
        if prev is None:
            merged[key] = h
        else:
            merged[key] = Holding(
                issuer=prev.issuer,
                cusip=h.cusip,
                value_kusd=prev.value_kusd + h.value_kusd,
                shares=prev.shares + h.shares,
                put_call=h.put_call,
            )
    return merged


def holdings_diff(previous: list[Holding], current: list[Holding]) -> list[HoldingChange]:
    """Quarter-over-quarter position changes, largest absolute share move first.

    Classified on SHARE COUNT, not market value. 13F ``value`` is shares times
    the quarter-end price, so a value diff conflates the filer's decision with
    the price move: a filer who 2.5x'd a position into a falling price showed as
    "no change", and one who did nothing through a rally showed as "increased".
    Shares are the only price-independent quantity a 13F reports.
    """
    prev = aggregate_by_cusip(previous)
    cur = aggregate_by_cusip(current)
    changes: list[HoldingChange] = []
    for key, holding in cur.items():
        before = prev.get(key)
        if before is None:
            changes.append(
                HoldingChange(holding.issuer, holding.cusip, "new", 0, holding.value_kusd)
            )
        elif holding.shares != before.shares:
            kind = "increased" if holding.shares > before.shares else "decreased"
            changes.append(
                HoldingChange(
                    holding.issuer, holding.cusip, kind, before.value_kusd, holding.value_kusd
                )
            )
    for key, holding in prev.items():
        if key not in cur:
            changes.append(
                HoldingChange(holding.issuer, holding.cusip, "exited", holding.value_kusd, 0)
            )
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
