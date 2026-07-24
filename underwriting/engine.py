from __future__ import annotations

from dataclasses import replace

from .models import (
    FinancingAssumptions,
    InvestmentAnalysis,
    PropertyAssumptions,
    YearProjection,
)


def _npv(rate: float, cash_flows: list[float]) -> float:
    return sum(value / ((1.0 + rate) ** year) for year, value in enumerate(cash_flows))


def annual_irr(cash_flows: list[float]) -> float | None:
    """Calculate an annual IRR for conventional annual cash flows."""
    if not cash_flows or not any(value < 0 for value in cash_flows):
        return None
    if not any(value > 0 for value in cash_flows):
        return None

    low, high = -0.9999, 10.0
    low_npv, high_npv = _npv(low, cash_flows), _npv(high, cash_flows)
    if low_npv * high_npv > 0:
        return None

    for _ in range(250):
        midpoint = (low + high) / 2.0
        midpoint_npv = _npv(midpoint, cash_flows)
        if abs(midpoint_npv) < 1e-7:
            return midpoint
        if low_npv * midpoint_npv <= 0:
            high = midpoint
        else:
            low = midpoint
            low_npv = midpoint_npv
    return (low + high) / 2.0


def _operating_projection(
    assumptions: PropertyAssumptions,
    year: int,
) -> tuple[float, float, float, float, float, float]:
    rent_factor = (1.0 + assumptions.rent_growth_rate) ** (year - 1)
    expense_factor = (1.0 + assumptions.expense_growth_rate) ** (year - 1)
    potential_rent = assumptions.potential_gross_rent * rent_factor
    other_income = assumptions.other_income * rent_factor
    vacancy_loss = potential_rent * assumptions.vacancy_rate
    effective_income = potential_rent - vacancy_loss + other_income
    operating_expenses = assumptions.operating_expenses * expense_factor
    noi = effective_income - operating_expenses
    return (
        potential_rent,
        vacancy_loss,
        effective_income,
        operating_expenses,
        noi,
        other_income,
    )


def analyse_investment(
    property_assumptions: PropertyAssumptions,
    financing_assumptions: FinancingAssumptions,
) -> InvestmentAnalysis:
    loan_amount = property_assumptions.purchase_price * financing_assumptions.loan_to_value
    initial_equity = property_assumptions.purchase_price - loan_amount
    opening_balance = loan_amount
    annual_scheduled_principal = loan_amount * financing_assumptions.annual_amortization_rate
    projections: list[YearProjection] = []

    for year in range(1, property_assumptions.holding_period_years + 1):
        (
            potential_rent,
            vacancy_loss,
            effective_income,
            operating_expenses,
            noi,
            _,
        ) = _operating_projection(property_assumptions, year)
        capex = property_assumptions.capex_for_year(year)
        interest = opening_balance * financing_assumptions.interest_rate
        principal = min(annual_scheduled_principal, opening_balance)
        debt_service = interest + principal
        ending_balance = opening_balance - principal
        dscr = noi / debt_service if debt_service > 0 else None
        projections.append(
            YearProjection(
                year=year,
                potential_gross_rent=potential_rent,
                vacancy_loss=vacancy_loss,
                effective_income=effective_income,
                operating_expenses=operating_expenses,
                noi=noi,
                capex=capex,
                unlevered_cash_flow=noi - capex,
                opening_loan_balance=opening_balance,
                interest_payment=interest,
                principal_payment=principal,
                debt_service=debt_service,
                ending_loan_balance=ending_balance,
                dscr=dscr,
                cash_flow_to_equity_before_sale=noi - capex - debt_service,
            )
        )
        opening_balance = ending_balance

    next_year_noi = _operating_projection(
        property_assumptions,
        property_assumptions.holding_period_years + 1,
    )[4]
    terminal_value = next_year_noi / property_assumptions.exit_cap_rate
    selling_costs = terminal_value * property_assumptions.selling_cost_rate
    net_sale_proceeds = terminal_value - selling_costs

    unlevered_cash_flows = [-property_assumptions.purchase_price]
    levered_cash_flows = [-initial_equity]
    for projection in projections:
        unlevered_cash_flows.append(projection.unlevered_cash_flow)
        levered_cash_flows.append(projection.cash_flow_to_equity_before_sale)
    unlevered_cash_flows[-1] += net_sale_proceeds
    levered_cash_flows[-1] += net_sale_proceeds - projections[-1].ending_loan_balance

    dcf_value = sum(
        projection.unlevered_cash_flow
        / ((1.0 + property_assumptions.discount_rate) ** projection.year)
        for projection in projections
    )
    dcf_value += net_sale_proceeds / (
        (1.0 + property_assumptions.discount_rate)
        ** property_assumptions.holding_period_years
    )

    year_one_noi = projections[0].noi
    implied_cap_rate = (
        year_one_noi / property_assumptions.purchase_price
        if property_assumptions.purchase_price
        else 0.0
    )
    direct_cap_value = year_one_noi / property_assumptions.market_cap_rate
    dscr_values = [item.dscr for item in projections if item.dscr is not None]
    equity_distributions = sum(max(value, 0.0) for value in levered_cash_flows)
    total_equity_contributions = abs(
        sum(min(value, 0.0) for value in levered_cash_flows)
    )
    equity_multiple = (
        equity_distributions / total_equity_contributions
        if total_equity_contributions > 0
        else 0.0
    )
    year_one_debt_service = projections[0].debt_service
    required_occupied_rent = (
        property_assumptions.operating_expenses
        + year_one_debt_service
        - property_assumptions.other_income
    )
    break_even_occupancy = (
        required_occupied_rent / property_assumptions.potential_gross_rent
        if property_assumptions.potential_gross_rent
        else 0.0
    )

    return InvestmentAnalysis(
        property=property_assumptions,
        financing=financing_assumptions,
        projections=tuple(projections),
        loan_amount=loan_amount,
        initial_equity=initial_equity,
        year_one_noi=year_one_noi,
        implied_cap_rate=implied_cap_rate,
        direct_cap_value=direct_cap_value,
        terminal_value=terminal_value,
        selling_costs=selling_costs,
        net_sale_proceeds_before_debt=net_sale_proceeds,
        dcf_value=dcf_value,
        npv_at_asking_price=dcf_value - property_assumptions.purchase_price,
        unlevered_irr=annual_irr(unlevered_cash_flows),
        levered_irr=annual_irr(levered_cash_flows),
        equity_multiple=equity_multiple,
        minimum_dscr=min(dscr_values) if dscr_values else None,
        break_even_occupancy_year_one=break_even_occupancy,
        unlevered_cash_flows=tuple(unlevered_cash_flows),
        levered_cash_flows=tuple(levered_cash_flows),
    )


def with_changes(
    assumptions: PropertyAssumptions,
    **changes: float,
) -> PropertyAssumptions:
    """Create a scenario without mutating the original assumptions."""
    return replace(assumptions, **changes)
