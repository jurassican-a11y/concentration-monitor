import unittest

from scripts.build_html import event_metrics


class EventMetricsTests(unittest.TestCase):
    def test_first_reach_in_event_year_includes_threshold_and_ignores_later_recrossing(self):
        records = [
            {"date": "2025-12-31", "value": 0.50},
            {"date": "2026-01-01", "value": 0.44},
            {"date": "2026-01-02", "value": 0.45},
            {"date": "2026-01-05", "value": 0.40},
            {"date": "2026-01-06", "value": 0.48},
            {"date": "2026-01-07", "value": 0.43},
        ]
        result = event_metrics(records[::-1], {"date": "2026-01-07", "label": "顶"}, 0.45)
        self.assertEqual(result["warning_start"], "2026-01-02")
        self.assertEqual(result["days_to_top"], 5)
        self.assertEqual(result["value"], 0.43)

    def test_no_reach_before_event_does_not_use_later_data(self):
        result = event_metrics([
            {"date": "2026-01-05", "value": 0.44},
            {"date": "2026-01-06", "value": 0.50},
        ], {"date": "2026-01-05", "label": "顶"}, 0.45)
        self.assertIsNone(result["days_to_top"])
        self.assertIsNone(result["warning_start"])

    def test_event_day_reach_is_zero_days(self):
        result = event_metrics([{"date": "2026-07-01", "value": 0.45}],
                               {"date": "2026-07-01", "label": "顶"}, 0.45)
        self.assertEqual(result["days_to_top"], 0)

    def test_missing_event_day_never_substitutes_another_date(self):
        result = event_metrics([{"date": "2026-06-30", "value": 0.46}],
                               {"date": "2026-07-01", "label": "顶"}, 0.45)
        self.assertIsNone(result["value"])
        self.assertEqual(result["days_to_top"], 1)


if __name__ == "__main__":
    unittest.main()
