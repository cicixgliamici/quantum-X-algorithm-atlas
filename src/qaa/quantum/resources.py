"""Logical circuit accounting under one explicit, reproducible compiler convention."""

from dataclasses import dataclass

from qiskit import QuantumCircuit, transpile


@dataclass(frozen=True)
class CircuitMetrics:
    """u/cx logical resources; depth includes measurements, gates exclude directives."""

    qubits: int
    depth: int
    gate_count: int
    single_qubit_gate_count: int
    two_qubit_gate_count: int
    measurement_count: int
    operations: dict[str, int]


def measure_circuit(circuit: QuantumCircuit) -> CircuitMetrics:
    """Decompose without backend routing or optimization; never count blocks as gates."""
    expanded = transpile(circuit, basis_gates=["u", "cx"], optimization_level=0, seed_transpiler=0)
    operations = {name: int(count) for name, count in expanded.count_ops().items()}
    unexpected = set(operations) - {"u", "cx", "measure", "barrier"}
    if unexpected:
        raise ValueError(f"Circuit contains unsupported non-unitary operations: {unexpected}")
    single_qubit = operations.get("u", 0)
    two_qubit = operations.get("cx", 0)
    return CircuitMetrics(
        qubits=expanded.num_qubits,
        depth=expanded.depth(),
        gate_count=single_qubit + two_qubit,
        single_qubit_gate_count=single_qubit,
        two_qubit_gate_count=two_qubit,
        measurement_count=operations.get("measure", 0),
        operations=operations,
    )
