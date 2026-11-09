"""Zeitabstände – wann ein Plan überhaupt möglich ist - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein Umlaufplan aus Mindest- und Höchstabständen als Differenzbedingungen; Bellman-Ford auf dem Bedingungsgraphen entscheidet über Machbarkeit
(Kreis positiver Länge = unmöglich) und liefert früheste und späteste Lagen. Vehikel: ein Umlauf je Linie eines synthetischen Netzes. Gehört zur Linie „Takt und Periodizität“ der Konzepte-Reihe.

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import zab_bridge as B
import zab_constants as C
import zab_evaluation as ev
import zab_model as M
import zab_schedule as S
import zab_sweeps as SW
import zab_witness as W
from zab_evaluation import analyse, settings_from_widgets
from zab_layout import dunkles_design, kopf_css
from zab_pdf_export import generate_plan_pdf
from zab_presets import (
    SETTING_SPECS,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)
from zab_visualization import (
    build_bar_chart,
    build_e1_chart,
    build_event_chart,
    build_network_map,
    build_witness_waterfall,
)

st.set_page_config(page_title="Zeitabstände – Sebastian Hanisch", layout="wide")


def fmt(x, digits=1):
    """Zahl mit Dezimalkomma."""
    return f"{x:.{digits}f}".replace(".", ",")


def pct(x, digits=1):
    return f"{fmt(100 * x, digits)} %"


def pct_std(ms, digits=1):
    return f"{fmt(100 * ms[0], digits)} % ± {fmt(100 * ms[1], digits)}"


def hi_text(hi):
    return "∞" if hi is None else str(hi)


@st.cache_data(show_spinner=False)
def _analysis(lines, seed, settings):
    return analyse(lines, seed, settings)


@st.cache_data(show_spinner=False)
def _results():
    return SW.load_results()


@st.cache_data(show_spinner=False)
def _minimal(lines, seed, settings):
    a = analyse(lines, seed, settings)
    info = W.explain_infeasible(a.n, list(a.arcs))
    return info["keep"], info


@st.cache_data(show_spinner=False)
def _periodic(lines, seed, settings):
    a = analyse(lines, seed, settings)
    ok, phases, xs = B.periodic_solution(a.n, list(a.arcs), C.T, limit=C.CPSAT_LIVE_SECONDS, workers=1)
    total = None
    if ok and a.witness is not None:
        total = B.cycle_sum_of_x(list(a.witness), xs)
    return ok, total


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in zab_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("⏱️ Zeitabstände – wann ein Plan überhaupt möglich ist")
st.markdown(
    """
**Wann ist ein Plan aus Mindest- und Höchstabständen überhaupt möglich, wie viel Spielraum hat jedes Ereignis, und was kippt ihn?** Jede Bedingung eines Umlaufplans ist eine
Differenz zweier Zeitpunkte: Fahrzeit, Halt, Wende, Umsteigeanschluss. Ein **Bellman-Ford-Lauf** auf dem Bedingungsgraphen entscheidet: Ein **Kreis positiver Länge** heißt
*unmöglich*, sonst ergeben Vor- und Rückwärtslauf die **früheste und späteste Lage** jedes Ereignisses. Vehikel ist je ein Umlauf der Linien eines synthetischen Netzes
(**Annahmen, keine Echtdaten**; die Anschlussliste „die *k* am stärksten nachgefragten Umstiege, je Richtung gezählt“ und die Richtung „gerichtet“ sind **Planungsannahmen**). Die Höchstwartezeit *W* am Anschluss ist **über der Mindest-Umsteigezeit gemessen**.

Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe: Der Plan gilt **einmal**, nicht im Takt. Experiment 5 lässt dieselben Bedingungen modulo *T* gelten. Den Algorithmus
selbst zeigt `bellman-ford-demo`, den kritischen Pfad ohne Höchstabstände `kritischer-pfad-demo`; hier zählen die Befunde auf dem Fahrplan.

Wer die Frage zuerst ohne Fachbegriffe verstehen will, öffnet **💬 In einfachen Worten**. Weiter unten: fünf Abschnitte **🔬 Experiment**, **🚧 Wo die Annahmen enden** und der Expander **📐 Mathematische Formulierung**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/zeitabstaende-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Stellen Sie sich einen Fahrplan vor, in dem jede Bedingung ein Abstand zwischen zwei Zeitpunkten ist: Eine Fahrt dauert mindestens so lang, ein Umsteiger braucht mindestens so viel Zeit, ein Anschluss soll, über der Mindest-Umsteigezeit gemessen, höchstens so lange warten. Die Demo prüft, ob sich alle Bedingungen **zugleich erfüllen lassen**.

