"""Validate finite problem inputs and original-unit classical sampling."""

import numpy as np
import pytest

from qaa.classical.monte_carlo import estimate_expectation
from qaa.problems.discrete import DiscreteExpectation, synthetic_call_payoff


def test_analytical_payoff_and_monte_carlo():
    problem = synthetic_call_payoff()
    assert problem.function_values == (0, 0, 10, 30)
    assert problem.exact_expectation == pytest.approx(13)
    assert problem.normalized_values == pytest.approx([0, 0, 1 / 3, 1])
    result = estimate_expectation(problem.sample, 20000, bounds=problem.bounds, seed=42)
    # Exact variance: E[f^2]-E[f]^2 = 310-169 = 141.
    assert abs(result.estimate - 13) < 6 * np.sqrt(141 / 20000)
    repeated = estimate_expectation(problem.sample, 20000, bounds=problem.bounds, seed=42)
    assert result.estimate == repeated.estimate
    assert result.sample_variance == repeated.sample_variance


def test_negative_values_and_immutable_input():
    probabilities, values = [0.25, 0.75], [-2, 6]
    problem = DiscreteExpectation(probabilities, values, (-2, 6))
    probabilities[0] = 1
    values[0] = 100
    assert problem.probabilities == (0.25, 0.75)
    assert problem.exact_expectation == 4
    assert problem.normalized_values == pytest.approx([0, 1])


@pytest.mark.parametrize(
    "probabilities, values, bounds",
    [
        ([], [], (0, 1)),
        ([0.2, 0.2], [0, 1], (0, 1)),
        ([-0.1, 1.1], [0, 1], (0, 1)),
        ([np.nan, 1], [0, 1], (0, 1)),
        ([[1]], [0], (0, 1)),
        ([1], [0, 1], (0, 1)),
        ([1], [np.inf], (0, 1)),
        ([1], [2], (0, 1)),
        ([1], [0], (1, 0)),
        ([1], [0], (0, 0)),
        ([1], [0], (0, np.inf)),
        ([1], [0], (-1e308, 1e308)),
        ([1], [0], (0,)),
    ],
)
def test_invalid_tables(probabilities, values, bounds):
    with pytest.raises(ValueError):
        DiscreteExpectation(probabilities, values, bounds)


def test_probability_roundoff():
    problem = DiscreteExpectation((0.1, 0.9 + 1e-13), (0, 1), (0, 1))
    assert sum(problem.probabilities) == pytest.approx(1)
    assert problem.sample(np.random.default_rng(1), 10).shape == (10,)
