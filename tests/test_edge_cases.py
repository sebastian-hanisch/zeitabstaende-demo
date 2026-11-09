"""Randfälle, an denen Kernroutinen erfahrungsgemäß brechen (DEMO-PLAYBOOK §12): ein Ereignis, genau zwei Ereignisse, Kreis der Länge genau 0, Fenster der Breite 0,
Gleichstände der Nachfrage, k größer als die Zahl der Anschlüsse, Grenzwerte der Regler."""

import pytest

import zab_bridge as B
import zab_graph as G
import zab_model as M
import zab_schedule as S
import zab_witness as W
from zab_model import Arc, Settings
from zab_network import Instance, Line


def test_a_single_event_without_arcs():
    sch, wit = S.schedule(1, [])
    assert wit is None and sch.earliest == (0,) and sch.latest == (0,) and sch.slack == (0,) and sch.end == 0
    assert G.is_feasible(1, []) and W.minimal_infeasible(1, []) == []


def test_exactly_two_events_with_a_fixed_window():
    sch, _ = S.schedule(2, [Arc(0, 1, 7, 7, "run")])
    assert sch.earliest == (0, 7) and sch.latest == (0, 7) and sch.end == 7


def test_two_events_in_both_directions_a_cycle_of_length_exactly_zero_is_possible():
    """a -> b mindestens 3 und höchstens 3: Kreis 3 + (-3) = 0 ist erlaubt (Grenze inklusive). Mindestens 3, höchstens 2: Länge +1, unmöglich."""
    assert S.schedule(2, [Arc(0, 1, 3, 3, "run")])[0] is not None
    sch, wit = S.schedule(2, [Arc(0, 1, 3, 2, "run")])
    assert sch is None and sum(e[2] for e in wit) == 1


def test_two_events_with_contradicting_windows_have_a_two_edge_witness():
    arcs = [Arc(0, 1, 5, None, "run"), Arc(0, 1, 0, 4, "run")]       # x1 >= x0 + 5 und x1 <= x0 + 4
    wit = W.witness_cycle(2, arcs)
    assert wit is not None and G.is_closed_walk(wit) and G.cycle_weight(wit) == 1 and len(wit) == 2


def test_negative_lower_bounds_are_allowed():
    """Ein Mindestabstand von -100 hindert nichts (Gerüst der Mini-Raute)."""
    assert S.schedule(2, [Arc(0, 1, -100, 5, "run")])[0] is not None


def test_k_larger_than_the_number_of_transfers_returns_all():
    inst = Instance([Line([0, 1], [5]), Line([1, 2], [4])], {(0, "f", 1, 1, "f", 0): 2.0})
    assert M.chosen_transfers(inst, Settings(transfers="alle", k_transfers=50)) == [(0, "f", 1, 1, "f", 0)]
    assert M.chosen_transfers(inst, Settings(transfers="alle", k_transfers=0)) == []


def test_ties_in_the_demand_follow_the_key_order():
    inst = Instance([Line([0, 1], [5]), Line([1, 2], [4]), Line([1, 3], [4])],
                    {(0, "f", 1, 2, "f", 0): 3.0, (0, "f", 1, 1, "f", 0): 3.0, (1, "b", 0, 2, "f", 0): 3.0})
    keys = M.chosen_transfers(inst, Settings(transfers="alle", k_transfers=2))
    assert keys == [(0, "f", 1, 1, "f", 0), (0, "f", 1, 2, "f", 0)]


def test_zero_wait_and_zero_transfer_min_make_a_window_of_width_zero():
    inst = Instance([Line([0, 1], [5]), Line([1, 2], [4])], {(0, "f", 1, 1, "f", 0): 2.0})
    n, arcs = M.build_arcs(inst, Settings(transfers="alle", transfer_min=0, wait_max=0))
    tr = [arcs[i] for i in M.transfer_arc_index(arcs)]
    assert tr == [Arc(1, 4, 0, 0, "transfer")]
    assert S.schedule(n, arcs)[0] is not None


def test_a_zero_extra_turn_leaves_a_window_of_width_zero():
    inst = Instance([Line([0, 1], [5])], {})
    n, arcs = M.build_arcs(inst, Settings(turn_extra=0))
    assert [a for a in arcs if a.kind == "turn"] == [Arc(1, 2, 4, 4, "turn")]


def test_periodic_with_a_window_of_at_least_t_minutes_never_binds():
    assert B.periodic_feasible(2, [Arc(0, 1, 5, 70, "run"), Arc(1, 0, 3, None, "run")], T=60) is True


def test_largest_net_with_all_transfers_is_decided_quickly_by_both_versions():
    from zab_network import make_instance
    inst = make_instance(10, 3000)[0]
    n, arcs = M.build_arcs(inst, Settings(transfers="alle", k_transfers=None, wait_max=None, headway=10))
    assert n == 200 and len(arcs) > 300
    assert G.is_feasible(n, arcs) == (S.earliest(n, arcs)[0] is not None)
