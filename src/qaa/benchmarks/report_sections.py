"""Scientific narrative and tables derived from validated study summaries."""

from dataclasses import dataclass

METHOD_NAMES = {"classical": "Monte Carlo", "quantum": "IQAE"}


@dataclass(frozen=True)
class Table:
    """Formatted cells share one source between Markdown and HTML renderers."""

    headers: tuple[str, ...]
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class Section:
    """Small semantic report blocks keep rendering separate from numerical analysis."""

    title: str
    paragraphs: tuple[str, ...] = ()
    tables: tuple[Table, ...] = ()
    figure: str | None = None
    caption: str = ""


def number(value: float | None) -> str:
    """Retain useful precision in print; machine-readable summaries keep all digits."""
    return "—" if value is None else f"{value:.5g}"


def rate(value: dict) -> str:
    """A denominator and Wilson interval must accompany every empirical rate."""
    if value["rate"] is None:
        return f"— (0/{value['denominator']}; no interval)"
    low, high = value["wilson_95"]
    return (
        f"{value['count']}/{value['denominator']} = {100 * value['rate']:.1f}% "
        f"[{100 * low:.1f}%, {100 * high:.1f}%]"
    )


def quantiles(value: dict | None, multiplier: float = 1.0) -> str:
    """Keep spread next to the median rather than reporting a single favorable run."""
    if value is None:
        return "—"
    return (
        f"{number(value['median'] * multiplier)} "
        f"[{number(value['q10'] * multiplier)}, {number(value['q90'] * multiplier)}]"
    )


def identity(cell: dict) -> tuple[str, str, str]:
    """Identify a comparison cell without merging methods or endpoint controls."""
    return number(cell["probability"]), number(cell["epsilon"]), METHOD_NAMES[cell["method"]]


def run_status(summary: dict) -> Section:
    """Make missing or failed trials visible before any conditional accuracy claims."""
    completed, planned = summary["completed_trials"], summary["planned_trials"]
    status = "Complete" if completed == planned else "Incomplete: conditional results only"
    rows = []
    for cell in summary["cells"]:
        counts = cell["status_counts"]
        rows.append(
            (
                *identity(cell),
                cell["kind"],
                str(cell["planned"]),
                str(counts.get("completed", 0)),
                str(counts.get("failed", 0)),
                str(counts.get("unavailable", 0)),
                str(counts.get("not_recorded", 0)),
            )
        )
    return Section(
        "Study status and completeness",
        (
            f"{status}. {completed}/{planned} planned estimations completed; "
            f"{summary['recorded_trials']} attempts are present in the raw log. "
            f"Classification: {summary['classification']}. "
            "No new estimates were generated for this report.",
            "Accuracy, coverage and cost statistics below are conditional on completed runs. "
            "A target miss is a valid completed estimation, distinct from an execution failure. "
            "Missing, unavailable and failed trials remain visible in these counts.",
        ),
        (
            Table(
                (
                    "p",
                    "ε",
                    "Method",
                    "Cell kind",
                    "Planned",
                    "Completed",
                    "Failed",
                    "Unavailable",
                    "Missing",
                ),
                rows,
            ),
        ),
    )


def observed_findings(summary: dict) -> Section:
    """Describe ranges of per-cell rates without pooling cells into a single test."""
    paragraphs = []
    for method, name in METHOD_NAMES.items():
        cells = [c for c in summary["cells"] if c["kind"] == "grid" and c["method"] == method]
        if not cells:
            paragraphs.append(f"{name} was not selected in this study.")
            continue
        available = [c for c in cells if c["completion"]["count"]]
        if not available:
            paragraphs.append(f"{name}: no completed grid cells; accuracy cannot be assessed.")
            continue
        statements = []
        for event, label in (("success", "success within ε"), ("coverage", "interval coverage")):
            rates = [c["accuracy_conditional_on_completion"][event]["rate"] for c in available]
            statements.append(
                f"{label} ranges from {100 * min(rates):.1f}% to {100 * max(rates):.1f}%"
            )
        paragraphs.append(
            f"{name}, across {len(available)} grid cells: " + "; ".join(statements) + "."
        )
    paragraphs.append(
        "These are observed per-cell frequencies with finite replication uncertainty. "
        "The Wilson intervals and denominators appear in the confidence table. "
        "They do not establish a universal success rate or practical quantum speedup."
    )
    return Section("Observed findings", tuple(paragraphs))


