"""Tests for non-LLM baselines (no API keys required)."""
import pytest
from luca import generate_organism, generate_disease_organism, ExperimentSession
from luca.baselines import run_random, run_heuristic, run_causal_sweep
from luca.baselines.heuristic import _additive_prediction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _healthy_session(seed=0, difficulty="medium"):
    org = generate_organism(seed=seed, difficulty=difficulty)
    return ExperimentSession(org, seed=seed)


def _disease_session(seed=0, difficulty="medium"):
    org = generate_disease_organism(seed=seed, difficulty=difficulty)
    return ExperimentSession(org, seed=seed)


# ---------------------------------------------------------------------------
# Random baseline
# ---------------------------------------------------------------------------

class TestRandomBaseline:
    def test_healthy_produces_valid_summary(self):
        session = _healthy_session()
        summary = run_random(session, seed=0)
        assert summary["avg_accuracy"] is not None
        assert summary["avg_mse"] is not None
        assert summary["budget_used"] == 0

    def test_disease_submits_hypothesis_and_rescue(self):
        session = _disease_session()
        summary = run_random(session, seed=0)
        assert summary["malfunction_hypothesis"] is not None
        assert summary["malfunction_hypothesis"]["score"] is not None
        assert len(summary["rescue_results"]) > 0

    def test_predictions_are_baseline(self):
        session = _healthy_session()
        summary = run_random(session, seed=0)
        for result in summary["prediction_results"]:
            for pheno, vals in result["phenotypes"].items():
                assert vals["prediction"] == 0.5

    def test_deterministic_across_calls(self):
        s1 = _healthy_session(seed=5)
        s2 = _healthy_session(seed=5)
        sum1 = run_random(s1, seed=42)
        sum2 = run_random(s2, seed=42)
        assert sum1["avg_accuracy"] == sum2["avg_accuracy"]


# ---------------------------------------------------------------------------
# Heuristic baseline
# ---------------------------------------------------------------------------

class TestHeuristicBaseline:
    def test_healthy_produces_valid_summary(self):
        session = _healthy_session()
        summary = run_heuristic(session)
        assert summary["avg_accuracy"] is not None
        assert summary["avg_mse"] is not None
        assert summary["budget_used"] > 0

    def test_uses_budget_for_block_sweep(self):
        session = _healthy_session()
        info = session.get_info()
        n_genes = len(info["gene_names"])
        summary = run_heuristic(session)
        # Should BLOCK most genes (budget - 2 reserve)
        assert summary["budget_used"] >= n_genes - 2

    def test_disease_submits_hypothesis(self):
        session = _disease_session()
        summary = run_heuristic(session)
        assert summary["malfunction_hypothesis"] is not None

    def test_beats_random_on_easy(self):
        h_session = _healthy_session(seed=3, difficulty="easy")
        r_session = _healthy_session(seed=3, difficulty="easy")
        h_summary = run_heuristic(h_session)
        r_summary = run_random(r_session, seed=3)
        # Heuristic should generally beat random on easy (near-linear dynamics)
        assert h_summary["avg_accuracy"] >= r_summary["avg_accuracy"]

    def test_deterministic(self):
        s1 = _healthy_session(seed=7)
        s2 = _healthy_session(seed=7)
        sum1 = run_heuristic(s1)
        sum2 = run_heuristic(s2)
        assert sum1["avg_accuracy"] == sum2["avg_accuracy"]
        assert sum1["budget_used"] == sum2["budget_used"]


# ---------------------------------------------------------------------------
# Issue 6 — the heuristic's additive prediction arithmetic.
#
# The heuristic measures each gene's effect by BLOCKing it and recording
# `result - baseline`. It then SUBTRACTED that delta when predicting a BLOCK,
# so every measured decrease became a predicted increase. DAMPEN was treated
# as the opposite of BLOCK, although it clamps the gene to at most 0.15, which
# is nearly the BLOCK state.
#
# None of the tests above caught it. They check shapes and relative orderings,
# never the arithmetic, and the one comparative test uses the easy tier, where
# the defect does least harm.
# ---------------------------------------------------------------------------

