"""Validate real QAE execution, calibration accuracy and resource accounting."""

from dataclasses import asdict

import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_algorithms")

from qiskit.quantum_info import Statevector  # noqa: E402

from qaa.quantum.amplitude_estimation import (  # noqa: E402
    bernoulli_problem,
    estimate_bernoulli_amplitude,
)


@pytest.mark.parametrize("p", [0.0, 0.3, 0.8, 1.0])
def test_state_preparation(p):
    problem = bernoulli_problem(p)
    assert problem.state_preparation.num_qubits == 1
    assert Statevector(problem.state_preparation).probabilities()[1] == pytest.approx(p)
    assert problem.objective_qubits == [0]


@pytest.mark.parametrize("p", [0.0, 0.3, 0.8, 1.0])
def test_qae_accuracy_and_resources(p):
    result = estimate_bernoulli_amplitude(p, seed=42)
    assert abs(result.estimate - p) <= result.epsilon_target
    assert result.confidence_interval[0] <= p <= result.confidence_interval[1]
    assert result.total_shots == result.shots_per_circuit * result.circuit_executions
    assert result.grover_queries == sum(
        resource.grover_power * result.shots_per_circuit for resource in result.circuits
    )
    assert result.state_preparation_calls == result.total_shots + 2 * result.grover_queries
    assert all(c.qubits == 1 and c.depth > 0 and c.gate_count > 0 for c in result.circuits)
    assert all(c.measurement_count == 1 for c in result.circuits)
    assert result.circuits[0].grover_power == 0
    assert result.circuits[0].gate_count == 1  # Only Ry; the barrier is not a gate.
    if 0 < p < 1:
        assert result.grover_queries > 0


def test_reproducibility():
    first = asdict(estimate_bernoulli_amplitude(0.3, seed=17))
    second = asdict(estimate_bernoulli_amplitude(0.3, seed=17))
    first.pop("elapsed_seconds")
    second.pop("elapsed_seconds")
    assert first == second


@pytest.mark.parametrize(
    "kwargs",
    [
        {"shots": 0},
        {"shots": True},
        {"shots": 3.5},
        {"seed": -1},
        {"epsilon_target": 0},
        {"epsilon_target": 0.6},
        {"epsilon_target": float("nan")},
        {"alpha": 0},
        {"alpha": 1},
        {"alpha": float("inf")},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        estimate_bernoulli_amplitude(0.3, **kwargs)


@pytest.mark.parametrize("p", [-1, 2, float("nan")])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        bernoulli_problem(p)
