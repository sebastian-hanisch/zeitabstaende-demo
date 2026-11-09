"""Bedingungsgraph, Bellman-Ford mit Zeuge und die numpy-Fassung: an den von Hand gerechneten Mini-Systemen (conftest.py)."""

import pytest

import zab_graph as G
from zab_model import Arc


def test_constraint_edges_of_one_window():
    edges = G.constraint_edges([Arc(0, 1, 2, 4, "run")])
    assert edges == [(0, 1, 2, (0, "lo")), (1, 0, -4, (0, "hi"))]


def test_no_upper_bound_gives_only_the_lower_edge():
    assert G.constraint_edges([Arc(0, 1, 2, None, "run")]) == [(0, 1, 2, (0, "lo"))]


def test_chain_earliest_by_hand(chain):
    n, arcs = chain
    dist, _pred, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    assert cyc is None
    assert dist[:n] == [0, 2, 5]


def test_chain_with_loose_upper_bound_is_unchanged(chain):
    n, arcs = chain
    arcs = arcs + [Arc(0, 2, 0, 6, "turn")]
    dist, _p, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    assert cyc is None and dist[:n] == [0, 2, 5]


def test_chain_with_tight_upper_bound_has_a_positive_cycle_of_length_one(chain):
    n, arcs = chain
    arcs = arcs + [Arc(0, 2, 0, 4, "turn")]    # c - a <= 4, aber b - a >= 2 und c - b >= 3: 2 + 3 - 4 = +1
    _d, _p, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    assert cyc is not None
    assert G.is_closed_walk(cyc) and G.cycle_weight(cyc) == 1
    assert {e[0] for e in cyc} == {0, 1, 2}


def test_time_cycle_has_length_26_and_no_upper_bound(time_cycle):
    n, arcs = time_cycle
    _d, _p, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    assert cyc is not None and G.is_closed_walk(cyc)
    ex = G.cycle_excess(cyc)
    assert ex == {"min_sum": 26, "max_sum": 0, "excess": 26, "hi_count": 0, "length": 4}


def test_cycle_excess_of_a_cycle_with_one_upper_bound(chain):
    n, arcs = chain
    arcs = arcs + [Arc(0, 2, 0, 4, "turn")]
    _d, _p, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    ex = G.cycle_excess(cyc)
    assert ex["min_sum"] == 5 and ex["max_sum"] == 4 and ex["excess"] == 1 == G.cycle_weight(cyc) and ex["hi_count"] == 1


def test_unreachable_node_stays_none():
    edges = [(0, 1, 3, (0, "lo"))]
    dist, _p, cyc = G.longest_paths(edges, 0, 3)
    assert cyc is None and dist == [0, 3, None]


@pytest.mark.parametrize("name", ["chain", "diamond", "diamond_hi", "time_cycle"])
def test_fast_version_equals_python_version(name, request):
    n, arcs = request.getfixturevalue(name)
    dist, _p, cyc = G.longest_paths(G.with_source(G.constraint_edges(arcs), n), n, n + 1)
    fast, ok = G.FastBF(n, arcs).run()
    assert ok == (cyc is None) == G.is_feasible(n, arcs)
    if cyc is None:
        assert list(fast) == dist[:n]


def test_fast_version_with_no_arcs():
    fast, ok = G.FastBF(3, []).run()
    assert ok and list(fast) == [0, 0, 0]