def methods_section(manifest: dict) -> Section:
    """Separate assumptions and analytical predictions from measured results."""
    design = manifest["design"]
    return Section(
        "Problem, methods and theoretical context",
        (
            "The task is to estimate a Bernoulli probability p as a classical scalar. "
            "p is deliberately known to the experiment harness: this is calibration, "
            "not the discovery of unknown data. Monte Carlo draws IID Bernoulli observations; "
            "quantum state preparation uses Ry(2 asin(sqrt(p))) and marks |1> as success.",
            f"Requested failure probability α = {number(design['alpha'])}; normalized absolute "
            f"error targets ε = {', '.join(number(v) for v in design['epsilons'])}. "
            f"Each method/cell has {design['replications']} planned independent replications. "
            f"IQAE, when selected, uses {design['shots']} shots per circuit, beta intervals "
            "and min_ratio = 2. Powers and the number of iterations are adaptive.",
            "The classical budget is fixed before sampling: N = ceil(log(2/α)/(2ε²)), "
            "with at least two observations. A clipped Hoeffding interval uses the same α. "
            "The estimator is unbiased with analytical RMSE sqrt(p(1-p)/N). Hoeffding is "
            "conservative and is not an optimal Bernoulli-specific classical baseline.",
            "For bounded IID sampling, RMSE scales as N^(-1/2). Ideal amplitude estimation "
            "can improve additive-error query complexity under coherent access to A, its "
            "inverse and reflections [1]. IQAE avoids phase estimation, with logarithmic "
            "overhead in its query guarantee [2]. A finite precision grid does not "
            "prove an asymptotic law or show an end-to-end hardware advantage.",
            f"Root seed: {design['seed']}. Cell streams follow the registered p-major grid, "
            "then endpoint controls; separate method branches and replicate children produce "
            "uint64 seeds. Replicate indices are not paired observations across methods.",
        ),
    )


def accuracy_sections(summary: dict) -> list[Section]:
    """Endpoint controls and the main grid are displayed separately."""
    grid = [c for c in summary["cells"] if c["kind"] == "grid"]
    error_rows, confidence_rows, endpoint_rows = [], [], []
    for cell in grid:
        accuracy = cell["accuracy_conditional_on_completion"]
        error_rows.append(
            (
                *identity(cell),
                str(cell["completion"]["count"]),
                number(accuracy["rmse"]),
                number(accuracy["bias"]),
            )
        )
        confidence_rows.append(
            (*identity(cell), rate(accuracy["success"]), rate(accuracy["coverage"]))
        )
    for cell in summary["cells"]:
        if cell["kind"] == "endpoint":
            accuracy = cell["accuracy_conditional_on_completion"]
            endpoint_rows.append(
                (
                    *identity(cell),
                    number(accuracy["rmse"]),
                    number(accuracy["bias"]),
                    rate(accuracy["success"]),
                    rate(accuracy["coverage"]),
                )
            )
    return [
        Section(
            "Estimation error",
            (
                "Bias is mean(estimate − p); RMSE is sqrt(mean((estimate − p)²)). "
                "Both use completed replications. RMSE is not a confidence-interval half-width.",
            ),
            (Table(("p", "ε", "Method", "Completed", "RMSE", "Bias"), error_rows),),
            "rmse",
            "Points are empirical cell RMSEs; the dashed reference is the exact IID "
            "Monte Carlo RMSE at the fixed sample budget. The ε line is a visual reference, "
            "not an RMSE guarantee. Log axes omit zero RMSE; those values remain in the table. "
            "Endpoints are excluded; lines connect observations, with no fitted scaling law.",
        ),
        Section(
            "Success and confidence-interval coverage",
            (
                "Success means abs(estimate − p) ≤ ε; coverage means the reported interval "
                "contains p. These events can differ. Brackets in the table are 95% Wilson "
                "intervals for the empirical rates, not the per-estimation intervals. "
                "The nominal target is 1 − α per run, without a simultaneous guarantee over cells.",
            ),
            (
                Table(
                    ("p", "ε", "Method", "Success; Wilson 95%", "Coverage; Wilson 95%"),
                    confidence_rows,
                ),
            ),
            "success",
            "Observed success rates and Wilson intervals, conditional on completion. "
            "The dashed line is the nominal target. Small horizontal display offsets "
            "separate methods. Vertical axes may be zoomed; see tick labels.",
        ),
        Section(
            "Coverage across precision targets",
            (),
            (),
            "coverage",
            "Observed coverage and 95% Wilson intervals across independent replications. "
            "A rate below the nominal target alone does not establish an implementation defect. "
            "Small horizontal display offsets separate methods. Axes may be zoomed, "
            "and endpoint controls are separate.",
        ),
        Section(
            "Endpoint controls",
            (
                "p = 0 and p = 1 are deterministic classical controls. IQAE can return a "
                "nonzero error because it reports a finite-shot interval-based estimate. "
                "These cells are excluded from precision plots and grid findings."
                if endpoint_rows
                else "No endpoint controls were included in this design.",
            ),
            (
                Table(
                    (
                        "p",
                        "ε",
                        "Method",
                        "RMSE",
                        "Bias",
                        "Success; Wilson 95%",
                        "Coverage; Wilson 95%",
                    ),
                    endpoint_rows,
                ),
            )
            if endpoint_rows
            else (),
            caption="",
        ),
    ]


