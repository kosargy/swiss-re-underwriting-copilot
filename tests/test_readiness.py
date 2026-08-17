import unittest
from dataclasses import replace

from development import DevelopmentPlan, DevelopmentProject, compare_development_plans
from readiness import assess_development_readiness, assess_value_add_readiness
from value_add import ValueAddFinancing, ValueAddProject, analyse_value_add


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.value_add = ValueAddProject(
            name="Case", location="Zürich", purchase_price=5_000_000,
            acquisition_cost_rate=0.02, current_potential_rent=350_000,
            current_vacancy_rate=0.05, current_operating_expenses=80_000,
            current_market_cap_rate=0.05, renovation_years=1,
            renovation_capex_by_year=(300_000,), income_retention_during_renovation=0.8,
            stabilized_potential_rent=450_000, stabilized_vacancy_rate=0.03,
            stabilized_operating_expenses=90_000, annual_rent_growth_rate=0.02,
            annual_expense_growth_rate=0.02, exit_cap_rate=0.05,
            discount_rate=0.07, selling_cost_rate=0.01, holding_period_years=5,
            target_unlevered_irr=0.07, target_levered_irr=0.10,
        )
        self.financing = ValueAddFinancing(0.6, 0.03, 0.01)

    def test_overpriced_value_add_is_not_ready(self):
        analysis = analyse_value_add(replace(self.value_add, purchase_price=20_000_000), self.financing)
        readiness = assess_value_add_readiness(analysis)
        self.assertEqual(readiness.status, "NOT IC READY")
        self.assertTrue(any(item.check == "Pricing discipline" and item.severity == "Critical" for item in readiness.findings))

    def test_development_low_contingency_is_flagged(self):
        project = DevelopmentProject("Site", "Zürich", 1_000_000, 1_000, 1.0, 0.8, 0.08, 0.02, 0.01, 0.10, 0.03, 0.02, 0.02)
        plan = DevelopmentPlan("Plan A", 1.0, 2, 1.0, 0.0, 0.0, 350, 0, 0, 0.04, 0.05, 2_500, 0, 0)
        readiness = assess_development_readiness(project, compare_development_plans(project, (plan,)))
        self.assertTrue(any(item.check == "Construction contingency" and item.severity == "Warning" for item in readiness.findings))


if __name__ == "__main__":
    unittest.main()
