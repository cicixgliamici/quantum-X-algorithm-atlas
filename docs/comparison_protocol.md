# Monte Carlo / IQAE comparison protocol

Protocol ID: `mc-iqae-v1`. The design below fixes the comparison before further experiments. Current implementation support is listed in section 7.

## 1. Research question and scope

How does the cost of estimating the same bounded expectation change as the
required absolute error decreases, at a fixed probability of success?

Measure accuracy and logical resources separately from simulator runtime. The
study can investigate query scaling under explicit access assumptions. A practical
quantum advantage would additionally require a hardware and data-loading cost
model; it cannot be inferred from this simulation.

The first stage uses known Bernoulli probabilities to validate the comparison
procedure. The discrete extension now encodes a nontrivial finite expectation. Neither
stage includes MCMC, noise, error correction or the remaining algorithm families.

## 2. Common estimation task

Given a distribution P and a function f with declared finite bounds a < b, estimate
mu = E_P[f(X)]. Both methods must return a classical scalar in the original units.
Define g(x) = (f(x)-a)/(b-a), q = E_P[g(X)] and mu = a+(b-a)q.

For normalized tolerance epsilon, the common success event is

`abs(mu_hat - mu) <= (b-a)*epsilon`,

with required probability at least `1-alpha`. A constant function (a=b) is solved
exactly and treated as a deterministic control, outside scaling comparisons.
Absolute error, RMSE and confidence coverage are different quantities; none may
be substituted for another in the results.

| Contract | Classical Monte Carlo | Iterative amplitude estimation |
| --- | --- | --- |
| Access | IID draws X from P and classical evaluation of f(X) | Coherent A encoding q, A inverse, success and zero-state reflections |
| Estimate | Sample mean of f(X) | Estimated success amplitude mapped back to original units |
| Error target | Absolute error (b-a)*epsilon | Same absolute error after rescaling |
| Failure target | alpha | Same alpha |
| Primary resource | Number of IID observations N | Logical Grover applications and A/A-inverse calls |
| Additional costs | Sampling and function evaluation | Distribution loading, reversible evaluation, rotations and reflections |

This matches the mathematical output and accuracy contract, while exposing the
different access models. In the later discrete case, A must be constructed from
P and f, not from a precomputed answer q. Record loading and construction costs;
providing arbitrary coherent access for free is an assumption, not an achievement.
Compute the exact expectation separately as a validation baseline. For small
explicit inputs, also acknowledge that direct summation may be the best solver.

## 3. Algorithms and stopping rules

### Classical baseline

Use the existing sample mean with an IID sampler. Before drawing any samples, set

`N = max(2, ceil(log(2/alpha) / (2*epsilon**2)))`.

For normalized observations in [0,1], Hoeffding's bound gives the requested
absolute-error guarantee without knowing the variance. Report the interval
`[max(0, mean_g-h), min(1, mean_g+h)]`, where
`h = sqrt(log(2/alpha)/(2*N))`, and transform it to original units.

This is a conservative, distribution-independent baseline. It is not the optimal
classical sample complexity for every instance. Do not use the known analytical
variance to tune N after observing results. Report sample variance and standard
error as diagnostics, not as finite-sample confidence guarantees. Variance-adaptive
or Bernoulli-specific baselines require a separately labeled protocol extension.

### Quantum estimator

Use the existing Qiskit IQAE adapter with `epsilon_target=epsilon`, `alpha=alpha`
and 256 shots per sampled circuit. Keep the installed IQAE configuration fixed
across the primary study; record its confidence method and other defaults with
the package version. IQAE chooses Grover powers and stops adaptively using its
confidence interval. Never stop based on the known answer or rerun an unfavorable
seed. Preserve the returned interval and rescale it for a general bounded task.

Confidence claims rely on each method's assumptions. Analytical bounds and
finite empirical coverage measurements must appear as separate evidence.

## 4. Prespecified calibration design

| Parameter | Primary study specification |
| --- | --- |
| Bernoulli p | 0.1, 0.3, 0.5, 0.9 |
| Normalized epsilon | 0.1, 0.05, 0.025, 0.0125 |
| alpha | 0.05 per estimation run |
| Replications | 200 independent runs per method and (p, epsilon) cell |
| Quantum shots | 256 per circuit, fixed across cells |
| Root seed | 20261111 |
| Endpoint controls | p=0 and p=1, epsilon=0.05, same alpha and replications |

At alpha=0.05 the classical sample budgets are respectively 185, 738, 2952 and
11805. The primary grid has 16 cells and 6400 method runs; endpoint controls add
800 method runs. Endpoint controls are reported separately from scaling fits.

For reproducible independent streams, use NumPy SeedSequence with the root seed.
List cells with p outermost and epsilon innermost in the order above, then append
the two endpoint cells. Spawn one child per cell, then two children in method
order (classical, quantum), then 200 children in replicate order. Generate and
record one uint64 integer seed per replicate. Use persistent local RNG streams
within a run; do not restart measurement randomness at each IQAE iteration.
The current single-run CLI has a different seed mapping and does not implement
this study design.

