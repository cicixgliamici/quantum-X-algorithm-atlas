"""Static scientific figures from verified cell summaries, with explicit cost units."""

import math
import os
import tempfile
from pathlib import Path

# A writable temporary cache supports restricted workstations without home-directory writes.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "qaa-matplotlib"))
import matplotlib  # noqa: E402

# Reports must run in CI and on workstations without launching a GUI.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import NullLocator  # noqa: E402

METHODS = {"classical": ("Monte Carlo", "#245a81", "o"), "quantum": ("IQAE", "#b55324", "s")}


def grid_cells(
    summary: dict, method: str | None = None, probability: float | None = None
) -> list[dict]:
    """Keep endpoint controls out of precision plots and preserve actual missing cells."""
    return sorted(
        (
            cell
            for cell in summary["cells"]
            if cell["kind"] == "grid"
            and (method is None or cell["method"] == method)
            and (probability is None or cell["probability"] == probability)
        ),
        key=lambda cell: cell["epsilon"],
        reverse=True,
    )


def panel_grid(summary: dict):
    """Use one panel per probability, including incomplete and classical-only studies."""
    probabilities = sorted({cell["probability"] for cell in grid_cells(summary)})
    columns = min(2, len(probabilities))
    rows = math.ceil(len(probabilities) / columns)
    figure, axes = plt.subplots(rows, columns, figsize=(5.4 * columns, 3.6 * rows), squeeze=False)
    for axis in axes.flat[len(probabilities) :]:
        axis.set_visible(False)
    return figure, list(zip(probabilities, axes.flat, strict=False))


def precision_axis(axis, epsilons: list[float], ylabel: str) -> None:
    """Read coarse to fine precision from left to right; show only measured targets."""
    axis.set_xscale("log")
    axis.set_xlim(max(epsilons) * 1.2, min(epsilons) / 1.2)
    ticks = sorted(set(epsilons), reverse=True)
    axis.set_xticks(ticks, [f"{value:g}" for value in ticks])
    axis.xaxis.set_minor_locator(NullLocator())
    axis.set_xlabel("Normalized error target ε")
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.22)


def finish_figure(figure, title: str) -> None:
    """A figure-level legend avoids repeating labels in every probability panel."""
    labels = {}
    for axis in figure.axes:
        handles, names = axis.get_legend_handles_labels()
        labels.update(zip(names, handles, strict=True))
    figure.suptitle(title, fontsize=14)
    columns = min(4, len(labels)) if labels else 1
    legend_rows = math.ceil(len(labels) / columns)
    if labels:
        figure.legend(labels.values(), labels.keys(), loc="lower center", ncol=columns)
    # Reserve physical space so multi-line legends cannot overlap a short figure's labels.
    height = figure.get_figheight()
    bottom = (0.4 + 0.25 * legend_rows) / height
    figure.tight_layout(rect=(0, bottom, 1, 1 - 0.55 / height), w_pad=3.5, h_pad=2.4)


def rmse_figure(summary: dict):
    """Observed RMSE and the exact classical IID reference are distinct series."""
    figure, panels = panel_grid(summary)
    for probability, axis in panels:
        cells = grid_cells(summary, probability=probability)
        epsilons = sorted({c["epsilon"] for c in cells}, reverse=True)
        for method, (name, color, marker) in METHODS.items():
            selected = grid_cells(summary, method, probability)
            available = [
                c for c in selected if (c["accuracy_conditional_on_completion"]["rmse"] or 0) > 0
            ]
            if not available:
                continue
            axis.plot(
                [c["epsilon"] for c in available],
                [c["accuracy_conditional_on_completion"]["rmse"] for c in available],
                label=name,
                color=color,
                marker=marker,
            )
        classical = [c for c in cells if c["method"] == "classical" and c["completion"]["count"]]
        axis.plot(
            [c["epsilon"] for c in classical],
            [
                math.sqrt(
                    probability
                    * (1 - probability)
                    / c["costs_conditional_on_completion"]["sample_count"]["median"]
                )
                for c in classical
            ],
            color="#68717b",
            linestyle="--",
            label="Analytical IID MC RMSE",
        )
        axis.plot(epsilons, epsilons, color="#363d44", linestyle=":", label="ε reference")
        axis.set_yscale("log")
        axis.set_title(f"p = {probability:g}")
        precision_axis(axis, epsilons, "RMSE (log scale)")
    finish_figure(figure, "Estimation error by precision target")
    return figure


def rate_figure(summary: dict, event: str, alpha: float):
    """Wilson intervals quantify uncertainty of the empirical replication rate."""
    figure, panels = panel_grid(summary)
    for probability, axis in panels:
        lower_limits = [1 - alpha]
        for method_index, (method, (name, color, marker)) in enumerate(METHODS.items()):
            cells = grid_cells(summary, method, probability)
            available = [
                c
                for c in cells
                if c["accuracy_conditional_on_completion"][event]["rate"] is not None
            ]
            rates = [c["accuracy_conditional_on_completion"][event] for c in available]
            if rates:
                values = np.array([r["rate"] for r in rates])
                limits = np.array([r["wilson_95"] for r in rates]).T
                axis.errorbar(
                    # Display offsets reveal coincident intervals; numerical targets stay unchanged.
                    [c["epsilon"] * math.exp((method_index - 0.5) * 0.035) for c in available],
                    values,
                    yerr=np.maximum(0, np.vstack((values - limits[0], limits[1] - values))),
                    label=name,
                    color=color,
                    marker=marker,
                    capsize=3,
                    linewidth=1.4,
                )
                lower_limits.extend(limits[0])
        axis.axhline(1 - alpha, color="#363d44", linestyle="--", label="Nominal 1 − α")
        axis.set_ylim(max(0, min(lower_limits) - 0.04), 1.015)
        axis.set_title(f"p = {probability:g}")
        precision_axis(
            axis,
            [c["epsilon"] for c in grid_cells(summary, probability=probability)],
            "Empirical rate",
        )
    title = "Interval coverage" if event == "coverage" else "Success within the requested tolerance"
    finish_figure(figure, f"{title} · 95% Wilson intervals")
    return figure


