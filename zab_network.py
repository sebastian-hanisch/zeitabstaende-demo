"""Netz, Linien und verlangte Umsteigeanschlüsse (der Generator der Fall-Demo, kopiert).

aus taktfahrplan-demo (tkt_network.py und Teile von tkt_timetable.py), angepasst: Präfix, nur die Teile, die diese Demo braucht (keine Takt-
Auswertung), `Instance` ohne Takt. Die Demos sind eigenständig, deshalb wird kopiert und nicht importiert; `tests/test_network.py` prüft, dass die Kopie
dieselben Netze erzeugt wie das Original (eingefrorene Kennzahlen immer, Vergleich mit dem Geschwisterordner, wenn er da ist).

Ganzzahliger Netzgenerator: Haltestellen auf einem Raster, symmetrische ganzzahlige Nachfrage mit Hub-Konzentration, Linien nach der
Nachfrage-Greedy-Konstruktion (Port von `demand_greedy_construction` der transit-demo), Fahrzeiten aus ganzzahligen Entfernungen (`isqrt`).
Zufall nur über SplitMix64. Alle Netze sind Annahmen, keine Echtdaten.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isqrt

import numpy as np

from zab_rng import SplitMix64


@dataclass
class Line:
    stops: list          # Haltestellen-Indizes in Reihenfolge
    run: list            # Fahrzeit (Minuten) je Abschnitt k: stops[k] -> stops[k+1]


@dataclass
class Instance:
    lines: list
    transfers: dict      # (la, da, ka, lb, db, kb) -> Nachfrage; Ankunft (la,da,ka) -> Abfahrt (lb,db,kb)
    tmin: int = 4        # kürzeste Standzeit an einem Endpunkt (min)


# ---------------------------------------------------------------- Umsteiger ableiten
def direction(pos_from: int, pos_to: int) -> str:
    return "f" if pos_to > pos_from else "b"


def opposite(d: str) -> str:
    return "b" if d == "f" else "f"


def run_between(line: Line, a: int, b: int) -> int:
    lo, hi = min(a, b), max(a, b)
    return sum(line.run[lo:hi])


def derive_transfers(lines: list, demand: np.ndarray) -> dict:
    """Je Haltestellenpaar ohne Direktlinie die Route mit kürzester Fahrzeit über genau einen Umstieg;
    Nachfrage je zur Hälfte in jede Richtung auf die Umstiegsaktivität Ankunft -> Abfahrt."""
    pos = [{s: k for k, s in enumerate(line.stops)} for line in lines]
    n = demand.shape[0]
    out = defaultdict(float)
    for i in range(n):
        for j in range(i + 1, n):
            d = float(demand[i][j])
            if d <= 0:
                continue
            li = [x for x in range(len(lines)) if i in pos[x]]
            lj = [x for x in range(len(lines)) if j in pos[x]]
            if set(li) & set(lj):
                continue
            best = None
            for la in li:
                for lb in lj:
                    for s in set(pos[la]) & set(pos[lb]):
                        cost = run_between(lines[la], pos[la][i], pos[la][s]) + run_between(lines[lb], pos[lb][s], pos[lb][j])
                        if best is None or cost < best[0]:
                            best = (cost, la, lb, s)
            if best is None:
                continue
            _, la, lb, s = best
            ai, as_, bs, bj = pos[la][i], pos[la][s], pos[lb][s], pos[lb][j]
            dA, dB = direction(ai, as_), direction(bs, bj)
            out[(la, dA, as_, lb, dB, bs)] += d / 2
            dB2, dA2 = opposite(dB), opposite(dA)
            out[(lb, dB2, bs, la, dA2, as_)] += d / 2
    return dict(out)


def shared_segments(inst: Instance) -> list:
    """Paare von Abfahrtsereignissen zweier Linien auf demselben gerichteten Abschnitt."""
    seg = defaultdict(list)
    for li, line in enumerate(inst.lines):
        m = len(line.stops) - 1
        for k in range(m):
            seg[(line.stops[k], line.stops[k + 1])].append((li, ("dep", "f", k)))
            seg[(line.stops[k + 1], line.stops[k])].append((li, ("dep", "b", k + 1)))
    pairs = []
    for lst in seg.values():
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                if lst[x][0] != lst[y][0]:
                    pairs.append((lst[x], lst[y]))
    return pairs


# ---------------------------------------------------------------- Generator
def generate_network(n_stops: int, seed: int, hub_pct: int = 50, n_hubs: int = 2):
    """Ganzzahlige Haltestellen (Raster 5..95) und symmetrische ganzzahlige Nachfrage; hub_pct = Hub-Konzentration in Prozent."""
    rng = SplitMix64(seed)
    coords = np.array([[5 + rng.below(91), 5 + rng.below(91)] for _ in range(n_stops)], dtype=np.int64)
    base = [[0] * n_stops for _ in range(n_stops)]
    for i in range(n_stops):
        for j in range(i + 1, n_stops):
            base[i][j] = base[j][i] = 1 + rng.below(10)
    pool = list(range(n_stops))
    hubs = []
    for _ in range(max(1, min(n_hubs, n_stops))):
        hubs.append(pool.pop(rng.below(len(pool))))
    boost = 100 + 6 * hub_pct
    b = [boost if i in hubs else 100 for i in range(n_stops)]
    demand = np.zeros((n_stops, n_stops), dtype=np.int64)
    for i in range(n_stops):
        for j in range(n_stops):
            if i != j:
                demand[i, j] = (base[i][j] * b[i] * b[j] + 5000) // 10000
    return coords, demand, hubs


def sq_dist(coords, a: int, b: int) -> int:
    dx = int(coords[a][0]) - int(coords[b][0])
    dy = int(coords[a][1]) - int(coords[b][1])
    return dx * dx + dy * dy


def demand_greedy(coords, demand, n_lines: int, max_line_length: int) -> list:
    """Port von `demand_greedy_construction` (Wachstumsbonus 2,5 = 5/2; alle Bewertungen mit 2 multipliziert, damit ganzzahlig;
    Gleichstände wie im Original: der erste Kandidat in Index-Reihenfolge gewinnt; Endenwahl über Quadratdistanzen)."""
    n = len(coords)
    GROW, ONE = 5, 2
    lines, covered, network = [], set(), set()
    for line_num in range(n_lines):
        best_pair, best_score, best_pair_demand = None, -1, 0
        for i in range(n):
            for j in range(i + 1, n):
                if (i, j) in covered:
                    continue
                i_in, j_in = i in network, j in network
                if line_num > 0 and not (i_in or j_in):
                    continue
                d = int(demand[i][j])
                score = ONE * d
                if line_num > 0 and (i_in != j_in):
                    score = GROW * d
                if score > best_score:
                    best_score, best_pair, best_pair_demand = score, (i, j), d
        if best_pair is None or best_pair_demand <= 0:
            break
        line = list(best_pair)
        while len(line) < max_line_length:
            best_ext, best_ext_score = None, 0
            for cand in range(n):
                if cand in line:
                    continue
                gain = sum(int(demand[cand][s]) for s in line)
                score = gain * (GROW if cand not in network else ONE)
                if score > best_ext_score:
                    best_ext_score, best_ext = score, cand
            if best_ext is None:
                break
            if sq_dist(coords, best_ext, line[0]) <= sq_dist(coords, best_ext, line[-1]):
                line.insert(0, best_ext)
            else:
                line.append(best_ext)
        lines.append(line)
        network.update(line)
        for a in range(len(line)):
            for c in range(a + 1, len(line)):
                covered.add(tuple(sorted((line[a], line[c]))))
    while len(lines) < n_lines:
        lines.append([])
    return lines


def build_instance_int(n_stops: int, n_lines: int, max_len: int, seed: int, hub_pct: int = 50):
    """Netz + Linien + Umsteiger; Fahrzeit = Entfernung (isqrt, ganzzahlig) / 5 gerundet, mindestens 2 min."""
    coords, demand, _hubs = generate_network(n_stops, seed, hub_pct)
    raw = [line for line in demand_greedy(coords, demand, n_lines, max_len) if len(line) >= 2]
    lines = []
    for line in raw:
        run = [max(2, (isqrt(sq_dist(coords, a, b)) + 2) // 5) for a, b in zip(line, line[1:])]
        lines.append(Line([int(x) for x in line], run))
    return Instance(lines, derive_transfers(lines, demand)), demand, coords


def build_valid_instance(n_lines: int, seed: int, n_stops: int = 20, max_len: int = 6, min_transfers: int = 3, attempts: int = 50):
    """Der erste gültige Seed ab `seed`: gültig = mindestens `min_transfers` Umsteigeverbindungen (sonst gäbe es nichts zu planen).
    Rückgabe (Instance, Nachfrage, Koordinaten, tatsächlich verwendeter Seed); die Versuche zählen den Seed einfach hoch."""
    for k in range(attempts):
        inst, demand, coords = build_instance_int(n_stops, n_lines, max_len, seed + k)
        if len(inst.lines) >= 2 and len(inst.transfers) >= min_transfers:
            return inst, demand, coords, seed + k
    raise ValueError(f"kein gültiger Seed ab {seed} in {attempts} Versuchen")


def make_instance(n_lines: int, seed: int):
    """Kurzform für Sweeps: (Instance, tatsächlich verwendeter Seed)."""
    inst, _demand, _coords, used = build_valid_instance(n_lines, seed)
    return inst, used
