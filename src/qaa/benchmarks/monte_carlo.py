"""Run a calibration benchmark; timings do not establish a quantum speedup."""

import argparse
import json
import platform
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from qaa._validation import probability, validate_seed
from qaa.classical.monte_carlo import estimate_bernoulli


def dependency_versions() -> dict[str, str | None]:
    """Record the actual environment, including absent optional packages."""
    versions: dict[str, str | None] = {}
    for name in ("quantum-algorithm-atlas", "numpy", "qiskit", "qiskit-algorithms"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    return versions


def run_benchmark(
    sample_sizes: tuple[int, ...] = (100, 1000, 10000),
    *,
    target_probability: float = 0.3,
    seed: int = 42,
    quantum: bool = True,
    shots: int = 256,
    epsilon_target: float = 0.03,
) -> dict:
    """Collect one seeded run per size; timing is descriptive, not a speedup test."""
    probability(target_probability)
    validate_seed(seed)
    if not sample_sizes:
        raise ValueError("sample_sizes must not be empty")
    classical = []
    # Distinct child streams avoid treating nested prefixes as independent trials.
    import numpy as np

    streams = np.random.SeedSequence(seed).spawn(len(sample_sizes))
    for count, stream in zip(sample_sizes, streams, strict=True):
        child_seed = int(stream.generate_state(1)[0])
        result = estimate_bernoulli(target_probability, count, seed=child_seed)
        classical.append(
            {**asdict(result), "absolute_error": abs(result.estimate - target_probability)}
        )
    quantum_result: dict = {"status": "disabled"}
    if quantum:
        try:
            from qaa.quantum.amplitude_estimation import estimate_bernoulli_amplitude
        except ModuleNotFoundError as error:
            # Missing extras are optional; algorithm/runtime errors must remain visible.
            if error.name not in {"qiskit", "qiskit_algorithms"}:
                raise
            quantum_result = {"status": "unavailable", "reason": str(error)}
        else:
            result = estimate_bernoulli_amplitude(
                target_probability, seed=seed, shots=shots, epsilon_target=epsilon_target
            )
            quantum_result = {
                "status": "completed",
                **asdict(result),
                "absolute_error": abs(result.estimate - target_probability),
            }
    return {
        "schema_version": 1,
        "problem": "known Bernoulli calibration",
        "target_probability": target_probability,
        "seed": seed,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
        },
        "classical": classical,
        "quantum": quantum_result,
        "interpretation": "Classical samples, simulator shots and logical Grover queries differ.",
    }


def main() -> None:
    """Export portable JSON; errors fail the command instead of inventing results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/monte_carlo.json"))
    parser.add_argument("--sample-sizes", nargs="+", type=int, default=[100, 1000, 10000])
    parser.add_argument("--probability", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--shots", type=int, default=256)
    parser.add_argument("--epsilon", type=float, default=0.03)
    parser.add_argument("--classical-only", action="store_true")
    args = parser.parse_args()
    report = run_benchmark(
        tuple(args.sample_sizes),
        target_probability=args.probability,
        seed=args.seed,
        quantum=not args.classical_only,
        shots=args.shots,
        epsilon_target=args.epsilon,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
