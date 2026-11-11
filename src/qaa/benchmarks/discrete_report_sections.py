"""Finite-payoff report text with original-unit accuracy and separate problem cells."""

from qaa.benchmarks.report_sections import METHOD_NAMES, Section, Table, number, quantiles, rate


def identity(cell: dict) -> tuple[str, str, str]:
    """Show normalized precision next to the payoff identity and estimator."""
    return cell["problem_id"], number(cell["epsilon"]), METHOD_NAMES[cell["method"]]


def problem_section(manifest: dict) -> Section:
    """Expose actual input tables and rescaling instead of treating a payoff as Bernoulli."""
    cells = {c["problem_id"]: c for c in manifest["cells"]}
    rows = []
    for name, problem in manifest["problems"].items():
        cell = cells[name]
        rows.append(
            (
                name,
                str(problem["probabilities"]),
                str(problem["function_values"]),
                str(problem["bounds"]),
                number(cell["exact_expectation"]),
                cell["kind"],
            )
        )
    design = manifest["design"]
    return Section(
        "Finite-payoff protocol and units",
        (
            f"Protocol {manifest['protocol_id']}; {design['replications']} independent "
            f"replications per cell and method; alpha={number(design['alpha'])}; "
            f"IQAE shots={design['shots']}; root seed={design['seed']}.",
            "For bounds [a,b], IQAE encodes g=(f-a)/(b-a). Epsilon is normalized; "
            "the absolute target is (b-a)*epsilon. Estimates, intervals, bias, RMSE and "
            "interval widths below use the original payoff units. Coverage checks E[f] "
            "against the rescaled interval, not the normalized amplitude.",
            "Classical IID sampling uses a fixed Hoeffding budget from normalized epsilon "
            "and alpha. IQAE uses beta intervals and min_ratio=2. Exact table summation "
            "is the validation reference; it does not tune either estimator's stopping. "
            "Independent cell/method/replicate seed branches are fixed before execution.",
        ),
        (Table(("Payoff", "Probabilities", "Values", "Bounds", "Exact mean", "Kind"), rows),),
    )


def accuracy_sections(summary: dict) -> list[Section]:
    """Keep empirical rates, event counts and Wilson uncertainty together."""
    error_rows, rate_rows = [], []
    for cell in summary["cells"]:
        accuracy = cell["accuracy_conditional_on_completion"]
        error_rows.append(
            (
                *identity(cell),
                number(cell["absolute_error_target"]),
                number(accuracy["bias"]),
                number(accuracy["rmse"]),
                quantiles(accuracy["interval_width"]),
            )
        )
        rate_rows.append(
            (*identity(cell), cell["kind"], rate(accuracy["success"]), rate(accuracy["coverage"]))
        )
    return [
        Section(
            "Accuracy in original payoff units",
            tables=(
                Table(
                    (
                        "Payoff",
                        "Normalized epsilon",
                        "Method",
                        "Absolute target",
                        "Bias",
                        "RMSE",
                        "Interval width: median [q10,q90]",
                    ),
                    error_rows,
                ),
            ),
            figure="rmse",
            caption="Separate payoff panels; analytical IID MC RMSE uses "
            "the exact payoff variance. "
            "The dotted line is the absolute target. Controls appear only in tables.",
        ),
        Section(
            "Success and interval coverage",
            (
                "Rates are conditional on valid completed runs. Brackets give 95% Wilson "
                "intervals for replication rates, distinct from each estimator's confidence "
                "interval. Small pilots cannot establish nominal coverage. Cells are never pooled.",
            ),
            (
                Table(
                    ("Payoff", "Normalized epsilon", "Method", "Kind", "Within target", "Coverage"),
                    rate_rows,
                ),
            ),
            figure="success",
            caption="Success means original-unit absolute error at most the declared target.",
        ),
        Section(
            "Coverage by precision",
            figure="coverage",
            caption="Coverage of the original-unit expectation; bars are Wilson intervals. "
            "The dashed line is nominal 1-alpha, not an observed guarantee.",
        ),
    ]


