from __future__ import annotations

from dataclasses import dataclass, field


def _non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _rate(name: str, value: float, *, allow_one: bool = True) -> None:
    upper = 1.0 if allow_one else 1.0 - 1e-12
    if value < 0 or value > upper:
        raise ValueError(f"{name} must be between 0 and {upper}")


@dataclass(frozen=True)
class ValueAddProject:
    name: str
    location: str
    purchase_price: float
    acquisition_cost_rate: float
    current_potential_rent: float
    current_vacancy_rate: float
    current_operating_expenses: float
    current_market_cap_rate: float
    renovation_years: int
    renovation_capex_by_year: tuple[float, ...] = field(default_factory=tuple)
    income_retention_during_renovation: float = 0.70
    stabilized_potential_rent: float = 0.0
    stabilized_vacancy_rate: float = 0.03
    stabilized_operating_expenses: float = 0.0
    annual_rent_growth_rate: float = 0.015
    annual_expense_growth_rate: float = 0.02
    exit_cap_rate: float = 0.04
    discount_rate: float = 0.07
    selling_cost_rate: float = 0.01
    holding_period_years: int = 5
    target_unlevered_irr: float = 0.07
    target_levered_irr: float = 0.10

    def __post_init__(self) -> None:
        for field_name in (
            "purchase_price",
            "current_potential_rent",
            "current_operating_expenses",
            "stabilized_potential_rent",
            "stabilized_operating_expenses",
        ):
            _non_negative(field_name, getattr(self, field_name))
        for field_name in (
            "acquisition_cost_rate",
            "current_vacancy_rate",
            "current_market_cap_rate",
            "income_retention_during_renovation",
            "stabilized_vacancy_rate",
            "annual_rent_growth_rate",
            "annual_expense_growth_rate",
            "exit_cap_rate",
            "discount_rate",
            "selling_cost_rate",
            "target_unlevered_irr",
            "target_levered_irr",
        ):
            _rate(field_name, getattr(self, field_name), allow_one=False)
        if self.current_market_cap_rate == 0 or self.exit_cap_rate == 0:
            raise ValueError("capitalization rates must be above zero")
        if self.renovation_years < 1:
            raise ValueError("renovation_years must be at least 1")
        if self.holding_period_years <= self.renovation_years:
            raise ValueError("holding period must extend beyond renovation")
        if len(self.renovation_capex_by_year) != self.renovation_years:
            raise ValueError("provide one CapEx amount for each renovation year")
        for amount in self.renovation_capex_by_year:
            _non_negative("renovation CapEx", amount)

    @property
    def total_renovation_capex(self) -> float:
        return sum(self.renovation_capex_by_year)

    def capex_for_year(self, year: int) -> float:
        if 1 <= year <= self.renovation_years:
            return self.renovation_capex_by_year[year - 1]
        return 0.0


@dataclass(frozen=True)
class ValueAddFinancing:
    purchase_loan_to_value: float
    interest_rate: float
    annual_amortization_rate: float = 0.0

    def __post_init__(self) -> None:
        _rate("purchase_loan_to_value", self.purchase_loan_to_value)
        _rate("interest_rate", self.interest_rate, allow_one=False)
        _rate("annual_amortization_rate", self.annual_amortization_rate)


@dataclass(frozen=True)
class ValueAddProjection:
    year: int
    phase: str
    potential_rent: float
    vacancy_loss: float
    renovation_income_loss: float
    effective_income: float
    operating_expenses: float
    noi: float
    renovation_capex: float
    unlevered_cash_flow_before_sale: float
    opening_loan_balance: float
    interest_payment: float
    principal_payment: float
    debt_service: float
    ending_loan_balance: float
    dscr: float | None
    equity_cash_flow_before_sale: float


@dataclass(frozen=True)
class ValueAddAnalysis:
    project: ValueAddProject
    financing: ValueAddFinancing
    projections: tuple[ValueAddProjection, ...]
    current_noi: float
    as_is_value: float
    stabilized_noi: float
    stabilized_value: float
    gross_value_uplift: float
    incremental_value_created: float
    renovation_roi: float | None
    loan_amount: float
    initial_equity: float
    terminal_value: float
    selling_costs: float
    maximum_supportable_purchase_price: float
    break_even_total_renovation_capex: float | None
    project_npv_at_asking_price: float
    unlevered_irr: float | None
    levered_irr: float | None
    equity_multiple: float
    minimum_stabilized_dscr: float | None
    recommendation: str
    unlevered_cash_flows: tuple[float, ...]
    levered_cash_flows: tuple[float, ...]
