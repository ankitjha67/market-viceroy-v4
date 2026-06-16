# Known failure modes — dual_momentum_gem

## 1. Whipsaws at regime-change turning points

GEM switches the entire book between 3 assets monthly. At regime
changes (e.g. 2018 Q4, 2020 Q1, 2022 Q1) the strategy can get caught
in a sequence of monthly flips — exiting equities one month, re-entering
the next, exiting again. This is the #1 source of investor frustration
with the strategy.

Expected behaviour around regime breaks:
* 2-3 consecutive monthly flips
* 3-8% drawdown per flip
* Net cost: ~1-2% per flip vs. a buy-and-hold benchmark

## 2. Strong relative but weak absolute momentum

When US equities are outperforming international but both are **below**
the risk-free return, the strategy correctly flags the regime and
holds bonds — but this misses the *relative* winner. During the early
stages of a new bull market the strategy can lag by 3-6 months as the
absolute-momentum filter catches up.

## 3. Symbol-specific failure

The strategy is sensitive to which ETFs you use for US / International
/ risk-free. Swapping VEU for VXUS (different underlying index) can
change the monthly direction in ~5% of months because the two ETFs
have different emerging-market exposures. Always pick long-history
proxies that match the paper's intent.

## 4. Does not protect from flash crashes

The monthly rebalance means GEM cannot react to a flash crash that
mean-reverts within a month (e.g. Volmageddon in Feb 2018). It will
take the full drawdown of whichever leg it was holding.
