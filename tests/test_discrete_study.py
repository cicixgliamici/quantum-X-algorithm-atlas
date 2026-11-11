"""Check payoff units, frozen designs, independent seeds and real IQAE replications."""

import hashlib
import json
import math
from dataclasses import replace

import pytest

from qaa.benchmarks import statistical_study
from qaa.benchmarks.discrete_study_design import DiscreteStudyDesign, study_problem
from qaa.benchmarks.statistical_study import execute_trial, read_study, run_study
from qaa.benchmarks.study_design import trial_plan
from qaa.benchmarks.study_statistics import summarize_records


def small_design(**changes):
    """Run the whole payoff/control catalog with a small explicit pilot budget."""
    return replace(DiscreteStudyDesign(epsilons=(0.1,), replications=2, quantum=False), **changes)


def test_registered_design_and_independent_streams():
    design = DiscreteStudyDesign()
    plan = list(trial_plan(design))
    assert design.classification == "primary"
    assert len(design.cells) == 11
    assert len(plan) == len({trial["seed"] for trial in plan}) == 4400
    assert [cell["kind"] for cell in design.cells[-2:]] == ["endpoint", "endpoint"]
    classical = replace(design, quantum=False)
    assert [r["seed"] for r in trial_plan(classical)] == [
        r["seed"] for r in plan if r["method"] == "classical"
    ]
    assert classical.classification == "pilot"
    assert study_problem("call").exact_expectation == 13
    assert study_problem("rare").exact_expectation == pytest.approx(1.2)
    assert study_problem("signed").exact_expectation == pytest.approx(-1.2)


@pytest.mark.parametrize(
    "changes",
    [
        {"payoffs": ()},
        {"payoffs": ("call", "call")},
        {"payoffs": ("unknown",)},
        {"payoffs": ["call"]},
        {"epsilons": (0,)},
        {"replications": 0},
        {"seed": None},
        {"alpha": 1},
        {"endpoints": 1},
    ],
)
def test_invalid_design(changes):
    with pytest.raises(ValueError):
        replace(DiscreteStudyDesign(), **changes)


def test_original_unit_tolerance_and_coverage(monkeypatch):
    design = small_design(payoffs=("call",), epsilons=(0.05,), endpoints=False)
    trial = next(trial_plan(design))
    monkeypatch.setattr(
        statistical_study,
        "discrete_classical_estimate",
        lambda *args: {
            "estimate": 13.2,
            "confidence_interval": (12.9, 13.4),
            "costs": {},
            "timings": {},
        },
    )
    record = execute_trial(trial, design)
    assert record["status"] == "completed"
    # Error 0.2 exceeds normalized epsilon 0.05 but meets the actual target 1.5.
    assert record["absolute_error"] > trial["epsilon"]
    assert record["absolute_error_target"] == 1.5
    assert record["within_tolerance"] and record["interval_contains_truth"]
    accuracy = summarize_records(design, [record])["cells"][0]["accuracy_conditional_on_completion"]
    assert accuracy["rmse"] == pytest.approx(0.2)
    assert accuracy["coverage"]["rate"] == 1
    with pytest.raises(ValueError, match="inconsistent"):
        summarize_records(design, [{**record, "within_tolerance": False}])
    with pytest.raises(ValueError, match="seed/design"):
        summarize_records(design, [{**record, "exact_expectation": 0.4333333333}])


def test_classical_archive_reanalysis_and_controls(tmp_path, monkeypatch):
    directory = tmp_path / "study"
    summary = run_study(directory, small_design())
    assert summary["completed_trials"] == summary["planned_trials"] == 10
    for cell in summary["cells"][-2:]:
        accuracy = cell["accuracy_conditional_on_completion"]
        assert accuracy["rmse"] == 0
        assert accuracy["coverage"]["rate"] == 1
    raw = (directory / "trials.jsonl").read_bytes()
    assert all(
        r["estimate"] < 0
        for r in map(json.loads, raw.splitlines())
        if r["problem_id"] == "constant_lower"
    )

    def forbidden(*args):
        raise AssertionError("Reanalysis must not invoke estimators")

    monkeypatch.setattr(statistical_study, "discrete_classical_estimate", forbidden)
    manifest, recomputed = read_study(directory)
    assert json.loads(json.dumps(recomputed)) == json.loads(json.dumps(summary))
    assert manifest["protocol_id"] == "discrete-iqae-v1"
    assert manifest["problems"]["call"]["function_values"] == [0, 0, 10, 30]
    assert (directory / "trials.jsonl").read_bytes() == raw
    manifest["problems"]["call"]["function_values"][2] = 9
    (directory / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="tables or cells"):
        read_study(directory)


def test_real_discrete_iqae_and_rescaled_diagnostics(tmp_path):
    pytest.importorskip("qiskit_algorithms")
    directory = tmp_path / "quantum"
    summary = run_study(directory, small_design(quantum=True))
    assert summary["completed_trials"] == summary["planned_trials"] == 20
    records = map(json.loads, (directory / "trials.jsonl").read_text().splitlines())
    for record in records:
        if record["method"] != "quantum":
            continue
        lower, upper = record["bounds"]
        amplitude = record["estimator_result"]["amplitude_result"]
        assert record["estimate"] == pytest.approx(lower + (upper - lower) * amplitude["estimate"])
        assert record["confidence_interval"] == pytest.approx(
            [lower + (upper - lower) * v for v in amplitude["confidence_interval"]]
        )
        assert record["costs"]["state_preparation_calls"] >= record["costs"]["total_shots"]


def test_failed_discrete_trials_remain_visible(tmp_path, monkeypatch):
    def failed(*args):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(statistical_study, "discrete_quantum_estimate", failed)
    summary = run_study(tmp_path / "failed", small_design(quantum=True))
    assert summary["completed_trials"] == 10
    assert summary["planned_trials"] == 20
    assert all(
        c["status_counts"].get("failed") == 2 for c in summary["cells"] if c["method"] == "quantum"
    )


def test_discrete_report_units_plot_reference_and_read_only(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    from qaa.benchmarks.report_figures import plt, rmse_figure
    from qaa.benchmarks.scientific_report import generate_report

    directory, output = tmp_path / "study", tmp_path / "report"
    run_study(directory, small_design())
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob("*") if p.is_file()
    }

    def forbidden(*args):
        raise AssertionError("Reports must not estimate")

    monkeypatch.setattr(statistical_study, "discrete_classical_estimate", forbidden)
    report = generate_report(directory, output)
    assert report["report_id"] == "discrete-iqae-report-v1"
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
    html = (output / "report.html").read_text(encoding="utf-8")
    assert html.count('src="data:image/png;base64,') == 4
    assert "original payoff units" in html
    assert "demonstrates no practical quantum speedup" in html
    _, summary = read_study(directory)
    figure = rmse_figure(summary)
    try:
        call = next(c for c in summary["cells"] if c["problem_id"] == "call")
        lines = {line.get_label(): line for line in figure.axes[0].get_lines()}
        count = call["costs_conditional_on_completion"]["sample_count"]["median"]
        assert lines["Analytical IID MC RMSE"].get_ydata() == pytest.approx(
            [math.sqrt(call["iid_variance"] / count)]
        )
        assert lines["Absolute target"].get_ydata() == pytest.approx([3])
    finally:
        plt.close(figure)
