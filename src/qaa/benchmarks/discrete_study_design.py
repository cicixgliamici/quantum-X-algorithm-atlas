"""Versioned finite-payoff replication design, distinct from Bernoulli calibration."""

from dataclasses import asdict, dataclass

import numpy as np

from qaa.benchmarks.study_design import StudyDesign
from qaa.problems.discrete import DiscreteExpectation, synthetic_call_payoff

PROTOCOL_ID = "discrete-iqae-v1"
PAYOFF_NAMES = ("call", "rare", "signed")
CONTROL_NAMES = ("constant_lower", "constant_upper")


def study_problem(name: str) -> DiscreteExpectation:
    """Fix tables before sampling; exact sums are validation references only."""
    problems = {
        "call": synthetic_call_payoff(),
        "rare": DiscreteExpectation((0.97, 0.02, 0.01), (0, 10, 100), (0, 100)),
        "signed": DiscreteExpectation((0.2, 0.5, 0.3), (-10, -2, 6), (-10, 6)),
        "constant_lower": DiscreteExpectation((0.25, 0.75), (-5, -5), (-5, 15)),
        "constant_upper": DiscreteExpectation((0.25, 0.75), (15, 15), (-5, 15)),
    }
    if name not in problems:
        raise ValueError(f"unknown discrete payoff: {name}")
    return problems[name]


def problem_cell(name: str, epsilon: float, kind: str) -> dict:
    """Retain both scales so tolerance and coverage cannot silently mix units."""
    problem = study_problem(name)
    lower, upper = problem.bounds
    truth = problem.exact_expectation
    variance = float(
        np.dot(problem.probabilities, (np.array(problem.function_values) - truth) ** 2)
    )
    return {
        "problem_id": name,
        "kind": kind,
        "epsilon": epsilon,
        "absolute_error_target": (upper - lower) * epsilon,
        "bounds": [lower, upper],
        "exact_expectation": truth,
        "iid_variance": variance,
    }


@dataclass(frozen=True)
class DiscreteStudyDesign:
    """Only the complete fixed design is primary; every override is a pilot."""

    payoffs: tuple[str, ...] = PAYOFF_NAMES
    epsilons: tuple[float, ...] = (0.1, 0.05, 0.025)
    replications: int = 200
    alpha: float = 0.05
    shots: int = 256
    seed: int = 20261112
    endpoints: bool = True
    quantum: bool = True

    def __post_init__(self) -> None:
        # Reuse scalar validation and preserve the established method-branch convention.
        StudyDesign(
            probabilities=(0.5,),
            epsilons=self.epsilons,
            replications=self.replications,
            alpha=self.alpha,
            shots=self.shots,
            seed=self.seed,
            endpoints=self.endpoints,
            quantum=self.quantum,
        )
        if not isinstance(self.payoffs, tuple) or not self.payoffs:
            raise ValueError("payoffs must be a nonempty tuple")
        if len(set(self.payoffs)) != len(self.payoffs) or any(
            name not in PAYOFF_NAMES for name in self.payoffs
        ):
            raise ValueError("payoffs must be distinct names from call, rare, signed")

    @property
    def methods(self) -> tuple[str, ...]:
        """Disabled quantum execution leaves classical seeds unchanged."""
        return ("classical", "quantum") if self.quantum else ("classical",)

    @property
    def cells(self) -> list[dict]:
        """Do not pool endpoint controls with the nonconstant precision grid."""
        cells = [
            problem_cell(name, epsilon, "grid")
            for name in self.payoffs
            for epsilon in self.epsilons
        ]
        if self.endpoints:
            cells.extend(problem_cell(name, 0.05, "endpoint") for name in CONTROL_NAMES)
        return [{"cell_id": index, **cell} for index, cell in enumerate(cells)]

    @property
    def classification(self) -> str:
        """Changing the sample count or selected tables never revises the protocol."""
        return "primary" if asdict(self) == asdict(DiscreteStudyDesign()) else "pilot"

    @property
    def problems(self) -> dict:
        """Archive actual input tables, rather than relying on human-readable labels."""
        names = dict.fromkeys(cell["problem_id"] for cell in self.cells)
        return {name: asdict(study_problem(name)) for name in names}
