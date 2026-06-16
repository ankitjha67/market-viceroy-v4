# Paper — Bond Carry-and-Rolldown (KMPV 2018, after Fama 1984)

## Citations

**Initial inspiration:** Fama, E. F. (1984). **Forward rates as
predictors of future spot rates.** *Journal of Financial Economics*,
13(4), 509–528.
[https://doi.org/10.1016/0304-405X(84)90013-8](https://doi.org/10.1016/0304-405X(84)90013-8)

**Primary methodology:** Koijen, R. S. J., Moskowitz, T. J., Pedersen,
L. H. & Vrugt, E. B. (2018). **Carry.** *Journal of Financial
Economics*, 127(2), 197–225.
[https://doi.org/10.1016/j.jfineco.2017.11.002](https://doi.org/10.1016/j.jfineco.2017.11.002)

BibTeX entries: `fama1984forward` (foundational) and `koijen2018carry`
(primary) in `docs/papers/phase-2.bib`.

## Why two papers

Fama (1984) is the seminal *expected-return* result for bonds: he shows
that forward rates are *biased* predictors of future spot rates,
implying that the term premium (the excess holding-period return on
long bonds vs short bonds) is non-zero and forecastable. The
unbiased-expectations hypothesis, which would have made carry-and-
rolldown trades zero-sum, is rejected.

Koijen et al. (2018) operationalise that result with a uniform
*carry* definition that applies across asset classes: for a coupon
bond the carry is the current yield plus the rolldown contribution
(the price appreciation from moving down a positively-sloped curve
as the bond ages). KMPV demonstrate that bond carry is a robust,
persistent and *priced* source of expected return.

We anchor the implementation on KMPV (2018) §III because that
section explicitly defines the bond carry signal in a tradeable form;
Fama (1984) is cited as the foundational expected-return-existence
result.

## Carry-and-rolldown intuition

For a coupon bond with current yield ``Y`` and modified duration
``D``, holding for a period ``Δt`` while the curve stays unchanged
yields three components:

1. **Coupon income:** ``Y × Δt`` (the current yield, accumulated over
   the holding period).
2. **Rolldown:** as time passes, the bond's maturity decreases and
   it moves to a shorter point on the curve. If the curve is upward-
   sloping (``Y_n > Y_{n−Δt}``), the bond's yield decreases by
   ``ΔY_roll`` and its price rises by ``D × ΔY_roll`` (modified-
   duration approximation).
3. **Yield-shift P&L:** ``−D × ΔY_market``, where ``ΔY_market`` is
   the change in the relevant point of the curve over the holding
   period.

KMPV's carry definition is the sum of (1) and (2): the return assuming
the curve stays *constant* (i.e. ``ΔY_market = 0``). It is the
"if nothing changes" return, and it is forecastable from the current
shape of the curve.

When the curve is **steep**, both (1) and (2) are large positive
numbers — high carry. When the curve is **flat**, both are small —
low carry. The trade is therefore: hold the long bond when carry is
elevated.

## Differentiation from sibling strategies

* **`curve_steepener_2s10s`** — bets on *mean-reversion of the slope*.
  Enters when the slope is *flat* (yield spread narrow), expecting
  it to widen.
* **`curve_flattener_2s10s`** — opposite of the steepener. Enters
  when the slope is *steep*, expecting it to flatten.
* **`bond_carry_rolldown` (this strategy)** — bets on *capturing the
  carry*. Enters when the slope is *steep* (yield spread wide), to
  hold the long bond while it is paying high carry+rolldown.

The flattener and the carry-rolldown both enter in *steep-curve*
regimes but for opposite reasons: the flattener bets the slope will
flatten (and profits if so), while the carry-rolldown bets the slope
*persists* long enough to harvest the carry. Their P&L correlation
depends on which side wins — moderately *negative* when mean-reversion
realises (flattener wins, carry loses some of the realisation),
moderately *positive* when the curve persists (flattener bleeds,
carry harvests).

* **`bond_carry_roll`** (in `alphakit-strategies-carry`) — the
  *cross-sectional* version of the same KMPV framework. Ranks many
  bond indices by carry and takes long/short positions on the
  ranking. ``bond_carry_rolldown`` is the *time-series* version on
  a single bond. They trade orthogonal information from the same
  underlying signal and are *not* duplicates.

## Carry-and-rolldown signal (this implementation)

Direct yield curve construction is data-hungry; the implementation
uses a price-space proxy that is monotone in the curve slope:

    log_spread = log(P_target_long) − log(P_short)
    z = (log_spread − rolling_mean) / rolling_std

* ``log_spread`` *high* ↔ long-end has out-performed ↔ curve is
  *narrow* (small yield spread) ↔ low carry.
* ``log_spread`` *low* ↔ long-end has under-performed (or curve has
  steepened) ↔ curve is *wide* (large yield spread) ↔ high carry.

Entry rule: ``z < −entry_threshold`` → long the target bond. Exit:
``z > −exit_threshold`` → close.

Position sizing
---------------
Single-asset trade. When entered, weight on the target bond is +1.0;
weight on the short-end column is always 0 (the short-end is
informational only — used to compute the slope proxy, not to take
a position). This is *not* DV01-neutral and does carry parallel-shift
exposure by design — that is, you take outright duration exposure
in steep-curve regimes.

## In-sample period (KMPV 2018)

* Data: 1971–2014 monthly, multi-asset
* Bond-carry sleeve uses 10Y futures across G10
* Sharpe of bond-carry across G10 ≈ 0.6 over 1971–2014;
  single-country US 10Y carry typically slightly lower

This single-asset US-only version is expected to under-perform the
cross-country sleeve for the same reason single-asset TSMOM
under-performs the cross-section: no cross-country diversification.

## Implementation deviations from KMPV (2018)

1. **Time-series binary entry rule** instead of cross-sectional
   ranking. KMPV §IV ranks all bonds by carry and takes long-top /
   short-bottom positions; this implementation conditions a single
   asset's exposure on its own carry vs history.
2. **Price-space slope proxy** instead of explicit yield-curve carry
   computation. The proxy is monotone in the slope, but the absolute
   units differ; the strategy z-scores the proxy so the absolute
   units don't matter for the entry rule.
3. **No transaction-cost or short-borrow model** — bridge applies
   ``commission_bps``, but only the long leg is held so short borrow
   does not apply.

None of these deviations change the **direction** of the trade
relative to the paper's economic content.

## Known replications and follow-ups

* **Asness, Moskowitz & Pedersen (2013)** — "Value and Momentum
  Everywhere", JF. Cross-sectional carry on bonds is one of their
  documented sleeves; complementary to KMPV's later work.
* **Cieslak & Povala (2015)** — "Expected Returns in Treasury Bonds",
  RFS. Refines the term-premium estimate using inflation expectations
  as an additional state variable.
