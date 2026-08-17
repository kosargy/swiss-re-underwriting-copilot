from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from development import (
    DevelopmentPlan,
    DevelopmentProject,
    compare_development_plans,
    development_sensitivity_grid,
)
from strategy_memo import build_development_memo, build_value_add_memo
from underwriting import (
    FinancingAssumptions,
    InvestmentCriteria,
    MarketBenchmarks,
    ComparableProperty,
    DealStore,
    PropertyAssumptions,
    analyse_investment,
    analyse_comparables,
    analyse_market_benchmarks,
    build_ic_memo,
    make_decision,
    sensitivity_grid,
    standard_scenarios,
)
from value_add import (
    ValueAddFinancing,
    ValueAddProject,
    analyse_value_add,
    value_add_sensitivity_grid,
)


st.set_page_config(
    page_title="Swiss RE Underwriting Copilot",
    page_icon="🏢",
    layout="wide",
)

deal_store = DealStore(Path(__file__).parent / "data" / "deals.sqlite3")

pending_payload = st.session_state.pop("_pending_deal_payload", None)
if pending_payload:
    for widget_key, widget_value in pending_payload.get("widget_values", {}).items():
        st.session_state[widget_key] = widget_value
    st.session_state["_comparable_seed"] = pending_payload.get("comparables", [])
    st.session_state["_comparables_editor_version"] = (
        st.session_state.get("_comparables_editor_version", 0) + 1
    )
    st.session_state["_active_deal_id"] = pending_payload.get("deal_id")
    st.session_state["_loaded_deal_notice"] = pending_payload.get("deal_name")


def chf(value: float) -> str:
    return f"CHF {value:,.0f}"


def percentage(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def render_interview_demo() -> None:
    st.divider()
    st.subheader("3-minute Investment Committee demo")
    st.caption(
        "A guided Value-Add case designed to demonstrate how assumptions become "
        "an investment decision."
    )

    base_project = ValueAddProject(
        name="Zürich Residential Repositioning",
        location="Zürich, Switzerland",
        purchase_price=12_000_000,
        acquisition_cost_rate=0.02,
        current_potential_rent=720_000,
        current_vacancy_rate=0.08,
        current_operating_expenses=210_000,
        current_market_cap_rate=0.0425,
        renovation_years=2,
        renovation_capex_by_year=(1_200_000, 1_000_000),
        income_retention_during_renovation=0.70,
        stabilized_potential_rent=980_000,
        stabilized_vacancy_rate=0.03,
        stabilized_operating_expenses=245_000,
        annual_rent_growth_rate=0.015,
        annual_expense_growth_rate=0.02,
        exit_cap_rate=0.04,
        discount_rate=0.07,
        selling_cost_rate=0.01,
        holding_period_years=5,
        target_unlevered_irr=0.07,
        target_levered_irr=0.10,
    )
    financing = ValueAddFinancing(
        purchase_loan_to_value=0.60,
        interest_rate=0.035,
        annual_amortization_rate=0.01,
    )
    base = analyse_value_add(base_project, financing)

    st.markdown("#### 1 · The opportunity")
    opportunity_1, opportunity_2, opportunity_3, opportunity_4 = st.columns(4)
    opportunity_1.metric("Asking price", chf(base_project.purchase_price))
    opportunity_2.metric("Current vacancy", percentage(base_project.current_vacancy_rate))
    opportunity_3.metric("Current NOI", chf(base.current_noi))
    opportunity_4.metric("As-is value", chf(base.as_is_value))
    st.write(
        "An older residential asset is offered above its income-capitalized as-is "
        "value. The investment thesis depends on renovation, lease-up and a "
        "material improvement in rental income."
    )

    st.markdown("#### 2 · The business plan")
    plan_1, plan_2, plan_3, plan_4 = st.columns(4)
    plan_1.metric("Renovation CapEx", chf(base_project.total_renovation_capex))
    plan_2.metric("Renovation period", "2 years")
    plan_3.metric("Stabilized NOI", chf(base.stabilized_noi))
    plan_4.metric("Stabilized value", chf(base.stabilized_value))

    st.markdown("#### 3 · Base-case decision")
    base_1, base_2, base_3, base_4 = st.columns(4)
    base_1.metric("Maximum bid", chf(base.maximum_supportable_purchase_price))
    base_2.metric("Levered IRR", percentage(base.levered_irr))
    base_3.metric("Value after CapEx", chf(base.incremental_value_created))
    base_4.metric("Equity multiple", f"{base.equity_multiple:.2f}x")
    st.success(base.recommendation)

    st.markdown("#### 4 · Challenge the investment thesis")
    st.caption(
        "Move the downside assumptions and watch the decision and maximum bid change."
    )
    stress_1, stress_2, stress_3 = st.columns(3)
    with stress_1:
        demo_capex_overrun_pct = st.slider(
            "Renovation CapEx overrun (%)",
            min_value=0,
            max_value=40,
            value=15,
            step=5,
            key="demo_capex_overrun_pct",
        )
    with stress_2:
        demo_rent_downside_pct = st.slider(
            "Stabilized rent downside (%)",
            min_value=0,
            max_value=20,
            value=10,
            step=2,
            key="demo_rent_downside_pct",
        )
    with stress_3:
        demo_exit_cap_expansion_bps = st.slider(
            "Exit cap expansion (bps)",
            min_value=0,
            max_value=150,
            value=50,
            step=25,
            key="demo_exit_cap_expansion_bps",
        )

    stressed_project = replace(
        base_project,
        renovation_capex_by_year=tuple(
            amount * (1.0 + demo_capex_overrun_pct / 100)
            for amount in base_project.renovation_capex_by_year
        ),
        stabilized_potential_rent=(
            base_project.stabilized_potential_rent
            * (1.0 - demo_rent_downside_pct / 100)
        ),
        exit_cap_rate=(
            base_project.exit_cap_rate
            + demo_exit_cap_expansion_bps / 10_000
        ),
    )
    stressed = analyse_value_add(stressed_project, financing)

    comparison_frame = pd.DataFrame(
        [
            {
                "Case": "Base case",
                "Renovation CapEx": base_project.total_renovation_capex,
                "Stabilized rent": base_project.stabilized_potential_rent,
                "Exit cap rate": percentage(base_project.exit_cap_rate),
                "Maximum bid": base.maximum_supportable_purchase_price,
                "Levered IRR": percentage(base.levered_irr),
                "NPV": base.project_npv_at_asking_price,
                "Decision": base.recommendation,
            },
            {
                "Case": "Stressed case",
                "Renovation CapEx": stressed_project.total_renovation_capex,
                "Stabilized rent": stressed_project.stabilized_potential_rent,
                "Exit cap rate": percentage(stressed_project.exit_cap_rate),
                "Maximum bid": stressed.maximum_supportable_purchase_price,
                "Levered IRR": percentage(stressed.levered_irr),
                "NPV": stressed.project_npv_at_asking_price,
                "Decision": stressed.recommendation,
            },
        ]
    )
    st.dataframe(
        comparison_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Renovation CapEx": st.column_config.NumberColumn(format="CHF %.0f"),
            "Stabilized rent": st.column_config.NumberColumn(format="CHF %.0f"),
            "Maximum bid": st.column_config.NumberColumn(format="CHF %.0f"),
            "NPV": st.column_config.NumberColumn(format="CHF %.0f"),
        },
    )
    impact_1, impact_2, impact_3 = st.columns(3)
    impact_1.metric(
        "Stressed maximum bid",
        chf(stressed.maximum_supportable_purchase_price),
        chf(
            stressed.maximum_supportable_purchase_price
            - base.maximum_supportable_purchase_price
        ),
    )
    impact_2.metric(
        "Stressed levered IRR",
        percentage(stressed.levered_irr),
        (
            "n/a"
            if stressed.levered_irr is None or base.levered_irr is None
            else f"{(stressed.levered_irr - base.levered_irr) * 100:+.2f} pp"
        ),
    )
    impact_3.metric("Stressed NPV", chf(stressed.project_npv_at_asking_price))

    if stressed.recommendation.startswith(("ATTRACTIVE", "FEASIBLE")):
        st.success(stressed.recommendation)
    elif stressed.recommendation.startswith("NEGOTIATE"):
        st.warning(stressed.recommendation)
    else:
        st.error(stressed.recommendation)

    maximum_bid_change = (
        stressed.maximum_supportable_purchase_price
        - base.maximum_supportable_purchase_price
    )
    st.info(
        f"Investment Committee insight: the selected downside assumptions reduce "
        f"the supportable purchase price by {chf(abs(maximum_bid_change))}. "
        f"The stressed maximum bid is "
        f"{chf(stressed.maximum_supportable_purchase_price)} versus the seller's "
        f"{chf(base_project.purchase_price)} asking price."
    )

    stressed_memo = build_value_add_memo(stressed)
    st.download_button(
        "Generate stressed Investment Committee memo (PDF)",
        data=stressed_memo,
        file_name="interview_demo_stressed_ic_memo.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="download_demo_stressed_memo",
    )

    with st.expander("Suggested 3-minute interview script"):
        st.markdown(
            """
**Opening:** “I built a decision-support platform for three real-estate investment
strategies. This case demonstrates a Value-Add acquisition.”

**Opportunity:** “The asking price is above the property's as-is income value, so
the deal only works if the renovation business plan creates sufficient NOI.”

**Base case:** “The platform models income disruption, CapEx, debt service,
stabilization and exit, then calculates the maximum supportable bid.”

**Challenge:** “I can stress renovation cost, achievable rent and the exit cap
rate. The platform immediately reprices the deal and changes the recommendation.”

**Close:** “It then converts the underwriting into an auditable Investment
Committee memo with the decision, risks and required due diligence.”
"""
        )


