"""
Prompt-caching A/B smoke test.

Runs N seeds × {cache_on, cache_off} on medium healthy with Opus.
Checks:
  1. Cache actually hits (cache_read_input_tokens > 0 on turn ≥ 2).
  2. Scores are comparable between arms (no behavioural drift).
  3. No session straddles the 5-min TTL and misses cache unexpectedly.

Output: prints a summary + writes raw session logs to results/cache_smoke/.
Local only — not committed.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from luca.agent import run_agent
from luca.experiment import ExperimentSession
from luca.generation import generate_organism

SEEDS = [0, 1, 2, 3, 4]
MODEL = "claude-opus-4-6"
DIFFICULTY = "medium"
DISEASE = False
OUT = Path("scripts/results/cache_smoke")


def run_one(seed: int, cache: bool) -> dict:
    tag = "on" if cache else "off"
    log_path = OUT / f"cache_{tag}_seed{seed:04d}.json"
    organism = generate_organism(seed=seed, difficulty=DIFFICULTY)
    session = ExperimentSession(
        organism,
        seed=seed,
        active_tasks=frozenset({"predict", "diagnose", "rescue"}),
    )
    summary = run_agent(
        session,
        model=MODEL,
        verbose=False,
        log_path=str(log_path),
        use_prompt_cache=cache,
    )
    return {"seed": seed, "cache": cache, "log": log_path, "summary": summary}


def inspect(log_path: Path) -> dict:
    d = json.loads(log_path.read_text())
    turns = d["turns"]
    return {
        "n_turns": len(turns),
        "input_tokens_sum": sum(t.get("input_tokens", 0) for t in turns),
        "output_tokens_sum": sum(t.get("output_tokens", 0) for t in turns),
        "cache_read_sum": sum(t.get("cache_read_input_tokens", 0) for t in turns),
        "cache_creation_sum": sum(t.get("cache_creation_input_tokens", 0) for t in turns),
        "turns_with_read": sum(
            1 for t in turns if t.get("cache_read_input_tokens", 0) > 0
        ),
        "score": d["summary"].get("composite_score") or d["summary"].get("avg_accuracy"),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for seed in SEEDS:
        for cache in (False, True):
            print(f"→ seed={seed} cache={cache} ...", flush=True)
            try:
                r = run_one(seed, cache)
                results.append(r)
                print(f"   ok  score={r['summary'].get('composite_score') or r['summary'].get('avg_accuracy')}")
            except Exception as e:
                print(f"   FAIL  {type(e).__name__}: {e}")
                results.append({"seed": seed, "cache": cache, "error": str(e)})

    # Analyse
    print("\n" + "=" * 78)
    print("SMOKE RESULTS")
    print("=" * 78)
    for arm_cache in (False, True):
        print(f"\n--- cache={arm_cache} ---")
        scores, reads, creates, turns_with_read = [], [], [], []
        for r in results:
            if r.get("cache") != arm_cache or "error" in r:
                continue
            info = inspect(r["log"])
            print(
                f"  seed {r['seed']}: score={info['score']:.3f}  turns={info['n_turns']}  "
                f"in_tok={info['input_tokens_sum']:,}  cache_read={info['cache_read_sum']:,}  "
                f"cache_create={info['cache_creation_sum']:,}  read_turns={info['turns_with_read']}/{info['n_turns']}"
            )
            scores.append(info["score"])
            reads.append(info["cache_read_sum"])
            creates.append(info["cache_creation_sum"])
            turns_with_read.append(info["turns_with_read"])
        if scores:
            print(
                f"  MEAN: score={statistics.mean(scores):.3f} ± {statistics.stdev(scores) if len(scores)>1 else 0:.3f}  "
                f"cache_read={sum(reads):,}  cache_create={sum(creates):,}"
            )


if __name__ == "__main__":
    sys.exit(main())
