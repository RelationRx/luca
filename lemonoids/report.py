"""Session diagnostic tools for Lemonoids experiments."""
from __future__ import annotations

import json
import os
from typing import Any


# ---------------------------------------------------------------------------
# Text trace
# ---------------------------------------------------------------------------

def print_session_trace(log: dict) -> None:
    """Print a human-readable turn-by-turn trace of an agent session to stdout."""
    meta = log.get("metadata", {})
    turns = log.get("turns", [])
    summary = log.get("summary", {})

    disease_str = "DISEASE" if meta.get("disease_mode") else "healthy"
    print(f"\n{'═'*72}")
    print(f"  {meta.get('organism_id','?')}  ·  seed={meta.get('seed','?')}  ·  "
          f"budget={meta.get('budget','?')}  ·  {disease_str}  ·  {meta.get('model','?')}")
    print(f"  {meta.get('timestamp','')}")
    print(f"{'═'*72}")

    # Extract baseline phenotypes and healthy ranges from get_organism_info result
    baseline_phenos: dict[str, float] = {}
    healthy_ranges: dict[str, list] = {}
    for turn in turns:
        for tc in turn.get("tool_calls", []):
            if tc["tool"] == "get_organism_info":
                r = tc["result"]
                baseline_phenos = r.get("baseline_phenotypes", {})
                healthy_ranges = r.get("healthy_phenotype_ranges", {})
                break
        if baseline_phenos:
            break

    for turn in turns:
        n = turn["turn"]
        print(f"\n─── Turn {n} {'─' * (62 - len(str(n)))}")
        text = (turn.get("agent_text") or "").strip()
        if text:
            snippet = text[:400].replace("\n", " ")
            if len(text) > 400:
                snippet += "…"
            print(f"  💭 {snippet}")
        for tc in turn.get("tool_calls", []):
            _print_tool_call(tc, baseline_phenos, healthy_ranges)

    # Summary
    print(f"\n{'═'*72}")
    print("  SUMMARY")
    print(f"{'═'*72}")
    if summary:
        bu = summary.get("budget_used", "?")
        bt = summary.get("budget_total", "?")
        print(f"  Budget:       {bu}/{bt}")
        acc = summary.get("avg_accuracy")
        mse = summary.get("avg_mse")
        if acc is not None:
            sym = "✓" if acc >= 0.8 else ("~" if acc >= 0.5 else "✗")
            print(f"  Predictions:  {sym}  accuracy={acc}  mse={mse}")
        mh = summary.get("malfunction_hypothesis")
        if mh:
            score = mh["score"]
            sym = "✓" if score == 1.0 else ("~" if score == 0.5 else "✗")
            print(f"  Malfunction:  {sym}  {mh['target_name']} ({mh['malfunction_type']})  score={score}")
        rr = summary.get("rescue_results", [])
        if rr:
            best = max(r["restored_fraction"] for r in rr)
            best_mse = min(r["mse_vs_healthy"] for r in rr)
            sym = "✓" if best >= 1.0 else ("~" if best >= 0.5 else "✗")
            print(f"  Best rescue:  {sym}  restored={best:.0%}  mse_vs_healthy={best_mse}")
    print()