def cost_figure(summary: dict):
    """Each panel has one resource unit; zero Grover-query workloads stay visible."""
    metrics = (
        ("classical", "sample_count", "IID observations"),
        ("quantum", "total_shots", "Simulator measurement draws"),
        ("quantum", "grover_queries", "Logical Grover applications"),
        ("quantum", "state_preparation_calls", "Forward + inverse A calls"),
        ("quantum", "logical_gate_applications", "Shot-weighted logical gates"),
        ("quantum", "max_circuit_depth", "Maximum circuit depth"),
    )
    figure, axes = plt.subplots(3, 2, figsize=(10.8, 10.2))
    probabilities = sorted({c["probability"] for c in grid_cells(summary)})
    colors = plt.get_cmap("viridis")(np.linspace(0.1, 0.8, len(probabilities)))
    for axis, (method, metric, label) in zip(axes.flat, metrics, strict=True):
        has_data = False
        for probability_index, (probability, color) in enumerate(
            zip(probabilities, colors, strict=True)
        ):
            cells = [
                c
                for c in grid_cells(summary, method, probability)
                if c["costs_conditional_on_completion"].get(metric)
            ]
            if not cells:
                continue
            has_data = True
            distributions = [c["costs_conditional_on_completion"][metric] for c in cells]
            medians = np.array([d["median"] for d in distributions])
            axis.errorbar(
                [
                    c["epsilon"]
                    * math.exp((probability_index - (len(probabilities) - 1) / 2) * 0.035)
                    for c in cells
                ],
                medians,
                yerr=[
                    medians - [d["q10"] for d in distributions],
                    [d["q90"] for d in distributions] - medians,
                ],
                color=color,
                marker="o",
                capsize=3,
                label=f"p = {probability:g}",
            )
        precision_axis(axis, [c["epsilon"] for c in grid_cells(summary)], label)
        axis.set_ylim(bottom=0)
        axis.set_title("Monte Carlo" if method == "classical" else "IQAE")
        if not has_data:
            axis.text(0.5, 0.5, "No completed runs", transform=axis.transAxes, ha="center")
    finish_figure(figure, "Logical resources · median and 10th–90th percentiles")
    return figure


def oracle_figure(oracle: dict):
    """A separate input-size study makes loading/function costs visible."""
    rows = sorted(oracle["rows"], key=lambda row: row["outcome_count"])
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    sizes = [row["outcome_count"] for row in rows]
    for component, name, color, marker, style in (
        ("distribution_loading", "Distribution P", "#245a81", "o", "-"),
        ("function_encoding", "Function F", "#ce8a24", "s", "-"),
        ("state_preparation", "Preparation A", "#27806b", "o", "-"),
        ("inverse_state_preparation", "Inverse A", "#81549e", "x", "--"),
        ("grover_operator", "Grover Q", "#b55324", "s", "-"),
    ):
        values = [row["oracle"]["components"][component] for row in rows]
        axes[0].plot(
            sizes,
            [v["gate_count"] for v in values],
            marker=marker,
            linestyle=style,
            color=color,
            label=name,
        )
        if component in {"state_preparation", "grover_operator"}:
            axes[1].plot(
                sizes,
                [v["depth"] for v in values],
                marker=marker,
                linestyle=style,
                color=color,
                label=name,
            )
    for axis, label in zip(axes, ("Logical u + cx gates", "Circuit depth"), strict=True):
        axis.set_xlabel("Number of table outcomes m")
        axis.set_ylabel(label)
        axis.set_xticks(sizes)
        axis.set_ylim(bottom=0)
        axis.grid(True, alpha=0.22)
    finish_figure(figure, "Separate oracle construction study · dense explicit tables")
    return figure


def generate_figures(
    summary: dict, alpha: float, output: Path, oracle: dict | None = None
) -> list[str]:
    """Export standalone PNG/SVG files with stable metadata and SVG identifiers."""
    names = ["rmse", "success", "coverage", "costs"]
    with plt.rc_context({"font.size": 10, "svg.hashsalt": "qaa-report-v1", "svg.fonttype": "none"}):
        figures = [
            rmse_figure(summary),
            rate_figure(summary, "success", alpha),
            rate_figure(summary, "coverage", alpha),
            cost_figure(summary),
        ]
        if oracle is not None:
            names.append("oracle-cost")
            figures.append(oracle_figure(oracle))
        for name, figure in zip(names, figures, strict=True):
            try:
                figure.savefig(
                    output / f"{name}.png",
                    dpi=180,
                    metadata={"Software": "Quantum Algorithm Atlas"},
                )
                figure.savefig(
                    output / f"{name}.svg",
                    metadata={"Date": None, "Creator": "Quantum Algorithm Atlas"},
                )
            finally:
                plt.close(figure)
    return names
