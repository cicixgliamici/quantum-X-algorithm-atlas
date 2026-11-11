"""Encode finite P and f tables coherently, without loading their expectation."""

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import RYGate, StatePreparation, grover_operator
from qiskit_algorithms import EstimationProblem

from qaa._validation import positive_integer
from qaa.problems.discrete import DiscreteExpectation
from qaa.quantum.amplitude_estimation import AmplitudeEstimationResult, estimate_amplitude


@dataclass(frozen=True)
class DiscreteQuantumResult:
    """Original-unit estimate and interval alongside normalized IQAE diagnostics."""

    estimate: float
    confidence_interval: tuple[float, float]
    absolute_error_target: float
    amplitude_result: AmplitudeEstimationResult
    problem_construction_seconds: float
    total_elapsed_seconds: float


@dataclass(frozen=True)
class DiscreteCircuits:
    """Inspectable components of the same A and Q supplied to IQAE."""

    distribution_loading: QuantumCircuit
    function_encoding: QuantumCircuit
    state_preparation: QuantumCircuit
    inverse_state_preparation: QuantumCircuit
    success_reflection: QuantumCircuit
    zero_reflection: QuantumCircuit
    grover_operator: QuantumCircuit


def distribution_circuit(problem: DiscreteExpectation) -> QuantumCircuit:
    """Load sqrt(p_i) on an index register, padding unused indices with zeros."""
    index_qubits = max(1, (len(problem.probabilities) - 1).bit_length())
    amplitudes = np.zeros(2**index_qubits)
    amplitudes[: len(problem.probabilities)] = np.sqrt(problem.probabilities)
    circuit = QuantumCircuit(index_qubits, name="P")
    circuit.append(StatePreparation(amplitudes), range(index_qubits))
    return circuit


def function_circuit(problem: DiscreteExpectation, index_qubits: int) -> QuantumCircuit:
    """Encode each normalized function entry with an index-controlled rotation."""
    circuit = QuantumCircuit(index_qubits + 1, name="F")
    for index, value in enumerate(problem.normalized_values):
        if value == 0:
            continue
        # Angles use individual entries; concrete gates support direct simulation.
        rotation = RYGate(2 * np.arcsin(np.sqrt(value))).control(
            index_qubits, ctrl_state=index, annotated=False
        )
        circuit.append(rotation, [*range(index_qubits), index_qubits])
    return circuit


def zero_state_reflection(qubits: int) -> QuantumCircuit:
    """Implement I-2|0><0| using the same construction as Qiskit's Grover default."""
    positive_integer(qubits, "qubits")
    circuit = QuantumCircuit(qubits, name="zero_reflection")
    circuit.x(range(qubits))
    if qubits == 1:
        circuit.z(0)
    else:
        circuit.h(qubits - 1)
        circuit.mcx(list(range(qubits - 1)), qubits - 1)
        circuit.h(qubits - 1)
    circuit.x(range(qubits))
    return circuit


def build_discrete_circuits(problem: DiscreteExpectation) -> DiscreteCircuits:
    """Compose explicit P, F, reflections and Q without reading the exact answer."""
    distribution = distribution_circuit(problem)
    function = function_circuit(problem, distribution.num_qubits)
    preparation = QuantumCircuit(function.num_qubits, name="A_discrete")
    preparation.compose(distribution, range(distribution.num_qubits), inplace=True)
    preparation.compose(function, inplace=True)
    oracle = QuantumCircuit(preparation.num_qubits, name="success_reflection")
    oracle.z(preparation.num_qubits - 1)
    reflection = zero_state_reflection(preparation.num_qubits)
    return DiscreteCircuits(
        distribution_loading=distribution,
        function_encoding=function,
        state_preparation=preparation,
        inverse_state_preparation=preparation.inverse(),
        success_reflection=oracle,
        zero_reflection=reflection,
        grover_operator=grover_operator(
            oracle, state_preparation=preparation, zero_reflection=reflection
        ),
    )


def discrete_problem(problem: DiscreteExpectation) -> EstimationProblem:
    """Prepare sum_i sqrt(p_i)|i>(sqrt(1-g_i)|0>+sqrt(g_i)|1>).

    The index uses Qiskit's little-endian ordering. Zero-probability padding
    allows table sizes that are not powers of two. StatePreparation is unitary,
    unlike reset-based initialization, so IQAE can use A inverse.
    """
    circuits = build_discrete_circuits(problem)
    return EstimationProblem(
        state_preparation=circuits.state_preparation,
        objective_qubits=[circuits.state_preparation.num_qubits - 1],
        grover_operator=circuits.grover_operator,
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
    started = perf_counter()
    estimation_problem = discrete_problem(problem)
    construction_seconds = perf_counter() - started
    amplitude = estimate_amplitude(
        estimation_problem,
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
        problem_construction_seconds=construction_seconds,
        total_elapsed_seconds=perf_counter() - started,
    )
