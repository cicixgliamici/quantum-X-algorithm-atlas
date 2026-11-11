"""Encode finite P and f tables coherently, without loading their expectation."""

from dataclasses import dataclass

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RYGate, StatePreparation, grover_operator
from qiskit_algorithms import EstimationProblem

from qaa.problems.discrete import DiscreteExpectation
from qaa.quantum.amplitude_estimation import AmplitudeEstimationResult, estimate_amplitude


@dataclass(frozen=True)
class DiscreteQuantumResult:
    """Original-unit estimate and interval alongside normalized IQAE diagnostics."""

    estimate: float
    confidence_interval: tuple[float, float]
    absolute_error_target: float
    amplitude_result: AmplitudeEstimationResult


def discrete_problem(problem: DiscreteExpectation) -> EstimationProblem:
    """Prepare individual table entries coherently without using their weighted mean."""
    index_qubits = max(1, (len(problem.probabilities) - 1).bit_length())
    amplitudes = np.zeros(2**index_qubits)
    amplitudes[: len(problem.probabilities)] = np.sqrt(problem.probabilities)
    preparation = QuantumCircuit(index_qubits + 1, name="A_discrete")
    preparation.append(StatePreparation(amplitudes), range(index_qubits))
    for index, value in enumerate(problem.normalized_values):
        if value == 0:
            continue
        # Each angle depends on one function entry, never on the weighted mean.
        rotation = RYGate(2 * np.arcsin(np.sqrt(value))).control(
            index_qubits, ctrl_state=index, annotated=False
        )
        preparation.append(rotation, [*range(index_qubits), index_qubits])
    oracle = QuantumCircuit(index_qubits + 1, name="success_reflection")
    oracle.z(index_qubits)
    return EstimationProblem(
        state_preparation=preparation,
        objective_qubits=[index_qubits],
        grover_operator=grover_operator(oracle, state_preparation=preparation),
    )


def estimate_discrete_expectation(
    problem: DiscreteExpectation,
    *,
    epsilon_target: float = 0.03,
    alpha: float = 0.05,
    shots: int = 256,
    seed: int | None = None,
) -> DiscreteQuantumResult:
    """epsilon_target is normalized; rescale the result and interval to f's units."""
    amplitude = estimate_amplitude(
        discrete_problem(problem),
        epsilon_target=epsilon_target,
        alpha=alpha,
        shots=shots,
        seed=seed,
    )
    lower, upper = problem.bounds
    width = upper - lower
    return DiscreteQuantumResult(
        estimate=lower + width * amplitude.estimate,
        confidence_interval=tuple(lower + width * v for v in amplitude.confidence_interval),
        absolute_error_target=width * amplitude.epsilon_target,
        amplitude_result=amplitude,
    )
