"""Iterative QAE for a known Bernoulli calibration circuit, not unknown data."""

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import grover_operator
from qiskit.primitives import StatevectorSampler
from qiskit_algorithms import EstimationProblem, IterativeAmplitudeEstimation

from qaa._validation import positive_integer, probability, validate_seed


@dataclass(frozen=True)
class CircuitResources:
    """Logical resources after decomposition to u/cx, including measurements.

    These are circuit descriptions, not backend-transpiled hardware costs.
    """

    grover_power: int
    qubits: int
    depth: int
    gate_count: int
    measurement_count: int


@dataclass(frozen=True)
class AmplitudeEstimationResult:
    """Query counts are logical costs represented by the simulated circuits."""

    estimate: float
    confidence_interval: tuple[float, float]
    epsilon_target: float
    alpha: float
    shots_per_circuit: int
    circuit_executions: int
    total_shots: int
    grover_queries: int
    state_preparation_calls: int
    elapsed_seconds: float
    seed: int | None
    circuits: tuple[CircuitResources, ...]
    method: str = "iterative_amplitude_estimation"
    backend: str = "StatevectorSampler (ideal simulation, finite shots)"


def bernoulli_problem(target_probability: float) -> EstimationProblem:
    """Encode known p using A=Ry(2 asin(sqrt(p))); |1> marks success."""
    probability(target_probability)
    preparation = QuantumCircuit(1, name="A")
    preparation.ry(2 * np.arcsin(np.sqrt(target_probability)), 0)
    # Supply Q explicitly: Algorithms 0.4's default uses a deprecated Qiskit class.
    oracle = QuantumCircuit(1, name="success_reflection")
    oracle.z(0)
    return EstimationProblem(
        state_preparation=preparation,
        objective_qubits=[0],
        grover_operator=grover_operator(oracle, state_preparation=preparation),
    )


def circuit_resources(circuit: QuantumCircuit, power: int) -> CircuitResources:
    """Use a common logical basis so composite Q gates do not count as one gate."""
    from qiskit import transpile

    expanded = transpile(circuit, basis_gates=["u", "cx"], optimization_level=0)
    operations = expanded.count_ops()
    measurements = int(operations.get("measure", 0))
    return CircuitResources(
        int(power),
        expanded.num_qubits,
        expanded.depth(),
        # Barriers are scheduling directives, not physical or logical gates.
        int(sum(count for name, count in operations.items() if name not in {"measure", "barrier"})),
        measurements,
    )


def estimate_bernoulli_amplitude(
    target_probability: float,
    *,
    epsilon_target: float = 0.03,
    alpha: float = 0.05,
    shots: int = 256,
    seed: int | None = None,
) -> AmplitudeEstimationResult:
    """Run Qiskit's iterative QAE using reproducible finite-shot simulation.

    epsilon_target is an absolute confidence-interval half-width; alpha is
    the algorithm's failure probability, not an observed accuracy guarantee.
    """
    positive_integer(shots, "shots")
    validate_seed(seed)
    probability(epsilon_target, "epsilon_target")
    probability(alpha, "alpha")
    if not 0 < epsilon_target <= 0.5 or not 0 < alpha < 1:
        raise ValueError("require 0 < epsilon_target <= 0.5 and 0 < alpha < 1")
    problem = bernoulli_problem(target_probability)
    # A persistent stream avoids resetting identical measurement draws each round.
    sampler = StatevectorSampler(default_shots=int(shots), seed=np.random.default_rng(seed))
    algorithm = IterativeAmplitudeEstimation(epsilon_target, alpha, sampler=sampler)
    started = perf_counter()
    result = algorithm.estimate(problem)
    elapsed = perf_counter() - started
    # Qiskit's powers begins with a sentinel zero, before any circuit is run.
    powers = result.powers[1:]
    resources = tuple(
        circuit_resources(algorithm.construct_circuit(problem, k, measurement=True), k)
        for k in powers
    )
    total_shots = int(shots) * len(powers)
    queries = int(result.num_oracle_queries)
    return AmplitudeEstimationResult(
        estimate=float(result.estimation),
        confidence_interval=tuple(float(value) for value in result.confidence_interval),
        epsilon_target=float(epsilon_target),
        alpha=float(alpha),
        shots_per_circuit=int(shots),
        circuit_executions=len(powers),
        total_shots=total_shots,
        grover_queries=queries,
        # Each Q uses A and A^-1, plus one initial A per shot.
        state_preparation_calls=total_shots + 2 * queries,
        elapsed_seconds=elapsed,
        seed=seed,
        circuits=resources,
    )
