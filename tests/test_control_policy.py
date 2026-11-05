"""Smoke test for the prototype policy contract, using explicitly synthetic input."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "dashboard_data.sample.json"


class PolicyExportTest(unittest.TestCase):
    def test_policy_is_exported_and_not_for_actuation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "policy.json"
            subprocess.run(
                [
                    sys.executable, str(ROOT / "scripts" / "export_control_policy.py"),
                    "--dashboard-data", str(SOURCE),
                    "--comparison", str(Path(tmp) / "missing.csv"),
                    "--crop", "tomato",
                    "--panel", "semi_transparent",
                    "--out", str(target),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            policy = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(policy["decision"]["recommended_angle_deg"], 20)
            self.assertEqual(policy["decision"]["mode"], "optimized_tracking")
            self.assertTrue(policy["constraints"]["requires_human_validation_before_real_actuation"])


if __name__ == "__main__":
    unittest.main()