def completion_section(summary: dict) -> Section:
    """Retain failed, unavailable and unrecorded attempts in planned denominators."""
    rows = []
    for cell in summary["cells"]:
        counts = cell["status_counts"]
        rows.append(
            (
                *identity(cell),
                cell["kind"],
                str(cell["planned"]),
                *(
                    str(counts.get(status, 0))
                    for status in ("completed", "failed", "unavailable", "not_recorded")
                ),
                number(cell["verified_success_fraction_of_planned"]),
            )
        )
    return Section(
        "Per-cell completion ledger",
        tables=(
            Table(
                (
                    "Payoff",
                    "Normalized epsilon",
                    "Method",
                    "Kind",
                    "Planned",
                    "Completed",
                    "Failed",
                    "Unavailable",
                    "Missing",
                    "Verified success/planned",
                ),
                rows,
            ),
        ),
    )


def resource_section(summary: dict) -> Section:
    """Unlike resource units remain separate; simulator runtime is not hardware runtime."""
    rows = []
    for cell in summary["cells"]:
        for metric, distribution in cell["costs_conditional_on_completion"].items():
            rows.append((*identity(cell), metric, quantiles(distribution)))
    return Section(
        "Resources conditional on completion",
        (
            "IID observations, simulator measurement draws, Grover applications and shot-weighted "
            "logical gates are different costs. Logical gates include preparation and inverse "
            "workloads under the existing u/cx decomposition; these are not hardware estimates. "
            "Construction, inspection and estimator timings remain separate in the raw records.",
        ),
        (Table(("Payoff", "Normalized epsilon", "Method", "Resource", "Median [q10,q90]"), rows),),
        figure="costs",
        caption="Costs by payoff; bars show empirical q10-q90 spread.",
    )


def build_discrete_sections(manifest: dict, summary: dict, oracle: dict | None) -> list[Section]:
    """Reuse verified summaries and renderers without importing Bernoulli conclusions."""
    from qaa.benchmarks.report_sections import oracle_section

    complete = summary["completed_trials"] == summary["planned_trials"]
    sections = [
        Section(
            "Discrete study status",
            (
                f"{'Complete' if complete else 'Incomplete: conditional results only'}. "
                f"{summary['completed_trials']}/{summary['planned_trials']} "
                "planned trials completed. "
                f"Classification: {summary['classification']}. "
                "No estimators were run for this report.",
            ),
        ),
        problem_section(manifest),
        *accuracy_sections(summary),
        resource_section(summary),
        completion_section(summary),
        Section(
            "Interpretation and limits",
            (
                "These tiny explicit tables admit exact O(m) summation, which is preferable "
                "when the whole table is already available. The experiment validates coherent "
                "encoding and statistical behavior; it demonstrates no practical quantum speedup. "
                "Classical sampling and coherent table access have different implementation costs.",
                "The rare payoff has only 3% nonzero outcomes. The signed payoff checks affine "
                "rescaling with a negative lower bound. Constant lower/upper controls use a "
                "positive declared range and are excluded from precision plots. This selection "
                "is a fixed calibration suite, not evidence for all finite distributions.",
                "Accuracy and resource summaries condition on completion. Failures never become "
                "successful estimates; missing seeds are not retried. Wilson intervals describe "
                "individual cells without a simultaneous multiple-comparison guarantee.",
            ),
        ),
        Section(
            "Reproducibility and provenance",
            (
                f"Experiment source SHA256: {summary['source_sha256']}. "
                f"Raw trial log SHA256: {summary['trials_sha256']}.",
                "Input tables, settings and installed dependency versions are retained in "
                "data/study-manifest.json. Figures and tables come from freshly validated raw "
                "records; input artifacts are read-only. Reporting sources and output checksums "
                "are archived separately in report-manifest.json and source-files.json.",
            ),
        ),
    ]
    if oracle is not None:
        sections.insert(-2, oracle_section(oracle))
    return sections