Use independent streams across methods rather than assuming that equal integer
seeds create meaningfully paired observations. A smaller development run must be
labeled a pilot. Freeze the final design and source revision before executing
the primary study; changes require a new protocol revision with a rationale.

## 5. Resource and timing ledger

For circuit instance j with s_j shots and Grover power k_j, report:

- Classical observations: N, with sampling and f-evaluation costs stated.
- Sampled circuit instances: J, including repeated powers as separate instances.
- Simulator measurement draws: S = sum_j s_j.
- Logical Grover applications: G = sum_j s_j*k_j.
- Forward A calls: sum_j s_j*(k_j+1); inverse A calls: sum_j s_j*k_j.
- Combined A/A-inverse calls: S+2G, including initial A at k=0.
- Per-instance qubits, depth, gate count and measurements; maximum depth and
  shot-weighted logical gate total sum_j s_j*gate_count_j.

G and S+2G describe the circuits represented by the simulation. Actual hardware
oracle calls in this study are zero. Reflections remain part of the gate ledger;
do not call an A invocation, Grover iteration, shot and classical sample the same
unit. The initialization entry in Qiskit's power history is not an execution.

Keep the logical resource convention fixed: u/cx basis, optimization level 0,
gate counts excluding measurements and barriers, depth including measurements.
Report quantum resources per circuit and per shot-weighted run; circuit depth
alone is not a total execution cost. These logical counts have no hardware
connectivity or gate-duration model.

Distinguish setup/state-preparation construction, estimation, resource inspection
and total local wall time. Record which phases are included. The current classical
timer includes RNG creation, sampling, sample validation and reductions; its
scalar input validation is outside the timer. The quantum timer includes IQAE's
adaptive estimation, but excludes initial problem/sampler construction and
post-run circuit inspection. Existing timers therefore have different boundaries.
They are useful diagnostic measurements, not an end-to-end speed comparison.

Future total-cost measurements must include all required phases, identify one-time
versus repeated costs, and state any amortization assumptions. Do not interpret a
statevector simulator's implementation work as physical execution of every shot.

## 6. Analysis and reporting rules

Retain each run's estimate, interval, error, success indicator, seed, status,
resource ledger and timings. For each cell and method, report bias, RMSE, fraction
within epsilon, interval coverage, interval width, and resource median and 10th/90th
percentiles. Show accuracy and resources against epsilon on separate axes or
panels; never combine unlike cost units into a single unlabeled speedup ratio.

For empirical success and coverage rates, include 95% Wilson binomial intervals
over independent replications. These summarize uncertainty in the measured rate;
they are different from each estimator's nominal 95% interval. At R=200 and a true
rate of 0.95 the standard deviation of the measured rate is about 0.0154, so an
observed rate below 0.95 does not by itself refute the nominal guarantee.
The alpha target is per run, not a simultaneous guarantee over the whole grid.
Treat multiple-cell comparisons and slopes over four precision values as
descriptive, not proofs of asymptotic scaling or confirmatory hypothesis tests.

Record numerical failures, unavailable dependencies, timeouts and budget stops.
Do not silently discard or replace them. A resource/time cap must be declared
before a capped study; show completion rates and label summaries conditional on
completion. Incomplete runs cannot support an unconditional accuracy claim.

Archive raw records, protocol ID, ordered design, code revision (or source
snapshot), dependency versions, Python/platform, seed mapping and analysis commands.
The report must separate analytical guarantees, empirical simulation results and
unmeasured hardware costs. A result against the Hoeffding baseline alone is not
evidence of superiority over the best available classical method.

## 7. Current support and completion criteria

| Capability | Repository status |
| --- | --- |
| IID estimator and finite-shot IQAE calibration | Implemented |
| Single-run JSON, seeds, environment and core logical resources | Implemented |
| Accuracy/confidence/cost comparison contract | Specified by this protocol |
| Full grid and replication runner | Not yet implemented |
| Classical Hoeffding intervals | Implemented in the discrete runner |
| Coverage/RMSE aggregation and Wilson intervals | Not yet implemented |
| Separate A/A-inverse and weighted gate totals | Implemented |
| Discrete P/f preparation | Implemented |
| Preparation-cost study across input sizes | Implemented |
| Generated scientific report and plots | Future stage |

The full study is complete only when the grid is executed without selective
reruns, raw records and failures are retained, analysis is reproducible, accounting
identities are checked, and the report states the access assumptions and remaining
limits. Existing seeded correctness tests do not establish full-study coverage.

## 8. Runnable calibration check

After the README installation, run this single cell to check the implemented path:

```powershell
qaa-benchmark --probability 0.3 --sample-sizes 2952 --epsilon 0.025 --shots 256 --seed 20261111 --output results/protocol-calibration.json
```

This produces one run per method with the matched nominal accuracy/confidence
configuration (IQAE currently defaults to alpha=0.05). The classical interval is
defined above but not exported by the current CLI. The root seed here exercises
the existing CLI mapping, not the replicated design. A successful command
does not mean the full study ran or that every random run must meet the target.

See [mathematical background](mathematical_background.md) for the derivations and
primary algorithm references, and [architecture](architecture.md) for implemented
module boundaries.
