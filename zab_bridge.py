"""Brücke zum Takt und zu den Grenzen des einmaligen Plans (CP-SAT, höchstens zwei Arbeiter).

* `periodic_feasible` / `periodic_solution`: dieselben Bögen, aber periodisch: pi_v - pi_u + T*p = x mit x in [lo, hi] (Abstände nur noch modulo T).
  Satz: jede einmalige Lösung, modulo T genommen, löst das periodische System. Also: einmalig möglich => periodisch möglich, nicht umgekehrt.
* `free_order_feasible`: die Mindestzugfolge mit freier Reihenfolge (Entweder-oder je Abschnittspaar), im Gegensatz zur festen Reihenfolge nach
  Liniennummer im Hauptplan. Die Wahl der Reihenfolge ist ein Job-Shop-Problem (disjunktiver Graph).
* `max_kept_weight` / `greedy_kept_weight`: wie viel der verlangten Nachfrage ein einmaliger Plan höchstens halten kann, wenn Anschlüsse
  gestrichen werden dürfen (exakt) bzw. wenn man den billigsten Anschluss im Zeugen-Kreis streicht, bis der Plan möglich ist (Greedy).
"""
from __future__ import annotations

import math
from typing import Optional

from ortools.sat.python import cp_model

import zab_constants as C
from zab_model import KIND_TRANSFER, Settings, build_arcs, chosen_transfers, headway_pairs
from zab_witness import witness_cycle

HORIZON = 5000   # größte Minute im CP-SAT-Modell des einmaligen Plans


def _status(solver, st) -> Optional[bool]:
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return True
    if st == cp_model.INFEASIBLE:
        return False
    return None   # Zeitlimit: nicht bewiesen


def periodic_solution(n: int, arcs, T: int = C.T, limit: float = C.CPSAT_LIVE_SECONDS, workers: int = 1):
    """(Status, pi, x): Status True/False/None (None: Zeitlimit, nicht bewiesen); pi = Phase je Ereignis in 0 .. T-1, x = Abstand je Bogen
    (kleinster Wert >= lo, der zu pi_v - pi_u modulo T passt). Bei Status False/None sind pi und x None."""
    m = cp_model.CpModel()
    pi = [m.NewIntVar(0, T - 1, f"p{e}") for e in range(n)]
    m.Add(pi[0] == 0)
    for a, arc in enumerate(arcs):
        hi_eff = arc.lo + T - 1 if arc.hi is None else arc.hi
        if hi_eff - arc.lo >= T - 1:
            continue   # ein Fenster von mindestens T Minuten lässt jeden Rest modulo T zu
        x = m.NewIntVar(arc.lo, hi_eff, f"x{a}")
        pmin = math.ceil((arc.lo - (T - 1)) / T)
        pmax = math.floor((hi_eff + (T - 1)) / T)
        p = m.NewIntVar(pmin, pmax, f"k{a}")
        m.Add(pi[arc.v] - pi[arc.u] + T * p == x)
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = workers
    solver.parameters.max_time_in_seconds = limit
    st = solver.Solve(m)
    ok = _status(solver, st)
    if not ok:
        return ok, None, None
    phases = [solver.Value(v) for v in pi]
    xs = [a.lo + ((phases[a.v] - phases[a.u] - a.lo) % T) for a in arcs]
    return True, phases, xs


def periodic_feasible(n: int, arcs, T: int = C.T, limit: float = C.CPSAT_LIVE_SECONDS, workers: int = 1) -> Optional[bool]:
    """Gibt es einen periodischen Plan mit Takt T? True/False, None bei Zeitlimit (nicht bewiesen)."""
    return periodic_solution(n, arcs, T, limit, workers)[0]


def cycle_sum_of_x(cycle: list, xs: list) -> int:
    """Summe der tatsächlichen Abstände entlang des Kreises (Mindestabstände +x, Höchstabstände -x); im periodischen Plan ein Vielfaches von T."""
    return sum(xs[e[3][0]] if e[3][1] == "lo" else -xs[e[3][0]] for e in cycle)


