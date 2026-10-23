"""
stress_tester: Systematic stress testing for multi-asset portfolios.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from stats_core import (
    mean, stdev, percentile, max_drawdown, pearson_corr,
    covariance_matrix, portfolio_variance, correlation_matrix,
    annualise_vol, TRADING_DAYS,
)

SCENARIOS: Dict[str, Dict[str, float]] = {
    "2008_GFC":       {"major_forex": -0.030, "jpy": -0.050, "indices": -0.060, "commodities": -0.040},
    "2020_COVID":     {"major_forex": -0.015, "jpy": -0.030, "indices": -0.080, "commodities": -0.050},
    "2022_RATE_SHOCK":{"major_forex": -0.010, "jpy": -0.040, "indices": -0.035, "commodities": -0.020},
    "2024_JPY_UNWIND":{"major_forex": -0.008, "jpy": -0.060, "indices": -0.020, "commodities": -0.010},
    "2000_DOTCOM":    {"major_forex": -0.010, "jpy": -0.015, "indices": -0.050, "commodities": -0.020},
    "1997_ASIAN_FX":  {"major_forex": -0.015, "jpy": -0.050, "indices": -0.040, "commodities": -0.030},
}

DEFAULT_CAT = "major_forex"

def _cat(symbol: str) -> str:
    s = symbol.upper()
    if any(x in s for x in ["JPY", "CHF", "NZD"]):  return "jpy"
    if any(x in s for x in ["SPY", "QQQ", "NDX", "FTSE", "DAX", "NIFTY", "NIKKEI"]):  return "indices"
    if any(x in s for x in ["XAU", "GOLD", "OIL", "CRUDE", "BRENT"]):  return "commodities"
    return DEFAULT_CAT


class PortfolioExposure:
    def __init__(self, weights: Optional[Dict[str, float]] = None,
                 beta: Optional[Dict[str, float]] = None,
                 total_value: float = 1_000_000.0):
        self.weights = weights or {}
        self.beta    = beta    or {}
        self.total_value = total_value

    def symbols(self) -> List[str]:  return list(self.weights.keys())
    def w(self, s: str) -> float:    return self.weights.get(s, 0.0)
    def b(self, s: str) -> float:    return self.beta.get(s, 1.0)


class StressResult:
    def __init__(self, scenario: str, loss_pct: float, loss_dol: float,
                 worst_loss: float, worst_sym: str, breached: Dict[str, bool],
                 action: str, notes: str = "", impacts: Optional[Dict[str,float]] = None):
        self.scenario        = scenario
        self.loss_pct        = loss_pct
        self.loss_dol        = loss_dol
        self.worst_loss      = worst_loss
        self.worst_sym       = worst_sym
        self.breached        = breached
        self.action          = action
        self.notes           = notes
        self.impacts         = impacts or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "loss_pct":      round(self.loss_pct, 4),
            "loss_dollars":  round(self.loss_dol, 2),
            "worst_loss":    round(self.worst_loss, 4),
            "worst_symbol":  self.worst_sym,
            "breached":      {k:v for k,v in self.breached.items() if v},
            "action":        self.action,
            "notes":         self.notes,
            "impacts":       {k: round(v,4) for k,v in self.impacts.items()},
        }

    def __repr__(self): return f"StressResult({self.scenario}) loss={self.loss_pct*100:.2f}% action={self.action}"
    def __float__(self): return self.loss_pct


def _loss(portfolio: PortfolioExposure, shocks: Dict[str, float],
          corr_boost: float = 0.0, name: str = "custom") -> StressResult:
    symbols  = portfolio.symbols()
    tv       = portfolio.total_value
    total    = 0.0
    worst_l  = 0.0
    worst_s  = ""
    impacts: Dict[str,float] = {}
    for sym in symbols:
        cat   = _cat(sym)
        shock = shocks.get(cat, shocks.get(DEFAULT_CAT, -0.02)) * (1.0 + corr_boost)
        pl    = portfolio.w(sym) * shock
        impacts[sym] = pl
        total += pl
        if pl < worst_l: worst_l = pl; worst_s = sym
    dol      = total * tv
    breach   = {"drawdown_10pct": abs(total) > 0.10, "drawdown_20pct": abs(total) > 0.20,
                 "single_pos_10pct": abs(worst_l) > 0.10}
    action   = "REDUCE" if abs(total) > 0.05 else "NO_ACTION"
    return StressResult(name, total, dol, worst_l, worst_s, breach, action,
                        f"corr_boost={corr_boost:.2f}", impacts)


def apply_scenario(portfolio: PortfolioExposure, scenario: Dict[str,float],
                   name: str = "custom", corr_boost: float = 0.0) -> StressResult:
    return _loss(portfolio, scenario, corr_boost, name)


def correlation_breakdown(portfolio: PortfolioExposure, shock: float = -0.03) -> StressResult:
    shocks = {s: shock for s in portfolio.symbols()}
    return _loss(portfolio, shocks, 0.0, "CORRELATION_BREAKDOWN")


def vol_spike(portfolio: PortfolioExposure,
              asset_returns: Dict[str, Sequence[float]],
              mult: float = 2.0) -> StressResult:
    symbols = portfolio.symbols()
    total   = 0.0
    worst_l = 0.0
    worst_s = ""
    impacts: Dict[str,float] = {}
    for sym in symbols:
        vol  = stdev(asset_returns.get(sym, [0.0]))
        pl   = portfolio.w(sym) * (-vol * mult)
        impacts[sym] = pl
        total += pl
        if pl < worst_l: worst_l = pl; worst_s = sym
    breach = {"vol_spike": abs(total) > 0.10}
    action = "REDUCE" if abs(total) > 0.05 else "NO_ACTION"
    return StressResult(f"VOL_SPIKE_{mult}x", total, total * portfolio.total_value,
                        worst_l, worst_s, breach, action,
                        f"{mult}x vol  1-sigma loss", impacts)


def conc_shock(portfolio: PortfolioExposure, drop: float = 0.30) -> StressResult:
    syms  = portfolio.symbols()
    top   = max(syms, key=lambda s: abs(portfolio.w(s)), default="")
    total = 0.0
    worst_l = 0.0; worst_s = ""
    impacts: Dict[str,float] = {}
    for s in syms:
        pl = portfolio.w(s) * (-drop if s == top else -drop*0.10)
        impacts[s] = pl; total += pl
        if pl < worst_l: worst_l = pl; worst_s = s
    breach = {"conc_shock": True, "max_concentration": portfolio.w(top) > 0.25}
    action = "REDUCE" if abs(total) > 0.05 else "NO_ACTION"
    return StressResult(f"CONC_{int(drop*100)}pct_{top}", total,
                        total * portfolio.total_value, worst_l, worst_s,
                        breach, action, f"top position ({top}) drops {drop*100:.0f}%", impacts)


def beta_stress(portfolio: PortfolioExposure,
                asset_returns: Dict[str, Sequence[float]],
                market_returns: Optional[Sequence[float]] = None,
                shock: float = -0.05) -> StressResult:
    total = 0.0; worst_l = 0.0; worst_s = ""
    impacts: Dict[str,float] = {}
    for sym in portfolio.symbols():
        b = portfolio.b(sym)
        if market_returns and sym in asset_returns:
            b = abs(pearson_corr(asset_returns[sym], market_returns))
        pl = portfolio.w(sym) * b * shock
        impacts[sym] = pl; total += pl
        if pl < worst_l: worst_l = pl; worst_s = sym
    breach = {"beta_stress": abs(total) > 0.10}
    action = "REDUCE" if abs(total) > 0.05 else "NO_ACTION"
    return StressResult("BETA_STRESS", total, total * portfolio.total_value,
                        worst_l, worst_s, breach, action, "beta-scaled market shock", impacts)


def custom_scenario(portfolio: PortfolioExposure,
                    shocks: Dict[str,float], name: str = "CUSTOM") -> StressResult:
    return _loss(portfolio, shocks, 0.0, name)


class StressReport:
    def __init__(self, results: List[StressResult]):
        self.results = results
    def worst(self) -> StressResult:
        return min(self.results, key=lambda r: r.loss_pct) if self.results else \
               StressResult("none", 0.0, 0.0, 0.0, "", {}, "NO_ACTION")
    def summary(self) -> Dict[str, Any]:
        w = self.worst()
        return {
            "scenarios":    len(self.results),
            "reduce_count": sum(1 for r in self.results if r.action == "REDUCE"),
            "worst_scenario": w.scenario,
            "worst_loss_pct": round(w.loss_pct, 4),
            "actions":       {r.scenario: r.action for r in self.results},
            "details":       [r.to_dict() for r in self.results],
        }
    def __repr__(self): return f"StressReport({len(self.results)} scenarios)"


def full_stress_test(
    portfolio: PortfolioExposure,
    asset_returns: Optional[Dict[str, Sequence[float]]] = None,
    market_returns: Optional[Sequence[float]] = None,
    corr_boost: float = 0.30,
) -> StressReport:
    results: List[StressResult] = []
    for name, scen in SCENARIOS.items():
        results.append(apply_scenario(portfolio, scen, name, corr_boost))
    results.append(correlation_breakdown(portfolio))
    if asset_returns:
        results.extend([vol_spike(portfolio, asset_returns, m) for m in [2.0, 3.0]])
    results.extend([conc_shock(portfolio, d) for d in [0.20, 0.30, 0.50]])
    if asset_returns:
        results.append(beta_stress(portfolio, asset_returns, market_returns))
    return StressReport(results)


__all__ = [
    "PortfolioExposure", "StressResult", "StressReport",
    "SCENARIOS",
    "apply_scenario", "correlation_breakdown", "vol_spike",
    "conc_shock", "beta_stress", "custom_scenario",
    "full_stress_test",
]