def render_value_add_workflow() -> None:
    st.divider()
    st.subheader("Value-Add / Repositioning")
    st.caption(
        "Underwrite an existing property through renovation, income disruption, "
        "stabilization and exit."
    )
    st.warning(
        "Preliminary decision-support model. Purchase debt is modelled separately; "
        "renovation CapEx is assumed to be funded with equity in this version."
    )

    current_tab, plan_tab, finance_tab = st.tabs(
        [
            "1 · Property today",
            "2 · Business plan",
            "3 · Financing & targets",
        ]
    )
    with current_tab:
        current_1, current_2, current_3 = st.columns(3)
        with current_1:
            va_name = st.text_input(
                "Project name",
                "Zürich Residential Repositioning",
                key="va_name",
            )
            va_location = st.text_input(
                "Location",
                "Zürich, Switzerland",
                key="va_location",
            )
            va_purchase_price = st.number_input(
                "Asking price (CHF)",
                min_value=100_000.0,
                value=12_000_000.0,
                step=100_000.0,
                key="va_purchase_price",
            )
        with current_2:
            va_current_rent = st.number_input(
                "Current potential annual rent (CHF)",
                min_value=0.0,
                value=720_000.0,
                step=10_000.0,
                key="va_current_rent",
            )
            va_current_vacancy_pct = st.number_input(
                "Current vacancy (%)",
                min_value=0.0,
                max_value=99.0,
                value=8.0,
                step=0.5,
                key="va_current_vacancy_pct",
            )
            va_current_opex = st.number_input(
                "Current operating expenses (CHF)",
                min_value=0.0,
                value=210_000.0,
                step=10_000.0,
                key="va_current_opex",
            )
        with current_3:
            va_current_cap_pct = st.number_input(
                "Current market cap rate (%)",
                min_value=0.1,
                max_value=30.0,
                value=4.25,
                step=0.05,
                key="va_current_cap_pct",
            )
            va_acquisition_cost_pct = st.number_input(
                "Acquisition costs (%)",
                min_value=0.0,
                max_value=20.0,
                value=2.0,
                step=0.25,
                key="va_acquisition_cost_pct",
            )

    with plan_tab:
        plan_1, plan_2, plan_3 = st.columns(3)
        with plan_1:
            va_renovation_years = st.number_input(
                "Renovation period (years)",
                min_value=1,
                max_value=5,
                value=2,
                step=1,
                key="va_renovation_years",
            )
            va_total_capex = st.number_input(
                "Total renovation CapEx (CHF)",
                min_value=0.0,
                value=2_200_000.0,
                step=100_000.0,
                key="va_total_capex",
            )
            va_income_retention_pct = st.number_input(
                "Rental income retained during works (%)",
                min_value=0.0,
                max_value=100.0,
                value=70.0,
                step=5.0,
                key="va_income_retention_pct",
                help=(
                    "Share of occupied rental income that remains collectible while "
                    "the renovation is in progress."
                ),
            )
        with plan_2:
            va_stabilized_rent = st.number_input(
                "Stabilized potential annual rent (CHF)",
                min_value=0.0,
                value=980_000.0,
                step=10_000.0,
                key="va_stabilized_rent",
            )
            va_stabilized_vacancy_pct = st.number_input(
                "Stabilized vacancy (%)",
                min_value=0.0,
                max_value=99.0,
                value=3.0,
                step=0.5,
                key="va_stabilized_vacancy_pct",
            )
            va_stabilized_opex = st.number_input(
                "Stabilized operating expenses (CHF)",
                min_value=0.0,
                value=245_000.0,
                step=10_000.0,
                key="va_stabilized_opex",
            )
        with plan_3:
            va_rent_growth_pct = st.number_input(
                "Annual rent growth (%)",
                min_value=0.0,
                max_value=20.0,
                value=1.5,
                step=0.1,
                key="va_rent_growth_pct",
            )
            va_expense_growth_pct = st.number_input(
                "Annual expense growth (%)",
                min_value=0.0,
                max_value=20.0,
                value=2.0,
                step=0.1,
                key="va_expense_growth_pct",
            )
            va_holding_period = st.number_input(
                "Holding period (years)",
                min_value=int(va_renovation_years) + 1,
                max_value=15,
                value=max(5, int(va_renovation_years) + 1),
                step=1,
                key="va_holding_period",
            )

    with finance_tab:
        finance_1, finance_2, finance_3 = st.columns(3)
        with finance_1:
            va_ltv_pct = st.number_input(
                "Purchase loan-to-value (%)",
                min_value=0.0,
                max_value=99.0,
                value=60.0,
                step=1.0,
                key="va_ltv_pct",
            )
            va_interest_pct = st.number_input(
                "Interest rate (%)",
                min_value=0.0,
                max_value=30.0,
                value=3.5,
                step=0.1,
                key="va_interest_pct",
            )
            va_amortization_pct = st.number_input(
                "Annual amortization (%)",
                min_value=0.0,
                max_value=20.0,
                value=1.0,
                step=0.25,
                key="va_amortization_pct",
            )
        with finance_2:
            va_discount_pct = st.number_input(
                "Discount rate (%)",
                min_value=0.1,
                max_value=30.0,
                value=7.0,
                step=0.25,
                key="va_discount_pct",
            )
            va_exit_cap_pct = st.number_input(
                "Exit cap rate (%)",
                min_value=0.1,
                max_value=30.0,
                value=4.0,
                step=0.05,
                key="va_exit_cap_pct",
            )
            va_selling_cost_pct = st.number_input(
                "Selling costs (%)",
                min_value=0.0,
                max_value=20.0,
                value=1.0,
                step=0.25,
                key="va_selling_cost_pct",
            )
        with finance_3:
            va_target_unlevered_pct = st.number_input(
                "Target unlevered IRR (%)",
                min_value=0.0,
                max_value=100.0,
                value=7.0,
                step=0.25,
                key="va_target_unlevered_pct",
            )
            va_target_levered_pct = st.number_input(
                "Target levered IRR (%)",
                min_value=0.0,
                max_value=100.0,
                value=10.0,
                step=0.25,
                key="va_target_levered_pct",
            )

    renovation_years = int(va_renovation_years)
    capex_schedule = tuple(
        va_total_capex / renovation_years for _ in range(renovation_years)
    )
    value_add_project = ValueAddProject(
        name=va_name,
        location=va_location,
        purchase_price=va_purchase_price,
        acquisition_cost_rate=va_acquisition_cost_pct / 100,
        current_potential_rent=va_current_rent,
        current_vacancy_rate=va_current_vacancy_pct / 100,
        current_operating_expenses=va_current_opex,
        current_market_cap_rate=va_current_cap_pct / 100,
        renovation_years=renovation_years,
        renovation_capex_by_year=capex_schedule,
        income_retention_during_renovation=va_income_retention_pct / 100,
        stabilized_potential_rent=va_stabilized_rent,
        stabilized_vacancy_rate=va_stabilized_vacancy_pct / 100,
        stabilized_operating_expenses=va_stabilized_opex,
        annual_rent_growth_rate=va_rent_growth_pct / 100,
        annual_expense_growth_rate=va_expense_growth_pct / 100,
        exit_cap_rate=va_exit_cap_pct / 100,
        discount_rate=va_discount_pct / 100,
        selling_cost_rate=va_selling_cost_pct / 100,
        holding_period_years=int(va_holding_period),
        target_unlevered_irr=va_target_unlevered_pct / 100,
        target_levered_irr=va_target_levered_pct / 100,
    )
    value_add_financing = ValueAddFinancing(
        purchase_loan_to_value=va_ltv_pct / 100,
        interest_rate=va_interest_pct / 100,
        annual_amortization_rate=va_amortization_pct / 100,
    )
    result = analyse_value_add(value_add_project, value_add_financing)

    st.divider()
    st.markdown("#### 4 · Investment decision")
    decision_1, decision_2, decision_3, decision_4 = st.columns(4)
    decision_1.metric("As-is value", chf(result.as_is_value))
    decision_2.metric("Stabilized value", chf(result.stabilized_value))
    decision_3.metric(
        "Maximum purchase price",
        chf(result.maximum_supportable_purchase_price),
    )
    decision_4.metric("NPV at asking", chf(result.project_npv_at_asking_price))

    return_1, return_2, return_3, return_4 = st.columns(4)
    return_1.metric("Unlevered IRR", percentage(result.unlevered_irr))
    return_2.metric("Levered IRR", percentage(result.levered_irr))
    return_3.metric("Equity multiple", f"{result.equity_multiple:.2f}x")
    return_4.metric(
        "Minimum stabilized DSCR",
        (
            "n/a"
            if result.minimum_stabilized_dscr is None
            else f"{result.minimum_stabilized_dscr:.2f}x"
        ),
    )

    if result.recommendation.startswith("ATTRACTIVE"):
        st.success(result.recommendation)
    elif result.recommendation.startswith("FEASIBLE"):
        st.success(result.recommendation)
    elif result.recommendation.startswith("NEGOTIATE"):
        st.warning(result.recommendation)
    else:
        st.error(result.recommendation)

    if result.project_npv_at_asking_price >= 0:
        st.info(
            f"The current asking price is supportable under the base case. "
            f"The model indicates a maximum purchase price of approximately "
            f"{chf(result.maximum_supportable_purchase_price)}."
        )
    else:
        st.info(
            f"The current asking price is not supportable under the base case. "
            f"A price at or below approximately "
            f"{chf(result.maximum_supportable_purchase_price)} is required."
        )

    st.markdown("#### Value-creation bridge")
    bridge_1, bridge_2, bridge_3, bridge_4 = st.columns(4)
    bridge_1.metric("Current NOI", chf(result.current_noi))
    bridge_2.metric("Stabilized NOI", chf(result.stabilized_noi))
    bridge_3.metric("Gross value uplift", chf(result.gross_value_uplift))
    bridge_4.metric(
        "Value created after CapEx",
        chf(result.incremental_value_created),
    )
    limit_1, limit_2 = st.columns(2)
    limit_1.metric(
        "Break-even renovation budget",
        (
            "n/a"
            if result.break_even_total_renovation_capex is None
            else chf(result.break_even_total_renovation_capex)
        ),
        help="Total CapEx that would reduce project NPV to zero at the asking price.",
    )
    limit_2.metric("Renovation ROI", percentage(result.renovation_roi))

    projection_frame = pd.DataFrame(
        [
            {
                "Year": item.year,
                "Phase": item.phase,
                "Potential rent": item.potential_rent,
                "Income disruption": item.renovation_income_loss,
                "NOI": item.noi,
                "Renovation CapEx": item.renovation_capex,
                "Debt service": item.debt_service,
                "Equity cash flow before sale": item.equity_cash_flow_before_sale,
                "DSCR": item.dscr,
            }
            for item in result.projections
        ]
    )
    st.markdown("#### Annual business-plan cash flows")
    st.dataframe(
        projection_frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            column: st.column_config.NumberColumn(format="CHF %.0f")
            for column in (
                "Potential rent",
                "Income disruption",
                "NOI",
                "Renovation CapEx",
                "Debt service",
                "Equity cash flow before sale",
            )
        }
        | {"DSCR": st.column_config.NumberColumn(format="%.2fx")},
    )

    cash_flow_chart = px.bar(
        projection_frame,
        x="Year",
        y=["NOI", "Renovation CapEx"],
        barmode="group",
        title="NOI and renovation investment by year",
    )
    st.plotly_chart(cash_flow_chart, use_container_width=True)

    st.markdown("#### Sensitivity: maximum supportable purchase price")
    sensitivity_points = value_add_sensitivity_grid(
        value_add_project,
        value_add_financing,
    )
    sensitivity_frame = pd.DataFrame(
        [
            {
                "Renovation cost change": f"{point.renovation_cost_change:+.0%}",
                "Stabilized rent change": f"{point.stabilized_rent_change:+.0%}",
                "Maximum purchase price": point.maximum_supportable_purchase_price,
            }
            for point in sensitivity_points
        ]
    )
    sensitivity_matrix = sensitivity_frame.pivot(
        index="Renovation cost change",
        columns="Stabilized rent change",
        values="Maximum purchase price",
    )
    labels = ["-10%", "-5%", "+0%", "+5%", "+10%"]
    sensitivity_matrix = sensitivity_matrix.reindex(index=labels, columns=labels)
    sensitivity_figure = px.imshow(
        sensitivity_matrix,
        text_auto=",.0f",
        aspect="auto",
        color_continuous_scale="RdYlGn",
        labels={
            "x": "Stabilized rent change",
            "y": "Renovation-cost change",
            "color": "Max purchase price (CHF)",
        },
    )
    st.plotly_chart(sensitivity_figure, use_container_width=True)
    st.caption(
        "The maximum purchase price is the price that makes NPV equal to zero "
        "at the selected discount rate. It is not a certified valuation."
    )
    value_add_memo = build_value_add_memo(result)
    st.download_button(
        "Download Value-Add Investment Committee memo (PDF)",
        data=value_add_memo,
        file_name="value_add_investment_committee_memo.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="download_value_add_memo",
    )


