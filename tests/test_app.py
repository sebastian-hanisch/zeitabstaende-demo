"""End-to-end Smoke-Test via Streamlits AppTest: lädt app.py, klickt jeden Button, fährt jeden Regler (Auswahlstufen, Radio, Zahl) an seine Grenzen, durchläuft
jedes Preset und löst jeden ▶️-Knopf einzeln aus. Geprüft wird, dass kein Python-Fehler auftritt (insbesondere StreamlitDuplicateElementId bei Diagrammen
gleichen Inhalts und StreamlitAPIException bei Reglern) und dass die Seitenleiste die Regler aus SETTING_SPECS enthält."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import zab_constants as C
import zab_presets as P

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))
AUTOPLAY_MARKER = "\u25b6"      # ▶️-Knöpfe rechnen live (CP-SAT) und werden unten einzeln geprüft


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=TIMEOUT)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _widget(at, key):
    for art in ("select_slider", "radio", "number_input"):
        try:
            return getattr(at.sidebar, art)(key=key)
        except KeyError:
            continue
    raise AssertionError(key)


def test_app_loads_without_exception():
    at = _fresh_app()
    assert at.title and not at.error


def test_every_button_except_the_live_ones_does_not_raise():
    labels = [b.label for b in _fresh_app().button]
    assert labels, "keine Buttons gefunden"
    for index, label in enumerate(labels):
        if AUTOPLAY_MARKER in label:
            continue
        at = _fresh_app()
        at.button[index].click().run(timeout=TIMEOUT)
        assert not at.exception, (label, [str(e) for e in at.exception])


@pytest.mark.parametrize("state_key", list(P.SETTING_SPECS))
@pytest.mark.parametrize("edge", ["first", "last"])
def test_every_regler_at_its_first_and_last_stage_does_not_raise(state_key, edge):
    at = _fresh_app()
    spec = P.SETTING_SPECS[state_key]
    _widget(at, state_key).set_value(spec.first if edge == "first" else spec.last).run(timeout=TIMEOUT)
    assert not at.exception, (state_key, edge, [str(e) for e in at.exception])


def test_the_largest_net_with_all_transfers_does_not_raise():
    """Slider-Maxima zugleich: 10 Linien, alle Anschlüsse beider Richtungen, keine Höchstwartezeit, Zugfolge 10 min (200 Ereignisse, mehrere hundert Bögen)."""
    at = _fresh_app()
    for key, value in (("lines_select", 10), ("mode_radio", "alle"), ("k_select", "alle"), ("headway_select", 10)):
        _widget(at, key).set_value(value)
    at.run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]


def test_the_live_free_order_button():
    at = _fresh_app()
    _widget(at, "headway_select").set_value(4)
    at.run(timeout=TIMEOUT)
    btn = next(b for b in at.button if b.key == "run_free")
    btn.click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("freie Reihenfolge" in i.value and "Abschnittspaare" in i.value for i in at.info)


def test_the_live_free_order_button_is_hidden_without_a_headway():
    at = _fresh_app()
    assert not [b for b in at.button if b.key == "run_free"]


def test_the_live_kept_weight_button():
    at = _fresh_app()
    _widget(at, "mode_radio").set_value("alle")
    _widget(at, "k_select").set_value(8)
    at.run(timeout=TIMEOUT)
    btn = next(b for b in at.button if b.key == "run_kept")
    btn.click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("höchstens" in i.value and "verlangten Nachfrage halten" in i.value for i in at.info)


def test_the_live_kept_weight_button_is_hidden_beyond_the_live_limit():
    at = _fresh_app()
    _widget(at, "mode_radio").set_value("alle")
    _widget(at, "k_select").set_value(24)
    at.run(timeout=TIMEOUT)
    assert not [b for b in at.button if b.key == "run_kept"]


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_every_preset_gives_the_expected_verdict_kind(name):
    """Jedes Preset durchlaufen (DEMO-PLAYBOOK §11a.7): Art des Verdikts der Kernfrage und der Einstieg in die Experimente."""
    at = _fresh_app()
    at.sidebar.button(key=f"preset_{name}").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    from zab_evaluation import analyse, settings_from_widgets
    p = C.PRESETS[name]
    a = analyse(p["lines"], p["seed"], settings_from_widgets(p["mode"], p["k"], p["w"], p["turn"], p["reserve"], p["dwell_hi"], p["transfer_min"], p["headway"]))
    shown_ok = any("Der Plan ist **möglich**" in s.value for s in at.success)
    shown_bad = any("Der Plan ist **unmöglich**" in e.value for e in at.error)
    assert shown_ok == a.feasible and shown_bad == (not a.feasible)