def resource_sections(summary: dict) -> list[Section]:
    """Logical counts are kept in separate columns and panels, never converted to speed."""
    count_rows, gate_rows, classical_rows, time_rows = [], [], [], []
    for cell in summary["cells"]:
        if cell["kind"] != "grid":
            continue
        costs, timings = (
            cell["costs_conditional_on_completion"],
            cell["timings_conditional_on_completion"],
        )
        key = identity(cell)
        if cell["method"] == "classical":
            classical_rows.append((*key[:2], quantiles(costs.get("sample_count"))))
        else:
            count_rows.append(
                (
                    *key[:2],
                    *(
                        quantiles(costs.get(name))
                        for name in (
                            "total_shots",
                            "grover_queries",
                            "forward_state_preparation_calls",
                            "inverse_state_preparation_calls",
                        )
                    ),
                )
            )
            gate_rows.append(
                (
                    *key[:2],
                    *(
                        quantiles(costs.get(name))
                        for name in (
                            "logical_gate_applications",
                            "logical_two_qubit_gate_applications",
                            "max_circuit_depth",
                        )
                    ),
                )
            )
        time_rows.append(
            (
                *key,
                quantiles(timings.get("estimation_seconds"), 1000),
                quantiles(timings.get("resource_inspection_seconds"), 1000),
                quantiles(timings.get("run_wall_seconds"), 1000),
            )
        )
    return [
        Section(
            "Resource distributions",
            (
                "All resource-table entries are median [10th, 90th percentile] over completed "
                "replications, using linear quantiles. IID samples, simulator draws, Grover "
                "applications and gate applications are distinct units. "
                "No common-cost ratio is computed.",
                "For S sampled shots and G logical Grover applications, forward A calls are S+G "
                "and inverse A calls are G. Gate applications sum each circuit's decomposed "
                "gate count times its shots. Maximum depth is a per-run circuit maximum, "
                "not a sum or an elapsed time. Actual hardware executions are zero.",
            ),
            (
                Table(("p", "ε", "Classical IID samples"), classical_rows),
                Table(
                    (
                        "p",
                        "ε",
                        "Simulator draws S",
                        "Grover applications G",
                        "Forward A",
                        "Inverse A",
                    ),
                    count_rows,
                ),
                Table(
                    ("p", "ε", "Logical gate applications", "cx applications", "Maximum depth"),
                    gate_rows,
                ),
            ),
            "costs",
            "Each panel retains its own resource unit. Points and bars are medians "
            "and 10th–90th percentiles, not confidence intervals. Linear count axes retain "
            "zero-query workloads. Small horizontal display offsets separate probabilities. "
            "These are modeled logical usage counts, not simulator work.",
        ),
        Section(
            "Diagnostic host timings",
            (
                "Values are milliseconds, median [10th, 90th percentile]. Estimation timers "
                "retain method-specific boundaries. IQAE resource inspection has a separate "
                "timer; invocation time includes extraction and validation but excludes raw-log "
                "writing. Fixed method order, cold imports and uncontrolled host load prevent "
                "these distributions from establishing a hardware or end-to-end speedup.",
            ),
            (
                Table(
                    ("p", "ε", "Method", "Estimation ms", "Inspection ms", "Invocation ms"),
                    time_rows,
                ),
            ),
        ),
    ]