Das scheitert, wenn eine Kette von Mindestzeiten einen Kreis bildet: Dann müsste ein Ereignis später stattfinden als es selbst, und keine längere Wartezeit hilft. Geht der Plan auf, zeigt die Demo für jedes Ereignis, wie früh und wie spät es liegen darf, den **Spielraum**; ohne Spielraum ist es kritisch. Alles gilt nur einmal und für erfundene Netze.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/zeitabstaende-erklaert.html)
        """
    )
# erklaerseite:einfach:end

with st.expander("So funktioniert ein Plan aus Zeitabständen", expanded=True):
    st.markdown(
        """
1. **Jede Bedingung ist ein Fenster** $l \\le x_v - x_u \\le h$ zwischen zwei Ereignissen (Abfahrt oder Ankunft eines Zuges an einem Halt). Ohne Höchstabstand ist $h = \\infty$.
2. **Der Bedingungsgraph** hat zwei Kanten je Fenster: $u \\to v$ mit Gewicht $+l$ und, wenn es einen Höchstabstand gibt, $v \\to u$ mit Gewicht $-h$.
3. **Ein Kreis positiver Länge heißt unmöglich:** Die Mindestabstände entlang des Kreises sind zusammen länger, als die Höchstabstände erlauben. Ein Kreis *ohne*
   Höchstabstand (ein **Zeitkreis**) ist sogar durch keine Lockerung der Wartezeit aufzulösen.
4. **Sonst** ist der **längste Weg** ab der Quelle die früheste Lage jedes Ereignisses, der **Rückwärtslauf** vom Gesamtende die späteste. Die Differenz ist der **Spielraum**;
   Ereignisse mit Spielraum 0 sind **kritisch**.

