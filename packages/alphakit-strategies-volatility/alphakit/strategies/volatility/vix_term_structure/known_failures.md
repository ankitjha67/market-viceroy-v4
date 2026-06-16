# Known failure modes — vix_term_structure

## 1. VIX proxy limitation (realized vol is not VIX)

## 2. Contango/backwardation detection lag

## 3. Proxy limitation
Price-derived proxy does not capture the paper's actual mechanism. See docs/deviations.md.

## 4. Tail risk
Volatility strategies have inherent tail risk — large losses can occur in vol spikes.
