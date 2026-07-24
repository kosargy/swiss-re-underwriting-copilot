from __future__ import annotations

from dataclasses import dataclass

from .engine import analyse_development_plan
from .models import DevelopmentAnalysis, DevelopmentPlan, DevelopmentProject


@dataclass(frozen=True)
class DevelopmentComparison:
    analyses: tuple[DevelopmentAnalysis, ...]
    expected_maximum_land_price: float
    expected_npv_at_asking_price: float
    preferred_plan_name: str


def compare_development_plans(
    project: DevelopmentProject,
    plans: tuple[DevelopmentPlan, ...],
) -> DevelopmentComparison:
    if not plans:
        raise ValueError("at least one development plan is required")
    probability_total = sum(plan.probability for plan in plans)
    if abs(probability_total - 1.0) > 1e-8:
        raise ValueError("development plan probabilities must total 100%")
    analyses = tuple(analyse_development_plan(project, plan) for plan in plans)
    expected_land_value = sum(
        analysis.maximum_supportable_land_price * analysis.plan.probability
        for analysis in analyses
    )
    expected_npv = sum(
        analysis.project_npv_at_asking_price * analysis.plan.probability
        for analysis in analyses
    )
    preferred = max(
        analyses,
        key=lambda analysis: analysis.maximum_supportable_land_price,
    )
    return DevelopmentComparison(
        analyses=analyses,
        expected_maximum_land_price=expected_land_value,
        expected_npv_at_asking_price=expected_npv,
        preferred_plan_name=preferred.plan.name,
    )
