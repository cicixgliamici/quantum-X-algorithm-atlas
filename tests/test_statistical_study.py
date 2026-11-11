"""Real small studies, source integrity, reanalysis and retained estimator failures."""

import json

import pytest

from qaa.benchmarks import statistical_study
from qaa.benchmarks.statistical_study import analyze_study, execute_trial, run_study
from qaa.benchmarks.study_design import StudyDesign, trial_plan


def small_design(quantum=False):
    return StudyDesign(
        probabilities=(0.3,), epsilons=(0.1,), replications=2, endpoints=True, quantum=quantum
    )


def test_real_classical_study_and_reanalysis(tmp_path, monkeypatch):
    directory = tmp_path / "study"
    summary = run_study(directory, small_design())
    assert summary["classification"] == "pilot"
    assert summary["completed_trials"] == 6
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["execution_state"] == "completed"
    assert (directory / "source" / "docs" / "comparison_protocol.md").is_file()

    def forbidden(*args):
        raise AssertionError("Reanalysis must not run estimators")

    monkeypatch.setattr(statistical_study, "classical_estimate", forbidden)
    # JSON represents Wilson interval tuples as arrays; compare the exported form.
    assert json.loads(json.dumps(analyze_study(directory))) == json.loads(
        (directory / "summary.json").read_text()
    )
    with pytest.raises(FileExistsError):
        run_study(directory, small_design())


def test_real_quantum_pilot(tmp_path):
    pytest.importorskip("qiskit_algorithms")
    summary = run_study(tmp_path / "quantum", small_design(quantum=True))
    assert summary["completed_trials"] == summary["planned_trials"] == 12
    for cell in summary["cells"]:
        assert cell["accuracy_conditional_on_completion"]["success"]["denominator"] == 2
        if cell["method"] == "quantum":
            assert "grover_queries" in cell["costs_conditional_on_completion"]


def test_failed_runs_written_once_without_retries(tmp_path, monkeypatch):
    attempted = []

    def failed(trial, design):
        attempted.append(trial["seed"])
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(statistical_study, "quantum_estimate", failed)
    directory = tmp_path / "failed"
    summary = run_study(directory, small_design(quantum=True))
    assert len(attempted) == len(set(attempted)) == 6
    assert summary["recorded_trials"] == summary["planned_trials"] == 12
    assert summary["completed_trials"] == 6
    records = [json.loads(line) for line in (directory / "trials.jsonl").read_text().splitlines()]
    assert sum(r["status"] == "failed" for r in records) == 6
    assert (
        json.loads((directory / "manifest.json").read_text())["execution_state"]
        == "completed_with_failures"
    )


def test_failed_and_unavailable_trials_retained(monkeypatch):
    design = small_design(quantum=True)
    trial = next(r for r in trial_plan(design) if r["method"] == "quantum")

    def missing(*args):
        raise ModuleNotFoundError("No module named 'qiskit'", name="qiskit")

    monkeypatch.setattr(statistical_study, "quantum_estimate", missing)
    assert execute_trial(trial, design)["status"] == "unavailable"

    def failed(*args):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(statistical_study, "quantum_estimate", failed)
    result = execute_trial(trial, design)
    assert result["status"] == "failed"
    assert result["error"]["type"] == "TimeoutError"
    assert result["seed"] == trial["seed"]


def test_invalid_numerical_output_is_failed(monkeypatch):
    design = small_design()
    trial = next(trial_plan(design))
    monkeypatch.setattr(
        statistical_study,
        "classical_estimate",
        lambda *args: {
            "estimate": float("nan"),
            "confidence_interval": [0, 1],
            "costs": {},
        },
    )
    assert execute_trial(trial, design)["status"] == "failed"


def test_raw_and_source_tampering_detected(tmp_path):
    directory = tmp_path / "study"
    run_study(directory, small_design())
    raw = directory / "trials.jsonl"
    original = raw.read_bytes()
    raw.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        analyze_study(directory)
    raw.write_bytes(original)
    (directory / "source" / "README.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="archived source changed"):
        analyze_study(directory)


def test_interruption_preserves_missing_denominators(tmp_path, monkeypatch):
    directory = tmp_path / "interrupted"
    original = statistical_study.execute_trial
    attempted = 0

    def interrupt_after_one(trial, design):
        nonlocal attempted
        attempted += 1
        if attempted == 2:
            raise KeyboardInterrupt
        return original(trial, design)

    monkeypatch.setattr(statistical_study, "execute_trial", interrupt_after_one)
    with pytest.raises(KeyboardInterrupt):
        run_study(directory, small_design())
    summary = analyze_study(directory)
    assert summary["completed_trials"] == 1
    assert summary["planned_trials"] == 6
    assert sum(c["status_counts"]["not_recorded"] for c in summary["cells"]) == 5
