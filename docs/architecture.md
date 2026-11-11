# Architecture and engineering decisions

The src layout prevents accidental imports from the repository root. Setuptools
provides editable installs and a benchmark entry point. NumPy is the only base
runtime dependency; Qiskit is an extra so classical work remains lightweight.
Pure validation helpers, short functions and immutable result dataclasses keep
the code reviewable without introducing a plugin framework prematurely.

The classical callback receives an explicit Generator and sample count, returning
scalar observations of the integrand. The caller owns the distribution and must
ensure IID sampling. A seed creates a local RNG, without changing global state.
Variance uses Bessel's correction; standard error is the estimated standard
deviation of the sample mean. Timings exclude input validation.

The quantum module builds either one-qubit Bernoulli A or a discrete table-based A,
delegates estimation to the shared IQAE runner,
then inspects the circuits used at each Grover power. The first element of Qiskit's
powers history is initialization, not an executed circuit. Each subsequent element
represents a circuit execution with the configured shots. Query accounting is
checked against Qiskit's result in tests. Repeated powers remain separate executions.

`problems/discrete.py` owns validated immutable input tables, normalization and the
direct-sum reference without importing Qiskit. The quantum discrete adapter loads
the distribution unitarily and uses controlled rotations for function values;
its estimator does not access the reference expectation. Results preserve both
normalized diagnostics and original-unit estimates. The classical callback uses
the same problem's IID sampler. A separate discrete benchmark applies matched
Hoeffding/IQAE targets without changing the existing Bernoulli CLI or seed mapping.

`quantum/resources.py` provides one u/cx decomposition convention for both IQAE
and profiling. The discrete builder exposes P, F, A, A inverse and reflections;
the IQAE circuit and oracle-cost profiler use these same components. The profiler
compiles fixed-power circuits without sampling; its optional single IQAE run is
kept as a separate workload. `benchmarks/oracle_cost.py` owns size-specific seeds,
input generation and versioned JSON exports. This is a resource study, not the
replicated accuracy study or a hardware performance model.

The replicated Bernoulli study separates `study_design.py` (registered cells and
seed tree), `study_statistics.py` (pure descriptive statistics and denominators),
`study_archive.py` (source snapshots/checksums), and `statistical_study.py` (execution
and raw-record reanalysis). Each attempt is flushed before continuing. Estimator
exceptions become explicit failed/unavailable records; a missing record remains
unresolved. Reanalysis never invokes an estimator or invents observations.

The read-only `read_study` path also serves reporting. `scientific_report.py`
verifies inputs, archives the reporting source and orchestrates export.
`report_sections.py` owns shared narrative/tables, `report_figures.py` owns static
Matplotlib plots, and `report_rendering.py` renders the same content to Markdown
and self-contained HTML. The optional report dependency does not enter estimation
modules. Report provenance distinguishes the original study from the current
generator; the saved dataset is never rewritten during reporting.

The benchmark writes a versioned JSON record. It uses child SeedSequence streams
for classical sizes, records their integer seeds, and uses the requested seed for
QAE. Runtime algorithm errors propagate; only an absent quantum extra is optional.
Wall-clock values should not be compared as evidence of quantum acceleration.

CI runs format, lint, tests and a real quantum benchmark over supported Python
versions, plus a separate environment with no quantum dependencies. Statistical
checks use fixed seeds and analytical or generous ensemble tolerances. CI is
configured here; its remote execution is distinct from local verification.

Extension rule: introduce a new module only when the next case study needs it.
Share result fields or interfaces only after their mathematical meanings match.
Avoid forcing matrix algorithms or compilers into a Monte Carlo-shaped API.
