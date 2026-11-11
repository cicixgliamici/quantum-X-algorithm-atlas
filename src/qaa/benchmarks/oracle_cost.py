"""Reproducible problem-size study of explicit table-based quantum oracles."""

import argparse
import json
import platform
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from time import perf_counter

import numpy as np

from qaa._validation import positive_integer, validate_seed
from qaa.benchmarks.discrete_expectation import hoeffding_sample_count, quantum_record
from qaa.benchmarks.monte_carlo import dependency_versions
from qaa.problems.discrete import DiscreteExpectation


def synthetic_table(size: int, seed: int) -> DiscreteExpectation:
    """Generate dense irregular entries, avoiding uniform-state preparation shortcuts."""
    positive_integer(size, "size")
    validate_seed(seed)
    rng = np.random.default_rng(seed)
    weights = rng.uniform(0.1, 1.0, size)
    return DiscreteExpectation(
        probabilities=tuple(weights / np.sum(weights)),
        function_values=tuple(rng.uniform(0.05, 0.95, size)),
        bounds=(0.0, 1.0),
    )


def validate_design(sizes: tuple[int, ...], powers: tuple[int, ...], shots: int) -> None:
    """Validate before importing optional dependencies or constructing circuits."""
    for name, values, minimum in (("sizes", sizes, 1), ("powers", powers, 0)):
        if not values:
            raise ValueError(f"{name} must not be empty")
        for value in values:
            positive_integer(value, name, minimum=minimum)
        if len(set(values)) != len(values):
            raise ValueError(f"{name} must not contain duplicates")
    positive_integer(shots, "shots")


def profile_size(size: int, seed: int, powers: tuple[int, ...], shots: int) -> dict:
    """Derive size-specific streams so adding or reordering sizes preserves inputs."""
    from qaa.quantum.oracle_resources import profile_discrete_oracle

    started = perf_counter()
    streams = np.random.SeedSequence([seed, size]).spawn(2)
    input_seed, estimation_seed = (int(stream.generate_state(1)[0]) for stream in streams)
    problem = synthetic_table(size, input_seed)
    input_seconds = perf_counter() - started
    return {
        "outcome_count": size,
        "index_qubits": max(1, (size - 1).bit_length()),
        "padded_outcome_count": 2 ** max(1, (size - 1).bit_length()),
        "input_seed": input_seed,
        "estimation_seed": estimation_seed,
        "inputs": asdict(problem),
        "exact_expectation": problem.exact_expectation,
        "input_generation_seconds": input_seconds,
        "oracle": profile_discrete_oracle(problem, powers, shots),
    }


def study_metadata(seed: int, design: dict) -> dict:
    """Keep compiler assumptions and environment beside every exported study."""
    return {
        "schema_version": 1,
        "study_id": "discrete-oracle-cost-v1",
        "seed": seed,
        "design": design,
        "resource_convention": {
            "basis_gates": ["u", "cx"],
            "optimization_level": 0,
            "seed_transpiler": 0,
            "depth_includes_measurements": True,
            "gate_counts_exclude": ["measure", "barrier"],
            "hardware_backend": None,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
        },
        "rows": [],
        "interpretation": (
            "Fixed-power probes are compiled but not sampled. Shot-weighted totals model "
            "circuit usage, not simulator work or hardware runtime. Optional IQAE runs are "
            "separate workloads; explicit table costs do not establish a quantum advantage."
        ),
    }


def run_oracle_cost_study(
    sizes: tuple[int, ...] = (2, 4, 8, 16),
    *,
    powers: tuple[int, ...] = (0, 1, 2, 4),
    shots: int = 256,
    seed: int = 42,
    with_estimation: bool = False,
    epsilon: float = 0.05,
    alpha: float = 0.05,
) -> dict:
    """Profile fixed workloads; optional IQAE is a separate single run per size."""
    validate_design(sizes, powers, shots)
    validate_seed(seed)
    hoeffding_sample_count(epsilon, alpha)
    started = perf_counter()
    report = study_metadata(
        seed,
        {
            "sizes": sizes,
            "grover_powers": powers,
            "shots_per_probe": shots,
            "with_estimation": with_estimation,
            "epsilon_normalized": epsilon,
            "alpha": alpha,
            "input_family": "seeded dense irregular probability and function tables",
        },
    )
    try:
        import_module("qaa.quantum.oracle_resources")
    except ModuleNotFoundError as error:
        if error.name not in {"qiskit", "qiskit_algorithms"}:
            raise
        return {**report, "status": "unavailable", "reason": str(error)}
    for size in sizes:
        row = profile_size(size, seed, powers, shots)
        row["iqae"] = (
            quantum_record(
                DiscreteExpectation(**row["inputs"]), epsilon, alpha, shots, row["estimation_seed"]
            )
            if with_estimation
            else {"status": "disabled"}
        )
        report["rows"].append(row)
    return {**report, "status": "completed", "total_elapsed_seconds": perf_counter() - started}


def main() -> None:
    """Export component and workload costs as JSON without plotting dependencies."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=int, default=[2, 4, 8, 16])
    parser.add_argument("--powers", nargs="+", type=int, default=[0, 1, 2, 4])
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--with-estimation", action="store_true")
    parser.add_argument("--epsilon", type=float, default=0.05)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--output", type=Path, default=Path("results/oracle-cost.json"))
    args = parser.parse_args()
    report = run_oracle_cost_study(
        tuple(args.sizes),
        powers=tuple(args.powers),
        shots=args.shots,
        seed=args.seed,
        with_estimation=args.with_estimation,
        epsilon=args.epsilon,
        alpha=args.alpha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({report['status']})")


if __name__ == "__main__":
    main()