def _print_tool_call(tc: dict, baseline_phenos: dict, healthy_ranges: dict) -> None:
    tool = tc["tool"]
    inp  = tc["input"]
    res  = tc["result"]

    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass

    if tool == "get_organism_info":
        n_genes  = len(res.get("gene_names", []))
        n_sigs   = len(res.get("signals", []))
        n_phenos = len(res.get("observable_phenotypes", []))
        print(f"  ▶ get_organism_info()")
        print(f"     {n_genes} genes · {n_sigs} signals · {n_phenos} phenotypes")
        bp = res.get("baseline_phenotypes", {})
        if bp:
            print("     baseline: " + "  ".join(f"{k}={v:.3f}" for k, v in bp.items()))
        for a in res.get("aberrant_phenotypes", []):
            val = bp.get(a, "?")
            rng = res.get("healthy_phenotype_ranges", {}).get(a, ["?", "?"])
            val_str = f"{val:.3f}" if isinstance(val, float) else str(val)
            print(f"     ⚠ ABERRANT: {a}={val_str}  [healthy: {rng[0]:.3f}–{rng[1]:.3f}]")

    elif tool == "get_next_prediction_task":
        task_id = res.get("task_id")
        if task_id:
            iv_str = "  ".join(
                f"{g} {v['type']}" if isinstance(v, dict) else f"{g}:{v}"
                for g, v in res.get("interventions", {}).items()
            )
            print(f"  ▶ get_next_prediction_task()  → {task_id}: {iv_str}")
        elif res.get("done"):
            print(f"  ▶ get_next_prediction_task()  → all tasks submitted")

    elif tool == "run_experiment":
        iv  = inp.get("interventions", {})
        bud = res.get("budget_remaining", "?")
        status = res.get("status", "")
        print(f"  ▶ run_experiment({_fmt_iv(iv)})  [budget→{bud}]")
        phenos = res.get("phenotypes", {})
        if phenos:
            parts = []
            for ph, val in phenos.items():
                base = baseline_phenos.get(ph)
                delta = f"({val - base:+.3f})" if base is not None else ""
                hr = healthy_ranges.get(ph)
                in_range = (hr[0] <= val <= hr[1]) if hr else None
                flag = ""
                if in_range is True:
                    flag = " ✓"
                elif in_range is False:
                    flag = " ✗"
                parts.append(f"{ph}={val:.3f}{delta}{flag}")
            print("     " + "  ".join(parts))
        if status == "max_steps_reached":
            print("     ⚠ simulation did not converge")

    elif tool == "test_rescue":
        iv  = inp.get("interventions", {})
        bud = res.get("budget_remaining", "?")
        rf  = res.get("restored_fraction", 0.0)
        mse = res.get("mse_vs_healthy", "?")
        sym = "✓" if rf >= 1.0 else ("~" if rf >= 0.5 else "✗")
        print(f"  ▶ test_rescue({_fmt_iv(iv)})  [budget→{bud}]")
        print(f"     {sym} restored={rf:.0%}  mse_vs_healthy={mse}")
        for ph, ok in res.get("phenotype_in_healthy_range", {}).items():
            val = res.get("phenotypes", {}).get(ph, float("nan"))
            hr  = healthy_ranges.get(ph, ["?", "?"])
            s   = "✓" if ok else "✗"
            print(f"       {s} {ph}={val:.3f}  [healthy: {hr[0]:.3f}–{hr[1]:.3f}]")

    elif tool == "submit_malfunction_hypothesis":
        target = inp.get("target_name", "?")
        mtype  = inp.get("malfunction_type", "?")
        if "error" in res:
            print(f"  ▶ submit_malfunction_hypothesis(target={target}, type={mtype})")
            print(f"     ✗ ERROR: {res['error']}")
        else:
            print(f"  ▶ submit_malfunction_hypothesis(target={target}, type={mtype})")
            print(f"     🔒 locked — score revealed at session end")

    elif tool == "submit_prediction":
        task_id = inp.get("task_id", "?")
        acc = res.get("accuracy", "?")
        mse = res.get("mse", "?")
        sym = "✓" if acc == 1.0 else ("~" if (isinstance(acc, float) and acc >= 0.8) else "✗")
        print(f"  ▶ submit_prediction({task_id})")
        print(f"     {sym} accuracy={acc}  mse={mse}")
        for ph, d in res.get("details", {}).items():
            gt   = d.get("ground_truth", "?")
            pred = d.get("prediction", "?")
            ok   = d.get("within_threshold", False)
            s    = "✓" if ok else "✗"
            print(f"       {s} {ph}: pred={pred}  gt={gt}")

    elif tool == "submit_hypothesis":
        length = res.get("length", 0)
        print(f"  ▶ submit_hypothesis()  [{length} chars stored]")

    else:
        print(f"  ▶ {tool}({json.dumps(inp)[:60]})")
        if "error" in res:
            print(f"     ✗ ERROR: {res['error']}")


