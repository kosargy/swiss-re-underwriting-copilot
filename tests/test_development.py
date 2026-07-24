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