def render_development_workflow() -> None:
    st.subheader("Development feasibility & residual land value")
    st.caption(
        "Test alternative development concepts and calculate the maximum land price "
        "that still meets the target return."
    )
    st.warning(
        "Decision-support prototype only. Outputs depend on the assumptions entered "
        "and do not constitute a certified valuation."
    )

    st.markdown("#### 1 · Site and project assumptions")
    project_col_1, project_col_2, project_col_3 = st.columns(3)
    with project_col_1:
        dev_project_name = st.text_input(
            "Project name",
            "Limmat Development Site",
            key="dev_project_name",
        )
        dev_location = st.text_input(
            "Location",
            "Zürich, Switzerland",
            key="dev_location",
        )
        dev_asking_land_price = st.number_input(
            "Asking land price (CHF)",
            min_value=0.0,
            value=5_000_000.0,
            step=100_000.0,
            key="dev_asking_land_price",
        )
        dev_land_acquisition_cost_pct = st.number_input(
            "Land acquisition costs (%)",
            min_value=0.0,
            max_value=100.0,
            value=3.0,
            step=0.25,
            key="dev_land_acquisition_cost_pct",
        )
    with project_col_2:
        dev_plot_size = st.number_input(
            "Plot size (sqm)",
            min_value=1.0,
            value=2_000.0,
            step=100.0,
            key="dev_plot_size",
        )
        dev_density = st.number_input(
            "Permitted density ratio",
            min_value=0.01,
            value=1.60,
            step=0.05,
            key="dev_density",
        )
        dev_efficiency_pct = st.number_input(
            "Floor-space efficiency (%)",
            min_value=1.0,
            max_value=100.0,
            value=80.0,
            step=1.0,
            key="dev_efficiency_pct",
        )
        dev_discount_rate_pct = st.number_input(
            "Target discount rate (%)",
            min_value=0.0,
            max_value=100.0,
            value=8.0,
            step=0.25,
            key="dev_discount_rate_pct",
        )
    with project_col_3:
        dev_cost_inflation_pct = st.number_input(
            "Construction-cost inflation (%)",
            min_value=0.0,
            max_value=100.0,
            value=2.5,
            step=0.25,
            key="dev_cost_inflation_pct",
        )
        dev_revenue_growth_pct = st.number_input(
            "Revenue growth until completion (%)",
            min_value=0.0,
            max_value=100.0,
            value=1.5,
            step=0.25,
            key="dev_revenue_growth_pct",
        )
        dev_professional_fees_pct = st.number_input(
            "Professional fees (% of construction)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.5,
            key="dev_professional_fees_pct",
        )
        dev_contingency_pct = st.number_input(
            "Contingency (% of construction)",
            min_value=0.0,
            max_value=100.0,
            value=7.5,
            step=0.5,
            key="dev_contingency_pct",
        )
        dev_selling_cost_pct = st.number_input(
            "Selling costs (% of GDV)",
            min_value=0.0,
            max_value=100.0,
            value=2.0,
            step=0.25,
            key="dev_selling_cost_pct",
        )

    development_project = DevelopmentProject(
        name=dev_project_name,
        location=dev_location,
        asking_land_price=dev_asking_land_price,
        plot_size_sqm=dev_plot_size,
        density_ratio=dev_density,
        floor_space_efficiency=dev_efficiency_pct / 100,
        discount_rate=dev_discount_rate_pct / 100,
        construction_cost_inflation=dev_cost_inflation_pct / 100,
        revenue_growth_rate=dev_revenue_growth_pct / 100,
        professional_fees_rate=dev_professional_fees_pct / 100,
        contingency_rate=dev_contingency_pct / 100,
        selling_cost_rate=dev_selling_cost_pct / 100,
        land_acquisition_cost_rate=dev_land_acquisition_cost_pct / 100,
    )
    area_col_1, area_col_2 = st.columns(2)
    area_col_1.metric(
        "Gross floor area (GFA)",
        f"{development_project.gross_floor_area_sqm:,.0f} sqm",
    )
    area_col_2.metric(
        "Net floor area (NFA)",
        f"{development_project.net_floor_area_sqm:,.0f} sqm",
    )

    st.markdown("#### 2 · Alternative development plans")

    def development_plan_inputs(
        *,
        prefix: str,
        name: str,
        probability: float,
        years: int,
        residential_share: float,
        condo_share: float,
        commercial_share: float,
        residential_rent: float,
        condo_price: float,
        commercial_rent: float,
        residential_cost: float,
        condo_cost: float,
        commercial_cost: float,
        rental_parking: int,
        sale_parking: int,
    ) -> tuple[DevelopmentPlan | None, float]:
        st.markdown(f"##### {name}")
        basic_1, basic_2 = st.columns(2)
        with basic_1:
            probability_pct = st.number_input(
                "Probability (%)",
                min_value=0.0,
                max_value=100.0,
                value=probability,
                step=5.0,
                key=f"{prefix}_probability",
            )
        with basic_2:
            development_years = st.number_input(
                "Years to completion",
                min_value=1,
                max_value=20,
                value=years,
                step=1,
                key=f"{prefix}_years",
            )

        st.caption("Use mix — must total 100%")
        mix_1, mix_2, mix_3 = st.columns(3)
        residential_share_pct = mix_1.number_input(
            "Residential rental (%)",
            min_value=0.0,
            max_value=100.0,
            value=residential_share,
            step=5.0,
            key=f"{prefix}_residential_share",
        )
        condo_share_pct = mix_2.number_input(
            "Condominium sales (%)",
            min_value=0.0,
            max_value=100.0,
            value=condo_share,
            step=5.0,
            key=f"{prefix}_condo_share",
        )
        commercial_share_pct = mix_3.number_input(
            "Commercial rental (%)",
            min_value=0.0,
            max_value=100.0,
            value=commercial_share,
            step=5.0,
            key=f"{prefix}_commercial_share",
        )
        use_total = (
            residential_share_pct + condo_share_pct + commercial_share_pct
        )
        if abs(use_total - 100.0) > 0.001:
            st.error(f"{name} use mix currently totals {use_total:.1f}%, not 100%.")

        st.caption("Market assumptions")
        market_1, market_2, market_3 = st.columns(3)
        residential_rent_value = market_1.number_input(
            "Residential rent (CHF/sqm/year)",
            min_value=0.0,
            value=residential_rent,
            step=10.0,
            key=f"{prefix}_residential_rent",
        )
        condo_price_value = market_2.number_input(
            "Condo selling price (CHF/sqm)",
            min_value=0.0,
            value=condo_price,
            step=100.0,
            key=f"{prefix}_condo_price",
        )
        commercial_rent_value = market_3.number_input(
            "Commercial rent (CHF/sqm/year)",
            min_value=0.0,
            value=commercial_rent,
            step=10.0,
            key=f"{prefix}_commercial_rent",
        )
        cap_1, cap_2 = st.columns(2)
        residential_cap_pct = cap_1.number_input(
            "Residential exit cap rate (%)",
            min_value=0.01,
            max_value=100.0,
            value=3.75,
            step=0.10,
            key=f"{prefix}_residential_cap",
        )
        commercial_cap_pct = cap_2.number_input(
            "Commercial exit cap rate (%)",
            min_value=0.01,
            max_value=100.0,
            value=4.75,
            step=0.10,
            key=f"{prefix}_commercial_cap",
        )

        st.caption("Construction and parking assumptions")
        cost_1, cost_2, cost_3 = st.columns(3)
        residential_cost_value = cost_1.number_input(
            "Residential rental cost (CHF/sqm)",
            min_value=0.0,
            value=residential_cost,
            step=100.0,
            key=f"{prefix}_residential_cost",
        )
        condo_cost_value = cost_2.number_input(
            "Condo construction cost (CHF/sqm)",
            min_value=0.0,
            value=condo_cost,
            step=100.0,
            key=f"{prefix}_condo_cost",
        )
        commercial_cost_value = cost_3.number_input(
            "Commercial construction cost (CHF/sqm)",
            min_value=0.0,
            value=commercial_cost,
            step=100.0,
            key=f"{prefix}_commercial_cost",
        )
        parking_1, parking_2, parking_3, parking_4 = st.columns(4)
        rental_parking_value = parking_1.number_input(
            "Rental spaces",
            min_value=0,
            value=rental_parking,
            step=1,
            key=f"{prefix}_rental_parking",
        )
        parking_rent_value = parking_2.number_input(
            "Rent/space/year (CHF)",
            min_value=0.0,
            value=2_400.0,
            step=100.0,
            key=f"{prefix}_parking_rent",
        )
        sale_parking_value = parking_3.number_input(
            "Spaces for sale",
            min_value=0,
            value=sale_parking,
            step=1,
            key=f"{prefix}_sale_parking",
        )
        parking_sale_price_value = parking_4.number_input(
            "Sale price/space (CHF)",
            min_value=0.0,
            value=60_000.0,
            step=2_500.0,
            key=f"{prefix}_parking_sale_price",
        )

        if abs(use_total - 100.0) > 0.001:
            return None, probability_pct
        return (
            DevelopmentPlan(
                name=name,
                probability=probability_pct / 100,
                development_years=int(development_years),
                residential_rental_share=residential_share_pct / 100,
                condo_sale_share=condo_share_pct / 100,
                commercial_rental_share=commercial_share_pct / 100,
                residential_rent_per_sqm=residential_rent_value,
                condo_sale_price_per_sqm=condo_price_value,
                commercial_rent_per_sqm=commercial_rent_value,
                residential_cap_rate=residential_cap_pct / 100,
                commercial_cap_rate=commercial_cap_pct / 100,
                residential_cost_per_sqm=residential_cost_value,
                condo_cost_per_sqm=condo_cost_value,
                commercial_cost_per_sqm=commercial_cost_value,
                rental_parking_spaces=int(rental_parking_value),
                annual_rent_per_parking_space=parking_rent_value,
                sale_parking_spaces=int(sale_parking_value),
                sale_price_per_parking_space=parking_sale_price_value,
            ),
            probability_pct,
        )

    plan_a_tab, plan_b_tab = st.tabs(["Plan A · Income-led", "Plan B · Sell-led"])
    with plan_a_tab:
        plan_a, plan_a_probability = development_plan_inputs(
            prefix="dev_a",
            name="Plan A",
            probability=60.0,
            years=3,
            residential_share=80.0,
            condo_share=0.0,
            commercial_share=20.0,
            residential_rent=420.0,
            condo_price=12_500.0,
            commercial_rent=350.0,
            residential_cost=5_500.0,
            condo_cost=5_700.0,
            commercial_cost=6_500.0,
            rental_parking=25,
            sale_parking=0,
        )
    with plan_b_tab:
        plan_b, plan_b_probability = development_plan_inputs(
            prefix="dev_b",
            name="Plan B",
            probability=40.0,
            years=4,
            residential_share=30.0,
            condo_share=60.0,
            commercial_share=10.0,
            residential_rent=430.0,
            condo_price=13_000.0,
            commercial_rent=360.0,
            residential_cost=5_700.0,
            condo_cost=5_900.0,
            commercial_cost=6_700.0,
            rental_parking=10,
            sale_parking=20,
        )

    probability_total = plan_a_probability + plan_b_probability
    if abs(probability_total - 100.0) > 0.001:
        st.error(
            f"Plan probabilities currently total {probability_total:.1f}%, not 100%."
        )
    elif plan_a is not None and plan_b is not None:
        comparison = compare_development_plans(
            development_project,
            (plan_a, plan_b),
        )
        st.divider()
        st.markdown("#### 3 · Feasibility decision")
        decision_1, decision_2, decision_3, decision_4 = st.columns(4)
        decision_1.metric(
            "Expected maximum land price",
            chf(comparison.expected_maximum_land_price),
        )
        decision_2.metric("Seller asking price", chf(dev_asking_land_price))
        decision_3.metric(
            "Expected NPV at asking",
            chf(comparison.expected_npv_at_asking_price),
        )
        decision_4.metric("Highest-value plan", comparison.preferred_plan_name)

        if comparison.expected_npv_at_asking_price >= 0:
            st.success(
                f"At the current assumptions, the land is financially supportable. "
                f"Do not pay more than approximately "
                f"{chf(comparison.expected_maximum_land_price)} on a "
                "probability-weighted basis."
            )
        else:
            st.error(
                f"The asking price is too high under the current assumptions. "
                f"A probability-weighted maximum price is approximately "
                f"{chf(comparison.expected_maximum_land_price)}."
            )

        development_memo = build_development_memo(
            development_project,
            comparison,
        )
        st.download_button(
            "Download Development Investment Committee memo (PDF)",
            data=development_memo,
            file_name="development_investment_committee_memo.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="download_development_memo",
        )

        comparison_frame = pd.DataFrame(
            [
                {
                    "Plan": analysis.plan.name,
                    "Probability": percentage(analysis.plan.probability),
                    "GFA (sqm)": analysis.gross_floor_area_sqm,
                    "NFA (sqm)": analysis.net_floor_area_sqm,
                    "GDV": analysis.gross_development_value,
                    "Development cost": analysis.total_nominal_development_cost,
                    "Maximum land price": analysis.maximum_supportable_land_price,
                    "NPV at asking": analysis.project_npv_at_asking_price,
                    "IRR": percentage(analysis.project_irr_at_asking_price),
                    "Profit margin": percentage(analysis.profit_margin_on_gdv),
                    "Recommendation": analysis.recommendation,
                }
                for analysis in comparison.analyses
            ]
        )
        st.dataframe(
            comparison_frame,
            use_container_width=True,
            hide_index=True,
            column_config={
                "GFA (sqm)": st.column_config.NumberColumn(format="%.0f"),
                "NFA (sqm)": st.column_config.NumberColumn(format="%.0f"),
                "GDV": st.column_config.NumberColumn(format="CHF %.0f"),
                "Development cost": st.column_config.NumberColumn(format="CHF %.0f"),
                "Maximum land price": st.column_config.NumberColumn(format="CHF %.0f"),
                "NPV at asking": st.column_config.NumberColumn(format="CHF %.0f"),
            },
        )

        price_chart_frame = pd.DataFrame(
            {
                "Case": [
                    analysis.plan.name for analysis in comparison.analyses
                ]
                + ["Seller asking price"],
                "CHF": [
                    analysis.maximum_supportable_land_price
                    for analysis in comparison.analyses
                ]
                + [dev_asking_land_price],
            }
        )
        price_figure = px.bar(
            price_chart_frame,
            x="Case",
            y="CHF",
            color="Case",
            title="Maximum supportable land price by plan",
        )
        price_figure.update_layout(showlegend=False)
        st.plotly_chart(price_figure, use_container_width=True)

        for analysis in comparison.analyses:
            with st.expander(f"{analysis.plan.name} · Detailed calculation"):
                value_col, cost_col = st.columns(2)
                with value_col:
                    st.markdown("**Completion value**")
                    st.write(
                        f"Residential income value: "
                        f"{chf(analysis.residential_income_value)}"
                    )
                    st.write(
                        f"Commercial income value: "
                        f"{chf(analysis.commercial_income_value)}"
                    )
                    st.write(f"Condo sales: {chf(analysis.condo_sales_value)}")
                    st.write(f"Parking sales: {chf(analysis.parking_sales_value)}")
                    st.write(f"Gross development value: **{chf(analysis.gross_development_value)}**")
                with cost_col:
                    st.markdown("**Residual calculation**")
                    st.write(
                        f"PV of completion proceeds: "
                        f"{chf(analysis.present_value_of_completion_proceeds)}"
                    )
                    st.write(
                        f"PV of development costs: "
                        f"{chf(analysis.present_value_of_development_cost)}"
                    )
                    st.write(
                        f"Residual before land costs: "
                        f"{chf(analysis.residual_land_value_before_acquisition_costs)}"
                    )
                    st.write(
                        f"Maximum supportable land price: "
                        f"**{chf(analysis.maximum_supportable_land_price)}**"
                    )
                annual_cost_frame = pd.DataFrame(
                    [
                        {
                            "Year": year.year,
                            "Construction": year.construction_cost,
                            "Professional fees": year.professional_fees,
                            "Contingency": year.contingency,
                            "Total cost": year.total_development_cost,
                            "PV of cost": year.present_value_of_cost,
                        }
                        for year in analysis.development_years
                    ]
                )
                st.dataframe(
                    annual_cost_frame,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        column: st.column_config.NumberColumn(format="CHF %.0f")
                        for column in (
                            "Construction",
                            "Professional fees",
                            "Contingency",
                            "Total cost",
                            "PV of cost",
                        )
                    },
                )

        st.markdown("#### 4 · Sensitivity of the preferred plan")
        preferred_analysis = next(
            analysis
            for analysis in comparison.analyses
            if analysis.plan.name == comparison.preferred_plan_name
        )
        sensitivity_points = development_sensitivity_grid(
            development_project,
            preferred_analysis.plan,
        )
        sensitivity_frame = pd.DataFrame(
            [
                {
                    "Construction cost change": f"{point.construction_cost_change:+.0%}",
                    "Revenue change": f"{point.revenue_change:+.0%}",
                    "Maximum land price": point.maximum_supportable_land_price,
                }
                for point in sensitivity_points
            ]
        )
        sensitivity_matrix = sensitivity_frame.pivot(
            index="Construction cost change",
            columns="Revenue change",
            values="Maximum land price",
        )
        ordered_labels = ["-10%", "-5%", "+0%", "+5%", "+10%"]
        sensitivity_matrix = sensitivity_matrix.reindex(
            index=ordered_labels,
            columns=ordered_labels,
        )
        sensitivity_figure = px.imshow(
            sensitivity_matrix,
            text_auto=",.0f",
            aspect="auto",
            color_continuous_scale="RdYlGn",
            labels={
                "x": "Revenue change",
                "y": "Construction-cost change",
                "color": "Max land price (CHF)",
            },
            title=(
                f"{comparison.preferred_plan_name}: maximum supportable land price"
            ),
        )
        st.plotly_chart(sensitivity_figure, use_container_width=True)
        st.info(
            "The maximum supportable land price is the purchase price that makes "
            "NPV equal to zero at the selected target discount rate. Plan "
            "probabilities represent alternative planning/outcome assumptions; "
            "the highest-value plan is shown separately from the probability-weighted result."
        )



