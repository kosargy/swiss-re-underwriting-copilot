from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime


REQUIRED_COLUMNS = ("unit_id", "tenant", "annual_rent", "status", "lease_expiry")


@dataclass(frozen=True)
class RentRollUnit:
    unit_id: str
    tenant: str
    annual_rent: float
    status: str
    lease_expiry: date | None


@dataclass(frozen=True)
class RentRollAnalysis:
    units: tuple[RentRollUnit, ...]
    potential_annual_rent: float
    passing_annual_rent: float
    economic_vacancy_rate: float
    occupied_units: int
    vacant_units: int
    largest_tenant_share: float
    leases_expiring_within_12_months: int


def parse_rent_roll_csv(data: bytes) -> tuple[RentRollUnit, ...]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Rent roll must be UTF-8 CSV") from error

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or any(name not in reader.fieldnames for name in REQUIRED_COLUMNS):
        raise ValueError(f"Required columns: {', '.join(REQUIRED_COLUMNS)}")

    units: list[RentRollUnit] = []
    for row_number, row in enumerate(reader, start=2):
        unit_id = (row.get("unit_id") or "").strip()
        if not unit_id:
            raise ValueError(f"Row {row_number}: unit_id is required")
        try:
            annual_rent = float((row.get("annual_rent") or "").replace(",", ""))
        except ValueError as error:
            raise ValueError(f"Row {row_number}: annual_rent must be numeric") from error
        if annual_rent < 0:
            raise ValueError(f"Row {row_number}: annual_rent cannot be negative")
        status = (row.get("status") or "").strip().title()
        if status not in {"Occupied", "Vacant"}:
            raise ValueError(f"Row {row_number}: status must be Occupied or Vacant")
        expiry_text = (row.get("lease_expiry") or "").strip()
        try:
            lease_expiry = datetime.strptime(expiry_text, "%Y-%m-%d").date() if expiry_text else None
        except ValueError as error:
            raise ValueError(f"Row {row_number}: lease_expiry must use YYYY-MM-DD") from error
        units.append(
            RentRollUnit(
                unit_id=unit_id,
                tenant=(row.get("tenant") or "").strip(),
                annual_rent=annual_rent,
                status=status,
                lease_expiry=lease_expiry,
            )
        )
    if not units:
        raise ValueError("Rent roll contains no units")
    return tuple(units)


def analyse_rent_roll(
    units: tuple[RentRollUnit, ...],
    *,
    as_of: date | None = None,
) -> RentRollAnalysis:
    if not units:
        raise ValueError("Rent roll contains no units")
    as_of = as_of or date.today()
    horizon = date(as_of.year + 1, as_of.month, min(as_of.day, 28))
    potential = sum(unit.annual_rent for unit in units)
    occupied = tuple(unit for unit in units if unit.status == "Occupied")
    passing = sum(unit.annual_rent for unit in occupied)
    tenant_income: dict[str, float] = {}
    for unit in occupied:
        tenant = unit.tenant or "Unidentified tenant"
        tenant_income[tenant] = tenant_income.get(tenant, 0.0) + unit.annual_rent
    largest_share = max(tenant_income.values(), default=0.0) / passing if passing else 0.0
    expiries = sum(
        1
        for unit in occupied
        if unit.lease_expiry is not None and as_of <= unit.lease_expiry <= horizon
    )
    return RentRollAnalysis(
        units=units,
        potential_annual_rent=potential,
        passing_annual_rent=passing,
        economic_vacancy_rate=(potential - passing) / potential if potential else 0.0,
        occupied_units=len(occupied),
        vacant_units=len(units) - len(occupied),
        largest_tenant_share=largest_share,
        leases_expiring_within_12_months=expiries,
    )


def rent_roll_template() -> bytes:
    return (
        "unit_id,tenant,annual_rent,status,lease_expiry\n"
        "A-01,Example Tenant AG,48000,Occupied,2028-12-31\n"
        "A-02,,42000,Vacant,\n"
    ).encode("utf-8")
