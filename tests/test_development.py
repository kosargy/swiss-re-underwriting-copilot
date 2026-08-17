import unittest

from development import (
    DevelopmentPlan,
    DevelopmentProject,
    analyse_development_plan,
    compare_development_plans,
    development_sensitivity_grid,
)


def sample_project(**changes) -> DevelopmentProject:
    values = {
        "name": "Test land",
        "location": "Zurich",
        "asking_land_price": 500_000,
        "plot_size_sqm": 1_000,
        "density_ratio": 1.0,
        "floor_space_efficiency": 1.0,
        "discount_rate": 0.10,
        "construction_cost_inflation": 0.0,
        "revenue_growth_rate": 0.0,
        "professional_fees_rate": 0.0,
        "contingency_rate": 0.0,
        "selling_cost_rate": 0.0,
        "land_acquisition_cost_rate": 0.0,
    }
    values.update(changes)
    return DevelopmentProject(**values)


def sample_plan(**changes) -> DevelopmentPlan:
    values = {
        "name": "Rental plan",
        "probability": 1.0,
        "development_years": 1,
        "residential_rental_share": 1.0,
        "condo_sale_share": 0.0,
        "commercial_rental_share": 0.0,
        "residential_rent_per_sqm": 100.0,
        "condo_sale_price_per_sqm": 0.0,
        "commercial_rent_per_sqm": 0.0,
        "residential_cap_rate": 0.05,
        "commercial_cap_rate": 0.05,
        "residential_cost_per_sqm": 1_000.0,
        "condo_cost_per_sqm": 0.0,
        "commercial_cost_per_sqm": 0.0,
    }
    values.update(changes)
    return DevelopmentPlan(**values)


class DevelopmentEngineTests(unittest.TestCase):
    def test_residual_land_value_matches_independent_one_year_example(self):
        result = analyse_development_plan(sample_project(), sample_plan())
        self.assertAlmostEqual(result.net_floor_area_sqm, 1_000)
        self.assertAlmostEqual(result.gross_development_value, 2_000_000)
        self.assertAlmostEqual(result.total_nominal_development_cost, 1_000_000)
        self.assertAlmostEqual(
            result.maximum_supportable_land_price,
            1_000_000 / 1.10,
        )
        self.assertAlmostEqual(
            result.project_npv_at_asking_price,
            1_000_000 / 1.10 - 500_000,
        )
        self.assertAlmostEqual(result.project_irr_at_asking_price, 1.0)

    def test_land_acquisition_cost_reduces_maximum_purchase_price(self):
        without_cost = analyse_development_plan(sample_project(), sample_plan())
        with_cost = analyse_development_plan(
            sample_project(land_acquisition_cost_rate=0.05),
            sample_plan(),
        )
        self.assertLess(
            with_cost.maximum_supportable_land_price,
            without_cost.maximum_supportable_land_price,
        )
        self.assertAlmostEqual(
            with_cost.maximum_supportable_land_price,
            without_cost.maximum_supportable_land_price / 1.05,
        )

    def test_predevelopment_income_is_discounted_and_added_to_land_value(self):
        no_income = analyse_development_plan(
            sample_project(predevelopment_income_years=1),
            sample_plan(),
        )
        with_income = analyse_development_plan(
            sample_project(
                predevelopment_income_years=1,
                predevelopment_potential_income=120_000,
                predevelopment_operating_expenses=20_000,
            ),
            sample_plan(),
        )
        self.assertAlmostEqual(
            with_income.present_value_of_predevelopment_income,
            100_000 / 1.10,
        )
        self.assertAlmostEqual(
            with_income.maximum_supportable_land_price
            - no_income.maximum_supportable_land_price,
            100_000 / 1.10,
        )

    def test_predevelopment_period_delays_build_and_includes_termination_cost(self):
        result = analyse_development_plan(
            sample_project(
                predevelopment_income_years=2,
                predevelopment_potential_income=100_000,
                predevelopment_vacancy_rate=0.10,
                predevelopment_operating_expenses=20_000,
                predevelopment_income_growth_rate=0.05,
                predevelopment_termination_cost=30_000,
            ),
            sample_plan(),
        )
        self.assertEqual(len(result.cash_flows_at_asking_price), 4)
        self.assertEqual(result.development_years[0].year, 3)
        self.assertAlmostEqual(result.predevelopment_years[0].net_cash_flow, 70_000)
        self.assertAlmostEqual(result.predevelopment_years[1].net_cash_flow, 44_500)

    def test_use_mix_must_total_one_hundred_percent(self):
        with self.assertRaises(ValueError):
            sample_plan(
                residential_rental_share=0.5,
                condo_sale_share=0.2,
                commercial_rental_share=0.1,
            )

    def test_probability_weighted_comparison(self):
        plan_a = sample_plan(name="A", probability=0.75)
        plan_b = sample_plan(
            name="B",
            probability=0.25,
            residential_rent_per_sqm=125.0,
        )
        comparison = compare_development_plans(
            sample_project(),
            (plan_a, plan_b),
        )
        values = {
            analysis.plan.name: analysis.maximum_supportable_land_price
            for analysis in comparison.analyses
        }
        self.assertAlmostEqual(
            comparison.expected_maximum_land_price,
            0.75 * values["A"] + 0.25 * values["B"],
        )
        self.assertEqual(comparison.preferred_plan_name, "B")

    def test_sensitivity_has_25_points_and_correct_directions(self):
        points = development_sensitivity_grid(sample_project(), sample_plan())
        self.assertEqual(len(points), 25)
        low_cost = min(points, key=lambda point: point.construction_cost_change)
        high_cost = max(points, key=lambda point: point.construction_cost_change)
        self.assertGreater(
            low_cost.maximum_supportable_land_price,
            high_cost.maximum_supportable_land_price,
        )
        low_revenue = min(points, key=lambda point: point.revenue_change)
        high_revenue = max(points, key=lambda point: point.revenue_change)
        self.assertLess(
            low_revenue.maximum_supportable_land_price,
            high_revenue.maximum_supportable_land_price,
        )


if __name__ == "__main__":
    unittest.main()
