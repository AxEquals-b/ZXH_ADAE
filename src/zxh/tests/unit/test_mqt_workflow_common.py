from __future__ import annotations

import unittest

from benchmarks.ADAE.prepare.generators.mqt_workflow.common import (
    EXPECTED_ADAE_CASE_FAMILIES,
    benchmark_default_kwargs,
    is_environment_error,
    select_size_at_or_below,
    validate_expected_adae_case_families,
)


class MQTWorkflowCommonTests(unittest.TestCase):
    def test_seed_is_injected_only_for_families_with_seed_parameter(self) -> None:
        self.assertEqual(benchmark_default_kwargs("graphstate"), {"seed": 10})
        self.assertEqual(benchmark_default_kwargs("qaoa"), {"seed": 10})
        self.assertEqual(benchmark_default_kwargs("bv"), {})

    def test_is_environment_error_walks_exception_chain(self) -> None:
        try:
            try:
                raise ModuleNotFoundError("missing dep")
            except ModuleNotFoundError as exc:
                raise RuntimeError("wrapper") from exc
        except RuntimeError as exc:
            self.assertTrue(is_environment_error(exc))

    def test_validate_expected_adae_case_families_accepts_expected_set(self) -> None:
        self.assertEqual(
            validate_expected_adae_case_families(list(EXPECTED_ADAE_CASE_FAMILIES)),
            EXPECTED_ADAE_CASE_FAMILIES,
        )

    def test_validate_expected_adae_case_families_rejects_drift(self) -> None:
        observed = list(EXPECTED_ADAE_CASE_FAMILIES[:-1])
        with self.assertRaises(RuntimeError):
            validate_expected_adae_case_families(observed)

    def test_select_size_at_or_below_picks_largest_valid_candidate(self) -> None:
        self.assertEqual(select_size_at_or_below([20, 22, 24, 26], 25), 24)
        self.assertEqual(select_size_at_or_below([21, 25, 29, 31], 30), 29)

    def test_select_size_at_or_below_rejects_empty_candidate_set(self) -> None:
        with self.assertRaises(ValueError):
            select_size_at_or_below([25, 29], 24)


if __name__ == "__main__":
    unittest.main()
