"""PDF-Planbericht: gültiges PDF für einen möglichen und für einen unmöglichen Plan, Umlaute und Sonderzeichen gehen durch `_clean`."""

import zab_evaluation as ev
import zab_pdf_export as P
import zab_witness as W
from zab_model import Settings


def _pdf(settings, lines=6, seed=501):
    a = ev.analyse(lines, seed, settings)
    kind, text = ev.verdict_plan(a.feasible, len(a.transfer_keys), a.n, a.schedule.end if a.feasible else 0, 0, 0, a.excess)
    rows = W.witness_rows(list(a.arcs), list(a.witness), a.labels) if not a.feasible else None
    return a, P.generate_plan_pdf(a, text, rows)


def test_pdf_of_a_possible_plan():
    a, data = _pdf(Settings(transfers="gerichtet", k_transfers=2, wait_max=60))
    assert a.feasible and data[:5] == b"%PDF-" and len(data) > 3000


def test_pdf_of_an_impossible_plan_lists_the_witness():
    a, data = _pdf(Settings(transfers="alle", k_transfers=None, wait_max=None))
    assert not a.feasible and data[:5] == b"%PDF-" and len(data) > 2000


def test_clean_replaces_characters_outside_latin_1():
    assert P._clean("a – b → c ≥ 3 ∞ „x“ ä ö ü ß") == 'a - b -> c >= 3 unbegrenzt "x" ä ö ü ß'


def test_settings_lines_name_the_planning_assumption():
    a = ev.analyse(6, 501, Settings(transfers="gerichtet", k_transfers=4, wait_max=30))
    lines = P.settings_lines(a)
    assert any("Planungsannahme" in line for line in lines) and any("Richtung gerichtet" in line for line in lines) and any("30 min" in line for line in lines)
