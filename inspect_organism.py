#!/usr/bin/env python
"""LUCA — organism inspector CLI.

Usage:
    python inspect_organism.py
    python inspect_organism.py --seed 7 --n-genes 25
    python inspect_organism.py --seed 42 --save org.png --no-show
    python inspect_organism.py --no-plot
    python inspect_organism.py --difficulty hard --seed 3
    python inspect_organism.py --disease --seed 7 --no-show --save /tmp/disease.png
    python inspect_organism.py --disease --compare --seed 42 --no-show --save /tmp/compare.png
    python inspect_organism.py --replay --seed 42 --log logs/run.json
    python inspect_organism.py --replay --model gpt-4o --seed 42 --log logs/run.json
    python inspect_organism.py --replay --disease --seed 42 --budget 15 --log logs/run.json
"""
import argparse
import os

# Auto-load .env if present (so API keys don't need to be manually exported)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

from luca import generate_organism, generate_disease_organism
from luca.inspect import print_organism, print_disease_organism, plot_organism, plot_disease_organism, plot_disease_comparison


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LUCA organism inspector",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--seed", type=int, default=42, help="Organism seed")
    parser.add_argument("--n-genes", type=int, default=15, help="Number of genes")
    parser.add_argument("--n-modules", type=int, default=4, help="Number of modules")
    parser.add_argument("--save", type=str, default=None, metavar="PATH",
                        help="Save plot to this path (e.g. org.png)")
    parser.add_argument("--no-show", action="store_true",
                        help="Don't open an interactive plot window")
    parser.add_argument("--no-terminal", action="store_true",
                        help="Skip the rich terminal summary")
    parser.add_argument("--no-plot", action="store_true",
                        help="Skip the matplotlib figure entirely")
    parser.add_argument("--disease", action="store_true",
                        help="Generate and visualise a disease organism")
    parser.add_argument("--compare", action="store_true",
                        help="When used with --disease, show a side-by-side healthy vs disease "
                             "GRN comparison (plot_disease_comparison) instead of the single-panel "
                             "disease plot")
    parser.add_argument("--difficulty", default="medium",
                        metavar="TIER",
                        help="Organism difficulty tier: easy / medium / hard "
                             "(or prokaryote / simple_eukaryote / complex_eukaryote)")
    parser.add_argument("--replay", action="store_true",
                        help="Run an agent session and save an HTML report (requires API key)")
    parser.add_argument("--model", type=str, default="claude-opus-4-6",
                        metavar="MODEL",
                        help="Model to use for --replay sessions (default: claude-opus-4-6)")
    parser.add_argument("--budget", type=int, default=None,
                        help="Experiment budget for --replay sessions "
                             "(default: auto = n_genes + n_signals + 8)")
    parser.add_argument("--log", type=str, default=None, metavar="PATH",
                        help="Save agent session log to this JSON path and generate HTML report "
                             "(e.g. logs/run.json)")
    parser.add_argument("--trace", action="store_true",
                        help="Print a human-readable turn-by-turn trace after --replay")
    args = parser.parse_args()

    # ── Generate organism ────────────────────────────────────────────────────
    if args.disease:
        org = generate_disease_organism(
            n_genes=args.n_genes,
            n_modules=args.n_modules,
            seed=args.seed,
            difficulty=args.difficulty,
        )
    else:
        org = generate_organism(
            n_genes=args.n_genes,
            n_modules=args.n_modules,
            seed=args.seed,
            difficulty=args.difficulty,
        )

    # ── Replay mode ──────────────────────────────────────────────────────────
    if args.replay:
        from luca import ExperimentSession
        from luca.agent import run_agent

        import json as _json
        from luca.report import print_session_trace, export_session_html

        from luca.experiment import recommended_budget
        budget = args.budget if args.budget is not None else recommended_budget(org)
        session = ExperimentSession(org, budget=budget, seed=args.seed)
        print(f"Running agent session (budget={budget}, disease={args.disease})…")
        run_agent(session, model=args.model, max_turns=50, verbose=True,
                  log_path=args.log)

        if args.log and os.path.exists(args.log):
            with open(args.log) as f:
                agent_log = _json.load(f)
            html_path = args.log.rsplit(".", 1)[0] + ".html"
            export_session_html(agent_log, html_path)
            print(f"HTML report → {html_path}")
            if args.trace:
                print_session_trace(agent_log)
        return

    # ── Standard inspect mode ────────────────────────────────────────────────
    if not args.no_terminal:
        if args.disease:
            print_disease_organism(org)
        else:
            print_organism(org)

    if not args.no_plot:
        show = not args.no_show
        if args.disease and args.compare:
            plot_disease_comparison(org, save_path=args.save, show=show)
        elif args.disease:
            plot_disease_organism(org, save_path=args.save, show=show)
        else:
            plot_organism(org, save_path=args.save, show=show)


if __name__ == "__main__":
    main()
