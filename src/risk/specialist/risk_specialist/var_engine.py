"""var_engine: Value-at-Risk and Expected Shortfall engine."""

import math
from typing import Dict, List, Optional, Sequence

from stats_core import (
    mean, stdev, quantile, skewness, kurtosis_excess, norm_ppf,
    covariance_matrix, portfolio_variance, pct_returns, annualise_vol,
    ewma_volatility, TRADING_DAYS,
)


class VaRResult:
    def __init__(self, value, method, confidence, horizon_days, tail_sample):
        self.value = float(value)
        self.method = str(method)
        self.confidence = float(confidence)
        self.horizon_days = int(horizon_days)
        self.tail_sample = list(tail_sample)
        self._es = None

    @property
    def es(self):
        if self._es is None:
            tail = [x for x in self.tail_sample if x <= self.value]
            self._es = mean(tail) if tail else self.value
        return self._es

    def to_dict(self):
        return {
            "var": round(self.value, 6),
            "es": round(self.es, 6),
            "method": self.method,
            "confidence": self.confidence,
            "horizon_days": self.horizon_days,
        }

    def __repr__(self):
        return f"VaRResult({self.confidence*100:.0f}% {self.horizon_days}d {self.method})={self.value:.4f} ES={self.es:.4f}"

    def __float__(self):
        return self.value


def _blend_returns(weights, asset_returns):
    assets = list(asset_returns.keys())
    n = min(len(asset_returns[a]) for a in assets)
    return [sum(weights[j] * asset_returns[assets[j]][i] for j in range(len(assets))) for i in range(n)]


def _rolling_ewma_vars(returns, lam=0.94):
    """EWMA variance series. First few points use expanding window."""
    n = len(returns)
    if n < 2:
        return []
    vols = [0.0] * n
    for i in range(n):
        window = returns[max(0, i - 19):i + 1]
        if i == 0:
            vols[0] = (window[0] - mean(window)) ** 2 if len(window) > 1 else 0.0
        elif len(window) >= 2:
            vols[i] = lam * vols[i - 1] + (1 - lam) * (returns[i] - mean(returns[max(0, i - 19):i])) ** 2
    return vols


def historical_var(returns, confidence=0.95, horizon_days=1):
    """Empirical percentile VaR. No distributional assumption."""
    if not returns or len(returns) < 2:
        return VaRResult(0.0, "historical", confidence, horizon_days, [])
    raw = quantile(list(returns), 1.0 - confidence)
    if horizon_days > 1:
        raw = raw * math.sqrt(horizon_days)
    tail = [r for r in returns if r <= raw]
    return VaRResult(raw, "historical", confidence, horizon_days, list(returns))


def parametric_var(returns, confidence=0.95, horizon_days=1):
    """Gaussian parametric VaR: VaR = z * sigma."""
    if not returns or len(returns) < 2:
        return VaRResult(0.0, "parametric", confidence, horizon_days, [])
    z = norm_ppf(1.0 - confidence)
    sigma = stdev(returns)
    raw = z * sigma
    if horizon_days > 1:
        raw = raw * math.sqrt(horizon_days)
    tail = [r for r in returns if r <= raw]
    return VaRResult(raw, "parametric", confidence, horizon_days, list(returns))


def modified_var(returns, confidence=0.95, horizon_days=1):
    """Cornish-Fisher modified VaR: adjusts normal quantile for skew and kurtosis."""
    if not returns or len(returns) < 2:
        return VaRResult(0.0, "modified", confidence, horizon_days, [])
    z = norm_ppf(1.0 - confidence)
    S = skewness(returns)
    K = kurtosis_excess(returns)
    z2 = z * z
    z3 = z2 * z
    # Cornish-Fisher expansion
    z_cf = z + (z2 - 1.0) * S / 6.0 + (z3 - 3.0 * z) * K / 24.0 - (2.0 * z3 - 5.0 * z) * S * S / 36.0
    sigma = stdev(returns)
    raw = z_cf * sigma
    if horizon_days > 1:
        raw = raw * math.sqrt(horizon_days)
    tail = [r for r in returns if r <= raw]
    return VaRResult(raw, "modified", confidence, horizon_days, list(returns))


