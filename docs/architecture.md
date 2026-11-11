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

The quantum module builds one-qubit A, delegates estimation to maintained IQAE,
then inspects the circuits used at each Grover power. The first element of Qiskit's
powers history is initialization, not an executed circuit. Each subsequent element
represents a circuit execution with the configured shots. Query accounting is
checked against Qiskit's result in tests. Repeated powers remain separate executions.

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

The immutable `problems/discrete.py` tables are shared by the classical sampler and the quantum discrete adapter. A shared IQAE runner preserves normalized diagnostics while the discrete result restores original units.

`quantum/resources.py` fixes a common u/cx decomposition. The discrete builder exposes P, F, A, A inverse and reflections to both IQAE and the oracle profiler. Fixed-power probes are compiled without sampling; optional IQAE is a separate workload.
