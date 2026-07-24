from __future__ import annotations

from dataclasses import dataclass, replace

from .engine import analyse_development_plan
from .models import DevelopmentPlan, DevelopmentProject


@dataclass(frozen=True)
class DevelopmentSensitivityPoint:
    construction_cost_change: float
    revenue_change: float
    maximum_supportable_land_price: float
    project_irr_at_asking_price: float | None


def development_sensitivity_grid(
    project: DevelopmentProject,
    plan: DevelopmentPlan,
    changes: tuple[float, ...] = (-0.10, -0.05, 0.0, 0.05, 0.10),
) -> tuple[DevelopmentSensitivityPoint, ...]:
    points: list[DevelopmentSensitivityPoint] = []
    for cost_change in changes:
        for revenue_change in changes:
            adjusted_plan = replace(
                plan,
                residential_rent_per_sqm=(
                    plan.residential_rent_per_sqm * (1.0 + revenue_change)
                ),
                condo_sale_price_per_sqm=(
                    plan.condo_sale_price_per_sqm * (1.0 + revenue_change)
                ),
                commercial_rent_per_sqm=(
                    plan.commercial_rent_per_sqm * (1.0 + revenue_change)
                ),
                annual_rent_per_parking_space=(
                    plan.annual_rent_per_parking_space * (1.0 + revenue_change)
                ),
                sale_price_per_parking_space=(
                    plan.sale_price_per_parking_space * (1.0 + revenue_change)
                ),
                residential_cost_per_sqm=(
                    plan.residential_cost_per_sqm * (1.0 + cost_change)
                ),
                condo_cost_per_sqm=plan.condo_cost_per_sqm * (1.0 + cost_change),
                commercial_cost_per_sqm=(
                    plan.commercial_cost_per_sqm * (1.0 + cost_change)
                ),
            )
            analysis = analyse_development_plan(project, adjusted_plan)
            points.append(
                DevelopmentSensitivityPoint(
                    construction_cost_change=cost_change,
                    revenue_change=revenue_change,
                    maximum_supportable_land_price=(
                        analysis.maximum_supportable_land_price
                    ),
                    project_irr_at_asking_price=analysis.project_irr_at_asking_price,
                )
            )
    return tuple(points)
