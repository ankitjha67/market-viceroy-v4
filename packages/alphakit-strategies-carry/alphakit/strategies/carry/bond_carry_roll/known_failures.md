# Known failure modes — bond_carry_roll

## 1. Yield curve inversion breaks roll-down

The roll-down component of bond carry assumes a positively sloped
yield curve. When the curve inverts (e.g., US 2019, 2022-2023),
roll-down becomes negative and the carry signal loses its
predictive power.

## 2. Rate-hiking cycles

During aggressive rate-hiking cycles, bonds with the highest
carry (highest yield) suffer the largest capital losses. The
carry signal points to markets that are about to experience
the sharpest sell-offs, inverting the expected return profile.

## 3. Proxy doesn't capture actual yield

The Phase 1 proxy (trailing return) does not measure actual
bond yield or roll-down. It conflates carry with momentum
and duration effects. A bond market with high trailing returns
may have low forward carry if yields have already compressed.

## 4. Convexity not modeled

This implementation does not account for bond convexity. For
large yield moves, the linear carry approximation breaks down,
especially for longer-duration bonds. Convexity effects can
cause the realized return to diverge significantly from the
carry estimate.
