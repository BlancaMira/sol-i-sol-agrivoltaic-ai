"""Basic checks for the standalone portfolio dashboard.

This only checks that the HTML asset exists and is self-contained in size.
It is not an interactive browser or model-validity test.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardAssetTest(unittest.TestCase):
    def test_standalone_html_exists(self):
        path = ROOT / "dashboard" / "index.html"
        self.assertTrue(path.is_file())
        self.assertGreater(path.stat().st_size, 1_000_000)
        self.assertLess(path.stat().st_size, 10_000_000)

    def test_original_server_html_is_available(self):
        path = ROOT / "dashboard" / "index.server.html"
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
