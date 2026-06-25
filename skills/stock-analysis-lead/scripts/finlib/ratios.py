"""finlib.ratios — deterministic financial-ratio engine.

Every ratio is a named function whose name *is* its formula contract. The point
is to make it impossible to mislabel a metric: you cannot compute an EV multiple
without passing debt and cash, because the function signature demands them.

All values are plain floats in consistent units (USD billions for $ figures,
fractions for margins/percentages unless noted). No external dependencies.

Each public function returns a Metric dict:
    {"name", "value", "formula", "inputs", "kind"}
so the linter can recompute and a report can show the bridge.
"""
from __future__ import annotations

from typing import Optional


def _metric(name: str, value: Optional[float], formula: str, inputs: dict, kind: str) -> dict:
    return {"name": name, "value": value, "formula": formula, "inputs": dict(inputs), "kind": kind}


# --- Enterprise value: the single most-mislabeled concept ---------------------

def enterprise_value(mktcap: float, total_debt: float, cash_and_sti: float) -> dict:
    """EV = market cap + total debt - cash & short-term investments.

    For a net-cash company (cash > debt) EV < mktcap, which is exactly why an
    EV multiple must never be computed off market cap alone.
    """
    ev = mktcap + total_debt - cash_and_sti
    return _metric("enterprise_value", ev, "mktcap + total_debt - cash_and_sti",
                   {"mktcap": mktcap, "total_debt": total_debt, "cash_and_sti": cash_and_sti},
                   "enterprise_value")


# --- Price-based multiples (numerator = market cap / price) -------------------

def pe(price: float, eps: float) -> dict:
    v = price / eps if eps else None
    return _metric("pe", v, "price / eps", {"price": price, "eps": eps}, "price_multiple")


def pfcf(mktcap: float, fcf: float) -> dict:
    """Price / Free Cash Flow. numerator is MARKET CAP, not EV."""
    v = mktcap / fcf if fcf else None
    return _metric("pfcf", v, "mktcap / fcf", {"mktcap": mktcap, "fcf": fcf}, "price_multiple")


def ps(mktcap: float, revenue: float) -> dict:
    v = mktcap / revenue if revenue else None
    return _metric("ps", v, "mktcap / revenue", {"mktcap": mktcap, "revenue": revenue}, "price_multiple")


# --- EV-based multiples (numerator = enterprise value) ------------------------

def ev_fcf(mktcap: float, total_debt: float, cash_and_sti: float, fcf: float) -> dict:
    ev = enterprise_value(mktcap, total_debt, cash_and_sti)["value"]
    v = ev / fcf if fcf else None
    return _metric("ev_fcf", v, "(mktcap + total_debt - cash_and_sti) / fcf",
                   {"mktcap": mktcap, "total_debt": total_debt, "cash_and_sti": cash_and_sti, "fcf": fcf},
                   "ev_multiple")


def ev_ebitda(mktcap: float, total_debt: float, cash_and_sti: float, ebitda: float) -> dict:
    ev = enterprise_value(mktcap, total_debt, cash_and_sti)["value"]
    v = ev / ebitda if ebitda else None
    return _metric("ev_ebitda", v, "(mktcap + total_debt - cash_and_sti) / ebitda",
                   {"mktcap": mktcap, "total_debt": total_debt, "cash_and_sti": cash_and_sti, "ebitda": ebitda},
                   "ev_multiple")


def ev_sales(mktcap: float, total_debt: float, cash_and_sti: float, revenue: float) -> dict:
    ev = enterprise_value(mktcap, total_debt, cash_and_sti)["value"]
    v = ev / revenue if revenue else None
    return _metric("ev_sales", v, "(mktcap + total_debt - cash_and_sti) / revenue",
                   {"mktcap": mktcap, "total_debt": total_debt, "cash_and_sti": cash_and_sti, "revenue": revenue},
                   "ev_multiple")


# --- Growth-adjusted ----------------------------------------------------------

def peg(forward_pe: float, eps_growth_pct: float) -> dict:
    """PEG = forward P/E / (expected EPS growth in PERCENT points, e.g. 18 not 0.18)."""
    v = forward_pe / eps_growth_pct if eps_growth_pct else None
    return _metric("peg", v, "forward_pe / eps_growth_pct",
                   {"forward_pe": forward_pe, "eps_growth_pct": eps_growth_pct}, "growth_adjusted")


# --- Leverage / cash ----------------------------------------------------------

def net_debt(total_debt: float, cash_and_sti: float) -> dict:
    return _metric("net_debt", total_debt - cash_and_sti, "total_debt - cash_and_sti",
                   {"total_debt": total_debt, "cash_and_sti": cash_and_sti}, "leverage")


