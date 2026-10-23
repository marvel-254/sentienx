"""
portfolio_allocator
===================
Strategic capital allocation across multiple assets / strategies.

Implements five complementary sizing methodologies so the orchestrator
can choose the right one for the current regime and investor profile:

  1. Risk Parity (RP)
     Equal risk contribution from each position. The portfolio that
     equalises the marginal risk contribution of every asset. Works best
     in calm / elevated regimes.

  2. Mean-Variance (Markowitz) / Minimum Variance (MinVol)
     Classical MPT: maximise return for a given risk, or minimise risk
     for a target return. Uses the Gauss-Jordan matrix inverse from
     stats_core, so no numpy dependency.

  3. Inverse-Volatility Weighted (IVW)
     Weight ~ 1 / annualised vol. Simple, robust, avoids the quadratic
     programming of full Markowitz. Good default when correlation
     estimates are unreliable.

  4. Kelly Criterion (fractional)
     Geometric-growth optimal position size. Half-Kelly is used by
     default because full Kelly over-concentrates in practice.

  5. Black-Litterman (BL)
     Bayesian asset allocation: starts from market-implied equilibrium
     returns (reverse-optimisation of the cap-weighted portfolio) and
     blends them with analyst views to produce a posterior estimate.

All methods return a dictionary {asset_name: weight} where weights are
positive fractions summing to approximately 1.0. Positions that would
receive negative weights are floored at zero and the remaining weight
is re-normalised.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from stats_core import (
    mean, stdev, variance, ewma_volatility, pearson_corr,
    covariance_matrix, portfolio_variance, inverse, mean as _mean,
    correlation_matrix, annualise_vol, TRADING_DAYS,
)


# ----------------------------------------------------------------------------
# Allocation result
# ---------------------------------------------------------------------------

class AllocationResult:
    def __init__(
        self,
        weights: Dict[str, float],
        method: str,
        expected_return: float,
        expected_vol: float,
        sharpe: float,
        turnover: Optional[float] = None,
        notes: str = "",
    ):
        self.weights = weights          # {asset: fraction of portfolio}
        self.method = method            # e.g. "risk_parity"
        self.expected_return = expected_return
        self.expected_vol = expected_vol
        self.sharpe = sharpe
        self.turnover = turnover        # annual turnover fraction (optional)
        self.notes = notes

    def to_dict(self) -> Dict:
        return {
            "method": self.method,
            "weights": {k: round(v, 6) for k, v in self.weights.items()},
            "expected_return_ann": round(self.expected_return, 6),
            "expected_vol_ann": round(self.expected_vol, 6),
            "sharpe": round(self.sharpe, 4),
            "turnover_ann": round(self.turnover, 4) if self.turnover is not None else None,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        top = sorted(self.weights.items(), key=lambda x: -x[1])[:5]
        lines = [f"Allocation({self.method})  sharpe={self.sharpe:.3f}  vol={self.expected_vol:.3f}"]
        for a, w in top:
            lines.append(f"  {a}: {w*100:.2f}%")
        return "\n".join(lines)

    def __float__(self) -> float:
        return sum(self.weights.values())  # should be ~1.0


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise(weights: Dict[str, float]) -> Dict[str, float]:
    """Floor negative weights at 0 and re-normalise to sum=1."""
    assets = list(weights.keys())
    raw = [max(0.0, weights.get(a, 0.0)) for a in assets]
    total = sum(raw)
    if total <= 0.0:
        return {a: 1.0 / len(assets) for a in assets}  # uniform fallback
    return {a: w / total for a, w in zip(assets, raw)}


def _portfolio_stats(
    weights: Dict[str, float],
    asset_returns: Dict[str, Sequence[float]],
    cov: Dict[str, Dict[str, float]],
    risk_free: float = 0.0,
) -> Tuple[float, float, float]:
    """Expected return, vol, Sharpe for a weight vector."""
    assets = list(asset_returns.keys())
    w_list = [weights.get(a, 0.0) for a in assets]
    ret_list = [asset_returns[a] for a in assets]

    # Annualised expected return (mean of blended series)
    blended = _blend_returns(w_list, asset_returns)
    ann_ret = mean(blended) * TRADING_DAYS

    # Portfolio volatility
    port_var = portfolio_variance(w_list, cov, assets)
    ann_vol = annualise_vol(math.sqrt(max(0.0, port_var)))

    # Sharpe
    if ann_vol > 0.0:
        sharpe = (ann_ret - risk_free) / ann_vol
    else:
        sharpe = 0.0

    return ann_ret, ann_vol, sharpe


def _blend_returns(weights, asset_returns) -> List[float]:
    assets = list(asset_returns.keys())
    n = min(len(asset_returns[a]) for a in assets) if assets else 0
    if n == 0:
        return []
    out = []
    for i in range(n):
        out.append(sum(weights[j] * asset_returns[assets[j]][i]
                       for j in range(len(assets))))
    return out


# ---------------------------------------------------------------------------
# Method 1: Risk Parity
# ---------------------------------------------------------------------------

def risk_parity(
    asset_returns: Dict[str, Sequence[float]],
    vol_window: int = 60,
    risk_free: float = 0.0,
) -> AllocationResult:
    """
    Risk Parity: each asset contributes equally to total portfolio risk.

    Algorithm (Bruderer & Chaker, 2013):
    1. Annualise volatilities from the supplied return series.
    2. Form the covariance matrix.
    3. Solve: w_i * (Sigma w)_i / (w^T Sigma w) = 1/N  for all i.
       Iterative algorithm: w_i_next = (w_i * risk_contrib_i) / sum(...).
       Converges in ~20 iterations for most matrices.

    Returns equal risk contribution weights.
    """
    assets = list(asset_returns.keys())
    n = len(assets)
    if n == 0:
        return AllocationResult({}, "risk_parity", 0.0, 0.0, 0.0, notes="no assets")
    if n == 1:
        return AllocationResult({assets[0]: 1.0}, "risk_parity", 0.0, 0.0, 0.0,
                                 notes="single asset")

    # Annualised volatilities
    vols = {a: annualise_vol(stdev(asset_returns[a])) for a in assets}
    cov = covariance_matrix(asset_returns)

    # Initialise equal weights
    w = {a: 1.0 / n for a in assets}
    for _ in range(100):  # iterative solver, usually converges < 20 iter
        w_list = [w[a] for a in assets]
        port_var = portfolio_variance(w_list, cov, assets)
        port_vol = math.sqrt(max(port_var, 1e-20))

        # Marginal risk contributions
        new_w = {}
        for i, a in enumerate(assets):
            mrc = sum(cov[a][b] * w_list[j]
                      for j, b in enumerate(assets)) / port_vol
            # Target: equal risk contribution = port_vol / n
            target_rc = port_vol / n
            if mrc > 0.0:
                new_w[a] = w[a] * (target_rc / mrc)
            else:
                new_w[a] = w[a]

        w = _normalise(new_w)

    ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)
    return AllocationResult(
        w, "risk_parity", ann_ret, ann_vol, sharpe,
        notes=f"risk parity over {n} assets"
    )


# ---------------------------------------------------------------------------
# Method 2: Mean-Variance / Minimum Variance
# ---------------------------------------------------------------------------

def mean_variance(
    asset_returns: Dict[str, Sequence[float]],
    target_return: Optional[float] = None,
    risk_free: float = 0.0,
    allow_short: bool = False,
) -> AllocationResult:
    """
    Classical Markowitz Mean-Variance optimisation.

    If target_return is None: minimises portfolio variance (MinVol portfolio).
    If target_return is set: finds the portfolio on the efficient frontier
    with that expected return.

    Solves via the two-fund theorem using the closed-form analytic solution
    (no quadratic programming needed for the unconstrained case).
    Short positions are disabled by default (can be enabled with allow_short).
    """
    assets = list(asset_returns.keys())
    n = len(assets)
    if n == 0:
        return AllocationResult({}, "mean_variance", 0.0, 0.0, 0.0)
    if n == 1:
        return AllocationResult({assets[0]: 1.0}, "mean_variance", 0.0, 0.0, 0.0)

    # Vector of annualised expected returns
    mu = {a: mean(asset_returns[a]) * TRADING_DAYS for a in assets}
    cov = covariance_matrix(asset_returns)

    # Long-only minimum variance (no target return) via closed form
    if target_return is None:
        w = _min_variance_weights(cov, assets)
    else:
        w = _efficient_portfolio_weights(mu, cov, assets, target_return)

    if not allow_short:
        w = _normalise(w)  # floors negatives

    ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)
    method = "min_variance" if target_return is None else "mean_variance"
    return AllocationResult(
        w, method, ann_ret, ann_vol, sharpe,
        notes=f"{method}  target_return={target_return}"
    )


def _min_variance_weights(
    cov: Dict[str, Dict[str, float]],
    assets: List[str],
) -> Dict[str, float]:
    """Closed-form minimum-variance weights: w ~ Sigma^{-1} 1."""
    n = len(assets)
    if n == 0:
        return {}
    if n == 1:
        return {assets[0]: 1.0}

    # Build dense covariance matrix
    sigma = [[cov[a][b] for b in assets] for a in assets]
    try:
        sigma_inv = inverse(sigma)
    except ValueError:
        # Singular matrix: fall back to equal weights
        return {a: 1.0 / n for a in assets}

    # w ~ Sigma^{-1} 1
    ones = [1.0] * n
    inv_ones = [sum(sigma_inv[i][j] * ones[j] for j in range(n)) for i in range(n)]
    total = sum(inv_ones)
    if total <= 0.0:
        return {a: 1.0 / n for a in assets}
    return {a: inv_ones[i] / total for i, a in enumerate(assets)}


def _efficient_portfolio_weights(
    mu: Dict[str, float],
    cov: Dict[str, Dict[str, float]],
    assets: List[str],
    target_return: float,
) -> Dict[str, float]:
    """
    Analytic efficient portfolio (two-fund theorem):

    Solve for w on the efficient frontier at target_return.
    Uses the global minimum-variance portfolio (g) and the tangency portfolio (t)
    shifted to meet the target return:

        w = g + lambda * (t - g)

    where lambda is chosen so that w^T mu = target_return.
    """
    n = len(assets)
    if n == 0:
        return {}
    if n == 1:
        return {assets[0]: 1.0}

    sigma = [[cov[a][b] for b in assets] for a in assets]
    mu_vec = [mu[a] for a in assets]

    try:
        sigma_inv = inverse(sigma)
    except ValueError:
        return {a: 1.0 / n for a in assets}

    ones = [1.0] * n
    inv_ones = [sum(sigma_inv[i][j] * ones[j] for j in range(n)) for i in range(n)]
    inv_mu = [sum(sigma_inv[i][j] * mu_vec[j] for j in range(n)) for i in range(n)]

    # Global minimum variance
    t1 = sum(inv_ones[i] * ones[i] for i in range(n))
    t2 = sum(inv_ones[i] * mu_vec[i] for i in range(n))
    t3 = sum(mu_vec[i] * ones[i] for i in range(n))
    t4 = sum(mu_vec[i] * mu_vec[i] for i in range(n))

    denom = t1 * t4 - t2 * t3
    if abs(denom) < 1e-20:
        return {a: 1.0 / n for a in assets}

    # Minimum variance weights
    w_g = [inv_ones[i] / t1 for i in range(n)]

    # Tangency portfolio weights
    inv_ones_dot_mu = t2
    if abs(inv_ones_dot_mu) < 1e-20:
        return dict(zip(assets, w_g))
    w_t = [inv_mu[i] / inv_ones_dot_mu for i in range(n)]

    # Efficient portfolio
    g_return = sum(w_g[i] * mu_vec[i] for i in range(n))
    t_return = sum(w_t[i] * mu_vec[i] for i in range(n))
    denom_ret = t_return - g_return
    if abs(denom_ret) < 1e-20:
        return dict(zip(assets, w_g))

    lam = (target_return - g_return) / denom_ret
    w_eff = [w_g[i] + lam * (w_t[i] - w_g[i]) for i in range(n)]
    return dict(zip(assets, w_eff))


# ---------------------------------------------------------------------------
# Method 3: Inverse-Volatility Weighted (IVW)
# ---------------------------------------------------------------------------

def inverse_volatility_weighted(
    asset_returns: Dict[str, Sequence[float]],
    vol_window: int = 60,
    risk_free: float = 0.0,
    ewma_lam: float = 0.94,
) -> AllocationResult:
    """
    Weights proportional to 1 / annualised volatility.

    Formula: w_i = (1 / sigma_i) / sum_j(1 / sigma_j)

    Robust when correlation estimates are noisy. IVW is the basis of
    many popular factor portfolios (e.g. RAFI, low-vol indexes).
    """
    assets = list(asset_returns.keys())
    n = len(assets)
    if n == 0:
        return AllocationResult({}, "inverse_vol", 0.0, 0.0, 0.0)

    inv_vols = []
    for a in assets:
        series = asset_returns[a]
        if len(series) < 2:
            inv_vols.append(0.0)
        else:
            ann_vol = annualise_vol(stdev(series))
            if ann_vol > 1e-8:
                inv_vols.append(1.0 / ann_vol)
            else:
                inv_vols.append(0.0)

    total = sum(inv_vols)
    if total <= 0.0:
        return AllocationResult({a: 1.0 / n for a in assets}, "inverse_vol",
                                0.0, 0.0, 0.0, notes="fallback equal weight")

    w = {a: iv / total for a, iv in zip(assets, inv_vols)}
    cov = covariance_matrix(asset_returns)
    ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)

    return AllocationResult(
        w, "inverse_vol", ann_ret, ann_vol, sharpe,
        notes=f"IVW over {n} assets  lam={ewma_lam}"
    )


# ---------------------------------------------------------------------------
# Method 4: Kelly Criterion
# ---------------------------------------------------------------------------

def kelly_allocator(
    asset_returns: Dict[str, Sequence[float]],
    fraction: float = 0.5,
    risk_free: float = 0.0,
) -> AllocationResult:
    """
    Full-Kelly position sizing from win rate and average return ratios.

    Kelly % = (bp - q) / b
      b = odds received on the winning trade (e.g. 2.0 for 2:1 R/R)
      p = win probability
      q = 1 - p

    In practice, fractional Kelly (0.5 = half-Kelly) is used because
    the full Kelly over-concentrates and has high Sharpe variance.

    The estimator uses the realised win rate and average win/loss as
    proxies for p and b.
    """
    assets = list(asset_returns.keys())
    n = len(assets)
    if n == 0:
        return AllocationResult({}, "kelly", 0.0, 0.0, 0.0)
    if n == 1:
        return AllocationResult({assets[0]: 1.0}, "kelly", 0.0, 0.0, 0.0)

    kelly_fractions = {}
    for a in assets:
        rets = asset_returns[a]
        if len(rets) < 5:
            kelly_fractions[a] = 0.0
            continue
        avg_ret = mean(rets)
        # Estimate win rate as fraction of positive returns
        wins = [r for r in rets if r > 0]
        losses = [r for r in rets if r < 0]
        p = len(wins) / max(len(rets), 1)
        q = 1.0 - p
        avg_win = abs(mean(wins)) if wins else 0.0
        avg_loss = abs(mean(losses)) if losses else 1e-9
        b = avg_win / max(avg_loss, 1e-12)
        raw = (b * p - q) / max(b, 1e-12)
        # Half-Kelly by default; also cap at 20% max per asset
        kelly_fractions[a] = max(0.0, min(raw * fraction, 0.20))

    w = _normalise(kelly_fractions)
    cov = covariance_matrix(asset_returns)
    ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)

    return AllocationResult(
        w, "kelly", ann_ret, ann_vol, sharpe,
        notes=f"fractional Kelly ({fraction}x) over {n} assets"
    )


# ---------------------------------------------------------------------------
# Method 5: Black-Litterman
# ---------------------------------------------------------------------------

def black_litterman(
    market_weights: Dict[str, float],
    market_cov: Dict[str, Dict[str, float]],
    asset_returns: Dict[str, Sequence[float]],
    views: Optional[Dict[str, float]] = None,
    view_confidence: float = 0.5,
    risk_aversion: float = 2.5,
    risk_free: float = 0.0,
) -> AllocationResult:
    """
    Black-Litterman Bayesian asset allocation (Black & Litterman, 1992).

    Steps:
    1. Reverse-optimise the cap-weighted market portfolio to recover
       implied equilibrium returns:  mu = lambda * Sigma * w_mkt
    2. Specify investor views (optional) as returns overrides.
    3. Blend equilibrium and view returns using Bayesian posterior:
       mu_bl = (Sigma^{-1} + tau * P^T Omega^{-1} P)^{-1}
               (Sigma^{-1} mu + tau * P^T Omega^{-1} q)
       where P = view matrix, q = view returns, tau = 1/T.
    4. Compute optimal weights from posterior returns via mean-variance.

    Requires a market cap-weighted portfolio as prior (market_weights).
    If no views are supplied, the result defaults to the market-implied
    weights (a sensible, diversified starting point).
    """
    assets = list(market_weights.keys())
    n = len(assets)
    if n == 0:
        return AllocationResult({}, "black_litterman", 0.0, 0.0, 0.0)
    if n == 1:
        return AllocationResult({assets[0]: 1.0}, "black_litterman", 0.0, 0.0, 0.0)

    if not views:
        # No views: BL collapses to the market-implied weights
        cov = market_cov
        w = _normalise(market_weights)
        ret_dict = {a: mean(asset_returns.get(a, [0.0])) * TRADING_DAYS for a in assets}
        ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)
        return AllocationResult(
            w, "black_litterman", ann_ret, ann_vol, sharpe,
            notes="market-implied weights (no views provided)"
        )

    # Implied equilibrium returns: mu = lambda * Sigma * w_mkt
    sigma = [[market_cov[a][b] for b in assets] for a in assets]
    w_mkt = [market_weights.get(a, 0.0) for a in assets]

    # mu_eq = lambda * Sigma * w_mkt
    mu_eq = [risk_aversion * sum(sigma[i][j] * w_mkt[j] for j in range(n))
             for i in range(n)]

    # Build view matrix P and observed view returns q
    # Views format: {asset: expected_return}
    view_assets = list(views.keys())
    k = len(view_assets)
    if k == 0:
        return AllocationResult(_normalise(market_weights), "black_litterman",
                                mean(mu_eq), 0.0, 0.0,
                                notes="no valid views")

    P = [[0.0] * n for _ in range(k)]
    q = []
    for i, va in enumerate(view_assets):
        if va in market_weights:
            idx = assets.index(va)
            P[i][idx] = 1.0
        q.append(views[va])

    tau = 1.0 / max(len(next(iter(asset_returns.values()), [])), 252.0)
    tau = min(tau, 0.1)  # cap tau to avoid numeric instability

    # Omega = tau * P * Sigma * P^T  (diagonal uncertainty)
    # Simplified: use diagonal of full matrix for robustness
    try:
        sigma_inv = inverse(sigma)
    except ValueError:
        return AllocationResult(_normalise(market_weights), "black_litterman",
                                mean(mu_eq), 0.0, 0.0,
                                notes="singular cov in BL, reverted to mkt weights")

    # Posterior mean: mu_bl = (Sigma_inv + tau P^T Omega^{-1} P)^{-1}
    #                        * (Sigma_inv mu_eq + tau P^T Omega^{-1} q)
    # Omega simplified as diagonal: Omega_ii = tau * Var(P_i * Sigma * P_i^T)
    Omega_diag = []
    for i in range(k):
        row = P[i]
        var_pi = sum(row[j] * sum(sigma[j][m] * row[m] for m in range(n))
                     for j in range(n))
        Omega_diag.append(tau * max(abs(var_pi), 1e-12))

    # Compute P^T Omega^{-1} P and P^T Omega^{-1} q
    P_t_Om_P = [[0.0] * n for _ in range(n)]
    P_t_Om_q = [0.0] * n
    for j in range(n):
        for l in range(n):
            for i in range(k):
                if Omega_diag[i] > 0:
                    P_t_Om_P[j][l] += P[i][j] * P[i][l] / Omega_diag[i]
        for i in range(k):
            if Omega_diag[i] > 0:
                P_t_Om_q[j] += P[i][j] * q[i] / Omega_diag[i]

    # (Sigma_inv + tau * P^T Omega^{-1} P)
    combined = [[sigma_inv[i][j] + tau * P_t_Om_P[i][j]
                 for j in range(n)] for i in range(n)]

    try:
        combined_inv = inverse(combined)
    except ValueError:
        return AllocationResult(_normalise(market_weights), "black_litterman",
                                mean(mu_eq), 0.0, 0.0,
                                notes="singular combined in BL")

    # Posterior returns
    term1 = [sum(combined_inv[i][j] * sigma_inv[j][m] * mu_eq[m]
                 for j in range(n)) for i in range(n)]
    term2 = [sum(combined_inv[i][j] * tau * P_t_Om_q[j]
                 for j in range(n)) for i in range(n)]
    mu_bl = [term1[i] + term2[i] for i in range(n)]

    # Optimal weights from posterior returns: w_bl ~ Sigma^{-1} mu_bl
    w_bl_raw = [sum(sigma_inv[i][j] * mu_bl[j] for j in range(n)) for i in range(n)]
    # Scale by risk aversion
    w_bl = [w / risk_aversion for w in w_bl_raw]
    w = _normalise({a: max(0.0, w_bl[i]) for i, a in enumerate(assets)})

    cov = market_cov
    ann_ret, ann_vol, sharpe = _portfolio_stats(w, asset_returns, cov, risk_free)
    return AllocationResult(
        w, "black_litterman", ann_ret, ann_vol, sharpe,
        notes=f"BL with {len(views)} view(s), confidence={view_confidence}"
    )


# ---------------------------------------------------------------------------
# Convenience: all-methods report
# ---------------------------------------------------------------------------

def full_allocation_report(
    asset_returns: Dict[str, Sequence[float]],
    market_weights: Optional[Dict[str, float]] = None,
    views: Optional[Dict[str, float]] = None,
    risk_free: float = 0.0,
    target_return: Optional[float] = None,
) -> Dict[str, AllocationResult]:
    """
    Run all five allocators and return a dictionary of results.

    market_weights: optional cap-weighted market portfolio for BL prior.
    views: optional {asset: expected_return} overrides for Black-Litterman.
    """
    results = {}

    try:
        results["risk_parity"] = risk_parity(asset_returns, risk_free=risk_free)
    except Exception as e:
        results["risk_parity"] = AllocationResult({}, "risk_parity", 0, 0, 0, notes=f"error: {e}")

    try:
        results["mean_variance"] = mean_variance(
            asset_returns, target_return=target_return, risk_free=risk_free
        )
    except Exception as e:
        results["mean_variance"] = AllocationResult({}, "mean_variance", 0, 0, 0, notes=f"error: {e}")

    try:
        results["inverse_vol"] = inverse_volatility_weighted(asset_returns, risk_free=risk_free)
    except Exception as e:
        results["inverse_vol"] = AllocationResult({}, "inverse_vol", 0, 0, 0, notes=f"error: {e}")

    try:
        results["kelly"] = kelly_allocator(asset_returns, risk_free=risk_free)
    except Exception as e:
        results["kelly"] = AllocationResult({}, "kelly", 0, 0, 0, notes=f"error: {e}")

    if market_weights:
        try:
            cov = covariance_matrix(asset_returns)
            results["black_litterman"] = black_litterman(
                market_weights, cov, asset_returns,
                views=views, risk_free=risk_free
            )
        except Exception as e:
            results["black_litterman"] = AllocationResult({}, "black_litterman", 0, 0, 0, notes=f"error: {e}")

    return results


__all__ = [
    "AllocationResult",
    "risk_parity", "mean_variance", "inverse_volatility_weighted",
    "kelly_allocator", "black_litterman", "full_allocation_report",
]
