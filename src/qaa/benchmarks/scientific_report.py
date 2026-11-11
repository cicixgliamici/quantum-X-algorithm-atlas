"""Generate a reproducible report and static figures from saved study artifacts."""

import argparse
import hashlib
import json
import platform
from importlib.metadata import distributions
from pathlib import Path

from qaa._validation import positive_integer
from qaa.benchmarks.report_rendering import render_html, render_markdown
from qaa.benchmarks.report_sections import build_sections
from qaa.benchmarks.statistical_study import read_study
from qaa.benchmarks.study_archive import archive_source, write_json


def validate_oracle_study(oracle: dict) -> None:
    """Reject unsupported or inconsistent counts rather than plotting an unlabeled model."""
    if oracle.get("study_id") != "discrete-oracle-cost-v1" or oracle.get("status") != "completed":
        raise ValueError("oracle input must be a completed discrete-oracle-cost-v1 study")
    convention = oracle["resource_convention"]
    if (
        convention["basis_gates"] != ["u", "cx"]
        or convention["optimization_level"] != 0
        or convention["seed_transpiler"] != 0
        or convention["hardware_backend"] is not None
        or not convention["depth_includes_measurements"]
        or set(convention["gate_counts_exclude"]) != {"measure", "barrier"}
    ):
        raise ValueError("unsupported oracle decomposition convention")
    if not oracle["rows"] or len({r["outcome_count"] for r in oracle["rows"]}) != len(
        oracle["rows"]
    ):
        raise ValueError("oracle study must contain distinct nonempty outcome sizes")
    for row in oracle["rows"]:
        positive_integer(row["outcome_count"], "outcome_count")
        for name in (
            "distribution_loading",
            "function_encoding",
            "state_preparation",
            "inverse_state_preparation",
            "grover_operator",
        ):
            metrics = row["oracle"]["components"][name]
            for field in (
                "gate_count",
                "single_qubit_gate_count",
                "two_qubit_gate_count",
                "depth",
                "qubits",
            ):
                positive_integer(metrics[field], field, minimum=1 if field == "qubits" else 0)
            if (
                metrics["gate_count"]
                != metrics["single_qubit_gate_count"] + metrics["two_qubit_gate_count"]
            ):
                raise ValueError("oracle gate-count identity failed")


def file_hashes(directory: Path) -> dict[str, str]:
    """Hash generated content; source bytes have their own inventory and combined hash."""
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
        and "source" not in path.relative_to(directory).parts
        and path.name != "report-manifest.json"
    }


def generate_report(study: Path, output: Path, *, oracle_study: Path | None = None) -> dict:
    """Read inputs without rewriting them and refuse to overwrite an existing report."""
    manifest, summary = read_study(study)
    if manifest["protocol_id"] != "mc-iqae-v1":
        raise ValueError("only mc-iqae-v1 studies are supported")
    oracle_bytes = oracle_study.read_bytes() if oracle_study else None
    oracle = json.loads(oracle_bytes) if oracle_bytes is not None else None
    if oracle is not None:
        validate_oracle_study(oracle)
    try:
        from qaa.benchmarks.report_figures import generate_figures
    except ModuleNotFoundError as error:
        if error.name != "matplotlib":
            raise
        raise ModuleNotFoundError(
            "Install the report extra: python -m pip install -e '.[report]'"
        ) from error
    output.mkdir(parents=True, exist_ok=False)
    provenance = archive_source(output)
    (output / "data").mkdir()
    (output / "figures").mkdir()
    write_json(output / "data" / "study-manifest.json", manifest)
    write_json(output / "data" / "summary.json", summary)
    if oracle_bytes is not None:
        (output / "data" / "oracle-cost.json").write_bytes(oracle_bytes)
    names = generate_figures(summary, manifest["design"]["alpha"], output / "figures", oracle)
    sections = build_sections(manifest, summary, oracle)
    (output / "report.md").write_text(render_markdown(sections), encoding="utf-8")
    (output / "report.html").write_text(render_html(sections, output), encoding="utf-8")
    result = {
        "report_id": "mc-iqae-report-v1",
        "classification": summary["classification"],
        "completed_trials": summary["completed_trials"],
        "planned_trials": summary["planned_trials"],
        "study_source_sha256": summary["source_sha256"],
        "trials_sha256": summary["trials_sha256"],
        "input_manifest_sha256": hashlib.sha256((study / "manifest.json").read_bytes()).hexdigest(),
        "oracle_input_sha256": hashlib.sha256(oracle_bytes).hexdigest() if oracle_bytes else None,
        "generator_provenance": provenance,
        "figure_names": names,
        "report_environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "installed_packages": dict(
                sorted(
                    (p.metadata["Name"], p.version) for p in distributions() if p.metadata["Name"]
                )
            ),
        },
        "files": file_hashes(output),
    }
    write_json(output / "report-manifest.json", result)
    return result


def main() -> None:
    """Reporting never invokes estimation; incomplete studies remain explicitly labeled."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", type=Path)
    parser.add_argument("--oracle-study", type=Path)
    parser.add_argument("--output", type=Path, default=Path("results/scientific-report"))
    args = parser.parse_args()
    report = generate_report(args.study, args.output, oracle_study=args.oracle_study)
    print(
        f"Wrote {args.output / 'report.html'} ({report['classification']}; "
        f"{report['completed_trials']}/{report['planned_trials']} completed)"
    )


if __name__ == "__main__":
    main()
