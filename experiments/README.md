# Experiments

Each subdirectory is a self-contained study. Scripts are tracked; per-session logs are not.

## Layout

```
<study>/
├── run_*.py          # sweep / agent runner — generates results_*.jsonl
├── fig_*.py          # visualisation — reads results and saves *.png
├── results*.jsonl    # summary results (tracked, one record per run)
├── metadata.json     # run configuration (tracked, if present)
└── logs/             # per-session agent traces — NOT tracked (regenerate locally)
    ├── *.json        # structured turn-by-turn log
    └── *.html        # self-contained diagnostic report
```

## Studies

| Directory | Description |
|-----------|-------------|
| `scaling_study_v1/` | Main scaling sweep: n_genes × budget × seed |
| `difficulty_pilot/` | Difficulty tier pilot: easy / medium / hard comparison |
| `difficulty_2d/` | 2D grid: n_genes × difficulty, single seed |
| `medium_vs_hard/` | Medium vs hard difficulty at varying n_genes |
| `harder_regimes/` | Large n (75–100) and budget sensitivity; heuristic baseline |

## Running an experiment

```bash
# Install the package first
pip install -e .

# Run a sweep (generates results*.jsonl and logs/)
python experiments/scaling_study_v1/run_sweep.py

# Plot results (reads results*.jsonl, saves *.png)
python experiments/scaling_study_v1/fig_paper_main.py
```

> Session logs are gitignored. To share a specific run, copy the relevant
> `logs/*.json` file out and attach it separately, or use
> `lemonoids.report.export_session_html()` to produce a standalone HTML report.
