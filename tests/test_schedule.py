"""Frühest- und Spätestlagen, Spielraum, kritische Ereignisse: von Hand gerechnete Mini-Systeme (conftest.py)."""

import zab_schedule as S
from zab_model import Arc, without_upper_bounds


def test_chain_has_zero_slack_everywhere(chain):
    n, arcs = chain
    sch, wit = S.schedule(n, arcs)
    assert wit is None
    assert sch.earliest == (0, 2, 5) and sch.latest == (0, 2, 5) and sch.slack == (0, 0, 0) and sch.end == 5


def test_chain_with_loose_upper_bound_is_unchanged(chain):
    n, arcs = chain
    sch, _ = S.schedule(n, arcs + [Arc(0, 2, 0, 6, "turn")])
    assert sch.earliest == (0, 2, 5) and sch.slack == (0, 0, 0)


def test_chain_with_tight_upper_bound_is_infeasible_and_returns_the_witness(chain):
    n, arcs = chain
    sch, wit = S.schedule(n, arcs + [Arc(0, 2, 0, 4, "turn")])
    assert sch is None and wit is not None and sum(e[2] for e in wit) == 1


def test_diamond_slack_by_hand(diamond):
    n, arcs = diamond
    sch, _ = S.schedule(n, arcs)
    # s = 0, x = 4, y = 2, e = 7; y darf bis 5 warten: Spielraum 3
    assert sch.earliest == (0, 4, 2, 7) and sch.end == 7
    assert sch.latest == (0, 4, 5, 7) and sch.slack == (0, 0, 3, 0)
    assert S.critical(sch.slack) == [0, 1, 3]


def test_diamond_with_upper_bound_shrinks_the_slack_of_y(diamond):
    n, arcs = diamond
    arcs = arcs + [Arc(2, 1, -100, 1, "turn")]        # x - y <= 1: y frühestens 3
    sch, _ = S.schedule(n, arcs)
    assert sch.earliest == (0, 4, 3, 7) and sch.slack[2] == 2
    cpm_crit, cpm = S.critical_cpm(n, arcs)
    assert cpm.slack[2] == 3 and cpm_crit == [0, 1, 3]       # die klassische Rechnung meldet 3


def test_event_critical_only_because_of_an_upper_bound(diamond_hi):
    n, arcs = diamond_hi
    full, _ = S.schedule(n, arcs)
    assert full.earliest == (0, 4, 3, 8) and full.end == 8 and full.slack == (0, 0, 0, 0)
    cpm_crit, cpm = S.critical_cpm(n, arcs)
    assert cpm.earliest == (0, 4, 1, 7) and cpm.slack == (0, 0, 1, 0) and cpm_crit == [0, 1, 3]
    only, wit = S.critical_only_by_upper_bounds(n, arcs)
    assert wit is None and only == [2]


def test_critical_only_by_upper_bounds_of_an_infeasible_plan(time_cycle):
    n, arcs = time_cycle
    only, wit = S.critical_only_by_upper_bounds(n, arcs)
    assert only is None and wit is not None


def test_without_upper_bounds_removes_every_upper_bound(chain):
    n, arcs = chain
    assert all(a.hi is None for a in without_upper_bounds(arcs))
    assert [a.lo for a in without_upper_bounds(arcs)] == [a.lo for a in arcs]


def test_latest_with_later_end_shifts_every_latest_lage(chain):
    n, arcs = chain
    late, end = S.latest(n, arcs, end=9)
    assert end == 9 and late == [4, 6, 9]


def test_slack_is_never_negative_on_a_feasible_plan(diamond, diamond_hi, chain):
    for n, arcs in (diamond, diamond_hi, chain):
        sch, _ = S.schedule(n, arcs)
        assert min(sch.slack) == 0 and all(s >= 0 for s in sch.slack)
