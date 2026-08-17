from __future__ import annotations

import unittest
from dataclasses import replace

from value_add import (
    ValueAddFinancing,
    ValueAddProject,
    analyse_value_add,
    value_add_sensitivity_grid,
)


def sample_project() -> ValueAddProject:
    return ValueAddProject(
        name="Zürich Value-Add Case",
        location="Zürich",
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


def sample_financing() -> ValueAddFinancing:
    return ValueAddFinancing(
        purchase_loan_to_value=0.60,
        interest_rate=0.035,
        annual_amortization_rate=0.01,
    )


class ValueAddEngineTests(unittest.TestCase):
    def test_current_and_stabilized_noi(self) -> None:
        result = analyse_value_add(sample_project(), sample_financing())
        self.assertAlmostEqual(result.current_noi, 452_400)
        self.assertAlmostEqual(result.stabilized_noi, 705_600)
        self.assertAlmostEqual(result.as_is_value, 452_400 / 0.0425)
        self.assertAlmostEqual(result.stabilized_value, 705_600 / 0.04)

    def test_maximum_price_sets_unlevered_npv_to_zero(self) -> None:
        project = sample_project()
        result = analyse_value_add(project, sample_financing())
        break_even_project = replace(
            project,
            purchase_price=result.maximum_supportable_purchase_price,
        )
        break_even = analyse_value_add(break_even_project, sample_financing())
        self.assertAlmostEqual(break_even.project_npv_at_asking_price, 0.0, places=5)

    def test_renovation_phase_has_income_loss_and_capex(self) -> None:
        result = analyse_value_add(sample_project(), sample_financing())
        self.assertEqual(result.projections[0].phase, "Renovation")
        self.assertGreater(result.projections[0].renovation_income_loss, 0)
        self.assertEqual(result.projections[0].renovation_capex, 1_200_000)
        self.assertEqual(result.projections[2].phase, "Stabilized")
        self.assertEqual(result.projections[2].renovation_capex, 0)

    def test_sensitivity_has_25_points_and_expected_directions(self) -> None:
        points = value_add_sensitivity_grid(sample_project(), sample_financing())
        self.assertEqual(len(points), 25)
        lookup = {
            (point.renovation_cost_change, point.stabilized_rent_change): point
            for point in points
        }
        self.assertGreater(
            lookup[(-0.10, 0.0)].maximum_supportable_purchase_price,
            lookup[(0.10, 0.0)].maximum_supportable_purchase_price,
        )
        self.assertGreater(
            lookup[(0.0, 0.10)].maximum_supportable_purchase_price,
            lookup[(0.0, -0.10)].maximum_supportable_purchase_price,
        )

    def test_capex_schedule_must_match_renovation_period(self) -> None:
        with self.assertRaises(ValueError):
            replace(sample_project(), renovation_capex_by_year=(2_200_000,))


if __name__ == "__main__":
    unittest.main()
