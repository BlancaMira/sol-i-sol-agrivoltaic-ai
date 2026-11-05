"""Lightweight structural test for the curated subset of coursework dashboard data."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DashboardSubsetTest(unittest.TestCase):
    def test_subset_has_expected_crops_panels_and_points(self):
        p = json.loads((ROOT / "dashboard" / "dashboard_data.json").read_text(encoding="utf-8"))
        self.assertEqual(len(p["series"]), 4)
        for crop, panels in p["series"].items():
            self.assertEqual(len(panels), 3)
            for panel, observations in panels.items():
                self.assertEqual(len(observations), 168, (crop, panel))
        self.assertTrue((ROOT / "dashboard" / "index.html").is_file())

if __name__ == "__main__":
    unittest.main()
