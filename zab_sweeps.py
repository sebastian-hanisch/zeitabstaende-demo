"""Messreihen über viele Netze (vier Blöcke zu je 250 Netzen des Generators), die in `data/zab_results.json` vorgerechnet liegen.

Die Netze sind dieselben für alle Zellen: Netz Nr = 250 * Block + i, Seed = 3000 + 100 * Nr (der Abstand 100 verhindert, dass die Seed-Suche der
Netzerzeugung, bis +49, dasselbe Netz zweimal liefert). Ergebnisse werden als Zähler je Block gespeichert; ausgewiesen wird später Mittel ± Standard-
abweichung über die vier Blöcke (`mean_std`). Alle Messungen laufen mit dem Code dieses Repos (`tools/sweep.py` ruft diese Funktionen auf);
`generator_hash()` bindet die Datei an den Stand des Rechenkerns (Tests melden eine veraltete Datei).
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import statistics
import tokenize
from pathlib import Path

import numpy as np

import zab_bridge as B
import zab_constants as C
import zab_graph as G
import zab_model as M
import zab_schedule as S
import zab_witness as W
from zab_model import Settings
from zab_network import make_instance

ROOT = Path(__file__).resolve().parent
HASHED_MODULES = ("zab_rng.py", "zab_network.py", "zab_model.py", "zab_graph.py", "zab_schedule.py", "zab_witness.py", "zab_bridge.py", "zab_sweeps.py")


def normalized_source(src: str) -> str:
    """Quelltext ohne Docstrings, Kommentare, Leerzeilen und überzählige Leerzeichen. Bewusst textbasiert statt `ast.dump`: der Syntaxbaum-Ausdruck ändert
    sich zwischen Python-Versionen (die CI läuft mit einer anderen Version als der Rechner der Messung), der normalisierte Text nicht."""
    tree = ast.parse(src)
    doc_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                doc_lines.update(range(first.lineno, first.end_lineno + 1))
    lines = src.splitlines()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            row, col = tok.start
            lines[row - 1] = lines[row - 1][:col]
    kept = [" ".join(line.split()) for i, line in enumerate(lines, 1) if i not in doc_lines]
    return "\n".join(line for line in kept if line)


def generator_hash() -> str:
    """Hash über den Rechenkern (normalisierter Quelltext ohne Kommentare und Docstrings, unabhängig von Zeilenenden und Python-Version): ändert sich der Kern, ist die Ergebnisdatei veraltet."""
    h = hashlib.sha256()
    for name in HASHED_MODULES:
        h.update(name.encode() + b"\0" + normalized_source((ROOT / name).read_text(encoding="utf-8")).encode() + b"\0")
    return h.hexdigest()[:16]


def net_seed(number: int) -> int:
    return C.SWEEP_BASE + C.SWEEP_STEP * number


def block_instances(n_lines: int, per_block: int = C.SWEEP_PER, blocks: int = C.SWEEP_BLOCKS):
    """Liste von Blöcken, jeder mit `per_block` Netzen; Block b enthält die Netze Nr = 250 * b + i (i < per_block)."""
    return [[make_instance(n_lines, net_seed(C.SWEEP_PER * b + i))[0] for i in range(per_block)] for b in range(blocks)]


def mean_std(values):
    """Mittel und Standardabweichung (Grundgesamtheit) über die Blöcke."""
    v = [float(x) for x in values]
    return statistics.fmean(v), statistics.pstdev(v)


def share_per_block(counts, per_block):
    return [c / per_block for c in counts]


def feasible_counts(blocks, s: Settings):
    """Zahl möglicher Pläne je Block."""
    out = []
    for blk in blocks:
        c = 0
        for inst in blk:
            n, arcs = M.build_arcs(inst, s)
            c += G.is_feasible(n, arcs)
        out.append(c)
    return out


# ------------------------------------------------------------------ E1: Anteil möglicher Pläne gegen k, W und Linienzahl
def grid_e1(progress=None):
    recs = []
    plan = [(nl, C.SWEEP_W_FULL) for nl in C.SWEEP_LINES_FULL] + [(nl, C.SWEEP_W_SHORT) for nl in C.SWEEP_LINES_SHORT]
    for nl, ws in plan:
        blocks = block_instances(nl)
        for mode in ("alle", "gerichtet"):
            for k in C.SWEEP_K:
                for w in ws:
                    cnt = feasible_counts(blocks, Settings(transfers=mode, k_transfers=k, wait_max=w))
                    recs.append({"nl": nl, "mode": mode, "k": k, "W": w, "feasible": cnt, "n": C.SWEEP_PER})
        if progress:
            progress(f"e1 nl={nl} fertig")
    return recs


# ------------------------------------------------------------------ E2: Wer macht den Plan unmöglich (Kreise), Wirkung der übrigen Regler
E2_CYCLE_CONFIGS = [
    ("alle, k = 4, W unbegrenzt", dict(transfers="alle", k_transfers=4, wait_max=None)),
    ("alle, k = 4, W = 10", dict(transfers="alle", k_transfers=4, wait_max=10)),
    ("alle, k = 8, W unbegrenzt", dict(transfers="alle", k_transfers=8, wait_max=None)),
    ("alle, k = 8, W = 10", dict(transfers="alle", k_transfers=8, wait_max=10)),
    ("gerichtet, k = 4, W = 30", dict(transfers="gerichtet", k_transfers=4, wait_max=30)),
    ("gerichtet, k = 4, W = 10", dict(transfers="gerichtet", k_transfers=4, wait_max=10)),
    ("gerichtet, k = 8, W = 10", dict(transfers="gerichtet", k_transfers=8, wait_max=10)),
]


def grid_e2_cycles(progress=None):
    blocks = block_instances(6, C.SWEEP_SMALL_PER)
    recs = []
    for label, kw in E2_CYCLE_CONFIGS:
        s = Settings(**kw)
        rows, total = [], 0
        for blk in blocks:
            for inst in blk:
                n, arcs = M.build_arcs(inst, s)
                total += 1
                info = W.explain_infeasible(n, arcs)
                if info is not None:
                    rows.append(info)
        recs.append({"label": label, "settings": kw, "von": total, "unmoeglich": len(rows),
                     "zeitkreis": sum(1 for r in rows if r["time_cycle"]), "nur_hoechstabstaende": sum(1 for r in rows if not r["time_cycle"]),
                     "anschluesse_im_kreis": {str(c): sum(1 for r in rows if r["transfer"] == c) for c in sorted({r["transfer"] for r in rows})},
                     "rueckkanten_median": statistics.median(r["hi"] for r in rows) if rows else None,
                     "kreis_kanten_median": statistics.median(r["len"] for r in rows) if rows else None,
                     "bogen_median": statistics.median(r["iis"] for r in rows) if rows else None})
        if progress:
            progress(f"e2 {label}")
    return recs


E2_REGLER = {
    "reserve_pct": [0, 10, 25, 50, 100, 200],
    "turn_extra": [None, 60, 30, 15, 5, 0],
    "dwell_hi": [1, 3, 10],
    "transfer_min": [0, 3, 8, 12],
}
E2_REGLER_BASES = [("alle", 4, None), ("gerichtet", 4, 15)]


def grid_e2_regler(progress=None):
    blocks = block_instances(6)
    recs = []
    for mode, k, w in E2_REGLER_BASES:
        for name, vals in E2_REGLER.items():
            for v in vals:
                kw = {"transfers": mode, "k_transfers": k, "wait_max": w, name: v}
                recs.append({"mode": mode, "k": k, "W": w, "regler": name, "wert": v, "feasible": feasible_counts(blocks, Settings(**kw)), "n": C.SWEEP_PER})
        if progress:
            progress(f"e2 regler {mode}")
    return recs


# ------------------------------------------------------------------ E3: Spielraum und kritische Ereignisse gegen die klassische Rechnung
E3_CONFIGS = [
    ("gerichtet, k = 4, W = 30", dict(transfers="gerichtet", k_transfers=4, wait_max=30)),
    ("gerichtet, k = 6, W = 30", dict(transfers="gerichtet", k_transfers=6, wait_max=30)),
    ("gerichtet, k = 3, W = 15", dict(transfers="gerichtet", k_transfers=3, wait_max=15)),
    ("alle, k = 4, W unbegrenzt", dict(transfers="alle", k_transfers=4, wait_max=None)),
    ("alle, k = 4, W = 30", dict(transfers="alle", k_transfers=4, wait_max=30)),
    ("alle, k = 2, W = 15", dict(transfers="alle", k_transfers=2, wait_max=15)),
]


def grid_e3(progress=None):
    recs = []
    for nl in (6, 10):
        blocks = block_instances(nl)
        for label, kw in E3_CONFIGS:
            s = Settings(**kw)
            per_block, all_slack, crit_lines = [], [], []
            for blk in blocks:
                feas = crit_full = crit_cpm = only = ev_tot = 0
                for inst in blk:
                    n, arcs = M.build_arcs(inst, s)
                    full, _w = S.schedule(n, arcs)
                    if full is None:
                        continue
                    cpm_crit, _cpm = S.critical_cpm(n, arcs)
                    sl = np.array(full.slack)
                    feas += 1
                    ev_tot += n
                    crit_full += int((sl == 0).sum())
                    crit_cpm += len(cpm_crit)
                    only += len(set(S.critical(full.slack)) - set(cpm_crit))
                    all_slack.extend(sl.tolist())
                    lines = M.event_line(inst)
                    crit_lines.append(len({lines[e] for e in range(n) if sl[e] == 0}))
                per_block.append({"machbar": feas, "events": ev_tot, "krit_voll": crit_full, "krit_cpm": crit_cpm, "nur_hoechst": only})
            q = np.percentile(np.array(all_slack) if all_slack else np.array([0]), [0, 10, 25, 50, 75, 90, 100])
            recs.append({"label": label, "settings": kw, "nl": nl, "blocks": per_block, "spielraum_quantile": [int(x) for x in q],
                         "linien_mit_kritischem_ereignis_mittel": statistics.fmean(crit_lines) if crit_lines else None,
                         "plaene_mit_einer_kritischen_linie": sum(1 for c in crit_lines if c == 1), "plaene_machbar": len(crit_lines)})
            if progress:
                progress(f"e3 nl={nl} {label}")
    return recs


# ------------------------------------------------------------------ E4: Mindestzugfolge, Reihenfolge fest oder frei
E4_CONFIGS = [("alle", 4, None), ("alle", 4, 10), ("gerichtet", 4, 30), ("gerichtet", 6, 30), ("alle", 2, None)]
E4_HEADWAYS = (0, 2, 4, 10)


def grid_e4(progress=None):
    blocks = block_instances(6, C.SWEEP_SMALL_PER)
    recs = []
    for mode, k, w in E4_CONFIGS:
        for h in E4_HEADWAYS:
            fixed, free, unknown, pairs = [], [], 0, []
            for blk in blocks:
                f1 = f2 = 0
                for inst in blk:
                    s = Settings(transfers=mode, k_transfers=k, wait_max=w, headway=h)
                    n, arcs = M.build_arcs(inst, s)
                    f1 += G.is_feasible(n, arcs)
                    r, npairs = B.free_order_feasible(inst, s, limit=10.0, workers=1)
                    pairs.append(npairs)
                    if r is None:
                        unknown += 1
                        r = False
                    f2 += r
                fixed.append(f1)
                free.append(f2)
            recs.append({"mode": mode, "k": k, "W": w, "h": h, "n": C.SWEEP_SMALL_PER, "fest": fixed, "frei": free, "unbekannt": unknown,
                         "abschnittspaare_mittel": statistics.fmean(pairs)})
            if progress:
                progress(f"e4 {mode} k={k} W={w} h={h}")
    return recs


# ------------------------------------------------------------------ E5: einmalig gegen periodisch, größter haltbarer Anteil
E5_PA = [("alle", (2, 4, 8, None)), ("gerichtet", (4, 8))]
E5_W = (None, 30, 15, 10, 5, 0)


def grid_e5_pa(progress=None):
    blocks = block_instances(6, C.SWEEP_SMALL_PER)
    recs = []
    for mode, ks in E5_PA:
        for k in ks:
            for w in E5_W:
                s = Settings(transfers=mode, k_transfers=k, wait_max=w)
                once, per, viol, rescued, unknown = [], [], 0, 0, 0
                for blk in blocks:
                    a1 = a2 = 0
                    for inst in blk:
                        n, arcs = M.build_arcs(inst, s)
                        f1 = G.is_feasible(n, arcs)
                        f2 = B.periodic_feasible(n, arcs, C.T, limit=10.0, workers=1)
                        if f2 is None:
                            unknown += 1
                            f2 = False
                        a1 += f1
                        a2 += f2
                        viol += f1 and not f2
                        rescued += (not f1) and f2
                    once.append(a1)
                    per.append(a2)
                recs.append({"mode": mode, "k": k, "W": w, "n": C.SWEEP_SMALL_PER, "einmalig": once, "periodisch": per, "einmalig_nicht_periodisch": viol,
                             "einmalig_nein_periodisch_ja": rescued, "periodisch_unbekannt": unknown})
            if progress:
                progress(f"e5 {mode} k={k}")
    return recs


E5_REST_K = (8, 16, None)
E5_REST_W = (None, 30, 15, 10)


def grid_e5_rest(progress=None, limit: float = 10.0):
    recs = []
    for k in E5_REST_K:
        for w in E5_REST_W:
            hard = k is None and w is not None          # alle Anschlüsse bei endlicher Höchstwartezeit: je Netz Sekunden bis zum Zeitlimit, deshalb weniger Netze
            per_block = C.SWEEP_REST_PER_HARD if hard else C.SWEEP_REST_PER
            blocks = block_instances(6, per_block)
            s = Settings(transfers="alle", k_transfers=k, wait_max=w)
            exact_b, greedy_b, per_b, status = [], [], [], {}
            for blk in blocks:
                ex, gr, pf = [], [], 0
                for inst in blk:
                    kept, st = B.max_kept_weight(inst, s, limit=limit, workers=C.CPSAT_WORKERS)
                    status[st] = status.get(st, 0) + 1
                    ex.append(kept if kept is not None else float("nan"))
                    g = B.greedy_kept_weight(inst, s)
                    gr.append(g if g is not None else float("nan"))
                    n, arcs = M.build_arcs(inst, s)
                    pf += 1 if B.periodic_feasible(n, arcs, C.T, limit=10.0, workers=1) else 0
                exact_b.append(float(np.nanmean(ex)))
                greedy_b.append(float(np.nanmean(gr)))
                per_b.append(pf)
            recs.append({"k": k, "W": w, "n": per_block, "exakt": exact_b, "greedy": greedy_b, "periodisch_alle": per_b, "status": status, "limit_s": limit})
            if progress:
                progress(f"e5 rest k={k} W={w} {status}")
    return recs


SECTIONS = {"e1": grid_e1, "e2_cycles": grid_e2_cycles, "e2_regler": grid_e2_regler, "e3": grid_e3, "e4": grid_e4, "e5_pa": grid_e5_pa, "e5_rest": grid_e5_rest}


def load_results(path=None) -> dict:
    """Die vorgerechnete Ergebnisdatei (leeres Wörterbuch, wenn sie fehlt)."""
    p = Path(path) if path else ROOT / C.RESULTS_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
