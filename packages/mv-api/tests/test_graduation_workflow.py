"""Unit tests for the graduation composition handler (eligibility + compliance)."""

from __future__ import annotations

from decimal import Decimal

from mv.api.graduation import GraduationEntry, build_graduate_handler
from mv.risk.compliance import ComplianceChecklist
from mv.risk.graduation import PaperRecord


class _FakeStore:
    def __init__(self) -> None:
        self.entries: list[GraduationEntry] = []

    def record(self, entry: GraduationEntry) -> None:
        self.entries.append(entry)


def _record(**over: object) -> PaperRecord:
    base = {
        "strategy": "ema_cross_12_26",
        "gate_status": "active",
        "months_paper": 4.0,
        "oos_sharpe": 1.3,
        "max_drawdown": Decimal("0.08"),
        "n_trades": 140,
        "projection_honesty": None,
    }
    base.update(over)
    return PaperRecord(**base)  # type: ignore[arg-type]


def _clear() -> ComplianceChecklist:
    return ComplianceChecklist(True, True, True, True)


def test_eligible_and_compliant_graduates() -> None:
    store = _FakeStore()
    handler = build_graduate_handler(
        records_provider=lambda _slug: _record(),
        compliance_provider=_clear,
        store=store,
    )
    result = handler("ema_cross_12_26", "ankit")
    assert result["graduated"] is True
    assert result["reasons"] == []
    assert result["live_cap_pct"] == "0.01"
    assert store.entries[0].graduated is True


def test_ineligible_record_is_rejected_and_recorded() -> None:
    store = _FakeStore()
    handler = build_graduate_handler(
        records_provider=lambda _slug: _record(months_paper=1.0, oos_sharpe=0.2),
        compliance_provider=_clear,
        store=store,
    )
    result = handler("weak", "ankit")
    assert result["graduated"] is False
    assert result["reasons"]
    assert store.entries[0].graduated is False  # the rejected attempt is audited


def test_compliance_block_rejects_even_if_eligible() -> None:
    store = _FakeStore()
    handler = build_graduate_handler(
        records_provider=lambda _slug: _record(),
        compliance_provider=lambda: ComplianceChecklist(sebi_algo_cleared=True),  # rest unresolved
        store=store,
    )
    result = handler("ema_cross_12_26", "ankit")
    assert result["graduated"] is False
    assert any("LRS/FEMA" in r for r in result["reasons"])


def test_missing_paper_record_is_rejected() -> None:
    store = _FakeStore()
    handler = build_graduate_handler(
        records_provider=lambda _slug: None,
        compliance_provider=_clear,
        store=store,
    )
    result = handler("unknown", "ankit")
    assert result["graduated"] is False
    assert any("no paper record" in r for r in result["reasons"])
