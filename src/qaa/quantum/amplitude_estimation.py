"""Reusable iterative QAE execution and a known Bernoulli calibration circuit."""

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import grover_operator
from qiskit.primitives import StatevectorSampler
from qiskit_algorithms import EstimationProblem, IterativeAmplitudeEstimation

from qaa._validation import positive_integer, probability, validate_seed
from qaa.quantum.resources import CircuitMetrics, measure_circuit


@dataclass(frozen=True)
class CircuitResources(CircuitMetrics):
    """Logical resources after decomposition to u/cx, including measurements.

    These are circuit descriptions, not backend-transpiled hardware costs.
    """

    grover_power: int


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
    forward_state_preparation_calls: int
    inverse_state_preparation_calls: int
    logical_gate_applications: int
    logical_single_qubit_gate_applications: int
    logical_two_qubit_gate_applications: int
    max_circuit_depth: int
    elapsed_seconds: float
    resource_inspection_seconds: float
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
    return CircuitResources(grover_power=int(power), **asdict(measure_circuit(circuit)))


def estimate_bernoulli_amplitude(
    target_probability: float,
    *,
    epsilon_target: float = 0.03,
    alpha: float = 0.05,
    shots: int = 256,
    seed: int | None = None,
) -> AmplitudeEstimationResult:
    """Estimate a known Bernoulli calibration amplitude using the shared runner."""
    return estimate_amplitude(
        bernoulli_problem(target_probability),
        epsilon_target=epsilon_target,
        alpha=alpha,
        shots=shots,
        seed=seed,
    )


def estimate_amplitude(
    problem: EstimationProblem,
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
    # A persistent stream avoids resetting identical measurement draws each round.
    sampler = StatevectorSampler(default_shots=int(shots), seed=np.random.default_rng(seed))
    # Explicit settings make the replicated protocol independent of changing defaults.
    algorithm = IterativeAmplitudeEstimation(
        epsilon_target, alpha, confint_method="beta", min_ratio=2, sampler=sampler
    )
    started = perf_counter()
    result = algorithm.estimate(problem)
    elapsed = perf_counter() - started
    # Qiskit's powers begins with a sentinel zero, before any circuit is run.
    powers = result.powers[1:]
    inspection_started = perf_counter()
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
        forward_state_preparation_calls=total_shots + queries,
        inverse_state_preparation_calls=queries,
        logical_gate_applications=int(shots) * sum(c.gate_count for c in resources),
        logical_single_qubit_gate_applications=(
            int(shots) * sum(c.single_qubit_gate_count for c in resources)
        ),
        logical_two_qubit_gate_applications=(
            int(shots) * sum(c.two_qubit_gate_count for c in resources)
        ),
        max_circuit_depth=max(c.depth for c in resources),
        elapsed_seconds=elapsed,
        resource_inspection_seconds=perf_counter() - inspection_started,
        seed=seed,
        circuits=resources,
    )
