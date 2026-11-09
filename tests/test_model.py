"""Ereignisse, Bögen und Anschlussliste an der von Hand gerechneten Mini-Instanz `mini_net` (conftest.py)."""

import pytest

import zab_model as M
import zab_schedule as S
from zab_model import Arc, Settings


def test_event_ids_follow_the_travel_order(mini_net):
    ids = M.event_ids(mini_net)
    assert len(ids) == 12                       # Linie 0: 4 * 2 = 8 Ereignisse, Linie 1: 4 * 1 = 4
    assert ids[(0, "dep", "f", 0)] == 0 and ids[(0, "arr", "f", 1)] == 1 and ids[(0, "dep", "f", 1)] == 2
    assert ids[(0, "arr", "f", 2)] == 3 and ids[(0, "dep", "b", 2)] == 4 and ids[(0, "arr", "b", 1)] == 5
    assert ids[(0, "dep", "b", 1)] == 6 and ids[(0, "arr", "b", 0)] == 7 and ids[(1, "dep", "f", 0)] == 8 and ids[(1, "arr", "b", 0)] == 11


def test_event_labels_and_lines(mini_net):
    labels = M.event_labels(mini_net)
    assert labels[0] == "L1 Hin · Halt 0 ab" and labels[3] == "L1 Hin · Halt 2 an" and labels[11] == "L2 Rück · Halt 1 an"
    assert M.event_line(mini_net) == [0] * 8 + [1] * 4


def test_reserve_rounds_up():
    assert M.reserve(5, 50) == 3 and M.reserve(7, 50) == 4 and M.reserve(10, 50) == 5 and M.reserve(5, 0) == 0 and M.reserve(3, 1) == 1


def test_arcs_without_transfers_by_hand(mini_net):
    n, arcs = M.build_arcs(mini_net, Settings(k_transfers=0))
    assert n == 12
    assert arcs[:7] == [Arc(0, 1, 5, 5, "run"), Arc(1, 2, 1, 3, "dwell"), Arc(2, 3, 7, 7, "run"), Arc(3, 4, 4, None, "turn"),
                        Arc(4, 5, 7, 7, "run"), Arc(5, 6, 1, 3, "dwell"), Arc(6, 7, 5, 5, "run")]
    assert arcs[7:] == [Arc(8, 9, 4, 4, "run"), Arc(9, 10, 4, None, "turn"), Arc(10, 11, 4, 4, "run")]
    sch, _ = S.schedule(n, [a for a in arcs if a.u < 8])
    assert sch.earliest[:8] == (0, 5, 6, 13, 17, 24, 25, 30)       # 5, +1, +7, +4, +7, +1, +5


def test_reserve_and_turn_extra_and_dwell_change_the_windows(mini_net):
    n, arcs = M.build_arcs(mini_net, Settings(k_transfers=0, reserve_pct=50, turn_extra=6, dwell_hi=10))
    assert arcs[0] == Arc(0, 1, 5, 8, "run") and arcs[2] == Arc(2, 3, 7, 11, "run")        # 5 + 3, 7 + 4
    assert arcs[1] == Arc(1, 2, 1, 10, "dwell") and arcs[3] == Arc(3, 4, 4, 10, "turn")      # tmin 4, 4 + 6


def test_chosen_transfers_by_demand_and_direction(mini_net):
    both = M.chosen_transfers(mini_net, Settings(transfers="alle"))
    assert both == [(0, "f", 1, 1, "f", 0), (1, "b", 0, 0, "b", 1)]          # Nachfrage 6 vor 4
    assert M.chosen_transfers(mini_net, Settings(transfers="alle", k_transfers=1)) == both[:1]
    assert M.chosen_transfers(mini_net, Settings(transfers="gerichtet")) == both[:1]      # der zweite geht von Linie 2 nach Linie 1
    assert M.chosen_transfers(mini_net, Settings(transfers="alle", k_transfers=0)) == []


def test_transfer_arcs_carry_min_and_max_wait(mini_net):
    n, arcs = M.build_arcs(mini_net, Settings(transfers="alle", transfer_min=3, wait_max=10, dwell_hi=3))
    tr = [arcs[i] for i in M.transfer_arc_index(arcs)]
    assert tr == [Arc(1, 8, 3, 13, "transfer"), Arc(11, 6, 3, 13, "transfer")]
    n, arcs = M.build_arcs(mini_net, Settings(transfers="alle"))
    assert [arcs[i].hi for i in M.transfer_arc_index(arcs)] == [None, None]


def test_headway_arcs_fix_the_order_by_line_number(mini_net):
    n, arcs = M.build_arcs(mini_net, Settings(k_transfers=0, headway=4))
    hw = [a for a in arcs if a.kind == "headway"]
    assert sorted(hw) == [Arc(2, 8, 4, None, "headway"), Arc(4, 10, 4, None, "headway")]       # Linie 1 vor Linie 2 auf 1->2 und auf 2->1
    assert sorted(M.headway_pairs(mini_net)) == [(2, 8), (4, 10)]
    assert not [a for a in M.build_arcs(mini_net, Settings(k_transfers=0))[1] if a.kind == "headway"]


def test_the_mini_net_plan_is_possible_and_has_the_hand_computed_end(mini_net):
    n, arcs = M.build_arcs(mini_net, Settings(transfers="gerichtet", wait_max=10))
    sch, wit = S.schedule(n, arcs)
    assert wit is None
    # Linie 0 hat Ankunft 5 an Halt 1; Linie 1 fährt ab >= 5 + 3 = 8, Rückkehr 8 + 4 + 4 + 4 = 20; Linie 0 endet bei 30 -> Ende 30
    assert sch.earliest[8] == 8 and sch.earliest[11] == 20 and sch.end == 30




def test_hin_and_rueck_transfers_close_a_time_cycle_without_any_upper_bound(mini_net):
    """Anschluss L1 zurück (Ereignis 5) -> L2 hin (8) und L2 zurück (11) -> L1 hin (2): Kreis 2->3 (7) ->4 (4) ->5 (7) ->8 (3) ->9 ->10 ->11 (12) ->2 (3) = 36."""
    from zab_network import Instance
    inst = Instance(mini_net.lines, {(0, "b", 1, 1, "f", 0): 5.0, (1, "b", 0, 0, "f", 1): 5.0})
    n, arcs = M.build_arcs(inst, Settings(transfers="alle"))
    sch, wit = S.schedule(n, arcs)
    assert sch is None and sum(e[2] for e in wit) > 0
    # nur ein Anschluss (gerichtet: der von Linie 1 nach Linie 2) ist möglich, der Kreis braucht beide
    n, arcs = M.build_arcs(inst, Settings(transfers="gerichtet"))
    assert S.schedule(n, arcs)[0] is not None
