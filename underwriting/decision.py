from __future__ import annotations

from dataclasses import dataclass, replace

from .engine import analyse_investment
from .models import FinancingAssumptions, InvestmentAnalysis, PropertyAssumptions
from .scenarios import ScenarioAnalysis


@dataclass(frozen=True)
class InvestmentCriteria:
    target_unlevered_irr: float = 0.06
    target_levered_irr: float = 0.08
    minimum_dscr: float = 1.30
    margin_of_safety: float = 0.05


@dataclass(frozen=True)
class RiskItem:
    category: str
    severity: str
    finding: str
    evidence: str
    action: str


@dataclass(frozen=True)
class Decision:
    recommendation: str
    summary: str
    maximum_price_dcf: float
    maximum_price_target_irr: float | None
    recommended_price: float
    reasons: tuple[str, ...]
    conditions: tuple[str, ...]
    risks: tuple[RiskItem, ...]


def _target_irr_price(
    property_assumptions: PropertyAssumptions,
    financing_assumptions: FinancingAssumptions,
    target_irr: float,
) -> float | None:
    """Solve for the highest price that still meets the target levered IRR."""
    low = max(1.0, property_assumptions.purchase_price * 0.20)
    high = property_assumptions.purchase_price * 2.0

    def irr_at(price: float) -> float | None:
        return analyse_investment(
            replace(property_assumptions, purchase_price=price),
            financing_assumptions,
        ).levered_irr

    low_irr, high_irr = irr_at(low), irr_at(high)
    if low_irr is None or high_irr is None:
        return None
    if low_irr < target_irr:
        return None
    if high_irr >= target_irr:
        return high

    for _ in range(100):
        midpoint = (low + high) / 2.0
        midpoint_irr = irr_at(midpoint)
        if midpoint_irr is None:
            return None
        if midpoint_irr >= target_irr:
            low = midpoint
        else:
            high = midpoint
    return low


def build_risk_register(
    base: InvestmentAnalysis,
    scenarios: tuple[ScenarioAnalysis, ...],
    criteria: InvestmentCriteria,
) -> tuple[RiskItem, ...]:
    risks: list[RiskItem] = []
    downside = next(item.analysis for item in scenarios if item.name == "Downside")
    pricing_gap = base.property.purchase_price / base.dcf_value - 1.0
    if pricing_gap > 0:
        severity = "High" if pricing_gap >= 0.10 else "Medium"
        risks.append(
            RiskItem(
                "Pricing",
                severity,
                "Asking price exceeds the base-case DCF value.",
                f"Premium to DCF value: {pricing_gap:.1%}.",
                "Renegotiate price or substantiate additional income/value-creation upside.",
            )
        )

    if base.minimum_dscr is not None and base.minimum_dscr < criteria.minimum_dscr:
        severity = "High" if base.minimum_dscr < 1.0 else "Medium"
        risks.append(
            RiskItem(
                "Debt service",
                severity,
                "Debt-service coverage is below the investment threshold.",
                f"Minimum DSCR: {base.minimum_dscr:.2f}x; target: "
                f"{criteria.minimum_dscr:.2f}x.",
                "Reduce leverage, improve NOI or negotiate a lower financing cost.",
            )
        )

    if base.implied_cap_rate <= base.financing.interest_rate:
        risks.append(
            RiskItem(
                "Financing",
                "High",
                "The acquisition starts with negative leverage.",
                f"Implied cap rate: {base.implied_cap_rate:.2%}; interest rate: "
                f"{base.financing.interest_rate:.2%}.",
                "Reduce debt cost/LTV or lower the purchase price.",
            )
        )

    total_capex = sum(base.property.capex_by_year)
    capex_ratio = total_capex / base.property.purchase_price
    if capex_ratio >= 0.05:
        risks.append(
            RiskItem(
                "Capital expenditure",
                "High" if capex_ratio >= 0.10 else "Medium",
                "Material planned CapEx may create funding and execution risk.",
                f"Planned CapEx: CHF {total_capex:,.0f} ({capex_ratio:.1%} of price).",
                "Validate scope, timing, contingency and funding source.",
            )
        )

    if base.property.vacancy_rate >= 0.08:
        risks.append(
            RiskItem(
                "Leasing",
                "High" if base.property.vacancy_rate >= 0.15 else "Medium",
                "Vacancy is elevated.",
                f"Base vacancy assumption: {base.property.vacancy_rate:.1%}.",
                "Review leasing pipeline, incentives and time-to-lease assumptions.",
            )
        )

    exit_value_pv = base.net_sale_proceeds_before_debt / (
        (1.0 + base.property.discount_rate) ** base.property.holding_period_years
    )
    terminal_share = exit_value_pv / base.dcf_value
    if terminal_share >= 0.70:
        risks.append(
            RiskItem(
                "Terminal value",
                "Medium",
                "A large share of DCF value depends on the assumed exit.",
                f"Discounted sale proceeds represent {terminal_share:.1%} of DCF value.",
                "Stress-test exit cap rate, sale timing and transaction costs.",
            )
        )

    if downside.levered_irr is None or downside.levered_irr < 0:
        risks.append(
            RiskItem(
                "Downside",
                "High",
                "The downside case produces a negative or undefined equity return.",
                f"Downside levered IRR: "
                f"{'n/a' if downside.levered_irr is None else f'{downside.levered_irr:.2%}'}.",
                "Require a lower entry price or additional downside protection.",
            )
        )
    elif downside.levered_irr < criteria.target_levered_irr:
        risks.append(
            RiskItem(
                "Downside",
                "Medium",
                "Downside return falls below the target.",
                f"Downside levered IRR: {downside.levered_irr:.2%}; target: "
                f"{criteria.target_levered_irr:.2%}.",
                "Test a lower price, lower leverage and stronger operating contingency.",
            )
        )
    return tuple(risks)


