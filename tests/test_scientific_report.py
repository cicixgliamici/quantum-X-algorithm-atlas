"""Read-only reporting, numerical plot data, reproducible exports and visible failures."""

import hashlib
import json
import math
import shutil

import pytest

pytest.importorskip("matplotlib")

from qaa.benchmarks import statistical_study  # noqa: E402
from qaa.benchmarks.report_figures import plt, rate_figure, rmse_figure  # noqa: E402
from qaa.benchmarks.report_rendering import html_table  # noqa: E402
from qaa.benchmarks.report_sections import Table, build_sections  # noqa: E402
from qaa.benchmarks.scientific_report import generate_report, validate_oracle_study  # noqa: E402
from qaa.benchmarks.statistical_study import read_study, run_study  # noqa: E402
from qaa.benchmarks.study_design import StudyDesign  # noqa: E402


@pytest.fixture(scope="module")
def saved_study(tmp_path_factory):
    directory = tmp_path_factory.mktemp("report-inputs") / "study"
    design = StudyDesign(probabilities=(0.3,), epsilons=(0.1, 0.05), replications=2, quantum=False)
    run_study(directory, design)
    return directory


def directory_hashes(directory):
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_read_only_standalone_and_reproducible_report(saved_study, tmp_path, monkeypatch):
    before = directory_hashes(saved_study)

    def forbidden(*args):
        raise AssertionError("Reporting must not invoke an estimator")

    monkeypatch.setattr(statistical_study, "classical_estimate", forbidden)
    monkeypatch.setattr(statistical_study, "quantum_estimate", forbidden)
    first, second = tmp_path / "first", tmp_path / "second"
    result = generate_report(saved_study, first)
    repeated = generate_report(saved_study, second)
    assert directory_hashes(saved_study) == before
    assert result["classification"] == "pilot"
    assert result["completed_trials"] == result["planned_trials"] == 8
    assert result["files"] == repeated["files"]
    for relative, digest in result["files"].items():
        assert hashlib.sha256((first / relative).read_bytes()).hexdigest() == digest
    html = (first / "report.html").read_text(encoding="utf-8")
    assert html.count('src="data:image/png;base64,') == 4
    assert '<html lang="en">' in html
    assert "IQAE was not selected" in html
    assert "pilot" in html
    assert "No new estimates were generated" in html
    with pytest.raises(FileExistsError):
        generate_report(saved_study, first)


def test_plotted_values_match_recomputed_summary(saved_study):
    manifest, summary = read_study(saved_study)
    cells = sorted(
        [c for c in summary["cells"] if c["kind"] == "grid"],
        key=lambda c: c["epsilon"],
        reverse=True,
    )
    figure = rmse_figure(summary)
    try:
        lines = {line.get_label(): line for line in figure.axes[0].get_lines()}
        assert lines["Monte Carlo"].get_ydata() == pytest.approx(
            [c["accuracy_conditional_on_completion"]["rmse"] for c in cells]
        )
        assert lines["Analytical IID MC RMSE"].get_ydata() == pytest.approx(
            [
                math.sqrt(0.21 / c["costs_conditional_on_completion"]["sample_count"]["median"])
                for c in cells
            ]
        )
    finally:
        plt.close(figure)
    figure = rate_figure(summary, "coverage", manifest["design"]["alpha"])
    try:
        central_line = figure.axes[0].containers[0].lines[0]
        assert central_line.get_ydata() == pytest.approx(
            [c["accuracy_conditional_on_completion"]["coverage"]["rate"] for c in cells]
        )
    finally:
        plt.close(figure)


def test_invalid_inputs_cannot_produce_a_report(saved_study, tmp_path):
    corrupted = tmp_path / "corrupted"
    shutil.copytree(saved_study, corrupted)
    with (corrupted / "trials.jsonl").open("ab") as raw:
        raw.write(b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        generate_report(corrupted, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_incomplete_runs_remain_visible(tmp_path, monkeypatch):
    def failed(*args):
        raise RuntimeError("synthetic estimator failure")

    monkeypatch.setattr(statistical_study, "classical_estimate", failed)
    directory = tmp_path / "incomplete-study"
    run_study(
        directory,
        StudyDesign(
            probabilities=(0.3,), epsilons=(0.1,), replications=1, quantum=False, endpoints=False
        ),
    )
    manifest, summary = read_study(directory)
    sections = build_sections(manifest, summary, None)
    assert "Incomplete" in sections[0].paragraphs[0]
    ledger = next(section for section in sections if section.title == "Per-cell completion ledger")
    assert ledger.tables[0].rows[0][6] == "1"
    report = generate_report(directory, tmp_path / "incomplete-report")
    assert report["completed_trials"] == 0
    assert "conditional" in (tmp_path / "incomplete-report" / "report.html").read_text()


def test_separate_oracle_artifact(saved_study, tmp_path):
    pytest.importorskip("qiskit_algorithms")
    from qaa.benchmarks.oracle_cost import run_oracle_cost_study

    oracle = run_oracle_cost_study((2,), powers=(0, 1))
    path = tmp_path / "oracle.json"
    path.write_text(json.dumps(oracle), encoding="utf-8")
    report = generate_report(saved_study, tmp_path / "with-oracle", oracle_study=path)
    assert "oracle-cost" in report["figure_names"]
    assert report["oracle_input_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    oracle["rows"][0]["oracle"]["components"]["state_preparation"]["gate_count"] += 1
    with pytest.raises(ValueError, match="identity failed"):
        validate_oracle_study(oracle)


def test_table_escapes_untrusted_content():
    rendered = html_table(Table(("<heading>",), [("<script>alert('bad')</script>",)]))
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