def free_order_feasible(inst, s: Settings, limit: float = C.CPSAT_LIVE_SECONDS, workers: int = 1):
    """Einmaliger Plan mit Mindestzugfolge s.headway, Reihenfolge je Abschnittspaar FREI (Entweder-oder). Rückgabe (True/False/None, Zahl der Paare)."""
    s0 = Settings(**{**s.__dict__, "headway": 0})
    n, arcs = build_arcs(inst, s0)
    m = cp_model.CpModel()
    x = [m.NewIntVar(0, HORIZON, f"x{e}") for e in range(n)]
    for a in arcs:
        m.Add(x[a.v] - x[a.u] >= a.lo)
        if a.hi is not None:
            m.Add(x[a.v] - x[a.u] <= a.hi)
    pairs = headway_pairs(inst) if s.headway > 0 else []
    for (a, b) in pairs:
        z = m.NewBoolVar("o")
        m.Add(x[b] - x[a] >= s.headway).OnlyEnforceIf(z)
        m.Add(x[a] - x[b] >= s.headway).OnlyEnforceIf(z.Not())
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = workers
    solver.parameters.max_time_in_seconds = limit
    return _status(solver, solver.Solve(m)), len(pairs)


def max_kept_weight(inst, s: Settings, limit: float = C.CPSAT_LIVE_SECONDS, workers: int = C.CPSAT_WORKERS):
    """Größter Anteil der verlangten Nachfrage, den ein einmaliger Plan halten kann, wenn Anschlüsse gestrichen werden dürfen (Anschlüsse als
    optionale Bögen, maximiere die gehaltene Nachfrage). Rückgabe (Anteil, Statusname); Status „OPTIMAL“ = bewiesen, „FEASIBLE“ = Zeitlimit,
    der Anteil ist dann nur eine untere Schranke."""
    n, arcs = build_arcs(inst, s)
    keys = chosen_transfers(inst, s)
    weights = [inst.transfers[k] for k in keys]
    total = sum(weights)
    fixed = [a for a in arcs if a.kind != KIND_TRANSFER]
    trans = [a for a in arcs if a.kind == KIND_TRANSFER]
    assert len(trans) == len(keys)
    m = cp_model.CpModel()
    x = [m.NewIntVar(0, HORIZON, f"x{e}") for e in range(n)]
    for a in fixed:
        m.Add(x[a.v] - x[a.u] >= a.lo)
        if a.hi is not None:
            m.Add(x[a.v] - x[a.u] <= a.hi)
    z = []
    for a in trans:
        b = m.NewBoolVar("z")
        m.Add(x[a.v] - x[a.u] >= a.lo).OnlyEnforceIf(b)
        if a.hi is not None:
            m.Add(x[a.v] - x[a.u] <= a.hi).OnlyEnforceIf(b)
        z.append(b)
    m.Maximize(sum(int(round(w * 2)) * zi for w, zi in zip(weights, z)))   # Nachfrage ist ein Vielfaches von 0,5
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = workers
    solver.parameters.max_time_in_seconds = limit
    st = solver.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, solver.StatusName(st)
    kept = sum(w for w, zi in zip(weights, z) if solver.Value(zi)) / total if total else 1.0
    return kept, solver.StatusName(st)


def greedy_kept_weight(inst, s: Settings):
    """Zeuge suchen (Bellman-Ford), den Anschluss mit der kleinsten Nachfrage im Kreis streichen, wiederholen, bis der Plan möglich ist.
    Rückgabe: gehaltener Anteil der Nachfrage, oder None, wenn ein Zeuge keinen Anschluss enthält (dann hilft Streichen nicht)."""
    n, arcs = build_arcs(inst, s)
    keys = chosen_transfers(inst, s)
    trans_idx = [i for i, a in enumerate(arcs) if a.kind == KIND_TRANSFER]
    weight = {trans_idx[j]: inst.transfers[keys[j]] for j in range(len(keys))}
    total = sum(weight.values())
    alive = set(range(len(arcs)))
    while True:
        order = sorted(alive)
        cyc = witness_cycle(n, [arcs[i] for i in order])
        if cyc is None:
            break
        on = {order[e[3][0]] for e in cyc if arcs[order[e[3][0]]].kind == KIND_TRANSFER}
        if not on:
            return None
        alive.discard(min(on, key=lambda i: (weight[i], i)))
    return sum(w for i, w in weight.items() if i in alive) / total if total else 1.0
