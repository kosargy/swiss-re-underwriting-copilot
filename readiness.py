from __future__ import annotations

from dataclasses import dataclass

from development import DevelopmentComparison, DevelopmentProject
from value_add import ValueAddAnalysis


@dataclass(frozen=True)
class ReadinessFinding:
    severity: str
    check: str
    conclusion: str


@dataclass(frozen=True)
class ReadinessAssessment:
    score: int
    status: str
    findings: tuple[ReadinessFinding, ...]


def _assessment(findings: list[ReadinessFinding]) -> ReadinessAssessment:
    deductions = {"Critical": 25, "Warning": 10, "Passed": 0}
    score = max(0, 100 - sum(deductions[item.severity] for item in findings))
    if any(item.severity == "Critical" for item in findings):
        status = "NOT IC READY"
    elif any(item.severity == "Warning" for item in findings):
        status = "CONDITIONAL — CLOSE EVIDENCE GAPS"
    else:
        status = "READY FOR PRELIMINARY IC REVIEW"
    return ReadinessAssessment(score, status, tuple(findings))


def assess_value_add_readiness(analysis: ValueAddAnalysis) -> ReadinessAssessment:
    project = analysis.project
    findings: list[ReadinessFinding] = []

    findings.append(
        ReadinessFinding(
            "Passed" if analysis.project_npv_at_asking_price >= 0 else "Critical",
            "Pricing discipline",
            (
                "Asking price is within the maximum supportable price."
                if analysis.project_npv_at_asking_price >= 0
                else "Asking price exceeds the maximum supportable price."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Passed"
            if analysis.levered_irr is not None
            and analysis.levered_irr >= project.target_levered_irr
            else "Critical",
            "Target levered return",
            (
                "Levered IRR meets the selected investment hurdle."
                if analysis.levered_irr is not None
                and analysis.levered_irr >= project.target_levered_irr
                else "Levered IRR is unavailable or below the selected hurdle."
            ),
        )
    )
    dscr = analysis.minimum_stabilized_dscr
    findings.append(
        ReadinessFinding(
            "Passed" if dscr is None or dscr >= 1.25 else "Warning",
            "Debt-service resilience",
            (
                "Stabilized DSCR provides at least 1.25x coverage."
                if dscr is not None and dscr >= 1.25
                else (
                    "No acquisition debt is modelled."
                    if dscr is None
                    else "Stabilized DSCR is below the 1.25x screening threshold."
                )
            ),
        )
    )
    rent_uplift = (
        project.stabilized_potential_rent / project.current_potential_rent - 1
        if project.current_potential_rent > 0
        else 0.0
    )
    findings.append(
        ReadinessFinding(
            "Warning" if rent_uplift > 0.30 else "Passed",
            "Rent-uplift assumption",
            (
                f"Stabilized rent requires a {rent_uplift:.1%} uplift; external market evidence is essential."
                if rent_uplift > 0.30
                else f"Required rent uplift of {rent_uplift:.1%} is below the 30% challenge threshold."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Warning" if project.exit_cap_rate < project.current_market_cap_rate else "Passed",
            "Exit-cap conservatism",
            (
                "Exit cap is tighter than the current market cap and assumes yield compression."
                if project.exit_cap_rate < project.current_market_cap_rate
                else "Exit cap is no tighter than the current market cap."
            ),
        )
    )
    return _assessment(findings)


def assess_development_readiness(
    project: DevelopmentProject,
    comparison: DevelopmentComparison,
) -> ReadinessAssessment:
    findings: list[ReadinessFinding] = []
    preferred = next(
        item for item in comparison.analyses if item.plan.name == comparison.preferred_plan_name
    )

    findings.append(
        ReadinessFinding(
            "Passed" if comparison.expected_npv_at_asking_price >= 0 else "Critical",
            "Land pricing",
            (
                "Asking land price is supported on a probability-weighted basis."
                if comparison.expected_npv_at_asking_price >= 0
                else "Asking land price exceeds the probability-weighted residual value."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Passed"
            if preferred.project_irr_at_asking_price is not None
            and preferred.project_irr_at_asking_price >= project.discount_rate
            else "Critical",
            "Preferred-plan return",
            (
                "Preferred-plan IRR meets the selected discount-rate hurdle."
                if preferred.project_irr_at_asking_price is not None
                and preferred.project_irr_at_asking_price >= project.discount_rate
                else "Preferred-plan IRR is unavailable or below the selected hurdle."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Warning" if project.contingency_rate < 0.05 else "Passed",
            "Construction contingency",
            (
                "Contingency is below 5%; cost-overrun evidence should be strengthened."
                if project.contingency_rate < 0.05
                else "Contingency is at least 5% of construction cost."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Warning"
            if project.revenue_growth_rate > project.construction_cost_inflation
            else "Passed",
            "Growth-assumption balance",
            (
                "Revenue growth exceeds cost inflation and requires market support."
                if project.revenue_growth_rate > project.construction_cost_inflation
                else "Revenue growth does not exceed construction-cost inflation."
            ),
        )
    )
    findings.append(
        ReadinessFinding(
            "Warning" if preferred.plan.development_years > 4 else "Passed",
            "Delivery duration",
            (
                "Development extends beyond four years, increasing planning and market-cycle exposure."
                if preferred.plan.development_years > 4
                else "Development duration is within the four-year screening threshold."
            ),
        )
    )
    return _assessment(findings)