def _fmt_iv(iv: dict) -> str:
    if not iv:
        return "∅"
    parts = []
    for k, v in iv.items():
        parts.append(f"{k} {v['type']}" if isinstance(v, dict) else f"{k}:{v}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Network schematic helpers
# ---------------------------------------------------------------------------

def _build_discovered_network(
    turns: list[dict],
    baseline_phenos: dict[str, float],
    threshold: float = 0.10,
) -> list[dict]:
    """
    Infer gene/signal → phenotype causal edges from single-target experiments.

    Only single-intervention experiments are attributed (multi-gene experiments
    cannot cleanly identify which gene caused which phenotype change).

    Returns a list of edge dicts: {from, to, direction, delta}
    where direction is "activates" or "inhibits".
    """
    edges: dict[tuple, dict] = {}

    for turn in turns:
        for tc in turn.get("tool_calls", []):
            if tc["tool"] not in ("run_experiment", "test_rescue"):
                continue
            ivs = tc["input"].get("interventions", {})
            result = tc.get("result", {})
            if not result or "error" in result:
                continue
            phenos = result.get("phenotypes", {})
            if not phenos or len(ivs) != 1:
                continue

            target, iv = next(iter(ivs.items()))
            iv_type = iv.get("type", iv) if isinstance(iv, dict) else iv

            for p_label, p_val in phenos.items():
                delta = p_val - baseline_phenos.get(p_label, 0.5)
                if abs(delta) < threshold:
                    continue
                # Causal direction:
                #   BLOCK/DAMPEN → node removed → phenotype drops  ⟹ node was activating it
                #   BLOCK/DAMPEN → node removed → phenotype rises  ⟹ node was inhibiting it
                #   BOOST/activate → node added → phenotype rises  ⟹ node activates
                #   BOOST/activate → node added → phenotype drops  ⟹ node inhibits
                if iv_type in ("BLOCK", "DAMPEN"):
                    direction = "inhibits" if delta > 0 else "activates"
                elif iv_type in ("BOOST", "activate"):
                    direction = "activates" if delta > 0 else "inhibits"
                else:
                    continue

                key = (target, p_label)
                if key not in edges or abs(delta) > abs(edges[key]["delta"]):
                    edges[key] = {
                        "from": target, "to": p_label,
                        "direction": direction, "delta": delta,
                    }

    return list(edges.values())


def _render_network_svg(
    gene_names: list[str],
    signal_labels: list[str],
    phenotype_labels: list[str],
    baseline_phenos: dict[str, float],
    discovered_edges: list[dict],
    current_phenos: dict[str, float] | None,
    current_interventions: dict[str, str],
    aberrant_phenotypes: list[str] | None = None,
    healthy_ranges: dict | None = None,
    edge_opacity: float = 0.45,
) -> str:
    """
    Render a minimal bipartite schematic of the organism as inline SVG.

    Left column: genes (circles) and signals (diamonds).
    Right column: phenotypes (rectangles).
    Edges: causal relationships inferred from experiments so far.
    Highlighted nodes: interventions applied in the current turn.
    """
    W = 500
    NODE_R = 9        # gene circle radius
    SIG_H = 8         # signal diamond half-size
    P_W, P_H = 90, 20 # phenotype rect dimensions
    GENE_X = 110      # gene column center x
    PHENO_X = 392     # phenotype column center x
    GENE_SP = 26      # vertical spacing between left nodes
    PHENO_SP = 38     # vertical spacing between right nodes
    TOP_PAD = 30      # space above content (column labels)
    BOT_PAD = 26      # space below content (legend)

    left_nodes = gene_names + signal_labels
    n_left = len(left_nodes)
    n_right = len(phenotype_labels)

    left_h = max(n_left * GENE_SP, 1)
    right_h = max(n_right * PHENO_SP, 1)
    content_h = max(left_h, right_h, 60)
    H = content_h + TOP_PAD + BOT_PAD

    def left_y(i: int) -> int:
        offset = (content_h - left_h) // 2
        return TOP_PAD + offset + i * GENE_SP + GENE_SP // 2

    def right_y(i: int) -> int:
        offset = (content_h - right_h) // 2
        return TOP_PAD + offset + i * PHENO_SP + PHENO_SP // 2

    left_idx = {n: i for i, n in enumerate(left_nodes)}
    right_idx = {n: i for i, n in enumerate(phenotype_labels)}

    EDGE_C = {"activates": "#22c55e", "inhibits": "#ef4444"}
    IV_C   = {"BLOCK": "#ef4444", "BOOST": "#22c55e", "DAMPEN": "#f97316", "activate": "#a78bfa"}

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:6px;display:block;margin-top:8px;">'
    )

    # Column labels
    p.append(
        f'<text x="{GENE_X}" y="18" text-anchor="middle" font-size="10" '
        f'fill="#475569" font-family="monospace">genes / signals</text>'
    )
    p.append(
        f'<text x="{PHENO_X}" y="18" text-anchor="middle" font-size="10" '
        f'fill="#475569" font-family="monospace">phenotypes</text>'
    )

    # Edges (drawn first, behind nodes)
    for edge in discovered_edges:
        src, tgt = edge["from"], edge["to"]
        if src not in left_idx or tgt not in right_idx:
            continue
        sx = GENE_X + (NODE_R if src in gene_names else SIG_H)
        sy = left_y(left_idx[src])
        tx = PHENO_X - P_W // 2
        ty = right_y(right_idx[tgt])
        color = EDGE_C.get(edge["direction"], "#94a3b8")
        magnitude = abs(edge.get("delta", edge.get("weight", 0.3)))
        sw = min(3.0, max(1.0, magnitude / 0.3))
        p.append(
            f'<line x1="{sx}" y1="{sy}" x2="{tx}" y2="{ty}" '
            f'stroke="{color}" stroke-width="{sw:.1f}" stroke-opacity="{edge_opacity}"/>'
        )

    # Gene nodes (circles)
    for i, name in enumerate(gene_names):
        y = left_y(i)
        iv = current_interventions.get(name)
        fill   = IV_C[iv] + "22" if iv else "#1e293b"
        stroke = IV_C.get(iv, "#475569")
        sw     = 2.5 if iv else 1.0
        p.append(
            f'<circle cx="{GENE_X}" cy="{y}" r="{NODE_R}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        p.append(
            f'<text x="{GENE_X - NODE_R - 4}" y="{y + 4}" text-anchor="end" '
            f'font-size="10" fill="#64748b" font-family="monospace">{_he(name[:5])}</text>'
        )
        if iv:
            p.append(
                f'<text x="{GENE_X + NODE_R + 3}" y="{y + 4}" text-anchor="start" '
                f'font-size="9" fill="{stroke}" font-family="monospace">{_he(iv)}</text>'
            )

    # Signal nodes (diamonds)
    for i, sname in enumerate(signal_labels):
        idx = len(gene_names) + i
        y = left_y(idx)
        iv     = current_interventions.get(sname)
        fill   = "#2d2060" if iv else "#1e1b4b"
        stroke = "#a78bfa" if iv else "#6d28d9"
        sw     = 2.5 if iv else 1.0
        r      = SIG_H
        pts    = f"{GENE_X},{y - r} {GENE_X + r},{y} {GENE_X},{y + r} {GENE_X - r},{y}"
        p.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        p.append(
            f'<text x="{GENE_X - SIG_H - 4}" y="{y + 4}" text-anchor="end" '
            f'font-size="9" fill="#7c3aed" font-family="monospace">{_he(sname[:8])}</text>'
        )
        if iv:
            p.append(
                f'<text x="{GENE_X + SIG_H + 3}" y="{y + 4}" text-anchor="start" '
                f'font-size="9" fill="{stroke}" font-family="monospace">act</text>'
            )

    # Phenotype nodes (rectangles)
    for i, p_label in enumerate(phenotype_labels):
        y   = right_y(i)
        rx  = PHENO_X - P_W // 2
        ry  = y - P_H // 2

        is_aberrant = bool(aberrant_phenotypes and p_label in aberrant_phenotypes)
        fill   = "#3b1515" if is_aberrant else "#1e293b"
        stroke = "#ef4444" if is_aberrant else "#334155"
        sw     = 2 if is_aberrant else 1

        val = (current_phenos or baseline_phenos).get(p_label)

        # Healthy range bar (thin green strip at bottom of rect)
        if healthy_ranges and p_label in healthy_ranges:
            hr = healthy_ranges[p_label]
            lo, hi = float(hr[0]), float(hr[1])
            bar_inner_w = P_W - 8
            bx = rx + 4 + int(lo * bar_inner_w)
            bw = max(1, int((hi - lo) * bar_inner_w))
            p.append(
                f'<rect x="{bx}" y="{ry + P_H - 4}" width="{bw}" height="3" '
                f'fill="#22c55e" opacity="0.4" rx="1"/>'
            )

        p.append(
            f'<rect x="{rx}" y="{ry}" width="{P_W}" height="{P_H}" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )
        # Label (truncated, left-aligned within rect)
        p.append(
            f'<text x="{rx + 5}" y="{y + 4}" text-anchor="start" '
            f'font-size="9" fill="#94a3b8" font-family="monospace">{_he(p_label[:11])}</text>'
        )
        # Value (right-aligned within rect)
        if val is not None:
            val_color = "#ef4444" if is_aberrant else "#64748b"
            p.append(
                f'<text x="{rx + P_W - 4}" y="{y + 4}" text-anchor="end" '
                f'font-size="9" fill="{val_color}" font-family="monospace">{val:.2f}</text>'
            )

    # Legend
    leg_y = H - 14
    for j, (lbl, color) in enumerate([("BLOCK", "#ef4444"), ("BOOST", "#22c55e"), ("DAMPEN", "#f97316")]):
        bx = 10 + j * 42
        p.append(
            f'<circle cx="{bx + 5}" cy="{leg_y}" r="5" '
            f'fill="{color}22" stroke="{color}" stroke-width="1.5"/>'
        )
        p.append(
            f'<text x="{bx + 13}" y="{leg_y + 4}" font-size="8" '
            f'fill="#475569" font-family="monospace">{lbl}</text>'
        )
    for j, (lbl, color) in enumerate([("activates", "#22c55e"), ("inhibits", "#ef4444")]):
        bx = 150 + j * 100
        p.append(
            f'<line x1="{bx}" y1="{leg_y}" x2="{bx + 16}" y2="{leg_y}" '
            f'stroke="{color}" stroke-width="2" stroke-opacity="0.7"/>'
        )
        p.append(
            f'<text x="{bx + 20}" y="{leg_y + 4}" font-size="8" '
            f'fill="#475569" font-family="monospace">{lbl}</text>'
        )

    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_CSS = """
body{font-family:'Courier New',monospace;background:#0d0d1a;color:#d0d0e0;margin:0;padding:16px}
h1{color:#FFC107;font-size:1.1em;margin:0 0 4px}
.meta{color:#888;font-size:.8em;margin-bottom:16px}
.turn{border:1px solid #2a2a4a;border-radius:6px;margin:10px 0;overflow:hidden}
.turn-header{background:#111128;padding:6px 12px;cursor:pointer;display:flex;align-items:center;gap:10px}
.turn-num{color:#FFC107;font-weight:bold;min-width:60px}
.turn-summary{color:#888;font-size:.8em;flex:1}
.turn-body{padding:10px 14px;border-top:1px solid #2a2a4a}
.reasoning{background:#0e1e0e;border-left:3px solid #4CAF50;padding:8px 10px;
           margin:6px 0 10px;font-size:.78em;white-space:pre-wrap;color:#aec;
           max-height:200px;overflow-y:auto;border-radius:0 4px 4px 0}
.tool{border-left:3px solid #334;margin:5px 0;padding:4px 10px}
.tool-name{color:#90CAF9;font-weight:bold;font-size:.82em}
.tool-io{font-size:.76em;margin-top:3px;color:#aaa}
.ok{color:#4CAF50}.warn{color:#FFC107}.err{color:#EF5350}.info{color:#90CAF9}
.result-row{margin:2px 0;font-size:.76em}
.net-summary{font-size:.75em;color:#475569;cursor:pointer;margin-top:8px;
             padding:3px 0;border-top:1px solid #1a1a2e;list-style:none}
.net-summary::-webkit-details-marker{display:none}
table.summary{border-collapse:collapse;width:100%;margin-top:12px}
table.summary td,table.summary th{padding:4px 10px;border:1px solid #2a2a4a;font-size:.8em}
table.summary th{background:#111128;color:#FFC107}
.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.75em;font-weight:bold}
.badge-ok{background:#1b3a1b;color:#4CAF50}
.badge-warn{background:#3a3010;color:#FFC107}
.badge-err{background:#3a1010;color:#EF5350}
details>summary{cursor:pointer;list-style:none}
details>summary::-webkit-details-marker{display:none}
"""

_JS = """
function toggleAll(open){
  document.querySelectorAll('details').forEach(d=>d.open=open);
}
"""


def export_session_html(log: dict, path: str) -> None:
    """Export a session log as a self-contained HTML diagnostic report."""
    html = _build_html(log)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] HTML saved → {path}")


