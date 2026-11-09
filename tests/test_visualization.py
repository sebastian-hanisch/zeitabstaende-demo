"""Abbildungen: bauen ohne Fehler, Achsen gesperrt, Inhalte stimmen mit der Analyse überein."""

import zab_evaluation as ev
import zab_visualization as V
import zab_witness as W
from zab_model import Settings


def _locked(fig):
    return all(ax.fixedrange for ax in (fig.layout.xaxis, fig.layout.yaxis))


def test_event_chart_has_one_row_per_event_of_the_line_and_the_right_positions():
    a = ev.analyse(6, 501, Settings(transfers="gerichtet", k_transfers=4, wait_max=30))
    assert a.feasible
    fig = V.build_event_chart(a, 0)
    rows = V.event_rows(a, 0)
    assert len(rows) == 20 and _locked(fig)
    bar = fig.data[0]
    assert list(bar.base) == [a.schedule.earliest[e] for e, _ in rows]
    assert [b + w for b, w in zip(bar.base, bar.x)] == [a.schedule.latest[e] for e, _ in rows]
    points = sum(len(t.x) for t in fig.data[1:])
    assert points == 20                                     # jedes Ereignis genau einmal als Raute


def test_witness_waterfall_sums_to_the_excess():
    a = ev.analyse(6, 501, Settings(transfers="alle", k_transfers=None, wait_max=None))
    rows = W.witness_rows(list(a.arcs), list(a.witness), a.labels)
    fig = V.build_witness_waterfall(rows)
    assert _locked(fig) and sum(r["beitrag"] for r in rows) == a.excess["excess"] > 0
    assert list(fig.data[0].y)[:-1] == [r["beitrag"] for r in rows]


def test_network_map_marks_each_transfer_stop_once():
    a = ev.analyse(6, 501, Settings(transfers="gerichtet", k_transfers=4, wait_max=30))
    fig = V.build_network_map(a)
    assert _locked(fig)
    ring = [t for t in fig.data if t.name == "Umsteigehalt eines verlangten Anschlusses"]
    hubs = {a.inst.lines[k[0]].stops[k[2]] for k in a.transfer_keys}
    assert len(ring) == 1 and len(ring[0].x) == len(hubs)


def test_bar_and_curve_charts_lock_their_axes():
    assert _locked(V.build_bar_chart(["a", "b"], {"x": [0.1, 0.2], "y": ([0.3, 0.4], [0.01, 0.02])}, "Anteil"))
    assert _locked(V.build_e1_chart({"W = 30": [(1, 1.0, 0.0), (2, 0.5, 0.1), (None, 0.0, 0.0)]}))
