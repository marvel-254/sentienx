"""
risk_specialist.stats_core
===========================
Dependency-free statistical primitives for risk measurement.

Pure Python 3 stdlib only. Every routine is deterministic: given identical
input it produces identical output. This is a hard requirement for a risk
engine -- a VaR number that changes between two runs on the same data cannot
be audited, reconciled, or defended to a risk committee.

Design notes
------------
* No RNG anywhere. Where a textbook formula would use Monte Carlo (parametric
  VaR) we instead use the closed-form Gaussian quantile, evaluated from
  Acklam rational approximation with a Newton refinement.
* Numerical guards: every estimator that can divide by a near-zero quantity
  (variance, correlation) is guarded and degrades to a documented neutral
  value rather than raising or emitting NaN.
* Complexity is O(n) or O(n log n); memory is O(n). Suitable for an intraday
  rebalance loop running in-process.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Trading days per year, used for annualising daily observations.
TRADING_DAYS = 252

#: Return observations per year for other frequencies.
PERIODS_PER_YEAR: Dict[str, int] = {
    "tick": 252 * 24 * 60 * 60 * 365,
    "1m": 252 * 24 * 60,
    "5m": 252 * 24 * 12,
    "15m": 252 * 24 * 4,
    "30m": 252 * 24 * 2,
    "1h": 252 * 24,
    "4h": 252 * 6,
    "daily": 252,
    "weekly": 52,
    "monthly": 12,
}

_SQRT2 = math.sqrt(2.0)


# ---------------------------------------------------------------------------
# Basic descriptive statistics
# ---------------------------------------------------------------------------


def mean(xs: Sequence[float]) -> float:
    """Arithmetic mean. Returns 0.0 for an empty input."""
    if not xs:
        return 0.0
    return math.fsum(xs) / len(xs)


def variance(xs: Sequence[float], ddof: int = 1) -> float:
    """
    Sample variance using a compensated two-pass algorithm.

    math.fsum accumulates with error compensation, so the result stays stable
    even for return series whose mean is tiny relative to their dispersion
