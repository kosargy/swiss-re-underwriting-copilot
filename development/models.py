from __future__ import annotations

from dataclasses import dataclass


def _non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")


def _rate(name: str, value: float, *, allow_one: bool = True) -> None:
    upper = 1.0 if allow_one else 1.0 - 1e-12
    if value < 0 or value > upper:
        raise ValueError(f"{name} must be between 0 and {upper}")


@dataclass(frozen=True)
class DevelopmentProject:
    name: str
    location: str
    asking_land_price: float
    plot_size_sqm: float
    density_ratio: float
    floor_space_efficiency: float
    discount_rate: float
    construction_cost_inflation: float
    revenue_growth_rate: float
    professional_fees_rate: float
    contingency_rate: float
    selling_cost_rate: float
    land_acquisition_cost_rate: float
    predevelopment_potential_income: float = 0.0
    predevelopment_vacancy_rate: float = 0.0
    predevelopment_operating_expenses: float = 0.0
    predevelopment_income_growth_rate: float = 0.0
    predevelopment_income_years: int = 0
    predevelopment_termination_cost: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "asking_land_price",
            "plot_size_sqm",
            "density_ratio",
            "predevelopment_potential_income",
            "predevelopment_operating_expenses",
            "predevelopment_termination_cost",
        ):
            _non_negative(field_name, getattr(self, field_name))
        if self.plot_size_sqm == 0 or self.density_ratio == 0:
            raise ValueError("plot_size_sqm and density_ratio must be above zero")
        for field_name in (
            "floor_space_efficiency",
            "discount_rate",
            "construction_cost_inflation",
            "revenue_growth_rate",
            "professional_fees_rate",
            "contingency_rate",
            "selling_cost_rate",
            "land_acquisition_cost_rate",
            "predevelopment_vacancy_rate",
            "predevelopment_income_growth_rate",
        ):
            _rate(field_name, getattr(self, field_name))
        if self.predevelopment_income_years < 0:
            raise ValueError("predevelopment_income_years cannot be negative")
        if self.floor_space_efficiency == 0:
            raise ValueError("floor_space_efficiency must be above zero")

    @property
    def gross_floor_area_sqm(self) -> float:
        return self.plot_size_sqm * self.density_ratio

    @property
    def net_floor_area_sqm(self) -> float:
        return self.gross_floor_area_sqm * self.floor_space_efficiency


@dataclass(frozen=True)
class DevelopmentPlan:
    name: str
    probability: float
    development_years: int
    residential_rental_share: float
    condo_sale_share: float
    commercial_rental_share: float
    residential_rent_per_sqm: float
    condo_sale_price_per_sqm: float
    commercial_rent_per_sqm: float
    residential_cap_rate: float
    commercial_cap_rate: float
    residential_cost_per_sqm: float
    condo_cost_per_sqm: float
    commercial_cost_per_sqm: float
    rental_parking_spaces: int = 0
    annual_rent_per_parking_space: float = 0.0
    sale_parking_spaces: int = 0
    sale_price_per_parking_space: float = 0.0

    def __post_init__(self) -> None:
        _rate("probability", self.probability)
        if self.development_years < 1:
            raise ValueError("development_years must be at least 1")
        for field_name in (
            "residential_rental_share",
            "condo_sale_share",
            "commercial_rental_share",
        ):
            _rate(field_name, getattr(self, field_name))
        if abs(self.total_use_share - 1.0) > 1e-8:
            raise ValueError("development use shares must total 100%")
        for field_name in (
            "residential_rent_per_sqm",
            "condo_sale_price_per_sqm",
            "commercial_rent_per_sqm",
            "residential_cost_per_sqm",
            "condo_cost_per_sqm",
            "commercial_cost_per_sqm",
            "annual_rent_per_parking_space",
            "sale_price_per_parking_space",
        ):
            _non_negative(field_name, getattr(self, field_name))
        for field_name in ("residential_cap_rate", "commercial_cap_rate"):
            _rate(field_name, getattr(self, field_name), allow_one=False)
        if self.residential_rental_share and self.residential_cap_rate == 0:
            raise ValueError("residential_cap_rate must be above zero")
        if self.commercial_rental_share and self.commercial_cap_rate == 0:
            raise ValueError("commercial_cap_rate must be above zero")
        if self.rental_parking_spaces < 0 or self.sale_parking_spaces < 0:
            raise ValueError("parking spaces cannot be negative")

    @property
    def total_use_share(self) -> float:
        return (
            self.residential_rental_share
            + self.condo_sale_share
            + self.commercial_rental_share
        )


@dataclass(frozen=True)
class DevelopmentYear:
    year: int
    construction_cost: float
    professional_fees: float
    contingency: float
    total_development_cost: float
    discount_factor: float
    present_value_of_cost: float


@dataclass(frozen=True)
class PreDevelopmentYear:
    year: int
    potential_income: float
    vacancy_loss: float
    operating_expenses: float
    termination_cost: float
    net_cash_flow: float
    discount_factor: float
    present_value: float


@dataclass(frozen=True)
class DevelopmentAnalysis:
    project: DevelopmentProject
    plan: DevelopmentPlan
    gross_floor_area_sqm: float
    net_floor_area_sqm: float
    residential_rental_area_sqm: float
    condo_sale_area_sqm: float
    commercial_rental_area_sqm: float
    residential_annual_rent: float
    commercial_annual_rent: float
    rental_parking_income: float
    residential_income_value: float
    commercial_income_value: float
    condo_sales_value: float
    parking_sales_value: float
    gross_development_value: float
    selling_costs: float
    net_completion_proceeds: float
    predevelopment_years: tuple[PreDevelopmentYear, ...]
    present_value_of_predevelopment_income: float
    development_years: tuple[DevelopmentYear, ...]
    total_nominal_development_cost: float
    present_value_of_development_cost: float
    present_value_of_completion_proceeds: float
    residual_land_value_before_acquisition_costs: float
    maximum_supportable_land_price: float
    project_npv_at_asking_price: float
    project_irr_at_asking_price: float | None
    nominal_project_profit_at_asking_price: float
    profit_margin_on_gdv: float
    value_surplus_to_asking_price: float
    recommendation: str
    cash_flows_at_asking_price: tuple[float, ...]
