"""Brücke: periodischer Plan (modulo T), freie Zugfolge, größter haltbarer Anteil; an Mini-Systemen von Hand."""

import pytest

import zab_bridge as B
import zab_model as M
from zab_model import Arc, Settings


def test_time_cycle_is_impossible_once_but_possible_periodically(time_cycle):
    n, arcs = time_cycle
    ok, phases, xs = B.periodic_solution(n, arcs, T=60)
    assert ok is True and len(phases) == n
    cyc = __import__("zab_witness").witness_cycle(n, arcs)
    total = B.cycle_sum_of_x(cyc, xs)
    assert total % 60 == 0 and total >= 26 and total > 0       # entlang des Kreises summieren sich die Abstände zu einem Vielfachen des Taktes
    for a, x in zip(arcs, xs):
        assert x >= a.lo and (a.hi is None or x <= a.hi)


def test_periodic_x_stays_inside_the_window(chain):
    n, arcs = chain
    ok, phases, xs = B.periodic_solution(n, arcs, T=60)
    assert ok and 2 <= xs[0] <= 4 and 3 <= xs[1] <= 5
    for a, x in zip(arcs, xs):
        assert (phases[a.v] - phases[a.u] - x) % 60 == 0


def test_periodic_infeasible_when_the_cycle_is_shorter_than_the_period_allows():
    """a -> b in [5, 5], b -> a in [30, 30]: Summe 35, nie ein Vielfaches von 60: periodisch unmöglich, einmalig sowieso."""
    arcs = [Arc(0, 1, 5, 5, "run"), Arc(1, 0, 30, 30, "run")]
    assert B.periodic_feasible(2, arcs, T=60) is False
    arcs = [Arc(0, 1, 5, 5, "run"), Arc(1, 0, 55, 55, "run")]
    assert B.periodic_feasible(2, arcs, T=60) is True       # 5 + 55 = 60 = 1 Takt


def test_free_order_is_also_infeasible_when_both_orders_fail(mini_net):
    """Auf der Mini-Instanz gilt x8 - x1 = 3 (Anschluss, Höchstwartezeit 0) und x2 - x1 in [1, 3] (Halt). Fest (Ereignis 2 vor 8, 4 min): x8 >= x2 + 4 >= x1 + 5,
    unmöglich. Frei, andere Reihenfolge (8 vor 2): x2 >= x8 + 4 = x1 + 7 > x1 + 3, ebenfalls unmöglich: frei hilft hier nicht."""
    s = Settings(transfers="gerichtet", wait_max=0, headway=4)
    n, arcs = M.build_arcs(mini_net, s)
    import zab_graph as G
    assert not G.is_feasible(n, arcs)
    ok, pairs = B.free_order_feasible(mini_net, s)
    assert pairs == 2 and ok is False


def test_free_order_is_feasible_where_the_fixed_order_is_not():
    """Zwei gleiche Linien 0-1 (Ereignisse 0..3 und 4..7). Anschluss: Linie 2 zurück an Halt 0 (7) -> Linie 1 ab Halt 0 (0), genau 3 min (Höchstwartezeit 0).
    Linie 2 ist frühestens 4 + 10 + 4 + 10 = 24 min nach ihrer Abfahrt (4) wieder da. Feste Reihenfolge (Linie 1 zuerst, 4 min Zugfolge): x4 >= x0 + 4 und
    x0 = x7 + 3 >= x4 + 27 >= x0 + 31, ein Kreis 4 + 10 + 4 + 10 + 3 = +31. Frei darf Linie 2 zuerst fahren (x0 >= x4 + 4): möglich."""
    from zab_network import Instance, Line
    inst = Instance([Line([0, 1], [10]), Line([0, 1], [10])], {(1, "b", 0, 0, "f", 0): 5.0})
    s = Settings(transfers="alle", wait_max=0, headway=4, transfer_min=3)
    n, arcs = M.build_arcs(inst, s)
    import zab_graph as G
    import zab_witness as W
    assert not G.is_feasible(n, arcs)
    assert sum(e[2] for e in W.witness_cycle(n, arcs)) > 0
    ok, pairs = B.free_order_feasible(inst, s)
    assert ok is True and pairs == 2


def test_max_kept_weight_is_one_when_the_plan_is_feasible(mini_net):
    kept, status = B.max_kept_weight(mini_net, Settings(transfers="gerichtet"))
    assert kept == 1.0 and status == "OPTIMAL"
    assert B.greedy_kept_weight(mini_net, Settings(transfers="gerichtet")) == 1.0


def test_max_kept_weight_drops_the_cheaper_transfer_of_a_time_cycle(mini_net):
    from zab_network import Instance
    inst = Instance(mini_net.lines, {(0, "b", 1, 1, "f", 0): 6.0, (1, "b", 0, 0, "f", 1): 4.0})
    s = Settings(transfers="alle")
    kept, status = B.max_kept_weight(inst, s)
    assert status == "OPTIMAL" and kept == pytest.approx(0.6)       # der Anschluss mit Nachfrage 4 fällt weg
    assert B.greedy_kept_weight(inst, s) == pytest.approx(0.6)