(the usual case: daily returns ~1e-3 with volatility ~1e-2).
    """
    n = len(xs)
    if n <= ddof:
        return 0.0
    mu = mean(xs)
    ss = math.fsum((x - mu) ** 2 for x in xs)
    return ss / (n - ddof)


def stdev(xs: Sequence[float], ddof: int = 1) -> float:
    """Sample standard deviation."""
    return math.sqrt(variance(xs, ddof=ddof))


def median(xs: Sequence[float]) -> float:
    """Sample median (mean of the two central values when even-length)."""
    n = len(xs)
    if n == 0:
        return 0.0
    s = sorted(xs)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def quantile(xs: Sequence[float], q: float) -> float:
    """
    Linear-interpolation quantile (the "type 7" definition, matching the
    numpy default and R quantile default).

    We do not use nearest-rank because published historical VaR figures from
    commercial risk systems use interpolated percentiles; matching that
    convention keeps our numbers comparable with theirs.
    """
    if not xs:
        return 0.0
    if q <= 0.0:
        return min(xs)
    if q >= 1.0:
        return max(xs)
    s = sorted(xs)
    n = len(s)
    if n == 1:
        return s[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def percentile(xs: Sequence[float], p: float) -> float:
    """Percentile wrapper (p in 0..100)."""
    return quantile(xs, p / 100.0)


def skewness(xs: Sequence[float]) -> float:
    """
    Sample skewness (Fisher-Pearson g1, bias-corrected like scipy default).

    Matches numpy/pandas skew so our output stays comparable with the rest of
    the SentienX stack. Returns 0.0 when undefined (<3 points or zero spread).
    """
    n = len(xs)
    if n < 3:
        return 0.0
    s2 = variance(xs, ddof=0)
    if s2 <= 0.0:
        return 0.0
    mu = mean(xs)
    m3 = math.fsum((x - mu) ** 3 for x in xs) / n
    g1 = m3 / (s2 ** 1.5)
    return g1 * math.sqrt(n * (n - 1.0)) / (n - 2.0)


def kurtosis_excess(xs: Sequence[float]) -> float:
    """
    Excess kurtosis (normal distribution is 0), bias-corrected like scipy.

    Returns 0.0 for degenerate input so downstream Cornish-Fisher corrections
    stay finite.
    """
    n = len(xs)
    if n < 4:
        return 0.0
    s2 = variance(xs, ddof=0)
    if s2 <= 0.0:
        return 0.0
    mu = mean(xs)
    m4 = math.fsum((x - mu) ** 4 for x in xs) / n
    g2 = m4 / (s2 ** 2) - 3.0
    return ((n + 1.0) * g2 + 6.0) * (n - 1.0) / ((n - 2.0) * (n - 3.0))


# ---------------------------------------------------------------------------
# Normal quantile / CDF
# ---------------------------------------------------------------------------


def norm_ppf(p: float) -> float:
    """
    Inverse standard-normal CDF (probit).

    Acklam rational approximation plus one Halley refinement using erfc,
    giving roughly 1e-15 relative accuracy. Fully deterministic.
    """
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    if p == 0.5:
        return 0.0

    a = (
        -3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
        1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
        6.680131188771972e01, -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
        -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low = 0.02425
    p_high = 1.0 - 0.02425

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
            ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
        )
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )

    e = 0.5 * math.erfc(-x / _SQRT2) - p
    u = e * _SQRT2 * math.pi ** 0.5 * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


def norm_cdf(x: float) -> float:
    """Standard-normal cumulative distribution function."""
    return 0.5 * math.erfc(-x / _SQRT2)


# ---------------------------------------------------------------------------
# Return series construction
# ---------------------------------------------------------------------------


def pct_returns(prices: Sequence[float]) -> List[float]:
    """
    Simple period-over-period returns from a price series.

    Simple rather than log returns deliberately: weighted sums of simple
    returns equal the exact percentage change of the portfolio, which matters
    when reconciling a VaR number against realised P&L.
    """
    out: List[float] = []
    for prev, cur in zip(prices, prices[1:]):
        if prev == 0:
            continue
        out.append(cur / prev - 1.0)
    return out


def log_returns(prices: Sequence[float]) -> List[float]:
    """Continuously-compounded (log) returns."""
    out: List[float] = []
    for prev, cur in zip(prices, prices[1:]):
        if prev <= 0 or cur <= 0:
            continue
        out.append(math.log(cur / prev))
    return out


def annualise_vol(daily_vol: float, periods_per_year: int = TRADING_DAYS) -> float:
    """Convert a per-period volatility to an annualised one (sqrt of time)."""
    return daily_vol * math.sqrt(periods_per_year)


def annualised_return(returns: Sequence[float], periods_per_year: int = TRADING_DAYS) -> float:
    """Annualised mean return (arithmetic convention)."""
    return mean(returns) * periods_per_year


# ---------------------------------------------------------------------------
# Risk ratios
# ---------------------------------------------------------------------------


def sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """
    Annualised Sharpe ratio. risk_free_rate is an annual figure, converted
    internally to a per-period rate. Zero-variance input returns 0.0 rather
    than raising or returning infinity.
    """
    if len(returns) < 2:
        return 0.0
    rf = risk_free_rate / periods_per_year
    excess = [r - rf for r in returns]
    sd = stdev(excess)
    if sd <= 0.0:
        return 0.0
    return (mean(excess) / sd) * math.sqrt(periods_per_year)


def sortino_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """
    Annualised Sortino ratio: excess return per unit of downside deviation.

    Uses the standard definition sqrt(mean(min(0, excess)^2)). The denominator
    is deliberately NOT rescaled by the count of downside observations; that
    alternative makes the ratio unstable on low-frequency samples.
    """
    n = len(returns)
    if n < 2:
        return 0.0
    rf = risk_free_rate / periods_per_year
    excess = [r - rf for r in returns]
    downside_sq = [min(0.0, e) ** 2 for e in excess]
    dd = math.sqrt(math.fsum(downside_sq) / n)
    if dd <= 0.0:
        return 0.0
    return (mean(excess) / dd) * math.sqrt(periods_per_year)


def max_drawdown(returns: Sequence[float]) -> float:
    """
    Maximum peak-to-trough drawdown as a negative fraction (e.g. -0.18).

    Computed on the equity curve implied by the return series, with the
    running peak seeded at 1.0 so a drawdown from inception is captured.
    """
    if not returns:
        return 0.0
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        if peak > 0.0:
            dd = equity / peak - 1.0
            if dd < worst:
                worst = dd
    return worst


def current_drawdown(returns: Sequence[float]) -> float:
    """Drawdown from the running peak to the latest observation."""
    if not returns:
        return 0.0
    equity = 1.0
    peak = 1.0
    for r in returns:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
    if peak <= 0.0:
        return 0.0
    return equity / peak - 1.0


def ulcer_index(returns: Sequence[float]) -> float:
    """
    Ulcer index: root-mean-square drawdown. Penalises deep and long drawdowns
    alike, unlike max drawdown which only sees the single worst excursion.
    """
    if not returns:
        return 0.0
    equity = 1.0
    peak = 1.0
    sq: List[float] = []
    for r in returns:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        sq.append((equity / peak - 1.0) ** 2 if peak > 0.0 else 0.0)
    return math.sqrt(math.fsum(sq) / len(sq))


def calmar_ratio(returns: Sequence[float], periods_per_year: int = TRADING_DAYS) -> float:
    """Annualised return divided by absolute maximum drawdown."""
    mdd = abs(max_drawdown(returns))
    if mdd <= 0.0:
        return 0.0
    return annualised_return(returns, periods_per_year) / mdd


def omega_ratio(returns: Sequence[float], threshold: float = 0.0) -> float:
    """
    Omega ratio: probability-weighted gains above a threshold divided by
    probability-weighted losses below it. Uses the whole distribution, not
    just the first two moments.
    """
    gains = [r - threshold for r in returns if r > threshold]
    losses = [threshold - r for r in returns if r <= threshold]
    if not gains or not losses:
        return 0.0
    l = math.fsum(losses)
    if l <= 0.0:
        return 0.0
    return math.fsum(gains) / l


# ---------------------------------------------------------------------------
# Covariance and correlation
# ---------------------------------------------------------------------------


def pearson_corr(xs: Sequence[float], ys: Sequence[float]) -> float:
    """
    Pearson correlation. Returns 0.0 for degenerate input (constant series).

    NaN is a legal float but poisons every downstream aggregation, so a neutral
    0.0 is returned; callers that need to distinguish "uncorrelated" from
    "unmeasurable" should inspect the input variances themselves.
    """
    n = min(len(xs), len(ys))
    if n < 2:
        return 0.0
    x = xs[:n]
    y = ys[:n]
    mx = mean(x)
    my = mean(y)
    sxy = math.fsum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = math.fsum((a - mx) ** 2 for a in x)
    syy = math.fsum((b - my) ** 2 for b in y)
    if sxx <= 0.0 or syy <= 0.0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def covariance(xs: Sequence[float], ys: Sequence[float], ddof: int = 1) -> float:
    """Sample covariance of two equal-length series."""
    n = min(len(xs), len(ys))
    if n <= ddof:
        return 0.0
    x = xs[:n]
    y = ys[:n]
    mx = mean(x)
    my = mean(y)
    return math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / (n - ddof)


def correlation_matrix(series: Dict[str, Sequence[float]]) -> Dict[str, Dict[str, float]]:
    """
    Pairwise correlation matrix keyed by asset. Series of different lengths
    are truncated to the shortest common length (pairwise deletion).
    """
    names = list(series.keys())
    out: Dict[str, Dict[str, float]] = {a: {} for a in names}
    for i, a in enumerate(names):
        out[a][a] = 1.0
        for b in names[i + 1:]:
            c = pearson_corr(series[a], series[b])
            out[a][b] = c
            out[b][a] = c
    return out


def covariance_matrix(series: Dict[str, Sequence[float]], ddof: int = 1) -> Dict[str, Dict[str, float]]:
    """Pairwise covariance matrix keyed by asset."""
    names = list(series.keys())
    out: Dict[str, Dict[str, float]] = {a: {} for a in names}
    for i, a in enumerate(names):
        out[a][a] = variance(series[a], ddof=ddof)
        for b in names[i + 1:]:
            c = covariance(series[a], series[b], ddof=ddof)
            out[a][b] = c
            out[b][a] = c
    return out


def ewma_variance(series: Sequence[float], lam: float = 0.94) -> float:
    """
    Exponentially weighted variance with decay lam (RiskMetrics daily default
    0.94), initialised with the sample variance as burn-in.

    EWMA is the standard estimator in risk systems because it reacts to
    volatility regime shifts far faster than a fixed window while still
    averaging enough history to be stable.
    """
    n = len(series)
    if n < 2:
        return 0.0
    lam = min(max(lam, 0.0), 0.999999)
    mu = mean(series)
    s = variance(series, ddof=1)
    for r in series[1:]:
        s = lam * s + (1.0 - lam) * (r - mu) ** 2
    return s


def ewma_volatility(series: Sequence[float], lam: float = 0.94) -> float:
    """EWMA standard deviation per period."""
    return math.sqrt(max(0.0, ewma_variance(series, lam)))


# ---------------------------------------------------------------------------
# Small dense matrix helpers
# ---------------------------------------------------------------------------


def zeros(n: int, m: int) -> List[List[float]]:
    """Zero-filled matrix."""
    return [[0.0] * m for _ in range(n)]


def matmul(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> List[List[float]]:
    """Matrix product for small dense matrices."""
    n = len(a)
    k = len(b)
    m = len(b[0]) if k else 0
    out = zeros(n, m)
    for i in range(n):
        ai = a[i]
        oi = out[i]
        for t in range(k):
            ait = ai[t]
            if ait == 0.0:
                continue
            bt = b[t]
            for j in range(m):
                oi[j] += ait * bt[j]
    return out


def transpose(a: Sequence[Sequence[float]]) -> List[List[float]]:
    """Matrix transpose."""
    if not a:
        return []
    n = len(a)
    m = len(a[0])
    out = zeros(m, n)
    for i in range(n):
        for j in range(m):
            out[j][i] = a[i][j]
    return out


def matvec(a: Sequence[Sequence[float]], v: Sequence[float]) -> List[float]:
    """Matrix-vector product."""
    return [math.fsum(row[j] * v[j] for j in range(len(v))) for row in a]


def inverse(a: Sequence[Sequence[float]]) -> List[List[float]]:
    """
    Inverse of a small dense matrix by Gauss-Jordan elimination with partial
    pivoting. Raises ValueError for singular input.
    """
    n = len(a)
    if n == 0:
        return []
    aug = [list(a[i]) + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-14:
            raise ValueError("singular matrix in inverse")
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        aug[col] = [x / pivot for x in aug[col]]
        for r in range(n):
            if r == col:
                continue
            f = aug[r][col]
            if f != 0.0:
                aug[r] = [x - f * y for x, y in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


def portfolio_variance(
    weights: Sequence[float],
    cov: Dict[str, Dict[str, float]],
    assets: Sequence[str],
) -> float:
    """Quadratic form w-Sigma-w using a named covariance dictionary."""
    total = 0.0
    for i, ai in enumerate(assets):
        wi = weights[i]
        if wi == 0.0:
            continue
        row = cov[ai]
        for j, aj in enumerate(assets):
            wj = weights[j]
            if wj == 0.0:
                continue
            total += wi * wj * row[aj]
    return total


__all__ = [
    "TRADING_DAYS", "PERIODS_PER_YEAR",
    "mean", "variance", "stdev", "median", "quantile", "percentile",
    "skewness", "kurtosis_excess", "norm_ppf", "norm_cdf",
    "pct_returns", "log_returns", "annualise_vol", "annualised_return",
    "sharpe_ratio", "sortino_ratio", "max_drawdown", "current_drawdown",
    "ulcer_index", "calmar_ratio", "omega_ratio",
    "pearson_corr", "covariance", "correlation_matrix", "covariance_matrix",
    "ewma_variance", "ewma_volatility",
    "zeros", "matmul", "transpose", "matvec", "inverse", "portfolio_variance",
]