"""Tests for non-LLM baselines (no API keys required)."""
import pytest
from luca import generate_organism, generate_disease_organism, ExperimentSession
from luca.baselines import run_random, run_heuristic, run_causal_sweep


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
