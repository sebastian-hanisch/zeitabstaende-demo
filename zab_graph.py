"""Bedingungsgraph und längste Wege (Bellman-Ford).

Jeder Bogen (u, v, lo, hi) liefert zwei Kanten: u -> v mit Gewicht +lo (x_v >= x_u + lo) und, wenn ein Höchstabstand da ist, v -> u mit Gewicht
-hi (x_u >= x_v - hi). Ein Plan ist genau dann möglich, wenn der Graph keinen Kreis positiver Länge hat: die Summe der Mindestabstände entlang
des Kreises ist dann größer als die Summe der Höchstabstände, die ihn zurückholen. Sonst ergibt der längste Weg ab einer Quelle z (x_z = 0, alle
Ereignisse ab Minute 0) die frühesten Lagen.

Eine Kante ist (u, v, w, tag); tag = (Bogen-Index, "lo" | "hi") oder None bei den künstlichen Kanten der Quelle und der Senke. Zwei Fassungen:
`longest_paths` (Python, liefert bei positivem Kreis den Zeugen als Kantenzug) und `FastBF` (numpy, rundenweise, nur Entscheidung und Abstände).
"""
from __future__ import annotations

import numpy as np

NEG = None   # „unerreichbar“ in der Python-Fassung


def constraint_edges(arcs) -> list:
    """Kanten des Bedingungsgraphen: u -> v mit +lo, v -> u mit -hi (nur wenn hi nicht None). Tag = (Bogen-Index, "lo" | "hi")."""
    edges = []
    for i, a in enumerate(arcs):
        edges.append((a.u, a.v, a.lo, (i, "lo")))
        if a.hi is not None:
            edges.append((a.v, a.u, -a.hi, (i, "hi")))
    return edges


def with_source(edges: list, n: int) -> list:
    """Quelle z = n: Kante z -> e mit Gewicht 0 für jedes Ereignis e (x_e >= 0)."""
    return edges + [(n, e, 0, None) for e in range(n)]


def with_sink(edges: list, n: int, sink: int) -> list:
    """Senke `sink`: Kante e -> sink mit Gewicht 0 für jedes Ereignis e (Gesamtende >= jedes x_e)."""
    return edges + [(e, sink, 0, None) for e in range(n)]


def longest_paths(edges: list, source: int, n_nodes: int):
    """Bellman-Ford für längste Wege ab `source` (Knoten 0 .. n_nodes-1). Rückgabe (dist, pred, cycle):
    dist[v] = Länge des längsten Weges (None: unerreichbar), pred[v] = Index der letzten Kante dieses Weges (-1 ohne),
    cycle = None, wenn kein positiver Kreis erreichbar ist, sonst die Kanten eines Kreises positiver Länge in Fahrtrichtung (Zeuge)."""
    dist: list = [NEG] * n_nodes
    pred = [-1] * n_nodes
    dist[source] = 0
    last = -1
    for _rnd in range(n_nodes):
        last = -1
        for ei, (u, v, w, _t) in enumerate(edges):
            du = dist[u]
            if du is not None and (dist[v] is None or du + w > dist[v]):
                dist[v] = du + w
                pred[v] = ei
                last = v
        if last == -1:
            return dist, pred, None
    # `last` wurde in der n-ten Runde noch verbessert: n Schritte rückwärts landen sicher auf dem Kreis
    x = last
    for _ in range(n_nodes):
        x = edges[pred[x]][0]
    cyc = []
    y = x
    while True:
        ei = pred[y]
        cyc.append(edges[ei])
        y = edges[ei][0]
        if y == x:
            break
    cyc.reverse()
    return dist, pred, cyc


def cycle_weight(cycle: list) -> int:
    """Länge des Kantenzuges: Summe der Kantengewichte."""
    return sum(e[2] for e in cycle)


def is_closed_walk(cycle: list) -> bool:
    """Jede Kante beginnt dort, wo die vorige endet, und der Zug schließt sich."""
    return bool(cycle) and all(cycle[i][1] == cycle[(i + 1) % len(cycle)][0] for i in range(len(cycle)))


def cycle_excess(cycle: list) -> dict:
    """Zerlegung eines Kreises: Summe der Mindestabstände (Kanten „lo“), Summe der Höchstabstände (Kanten „hi“) und ihr Überschuss
    (Mindestabstände minus Höchstabstände = Länge des Kreises); `hi_count` = Zahl der Höchstabstände im Kreis."""
    lo_sum = sum(e[2] for e in cycle if e[3] is not None and e[3][1] == "lo")
    hi_sum = sum(-e[2] for e in cycle if e[3] is not None and e[3][1] == "hi")
    return {"min_sum": lo_sum, "max_sum": hi_sum, "excess": lo_sum - hi_sum, "hi_count": sum(1 for e in cycle if e[3] is not None and e[3][1] == "hi"),
            "length": len(cycle)}


class FastBF:
    """Rundenweises Bellman-Ford mit numpy; Kanten nach Zielknoten sortiert (reduceat). Nur Entscheidung und Abstände, keine Zeugen.
    Quelle ist der Knoten n (x_n = 0), der mit Gewicht 0 zu jedem Ereignis führt."""

    def __init__(self, n: int, arcs):
        self.n = n
        if arcs:
            u = np.array([a.u for a in arcs], dtype=np.int64)
            v = np.array([a.v for a in arcs], dtype=np.int64)
            lo = np.array([a.lo for a in arcs], dtype=np.int64)
            has_hi = np.array([a.hi is not None for a in arcs], dtype=bool)
            hi = np.array([a.hi if a.hi is not None else 0 for a in arcs], dtype=np.int64)
        else:
            u = v = lo = hi = np.zeros(0, dtype=np.int64)
            has_hi = np.zeros(0, dtype=bool)
        ev = np.arange(n, dtype=np.int64)
        eu = np.concatenate([u, v[has_hi], np.full(n, n, dtype=np.int64)])
        evv = np.concatenate([v, u[has_hi], ev])
        ew = np.concatenate([lo, -hi[has_hi], np.zeros(n, dtype=np.int64)])
        order = np.argsort(evv, kind="stable")
        self.u, self.v, self.w = eu[order], evv[order], ew[order]
        self.starts = np.flatnonzero(np.r_[True, self.v[1:] != self.v[:-1]])
        self.targets = self.v[self.starts]

    def run(self):
        """(dist, ok): dist = früheste Lagen der n Ereignisse (Knoten n ist die Quelle), ok = False bei positivem Kreis."""
        nn = self.n + 1
        neg = -10 ** 9
        d = np.full(nn, neg, dtype=np.int64)
        d[self.n] = 0
        for _rnd in range(nn):
            cand = np.where(d[self.u] > neg, d[self.u] + self.w, neg)
            red = np.maximum.reduceat(cand, self.starts)
            better = red > d[self.targets]
            if not better.any():
                return d[: self.n], True
            d[self.targets[better]] = red[better]
        return d[: self.n], False


def is_feasible(n: int, arcs) -> bool:
    """Gibt es einen Plan? (Kein Kreis positiver Länge im Bedingungsgraphen.) Schnelle numpy-Fassung."""
    return FastBF(n, arcs).run()[1]
