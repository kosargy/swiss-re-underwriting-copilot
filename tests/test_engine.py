import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from underwriting.engine import analyse_investment, annual_irr
from underwriting.decision import InvestmentCriteria, make_decision
from underwriting.models import FinancingAssumptions, PropertyAssumptions
from underwriting.memo import build_ic_memo
from underwriting.benchmark import MarketBenchmarks, analyse_market_benchmarks
from underwriting.comparables import ComparableProperty, analyse_comparables
from underwriting.deal_store import DealStore
from underwriting.scenarios import standard_scenarios
from underwriting.sensitivity import sensitivity_grid


def sample_property(**changes) -> PropertyAssumptions:
    values = {
        "name": "Test Residential",
        "location": "Zurich",
        "purchase_price": 10_000_000,
        "potential_gross_rent": 600_000,
        "vacancy_rate": 0.05,
        "operating_expenses": 150_000,
        "other_income": 0,
        "market_cap_rate": 0.05,
        "rent_growth_rate": 0.02,
        "expense_growth_rate": 0.02,
        "discount_rate": 0.07,
        "exit_cap_rate": 0.05,
        "selling_cost_rate": 0.01,
        "holding_period_years": 5,
        "capex_by_year": (0, 0, 100_000, 0, 0),
    }
    values.update(changes)
    return PropertyAssumptions(**values)