def _build_html(log: dict) -> str:
    meta    = log.get("metadata", {})
    turns   = log.get("turns", [])
    summary = log.get("summary", {})

    disease_str = "DISEASE" if meta.get("disease_mode") else "healthy"

    # ── Ground truth edges from log metadata (embedded by run_agent) ─────
    gt_edges: list[dict] = meta.get("ground_truth", {}).get("gene_phenotype_edges", [])

    # ── Extract organism structure from first get_organism_info call ──────
    baseline_phenos: dict[str, float] = {}
    healthy_ranges: dict[str, list]   = {}
    gene_names_svg: list[str]         = []
    signal_labels_svg: list[str]      = []
    phenotype_labels_svg: list[str]   = []
    aberrant_phenotypes: list[str]    = []

    for turn in turns:
        for tc in turn.get("tool_calls", []):
            if tc["tool"] == "get_organism_info":
                r = tc["result"]
                if isinstance(r, str):
                    try:
                        r = json.loads(r)
                    except Exception:
                        pass
                baseline_phenos       = r.get("baseline_phenotypes", {})
                healthy_ranges        = r.get("healthy_phenotype_ranges", {})
                gene_names_svg        = r.get("gene_names", [])
                signal_labels_svg     = [s["label"] for s in r.get("signals", [])]
                phenotype_labels_svg  = r.get("observable_phenotypes", [])
                aberrant_phenotypes   = r.get("aberrant_phenotypes", [])
                break
        if gene_names_svg:
            break

    parts = [
        "<!DOCTYPE html><html lang='en'><head>",
        "<meta charset='utf-8'>",
        f"<title>Session {meta.get('organism_id','?')} — {disease_str}</title>",
        f"<style>{_CSS}</style>",
        f"<script>{_JS}</script>",
        "</head><body>",
        "<h1>🍋 LEMONOIDS Session Report</h1>",
        f"<div class='meta'>"
        f"{meta.get('organism_id','?')}  ·  seed={meta.get('seed','?')}  ·  "
        f"budget={meta.get('budget','?')}  ·  <b>{disease_str}</b>  ·  "
        f"{meta.get('model','?')}  ·  {meta.get('timestamp','')}"
        f"</div>",
        "<div style='margin-bottom:8px'>",
        "<button onclick='toggleAll(true)'  style='margin-right:6px;background:#111128;"
        "color:#aaa;border:1px solid #333;padding:3px 8px;cursor:pointer'>expand all</button>",
        "<button onclick='toggleAll(false)' style='background:#111128;"
        "color:#aaa;border:1px solid #333;padding:3px 8px;cursor:pointer'>collapse all</button>",
        "</div>",
    ]

    for t_idx, turn in enumerate(turns):
        n     = turn["turn"]
        calls = turn.get("tool_calls", [])
        call_names  = [tc["tool"] for tc in calls]
        summary_str = " · ".join(call_names)
        text  = (turn.get("agent_text") or "").strip()

        # ── Interventions applied in this specific turn ───────────────────
        current_ivs: dict[str, str]         = {}
        current_phenos: dict[str, float] | None = None
        for tc in calls:
            if tc["tool"] in ("run_experiment", "test_rescue"):
                ivs = tc["input"].get("interventions", {})
                # normalise list-of-dicts format (e.g. from gpt-5.1)
                if isinstance(ivs, list):
                    ivs = {item["gene"]: {"type": item.get("mode", "BLOCK")} for item in ivs if "gene" in item}
                for name, val in ivs.items():
                    if isinstance(val, dict):
                        current_ivs[name] = val.get("type", "BLOCK")
                    else:
                        current_ivs[name] = "activate"
                res = tc.get("result", {})
                if isinstance(res, str):
                    try:
                        res = json.loads(res)
                    except Exception:
                        pass
                if res.get("phenotypes"):
                    current_phenos = res["phenotypes"]

        # ── Cumulative discovered network up to and including this turn ───
        discovered_edges = _build_discovered_network(
            turns[: t_idx + 1], baseline_phenos
        )

        # ── Turn card ─────────────────────────────────────────────────────
        parts.append("<details open><summary>")
        parts.append("<div class='turn-header'>")
        parts.append(f"<span class='turn-num'>Turn {n}</span>")
        parts.append(f"<span class='turn-summary'>{_he(summary_str)}</span>")
        parts.append("</div></summary>")
        parts.append("<div class='turn-body'>")

        if text:
            parts.append(f"<div class='reasoning'>{_he(text)}</div>")

        for tc in calls:
            parts.append(_html_tool_call(tc, baseline_phenos, healthy_ranges))

        # ── Network schematic (collapsible, open by default) ──────────────
        if gene_names_svg:
            n_edges = len(discovered_edges)
            edge_summary = f"{n_edges} edge{'s' if n_edges != 1 else ''} discovered"
            if current_ivs:
                iv_str = ", ".join(f"{k} {v}" for k, v in current_ivs.items())
                edge_summary += f" · interventions: {iv_str}"

            agent_svg = _render_network_svg(
                gene_names_svg, signal_labels_svg, phenotype_labels_svg,
                baseline_phenos, discovered_edges, current_phenos, current_ivs,
                aberrant_phenotypes, healthy_ranges,
            )

            if gt_edges:
                gt_svg = _render_network_svg(
                    gene_names_svg, signal_labels_svg, phenotype_labels_svg,
                    baseline_phenos, gt_edges, current_phenos, {},
                    aberrant_phenotypes, healthy_ranges,
                    edge_opacity=0.65,
                )
                _lbl = (
                    "font-size:.7em;color:#475569;margin:0 0 3px;"
                    "font-family:'Courier New',monospace"
                )
                net_html = (
                    f"<div style='display:flex;gap:12px;overflow-x:auto'>"
                    f"<div><div style='{_lbl}'>agent model</div>{agent_svg}</div>"
                    f"<div><div style='{_lbl}'>ground truth</div>{gt_svg}</div>"
                    f"</div>"
                )
            else:
                net_html = agent_svg

            parts.append(
                f"<details open style='margin-top:10px'>"
                f"<summary class='net-summary'>🔬 network state after turn {n}"
                f" &nbsp;·&nbsp; {_he(edge_summary)}</summary>"
            )
            parts.append(net_html)
            parts.append("</details>")

        parts.append("</div></details>")

    # ── Summary table ─────────────────────────────────────────────────────
    parts.append("<hr style='border-color:#2a2a4a;margin:20px 0'>")
    parts.append("<h2 style='color:#FFC107;font-size:.95em'>Session Summary</h2>")
    parts.append("<table class='summary'><tr><th>Metric</th><th>Value</th><th></th></tr>")

    bu = summary.get("budget_used", "?")
    bt = summary.get("budget_total", "?")
    parts.append(f"<tr><td>Budget used</td><td>{bu}/{bt}</td><td></td></tr>")

    acc = summary.get("avg_accuracy")
    mse = summary.get("avg_mse")
    if acc is not None:
        badge = _badge(acc, 0.8, 0.5)
        parts.append(f"<tr><td>Prediction accuracy</td><td>{acc}</td><td>{badge}</td></tr>")
        parts.append(f"<tr><td>Prediction MSE</td><td>{mse}</td><td></td></tr>")

    mh = summary.get("malfunction_hypothesis")
    if mh:
        score = mh["score"]
        badge = _badge(score, 1.0, 0.5)
        parts.append(
            f"<tr><td>Malfunction</td>"
            f"<td>{_he(mh['target_name'])} ({_he(mh['malfunction_type'])})</td>"
            f"<td>{badge} score={score}</td></tr>"
        )

    rr = summary.get("rescue_results", [])
    if rr:
        best     = max(r["restored_fraction"] for r in rr)
        best_mse = min(r["mse_vs_healthy"] for r in rr)
        badge    = _badge(best, 1.0, 0.5)
        parts.append(
            f"<tr><td>Best rescue</td>"
            f"<td>restored={best:.0%}  mse_vs_healthy={best_mse}</td>"
            f"<td>{badge}</td></tr>"
        )

    parts.append("</table>")

    hyp = summary.get("hypothesis")
    if hyp:
        parts.append(
            "<h2 style='color:#FFC107;font-size:.95em;margin-top:14px'>Hypothesis</h2>"
        )
        parts.append(
            f"<div class='reasoning' style='max-height:none'>{_he(hyp)}</div>"
        )

    parts.append("</body></html>")
    return "\n".join(parts)


