from __future__ import annotations

import unittest

from benchmarks.ADAE.prepare.generators.mqt_workflow.sweep import (
    EXPECTED_REPRESENTATIVE_FAMILIES,
    _validate_expected_representatives,
)


class MQTWorkflowSweepTests(unittest.TestCase):
    def test_validate_expected_representatives_accepts_expected_mapping(self) -> None:
        obj = {
            "rows": [
                {"criterion": criterion, "family": family}
                for criterion, family in EXPECTED_REPRESENTATIVE_FAMILIES.items()
            ]
        }
        self.assertEqual(_validate_expected_representatives(obj), EXPECTED_REPRESENTATIVE_FAMILIES)

    def test_validate_expected_representatives_rejects_drift(self) -> None:
        obj = {
            "rows": [
                {"criterion": "bounded_support_min_rho_M_excluding_ghz", "family": "qft"},
                {"criterion": "transport_heavy_max_rho_X_excluding_ghz", "family": "vqe_two_local"},
                {"criterion": "lazy_expansion_min_rho_L_excluding_ghz", "family": "qft"},
                {"criterion": "adverse_full_support_max_rho_L_excluding_ghz", "family": "qwalk"},
            ]
        }
        with self.assertRaises(RuntimeError):
            _validate_expected_representatives(obj)


if __name__ == "__main__":
    unittest.main()
