"""Der kopierte Generator: SplitMix64, Eigenschaften, Netze gleich dem Original (eingefroren, und im Vergleich mit dem Geschwisterordner, wenn er da ist)."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import zab_network as N
import zab_rng

ROOT = Path(__file__).resolve().parent.parent
SIBLING = ROOT.parent / "taktfahrplan-demo"


def test_splitmix64_reference_values():
    r = zab_rng.SplitMix64(0)       # Referenzwerte des Originalalgorithmus (Vigna) für Seed 0
    assert r.next() == 0xE220A8397B1DCDAF
    assert r.next() == 0x6E789E6AA1B965F4
    assert r.next() == 0x06C45D188009454F
    r = zab_rng.SplitMix64(12345)
    assert set(r.below(7) for _ in range(2000)) == set(range(7))


def test_generator_properties_and_determinism():
    c1, d1, h1 = N.generate_network(20, 7)
    c2, d2, h2 = N.generate_network(20, 7)
    assert (c1 == c2).all() and (d1 == d2).all() and h1 == h2
    assert c1.min() >= 5 and c1.max() <= 95 and (d1 == d1.T).all() and (np.diag(d1) == 0).all() and len(set(h1)) == 2


# Referenzlinien des Originals (transit-demo, demand_greedy_construction), eingefroren aus taktfahrplan-demo/tests/test_network.py
FROZEN = {
    (20, 3, 6, 100): [[9, 2, 8, 1, 7, 11], [13, 14, 2, 12, 19, 18], [16, 5, 6, 8, 2, 3]],
    (20, 6, 6, 5): [[4, 2, 8, 11, 15, 5], [1, 16, 17, 0, 11, 14], [13, 11, 8, 18, 19, 9], [2, 12, 11, 8, 10, 15], [3, 15, 7, 8, 11, 2], [15, 11, 6, 10, 8, 2]],
    (20, 10, 6, 400): [[7, 11, 15, 19, 9, 2], [10, 19, 15, 18, 13, 8], [0, 19, 15, 3, 16, 5], [9, 1, 15, 19, 17, 14], [9, 12, 4, 19, 15, 6],
                       [11, 15, 1, 6, 19, 9], [11, 19, 15, 1, 16, 9], [2, 9, 4, 11, 19, 15], [11, 15, 19, 4, 16, 9], [11, 15, 19, 5, 10, 9]],
}


def test_port_equals_frozen_reference():
    assert len(FROZEN) == 3 and all(ref for ref in FROZEN.values())
    for (n_stops, n_lines, max_len, seed), ref in FROZEN.items():
        coords, demand, _ = N.generate_network(n_stops, seed)
        assert N.demand_greedy(coords, demand, n_lines, max_len) == ref


def test_built_instances_are_usable():
    for n_lines in (3, 6, 10):
        for seed in range(0, 3000, 500):
            inst, _demand, _coords, used = N.build_valid_instance(n_lines, seed)
            assert seed <= used < seed + 50 and len(inst.lines) >= 2 and len(inst.transfers) >= 3
            assert all(len(line.stops) - 1 == len(line.run) and min(line.run) >= 2 for line in inst.lines)
            assert all(w > 0 for w in inst.transfers.values())


def _fingerprint(n_lines, seed):
    inst, _d, _c, used = N.build_valid_instance(n_lines, seed)
    return used, [(l.stops, l.run) for l in inst.lines], sorted(inst.transfers.items())


def test_equals_the_fall_demo_copy_when_present():
    """Die Kopie erzeugt dieselben Netze wie taktfahrplan-demo (nur wenn der Geschwisterordner da ist, sonst übersprungen)."""
    if not (SIBLING / "tkt_network.py").exists():
        pytest.skip("taktfahrplan-demo liegt nicht neben diesem Repo")
    sys.path.insert(0, str(SIBLING))
    try:
        spec = importlib.util.spec_from_file_location("tkt_network_original", SIBLING / "tkt_network.py")
        orig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(orig)
    finally:
        sys.path.remove(str(SIBLING))
    checked = 0
    for n_lines in (3, 5, 6, 8, 10):
        for seed in (0, 501, 3000, 3100, 7777):
            inst, _d, _c, used = orig.build_valid_instance(n_lines, seed)
            assert (used, [(l.stops, l.run) for l in inst.lines], sorted(inst.transfers.items())) == _fingerprint(n_lines, seed)
            checked += 1
    assert checked == 25
