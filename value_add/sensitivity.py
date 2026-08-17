from __future__ import annotations

from dataclasses import dataclass, replace

from .engine import analyse_value_add
from .models import ValueAddFinancing, ValueAddProject


@dataclass(frozen=True)
class ValueAddSensitivityPoint:
    renovation_cost_change: float
    stabilized_rent_change: float
    maximum_supportable_purchase_price: float
    levered_irr: float | None


def value_add_sensitivity_grid(
    project: ValueAddProject,
    financing: ValueAddFinancing,
    changes: tuple[float, ...] = (-0.10, -0.05, 0.0, 0.05, 0.10),
) -> tuple[ValueAddSensitivityPoint, ...]:
    points: list[ValueAddSensitivityPoint] = []
    for cost_change in changes:
        for rent_change in changes:
            scenario = replace(
                project,
                renovation_capex_by_year=tuple(
                    amount * (1.0 + cost_change)
                    for amount in project.renovation_capex_by_year
                ),
                stabilized_potential_rent=(
                    project.stabilized_potential_rent * (1.0 + rent_change)
                ),
            )
            result = analyse_value_add(scenario, financing)
            points.append(
                ValueAddSensitivityPoint(
                    renovation_cost_change=cost_change,
                    stabilized_rent_change=rent_change,
                    maximum_supportable_purchase_price=(
                        result.maximum_supportable_purchase_price
                    ),
                    levered_irr=result.levered_irr,
                )
            )
    return tuple(points)
