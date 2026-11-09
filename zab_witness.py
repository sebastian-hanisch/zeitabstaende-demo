"""Zeugen für einen unmöglichen Plan: der Kreis positiver Länge und eine inklusionsminimale unmögliche Bogenmenge.

Ein Plan ist unmöglich, wenn der Bedingungsgraph einen Kreis positiver Länge hat (`zab_graph`). `witness_cycle` liefert einen solchen Kreis als
geschlossenen Kantenzug. `minimal_infeasible` liefert per Löschfilter eine inklusionsminimale unmögliche Bogenmenge: jeder Bogen wird probeweise entfernt,
bleibt der Plan unmöglich, bleibt er entfernt. Übrig bleibt eine Menge, aus der kein Bogen mehr fehlen darf (jeder Bogen darin ist nötig); sie ist nicht
eindeutig, welche übrig bleibt, hängt von der Bogenreihenfolge ab. `classify_cycle` zählt, wie viele Höchstabstände der Kreis in einer solchen Menge benutzt.
Ob ein Plan einen **Zeitkreis** hat, hängt nicht von der Reihenfolge ab und zeigt der Test ohne alle Höchstabstände (`has_time_cycle`): Ein Plan ist ein
Zeitkreis-Plan, wenn er schon ohne jeden Höchstabstand unmöglich ist, sonst ist er „nur durch Höchstabstände unmöglich“. `explain_infeasible` fasst beides zusammen;
bei einem Zeitkreis-Plan wird die Löschfilter-Menge im Plan ohne Höchstabstände gesucht (sie enthält dann keinen Höchstabstand), sonst im Plan selbst.
"""
from __future__ import annotations

from typing import Optional

from zab_graph import constraint_edges, cycle_excess, is_feasible, longest_paths, with_source
from zab_model import without_upper_bounds


def witness_cycle(n: int, arcs):
    """Kreis positiver Länge als Kantenzug (Liste von Kanten (u, v, w, tag)), oder None, wenn der Plan möglich ist."""
    _d, _p, cyc = longest_paths(with_source(constraint_edges(arcs), n), n, n + 1)
    return cyc


def minimal_infeasible(n: int, arcs) -> list:
    """Indizes einer inklusionsminimalen unmöglichen Bogenmenge (Löschfilter, nicht eindeutig); leere Liste, wenn der Plan möglich ist."""
    if is_feasible(n, arcs):
        return []
    keep = list(range(len(arcs)))
    for i in list(keep):
        trial = [j for j in keep if j != i]
        if not is_feasible(n, [arcs[j] for j in trial]):
            keep = trial
    return keep


def classify_cycle(n: int, arcs_subset) -> dict:
    """Kreis in einer inklusionsminimalen unmöglichen Bogenmenge: Länge in Kanten, Zahl der Höchstabstände (Rückkanten), Zahl der Anschlüsse und Bogenarten.
    Ob der Plan einen Zeitkreis hat, sagt das nicht (der Kreis einer Menge mit Höchstabstand kann neben einem Zeitkreis stehen): dafür `has_time_cycle`."""
    cyc = witness_cycle(n, arcs_subset)
    assert cyc is not None
    used = {e[3][0]: arcs_subset[e[3][0]].kind for e in cyc if e[3] is not None}
    kinds = list(used.values())
    info = cycle_excess(cyc)
    return {"len": len(cyc), "hi": info["hi_count"], "transfer": kinds.count("transfer"), "kinds": {k: kinds.count(k) for k in sorted(set(kinds))},
            "excess": info["excess"]}


def has_time_cycle(n: int, arcs) -> bool:
    """Zeitkreis-Plan: schon ohne jeden Höchstabstand unmöglich (unabhängig von der Bogenreihenfolge). Ein möglicher Plan hat keinen."""
    return not is_feasible(n, without_upper_bounds(arcs))


def explain_infeasible(n: int, arcs) -> Optional[dict]:
    """Zerlegung eines unmöglichen Plans oder None, wenn er möglich ist: `time_cycle` (Zeitkreis-Plan, sonst nur durch Höchstabstände unmöglich), `keep` (Indizes in `arcs`
    einer inklusionsminimalen unmöglichen Menge), `iis` (ihre Größe) und die Felder von `classify_cycle` für den Kreis darin."""
    if is_feasible(n, arcs):
        return None
    time_cycle = has_time_cycle(n, arcs)
    base = without_upper_bounds(arcs) if time_cycle else list(arcs)
    keep = minimal_infeasible(n, base)
    info = classify_cycle(n, [base[j] for j in keep])
    return {**info, "time_cycle": time_cycle, "keep": keep, "iis": len(keep)}


def witness_rows(arcs, cycle, labels) -> list:
    """Zeilen für die Anzeige des Zeugen: je Kante des Kreises Art des Bogens, ob Mindest- oder Höchstabstand, die beiden Ereignisse und den Beitrag.
    Mindestabstand: „Ereignis v frühestens lo nach u“ (Beitrag +lo). Höchstabstand: „Ereignis u höchstens hi nach v“, der Kreis geht von v zurück nach u
    (Beitrag -hi)."""
    rows = []
    for (u, v, w, tag) in cycle:
        arc = arcs[tag[0]]
        rows.append({"art": arc.kind, "seite": "Mindestabstand" if tag[1] == "lo" else "Höchstabstand", "von": labels[u], "nach": labels[v], "beitrag": w})
    return rows
