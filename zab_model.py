"""Das System aus Mindest- und Höchstabständen: Ereignisse, Bögen, verlangte Anschlüsse.

Beobachtungseinheit ist ein Umlauf je Linie (Hinfahrt, Wende, Rückfahrt), ohne Wiederholung. Ereignisse sind Abfahrt und Ankunft je Halt und
Richtung. Jede Bedingung ist ein Bogen (u, v, lo, hi): lo <= x_v - x_u <= hi, hi = None heißt „kein Höchstabstand“. Die Bögen:

  run      Fahrzeit r:                [r, r + Reserve]            (Reserve = Fahrzeitreserve in Prozent der Fahrzeit, aufgerundet)
  dwell    Halt:                      [Haltezeit-Minimum, Haltezeit-Höchst]
  turn     Wende am Endpunkt:         [Mindest-Standzeit, Mindest-Standzeit + Höchstwende]   (Höchstwende unbegrenzt: kein Höchstabstand)
  transfer Anschluss (Ankunft -> Abfahrt): [Mindest-Umsteigezeit, Mindest-Umsteigezeit + Höchstwartezeit]
  headway  Mindestzugfolge auf einem gemeinsamen Abschnitt: [h, kein Höchstabstand], die Reihenfolge ist FEST (kleinere Liniennummer zuerst)

Die Anschlussliste ist eine Planungsannahme: verlangt werden nur die k Anschlüsse mit der größten Nachfrage (Gleichstand: Schlüsselreihenfolge),
wahlweise nur Zubringer von der kleineren zur größeren Liniennummer („gerichtet“). Keine Echtdaten.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Optional

from zab_network import Instance, shared_segments

KIND_RUN, KIND_DWELL, KIND_TURN, KIND_TRANSFER, KIND_HEADWAY = "run", "dwell", "turn", "transfer", "headway"


class Arc(NamedTuple):
    u: int
    v: int
    lo: int
    hi: Optional[int]   # None: kein Höchstabstand
    kind: str


@dataclass(frozen=True)
class Settings:
    """Regler des Plans (immer mit Schlüsselwörtern aufrufen, nie positional). Alle Zeiten in ganzen Minuten."""
    reserve_pct: int = 0                 # Fahrzeitreserve in Prozent der Fahrzeit (aufgerundet)
    dwell_lo: int = 1
    dwell_hi: int = 3
    turn_extra: Optional[int] = None     # Wende: mindestens tmin, höchstens tmin + turn_extra (None: unbegrenzt)
    transfer_min: int = 3                # Mindest-Umsteigezeit
    wait_max: Optional[int] = None       # Höchstwartezeit über der Mindestzeit (None: unbegrenzt)
    headway: int = 0                     # Mindestzugfolge auf gemeinsamen Abschnitten (Reihenfolge fest nach Liniennummer), 0 = aus
    transfers: str = "alle"              # "alle" (beide Richtungen) oder "gerichtet" (nur Zubringer mit kleinerer Liniennummer)
    k_transfers: Optional[int] = None    # nur die k Anschlüsse mit der größten Nachfrage werden verlangt (None: alle)


def reserve(run: int, pct: int) -> int:
    """Fahrzeitreserve in Minuten: pct Prozent der Fahrzeit, aufgerundet."""
    return -((-run * pct) // 100)


def event_ids(inst: Instance) -> dict:
    """Ereignisschlüssel (Linie, "dep"|"arr", "f"|"b", Halt-Position) -> Index, in Fahrtreihenfolge je Linie."""
    ids: dict = {}

    def ev(key):
        return ids.setdefault(key, len(ids))

    for li, line in enumerate(inst.lines):
        m = len(line.stops) - 1
        ev((li, "dep", "f", 0))
        for k in range(1, m + 1):
            ev((li, "arr", "f", k))
            if k < m:
                ev((li, "dep", "f", k))
        ev((li, "dep", "b", m))
        for k in range(m - 1, -1, -1):
            ev((li, "arr", "b", k))
            if k > 0:
                ev((li, "dep", "b", k))
    return ids


def event_labels(inst: Instance) -> list:
    """Kurzbezeichnung je Ereignis, z. B. „L3 Hin · Halt 7 an“ (Linie, Richtung, Haltestellennummer, an/ab)."""
    ids = event_ids(inst)
    out = [""] * len(ids)
    for (li, art, d, k), e in ids.items():
        stop = inst.lines[li].stops[k]
        out[e] = f"L{li + 1} {'Hin' if d == 'f' else 'Rück'} · Halt {stop} {'an' if art == 'arr' else 'ab'}"
    return out


def event_line(inst: Instance) -> list:
    """Liniennummer (ab 0) je Ereignis."""
    ids = event_ids(inst)
    out = [0] * len(ids)
    for (li, _a, _d, _k), e in ids.items():
        out[e] = li
    return out


def chosen_transfers(inst: Instance, s: Settings) -> list:
    """Verlangte Anschlüsse: nach Nachfrage absteigend (Gleichstand: Schlüsselreihenfolge), die ersten k; „gerichtet“: nur kleine -> große Liniennummer."""
    keys = [k for k in inst.transfers if not (s.transfers == "gerichtet" and k[0] > k[3])]
    keys.sort(key=lambda k: (-inst.transfers[k], k))
    return keys if s.k_transfers is None else keys[:s.k_transfers]


def build_arcs(inst: Instance, s: Settings):
    """(Zahl der Ereignisse, Liste der Bögen). Die Reihenfolge der Bögen ist fest: Fahrt/Halt/Wende je Linie, dann die Anschlüsse in
    der Reihenfolge von `chosen_transfers`, dann die Zugfolge-Bögen."""
    ids = event_ids(inst)
    arcs: list = []
    tmin = inst.tmin
    for li, line in enumerate(inst.lines):
        m = len(line.stops) - 1
        for k in range(1, m + 1):
            r = line.run[k - 1]
            arcs.append(Arc(ids[(li, "dep", "f", k - 1)], ids[(li, "arr", "f", k)], r, r + reserve(r, s.reserve_pct), KIND_RUN))
            if k < m:
                arcs.append(Arc(ids[(li, "arr", "f", k)], ids[(li, "dep", "f", k)], s.dwell_lo, s.dwell_hi, KIND_DWELL))
        hi = None if s.turn_extra is None else tmin + s.turn_extra
        arcs.append(Arc(ids[(li, "arr", "f", m)], ids[(li, "dep", "b", m)], tmin, hi, KIND_TURN))
        for k in range(m - 1, -1, -1):
            r = line.run[k]
            arcs.append(Arc(ids[(li, "dep", "b", k + 1)], ids[(li, "arr", "b", k)], r, r + reserve(r, s.reserve_pct), KIND_RUN))
            if k > 0:
                arcs.append(Arc(ids[(li, "arr", "b", k)], ids[(li, "dep", "b", k)], s.dwell_lo, s.dwell_hi, KIND_DWELL))
    for (la, da, ka, lb, db, kb) in chosen_transfers(inst, s):
        hi = None if s.wait_max is None else s.transfer_min + s.wait_max
        arcs.append(Arc(ids[(la, "arr", da, ka)], ids[(lb, "dep", db, kb)], s.transfer_min, hi, KIND_TRANSFER))
    if s.headway > 0:
        for (la, ea), (lb, eb) in shared_segments(inst):
            a = ids[(la, ea[0], ea[1], ea[2])]
            b = ids[(lb, eb[0], eb[1], eb[2])]
            if la > lb:
                a, b = b, a
            arcs.append(Arc(a, b, s.headway, None, KIND_HEADWAY))
    return len(ids), arcs


def headway_pairs(inst: Instance) -> list:
    """Abschnittspaare mit gemeinsamem Abschnitt als Ereignis-Indizes (a, b), beide Abfahrten; Reihenfolge nach Liniennummer (a gehört zur kleineren)."""
    ids = event_ids(inst)
    out = []
    for (la, ea), (lb, eb) in shared_segments(inst):
        a = ids[(la, ea[0], ea[1], ea[2])]
        b = ids[(lb, eb[0], eb[1], eb[2])]
        out.append((a, b) if la < lb else (b, a))
    return out


def transfer_arc_index(arcs: list) -> list:
    """Indizes der Anschluss-Bögen in `arcs`, in der Reihenfolge von `chosen_transfers`."""
    return [i for i, a in enumerate(arcs) if a.kind == KIND_TRANSFER]


def without_upper_bounds(arcs: list) -> list:
    """Dieselben Bögen ohne jeden Höchstabstand (die klassische Rechnung des kritischen Pfades, CPM)."""
    return [Arc(a.u, a.v, a.lo, None, a.kind) for a in arcs]
