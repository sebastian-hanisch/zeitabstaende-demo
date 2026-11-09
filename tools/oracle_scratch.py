"""Großer Orakel-Lauf (nicht Teil der Testsuite, ORACLE-PLAYBOOK §2: mindestens 200 Zufallsinstanzen im Scratch-Lauf, im Repo nur die kleine Fassung).

Aufruf (aus dem Repo-Ordner): python tools/oracle_scratch.py [Zahl der Zufallssysteme, Standard 3000] [Zahl der echten Netze, Standard 40]
Vergleicht den Kern mit unabhängigen Rechenwegen und zählt Abweichungen:
  1. Zufallssysteme (4 Ereignisse, Werte 0 bis 8, Zufall über SplitMix64): Machbarkeit, früheste und späteste Lage, Gesamtende gegen die Aufzählung aller Belegungen.
  2. Echte Netze (6 Linien, 15 Einstellungen je Netz): Machbarkeit gegen networkx (negativer Kreis im negierten Graphen) und CP-SAT, frühe Lagen gegen networkx;
     jeder Zeuge ein geschlossener Kantenzug positiver Länge.
Die Ausgabe nennt Vergleiche und Abweichungen (erwartet: 0).
"""
import itertools
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from ortools.sat.python import cp_model

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zab_graph as G  # noqa: E402
import zab_model as M  # noqa: E402
import zab_schedule as S  # noqa: E402
import zab_witness as W  # noqa: E402
from zab_model import Arc, Settings  # noqa: E402
from zab_network import make_instance  # noqa: E402
from zab_rng import SplitMix64  # noqa: E402


def random_system(seed, n_ev):
    rng = SplitMix64(seed)
    arcs = []
    for _ in range(3 + rng.below(6)):
        u, v = rng.below(n_ev), rng.below(n_ev)
        if u != v:
            lo = rng.below(5)
            arcs.append(Arc(u, v, lo, None if rng.below(3) == 0 else lo + rng.below(6), "run"))
    return arcs


def part1(n_systems, n_ev=4, H=8):
    grid = np.array(list(itertools.product(range(H + 1), repeat=n_ev)), dtype=np.int32)
    compared = bad = feas = 0
    for t in range(n_systems):
        arcs = random_system(20000 + t, n_ev)
        ok = np.ones(len(grid), dtype=bool)
        for a in arcs:
            d = grid[:, a.v] - grid[:, a.u]
            ok &= d >= a.lo
            if a.hi is not None:
                ok &= d <= a.hi
        sch, _w = S.schedule(n_ev, arcs)
        if sch is not None and max(sch.earliest) > H:
            continue
        compared += 1
        if (sch is not None) != bool(ok.any()):
            bad += 1
            continue
        if sch is None:
            continue
        feas += 1
        sub = grid[ok]
        end = int(sub.max(axis=1).min())
        if sch.end != end or list(sch.earliest) != list(sub.min(axis=0)) or list(sch.latest) != list(sub[sub.max(axis=1) <= end].max(axis=0)):
            bad += 1
    return compared, feas, bad


def nx_graph(n, arcs):
    g = nx.DiGraph()
    for e in range(n):
        g.add_edge(n, e, weight=0)
    for a in arcs:
        for (u, v, w) in ([(a.u, a.v, a.lo)] + ([(a.v, a.u, -a.hi)] if a.hi is not None else [])):
            g.add_edge(u, v, weight=min(g[u][v]["weight"], -w) if g.has_edge(u, v) else -w)
    return g


def cpsat_ok(n, arcs):
    m = cp_model.CpModel()
    x = [m.NewIntVar(0, 5000, f"x{e}") for e in range(n)]
    for a in arcs:
        m.Add(x[a.v] - x[a.u] >= a.lo)
        if a.hi is not None:
            m.Add(x[a.v] - x[a.u] <= a.hi)
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    return s.Solve(m) == cp_model.OPTIMAL


def part2(n_nets):
    configs = [Settings(transfers="alle", k_transfers=k, wait_max=w) for k in (2, 4, 8) for w in (None, 15, 5)] + \
              [Settings(transfers="gerichtet", k_transfers=k, wait_max=w) for k in (3, 6) for w in (30, 10)] + \
              [Settings(transfers="alle", k_transfers=4, wait_max=10, headway=4), Settings(transfers="gerichtet", k_transfers=4, wait_max=30, turn_extra=10)]
    compared = bad = feas = witnesses = 0
    for i in range(n_nets):
        inst = make_instance(6, 40000 + 100 * i)[0]
        for s in configs:
            n, arcs = M.build_arcs(inst, s)
            early, wit = S.earliest(n, arcs)
            g = nx_graph(n, arcs)
            compared += 1
            ok = early is not None
            if nx.negative_edge_cycle(g, weight="weight") == ok or cpsat_ok(n, arcs) != ok or G.is_feasible(n, arcs) != ok:
                bad += 1
                continue
            if ok:
                feas += 1
                dist = nx.single_source_bellman_ford_path_length(g, n, weight="weight")
                bad += [-dist[e] for e in range(n)] != early
            else:
                witnesses += 1
                cyc = W.witness_cycle(n, arcs)
                bad += not (G.is_closed_walk(cyc) and G.cycle_weight(cyc) > 0)
    return compared, feas, witnesses, bad


if __name__ == "__main__":
    n1 = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    n2 = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    c, f, b = part1(n1)
    print(f"Zufallssysteme: {n1} erzeugt, {c} verglichen (Rest: Wertebox), davon {f} möglich, Abweichungen: {b}")
    c, f, w, b = part2(n2)
    print(f"Echte Netze: {n2} Netze x 15 Einstellungen = {c} Vergleiche, {f} möglich, {w} unmöglich (Zeugen geprüft), Abweichungen: {b}")
