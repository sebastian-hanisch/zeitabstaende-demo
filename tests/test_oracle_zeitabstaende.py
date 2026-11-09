"""Orakel-Tests (ORACLE-PLAYBOOK §2, Kürzeste Wege / Scheduling): jede Kernroutine gegen einen anderen Rechenweg.

* Bellman-Ford (Machbarkeit, früheste und späteste Lage, Gesamtende) gegen die **Aufzählung** aller Belegungen kleiner Zufallssysteme.
* Machbarkeit und früheste Lagen auf echten Netzen gegen **networkx** (negative Kreise im negierten Graphen), Machbarkeit auch gegen **CP-SAT**.
* Früheste und späteste Lage gegen das **lineare Programm** (HiGHS, scipy).
* Der Zeuge ist ein geschlossener Kantenzug positiver Länge, **unabhängig aus den Bögen nachgerechnet**.
* Periodische Machbarkeit gegen die **Aufzählung** aller Phasen kleiner Systeme; Satz „einmalig möglich => periodisch möglich“ an echten Netzen.
* Zeitkreis-Zählung (schon ohne jeden Höchstabstand unmöglich) und gefundene unmögliche Menge gegen die **Aufzählung aller Teilmengen** kleiner Systeme.
* Größter haltbarer Anteil und freie Zugfolge gegen die **Aufzählung** aller Teilmengen bzw. aller Reihenfolgen.
Zufall nur über SplitMix64. Die großen Läufe (Hunderte bis Tausende Systeme) stehen in der README unter Verifikation, hier nur die schnelle Fassung.
"""
import itertools

import numpy as np
import pytest

import zab_bridge as B
import zab_graph as G
import zab_model as M
import zab_schedule as S
import zab_witness as W
from zab_model import Arc, Settings
from zab_network import make_instance
from zab_rng import SplitMix64

nx = pytest.importorskip("networkx")
cp_model = pytest.importorskip("ortools.sat.python.cp_model")
linprog = pytest.importorskip("scipy.optimize").linprog


def _random_system(seed, n_ev, lo_max=4, extra_hi=5):
    rng = SplitMix64(seed)
    arcs = []
    for _ in range(3 + rng.below(6)):
        u, v = rng.below(n_ev), rng.below(n_ev)
        if u == v:
            continue
        lo = rng.below(lo_max + 1)
        hi = None if rng.below(3) == 0 else lo + rng.below(extra_hi + 1)
        arcs.append(Arc(u, v, lo, hi, "run"))
    return arcs


def _nx_graph(n, arcs):
    """Negierter Bedingungsgraph mit Quelle n: längste Wege werden kürzeste Wege, ein positiver Kreis wird ein negativer."""
    g = nx.DiGraph()
    for e in range(n):
        g.add_edge(n, e, weight=0)
    for a in arcs:
        for (u, v, w) in ([(a.u, a.v, a.lo)] + ([(a.v, a.u, -a.hi)] if a.hi is not None else [])):
            if g.has_edge(u, v):
                g[u][v]["weight"] = min(g[u][v]["weight"], -w)
            else:
                g.add_edge(u, v, weight=-w)
    return g


def test_bellman_ford_equals_enumeration_on_random_small_systems():
    n_ev, H = 4, 8
    grid = np.array(list(itertools.product(range(H + 1), repeat=n_ev)), dtype=np.int32)
    compared = feasible_seen = infeasible_seen = 0
    for t in range(300):
        arcs = _random_system(5000 + t, n_ev)
        ok = np.ones(len(grid), dtype=bool)
        for a in arcs:
            d = grid[:, a.v] - grid[:, a.u]
            ok &= d >= a.lo
            if a.hi is not None:
                ok &= d <= a.hi
        sch, wit = S.schedule(n_ev, arcs)
        if sch is not None and max(sch.earliest) > H:
            continue                                     # die Wertebox 0..H schneidet das System ab: nicht vergleichbar
        assert (sch is not None) == bool(ok.any()), t
        compared += 1
        if sch is None:
            infeasible_seen += 1
            continue
        feasible_seen += 1
        sub = grid[ok]
        end = int(sub.max(axis=1).min())                 # kleinstmögliches Gesamtende
        assert sch.end == end, t
        assert list(sch.earliest) == list(sub.min(axis=0)), t
        assert list(sch.latest) == list(sub[sub.max(axis=1) <= end].max(axis=0)), t
    assert compared >= 250 and feasible_seen >= 80 and infeasible_seen >= 40, (compared, feasible_seen, infeasible_seen)


