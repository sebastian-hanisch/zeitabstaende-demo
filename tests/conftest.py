"""Gemeinsame Fixtures: die Mini-Instanzen, an denen jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b).

Handrechnungen (Ereignis-Indizes in Klammern):
(1) Kette a(0), b(1), c(2) mit b-a in [2, 4], c-b in [3, 5]: früheste Lagen 0, 2, 5, Gesamtende D = 5, späteste Lagen 0, 2, 5, Spielraum überall 0.
    Mit c-a <= 6 unverändert; mit c-a <= 4 hat der Kreis a->b->c->a die Länge 2 + 3 - 4 = +1: unmöglich.
(2) Raute s(0)->x(1) >= 4, x->e(3) >= 3, s->y(2) >= 2, y->e >= 2: früheste x = 4, y = 2, e = 7; Spielraum x = 0, y = 3.
    Mit x - y <= 1 wird y frühestens 3 und der Spielraum von y 2 (die klassische Rechnung meldet 3).
(2b) Raute, in der y nur wegen eines Höchstabstands kritisch ist: s->y >= 1, y->e >= 5, x - y <= 1: mit Höchstabstand y = 3, e = 8, y kritisch;
    ohne: y = 1, e = 7, Spielraum von y 1.
(3) Zeitkreis: Linie A fährt ab (0) und kommt nach >= 10 min zurück (1), ebenso B (2 -> 3); Anschlüsse A zurück -> B hin (1 -> 2) und B zurück -> A hin (3 -> 0)
    je >= 3: Kreis 10 + 3 + 10 + 3 = +26, unmöglich ohne jeden Höchstabstand.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from zab_model import Arc  # noqa: E402
from zab_network import Instance, Line  # noqa: E402


@pytest.fixture
def chain():
    return 3, [Arc(0, 1, 2, 4, "run"), Arc(1, 2, 3, 5, "run")]


@pytest.fixture
def diamond():
    return 4, [Arc(0, 1, 4, None, "run"), Arc(1, 3, 3, None, "run"), Arc(0, 2, 2, None, "run"), Arc(2, 3, 2, None, "run")]


@pytest.fixture
def diamond_hi():
    """Raute (2b): y ist nur wegen des Höchstabstands x - y <= 1 kritisch."""
    return 4, [Arc(0, 1, 4, None, "run"), Arc(1, 3, 3, None, "run"), Arc(0, 2, 1, None, "run"), Arc(2, 3, 5, None, "run"), Arc(2, 1, -100, 1, "turn")]


@pytest.fixture
def time_cycle():
    return 4, [Arc(0, 1, 10, None, "run"), Arc(2, 3, 10, None, "run"), Arc(1, 2, 3, None, "transfer"), Arc(3, 0, 3, None, "transfer")]


@pytest.fixture
def mini_net():
    """Zwei Linien. Linie 0: Halte 0-1-2, Fahrzeiten 5 und 7 (8 Ereignisse 0..7); Linie 1: Halte 1-2, Fahrzeit 4 (4 Ereignisse 8..11).
    Anschlüsse: Linie 0 an Halt 1 -> Linie 1 ab Halt 1 (Nachfrage 6) und Linie 1 an Halt 1 (Rück) -> Linie 0 ab Halt 1 (Rück) (Nachfrage 4)."""
    lines = [Line([0, 1, 2], [5, 7]), Line([1, 2], [4])]
    transfers = {(0, "f", 1, 1, "f", 0): 6.0, (1, "b", 0, 0, "b", 1): 4.0}
    return Instance(lines, transfers)
