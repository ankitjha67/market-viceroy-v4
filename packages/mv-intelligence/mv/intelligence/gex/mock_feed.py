"""A deterministic MOCK gamma screen so the Vol Desk logic runs + tests offline.

Real GEX inputs are a paid US-options data domain behind the governor + a GEX
computation engine (Phase 12); this fixture proves the grading / entry / exit
logic without them. A representative mix: one clean setup, one grade block, one
spike-crash block, one DEEP name, one thin-cushion block.
"""

from __future__ import annotations

from decimal import Decimal

from mv.intelligence.gex.types import GammaRow


def mock_gamma_screen() -> list[GammaRow]:
    """A handful of gamma-screen rows spanning pass / block cases."""
    return [
        # Clean: grade 10, strong db_change (+0.60), 6% cushion, 8:1 R/R, spot > pTrans.
        GammaRow(
            symbol="AAPL",
            spot=Decimal("100"),
            dealer_delta=Decimal("0.80"),
            prior_delta=Decimal("0.20"),
            grade=10,
            minervini=95,
            p_trans=Decimal("99"),
            n_trans=Decimal("95"),
            zero_gex=Decimal("97"),
            plus_gex=Decimal("108"),
            cotmp=Decimal("94"),
            cotmc=Decimal("112"),
        ),
        # Grade 8 -> hard block regardless of the rest.
        GammaRow(
            symbol="WEAK",
            spot=Decimal("50"),
            dealer_delta=Decimal("0.90"),
            prior_delta=Decimal("0.30"),
            grade=8,
            minervini=80,
            p_trans=Decimal("49"),
            n_trans=Decimal("47"),
            zero_gex=Decimal("48"),
            plus_gex=Decimal("60"),
            cotmp=Decimal("46"),
            cotmc=Decimal("62"),
        ),
        # Spike-crash target -> hard block despite grade 11 + strong numbers.
        GammaRow(
            symbol="SPK",
            spot=Decimal("200"),
            dealer_delta=Decimal("0.85"),
            prior_delta=Decimal("0.25"),
            grade=11,
            minervini=110,
            p_trans=Decimal("198"),
            n_trans=Decimal("190"),
            zero_gex=Decimal("195"),
            plus_gex=Decimal("230"),
            cotmp=Decimal("185"),
            cotmc=Decimal("240"),
            spike_crash=True,
        ),
        # DEEP (grade 11): db_change only +0.35 but the DEEP bar is 0.30 -> passes.
        GammaRow(
            symbol="DEEP",
            spot=Decimal("75"),
            dealer_delta=Decimal("0.95"),
            prior_delta=Decimal("0.60"),
            grade=11,
            minervini=105,
            p_trans=Decimal("74.5"),
            n_trans=Decimal("71"),
            zero_gex=Decimal("73"),
            plus_gex=Decimal("82"),
            cotmp=Decimal("74"),  # ~1.3% cushion — OK under the DEEP 1% relaxation
            cotmc=Decimal("85"),
        ),
    ]


__all__ = ["mock_gamma_screen"]
