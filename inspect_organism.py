#!/usr/bin/env python
"""🍋 LEMONS — organism inspector CLI.

Usage:
    python inspect_organism.py
    python inspect_organism.py --seed 7 --n-genes 25
    python inspect_organism.py --seed 42 --save org.png --no-show
    python inspect_organism.py --no-plot
"""
import argparse

from bioworld import generate_organism
from bioworld.inspect import print_organism, plot_organism


def main() -> None:
    parser = argparse.ArgumentParser(
        description="🍋 LEMONS organism inspector",
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
    args = parser.parse_args()

    org = generate_organism(
        n_genes=args.n_genes,
        n_modules=args.n_modules,
        seed=args.seed,
    )

    if not args.no_terminal:
        print_organism(org)

    if not args.no_plot:
        show = not args.no_show
        plot_organism(org, save_path=args.save, show=show)


if __name__ == "__main__":
    main()
