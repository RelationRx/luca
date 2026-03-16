"""
Paper v1 experiment configuration.

Sweeps
------
A_medium_healthy   medium × healthy   — main results table
A_medium_disease   medium × disease   — main results table (disease track)
B_easy_healthy     easy   × healthy   — complexity lower bound
B_hard_healthy     hard   × healthy   — complexity upper bound

Seeds are pre-screened via select_seeds.py and stored in selected_seeds.json.
Each tier has its own seed list (easy skips seeds 0, 6 which are ALL_TASKS_ADDITIVE).

All sweeps run the same model list. Results land in results/<sweep>/<model>.jsonl
and are concatenated into results/<sweep>/all.jsonl for analysis.
"""
from __future__ import annotations
import json
from pathlib import Path

# Load pre-screened seeds from select_seeds.py output
_seeds_path = Path(__file__).parent / "selected_seeds.json"
_selected = json.loads(_seeds_path.read_text())["seeds"]

MODELS = [
    "random",
    "heuristic",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "gpt-4o",
    "gpt-4.1",
    "gpt-5.1",
]

SWEEPS: dict[str, dict] = {
    "A_medium_healthy": dict(difficulty="medium", disease=False, seeds=_selected["medium"]),
    "A_medium_disease": dict(difficulty="medium", disease=True,  seeds=_selected["medium"]),
    "B_easy_healthy":   dict(difficulty="easy",   disease=False, seeds=_selected["easy"]),
    "B_hard_healthy":   dict(difficulty="hard",   disease=False, seeds=_selected["hard"]),
}