def oracle_section(oracle: dict | None) -> Section:
    """Avoid conflating the dense-table experiment with the Bernoulli calibration grid."""
    if oracle is None:
        return Section(
            "Oracle preparation costs",
            (
                "No separate oracle-cost artifact was supplied. This report therefore makes "
                "no empirical claim about loading or function-encoding costs "
                "as problem size grows.",
            ),
        )
    rows = []
    for row in sorted(oracle["rows"], key=lambda value: value["outcome_count"]):
        components = row["oracle"]["components"]
        rows.append(
            (
                str(row["outcome_count"]),
                str(components["state_preparation"]["qubits"]),
                *(
                    str(components[name]["gate_count"])
                    for name in (
                        "distribution_loading",
                        "function_encoding",
                        "state_preparation",
                        "inverse_state_preparation",
                        "grover_operator",
                    )
                ),
                str(components["grover_operator"]["depth"]),
            )
        )
    versions = oracle["environment"]["dependencies"]
    return Section(
        "Separate oracle construction study",
        (
            "This section uses a separate dense, irregular finite-table family. It is not "
            "the Bernoulli calibration and its probe workloads are not added to IQAE's "
            "replicated costs. Tables are known explicitly; direct O(m) summation remains "
            "a cheap reference. Logarithmic register width alone does not imply cheap loading.",
            f"Oracle study seed: {oracle['seed']}; Qiskit {versions.get('qiskit')}. "
            "P loads the distribution, F encodes function values, A composes them, and Q "
            "includes A, its inverse and reflections. Components are actually decomposed "
            "to u/cx at optimization level 0; gate counts exclude measurements and barriers. "
            "Depth and counts describe this construction and compiler, not universal lower bounds.",
        ),
        (
            Table(
                (
                    "Outcomes m",
                    "Full qubits",
                    "P gates",
                    "F gates",
                    "A gates",
                    "Inverse A gates",
                    "Q gates",
                    "Q depth",
                ),
                rows,
            ),
        ),
        "oracle-cost",
        "Measured logical component costs from the separate size study. "
        "Coincident preparation/inverse curves are possible; both are tabulated independently. "
        "No hardware connectivity, duration or fault-tolerant synthesis is modeled.",
    )


def final_sections(manifest: dict, summary: dict) -> list[Section]:
    """State limitations explicitly and keep exact experiment provenance inspectable."""
    versions = manifest["environment"]["dependencies"]
    return [
        Section(
            "Limitations and next research questions",
            (
                "The experiment validates known-input Bernoulli calibration. The separate "
                "discrete payoff implementation encodes individual inputs but is not part of "
                "this replicated grid. No noise, error correction, hardware execution or "
                "realistic data-loading advantage is measured.",
                "Classical Hoeffding budgets are conservative. Observed results against that "
                "baseline do not establish superiority over the best classical estimator. "
                "Empirical RMSE, success and coverage are descriptive finite-grid results; "
                "no significance test, fitted complexity exponent or simultaneous guarantee "
                "is inferred. Failed or missing observations make summaries conditional.",
                "Next questions are repeated discrete-expectation coverage, alternative "
                "classical confidence procedures, structured reversible function evaluation "
                "and a declared hardware cost model. Those require new registered designs.",
            ),
        ),
        Section(
            "Reproducibility and provenance",
            (
                f"Protocol: {manifest['protocol_id']}. "
                f"Experiment source SHA256: {summary['source_sha256']}. "
                f"Raw trial log SHA256: {summary['trials_sha256']}.",
                f"Study environment: Python {manifest['environment']['python']}; "
                f"NumPy {versions.get('numpy')}; Qiskit {versions.get('qiskit')}; "
                f"Qiskit Algorithms {versions.get('qiskit-algorithms')}. Full installed versions "
                "are retained in data/study-manifest.json. Reporting environment and generator "
                "source hashes are recorded separately in report-manifest.json.",
                "Every table and figure is generated from a fresh in-memory summary of the "
                "verified raw log. The original study artifacts are read-only. Numerical "
                "values retain full precision in data/summary.json; displayed values are rounded. "
                "The standalone HTML embeds figures; Markdown uses the exported PNG files. "
                "Checksums provide integrity checks, not authenticity guarantees.",
            ),
        ),
        Section(
            "Primary references",
            tables=(
                Table(
                    ("Reference", "Source"),
                    [
                        (
                            "[1] Brassard et al. Quantum Amplitude Amplification "
                            "and Estimation (2000/2002).",
                            "https://arxiv.org/abs/quant-ph/0005055",
                        ),
                        (
                            "[2] Grinko et al. Iterative Quantum Amplitude Estimation (2021).",
                            "https://arxiv.org/abs/1912.05559",
                        ),
                    ],
                ),
            ),
        ),
    ]


def build_sections(manifest: dict, summary: dict, oracle: dict | None) -> list[Section]:
    """One semantic document drives both renderers, preventing divergent claims."""
    status = run_status(summary)
    # Keep completeness warnings up front; move the long per-cell ledger after results.
    return [
        Section(status.title, status.paragraphs),
        observed_findings(summary),
        methods_section(manifest),
        *accuracy_sections(summary),
        *resource_sections(summary),
        oracle_section(oracle),
        Section(
            "Per-cell completion ledger",
            (
                "These counts retain every planned cell and method, including endpoint controls. "
                "They distinguish estimation target misses from unavailable, failed "
                "or unrecorded attempts.",
            ),
            status.tables,
        ),
        *final_sections(manifest, summary),
    ]
