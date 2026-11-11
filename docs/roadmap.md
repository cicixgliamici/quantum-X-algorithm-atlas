# Research roadmap

Only the first case study is implemented. These are questions for future work,
not promises that useful quantum acceleration exists for every family.

| Classical family | Status and research question |
| --- | --- |
| Monte Carlo / Metropolis | IID Monte Carlo, Bernoulli IQAE and discrete expectation encoding; MCMC deferred |
| Simplex | Deferred: compare optimization models and input assumptions |
| Krylov subspace methods | Deferred: investigate linear-system access and output costs |
| Matrix decompositions | Deferred: distinguish classical outputs from quantum states |
| Optimizing compilers | Deferred: define a precise optimization problem first |
| QR eigenvalue algorithm | Deferred: compare spectral tasks and readout requirements |
| Quicksort | Deferred: examine comparison bounds and data access |
| Fast Fourier Transform | Deferred: distinguish QFT states from explicit Fourier coefficients |
| Integer relation detection | Deferred: identify a defensible quantum research question |
| Fast Multipole Method | Deferred: compare approximation, geometry and data-loading costs |

The [comparison protocol](comparison_protocol.md) now fixes the estimation task,
accuracy/confidence contract, cost ledger and replicated calibration design.
The statistical-study runner and raw-record reanalysis implement this design.

The [discrete expectation case study](discrete_expectation.md) now prepares a
nontrivial bounded function and finite distribution coherently, with a direct-sum
validation reference and a matched single-run comparison.

The [oracle-cost study](oracle_cost.md) now measures preparation/inverse, function
encoding, reflections and full Grover costs across increasing table sizes,
including optional shot-weighted IQAE workloads.

The [replicated study](statistical_study.md) now implements independent Bernoulli
replications, RMSE, empirical success/coverage with Wilson intervals, cost
distributions, retained failures and source-linked raw records.

The [scientific report generator](scientific_report.md) now exports English HTML
and Markdown, standalone PNG/SVG figures, numerical tables and reporting provenance
from verified study artifacts, with optional separate oracle-cost results.

The [discrete replication study](discrete_study.md) now implements coverage and
original-unit accuracy across call, rare-event and signed payoffs plus controls.
Next scientific questions include stronger classical confidence baselines and
structured reversible function evaluation. Hardware/noise studies should follow a
defensible cost model. Each later
case study needs classical references, analytical examples and documented limits
before generalized framework abstractions are introduced.