def filtered_historical_var(returns, confidence=0.95, horizon_days=1, ewma_lam=0.94):
    """Filtered Historical Simulation: scale historical returns by vol ratio, then percentile."""
    if not returns or len(returns) < 5:
        return historical_var(returns, confidence, horizon_days)
    n = len(returns)
    current_vol = ewma_volatility(returns, lam=ewma_lam)
    if current_vol <= 0:
        return historical_var(returns, confidence, horizon_days)
    vol_series = _rolling_ewma_vars(returns, lam=ewma_lam)
    scaled = []
    for i in range(n):
        v_i = vol_series[i] if i < len(vol_series) and vol_series[i] > 0 else current_vol
        scaled.append(returns[i] * (current_vol / v_i))
    raw = quantile(scaled, 1.0 - confidence)
    if horizon_days > 1:
        raw = raw * math.sqrt(horizon_days)
    tail = [s for s in scaled if s <= raw]
    return VaRResult(raw, "filtered_historical", confidence, horizon_days, scaled)


def expected_shortfall(returns, confidence=0.975, horizon_days=1):
    """Expected Shortfall (CVaR): mean of tail beyond VaR. Basel III.5 / FRTB standard."""
    if not returns or len(returns) < 3:
        return VaRResult(0.0, "expected_shortfall", confidence, horizon_days, [])
    var_pct = 1.0 - confidence
    threshold = quantile(list(returns), var_pct)
    tail = [r for r in returns if r <= threshold]
    if not tail:
        tail = [min(returns)]
    es_val = mean(tail)
    if horizon_days > 1:
        es_val = es_val * math.sqrt(horizon_days)
        threshold = threshold * math.sqrt(horizon_days)
    return VaRResult(es_val, "expected_shortfall", confidence, horizon_days, list(returns))


def relative_var(portfolio_returns, benchmark_returns, confidence=0.95, horizon_days=1):
    """Benchmark-relative VaR: risk of active returns."""
    n = min(len(portfolio_returns), len(benchmark_returns))
    active = [portfolio_returns[i] - benchmark_returns[i] for i in range(n)]
    return historical_var(active, confidence, horizon_days)


def portfolio_var_parametric(weights, asset_returns, confidence=0.95, horizon_days=1):
    """Multi-asset parametric VaR: sqrt(w Sigma w^T) * z_crit."""
    assets = list(asset_returns.keys())
    if not assets:
        return VaRResult(0.0, "portfolio_parametric", confidence, horizon_days, [])
    cov = covariance_matrix(asset_returns)
    port_var = portfolio_variance(weights, cov, assets)
    port_vol = math.sqrt(max(0.0, port_var))
    z = norm_ppf(1.0 - confidence)
    raw = z * port_vol
    if horizon_days > 1:
        raw = raw * math.sqrt(horizon_days)
    all_rets = _blend_returns(weights, asset_returns)
    tail = [r for r in all_rets if r <= raw]
    return VaRResult(raw, "portfolio_parametric", confidence, horizon_days, all_rets)


class VaRReport:
    def __init__(self, results):
        self.results = list(results)

    def best_var(self, preference="modified"):
        for m in [preference, "historical", "parametric", "modified", "filtered_historical", "expected_shortfall"]:
            for r in self.results:
                if r.method == m:
                    return r
        return self.results[0] if self.results else VaRResult(0.0, "none", 0.95, 1, [])

    def worst_var(self):
        return max(self.results, key=lambda r: abs(r.value)) if self.results else self.results[0]

    def summary(self):
        return {r.method: r.to_dict() for r in self.results}

    def __repr__(self):
        return "
".join([f"VaR Report ({len(self.results)} methods)"] + [f"  {r}" for r in self.results])


def full_var_report(
    returns,
    confidence=0.95,
    horizon_days=1,
    asset_returns=None,
    weights=None,
    benchmark_returns=None,
    ewma_lam=0.94,
):
    results = [
        historical_var(returns, confidence, horizon_days),
        parametric_var(returns, confidence, horizon_days),
        modified_var(returns, confidence, horizon_days),
        filtered_historical_var(returns, confidence, horizon_days, ewma_lam=ewma_lam),
        expected_shortfall(returns, max(0.975, confidence), horizon_days),
    ]
    if asset_returns and weights and len(asset_returns) > 1:
        results.append(portfolio_var_parametric(weights, asset_returns, confidence, horizon_days))
    if benchmark_returns:
        results.append(relative_var(returns, benchmark_returns, confidence, horizon_days))
    return VaRReport(results)


__all__ = [
    "VaRResult", "VaRReport",
    "historical_var", "parametric_var", "modified_var",
    "filtered_historical_var", "expected_shortfall",
    "relative_var", "portfolio_var_parametric",
    "full_var_report",
]
