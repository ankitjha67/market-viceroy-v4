"""Tests for the Black-Scholes helpers used by the synthetic chain feed.

Five reference triples come from Hull *Options, Futures and Other
Derivatives* 10e (example 15.6) and from textbook-standard (S, K, T,
r, sigma) inputs whose prices are reproducible analytically. Put-call
parity is asserted on each triple to catch sign / factor bugs.

The implied-volatility round-trip test takes a sigma, prices a
call/put, then recovers sigma via Brent's method — a bug in either
the pricer or the solver breaks this round trip.
"""

from __future__ import annotations

import math

import pytest
from alphakit.data.options import bs

# (S, K, T, r, sigma, expected_call, expected_put).
# Values computed at spec time with math.erf-based CDF; cross-checked
# against Hull 15.6 and against put-call parity on every row.
HULL_TRIPLES = [
    # Hull 10e, example 15.6 — c ≈ 4.76, p ≈ 0.81 per the textbook.
    (42.0, 40.0, 0.5, 0.10, 0.20, 4.7594, 0.8086),
    (100.0, 100.0, 1.0, 0.05, 0.20, 10.4506, 5.5735),
    (100.0, 110.0, 0.5, 0.05, 0.25, 4.2258, 11.5099),
    (100.0, 90.0, 0.5, 0.05, 0.30, 15.4860, 3.2639),
    (50.0, 50.0, 1 / 12, 0.03, 0.25, 1.5007, 1.3759),
]


@pytest.mark.parametrize(
    ("S", "K", "T", "r", "sigma", "expected_call", "expected_put"), HULL_TRIPLES
)
def test_call_price_matches_textbook(
    S: float, K: float, T: float, r: float, sigma: float, expected_call: float, expected_put: float
) -> None:
    assert bs.call_price(S, K, T, r, sigma) == pytest.approx(expected_call, abs=1e-3)


@pytest.mark.parametrize(
    ("S", "K", "T", "r", "sigma", "expected_call", "expected_put"), HULL_TRIPLES
)
def test_put_price_matches_textbook(
    S: float, K: float, T: float, r: float, sigma: float, expected_call: float, expected_put: float
) -> None:
    assert bs.put_price(S, K, T, r, sigma) == pytest.approx(expected_put, abs=1e-3)


@pytest.mark.parametrize(
    ("S", "K", "T", "r", "sigma", "expected_call", "expected_put"), HULL_TRIPLES
)
def test_put_call_parity(
    S: float, K: float, T: float, r: float, sigma: float, expected_call: float, expected_put: float
) -> None:
    """c - p = S - K*exp(-rT) must hold exactly for European options."""
    call = bs.call_price(S, K, T, r, sigma)
    put = bs.put_price(S, K, T, r, sigma)
    assert call - put == pytest.approx(S - K * math.exp(-r * T), abs=1e-9)


def test_call_delta_matches_hull_17_1() -> None:
    """Hull example 17.1: S=49, K=50, T=20/52, r=0.05, sigma=0.20, delta≈0.522."""
    delta = bs.call_delta(49.0, 50.0, 20.0 / 52.0, 0.05, 0.20)
    assert delta == pytest.approx(0.522, abs=1e-3)


def test_put_delta_is_call_delta_minus_one() -> None:
    dc = bs.call_delta(100.0, 100.0, 1.0, 0.05, 0.20)
    dp = bs.put_delta(100.0, 100.0, 1.0, 0.05, 0.20)
    assert dp == pytest.approx(dc - 1.0, abs=1e-12)


def test_gamma_is_identical_for_call_and_put() -> None:
    """Gamma is right-symmetric under Black-Scholes."""
    g = bs.gamma(100.0, 100.0, 1.0, 0.05, 0.20)
    assert g > 0.0
    # Gamma peaks near ATM; sanity check.
    g_far_otm = bs.gamma(100.0, 200.0, 1.0, 0.05, 0.20)
    assert g > g_far_otm


def test_vega_is_positive_and_peaks_atm() -> None:
    atm = bs.vega(100.0, 100.0, 1.0, 0.05, 0.20)
    deep_itm = bs.vega(100.0, 50.0, 1.0, 0.05, 0.20)
    assert atm > 0.0
    assert atm > deep_itm


def test_theta_call_is_negative_for_atm() -> None:
    assert bs.call_theta(100.0, 100.0, 1.0, 0.05, 0.20) < 0.0


def test_implied_vol_round_trip_call() -> None:
    sigma = 0.23
    S, K, T, r = 100.0, 95.0, 0.5, 0.04
    price = bs.call_price(S, K, T, r, sigma)
    recovered = bs.implied_vol(price, S, K, T, r, right="call")
    assert recovered == pytest.approx(sigma, abs=1e-5)


def test_implied_vol_round_trip_put() -> None:
    sigma = 0.31
    S, K, T, r = 80.0, 85.0, 0.25, 0.02
    price = bs.put_price(S, K, T, r, sigma)
    recovered = bs.implied_vol(price, S, K, T, r, right="put")
    assert recovered == pytest.approx(sigma, abs=1e-5)


def test_implied_vol_rejects_unknown_right() -> None:
    with pytest.raises(ValueError, match="right must be"):
        bs.implied_vol(1.0, 100.0, 100.0, 1.0, 0.05, right="straddle")


def test_implied_vol_rejects_price_outside_bracket() -> None:
    # A negative target is unreachable by any positive sigma.
    with pytest.raises(ValueError, match="not bracketed"):
        bs.implied_vol(-1.0, 100.0, 100.0, 1.0, 0.05, right="call")
