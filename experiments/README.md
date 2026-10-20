# Experiments

Each subdirectory is a self-contained study behind a result reported in the
paper. Scripts and small summary artefacts are tracked; per-session logs are
not.

## Layout

```
<study>/
├── run*.py           # sweep / agent runner — writes session logs
├── analyse*.py       # analysis over the session logs
├── plot.py, fig_*.py # visualisation (where present)
├── *.json            # tracked inputs and summary statistics
└── logs/             # per-session agent traces — NOT tracked (regenerate locally)
    ├── *.json        # structured turn-by-turn log
    └── *.html        # self-contained diagnostic report
```

## Studies

| Directory | What it produced |
|-----------|------------------|
| `paper_v1/` | Main benchmark: 10 models × 6 conditions × 20 seeds (1,200 sessions) |
| `scaling_v1/` | Scaling study: network sizes N = 20 … 1280 |
| `vocabulary_ablation/` | Invented vs real vocabulary × prompt permission |
| `backwards_ablation/` | Backwards-inverted organisms; see its own README |

Results for all four are reported in the paper.

## Running an experiment

```bash
# Install the package first
pip install -e .

# Run the main benchmark sweep (writes session logs under logs/)
python experiments/paper_v1/run.py

# Analyse the resulting logs
python experiments/paper_v1/analyse.py
```

> Session logs are gitignored. To share a specific run, copy the relevant
> `logs/*.json` file out and attach it separately, or use
> `luca.report.export_session_html()` to produce a standalone HTML report.
