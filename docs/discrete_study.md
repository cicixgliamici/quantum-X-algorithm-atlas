# Replicated discrete-payoff study

Protocol ID: `discrete-iqae-v1`. This fixed calibration design extends the
Bernoulli study without revising `mc-iqae-v1` or its historical seed mapping.
The protocol and tables are defined before observations are generated.

## Registered design

| Payoff | Probabilities | Function values | Declared bounds | Exact mean |
| --- | --- | --- | --- | --- |
| call | 0.1, 0.2, 0.4, 0.3 | 0, 0, 10, 30 | [0,30] | 13 |
| rare | 0.97, 0.02, 0.01 | 0, 10, 100 | [0,100] | 1.2 |
| signed | 0.2, 0.5, 0.3 | -10, -2, 6 | [-10,6] | -1.2 |
| constant_lower | 0.25, 0.75 | -5, -5 | [-5,15] | -5 |
| constant_upper | 0.25, 0.75 | 15, 15 | [-5,15] | 15 |

The three nonconstant payoffs each use normalized epsilon 0.1, 0.05 and 0.025.
The two constant controls each use epsilon 0.05. Every cell runs 200 independent
replications per method, alpha 0.05, 256 shots per IQAE circuit, and root seed
20261112: **11 cells, two methods, 4,400 planned attempts**. IQAE uses beta
confidence intervals and min_ratio=2. Classical sampling uses IID NumPy choice
with fixed Hoeffding budget `ceil(log(2/alpha)/(2*epsilon**2))`, at least two draws.
Exact expectations never tune the budget, stopping or function-encoding angles.

Any settings override, including classical-only execution, is labeled `pilot`.
This classification records design identity, not independent preregistration or
proof of statistical validity. Tables and settings are frozen in the source
snapshot and manifest before the first observation. Primary execution is separate
from the small CI pilot; there is no optional stopping based on observed coverage.

## Units and diagnostics

For declared bounds [a,b], the coherent oracle encodes each entry of
`g=(f-a)/(b-a)`. IQAE estimates E[g]; its estimate and both interval endpoints
are transformed by `a+(b-a)*value`. The absolute tolerance is `(b-a)*epsilon`.
Monte Carlo samples the original function values with that same absolute target.

Bias, RMSE, signed/absolute error and interval widths use **original payoff units**.
Success compares absolute error with the absolute target. Coverage tests the
original expectation against the original-unit interval. The call's epsilon
0.05 therefore means 1.5 payoff units, not 0.05 payoff units. Its normalized mean
must never be substituted for the exact expectation 13 during coverage analysis.

Each cell also records exact IID payoff variance. Figures use `sqrt(variance/N)`
as the analytical classical RMSE reference, rather than a Bernoulli variance.
The signed case tests a negative lower bound; the three-outcome cases test padded
index registers. Constant controls retain a positive declared range and are
reported separately from precision plots. Errors are not pooled across payoffs.

## Execute, reanalyze and report

```powershell
python -m qaa.benchmarks.discrete_study run --output results/discrete-study
python -m qaa.benchmarks.discrete_study analyze results/discrete-study
python -m qaa.benchmarks.scientific_report results/discrete-study --output results/discrete-study-report
```

For a quick pilot using every payoff and both controls:

```powershell
python -m qaa.benchmarks.discrete_study run --epsilons 0.1 --replications 2 --output results/discrete-pilot
python -m qaa.benchmarks.discrete_study run --epsilons 0.1 --replications 2 --classical-only --output results/discrete-classical
```

Output directories must be new. The optional `quantum` extra enables IQAE;
without it requested quantum trials remain explicitly unavailable. The optional
`report` extra enables HTML/Markdown and four PNG/SVG figures. Saved artifacts
can be reanalyzed and reported without quantum dependencies.

The shared [study runner](statistical_study.md) archives exact sources, environment,
input tables, per-trial seeds, JSONL records and SHA256 checksums. Each attempt
is flushed. Estimator failures are retained without retries; interruptions retain
unrecorded trials in planned denominators. Reanalysis verifies registered tables,
cells, seeds, source/raw checksums and recomputed accuracy flags. Reporting is
read-only and never invokes estimators. A changed saved table is rejected.

## Interpretation

Coverage and success include counts, completed-run denominators and 95% Wilson
intervals. A separate verified-success/planned fraction exposes unresolved trials.
There is no simultaneous multiple-cell confidence guarantee, and a small pilot
cannot establish nominal coverage. Below-target coverage and target misses are
completed estimations, distinct from execution failures.

These tiny explicit tables admit exact O(m) summation. Sampling and coherent
lookup are calibration tools here, not preferable ways to solve known tables.
The study validates encoding, rescaling and statistical behavior; it establishes
no practical quantum speedup. Logical gates, simulator shots and IID observations
remain separate costs; host timings are not hardware predictions. The next
scientific improvements are stronger classical baselines and structured reversible
oracles, rather than another algorithm family.
