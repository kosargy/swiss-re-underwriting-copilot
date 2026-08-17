import unittest
from datetime import date

from rent_roll import analyse_rent_roll, parse_rent_roll_csv


class RentRollTests(unittest.TestCase):
    def test_analysis_calculates_rent_vacancy_and_concentration(self):
        units = parse_rent_roll_csv(
            b"unit_id,tenant,annual_rent,status,lease_expiry\n"
            b"1,Tenant A,60000,Occupied,2026-12-31\n"
            b"2,Tenant B,40000,Occupied,2028-12-31\n"
            b"3,,25000,Vacant,\n"
        )
        result = analyse_rent_roll(units, as_of=date(2026, 8, 17))
        self.assertEqual(result.potential_annual_rent, 125000)
        self.assertEqual(result.passing_annual_rent, 100000)
        self.assertAlmostEqual(result.economic_vacancy_rate, 0.20)
        self.assertAlmostEqual(result.largest_tenant_share, 0.60)
        self.assertEqual(result.leases_expiring_within_12_months, 1)

    def test_invalid_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Occupied or Vacant"):
            parse_rent_roll_csv(
                b"unit_id,tenant,annual_rent,status,lease_expiry\n1,A,100,Unknown,\n"
            )


if __name__ == "__main__":
    unittest.main()
