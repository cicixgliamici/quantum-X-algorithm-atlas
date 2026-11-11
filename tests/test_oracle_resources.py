"""Independent gate-count identities and physical meaning of the probe circuits."""

import numpy as np
import pytest

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_algorithms")

from qiskit import QuantumCircuit  # noqa: E402
from qiskit.circuit.library import grover_operator  # noqa: E402
from qiskit.quantum_info import Operator, Statevector  # noqa: E402

from qaa.problems.discrete import DiscreteExpectation  # noqa: E402
from qaa.quantum.discrete_expectation import (  # noqa: E402
    build_discrete_circuits,
    zero_state_reflection,
)
from qaa.quantum.oracle_resources import probe_circuit, profile_discrete_oracle  # noqa: E402
from qaa.quantum.resources import measure_circuit  # noqa: E402


def test_known_basis_counts_and_barriers():
    circuit = QuantumCircuit(2, 1)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.barrier()
    circuit.measure(1, 0)
    metrics = measure_circuit(circuit)
    assert metrics.qubits == 2
    assert metrics.gate_count == 2
    assert metrics.single_qubit_gate_count == metrics.two_qubit_gate_count == 1
    assert metrics.measurement_count == 1
    assert metrics.depth == 3
    assert metrics.operations == {"u": 1, "cx": 1, "barrier": 1, "measure": 1}


@pytest.mark.parametrize("qubits", [1, 2, 3])
def test_zero_reflection_operator(qubits):
    expected = np.ones(2**qubits)
    expected[0] = -1
    assert Operator(zero_state_reflection(qubits)).data == pytest.approx(np.diag(expected))


def test_components_and_amplification():
    problem = DiscreteExpectation((0.2, 0.3, 0.5), (0.1, 0.4, 0.8), (0, 1))
    circuits = build_discrete_circuits(problem)
    reference_q = grover_operator(
        circuits.success_reflection, state_preparation=circuits.state_preparation
    )
    assert Operator(circuits.grover_operator).equiv(Operator(reference_q))
    identity = circuits.state_preparation.compose(circuits.inverse_state_preparation)
    assert Operator(identity).equiv(Operator(np.eye(8)))
    theta = np.arcsin(np.sqrt(problem.exact_expectation))
    for power in (0, 1, 2):
        circuit = probe_circuit(circuits, power).remove_final_measurements(inplace=False)
        success = Statevector(circuit).probabilities([2])[1]
        assert success == pytest.approx(np.sin((2 * power + 1) * theta) ** 2)


def test_profile_workload_and_padding():
    problem = DiscreteExpectation((0.2, 0.3, 0.5), (0.1, 0.4, 0.8), (0, 1))
    profile = profile_discrete_oracle(problem, (0, 2), shots=11)
    components = profile["components"]
    assert components["distribution_loading"]["qubits"] == 2
    assert components["state_preparation"]["qubits"] == 3
    assert profile["sampler_executions"] == 0
    for probe in profile["probes"]:
        workload, metrics, power = (
            probe["modeled_workload"],
            probe["circuit"],
            probe["grover_power"],
        )
        assert (
            metrics["gate_count"]
            == metrics["single_qubit_gate_count"] + metrics["two_qubit_gate_count"]
        )
        assert workload["grover_queries"] == 11 * power
        assert workload["forward_state_preparation_calls"] == 11 * (power + 1)
        assert workload["inverse_state_preparation_calls"] == 11 * power
        assert workload["logical_gate_applications"] == 11 * metrics["gate_count"]
        assert metrics["measurement_count"] == 1
    assert all(seconds >= 0 for seconds in profile["timing"].values())


@pytest.mark.parametrize("powers, shots", [((-1,), 10), ((True,), 10), ((), 10), ((0,), 0)])
def test_invalid_profile_workload(powers, shots):
    with pytest.raises(ValueError):
        profile_discrete_oracle(DiscreteExpectation((1,), (0.3,), (0, 1)), powers, shots)
