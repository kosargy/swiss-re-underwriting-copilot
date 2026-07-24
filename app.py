from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

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


st.title("Swiss Real Estate Underwriting Copilot")
st.caption(
    "Preliminary underwriting for Swiss income-producing residential properties · "
    "Portfolio MVP v0.4"
)
if loaded_name := st.session_state.pop("_loaded_deal_notice", None):
    st.success(f"Loaded saved deal: {loaded_name}")

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
