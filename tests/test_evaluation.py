"""Analyse eines Plans (möglich und unmöglich) und Zusammenfassungen der Messdateien an handgesetzten Zeilen."""

import pytest

import zab_evaluation as ev
import zab_schedule as S
from zab_model import Settings


def test_analysis_of_a_possible_plan_is_consistent():
    a = ev.analyse(6, 501, Settings(transfers="gerichtet", k_transfers=4, wait_max=30))
    assert a.feasible and a.witness is None and a.excess is None
    assert len(a.transfer_keys) == 4 and a.n == len(a.labels) == len(a.event_line) == len(a.schedule.earliest) == 120
    assert min(a.schedule.slack) == 0 and a.schedule.end == max(a.schedule.earliest)
    assert set(a.only_by_upper) <= set(S.critical(a.schedule.slack)) and not set(a.only_by_upper) & set(a.cpm_critical)
    assert set(S.critical(a.schedule.slack)) - set(a.cpm_critical) == set(a.only_by_upper)       # kritisch mit Höchstabständen, nicht klassisch


def test_analysis_of_a_time_cycle_does_not_need_the_classical_rule():
    """Ein Zeitkreis bleibt auch ohne Höchstabstände unmöglich: die klassische Rechnung entfällt, die Analyse bricht nicht ab (Regressionstest)."""
    a = ev.analyse(6, 501, Settings(transfers="alle", k_transfers=None, wait_max=None))
    assert not a.feasible and a.schedule is None and a.cpm_critical == () and a.only_by_upper == ()
    assert a.excess["excess"] > 0 and a.excess["hi_count"] == 0 and a.excess["length"] == len(a.witness)


def test_analysis_reports_the_seed_actually_used():
    a = ev.analyse(3, 0, Settings())
    assert 0 <= a.used_seed < 50 and a.seed == 0


def test_find_records_and_e1_curve_order():
    recs = [{"nl": 6, "mode": "alle", "k": k, "W": None, "feasible": [c] * 4, "n": 10} for k, c in ((None, 0), (4, 5), (1, 10), (2, 8))]
    recs.append({"nl": 6, "mode": "gerichtet", "k": 1, "W": None, "feasible": [1] * 4, "n": 10})
    curve = ev.e1_curve(recs, 6, "alle", None)
    assert [c[0] for c in curve] == [1, 2, 4, None] and [c[1] for c in curve] == [1.0, 0.8, 0.5, 0.0]
    assert ev.e1_curve(recs, 6, "alle", 30) == []


def test_regler_curve_labels_unlimited_and_keeps_order():
    recs = [{"mode": "alle", "k": 4, "W": None, "regler": "turn_extra", "wert": v, "feasible": [c] * 4, "n": 100} for v, c in ((None, 60), (60, 50), (0, 20))]
    assert ev.regler_curve(recs, "alle", 4, None, "turn_extra") == [("unbegrenzt", 0.6, 0.0), ("60", 0.5, 0.0), ("0", 0.2, 0.0)]


def test_e5_rows_sort_by_unlimited_first_then_descending_wait():
    recs = [{"mode": "alle", "k": 4, "W": w, "n": 60, "einmalig": [10] * 4, "periodisch": [60] * 4, "einmalig_nicht_periodisch": 0,
             "einmalig_nein_periodisch_ja": 5, "periodisch_unbekannt": 0} for w in (10, None, 30, 0)]
    rows = ev.e5_pa_rows(recs, "alle", 4)
    assert [r["W"] for r in rows] == [None, 30, 10, 0] and rows[0]["von"] == 240 and rows[0]["einmalig"][0] == pytest.approx(10 / 60)


def test_e4_rows_are_sorted_by_headway():
    recs = [{"mode": "alle", "k": 4, "W": None, "h": h, "n": 60, "fest": [30] * 4, "frei": [40] * 4, "unbekannt": 0, "abschnittspaare_mittel": 16.8} for h in (10, 0, 4)]
    assert [r[0] for r in ev.e4_rows(recs, "alle", 4, None)] == [0, 4, 10]


def _e1(nl, c):
    return {"nl": nl, "mode": "alle", "k": None, "W": None, "feasible": [c] * 4, "n": 250}


def test_sentence_all_transfers_names_zero_counts_and_the_exception():
    text = ev.sentence_all_transfers([_e1(3, 3), _e1(5, 0), _e1(6, 0), _e1(8, 0), _e1(10, 0), {**_e1(6, 7), "W": 30}])
    assert text == ("Mit allen Anschlüssen beider Richtungen und ohne Höchstwartezeit war ein einmaliger Plan bei 5, 6, 8 und 10 Linien in 0 von je 1000 Netzen, "
                    "bei 3 Linien in 12 von 1000 möglich (Experiment 1).")
    assert "bei 5 Linien in 0 von 1000 Netzen möglich" in ev.sentence_all_transfers([_e1(5, 0)])


def test_free_vs_fixed_counts_ignore_the_cells_without_headway():
    recs = [{"h": 0, "fest": [5] * 4, "frei": [5] * 4}, {"h": 2, "fest": [3] * 4, "frei": [5] * 4}, {"h": 4, "fest": [5] * 4, "frei": [5] * 4},
            {"h": 10, "fest": [5, 5, 5, 6], "frei": [5, 5, 5, 5]}]
    assert ev.free_vs_fixed_counts(recs) == (3, 2, 1)
    assert "in 2 von 3 gemessenen Zellen" in ev.sentence_free_order(recs) and "in 1 höher" in ev.sentence_free_order(recs)