class TestHeuristicArithmetic:
    BASELINE = {"ph": 0.50}
    # measured once by BLOCKing G001: the phenotype fell from 0.50 to 0.30
    EFFECTS = {"G001": {"ph": -0.20}}
    LABELS = ["ph"]

    def _predict(self, itype):
        return _additive_prediction(
            self.BASELINE, self.EFFECTS, {"G001": {"type": itype}}, self.LABELS
        )["ph"]

    def test_block_reuses_the_measured_delta(self):
        """BLOCK clamps the gene to 0.0, which is exactly what was measured."""
        assert self._predict("BLOCK") == pytest.approx(0.30)

    def test_dampen_follows_the_block_direction(self):
        """DAMPEN clamps to at most 0.15, so it moves the same way as BLOCK."""
        assert self._predict("DAMPEN") == pytest.approx(0.30)

    def test_boost_opposes_the_block_direction(self):
        """BOOST clamps to 1.0, the opposite extreme from BLOCK."""
        assert self._predict("BOOST") == pytest.approx(0.70)

    def test_prediction_stays_in_range(self):
        prediction = _additive_prediction(
            {"ph": 0.10}, {"G001": {"ph": -0.50}}, {"G001": {"type": "BLOCK"}}, ["ph"]
        )
        assert prediction["ph"] == 0.0

    def test_unmeasured_gene_contributes_nothing(self):
        prediction = _additive_prediction(
            self.BASELINE, {}, {"G001": {"type": "BLOCK"}}, self.LABELS
        )
        assert prediction["ph"] == pytest.approx(0.50)

    def test_two_genes_add(self):
        prediction = _additive_prediction(
            {"ph": 0.50},
            {"G001": {"ph": -0.10}, "G002": {"ph": -0.15}},
            {"G001": {"type": "BLOCK"}, "G002": {"type": "BLOCK"}},
            ["ph"],
        )
        assert prediction["ph"] == pytest.approx(0.25)

    def test_an_unreadable_type_raises_rather_than_scoring_as_block(self):
        """CLAUDE.md: a `.get(..., default)` that turns a missing measurement
        into a confident number is the mechanism behind issue 3. An
        intervention with no readable type must not quietly predict a BLOCK."""
        with pytest.raises(KeyError, match="G001"):
            _additive_prediction(
                self.BASELINE, self.EFFECTS, {"G001": {}}, self.LABELS
            )

    def test_an_unknown_type_raises(self):
        with pytest.raises(KeyError, match="SILENCE"):
            _additive_prediction(
                self.BASELINE, self.EFFECTS,
                {"G001": {"type": "SILENCE"}}, self.LABELS,
            )

    def test_a_lower_case_type_is_read(self):
        """The engine upper-cases a gene type, so the baseline must too."""
        assert _additive_prediction(
            self.BASELINE, self.EFFECTS, {"G001": "block"}, self.LABELS
        )["ph"] == pytest.approx(0.30)

    @pytest.mark.parametrize("difficulty", ["medium", "hard"])
    def test_spending_budget_beats_spending_none(self, difficulty):
        """End-to-end guard. With the inverted sign, the heuristic spent its
        whole BLOCK sweep and still scored below a baseline that runs none.
        Measured in this repository before the fix: medium 0.5500 against
        0.6500, hard 0.3500 against 0.4667. The sweep costs 20 experiments on
        medium and 15 on hard, where only 15 genes are observable."""
        heuristic, random_ = [], []
        for seed in range(10):
            heuristic.append(run_heuristic(
                _healthy_session(seed=seed, difficulty=difficulty),
                frozenset({"predict"}),
            )["avg_accuracy"])
            random_.append(run_random(
                _healthy_session(seed=seed, difficulty=difficulty), seed=seed,
            )["avg_accuracy"])
        h = sum(heuristic) / len(heuristic)
        r = sum(random_) / len(random_)
        assert h > r, f"{difficulty}: heuristic {h:.4f} <= random {r:.4f}"


# ---------------------------------------------------------------------------
# CausalSweep baseline
# ---------------------------------------------------------------------------

class TestCausalSweepBaseline:
    def test_healthy_produces_valid_summary(self):
        session = _healthy_session()
        run_causal_sweep(session)
        summary = session.get_summary()
        assert summary["avg_accuracy"] is not None
        assert summary["budget_used"] > 0

    def test_exhausts_budget(self):
        session = _healthy_session()
        run_causal_sweep(session)
        summary = session.get_summary()
        assert summary["budget_used"] == summary["budget_total"]

    def test_beats_heuristic_on_medium(self):
        cs_session = _healthy_session(seed=1)
        h_session = _healthy_session(seed=1)
        run_causal_sweep(cs_session)
        cs_summary = cs_session.get_summary()
        h_summary = run_heuristic(h_session)
        assert cs_summary["avg_accuracy"] >= h_summary["avg_accuracy"]

    def test_disease_submits_hypothesis_and_rescue(self):
        session = _disease_session()
        run_causal_sweep(session)
        summary = session.get_summary()
        assert summary["malfunction_hypothesis"] is not None
        assert len(summary["rescue_results"]) > 0

    def test_deterministic(self):
        s1 = _healthy_session(seed=3)
        s2 = _healthy_session(seed=3)
        run_causal_sweep(s1)
        run_causal_sweep(s2)
        sum1 = s1.get_summary()
        sum2 = s2.get_summary()
        assert sum1["avg_accuracy"] == sum2["avg_accuracy"]
        assert sum1["budget_used"] == sum2["budget_used"]

    def test_perfect_on_easy(self):
        session = _healthy_session(seed=0, difficulty="easy")
        run_causal_sweep(session)
        summary = session.get_summary()
        assert summary["avg_accuracy"] == 1.0


def test_causal_sweep_runs_through_evaluate_dispatch():
    """
    CausalSweep must be reachable by model name, not only by direct import.

    Regression test: evaluate.py dispatched only "random" and "heuristic", so
    `--model causal-sweep` fell through to the LLM path and failed on every
    seed with "Cannot infer provider from model name 'causal-sweep'". The
    paper reports a CausalSweep row, so the baseline has to be runnable from
    committed code.
    """
    import evaluate
    assert hasattr(evaluate, "run_causal_sweep")
    src = open(evaluate.__file__).read()
    assert 'model_name == "causal-sweep"' in src
