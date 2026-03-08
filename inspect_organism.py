#!/usr/bin/env python
"""🍋 LEMONOIDS — organism inspector CLI.

Usage:
    python inspect_organism.py
    python inspect_organism.py --seed 7 --n-genes 25
    python inspect_organism.py --seed 42 --save org.png --no-show
    python inspect_organism.py --no-plot
    python inspect_organism.py --disease --seed 7 --no-show --save /tmp/disease.png
    python inspect_organism.py --replay --seed 42 --no-show --save replay.png
    python inspect_organism.py --replay --disease --seed 42 --budget 15 --no-show --save replay.png
"""
import argparse
import os

from lemonoids import generate_organism, generate_disease_organism
from lemonoids.inspect import print_organism, plot_organism, plot_disease_organism


def main() -> None:
    parser = argparse.ArgumentParser(
        description="🍋 LEMONOIDS organism inspector",
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
    parser.add_argument("--replay", action="store_true",
                        help="Run an agent session and visualise the experiment replay heatmap "
                             "(requires ANTHROPIC_API_KEY)")
    parser.add_argument("--budget", type=int, default=None,
                        help="Experiment budget for --replay sessions "
                             "(default: auto = n_genes + n_signals + 8)")
    parser.add_argument("--all-genes", action="store_true",
                        help="Show all genes in --replay heatmap (default: observable only)")
    parser.add_argument("--log", type=str, default=None, metavar="PATH",
                        help="Save agent session log to this JSON path (e.g. logs/run.json)")
    parser.add_argument("--trace", action="store_true",
                        help="Print a human-readable turn-by-turn trace after --replay")
    args = parser.parse_args()

    # ── Generate organism ────────────────────────────────────────────────────
    if args.disease:
        org = generate_disease_organism(
            n_genes=args.n_genes,
            n_modules=args.n_modules,
            seed=args.seed,
        )
    else:
        org = generate_organism(
            n_genes=args.n_genes,
            n_modules=args.n_modules,
            seed=args.seed,
        )

    # ── Replay mode ──────────────────────────────────────────────────────────
    if args.replay:
        from lemonoids import ExperimentSession
        from lemonoids.agent import run_agent
        from lemonoids.inspect import plot_session

        import json as _json
        from lemonoids.report import print_session_trace, export_session_html

        from lemonoids.experiment import recommended_budget
        budget = args.budget if args.budget is not None else recommended_budget(org)
        session = ExperimentSession(org, budget=budget, seed=args.seed)
        print(f"Running agent session (budget={budget}, disease={args.disease})…")
        run_agent(session, model="claude-opus-4-6", max_turns=50, verbose=True,
                  log_path=args.log)

        # Load log for diagnostics (only if saved)
        agent_log = None
        if args.log and os.path.exists(args.log):
            with open(args.log) as f:
                agent_log = _json.load(f)
            # Auto-generate HTML report alongside the JSON log
            html_path = args.log.rsplit(".", 1)[0] + ".html"
            export_session_html(agent_log, html_path)
            if args.trace:
                print_session_trace(agent_log)

        show = not args.no_show
        plot_session(
            session,
            save_path=args.save,
            show=show,
            observable_only=not args.all_genes,
            agent_log=agent_log,
        )
        return

    # ── Standard inspect mode ────────────────────────────────────────────────
    if not args.no_terminal:
        print_organism(org)

    if not args.no_plot:
        show = not args.no_show
        if args.disease:
            plot_disease_organism(org, save_path=args.save, show=show)
        else:
            plot_organism(org, save_path=args.save, show=show)


if __name__ == "__main__":
    main()
