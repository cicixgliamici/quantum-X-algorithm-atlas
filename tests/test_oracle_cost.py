"""Study design, optional dependencies, reproducibility and JSON export."""

import json
import subprocess
import sys

import pytest

from qaa.benchmarks import oracle_cost
from qaa.benchmarks.oracle_cost import run_oracle_cost_study, synthetic_table


def deterministic_fields(value):
    """Compare all scientific fields while excluding host clock measurements."""
    if isinstance(value, dict):
        return {k: deterministic_fields(v) for k, v in value.items() if not k.endswith("_seconds")}
    if isinstance(value, list):
        return [deterministic_fields(v) for v in value]
    return value


def test_dense_input_family():
    first = synthetic_table(3, 42)
    assert first == synthetic_table(3, 42)
    assert first != synthetic_table(3, 43)
    assert sum(first.probabilities) == pytest.approx(1)
    assert all(0.05 < value < 0.95 for value in first.function_values)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sizes": ()},
        {"sizes": (0,)},
        {"sizes": (2, 2)},
        {"sizes": (True,)},
        {"powers": ()},
        {"powers": (-1,)},
        {"powers": (1, 1)},
        {"shots": 0},
        {"seed": -1},
        {"epsilon": 0},
        {"alpha": 1},
    ],
)
def test_invalid_design(kwargs):
    with pytest.raises(ValueError):
        run_oracle_cost_study(**kwargs)


def test_missing_dependency(monkeypatch):
    def missing_module(name):
        raise ModuleNotFoundError("No module named 'qiskit'", name="qiskit")

    monkeypatch.setattr(oracle_cost, "import_module", missing_module)
    report = run_oracle_cost_study((2,))
    assert report["status"] == "unavailable"
    assert report["rows"] == []


def test_runtime_failures_propagate(monkeypatch):
    def broken_module(name):
        raise RuntimeError("Unexpected compiler failure")

    monkeypatch.setattr(oracle_cost, "import_module", broken_module)
    with pytest.raises(RuntimeError, match="compiler failure"):
        run_oracle_cost_study((2,))


def test_study_reproducibility_and_estimation():
    pytest.importorskip("qiskit_algorithms")
    first = run_oracle_cost_study((2, 3), powers=(0, 1), with_estimation=True)
    second = run_oracle_cost_study((3, 2), powers=(0, 1), with_estimation=True)
    assert first["status"] == "completed"
    assert deterministic_fields(first["rows"]) == deterministic_fields(second["rows"][::-1])
    for row in first["rows"]:
        assert row["iqae"]["status"] == "completed"
        amplitude = row["iqae"]["amplitude_result"]
        assert amplitude["logical_two_qubit_gate_applications"] > 0
        assert amplitude["forward_state_preparation_calls"] == (
            amplitude["total_shots"] + amplitude["grover_queries"]
        )
        assert row["iqae"]["total_elapsed_seconds"] >= (
            row["iqae"]["problem_construction_seconds"]
            + amplitude["elapsed_seconds"]
            + amplitude["resource_inspection_seconds"]
        )
    json.dumps(first, allow_nan=False)


def test_structural_only_cli(tmp_path):
    pytest.importorskip("qiskit_algorithms")
    path = tmp_path / "cost.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "qaa.benchmarks.oracle_cost",
            "--sizes",
            "2",
            "--powers",
            "0",
            "--output",
            str(path),
        ],
        check=True,
    )
    report = json.loads(path.read_text())
    assert report["rows"][0]["iqae"]["status"] == "disabled"
    assert report["rows"][0]["oracle"]["sampler_executions"] == 0
