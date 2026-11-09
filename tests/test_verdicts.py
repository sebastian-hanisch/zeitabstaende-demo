"""Verdikte an von Hand gesetzten Werten (DEMO-PLAYBOOK §12): jede Zahl im Text und jede Schwelle der Art steht hier.

Ein Verdikt ist eine reine Funktion (Art, Text) und bekommt Werte, nicht Seeds. Damit prüft der Test die Grenzen und jede genannte Zahl direkt."""

import pytest

import zab_evaluation as ev

CYCLE0 = {"min_sum": 26, "max_sum": 0, "excess": 26, "hi_count": 0, "length": 4}
CYCLE1 = {"min_sum": 30, "max_sum": 20, "excess": 10, "hi_count": 1, "length": 6}
CYCLE3 = {"min_sum": 41, "max_sum": 36, "excess": 5, "hi_count": 3, "length": 9}


def test_decimal_comma():
    assert ev.de(3.14159, 2) == "3,14" and ev.de(7.0, 0) == "7" and ev.de(61.7, 1) == "61,7"


def test_plan_possible_names_transfers_end_critical_and_events():
    kind, text = ev.verdict_plan(True, 5, 120, end=203, n_critical=24, n_only_upper=0)
    assert kind == "success"
    assert "mit 5 verlangten Anschlüssen" in text and "**203 min**" in text and "24 von 120 Ereignissen" in text and "nur wegen" not in text


def test_plan_possible_mentions_events_critical_only_by_upper_bounds():
    kind, text = ev.verdict_plan(True, 4, 80, end=150, n_critical=21, n_only_upper=3)
    assert kind == "success" and "davon 3 nur wegen eines Höchstabstands" in text and "klassische Rechnung" in text


def test_plan_impossible_without_upper_bound_is_a_time_cycle():
    kind, text = ev.verdict_plan(False, 2, 40, excess=CYCLE0)
    assert kind == "error"
    assert "Kreis aus 4 Abständen" in text and "**26 min**" in text and "nur 0 min" in text and "Überschuss 26 min" in text
    assert "keinen Höchstabstand" in text and "Zeitkreis" in text


def test_plan_impossible_with_one_upper_bound_gives_the_loosening():
    kind, text = ev.verdict_plan(False, 4, 40, excess=CYCLE1)
    assert kind == "error" and "Kreis aus 6 Abständen" in text and "**30 min**" in text and "nur 20 min" in text
    assert "einen Höchstabstand; um mindestens 10 min gelockert" in text and "Zeitkreis" not in text


def test_plan_impossible_with_several_upper_bounds():
    kind, text = ev.verdict_plan(False, 4, 40, excess=CYCLE3)
    assert kind == "error" and "3 Höchstabstände; zusammen um mindestens 5 min gelockert" in text


CURVE = [(1, 1.0, 0.0), (2, 0.8, 0.02), (4, 0.4, 0.05), (None, 0.0, 0.0)]


def test_k_at_share_interpolates_between_measured_k():
    assert ev.k_at_share(CURVE, 0.5) == pytest.approx(2 + 2 * (0.8 - 0.5) / (0.8 - 0.4))      # 3,5
    assert ev.k_at_share(CURVE, 0.9) == pytest.approx(1 + 1 * (1.0 - 0.9) / (1.0 - 0.8))      # 1,5


def test_k_at_share_edge_cases():
    assert ev.k_at_share([(1, 0.3, 0.0), (2, 0.2, 0.0)], 0.5) == 1                           # schon bei k = 1 unter der Marke
    assert ev.k_at_share([(1, 0.9, 0.0), (2, 0.8, 0.0), (None, 0.0, 0.0)], 0.5) is None      # k = alle zählt nicht für die Interpolation
    assert ev.k_at_share([], 0.5) is None


def test_verdict_e1_names_first_share_k_and_share_with_all_transfers():
    kind, text = ev.verdict_e1(CURVE, 6, "gerichtet", "30 min")
    assert kind == "info"
    assert "Bei 6 Linien, Richtung „gerichtet“ und Höchstwartezeit 30 min (über der Mindest-Umsteigezeit)" in text and "100 % der Pläne mit dem am stärksten nachgefragten Umstieg" in text
    assert "bei etwa k = 3,5 Anschlüssen unter 50 %" in text and "mit allen Anschlüssen sind 0,0 % der Pläne möglich" in text


