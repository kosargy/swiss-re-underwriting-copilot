from __future__ import annotations

from dataclasses import dataclass

from .models import InvestmentAnalysis


@dataclass(frozen=True)
class MarketBenchmarks:
    rentable_area_sqm: float
    market_rent_per_sqm: float
    market_vacancy_rate: float
    market_price_per_sqm: float
    market_cap_rate_low: float
    market_cap_rate_high: float
    market_opex_per_sqm: float
    source: str
    as_of_date: str

    def __post_init__(self) -> None:
        if self.rentable_area_sqm <= 0:
            raise ValueError("rentable_area_sqm must be above zero")
        for name in (
            "market_rent_per_sqm",
            "market_price_per_sqm",
            "market_opex_per_sqm",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        for name in (
            "market_vacancy_rate",
            "market_cap_rate_low",
            "market_cap_rate_high",
        ):
            value = getattr(self, name)
            if value < 0 or value >= 1:
                raise ValueError(f"{name} must be at least 0 and below 1")
        if self.market_cap_rate_low <= 0:
            raise ValueError("market_cap_rate_low must be above zero")
        if self.market_cap_rate_high < self.market_cap_rate_low:
            raise ValueError("market_cap_rate_high cannot be below market_cap_rate_low")


@dataclass(frozen=True)
class BenchmarkIndicator:
    metric: str
    subject_value: float
    market_value: float
    difference: float
    status: str
    interpretation: str


@dataclass(frozen=True)
class BenchmarkAnalysis:
    benchmarks: MarketBenchmarks
    indicators: tuple[BenchmarkIndicator, ...]
    subject_rent_per_sqm: float
    subject_price_per_sqm: float
    subject_opex_per_sqm: float
    market_cap_rate_midpoint: float
    indicative_market_value_income: float
    indicative_market_value_price_per_sqm: float
    blended_market_value: float
    rent_upside_annual: float


def _relative_difference(subject: float, market: float) -> float:
    return 0.0 if market == 0 else subject / market - 1.0


def analyse_market_benchmarks(
    investment: InvestmentAnalysis,
    benchmarks: MarketBenchmarks,
) -> BenchmarkAnalysis:
    area = benchmarks.rentable_area_sqm
    subject_rent = investment.property.potential_gross_rent / area
    subject_price = investment.property.purchase_price / area
    subject_opex = investment.property.operating_expenses / area
    midpoint_cap = (
        benchmarks.market_cap_rate_low + benchmarks.market_cap_rate_high
    ) / 2.0

    market_effective_income = (
        benchmarks.market_rent_per_sqm
        * area
        * (1.0 - benchmarks.market_vacancy_rate)
        + investment.property.other_income
    )
    market_opex = benchmarks.market_opex_per_sqm * area
    market_noi = max(0.0, market_effective_income - market_opex)
    income_value = market_noi / midpoint_cap
    price_sqm_value = benchmarks.market_price_per_sqm * area
    blended_value = (income_value + price_sqm_value) / 2.0
    rent_upside = (
        benchmarks.market_rent_per_sqm - subject_rent
    ) * area

    rent_gap = _relative_difference(subject_rent, benchmarks.market_rent_per_sqm)
    price_gap = _relative_difference(subject_price, benchmarks.market_price_per_sqm)
    vacancy_gap = (
        investment.property.vacancy_rate - benchmarks.market_vacancy_rate
    )
    opex_gap = _relative_difference(subject_opex, benchmarks.market_opex_per_sqm)
    implied_cap = investment.implied_cap_rate

    if rent_gap <= -0.05:
        rent_status = "Favorable"
        rent_text = (
            "In-place potential rent is below the benchmark, indicating possible "
            "rental reversion subject to lease and regulatory review."
        )
    elif rent_gap >= 0.05:
        rent_status = "Caution"
        rent_text = (
            "In-place potential rent is above the benchmark; validate sustainability "
            "and reletting assumptions."
        )
    else:
        rent_status = "Neutral"
        rent_text = "In-place potential rent is broadly aligned with the benchmark."

    if price_gap >= 0.05:
        price_status = "Caution"
        price_text = "The asking price per m² exceeds the selected market benchmark."
    elif price_gap <= -0.05:
        price_status = "Favorable"
        price_text = "The asking price per m² is below the selected market benchmark."
    else:
        price_status = "Neutral"
        price_text = "The asking price per m² is broadly aligned with the benchmark."

    if vacancy_gap >= 0.02:
        vacancy_status = "Caution"
        vacancy_text = "Underwritten vacancy is materially above the market benchmark."
    elif vacancy_gap <= -0.02:
        vacancy_status = "Favorable"
        vacancy_text = "Underwritten vacancy is below the market benchmark."
    else:
        vacancy_status = "Neutral"
        vacancy_text = "Underwritten vacancy is broadly aligned with the benchmark."

    if opex_gap >= 0.10:
        opex_status = "Caution"
        opex_text = "Operating expenses per m² are materially above the benchmark."
    elif opex_gap <= -0.10:
        opex_status = "Favorable"
        opex_text = (
            "Operating expenses per m² are below the benchmark; confirm that no "
            "cost items are omitted."
        )
    else:
        opex_status = "Neutral"
        opex_text = "Operating expenses per m² are broadly aligned with the benchmark."

    if implied_cap < benchmarks.market_cap_rate_low:
        cap_status = "Caution"
        cap_text = (
            "The implied acquisition cap rate is below the selected market range, "
            "suggesting aggressive pricing."
        )
    elif implied_cap > benchmarks.market_cap_rate_high:
        cap_status = "Favorable"
        cap_text = (
            "The implied acquisition cap rate is above the selected market range; "
            "investigate whether additional risk explains the yield premium."
        )
    else:
        cap_status = "Neutral"
        cap_text = "The implied acquisition cap rate sits within the selected range."

    indicators = (
        BenchmarkIndicator(
            "Potential rent / m²",
            subject_rent,
            benchmarks.market_rent_per_sqm,
            rent_gap,
            rent_status,
            rent_text,
        ),
        BenchmarkIndicator(
            "Asking price / m²",
            subject_price,
            benchmarks.market_price_per_sqm,
            price_gap,
            price_status,
            price_text,
        ),
        BenchmarkIndicator(
            "Vacancy",
            investment.property.vacancy_rate,
            benchmarks.market_vacancy_rate,
            vacancy_gap,
            vacancy_status,
            vacancy_text,
        ),
        BenchmarkIndicator(
            "Operating expenses / m²",
            subject_opex,
            benchmarks.market_opex_per_sqm,
            opex_gap,
            opex_status,
            opex_text,
        ),
        BenchmarkIndicator(
            "Implied cap rate",
            implied_cap,
            midpoint_cap,
            implied_cap - midpoint_cap,
            cap_status,
            cap_text,
        ),
    )
    return BenchmarkAnalysis(
        benchmarks=benchmarks,
        indicators=indicators,
        subject_rent_per_sqm=subject_rent,
        subject_price_per_sqm=subject_price,
        subject_opex_per_sqm=subject_opex,
        market_cap_rate_midpoint=midpoint_cap,
        indicative_market_value_income=income_value,
        indicative_market_value_price_per_sqm=price_sqm_value,
        blended_market_value=blended_value,
        rent_upside_annual=rent_upside,
    )
