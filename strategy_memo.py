from __future__ import annotations

from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from development import DevelopmentComparison, DevelopmentProject
from value_add import ValueAddAnalysis


NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#246B8E")
GREY = colors.HexColor("#667780")
PALE = colors.HexColor("#F4F6F7")
GREEN = colors.HexColor("#247A45")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B42318")
WHITE = colors.white


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}CHF {abs(value):,.0f}"


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "StrategyTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=27,
            textColor=NAVY,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "StrategySubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=GREY,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "StrategySection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "StrategyBody",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#36454F"),
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "MetricValueGeneric",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            "MetricLabelGeneric",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
            textColor=GREY,
            alignment=TA_CENTER,
        )
    )
    return styles


def _header_footer(canvas, document) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D7DFE3"))
    canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(NAVY)
    canvas.drawString(18 * mm, height - 11 * mm, "SWISS RE UNDERWRITING COPILOT")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GREY)
    canvas.drawRightString(
        width - 18 * mm,
        height - 11 * mm,
        "PRELIMINARY - FOR DISCUSSION ONLY",
    )
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.drawString(18 * mm, 10.5 * mm, f"Generated {date.today().isoformat()}")
    canvas.drawRightString(width - 18 * mm, 10.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def _p(
    value: object,
    styles,
    *,
    bold: bool = False,
    white: bool = False,
) -> Paragraph:
    text = escape(str(value))
    if bold:
        text = f"<b>{text}</b>"
    if white:
        text = f"<font color='#FFFFFF'>{text}</font>"
    return Paragraph(text, styles["StrategyBody"])


def _table(rows: list[list[object]], widths: list[float], styles) -> Table:
    rendered = []
    for row_index, row in enumerate(rows):
        rendered.append(
            [
                _p(
                    value,
                    styles,
                    bold=row_index == 0,
                    white=row_index == 0,
                )
                for value in row
            ]
        )
    table = Table(rendered, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DFE3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _metric_cards(metrics: list[tuple[str, str]], styles) -> Table:
    cells = [
        [
            Paragraph(value, styles["MetricValueGeneric"]),
            Spacer(1, 1 * mm),
            Paragraph(label, styles["MetricLabelGeneric"]),
        ]
        for label, value in metrics
    ]
    rows = [cells[index : index + 3] for index in range(0, len(cells), 3)]
    table = Table(rows, colWidths=[52.3 * mm] * 3, rowHeights=22 * mm)
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD6DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD6DB")),
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _recommendation_banner(
    recommendation: str,
    summary: str,
    styles,
) -> Table:
    upper = recommendation.upper()
    color = (
        GREEN
        if "ATTRACTIVE" in upper or "FEASIBLE" in upper or "PROCEED" in upper
        else ORANGE if "NEGOTIATE" in upper else RED
    )
    table = Table(
        [
            [
                _p(recommendation, styles, bold=True, white=True),
                _p(summary, styles, white=True),
            ]
        ],
        colWidths=[56 * mm, 101 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _build_document(
    *,
    title: str,
    subtitle: str,
    recommendation: str,
    recommendation_summary: str,
    metrics: list[tuple[str, str]],
    executive_summary: str,
    assumptions: list[list[object]],
    analysis_rows: list[list[object]],
    risks: list[str],
    due_diligence: list[str],
    final_recommendation: str,
) -> bytes:
    buffer = BytesIO()
    styles = _styles()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=title,
        author="Swiss Real Estate Underwriting Copilot",
    )
    story: list = [
        Spacer(1, 5 * mm),
        Paragraph("Investment Committee Memo", styles["StrategyTitle"]),
        Paragraph(subtitle, styles["StrategySubtitle"]),
        _recommendation_banner(
            recommendation,
            recommendation_summary,
            styles,
        ),
        Spacer(1, 5 * mm),
        _metric_cards(metrics, styles),
        Paragraph("1. Executive summary", styles["StrategySection"]),
        Paragraph(executive_summary, styles["StrategyBody"]),
        Paragraph("2. Key underwriting assumptions", styles["StrategySection"]),
        _table(assumptions, [57 * mm, 38 * mm, 40 * mm, 22 * mm], styles),
        PageBreak(),
        Paragraph("3. Financial analysis", styles["StrategySection"]),
        _table(analysis_rows, [18 * mm, 29 * mm, 31 * mm, 31 * mm, 31 * mm, 27 * mm], styles),
        Paragraph("4. Principal risks", styles["StrategySection"]),
    ]
    for risk in risks:
        story.append(Paragraph(f"- {escape(risk)}", styles["StrategyBody"]))
    story.append(Paragraph("5. Required due diligence", styles["StrategySection"]))
    for item in due_diligence:
        story.append(Paragraph(f"- {escape(item)}", styles["StrategyBody"]))
    story.extend(
        [
            Paragraph("6. Recommendation", styles["StrategySection"]),
            Paragraph(final_recommendation, styles["StrategyBody"]),
            Spacer(1, 5 * mm),
            Paragraph(
                "This automated memo is a preliminary analytical output based on "
                "user-entered assumptions. It is not a certified valuation, lending "
                "decision or investment recommendation.",
                styles["StrategyBody"],
            ),
        ]
    )
    document.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buffer.getvalue()


def build_value_add_memo(analysis: ValueAddAnalysis) -> bytes:
    project = analysis.project
    pricing_gap = project.purchase_price - analysis.maximum_supportable_purchase_price
    summary = (
        f"The asset is offered at {_money(project.purchase_price)}. The business plan "
        f"requires {_money(project.total_renovation_capex)} of renovation CapEx and "
        f"increases NOI from {_money(analysis.current_noi)} to "
        f"{_money(analysis.stabilized_noi)}. The maximum supportable purchase price "
        f"is {_money(analysis.maximum_supportable_purchase_price)}."
    )
    assumptions = [
        ["Property", "Value", "Business plan", "Value"],
        ["Asking price", _money(project.purchase_price), "Renovation period", f"{project.renovation_years} years"],
        ["Current rent", _money(project.current_potential_rent), "Renovation CapEx", _money(project.total_renovation_capex)],
        ["Current vacancy", _percent(project.current_vacancy_rate), "Income retained", _percent(project.income_retention_during_renovation)],
        ["Stabilized rent", _money(project.stabilized_potential_rent), "Exit cap rate", _percent(project.exit_cap_rate)],
        ["Purchase LTV", _percent(analysis.financing.purchase_loan_to_value), "Interest rate", _percent(analysis.financing.interest_rate)],
    ]
    analysis_rows = [["Year", "Phase", "NOI", "CapEx", "Debt service", "Equity CF"]]
    analysis_rows.extend(
        [
            item.year,
            item.phase,
            _money(item.noi),
            _money(item.renovation_capex),
            _money(item.debt_service),
            _money(item.equity_cash_flow_before_sale),
        ]
        for item in analysis.projections
    )
    rent_uplift = (
        project.stabilized_potential_rent / project.current_potential_rent - 1.0
        if project.current_potential_rent
        else 0.0
    )
    risks = [
        f"The business plan assumes a {rent_uplift:.1%} increase in potential rent.",
        f"Only {project.income_retention_during_renovation:.0%} of occupied income is retained during works.",
        "Renovation CapEx is modelled as equity-funded; alternative debt funding would change equity returns and covenants.",
        f"The exit valuation depends on a {project.exit_cap_rate:.2%} capitalization rate.",
    ]
    due_diligence = [
        "Validate the unit-level rent roll, lease expiry profile and legal rent-uplift potential.",
        "Obtain a technical condition survey and independently cost the renovation scope.",
        "Confirm tenant relocation, phasing, permits and the achievable construction programme.",
        "Stress-test lender covenants and liquidity during negative renovation cash flows.",
    ]
    final = (
        f"{escape(analysis.recommendation)}. Do not exceed approximately "
        f"<b>{_money(analysis.maximum_supportable_purchase_price)}</b> under the base "
        f"case. The asking-price gap is <b>{_money(pricing_gap)}</b>. Proceed only "
        "after validating rents, renovation costs, phasing and financing capacity."
    )
    return _build_document(
        title=f"Value-Add IC Memo - {project.name}",
        subtitle=(
            f"<b>{escape(project.name)}</b><br/>{escape(project.location)}<br/>"
            "Value-Add / Repositioning underwriting"
        ),
        recommendation=analysis.recommendation,
        recommendation_summary=(
            f"Maximum bid {_money(analysis.maximum_supportable_purchase_price)}; "
            f"levered IRR {_percent(analysis.levered_irr)}."
        ),
        metrics=[
            ("Asking price", _money(project.purchase_price)),
            ("Maximum purchase price", _money(analysis.maximum_supportable_purchase_price)),
            ("Stabilized value", _money(analysis.stabilized_value)),
            ("Unlevered IRR", _percent(analysis.unlevered_irr)),
            ("Levered IRR", _percent(analysis.levered_irr)),
            ("Value after CapEx", _money(analysis.incremental_value_created)),
        ],
        executive_summary=summary,
        assumptions=assumptions,
        analysis_rows=analysis_rows,
        risks=risks,
        due_diligence=due_diligence,
        final_recommendation=final,
    )


def build_development_memo(
    project: DevelopmentProject,
    comparison: DevelopmentComparison,
) -> bytes:
    expected_npv = comparison.expected_npv_at_asking_price
    recommendation = (
        "PROCEED TO DEVELOPMENT DUE DILIGENCE"
        if expected_npv >= 0
        else "NEGOTIATE OR REJECT LAND PRICE"
    )
    summary = (
        f"The land is offered at {_money(project.asking_land_price)}. The two planning "
        f"concepts support a probability-weighted maximum land price of "
        f"{_money(comparison.expected_maximum_land_price)}. "
        f"{comparison.preferred_plan_name} produces the highest residual value."
    )
    assumptions = [
        ["Site", "Value", "Valuation", "Value"],
        ["Asking land price", _money(project.asking_land_price), "Discount rate", _percent(project.discount_rate)],
        ["Plot size", f"{project.plot_size_sqm:,.0f} sqm", "Cost inflation", _percent(project.construction_cost_inflation)],
        ["Gross floor area", f"{project.gross_floor_area_sqm:,.0f} sqm", "Revenue growth", _percent(project.revenue_growth_rate)],
        ["Net floor area", f"{project.net_floor_area_sqm:,.0f} sqm", "Contingency", _percent(project.contingency_rate)],
        ["Land acquisition cost", _percent(project.land_acquisition_cost_rate), "Selling costs", _percent(project.selling_cost_rate)],
    ]
    analysis_rows = [["Plan", "Probability", "GDV", "Dev. cost", "Max land", "IRR"]]
    analysis_rows.extend(
        [
            item.plan.name,
            _percent(item.plan.probability),
            _money(item.gross_development_value),
            _money(item.total_nominal_development_cost),
            _money(item.maximum_supportable_land_price),
            _percent(item.project_irr_at_asking_price),
        ]
        for item in comparison.analyses
    )
    risks = [
        "Residual land value is highly sensitive to selling prices, market rents and capitalization rates.",
        "Planning probabilities and permitted density require independent legal and technical confirmation.",
        "Construction-cost inflation, delays and procurement risk can materially reduce the residual value.",
        "A significant share of value is realized only at completion and is exposed to exit-market liquidity.",
    ]
    due_diligence = [
        "Confirm zoning, permitted density, use mix, easements and planning timetable.",
        "Commission a concept design, quantity surveyor cost plan and independent contingency review.",
        "Validate achievable rents, selling prices, absorption and capitalization rates with market evidence.",
        "Review construction financing, drawdown timing, interest carry and required presales.",
    ]
    final = (
        f"{recommendation}. Do not exceed a probability-weighted land price of "
        f"<b>{_money(comparison.expected_maximum_land_price)}</b> under the current "
        f"assumptions. Use {escape(comparison.preferred_plan_name)} as the leading "
        "concept, subject to planning, cost and market validation."
    )
    preferred = next(
        item
        for item in comparison.analyses
        if item.plan.name == comparison.preferred_plan_name
    )
    return _build_document(
        title=f"Development IC Memo - {project.name}",
        subtitle=(
            f"<b>{escape(project.name)}</b><br/>{escape(project.location)}<br/>"
            "Ground-Up Development feasibility"
        ),
        recommendation=recommendation,
        recommendation_summary=(
            f"Maximum weighted land price {_money(comparison.expected_maximum_land_price)}; "
            f"preferred concept {comparison.preferred_plan_name}."
        ),
        metrics=[
            ("Asking land price", _money(project.asking_land_price)),
            ("Maximum weighted price", _money(comparison.expected_maximum_land_price)),
            ("Expected NPV", _money(comparison.expected_npv_at_asking_price)),
            ("Preferred plan", comparison.preferred_plan_name),
            ("Preferred GDV", _money(preferred.gross_development_value)),
            ("Preferred IRR", _percent(preferred.project_irr_at_asking_price)),
        ],
        executive_summary=summary,
        assumptions=assumptions,
        analysis_rows=analysis_rows,
        risks=risks,
        due_diligence=due_diligence,
        final_recommendation=final,
    )
