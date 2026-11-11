# Research roadmap

Only the first case study is implemented. These are questions for future work,
not promises that useful quantum acceleration exists for every family.

| Classical family | Status and research question |
| --- | --- |
| Monte Carlo / Metropolis | IID Monte Carlo, Bernoulli IQAE and discrete expectations; MCMC deferred |
| Simplex | Deferred: compare optimization models and input assumptions |
| Krylov subspace methods | Deferred: investigate linear-system access and output costs |
| Matrix decompositions | Deferred: distinguish classical outputs from quantum states |
| Optimizing compilers | Deferred: define a precise optimization problem first |
| QR eigenvalue algorithm | Deferred: compare spectral tasks and readout requirements |
| Quicksort | Deferred: examine comparison bounds and data access |
| Fast Fourier Transform | Deferred: distinguish QFT states from explicit Fourier coefficients |
| Integer relation detection | Deferred: identify a defensible quantum research question |
| Fast Multipole Method | Deferred: compare approximation, geometry and data-loading costs |

Next scientific milestone: a nontrivial bounded expectation with explicit coherent
state preparation and function evaluation, then repeated-trial accuracy and query
budgets. Hardware/noise studies should follow a defensible cost model. Each later
case study needs classical references, analytical examples and documented limits
before generalized framework abstractions are introduced.

The [comparison protocol](comparison_protocol.md) defines matched absolute-error and confidence targets, access assumptions, cost units and a prespecified replication design.

The [discrete expectation case study](discrete_expectation.md) adds a four-scenario synthetic payoff with exact expectation 13. Its quantum circuit encodes individual distribution/function entries; the exact weighted mean is only a validation reference.

The [oracle-cost study](oracle_cost.md) inspects loading, function encoding, A, A inverse, reflections and Grover circuits as table sizes grow. Logical gate totals are weighted by shots, with construction and inspection times separated.

The [replicated study](statistical_study.md) implements the 7200-trial protocol with independent seeds, retained failures, raw JSONL records, source snapshots, RMSE, success/coverage Wilson intervals and cost distributions. Run status lives in each manifest.
