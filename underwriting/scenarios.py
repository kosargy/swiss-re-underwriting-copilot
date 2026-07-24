from __future__ import annotations

from dataclasses import dataclass, replace

from .engine import analyse_investment
from .models import FinancingAssumptions, InvestmentAnalysis, PropertyAssumptions


@dataclass(frozen=True)
class Scenario:
    name: str
    property_changes: dict[str, object]
    financing_changes: dict[str, float]


@dataclass(frozen=True)
class ScenarioAnalysis:
    name: str
    analysis: InvestmentAnalysis


def standard_scenarios(
    property_assumptions: PropertyAssumptions,
    financing_assumptions: FinancingAssumptions,
) -> tuple[ScenarioAnalysis, ...]:
    """Create transparent base, upside and downside cases."""
    upside_capex = tuple(value * 0.90 for value in property_assumptions.capex_by_year)
    downside_capex = tuple(value * 1.20 for value in property_assumptions.capex_by_year)
    definitions = (
        Scenario("Base", {}, {}),
        Scenario(
            "Upside",
            {
                "vacancy_rate": max(0.0, property_assumptions.vacancy_rate - 0.01),
                "rent_growth_rate": property_assumptions.rent_growth_rate + 0.0075,
                "discount_rate": max(0.001, property_assumptions.discount_rate - 0.005),
                "exit_cap_rate": max(0.001, property_assumptions.exit_cap_rate - 0.0025),
                "capex_by_year": upside_capex,
            },
            {
                "interest_rate": max(0.0, financing_assumptions.interest_rate - 0.005),
            },
        ),
        Scenario(
            "Downside",
            {
                "vacancy_rate": min(0.99, property_assumptions.vacancy_rate + 0.03),
                "rent_growth_rate": max(0.0, property_assumptions.rent_growth_rate - 0.01),
                "expense_growth_rate": property_assumptions.expense_growth_rate + 0.01,
                "discount_rate": property_assumptions.discount_rate + 0.01,
                "exit_cap_rate": property_assumptions.exit_cap_rate + 0.005,
                "capex_by_year": downside_capex,
            },
            {
                "interest_rate": financing_assumptions.interest_rate + 0.01,
            },
        ),
    )

    results: list[ScenarioAnalysis] = []
    for definition in definitions:
        property_case = replace(property_assumptions, **definition.property_changes)
        financing_case = replace(financing_assumptions, **definition.financing_changes)
        results.append(
            ScenarioAnalysis(
                definition.name,
                analyse_investment(property_case, financing_case),
            )
        )
    return tuple(results)

