# Known failure modes — statarb_pca

## 1. Factor model misspecification

PCA factors are statistical, not economic. During regime changes, the
factor structure shifts and residuals become non-stationary.

## 2. Crowded stat arb trades

The Avellaneda-Lee approach is widely known and implemented. Many
funds trade similar signals, which can lead to crowding and sudden
unwinds (August 2007 quant quake).

## 3. PCA instability

Rolling PCA factors can rotate between windows, causing the
residuals to be inconsistent across time.

## 4. Decay parameter sensitivity

The cumulative residual decay (0.95) is hand-tuned. Too low and
residuals decay too fast; too high and they accumulate noise.
