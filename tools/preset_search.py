"""Sucht die Seeds der Presets (Abstimmung der Szenarien, nicht Teil der Messreihen).

Aufruf (aus dem Repo-Ordner): python tools/preset_search.py <Suche> ...     mit Suche = standard | zeitkreis | eng | wende | zug | takt
Jede Suche zählt Kandidaten-Seeds unter 3000 (die Messreihen nutzen 3000 und darüber), bei denen das Preset die Aussage zeigt, die sein Hilfetext macht:
  standard   möglich, mit mindestens zwei Ereignissen, die nur wegen eines Höchstabstands kritisch sind
  zeitkreis  alle Anschlüsse beider Richtungen, k = 2, Höchstwartezeit unbegrenzt: unmöglich, der Kreis hat keinen Höchstabstand
  eng        gerichtet, k = 4: bei W = 30 möglich, bei W = 5 unmöglich
  wende      wie Standard möglich, aber mit Höchstwende 5 unmöglich, der Kreis enthält eine Wende
  zug        alle, k = 4, W unbegrenzt: ohne Zugfolge möglich, mit 4 min bei fester Reihenfolge unmöglich, bei freier Reihenfolge möglich
  takt       alle, k = 8, W = 10: einmalig unmöglich, periodisch (T = 60) möglich
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zab_bridge as B  # noqa: E402
import zab_evaluation as ev  # noqa: E402
import zab_graph as G  # noqa: E402
import zab_model as M  # noqa: E402
import zab_schedule as S  # noqa: E402
from zab_model import Settings  # noqa: E402

LIMIT = 2990


def info(lines, seed, **kw):
    return ev.analyse(lines, seed, Settings(**kw))


def standard():
    out = []
    for seed in range(480, 700):
        a = info(6, seed, transfers="gerichtet", k_transfers=4, wait_max=30)
        if a.feasible and len(a.only_by_upper) >= 2:
            out.append((seed, a.schedule.end, len(S.critical(a.schedule.slack)), len(a.only_by_upper)))
    print("standard (Seed, Ende, kritisch, nur durch Höchstabstand)", out[:8])


def zeitkreis():
    out = []
    for seed in range(0, 400):
        a = info(6, seed, transfers="alle", k_transfers=2, wait_max=None)
        if not a.feasible and a.excess["hi_count"] == 0 and a.excess["length"] < 40:
            out.append((seed, a.excess["excess"], a.excess["length"]))
    print("zeitkreis (Seed, Überschuss, Kanten)", out[:8])


def eng():
    out = []
    for seed in range(0, 600):
        a = info(6, seed, transfers="gerichtet", k_transfers=4, wait_max=5)
        if not a.feasible and info(6, seed, transfers="gerichtet", k_transfers=4, wait_max=30).feasible:
            out.append((seed, a.excess["hi_count"], a.excess["excess"], a.excess["length"]))
    print("eng (Seed, Höchstabstände im Kreis, Überschuss, Kanten)", out[:10])


def wende():
    out = []
    for seed in range(0, 600):
        a = info(6, seed, transfers="gerichtet", k_transfers=4, wait_max=30, turn_extra=5)
        if not a.feasible and info(6, seed, transfers="gerichtet", k_transfers=4, wait_max=30).feasible:
            kinds = sorted({a.arcs[e[3][0]].kind for e in a.witness})
            if "turn" in kinds:
                out.append((seed, a.excess["hi_count"], a.excess["excess"], kinds))
    print("wende (Seed, Höchstabstände, Überschuss, Bogenarten)", out[:10])


def zug():
    out = []
    for seed in range(0, 300):
        inst = ev.build_valid_instance(6, seed)[0]
        s0 = Settings(transfers="alle", k_transfers=4, wait_max=None)
        s = Settings(transfers="alle", k_transfers=4, wait_max=None, headway=4)
        if not G.is_feasible(*M.build_arcs(inst, s0)) or G.is_feasible(*M.build_arcs(inst, s)):
            continue
        free, pairs = B.free_order_feasible(inst, s, limit=10.0, workers=1)
        if free:
            out.append((seed, pairs))
    print("zug (Seed, Abschnittspaare)", out[:10])


def takt():
    out = []
    for seed in range(0, 300):
        a = info(6, seed, transfers="alle", k_transfers=8, wait_max=10)
        if not a.feasible:
            ok, _ph, xs = B.periodic_solution(a.n, list(a.arcs), 60, limit=10.0)
            if ok:
                out.append((seed, a.excess["hi_count"], a.excess["excess"], B.cycle_sum_of_x(list(a.witness), xs)))
    print("takt (Seed, Höchstabstände, Überschuss, Summe der Abstände im Kreis)", out[:10])


if __name__ == "__main__":
    for name in sys.argv[1:]:
        globals()[name]()
