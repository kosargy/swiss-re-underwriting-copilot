from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import analyse_investment
from .models import FinancingAssumptions, PropertyAssumptions


def _money(value: float) -> str:
    return f"CHF {value:,.0f}"


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def load_case(path: Path) -> tuple[PropertyAssumptions, FinancingAssumptions]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    property_data = payload["property"]
    property_data["capex_by_year"] = tuple(property_data.get("capex_by_year", ()))
    return (
        PropertyAssumptions(**property_data),
        FinancingAssumptions(**payload["financing"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Swiss real estate underwriting case.")
    parser.add_argument("case", type=Path, help="Path to a JSON case file")
    args = parser.parse_args()
    property_assumptions, financing_assumptions = load_case(args.case)
    result = analyse_investment(property_assumptions, financing_assumptions)

    print(f"\n{result.property.name} — {result.property.location}")
    print("=" * 72)
    print(f"Asking price:           {_money(result.property.purchase_price)}")
    print(f"Year 1 NOI:             {_money(result.year_one_noi)}")
    print(f"Implied cap rate:       {_percent(result.implied_cap_rate)}")
    print(f"Direct-cap value:       {_money(result.direct_cap_value)}")
    print(f"DCF value:              {_money(result.dcf_value)}")
    print(f"NPV at asking price:    {_money(result.npv_at_asking_price)}")
    print(f"Unlevered IRR:          {_percent(result.unlevered_irr)}")
    print(f"Levered IRR:            {_percent(result.levered_irr)}")
    print(f"Equity multiple:        {result.equity_multiple:.2f}x")
    print(f"Minimum DSCR:           {result.minimum_dscr:.2f}x")
    print(f"Break-even occupancy:   {_percent(result.break_even_occupancy_year_one)}")
    print(f"Terminal value:         {_money(result.terminal_value)}")

    print("\nAnnual projection")
    print("-" * 72)
    print("Year        Effective income          NOI        CapEx    Debt service")
    for item in result.projections:
        print(
            f"{item.year:>4} "
            f"{_money(item.effective_income):>23} "
            f"{_money(item.noi):>12} "
            f"{_money(item.capex):>12} "
            f"{_money(item.debt_service):>15}"
        )


if __name__ == "__main__":
    main()

