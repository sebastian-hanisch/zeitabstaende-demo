"""Zeugen: Kreis positiver Länge, kleinste unmögliche Bogenmenge (Löschfilter), Klassifikation, Anzeigezeilen."""

import zab_graph as G
import zab_model as M
import zab_witness as W
from zab_model import Arc


def test_witness_is_none_for_a_feasible_plan(chain):
    n, arcs = chain
    assert W.witness_cycle(n, arcs) is None
    assert W.minimal_infeasible(n, arcs) == []


def test_minimal_infeasible_set_of_the_time_cycle_is_all_four_arcs(time_cycle):
    n, arcs = time_cycle
    assert W.minimal_infeasible(n, arcs) == [0, 1, 2, 3]
    info = W.classify_cycle(n, arcs)
    assert info["len"] == 4 and info["hi"] == 0 and info["transfer"] == 2 and info["excess"] == 26
    assert info["kinds"] == {"run": 2, "transfer": 2}
    assert W.has_time_cycle(n, arcs)


def test_minimal_infeasible_drops_unrelated_arcs(time_cycle):
    n, arcs = time_cycle
    extra = arcs + [Arc(0, 2, -1000, 500, "dwell"), Arc(1, 3, -1000, None, "dwell")]      # hindern nicht (Mindestabstand -1000) und gehören nicht zum Kreis
    keep = W.minimal_infeasible(n, extra)
    assert keep == [0, 1, 2, 3] and not G.is_feasible(n, [extra[i] for i in keep])
    assert all(G.is_feasible(n, [extra[j] for j in keep if j != i]) for i in keep)       # jeder Bogen darin ist nötig


def test_a_cycle_with_an_upper_bound_is_not_a_time_cycle(chain):
    n, arcs = chain
    arcs = arcs + [Arc(0, 2, 0, 4, "turn")]
    keep = W.minimal_infeasible(n, arcs)
    assert keep == [0, 1, 2]
    info = W.classify_cycle(n, [arcs[i] for i in keep])
    assert info["hi"] == 1 and info["excess"] == 1 and info["transfer"] == 0
    assert not W.has_time_cycle(n, arcs)          # ohne Höchstabstände ist die Kette möglich (früheste Lagen 0, 2, 5)


def _chain_plus_time_cycle(time_cycle_first):
    """Handrechnung: Kette 0-1-2 mit Höchstabstand (Kreis 2 + 3 - 4 = +1, nur mit Höchstabstand unmöglich) und der Zeitkreis aus conftest (3) auf den Ereignissen 3 bis 6
    (10 + 3 + 10 + 3 = +26). Der Plan hat einen Zeitkreis, gleich in welcher Reihenfolge die Bögen stehen."""
    chain = [Arc(0, 1, 2, 4, "run"), Arc(1, 2, 3, 5, "run"), Arc(0, 2, 0, 4, "turn")]
    tc = [Arc(3, 4, 10, None, "run"), Arc(5, 6, 10, None, "run"), Arc(4, 5, 3, None, "transfer"), Arc(6, 3, 3, None, "transfer")]
    return 7, (tc + chain if time_cycle_first else chain + tc)


def test_deletion_filter_set_depends_on_the_arc_order_but_the_time_cycle_test_does_not():
    n, arcs = _chain_plus_time_cycle(False)
    keep = W.minimal_infeasible(n, arcs)
    assert keep == [3, 4, 5, 6] and W.classify_cycle(n, [arcs[i] for i in keep])["hi"] == 0
    n, arcs = _chain_plus_time_cycle(True)
    keep = W.minimal_infeasible(n, arcs)
    assert keep == [4, 5, 6] and W.classify_cycle(n, [arcs[i] for i in keep])["hi"] == 1      # die Menge mit Höchstabstand, obwohl der Plan einen Zeitkreis hat
    for first in (False, True):
        n, arcs = _chain_plus_time_cycle(first)
        assert W.has_time_cycle(n, arcs)
        info = W.explain_infeasible(n, arcs)
        assert info["time_cycle"] and info["hi"] == 0 and info["iis"] == 4 and info["excess"] == 26
        assert sorted(arcs[i].kind for i in info["keep"]) == ["run", "run", "transfer", "transfer"]


def test_explain_infeasible_separates_time_cycle_from_only_upper_bounds(chain, time_cycle):
    n, arcs = chain
    assert W.explain_infeasible(n, arcs) is None and not W.has_time_cycle(n, arcs)           # möglicher Plan: weder noch
    arcs = arcs + [Arc(0, 2, 0, 4, "turn")]
    info = W.explain_infeasible(n, arcs)
    assert not info["time_cycle"] and info["keep"] == [0, 1, 2] and info["hi"] == 1 and info["excess"] == 1
    n, arcs = time_cycle
    info = W.explain_infeasible(n, arcs)
    assert info["time_cycle"] and info["keep"] == [0, 1, 2, 3] and info["hi"] == 0 and info["transfer"] == 2


def test_witness_rows_name_events_kinds_and_contribution(time_cycle):
    n, arcs = time_cycle
    cyc = W.witness_cycle(n, arcs)
    rows = W.witness_rows(arcs, cyc, ["a", "b", "c", "d"])
    assert sum(r["beitrag"] for r in rows) == 26 and {r["seite"] for r in rows} == {"Mindestabstand"}
    assert sorted(r["art"] for r in rows) == ["run", "run", "transfer", "transfer"]
    assert {(r["von"], r["nach"]) for r in rows} == {("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")}


def test_witness_rows_of_an_upper_bound_go_backwards(chain):
    n, arcs = chain
    arcs = arcs + [Arc(0, 2, 0, 4, "turn")]
    rows = W.witness_rows(arcs, W.witness_cycle(n, arcs), ["a", "b", "c"])
    hi = [r for r in rows if r["seite"] == "Höchstabstand"]
    assert hi == [{"art": "turn", "seite": "Höchstabstand", "von": "c", "nach": "a", "beitrag": -4}]


def test_every_arc_kind_has_a_german_label():
    import zab_constants as C
    assert set(C.KIND_LABELS) == {M.KIND_RUN, M.KIND_DWELL, M.KIND_TURN, M.KIND_TRANSFER, M.KIND_HEADWAY}
    assert len(set(C.KIND_LABELS.values())) == 5 and all(C.KIND_LABELS.values())
