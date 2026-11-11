"""Verify protocol classification, complete grid and the precise seed hierarchy."""

import numpy as np
import pytest

from qaa.benchmarks.study_design import StudyDesign, trial_plan


def test_primary_design():
    design = StudyDesign()
    plan = list(trial_plan(design))
    assert design.classification == "primary"
    assert len(design.cells) == 18
    assert len(plan) == 7200
    assert [cell["kind"] for cell in design.cells[-2:]] == ["endpoint", "endpoint"]
    assert [cell["probability"] for cell in design.cells[-2:]] == [0.0, 1.0]
    assert all(cell["epsilon"] == 0.05 for cell in design.cells[-2:])
    assert len({row["seed"] for row in plan}) == len(plan)


def test_seed_tree_and_classical_branch():
    design = StudyDesign(probabilities=(0.3,), epsilons=(0.05,), replications=3, endpoints=False)
    plan = list(trial_plan(design))
    root = np.random.SeedSequence(20261111)
    streams = root.spawn(1)[0].spawn(2)
    expected = [
        int(child.generate_state(1, dtype=np.uint64)[0])
        for stream in streams
        for child in stream.spawn(3)
    ]
    assert [r["seed"] for r in plan] == expected
    classical = StudyDesign(
        probabilities=(0.3,), epsilons=(0.05,), replications=3, endpoints=False, quantum=False
    )
    assert [r["seed"] for r in trial_plan(classical)] == expected[:3]
    assert classical.classification == design.classification == "pilot"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"probabilities": ()},
        {"probabilities": (0.3, 0.3)},
        {"probabilities": (0.0,)},
        {"probabilities": (float("nan"),)},
        {"epsilons": (0,)},
        {"epsilons": [0.1]},
        {"replications": True},
        {"replications": 0},
        {"alpha": 1},
        {"shots": 0},
        {"seed": None},
        {"seed": -1},
        {"endpoints": 1},
    ],
)
def test_invalid_design(kwargs):
    with pytest.raises(ValueError):
        StudyDesign(**kwargs)