| Bogen | Fenster [Mindest-, Höchstabstand] in Minuten | Regler |
|---|---|---|
| Fahrzeit | [Fahrzeit, Fahrzeit + Reserve] | Fahrzeitreserve |
| Halt | [1, längste Haltezeit] | Haltezeit |
| Wende am Endpunkt | [4, 4 + Höchstwende] | Höchstwende |
| Anschluss | [Mindest-Umsteigezeit, Mindest-Umsteigezeit + Höchstwartezeit] | Mindest-Umsteigezeit, Höchstwartezeit, *k*, Richtung |
| Zugfolge | [h, ∞), Reihenfolge fest nach Liniennummer | Mindestzugfolge |
        """
    )

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Netz**")
    lines = st.select_slider("Linien", options=list(C.LINES_OPTIONS), key="lines_select", help="Zahl der Linien des synthetischen Netzes (jede Linie hat 6 Halte, also 20 Ereignisse je Umlauf).")
    seed = st.number_input("Zufalls-Seed des Netzes", C.SEED_MIN, C.SEED_MAX, key="seed_input", step=1,
                           help="Ab diesem Seed sucht der Generator das erste Netz mit mindestens 3 Umsteigeverbindungen.")
    st.button("🎲 Neues Netz generieren", width="stretch", on_click=randomize_seed)
    st.markdown("**Verlangte Anschlüsse (Planungsannahme)**")
    st.caption("Verlangt werden nur die *k* am stärksten nachgefragten Umstiege (je Richtung gezählt); „gerichtet“ nimmt nur Zubringer von der kleineren zur größeren Liniennummer.")
    mode = st.radio("Richtung", list(C.TRANSFER_MODES), key="mode_radio", horizontal=True,
                    help="„alle“: Hin- und Rück-Anschluss derselben Relation zählen beide; „gerichtet“: nur kleine zu großer Liniennummer (die Mindestabstände sind azyklisch nach Konstruktion; erst Höchstwartezeiten schließen Kreise).")
    k = st.select_slider("Verlangte Anschlüsse k", options=list(C.K_OPTIONS), key="k_select", help="Die k am stärksten nachgefragten Umstiege, je Richtung gezählt (Gleichstand: feste Reihenfolge).")
    w = st.select_slider("Höchstwartezeit über der Mindestzeit (min)", options=list(C.W_OPTIONS), key="w_select",
                         help="Wie lange ein Anschluss höchstens länger als die Mindest-Umsteigezeit dauern darf; „unbegrenzt“ = kein Höchstabstand am Anschluss.")
    tmin = st.select_slider("Mindest-Umsteigezeit (min)", options=list(C.TRANSFER_MIN_OPTIONS), key="tmin_select", help="Kürzeste Zeit zwischen Ankunft und Abfahrt beim Umsteigen.")
    st.markdown("**Fahrt, Halt, Wende**")
    reserve = st.select_slider("Fahrzeitreserve (%)", options=list(C.RESERVE_OPTIONS), key="reserve_select", help="Höchstfahrzeit = Fahrzeit + Reserve (aufgerundet).")
    dwell = st.select_slider("Längste Haltezeit (min)", options=list(C.DWELL_HI_OPTIONS), key="dwell_select", help="Die kürzeste Haltezeit ist 1 Minute.")
    turn = st.select_slider("Höchstwende (min über der Mindest-Standzeit)", options=list(C.TURN_OPTIONS), key="turn_select",
                            help="Am Endpunkt wartet der Zug mindestens 4 Minuten, höchstens 4 + diese Zahl; „unbegrenzt“ = kein Höchstabstand an der Wende.")
    headway = st.select_slider("Mindestzugfolge (min)", options=list(C.HEADWAY_OPTIONS), key="headway_select",
                               help="Mindestabstand zweier Abfahrten auf demselben Abschnitt; die Reihenfolge ist fest (kleinere Liniennummer zuerst), 0 = aus. Experiment 4 vergleicht mit freier Reihenfolge.")

sync_query_params({key: st.session_state[key] for key in SETTING_SPECS})

settings = settings_from_widgets(mode, k, w, turn, reserve, dwell, tmin, headway)
a = _analysis(int(lines), int(seed), settings)
results = _results()
if results and results.get("meta", {}).get("hash") != SW.generator_hash():
    st.warning("Die vorgerechneten Messreihen (data/zab_results.json) stammen von einem anderen Stand des Rechenkerns; die Experimente 1 bis 5 zeigen sie nur zur Orientierung.")

# --- Das Netz ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🗺️ Das Netz und die verlangten Anschlüsse")
col_map, col_tab = st.columns([3, 2])
with col_map:
    st.plotly_chart(build_network_map(a), width="stretch", key="net_map")
    st.caption(f"{len(a.inst.lines)} Linien mit je 6 Halten, Umlauf mit Hin- und Rückfahrt: {a.n} Ereignisse und {len(a.arcs)} Abstandsbedingungen. "
               "Rote Ringe: Haltestellen, an denen ein verlangter Anschluss umsteigt. Netz und Nachfrage sind Annahmen des Generators.")
with col_tab:
    idx = M.transfer_arc_index(list(a.arcs))
    rows = []
    for rank, (key, ai) in enumerate(zip(a.transfer_keys, idx), 1):
        la, da, ka, lb, db, kb = key
        arc = a.arcs[ai]
        rows.append({"Rang": rank, "Nachfrage": fmt(a.inst.transfers[key]), "von": f"L{la + 1} {'Hin' if da == 'f' else 'Rück'} · Halt {a.inst.lines[la].stops[ka]} an",
                     "nach": f"L{lb + 1} {'Hin' if db == 'f' else 'Rück'} · Halt {a.inst.lines[lb].stops[kb]} ab", "Fenster (min)": f"[{arc.lo}, {hi_text(arc.hi)}]"})
    st.markdown(f"**Verlangte Anschlüsse: {len(rows)}** (die {'alle' if settings.k_transfers is None else settings.k_transfers} am stärksten nachgefragten Umstiege, je Richtung gezählt, Richtung „{mode}“)")
    st.dataframe(rows, hide_index=True, width="stretch", height=min(520, 40 + 35 * len(rows)))
    st.caption("Planungsannahme: Welche Anschlüsse ein Betreiber wirklich halten will, steht nicht in den Daten. Die Auswahl nach Nachfrage ist ein Ersatz.")

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ergebnis")
n_crit = len(S.critical(a.schedule.slack)) if a.feasible else 0
kind, text = ev.verdict_plan(a.feasible, len(a.transfer_keys), a.n, a.schedule.end if a.feasible else 0, n_crit, len(a.only_by_upper), a.excess)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Plan", "möglich" if a.feasible else "unmöglich")
if a.feasible:
    m2.metric("Frühestes Gesamtende", f"{a.schedule.end} min")
    m3.metric("Kritische Ereignisse", f"{n_crit} von {a.n}")
    m4.metric("Nur durch Höchstabstände kritisch", str(len(a.only_by_upper)), help="Ereignisse mit Spielraum 0, die die klassische Rechnung ohne Höchstabstände als unkritisch zeigt.")
else:
    m2.metric("Mindestabstände im Kreis", f"{a.excess['min_sum']} min")
    m3.metric("Höchstabstände im Kreis", f"{a.excess['max_sum']} min")
    m4.metric("Überschuss", f"{a.excess['excess']} min", help="Länge des Kreises: Mindestabstände minus Höchstabstände. Positiv heißt unmöglich.")

witness_rows = W.witness_rows(list(a.arcs), list(a.witness), a.labels) if not a.feasible else None
if a.feasible:
    line_no = st.selectbox("Linie im Diagramm", list(range(1, int(lines) + 1)), key=f"view_line_{int(lines)}", format_func=lambda i: f"Linie {i}")
    st.plotly_chart(build_event_chart(a, line_no - 1), width="stretch", key="event_chart")
    st.caption("Balken: von der frühesten bis zur spätesten Lage, die ein Ereignis haben darf, ohne das früheste Gesamtende zu verschieben. Raute: früheste Lage. "
               "Alle Ereignisse beginnen frühestens in Minute 0.")
else:
    st.markdown("**Der Zeuge: ein geschlossener Zug durch den Bedingungsgraphen mit positiver Länge**")
    st.plotly_chart(build_witness_waterfall(witness_rows), width="stretch", key="witness_chart")
    st.dataframe([{"Nr.": i + 1, "Bogenart": C.KIND_LABELS[r["art"]], "Seite": r["seite"], "von": r["von"], "nach": r["nach"], "Beitrag (min)": r["beitrag"]} for i, r in enumerate(witness_rows)],
                 hide_index=True, width="stretch")
    st.caption("Mindestabstand: das zweite Ereignis liegt mindestens so viel nach dem ersten (Beitrag +). Höchstabstand: Der Kreis geht rückwärts und gibt höchstens so viel zurück (Beitrag −). "
               "Die Summe ist die Länge des Kreises.")
st.download_button("📄 Planbericht als PDF herunterladen", data=generate_plan_pdf(a, text, witness_rows), file_name="zeitabstaende_plan.pdf", mime="application/pdf", key="pdf_download")

# --- Kernfrage -----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage: Ist dieser Plan überhaupt möglich?")
getattr(st, kind)(text)

st.markdown("---")

# --- Experiment 1 --------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment 1: Wie viele Anschlüsse verträgt das Netz?")
st.caption("Anteil möglicher Pläne über viele Netze des Generators, gegen die Zahl *k* der verlangten Anschlüsse und die Höchstwartezeit. Die Höchstwartezeit *W* ist über der Mindest-Umsteigezeit gemessen. Vorgerechnet: vier Blöcke zu je 250 Netzen, "
           "Mittel ± Standardabweichung über die Blöcke, übrige Regler auf Standard (keine Reserve, Haltezeit 1 bis 3, Mindest-Umsteigezeit 3, Wende unbegrenzt, Zugfolge aus).")
e1 = results.get("e1")
if not e1:
    st.info("Die vorgerechnete Messreihe fehlt (data/zab_results.json).")
else:
    shown_w = [None, 30, 15, 10, 0] if int(lines) in C.SWEEP_LINES_FULL else [None, 10]
    cols = st.columns(2)
    for col, md in zip(cols, ("alle", "gerichtet")):
        with col:
            curves = {}
            for wv in shown_w:
                curve = ev.e1_curve(e1, int(lines), md, wv)
                if curve:
                    curves["W unbegrenzt" if wv is None else f"W = {wv}"] = curve
            st.markdown(f"**Richtung „{md}“**")
            st.plotly_chart(build_e1_chart(curves), width="stretch", key=f"e1_chart_{md}")
    w_now = ev.w_value(w)
    curve_now = ev.e1_curve(e1, int(lines), mode, w_now)
    if curve_now:
        kind1, text1 = ev.verdict_e1(curve_now, int(lines), mode, "unbegrenzt" if w_now is None else f"{w_now} min")
        getattr(st, kind1)(text1)
        cell = next((c for c in curve_now if c[0] == ev.k_value(k)), None)
        if cell:
            st.caption(f"Ihre Einstellung (k = {k}, W = {w}): in der Messreihe {pct_std(cell[1:])} der Netze mit {int(lines)} Linien möglich; Ihr Netz ist {'möglich' if a.feasible else 'unmöglich'}.")
    else:
        st.info(f"Für {int(lines)} Linien sind nur die Höchstwartezeiten „unbegrenzt“ und 10 min gemessen; stellen Sie eine davon ein, um das Verdikt zu sehen.")

st.markdown("---")

# --- Experiment 2 --------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment 2: Wer kippt den Plan?")
st.caption("Ein unmöglicher Plan hat einen **Zeitkreis**, wenn er schon ohne jeden Höchstabstand unmöglich ist; sonst wird er erst durch Höchstabstände unmöglich. "
           "Dieser Test hängt nicht von der Reihenfolge der Bögen ab. Dazu liefert der Löschfilter eine unmögliche Bogenmenge (jeden Bogen probeweise entfernen, bleibt der Plan unmöglich, "
           "bleibt er weg), aus der kein Bogen mehr fehlen darf (inklusionsminimal, nicht eindeutig: welche Menge übrig bleibt, hängt von der Bogenreihenfolge ab). "
           "Bei einem Zeitkreis-Plan sucht er im Plan ohne Höchstabstände, sonst im Plan selbst. *W* in der Tabelle: Höchstwartezeit über der Mindest-Umsteigezeit.")
e2c = results.get("e2_cycles")
if e2c:
    rows2 = ev.e2_cycle_rows(e2c)
    st.dataframe([{"Einstellung (6 Linien)": r["label"], "unmögliche Pläne": f"{r['unmoeglich']} von {r['von']}", "davon schon ohne jeden Höchstabstand unmöglich (Zeitkreis)": r["zeitkreis"],
                   "davon erst durch Höchstabstände unmöglich": r["nur_hoechst"], "Höchstabstände im gefundenen Kreis (Median)": "–" if r["rueckkanten_median"] is None else fmt(r["rueckkanten_median"], 1)}
                  for r in rows2], hide_index=True, width="stretch")
    getattr(st, "info")(ev.verdict_e2(rows2[0])[1])
e2r = results.get("e2_regler")
if e2r:
    st.markdown("**Welcher Regler hilft?** Anteil möglicher Pläne über die Werte eines Reglers (6 Linien, vier Blöcke zu je 250 Netzen, übrige Regler auf Standard):")
    c1, c2 = st.columns(2)
    regler = c1.selectbox("Regler", list(ev.REGLER_LABELS), format_func=lambda r: ev.REGLER_LABELS[r], key="e2_regler_select")
    base = c2.selectbox("Anschlussliste", [(md, kk, ww) for md, kk, ww in SW.E2_REGLER_BASES],
                        format_func=lambda t: f"{t[0]}, k = {t[1]}, W {'unbegrenzt' if t[2] is None else '= ' + str(t[2])}", key="e2_base_select")
    curve = ev.regler_curve(e2r, base[0], base[1], base[2], regler)
    st.plotly_chart(build_bar_chart([c[0] for c in curve], {"Anteil möglich": ([c[1] for c in curve], [c[2] for c in curve])}, "Anteil möglicher Pläne",
                                    y_range=[0, 1.05], x_title=ev.REGLER_LABELS[regler]), width="stretch", key="e2_regler_chart")
if not a.feasible:
    keep, info = _minimal(int(lines), int(seed), settings)
    st.info(f"**Ihr Netz:** Von {len(a.arcs)} Bedingungen bilden {len(keep)} eine unmögliche Menge, aus der kein Bogen mehr fehlen darf, darunter {info['transfer']} Anschlüsse; "
            f"der Kreis darin hat {info['hi']} Höchstabstände. Der Plan ist {'schon ohne jeden Höchstabstand unmöglich (Zeitkreis)' if info['time_cycle'] else 'nur durch Höchstabstände unmöglich (kein Zeitkreis)'}. Bogenarten im Kreis: "
            + ", ".join(f"{C.KIND_LABELS[kk]} {vv}" for kk, vv in info["kinds"].items()) + ".")
else:
    st.caption("Ihr Netz ist möglich: Es gibt keine unmögliche Menge. Stellen Sie z. B. „Zeitkreis“ im Schnellstart ein.")

st.markdown("---")

# --- Experiment 3 --------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment 3: Spielraum gegen die klassische Rechnung")
st.caption("Kritisch heißt Spielraum 0. Die klassische Rechnung des kritischen Pfades kennt nur Mindestabstände. Mit Höchstabständen werden zusätzliche Ereignisse kritisch, "
           "die sie als unkritisch zeigt. Vorgerechnet über die möglichen Pläne von je vier Blöcken zu 250 Netzen.")
e3 = results.get("e3")
if e3:
    nl3 = int(lines) if int(lines) in (6, 10) else 6          # vorgerechnet sind 6 und 10 Linien
    if nl3 != int(lines):
        st.caption(f"Für {int(lines)} Linien liegt keine Messreihe vor; gezeigt sind 6 Linien.")
    rows3 = [r for r in ev.e3_rows(e3) if r["nl"] == nl3]
    st.dataframe([{"Einstellung": r["label"], "mögliche Pläne": f"{r['machbar']} von 1000", "kritisch (mit Höchstabständen)": pct_std((r["voll"], r["voll_std"])),
                   "kritisch (klassisch)": pct(r["cpm"]), "nur durch Höchstabstände": f"{fmt(100 * r['nur_hoechst'])} Punkte",
                   "Spielraum 0 / 10 / 25 / 50 / 75 / 90 / 100 % (min)": " / ".join(str(q) for q in r["quantile"])} for r in rows3], hide_index=True, width="stretch")
    st.plotly_chart(build_bar_chart([r["label"] for r in rows3], {"mit Höchstabständen": [r["voll"] for r in rows3], "klassisch (nur Mindestabstände)": [r["cpm"] for r in rows3]},
                                    "Anteil kritischer Ereignisse", height=340), width="stretch", key="e3_chart")
    first = rows3[0]
    st.info(f"Bei „{first['label']}“ ({nl3} Linien) sind {pct(first['voll'])} der Ereignisse kritisch, klassisch gerechnet {pct(first['cpm'])}: "
            f"{fmt(100 * first['nur_hoechst'])} Prozentpunkte der Ereignisse sind erst durch Höchstabstände kritisch; umgekehrt sind manche klassisch kritische Ereignisse mit Höchstabständen "
            f"nicht mehr kritisch, der Unterschied der beiden Anteile ist deshalb kleiner. Bei „alle, k = 4, W unbegrenzt“ ist der Zuwachs "
            f"{fmt(100 * next(r for r in rows3 if r['label'].startswith('alle, k = 4, W unbegrenzt'))['nur_hoechst'])} Punkte.")
if a.feasible:
    st.caption(f"Ihr Netz: {n_crit} von {a.n} Ereignissen sind kritisch, {len(a.only_by_upper)} davon nur durch Höchstabstände"
               + (": " + "; ".join(a.labels[e] for e in a.only_by_upper[:6]) + (" …" if len(a.only_by_upper) > 6 else "") if a.only_by_upper else "."))
else:
    st.caption("Ihr Netz ist unmöglich: Spielraum gibt es nur bei möglichen Plänen.")

st.markdown("---")

# --- Experiment 4 --------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment 4: Zugfolge – Zahl oder Reihenfolge?")
st.caption("Die Mindestzugfolge *h* verbietet zwei Abfahrten auf demselben Abschnitt zu nah beieinander. Im Hauptplan ist die **Reihenfolge fest** (kleinere Liniennummer zuerst, "
           "Planungsannahme). Mit freier Reihenfolge ist es ein Entweder-oder je Abschnittspaar, also ein Job-Shop-Problem (`job-shop-demo`).")
e4 = results.get("e4")
if e4:
    cfgs = sorted({(r["mode"], r["k"], r["W"]) for r in e4}, key=lambda t: (t[0], t[1], t[2] is not None, t[2] or 0))
    cfg = st.selectbox("Anschlussliste", cfgs, format_func=lambda t: f"{t[0]}, k = {t[1]}, W {'unbegrenzt' if t[2] is None else '= ' + str(t[2])}", key="e4_cfg_select")
    rows4 = ev.e4_rows(e4, *cfg)
    st.plotly_chart(build_bar_chart([f"h = {r[0]}" for r in rows4], {"Reihenfolge fest": [r[1] for r in rows4], "Reihenfolge frei": [r[2] for r in rows4]},
                                    "Anteil möglicher Pläne", y_range=[0, 1.05]), width="stretch", key="e4_chart")
    getattr(st, "info")(ev.verdict_e4(rows4)[1] + f" (6 Linien, vier Blöcke zu je {C.SWEEP_SMALL_PER} Netzen, im Mittel {fmt(rows4[-1][3], 1)} Abschnittspaare.)")
if settings.headway > 0:
    sig = (int(lines), int(seed), settings)
    if st.button("▶️ Freie Reihenfolge für dieses Netz prüfen", key="run_free", help=f"CP-SAT, Zeitlimit {C.CPSAT_LIVE_SECONDS:.0f} s"):
        with st.spinner(f"Freie Reihenfolge wird gesucht (Zeitlimit {C.CPSAT_LIVE_SECONDS:.0f} s) …"):
            st.session_state["free_result"] = (sig, B.free_order_feasible(a.inst, settings, limit=C.CPSAT_LIVE_SECONDS, workers=1))
    res = st.session_state.get("free_result")
    if res and res[0] == sig:
        free_ok, pairs = res[1]
        fixed_word = "möglich" if a.feasible else "unmöglich"
        free_word = "nicht bewiesen (Zeitlimit)" if free_ok is None else ("möglich" if free_ok else "unmöglich")
        st.info(f"Ihr Netz mit h = {settings.headway} min: feste Reihenfolge {fixed_word}, freie Reihenfolge {free_word} ({pairs} Abschnittspaare).")
else:
    st.caption("Stellen Sie links eine Mindestzugfolge größer 0 ein oder laden Sie das Preset „Zugfolge: Reihenfolge entscheidet“, um dieses Netz mit freier Reihenfolge zu prüfen.")

st.markdown("---")

# --- Experiment 5 --------------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment 5: Zum Takt – dieselben Abstände modulo T")
st.caption(f"Dieselben Bögen, aber periodisch: Die Abstände gelten nur modulo *T* = {C.T} min ($\\pi_v - \\pi_u + T\\,p = x$ mit $x \\in [l, h]$). Jede einmalige Lösung, modulo *T* genommen, "
           "löst das periodische System; einmalig möglich heißt also periodisch möglich, aber nicht umgekehrt.")
per_ok, cyc_sum = _periodic(int(lines), int(seed), settings)
if per_ok is None:
    st.warning(f"Die periodische Machbarkeit ist in {C.CPSAT_LIVE_SECONDS:.0f} s nicht bewiesen worden.")
elif a.feasible:
    st.success("Ihr Netz: einmalig **möglich**, damit auch periodisch möglich (Satz).")
elif per_ok:
    st.success(f"Ihr Netz: einmalig **unmöglich**, periodisch (T = {C.T}) **möglich**." + (
        f" Entlang des Kreises aus dem Abschnitt „Ergebnis“ summieren sich die tatsächlichen Abstände des periodischen Plans auf **{cyc_sum} min** = {cyc_sum // C.T} × {C.T} min, ein Vielfaches des Taktes." if cyc_sum else ""))
else:
    st.error(f"Ihr Netz: einmalig und periodisch (T = {C.T}) **unmöglich**: Auch der Takt rettet nicht jeden Plan.")
e5 = results.get("e5_pa")
if e5:
    c1, c2 = st.columns(2)
    combos = sorted({(r["mode"], r["k"]) for r in e5}, key=lambda t: (t[0], t[1] is None, t[1] or 0))
    sel = c1.selectbox("Anschlussliste", combos, format_func=lambda t: f"{t[0]}, k = {'alle' if t[1] is None else t[1]}", key="e5_combo_select")
    rows5 = ev.e5_pa_rows(e5, *sel)
    st.plotly_chart(build_bar_chart(["unbegrenzt" if r["W"] is None else str(r["W"]) for r in rows5],
                                    {"einmalig": ([r["einmalig"][0] for r in rows5], [r["einmalig"][1] for r in rows5]),
                                     f"periodisch (T = {C.T})": ([r["periodisch"][0] for r in rows5], [r["periodisch"][1] for r in rows5])},
                                    "Anteil möglicher Pläne", y_range=[0, 1.1], x_title="Höchstwartezeit über der Mindestzeit (min)"), width="stretch", key="e5_chart")
    getattr(st, "info")(ev.verdict_e5(rows5[0])[1] + f" (Richtung „{sel[0]}“, k = {'alle' if sel[1] is None else sel[1]}, Höchstwartezeit unbegrenzt; 6 Linien.)")
e5r = results.get("e5_rest")
if e5r:
    st.markdown("**Was hält der einmalige Plan, wenn Anschlüsse gestrichen werden dürfen?** Größter Anteil der verlangten Nachfrage, den ein einmaliger Plan halten kann "
                "(alle Anschlüsse beider Richtungen unter den *k* am stärksten nachgefragten Umstiegen, je Richtung gezählt; CP-SAT gegen Greedy: Zeuge suchen, billigsten Anschluss im Kreis streichen; wo das Zeitlimit nicht reichte, ist der CP-SAT-Wert eine untere Schranke):")
    st.dataframe([{"k": "alle" if r["k"] is None else r["k"], "Höchstwartezeit (über der Mindest-Umsteigezeit)": "unbegrenzt" if r["W"] is None else r["W"], "größter gefundener Anteil (CP-SAT, Mittel ± Std über Blöcke)": pct_std(r["exakt"]),
                   "Greedy": pct_std(r["greedy"]), "periodisch alle haltbar": f"{r['periodisch_alle']} von {r['von']}", "bewiesen optimal": f"{r['optimal']} von {r['von']}"}
                  for r in ev.e5_rest_rows(e5r)], hide_index=True, width="stretch")
k_now = ev.k_value(k)
if mode == "alle" and (k_now is not None and k_now <= C.MAX_KEPT_LIVE_K):
    sig5 = (int(lines), int(seed), settings)
    if st.button("▶️ Größten haltbaren Anteil für dieses Netz berechnen", key="run_kept", help=f"CP-SAT mit {C.CPSAT_WORKERS} Arbeitern, Zeitlimit {C.CPSAT_LIVE_SECONDS:.0f} s"):
        with st.spinner(f"Optimaler Anteil wird gesucht (Zeitlimit {C.CPSAT_LIVE_SECONDS:.0f} s) …"):
            st.session_state["kept_result"] = (sig5, B.max_kept_weight(a.inst, settings, limit=C.CPSAT_LIVE_SECONDS, workers=C.CPSAT_WORKERS),
                                               B.greedy_kept_weight(a.inst, settings))
    res5 = st.session_state.get("kept_result")
    if res5 and res5[0] == sig5:
        (kept, status), greedy = res5[1], res5[2]
        st.info("Ihr Netz: Der einmalige Plan kann " + ("höchstens" if status == "OPTIMAL" else "mindestens") + f" **{pct(kept)}** der verlangten Nachfrage halten"
                + ("" if status == "OPTIMAL" else " (Zeitlimit: Optimum nicht bewiesen)") + f"; der Greedy hält {pct(greedy) if greedy is not None else '–'}.")
else:
    st.caption("Der größte haltbare Anteil wird live nur für Richtung „alle“ und k bis " + str(C.MAX_KEPT_LIVE_K) + " gerechnet; größere Fälle stehen in der Tabelle oben.")

st.markdown("---")

# --- Grenzen -------------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
_all_text = ev.sentence_all_transfers(results["e1"]) if results.get("e1") else "Die Messreihe zu Experiment 1 fehlt."
_free_text = ev.sentence_free_order(results["e4"]) if results.get("e4") else "Die Messreihe zu Experiment 4 fehlt."
st.markdown(
    f"""
