import unittest

from development import build_cap_rate


class CapRateBuilderTests(unittest.TestCase):
    def test_excel_reference_example(self):
        result = build_cap_rate(
            use="Predominantly residential",
            location="Small city",
            risk_free_rate=0.01,
            real_estate_risk_premium=0.01,
            object_specific_premium=0.0,
            real_rental_growth=0.0,
            operating_cost_rate=0.08,
            vacancy_rate=0.02,
            repair_reserve_rate=0.12,
        )
        self.assertAlmostEqual(result.net_cap_rate, 0.03)
        self.assertAlmostEqual(result.gross_cap_rate, 0.03 / 0.78)

    def test_risk_and_growth_move_rate_in_expected_directions(self):
        inputs = dict(
            use="Office",
            location="Large city · central",
            risk_free_rate=0.01,
            real_estate_risk_premium=0.01,
            object_specific_premium=0.002,
            real_rental_growth=0.0,
            operating_cost_rate=0.08,
            vacancy_rate=0.02,
            repair_reserve_rate=0.05,
        )
        base = build_cap_rate(**inputs)
        riskier = build_cap_rate(**{**inputs, "object_specific_premium": 0.01})
        growth = build_cap_rate(**{**inputs, "real_rental_growth": 0.005})
        self.assertGreater(riskier.gross_cap_rate, base.gross_cap_rate)
        self.assertLess(growth.gross_cap_rate, base.gross_cap_rate)


if __name__ == "__main__":
    unittest.main()