def test_verdict_e1_when_the_share_never_drops():
    _kind, text = ev.verdict_e1([(1, 1.0, 0.0), (2, 0.9, 0.0)], 3, "alle", "unbegrenzt")
    assert "bleibt für alle gemessenen k bei 50 % oder darüber" in text and "mit allen Anschlüssen" not in text


def test_blocks_share_mean_and_std():
    m, sd = ev.blocks_share([50, 100, 150, 200], 250)
    assert m == pytest.approx((0.2 + 0.4 + 0.6 + 0.8) / 4) and sd == pytest.approx(0.2236067977, abs=1e-9)


def test_verdict_e2_counts_time_cycles():
    row = {"label": "alle, k = 4", "von": 240, "unmoeglich": 191, "zeitkreis": 108, "nur_hoechst": 83, "anschluesse": {}, "rueckkanten_median": 0}
    kind, text = ev.verdict_e2(row)
    assert kind == "info" and "191 von 240 Plänen unmöglich" in text and "108 davon sind schon ohne jeden Höchstabstand unmöglich (Zeitkreis)" in text
    assert "83 werden erst durch Höchstabstände unmöglich" in text and "Löschfilter" not in text
    assert "keiner der 240" in ev.verdict_e2({**row, "unmoeglich": 0, "zeitkreis": 0, "nur_hoechst": 0})[1]


def test_verdict_e4_gives_fixed_and_free_ranges():
    rows = [(0, 0.55, 0.55, 16.8, 0), (2, 0.35, 0.55, 16.8, 0), (4, 0.35, 0.55, 16.8, 0), (10, 0.34, 0.55, 16.8, 0)]
    kind, text = ev.verdict_e4(rows)
    assert kind == "info"
    assert "Ohne Zugfolge sind 55,0 % der Pläne möglich" in text and "(h = 2, 4, 10 min)" in text
    assert "fester Reihenfolge bei 34,0 bis 35,0 %" in text and "freier Reihenfolge bei 55,0 %" in text


def test_verdict_e5_counts_once_periodic_and_only_periodic():
    row = {"W": None, "einmalig": (0.55, 0.02), "periodisch": (1.0, 0.0), "nur_periodisch": 108, "verletzt": 0, "von": 240, "unbekannt": 0}
    kind, text = ev.verdict_e5(row)
    assert kind == "info"
    assert "Von 240 Netzen sind einmalig 55,0 %, periodisch 100,0 % möglich" in text and "108 Netze sind nur periodisch möglich, 0 nur einmalig" in text


def test_e3_rows_pools_the_blocks():
    rec = [{"label": "x", "nl": 6, "settings": {}, "blocks": [{"machbar": 10, "events": 100, "krit_voll": 30, "krit_cpm": 25, "nur_hoechst": 5},
                                                              {"machbar": 12, "events": 200, "krit_voll": 50, "krit_cpm": 50, "nur_hoechst": 0}],
            "spielraum_quantile": [0, 0, 0, 13, 35, 68, 182], "linien_mit_kritischem_ereignis_mittel": 1.5, "plaene_mit_einer_kritischen_linie": 11, "plaene_machbar": 22}]
    (row,) = ev.e3_rows(rec)
    assert row["machbar"] == 22 and row["voll"] == pytest.approx((0.30 + 0.25) / 2) and row["cpm"] == pytest.approx((0.25 + 0.25) / 2)
    assert row["nur_hoechst"] == pytest.approx((0.05 + 0.0) / 2) and row["einzige_linie"] == 0.5 and row["quantile"][3] == 13


def test_settings_from_widgets_maps_the_labels():
    s = ev.settings_from_widgets("alle", "alle", "unbegrenzt", "unbegrenzt", 25, 10, 8, 4)
    assert s.k_transfers is None and s.wait_max is None and s.turn_extra is None
    assert (s.reserve_pct, s.dwell_hi, s.transfer_min, s.headway, s.transfers, s.dwell_lo) == (25, 10, 8, 4, "alle", 1)
    t = ev.settings_from_widgets("gerichtet", 4, 30, 5, 0, 3, 3, 0)
    assert (t.k_transfers, t.wait_max, t.turn_extra) == (4, 30, 5)
