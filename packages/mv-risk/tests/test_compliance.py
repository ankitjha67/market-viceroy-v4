"""Unit tests for the §13 compliance pre-checks."""

from __future__ import annotations

from mv.risk.compliance import ComplianceChecklist


def test_default_blocks_everything() -> None:
    checklist = ComplianceChecklist()
    assert checklist.all_clear() is False
    assert len(checklist.blocking_reasons()) == 4


def test_partial_still_blocks() -> None:
    checklist = ComplianceChecklist(sebi_algo_cleared=True, tax_configured=True)
    assert checklist.all_clear() is False
    reasons = checklist.blocking_reasons()
    assert any("LRS/FEMA" in r for r in reasons)
    assert any("withdrawal-disabled" in r for r in reasons)


def test_all_clear() -> None:
    checklist = ComplianceChecklist(
        sebi_algo_cleared=True,
        lrs_fema_cleared=True,
        keys_withdrawal_disabled=True,
        tax_configured=True,
    )
    assert checklist.all_clear() is True
    assert checklist.blocking_reasons() == []
