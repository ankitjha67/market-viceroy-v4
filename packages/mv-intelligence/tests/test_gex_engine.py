"""Tests for the GEX engine (gamma profile, flip level, GammaRow mapping)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from mv.intelligence.gex.engine import bs_gamma, gamma_profile, gamma_row_from_profile
from mv.intelligence.sources.deribit import OptionSummary

_NOW = datetime(2026, 8, 5, tzinfo=timezone.utc)
_EXPIRY = _NOW + timedelta(days=30)


def _opt(strike: float, right: str, oi: float, iv: float = 0.6) -> OptionSummary:
    assert right in ("C", "P")
    return OptionSummary(
        strike=strike,
        expiry=_EXPIRY,
        right="C" if right == "C" else "P",
        open_interest=oi,
        mark_iv=iv,
        underlying=100000.0,
    )


def test_bs_gamma_positive_and_degenerate_safe() -> None:
    assert bs_gamma(100.0, 100.0, 0.5, 0.25) > 0
    assert bs_gamma(100.0, 100.0, 0.0, 0.25) == 0.0
    assert bs_gamma(0.0, 100.0, 0.5, 0.25) == 0.0


def test_gamma_profile_levels_from_a_synthetic_chain() -> None:
    # Put mass concentrated at 90k, call mass at 110k: the flip must sit
    # between them, +GEX at the call magnet, mass centers at the strikes.
    chain = [
        _opt(90000, "P", oi=2000),
        _opt(110000, "C", oi=2000),
        _opt(120000, "C", oi=100),
    ]
    profile = gamma_profile(chain, as_of=_NOW)
    assert profile is not None
    assert 90000 < profile.zero_gex <= 110000
    assert profile.plus_gex == 110000
    assert profile.cotmp == 90000
    assert 110000 < profile.cotmc < 120000  # call-mass weighted center
    assert 0.0 <= profile.dealer_delta <= 1.0


def test_gamma_profile_ignores_expired_and_zero_oi() -> None:
    chain = [
        OptionSummary(
            strike=90000,
            expiry=_NOW - timedelta(days=1),
            right="P",
            open_interest=5000,
            mark_iv=0.6,
            underlying=100000.0,
        ),
        _opt(110000, "C", oi=0),
    ]
    assert gamma_profile(chain, as_of=_NOW) is None


def test_gamma_row_mapping_decimal_boundary() -> None:
    chain = [_opt(90000, "P", oi=2000), _opt(110000, "C", oi=2000)]
    profile = gamma_profile(chain, as_of=_NOW)
    assert profile is not None
    row = gamma_row_from_profile("BTC", profile, prior_delta=0.4, grade=9, minervini=7)
    assert isinstance(row.spot, Decimal)
    assert row.grade == 9  # caller-supplied structural evidence, not fabricated
    assert row.zero_gex == row.p_trans  # v1 transition proxy documented
    assert Decimal("0") <= row.dealer_delta <= Decimal("1")
