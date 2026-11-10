"""Check the exported scientific record, including CLI serialization."""

import builtins
import json
import subprocess
import sys

import pytest

from qaa.benchmarks.monte_carlo import run_benchmark


def test_classical_report():
    report = run_benchmark((20, 200), quantum=False)
    assert report["schema_version"] == 1
    assert [r["sample_count"] for r in report["classical"]] == [20, 200]
    for result in report["classical"]:
        assert result["absolute_error"] == abs(result["estimate"] - 0.3)
    assert report["quantum"]["status"] == "disabled"
    json.dumps(report, allow_nan=False)


def test_quantum_report():
    pytest.importorskip("qiskit_algorithms")
    report = run_benchmark((20,))
    assert report["quantum"]["status"] == "completed"
    assert report["quantum"]["circuits"]
    json.dumps(report, allow_nan=False)


def test_cli(tmp_path):
    output = tmp_path / "nested" / "report.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "qaa.benchmarks.monte_carlo",
            "--classical-only",
            "--output",
            str(output),
        ],
        check=True,
    )
    assert json.loads(output.read_text())["quantum"]["status"] == "disabled"


def test_empty_sample_sizes():
    with pytest.raises(ValueError):
        run_benchmark((), quantum=False)


def test_missing_quantum_extra(monkeypatch):
    original_import = builtins.__import__

    def without_quantum(name, *args, **kwargs):
        if name == "qaa.quantum.amplitude_estimation":
            raise ModuleNotFoundError("No module named 'qiskit'", name="qiskit")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_quantum)
    report = run_benchmark((20,))
    assert report["quantum"]["status"] == "unavailable"
    assert report["classical"][0]["sample_count"] == 20
