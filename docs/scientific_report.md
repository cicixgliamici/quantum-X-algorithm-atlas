# Reproducible scientific report

The phase-5 generator turns a saved replicated study into one scientific report
with static figures, numerical tables, primary references and explicit limitations.
It verifies source and raw-log hashes, recomputes the summary in memory, and reads
the input archive without rewriting it. No estimator or sampler is invoked.

## Install and generate

Matplotlib is an optional reporting dependency. Existing study artifacts can be
reported without Qiskit installed:

```powershell
python -m pip install -e '.[dev,report]'
python -m qaa.benchmarks.scientific_report results/statistical-study --oracle-study results/oracle-cost.json --output results/scientific-report
```

This command consumes the outputs from phases 3 and 4. `--oracle-study` is optional:

```powershell
python -m qaa.benchmarks.scientific_report results/statistical-pilot --output results/pilot-report
python -m qaa.benchmarks.scientific_report results/statistical-classical --output results/classical-report
```

The output directory must be new. To regenerate, choose another directory; input
archives and prior reports remain intact. Raw checksums and trial/seed identities
are checked before writing a report. A malformed or corrupted dataset fails
explicitly; a valid incomplete dataset is reported with its actual denominators.
Classification follows the verified study design, so a pilot never becomes a
primary result by changing a report label.

## Delivered artifacts

| Artifact | Purpose |
| --- | --- |
| report.html | Standalone English report, with all figures embedded as PNG data |
| report.md | Same sections and numerical tables, with relative PNG links |
| figures/*.png | Raster figures at 180 dpi for review and sharing |
| figures/*.svg | Vector versions with stable identifiers and no creation timestamp |
| data/summary.json | Freshly recomputed cell statistics at full numerical precision |
| data/study-manifest.json | Original experiment design, settings and environment |
| data/oracle-cost.json | Byte-for-byte optional oracle-cost input |
| source/ and source-files.json | Archived reporting source and its per-file inventory |
| report-manifest.json | Input digests, reporting environment, generator provenance and output hashes |

The HTML can be copied on its own for reading. Copy the full report directory to
retain the Markdown figures, vector exports, machine-readable data and generator
source. The bundle does not duplicate the full trial log or original study source
archive; retain the phase-4 dataset to independently regenerate statistics.
The study source hash and reporting source hash identify different roles. The
report records its own installed package versions, independently of the original
simulation environment. Restoring matching versions is necessary for byte-identical
rendering; different Matplotlib/font/backend versions may change image output.

## Report content and figure conventions

The report separates run completeness, empirical findings, methods/theory,
estimation error, success/coverage, endpoint controls, resource distributions,
diagnostic timings, optional oracle construction, limitations and provenance.
Tables for accuracy and confidence are separate to keep each quantity readable.
Numbers in tables are rounded; the JSON retains full precision.

- **RMSE:** one panel per grid probability, excluding endpoints. Empirical RMSE,
  exact IID Bernoulli Monte Carlo RMSE at the actual fixed budget, and an epsilon
  reference are distinct curves. Both axes use logarithmic scales. Zero RMSE is
  omitted from the log plot and retained in the table. No complexity exponent is fit.
- **Success and coverage:** separate figures with 95% Wilson intervals over
  independent replications. A dashed line marks 1-alpha. Vertical axes may be
  zoomed with explicit ticks; small fixed horizontal display offsets reveal
  coincident methods without changing the numerical precision targets.
- **Resources:** separate panels for IID samples, simulator draws, Grover calls,
  combined forward/inverse preparation calls, logical gate applications and maximum
  depth. Bars show 10th–90th percentiles around the median, not confidence intervals.
  Linear count axes preserve zero queries. Probability series have small fixed
  horizontal display offsets to keep coincident workloads visible.
- **Optional oracle costs:** a separate dense-table size experiment, with loading,
  function encoding, preparation, inverse and Grover costs. Its input is validated
  against the u/cx, optimization-level-0 convention, copied and hashed. It is not
  merged into the Bernoulli replication grid or treated as a free oracle.

Empty or incomplete completed subsets have no empirical accuracy claim. Status
tables retain failures, unavailable dependencies and missing records. Endpoint
controls remain separate; no confidence guarantee is pooled across cells. Timing
tables retain their method-specific boundaries and are labeled diagnostic.

## Engineering and verification

`read_study` verifies and recomputes in memory; `analyze_study` remains the separate
command that intentionally writes the saved summary. Reporting uses the read-only
path. `report_sections.py` supplies one semantic document and formatted tables to
both renderers; `report_figures.py` plots the same verified numerical summary.
`report_rendering.py` escapes content and embeds images without JavaScript or
network resources. Matplotlib uses the noninteractive Agg backend and a writable
temporary cache, respecting an explicitly configured MPLCONFIGDIR.

Tests check plotted values against the recomputed statistics, bit-for-bit exports
in the same environment, checksum consistency, read-only inputs, absence of
estimator calls, corrupted inputs, incomplete studies and separate oracle records.
Figures are also visually inspected before delivering the primary report.
CI generates a pilot report and a classical-only report; it does not rerun the
7200-trial design on every push.

The report supports scientific review of calibration and resource assumptions.
It does not establish hardware advantage, optimality against all classical methods,
or useful quantum acceleration for the other nine algorithm families.
