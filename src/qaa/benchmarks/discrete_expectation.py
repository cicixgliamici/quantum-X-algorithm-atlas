"""Single-run discrete calibration with matched nominal accuracy and confidence."""

import argparse
import json
import math
import platform
from dataclasses import asdict
from pathlib import Path

import numpy as np

from qaa._validation import positive_integer, probability, validate_seed
from qaa.benchmarks.monte_carlo import dependency_versions
from qaa.classical.monte_carlo import estimate_expectation
from qaa.problems.discrete import DiscreteExpectation, synthetic_call_payoff


def hoeffding_sample_count(epsilon: float, alpha: float) -> int:
    """Use normalized error and the same failure target as IQAE, without tuning."""
    probability(epsilon, "epsilon")
    probability(alpha, "alpha")
    if not 0 < epsilon <= 0.5 or not 0 < alpha < 1:
        raise ValueError("require 0 < epsilon <= 0.5 and 0 < alpha < 1")
    return max(2, math.ceil(math.log(2 / alpha) / (2 * epsilon**2)))


def classical_record(problem: DiscreteExpectation, epsilon: float, alpha: float, seed: int) -> dict:
    """Estimate original-unit values and include a clipped Hoeffding interval."""
    count = hoeffding_sample_count(epsilon, alpha)
    result = estimate_expectation(problem.sample, count, bounds=problem.bounds, seed=seed)
    lower, upper = problem.bounds
    half_width = (upper - lower) * math.sqrt(math.log(2 / alpha) / (2 * count))
    return {
        **asdict(result),
        "confidence_interval": (
            max(lower, result.estimate - half_width),
            min(upper, result.estimate + half_width),
        ),
        "confidence_method": "Hoeffding (conservative, IID bounded observations)",
        "alpha": alpha,
        "absolute_error": abs(result.estimate - problem.exact_expectation),
    }


def quantum_record(
    problem: DiscreteExpectation, epsilon: float, alpha: float, shots: int, seed: int
) -> dict:
    """Missing quantum extras are explicit; estimator failures propagate."""
    try:
        from qaa.quantum.discrete_expectation import estimate_discrete_expectation
    except ModuleNotFoundError as error:
        if error.name not in {"qiskit", "qiskit_algorithms"}:
            raise
        return {"status": "unavailable", "reason": str(error)}
    result = estimate_discrete_expectation(
        problem, epsilon_target=epsilon, alpha=alpha, shots=shots, seed=seed
    )
    return {
        "status": "completed",
        **asdict(result),
        "absolute_error": abs(result.estimate - problem.exact_expectation),
    }


def run_discrete_benchmark(
    problem: DiscreteExpectation,
    *,
    epsilon: float = 0.03,
    alpha: float = 0.05,
    shots: int = 256,
    seed: int = 42,
    quantum: bool = True,
) -> dict:
    """Run one independent stream per method; this is not the replicated study."""
    validate_seed(seed)
    positive_integer(shots, "shots")
    hoeffding_sample_count(epsilon, alpha)
    streams = np.random.SeedSequence(seed).spawn(2)
    classical_seed, quantum_seed = (int(stream.generate_state(1)[0]) for stream in streams)
    lower, upper = problem.bounds
    return {
        "schema_version": 1,
        "problem": "explicit discrete expectation calibration",
        "inputs": asdict(problem),
        "exact_expectation": problem.exact_expectation,
        "epsilon_normalized": epsilon,
        "absolute_error_target": (upper - lower) * epsilon,
        "alpha": alpha,
        "seed": seed,
        "method_seeds": {"classical": classical_seed, "quantum": quantum_seed},
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
        },
        "classical": classical_record(problem, epsilon, alpha, classical_seed),
        "quantum": (
            quantum_record(problem, epsilon, alpha, shots, quantum_seed)
            if quantum
            else {"status": "disabled"}
        ),
        "interpretation": (
            "Known explicit input tables; exact summation is the validation baseline. "
            "Logical queries, simulator shots and IID observations are different costs."
        ),
    }


def main() -> None:
    """Export the synthetic four-scenario payoff example as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/discrete-expectation.json"))
    parser.add_argument("--epsilon", type=float, default=0.03)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--classical-only", action="store_true")
    args = parser.parse_args()
    report = run_discrete_benchmark(
        synthetic_call_payoff(),
        epsilon=args.epsilon,
        alpha=args.alpha,
        shots=args.shots,
        seed=args.seed,
        quantum=not args.classical_only,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
