# Quantum Algorithm Atlas

A research and scientific software project investigating influential classical
algorithms and their possible quantum counterparts. The goal is to make the
mathematics, implementations and limitations easy to inspect and reproduce.
An asymptotic query advantage does not by itself establish a practical speedup.

## MVP 0: one case study

Implemented: independent Monte Carlo for bounded observations, a known Bernoulli
calibration problem, and genuine **Iterative Quantum Amplitude Estimation (IQAE)**
using Qiskit Algorithms and its V2 `StatevectorSampler`. Tests, JSON benchmarks
and GitHub Actions accompany the code. The other nine algorithm families remain
research directions; no placeholder implementations imply completed work.

## Installation

Requires Python 3.11+ (CI covers 3.11–3.14). From the repository root, on PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,quantum]'
```

On Linux/macOS activate with `source .venv/bin/activate` instead. Activation is
optional if commands use the virtual environment's executable directly.
The base install `python -m pip install -e '.[dev]'` needs only NumPy at runtime;
quantum tests skip and the benchmark reports `unavailable` without the quantum
extra. It never substitutes ordinary measurements and labels them as QAE.
Statevector simulation is supplied by Qiskit itself, so Aer is unnecessary.

## Reproduce and verify

```powershell
python -m pytest
ruff check .
ruff format --check .
python experiments/monte_carlo_demo.py
qaa-benchmark --seed 42 --sample-sizes 100 1000 10000 --output results/monte_carlo.json
qaa-benchmark --classical-only --output results/classical.json
python -m qaa.benchmarks.monte_carlo --probability 0.3 --shots 256 --epsilon 0.03
```

The benchmark records Python/package/platform versions, all seeds, estimates,
absolute errors, times, sample counts, quantum confidence intervals, shot counts,
logical Grover queries, and per-execution circuit resources. Seeds reproduce
numerical results in the same environment; elapsed times are not reproducible.
To archive an exact local dependency snapshot:

```powershell
python -m pip list --format=freeze --exclude quantum-algorithm-atlas > results/environment.txt
```

Compatible dependency ranges live in `pyproject.toml`. For exact repeat studies,
archive the JSON report and environment snapshot together; reinstall the snapshot
in a matching Python/platform environment, then install this repository separately.
Editable sources are excluded because an uncommitted repository has no immutable
Git revision; archive the source or record its commit as well. This is not a
cross-platform lockfile.

## API example

```python
from qaa.classical.monte_carlo import estimate_expectation

result = estimate_expectation(
    lambda rng, n: rng.uniform(size=n) ** 2,
    10_000,
    bounds=(0.0, 1.0),
    seed=42,
)
print(result.estimate, result.standard_error)  # Analytical expectation: 1/3.
```

The callback returns **independent scalar function values**, allowing arbitrary
sampling distributions and bounded integrands. Bounds are checked on observations;
neither global boundedness nor independence can be proved from samples. The MVP
uses one in-memory array and requires at least two observations for variance.

## Architecture

`src/qaa/classical` owns IID estimators; `src/qaa/quantum` owns the optional Qiskit
adapter; `src/qaa/benchmarks` combines structured dataclass results into JSON.
There is no shared abstraction that equates classical samples with oracle queries.
`tests` checks analytical identities, seeded convergence, circuits, IQAE and exports.
`experiments` contains the runnable case study, with theory in `docs`.

See [architecture](docs/architecture.md), [mathematical foundations](docs/mathematical_background.md)
and the [ten-algorithm roadmap](docs/roadmap.md).

## Scientific limits

The Bernoulli probability is **known and encoded deliberately**: this tests state
preparation and IQAE, not the discovery of an unknown probability. Both methods
solve a synthetic calibration problem with an analytical answer. Metropolis–Hastings
and correlated MCMC are outside MVP 0.

Quantum timings cover ideal finite-shot simulation and estimation, excluding
post-run resource inspection. They are not hardware timings. Classical timings
cover sampling and statistical reductions. These timings cannot establish an
end-to-end quantum advantage. State preparation, inverse preparation, success
reflections, noise, compilation and hardware access require separate cost models.
Gate counts are logical u/cx decompositions at optimization level 0, excluding
measurements and barriers; depth includes measurements. No backend topology is assumed.

Monte Carlo RMSE scales as O(N^-1/2). Ideal amplitude estimation can reach additive
error epsilon in O(1/epsilon) coherent oracle queries at fixed success probability;
IQAE has additional confidence-related logarithmic overhead. This relies on
coherent access to A, its inverse and success reflections. Simulator shots and
logical query counts are different accounting units.

The implementation follows the official
[IQAE API](https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.IterativeAmplitudeEstimation.html)
and [result contract](https://qiskit-community.github.io/qiskit-algorithms/stubs/qiskit_algorithms.IterativeAmplitudeEstimationResult.html).
Future work should evaluate nontrivial loading/oracles and repeated-trial resource
studies before discussing practical advantage. Licensed under [MIT](LICENSE).

## Research milestones

The [comparison protocol](docs/comparison_protocol.md) defines matched absolute-error and confidence targets, access assumptions, cost units and a prespecified replication design.

The [discrete expectation case study](docs/discrete_expectation.md) adds a four-scenario synthetic payoff with exact expectation 13. Its quantum circuit encodes individual distribution/function entries; the exact weighted mean is only a validation reference.

```powershell
python -m qaa.benchmarks.discrete_expectation --output results/discrete.json
```
