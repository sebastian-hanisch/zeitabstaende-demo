"""Planbericht als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen; Gedankenstrich, Pfeile, Mathezeichen und Emoji nicht, `_clean` ersetzt sie).

Bei einem möglichen Plan: Einstellungen, Kennzahlen und je Linie die früheste und späteste Lage jedes Ereignisses. Bei einem unmöglichen Plan:
Einstellungen und der Zeuge (der Kreis positiver Länge) mit der Rechnung. Aufbau nach tkt_pdf_export.py der Fall-Demo (angepasst).
"""
from __future__ import annotations

from fpdf import FPDF

from zab_constants import KIND_LABELS

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": ".", "∞": "unbegrenzt", "„": '"', "“": '"'}


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def _fmt_hi(hi) -> str:
    return "unbegrenzt" if hi is None else str(hi)


def settings_lines(a) -> list:
    s = a.settings
    return [
        f"Netz: {a.lines} Linien, Zufalls-Seed {a.seed} (verwendet: {a.used_seed}); {a.n} Ereignisse, {len(a.arcs)} Abstandsbedingungen",
        f"Anschlüsse: {len(a.transfer_keys)} verlangt (Richtung {s.transfers}, die {'alle' if s.k_transfers is None else s.k_transfers} am stärksten nachgefragten Umstiege, je Richtung gezählt), "
        f"Mindest-Umsteigezeit {s.transfer_min} min, Höchstwartezeit darüber {_fmt_hi(s.wait_max)} min",
        f"Fahrzeitreserve {s.reserve_pct} %, Haltezeit {s.dwell_lo} bis {s.dwell_hi} min, Höchstwende über der Mindest-Standzeit {_fmt_hi(s.turn_extra)} min, "
        f"Mindestzugfolge {s.headway} min (Reihenfolge fest nach Liniennummer)",
        "Annahmen, keine Echtdaten: synthetisches Netz; die Anschlussliste (die k am stärksten nachgefragten Umstiege, je Richtung gezählt) ist eine Planungsannahme.",
    ]


def generate_plan_pdf(a, verdict_text: str, witness_rows=None) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean("Zeitabstände: Plan aus Mindest- und Höchstabständen"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in settings_lines(a):
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 5, _clean(verdict_text.replace("**", "")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    if a.schedule is None:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _clean("Der Kreis positiver Länge (Zeuge)"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 8)
        for text, w in (("Art", 22), ("Seite", 30), ("von", 55), ("nach", 55), ("Beitrag", 20)):
            pdf.cell(w, 6, text, border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        for r in witness_rows or []:
            for text, w in ((KIND_LABELS[r["art"]], 22), (r["seite"], 30), (r["von"], 55), (r["nach"], 55), (f"{r['beitrag']:+d}", 20)):
                pdf.cell(w, 5.5, _clean(text), border=1)
            pdf.ln()
        return bytes(pdf.output())
    sch = a.schedule
    for li in range(len(a.inst.lines)):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, _clean(f"Linie {li + 1}: Halte {' - '.join(str(s) for s in a.inst.lines[li].stops)}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 8)
        for text, w in (("Ereignis", 70), ("früh", 22), ("spät", 22), ("Spielraum", 24)):
            pdf.cell(w, 5.5, _clean(text), border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
        for e in range(a.n):
            if a.event_line[e] != li:
                continue
            for text, w in ((a.labels[e].split(" ", 1)[1], 70), (str(sch.earliest[e]), 22), (str(sch.latest[e]), 22), (str(sch.slack[e]), 24)):
                pdf.cell(w, 5, _clean(text), border=1)
            pdf.ln()
        pdf.ln(2)
    return bytes(pdf.output())
