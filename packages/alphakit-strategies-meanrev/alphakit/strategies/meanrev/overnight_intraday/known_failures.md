# Known failure modes — overnight_intraday

## 1. No open price data

The AlphaKit protocol provides only close prices. The true overnight
return (close-to-open) cannot be computed, so this implementation
uses a cross-sectional residual proxy. The signal quality is
substantially degraded compared to the original paper.

## 2. Low cross-sectional dispersion

When all assets move in lockstep (high correlation regimes such as
2008 crisis or 2020 March), cross-sectional residuals shrink towards
zero, and the ranking becomes noisy. Signals degrade to near-random.

## 3. Transaction costs on daily rebalance

Daily rebalancing with rank-weighted portfolios generates high
turnover. After realistic transaction costs, the strategy's alpha
can be fully consumed, especially in less liquid universes.

## 4. Regime dependence

The overnight-vs-intraday reversal pattern varies across market
regimes. Lou et al. note the effect is strongest in stocks with
high institutional ownership. In ETF-only universes the signal
may be too weak to generate meaningful alpha.
