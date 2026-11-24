"""Agreement tests: the heatmap marker must read an intervention the same way
the strip above it does, and the same way the engine stored it.

Issue 17. `plot_session` resolved the intervention type twice, in two places,
with two different expressions:

    # the intervention strip
    itype = val.get("type", "?") if isinstance(val, dict) else str(val)
    # the heatmap marker, 24 lines later
    itype = val.get("type", "") if isinstance(val, dict) else ""

The second discards the bare-string form. `ExperimentSession` stores the
agent's own payload shape, so `{"G001": "BLOCK"}` is logged as
`{'G001': 'BLOCK'}` — see the stored-payload counts in CLAUDE.md, where 1,450
of 18,356 calls used that form. Such an intervention rendered as a white "?"
in the marker while the strip above showed it correctly.

The fix is one resolver used by both, so the two cannot disagree again.
"""
import pytest

from luca import inspect as luca_inspect


BARE = "BLOCK"
WRAPPED = {"type": "BLOCK"}


class TestInterventionTypeResolver:

    def test_the_wrapped_form_resolves_to_its_type(self):
        assert luca_inspect._iv_type(WRAPPED) == "BLOCK"

    def test_the_bare_string_form_resolves_to_its_type(self):
        # This is the issue 17 defect: it used to resolve to "".
        assert luca_inspect._iv_type(BARE) == "BLOCK"

    def test_both_payload_forms_resolve_identically(self):
        assert luca_inspect._iv_type(BARE) == luca_inspect._iv_type(WRAPPED)

    @pytest.mark.parametrize("itype", ["BLOCK", "BOOST", "DAMPEN"])
    def test_every_documented_type_resolves_in_both_forms(self, itype):
        assert luca_inspect._iv_type(itype) == itype
        assert luca_inspect._iv_type({"type": itype}) == itype

    def test_a_dict_without_a_type_resolves_to_empty(self):
        assert luca_inspect._iv_type({}) == ""


class TestHeatmapMarker:

    @pytest.mark.parametrize("itype,colour,symbol", [
        ("BLOCK", "#EF5350", "✕"),
        ("BOOST", "#66BB6A", "▲"),
        ("DAMPEN", "#FFA726", "▼"),
    ])
    def test_a_bare_string_intervention_gets_its_own_colour_and_symbol(
        self, itype, colour, symbol
    ):
        # Before the fix this returned the fallback ("#fff", "?") for every
        # bare-string intervention.
        assert luca_inspect._iv_marker(itype) == (colour, symbol)

    @pytest.mark.parametrize("itype,colour,symbol", [
        ("BLOCK", "#EF5350", "✕"),
        ("BOOST", "#66BB6A", "▲"),
        ("DAMPEN", "#FFA726", "▼"),
    ])
    def test_the_wrapped_form_gets_the_same_marker(self, itype, colour, symbol):
        assert luca_inspect._iv_marker({"type": itype}) == (colour, symbol)

    def test_both_payload_forms_give_the_same_marker(self):
        assert luca_inspect._iv_marker(BARE) == luca_inspect._iv_marker(WRAPPED)

    def test_an_unknown_type_falls_back_to_the_neutral_marker(self):
        assert luca_inspect._iv_marker("NOT_A_TYPE") == ("#fff", "?")
        assert luca_inspect._iv_marker({}) == ("#fff", "?")


class TestMarkerAgreesWithTheStoredLog:

    def test_the_form_the_engine_stores_renders_with_its_own_marker(self):
        # The engine logs the agent's payload shape unchanged. A bare-string
        # experiment must therefore not render as the unknown marker.
        from luca import generate_organism, ExperimentSession
        from luca.agent import dispatch_tool

        session = ExperimentSession(generate_organism(seed=0), budget=5, seed=0)
        gene = session.get_info()["gene_names"][0]
        dispatch_tool(session, "run_experiment", {gene: "BLOCK"})

        stored = session._experiment_log[-1]["interventions"]
        assert stored == {gene: "BLOCK"}, "precondition: the bare form is stored as-is"

        colour, symbol = luca_inspect._iv_marker(stored[gene])
        assert (colour, symbol) != ("#fff", "?")
        assert (colour, symbol) == ("#EF5350", "✕")
