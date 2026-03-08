"""Made-up but biologically plausible vocabulary — no real gene or pathway names."""

CELL_TYPE_LABELS = [
    "secretory-cell-Q",
    "barrier-cell-X",
    "motile-cell-alpha",
    "contractile-cell-VII",
    "absorptive-cell-B",
    "sensory-cell-R",
    "scaffold-cell-M",
    "signalling-cell-delta",
    "storage-cell-N",
    "transit-cell-epsilon",
    "progenitor-cell-Z",
    "exchange-cell-W",
    "adhesive-cell-P",
    "regulatory-cell-kappa",
    "effector-cell-T",
]

CELL_TYPE_DESCRIPTIONS = [
    "Produces and exports molecular cargo through a regulated secretory pathway.",
    "Maintains selective permeability across tissue boundaries.",
    "Generates directed mechanical force to achieve translocation through the environment.",
    "Converts chemical potential into coordinated mechanical contraction cycles.",
    "Internalises and processes extracellular substrates via membrane transport systems.",
    "Transduces environmental stimuli into intracellular biochemical signals.",
    "Provides structural support and organises the extracellular matrix scaffold.",
    "Synthesises and releases molecular messengers that coordinate neighbouring cells.",
    "Accumulates and mobilises energy-dense molecular reserves under metabolic demand.",
    "Undergoes rapid division and differentiation to replenish specialised cell populations.",
    "Maintains a multipotent state while contributing daughter cells to multiple lineages.",
    "Facilitates bidirectional transport of small molecules across compartment interfaces.",
    "Anchors to substrate and mediates cell–cell contact through surface ligands.",
    "Integrates multiple upstream signals to gate transcriptional output.",
    "Executes terminal effector functions in response to activation thresholds.",
]

MALFUNCTION_TYPES = ["LOCK_HI", "LOCK_LO", "PERSIST"]

MODULE_LABELS = [
    "ion-flux-regulator",
    "redox-oscillator",
    "membrane-cascade-X",
    "thermal-dampener",
    "phase-coordinator",
    "chromatin-relay",
    "voltage-buffer",
    "solute-gate",
    "signal-integrator-alpha",
    "pulse-generator",
    "lateral-amplifier",
    "entropy-sink",
    "cross-modal-coupler",
    "feedback-attenuator",
    "burst-modulator",
    "torsion-relay",
    "gradient-follower",
    "oscillation-dampener",
    "threshold-arbiter",
    "noise-filter-beta",
]

SIGNAL_LABELS = [
    "nutrient-X",
    "ligand-alpha",
    "photon-flux",
    "osmotic-stress",
    "thermal-pulse",
    "ligand-beta",
    "pressure-wave",
    "ion-gradient-A",
    "chemical-Y",
    "redox-signal",
    "field-oscillation",
    "gradient-Z",
    "cascade-trigger",
    "binding-factor-Q",
    "membrane-potential",
]

PHENOTYPE_LABELS = [
    "growth-rate",
    "stress-index",
    "motility-score",
    "energy-state",
    "division-rate",
    "repair-index",
    "signal-output",
    "dormancy-level",
    "adaptation-score",
    "viability-index",
]
