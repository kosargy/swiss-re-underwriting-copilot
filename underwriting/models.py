from __future__ import annotations

from dataclasses import dataclass, field


def _require_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _require_rate(name: str, value: float, *, allow_one: bool = False) -> None:
    upper = 1.0 if allow_one else 1.0 - 1e-12
    if value < 0 or value > upper:
        comparator = "between 0 and 1" if allow_one else "at least 0 and below 1"
        raise ValueError(f"{name} must be {comparator}")


@dataclass(frozen=True)
class PropertyAssumptions:
    name: str
    location: str
    purchase_price: float
    potential_gross_rent: float
    vacancy_rate: float
    operating_expenses: float
    market_cap_rate: float
    rent_growth_rate: float
    expense_growth_rate: float
    discount_rate: float
    exit_cap_rate: float
    holding_period_years: int = 5
    other_income: float = 0.0
    selling_cost_rate: float = 0.01
    capex_by_year: tuple[float, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in (
            "purchase_price",
            "potential_gross_rent",
            "operating_expenses",
            "other_income",
        ):
            _require_non_negative(name, getattr(self, name))
        for name in (
            "vacancy_rate",
            "market_cap_rate",
            "rent_growth_rate",
            "expense_growth_rate",
            "discount_rate",
            "exit_cap_rate",
            "selling_cost_rate",
        ):
            _require_rate(name, getattr(self, name))
        if self.market_cap_rate == 0 or self.exit_cap_rate == 0:
            raise ValueError("market_cap_rate and exit_cap_rate must be above zero")
        if self.holding_period_years < 1:
            raise ValueError("holding_period_years must be at least 1")
        if len(self.capex_by_year) > self.holding_period_years:
            raise ValueError("capex_by_year cannot exceed the holding period")
        for value in self.capex_by_year:
            _require_non_negative("capex", value)

    def capex_for_year(self, year: int) -> float:
        index = year - 1
        return self.capex_by_year[index] if index < len(self.capex_by_year) else 0.0


@dataclass(frozen=True)
class FinancingAssumptions:
    loan_to_value: float
    interest_rate: float
    annual_amortization_rate: float = 0.0

    def __post_init__(self) -> None:
        _require_rate("loan_to_value", self.loan_to_value, allow_one=True)
        _require_rate("interest_rate", self.interest_rate)
        _require_rate("annual_amortization_rate", self.annual_amortization_rate)


@dataclass(frozen=True)
class YearProjection:
    year: int
    potential_gross_rent: float
    vacancy_loss: float
    effective_income: float
    operating_expenses: float
    noi: float
    capex: float
    unlevered_cash_flow: float
    opening_loan_balance: float
    interest_payment: float
    principal_payment: float
    debt_service: float
    ending_loan_balance: float
    dscr: float | None
    cash_flow_to_equity_before_sale: float


@dataclass(frozen=True)
class InvestmentAnalysis:
    property: PropertyAssumptions
    financing: FinancingAssumptions
    projections: tuple[YearProjection, ...]
    loan_amount: float
    initial_equity: float
    year_one_noi: float
    implied_cap_rate: float
    direct_cap_value: float
    terminal_value: float
    selling_costs: float
    net_sale_proceeds_before_debt: float
    dcf_value: float
    npv_at_asking_price: float
    unlevered_irr: float | None
    levered_irr: float | None
    equity_multiple: float
    minimum_dscr: float | None
    break_even_occupancy_year_one: float
    unlevered_cash_flows: tuple[float, ...]
    levered_cash_flows: tuple[float, ...]

