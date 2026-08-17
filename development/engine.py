from __future__ import annotations

from underwriting.engine import annual_irr

from .models import (
    DevelopmentAnalysis,
    DevelopmentPlan,
    DevelopmentProject,
    DevelopmentYear,
    PreDevelopmentYear,
)


def analyse_development_plan(
    project: DevelopmentProject,
    plan: DevelopmentPlan,
) -> DevelopmentAnalysis:
    nfa = project.net_floor_area_sqm
    residential_area = nfa * plan.residential_rental_share
    condo_area = nfa * plan.condo_sale_share
    commercial_area = nfa * plan.commercial_rental_share
    predevelopment_delay = project.predevelopment_income_years
    completion_year = predevelopment_delay + plan.development_years
    revenue_growth_factor = (1.0 + project.revenue_growth_rate) ** completion_year

    residential_rent = (
        residential_area * plan.residential_rent_per_sqm * revenue_growth_factor
    )
    commercial_rent = (
        commercial_area * plan.commercial_rent_per_sqm * revenue_growth_factor
    )
    rental_parking_income = (
        plan.rental_parking_spaces
        * plan.annual_rent_per_parking_space
        * revenue_growth_factor
    )
    residential_income_value = 0.0
    if plan.residential_rental_share:
        residential_income_value = (
            residential_rent + rental_parking_income
        ) / plan.residential_cap_rate
    commercial_income_value = 0.0
    if plan.commercial_rental_share:
        commercial_income_value = commercial_rent / plan.commercial_cap_rate
    condo_sales_value = (
        condo_area * plan.condo_sale_price_per_sqm * revenue_growth_factor
    )
    parking_sales_value = (
        plan.sale_parking_spaces
        * plan.sale_price_per_parking_space
        * revenue_growth_factor
    )
    gdv = (
        residential_income_value
        + commercial_income_value
        + condo_sales_value
        + parking_sales_value
    )
    selling_costs = gdv * project.selling_cost_rate
    net_completion_proceeds = gdv - selling_costs

    base_construction_cost = (
        residential_area * plan.residential_cost_per_sqm
        + condo_area * plan.condo_cost_per_sqm
        + commercial_area * plan.commercial_cost_per_sqm
    )
    base_cost_per_year = base_construction_cost / plan.development_years
    development_years: list[DevelopmentYear] = []
    predevelopment_years: list[PreDevelopmentYear] = []
    cash_flows = [
        -project.asking_land_price * (1.0 + project.land_acquisition_cost_rate)
    ]

    for year in range(1, predevelopment_delay + 1):
        potential_income = project.predevelopment_potential_income * (
            (1.0 + project.predevelopment_income_growth_rate) ** (year - 1)
        )
        vacancy_loss = potential_income * project.predevelopment_vacancy_rate
        termination_cost = (
            project.predevelopment_termination_cost
            if year == predevelopment_delay
            else 0.0
        )
        net_cash_flow = (
            potential_income
            - vacancy_loss
            - project.predevelopment_operating_expenses
            - termination_cost
        )
        discount_factor = (1.0 + project.discount_rate) ** year
        predevelopment_years.append(
            PreDevelopmentYear(
                year=year,
                potential_income=potential_income,
                vacancy_loss=vacancy_loss,
                operating_expenses=project.predevelopment_operating_expenses,
                termination_cost=termination_cost,
                net_cash_flow=net_cash_flow,
                discount_factor=discount_factor,
                present_value=net_cash_flow / discount_factor,
            )
        )
        cash_flows.append(net_cash_flow)

    for development_year in range(1, plan.development_years + 1):
        year = predevelopment_delay + development_year
        inflated_construction_cost = base_cost_per_year * (
            (1.0 + project.construction_cost_inflation) ** (year - 1)
        )
        professional_fees = (
            inflated_construction_cost * project.professional_fees_rate
        )
        contingency = inflated_construction_cost * project.contingency_rate
        total_cost = inflated_construction_cost + professional_fees + contingency
        discount_factor = (1.0 + project.discount_rate) ** year
        present_value = total_cost / discount_factor
        development_years.append(
            DevelopmentYear(
                year=year,
                construction_cost=inflated_construction_cost,
                professional_fees=professional_fees,
                contingency=contingency,
                total_development_cost=total_cost,
                discount_factor=discount_factor,
                present_value_of_cost=present_value,
            )
        )
        cash_flows.append(-total_cost)

    cash_flows[-1] += net_completion_proceeds
    total_nominal_cost = sum(item.total_development_cost for item in development_years)
    pv_cost = sum(item.present_value_of_cost for item in development_years)
    pv_predevelopment_income = sum(
        item.present_value for item in predevelopment_years
    )
    completion_discount_factor = (1.0 + project.discount_rate) ** completion_year
    pv_proceeds = net_completion_proceeds / completion_discount_factor
    residual_before_acquisition_costs = (
        pv_proceeds - pv_cost + pv_predevelopment_income
    )
    maximum_land_price = residual_before_acquisition_costs / (
        1.0 + project.land_acquisition_cost_rate
    )
    npv_at_asking = (
        residual_before_acquisition_costs
        - project.asking_land_price * (1.0 + project.land_acquisition_cost_rate)
    )
    nominal_profit = (
        net_completion_proceeds
        + sum(item.net_cash_flow for item in predevelopment_years)
        - total_nominal_cost
        - project.asking_land_price * (1.0 + project.land_acquisition_cost_rate)
    )
    margin = nominal_profit / gdv if gdv else 0.0
    value_surplus = maximum_land_price - project.asking_land_price

    if project.asking_land_price <= maximum_land_price * 0.9:
        recommendation = "ATTRACTIVE AT CURRENT LAND PRICE"
    elif project.asking_land_price <= maximum_land_price:
        recommendation = "FEASIBLE AT CURRENT LAND PRICE"
    elif project.asking_land_price <= maximum_land_price * 1.1:
        recommendation = "NEGOTIATE LAND PRICE"
    else:
        recommendation = "NOT FEASIBLE AT CURRENT LAND PRICE"

    return DevelopmentAnalysis(
        project=project,
        plan=plan,
        gross_floor_area_sqm=project.gross_floor_area_sqm,
        net_floor_area_sqm=nfa,
        residential_rental_area_sqm=residential_area,
        condo_sale_area_sqm=condo_area,
        commercial_rental_area_sqm=commercial_area,
        residential_annual_rent=residential_rent,
        commercial_annual_rent=commercial_rent,
        rental_parking_income=rental_parking_income,
        residential_income_value=residential_income_value,
        commercial_income_value=commercial_income_value,
        condo_sales_value=condo_sales_value,
        parking_sales_value=parking_sales_value,
        gross_development_value=gdv,
        selling_costs=selling_costs,
        net_completion_proceeds=net_completion_proceeds,
        predevelopment_years=tuple(predevelopment_years),
        present_value_of_predevelopment_income=pv_predevelopment_income,
        development_years=tuple(development_years),
        total_nominal_development_cost=total_nominal_cost,
        present_value_of_development_cost=pv_cost,
        present_value_of_completion_proceeds=pv_proceeds,
        residual_land_value_before_acquisition_costs=residual_before_acquisition_costs,
        maximum_supportable_land_price=maximum_land_price,
        project_npv_at_asking_price=npv_at_asking,
        project_irr_at_asking_price=annual_irr(cash_flows),
        nominal_project_profit_at_asking_price=nominal_profit,
        profit_margin_on_gdv=margin,
        value_surplus_to_asking_price=value_surplus,
        recommendation=recommendation,
        cash_flows_at_asking_price=tuple(cash_flows),
    )
