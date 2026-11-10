"""Analytical identities and seeded numerical checks for IID sampling."""

import numpy as np
import pytest

from qaa.classical.monte_carlo import estimate_bernoulli, estimate_expectation


def test_known_observations():
    result = estimate_expectation(lambda rng, n: [0, 1, 0, 1], 4, bounds=(0, 1), seed=1)
    assert result.estimate == 0.5
    assert result.sample_variance == pytest.approx(1 / 3)
    assert result.standard_error == pytest.approx(np.sqrt(1 / 12))
    assert result.sample_count == 4
    assert result.elapsed_seconds >= 0


def test_reproducibility():
    first = estimate_bernoulli(0.3, 1000, seed=42)
    second = estimate_bernoulli(0.3, 1000, seed=42)
    # Wall-clock duration is intentionally excluded from reproducibility claims.
    assert first.estimate == second.estimate
    assert first.sample_variance == second.sample_variance
    assert first.standard_error == second.standard_error


@pytest.mark.parametrize("p", [0.0, 1.0])
def test_deterministic_endpoints(p):
    result = estimate_bernoulli(p, 10, seed=2)
    assert result.estimate == p
    assert result.sample_variance == result.standard_error == 0


def test_uniform_integral():
    result = estimate_expectation(
        lambda rng, n: rng.uniform(size=n) ** 2, 20000, bounds=(0, 1), seed=21
    )
    # E[X^2]=1/3 and Var(X^2)=4/45 for X uniform on [0,1].
    assert abs(result.estimate - 1 / 3) < 6 * np.sqrt((4 / 45) / 20000)


def test_convergence_across_independent_replicates():
    errors = {}
    for n in (200, 20000):
        estimates = [estimate_bernoulli(0.3, n, seed=s).estimate for s in range(80)]
        errors[n] = np.mean((np.array(estimates) - 0.3) ** 2)
        # Ensemble MSE should track p(1-p)/n; wide bounds avoid a flaky slope test.
        assert 0.4 * 0.21 / n < errors[n] < 1.8 * 0.21 / n
    assert errors[20000] < errors[200] / 20


@pytest.mark.parametrize("count", [0, 1, -2, True, 3.5])
def test_invalid_sample_count(count):
    with pytest.raises(ValueError):
        estimate_bernoulli(0.3, count)


@pytest.mark.parametrize("p", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        estimate_bernoulli(p, 10)


@pytest.mark.parametrize("values", [[0], [[0, 1]], [0, np.nan], [-1, 0], [0, np.inf]])
def test_invalid_samples(values):
    with pytest.raises(ValueError):
        estimate_expectation(lambda rng, n: values, 2, bounds=(0, 1))


@pytest.mark.parametrize("bounds", [(1, 0), (0, np.inf), (0,), (0, np.nan)])
def test_invalid_bounds(bounds):
    with pytest.raises(ValueError):
        estimate_expectation(lambda rng, n: np.zeros(n), 2, bounds=bounds)


@pytest.mark.parametrize("seed", [-1, True, 2.5])
def test_invalid_seed(seed):
    with pytest.raises(ValueError):
        estimate_bernoulli(0.3, 10, seed=seed)
