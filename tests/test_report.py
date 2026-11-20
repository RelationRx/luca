"""Agreement tests: the trace the reader sees must match what the engine ran.

`report.py` renders a stored session. It reads the same `tool_input` the tool
layer read, so the two must resolve a payload the same way. Issue 13 made the
tool layer apply the flat form `{"G001": "BLOCK"}`. `report.py` kept reading
the `interventions` key alone, so a flat experiment ran in the engine and then
vanished from the trace and from edge inference.
"""
import io
import pytest
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


class TestJsonStringPayloadAgrees:
    """Review finding 5. `_normalise_interventions` decodes a JSON-string
    payload; the shared resolver did not, so the trace raised AttributeError on
    a shape the engine applies. One shared reading means one shared decode."""

    PAYLOAD = {"interventions": '{"G001": {"type": "BLOCK"}}'}

    def test_the_engine_applies_a_json_string_payload(self):
        _gene, session = _session()
        dispatch_tool(session, "run_experiment", dict(self.PAYLOAD))
        assert "G001" in session._experiment_log[-1]["interventions"]

    def test_the_trace_names_the_gene_rather_than_raising(self):
        _gene, session, baseline, tc = _traced(dict(self.PAYLOAD))
        out = _render(tc, baseline)
        assert "G001" in out, f"the trace says: {out!r}"

    def test_edge_inference_reads_a_json_string_payload(self):
        _gene, _session, baseline, tc = _traced(dict(self.PAYLOAD))
        edges = report._build_discovered_network([{"tool_calls": [tc]}], baseline)
        assert edges and edges[0]["from"] == "G001"


class TestTheSharedReadingIsCanonical:
    """Round 3 of the review. `_tool_call_iv` returned whatever shape the model
    sent, while the engine normalises: `_resolve_interventions` upper-cases the
    type and wraps it. Three defects shared that one cause — the HTML schematic
    labelled every string value `activate`, a lowercase type never reached edge
    inference, and a non-dict payload raised while rendering.

    Gene types are upper case here; a signal action stays lower case, so the
    rendered trace shows the verb the agent sent.
    """

    def test_a_flat_string_value_becomes_a_typed_dict(self):
        assert report._tool_call_iv({"G001": "BLOCK"}) == {"G001": {"type": "BLOCK"}}

    def test_a_lowercase_type_is_upper_cased(self):
        assert report._tool_call_iv({"G001": "block"}) == {"G001": {"type": "BLOCK"}}

    def test_a_signal_action_keeps_its_lower_case_form(self):
        assert report._tool_call_iv({"wave-X": "activate"}) == {
            "wave-X": {"type": "activate"}
        }

    def test_a_lowercase_type_reaches_edge_inference(self):
        _gene, _session, baseline, tc = _traced({"G001": "block"})
        edges = report._build_discovered_network([{"tool_calls": [tc]}], baseline)
        assert edges and edges[0]["from"] == "G001"

    def test_a_non_dict_payload_reads_as_empty(self):
        assert report._tool_call_iv({"interventions": 42}) == {}
        assert report._tool_call_iv({"interventions": "BLOCK G001"}) == {}

    def test_a_non_dict_payload_renders_without_raising(self):
        base = {"energy-state": 0.5}
        tc = {"tool": "run_experiment", "input": {"interventions": 42},
              "result": {"phenotypes": base, "budget_remaining": 1}}
        assert "∅" in _render(tc, base)

    def test_a_double_encoded_json_payload_renders(self):
        import json as _json
        payload = {"interventions": _json.dumps(_json.dumps({"G001": {"type": "BLOCK"}}))}
        _gene, _session, baseline, tc = _traced(dict(payload))
        assert "G001" in _render(tc, baseline)


