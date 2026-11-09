"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets (eine Wahrheitsquelle).

Alle Zeiten in ganzen Minuten. Netze, Linien und Nachfrage sind Annahmen des Generators (20 Haltestellen, jede Linie 6 Halte), keine Echtdaten.
"""

# ------------------------------------------------------------------ feste Annahmen des Modells
T = 60                      # Takt in Minuten, nur für den Vergleich „einmalig gegen periodisch“ (Experiment 5)
EVENTS_PER_LINE = 20        # 20 Ereignisse je Linie bei 6 Halten: je Richtung 1 + 2 * 4 + 1 (Abfahrt am Anfang, Ankunft und Abfahrt an den vier Zwischenhalten, Ankunft am Ende)
RESULTS_FILE = "data/zab_results.json"

# ------------------------------------------------------------------ Regler: Auswahlstufen (eine Stufe je Wert, in dieser Reihenfolge)
LINES_OPTIONS = (3, 5, 6, 8, 10)
DEFAULT_LINES = 6
SEED_MIN, SEED_MAX = 0, 9999
DEFAULT_SEED = 501

TRANSFER_MODES = ("gerichtet", "alle")          # „gerichtet“: nur Zubringer von der kleineren zur größeren Liniennummer
DEFAULT_MODE = "gerichtet"
K_ALL = "alle"
K_OPTIONS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 24, K_ALL)
DEFAULT_K = 4
W_UNLIMITED = "unbegrenzt"
W_OPTIONS = (0, 5, 10, 15, 20, 30, 40, W_UNLIMITED)
DEFAULT_W = 30
TURN_UNLIMITED = "unbegrenzt"
TURN_OPTIONS = (0, 5, 15, 30, 60, TURN_UNLIMITED)   # höchstens so viele Minuten über der Mindest-Standzeit an den Endpunkten
DEFAULT_TURN = TURN_UNLIMITED
RESERVE_OPTIONS = (0, 10, 25, 50, 100, 200)         # Fahrzeitreserve in Prozent der Fahrzeit
DEFAULT_RESERVE = 0
DWELL_HI_OPTIONS = (1, 3, 10)                       # längste Haltezeit (die kürzeste ist 1 Minute)
DEFAULT_DWELL_HI = 3
DWELL_LO = 1
TRANSFER_MIN_OPTIONS = (0, 3, 8, 12)                # Mindest-Umsteigezeit
DEFAULT_TRANSFER_MIN = 3
HEADWAY_OPTIONS = (0, 2, 4, 10)                     # Mindestzugfolge auf gemeinsamen Abschnitten, 0 = aus
DEFAULT_HEADWAY = 0
TURN_MIN = 4                                        # kürzeste Standzeit an den Endpunkten (Fall-Demo)

# ------------------------------------------------------------------ Messreihen (vorgerechnet in data/zab_results.json)
SWEEP_BLOCKS = 4            # vier Blöcke (Seeds) ...
SWEEP_PER = 250             # ... zu je 250 Netzen: Netz Nr = 250 * Block + i, Seed = SWEEP_BASE + SWEEP_STEP * Nr
SWEEP_BASE = 3000
SWEEP_STEP = 100            # Abstand 100 gegen doppelte Netze durch die Seed-Suche (bis +49)
SWEEP_K = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 24, None)
SWEEP_W_FULL = (None, 40, 30, 20, 15, 10, 5, 0)
SWEEP_W_SHORT = (None, 10)
SWEEP_LINES_FULL = (3, 6, 10)
SWEEP_LINES_SHORT = (5, 8)
SWEEP_SMALL_PER = 60        # Messungen mit Löschfilter, Zugfolge frei und Takt: je Block 60 Netze (Zeit)
SWEEP_REST_PER = 40         # größter haltbarer Anteil: je Block 40 Netze
SWEEP_REST_PER_HARD = 10    # ... bei allen Anschlüssen und endlicher Höchstwartezeit (Sekunden je Netz): je Block 10 Netze

# ------------------------------------------------------------------ Live-Rechnung (Obergrenzen der App)
CPSAT_WORKERS = 2           # CP-SAT höchstens zwei Arbeiter
CPSAT_LIVE_SECONDS = 10.0
MAX_KEPT_LIVE_K = 16        # „größter haltbarer Anteil“ live nur bis zu dieser Zahl verlangter Anschlüsse (darüber vorgerechnet)

# ------------------------------------------------------------------ Darstellung
KIND_LABELS = {"run": "Fahrt", "dwell": "Halt", "turn": "Wende", "transfer": "Anschluss", "headway": "Zugfolge"}
COLOR_OK = "#2e7d4f"
COLOR_BAD = "#c0392b"
COLOR_CRIT = "#c0392b"
COLOR_CRIT_MAX = "#c77700"      # nur durch einen Höchstabstand kritisch
COLOR_SLACK = "#7d8898"
COLOR_LINE = "#2a6fb0"
LINE_COLORS = ["#2a6fb0", "#2e7d4f", "#c77700", "#8e44ad", "#c0392b", "#16a085", "#7f8c8d", "#d35400", "#2c3e50", "#b03a6f"]

# ------------------------------------------------------------------ Presets (Seeds liegen unter 3000, also außerhalb der Messreihen-Seeds; gefunden mit tools/preset_search.py)
_BASE = {"lines": 6, "seed": 501, "mode": "gerichtet", "k": 4, "w": 30, "turn": TURN_UNLIMITED, "reserve": 0, "dwell_hi": 3, "transfer_min": 3, "headway": 0}
PRESET_ORDER = ["Standard", "Zeitkreis", "Höchstwartezeit zu eng", "Wende begrenzt", "Zugfolge: Reihenfolge entscheidet", "Zum Takt"]
PRESETS = {
    "Standard": dict(_BASE),
    "Zeitkreis": {**_BASE, "seed": 14, "mode": "alle", "k": 2, "w": W_UNLIMITED},
    "Höchstwartezeit zu eng": {**_BASE, "seed": 1, "w": 5},
    "Wende begrenzt": {**_BASE, "seed": 416, "turn": 5},
    "Zugfolge: Reihenfolge entscheidet": {**_BASE, "seed": 17, "mode": "alle", "k": 4, "w": W_UNLIMITED, "headway": 4},
    "Zum Takt": {**_BASE, "seed": 3, "mode": "alle", "k": 8, "w": 10},
}
PRESET_HELP = {
    "Standard": "6 Linien, die 4 am stärksten nachgefragten Umstiege (je Richtung gezählt, nur von der kleineren zur größeren Liniennummer), Höchstwartezeit 30 min über der Mindest-Umsteigezeit: der Grundfall. Der Plan ist möglich; einige Ereignisse sind erst durch Höchstabstände kritisch.",
    "Zeitkreis": "Hin- und Rück-Anschlüsse (Richtung „alle“), nur die 2 am stärksten nachgefragten Umstiege (je Richtung gezählt), keine Höchstwartezeit: Der Plan ist trotzdem unmöglich, denn der Kreis enthält keinen Höchstabstand.",
    "Höchstwartezeit zu eng": "Die 4 am stärksten nachgefragten gerichteten Umstiege (je Richtung gezählt) mit Höchstwartezeit 5 min statt 30 (über der Mindest-Umsteigezeit gemessen): Der Plan ist unmöglich, der Kreis enthält Höchstabstände. Mit 30 min wäre dieses Netz möglich.",
    "Wende begrenzt": "Wie der Standard, aber die Wende am Endpunkt darf höchstens 5 min über der Mindest-Standzeit liegen: Der Plan ist unmöglich, der Kreis läuft über eine Wende. Ohne Höchstwende wäre dieses Netz möglich.",
    "Zugfolge: Reihenfolge entscheidet": "Mindestzugfolge 4 min mit fester Reihenfolge (kleinere Liniennummer zuerst): unmöglich, obwohl das Netz ohne Zugfolge möglich ist. Experiment 4 prüft die freie Reihenfolge: dann ist es möglich.",
    "Zum Takt": "Alle Anschlüsse beider Richtungen unter den 8 am stärksten nachgefragten Umstiegen (je Richtung gezählt), Höchstwartezeit 10 min über der Mindest-Umsteigezeit: einmalig unmöglich, periodisch (T = 60 min) möglich. Experiment 5 zeigt die Summe der Abstände entlang des Kreises.",
}
