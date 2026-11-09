"""Frühest- und Spätestlagen, Spielraum und kritische Ereignisse eines möglichen Plans.

Rahmen: alle Ereignisse ab Minute 0 (Quelle z), das Gesamtende D ist das früheste mögliche (längster Weg zur Senke t). Frühestlage =
längster Weg von z; Spätestlage = D minus längster Weg zur Senke (der Rückwärtslauf); Spielraum = spät minus früh; kritisch = Spielraum 0.
`critical_cpm` rechnet dasselbe ohne jeden Höchstabstand (die klassische Rechnung des kritischen Pfades): Ereignisse, die nur mit
Höchstabständen kritisch sind, fehlen dort.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from zab_graph import constraint_edges, longest_paths, with_sink, with_source
from zab_model import without_upper_bounds


@dataclass(frozen=True)
class Schedule:
    """Ergebnis für einen Plan: früheste und späteste Lage je Ereignis, Spielraum, Gesamtende D."""
    earliest: tuple
    latest: tuple
    slack: tuple
    end: int


def earliest(n: int, arcs):
    """(frueheste Lagen, None) bei möglichem Plan, sonst (None, Zeuge) mit dem Kreis positiver Länge als Kantenzug."""
    edges = with_source(constraint_edges(arcs), n)
    dist, _pred, cyc = longest_paths(edges, n, n + 1)
    if cyc is not None:
        return None, cyc
    return [dist[e] for e in range(n)], None


def latest(n: int, arcs, end: Optional[int] = None):
    """Spätestlagen bei Gesamtende `end` (Standard: das früheste mögliche). Rückwärtslauf: längster Weg von der Senke im umgekehrten Graphen.
    Rückgabe (Spätestlagen, end) oder (None, Zeuge) bei unmöglichem Plan."""
    sink = n + 1
    edges = with_sink(with_source(constraint_edges(arcs), n), n, sink)
    dist, _pred, cyc = longest_paths(edges, n, n + 2)
    if cyc is not None:
        return None, cyc
    d_end = dist[sink]
    if end is None:
        end = d_end
    rev = [(v, u, w, t) for (u, v, w, t) in edges]
    dist_t, _p, cyc2 = longest_paths(rev, sink, n + 2)
    assert cyc2 is None   # derselbe Graph, nur umgekehrt: hat der Hinlauf keinen positiven Kreis, hat ihn der Rücklauf auch nicht
    return [end - dist_t[e] for e in range(n)], end


def slack(early, late) -> list:
    """Spielraum je Ereignis: späteste minus früheste Lage."""
    return [b - a for a, b in zip(early, late)]


def critical(slack_list) -> list:
    """Indizes der Ereignisse mit Spielraum 0."""
    return [e for e, s in enumerate(slack_list) if s == 0]


def schedule(n: int, arcs):
    """Vollständige Rechnung: (Schedule, None) bei möglichem Plan, sonst (None, Zeuge)."""
    early, wit = earliest(n, arcs)
    if early is None:
        return None, wit
    late, end = latest(n, arcs)
    return Schedule(tuple(early), tuple(late), tuple(slack(early, late)), end), None


def critical_cpm(n: int, arcs):
    """Kritische Ereignisse der klassischen Rechnung (alle Höchstabstände weggelassen). Voraussetzung: der Plan MIT Höchstabständen ist möglich; dann ist er
    es auch ohne sie (weniger Bedingungen). Ein Zeitkreis (nur Mindestabstände) bleibt auch ohne Höchstabstände unmöglich, dann gibt es keine klassische
    Rechnung: die Prüfung `assert` bricht ab. `critical_only_by_upper_bounds` prüft die Voraussetzung selbst."""
    sch, wit = schedule(n, without_upper_bounds(arcs))
    assert wit is None
    return critical(sch.slack), sch


def critical_only_by_upper_bounds(n: int, arcs):
    """Ereignisse, die mit Höchstabständen kritisch sind, in der klassischen Rechnung aber nicht (Spielraum dort > 0)."""
    full, wit = schedule(n, arcs)
    if full is None:
        return None, wit
    cpm_crit, _ = critical_cpm(n, arcs)
    return sorted(set(critical(full.slack)) - set(cpm_crit)), None
