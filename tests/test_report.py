"""Agreement tests: the trace the reader sees must match what the engine ran.

`report.py` renders a stored session. It reads the same `tool_input` the tool
layer read, so the two must resolve a payload the same way. Issue 13 made the
tool layer apply the flat form `{"G001": "BLOCK"}`. `report.py` kept reading
the `interventions` key alone, so a flat experiment ran in the engine and then
vanished from the trace and from edge inference.
"""
import io
import contextlib

from luca import generate_organism, ExperimentSession
from luca.agent import dispatch_tool
from luca import report


def _session(budget=5):
    session = ExperimentSession(generate_organism(seed=0), budget=budget, seed=0)
    return session.get_info()["gene_names"][0], session


def _traced(payload):
    """Run one experiment through the tool layer and return (tc, baseline)."""
    gene, session = _session()
    baseline = session.get_info()["baseline_phenotypes"]
    result = dispatch_tool(session, "run_experiment", payload)
    assert "error" not in result, result
    tc = {"tool": "run_experiment", "input": payload, "result": result}
    return gene, session, baseline, tc


def _render(tc, baseline):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report._print_tool_call(tc, baseline, {})
    return buf.getvalue()


class TestTraceAgreesWithTheEngine:

    def test_flat_payload_is_named_in_the_trace(self):
        gene, session, baseline, tc = _traced({"G001": "BLOCK"})
        applied = session._experiment_log[-1]["interventions"]
        assert applied != {}, "precondition: the engine applied the flat form"
        out = _render(tc, baseline)
        assert "G001" in out, f"engine ran {applied} but the trace says: {out!r}"
        assert "∅" not in out

    def test_flat_payload_reaches_edge_inference(self):
        """_build_discovered_network takes turns, each holding tool_calls."""
        _gene, _session, baseline, tc = _traced({"G001": "BLOCK"})
        turns = [{"tool_calls": [tc]}]
        edges = report._build_discovered_network(turns, baseline)
        assert edges, "a single-gene flat experiment must yield an edge"
        assert edges[0]["from"] == "G001"

    def test_gene_interventions_key_is_named_in_the_trace(self):
        _gene, _session, baseline, tc = _traced(
            {"gene_interventions": {"G001": {"type": "BLOCK"}}}
        )
        out = _render(tc, baseline)
        assert "G001" in out, f"the trace says: {out!r}"

    def test_wrapped_payload_still_renders(self):
        _gene, _session, baseline, tc = _traced(
            {"interventions": {"G001": {"type": "BLOCK"}}}
        )
        assert "G001" in _render(tc, baseline)

    def test_deliberate_null_experiment_renders_as_empty(self):
        _gene, _session, baseline, tc = _traced({"interventions": {}})
        assert "∅" in _render(tc, baseline)