| Annahme | Was passiert, wenn sie verletzt ist | Wer setzt an |
|---|---|---|
| **Ein Umlauf je Linie, keine Wiederholung** | Der Plan gilt einmal; ein Takt wiederholt ihn, und die Abstände gelten dann nur modulo *T* (Experiment 5). | Experiment 5 zeigt den Sprung, löst ihn nicht |
| **Anschlüsse: die *k* am stärksten nachgefragten Umstiege (je Richtung gezählt), wahlweise nur „gerichtet“** | Planungsannahme, kein Befund über echte Betriebe. {_all_text} | – |
| **Ganzzahlige Minuten, feste Fenster** | Verspätungen, Zufallsdauern und Fahrzeuge (Umlauf des Fahrzeugs über mehrere Linien) kommen nicht vor. | `kritischer-pfad-demo` (unsichere Dauern) |
| **Zugfolge mit fester Reihenfolge nach Liniennummer** | {_free_text} | `job-shop-demo`, `shifting-bottleneck-demo` |
| **Anschlüsse müssen gehalten werden** | Streichen bis zur Machbarkeit (Feedback-Arc-Set) lässt sich exakt oder per Greedy rechnen (Experiment 5); die Demo wählt keinen Plan. | `kreise-aufloesen-demo` |
| **Kein Zeit-Kosten-Abgleich** | Beschleunigen gegen Geld (ein lineares Programm) kommt nicht vor. | – |
    """
)

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/zeitabstaende-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind Ereignisse (Abfahrt und Ankunft je Halt und Richtung) und für Paare von Ereignissen ein Mindest- und ein Höchstabstand. Gesucht sind Zeitpunkte in ganzen Minuten, die alle Abstände einhalten, und, wenn es sie gibt, früheste und späteste Lage jedes Ereignisses.

| Symbol | Bedeutung |
|---|---|
| $x_e$ | Zeitpunkt des Ereignisses $e$ in Minuten |
| $l_{uv}$, $h_{uv}$ | Mindest- und Höchstabstand des Bogens $(u, v)$ |
| $w(C)$ | Länge eines Kreises $C$ im Bedingungsgraphen |
| $L(a \to b)$ | Länge des längsten Weges von $a$ nach $b$ |
| $z$, $t$ | Quelle und Senke des Bedingungsgraphen |
| $x_e^{\min}$, $x_e^{\max}$ | früheste und späteste Lage von $e$ |
| $D$, $s_e$ | frühestes Gesamtende, Spielraum von $e$ (kritisch heißt $s_e = 0$) |
| $T$, $\pi_e$, $p_{uv}$ | Takt, Phase von $e$ und ganzzahlige Zahl voller Takte auf dem Bogen $(u, v)$ |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/zeitabstaende-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        r"""
**Gegeben.** Ereignisse $e = 1, \dots, n$ (Abfahrt und Ankunft je Halt und Richtung) und Bögen $(u, v)$ mit Mindestabstand $l_{uv}$ und Höchstabstand $h_{uv}$ (möglich: $h_{uv} = \infty$).
**Gesucht.** Zeitpunkte $x_e \ge 0$ (ganze Minuten) mit

