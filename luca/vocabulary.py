"""Made-up vocabulary — abstract functional terms, no real biological system names."""

from itertools import product as _product


def _make_labels(base: list[str], *word_groups: list[str], target: int) -> list[str]:
    """Return base labels extended with combinatorial names until target length.

    Combines word_groups with hyphens (e.g. ["spectral"] × ["flux"] × ["relay"]
    → "spectral-flux-relay"). Existing base labels are always preserved first;
    combinations are added only as needed and duplicates are skipped.
    """
    result = list(base)
    seen = set(base)
    for combo in _product(*word_groups):
        if len(result) >= target:
            break
        label = "-".join(combo)
        if label not in seen:
            result.append(label)
            seen.add(label)
    return result

CELL_TYPE_LABELS = [
    "emitter-cell-Q",
    "filter-cell-X",
    "mobile-cell-alpha",
    "actuator-cell-VII",
    "intake-cell-B",
    "detector-cell-R",
    "frame-cell-M",
    "relay-cell-delta",
    "buffer-cell-N",
    "carrier-cell-epsilon",
    "source-cell-Z",
    "bridge-cell-W",
    "anchor-cell-P",
    "control-cell-kappa",
    "executor-cell-T",
]

CELL_TYPE_DESCRIPTIONS = [
    "Packages and exports internal cargo through a regulated output channel.",
    "Maintains selective throughput across compartment boundaries.",
    "Generates directed force to achieve translocation through the environment.",
    "Converts stored potential into coordinated mechanical output cycles.",
    "Internalises and processes external inputs via surface intake systems.",
    "Transduces environmental stimuli into internal state changes.",
    "Provides structural support and organises the surrounding scaffold.",
    "Synthesises and releases coordinator signals to neighbouring units.",
    "Accumulates and mobilises reserves under demand conditions.",
    "Transfers state between compartments without undergoing transformation.",
    "Maintains a generative state while producing output units to multiple channels.",
    "Facilitates bidirectional transfer of small quantities across interface zones.",
    "Anchors to substrate and mediates unit–unit contact through surface coupling.",
    "Integrates multiple upstream signals to gate downstream output.",
    "Executes terminal output functions in response to activation thresholds.",
]

MALFUNCTION_TYPES = ["LOCK_HI", "LOCK_LO", "PERSIST"]

_MODULE_BASE = [
    "charge-flow-regulator",
    "polarity-oscillator",
    "boundary-cascade-X",
    "thermal-dampener",
    "phase-coordinator",
    "topology-relay",
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

_MODULE_MODIFIERS = ["spectral", "resonant", "cascade", "lateral", "diffuse",
                     "cyclic", "torsional", "angular", "radial", "temporal"]
_MODULE_NOUNS     = ["flow", "pulse", "flux", "wave", "gradient",
                     "field", "charge", "phase", "pressure", "signal"]
_MODULE_TYPES     = ["regulator", "buffer", "relay", "gate", "coupler",
                     "integrator", "dampener", "modulator", "arbiter", "distributor"]

# 20 curated + up to 1000 combinatorial — sufficient for any practical N
MODULE_LABELS = _make_labels(
    _MODULE_BASE,
    _MODULE_MODIFIERS, _MODULE_NOUNS, _MODULE_TYPES,
    target=1000,
)

_SIGNAL_BASE = [
    "substrate-X",
    "factor-alpha",
    "photon-flux",
    "flux-stress",
    "thermal-pulse",
    "factor-beta",
    "pressure-wave",
    "polarity-gradient-A",
    "chemical-Y",
    "polarity-signal",
    "field-oscillation",
    "gradient-Z",
    "cascade-trigger",
    "coupling-factor-Q",
    "interface-potential",
]

_SIGNAL_TYPES    = ["factor", "flux", "wave", "gradient", "pulse",
                    "signal", "potential", "cascade", "field", "trigger",
                    "current", "burst", "shift", "oscillation", "impulse"]
_SIGNAL_SUFFIXES = ["alpha", "beta", "gamma", "delta", "epsilon",
                    "A", "B", "C", "Q", "R", "X", "Y", "Z", "I", "II",
                    "zeta", "eta", "theta", "kappa", "lambda"]

# 15 curated + up to 300 combinatorial (covers N up to ~2000)
SIGNAL_LABELS = _make_labels(
    _SIGNAL_BASE,
    _SIGNAL_TYPES, _SIGNAL_SUFFIXES,
    target=300,
)

PHENOTYPE_LABELS = [
    "expansion-rate",
    "stress-index",
    "displacement-score",
    "energy-state",
    "replication-index",
    "recovery-index",
    "signal-output",
    "standby-level",
    "adaptation-score",
    "integrity-index",
]
