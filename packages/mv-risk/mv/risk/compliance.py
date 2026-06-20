"""Compliance pre-checks for graduation (PRD §13) — block live until cleared.

Real money is blocked until the legal/operational checklist is all-clear:

- **SEBI algo framework** — broker approval / exchange-tagged-algo obligations
  confirmed for the chosen broker (India automated orders).
- **Cross-border (LRS/FEMA)** — real-money non-Indian trading constraints
  resolved (or the strategy is domestic-only).
- **Withdrawal-disabled keys** — the live exchange keys are scoped,
  withdrawal-disabled, and IP-allowlisted (CLAUDE.md #6).
- **Tax configured** — the cost model's tax fields (e.g. India crypto flat + TDS)
  are set so net-PnL is honest.

This is a **gate**, not legal advice: it records what the Operator has attested
and blocks graduation while anything is unresolved. Pure and unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComplianceChecklist:
    """The Operator's attestations required before any live graduation (§13)."""

    sebi_algo_cleared: bool = False
    lrs_fema_cleared: bool = False
    keys_withdrawal_disabled: bool = False
    tax_configured: bool = False

    def blocking_reasons(self) -> list[str]:
        """The unresolved items blocking graduation (empty when all-clear)."""
        reasons: list[str] = []
        if not self.sebi_algo_cleared:
            reasons.append("SEBI algo obligations not confirmed for the broker")
        if not self.lrs_fema_cleared:
            reasons.append("LRS/FEMA cross-border constraints not resolved")
        if not self.keys_withdrawal_disabled:
            reasons.append("live keys not attested scoped/withdrawal-disabled/IP-allowlisted")
        if not self.tax_configured:
            reasons.append("tax fields not configured in the cost model")
        return reasons

    def all_clear(self) -> bool:
        """True only when every compliance item is attested."""
        return not self.blocking_reasons()


__all__ = ["ComplianceChecklist"]
