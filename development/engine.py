from __future__ import annotations

from underwriting.engine import annual_irr

from .models import (
    DevelopmentAnalysis,
    DevelopmentPlan,
    DevelopmentProject,
    DevelopmentYear,
)


def analyse_development_plan(
    project: DevelopmentProject,
    plan: DevelopmentPlan,
) -> DevelopmentAnalysis:
    nfa = project.net_floor_area_sqm
    residential_area = nfa * plan.residential_rental_share
    condo_area = nfa * plan.condo_sale_share
    commercial_area = nfa * plan.commercial_rental_share
    revenue_growth_factor = (1.0 + project.revenue_growth_rate) ** plan.development_years

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
    cash_flows = [
        -project.asking_land_price * (1.0 + project.land_acquisition_cost_rate)
    ]

    for year in range(1, plan.development_years + 1):
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
    completion_discount_factor = (
        1.0 + project.discount_rate
    ) ** plan.development_years
    pv_proceeds = net_completion_proceeds / completion_discount_factor
    residual_before_acquisition_costs = pv_proceeds - pv_cost
    maximum_land_price = residual_before_acquisition_costs / (
        1.0 + project.land_acquisition_cost_rate
    )
    npv_at_asking = (
        residual_before_acquisition_costs
        - project.asking_land_price * (1.0 + project.land_acquisition_cost_rate)
    )
    nominal_profit = (
        net_completion_proceeds
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
