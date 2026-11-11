"""Run or reanalyze independent Monte Carlo/IQAE replications from mc-iqae-v1."""

import argparse
import hashlib
import json
import math
import platform
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import distributions
from pathlib import Path
from time import perf_counter

from qaa.benchmarks.discrete_expectation import classical_record, hoeffding_sample_count
from qaa.benchmarks.discrete_study_design import (
    PROTOCOL_ID,
    DiscreteStudyDesign,
    study_problem,
)
from qaa.benchmarks.monte_carlo import dependency_versions
from qaa.benchmarks.study_archive import archive_source, verify_source_archive, write_json
from qaa.benchmarks.study_design import StudyDesign, trial_plan
from qaa.benchmarks.study_statistics import summarize_records
from qaa.classical.monte_carlo import estimate_bernoulli

QUANTUM_COST_FIELDS = (
    "total_shots",
    "circuit_executions",
    "grover_queries",
    "state_preparation_calls",
    "forward_state_preparation_calls",
    "inverse_state_preparation_calls",
    "logical_gate_applications",
    "logical_single_qubit_gate_applications",
    "logical_two_qubit_gate_applications",
    "max_circuit_depth",
)

Study = StudyDesign | DiscreteStudyDesign


def discrete_classical_estimate(trial: dict, design: DiscreteStudyDesign) -> dict:
    """Use the declared range for the budget, never the observed sample variance."""
    result = classical_record(
        study_problem(trial["problem_id"]), trial["epsilon"], design.alpha, trial["seed"]
    )
    return {
        "estimate": result["estimate"],
        "confidence_interval": result["confidence_interval"],
        "costs": {"sample_count": result["sample_count"]},
        "timings": {"estimation_seconds": result["elapsed_seconds"]},
        "estimator_result": result,
    }


def discrete_quantum_estimate(trial: dict, design: DiscreteStudyDesign) -> dict:
    """Keep original-unit outputs and the complete normalized IQAE resource ledger."""
    from qaa.quantum.discrete_expectation import estimate_discrete_expectation

    result = estimate_discrete_expectation(
        study_problem(trial["problem_id"]),
        epsilon_target=trial["epsilon"],
        alpha=design.alpha,
        shots=design.shots,
        seed=trial["seed"],
    )
    record = quantum_diagnostics(result.amplitude_result, design.shots)
    return {
        **record,
        "estimate": result.estimate,
        "confidence_interval": result.confidence_interval,
        "timings": {
            **record["timings"],
            "problem_construction_seconds": result.problem_construction_seconds,
            "total_elapsed_seconds": result.total_elapsed_seconds,
        },
        "estimator_result": asdict(result),
    }


def classical_estimate(trial: dict, design: StudyDesign) -> dict:
    """Use a fixed Hoeffding budget; the analytical answer never tunes stopping."""
    count = hoeffding_sample_count(trial["epsilon"], design.alpha)
    result = estimate_bernoulli(trial["probability"], count, seed=trial["seed"])
    half_width = math.sqrt(math.log(2 / design.alpha) / (2 * count))
    return {
        "estimate": result.estimate,
        "confidence_interval": (
            max(0.0, result.estimate - half_width),
            min(1.0, result.estimate + half_width),
        ),
        "costs": {"sample_count": count},
        "timings": {"estimation_seconds": result.elapsed_seconds},
        "estimator_result": asdict(result),
    }


def quantum_estimate(trial: dict, design: StudyDesign) -> dict:
    """Keep real IQAE diagnostics, including every sampled circuit's resource ledger."""
    from qaa.quantum.amplitude_estimation import estimate_bernoulli_amplitude

    result = estimate_bernoulli_amplitude(
        trial["probability"],
        epsilon_target=trial["epsilon"],
        alpha=design.alpha,
        shots=design.shots,
        seed=trial["seed"],
    )
    return quantum_diagnostics(result, design.shots)


