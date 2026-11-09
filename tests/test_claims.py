"""Jede Zahl und jede Aussage der README und der App-Hilfetexte, hier nachgerechnet (DEMO-PLAYBOOK §4 und §11a).

Die Messreihen liegen vorgerechnet in data/zab_results.json (tools/sweep.py, vier Blöcke zu je 250 Netzen; Zugfolge, Takt und Löschfilter vier Blöcke zu je 60 Netzen,
„größter haltbarer Anteil“ je 40 bzw. 10). Hier: (1) die Datei gehört zum Rechenkern, (2) die Zellen, die in der README stehen, werden mit dem Kern neu gerechnet und
stimmen mit der Datei überein, (3) jede README-Zahl wird aus der Datei gelesen und mit der README verglichen, (4) Zweig-Tests (Nullspalten-Regel), (5) die Presets.
"""
import math
import re
import statistics
from pathlib import Path

import pytest

import zab_bridge as B
import zab_constants as C
import zab_evaluation as ev
import zab_graph as G
import zab_model as M
import zab_schedule as S
import zab_sweeps as SW
from zab_model import Settings
from zab_network import make_instance

ROOT = Path(__file__).resolve().parent.parent
R = SW.load_results()
README = (ROOT / "README.md").read_text(encoding="utf-8")
SECTIONS = ("e1", "e2_cycles", "e2_regler", "e3", "e4", "e5_pa", "e5_rest")


