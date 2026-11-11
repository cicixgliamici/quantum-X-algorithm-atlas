# Cost of explicit discrete oracles

Study ID: `discrete-oracle-cost-v1`. This problem-size study measures the quantum
circuits already used by the discrete expectation estimator. It does not assume
that coherent distribution loading or a Grover query has unit gate cost.

## Question and controlled design

How much does one preparation or Grover application cost as the number of table
entries m grows? How do those costs accumulate over a finite-shot workload?

The default sizes are 2, 4, 8 and 16. Each table contains positive irregular
probabilities and normalized function entries strictly between 0.05 and 0.95.
Generate weights uniformly in [0.1,1), normalize them, then generate function
entries uniformly in [0.05,0.95). These are dense synthetic lookup problems,
chosen to avoid uniform-state and zero-payoff shortcuts. They are not refinements
of a single continuous distribution or a representative sample of all inputs.

With root seed 42, derive two SeedSequence children from `[root_seed, m]`:
one for input generation and one for optional IQAE. Record their generated
uint32 seeds and the complete input tables. Adding or reordering sizes preserves
each size's inputs and random stream. Non-power-of-two sizes are also supported;
the output records both actual and padded table sizes.

## Components inspected

| Component | Meaning |
| --- | --- |
| distribution_loading P | Unitary preparation of sqrt(p_i) on index qubits |
| function_encoding F | Index-controlled objective rotations for each g_i |
| state_preparation A | P followed by F on the full register |
| inverse_state_preparation | The actual inverse of A, inspected independently |
| success_reflection | Z on the objective qubit |
| zero_reflection | I-2\|0><0\| on the full register |
| grover_operator Q | Success reflection, A inverse, zero reflection, A, with global phase |

These are the same components supplied to IQAE, not alternative simplified
resource proxies. The zero reflection is explicit and matches Qiskit's default
construction. Its global phase convention is handled by the Grover builder.
P acts on fewer qubits than A; all full-workload qubit counts include the objective.

All components and full probe circuits are transpiled to `u` and `cx`, with
optimization level 0 and transpiler seed 0. Record qubits, depth, one-qubit gates,
two-qubit gates, total gates, measurements and the operation histogram.
Total gates are u+cx; barriers and measurements are excluded. Depth includes
measurements where present. There is no hardware coupling map, native-gate model,
gate-duration model or fault-tolerant synthesis of arbitrary rotations.

This common basis makes composite gates visible, but does not make gate costs
hardware independent. Compiler/version changes may alter results even when the
prepared mathematical state is unchanged. Never infer physical runtime by
multiplying these counts by an unspecified gate duration.

## Fixed-power probes and optional estimation

For each size, compile measured `A` followed by `Q^k` for k=0,1,2,4. The default
probe workload models 256 shots per circuit. No sampler executes these probes.
The JSON explicitly records `sampler_executions=0` for this profiling stage.

For k and modeled shot count s, the workload ledger is:

- Grover queries: s*k.
- Forward A calls: s*(k+1); inverse A calls: s*k.
- Logical gate applications: s times the full probe's decomposed gate count.
- One- and two-qubit gate applications: their corresponding shot-weighted counts.

Report the additive component model separately:

`s*((k+1)*C_A + k*C_A_inverse + k*(C_success + C_zero))`.

The directly compiled full circuit is the primary gate count. A sum of separately
compiled components is a model; do not assume it equals whole-circuit synthesis
for every input or compiler. Component depths are not additive execution times.
Probes at different powers are separate hypothetical workloads, not a prescribed
IQAE schedule, and their totals must not be added to an IQAE run's costs.

With `--with-estimation`, run one actual finite-shot IQAE estimation per size,
with epsilon=0.05, alpha=0.05 and 256 shots per adaptive circuit by default.
Its record includes the actual chosen powers, sampled shots, forward/inverse
preparation calls, shot-weighted logical gates and maximum sampled-circuit depth.
IQAE's adaptive workload may differ across sizes because the encoded probabilities
and measurement outcomes differ. Use the fixed-power probes to isolate size
effects; do not infer a precision-scaling law from these four single IQAE runs.

## Timing boundaries

The structural study separates input-table generation, component construction,
component inspection (transpilation), and probe construction plus inspection.
Construction builds Python circuit descriptions; synthesis is charged to
inspection. It is not a measurement of physical state-preparation duration.

Discrete IQAE results separately report `problem_construction_seconds`, the nested
`amplitude_result.elapsed_seconds` for estimation, nested
`resource_inspection_seconds`, and `total_elapsed_seconds` for the estimator wrapper.
The total includes construction, estimation, inspection and wrapper processing.
The reference expectation and benchmark serialization are outside that wrapper.
The study-level total includes its profiling and optional estimation loop and
in-process dependency discovery, but excludes JSON writing and interpreter startup.

Each optional estimation constructs its own problem and inspects its own adaptive
circuits. Those costs are recorded in its own timing fields. They do not reuse
the structural profiler's work or represent a deployment amortization model.
Times are descriptive host measurements without repeated trials or warmup
controls; shot-weighted logical gates do not measure simulator implementation work.

## Reproduce

Install the quantum/dev extras described in the README, then run:

```powershell
python -m qaa.benchmarks.oracle_cost --output results/oracle-cost-structural.json
python -m qaa.benchmarks.oracle_cost --sizes 2 4 8 16 --with-estimation --output results/oracle-cost.json
python -m qaa.benchmarks.oracle_cost --sizes 3 5 --powers 0 1 3 --shots 128 --output results/oracle-cost-padded.json
```

JSON records include design, complete inputs, seeds, compiler convention,
environment, component metrics, probe ledgers and optional IQAE diagnostics.
Without quantum extras the command reports `unavailable` and no result rows.
Unexpected construction, compilation and estimation failures propagate. This
study does not silently omit failed sizes or replace their seeds.

## Observed example

The second command above was executed on Python 3.14.3 with Qiskit 2.6.2 and
Qiskit Algorithms 0.4.0, root seed 42. These are measured logical circuit costs:

| Outcomes m | Full qubits | P gates | F gates | A gates | A inverse gates | Q gates | Q cx gates | Q depth |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 2 | 1 | 10 | 11 | 11 | 30 | 9 | 23 |
| 4 | 3 | 4 | 100 | 104 | 104 | 232 | 72 | 156 |
| 8 | 4 | 11 | 464 | 475 | 475 | 992 | 342 | 700 |
| 16 | 5 | 26 | 1088 | 1114 | 1114 | 2346 | 826 | 1533 |

Even with logarithmically growing register width, the explicit lookup encoding
requires substantially more gates. The function-encoding component dominates A
in these examples. Counting one Q as one operation would hide this cost.
The table is an environment-specific observation, not an asymptotic lower bound
or a universal growth law. The measurements are not hardware executions.

The exact expectation is still cheaply available by O(m) direct summation.
Neither this construction nor a reduction in logical query count establishes
advantage over that baseline or over classical Monte Carlo. Any future claim
must account for classical input access, quantum loading/reflections, error
correction, output requirements and the actual hardware cost model.

This implements the preparation-cost stage of the roadmap. The
[replicated Bernoulli study](statistical_study.md) now analyzes accuracy/coverage
and logical cost distributions. The [scientific report generator](scientific_report.md)
can include this oracle study as a separate section and static figure.
See the [comparison protocol](comparison_protocol.md) and
[discrete expectation case study](discrete_expectation.md).