def quantum_diagnostics(result, shots: int) -> dict:
    """Check the same shot and query identities for both quantum problem families."""
    if result.grover_queries != shots * sum(c.grover_power for c in result.circuits):
        raise ValueError("IQAE Grover query accounting mismatch")
    if result.total_shots != shots * len(result.circuits):
        raise ValueError("IQAE shot accounting mismatch")
    return {
        "estimate": result.estimate,
        "confidence_interval": result.confidence_interval,
        "costs": {name: getattr(result, name) for name in QUANTUM_COST_FIELDS},
        "timings": {
            "estimation_seconds": result.elapsed_seconds,
            "resource_inspection_seconds": result.resource_inspection_seconds,
        },
        "estimator_result": asdict(result),
    }


def validate_result(result: dict, bounds: tuple | list = (0.0, 1.0)) -> None:
    """An invalid numerical result is a failed trial, never a successful missing value."""
    estimate = result["estimate"]
    interval = result["confidence_interval"]
    if len(interval) != 2 or not all(math.isfinite(v) for v in (estimate, *interval)):
        raise ValueError("estimate and confidence interval must be finite")
    if not bounds[0] <= interval[0] <= estimate <= interval[1] <= bounds[1]:
        raise ValueError("estimate must lie in an ordered confidence interval within bounds")
    if not all(math.isfinite(v) and v >= 0 for v in result["costs"].values()):
        raise ValueError("costs must be finite and nonnegative")


def execute_trial(trial: dict, design: Study) -> dict:
    """Never retry failed seeds; only missing quantum extras are unavailable."""
    started = perf_counter()
    record = {"schema_version": 1, **trial}
    try:
        if isinstance(design, DiscreteStudyDesign):
            estimator = (
                discrete_classical_estimate
                if trial["method"] == "classical"
                else discrete_quantum_estimate
            )
        else:
            estimator = classical_estimate if trial["method"] == "classical" else quantum_estimate
        result = estimator(trial, design)
        validate_result(result, trial.get("bounds", (0.0, 1.0)))
        # Validate nested diagnostics too, before classifying the attempt as completed.
        json.dumps(result, allow_nan=False)
        truth = trial["exact_expectation"] if "problem_id" in trial else trial["probability"]
        tolerance = trial.get("absolute_error_target", trial["epsilon"])
        signed_error = result["estimate"] - truth
        low, high = result["confidence_interval"]
        record.update(
            {
                "status": "completed",
                **result,
                "signed_error": signed_error,
                "absolute_error": abs(signed_error),
                "within_tolerance": abs(signed_error) <= tolerance,
                "interval_contains_truth": low <= truth <= high,
                "interval_width": high - low,
            }
        )
    except Exception as error:
        unavailable = (
            trial["method"] == "quantum"
            and isinstance(error, ModuleNotFoundError)
            and error.name in {"qiskit", "qiskit_algorithms"}
        )
        record.update(
            {
                "status": "unavailable" if unavailable else "failed",
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        )
    record["run_wall_seconds"] = perf_counter() - started
    if record["status"] == "completed":
        record["timings"]["run_wall_seconds"] = record["run_wall_seconds"]
    return record


def initial_manifest(design: Study, provenance: dict) -> dict:
    """Persist settings and frozen sources before generating any observations."""
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID if isinstance(design, DiscreteStudyDesign) else "mc-iqae-v1",
        "classification": design.classification,
        "design": asdict(design),
        "cells": design.cells,
        "methods": design.methods,
        "planned_trials": len(design.cells) * len(design.methods) * design.replications,
        "iqae_settings": {"confint_method": "beta", "min_ratio": 2},
        "classical_settings": {
            "budget": "Hoeffding",
            "sampling": "IID NumPy choice"
            if isinstance(design, DiscreteStudyDesign)
            else "IID NumPy binomial",
        },
        **({"problems": design.problems} if isinstance(design, DiscreteStudyDesign) else {}),
        "resource_limits": None,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
            "installed_packages": dict(
                sorted(
                    (package.metadata["Name"], package.version)
                    for package in distributions()
                    if package.metadata["Name"]
                )
            ),
        },
        "provenance": provenance,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "execution_state": "running",
    }


