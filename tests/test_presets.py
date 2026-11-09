"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, Permalink-Einrasten; die Verdikte der Presets stehen in test_claims.py."""

import pytest

import zab_constants as C
import zab_presets as P


def test_every_preset_has_help_and_all_keys():
    assert list(C.PRESETS) == C.PRESET_ORDER
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name]


def test_preset_values_are_valid_stages():
    for name, preset in C.PRESETS.items():
        for key, value in preset.items():
            spec = P.SETTING_SPECS[P.PRESET_KEYS[key]]
            if spec.options is not None:
                assert value in spec.options, (name, key, value)
            else:
                assert spec.lo <= value <= spec.hi, (name, key, value)


def test_preset_seeds_lie_outside_the_measurement_seeds():
    """Die Messreihen nutzen Seeds 3000 + 100 * Nr (Nr 0 bis 999) plus die Seed-Suche bis +49; Presets bleiben darunter."""
    top = C.SWEEP_BASE + C.SWEEP_STEP * (C.SWEEP_BLOCKS * C.SWEEP_PER - 1) + 49
    for name, preset in C.PRESETS.items():
        assert preset["seed"] + 49 < C.SWEEP_BASE or preset["seed"] > top, name


def test_default_preset_equals_the_default_settings():
    standard = C.PRESETS[C.PRESET_ORDER[0]]
    for key, state_key in P.PRESET_KEYS.items():
        assert standard[key] == P.SETTING_SPECS[state_key].default, key


def test_setting_specs_cover_every_preset_key():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)


def test_all_presets_are_different():
    assert len({tuple(sorted(p.items(), key=lambda kv: kv[0])) for p in C.PRESETS.values()}) == len(C.PRESETS)


@pytest.mark.parametrize("state_key,raw,expected", [
    ("k_select", "7", 6), ("k_select", "9", 8), ("k_select", "alle", "alle"), ("k_select", "13", 12), ("k_select", "100", 24),
    ("w_select", "unbegrenzt", "unbegrenzt"), ("w_select", "12", 10), ("w_select", "-5", 0), ("lines_select", "7", 6), ("lines_select", "4", 3),
    ("headway_select", "3", 2), ("mode_radio", "alle", "alle"),
])
def test_permalink_values_snap_to_the_nearest_stage(state_key, raw, expected):
    assert P.SETTING_SPECS[state_key].caster(raw) == expected


@pytest.mark.parametrize("state_key,raw", [("k_select", "viele"), ("w_select", "abc"), ("mode_radio", "zufällig")])
def test_permalink_text_that_matches_no_stage_is_rejected(state_key, raw):
    with pytest.raises(ValueError):
        P.SETTING_SPECS[state_key].caster(raw)
