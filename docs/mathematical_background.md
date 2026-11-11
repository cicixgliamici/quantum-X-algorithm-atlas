# Monte Carlo and amplitude estimation

The [comparison protocol](comparison_protocol.md) turns these foundations into
explicit accuracy targets, stopping rules, resource definitions and reporting
requirements. The replicated runner implements the design; each run's manifest
and summary record actual completion and measured results.

## Independent Monte Carlo

Let Y=f(X) be bounded in [a,b], with independent, identically distributed draws
Y_1,...,Y_N. The estimator is m_N=(1/N) sum_i Y_i. It is unbiased for mu=E[Y],
with Var(m_N)=sigma^2/N and root mean squared error sigma/sqrt(N).
The unbiased sample variance is s^2=sum_i (Y_i-m_N)^2/(N-1), and the estimated
standard error is s/sqrt(N). Standard error is not itself a confidence interval.

Hoeffding gives P(|m_N-mu| >= epsilon) <= 2 exp(-2N epsilon^2/(b-a)^2)
when a<b. Thus N >= (b-a)^2 log(2/delta)/(2 epsilon^2) suffices for failure
probability delta. For a=b the observations are deterministic. These assumptions
do not hold directly for correlated Markov chains; Metropolis–Hastings is excluded.
For Bernoulli(p), mu=p and sigma^2=p(1-p).

## Quantum construction

Set theta=asin(sqrt(p)). A=Ry(2theta) prepares
A|0> = sqrt(1-p)|0> + sqrt(p)|1>. The objective marks |1> as success.
The Grover operator Q combines A, A^-1 and reflections; powers Q^k amplify the
rotation, giving success probability sin^2((2k+1)theta). IQAE uses measurements at
adaptive k and confidence intervals to resolve theta's periodic ambiguities.
This is amplitude estimation, rather than merely measuring A|0> repeatedly.

Ideal QAE reaches additive error epsilon with O(1/epsilon) oracle queries at fixed
success probability, compared with O(1/epsilon^2) independent bounded samples.
IQAE avoids phase estimation, with a query bound including logarithmic confidence
overhead (see the paper). These bounds omit potentially expensive state loading,
reversible function evaluation and error correction. The one-qubit calibration
does not investigate those costs. It encodes known p; it learns no unknown data.

## Resource accounting

For a general finite distribution, the [discrete expectation case study](discrete_expectation.md)
prepares the index distribution and an objective rotation for each normalized
function value g_i. The objective probability is sum_i p_i*g_i, and the original
expectation is a+(b-a)*sum_i p_i*g_i. Unlike the Bernoulli calibration, this circuit
is built from individual input table entries, without using the weighted mean.

For an executed circuit A followed by Q^k and s shots, the logical Grover cost is
s*k. The total is sum_j s*k_j. The modeled total count of A or A^-1 calls is
sum_j s*(2*k_j+1); the initial A is counted even when k=0. This is an abstract
per-shot circuit cost, not an assertion about the work done internally by a
statevector simulator. Actual quantum hardware oracle queries are zero in this
experiment. Each Q also includes success and zero-state reflections.

`circuit_executions` counts sampled circuit instances, `total_shots` counts their
measurement draws, and `grover_queries` reports the logical Q applications those
shots represent. `state_preparation_calls` includes forward and inverse calls.
Logical u/cx counts depend on decomposition and are not calibrated hardware costs.
Neither N, shots nor Grover queries are interchangeable units of runtime.

If S=sum_j s_j and G=sum_j s_j*k_j, forward A calls are S+G and inverse
calls are G. For per-circuit decomposed gate counts c_j, the logical gate
application total is sum_j s_j*c_j. The [oracle-cost study](oracle_cost.md)
measures these circuit costs and the individual loading/function/reflection
components, rather than treating G alone as an execution-time proxy.

IQAE's alpha controls its nominal failure probability; its interval and error
target are probabilistic statements, not guarantees for every seed. Deterministic
tests validate selected calibration runs and accounting, not universal coverage.

## Primary references

- Brassard et al., [Quantum Amplitude Amplification and Estimation](https://arxiv.org/abs/quant-ph/0005055).
- Grinko et al., [Iterative Quantum Amplitude Estimation](https://arxiv.org/abs/1912.05559).
- [Qiskit IQAE implementation and documentation](https://qiskit-community.github.io/qiskit-algorithms/_modules/qiskit_algorithms/amplitude_estimators/iae.html).
