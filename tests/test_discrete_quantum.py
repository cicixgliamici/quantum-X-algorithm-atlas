"""Check the full joint encoding, inverse and original-unit IQAE result."""

from dataclasses import asdict

import numpy as np
import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_algorithms")

from qiskit.quantum_info import Statevector  # noqa: E402

from qaa.problems.discrete import DiscreteExpectation, synthetic_call_payoff  # noqa: E402
from qaa.quantum.discrete_expectation import (  # noqa: E402
    discrete_problem,
    estimate_discrete_expectation,
)


@pytest.mark.parametrize(
    "problem",
    [
        synthetic_call_payoff(),
        DiscreteExpectation((0.2, 0.3, 0.5), (-2, 0, 6), (-2, 6)),
        DiscreteExpectation((0, 0, 1), (1, 0, 0.4), (0, 1)),
        DiscreteExpectation((1,), (0.7,), (0, 1)),
    ],
)
def test_joint_distribution_and_unitary_inverse(problem):
    circuit = discrete_problem(problem).state_preparation
    index_size = 2 ** (circuit.num_qubits - 1)
    state = Statevector(circuit)
    # The objective is the highest qubit: the two contiguous blocks are 0 and 1.
    expected = np.zeros(2 * index_size)
    for i, (p, value) in enumerate(
        zip(problem.probabilities, problem.normalized_values, strict=True)
    ):
        expected[i] = p * (1 - value)
        expected[index_size + i] = p * value
    assert state.probabilities() == pytest.approx(expected, abs=1e-12)
    assert state.probabilities([circuit.num_qubits - 1])[1] == pytest.approx(
        np.dot(problem.probabilities, problem.normalized_values)
    )
    restored = state.evolve(circuit.inverse()).probabilities()
    assert restored[0] == pytest.approx(1)
    assert np.sum(restored[1:]) < 1e-12


@pytest.mark.parametrize(
    "problem",
    [
        synthetic_call_payoff(),
        DiscreteExpectation((0.2, 0.3, 0.5), (-2, 0, 6), (-2, 6)),
        DiscreteExpectation((1,), (0,), (0, 1)),
        DiscreteExpectation((1,), (1,), (0, 1)),
        DiscreteExpectation((0.2, 0.8), (5, 5), (0, 10)),
    ],
)
def test_iqae_original_units_and_reproducibility(problem):
    result = estimate_discrete_expectation(problem, epsilon_target=0.04, seed=42)
    assert abs(result.estimate - problem.exact_expectation) <= result.absolute_error_target
    assert (
        result.confidence_interval[0] <= problem.exact_expectation <= result.confidence_interval[1]
    )
    lower, upper = problem.bounds
    amplitude = result.amplitude_result
    assert result.estimate == pytest.approx(lower + (upper - lower) * amplitude.estimate)
    assert result.absolute_error_target == pytest.approx((upper - lower) * 0.04)
    qubits = max(1, (len(problem.probabilities) - 1).bit_length()) + 1
    assert all(c.qubits == qubits for c in amplitude.circuits)
    assert amplitude.grover_queries == sum(c.grover_power * 256 for c in amplitude.circuits)
    repeated = asdict(estimate_discrete_expectation(problem, epsilon_target=0.04, seed=42))
    original = asdict(result)
    repeated["amplitude_result"].pop("elapsed_seconds")
    original["amplitude_result"].pop("elapsed_seconds")
    assert original == repeated


def test_builder_does_not_read_exact_expectation(monkeypatch):
    def forbidden_reference(self):
        raise AssertionError("The exact answer must not be read by the estimator")

    monkeypatch.setattr(DiscreteExpectation, "exact_expectation", property(forbidden_reference))
    result = estimate_discrete_expectation(synthetic_call_payoff(), seed=42)
    assert abs(result.estimate - 13) <= result.absolute_error_target
