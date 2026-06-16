"""Black-Scholes helpers for the synthetic option-chain generator.

Small, dependency-light pricing utilities used by
:mod:`alphakit.data.options.synthetic`. Everything here operates on
Python scalars so strategies can call it in tight loops without paying
a numpy dispatch cost per quote. All functions assume European-style
exercise, continuous compounding, no dividends, and a lognormal
underlying — the standard Black-Scholes assumptions.

The module deliberately avoids SciPy. The normal CDF uses
:func:`math.erf`; the implied-volatility solver is a hand-rolled
Brent's method. This keeps the Phase 2 options family runnable on a
stripped-down install with only ``numpy`` (already required by
``alphakit-core``) and the standard library.

Sign / unit conventions
-----------------------
* ``T`` is year-fractions (e.g. 30 days = 30/365.0).
* ``r`` is a continuously-compounded annual risk-free rate.
* ``sigma`` is annualised volatility expressed as a decimal (``0.20``
  for 20 % vol, not ``20``).
* ``delta``, ``gamma``, ``vega``, ``theta`` are returned in their
  "textbook" units: delta dimensionless, gamma per 1-unit of spot,
  vega per 1.0 of vol (i.e. divide by 100 for per-percent), theta
  per 1.0 of year (i.e. divide by 365 for per-day).
"""

from __future__ import annotations

from math import erf, exp, log, pi, sqrt

_SQRT_2 = sqrt(2.0)
_SQRT_2PI = sqrt(2.0 * pi)


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF built on :func:`math.erf`."""
    return 0.5 * (1.0 + erf(x / _SQRT_2))


def _norm_pdf(x: float) -> float:
    """Standard-normal PDF."""
    return exp(-0.5 * x * x) / _SQRT_2PI


def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes ``d1`` term."""
    return (log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt(T))


def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes ``d2`` term."""
    return d1(S, K, T, r, sigma) - sigma * sqrt(T)


def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes price of a European call option."""
    d1_ = d1(S, K, T, r, sigma)
    d2_ = d1_ - sigma * sqrt(T)
    return S * _norm_cdf(d1_) - K * exp(-r * T) * _norm_cdf(d2_)


def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes price of a European put option."""
    d1_ = d1(S, K, T, r, sigma)
    d2_ = d1_ - sigma * sqrt(T)
    return K * exp(-r * T) * _norm_cdf(-d2_) - S * _norm_cdf(-d1_)


def call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Delta of a European call (``N(d1)``)."""
    return _norm_cdf(d1(S, K, T, r, sigma))


def put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Delta of a European put (``N(d1) - 1``)."""
    return _norm_cdf(d1(S, K, T, r, sigma)) - 1.0


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Gamma (same for calls and puts under BS)."""
    return _norm_pdf(d1(S, K, T, r, sigma)) / (S * sigma * sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vega (same for calls and puts under BS). Per 1.0 of vol."""
    return S * _norm_pdf(d1(S, K, T, r, sigma)) * sqrt(T)


def call_theta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Theta of a European call. Per 1.0 of year."""
    d1_ = d1(S, K, T, r, sigma)
    d2_ = d1_ - sigma * sqrt(T)
    return -S * _norm_pdf(d1_) * sigma / (2.0 * sqrt(T)) - r * K * exp(-r * T) * _norm_cdf(d2_)


def put_theta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Theta of a European put. Per 1.0 of year."""
    d1_ = d1(S, K, T, r, sigma)
    d2_ = d1_ - sigma * sqrt(T)
    return -S * _norm_pdf(d1_) * sigma / (2.0 * sqrt(T)) + r * K * exp(-r * T) * _norm_cdf(-d2_)


def implied_vol(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    *,
    right: str = "call",
    lower: float = 1e-3,
    upper: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float:
    """Invert Black-Scholes for implied volatility via Brent's method.

    Brackets sigma in ``[lower, upper]``. The function priced by BS at
    ``sigma`` is monotonically increasing in sigma, so a sign change on
    ``bs_price(sigma) - price`` gives a unique root.

    Raises
    ------
    ValueError
        If ``right`` is not ``"call"`` or ``"put"``, or if the target
        ``price`` falls outside the bracket [price(lower), price(upper)].
    """
    if right == "call":
        pricer = call_price
    elif right == "put":
        pricer = put_price
    else:
        raise ValueError(f"right must be 'call' or 'put', got {right!r}")

    def objective(sigma: float) -> float:
        return pricer(S, K, T, r, sigma) - price

    a, b = lower, upper
    fa = objective(a)
    fb = objective(b)
    if abs(fa) < tol:
        return a
    if abs(fb) < tol:
        return b
    if fa * fb > 0.0:
        raise ValueError(
            f"implied_vol: target price {price} not bracketed in "
            f"sigma=[{lower}, {upper}] (f(a)={fa:.4g}, f(b)={fb:.4g})"
        )

    # Brent's method: maintain three points (a contrapoint, b current,
    # c previous) and interpolate when safe, bisect when not.
    if abs(fa) < abs(fb):
        a, b = b, a
        fa, fb = fb, fa

    c, fc = a, fa
    mflag = True
    d = 0.0  # only read after the first iteration sets mflag=False

    for _ in range(max_iter):
        if fa != fc and fb != fc:
            # Inverse quadratic interpolation
            s = (
                a * fb * fc / ((fa - fb) * (fa - fc))
                + b * fa * fc / ((fb - fa) * (fb - fc))
                + c * fa * fb / ((fc - fa) * (fc - fb))
            )
        else:
            # Secant
            s = b - fb * (b - a) / (fb - fa)

        cond1 = not ((3 * a + b) / 4.0 <= s <= b or b <= s <= (3 * a + b) / 4.0)
        cond2 = mflag and abs(s - b) >= abs(b - c) / 2.0
        cond3 = (not mflag) and abs(s - b) >= abs(c - d) / 2.0
        cond4 = mflag and abs(b - c) < tol
        cond5 = (not mflag) and abs(c - d) < tol
        if cond1 or cond2 or cond3 or cond4 or cond5:
            s = 0.5 * (a + b)
            mflag = True
        else:
            mflag = False

        fs = objective(s)
        d, c, fc = c, b, fb
        if fa * fs < 0.0:
            b, fb = s, fs
        else:
            a, fa = s, fs
        if abs(fa) < abs(fb):
            a, b = b, a
            fa, fb = fb, fa
        if abs(fb) < tol or abs(b - a) < tol:
            return b

    raise RuntimeError(
        f"implied_vol did not converge within {max_iter} iterations "
        f"(tol={tol}); last iterate sigma={b}, residual={fb:.4g}"
    )