st.title("Swiss Real Estate Underwriting Copilot")
st.caption(
    "Decision support for core acquisitions, value-add strategies and "
    "ground-up developments · Portfolio MVP v0.9"
)
if loaded_name := st.session_state.pop("_loaded_deal_notice", None):
    st.success(f"Loaded saved deal: {loaded_name}")

experience_mode = st.segmented_control(
    "Experience",
    options=["Full underwriting", "3-minute interview demo"],
    default="Full underwriting",
    selection_mode="single",
    key="experience_mode",
)
if experience_mode == "3-minute interview demo":
    render_interview_demo()
    st.stop()

st.markdown("### Choose your investment strategy")
strategy_options = {
    "Core Acquisition": (
        "Underwrite a stabilized, income-producing property."
    ),
    "Value-Add / Repositioning": (
        "Evaluate renovation, lease-up and operational value creation."
    ),
    "Ground-Up Development": (
        "Test development concepts and determine the maximum land price."
    ),
}
investment_strategy = st.segmented_control(
    "Investment strategy",
    options=list(strategy_options),
    default="Core Acquisition",
    selection_mode="single",
    label_visibility="collapsed",
    key="investment_strategy",
)
if investment_strategy is None:
    investment_strategy = "Core Acquisition"
st.caption(strategy_options[investment_strategy])

