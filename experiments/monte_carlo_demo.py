"""Print the first case study after installing the package and quantum extra."""

import json

from qaa.benchmarks.monte_carlo import run_benchmark

if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, allow_nan=False))