def de(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def share(counts, n):
    return ev.blocks_share(counts, n)


def rec(section, **conds):
    rows = ev.find_records(R[section], **conds)
    assert len(rows) == 1, (section, conds, len(rows))
    return rows[0]


def nets(nl, per_block, block=None):
    blocks = SW.block_instances(nl, per_block)
    return blocks if block is None else blocks[block]


# ------------------------------------------------------------------ (1) die Datei gehört zum Kern
def test_results_file_belongs_to_the_current_code():
    assert R, "data/zab_results.json fehlt (python tools/sweep.py <Abschnitt>, dann merge)"
    meta = R["meta"]
    assert meta["hash"] == SW.generator_hash(), "der Rechenkern hat sich geändert: Messreihen neu rechnen (tools/sweep.py)"
    assert (meta["blocks"], meta["per_block"], meta["base_seed"], meta["seed_step"], meta["small_per_block"], meta["rest_per_block"], meta["T"]) == (4, 250, 3000, 100, 60, 40, 60)
    assert all(s in R and R[s] for s in SECTIONS)


def test_every_record_has_four_blocks():
    for rec_ in R["e1"] + R["e2_regler"]:
        assert len(rec_["feasible"]) == 4 and rec_["n"] == 250 and all(0 <= c <= 250 for c in rec_["feasible"])
    for rec_ in R["e4"] + R["e5_pa"]:
        assert rec_["n"] == 60 and all(len(rec_[k]) == 4 for k in (("fest", "frei") if "fest" in rec_ else ("einmalig", "periodisch")))
    for rec_ in R["e3"]:
        assert len(rec_["blocks"]) == 4


def test_generator_yields_1000_distinct_nets_per_line_count():
    """Die Messnetze eines Blocks und über die vier Blöcke sind verschieden (Seed-Abstand 100 gegen die Seed-Suche bis +49)."""
    for nl in (3, 6, 10):
        used = [make_instance(nl, SW.net_seed(i))[1] for i in range(1000)]
        assert len(set(used)) == 1000
        assert all(SW.net_seed(i) <= used[i] < SW.net_seed(i) + 50 for i in range(1000))


# ------------------------------------------------------------------ (2) Neu-Rechnung der README-Zellen
@pytest.mark.parametrize("nl,mode,k,w", [(6, "gerichtet", 4, 30), (6, "alle", 4, None), (6, "alle", None, None), (3, "alle", None, None), (6, "alle", 2, 10), (10, "gerichtet", 4, 30)])
def test_e1_cells_recompute_exactly(nl, mode, k, w):
    stored = rec("e1", nl=nl, mode=mode, k=k, W=w)["feasible"]
    assert SW.feasible_counts(nets(nl, 250), Settings(transfers=mode, k_transfers=k, wait_max=w)) == stored


def test_e2_impossible_counts_recompute():
    blocks = nets(6, 60)
    for row in R["e2_cycles"]:
        s = Settings(**row["settings"])
        assert row["von"] - sum(SW.feasible_counts(blocks, s)) == row["unmoeglich"] == row["zeitkreis"] + row["nur_hoechstabstaende"], row["label"]


def test_e2_classification_matches_the_kernel_on_a_sample():
    """Ohne Höchstwartezeit ist jeder unmögliche Plan ein Zeitkreis-Plan, die gefundene Menge enthält dann keinen Höchstabstand. Stichprobe: 12 Netze der ersten Zelle, dazu die Zahl der Anschlüsse im Kreis."""
    import zab_witness as W
    s = Settings(transfers="alle", k_transfers=4, wait_max=None)
    seen = 0
    for inst in nets(6, 60, 0)[:12]:
        n, arcs = M.build_arcs(inst, s)
        info = W.explain_infeasible(n, arcs)
        if info is not None:
            assert info["time_cycle"] and info["hi"] == 0 and info["iis"] == len(info["keep"])
            assert info["transfer"] in (2, 4)
            seen += 1
    assert seen >= 3


def test_e3_first_block_recomputes():
    row = rec("e3", label="gerichtet, k = 4, W = 30", nl=6)
    s = Settings(**row["settings"])
    feas = crit = cpm = only = events = 0
    for inst in nets(6, 250, 0):
        n, arcs = M.build_arcs(inst, s)
        full, _ = S.schedule(n, arcs)
        if full is None:
            continue
        cc, _sch = S.critical_cpm(n, arcs)
        feas += 1
        events += n
        crit += len(S.critical(full.slack))
        cpm += len(cc)
        only += len(set(S.critical(full.slack)) - set(cc))
    assert row["blocks"][0] == {"machbar": feas, "events": events, "krit_voll": crit, "krit_cpm": cpm, "nur_hoechst": only}


def test_e4_fixed_and_free_recompute():
    blocks = nets(6, 60)
    row = rec("e4", mode="alle", k=4, W=None, h=4)
    s = Settings(transfers="alle", k_transfers=4, wait_max=None, headway=4)
    assert SW.feasible_counts(blocks, s) == row["fest"]
    free = sum(B.free_order_feasible(inst, s, limit=10.0, workers=1)[0] is True for inst in blocks[0])
    assert free == row["frei"][0]


def test_e5_once_and_periodic_recompute():
    blocks = nets(6, 60)
    for mode, k, w in (("alle", 4, 10), ("gerichtet", 8, 30)):
        row = rec("e5_pa", mode=mode, k=k, W=w)
        s = Settings(transfers=mode, k_transfers=k, wait_max=w)
        assert SW.feasible_counts(blocks, s) == row["einmalig"]
        per = sum(B.periodic_feasible(*M.build_arcs(inst, s), C.T, limit=10.0, workers=1) is True for inst in blocks[0])
        assert per == row["periodisch"][0]


def test_e5_kept_weight_recomputes_on_the_first_block():
    blocks = nets(6, 40)
    for k, w in ((16, 30), (8, None)):
        row = rec("e5_rest", k=k, W=w)
        s = Settings(transfers="alle", k_transfers=k, wait_max=w)
        vals = [B.max_kept_weight(inst, s, limit=10.0, workers=1) for inst in blocks[0]]
        assert all(st == "OPTIMAL" for _, st in vals)
        assert statistics.fmean(v for v, _ in vals) == pytest.approx(row["exakt"][0])
        greedy = [B.greedy_kept_weight(inst, s) for inst in blocks[0]]
        assert statistics.fmean(greedy) == pytest.approx(row["greedy"][0])
        assert all(g <= v + 1e-9 for g, (v, _) in zip(greedy, vals))


# ------------------------------------------------------------------ (3) README-Zahlen aus der Datei
def readme_has(text):
    assert text in README, text


def test_readme_numbers_experiment_1():
    e1 = R["e1"]
    m = lambda nl, mode, k, w: share(rec("e1", nl=nl, mode=mode, k=k, W=w)["feasible"], 250)          # noqa: E731
    mean, std = m(6, "gerichtet", 4, 30)
    readme_has(f"{de(100 * mean)} % der Netze")                                                         # 55,6 % (gerichtet, k = 4, W = 30)
    mean, std = m(6, "alle", 4, None)
    readme_has(f"{de(100 * mean)} % ± {de(100 * std)}")                                                 # 61,7 % ± 3,2
    readme_has(ev.sentence_all_transfers(e1).replace(" (Experiment 1).", ""))
    for nl in (3, 6, 10):
        c = ev.e1_curve(e1, nl, "alle", 10)
        k9, k5, k1 = (ev.k_at_share(c, lv) for lv in (0.9, 0.5, 0.1))
        readme_has(f"{nl} Linien: {de(k9)} / {de(k5)} / {de(k1)}")
    c6 = {w: share(rec("e1", nl=6, mode="alle", k=4, W=w)["feasible"], 250)[0] for w in (None, 40, 30, 20, 15, 0)}
    readme_has(" → ".join(de(100 * c6[w]) for w in (None, 40, 30, 20, 15, 0)) + " %")                 # 61,7 → 45,7 → 35,9 → 28,2 → 26,3 → 23,8 %


def test_readme_numbers_experiment_2():
    for row in ev.e2_cycle_rows(R["e2_cycles"]):
        readme_has(f"| {row['label']} | {row['unmoeglich']} von {row['von']} | {row['zeitkreis']} | {row['nur_hoechst']} |")
    turn = [share(rec("e2_regler", mode="alle", k=4, W=None, regler="turn_extra", wert=v)["feasible"], 250)[0] for v in (None, 60, 30, 15, 5, 0)]
    readme_has(" / ".join(de(100 * x) for x in turn) + " %")                                           # 61,7 / 55,4 / 40,6 / 27,8 / 21,4 / 18,9 %
    g = lambda regler, v: share(rec("e2_regler", mode="gerichtet", k=4, W=15, regler=regler, wert=v)["feasible"], 250)[0]     # noqa: E731
    readme_has(f"{de(100 * g('reserve_pct', 0))} auf {de(100 * g('reserve_pct', 200))} %")
    readme_has(f"{de(100 * g('transfer_min', 0))} auf {de(100 * g('transfer_min', 12))} %")


def test_readme_numbers_experiment_3():
    rows = {(r["nl"], r["label"]): r for r in ev.e3_rows(R["e3"])}
    r = rows[(6, "gerichtet, k = 4, W = 30")]
    readme_has(f"{de(100 * r['voll'])} % ± {de(100 * r['voll_std'])}")
    readme_has(f"nur Mindestabstände {de(100 * r['cpm'])} %")
    readme_has(f"+{de(100 * r['nur_hoechst'])} Prozentpunkte")
    readme_has("Spielraum (Minuten, Quantile 0/10/25/50/75/90/100): " + "/".join(str(q) for q in r["quantile"]))
    r2 = rows[(6, "alle, k = 4, W unbegrenzt")]
    readme_has(f"+{de(100 * r2['nur_hoechst'])} Prozentpunkte")
    r10 = rows[(10, "gerichtet, k = 4, W = 30")]
    readme_has(f"10 Linien +{de(100 * r10['nur_hoechst'])}")


def test_readme_numbers_experiment_4():
    rows = ev.e4_rows(R["e4"], "alle", 4, None)
    readme_has(f"{de(100 * rows[0][1])} % ohne Zugfolge, {de(100 * rows[1][1])} % bei fester Reihenfolge, {de(100 * rows[1][2])} % bei freier")
    n, ge, gt = ev.free_vs_fixed_counts(R["e4"])
    readme_has(f"in {ge} von {n} Zellen")


def test_readme_numbers_experiment_5():
    pa = R["e5_pa"]
    total = sum(r["n"] * 4 for r in pa)
    once = sum(sum(r["einmalig"]) for r in pa)
    readme_has(f"{total} Vergleichen")
    readme_has(f"{once} einmalig")
    assert sum(r["einmalig_nicht_periodisch"] for r in pa) == 0 and sum(r["periodisch_unbekannt"] for r in pa) == 0
    r = rec("e5_pa", mode="alle", k=4, W=10)
    readme_has(f"{de(100 * share(r['einmalig'], 60)[0])} % gegen {de(100 * share(r['periodisch'], 60)[0])} %")
    assert r["einmalig_nein_periodisch_ja"] == 191
    readme_has("191 von 240")
    r = rec("e5_pa", mode="alle", k=None, W=30)
    readme_has(f"nur {de(100 * share(r['periodisch'], 60)[0])} %")


def test_readme_numbers_kept_weight():
    for row in ev.e5_rest_rows(R["e5_rest"]):
        k = "alle" if row["k"] is None else row["k"]
        w = "unbegrenzt" if row["W"] is None else row["W"]
        readme_has(f"| {k} | {w} | {pct_std(row['exakt'])} | {pct_std(row['greedy'])} | {row['periodisch_alle']} von {row['von']} | {row['optimal']} von {row['von']} |")


def pct_std(ms):
    return f"{de(100 * ms[0])} % ± {de(100 * ms[1])}"


def test_readme_testcount_and_oracle_numbers_are_stated():
    for text in ("2979", "3000", "0 Abweichungen", "600 Vergleiche"):
        readme_has(text)


# ------------------------------------------------------------------ (4) Zweig-Tests (Nullspalten-Regel)
def share_of(nl, mode, k, w):
    return share(rec("e1", nl=nl, mode=mode, k=k, W=w)["feasible"], 250)[0]


def test_the_directed_column_without_upper_bounds_is_one_everywhere():
    """Satz: „gerichtet“ ohne Höchstwartezeit hat keinen Kreis aus Mindestabständen (Zubringer nur von klein nach groß, die Rückkanten von Halt und Fahrzeit schließen
    allein keinen): Anteil 1,000 in allen 60 Zellen (5 Linienzahlen, 12 Werte von k); kein toter Zweig, sondern der Satz."""
    rows = [r for r in R["e1"] if r["mode"] == "gerichtet" and r["W"] is None]
    assert len(rows) == 5 * 12 and all(sum(r["feasible"]) == 1000 for r in rows)


def test_waiting_time_k_direction_and_turn_change_the_share():
    assert share_of(6, "alle", 4, None) != share_of(6, "alle", 4, 30) != share_of(6, "alle", 4, 0)
    assert share_of(6, "alle", 2, None) > share_of(6, "alle", 4, None) > share_of(6, "alle", 8, None)
    assert share_of(6, "gerichtet", 4, None) == 1.0 > share_of(6, "alle", 4, None)
    turn = [sum(rec("e2_regler", mode="alle", k=4, W=None, regler="turn_extra", wert=v)["feasible"]) for v in (None, 60, 30, 15, 5, 0)]
    assert turn == sorted(turn, reverse=True) and len(set(turn)) == 6


def test_reserve_dwell_and_transfer_min_are_without_effect_where_expected_and_effective_elsewhere():
    """Bei „alle“, k = 4, W unbegrenzt laufen die Kreise nicht über diese Rückkanten: gleiche Zahl in allen vier Blöcken, auch wenn die Bogengrenzen sich ändern.
    Bei „gerichtet“, k = 4, W = 15 wirken alle drei (mindestens ein Block ändert sich)."""
    for regler, values in (("reserve_pct", (0, 10, 25, 50, 100, 200)), ("dwell_hi", (1, 3, 10)), ("transfer_min", (0, 3, 8, 12))):
        cells = [rec("e2_regler", mode="alle", k=4, W=None, regler=regler, wert=v)["feasible"] for v in values]
        assert all(c == cells[0] for c in cells), regler
        cells = [rec("e2_regler", mode="gerichtet", k=4, W=15, regler=regler, wert=v)["feasible"] for v in values]
        assert any(c != cells[0] for c in cells), regler


def test_free_order_never_does_worse_than_the_fixed_order():
    """Feste Reihenfolge möglich => freie möglich (eine feste Wahl ist eine der freien Wahlen); über alle 15 Zellen mit Zugfolge, Block für Block."""
    cells = [r for r in R["e4"] if r["h"] > 0]
    assert len(cells) == 15
    assert all(all(fr >= fe for fr, fe in zip(r["frei"], r["fest"])) for r in cells) and all(r["unbekannt"] == 0 for r in R["e4"])


def headway_spread_and_jump():
    """Über die fünf Konfigurationen: größte Spanne des Anteils bei fester Reihenfolge zwischen h = 2, 4 und 10 min, kleinster Sprung von h = 0 auf h = 2 und größte
    Abweichung der freien Reihenfolge vom Anteil ohne Zugfolge, jeweils in Prozentpunkten (240 Netze je Zelle)."""
    spread, jump, free_dev = 0.0, 100.0, 0.0
    cfgs = {(r["mode"], r["k"], r["W"]) for r in R["e4"]}
    assert len(cfgs) == 5
    for mode, k, w in cfgs:
        row = {h: rec("e4", mode=mode, k=k, W=w, h=h) for h in (0, 2, 4, 10)}
        fest = [sum(row[h]["fest"]) for h in (2, 4, 10)]
        spread = max(spread, 100 * (max(fest) - min(fest)) / 240)
        jump = min(jump, 100 * (sum(row[0]["fest"]) - fest[0]) / 240)
        free_dev = max(free_dev, max(100 * abs(sum(row[0]["frei"]) - sum(row[h]["frei"])) / 240 for h in (2, 4, 10)))
    return spread, jump, free_dev


def test_the_headway_minutes_hardly_matter_but_the_order_does():
    """Bei fester Reihenfolge bricht der Anteil schon bei h = 2 min ein (kleinster Sprung 8,75 Punkte), h = 2 gegen 10 min ändert höchstens 3,33 Punkte; bei freier Reihenfolge
    liegt der Anteil höchstens 0,83 Punkte neben dem ohne Zugfolge. Je Konfiguration geprüft; die README nennt die Schranken gerundet (höchstens 3,4, mindestens 8,7,
    höchstens 0,9), also so, dass der gemessene Wert innerhalb der Schranke liegt."""
    spread, jump, free_dev = headway_spread_and_jump()
    assert spread <= 3.4 and jump >= 8.7 and free_dev <= 0.9
    up = lambda x: de(math.ceil(round(x * 10, 6)) / 10)          # noqa: E731  Obergrenze auf eine Stelle
    down = lambda x: de(math.floor(round(x * 10, 6)) / 10)       # noqa: E731  Untergrenze auf eine Stelle
    readme_has(f"höchstens {up(spread)} Prozentpunkte")
    readme_has(f"mindestens {down(jump)} Prozentpunkte")
    readme_has(f"höchstens {up(free_dev)} Prozentpunkte vom Anteil ohne Zugfolge")


def test_the_periodic_plan_loses_nothing_the_once_plan_has():
    """Satz: einmalig möglich => periodisch möglich; 0 Verletzungen in allen Zellen, und es gibt Netze, die nur periodisch möglich sind."""
    assert all(r["einmalig_nicht_periodisch"] == 0 and r["periodisch_unbekannt"] == 0 for r in R["e5_pa"])
    assert sum(r["einmalig_nein_periodisch_ja"] for r in R["e5_pa"]) > 1000


def test_even_the_period_does_not_save_every_plan():
    r = rec("e5_pa", mode="alle", k=None, W=30)
    assert sum(r["periodisch"]) < 0.2 * 240


# ------------------------------------------------------------------ (5) Presets: jede Aussage des Hilfetextes
def analysis(name, **override):
    p = {**C.PRESETS[name], **override}
    return ev.analyse(p["lines"], p["seed"], ev.settings_from_widgets(p["mode"], p["k"], p["w"], p["turn"], p["reserve"], p["dwell_hi"], p["transfer_min"], p["headway"]))


def test_preset_standard_is_possible_with_events_critical_only_by_upper_bounds():
    a = analysis("Standard")
    assert a.feasible and len(a.only_by_upper) >= 2 and len(a.transfer_keys) == 4


def test_preset_zeitkreis_is_impossible_without_any_upper_bound_in_the_cycle():
    a = analysis("Zeitkreis")
    assert not a.feasible and a.excess["hi_count"] == 0 and a.settings.wait_max is None and len(a.transfer_keys) == 2
    assert not analysis("Zeitkreis", turn=5).feasible                    # auch mit Höchstwende bleibt er unmöglich (der Zeitkreis hat keine Wende-Rückkante)


def test_preset_waiting_time_too_tight_is_impossible_but_possible_with_30_minutes():
    a = analysis("Höchstwartezeit zu eng")
    assert not a.feasible and a.excess["hi_count"] >= 1 and a.settings.wait_max == 5
    assert analysis("Höchstwartezeit zu eng", w=30).feasible


def test_preset_turn_limited_is_impossible_through_a_turn_and_possible_without_the_limit():
    a = analysis("Wende begrenzt")
    kinds = {a.arcs[e[3][0]].kind for e in a.witness}
    assert not a.feasible and "turn" in kinds and a.settings.turn_extra == 5
    assert analysis("Wende begrenzt", turn=C.TURN_UNLIMITED).feasible


def test_preset_headway_order_decides():
    a = analysis("Zugfolge: Reihenfolge entscheidet")
    assert not a.feasible and a.settings.headway == 4
    assert analysis("Zugfolge: Reihenfolge entscheidet", headway=0).feasible
    free, pairs = B.free_order_feasible(a.inst, a.settings, limit=10.0, workers=1)
    assert free is True and pairs > 0


def test_preset_to_the_period_is_once_impossible_and_periodic_possible():
    a = analysis("Zum Takt")
    assert not a.feasible
    ok, phases, xs = B.periodic_solution(a.n, list(a.arcs), C.T, limit=10.0, workers=1)
    assert ok is True and B.cycle_sum_of_x(list(a.witness), xs) % C.T == 0


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_every_preset_has_a_verdict_that_names_its_numbers(name):
    a = analysis(name)
    n_crit = len(S.critical(a.schedule.slack)) if a.feasible else 0
    kind, text = ev.verdict_plan(a.feasible, len(a.transfer_keys), a.n, a.schedule.end if a.feasible else 0, n_crit, len(a.only_by_upper), a.excess)
    assert kind == ("success" if a.feasible else "error")
    assert (f"{a.schedule.end} min" in text) if a.feasible else (f"**{a.excess['min_sum']} min**" in text and f"Überschuss {a.excess['excess']} min" in text)


def test_default_settings_are_the_ones_the_sweeps_used():
    """Die Messreihen fahren die übrigen Regler auf Standard; die Voreinstellungen der App sind dieselben (sonst gilt der Satz der Caption nicht)."""
    s = ev.settings_from_widgets(C.DEFAULT_MODE, C.DEFAULT_K, C.DEFAULT_W, C.DEFAULT_TURN, C.DEFAULT_RESERVE, C.DEFAULT_DWELL_HI, C.DEFAULT_TRANSFER_MIN, C.DEFAULT_HEADWAY)
    base = Settings()
    assert (s.reserve_pct, s.dwell_lo, s.dwell_hi, s.turn_extra, s.transfer_min, s.headway) == (base.reserve_pct, base.dwell_lo, base.dwell_hi, base.turn_extra, base.transfer_min, base.headway)


# ------------------------------------------------------------------ weitere Aussagen der README
def test_no_time_cycle_in_the_directed_direction_and_counts_in_the_text():
    rows = {r["label"]: r for r in ev.e2_cycle_rows(R["e2_cycles"])}
    g = [rows[k] for k in ("gerichtet, k = 4, W = 30", "gerichtet, k = 4, W = 10", "gerichtet, k = 8, W = 10")]
    assert all(r["zeitkreis"] == 0 and r["unmoeglich"] > 0 for r in g)
    readme_has(f"(0 von {g[0]['unmoeglich']}, {g[1]['unmoeglich']} und {g[2]['unmoeglich']} unmöglichen Plänen)")
    a, b = rows["alle, k = 4, W unbegrenzt"], rows["alle, k = 8, W unbegrenzt"]
    readme_has(f"(erste und dritte Zeile) sind alle unmöglichen Pläne ({a['unmoeglich']} bzw. {b['unmoeglich']}) schon ohne Höchstabstände unmöglich")
    w10 = [rows["alle, k = 4, W = 10"], rows["alle, k = 8, W = 10"]]
    assert w10[0]["zeitkreis"] == a["zeitkreis"] and w10[1]["zeitkreis"] == b["zeitkreis"]    # der Zeitkreis-Test kennt keine Höchstwartezeit: dieselbe Zahl wie ohne
    assert all(r["nur_hoechst"] > 0 and r["nur_hoechst"] + r["zeitkreis"] == r["unmoeglich"] for r in w10)
    readme_has(f"sind alle {a['unmoeglich']} unmöglichen Pläne schon ohne Höchstabstände unmöglich (Zeitkreis)")


def test_plans_impossible_without_any_upper_bound_match_the_readme():
    """Zeitkreis-Pläne = Pläne, die auch ohne alle Höchstabstände unmöglich sind (unabhängig von der Reihenfolge des Löschfilters). Ohne Höchstwartezeit sind das alle
    unmöglichen Pläne; mit Höchstwartezeit 10 min kommen Pläne hinzu, die erst durch Höchstabstände unmöglich werden (Zahlen der README)."""
    blocks = nets(6, 60)
    got = {}
    for row in R["e2_cycles"]:
        s = Settings(**row["settings"])
        time_cycle = sum(1 for blk in blocks for inst in blk if not G.is_feasible(*_arcs_without_upper(inst, s)))
        got[row["label"]] = (time_cycle, row["unmoeglich"] - time_cycle)
        assert (row["zeitkreis"], row["nur_hoechstabstaende"]) == got[row["label"]], row["label"]      # die gespeicherte Zerlegung = der unabhängige Test ohne Höchstabstände
    assert got["alle, k = 4, W unbegrenzt"] == (108, 0) and got["alle, k = 8, W unbegrenzt"] == (150, 0)
    assert got["alle, k = 4, W = 10"] == (108, 83) and got["alle, k = 8, W = 10"] == (150, 85)
    assert all(got[k][0] == 0 for k in got if k.startswith("gerichtet"))
    readme_has("mit Höchstwartezeit 10 min kommen 83 bzw. 85 Pläne hinzu, die erst durch Höchstabstände unmöglich werden")
    readme_has("(108 bzw. 150)")


def _anschluesse_text(counts):
    """{'2': 142, '3': 1, '4': 7} -> „142 von 150 zwei, 1 drei und 7 vier“ (die README-Schreibweise)."""
    words = {2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs"}
    total = sum(counts.values())
    parts = [(f"{counts[c]} von {total} {words[int(c)]}" if i == 0 else f"{counts[c]} {words[int(c)]}") for i, c in enumerate(sorted(counts, key=int))]
    return ", ".join(parts[:-1]) + " und " + parts[-1]


def test_anschluesse_im_zeitkreis_match_the_readme():
    """Zeitkreise ohne Höchstwartezeit (Richtung „alle“, 6 Linien, 240 Netze je Zeile): wie viele Anschlüsse der Kreis in der Löschfilter-Menge hat; die Zahlen kommen aus der Ergebnisdatei."""
    k4 = rec("e2_cycles", label="alle, k = 4, W unbegrenzt")
    k8 = rec("e2_cycles", label="alle, k = 8, W unbegrenzt")
    for row in (k4, k8):
        assert sum(row["anschluesse_im_kreis"].values()) == row["unmoeglich"] == row["zeitkreis"]      # ohne Höchstwartezeit ist jeder unmögliche Plan ein Zeitkreis-Plan
    c4, c8 = k4["anschluesse_im_kreis"], k8["anschluesse_im_kreis"]
    assert c4 == {"2": 102, "4": 6} and c8 == {"2": 142, "3": 1, "4": 7}
    readme_has(f"bei *k* = 4 {c4['2']} von {k4['zeitkreis']} Zeitkreisen zwei Anschlüsse und {c4['4']} vier")
    readme_has(f"bei *k* = 8 haben {_anschluesse_text(c8)}.")
    readme_has("(inklusionsminimal, nicht eindeutig, die Zahl kann je nach Bogenreihenfolge anders ausfallen; 6 Linien, „alle“, Höchstwartezeit unbegrenzt, 240 Netze je Zeile)")      # die Voraussetzungen


def _arcs_without_upper(inst, s):
    n, arcs = M.build_arcs(inst, s)
    return n, M.without_upper_bounds(arcs)


def test_no_sharp_transition_the_position_moves_up_and_the_band_widens_with_the_line_count():
    """Richtung „alle“, Höchstwartezeit 10 min: die Breite 0,9 bis 0,1 wächst mit 3, 6, 10 Linien (die README nennt die Breiten); die Mittelwerte der Lage 0,5 wachsen
    ebenfalls, die README sieht den Unterschied aber innerhalb der Streuung der Blöcke; bei unbegrenzter Höchstwartezeit ist die Lage nicht monoton."""
    k = {nl: [ev.k_at_share(ev.e1_curve(R["e1"], nl, "alle", 10), lv) for lv in (0.9, 0.5, 0.1)] for nl in (3, 6, 10)}
    assert k[3][1] < k[6][1] < k[10][1]
    assert (k[3][2] - k[3][0]) < (k[6][2] - k[6][0]) < (k[10][2] - k[10][0])
    readme_has("breiter (" + " / ".join(de(k[nl][2] - k[nl][0]) for nl in (3, 6, 10)) + " Anschlüsse)")
    readme_has("Lage des Anteils 0,5 (" + " / ".join(de(k[nl][1]) for nl in (3, 6, 10)) + ")")
    inf = {nl: ev.k_at_share(ev.e1_curve(R["e1"], nl, "alle", None), 0.5) for nl in (3, 6, 10)}
    assert not (inf[3] < inf[6] < inf[10])
    readme_has(f"bei {de(inf[3])} / {de(inf[6])} / {de(inf[10])} und wandert nicht monoton")


def test_step_then_flat_in_the_waiting_time():
    """Höchstwartezeit unbegrenzt gegen 40, 30, 20, 15 fällt der Anteil jeweils; von 15 auf 0 min nur noch um höchstens 3 Prozentpunkte (6 Linien, „alle“, k = 4)."""
    c = {w: share(rec("e1", nl=6, mode="alle", k=4, W=w)["feasible"], 250)[0] for w in (None, 40, 30, 20, 15, 0)}
    assert c[None] > c[40] > c[30] > c[20] > c[15] > c[0] and c[15] - c[0] <= 0.03 and c[None] - c[15] >= 0.3


def test_the_greedy_gap_grows_with_a_tighter_waiting_time_until_15_minutes():
    rows = {r["W"]: r for r in ev.e5_rest_rows(R["e5_rest"]) if r["k"] == 16}
    gaps = [rows[w]["exakt"][0] - rows[w]["greedy"][0] for w in (None, 30, 15, 10)]
    assert 0 <= gaps[0] < gaps[1] < gaps[2] and abs(gaps[3] - gaps[2]) < 0.001      # wächst bis 15 min, danach (15 auf 10 min) weniger als 0,1 Punkte Änderung
    readme_has("von 15 auf 10 min um weniger als 0,1 Prozentpunkte")
    readme_has(" / ".join(de(100 * g) for g in gaps))


def test_the_exact_value_is_never_below_the_greedy_where_proven():
    for r in R["e5_rest"]:
        if r["status"].get("OPTIMAL", 0) == r["n"] * 4:
            assert all(g <= e + 1e-9 for g, e in zip(r["greedy"], r["exakt"]))


def test_unproven_counts_of_the_kept_weight_are_stated():
    rows = ev.e5_rest_rows(R["e5_rest"])
    unproven = sum(r["von"] - r["optimal"] for r in rows)
    assert unproven > 0
    readme_has(f"({unproven} von {sum(r['von'] for r in rows)} Netzen in der gespeicherten Messung;")


def test_experiment_3_possible_plan_count_in_the_text():
    row = [r for r in ev.e3_rows(R["e3"]) if r["nl"] == 6 and r["label"] == "gerichtet, k = 4, W = 30"][0]
    readme_has(f"{row['machbar']} mögliche Pläne unter 1000 Netzen")
    assert row["machbar"] == sum(b["machbar"] for b in rec("e3", label="gerichtet, k = 4, W = 30", nl=6)["blocks"])


def test_experiment_1_text_numbers_of_the_impossible_share():
    mean = share(rec("e1", nl=6, mode="alle", k=4, W=None)["feasible"], 250)[0]
    readme_has(f"sind {de(100 * (1 - mean))} % der Pläne unmöglich")


def test_readme_test_count_matches_the_suite():
    """Die Testzahl der README stimmt mit der Suite überein (DEMO-PLAYBOOK §5); `--collect-only` führt nichts aus, also keine Rekursion."""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True, timeout=300).stdout
    n = int(re.search(r"(\d+) tests? collected", out).group(1))
    m = re.search(r"\*\*Testzahl:\*\* (\d+) Tests", README)
    assert m and int(m.group(1)) == n, (m.group(1) if m else None, n)