NETS = [make_instance(nl, 3000 + 100 * i)[0] for i, nl in enumerate((3, 3, 5, 6, 6, 6, 8, 10))]
CONFIGS = [Settings(transfers="alle", k_transfers=k, wait_max=w) for k in (2, 4, 8) for w in (None, 15, 5)] + \
          [Settings(transfers="gerichtet", k_transfers=k, wait_max=w) for k in (3, 6) for w in (30, 10)] + \
          [Settings(transfers="alle", k_transfers=4, wait_max=10, headway=4), Settings(transfers="gerichtet", k_transfers=4, wait_max=30, turn_extra=10)]


def _cpsat_feasible(n, arcs):
    m = cp_model.CpModel()
    x = [m.NewIntVar(0, 5000, f"x{e}") for e in range(n)]
    for a in arcs:
        m.Add(x[a.v] - x[a.u] >= a.lo)
        if a.hi is not None:
            m.Add(x[a.v] - x[a.u] <= a.hi)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    st = s.Solve(m)
    assert st in (cp_model.OPTIMAL, cp_model.INFEASIBLE)
    return st == cp_model.OPTIMAL


def test_feasibility_and_earliest_equal_networkx_and_cpsat_on_real_nets():
    n_ok = n_bad = 0
    for inst in NETS[:6]:
        for s in CONFIGS:
            n, arcs = M.build_arcs(inst, s)
            early, wit = S.earliest(n, arcs)
            feasible = early is not None
            g = _nx_graph(n, arcs)
            assert nx.negative_edge_cycle(g, weight="weight") == (not feasible)
            assert G.is_feasible(n, arcs) == feasible == _cpsat_feasible(n, arcs)
            if feasible:
                dist = nx.single_source_bellman_ford_path_length(g, n, weight="weight")
                assert [-dist[e] for e in range(n)] == early
                n_ok += 1
            else:
                n_bad += 1
    assert n_ok >= 15 and n_bad >= 25, (n_ok, n_bad)           # beide Seiten kommen vor


def test_earliest_and_latest_equal_the_linear_program():
    checked = 0
    for inst in NETS[:3]:                                      # 3-Linien-Netze: 60 Ereignisse
        n, arcs = M.build_arcs(inst, Settings(transfers="gerichtet", k_transfers=4, wait_max=30))
        sch, wit = S.schedule(n, arcs)
        if sch is None:
            continue
        rows, rhs = [], []
        for a in arcs:
            row = np.zeros(n)
            row[a.u], row[a.v] = 1, -1
            rows.append(row.copy()); rhs.append(-a.lo)                       # x_u - x_v <= -lo
            if a.hi is not None:
                rows.append(-row); rhs.append(a.hi)                          # x_v - x_u <= hi
        A, b = np.array(rows), np.array(rhs)
        for e in range(0, n, 3):
            c = np.zeros(n); c[e] = 1
            lo = linprog(c, A_ub=A, b_ub=b, bounds=[(0, sch.end)] * n, method="highs")
            hi = linprog(-c, A_ub=A, b_ub=b, bounds=[(0, sch.end)] * n, method="highs")
            assert lo.status == 0 and hi.status == 0
            assert lo.fun == pytest.approx(sch.earliest[e], abs=1e-6) and -hi.fun == pytest.approx(sch.latest[e], abs=1e-6), e
            checked += 1
    assert checked >= 30


def test_witnesses_are_closed_walks_of_positive_length_recomputed_from_the_arcs():
    checked = 0
    for inst in NETS:
        for s in CONFIGS:
            n, arcs = M.build_arcs(inst, s)
            cyc = W.witness_cycle(n, arcs)
            if cyc is None:
                continue
            assert G.is_closed_walk(cyc)
            total = 0
            for (u, v, w, tag) in cyc:
                a = arcs[tag[0]]
                if tag[1] == "lo":
                    assert (u, v) == (a.u, a.v) and w == a.lo
                    total += a.lo
                else:
                    assert (u, v) == (a.v, a.u) and a.hi is not None and w == -a.hi
                    total -= a.hi
            assert total > 0 and total == G.cycle_weight(cyc) == G.cycle_excess(cyc)["excess"]
            checked += 1
    assert checked >= 25