class UnderwritingEngineTests(unittest.TestCase):
    def test_year_one_noi_and_direct_cap(self):
        result = analyse_investment(
            sample_property(),
            FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04),
        )
        self.assertAlmostEqual(result.year_one_noi, 420_000)
        self.assertAlmostEqual(result.implied_cap_rate, 0.042)
        self.assertAlmostEqual(result.direct_cap_value, 8_400_000)

    def test_financing_and_dscr(self):
        result = analyse_investment(
            sample_property(),
            FinancingAssumptions(
                loan_to_value=0.6,
                interest_rate=0.04,
                annual_amortization_rate=0.01,
            ),
        )
        first = result.projections[0]
        self.assertAlmostEqual(result.loan_amount, 6_000_000)
        self.assertAlmostEqual(result.initial_equity, 4_000_000)
        self.assertAlmostEqual(first.interest_payment, 240_000)
        self.assertAlmostEqual(first.principal_payment, 60_000)
        self.assertAlmostEqual(first.dscr, 1.4)

    def test_exit_uses_next_year_noi(self):
        result = analyse_investment(
            sample_property(
                rent_growth_rate=0.0,
                expense_growth_rate=0.0,
                capex_by_year=(),
            ),
            FinancingAssumptions(loan_to_value=0.0, interest_rate=0.0),
        )
        self.assertAlmostEqual(result.terminal_value, 8_400_000)
        self.assertAlmostEqual(result.selling_costs, 84_000)

    def test_leverage_changes_equity_cash_flows(self):
        all_cash = analyse_investment(
            sample_property(),
            FinancingAssumptions(loan_to_value=0.0, interest_rate=0.0),
        )
        levered = analyse_investment(
            sample_property(),
            FinancingAssumptions(loan_to_value=0.6, interest_rate=0.03),
        )
        self.assertEqual(all_cash.initial_equity, 10_000_000)
        self.assertEqual(levered.initial_equity, 4_000_000)
        self.assertNotEqual(all_cash.levered_irr, levered.levered_irr)

    def test_equity_multiple_counts_additional_negative_cash_flow(self):
        result = analyse_investment(
            sample_property(capex_by_year=(0, 0, 2_000_000, 0, 0)),
            FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04),
        )
        inflows = sum(max(value, 0) for value in result.levered_cash_flows)
        contributions = abs(sum(min(value, 0) for value in result.levered_cash_flows))
        self.assertAlmostEqual(result.equity_multiple, inflows / contributions)

    def test_irr_known_example(self):
        self.assertAlmostEqual(annual_irr([-100, 110]), 0.10, places=8)

    def test_invalid_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            sample_property(vacancy_rate=1.2)

    def test_standard_scenarios_have_expected_ordering(self):
        cases = standard_scenarios(
            sample_property(),
            FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04),
        )
        by_name = {case.name: case.analysis for case in cases}
        self.assertGreater(by_name["Upside"].dcf_value, by_name["Base"].dcf_value)
        self.assertLess(by_name["Downside"].dcf_value, by_name["Base"].dcf_value)
        self.assertGreater(by_name["Upside"].levered_irr, by_name["Base"].levered_irr)
        self.assertLess(by_name["Downside"].levered_irr, by_name["Base"].levered_irr)

    def test_sensitivity_grid_has_25_points_and_expected_direction(self):
        property_case = sample_property()
        financing = FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04)
        points = sensitivity_grid(property_case, financing)
        self.assertEqual(len(points), 25)
        lowest_exit = min(points, key=lambda point: point.exit_cap_rate)
        highest_exit = max(points, key=lambda point: point.exit_cap_rate)
        self.assertGreater(lowest_exit.dcf_value, highest_exit.dcf_value)

    def test_decision_recommends_negotiation_for_overpriced_case(self):
        property_case = sample_property(purchase_price=12_000_000)
        financing = FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04)
        base = analyse_investment(property_case, financing)
        scenarios = standard_scenarios(property_case, financing)
        decision = make_decision(base, scenarios, InvestmentCriteria())
        self.assertEqual(decision.recommendation, "NEGOTIATE")
        self.assertLess(decision.recommended_price, property_case.purchase_price)
        self.assertTrue(decision.risks)

    def test_ic_memo_is_a_nontrivial_pdf(self):
        property_case = sample_property(purchase_price=12_000_000)
        financing = FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04)
        base = analyse_investment(property_case, financing)
        scenarios = standard_scenarios(property_case, financing)
        criteria = InvestmentCriteria()
        decision = make_decision(base, scenarios, criteria)
        pdf = build_ic_memo(base, scenarios, decision, criteria)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 8_000)

    def test_market_benchmark_analysis_identifies_rent_upside(self):
        result = analyse_investment(
            sample_property(potential_gross_rent=600_000),
            FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04),
        )
        benchmark = analyse_market_benchmarks(
            result,
            MarketBenchmarks(
                rentable_area_sqm=2_000,
                market_rent_per_sqm=330,
                market_vacancy_rate=0.03,
                market_price_per_sqm=5_200,
                market_cap_rate_low=0.04,
                market_cap_rate_high=0.05,
                market_opex_per_sqm=75,
                source="Test source",
                as_of_date="2026-Q2",
            ),
        )
        self.assertAlmostEqual(benchmark.subject_rent_per_sqm, 300)
        self.assertAlmostEqual(benchmark.rent_upside_annual, 60_000)
        self.assertEqual(benchmark.indicators[0].status, "Favorable")

    def test_ic_memo_includes_market_benchmarking(self):
        property_case = sample_property(purchase_price=12_000_000)
        financing = FinancingAssumptions(loan_to_value=0.6, interest_rate=0.04)
        base = analyse_investment(property_case, financing)
        scenarios = standard_scenarios(property_case, financing)
        criteria = InvestmentCriteria()
        decision = make_decision(base, scenarios, criteria)
        benchmark = analyse_market_benchmarks(
            base,
            MarketBenchmarks(
                rentable_area_sqm=2_000,
                market_rent_per_sqm=330,
                market_vacancy_rate=0.03,
                market_price_per_sqm=5_200,
                market_cap_rate_low=0.04,
                market_cap_rate_high=0.05,
                market_opex_per_sqm=75,
                source="Test source",
                as_of_date="2026-Q2",
            ),
        )
        pdf = build_ic_memo(base, scenarios, decision, criteria, benchmark)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 9_000)

    def test_comparable_analysis_scores_and_adjusts_evidence(self):
        comparables = (
            ComparableProperty(
                "A",
                "Zurich",
                "Residential",
                10_000_000,
                2_000,
                500_000,
                "2026-03-01",
                2.0,
                "Similar",
            ),
            ComparableProperty(
                "B",
                "Zurich",
                "Residential",
                9_600_000,
                2_000,
                480_000,
                "2025-10-01",
                4.0,
                "Inferior",
            ),
            ComparableProperty(
                "C",
                "Zurich",
                "Residential",
                10_800_000,
                2_000,
                520_000,
                "2025-08-01",
                6.0,
                "Superior",
            ),
        )
        analysis = analyse_comparables(
            comparables,
            subject_area_sqm=2_000,
            subject_property_type="Residential",
        )
        self.assertEqual(len(analysis.results), 3)
        self.assertGreater(analysis.indicated_value, 0)
        self.assertLess(analysis.lower_value, analysis.upper_value)
        self.assertEqual(analysis.confidence, "Medium")

    def test_deal_store_round_trip_and_update(self):
        with TemporaryDirectory() as directory:
            store = DealStore(Path(directory) / "deals.sqlite3")
            deal_id = store.save(
                name="Test deal",
                location="Zurich",
                payload={"schema_version": 1, "value": 10},
            )
            saved = store.get(deal_id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.payload["value"], 10)
            store.save(
                name="Updated deal",
                location="Zurich",
                payload={"schema_version": 1, "value": 20},
                deal_id=deal_id,
            )
            self.assertEqual(len(store.list()), 1)
            self.assertEqual(store.get(deal_id).payload["value"], 20)


if __name__ == "__main__":
    unittest.main()
