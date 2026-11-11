"""Run and reanalyze the registered finite-payoff replication study."""

import argparse
from pathlib import Path

from qaa.benchmarks.discrete_study_design import PAYOFF_NAMES, DiscreteStudyDesign
from qaa.benchmarks.statistical_study import analyze_study, run_study


def parser() -> argparse.ArgumentParser:
    """Keep execution explicit and analysis independent of optional quantum imports."""
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--output", type=Path, default=Path("results/discrete-study"))
    run.add_argument("--payoffs", nargs="+", choices=PAYOFF_NAMES, default=list(PAYOFF_NAMES))
    run.add_argument("--epsilons", nargs="+", type=float, default=[0.1, 0.05, 0.025])
    run.add_argument("--replications", type=int, default=200)
    run.add_argument("--alpha", type=float, default=0.05)
    run.add_argument("--shots", type=int, default=256)
    run.add_argument("--seed", type=int, default=20261112)
    run.add_argument("--no-endpoints", action="store_true")
    run.add_argument("--classical-only", action="store_true")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("directory", type=Path)
    return root


def main() -> None:
    """Retain failed trials and signal incomplete execution through the exit status."""
    args = parser().parse_args()
    if args.command == "analyze":
        summary = analyze_study(args.directory)
    else:
        design = DiscreteStudyDesign(
            payoffs=tuple(args.payoffs),
            epsilons=tuple(args.epsilons),
            replications=args.replications,
            alpha=args.alpha,
            shots=args.shots,
            seed=args.seed,
            endpoints=not args.no_endpoints,
            quantum=not args.classical_only,
        )
        summary = run_study(
            args.output, design, progress=lambda message: print(message, flush=True)
        )
    print(
        f"{summary['classification']}: "
        f"{summary['completed_trials']}/{summary['planned_trials']} completed"
    )
    if summary["completed_trials"] != summary["planned_trials"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