def test_minimal_infeasible_set_is_infeasible_and_minimal_on_real_nets():
    seen = 0
    for inst in NETS[:4]:
        for s in CONFIGS[:6]:
            n, arcs = M.build_arcs(inst, s)
            keep = W.minimal_infeasible(n, arcs)
            if not keep:
                continue
            sub = [arcs[i] for i in keep]
            assert not _cpsat_feasible(n, sub)
            assert all(_cpsat_feasible(n, sub[:i] + sub[i + 1:]) for i in range(len(sub)))
            seen += 1
    assert seen >= 5


def test_time_cycle_count_equals_enumeration_of_all_subsets_on_small_systems():
    """Zeitkreis-Plan = es gibt eine Teilmenge der Bögen, die auch ohne jeden Höchstabstand unmöglich ist; sonst „nur durch Höchstabstände unmöglich“. Orakel: alle Teilmengen,
    jede durch Aufzählung aller Belegungen 0..12 der 4 Ereignisse entschieden (ein möglicher Plan hat eine früheste Lage <= 3 Kanten * 4 = 12). Geprüft werden die Einordnung
    (unabhängig von der Bogenreihenfolge) und die gefundene Menge: unmöglich und jede echte Teilmenge möglich, bei einem Zeitkreis-Plan ohne Höchstabstand im Kreis."""
    n_ev, H = 4, 12
    grid = np.array(list(itertools.product(range(H + 1), repeat=n_ev)), dtype=np.int8)

    def arc_mask(a, with_hi):
        d = grid[:, a.v].astype(np.int16) - grid[:, a.u]
        ok = d >= a.lo
        return ok & (d <= a.hi) if (with_hi and a.hi is not None) else ok

    def subset_table(masks):
        """feasible[s] für jede Teilmenge s (Bitmaske über die Bögen): Aufzählung aller Belegungen, die alle Bögen von s erfüllen."""
        table = [np.ones(len(grid), dtype=bool)]
        for s in range(1, 1 << len(masks)):
            low = (s & -s).bit_length() - 1
            table.append(table[s & (s - 1)] & masks[low])
        return [bool(t.any()) for t in table]

    seen = {"possible": 0, "time_cycle": 0, "only_upper": 0}
    for t in range(300):
        arcs = _random_system(9000 + t, n_ev)
        m = len(arcs)
        full = subset_table([arc_mask(a, True) for a in arcs])
        lo_only = subset_table([arc_mask(a, False) for a in arcs])
        full_ok = full[(1 << m) - 1]
        for order in (arcs, arcs[::-1]):
            info = W.explain_infeasible(n_ev, order)
            assert (info is None) == full_ok, t
            if info is None:
                continue
            assert W.has_time_cycle(n_ev, order) == info["time_cycle"]
            assert info["time_cycle"] == (not all(lo_only[s] for s in range(1 << m))), t        # Teilmenge ohne Höchstabstände unmöglich
            table = lo_only if info["time_cycle"] else full
            masks_of_keep = sum(1 << (j if order is arcs else m - 1 - j) for j in info["keep"])   # Indizes der Umkehrung zurückrechnen
            assert not table[masks_of_keep], t                                                  # die Menge ist unmöglich ...
            sub = masks_of_keep
            while sub:                                                                          # ... und jede echte Teilmenge davon möglich
                sub = (sub - 1) & masks_of_keep
                if sub != masks_of_keep:
                    assert table[sub], (t, sub)
            assert (info["hi"] == 0) if info["time_cycle"] else (info["hi"] >= 1), t
        if full_ok:
            seen["possible"] += 1
        else:
            seen["time_cycle" if info["time_cycle"] else "only_upper"] += 1
    assert seen["time_cycle"] >= 50 and seen["only_upper"] >= 15 and seen["possible"] >= 50, seen


