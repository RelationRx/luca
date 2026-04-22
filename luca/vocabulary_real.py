"""Real biology gene names for the vocabulary ablation experiment.

These are real human gene names drawn from three tiers of familiarity.
Used when generate_organism(..., vocabulary="real") to test whether
prior knowledge from training data affects LLM performance.

The GRN topology is identical — only the gene name strings change.
Names are shuffled per seed so the mapping is random across organisms.
"""

# Tier 1 — Textbook genes (heavily in training data, strong functional priors)
TIER1_GENES = [
    "TP53", "BRCA1", "EGFR", "MYC", "KRAS", "RB1", "AKT1", "PTEN",
    "BRAF", "PIK3CA", "VEGFA", "TNF", "IL6", "NOTCH1", "WNT1", "SHH",
    "MAPK1", "JAK2",
]

# Tier 2 — Well-known but less iconic
TIER2_GENES = [
    "FOXP3", "SOX2", "STAT3", "SMAD4", "CDH1", "CTNNB1", "FGFR2", "ERBB2",
    "HDAC1", "SIRT1", "MTOR", "GSK3B", "TGFB1", "RAF1", "MEK1", "DICER1",
]

# Tier 3 — Less-studied / niche
TIER3_GENES = [
    "LMNA", "PPARG", "CEBPA", "KDM5A", "SETD2", "ARID1A", "STAG2", "KMT2D",
    "FBXW7", "NSD1", "BCOR", "CREBBP", "EP300", "PHF6", "CUX1", "ASXL1",
]

# Full pool (50 genes)
REAL_GENE_NAMES = TIER1_GENES + TIER2_GENES + TIER3_GENES
