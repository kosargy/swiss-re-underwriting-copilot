from __future__ import annotations

from dataclasses import dataclass


USE_PREMIUMS = {
    "Residential": 0.000,
    "Predominantly residential": 0.001,
    "Office": 0.003,
    "Retail": 0.007,
    "Industry / logistics": 0.013,
}

LOCATION_PREMIUMS = {
    "Residential": {
        "Large city · central": 0.000,
        "Large city · agglomeration": 0.003,
        "Small city": 0.007,
        "Rural": 0.015,
    },
    "Predominantly residential": {
        "Large city · central": 0.000,
        "Large city · agglomeration": 0.005,
        "Small city": 0.009,
        "Rural": 0.018,
    },
    "Office": {
        "Large city · central": 0.000,
        "Large city · agglomeration": 0.009,
        "Small city": 0.015,
        "Rural": 0.025,
    },
    "Retail": {
        "Large city · central": 0.000,
        "Large city · agglomeration": 0.010,
        "Small city": 0.015,
        "Rural": 0.025,
    },
    "Industry / logistics": {
        "Large city · central": 0.000,
        "Large city · agglomeration": 0.010,
        "Small city": 0.015,
        "Rural": 0.030,
    },
}


@dataclass(frozen=True)
class CapRateBuild:
    use: str
    location: str
    risk_free_rate: float
    real_estate_risk_premium: float
    use_premium: float
    location_premium: float
    object_specific_premium: float
    real_rental_growth: float
    net_cap_rate: float
    operating_cost_rate: float
    vacancy_rate: float
    repair_reserve_rate: float
    gross_cap_rate: float


def build_cap_rate(
    *,
    use: str,
    location: str,
    risk_free_rate: float,
    real_estate_risk_premium: float,
    object_specific_premium: float,
    real_rental_growth: float,
    operating_cost_rate: float,
    vacancy_rate: float,
    repair_reserve_rate: float,
) -> CapRateBuild:
    if use not in USE_PREMIUMS:
        raise ValueError(f"Unknown use: {use}")
    if location not in LOCATION_PREMIUMS[use]:
        raise ValueError(f"Unknown location: {location}")
    rates = (
        risk_free_rate,
        real_estate_risk_premium,
        object_specific_premium,
        real_rental_growth,
        operating_cost_rate,
        vacancy_rate,
        repair_reserve_rate,
    )
    if any(rate < 0 or rate > 1 for rate in rates):
        raise ValueError("Cap-rate inputs must be between 0% and 100%")
    cost_share = operating_cost_rate + vacancy_rate + repair_reserve_rate
    if cost_share >= 1:
        raise ValueError("Operating costs, vacancy and repairs must total below 100%")
    use_premium = USE_PREMIUMS[use]
    location_premium = LOCATION_PREMIUMS[use][location]
    net_cap_rate = (
        risk_free_rate
        + real_estate_risk_premium
        + use_premium
        + location_premium
        + object_specific_premium
        - real_rental_growth
    )
    if net_cap_rate <= 0:
        raise ValueError("The resulting net cap rate must be above zero")
    gross_cap_rate = net_cap_rate / (1.0 - cost_share)
    return CapRateBuild(
        use=use,
        location=location,
        risk_free_rate=risk_free_rate,
        real_estate_risk_premium=real_estate_risk_premium,
        use_premium=use_premium,
        location_premium=location_premium,
        object_specific_premium=object_specific_premium,
        real_rental_growth=real_rental_growth,
        net_cap_rate=net_cap_rate,
        operating_cost_rate=operating_cost_rate,
        vacancy_rate=vacancy_rate,
        repair_reserve_rate=repair_reserve_rate,
        gross_cap_rate=gross_cap_rate,
    )