def _periodic_by_enumeration(n, arcs, T):
    for phases in itertools.product(range(T), repeat=n):
        if phases[0] != 0:
            continue
        if all(any((phases[a.v] - phases[a.u] - x) % T == 0 for x in range(a.lo, (a.lo + T - 1 if a.hi is None else a.hi) + 1)) for a in arcs):
            return True
    return False


def test_periodic_feasibility_equals_enumeration_of_all_phases():
    T, n_ev = 6, 4
    seen = {True: 0, False: 0}
    for t in range(120):
        arcs = _random_system(9000 + t, n_ev, lo_max=5, extra_hi=3)
        expected = _periodic_by_enumeration(n_ev, arcs, T)
        got = B.periodic_feasible(n_ev, arcs, T=T, workers=1)
        assert got is expected, t
        seen[expected] += 1
        if G.is_feasible(n_ev, arcs):
            assert expected                                   # einmalig möglich => periodisch möglich
    assert seen[True] >= 30 and seen[False] >= 5, seen


def test_once_feasible_implies_periodic_feasible_on_real_nets():
    both = rescued = 0
    for inst in NETS[:6]:
        for s in CONFIGS:
            n, arcs = M.build_arcs(inst, s)
            once = G.is_feasible(n, arcs)
            per = B.periodic_feasible(n, arcs, T=60)
            assert per is not None
            assert not (once and not per)
            both += once and per
            rescued += (not once) and per
    assert both >= 10 and rescued >= 10, (both, rescued)


def test_max_kept_weight_equals_enumeration_of_all_subsets():
    checked = 0
    for inst in NETS[:6]:
        s = Settings(transfers="alle", k_transfers=7, wait_max=10)
        n, arcs = M.build_arcs(inst, s)
        keys = M.chosen_transfers(inst, s)
        fixed = [a for a in arcs if a.kind != "transfer"]
        trans = [a for a in arcs if a.kind == "transfer"]
        w = [inst.transfers[k] for k in keys]
        best = 0.0
        for mask in range(1 << len(trans)):
            sub = fixed + [t for i, t in enumerate(trans) if mask >> i & 1]
            if not nx.negative_edge_cycle(_nx_graph(n, sub), weight="weight"):
                best = max(best, sum(wi for i, wi in enumerate(w) if mask >> i & 1))
        kept, status = B.max_kept_weight(inst, s, workers=1)
        assert status == "OPTIMAL" and kept == pytest.approx(best / sum(w))
        greedy = B.greedy_kept_weight(inst, s)
        assert greedy is not None and greedy <= kept + 1e-9        # der Greedy kann nie mehr halten als das Optimum
        checked += 1
    assert checked == 6


SMALL_ORDER_NETS = [make_instance(3, seed)[0] for seed in (28, 42, 91, 112, 5, 14)]       # höchstens 6 Abschnittspaare


def test_free_order_equals_enumeration_of_all_orders():
    checked = free_only = infeasible_both = 0
    for inst in SMALL_ORDER_NETS:
        pairs = M.headway_pairs(inst)
        assert len(pairs) <= 9
        for s in (Settings(transfers="alle", k_transfers=4, headway=4), Settings(transfers="alle", k_transfers=3, wait_max=10, headway=10)):
            n, arcs = M.build_arcs(inst, Settings(**{**s.__dict__, "headway": 0}))
            expected = False
            for mask in range(1 << len(pairs)):        # alle 2^Paare Reihenfolgen, je eine Prüfung mit networkx
                extra = [Arc(a, b, s.headway, None, "headway") if mask >> i & 1 == 0 else Arc(b, a, s.headway, None, "headway") for i, (a, b) in enumerate(pairs)]
                if not nx.negative_edge_cycle(_nx_graph(n, arcs + extra), weight="weight"):
                    expected = True
                    break
            got, npairs = B.free_order_feasible(inst, s, workers=1)
            assert npairs == len(pairs) and got is expected
            fixed_ok = G.is_feasible(*M.build_arcs(inst, s))
            assert not (fixed_ok and not got)                    # feste Reihenfolge möglich => freie möglich
            free_only += got and not fixed_ok
            infeasible_both += not got
            checked += 1
    assert checked == 12 and free_only >= 3 and infeasible_both >= 1, (checked, free_only, infeasible_both)
