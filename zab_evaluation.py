"""Auswertung: die Analyse eines Plans (möglich oder unmöglich), Verdikte als reine Funktionen und Zusammenfassungen der vorgerechneten Messreihen.

Verdikte sind `verdict_*(...) -> (Art, Text)`; die App ruft `getattr(st, Art)(Text)`, `tests/test_verdicts.py` prüft Schwellen und jede Zahl im Text an
handgesetzten Werten. Messreihen werden als Zähler je Block gespeichert (`zab_sweeps`); hier wird daraus Mittel ± Standardabweichung über die Blöcke.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

import zab_constants as C
import zab_graph as G
import zab_model as M
import zab_schedule as S
from zab_model import Settings
from zab_network import Instance, build_valid_instance


def de(x, digits=1):
    """Zahl mit Dezimalkomma."""
    return f"{x:.{digits}f}".replace(".", ",")


def k_value(label):
    """Auswahlstufe -> Zahl der verlangten Anschlüsse (None: alle)."""
    return None if label == C.K_ALL else int(label)


def w_value(label):
    """Auswahlstufe -> Höchstwartezeit über der Mindestzeit (None: unbegrenzt)."""
    return None if label == C.W_UNLIMITED else int(label)


def turn_value(label):
    return None if label == C.TURN_UNLIMITED else int(label)


def settings_from_widgets(mode, k, w, turn, reserve, dwell_hi, transfer_min, headway) -> Settings:
    """Aus den Reglerwerten (Auswahlstufen) die Einstellungen des Plans."""
    return Settings(reserve_pct=int(reserve), dwell_lo=C.DWELL_LO, dwell_hi=int(dwell_hi), turn_extra=turn_value(turn), transfer_min=int(transfer_min),
                    wait_max=w_value(w), headway=int(headway), transfers=mode, k_transfers=k_value(k))


@dataclass(frozen=True)
class Analysis:
    lines: int
    seed: int
    used_seed: int                 # der Seed, mit dem die Netzerzeugung tatsächlich ein gültiges Netz gefunden hat
    inst: Instance
    coords: tuple                  # Haltestellenkoordinaten ((x, y), ...)
    settings: Settings
    n: int                         # Zahl der Ereignisse
    arcs: tuple
    transfer_keys: tuple
    labels: tuple
    event_line: tuple
    schedule: Optional[S.Schedule]
    witness: Optional[tuple]       # Kreis positiver Länge (Kantenzug), wenn der Plan unmöglich ist
    excess: Optional[dict]
    cpm_critical: tuple            # kritische Ereignisse der klassischen Rechnung (ohne Höchstabstände)
    only_by_upper: tuple           # kritisch nur wegen eines Höchstabstands

    @property
    def feasible(self) -> bool:
        return self.schedule is not None


def analyse(lines: int, seed: int, settings: Settings) -> Analysis:
    inst, _demand, coords, used = build_valid_instance(lines, seed)
    n, arcs = M.build_arcs(inst, settings)
    sch, wit = S.schedule(n, arcs)
    cpm_crit, only = (), ()
    if sch is not None:         # die klassische Rechnung gibt es nur für einen möglichen Plan (ein Zeitkreis bleibt auch ohne Höchstabstände unmöglich)
        cpm_crit, _ = S.critical_cpm(n, arcs)
        only = tuple(sorted(set(S.critical(sch.slack)) - set(cpm_crit)))
    return Analysis(lines, seed, used, inst, tuple((int(x), int(y)) for x, y in coords), settings, n, tuple(arcs), tuple(M.chosen_transfers(inst, settings)),
                    tuple(M.event_labels(inst)), tuple(M.event_line(inst)), sch, tuple(wit) if wit is not None else None,
                    G.cycle_excess(wit) if wit is not None else None, tuple(cpm_crit), only)


# ------------------------------------------------------------------ Verdikte (rein)
def verdict_plan(feasible: bool, n_transfers: int, n_events: int, end: int = 0, n_critical: int = 0, n_only_upper: int = 0, excess: Optional[dict] = None):
    """Verdikt der Kernfrage „Ist der Plan möglich?“ als (Art, Text)."""
    if feasible:
        text = (f"Der Plan ist **möglich**: mit {n_transfers} verlangten Anschlüssen endet er frühestens nach **{end} min**. "
                f"{n_critical} von {n_events} Ereignissen haben keinen Spielraum (kritisch)")
        if n_only_upper:
            text += f", davon {n_only_upper} nur wegen eines Höchstabstands: die klassische Rechnung ohne Höchstabstände zeigt sie als unkritisch"
        return "success", text + "."
    ex = excess
    text = (f"Der Plan ist **unmöglich**: Ein Kreis aus {ex['length']} Abständen braucht mindestens **{ex['min_sum']} min**, erlaubt aber nur {ex['max_sum']} min "
            f"(Überschuss {ex['excess']} min). ")
    if ex["hi_count"] == 0:
        text += "Der Kreis enthält **keinen Höchstabstand**: Auch mit unbegrenzter Wartezeit und unbegrenzter Wende ließe sich dieser Kreis nicht lösen (Zeitkreis)."
    elif ex["hi_count"] == 1:
        text += f"Der Kreis enthält einen Höchstabstand; um mindestens {ex['excess']} min gelockert, wäre dieser Kreis aufgelöst (andere Kreise können bleiben)."
    else:
        text += (f"Der Kreis enthält {ex['hi_count']} Höchstabstände; zusammen um mindestens {ex['excess']} min gelockert, wäre dieser Kreis aufgelöst "
                 "(andere Kreise können bleiben).")
    return "error", text


# ------------------------------------------------------------------ Zusammenfassungen der Messreihen
def blocks_share(counts, n):
    """(Mittel, Standardabweichung) des Anteils über die Blöcke; counts = Zähler je Block, n = Netze je Block."""
    v = [c / n for c in counts]
    return statistics.fmean(v), statistics.pstdev(v)


def find_records(records, **conds):
    return [r for r in records if all(r.get(k) == v for k, v in conds.items())]


def e1_curve(records, nl, mode, w):
    """Anteil möglicher Pläne gegen k für feste Linienzahl, Richtung und Höchstwartezeit (w None = unbegrenzt): Liste (k, Mittel, Std); k None = alle."""
    rows = find_records(records, nl=nl, mode=mode, W=w)
    out = []
    for r in rows:
        m, sd = blocks_share(r["feasible"], r["n"])
        out.append((r["k"], m, sd))
    out.sort(key=lambda t: (t[0] is None, t[0] or 0))
    return out


def k_at_share(curve, level=0.5):
    """k, bei dem der Anteil möglicher Pläne (linear zwischen den gemessenen k) die Marke `level` unterschreitet; None, wenn er nie darunter fällt.
    Die Kurve wird nur über die endlichen k geführt (k = alle bleibt außen vor)."""
    pts = [(k, m) for k, m, _s in curve if k is not None]
    for (k0, m0), (k1, m1) in zip(pts, pts[1:]):
        if m0 >= level > m1:
            return k0 + (k1 - k0) * (m0 - level) / (m0 - m1)
    return pts[0][0] if pts and pts[0][1] < level else None


def verdict_e1(curve, nl: int, mode: str, w_label: str):
    """Verdikt Experiment 1 aus der Kurve (k, Mittel, Std); nennt k beim Anteil 0,5 und den Anteil mit allen Anschlüssen."""
    all_share = next((m for k, m, _s in curve if k is None), None)
    k50 = k_at_share(curve, 0.5)
    first = curve[0][1]
    parts = [f"Bei {nl} Linien, Richtung „{mode}“ und Höchstwartezeit {w_label} (über der Mindest-Umsteigezeit) sind {de(first * 100, 0)} % der Pläne mit dem am stärksten nachgefragten Umstieg möglich"]
    if k50 is not None:
        parts.append(f"der Anteil fällt bei etwa k = {de(k50, 1)} Anschlüssen unter 50 %")
    else:
        parts.append("der Anteil bleibt für alle gemessenen k bei 50 % oder darüber")
    if all_share is not None:
        parts.append(f"mit allen Anschlüssen sind {de(all_share * 100, 1)} % der Pläne möglich")
    return "info", "; ".join(parts) + "."


def e3_rows(records):
    """Zeilen für Experiment 3: Anteil kritischer Ereignisse voll und klassisch (Mittel über die Blöcke) und der Zuwachs in Prozentpunkten."""
    out = []
    for r in records:
        full, cpm, only = [], [], []
        for b in r["blocks"]:
            if b["events"]:
                full.append(b["krit_voll"] / b["events"])
                cpm.append(b["krit_cpm"] / b["events"])
                only.append(b["nur_hoechst"] / b["events"])
        out.append({"label": r["label"], "nl": r["nl"], "machbar": sum(b["machbar"] for b in r["blocks"]),
                    "voll": statistics.fmean(full) if full else None, "voll_std": statistics.pstdev(full) if full else None,
                    "cpm": statistics.fmean(cpm) if cpm else None, "nur_hoechst": statistics.fmean(only) if only else None,
                    "quantile": r["spielraum_quantile"], "einzige_linie": (r["plaene_mit_einer_kritischen_linie"] / r["plaene_machbar"]) if r["plaene_machbar"] else None,
                    "linien_mittel": r["linien_mit_kritischem_ereignis_mittel"]})
    return out


# ------------------------------------------------------------------ Experiment 2: Kreise und Regler
REGLER_LABELS = {"reserve_pct": "Fahrzeitreserve (% der Fahrzeit)", "turn_extra": "Höchstwende (min über der Mindest-Standzeit)",
                 "dwell_hi": "längste Haltezeit (min)", "transfer_min": "Mindest-Umsteigezeit (min)"}
ALPHA_MODE = {"alle": "alle (beide Richtungen)", "gerichtet": "gerichtet (kleine zu großer Liniennummer)"}


def value_label(v):
    return "unbegrenzt" if v is None else str(v)


def regler_curve(records, mode, k, w, regler):
    """Anteil möglicher Pläne über die Werte eines Reglers (die übrigen Regler auf Standard): Liste (Beschriftung, Mittel, Std) in der Reihenfolge der Messung."""
    out = []
    for r in find_records(records, mode=mode, k=k, W=w, regler=regler):
        m, sd = blocks_share(r["feasible"], r["n"])
        out.append((value_label(r["wert"]), m, sd))
    return out


def e2_cycle_rows(records):
    """Zeilen der Kreis-Zerlegung: unmögliche Pläne, davon schon ohne jeden Höchstabstand unmöglich (Zeitkreis) und erst durch Höchstabstände unmöglich."""
    return [{"label": r["label"], "von": r["von"], "unmoeglich": r["unmoeglich"], "zeitkreis": r["zeitkreis"], "nur_hoechst": r["nur_hoechstabstaende"],
             "anschluesse": r["anschluesse_im_kreis"], "rueckkanten_median": r["rueckkanten_median"]} for r in records]


def verdict_e2(row):
    """Verdikt Experiment 2 aus einer Zeile von `e2_cycle_rows`: wie viele der unmöglichen Pläne sind schon ohne jeden Höchstabstand unmöglich (Zeitkreis)."""
    if row["unmoeglich"] == 0:
        return "info", f"Bei „{row['label']}“ ist keiner der {row['von']} Pläne unmöglich."
    return "info", (f"Bei „{row['label']}“ sind {row['unmoeglich']} von {row['von']} Plänen unmöglich; {row['zeitkreis']} davon sind schon ohne jeden Höchstabstand "
                    f"unmöglich (Zeitkreis), {row['nur_hoechst']} werden erst durch Höchstabstände unmöglich.")


# ------------------------------------------------------------------ Experiment 4: Zugfolge fest gegen frei
def e4_rows(records, mode, k, w):
    """Je Mindestzugfolge h: Anteil möglicher Pläne bei fester und bei freier Reihenfolge (Mittel über die Blöcke): Liste (h, fest, frei, Paare)."""
    out = []
    for r in find_records(records, mode=mode, k=k, W=w):
        out.append((r["h"], blocks_share(r["fest"], r["n"])[0], blocks_share(r["frei"], r["n"])[0], r["abschnittspaare_mittel"], r["unbekannt"]))
    return sorted(out)


def _range_text(values):
    """„X %“ oder „X bis Y %“ aus den Anteilen (0 bis 1), auf eine Stelle."""
    lo, hi = de(min(values) * 100, 1), de(max(values) * 100, 1)
    return f"{lo} %" if lo == hi else f"{lo} bis {hi} %"


def verdict_e4(rows):
    """Verdikt Experiment 4: Anteil ohne Zugfolge (h = 0), dann mit h > 0 bei fester und bei freier Reihenfolge (Spanne über die gemessenen Minutenzahlen h)."""
    base = next(r for r in rows if r[0] == 0)
    pos = [r for r in rows if r[0] > 0]
    return "info", (f"Ohne Zugfolge sind {de(base[1] * 100, 1)} % der Pläne möglich. Mit Zugfolge (h = {', '.join(str(r[0]) for r in pos)} min) liegt der Anteil bei fester "
                    f"Reihenfolge bei {_range_text([r[1] for r in pos])}, bei freier Reihenfolge bei {_range_text([r[2] for r in pos])}.")


# ------------------------------------------------------------------ Experiment 5: einmalig gegen periodisch, haltbarer Anteil
def e5_pa_rows(records, mode, k):
    """Je Höchstwartezeit: Anteil einmalig und periodisch möglicher Pläne (Mittel, Std über die Blöcke) und die Zahl der nur periodisch möglichen Pläne."""
    out = []
    for r in find_records(records, mode=mode, k=k):
        out.append({"W": r["W"], "einmalig": blocks_share(r["einmalig"], r["n"]), "periodisch": blocks_share(r["periodisch"], r["n"]),
                    "nur_periodisch": r["einmalig_nein_periodisch_ja"], "verletzt": r["einmalig_nicht_periodisch"], "von": r["n"] * len(r["einmalig"]),
                    "unbekannt": r["periodisch_unbekannt"]})
    return sorted(out, key=lambda x: (0, 0) if x["W"] is None else (1, -x["W"]))      # unbegrenzt zuerst, dann absteigend


def verdict_e5(row):
    """Verdikt Experiment 5 aus einer Zeile von `e5_pa_rows`."""
    return "info", (f"Von {row['von']} Netzen sind einmalig {de(row['einmalig'][0] * 100, 1)} %, periodisch {de(row['periodisch'][0] * 100, 1)} % möglich; "
                    f"{row['nur_periodisch']} Netze sind nur periodisch möglich, {row['verletzt']} nur einmalig.")


def e5_rest_rows(records):
    """Zeilen für „größter haltbarer Nachfrageanteil“: k, W, exakt (Mittel ± Std), Greedy, periodisch alle haltbar (Zahl von n), Status."""
    out = []
    for r in records:
        total = r["n"] * len(r["exakt"])
        out.append({"k": r["k"], "W": r["W"], "exakt": (statistics.fmean(r["exakt"]), statistics.pstdev(r["exakt"])),
                    "greedy": (statistics.fmean(r["greedy"]), statistics.pstdev(r["greedy"])), "periodisch_alle": sum(r["periodisch_alle"]), "von": total,
                    "optimal": r["status"].get("OPTIMAL", 0), "limit_s": r.get("limit_s")})
    return out


# ------------------------------------------------------------------ Sätze der Grenzen-Tabelle aus den Messreihen
def all_transfers_counts(e1_records):
    """Richtung „alle“, alle Anschlüsse, keine Höchstwartezeit: je Linienzahl (Linien, mögliche Pläne, Netze), sortiert nach Linienzahl."""
    rows = find_records(e1_records, mode="alle", k=None, W=None)
    return sorted((r["nl"], sum(r["feasible"]), r["n"] * len(r["feasible"])) for r in rows)


def sentence_all_transfers(e1_records):
    """Satz über Pläne mit allen Anschlüssen beider Richtungen ohne Höchstwartezeit, mit Zählung und benannter Ausnahme."""
    rows = all_transfers_counts(e1_records)
    zero = [nl for nl, c, _t in rows if c == 0]
    some = [(nl, c, t) for nl, c, t in rows if c > 0]
    parts = []
    if zero:
        total = rows[0][2]
        parts.append(f"bei {', '.join(str(n) for n in zero[:-1])} und {zero[-1]} Linien in 0 von je {total} Netzen" if len(zero) > 1 else f"bei {zero[0]} Linien in 0 von {total} Netzen")
    parts += [f"bei {nl} Linien in {c} von {t}" for nl, c, t in some]
    return "Mit allen Anschlüssen beider Richtungen und ohne Höchstwartezeit war ein einmaliger Plan " + ", ".join(parts) + " möglich (Experiment 1)."


def free_vs_fixed_counts(e4_records):
    """Zellen mit Zugfolge h > 0: (Zahl der Zellen, davon freie Reihenfolge mindestens so gut wie feste, davon besser)."""
    cells = [r for r in e4_records if r["h"] > 0]
    ge = sum(1 for r in cells if sum(r["frei"]) >= sum(r["fest"]))
    gt = sum(1 for r in cells if sum(r["frei"]) > sum(r["fest"]))
    return len(cells), ge, gt


def sentence_free_order(e4_records):
    n, ge, gt = free_vs_fixed_counts(e4_records)
    return (f"Mit freier Reihenfolge lag die Zahl möglicher Pläne in {ge} von {n} gemessenen Zellen mit Zugfolge mindestens so hoch wie bei fester, in {gt} höher "
            "(Experiment 4); die Wahl der Reihenfolge ist ein Job-Shop-Problem.")
