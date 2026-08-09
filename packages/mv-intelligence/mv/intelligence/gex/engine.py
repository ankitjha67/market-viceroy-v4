"""GEX engine v1 — dealer-gamma profile computed from a real options chain.

Closes the "GEX is mock-fed" gap using free Deribit chain summaries (strike,
expiry, OI, mark IV): Black-Scholes gamma per instrument, aggregated into a
net dealer-gamma profile by strike under the standard convention (dealers are
long the calls customers sold and short the puts customers bought: call gamma
positive, put gamma negative). Outputs the Vol Desk levels: the zero-gamma
flip, the +GEX magnet (T1), the put/call mass centers, and a dealer delta
balance. Pure math (floats internally, Decimal at the GammaRow boundary),
deterministic, unit-tested on synthetic chains. Grade/minervini remain
caller-supplied inputs — this engine computes LEVELS; the structural grade is
equity-momentum evidence the crypto v1 honestly does not have.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from mv.intelligence.gex.types import GammaRow
from mv.intelligence.sources.deribit import OptionSummary


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_gamma(spot: float, strike: float, iv: float, t_years: float) -> float:
    """Black-Scholes gamma (same for calls and puts); zero on degenerate inputs."""
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * t_years) / (iv * math.sqrt(t_years))
    return _norm_pdf(d1) / (spot * iv * math.sqrt(t_years))


def bs_delta(spot: float, strike: float, iv: float, t_years: float, right: str) -> float:
    """Black-Scholes delta (r = 0 convention); zero on degenerate inputs."""
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * iv * iv * t_years) / (iv * math.sqrt(t_years))
    return _norm_cdf(d1) if right == "C" else _norm_cdf(d1) - 1.0


@dataclass(frozen=True, slots=True)
class GammaProfile:
    """The chain's aggregated dealer-gamma structure (levels in underlying terms)."""

    spot: float
    zero_gex: float  # gamma-flip level (cumulative net GEX zero crossing)
    plus_gex: float  # strike with the largest positive net GEX (the T1 magnet)
    cotmp: float  # OI-weighted center of put mass (structural floor)
    cotmc: float  # OI-weighted center of call mass (T2 candidate)
    dealer_delta: float  # call-delta share of total delta mass, 0..1
    total_gex: float  # net dollar gamma per 1 percent move (sign = regime)
    by_strike: tuple[tuple[float, float], ...]  # (strike, net GEX) ascending


def gamma_profile(chain: list[OptionSummary], *, as_of: datetime) -> GammaProfile | None:
    """Aggregate a chain into the dealer-gamma profile; ``None`` if unusable.

    Net GEX per strike = sum over instruments of
    ``gamma * OI * spot^2 * 0.01`` with calls positive and puts negative
    (dollar gamma per 1 percent move, contract multiplier 1 as on Deribit).
    """
    live = [o for o in chain if o.expiry > as_of and o.open_interest > 0 and o.mark_iv > 0]
    if not live:
        return None
    # Deribit reports the per-expiry FORWARD as underlying_price and payload
    # order is not guaranteed, so taking whichever row happened to be last made
    # every level depend on input ordering. Anchor on the nearest expiry.
    spot = min(live, key=lambda o: o.expiry).underlying
    if spot <= 0:
        return None

    by_strike: dict[float, float] = {}
    put_mass = call_mass = 0.0
    put_center = call_center = 0.0
    call_delta_mass = put_delta_mass = 0.0
    for opt in live:
        t_years = max(1e-6, (opt.expiry - as_of).total_seconds() / (365.0 * 86400.0))
        gamma = bs_gamma(spot, opt.strike, opt.mark_iv, t_years)
        gex = gamma * opt.open_interest * spot * spot * 0.01
        signed = gex if opt.right == "C" else -gex
        by_strike[opt.strike] = by_strike.get(opt.strike, 0.0) + signed
        delta_mass = abs(bs_delta(spot, opt.strike, opt.mark_iv, t_years, opt.right))
        delta_mass *= opt.open_interest
        if opt.right == "P":
            put_mass += opt.open_interest
            put_center += opt.open_interest * opt.strike
            put_delta_mass += delta_mass
        else:
            call_mass += opt.open_interest
            call_center += opt.open_interest * opt.strike
            call_delta_mass += delta_mass

    strikes = sorted(by_strike)
    profile = tuple((k, by_strike[k]) for k in strikes)

    # Flip level: where the cumulative net GEX (ascending strikes) crosses zero.
    # The flip is the cumulative-GEX zero crossing in EITHER direction: a
    # put-heavy upper chain crosses positive-to-negative, and only testing the
    # negative-to-positive case reported the flip at the last strike (well wide
    # of spot, and on the wrong side of it).
    cumulative = 0.0
    zero_gex: float | None = None
    prev_strike, prev_cum = strikes[0], 0.0
    for strike in strikes:
        cumulative += by_strike[strike]
        crosses_up = prev_cum < 0.0 <= cumulative
        crosses_down = prev_cum > 0.0 >= cumulative
        if (crosses_up or crosses_down) and cumulative != prev_cum:
            frac = -prev_cum / (cumulative - prev_cum)
            zero_gex = prev_strike + frac * (strike - prev_strike)
            break
        prev_strike, prev_cum = strike, cumulative

    positive = [(k, v) for k, v in profile if v > 0]
    total_delta = call_delta_mass + put_delta_mass
    # A chain with no measurable gamma (illiquid rows quote mark_iv 0) cannot
    # produce levels. Report NO PROFILE rather than inventing a flip at the
    # first strike, a magnet at the last, and a "balanced" 0.5 dealer delta
    # that is indistinguishable from a genuine reading.
    if zero_gex is None or not positive or total_delta <= 0.0:
        return None
    plus_gex = max(positive, key=lambda kv: kv[1])[0]
    return GammaProfile(
        spot=spot,
        zero_gex=zero_gex,
        plus_gex=plus_gex,
        cotmp=put_center / put_mass if put_mass else strikes[0],
        cotmc=call_center / call_mass if call_mass else strikes[-1],
        dealer_delta=call_delta_mass / total_delta,
        total_gex=sum(v for _, v in profile),
        by_strike=profile,
    )


def gamma_row_from_profile(
    symbol: str,
    profile: GammaProfile,
    *,
    prior_delta: float,
    grade: int = 0,
    minervini: int = 0,
) -> GammaRow:
    """Map a profile into the Vol Desk :class:`GammaRow` (Decimal boundary).

    ``grade`` / ``minervini`` stay caller-supplied (structural/momentum evidence
    the chain alone cannot provide); pTrans/nTrans use the flip level and the
    put-mass floor as the v1 transition proxies.
    """

    def d(value: float) -> Decimal:
        return Decimal(str(round(value, 8)))

    return GammaRow(
        symbol=symbol,
        spot=d(profile.spot),
        dealer_delta=d(min(1.0, max(0.0, profile.dealer_delta))),
        prior_delta=d(min(1.0, max(0.0, prior_delta))),
        grade=grade,
        minervini=minervini,
        p_trans=d(profile.zero_gex),
        n_trans=d(min(profile.cotmp, profile.zero_gex)),
        zero_gex=d(profile.zero_gex),
        plus_gex=d(profile.plus_gex),
        cotmp=d(profile.cotmp),
        cotmc=d(profile.cotmc),
    )


__all__ = ["GammaProfile", "bs_delta", "bs_gamma", "gamma_profile", "gamma_row_from_profile"]
