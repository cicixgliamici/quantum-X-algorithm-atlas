# Quantum Algorithm Atlas

A research and scientific software project investigating influential classical
algorithms and their possible quantum counterparts. The goal is to make the
mathematics, implementations and limitations easy to inspect and reproduce.
An asymptotic query advantage does not by itself establish a practical speedup.

## MVP 0: one case study

Implemented: independent Monte Carlo for bounded observations, a known Bernoulli
calibration problem, a finite-distribution expectation with coherent function
encoding, and genuine **Iterative Quantum Amplitude Estimation (IQAE)**
using Qiskit Algorithms and its V2 `StatevectorSampler`. Tests, JSON benchmarks
and GitHub Actions accompany the code. The other nine algorithm families remain
research directions; no placeholder implementations imply completed work.

## Installation

Requires Python 3.11+ (CI covers 3.11–3.14). From the repository root, on PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,quantum,report]'
```

On Linux/macOS activate with `source .venv/bin/activate` instead. Activation is
optional if commands use the virtual environment's executable directly.
The base install `python -m pip install -e '.[dev]'` needs only NumPy at runtime;
quantum tests skip and the benchmark reports `unavailable` without the quantum
extra. It never substitutes ordinary measurements and labels them as QAE.
Statevector simulation is supplied by Qiskit itself, so Aer is unnecessary.
The optional `report` extra adds Matplotlib for static scientific figures. Saved
studies can be reported with `.[dev,report]` without installing quantum packages.

## Reproduce and verify

```powershell
python -m pytest
ruff check .
ruff format --check .
python experiments/monte_carlo_demo.py
qaa-benchmark --seed 42 --sample-sizes 100 1000 10000 --output results/monte_carlo.json
qaa-benchmark --classical-only --output results/classical.json
python -m qaa.benchmarks.monte_carlo --probability 0.3 --shots 256 --epsilon 0.03
python -m qaa.benchmarks.discrete_expectation --epsilon 0.03 --alpha 0.05 --output results/discrete-expectation.json
python -m qaa.benchmarks.oracle_cost --with-estimation --output results/oracle-cost.json
python -m qaa.benchmarks.statistical_study run --output results/statistical-study
python -m qaa.benchmarks.statistical_study analyze results/statistical-study
python -m qaa.benchmarks.scientific_report results/statistical-study --oracle-study results/oracle-cost.json --output results/scientific-report
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

The [Monte Carlo / IQAE comparison protocol](docs/comparison_protocol.md) specifies
matched accuracy and confidence targets, classical sample budgets, quantum access
assumptions and resource accounting. The [replicated study](docs/statistical_study.md)
implements its 7200-trial design with raw JSONL records, RMSE, success, coverage,
Wilson intervals and cost distributions. Each run archives its source and environment;
execution status lives in its manifest. The original benchmark remains single-run.

The [discrete expectation case study](docs/discrete_expectation.md) adds a synthetic
four-scenario payoff (exact expectation 13), explicit distribution/function encoding,
and a single-run comparison with matched Hoeffding/IQAE accuracy targets.

The [replicated discrete-payoff study](docs/discrete_study.md) extends calibration
to call, rare-event and signed payoffs, with separate constant controls. Its fixed
4,400-attempt design reports error and coverage in original payoff units, archives
input tables, and exports a dedicated scientific report through the same generator.

```powershell
python -m qaa.benchmarks.discrete_study run --output results/discrete-study
python -m qaa.benchmarks.discrete_study analyze results/discrete-study
python -m qaa.benchmarks.scientific_report results/discrete-study --output results/discrete-study-report
```

The [oracle-cost study](docs/oracle_cost.md) profiles loading, function encoding,
preparation/inverse, reflections and Grover gates as table sizes grow. Fixed-power
probes separate size effects from IQAE's adaptive workload; optional estimation
records shot-weighted logical gate costs and separate timing phases.

The [scientific report generator](docs/scientific_report.md) produces standalone
HTML, Markdown, PNG/SVG figures and numerical tables from verified saved data.
It records reporting provenance separately and leaves the original study unchanged.
Study and report output directories must be new; use a different `--output` for repeats.

## Scientific limits

The Bernoulli probability is **known and encoded deliberately**: this tests state
preparation and IQAE, not the discovery of an unknown probability. The discrete
extension encodes individual probabilities and function values instead of the
weighted mean; exact summation supplies an independent validation reference.
Both examples use known synthetic inputs. Metropolis–Hastings
and correlated MCMC are outside MVP 0.

Quantum timings cover ideal finite-shot simulation and estimation, excluding
post-run resource inspection, which now has its own timer. Discrete estimates
also expose construction and total wrapper time. These are not hardware timings. Classical timings
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
