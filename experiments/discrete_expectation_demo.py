"""Run the four-scenario synthetic payoff after installing the package."""

import json

from qaa.benchmarks.discrete_expectation import run_discrete_benchmark
from qaa.problems.discrete import synthetic_call_payoff

if __name__ == "__main__":
    print(json.dumps(run_discrete_benchmark(synthetic_call_payoff()), indent=2, allow_nan=False))
