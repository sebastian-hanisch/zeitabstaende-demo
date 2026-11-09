"""Rechnet die Messreihen vor (Experimente 1 bis 5) und schreibt sie nach data/zab_results.json.

Aufruf (aus dem Repo-Ordner, höchstens zwei Prozesse zugleich):
    python tools/sweep.py <Abschnitt>      Abschnitt: e1 | e2_cycles | e2_regler | e3 | e4 | e5_pa | e5_rest  -> data/raw/<Abschnitt>.json
    python tools/sweep.py merge            fügt alle Abschnitte zu data/zab_results.json zusammen (mit Hash des Rechenkerns und Messrahmen)
    python tools/sweep.py list             zeigt, welche Abschnitte vorliegen
Die Messung nutzt ausschließlich den Code dieses Repos (zab_sweeps.py); ändert sich der Rechenkern, meldet tests/test_claims.py eine veraltete Datei.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import zab_constants as C  # noqa: E402
import zab_sweeps as SW  # noqa: E402

RAW = ROOT / "data" / "raw"


def run(section):
    RAW.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    recs = SW.SECTIONS[section](progress=lambda msg: print(f"[{time.time() - t0:6.0f} s] {msg}", flush=True))
    out = {"hash": SW.generator_hash(), "records": recs, "seconds": round(time.time() - t0)}
    (RAW / f"{section}.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{section}: {len(recs)} Zeilen in {time.time() - t0:.0f} s", flush=True)


def merge():
    res = {"meta": {"hash": SW.generator_hash(), "blocks": C.SWEEP_BLOCKS, "per_block": C.SWEEP_PER, "base_seed": C.SWEEP_BASE, "seed_step": C.SWEEP_STEP,
                    "small_per_block": C.SWEEP_SMALL_PER, "rest_per_block": C.SWEEP_REST_PER, "T": C.T}}
    for section in SW.SECTIONS:
        p = RAW / f"{section}.json"
        if not p.exists():
            print(f"fehlt: {section}")
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw["hash"] != res["meta"]["hash"]:
            print(f"VERALTET: {section} (Hash {raw['hash']} statt {res['meta']['hash']})")
            continue
        res[section] = raw["records"]
    (ROOT / C.RESULTS_FILE).write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
    print("geschrieben:", C.RESULTS_FILE, "Abschnitte:", [k for k in res if k != "meta"])


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "list"
    if arg == "merge":
        merge()
    elif arg == "list":
        print([p.stem for p in sorted(RAW.glob("*.json"))] if RAW.exists() else "keine")
    else:
        run(arg)
