from __future__ import annotations

from dataclasses import dataclass, replace

from .engine import analyse_investment
from .models import FinancingAssumptions, PropertyAssumptions


@dataclass(frozen=True)
class SensitivityPoint:
    exit_cap_rate: float
    rent_growth_rate: float
    dcf_value: float
    levered_irr: float | None


def sensitivity_grid(
    property_assumptions: PropertyAssumptions,
    financing_assumptions: FinancingAssumptions,
    *,
    exit_cap_step: float = 0.0025,
    rent_growth_step: float = 0.005,
) -> tuple[SensitivityPoint, ...]:
    """Return a 5x5 exit-cap/rent-growth sensitivity grid."""
    points: list[SensitivityPoint] = []
    for exit_offset in (-2, -1, 0, 1, 2):
        for growth_offset in (-2, -1, 0, 1, 2):
            property_case = replace(
                property_assumptions,
                exit_cap_rate=max(
                    0.001,
                    property_assumptions.exit_cap_rate + exit_offset * exit_cap_step,
                ),
                rent_growth_rate=max(
                    0.0,
                    property_assumptions.rent_growth_rate
                    + growth_offset * rent_growth_step,
                ),
            )
            result = analyse_investment(property_case, financing_assumptions)
            points.append(
                SensitivityPoint(
                    exit_cap_rate=property_case.exit_cap_rate,
                    rent_growth_rate=property_case.rent_growth_rate,
                    dcf_value=result.dcf_value,
                    levered_irr=result.levered_irr,
                )
            )
    return tuple(points)

