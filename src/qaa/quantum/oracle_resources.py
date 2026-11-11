"""Profile discrete oracle components and fixed-power circuits without sampling."""

from dataclasses import asdict, fields
from time import perf_counter

from qiskit import QuantumCircuit

from qaa._validation import positive_integer
from qaa.problems.discrete import DiscreteExpectation
from qaa.quantum.discrete_expectation import DiscreteCircuits, build_discrete_circuits
from qaa.quantum.resources import CircuitMetrics, measure_circuit


def probe_circuit(circuits: DiscreteCircuits, power: int) -> QuantumCircuit:
    """Build the actual measured A-then-Q^k circuit; no sampler is invoked."""
    positive_integer(power, "power", minimum=0)
    qubits = circuits.state_preparation.num_qubits
    circuit = QuantumCircuit(qubits, 1)
    circuit.compose(circuits.state_preparation, inplace=True)
    if power:
        circuit.compose(circuits.grover_operator.power(power), inplace=True)
    circuit.measure(qubits - 1, 0)
    return circuit


def modeled_workload(metrics: CircuitMetrics, power: int, shots: int) -> dict[str, int]:
    """Represent repeated circuit use; simulator compilation does not execute it."""
    return {
        "modeled_shots": shots,
        "grover_queries": shots * power,
        "forward_state_preparation_calls": shots * (power + 1),
        "inverse_state_preparation_calls": shots * power,
        "logical_gate_applications": shots * metrics.gate_count,
        "logical_single_qubit_gate_applications": shots * metrics.single_qubit_gate_count,
        "logical_two_qubit_gate_applications": shots * metrics.two_qubit_gate_count,
    }


def component_gate_model(components: dict[str, dict], power: int, shots: int) -> int:
    """Keep an additive component model distinct from whole-circuit synthesis."""
    forward = components["state_preparation"]["gate_count"]
    inverse = components["inverse_state_preparation"]["gate_count"]
    reflections = sum(
        components[name]["gate_count"] for name in ("success_reflection", "zero_reflection")
    )
    return shots * ((power + 1) * forward + power * (inverse + reflections))


def profile_discrete_oracle(
    problem: DiscreteExpectation, powers: tuple[int, ...], shots: int
) -> dict:
    """Separate host construction, component inspection and full probe inspection."""
    positive_integer(shots, "shots")
    if not powers:
        raise ValueError("powers must not be empty")
    for power in powers:
        positive_integer(power, "power", minimum=0)
    started = perf_counter()
    circuits = build_discrete_circuits(problem)
    construction_seconds = perf_counter() - started
    inspection_started = perf_counter()
    components = {
        field.name: asdict(measure_circuit(getattr(circuits, field.name)))
        for field in fields(circuits)
    }
    component_inspection_seconds = perf_counter() - inspection_started
    probe_started = perf_counter()
    probes = []
    for power in powers:
        metrics = measure_circuit(probe_circuit(circuits, power))
        probes.append(
            {
                "grover_power": power,
                "circuit": asdict(metrics),
                "modeled_workload": modeled_workload(metrics, power, shots),
                "component_gate_application_model": component_gate_model(components, power, shots),
            }
        )
    return {
        "components": components,
        "probes": probes,
        "timing": {
            "component_construction_seconds": construction_seconds,
            "component_inspection_seconds": component_inspection_seconds,
            "probe_construction_and_inspection_seconds": perf_counter() - probe_started,
            "total_profile_seconds": perf_counter() - started,
        },
        "sampler_executions": 0,
    }
