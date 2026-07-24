from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ComparableProperty:
    name: str
    location: str
    property_type: str
    price: float
    rentable_area_sqm: float
    annual_rent: float
    transaction_date: str
    distance_km: float
    condition_vs_subject: str
    source_url: str = ""

    def __post_init__(self) -> None:
        if self.price <= 0:
            raise ValueError("Comparable price must be above zero")
        if self.rentable_area_sqm <= 0:
            raise ValueError("Comparable rentable area must be above zero")
        if self.annual_rent < 0 or self.distance_km < 0:
            raise ValueError("Comparable rent and distance cannot be negative")
        if self.condition_vs_subject not in {"Inferior", "Similar", "Superior"}:
            raise ValueError("Condition must be Inferior, Similar or Superior")


@dataclass(frozen=True)
class ComparableResult:
    comparable: ComparableProperty
    price_per_sqm: float
    gross_yield: float | None
    relevance_score: float
    adjusted_price_per_sqm: float
    adjustment: float


@dataclass(frozen=True)
class ComparableAnalysis:
    results: tuple[ComparableResult, ...]
    median_price_per_sqm: float
    weighted_adjusted_price_per_sqm: float
    lower_price_per_sqm: float
    upper_price_per_sqm: float
    indicated_value: float
    lower_value: float
    upper_value: float
    average_relevance_score: float
    confidence: str


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _months_old(value: str, as_of: date) -> int:
    try:
        observed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return 36
    return max(
        0,
        (as_of.year - observed.year) * 12 + as_of.month - observed.month,
    )


def analyse_comparables(
    comparables: tuple[ComparableProperty, ...],
    *,
    subject_area_sqm: float,
    subject_property_type: str,
    as_of: date | None = None,
) -> ComparableAnalysis:
    if not comparables:
        raise ValueError("At least one comparable is required")
    if subject_area_sqm <= 0:
        raise ValueError("subject_area_sqm must be above zero")
    as_of = as_of or date.today()
    results: list[ComparableResult] = []

    condition_adjustments = {
        "Inferior": 0.05,
        "Similar": 0.0,
        "Superior": -0.05,
    }
    for comparable in comparables:
        type_score = (
            30.0
            if comparable.property_type.casefold() == subject_property_type.casefold()
            else 10.0
        )
        distance_score = 25.0 * max(0.0, 1.0 - comparable.distance_km / 20.0)
        area_difference = abs(
            comparable.rentable_area_sqm / subject_area_sqm - 1.0
        )
        area_score = 25.0 * max(0.0, 1.0 - area_difference)
        months_old = _months_old(comparable.transaction_date, as_of)
        recency_score = 20.0 * max(0.0, 1.0 - months_old / 36.0)
        relevance = min(
            100.0,
            type_score + distance_score + area_score + recency_score,
        )

        price_per_sqm = comparable.price / comparable.rentable_area_sqm
        adjustment = condition_adjustments[comparable.condition_vs_subject]
        adjusted_price_per_sqm = price_per_sqm * (1.0 + adjustment)
        gross_yield = (
            comparable.annual_rent / comparable.price
            if comparable.annual_rent > 0
            else None
        )
        results.append(
            ComparableResult(
                comparable=comparable,
                price_per_sqm=price_per_sqm,
                gross_yield=gross_yield,
                relevance_score=relevance,
                adjusted_price_per_sqm=adjusted_price_per_sqm,
                adjustment=adjustment,
            )
        )

    adjusted_values = [item.adjusted_price_per_sqm for item in results]
    total_weight = sum(max(item.relevance_score, 1.0) for item in results)
    weighted_price = sum(
        item.adjusted_price_per_sqm * max(item.relevance_score, 1.0)
        for item in results
    ) / total_weight
    average_score = sum(item.relevance_score for item in results) / len(results)
    lower = _percentile(adjusted_values, 0.25)
    upper = _percentile(adjusted_values, 0.75)
    confidence = (
        "High"
        if len(results) >= 6 and average_score >= 70
        else "Medium"
        if len(results) >= 3 and average_score >= 50
        else "Low"
    )
    return ComparableAnalysis(
        results=tuple(sorted(results, key=lambda item: item.relevance_score, reverse=True)),
        median_price_per_sqm=_percentile(
            [item.price_per_sqm for item in results],
            0.50,
        ),
        weighted_adjusted_price_per_sqm=weighted_price,
        lower_price_per_sqm=lower,
        upper_price_per_sqm=upper,
        indicated_value=weighted_price * subject_area_sqm,
        lower_value=lower * subject_area_sqm,
        upper_value=upper * subject_area_sqm,
        average_relevance_score=average_score,
        confidence=confidence,
    )