def _html_tool_call(tc: dict, baseline_phenos: dict, healthy_ranges: dict) -> str:
    tool = tc["tool"]
    inp  = tc["input"]
    res  = tc["result"]

    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass

    color_map = {
        "get_organism_info":             "#2196F3",
        "get_next_prediction_task":      "#2196F3",
        "run_experiment":                "#FF9800",
        "test_rescue":                   "#9C27B0",
        "submit_malfunction_hypothesis": "#F44336",
        "submit_prediction":             "#4CAF50",
        "submit_hypothesis":             "#607D8B",
    }
    border = color_map.get(tool, "#555")
    rows: list[str] = []

    if tool == "get_organism_info":
        bp = res.get("baseline_phenotypes", {})
        if bp:
            rows.append("baseline: " + "  ".join(f"{k}={v:.3f}" for k, v in bp.items()))
        for a in res.get("aberrant_phenotypes", []):
            val = bp.get(a, "?")
            rng = res.get("healthy_phenotype_ranges", {}).get(a, ["?", "?"])
            val_str = f"{val:.3f}" if isinstance(val, float) else str(val)
            rows.append(
                f'<span class="err">⚠ ABERRANT: {a}={val_str} '
                f'[healthy: {rng[0]:.3f}–{rng[1]:.3f}]</span>'
            )

    elif tool == "get_next_prediction_task":
        task_id = res.get("task_id")
        if task_id:
            iv_str = "  ".join(
                f"{g} {v['type']}" if isinstance(v, dict) else f"{g}:{v}"
                for g, v in res.get("interventions", {}).items()
            )
            rows.append(f"{task_id}: {_he(iv_str)}")
            rows.append(f"tasks remaining: {res.get('tasks_remaining', '?')}")
        elif res.get("done"):
            rows.append('<span class="ok">all tasks submitted</span>')

    elif tool == "run_experiment":
        bud = res.get("budget_remaining", "?")
        rows.append(f"budget→{bud}")
        phenos = res.get("phenotypes", {})
        for ph, val in phenos.items():
            base  = baseline_phenos.get(ph)
            delta = f" ({val - base:+.3f})" if base is not None else ""
            hr    = healthy_ranges.get(ph)
            in_range = (hr[0] <= val <= hr[1]) if hr else None
            cls   = "ok" if in_range is True else ("err" if in_range is False else "")
            rows.append(f'<span class="{cls}">{ph}={val:.3f}{delta}</span>')
        if res.get("status") == "max_steps_reached":
            rows.append('<span class="warn">⚠ did not converge</span>')

    elif tool == "test_rescue":
        rf  = res.get("restored_fraction", 0.0)
        mse = res.get("mse_vs_healthy", "?")
        cls = "ok" if rf >= 1.0 else ("warn" if rf >= 0.5 else "err")
        rows.append(f'<span class="{cls}">restored={rf:.0%}  mse_vs_healthy={mse}</span>')
        for ph, ok in res.get("phenotype_in_healthy_range", {}).items():
            val   = res.get("phenotypes", {}).get(ph, float("nan"))
            hr    = healthy_ranges.get(ph, ["?", "?"])
            s_cls = "ok" if ok else "err"
            rows.append(
                f'<span class="{s_cls}">{"✓" if ok else "✗"} '
                f'{ph}={val:.3f} [healthy: {hr[0]:.3f}–{hr[1]:.3f}]</span>'
            )

    elif tool == "submit_malfunction_hypothesis":
        target = inp.get("target_name", "?")
        mtype  = inp.get("malfunction_type", "?")
        rows.append(f"target={_he(target)}  type={_he(mtype)}")
        if "error" in res:
            rows.append(f'<span class="err">ERROR: {_he(str(res["error"]))}</span>')
        else:
            rows.append('<span class="warn">🔒 locked — score revealed at session end</span>')

    elif tool == "submit_prediction":
        task_id = inp.get("task_id", "?")
        acc     = res.get("accuracy", "?")
        mse     = res.get("mse", "?")
        cls     = "ok" if acc == 1.0 else ("warn" if isinstance(acc, float) and acc >= 0.8 else "err")
        rows.append(f"task={task_id}")
        rows.append(f'<span class="{cls}">accuracy={acc}  mse={mse}</span>')
        for ph, d in res.get("details", {}).items():
            ok   = d.get("within_threshold", False)
            gt   = d.get("ground_truth", "?")
            pred = d.get("prediction", "?")
            s_cls = "ok" if ok else "err"
            rows.append(
                f'<span class="{s_cls}">{"✓" if ok else "✗"} '
                f'{ph}: pred={pred}  gt={gt}</span>'
            )

    elif tool == "submit_hypothesis":
        rows.append(f"{res.get('length', 0)} chars stored")

    else:
        if "error" in res:
            rows.append(f'<span class="err">ERROR: {_he(str(res["error"]))}</span>')

    row_html = "".join(f"<div class='result-row'>{r}</div>" for r in rows)
    return (
        f"<div class='tool' style='border-left-color:{border}'>"
        f"<div class='tool-name'>{_he(tool)}</div>"
        f"<div class='tool-io'>{row_html}</div>"
        f"</div>"
    )


def _badge(val: float, good: float, warn: float) -> str:
    if val >= good:
        return "<span class='badge badge-ok'>✓</span>"
    elif val >= warn:
        return "<span class='badge badge-warn'>~</span>"
    else:
        return "<span class='badge badge-err'>✗</span>"


def _he(s: str) -> str:
    """HTML-escape a string."""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
