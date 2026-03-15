"""
Paper v1 experiment configuration.

Sweeps
------
A_medium_healthy   20 seeds × medium × healthy    — main results table
A_medium_disease   20 seeds × medium × disease    — main results table (disease track)
B_easy_healthy     20 seeds × easy    × healthy   — complexity threshold (lower bound)
B_hard_healthy     20 seeds × hard    × healthy   — complexity threshold (upper bound)

All sweeps run the same model list. Results land in results/<sweep>/<model>.jsonl
and are concatenated into results/<sweep>/all.jsonl for analysis.
"""

SEEDS = list(range(20))

MODELS = [
    "heuristic",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "gpt-4o",
    "gpt-4.1",
    "gpt-5.1",
]

SWEEPS: dict[str, dict] = {
    "A_medium_healthy": dict(difficulty="medium", disease=False),
    "A_medium_disease": dict(difficulty="medium", disease=True),
    "B_easy_healthy":   dict(difficulty="easy",   disease=False),
    "B_hard_healthy":   dict(difficulty="hard",   disease=False),
}
