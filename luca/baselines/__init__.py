"""Built-in non-LLM baselines for the LUCA benchmark."""
from .random import run_random
from .heuristic import run_heuristic

__all__ = ["run_random", "run_heuristic"]
