# Replicated Monte Carlo / IQAE calibration

The phase-4 runner implements protocol `mc-iqae-v1`: independent replications,
accuracy and confidence diagnostics, and separate distributions of logical costs.
The full default design has 7200 estimation attempts. Execution status and measured
results live in the generated manifest and summary, not in a hard-coded success
claim in this document. The [phase-5 report generator](scientific_report.md) creates
plots and a scientific report from the verified archive without new estimations.

## Frozen design

The primary grid has p=0.1,0.3,0.5,0.9 and epsilon=0.1,0.05,0.025,0.0125,
200 replications per method/cell, alpha=0.05 and 256 shots per IQAE circuit.
Two additional endpoint cells use p=0,1 and epsilon=0.05. Each method returns a
scalar estimate and an interval for the same Bernoulli probability.

Classical sampling uses NumPy's binomial generator with the precomputed Hoeffding
budget: 185, 738, 2952 or 11805 observations depending on epsilon. Its clipped
Hoeffding interval uses the same alpha as IQAE. This is a conservative baseline,
not an optimal Bernoulli-specific classical method. IQAE fixes the beta confidence
method and min_ratio=2 explicitly, with a persistent measurement RNG per run.

The seed tree follows the protocol exactly: root 20261111, cells in p-major order,
endpoint cells last, classical then quantum branches, then replicate children.
Each child produces one uint64 seed. Methods have independent streams; equal
replicate indices do not imply paired statistical observations.

Only the exact default settings receive classification `primary`. A changed
probability grid, precision, replication count, seed, alpha, shot count, omission
of controls or classical-only selection is labeled `pilot`. The cell kind `grid`
distinguishes non-endpoint cells even in a pilot. No pilot silently replaces the
registered study. The runner does not modify the separate discrete or oracle-cost
benchmark designs.

## Run and reanalyze

Install the quantum/dev extras from the README, then execute the full design:

```powershell
python -m qaa.benchmarks.statistical_study run --output results/statistical-study
python -m qaa.benchmarks.statistical_study analyze results/statistical-study
```

The run command refuses an existing output directory. Reanalysis reads saved
records and regenerates summaries without drawing new samples or invoking IQAE.
It verifies the source archive and finalized raw-log checksums. To repeat the
experiment, use a new output directory. Retain the original even if some attempts
failed. Restoring the archived source and recorded dependency versions in a
matching Python environment is necessary to replay that exact implementation.

A quick development pilot, including endpoints, is:

```powershell
python -m qaa.benchmarks.statistical_study run --probabilities 0.3 --epsilons 0.1 --replications 2 --output results/statistical-pilot
```

A classical-only run works without Qiskit:

```powershell
python -m qaa.benchmarks.statistical_study run --probabilities 0.3 --epsilons 0.1 --replications 2 --classical-only --output results/statistical-classical
```

Other controls are `--alpha`, `--shots`, `--seed` and `--no-endpoints`. Progress is
printed after each cell/method group. A nonzero exit code indicates unresolved
or failed planned estimations; numerical target misses are valid completed runs
and do not fail the command. Missing quantum extras produce explicit unavailable
records, rather than an invented measurement fallback.

## Artifacts and provenance

| Artifact | Purpose |
| --- | --- |
| manifest.json | Frozen design, cells, environment, IQAE settings, Git status and execution state |
| source/ | Byte-for-byte copy of project code, tests, documentation and configuration before trials |
| source-files.json | Per-file SHA256 hashes and combined source inventory digest |
| trials.jsonl | One record per attempted estimation, flushed immediately |
| summary.json | Recomputable cell/method statistics linked to source and raw-log digests |

Every completed raw record retains cell ID, kind, method, replicate, seed,
probability, epsilon, alpha, estimate, interval, signed/absolute error, success and
coverage flags, costs, timings and complete estimator diagnostics. IQAE diagnostics
include the sampled powers and per-circuit resource counts. There is no pooling of
classical observations, simulator shots and Grover queries into a shared cost unit.

Failures retain their seed, design, exception type/message and attempted wall time.
Seeds are never retried. Ctrl+C preserves already flushed records and marks the
manifest interrupted; reanalysis counts unrecorded trials explicitly. There is no
automatic resume or deadline/resource cap. A forced process termination may leave
the state marked running or a partial final JSON line; malformed records are
reported as errors and are never silently discarded. Checksums detect accidental
changes, not malicious replacement of an entire archive.

The archive covers source inputs and records all installed package versions, including
transitive dependencies; it does
not vendor third-party dependencies. Local Git changes are included in the source
copy and recorded in the manifest. Generated results are excluded from that copy.

## Statistical definitions and denominators

For each cell and method, report:

- Bias: mean of estimate-p over completed runs.
- RMSE: sqrt(mean((estimate-p)^2)), distinct from mean absolute error.
- Success: fraction with abs(estimate-p)<=epsilon.
- Coverage: fraction whose reported confidence interval contains p, endpoints included.
- Absolute error and interval-width distributions: min, q10, median, q90 and max.
- Resource and timing distributions with the same explicitly linear quantiles.
- Planned, attempted, completed, failed, unavailable and not-recorded counts.

Success and coverage fractions include 95% Wilson binomial intervals across
independent replications. These describe uncertainty in the empirical rate and
are separate from each estimator's confidence interval. The nominal success/
coverage target is 1-alpha; an observed rate below that target does not alone
prove an implementation error. With 200 replications the measured rate is still
uncertain, and no simultaneous coverage guarantee is claimed over the full grid.

Accuracy and cost summaries are labeled conditional on completion. Completion
uses the planned replication count as denominator. The separate verified-success
fraction divides observed successes by planned runs; unresolved outcomes are not
assumed successful. It is a conservative observed fraction, not a statistical
lower confidence bound. With no completed runs, accuracy quantities are null,
not zero. Unavailable, failed and missing attempts cannot create an unconditional
accuracy claim by disappearing from the denominator.

Reanalysis rejects unknown/duplicate trial IDs, seed/design mismatches, invalid
intervals and accuracy flags inconsistent with the saved estimate. Endpoint
controls remain separate. Summaries describe each cell; they do not fit a slope
over four precision values or establish asymptotic scaling.

## Interpretation limits

This experiment encodes known Bernoulli probabilities for calibration. It tests
the estimators and resource accounting, rather than discovering unknown input
data. It does not establish that hardware can prepare the necessary oracles
cheaply. Use the separate [oracle-cost study](oracle_cost.md) for that construction.

Timing distributions are descriptive host measurements without controlled warmups
or randomized execution order. `estimation_seconds` retains each estimator's
existing boundary; quantum resource inspection has its own timer. `run_wall_seconds`
covers estimator invocation, result extraction and validation, excluding raw-log
writing. Method order is fixed by the seed protocol. No simulator timing ratio is
a practical quantum speedup claim. See the [comparison protocol](comparison_protocol.md)
for access assumptions and the distinction between costs and confidence claims.
