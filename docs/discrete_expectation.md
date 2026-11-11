# Discrete expectation: explicit distribution and function encoding

This extends Bernoulli calibration to a bounded function on a finite probability
space. Both estimators consume the same immutable tables of probabilities p_i
and function values f_i, with bounds a < b. Direct summation is the validation
reference; the quantum circuit never reads that reference value.

## Synthetic example

Take four terminal scenarios S and the payoff f(S)=max(S-110,0):

| Index i | S_i | p_i | f_i | g_i=f_i/30 |
| --- | --- | --- | --- | --- |
| 0 | 80 | 0.1 | 0 | 0 |
| 1 | 100 | 0.2 | 0 | 0 |
| 2 | 120 | 0.4 | 10 | 1/3 |
| 3 | 140 | 0.3 | 30 | 1 |

The exact, undiscounted expectation is 0.4*10+0.3*30=13 and the normalized
expectation is 13/30. This is a synthetic mathematical example, not a calibrated
pricing model. It has no time dynamics, market data or discount factor.
Its variance is 0.4*100+0.3*900-13^2=141.

## Classical route

Sample indices independently with probabilities p_i and return their function
values. The existing Monte Carlo estimator computes the mean, unbiased sample
variance and standard error in original units. It does not sample a Bernoulli
indicator whose probability is already the answer.

The new single-run benchmark fixes N using the protocol's Hoeffding rule and
reports a clipped Hoeffding interval in original units. With epsilon=0.03,
alpha=0.05, N=2050 and the absolute error target is 30*0.03=0.9.
This conservative baseline and IQAE share nominal error/confidence targets;
one run does not measure empirical coverage.

## Quantum route

An index register uses max(1,ceil(log2(m))) qubits for m table entries and one
additional objective qubit. The four-scenario example therefore uses three qubits.

1. Unitary StatePreparation loads sum_i sqrt(p_i)|i> on the index register.
2. For each index i, a controlled Ry(2*asin(sqrt(g_i))) acts on the objective,
   where g_i=(f_i-a)/(b-a). No weighted mean is used to choose rotation angles.
3. A success reflection marks objective |1>; the Grover operator uses this A,
   A inverse and a zero-state reflection. IQAE estimates the objective probability.

The prepared joint state is

`sum_i sqrt(p_i)|i>(sqrt(1-g_i)|0> + sqrt(g_i)|1>)`.

Consequently the success probability is q=sum_i p_i*g_i. IQAE returns q_hat and
its interval; both are mapped back using mu_hat=a+(b-a)*q_hat. The returned
`absolute_error_target` is (b-a)*epsilon. `amplitude_result` retains normalized
estimates, intervals, targets, seeds and resource accounting to avoid mixing units.

Qiskit indexes basis states little-endian. The objective is the highest-index
qubit, with the lower qubits holding the integer table index. Non-power-of-two
tables are padded with zero probability; unused states cannot contribute to the
expectation. Zero-probability entries, singleton tables and constant functions
within declared positive-width bounds are supported.

StatePreparation is a unitary gate with an inverse. Reset-based `initialize`
would not supply the coherent inverse required here. Implementation follows
the official [StatePreparation API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.5/qiskit.circuit.library.StatePreparation)
and [controlled Ry API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.5/qiskit.circuit.library.RYGate).

## Reproduce

After installing the README's quantum/dev extras:

```powershell
python -m qaa.benchmarks.discrete_expectation --epsilon 0.03 --alpha 0.05 --seed 42 --output results/discrete-expectation.json
python -m qaa.benchmarks.discrete_expectation --classical-only --output results/discrete-classical.json
python experiments/discrete_expectation_demo.py
python -m pytest
```

The CLI runs the fixed synthetic example; Python callers can supply other tables:

```python
from qaa.problems.discrete import DiscreteExpectation
from qaa.classical.monte_carlo import estimate_expectation
from qaa.quantum.discrete_expectation import estimate_discrete_expectation

problem = DiscreteExpectation(
    probabilities=(0.2, 0.3, 0.5),
    function_values=(-2.0, 0.0, 6.0),
    bounds=(-2.0, 6.0),
)
classical = estimate_expectation(problem.sample, 10000, bounds=problem.bounds, seed=42)
quantum = estimate_discrete_expectation(problem, epsilon_target=0.03, seed=42)
print(problem.exact_expectation, classical.estimate, quantum.estimate)
```

The JSON records input tables, exact reference, targets, independent method seeds and original-unit results. Quantum extras are optional. The estimation timer excludes problem construction and post-run resource inspection.

## What this demonstrates and what remains

This verifies coherent distribution/function encoding, true IQAE execution and
unit conversion on a non-Bernoulli function. Tests inspect the entire joint
distribution and the inverse, including padding and zero-probability states,
and prevent the quantum estimator from accessing `exact_expectation`.

Explicit tables are already known to the host. Direct summation takes O(m) and
is preferable for this tiny problem. General state loading and one conditional
rotation per table entry have substantial costs; the construction is not a claim
of efficient loading in log(m) or of end-to-end advantage. This is a transparent
lookup implementation, not a scalable arithmetic payoff oracle. A future study must measure loading, construction and circuit costs as input sizes grow.

The new runner is one calibration per method, with its own recorded seed mapping.
It does not execute or alter the Bernoulli grid in protocol `mc-iqae-v1`.
Repeated-trial accuracy analysis and a generated report remain future work.