def make_decision(
    base: InvestmentAnalysis,
    scenarios: tuple[ScenarioAnalysis, ...],
    criteria: InvestmentCriteria,
) -> Decision:
    risks = build_risk_register(base, scenarios, criteria)
    maximum_dcf_price = base.dcf_value
    maximum_irr_price = _target_irr_price(
        base.property,
        base.financing,
        criteria.target_levered_irr,
    )
    candidates = [maximum_dcf_price]
    if maximum_irr_price is not None:
        candidates.append(maximum_irr_price)
    break_even_price = min(candidates)
    recommended_price = break_even_price / (1.0 + criteria.margin_of_safety)

    reasons: list[str] = []
    conditions: list[str] = []
    price_is_supported = base.property.purchase_price <= maximum_dcf_price
    unlevered_met = (
        base.unlevered_irr is not None
        and base.unlevered_irr >= criteria.target_unlevered_irr
    )
    levered_met = (
        base.levered_irr is not None
        and base.levered_irr >= criteria.target_levered_irr
    )
    dscr_met = (
        base.minimum_dscr is None or base.minimum_dscr >= criteria.minimum_dscr
    )
    high_risks = [risk for risk in risks if risk.severity == "High"]

    if not price_is_supported:
        reasons.append(
            f"Asking price exceeds DCF value by "
            f"CHF {base.property.purchase_price - maximum_dcf_price:,.0f}."
        )
    if not unlevered_met:
        reasons.append(
            f"Unlevered IRR of "
            f"{'n/a' if base.unlevered_irr is None else f'{base.unlevered_irr:.2%}'} "
            f"is below the {criteria.target_unlevered_irr:.2%} target."
        )
    if not levered_met:
        reasons.append(
            f"Levered IRR of "
            f"{'n/a' if base.levered_irr is None else f'{base.levered_irr:.2%}'} "
            f"is below the {criteria.target_levered_irr:.2%} target."
        )
    if not dscr_met:
        reasons.append(
            f"Minimum DSCR of {base.minimum_dscr:.2f}x is below the "
            f"{criteria.minimum_dscr:.2f}x threshold."
        )

    conditions.extend(
        (
            "Validate rent roll, operating expenses and lease terms.",
            "Confirm CapEx scope, timing and contingency.",
            "Obtain market evidence for rent and exit-cap assumptions.",
        )
    )

    if (
        base.property.purchase_price > break_even_price
        or not unlevered_met
        or not levered_met
    ):
        recommendation = "NEGOTIATE"
        summary = "The deal does not meet return requirements at the current price."
    elif high_risks:
        recommendation = "PROCEED WITH CONDITIONS"
        summary = "Returns are supportable, but material risks require mitigation."
    elif not dscr_met or risks:
        recommendation = "PROCEED WITH CONDITIONS"
        summary = "The deal merits further work subject to the listed conditions."
    else:
        recommendation = "PROCEED TO DUE DILIGENCE"
        summary = "The base case meets pricing, return and debt-service criteria."

    return Decision(
        recommendation=recommendation,
        summary=summary,
        maximum_price_dcf=maximum_dcf_price,
        maximum_price_target_irr=maximum_irr_price,
        recommended_price=recommended_price,
        reasons=tuple(reasons),
        conditions=tuple(conditions),
        risks=risks,
    )