def read_study(directory: Path) -> tuple[dict, dict]:
    """Verify and recompute a study in memory without modifying its saved artifacts."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    verify_source_archive(directory, manifest["provenance"]["source_sha256"])
    settings = dict(manifest["design"])
    discrete = manifest["protocol_id"] == PROTOCOL_ID
    if manifest["protocol_id"] not in {PROTOCOL_ID, "mc-iqae-v1"}:
        raise ValueError("unsupported study protocol")
    for name in ("payoffs", "epsilons") if discrete else ("probabilities", "epsilons"):
        settings[name] = tuple(settings[name])
    design = DiscreteStudyDesign(**settings) if discrete else StudyDesign(**settings)
    if discrete:
        # JSON canonicalization reconciles immutable table tuples with saved arrays.
        expected_problems = json.loads(json.dumps(design.problems))
        if manifest["problems"] != expected_problems or manifest["cells"] != design.cells:
            raise ValueError("discrete tables or cells differ from the registered design")
    # An incomplete trailing JSON line is an explicit error, never silently dropped.
    raw_bytes = (directory / "trials.jsonl").read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if manifest.get("trials_sha256", digest) != digest:
        raise ValueError("raw trial log digest mismatch")
    records = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines()]
    summary = {
        "protocol_id": manifest["protocol_id"],
        "classification": design.classification,
        "source_sha256": manifest["provenance"]["source_sha256"],
        "trials_sha256": digest,
        **summarize_records(design, records),
    }
    return manifest, summary


def analyze_study(directory: Path) -> dict:
    """Rebuild saved summaries from raw records without running estimators."""
    _, summary = read_study(directory)
    write_json(directory / "summary.json", summary)
    return summary


def run_study(
    output: Path, design: Study, *, progress: Callable[[str], None] | None = None
) -> dict:
    """Append and flush each attempted trial; refuse to overwrite any existing study."""
    output.mkdir(parents=True, exist_ok=False)
    manifest = initial_manifest(design, archive_source(output))
    write_json(output / "manifest.json", manifest)
    finished = False
    try:
        with (output / "trials.jsonl").open("x", encoding="utf-8") as raw:
            for attempted, trial in enumerate(trial_plan(design), start=1):
                record = execute_trial(trial, design)
                raw.write(json.dumps(record, allow_nan=False) + "\n")
                raw.flush()
                if progress and trial["replicate"] == design.replications - 1:
                    progress(f"Recorded {attempted}/{manifest['planned_trials']} attempts")
        finished = True
    finally:
        manifest["execution_state"] = "finished" if finished else "interrupted"
        manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
        manifest["trials_sha256"] = hashlib.sha256(
            (output / "trials.jsonl").read_bytes()
        ).hexdigest()
        write_json(output / "manifest.json", manifest)
    summary = analyze_study(output)
    manifest["execution_state"] = (
        "completed"
        if summary["completed_trials"] == summary["planned_trials"]
        else "completed_with_failures"
    )
    write_json(output / "manifest.json", manifest)
    return summary


def parser() -> argparse.ArgumentParser:
    """Separate execution from analysis so regenerated summaries cannot rerun seeds."""
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output", type=Path, default=Path("results/statistical-study"))
    run.add_argument("--probabilities", nargs="+", type=float, default=[0.1, 0.3, 0.5, 0.9])
    run.add_argument("--epsilons", nargs="+", type=float, default=[0.1, 0.05, 0.025, 0.0125])
    run.add_argument("--replications", type=int, default=200)
    run.add_argument("--alpha", type=float, default=0.05)
    run.add_argument("--shots", type=int, default=256)
    run.add_argument("--seed", type=int, default=20261111)
    run.add_argument("--no-endpoints", action="store_true")
    run.add_argument("--classical-only", action="store_true")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("directory", type=Path)
    return root


def main() -> None:
    """Print progress and fail visibly if any planned estimation did not complete."""
    args = parser().parse_args()
    if args.command == "analyze":
        summary = analyze_study(args.directory)
    else:
        design = StudyDesign(
            tuple(args.probabilities),
            tuple(args.epsilons),
            args.replications,
            args.alpha,
            args.shots,
            args.seed,
            not args.no_endpoints,
            not args.classical_only,
        )
        summary = run_study(
            args.output, design, progress=lambda message: print(message, flush=True)
        )
    print(
        f"{summary['classification']}: "
        f"{summary['completed_trials']}/{summary['planned_trials']} completed"
    )
    if summary["completed_trials"] != summary["planned_trials"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
