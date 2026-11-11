"""Prespecified Bernoulli design and independent replication seeds."""

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from typing import Protocol

import numpy as np

from qaa._validation import positive_integer, probability, validate_seed
from qaa.benchmarks.discrete_expectation import hoeffding_sample_count


class ReplicationDesign(Protocol):
    """Share execution and seed planning without imposing a common problem model."""

    replications: int
    alpha: float
    shots: int
    seed: int

    @property
    def cells(self) -> list[dict]: ...

    @property
    def methods(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class StudyDesign:
    """Changes to the primary design produce a pilot, never an implicit protocol revision."""

    probabilities: tuple[float, ...] = (0.1, 0.3, 0.5, 0.9)
    epsilons: tuple[float, ...] = (0.1, 0.05, 0.025, 0.0125)
    replications: int = 200
    alpha: float = 0.05
    shots: int = 256
    seed: int = 20261111
    endpoints: bool = True
    quantum: bool = True

    def __post_init__(self) -> None:
        positive_integer(self.replications, "replications")
        positive_integer(self.shots, "shots")
        validate_seed(self.seed)
        if self.seed is None:
            raise ValueError("the study requires an explicit seed")
        for name, values in (("probabilities", self.probabilities), ("epsilons", self.epsilons)):
            if not isinstance(values, tuple) or not values:
                raise ValueError(f"{name} must be a nonempty tuple")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        for value in self.probabilities:
            probability(value)
            if value in (0, 1):
                raise ValueError("use endpoint controls for probabilities 0 and 1")
        for epsilon in self.epsilons:
            hoeffding_sample_count(epsilon, self.alpha)
        if not isinstance(self.endpoints, bool) or not isinstance(self.quantum, bool):
            raise ValueError("endpoints and quantum must be booleans")

    @property
    def methods(self) -> tuple[str, ...]:
        """Classical-only studies preserve the classical branch of the seed tree."""
        return ("classical", "quantum") if self.quantum else ("classical",)

    @property
    def cells(self) -> list[dict]:
        """p is outermost, epsilon innermost; endpoint controls are appended."""
        cells = [
            {"probability": p, "epsilon": epsilon, "kind": "grid"}
            for p in self.probabilities
            for epsilon in self.epsilons
        ]
        if self.endpoints:
            cells.extend(
                {"probability": p, "epsilon": 0.05, "kind": "endpoint"} for p in (0.0, 1.0)
            )
        return [{"cell_id": index, **cell} for index, cell in enumerate(cells)]

    @property
    def classification(self) -> str:
        """Only the exact registered grid is a primary protocol execution."""
        return "primary" if asdict(self) == asdict(StudyDesign()) else "pilot"


def trial_plan(design: ReplicationDesign) -> Iterator[dict]:
    """Yield deterministic IDs and uint64 seeds in protocol order, without RNG reuse."""
    cell_streams = np.random.SeedSequence(design.seed).spawn(len(design.cells))
    trial_id = 0
    for cell, cell_stream in zip(design.cells, cell_streams, strict=True):
        # Always spawn both branches, even when only the classical method is selected.
        method_streams = cell_stream.spawn(2)
        for method, stream in zip(("classical", "quantum"), method_streams, strict=True):
            if method not in design.methods:
                continue
            for replicate, replicate_stream in enumerate(stream.spawn(design.replications)):
                yield {
                    "trial_id": trial_id,
                    **cell,
                    "method": method,
                    "replicate": replicate,
                    "seed": int(replicate_stream.generate_state(1, dtype=np.uint64)[0]),
                    "alpha": design.alpha,
                }
                trial_id += 1
