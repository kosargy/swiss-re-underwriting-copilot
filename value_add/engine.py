from __future__ import annotations

from underwriting.engine import annual_irr

from .models import (
    ValueAddAnalysis,
    ValueAddFinancing,
    ValueAddProject,
    ValueAddProjection,
)


def _operating_year(
    project: ValueAddProject,
    year: int,
) -> tuple[str, float, float, float, float, float, float]:
    if year <= project.renovation_years:
        phase = "Renovation"
        rent_factor = (1.0 + project.annual_rent_growth_rate) ** (year - 1)
        expense_factor = (1.0 + project.annual_expense_growth_rate) ** (year - 1)
        potential_rent = project.current_potential_rent * rent_factor
        vacancy_loss = potential_rent * project.current_vacancy_rate
        occupied_income = potential_rent - vacancy_loss
        retained_income = occupied_income * project.income_retention_during_renovation
        renovation_income_loss = occupied_income - retained_income
        effective_income = retained_income
        operating_expenses = project.current_operating_expenses * expense_factor
    else:
        phase = "Stabilized"
        stabilized_year = year - project.renovation_years - 1
        rent_factor = (1.0 + project.annual_rent_growth_rate) ** stabilized_year
        expense_factor = (1.0 + project.annual_expense_growth_rate) ** stabilized_year
        potential_rent = project.stabilized_potential_rent * rent_factor
        vacancy_loss = potential_rent * project.stabilized_vacancy_rate
        renovation_income_loss = 0.0
        effective_income = potential_rent - vacancy_loss
        operating_expenses = project.stabilized_operating_expenses * expense_factor
    noi = effective_income - operating_expenses
    return (
        phase,
        potential_rent,
        vacancy_loss,
        renovation_income_loss,
        effective_income,
        operating_expenses,
        noi,
    )


