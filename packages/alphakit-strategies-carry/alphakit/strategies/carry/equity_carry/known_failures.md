# Known failure modes — equity_carry

## 1. Momentum overlap

The carry proxy (trailing return) conflates carry with momentum.
When momentum reverses sharply (e.g., March 2009, November 2020
rotation), the carry strategy suffers drawdowns driven by momentum
crashes rather than carry signal deterioration.

## 2. Regime sensitivity

Equity carry performance varies across macro regimes. During
risk-off periods, high-carry (high-yield) equities tend to
underperform defensive assets, causing the strategy to lose
on both legs of the long/short portfolio.

## 3. Earnings surprises disrupting carry

Unexpected earnings announcements can cause sudden re-pricing
that overwhelms the carry signal. A stock with stable high carry
can gap down 20%+ on an earnings miss, and these discrete events
are not captured by the trailing-return proxy.

## 4. Crowded trade

Cross-sectional carry in equities is a well-known factor. When
many systematic managers hold similar positions, unwinds are
correlated and amplified. Crowding also erodes expected returns
as carry spreads compress.
