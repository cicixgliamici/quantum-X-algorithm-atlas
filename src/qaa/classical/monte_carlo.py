"""Estimate expectations of bounded, independently sampled scalar observations."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

import numpy as np
from numpy.typing import ArrayLike

from qaa._validation import positive_integer, probability, validate_seed

Sampler = Callable[[np.random.Generator, int], ArrayLike]


@dataclass(frozen=True)
class MonteCarloResult:
    """Sample variance uses ddof=1; elapsed time covers sampling and reduction."""

    estimate: float
    sample_variance: float
    standard_error: float
    sample_count: int
    elapsed_seconds: float
    seed: int | None


def estimate_expectation(
    sampler: Sampler,
    sample_count: int,
    *,
    bounds: tuple[float, float],
    seed: int | None = None,
) -> MonteCarloResult:
    """Estimate E[f(X)] from a callback returning n IID values of f(X).

    The callback receives the only RNG it should use. Independence and the
    declared bounds are the caller's contract; independence cannot be verified.
    At least two observations are required to estimate an unbiased variance.
    """
    positive_integer(sample_count, "sample_count", minimum=2)
    validate_seed(seed)
    if not callable(sampler):
        raise ValueError("sampler must be callable")
    limits = np.asarray(bounds, dtype=float)
    if limits.shape != (2,) or not np.all(np.isfinite(limits)) or limits[0] > limits[1]:
        raise ValueError("bounds must contain two finite, ordered numbers")
    started = perf_counter()
    values = np.asarray(sampler(np.random.default_rng(seed), sample_count), dtype=float)
    if values.shape != (sample_count,):
        raise ValueError("sampler must return a one-dimensional array of sample_count values")
    if not np.all(np.isfinite(values)):
        raise ValueError("samples must be finite")
    if np.any(values < limits[0]) or np.any(values > limits[1]):
        raise ValueError("samples violate the declared bounds")
    variance = float(np.var(values, ddof=1))
    return MonteCarloResult(
        estimate=float(np.mean(values)),
        sample_variance=variance,
        standard_error=float(np.sqrt(variance / sample_count)),
        sample_count=int(sample_count),
        elapsed_seconds=perf_counter() - started,
        seed=seed,
    )


def estimate_bernoulli(
    target_probability: float, sample_count: int, *, seed: int | None = None
) -> MonteCarloResult:
    """Synthetic calibration problem with a known analytical answer."""
    probability(target_probability)
    return estimate_expectation(
        lambda rng, size: rng.binomial(1, target_probability, size),
        sample_count,
        bounds=(0.0, 1.0),
        seed=seed,
    )
