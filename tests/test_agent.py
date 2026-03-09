"""Tests for agent routing and tool dispatch."""
import pytest
from lemonoids import generate_organism, ExperimentSession
from lemonoids.agent import run_agent, dispatch_tool, _ANTHROPIC_PREFIXES, _OPENAI_PREFIXES


def test_run_agent_routes_anthropic():
    from lemonoids.agent import _run_agent_anthropic
    # run_agent with a claude- model should call _run_agent_anthropic
    # We verify routing without making API calls by checking ValueError is NOT raised
    # and that an ImportError/AuthError would come from the provider, not from routing
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    # Should route without raising ValueError
    try:
        run_agent(session, model="claude-opus-4-6", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_run_agent_routes_openai():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    try:
        run_agent(session, model="gpt-5.1", max_turns=1)
    except Exception as e:
        assert "Cannot infer provider" not in str(e), f"Routing failed: {e}"


def test_run_agent_unknown_model_raises():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    with pytest.raises(ValueError, match="Cannot infer provider"):
        run_agent(session, model="llama-3-70b")


def test_dispatch_tool_get_organism_info():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    result = dispatch_tool(session, "get_organism_info", {})
    assert "gene_names" in result
    assert "observable_phenotypes" in result


def test_dispatch_tool_run_experiment():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    result = dispatch_tool(session, "run_experiment", {"interventions": {gene: {"type": "BLOCK"}}})
    assert "phenotypes" in result


def test_dispatch_tool_run_experiment_json_string():
    """Agent sometimes serializes interventions as a JSON string — should be unwrapped."""
    import json
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    gene = session.get_info()["gene_names"][0]
    interventions_str = json.dumps({gene: {"type": "BLOCK"}})
    result = dispatch_tool(session, "run_experiment", {"interventions": interventions_str})
    assert "phenotypes" in result


def test_dispatch_tool_unknown():
    org = generate_organism(seed=0)
    session = ExperimentSession(org, budget=5)
    result = dispatch_tool(session, "nonexistent_tool", {})
    assert "error" in result