if investment_strategy == "Ground-Up Development":
    render_development_workflow()
    st.stop()

if investment_strategy == "Value-Add / Repositioning":
    render_value_add_workflow()
    st.stop()

with st.sidebar:
    st.header("Deal")
    property_name = st.text_input(
        "Property name",
        "Limmat Residential Case",
        key="property_name",
    )
    location = st.text_input(
        "Location",
        "Zürich, Switzerland",
        key="location",
    )
    st.divider()
    st.header("Investment criteria")
    target_unlevered_pct = st.number_input(
        "Target unlevered IRR (%)",
        min_value=0.0,
        value=6.0,
        step=0.25,
        key="target_unlevered_pct",
    )
    target_levered_pct = st.number_input(
        "Target levered IRR (%)",
        min_value=0.0,
        value=8.0,
        step=0.25,
        key="target_levered_pct",
    )
    minimum_dscr = st.number_input(
        "Minimum DSCR (x)",
        min_value=0.0,
        value=1.30,
        step=0.05,
        key="minimum_dscr",
    )
    margin_of_safety_pct = st.number_input(
        "Margin of safety (%)",
        min_value=0.0,
        value=5.0,
        step=0.5,
        key="margin_of_safety_pct",
    )
    st.divider()
    st.caption(
        "All calculations are transparent and based on the assumptions shown in the app."
    )

(
    input_tab,
    analysis_tab,
    scenarios_tab,
    benchmark_tab,
    comparables_tab,
    decision_tab,
    library_tab,
) = st.tabs(
    [
        "1 · Deal inputs",
        "2 · Base analysis",
        "3 · Scenarios",
        "4 · Market benchmarking",
        "5 · Comparable properties",
        "6 · Risks & decision",
        "7 · Deal library",
    ]
)

with input_tab:
    st.subheader("Property and operating assumptions")
    left, middle, right = st.columns(3)
    with left:
        purchase_price = st.number_input(
            "Asking price (CHF)",
            min_value=100_000.0,
            value=15_000_000.0,
            step=100_000.0,
            key="purchase_price",
        )
        potential_rent = st.number_input(
            "Potential annual rent (CHF)",
            min_value=0.0,
            value=900_000.0,
            step=10_000.0,
            key="potential_rent",
        )
        other_income = st.number_input(
            "Other annual income (CHF)",
            min_value=0.0,
            value=20_000.0,
            step=5_000.0,
            key="other_income",
        )
    with middle:
        vacancy_pct = st.number_input(
            "Vacancy (%)",
            min_value=0.0,
            max_value=99.0,
            value=4.0,
            step=0.25,
            key="vacancy_pct",
        )
        operating_expenses = st.number_input(
            "Annual operating expenses (CHF)",
            min_value=0.0,
            value=220_000.0,
            step=10_000.0,
            key="operating_expenses",
        )
        market_cap_pct = st.number_input(
            "Market cap rate (%)",
            min_value=0.1,
            max_value=30.0,
            value=4.25,
            step=0.05,
            key="market_cap_pct",
        )
    with right:
        rent_growth_pct = st.number_input(
            "Annual rent growth (%)",
            min_value=0.0,
            max_value=20.0,
            value=1.8,
            step=0.1,
            key="rent_growth_pct",
        )
        expense_growth_pct = st.number_input(
            "Annual expense growth (%)",
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.1,
            key="expense_growth_pct",
        )
        holding_period = st.number_input(
            "Holding period (years)",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            key="holding_period",
        )

    st.subheader("Valuation and financing assumptions")
    left, middle, right = st.columns(3)
    with left:
        discount_pct = st.number_input(
            "Discount rate (%)",
            min_value=0.1,
            max_value=30.0,
            value=6.0,
            step=0.1,
            key="discount_pct",
        )
        exit_cap_pct = st.number_input(
            "Exit cap rate (%)",
            min_value=0.1,
            max_value=30.0,
            value=4.5,
            step=0.05,
            key="exit_cap_pct",
        )
    with middle:
        ltv_pct = st.number_input(
            "Loan-to-value (%)",
            min_value=0.0,
            max_value=100.0,
            value=60.0,
            step=1.0,
            key="ltv_pct",
        )
        interest_pct = st.number_input(
            "Interest rate (%)",
            min_value=0.0,
            max_value=30.0,
            value=3.5,
            step=0.1,
            key="interest_pct",
        )
    with right:
        amortization_pct = st.number_input(
            "Annual amortization (%)",
            min_value=0.0,
            max_value=20.0,
            value=1.0,
            step=0.1,
            key="amortization_pct",
        )
        selling_cost_pct = st.number_input(
            "Selling costs (%)",
            min_value=0.0,
            max_value=20.0,
            value=1.2,
            step=0.1,
            key="selling_cost_pct",
        )

    st.subheader("Planned capital expenditure")
    capex_columns = st.columns(int(holding_period))
    capex: list[float] = []
    defaults = [0.0, 150_000.0, 800_000.0, 250_000.0, 0.0]
    for index, column in enumerate(capex_columns):
        with column:
            capex.append(
                st.number_input(
                    f"Year {index + 1}",
                    min_value=0.0,
                    value=defaults[index] if index < len(defaults) else 0.0,
                    step=50_000.0,
                    key=f"capex_{index}",
                )
            )

property_assumptions = PropertyAssumptions(
    name=property_name,
    location=location,
    purchase_price=purchase_price,
    potential_gross_rent=potential_rent,
    vacancy_rate=vacancy_pct / 100,
    operating_expenses=operating_expenses,
    other_income=other_income,
    market_cap_rate=market_cap_pct / 100,
    rent_growth_rate=rent_growth_pct / 100,
    expense_growth_rate=expense_growth_pct / 100,
    discount_rate=discount_pct / 100,
    exit_cap_rate=exit_cap_pct / 100,
    selling_cost_rate=selling_cost_pct / 100,
    holding_period_years=int(holding_period),
    capex_by_year=tuple(capex),
)
financing_assumptions = FinancingAssumptions(
    loan_to_value=ltv_pct / 100,
    interest_rate=interest_pct / 100,
    annual_amortization_rate=amortization_pct / 100,
)
criteria = InvestmentCriteria(
    target_unlevered_irr=target_unlevered_pct / 100,
    target_levered_irr=target_levered_pct / 100,
    minimum_dscr=minimum_dscr,
    margin_of_safety=margin_of_safety_pct / 100,
)
base = analyse_investment(property_assumptions, financing_assumptions)
scenario_results = standard_scenarios(property_assumptions, financing_assumptions)
decision = make_decision(base, scenario_results, criteria)

