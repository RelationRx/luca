"""Built-in non-LLM baselines for the LUCA benchmark."""
from .random import run_random
from .heuristic import run_heuristic
from .causal_sweep import run as run_causal_sweep

__all__ = ["run_random", "run_heuristic", "run_causal_sweep"]
