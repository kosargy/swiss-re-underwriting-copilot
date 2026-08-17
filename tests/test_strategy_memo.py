from __future__ import annotations

import unittest

from development import compare_development_plans
from strategy_memo import build_development_memo, build_value_add_memo
from value_add import analyse_value_add

from test_development import sample_plan, sample_project
from test_value_add import sample_financing, sample_project as sample_value_add_project


class StrategyMemoTests(unittest.TestCase):
    def test_value_add_memo_is_a_nontrivial_pdf(self) -> None:
        analysis = analyse_value_add(
            sample_value_add_project(),
            sample_financing(),
        )
        pdf = build_value_add_memo(analysis)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 5_000)

    def test_development_memo_is_a_nontrivial_pdf(self) -> None:
        project = sample_project()
        plan_a = sample_plan(name="Plan A", probability=0.60)
        plan_b = sample_plan(
            name="Plan B",
            probability=0.40,
            residential_rent_per_sqm=120.0,
        )
        comparison = compare_development_plans(project, (plan_a, plan_b))
        pdf = build_development_memo(project, comparison)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 5_000)


if __name__ == "__main__":
    unittest.main()
