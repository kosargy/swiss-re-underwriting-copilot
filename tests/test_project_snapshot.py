import json
import unittest

from project_snapshot import build_project_snapshot, parse_project_snapshot


class ProjectSnapshotTests(unittest.TestCase):
    def test_round_trip_keeps_allowed_assumptions(self):
        snapshot = build_project_snapshot(
            strategy="Value-Add / Repositioning",
            project_name="Zürich Case",
            widget_values={"va_purchase_price": 12_000_000.0, "va_name": "Case"},
        )

        restored = parse_project_snapshot(
            snapshot,
            expected_strategy="Value-Add / Repositioning",
            allowed_keys=("va_purchase_price", "va_name"),
        )

        self.assertEqual(restored["project_name"], "Zürich Case")
        self.assertEqual(restored["widget_values"]["va_purchase_price"], 12_000_000.0)

    def test_unknown_fields_are_ignored(self):
        snapshot = build_project_snapshot(
            strategy="Ground-Up Development",
            project_name="Site",
            widget_values={"dev_plot_size": 2_000.0, "unsupported": "ignore me"},
        )

        restored = parse_project_snapshot(
            snapshot,
            expected_strategy="Ground-Up Development",
            allowed_keys=("dev_plot_size",),
        )

        self.assertEqual(restored["widget_values"], {"dev_plot_size": 2_000.0})

    def test_wrong_strategy_is_rejected(self):
        snapshot = build_project_snapshot(
            strategy="Ground-Up Development",
            project_name="Site",
            widget_values={"dev_plot_size": 2_000.0},
        )

        with self.assertRaisesRegex(ValueError, "belongs to"):
            parse_project_snapshot(
                snapshot,
                expected_strategy="Value-Add / Repositioning",
                allowed_keys=("va_name",),
            )

    def test_invalid_schema_is_rejected(self):
        snapshot = json.dumps(
            {"schema": "unknown", "version": 1, "widget_values": {"va_name": "Case"}}
        ).encode()

        with self.assertRaisesRegex(ValueError, "schema"):
            parse_project_snapshot(
                snapshot,
                expected_strategy="Value-Add / Repositioning",
                allowed_keys=("va_name",),
            )


if __name__ == "__main__":
    unittest.main()