with analysis_tab:
    recommendation_colors = {
        "PROCEED TO DUE DILIGENCE": "#2e7d32",
        "PROCEED WITH CONDITIONS": "#1565c0",
        "NEGOTIATE": "#ef6c00",
        "REJECT AT CURRENT TERMS": "#c62828",
    }
    color = recommendation_colors.get(decision.recommendation, "#666")
    st.subheader("Base-case investment snapshot")
    st.markdown(
        f"<div style='padding:0.8rem 1rem;border-left:6px solid {color};"
        f"background:rgba(128,128,128,0.10);border-radius:0.35rem'>"
        f"<strong>Preliminary recommendation: {decision.recommendation}</strong><br>"
        f"{decision.summary}</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    row1 = st.columns(5)
    row1[0].metric("Year 1 NOI", chf(base.year_one_noi))
    row1[1].metric("Implied cap rate", percentage(base.implied_cap_rate))
    row1[2].metric(
        "DCF value",
        chf(base.dcf_value),
        percentage(base.dcf_value / base.property.purchase_price - 1),
    )
    row1[3].metric("Levered IRR", percentage(base.levered_irr))
    row1[4].metric("Minimum DSCR", f"{base.minimum_dscr:.2f}x")

    row2 = st.columns(5)
    row2[0].metric("Direct-cap value", chf(base.direct_cap_value))
    row2[1].metric("NPV", chf(base.npv_at_asking_price))
    row2[2].metric("Unlevered IRR", percentage(base.unlevered_irr))
    row2[3].metric("Equity multiple", f"{base.equity_multiple:.2f}x")
    row2[4].metric(
        "Break-even occupancy", percentage(base.break_even_occupancy_year_one)
    )

    projection_frame = pd.DataFrame(
        [
            {
                "Year": item.year,
                "Potential rent": item.potential_gross_rent,
                "Vacancy loss": item.vacancy_loss,
                "Effective income": item.effective_income,
                "Operating expenses": item.operating_expenses,
                "NOI": item.noi,
                "CapEx": item.capex,
                "Debt service": item.debt_service,
                "Cash flow to equity": item.cash_flow_to_equity_before_sale,
                "DSCR": item.dscr,
            }
            for item in base.projections
        ]
    )
    st.subheader("Annual projection")
    st.dataframe(
        projection_frame.style.format(
            {
                "Potential rent": "CHF {:,.0f}",
                "Vacancy loss": "CHF {:,.0f}",
                "Effective income": "CHF {:,.0f}",
                "Operating expenses": "CHF {:,.0f}",
                "NOI": "CHF {:,.0f}",
                "CapEx": "CHF {:,.0f}",
                "Debt service": "CHF {:,.0f}",
                "Cash flow to equity": "CHF {:,.0f}",
                "DSCR": "{:.2f}x",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    chart_frame = projection_frame.melt(
        id_vars="Year",
        value_vars=["NOI", "CapEx", "Debt service"],
        var_name="Metric",
        value_name="CHF",
    )
    st.plotly_chart(
        px.bar(
            chart_frame,
            x="Year",
            y="CHF",
            color="Metric",
            barmode="group",
            title="NOI, CapEx and debt service",
        ),
        use_container_width=True,
    )

with scenarios_tab:
    st.subheader("Base, upside and downside comparison")
    st.caption(
        "Upside assumes lower vacancy/financing cost and stronger rent growth. "
        "Downside assumes higher vacancy, financing cost, exit cap rate and CapEx."
    )
    scenario_frame = pd.DataFrame(
        [
            {
                "Scenario": item.name,
                "DCF value": item.analysis.dcf_value,
                "NPV": item.analysis.npv_at_asking_price,
                "Unlevered IRR": item.analysis.unlevered_irr,
                "Levered IRR": item.analysis.levered_irr,
                "Equity multiple": item.analysis.equity_multiple,
                "Minimum DSCR": item.analysis.minimum_dscr,
                "Exit cap rate": item.analysis.property.exit_cap_rate,
                "Vacancy": item.analysis.property.vacancy_rate,
            }
            for item in scenario_results
        ]
    )
    st.dataframe(
        scenario_frame.style.format(
            {
                "DCF value": "CHF {:,.0f}",
                "NPV": "CHF {:,.0f}",
                "Unlevered IRR": "{:.2%}",
                "Levered IRR": "{:.2%}",
                "Equity multiple": "{:.2f}x",
                "Minimum DSCR": "{:.2f}x",
                "Exit cap rate": "{:.2%}",
                "Vacancy": "{:.2%}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.plotly_chart(
        px.bar(
            scenario_frame,
            x="Scenario",
            y="DCF value",
            color="Scenario",
            text_auto=".3s",
            title="DCF value by scenario",
        ),
        use_container_width=True,
    )

    st.subheader("Scenario assumptions")
    assumptions_frame = pd.DataFrame(
        [
            {
                "Scenario": item.name,
                "Vacancy": item.analysis.property.vacancy_rate,
                "Rent growth": item.analysis.property.rent_growth_rate,
                "Expense growth": item.analysis.property.expense_growth_rate,
                "Discount rate": item.analysis.property.discount_rate,
                "Exit cap rate": item.analysis.property.exit_cap_rate,
                "Interest rate": item.analysis.financing.interest_rate,
                "Total CapEx": sum(item.analysis.property.capex_by_year),
            }
            for item in scenario_results
        ]
    )
    st.dataframe(
        assumptions_frame.style.format(
            {
                "Vacancy": "{:.2%}",
                "Rent growth": "{:.2%}",
                "Expense growth": "{:.2%}",
                "Discount rate": "{:.2%}",
                "Exit cap rate": "{:.2%}",
                "Interest rate": "{:.2%}",
                "Total CapEx": "CHF {:,.0f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Exit cap rate × rent growth sensitivity")
    st.caption(
        "Each cell shows the DCF value. Lower exit cap rates and stronger rent growth "
        "increase value."
    )
    sensitivity_points = sensitivity_grid(property_assumptions, financing_assumptions)
    sensitivity_frame = pd.DataFrame(
        [
            {
                "Exit cap rate": f"{point.exit_cap_rate:.2%}",
                "Rent growth": f"{point.rent_growth_rate:.2%}",
                "DCF value": point.dcf_value,
                "Levered IRR": point.levered_irr,
            }
            for point in sensitivity_points
        ]
    )
    value_matrix = sensitivity_frame.pivot(
        index="Exit cap rate",
        columns="Rent growth",
        values="DCF value",
    )
    st.plotly_chart(
        px.imshow(
            value_matrix,
            text_auto=".3s",
            aspect="auto",
            color_continuous_scale="RdYlGn",
            labels={"color": "DCF value (CHF)"},
            title="DCF value sensitivity",
        ),
        use_container_width=True,
    )

    irr_matrix = sensitivity_frame.pivot(
        index="Exit cap rate",
        columns="Rent growth",
        values="Levered IRR",
    )
    st.plotly_chart(
        px.imshow(
            irr_matrix,
            text_auto=".1%",
            aspect="auto",
            color_continuous_scale="RdYlGn",
            labels={"color": "Levered IRR"},
            title="Levered IRR sensitivity",
        ),
        use_container_width=True,
    )

with benchmark_tab:
    st.subheader("Market benchmark assumptions")
    st.caption(
        "Enter traceable market evidence. These values are manual benchmarks—not "
        "live market data—and remain separate from the property underwriting inputs."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        rentable_area_sqm = st.number_input(
            "Rentable area (m²)",
            min_value=1.0,
            value=2_500.0,
            step=50.0,
            key="rentable_area_sqm",
        )
        market_rent_sqm = st.number_input(
            "Market rent (CHF/m²/year)",
            min_value=0.0,
            value=380.0,
            step=5.0,
            key="market_rent_sqm",
        )
        market_vacancy_pct = st.number_input(
            "Market vacancy (%)",
            min_value=0.0,
            max_value=99.0,
            value=2.5,
            step=0.25,
            key="market_vacancy_pct",
        )
    with col2:
        market_price_sqm = st.number_input(
            "Comparable price (CHF/m²)",
            min_value=0.0,
            value=5_500.0,
            step=100.0,
            key="market_price_sqm",
        )
        market_cap_low_pct = st.number_input(
            "Market cap range – low (%)",
            min_value=0.1,
            max_value=30.0,
            value=4.0,
            step=0.05,
            key="market_cap_low_pct",
        )
        market_cap_high_pct = st.number_input(
            "Market cap range – high (%)",
            min_value=0.1,
            max_value=30.0,
            value=4.5,
            step=0.05,
            key="market_cap_high_pct",
        )
    with col3:
        market_opex_sqm = st.number_input(
            "Market operating expenses (CHF/m²/year)",
            min_value=0.0,
            value=90.0,
            step=5.0,
            key="market_opex_sqm",
        )
        benchmark_source = st.text_input(
            "Source / reference",
            "Illustrative benchmark – replace with documented market evidence",
            key="benchmark_source",
        )
        benchmark_date = st.text_input(
            "Benchmark date",
            "2026-Q2",
            key="benchmark_date",
        )

    if market_cap_high_pct < market_cap_low_pct:
        st.error("The high end of the market cap range must be at least the low end.")
        benchmark_analysis = None
    else:
        market_benchmarks = MarketBenchmarks(
            rentable_area_sqm=rentable_area_sqm,
            market_rent_per_sqm=market_rent_sqm,
            market_vacancy_rate=market_vacancy_pct / 100,
            market_price_per_sqm=market_price_sqm,
            market_cap_rate_low=market_cap_low_pct / 100,
            market_cap_rate_high=market_cap_high_pct / 100,
            market_opex_per_sqm=market_opex_sqm,
            source=benchmark_source,
            as_of_date=benchmark_date,
        )
        benchmark_analysis = analyse_market_benchmarks(base, market_benchmarks)

        st.subheader("Subject property vs selected market evidence")
        metric_columns = st.columns(4)
        metric_columns[0].metric(
            "Subject rent / m²",
            f"CHF {benchmark_analysis.subject_rent_per_sqm:,.0f}",
            f"{benchmark_analysis.subject_rent_per_sqm / market_rent_sqm - 1:.1%}"
            if market_rent_sqm
            else None,
        )
        metric_columns[1].metric(
            "Asking price / m²",
            f"CHF {benchmark_analysis.subject_price_per_sqm:,.0f}",
            f"{benchmark_analysis.subject_price_per_sqm / market_price_sqm - 1:.1%}"
            if market_price_sqm
            else None,
            delta_color="inverse",
        )
        metric_columns[2].metric(
            "Implied cap rate",
            percentage(base.implied_cap_rate),
            f"{(base.implied_cap_rate - benchmark_analysis.market_cap_rate_midpoint) * 10_000:+.0f} bps",
        )
        metric_columns[3].metric(
            "Annual rent reversion",
            chf(benchmark_analysis.rent_upside_annual),
            help="Positive means the selected market rent is above the property's potential rent.",
        )

        def display_value(metric: str, value: float) -> str:
            if metric in {"Vacancy", "Implied cap rate"}:
                return f"{value:.2%}"
            return f"CHF {value:,.0f}"

        benchmark_frame = pd.DataFrame(
            [
                {
                    "Metric": item.metric,
                    "Subject": display_value(item.metric, item.subject_value),
                    "Market benchmark": display_value(item.metric, item.market_value),
                    "Difference": (
                        f"{item.difference * 10_000:+.0f} bps"
                        if item.metric in {"Vacancy", "Implied cap rate"}
                        else f"{item.difference:+.1%}"
                    ),
                    "Signal": item.status,
                    "Interpretation": item.interpretation,
                }
                for item in benchmark_analysis.indicators
            ]
        )
        st.dataframe(benchmark_frame, use_container_width=True, hide_index=True)

        st.subheader("Indicative market-supported values")
        value_columns = st.columns(3)
        value_columns[0].metric(
            "Income benchmark",
            chf(benchmark_analysis.indicative_market_value_income),
            help="Benchmark market NOI capitalized at the midpoint market cap rate.",
        )
        value_columns[1].metric(
            "Comparable-price benchmark",
            chf(benchmark_analysis.indicative_market_value_price_per_sqm),
            help="Selected comparable CHF/m² multiplied by rentable area.",
        )
        value_columns[2].metric(
            "Blended indication",
            chf(benchmark_analysis.blended_market_value),
            f"{benchmark_analysis.blended_market_value / purchase_price - 1:.1%}",
        )

        value_frame = pd.DataFrame(
            {
                "Method": [
                    "Asking price",
                    "DCF value",
                    "Income benchmark",
                    "Comparable-price benchmark",
                    "Blended market indication",
                ],
                "Value": [
                    purchase_price,
                    base.dcf_value,
                    benchmark_analysis.indicative_market_value_income,
                    benchmark_analysis.indicative_market_value_price_per_sqm,
                    benchmark_analysis.blended_market_value,
                ],
            }
        )
        st.plotly_chart(
            px.bar(
                value_frame,
                x="Method",
                y="Value",
                text_auto=".3s",
                title="Valuation cross-check",
            ),
            use_container_width=True,
        )
        st.info(
            f"Source: {benchmark_source} · As of: {benchmark_date}. "
            "The outputs are indicative cross-checks, not an appraisal."
        )

with comparables_tab:
    st.subheader("Comparable properties")
    st.caption(
        "Build an auditable comparable set. The default rows are fictional demo "
        "observations; replace them with documented evidence before external use."
    )
    settings_left, settings_right = st.columns(2)
    with settings_left:
        subject_property_type = st.selectbox(
            "Subject property type",
            ["Residential", "Office", "Retail", "Logistics", "Mixed use"],
            key="subject_property_type",
        )
    with settings_right:
        comparables_file = st.file_uploader(
            "Upload comparables CSV",
            type=["csv"],
            help="Use the same column names shown in the editable table.",
        )

    default_comparables = pd.DataFrame(
        [
            {
                "Name": "Demo Zürich North",
                "Location": "Zürich",
                "Property type": "Residential",
                "Price (CHF)": 14_200_000,
                "Rentable area (m²)": 2_420,
                "Annual rent (CHF)": 875_000,
                "Date": "2026-03-15",
                "Distance (km)": 3.5,
                "Condition vs subject": "Similar",
                "Source URL": "",
            },
            {
                "Name": "Demo Limmat West",
                "Location": "Zürich",
                "Property type": "Residential",
                "Price (CHF)": 13_500_000,
                "Rentable area (m²)": 2_550,
                "Annual rent (CHF)": 820_000,
                "Date": "2025-11-30",
                "Distance (km)": 5.0,
                "Condition vs subject": "Inferior",
                "Source URL": "",
            },
            {
                "Name": "Demo Zürich Central",
                "Location": "Zürich",
                "Property type": "Residential",
                "Price (CHF)": 16_100_000,
                "Rentable area (m²)": 2_600,
                "Annual rent (CHF)": 940_000,
                "Date": "2026-01-20",
                "Distance (km)": 2.0,
                "Condition vs subject": "Superior",
                "Source URL": "",
            },
            {
                "Name": "Demo Altstetten",
                "Location": "Zürich",
                "Property type": "Residential",
                "Price (CHF)": 12_900_000,
                "Rentable area (m²)": 2_350,
                "Annual rent (CHF)": 790_000,
                "Date": "2025-08-10",
                "Distance (km)": 7.5,
                "Condition vs subject": "Similar",
                "Source URL": "",
            },
        ]
    )
    if comparables_file is not None:
        try:
            comparable_input_frame = pd.read_csv(comparables_file)
            editor_key = f"comparables_{hash(comparables_file.getvalue())}"
        except Exception as error:
            st.error(f"The CSV could not be read: {error}")
            comparable_input_frame = default_comparables
            editor_key = "comparables_default"
    elif st.session_state.get("_comparable_seed"):
        comparable_input_frame = pd.DataFrame(st.session_state["_comparable_seed"])
        editor_key = (
            "comparables_loaded_"
            f"{st.session_state.get('_comparables_editor_version', 0)}"
        )
    else:
        comparable_input_frame = default_comparables
        editor_key = "comparables_default"

    required_columns = list(default_comparables.columns)
    for column in required_columns:
        if column not in comparable_input_frame.columns:
            comparable_input_frame[column] = ""
    comparable_input_frame = comparable_input_frame[required_columns]

    edited_comparables = st.data_editor(
        comparable_input_frame,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        column_config={
            "Property type": st.column_config.SelectboxColumn(
                options=["Residential", "Office", "Retail", "Logistics", "Mixed use"]
            ),
            "Condition vs subject": st.column_config.SelectboxColumn(
                options=["Inferior", "Similar", "Superior"]
            ),
            "Source URL": st.column_config.LinkColumn(display_text="Open source"),
        },
    )
    st.download_button(
        "Download comparable set (CSV)",
        data=edited_comparables.to_csv(index=False).encode("utf-8"),
        file_name="comparable_properties.csv",
        mime="text/csv",
    )

    comparable_records: list[ComparableProperty] = []
    invalid_rows: list[str] = []
    for row_number, row in edited_comparables.iterrows():
        if not str(row.get("Name", "")).strip():
            continue
        try:
            comparable_records.append(
                ComparableProperty(
                    name=str(row["Name"]).strip(),
                    location=str(row["Location"]).strip(),
                    property_type=str(row["Property type"]).strip(),
                    price=float(row["Price (CHF)"]),
                    rentable_area_sqm=float(row["Rentable area (m²)"]),
                    annual_rent=float(row["Annual rent (CHF)"] or 0),
                    transaction_date=str(row["Date"]).strip(),
                    distance_km=float(row["Distance (km)"]),
                    condition_vs_subject=str(row["Condition vs subject"]).strip(),
                    source_url=str(row["Source URL"]).strip(),
                )
            )
        except (TypeError, ValueError) as error:
            invalid_rows.append(f"Row {row_number + 1}: {error}")

    if invalid_rows:
        st.warning("Some rows were excluded:\n\n" + "\n\n".join(invalid_rows))

    comparable_analysis = None
    if comparable_records:
        comparable_analysis = analyse_comparables(
            tuple(comparable_records),
            subject_area_sqm=rentable_area_sqm,
            subject_property_type=subject_property_type,
        )
        st.subheader("Comparable-set conclusion")
        summary_columns = st.columns(4)
        summary_columns[0].metric(
            "Adjusted indication",
            chf(comparable_analysis.indicated_value),
            f"{comparable_analysis.indicated_value / purchase_price - 1:.1%}",
        )
        summary_columns[1].metric(
            "Value range",
            f"{chf(comparable_analysis.lower_value)} – "
            f"{chf(comparable_analysis.upper_value)}",
        )
        summary_columns[2].metric(
            "Weighted CHF/m²",
            f"CHF {comparable_analysis.weighted_adjusted_price_per_sqm:,.0f}",
        )
        summary_columns[3].metric(
            "Evidence confidence",
            comparable_analysis.confidence,
            f"{len(comparable_analysis.results)} comparables · "
            f"{comparable_analysis.average_relevance_score:.0f}/100 avg. score",
            delta_color="off",
        )

        result_frame = pd.DataFrame(
            [
                {
                    "Comparable": item.comparable.name,
                    "Location": item.comparable.location,
                    "Price / m²": item.price_per_sqm,
                    "Gross yield": item.gross_yield,
                    "Condition adjustment": item.adjustment,
                    "Adjusted price / m²": item.adjusted_price_per_sqm,
                    "Relevance score": item.relevance_score,
                    "Source": item.comparable.source_url,
                }
                for item in comparable_analysis.results
            ]
        )
        st.dataframe(
            result_frame.style.format(
                {
                    "Price / m²": "CHF {:,.0f}",
                    "Gross yield": lambda value: (
                        "n/a" if pd.isna(value) else f"{value:.2%}"
                    ),
                    "Condition adjustment": "{:+.1%}",
                    "Adjusted price / m²": "CHF {:,.0f}",
                    "Relevance score": "{:.0f}/100",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        chart_data = result_frame.copy()
        chart_data["Subject asking price / m²"] = purchase_price / rentable_area_sqm
        st.plotly_chart(
            px.scatter(
                chart_data,
                x="Relevance score",
                y="Adjusted price / m²",
                size="Relevance score",
                hover_name="Comparable",
                title="Adjusted pricing evidence by relevance",
            ).add_hline(
                y=purchase_price / rentable_area_sqm,
                line_dash="dash",
                annotation_text="Subject asking price / m²",
            ),
            use_container_width=True,
        )
        st.info(
            "Adjustment convention: inferior comparable +5%, similar 0%, superior "
            "-5%. Relevance score combines property type (30%), distance (25%), "
            "size similarity (25%) and recency (20%)."
        )
    else:
        st.info("Add at least one complete comparable to run the analysis.")

with decision_tab:
    st.subheader("Preliminary investment decision")
    color = {
        "PROCEED TO DUE DILIGENCE": "#2e7d32",
        "PROCEED WITH CONDITIONS": "#1565c0",
        "NEGOTIATE": "#ef6c00",
        "REJECT AT CURRENT TERMS": "#c62828",
    }.get(decision.recommendation, "#666")
    st.markdown(
        f"<div style='padding:1rem 1.2rem;border-left:7px solid {color};"
        f"background:rgba(128,128,128,0.10);border-radius:0.4rem'>"
        f"<div style='font-size:1.35rem;font-weight:700'>{decision.recommendation}</div>"
        f"<div>{decision.summary}</div></div>",
        unsafe_allow_html=True,
    )
    st.write("")
    price_columns = st.columns(3)
    price_columns[0].metric("Asking price", chf(base.property.purchase_price))
    price_columns[1].metric("Maximum DCF price", chf(decision.maximum_price_dcf))
    price_columns[2].metric(
        "Recommended offer",
        chf(decision.recommended_price),
        f"{decision.recommended_price / base.property.purchase_price - 1:.1%}",
    )
    if decision.maximum_price_target_irr is not None:
        st.caption(
            f"Maximum price supporting the {criteria.target_levered_irr:.2%} "
            f"levered-IRR target: {chf(decision.maximum_price_target_irr)}."
        )

    if decision.reasons:
        st.markdown("#### Why")
        for reason in decision.reasons:
            st.write(f"• {reason}")

    st.markdown("#### Risk register")
    if decision.risks:
        severity_order = {"High": 0, "Medium": 1, "Low": 2}
        risk_frame = pd.DataFrame(
            [
                {
                    "Severity": risk.severity,
                    "Category": risk.category,
                    "Finding": risk.finding,
                    "Evidence": risk.evidence,
                    "Required action": risk.action,
                }
                for risk in sorted(
                    decision.risks,
                    key=lambda risk: severity_order.get(risk.severity, 3),
                )
            ]
        )
        st.dataframe(risk_frame, use_container_width=True, hide_index=True)
    else:
        st.success("No material rule-based risks were triggered.")

    st.markdown("#### Conditions before Investment Committee")
    for condition in decision.conditions:
        st.write(f"• {condition}")

    st.info(
        "This is a preliminary, rule-based recommendation. It does not replace "
        "professional valuation, legal/technical due diligence or Investment "
        "Committee judgment."
    )
    memo_pdf = build_ic_memo(
        base,
        scenario_results,
        decision,
        criteria,
        benchmark_analysis,
        comparable_analysis,
    )
    safe_name = "".join(
        character if character.isalnum() else "_"
        for character in base.property.name.lower()
    ).strip("_")
    st.download_button(
        "Download Investment Committee memo (PDF)",
        data=memo_pdf,
        file_name=f"{safe_name or 'investment'}_ic_memo.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

with library_tab:
    st.subheader("Deal library")
    st.caption(
        "Save a complete local snapshot of the underwriting assumptions, market "
        "benchmarks and comparable-property set."
    )

    widget_keys = (
        "property_name",
        "location",
        "target_unlevered_pct",
        "target_levered_pct",
        "minimum_dscr",
        "margin_of_safety_pct",
        "purchase_price",
        "potential_rent",
        "other_income",
        "vacancy_pct",
        "operating_expenses",
        "market_cap_pct",
        "rent_growth_pct",
        "expense_growth_pct",
        "holding_period",
        "discount_pct",
        "exit_cap_pct",
        "ltv_pct",
        "interest_pct",
        "amortization_pct",
        "selling_cost_pct",
        "rentable_area_sqm",
        "market_rent_sqm",
        "market_vacancy_pct",
        "market_price_sqm",
        "market_cap_low_pct",
        "market_cap_high_pct",
        "market_opex_sqm",
        "benchmark_source",
        "benchmark_date",
        "subject_property_type",
    )
    widget_values = {key: st.session_state[key] for key in widget_keys}
    for index in range(int(holding_period)):
        widget_values[f"capex_{index}"] = st.session_state.get(
            f"capex_{index}",
            0.0,
        )
    serializable_comparables = (
        edited_comparables.astype(object)
        .where(pd.notna(edited_comparables), None)
        .to_dict(orient="records")
    )
    current_payload = {
        "schema_version": 1,
        "widget_values": widget_values,
        "comparables": serializable_comparables,
    }

    save_left, save_right = st.columns([2, 1])
    with save_left:
        snapshot_name = st.text_input(
            "Snapshot name",
            value=property_name,
            key="snapshot_name",
        )
    with save_right:
        st.write("")
        st.write("")
        save_clicked = st.button(
            "Save current deal",
            type="primary",
            use_container_width=True,
        )
    if save_clicked:
        active_deal_id = st.session_state.get("_active_deal_id")
        saved_id = deal_store.save(
            name=snapshot_name,
            location=location,
            payload=current_payload,
            deal_id=active_deal_id,
        )
        st.session_state["_active_deal_id"] = saved_id
        st.success(
            "Deal updated successfully."
            if active_deal_id
            else "Deal saved successfully."
        )

    st.markdown("#### Portable snapshot")
    portable_left, portable_right = st.columns(2)
    with portable_left:
        portable_name = "".join(
            character if character.isalnum() else "_"
            for character in snapshot_name.lower()
        ).strip("_")
        st.download_button(
            "Export current deal (JSON)",
            data=json.dumps(
                current_payload,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            file_name=f"{portable_name or 'deal'}_snapshot.json",
            mime="application/json",
            use_container_width=True,
        )
    with portable_right:
        portable_upload = st.file_uploader(
            "Import deal snapshot",
            type=["json"],
            key="portable_deal_upload",
            label_visibility="collapsed",
        )
        if st.button(
            "Load imported JSON",
            disabled=portable_upload is None,
            use_container_width=True,
        ):
            try:
                imported_payload = json.loads(portable_upload.getvalue())
                if (
                    not isinstance(imported_payload, dict)
                    or "widget_values" not in imported_payload
                    or "comparables" not in imported_payload
                ):
                    raise ValueError("Unsupported deal snapshot structure")
                imported_name = imported_payload["widget_values"].get(
                    "property_name",
                    "Imported deal",
                )
                st.session_state["_pending_deal_payload"] = {
                    **imported_payload,
                    "deal_id": None,
                    "deal_name": imported_name,
                }
                st.rerun()
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                st.error(f"The snapshot could not be imported: {error}")

    saved_deals = deal_store.list()
    st.divider()
    st.markdown("#### Saved deals")
    if not saved_deals:
        st.info("No saved deals yet.")
    else:
        saved_frame = pd.DataFrame(
            [
                {
                    "Name": item.name,
                    "Location": item.location,
                    "Updated": item.updated_at.replace("T", " ").replace("+00:00", " UTC"),
                }
                for item in saved_deals
            ]
        )
        st.dataframe(saved_frame, use_container_width=True, hide_index=True)
        selected_deal_id = st.selectbox(
            "Select a saved deal",
            options=[item.deal_id for item in saved_deals],
            format_func=lambda identifier: next(
                item.name for item in saved_deals if item.deal_id == identifier
            ),
        )
        if st.button("Load selected deal", use_container_width=True):
            selected = deal_store.get(selected_deal_id)
            if selected is None:
                st.error("The selected deal could not be found.")
            else:
                st.session_state["_pending_deal_payload"] = {
                    **selected.payload,
                    "deal_id": selected.deal_id,
                    "deal_name": selected.name,
                }
                st.rerun()

    st.info(
        f"Local database: {deal_store.database_path}. "
        "When we publish the app online, we will replace local persistence with "
        "a hosted database or downloadable project files."
    )
