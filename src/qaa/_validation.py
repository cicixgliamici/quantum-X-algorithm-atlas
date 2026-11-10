"""Shared scalar validation keeps public entry points consistent."""

import math
from numbers import Integral, Real


def positive_integer(value: int, name: str, minimum: int = 1) -> None:
    """Reject booleans and fractional counts instead of silently coercing them."""
    if isinstance(value, bool) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def probability(value: float, name: str = "probability") -> None:
    """Require a finite probability, including the deterministic endpoints."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number in [0, 1]")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite number in [0, 1]")


def validate_seed(seed: int | None) -> None:
    """None requests fresh entropy; integer seeds reproduce the same stream."""
    if seed is not None:
        positive_integer(seed, "seed", minimum=0)
