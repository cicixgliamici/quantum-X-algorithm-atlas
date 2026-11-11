"""Descriptive cell summaries with explicit denominators and Wilson uncertainty."""

import math
from collections import Counter
from statistics import NormalDist

import numpy as np

from qaa._validation import positive_integer
from qaa.benchmarks.study_design import ReplicationDesign, trial_plan


def wilson_interval(successes: int, trials: int) -> tuple[float, float] | None:
    """Return a 95% binomial Wilson interval; zero observations have no estimate."""
    positive_integer(trials, "trials", minimum=0)
    positive_integer(successes, "successes", minimum=0)
    if successes > trials:
        raise ValueError("successes must not exceed trials")
    if trials == 0:
        return None
    z = NormalDist().inv_cdf(0.975)
    rate = successes / trials
    denominator = 1 + z**2 / trials
    center = (rate + z**2 / (2 * trials)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / trials + z**2 / (4 * trials**2)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def distribution_summary(values: list[float]) -> dict | None:
    """Use explicit linear quantiles; empty completed subsets have no distribution."""
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError("summary observations must be finite")
    return {
        "count": len(values),
        "minimum": float(array.min()),
        "maximum": float(array.max()),
        "q10": float(np.quantile(array, 0.1, method="linear")),
        "median": float(np.median(array)),
        "q90": float(np.quantile(array, 0.9, method="linear")),
    }


def rate_summary(successes: int, denominator: int) -> dict:
    """Keep the event count and its denominator next to the displayed fraction."""
    return {
        "count": successes,
        "denominator": denominator,
        "rate": successes / denominator if denominator else None,
        "wilson_95": wilson_interval(successes, denominator),
    }


def accuracy_summary(completed: list[dict]) -> dict:
    """All quantities here are conditional on a completed, valid estimator result."""
    errors = np.array([r["signed_error"] for r in completed], dtype=float)
    return {
        "bias": float(errors.mean()) if errors.size else None,
        "rmse": float(np.sqrt(np.mean(errors**2))) if errors.size else None,
        "absolute_error": distribution_summary([r["absolute_error"] for r in completed]),
        "interval_width": distribution_summary([r["interval_width"] for r in completed]),
        "success": rate_summary(sum(r["within_tolerance"] for r in completed), len(completed)),
        "coverage": rate_summary(
            sum(r["interval_contains_truth"] for r in completed), len(completed)
        ),
    }


def cell_summary(cell: dict, method: str, records: list[dict], replications: int) -> dict:
    """Failures are visible; unresolved outcomes never count as verified accuracy."""
    completed = [r for r in records if r["status"] == "completed"]
    counts = Counter(r["status"] for r in records)
    counts["not_recorded"] = replications - len(records)
    successes = sum(r["within_tolerance"] for r in completed)
    resource_names = sorted({name for r in completed for name in r["costs"]})
    timing_names = sorted({name for r in completed for name in r["timings"]})
    return {
        **cell,
        "method": method,
        "planned": replications,
        "attempted": len(records),
        "status_counts": dict(counts),
        "completion": rate_summary(len(completed), replications),
        "accuracy_conditional_on_completion": accuracy_summary(completed),
        "verified_success_fraction_of_planned": successes / replications,
        "unresolved_count": replications - len(completed),
        "costs_conditional_on_completion": {
            name: distribution_summary([r["costs"][name] for r in completed if name in r["costs"]])
            for name in resource_names
        },
        "timings_conditional_on_completion": {
            name: distribution_summary(
                [r["timings"][name] for r in completed if name in r["timings"]]
            )
            for name in timing_names
        },
    }


def validate_completed_record(record: dict) -> None:
    """Check accuracy indicators against the recorded estimate, not just stored flags."""
    estimate = record["estimate"]
    truth = record["exact_expectation"] if "problem_id" in record else record["probability"]
    lower, upper = record.get("bounds", (0.0, 1.0))
    low, high = record["confidence_interval"]
    if not all(math.isfinite(v) for v in (estimate, low, high)):
        raise ValueError("completed record contains nonfinite values")
    if not lower <= low <= estimate <= high <= upper:
        raise ValueError("completed record has an invalid confidence interval")
    error = estimate - truth
    checks = {
        "signed_error": error,
        "absolute_error": abs(error),
        "within_tolerance": abs(error) <= record.get("absolute_error_target", record["epsilon"]),
        "interval_contains_truth": low <= truth <= high,
        "interval_width": high - low,
    }
    if any(record[k] != value for k, value in checks.items()):
        raise ValueError("completed record has inconsistent accuracy diagnostics")


def summarize_records(design: ReplicationDesign, records: list[dict]) -> dict:
    """Reject duplicate or mismatched trials instead of silently changing the design."""
    expected = {r["trial_id"]: r for r in trial_plan(design)}
    seen = set()
    groups: dict[tuple[int, str], list[dict]] = {}
    for record in records:
        trial_id = record["trial_id"]
        if trial_id in seen or trial_id not in expected:
            raise ValueError(f"duplicate or unknown trial ID: {trial_id}")
        if any(record.get(k) != v for k, v in expected[trial_id].items()):
            raise ValueError(f"trial does not match its registered seed/design: {trial_id}")
        if record["status"] not in {"completed", "failed", "unavailable"}:
            raise ValueError(f"unknown trial status: {record['status']}")
        if record["status"] == "completed":
            validate_completed_record(record)
        seen.add(trial_id)
        groups.setdefault((record["cell_id"], record["method"]), []).append(record)
    cells = [
        cell_summary(cell, method, groups.get((cell["cell_id"], method), []), design.replications)
        for cell in design.cells
        for method in design.methods
    ]
    return {
        "schema_version": 1,
        "planned_trials": len(expected),
        "recorded_trials": len(records),
        "completed_trials": sum(r["status"] == "completed" for r in records),
        "cells": cells,
        "interpretation": (
            "Accuracy, coverage, cost and timing summaries are conditional on completion. "
            "Verified success/planned is a conservative observed fraction, not a confidence bound. "
            "Wilson intervals describe replication-rate uncertainty, not per-estimate intervals. "
            "Endpoint controls are separate; cells and unlike resource units are not pooled."
        ),
    }