def net_debt_ebitda(total_debt: float, cash_and_sti: float, ebitda: float) -> dict:
    nd = total_debt - cash_and_sti
    v = nd / ebitda if ebitda else None
    return _metric("net_debt_ebitda", v, "(total_debt - cash_and_sti) / ebitda",
                   {"total_debt": total_debt, "cash_and_sti": cash_and_sti, "ebitda": ebitda}, "leverage")


# --- Margins / intensity (return FRACTIONS; multiply by 100 for %) ------------

def fcf_margin(fcf: float, revenue: float) -> dict:
    v = fcf / revenue if revenue else None
    return _metric("fcf_margin", v, "fcf / revenue", {"fcf": fcf, "revenue": revenue}, "margin")


def capex_intensity(capex: float, revenue: float) -> dict:
    v = capex / revenue if revenue else None
    return _metric("capex_intensity", v, "capex / revenue", {"capex": capex, "revenue": revenue}, "intensity")


def gross_margin(gross_profit: float, revenue: float) -> dict:
    v = gross_profit / revenue if revenue else None
    return _metric("gross_margin", v, "gross_profit / revenue",
                   {"gross_profit": gross_profit, "revenue": revenue}, "margin")


def operating_margin(operating_income: float, revenue: float) -> dict:
    v = operating_income / revenue if revenue else None
    return _metric("operating_margin", v, "operating_income / revenue",
                   {"operating_income": operating_income, "revenue": revenue}, "margin")


def net_margin(net_income: float, revenue: float) -> dict:
    v = net_income / revenue if revenue else None
    return _metric("net_margin", v, "net_income / revenue",
                   {"net_income": net_income, "revenue": revenue}, "margin")


# --- Operating leverage / margin bridge ---------------------------------------
# "Operating leverage" names THREE distinct quantities in practice. A bare
# "+X pp" or "Yx" figure is unauditable until the report says which one it is, so
# each definition is a named function and the linter forces a recomputable choice.

def operating_leverage_pp(revenue_growth_pp: float, opex_growth_pp: float) -> dict:
    """Growth-gap definition, in PERCENTAGE POINTS: revenue growth − opex growth.
    Inputs are growth rates in pp (e.g. 16.0, not 0.16). Positive = revenue outran costs."""
    return _metric("operating_leverage_pp", revenue_growth_pp - opex_growth_pp,
                   "revenue_growth_pp - opex_growth_pp",
                   {"revenue_growth_pp": revenue_growth_pp, "opex_growth_pp": opex_growth_pp},
                   "operating_leverage")


def margin_delta_pp(margin_end_pct: float, margin_start_pct: float) -> dict:
    """Margin-expansion definition, in PERCENTAGE POINTS: end − start. Inputs are
    margins in pp (e.g. 57.6, not 0.576). Distinct from the growth-gap definition."""
    return _metric("margin_delta_pp", margin_end_pct - margin_start_pct,
                   "margin_end_pct - margin_start_pct",
                   {"margin_end_pct": margin_end_pct, "margin_start_pct": margin_start_pct},
                   "operating_leverage")


def dol(op_income_growth_pct: float, revenue_growth_pct: float) -> dict:
    """Degree of operating leverage = %ΔOperating income / %ΔRevenue — a RATIO
    (e.g. 1.3×), never a pp figure. >1 = positive leverage."""
    v = op_income_growth_pct / revenue_growth_pct if revenue_growth_pct else None
    return _metric("dol", v, "op_income_growth_pct / revenue_growth_pct",
                   {"op_income_growth_pct": op_income_growth_pct, "revenue_growth_pct": revenue_growth_pct},
                   "operating_leverage")


# Registry used by the linter to recompute a stated metric from its inputs.
RATIO_FUNCS = {
    "pe": pe, "pfcf": pfcf, "ps": ps,
    "ev_fcf": ev_fcf, "ev_ebitda": ev_ebitda, "ev_sales": ev_sales,
    "enterprise_value": enterprise_value,
    "peg": peg, "net_debt": net_debt, "net_debt_ebitda": net_debt_ebitda,
    "fcf_margin": fcf_margin, "capex_intensity": capex_intensity,
    "gross_margin": gross_margin, "operating_margin": operating_margin, "net_margin": net_margin,
    "operating_leverage_pp": operating_leverage_pp, "margin_delta_pp": margin_delta_pp, "dol": dol,
}

# Which metric ids are EV-based (numerator must include +debt-cash).
EV_MULTIPLES = {"ev_fcf", "ev_ebitda", "ev_sales"}