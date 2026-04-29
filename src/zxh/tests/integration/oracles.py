from __future__ import annotations

from collections.abc import Mapping


def _as_probabilities(counts: Mapping[str, int], shots: int) -> dict[str, float]:
    if shots <= 0:
        raise ValueError("shots must be positive")
    return {bitstr: count / shots for bitstr, count in counts.items()}


def _eval_delta(
    counts: Mapping[str, int], shots: int, oracle: Mapping[str, object]
) -> tuple[bool, dict]:
    expected = str(oracle["expected"])
    unexpected = {bitstr: count for bitstr, count in counts.items() if bitstr != expected}
    actual = counts.get(expected, 0)
    passed = actual == shots and not unexpected
    return passed, {
        "expected": expected,
        "actual": actual,
        "unexpected": unexpected,
    }


def _eval_support(counts: Mapping[str, int], oracle: Mapping[str, object]) -> tuple[bool, dict]:
    allowed = {str(bitstr) for bitstr in oracle["allowed"]}
    unexpected = {bitstr: count for bitstr, count in counts.items() if bitstr not in allowed}
    passed = not unexpected
    return passed, {
        "allowed": sorted(allowed),
        "unexpected": unexpected,
    }


def _eval_distribution(
    counts: Mapping[str, int], shots: int, oracle: Mapping[str, object]
) -> tuple[bool, dict]:
    expected = {str(bitstr): float(prob) for bitstr, prob in oracle["expected"].items()}
    tolerance = float(oracle["tolerance_abs"])
    actual = _as_probabilities(counts, shots)

    max_abs_error = 0.0
    per_state: dict[str, dict[str, float]] = {}
    for bitstr in sorted(set(actual) | set(expected)):
        actual_prob = actual.get(bitstr, 0.0)
        expected_prob = expected.get(bitstr, 0.0)
        abs_error = abs(actual_prob - expected_prob)
        max_abs_error = max(max_abs_error, abs_error)
        per_state[bitstr] = {
            "actual": actual_prob,
            "expected": expected_prob,
            "abs_error": abs_error,
        }

    passed = max_abs_error <= tolerance
    return passed, {
        "tolerance_abs": tolerance,
        "max_abs_error": max_abs_error,
        "per_state": per_state,
    }


def evaluate_oracle(
    counts: Mapping[str, int], shots: int, oracle: Mapping[str, object]
) -> tuple[bool, dict]:
    oracle_type = str(oracle["type"])
    if oracle_type == "delta":
        return _eval_delta(counts, shots, oracle)
    if oracle_type == "support":
        return _eval_support(counts, oracle)
    if oracle_type == "distribution":
        return _eval_distribution(counts, shots, oracle)
    raise ValueError(f"unsupported oracle type: {oracle_type}")