def analyse_value_add(
    project: ValueAddProject,
    financing: ValueAddFinancing,
) -> ValueAddAnalysis:
    loan_amount = project.purchase_price * financing.purchase_loan_to_value
    initial_equity = (
        project.purchase_price * (1.0 + project.acquisition_cost_rate) - loan_amount
    )
    opening_balance = loan_amount
    scheduled_principal = loan_amount * financing.annual_amortization_rate
    projections: list[ValueAddProjection] = []

    for year in range(1, project.holding_period_years + 1):
        (
            phase,
            potential_rent,
            vacancy_loss,
            renovation_income_loss,
            effective_income,
            operating_expenses,
            noi,
        ) = _operating_year(project, year)
        capex = project.capex_for_year(year)
        interest = opening_balance * financing.interest_rate
        principal = min(scheduled_principal, opening_balance)
        debt_service = interest + principal
        ending_balance = opening_balance - principal
        dscr = noi / debt_service if debt_service > 0 else None
        projections.append(
            ValueAddProjection(
                year=year,
                phase=phase,
                potential_rent=potential_rent,
                vacancy_loss=vacancy_loss,
                renovation_income_loss=renovation_income_loss,
                effective_income=effective_income,
                operating_expenses=operating_expenses,
                noi=noi,
                renovation_capex=capex,
                unlevered_cash_flow_before_sale=noi - capex,
                opening_loan_balance=opening_balance,
                interest_payment=interest,
                principal_payment=principal,
                debt_service=debt_service,
                ending_loan_balance=ending_balance,
                dscr=dscr,
                equity_cash_flow_before_sale=noi - capex - debt_service,
            )
        )
        opening_balance = ending_balance

    next_year_noi = _operating_year(project, project.holding_period_years + 1)[6]
    terminal_value = next_year_noi / project.exit_cap_rate
    selling_costs = terminal_value * project.selling_cost_rate
    net_sale_proceeds = terminal_value - selling_costs

    unlevered_cash_flows = [-project.purchase_price * (1.0 + project.acquisition_cost_rate)]
    levered_cash_flows = [-initial_equity]
    for projection in projections:
        unlevered_cash_flows.append(projection.unlevered_cash_flow_before_sale)
        levered_cash_flows.append(projection.equity_cash_flow_before_sale)
    unlevered_cash_flows[-1] += net_sale_proceeds
    levered_cash_flows[-1] += net_sale_proceeds - projections[-1].ending_loan_balance

    future_cash_flow_value = sum(
        projection.unlevered_cash_flow_before_sale
        / ((1.0 + project.discount_rate) ** projection.year)
        for projection in projections
    )
    future_cash_flow_value += net_sale_proceeds / (
        (1.0 + project.discount_rate) ** project.holding_period_years
    )
    maximum_purchase_price = future_cash_flow_value / (
        1.0 + project.acquisition_cost_rate
    )
    project_npv = (
        future_cash_flow_value
        - project.purchase_price * (1.0 + project.acquisition_cost_rate)
    )

    current_noi = (
        project.current_potential_rent * (1.0 - project.current_vacancy_rate)
        - project.current_operating_expenses
    )
    as_is_value = current_noi / project.current_market_cap_rate
    stabilized_noi = _operating_year(project, project.renovation_years + 1)[6]
    stabilized_value = stabilized_noi / project.exit_cap_rate
    gross_value_uplift = stabilized_value - as_is_value
    incremental_value = gross_value_uplift - project.total_renovation_capex
    renovation_roi = (
        incremental_value / project.total_renovation_capex
        if project.total_renovation_capex > 0
        else None
    )

    capex_present_value = sum(
        project.capex_for_year(year) / ((1.0 + project.discount_rate) ** year)
        for year in range(1, project.renovation_years + 1)
    )
    pv_per_capex_franc = (
        capex_present_value / project.total_renovation_capex
        if project.total_renovation_capex > 0
        else 0.0
    )
    future_value_before_capex = future_cash_flow_value + capex_present_value
    break_even_capex = (
        (
            future_value_before_capex
            - project.purchase_price * (1.0 + project.acquisition_cost_rate)
        )
        / pv_per_capex_franc
        if pv_per_capex_franc > 0
        else None
    )

    unlevered_irr = annual_irr(unlevered_cash_flows)
    levered_irr = annual_irr(levered_cash_flows)
    positive_equity_flows = sum(max(value, 0.0) for value in levered_cash_flows)
    equity_contributions = abs(sum(min(value, 0.0) for value in levered_cash_flows))
    equity_multiple = (
        positive_equity_flows / equity_contributions if equity_contributions else 0.0
    )
    stabilized_dscrs = [
        projection.dscr
        for projection in projections
        if projection.phase == "Stabilized" and projection.dscr is not None
    ]

    meets_returns = (
        unlevered_irr is not None
        and levered_irr is not None
        and unlevered_irr >= project.target_unlevered_irr
        and levered_irr >= project.target_levered_irr
    )
    if project_npv >= project.purchase_price * 0.10 and meets_returns:
        recommendation = "ATTRACTIVE VALUE-ADD CASE"
    elif project_npv >= 0 and meets_returns:
        recommendation = "FEASIBLE — PROCEED TO DUE DILIGENCE"
    elif maximum_purchase_price >= project.purchase_price * 0.90:
        recommendation = "NEGOTIATE PRICE OR BUSINESS PLAN"
    else:
        recommendation = "REJECT AT CURRENT ASSUMPTIONS"

    return ValueAddAnalysis(
        project=project,
        financing=financing,
        projections=tuple(projections),
        current_noi=current_noi,
        as_is_value=as_is_value,
        stabilized_noi=stabilized_noi,
        stabilized_value=stabilized_value,
        gross_value_uplift=gross_value_uplift,
        incremental_value_created=incremental_value,
        renovation_roi=renovation_roi,
        loan_amount=loan_amount,
        initial_equity=initial_equity,
        terminal_value=terminal_value,
        selling_costs=selling_costs,
        maximum_supportable_purchase_price=maximum_purchase_price,
        break_even_total_renovation_capex=break_even_capex,
        project_npv_at_asking_price=project_npv,
        unlevered_irr=unlevered_irr,
        levered_irr=levered_irr,
        equity_multiple=equity_multiple,
        minimum_stabilized_dscr=(
            min(stabilized_dscrs) if stabilized_dscrs else None
        ),
        recommendation=recommendation,
        unlevered_cash_flows=tuple(unlevered_cash_flows),
        levered_cash_flows=tuple(levered_cash_flows),
    )
