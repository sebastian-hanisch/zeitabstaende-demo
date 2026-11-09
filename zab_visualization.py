"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben.

Karte mit gleichem Maßstab: `scaleanchor` nur mit `autorange` (y umgekehrt) und zwei unsichtbaren Eckmarkern, sonst friert Plotly den Bereich beim
ersten Zeichnen ein. Beschriftungen als Text der Achsen oder als Annotation, damit nichts abgedunkelt wird.
"""
from __future__ import annotations

import plotly.graph_objects as go

import zab_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=360, **layout):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
                      plot_bgcolor="rgba(0,0,0,0)", **layout)
    return lock_axes(fig)


def build_network_map(a) -> go.Figure:
    """Netzkarte: Linien in Farbe auf den Haltestellen (gemeinsame Abschnitte gestaffelt), Haltestellen mit Nummer, Umsteigehalte der verlangten Anschlüsse mit Ring."""
    fig = go.Figure()
    n = len(a.inst.lines)
    for li, line in enumerate(a.inst.lines):
        xs, ys = [], []
        for s0, s1 in zip(line.stops, line.stops[1:]):
            xs += [a.coords[s0][0], a.coords[s1][0], None]
            ys += [a.coords[s0][1], a.coords[s1][1], None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=C.LINE_COLORS[li % len(C.LINE_COLORS)], width=2.5 + 1.1 * (n - 1 - li)),
                                 opacity=0.9, name=f"Linie {li + 1}", hoverinfo="name"))
    used = sorted({s for line in a.inst.lines for s in line.stops})
    fig.add_trace(go.Scatter(x=[a.coords[s][0] for s in used], y=[a.coords[s][1] for s in used], mode="markers+text",
                             marker=dict(size=9, color="white", line=dict(color="#1c2430", width=1.5)), text=[str(s) for s in used], textposition="top right",
                             textfont=dict(size=10), showlegend=False, hovertemplate="Haltestelle %{text}<extra></extra>"))
    hubs = sorted({a.inst.lines[k[0]].stops[k[2]] for k in a.transfer_keys})
    if hubs:
        fig.add_trace(go.Scatter(x=[a.coords[s][0] for s in hubs], y=[a.coords[s][1] for s in hubs], mode="markers",
                                 marker=dict(size=21, color="rgba(0,0,0,0)", line=dict(color=C.COLOR_BAD, width=3)), name="Umsteigehalt eines verlangten Anschlusses",
                                 hovertemplate="Umsteigehalt %{x}, %{y}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="markers", marker=dict(opacity=0), showlegend=False, hoverinfo="skip"))
    fig.update_layout(height=520, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0))
    fig.update_xaxes(visible=False, fixedrange=True, scaleanchor="y", scaleratio=1)
    fig.update_yaxes(visible=False, fixedrange=True, autorange="reversed")
    return fig


def event_rows(a, line_index: int) -> list:
    """Ereignisse einer Linie in Fahrtreihenfolge: (Index, Beschriftung ohne Linienkürzel)."""
    return [(e, a.labels[e].split(" ", 1)[1]) for e in range(a.n) if a.event_line[e] == line_index]


def build_event_chart(a, line_index: int) -> go.Figure:
    """Ereignis-Zeit-Diagramm einer Linie: Balken von der frühesten bis zur spätesten Lage (Länge = Spielraum), Raute auf der frühesten Lage;
    kritisch (Spielraum 0) rot, kritisch nur wegen eines Höchstabstands orange, übrige grau."""
    sch = a.schedule
    rows = event_rows(a, line_index)
    only = set(a.only_by_upper)
    ys = [r[1] for r in rows]
    fig = go.Figure()
    groups = [("kritisch (Spielraum 0)", C.COLOR_CRIT, lambda e: sch.slack[e] == 0 and e not in only),
              ("kritisch nur wegen eines Höchstabstands", C.COLOR_CRIT_MAX, lambda e: e in only),
              ("mit Spielraum", C.COLOR_SLACK, lambda e: sch.slack[e] > 0)]
    fig.add_trace(go.Bar(y=ys, x=[sch.latest[e] - sch.earliest[e] for e, _ in rows], base=[sch.earliest[e] for e, _ in rows], orientation="h",
                         marker=dict(color="rgba(125,136,152,0.35)"), showlegend=False, hoverinfo="skip"))
    for name, color, pick in groups:
        sel = [(e, lab) for e, lab in rows if pick(e)]
        if not sel:
            continue
        fig.add_trace(go.Scatter(x=[sch.earliest[e] for e, _ in sel], y=[lab for _, lab in sel], mode="markers", name=name,
                                 marker=dict(symbol="diamond", size=11, color=color), customdata=[[sch.latest[e], sch.slack[e]] for e, _ in sel],
                                 hovertemplate="%{y}<br>frühestens Minute %{x}, spätestens %{customdata[0]}, Spielraum %{customdata[1]} min<extra></extra>"))
    fig.update_xaxes(title_text="Minute seit Beginn des Umlaufs")
    fig.update_yaxes(autorange="reversed", type="category")
    return _base(fig, height=120 + 26 * len(rows))


def build_witness_waterfall(rows) -> go.Figure:
    """Der Kreis als Wasserfall: Mindestabstände steigen, Höchstabstände fallen; die letzte Säule ist der Überschuss (Länge des Kreises)."""
    fig = go.Figure(go.Waterfall(
        x=[f"{i + 1}" for i in range(len(rows))] + ["Überschuss"], measure=["relative"] * len(rows) + ["total"], y=[r["beitrag"] for r in rows] + [0],
        text=[f"{r['beitrag']:+d}" for r in rows] + [f"{sum(r['beitrag'] for r in rows):+d}"], textposition="outside",
        increasing=dict(marker=dict(color=C.COLOR_LINE)), decreasing=dict(marker=dict(color=C.COLOR_OK)), totals=dict(marker=dict(color=C.COLOR_BAD)),
        hovertemplate="%{x}: %{y} min<extra></extra>"))
    fig.update_xaxes(title_text="Abstand im Kreis (Reihenfolge der Tabelle)", type="category")
    fig.update_yaxes(title_text="Summe der Abstände (min)")
    return _base(fig, height=340, showlegend=False)


def build_e1_chart(curves: dict, current_k=None) -> go.Figure:
    """Anteil möglicher Pläne gegen k, eine Linie je Höchstwartezeit; `curves`: {Beschriftung: [(k, Mittel, Std), ...]} (k None = alle, wird als letzter Wert gesetzt)."""
    fig = go.Figure()
    palette = ["#1c2430", C.COLOR_LINE, C.COLOR_OK, "#c77700", C.COLOR_BAD, "#8e44ad", "#16a085", "#7f8c8d"]
    for i, (label, curve) in enumerate(curves.items()):
        xs = [(str(k) if k is not None else "alle") for k, _m, _s in curve]
        fig.add_trace(go.Scatter(x=xs, y=[m for _k, m, _s in curve], mode="lines+markers", name=label, line=dict(color=palette[i % len(palette)], width=2.5),
                                 error_y=dict(type="data", array=[s for _k, _m, s in curve], visible=True, thickness=1),
                                 hovertemplate="k = %{x}: %{y:.3f}<extra>" + label + "</extra>"))
    if current_k is not None:
        fig.add_vline(x=current_k, line=dict(color="#c0392b", dash="dot", width=2))
    fig.update_xaxes(title_text="verlangte Anschlüsse k (die k am stärksten nachgefragten Umstiege, je Richtung gezählt)", type="category")
    fig.update_yaxes(title_text="Anteil möglicher Pläne", range=[-0.02, 1.05])
    return _base(fig, height=400)


def build_bar_chart(categories, series: dict, y_title: str, y_range=None, height=340, x_title=None) -> go.Figure:
    """Gruppierte Balken: `series` = {Name: [Werte je Kategorie]} (ggf. mit Fehlerbalken als {Name: (Werte, Fehler)})."""
    fig = go.Figure()
    palette = [C.COLOR_LINE, C.COLOR_OK, "#c77700", C.COLOR_BAD]
    for i, (name, vals) in enumerate(series.items()):
        err = None
        if isinstance(vals, tuple):
            vals, err = vals
        fig.add_trace(go.Bar(x=[str(c) for c in categories], y=list(vals), name=name, marker_color=palette[i % len(palette)],
                             error_y=dict(type="data", array=list(err), visible=True) if err is not None else None,
                             hovertemplate="%{x}: %{y:.3f}<extra>" + name + "</extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text=y_title, **({"range": y_range} if y_range else {}))
    if x_title:
        fig.update_xaxes(title_text=x_title, type="category")
    else:
        fig.update_xaxes(type="category")
    return _base(fig, height=height)
