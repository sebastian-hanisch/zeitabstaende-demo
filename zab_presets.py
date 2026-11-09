"""Permalink (Begrenzen und Einrasten), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio).

Alle Regler außer dem Zufalls-Seed sind Auswahlstufen (`st.select_slider` bzw. `st.radio`); ein Permalink-Wert zwischen den Stufen rastet auf die nächste
numerische Stufe ein (bei Gleichstand auf die kleinere), ein Textwert muss genau passen. Die Regler haben feste Grenzen: der Zustand eines Reglers
wird nirgends in einem Lauf geschrieben, in dem er nicht gezeichnet wird (kein ausblendbarer Regler).
"""

import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import zab_constants as C


def snap_option(options):
    """Caster für Auswahlstufen: Text -> Stufe. Zahlen rasten auf die nächste numerische Stufe ein, Textstufen („alle“, „unbegrenzt“) müssen genau passen."""
    numeric = [o for o in options if not isinstance(o, str)]

    def cast(raw):
        for o in options:
            if isinstance(o, str) and o == raw:
                return o
        value = float(raw)      # wirft ValueError bei unbrauchbarem Text; der Aufrufer überspringt dann den Wert
        return min(numeric, key=lambda o: (abs(o - value), o))
    return cast


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    options: Optional[tuple] = None

    @property
    def first(self):
        return self.options[0] if self.options else self.lo

    @property
    def last(self):
        return self.options[-1] if self.options else self.hi


def _opt(url, options, default):
    return SettingSpec(url, snap_option(options), default, options=tuple(options))


SETTING_SPECS = {
    "lines_select": _opt("lines", C.LINES_OPTIONS, C.DEFAULT_LINES),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, C.SEED_MIN, C.SEED_MAX),
    "mode_radio": _opt("mode", C.TRANSFER_MODES, C.DEFAULT_MODE),
    "k_select": _opt("k", C.K_OPTIONS, C.DEFAULT_K),
    "w_select": _opt("w", C.W_OPTIONS, C.DEFAULT_W),
    "turn_select": _opt("turn", C.TURN_OPTIONS, C.DEFAULT_TURN),
    "reserve_select": _opt("reserve", C.RESERVE_OPTIONS, C.DEFAULT_RESERVE),
    "dwell_select": _opt("dwell", C.DWELL_HI_OPTIONS, C.DEFAULT_DWELL_HI),
    "tmin_select": _opt("tmin", C.TRANSFER_MIN_OPTIONS, C.DEFAULT_TRANSFER_MIN),
    "headway_select": _opt("hw", C.HEADWAY_OPTIONS, C.DEFAULT_HEADWAY),
}
PRESET_KEYS = {"lines": "lines_select", "seed": "seed_input", "mode": "mode_radio", "k": "k_select", "w": "w_select", "turn": "turn_select",
               "reserve": "reserve_select", "dwell_hi": "dwell_select", "transfer_min": "tmin_select", "headway": "headway_select"}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt bzw. auf die nächste Stufe eingerastet."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
            except (ValueError, TypeError):
                continue
            if spec.options is None:
                if spec.lo is not None:
                    value = max(spec.lo, value)
                if spec.hi is not None:
                    value = min(spec.hi, value)
            st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen
    Standardwert) mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS,
    dann hebt auch seine Änderung die Markierung auf (tests/test_layout.py prüft das für jeden Regler)."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
