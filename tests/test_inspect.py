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
`{'G001': 'BLOCK'}`, demonstrated by
`test_the_form_the_engine_stores_renders_with_its_own_marker` below. Such an
intervention rendered as a white "?" in the marker while the strip above
showed it correctly.

The fix is one resolver used by both, so the two cannot disagree again.
"""
import pytest

from luca import inspect as luca_inspect


BARE = "BLOCK"
WRAPPED = {"type": "BLOCK"}


class TestInterventionTypeResolver:

    def test_the_wrapped_form_resolves_to_its_type(self):
        assert luca_inspect.canonical_type(WRAPPED) == "BLOCK"

    def test_the_bare_string_form_resolves_to_its_type(self):
        # This is the issue 17 defect: it used to resolve to "".
        assert luca_inspect.canonical_type(BARE) == "BLOCK"

    def test_both_payload_forms_resolve_identically(self):
        assert luca_inspect.canonical_type(BARE) == luca_inspect.canonical_type(WRAPPED)

    @pytest.mark.parametrize("itype", ["BLOCK", "BOOST", "DAMPEN"])
    def test_every_documented_type_resolves_in_both_forms(self, itype):
        assert luca_inspect.canonical_type(itype) == itype
        assert luca_inspect.canonical_type({"type": itype}) == itype

    def test_a_dict_without_a_type_resolves_to_empty(self):
        assert luca_inspect.canonical_type({}) == ""


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


class TestTheMarkerUsesTheEnginesOwnResolver:
    """Found by the code review of this change.

    The first fix added a private `_iv_type` to this module. That was a fourth
    copy of a resolution `luca/payloads.canonical_type` already owned, so it
    re-created the very duplication issue 17 is about — and it did not
    upper-case, so the defect survived for a lowercase payload.
    """

    def test_a_lowercase_type_the_engine_accepts_renders_with_its_marker(self):
        # The engine accepts "block" and runs it as BLOCK, then logs the
        # agent's value verbatim. The marker must agree with the engine.
        assert luca_inspect._iv_marker("block") == ("#EF5350", "✕")
        assert luca_inspect._iv_marker({"type": "block"}) == ("#EF5350", "✕")

    def test_the_stored_lowercase_form_is_not_the_unknown_marker(self):
        from luca import generate_organism, ExperimentSession
        from luca.agent import dispatch_tool

        session = ExperimentSession(generate_organism(seed=0), budget=5, seed=0)
        gene = session.get_info()["gene_names"][0]
        result = dispatch_tool(session, "run_experiment", {gene: "block"})
        assert "error" not in result, "precondition: the engine accepts lowercase"

        stored = session._experiment_log[-1]["interventions"]
        assert luca_inspect._iv_marker(stored[gene]) == ("#EF5350", "✕")

    def test_a_signal_verb_keeps_its_case_like_the_engine(self):
        # canonical_type upper-cases a GENE type only. A signal verb is not a
        # gene type and keeps the case the agent sent.
        assert luca_inspect.canonical_type("deactivate") == "deactivate"