$$ l_{uv} \le x_v - x_u \le h_{uv} \qquad \text{für alle Bögen } (u, v). $$

**Bedingungsgraph.** Je Bogen zwei Kanten:

$$ w(u \to v) = l_{uv}, \qquad w(v \to u) = -h_{uv}. $$

**Satz (Machbarkeit).** Ein Plan existiert genau dann, wenn der Bedingungsgraph keinen Kreis $C$ positiver Länge enthält:

$$ w(C) = \sum_{\text{Mindestabstände in } C} l \;-\; \sum_{\text{Höchstabstände in } C} h \;\le\; 0 . $$

*Beweisidee, „nur wenn“:* Addiert man die Ungleichungen $x_v - x_u \ge w$ entlang eines Kreises, hebt sich die linke Seite auf, es bleibt $0 \ge w(C)$.

**Lagen.** Mit Quelle $z$ ($x_z = 0$) und Senke $t$ sowie $L(a \to b)$ als Länge des längsten Weges:

$$ x_e^{\min} = L(z \to e), \qquad D = \max_e x_e^{\min}, \qquad x_e^{\max} = D - L(e \to t), \qquad s_e = x_e^{\max} - x_e^{\min}. $$

Ein Ereignis ist **kritisch**, wenn $s_e = 0$. Die klassische Rechnung ($h_{uv} = \infty$ für alle Bögen) ergibt dieselben Formeln ohne die Rückkanten.

**Periodisch (Experiment 5).** Mit Takt $T$, Phasen $\pi_e \in \{0, \dots, T-1\}$ und ganzzahligem $p_{uv}$:

$$ \pi_v - \pi_u + T\,p_{uv} = x_{uv}, \qquad x_{uv} \in [l_{uv}, h_{uv}]. $$

Jede einmalige Lösung $x$ liefert mit $\pi_e = x_e \bmod T$ eine periodische.

**Zugfolge (Experiment 4).** Fest: $x_b - x_a \ge h$ für die Reihenfolge nach Liniennummer. Frei: je Abschnittspaar

$$ x_b - x_a \ge h \quad \text{oder} \quad x_a - x_b \ge h . $$

**Haltbarer Anteil (Experiment 5).** Mit Nachfrage $d_a$ und Entscheidungsvariable $z_a \in \{0, 1\}$ je Anschluss:

$$ \max \sum_a d_a z_a \quad \text{mit} \quad z_a = 1 \Rightarrow l_a \le x_{v_a} - x_{u_a} \le h_a . $$

        """
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html)."
)
