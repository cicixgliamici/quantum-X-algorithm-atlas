"""Analytical checks for statistics, denominators and incomplete trial handling."""

import math

import pytest

from qaa.benchmarks.study_design import StudyDesign, trial_plan
from qaa.benchmarks.study_statistics import distribution_summary, summarize_records, wilson_interval


def design_and_records():
    design = StudyDesign(
        probabilities=(0.5,), epsilons=(0.1,), replications=3, endpoints=False, quantum=False
    )
    records = []
    for trial, estimate, interval, cost in zip(
        trial_plan(design),
        (0.4, 0.5, 0.8),
        ((0.3, 0.5), (0.45, 0.55), (0.7, 0.9)),
        (10, 20, 30),
        strict=True,
    ):
        error = estimate - 0.5
        records.append(
            {
                **trial,
                "status": "completed",
                "estimate": estimate,
                "signed_error": error,
                "absolute_error": abs(error),
                "confidence_interval": interval,
                "interval_width": interval[1] - interval[0],
                "within_tolerance": abs(error) <= 0.1,
                "interval_contains_truth": interval[0] <= 0.5 <= interval[1],
                "costs": {"sample_count": cost},
                "timings": {"run_wall_seconds": cost / 1000},
            }
        )
    return design, records


def test_analytical_summary():
    design, records = design_and_records()
    summary = summarize_records(design, records)
    cell = summary["cells"][0]
    accuracy = cell["accuracy_conditional_on_completion"]
    assert accuracy["bias"] == pytest.approx(0.2 / 3)
    assert accuracy["rmse"] == pytest.approx(math.sqrt(0.1 / 3))
    assert accuracy["success"]["rate"] == accuracy["coverage"]["rate"] == 2 / 3
    assert cell["costs_conditional_on_completion"]["sample_count"] == {
        "count": 3,
        "minimum": 10,
        "maximum": 30,
        "q10": 12,
        "median": 20,
        "q90": 28,
    }
    assert summary["recorded_trials"] == summary["completed_trials"] == 3


def test_failure_and_missing_trial_denominators():
    design, records = design_and_records()
    failed = {**list(trial_plan(design))[1], "status": "failed"}
    summary = summarize_records(design, [records[0], failed])
    cell = summary["cells"][0]
    assert cell["status_counts"] == {"completed": 1, "failed": 1, "not_recorded": 1}
    assert cell["accuracy_conditional_on_completion"]["success"]["rate"] == 1
    assert cell["verified_success_fraction_of_planned"] == 1 / 3
    assert cell["unresolved_count"] == 2
    assert cell["completion"]["denominator"] == 3


def test_empty_results_have_no_accuracy_estimate():
    design, _ = design_and_records()
    summary = summarize_records(design, [])
    accuracy = summary["cells"][0]["accuracy_conditional_on_completion"]
    assert accuracy["rmse"] is None
    assert accuracy["success"]["rate"] is None
    assert accuracy["success"]["wilson_95"] is None


def test_wilson_known_values():
    assert wilson_interval(5, 10) == pytest.approx((0.23659309, 0.76340691))
    assert wilson_interval(0, 10) == pytest.approx((0, 0.2775328))
    assert wilson_interval(10, 10) == pytest.approx((0.7224672, 1))
    assert wilson_interval(0, 0) is None
    with pytest.raises(ValueError):
        wilson_interval(11, 10)
    with pytest.raises(ValueError):
        distribution_summary([float("nan")])


def test_duplicate_and_seed_mismatch_rejected():
    design, records = design_and_records()
    with pytest.raises(ValueError, match="duplicate"):
        summarize_records(design, [records[0], records[0]])
    with pytest.raises(ValueError, match="seed/design"):
        summarize_records(design, [{**records[0], "seed": 0}])
    with pytest.raises(ValueError, match="inconsistent"):
        summarize_records(design, [{**records[0], "within_tolerance": False}])
