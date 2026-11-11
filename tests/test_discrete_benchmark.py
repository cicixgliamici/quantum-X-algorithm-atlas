"""Test the matched single-run contract and structured export."""

import builtins
import json
import subprocess
import sys

import pytest

from qaa.benchmarks.discrete_expectation import hoeffding_sample_count, run_discrete_benchmark
from qaa.problems.discrete import synthetic_call_payoff


def test_classical_report():
    report = run_discrete_benchmark(synthetic_call_payoff(), epsilon=0.025, quantum=False)
    assert report["classical"]["sample_count"] == 2952
    assert report["absolute_error_target"] == 0.75
    assert report["exact_expectation"] == 13
    assert report["classical"]["confidence_interval"][0] <= 13
    assert report["classical"]["confidence_interval"][1] >= 13
    assert report["quantum"]["status"] == "disabled"
    assert report["method_seeds"]["classical"] != report["method_seeds"]["quantum"]
    json.dumps(report, allow_nan=False)


def test_quantum_report():
    pytest.importorskip("qiskit_algorithms")
    report = run_discrete_benchmark(synthetic_call_payoff())
    assert report["quantum"]["status"] == "completed"
    assert report["quantum"]["absolute_error_target"] == report["absolute_error_target"]
    assert report["quantum"]["amplitude_result"]["alpha"] == report["alpha"]
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("epsilon, alpha", [(0, 0.05), (0.6, 0.05), (0.1, 0), (0.1, 1)])
def test_invalid_accuracy(epsilon, alpha):
    with pytest.raises(ValueError):
        hoeffding_sample_count(epsilon, alpha)


def test_missing_quantum_extra(monkeypatch):
    original_import = builtins.__import__

    def without_quantum(name, *args, **kwargs):
        if name == "qaa.quantum.discrete_expectation":
            raise ModuleNotFoundError("No module named 'qiskit'", name="qiskit")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_quantum)
    assert run_discrete_benchmark(synthetic_call_payoff())["quantum"]["status"] == "unavailable"


def test_cli(tmp_path):
    path = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "qaa.benchmarks.discrete_expectation",
            "--classical-only",
            "--output",
            str(path),
        ],
        check=True,
    )
    assert json.loads(path.read_text())["exact_expectation"] == 13
