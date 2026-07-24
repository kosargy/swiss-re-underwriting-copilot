from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .benchmark import BenchmarkAnalysis
from .comparables import ComparableAnalysis
from .decision import Decision, InvestmentCriteria
from .models import InvestmentAnalysis
from .scenarios import ScenarioAnalysis


NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#246B8E")
LIGHT_BLUE = colors.HexColor("#EAF2F6")
PALE_GREY = colors.HexColor("#F4F6F7")
DARK_GREY = colors.HexColor("#36454F")
MEDIUM_GREY = colors.HexColor("#667780")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B42318")
GREEN = colors.HexColor("#247A45")
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
            "MemoTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=7 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "MemoSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=MEDIUM_GREY,
            spaceAfter=5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=NAVY,
            spaceBefore=5 * mm,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "BodyMemo",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=DARK_GREY,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallMemo",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=DARK_GREY,
        )
    )
    styles.add(
        ParagraphStyle(
            "Cell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=DARK_GREY,
        )
    )
    styles.add(
        ParagraphStyle(
            "CellBold",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=NAVY,
        )
    )
    styles.add(
        ParagraphStyle(
            "CellHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=WHITE,
        )
    )
    styles.add(
        ParagraphStyle(
            "MetricLabel",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=MEDIUM_GREY,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            "MetricValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=NAVY,
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
    canvas.setFillColor(MEDIUM_GREY)
    canvas.drawRightString(
        width - 18 * mm,
        height - 11 * mm,
        "PRELIMINARY - FOR DISCUSSION ONLY",
    )
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.drawString(18 * mm, 10.5 * mm, f"Generated {date.today().isoformat()}")
    canvas.drawRightString(width - 18 * mm, 10.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def _metric_card(label: str, value: str, styles) -> list:
    return [
        Paragraph(value, styles["MetricValue"]),
        Spacer(1, 1.2 * mm),
        Paragraph(label, styles["MetricLabel"]),
    ]


def _table(
    data: list[list],
    widths: list[float],
    *,
    header: bool = True,
    compact: bool = False,
) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4 if compact else 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 if compact else 6),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7DFE3")),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, PALE_GREY]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def build_ic_memo(
    base: InvestmentAnalysis,
    scenarios: tuple[ScenarioAnalysis, ...],
    decision: Decision,
    criteria: InvestmentCriteria,
    benchmark: BenchmarkAnalysis | None = None,
    comparables: ComparableAnalysis | None = None,
) -> bytes:
    """Build a polished, deterministic Investment Committee memo PDF."""
    buffer = BytesIO()
    styles = _styles()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=f"Investment Committee Memo - {base.property.name}",
        author="Swiss Real Estate Underwriting Copilot",
    )
    story: list = []

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Investment Committee Memo", styles["MemoTitle"]))
    story.append(
        Paragraph(
            f"<b>{base.property.name}</b><br/>{base.property.location}<br/>"
            "Preliminary acquisition underwriting",
            styles["MemoSubtitle"],
        )
    )

    recommendation_color = {
        "PROCEED TO DUE DILIGENCE": GREEN,
        "PROCEED WITH CONDITIONS": BLUE,
        "NEGOTIATE": ORANGE,
        "REJECT AT CURRENT TERMS": RED,
    }.get(decision.recommendation, MEDIUM_GREY)
    recommendation = Table(
        [
            [
                Paragraph(
                    f"<font color='#FFFFFF'><b>{decision.recommendation}</b></font>",
                    styles["BodyMemo"],
                ),
                Paragraph(
                    f"<font color='#FFFFFF'>{decision.summary}</font>",
                    styles["BodyMemo"],
                ),
            ]
        ],
        colWidths=[52 * mm, 105 * mm],
    )
    recommendation.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), recommendation_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([recommendation, Spacer(1, 6 * mm)])

    cards = Table(
        [
            [
                _metric_card("Asking price", _money(base.property.purchase_price), styles),
                _metric_card("DCF value", _money(base.dcf_value), styles),
                _metric_card("Recommended offer", _money(decision.recommended_price), styles),
            ],
            [
                _metric_card("Levered IRR", _percent(base.levered_irr), styles),
                _metric_card("Minimum DSCR", f"{base.minimum_dscr:.2f}x", styles),
                _metric_card("Equity multiple", f"{base.equity_multiple:.2f}x", styles),
            ],
        ],
        colWidths=[52.3 * mm] * 3,
        rowHeights=[23 * mm, 23 * mm],
    )
    cards.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD6DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD6DB")),
                ("BACKGROUND", (0, 0), (-1, -1), PALE_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.extend([cards, Spacer(1, 3 * mm)])

    story.append(Paragraph("1. Executive summary", styles["Section"]))
    pricing_gap = base.property.purchase_price - base.dcf_value
    summary_text = (
        f"The property is offered at <b>{_money(base.property.purchase_price)}</b>. "
        f"The base-case DCF value is <b>{_money(base.dcf_value)}</b>, implying a "
        f"pricing gap of <b>{_money(pricing_gap)}</b>. The base case generates an "
        f"unlevered IRR of <b>{_percent(base.unlevered_irr)}</b> and a levered IRR "
        f"of <b>{_percent(base.levered_irr)}</b>, compared with target returns of "
        f"{criteria.target_unlevered_irr:.2%} and {criteria.target_levered_irr:.2%}, "
        "respectively."
    )
    story.append(Paragraph(summary_text, styles["BodyMemo"]))
    if decision.reasons:
        for reason in decision.reasons:
            story.append(Paragraph(f"- {reason}", styles["BodyMemo"]))

    story.append(Paragraph("2. Property and underwriting assumptions", styles["Section"]))
    assumptions_data = [
        ["Property", "Value", "Valuation / financing", "Value"],
        [
            "Potential annual rent",
            _money(base.property.potential_gross_rent),
            "Discount rate",
            _percent(base.property.discount_rate),
        ],
        [
            "Vacancy",
            _percent(base.property.vacancy_rate),
            "Exit cap rate",
            _percent(base.property.exit_cap_rate),
        ],
        [
            "Operating expenses",
            _money(base.property.operating_expenses),
            "Loan-to-value",
            _percent(base.financing.loan_to_value),
        ],
        [
            "Year 1 NOI",
            _money(base.year_one_noi),
            "Interest rate",
            _percent(base.financing.interest_rate),
        ],
        [
            "Holding period",
            f"{base.property.holding_period_years} years",
            "Annual amortization",
            _percent(base.financing.annual_amortization_rate),
        ],
        [
            "Total planned CapEx",
            _money(sum(base.property.capex_by_year)),
            "Margin of safety",
            _percent(criteria.margin_of_safety),
        ],
    ]
    story.append(_table(assumptions_data, [44 * mm, 34 * mm, 44 * mm, 35 * mm]))

    story.append(PageBreak())
    story.append(Paragraph("3. Scenario analysis", styles["Section"]))
    scenario_data: list[list] = [
        [
            Paragraph("Scenario", styles["CellHeader"]),
            Paragraph("DCF value", styles["CellHeader"]),
            Paragraph("NPV", styles["CellHeader"]),
            Paragraph("Unlev. IRR", styles["CellHeader"]),
            Paragraph("Lev. IRR", styles["CellHeader"]),
            Paragraph("Min. DSCR", styles["CellHeader"]),
            Paragraph("Exit cap", styles["CellHeader"]),
        ]
    ]
    for item in scenarios:
        result = item.analysis
        scenario_data.append(
            [
                item.name,
                _money(result.dcf_value),
                _money(result.npv_at_asking_price),
                _percent(result.unlevered_irr),
                _percent(result.levered_irr),
                f"{result.minimum_dscr:.2f}x",
                _percent(result.property.exit_cap_rate),
            ]
        )
    story.append(
        _table(
            scenario_data,
            [22 * mm, 29 * mm, 27 * mm, 22 * mm, 22 * mm, 19 * mm, 19 * mm],
            compact=True,
        )
    )
    story.append(
        Paragraph(
            "Interpretation: value and equity returns are particularly sensitive to "
            "the terminal cap rate. The downside scenario should be treated as a "
            "minimum stress test rather than a complete risk boundary.",
            styles["SmallMemo"],
        )
    )

    story.append(Paragraph("4. Annual cash-flow projection", styles["Section"]))
    projection_data: list[list] = [
        [
            "Year",
            "Effective income",
            "NOI",
            "CapEx",
            "Debt service",
            "Equity CF before sale",
            "DSCR",
        ]
    ]
    for item in base.projections:
        projection_data.append(
            [
                str(item.year),
                _money(item.effective_income),
                _money(item.noi),
                _money(item.capex),
                _money(item.debt_service),
                _money(item.cash_flow_to_equity_before_sale),
                f"{item.dscr:.2f}x" if item.dscr is not None else "n/a",
            ]
        )
    story.append(
        _table(
            projection_data,
            [13 * mm, 27 * mm, 24 * mm, 25 * mm, 25 * mm, 31 * mm, 15 * mm],
            compact=True,
        )
    )
    story.append(
        Paragraph(
            f"Terminal value: <b>{_money(base.terminal_value)}</b>; net sale proceeds "
            f"before debt repayment: <b>{_money(base.net_sale_proceeds_before_debt)}</b>.",
            styles["BodyMemo"],
        )
    )

    story.append(Paragraph("5. Risk register", styles["Section"]))
    risk_data: list[list] = [
        [
            Paragraph("Severity", styles["CellHeader"]),
            Paragraph("Category", styles["CellHeader"]),
            Paragraph("Finding and evidence", styles["CellHeader"]),
            Paragraph("Required action", styles["CellHeader"]),
        ]
    ]
    for risk in decision.risks:
        risk_data.append(
            [
                Paragraph(risk.severity, styles["Cell"]),
                Paragraph(risk.category, styles["Cell"]),
                Paragraph(
                    f"<b>{risk.finding}</b><br/>{risk.evidence}",
                    styles["Cell"],
                ),
                Paragraph(risk.action, styles["Cell"]),
            ]
        )
    if len(risk_data) == 1:
        risk_data.append(["Low", "General", "No rule-based risk triggered.", "Continue DD."])
    story.append(
        _table(
            risk_data,
            [18 * mm, 27 * mm, 62 * mm, 53 * mm],
            compact=True,
        )
    )

    story.append(PageBreak())
    next_section = 6
    if benchmark is not None:
        story.append(Paragraph("6. Market benchmarking", styles["Section"]))
        benchmark_data: list[list] = [
            [
                "Metric",
                "Subject",
                "Market",
                "Difference",
                "Signal",
            ]
        ]
        for item in benchmark.indicators:
            rate_metric = item.metric in {"Vacancy", "Implied cap rate"}
            if rate_metric:
                subject = _percent(item.subject_value)
                market = _percent(item.market_value)
                difference = f"{item.difference * 10_000:+.0f} bps"
            else:
                subject = f"CHF {item.subject_value:,.0f}"
                market = f"CHF {item.market_value:,.0f}"
                difference = f"{item.difference:+.1%}"
            benchmark_data.append(
                [item.metric, subject, market, difference, item.status]
            )
        story.append(
            _table(
                benchmark_data,
                [45 * mm, 29 * mm, 29 * mm, 27 * mm, 27 * mm],
                compact=True,
            )
        )
        story.append(Spacer(1, 3 * mm))
        benchmark_values = [
            ["Cross-check", "Indicated value"],
            [
                "Income benchmark",
                _money(benchmark.indicative_market_value_income),
            ],
            [
                "Comparable-price benchmark",
                _money(benchmark.indicative_market_value_price_per_sqm),
            ],
            ["Blended market indication", _money(benchmark.blended_market_value)],
            ["Base-case DCF", _money(base.dcf_value)],
            ["Asking price", _money(base.property.purchase_price)],
        ]
        story.append(_table(benchmark_values, [85 * mm, 72 * mm], compact=True))
        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                f"<b>Evidence source:</b> {benchmark.benchmarks.source}<br/>"
                f"<b>As of:</b> {benchmark.benchmarks.as_of_date}<br/>"
                "These market outputs are indicative cross-checks based on manually "
                "entered evidence and do not constitute an appraisal.",
                styles["SmallMemo"],
            )
        )
        next_section = 7
        story.append(Spacer(1, 3 * mm))

    if comparables is not None:
        story.append(
            Paragraph(
                f"{next_section}. Comparable-properties analysis",
                styles["Section"],
            )
        )
        comparable_data: list[list] = [
            [
                "Comparable",
                "Price / m²",
                "Adjustment",
                "Adjusted / m²",
                "Score",
            ]
        ]
        for item in comparables.results[:6]:
            comparable_data.append(
                [
                    item.comparable.name,
                    f"CHF {item.price_per_sqm:,.0f}",
                    f"{item.adjustment:+.1%}",
                    f"CHF {item.adjusted_price_per_sqm:,.0f}",
                    f"{item.relevance_score:.0f}/100",
                ]
            )
        story.append(
            _table(
                comparable_data,
                [51 * mm, 29 * mm, 24 * mm, 31 * mm, 22 * mm],
                compact=True,
            )
        )
        story.append(Spacer(1, 2 * mm))
        story.append(
            Paragraph(
                f"<b>Adjusted value indication:</b> "
                f"{_money(comparables.indicated_value)} "
                f"(range {_money(comparables.lower_value)} to "
                f"{_money(comparables.upper_value)}). "
                f"<b>Evidence confidence:</b> {comparables.confidence}; "
                f"average relevance score {comparables.average_relevance_score:.0f}/100. "
                "The default demo observations must be replaced with documented "
                "market evidence before external use.",
                styles["SmallMemo"],
            )
        )
        next_section += 1

    if benchmark is not None or comparables is not None:
        story.append(PageBreak())

    story.append(
        Paragraph(
            f"{next_section}. Proposed decision and conditions",
            styles["Section"],
        )
    )
    decision_data = [
        ["Decision item", "Result"],
        ["Recommendation", decision.recommendation],
        ["Maximum DCF-supported price", _money(decision.maximum_price_dcf)],
        [
            "Maximum price at target levered IRR",
            (
                _money(decision.maximum_price_target_irr)
                if decision.maximum_price_target_irr is not None
                else "Not determinable under current cash-flow pattern"
            ),
        ],
        ["Recommended offer incl. margin of safety", _money(decision.recommended_price)],
    ]
    story.append(_table(decision_data, [72 * mm, 85 * mm], compact=True))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<b>Conditions before Investment Committee</b>", styles["BodyMemo"]))
    for condition in decision.conditions:
        story.append(Paragraph(f"- {condition}", styles["BodyMemo"]))

    story.append(
        Paragraph(
            f"{next_section + 1}. Methodology and limitations",
            styles["Section"],
        )
    )
    methodology = [
        "Annual year-end cash-flow convention.",
        "Terminal value equals next year's NOI divided by the exit cap rate.",
        "Selling costs are deducted from terminal proceeds.",
        "Interest is calculated on the opening annual loan balance.",
        "The analysis excludes acquisition taxes, income taxes and detailed lease-level cash flows.",
        "No legal, technical, environmental or market due diligence has been completed.",
    ]
    methodology_table = Table(
        [
            [
                Paragraph(
                    "<br/>".join(f"- {item}" for item in methodology[:3]),
                    styles["SmallMemo"],
                ),
                Paragraph(
                    "<br/>".join(f"- {item}" for item in methodology[3:]),
                    styles["SmallMemo"],
                ),
            ]
        ],
        colWidths=[78.5 * mm, 78.5 * mm],
    )
    methodology_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(methodology_table)
    story.append(Spacer(1, 2 * mm))
    disclaimer = Table(
        [
            [
                Paragraph(
                    "<b>Important:</b> This memo is a preliminary analytical output "
                    "for demonstration and discussion. It is not an appraisal, an "
                    "investment recommendation or a substitute for professional due "
                    "diligence and Investment Committee judgment.",
                    styles["SmallMemo"],
                )
            ]
        ],
        colWidths=[157 * mm],
    )
    disclaimer.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(KeepTogether(disclaimer))

    document.build(
        story,
        onFirstPage=_header_footer,
        onLaterPages=_header_footer,
    )
    return buffer.getvalue()