class TestTheTwoReadersCannotDisagree:
    """A targeted review of luca/payloads.py. `canonical_interventions` had its
    own copy of the entry-reading rule, and the copy disagreed with the engine:
    the target precedence was reversed, the action precedence differed and
    omitted `intervention`, and a missing action defaulted to BLOCK where the
    engine refuses the call. A module written to hold one reading held two.
    """

    CASES = [
        {"interventions": [{"target": "G001", "gene": "G002", "mode": "BOOST"}]},
        {"interventions": [{"gene": "G001", "action": "BOOST", "mode": "BLOCK"}]},
        {"interventions": [{"gene": "G001", "intervention": "BOOST"}]},
        {"interventions": [{"name": "G001", "type": "DAMPEN"}]},
        {"interventions": {"G001": "block"}},
        {"interventions": {"G001": {"type": "BOOST"}}},
    ]

    @pytest.mark.parametrize("payload", CASES)
    def test_the_trace_reads_what_the_engine_reads(self, payload):
        """The agreement that matters: which gene the simulator perturbs, and
        with which type. `_resolve_interventions` is the last word on that."""
        from luca.agent import _normalise_interventions
        _gene, session = _session()
        normalised = _normalise_interventions(payload["interventions"])
        assert isinstance(normalised, dict), normalised
        resolved = session._resolve_interventions(normalised)
        assert not isinstance(resolved, dict), resolved
        gene_ids, _signals = resolved
        id_to_name = {g.id: g.name for g in session.organism.genes}
        expected = {id_to_name[gid]: iv["type"] for gid, iv in gene_ids.items()}
        actual = {t: v["type"] for t, v in report._tool_call_iv(payload).items()}
        assert actual == expected

    def test_an_entry_with_no_action_is_dropped_not_guessed(self):
        """The engine refuses the whole call, so the trace must not invent a
        BLOCK experiment that never ran."""
        assert report._tool_call_iv({"interventions": [{"gene": "G001"}]}) == {}

    def test_an_invented_container_is_not_shown_as_a_target(self):
        """472 stored calls used a container name the engine refuses. The trace
        showed `perturbations` and `BLOCK` as if they were genes."""
        assert report._tool_call_iv({"perturbations": {"G001": "BLOCK"}}) == {}
        assert report._tool_call_iv({"BLOCK": ["G001"]}) == {}

    def test_a_signal_action_survives(self):
        assert report._tool_call_iv({"wave-X": "activate"}) == {
            "wave-X": {"type": "activate"}
        }


# ---------------------------------------------------------------------------
# Issue 5a changed the signal verb an agent sends. `deactivate` replaces
# `activate`, which is now refused. The renderer reads stored session logs, so
# it must handle both: the old verb still appears in logs recorded before the
# fix, and the new one appears in every log recorded after it.
# ---------------------------------------------------------------------------

class TestTheRendererReadsTheNewSignalVerb:

    def test_the_schematic_does_not_label_a_deactivation_as_act(self):
        """The signal diamond printed a hardcoded `act` beside any signal the
        agent touched. `activate` is now refused, so every signal an agent can
        touch is one it switched off, and `act` says the opposite."""
        svg = report._render_network_svg(
            gene_names=["G001"],
            signal_labels=["wave-X"],
            phenotype_labels=["energy-state"],
            baseline_phenos={"energy-state": 0.5},
            discovered_edges=[],
            current_phenos=None,
            current_interventions={"wave-X": "deactivate"},
        )
        assert "wave-X" in svg
        assert ">act<" not in svg

    def test_deactivating_a_signal_reads_as_removing_its_input(self):
        """Direction inference: switching a signal off removes its input, like
        BLOCK on a gene. A phenotype that drops means the signal was activating
        it. The verb matched no branch, so the edge was silently dropped."""
        base = {"energy-state": 0.5}
        tc = {
            "tool": "run_experiment",
            "input": {"interventions": {"wave-X": "deactivate"}},
            "result": {"phenotypes": {"energy-state": 0.1}, "budget_remaining": 1},
        }
        edges = report._build_discovered_network([{"tool_calls": [tc]}], base)
        assert edges == [{
            "from": "wave-X", "to": "energy-state",
            "direction": "activates", "delta": pytest.approx(-0.4),
        }]

    def test_the_old_verb_in_a_stored_log_still_reads(self):
        """Logs recorded before this fix contain `activate`. The renderer reads
        history and must keep reading it."""
        base = {"energy-state": 0.5}
        tc = {
            "tool": "run_experiment",
            "input": {"interventions": {"wave-X": "activate"}},
            "result": {"phenotypes": {"energy-state": 0.9}, "budget_remaining": 1},
        }
        edges = report._build_discovered_network([{"tool_calls": [tc]}], base)
        assert edges and edges[0]["direction"] == "activates"
