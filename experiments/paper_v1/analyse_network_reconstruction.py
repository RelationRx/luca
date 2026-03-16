"""
Network reconstruction analysis — no re-runs required.

For each session log we compute two things:

1. EXPERIMENTAL EDGE INFERENCE
   From the perturbation data in the log: for each gene that was BLOCKed or
   BOOSTed in isolation, record a putative gene→phenotype edge if the observed
   phenotype shift exceeds a threshold. Compare to ground truth readout edges.

2. HYPOTHESIS EDGE EXTRACTION
   Parse the agent's free-text `submit_hypothesis` to extract claimed
   gene→phenotype relationships using a simple heuristic (gene name + direction
   keywords + phenotype name). Compare to ground truth.

Metrics:
  - precision = |inferred ∩ GT| / |inferred|
  - recall    = |inferred ∩ GT| / |GT|
  - F1        = harmonic mean

Usage
-----
    python experiments/paper_v1/analyse_network_reconstruction.py
    python experiments/paper_v1/analyse_network_reconstruction.py --sweep A_medium_healthy --shift-threshold 0.05
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lemonoids import generate_organism  # noqa: E402

# ---------------------------------------------------------------------------

SHIFT_THRESHOLD = 0.05   # |phenotype_delta| to count as an inferred edge


def ground_truth_edges(seed: int, difficulty: str) -> set[tuple[str, str]]:
    """Return set of (gene_name, phenotype_label) from organism readout functions."""
    org = generate_organism(seed=seed, difficulty=difficulty)
    gene_id_to_name = {g.id: g.name for g in org.genes}
    edges: set[tuple[str, str]] = set()
    for ph in org.phenotypes:
        for gene_id in ph.readout.depends_on:
            gene_name = gene_id_to_name.get(gene_id)
            if gene_name:
                edges.add((gene_name, ph.label))
    return edges


def _parse_interventions(inp: dict) -> dict[str, str]:
    """Normalise all observed intervention formats to {gene: type}.

    Observed formats:
    - Claude:   {"interventions": {"G001": {"type": "BLOCK"}}}
    - GPT flat: {"G001": "BLOCK"}   (no wrapper key)
    - GPT wrapped: {"gene_interventions": {"G001": "BLOCK"}}
    """
    # Claude format
    if "interventions" in inp and isinstance(inp["interventions"], dict):
        ivs = inp["interventions"]
        result: dict[str, str] = {}
        for g, v in ivs.items():
            if isinstance(v, dict):
                result[g] = v.get("type", "BLOCK")
            elif isinstance(v, str):
                result[g] = v
        return result
    # GPT wrapped format
    if "gene_interventions" in inp and isinstance(inp["gene_interventions"], dict):
        ivs = inp["gene_interventions"]
        result = {}
        for g, v in ivs.items():
            if isinstance(v, str):
                result[g] = v
            elif isinstance(v, list):
                # {"BLOCK": ["G001", ...]}
                for gene in v:
                    result[gene] = g
        return result
    # GPT flat format: {"G001": "BLOCK", ...}
    if inp and all(isinstance(v, str) for v in inp.values()):
        return dict(inp)
    return {}


def infer_edges_from_experiments(
    log: dict,
    baseline: dict[str, float],
    threshold: float = SHIFT_THRESHOLD,
) -> set[tuple[str, str]]:
    """
    For each single-gene perturbation in the log, infer gene→phenotype edges
    where |observed_phenotype - baseline| > threshold.
    Only uses single-gene experiments to avoid confounded multi-gene signals.
    """
    edges: set[tuple[str, str]] = set()
    for turn in log.get("turns", []):
        for tc in turn.get("tool_calls", []):
            if tc.get("tool") != "run_experiment":
                continue
            interventions = _parse_interventions(tc.get("input", {}))
            result = tc.get("result", {})
            if len(interventions) != 1 or "phenotypes" not in result:
                continue
            gene = list(interventions.keys())[0]
            for ph_label, value in result["phenotypes"].items():
                if abs(value - baseline.get(ph_label, value)) > threshold:
                    edges.add((gene, ph_label))
    return edges


def extract_hypothesis_edges(
    hypothesis_text: str,
    gene_names: list[str],
    phenotype_labels: list[str],
) -> set[tuple[str, str]]:
    """
    Heuristic parse of free-text hypothesis. Looks for a gene name appearing
    in the same sentence/line as a phenotype name with a direction keyword nearby.
    Returns set of (gene_name, phenotype_label) claimed edges.
    """
    edges: set[tuple[str, str]] = set()
    text = hypothesis_text.lower()
    direction_keywords = {
        "positive", "activat", "increas", "upregulat", "driv", "promot",
        "negative", "inhibit", "decreas", "downregulat", "suppress", "reduc",
        "regulat", "affect", "control", "influenc", "correlat",
    }
    # Split into sentences/lines for proximity matching
    chunks = re.split(r"[.\n;]", text)
    for chunk in chunks:
        genes_in_chunk = [g for g in gene_names if g.lower() in chunk]
        phs_in_chunk = [p for p in phenotype_labels if p.lower() in chunk]
        has_direction = any(kw in chunk for kw in direction_keywords)
        if genes_in_chunk and phs_in_chunk and has_direction:
            for gene in genes_in_chunk:
                for ph in phs_in_chunk:
                    edges.add((gene, ph))
    return edges


def precision_recall_f1(
    inferred: set, ground_truth: set
) -> tuple[float, float, float]:
    if not inferred:
        return 0.0, 0.0, 0.0
    if not ground_truth:
        return 0.0, 0.0, 0.0
    tp = len(inferred & ground_truth)
    p = tp / len(inferred)
    r = tp / len(ground_truth)
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def analyse_session(
    log_path: Path,
    difficulty: str,
    shift_threshold: float,
) -> dict | None:
    log = json.loads(log_path.read_text())
    meta = log.get("metadata", {})
    seed = meta.get("seed")
    model = meta.get("model", log_path.stem.split("_seed")[0])
    if seed is None:
        return None

    # Ground truth
    try:
        gt = ground_truth_edges(seed, difficulty)
    except Exception:
        return None

    gene_names = sorted({g for g, _ in gt} | {
        gene
        for turn in log["turns"]
        for tc in turn.get("tool_calls", [])
        if tc.get("tool") == "run_experiment"
        for gene in _parse_interventions(tc.get("input", {})).keys()
    })
    phenotype_labels = sorted({p for _, p in gt})

    # Baseline from first get_organism_info call or first experiment baseline
    baseline: dict[str, float] = {}
    for turn in log["turns"]:
        for tc in turn.get("tool_calls", []):
            if tc.get("tool") == "get_organism_info":
                bp = tc.get("result", {}).get("baseline_phenotypes", {})
                if bp:
                    baseline = bp
                    break
        if baseline:
            break

    # Experimental edge inference
    exp_edges = infer_edges_from_experiments(log, baseline, shift_threshold)
    exp_p, exp_r, exp_f1 = precision_recall_f1(exp_edges, gt)

    # Hypothesis edge extraction
    hypothesis = log.get("summary", {}).get("hypothesis", "") or ""
    hyp_edges = extract_hypothesis_edges(hypothesis, gene_names, phenotype_labels)
    hyp_p, hyp_r, hyp_f1 = precision_recall_f1(hyp_edges, gt)

    return {
        "seed": seed,
        "model": model,
        "gt_n_edges": len(gt),
        "exp_inferred": len(exp_edges),
        "exp_precision": round(exp_p, 3),
        "exp_recall": round(exp_r, 3),
        "exp_f1": round(exp_f1, 3),
        "hyp_claimed": len(hyp_edges),
        "hyp_precision": round(hyp_p, 3),
        "hyp_recall": round(hyp_r, 3),
        "hyp_f1": round(hyp_f1, 3),
        "n_experiments": log.get("summary", {}).get("n_experiments", 0),
    }


def summarise(records: list[dict], label: str) -> None:
    if not records:
        print(f"  {label}: no data")
        return
    import statistics
    exp_f1s = [r["exp_f1"] for r in records]
    hyp_f1s = [r["hyp_f1"] for r in records]
    exp_rec = [r["exp_recall"] for r in records]
    hyp_rec = [r["hyp_recall"] for r in records]
    print(f"  {label} (n={len(records)})")
    print(f"    Experimental inference — F1: {statistics.mean(exp_f1s):.3f}±{statistics.stdev(exp_f1s):.3f}  "
          f"recall: {statistics.mean(exp_rec):.3f}")
    print(f"    Hypothesis extraction  — F1: {statistics.mean(hyp_f1s):.3f}±{statistics.stdev(hyp_f1s):.3f}  "
          f"recall: {statistics.mean(hyp_rec):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", default="A_medium_healthy",
                        help="Sweep name (default: A_medium_healthy)")
    parser.add_argument("--shift-threshold", type=float, default=SHIFT_THRESHOLD,
                        help=f"Phenotype shift threshold for edge inference (default: {SHIFT_THRESHOLD})")
    args = parser.parse_args()

    logs_dir = Path(__file__).parent / "logs" / args.sweep / "logs"
    if not logs_dir.exists():
        print(f"No logs found at {logs_dir}")
        return

    difficulty = args.sweep.split("_")[1] if "_" in args.sweep else "medium"

    all_records: list[dict] = []
    for log_path in sorted(logs_dir.glob("*.json")):
        r = analyse_session(log_path, difficulty, args.shift_threshold)
        if r:
            all_records.append(r)

    if not all_records:
        print("No records parsed.")
        return

    models = sorted({r["model"] for r in all_records})

    print(f"\nNetwork reconstruction — {args.sweep} (shift_threshold={args.shift_threshold})\n")
    print(f"{'Model':<22} {'Exp-F1':>8} {'Exp-R':>7} {'Hyp-F1':>8} {'Hyp-R':>7}  N")
    print("-" * 65)

    import statistics
    for model in models:
        recs = [r for r in all_records if r["model"] == model]
        ef1 = [r["exp_f1"] for r in recs]
        er  = [r["exp_recall"] for r in recs]
        hf1 = [r["hyp_f1"] for r in recs]
        hr  = [r["hyp_recall"] for r in recs]
        print(
            f"{model:<22} "
            f"{statistics.mean(ef1):>7.3f}  "
            f"{statistics.mean(er):>6.3f}  "
            f"{statistics.mean(hf1):>7.3f}  "
            f"{statistics.mean(hr):>6.3f}  "
            f"{len(recs)}"
        )

    # Save per-session results
    out_path = Path(__file__).parent / f"network_reconstruction_{args.sweep}.jsonl"
    with open(out_path, "w") as f:
        for r in sorted(all_records, key=lambda x: (x["model"], x["seed"])):
            f.write(json.dumps(r) + "\n")
    print(f"\nPer-session results → {out_path}")


if __name__ == "__main__":
    main()
