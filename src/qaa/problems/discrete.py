"""Explicit finite distributions and bounded function values."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class DiscreteExpectation:
    """Estimate sum_i p_i*f_i; indices identify the outcomes of the distribution.

    Tables are copied into immutable tuples so later caller mutations cannot
    change the problem. Bounds must have positive, finite width, even for a
    constant function, to make amplitude normalization unambiguous.
    """

    probabilities: tuple[float, ...]
    function_values: tuple[float, ...]
    bounds: tuple[float, float]

    def __post_init__(self) -> None:
        probabilities = np.asarray(self.probabilities, dtype=float)
        values = np.asarray(self.function_values, dtype=float)
        bounds = np.asarray(self.bounds, dtype=float)
        if probabilities.ndim != 1 or probabilities.size == 0:
            raise ValueError("probabilities must be a nonempty one-dimensional table")
        if values.shape != probabilities.shape or not np.all(np.isfinite(values)):
            raise ValueError("function_values must be finite and match probabilities")
        if not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0):
            raise ValueError("probabilities must be finite and nonnegative")
        total = float(np.sum(probabilities))
        if not np.isclose(total, 1.0, atol=1e-12, rtol=0):
            raise ValueError("probabilities must sum to one (absolute tolerance 1e-12)")
        if bounds.shape != (2,) or not np.all(np.isfinite(bounds)):
            raise ValueError("bounds must contain two finite numbers")
        with np.errstate(over="ignore"):
            width = bounds[1] - bounds[0]
        if not np.isfinite(width) or width <= 0:
            raise ValueError("bounds must have positive finite width")
        if np.any(values < bounds[0]) or np.any(values > bounds[1]):
            raise ValueError("function_values violate bounds")
        # Remove only accepted round-off so NumPy and Qiskit use identical weights.
        object.__setattr__(self, "probabilities", tuple(float(p) for p in probabilities / total))
        object.__setattr__(self, "function_values", tuple(float(v) for v in values))
        object.__setattr__(self, "bounds", tuple(float(v) for v in bounds))

    @property
    def normalized_values(self) -> NDArray[np.float64]:
        """Return g_i=(f_i-a)/(b-a), without computing the expectation."""
        lower, upper = self.bounds
        return (np.asarray(self.function_values) - lower) / (upper - lower)

    @property
    def exact_expectation(self) -> float:
        """Direct summation is a validation reference, not an estimator input."""
        return float(np.dot(self.probabilities, self.function_values))

    def sample(self, rng: np.random.Generator, size: int) -> NDArray[np.float64]:
        """Return IID function values for the existing Monte Carlo callback API."""
        return rng.choice(self.function_values, size=size, p=self.probabilities)


def synthetic_call_payoff() -> DiscreteExpectation:
    """Undiscounted toy payoff max(S-110, 0); these are not market data."""
    terminal_values = (80.0, 100.0, 120.0, 140.0)
    return DiscreteExpectation(
        probabilities=(0.1, 0.2, 0.4, 0.3),
        function_values=tuple(max(value - 110.0, 0.0) for value in terminal_values),
        bounds=(0.0, 30.0),
    )
