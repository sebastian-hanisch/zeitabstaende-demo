# Zeitabstände – wann ein Plan überhaupt möglich ist – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-zeitabstaende-demo.streamlit.app/)** -->

Diese Demo gehört zur Linie **Takt und Periodizität** der Konzepte-Reihe für die Website „Sebastian Hanisch – Operations Research und Machine Learning“. Die Demo ist **nicht periodisch**: Ein Umlaufplan gilt einmal, jede Bedingung ist eine Differenz zweier Zeitpunkte mit Mindest- und Höchstabstand (Fahrzeit, Halt, Wende, Umsteigeanschluss, Zugfolge). Ein Bellman-Ford-Lauf auf dem Bedingungsgraphen entscheidet, ob der Plan **überhaupt möglich** ist (kein Kreis positiver Länge), und liefert **früheste und späteste Lage** und den **Spielraum** jedes Ereignisses. Die Vorstufe zum Takt: Experiment 5 lässt dieselben Bedingungen modulo *T* gelten. Vehikel ist je ein Umlauf der Linien des Netzgenerators der Fall-Demo `taktfahrplan-demo` (**synthetisch, Annahmen, keine Echtdaten**). Die Anschlussliste („die *k* am stärksten nachgefragten Umstiege, je Richtung gezählt“) und die Richtung „gerichtet“ sind **Planungsannahmen**. Die Höchstwartezeit *W* am Anschluss wird überall in dieser Demo **über der Mindest-Umsteigezeit gemessen**.

Nachbarn: `bellman-ford-demo` zeigt das Verfahren (negative Kreise, Runde für Runde); `kritischer-pfad-demo` rechnet den kritischen Pfad ohne Höchstabstände und führt Zeitabstände zwischen Aufgaben ausdrücklich als eigene Demo; `job-shop-demo` und `shifting-bottleneck-demo` behandeln die Wahl der Reihenfolge; `kreise-aufloesen-demo` das Streichen bis zur Kreisfreiheit. Der Algorithmus allein trägt diese Demo nicht (er ist Lehrbuchstoff und steht in `bellman-ford-demo`); es tragen die Befunde auf dem Fahrplan unten.

## Warum dieses Problem

Mindestabstände (Fahrzeit, Halt, Mindest-Umsteigezeit) lassen sich durch Nach-hinten-Schieben erfüllen, solange sie keinen Kreis bilden. Höchstabstände (Fahrzeitreserve, Wende, Höchstwartezeit am Anschluss) machen aus „frühestens“ ein „nicht zu spät“ und schließen Kreise. In diesem Netz entstehen allerdings auch Kreise ganz ohne Höchstabstand (Zeitkreis), wenn Hin- und Rück-Anschluss derselben Relation verlangt werden. Die Kernfrage: **Wann ist ein Plan aus Mindest- und Höchstabständen überhaupt möglich, wie viel Spielraum hat jedes Ereignis, und was kippt ihn?** Die Antwort auf diesem Fahrplan: Der Plan kippt in der Messung schon ohne Höchstwartezeit am Anschluss, wenn Hin- und Rück-Anschluss derselben Relation verlangt werden (der **Zeitkreis**, Experimente 1 und 2).

## Modell

Ereignisse sind Abfahrt und Ankunft je Halt und Richtung (20 Ereignisse je Linie bei 6 Halten). Ein Bogen $(u, v)$ trägt ein Fenster $l \le x_v - x_u \le h$ in ganzen Minuten: Fahrzeit $[r, r + \text{Reserve}]$, Halt $[1, \text{längste Haltezeit}]$, Wende $[4, 4 + \text{Höchstwende}]$, Anschluss $[\text{Mindest-Umsteigezeit}, \text{Mindest-Umsteigezeit} + \text{Höchstwartezeit}]$ (die Höchstwartezeit *W* ist also über der Mindest-Umsteigezeit gemessen, nicht ab der Ankunft), Zugfolge $[h, \infty)$ mit **fester** Reihenfolge nach Liniennummer. Der Bedingungsgraph hat die Kanten $u \to v$ mit Gewicht $+l$ und $v \to u$ mit Gewicht $-h$; ein Plan ist genau dann möglich, wenn er keinen Kreis positiver Länge hat. Sonst sind früheste Lage (längster Weg ab der Quelle) und späteste Lage (Rückwärtslauf vom frühesten Gesamtende) die Grenzen jedes Ereignisses, der Unterschied ist der Spielraum, Spielraum 0 heißt kritisch. Formeln im 📐-Expander der App.

## Methodik

- **Entscheidung:** Bellman-Ford für längste Wege (`zab_graph.py`), in zwei Fassungen: Python mit Zeuge (der Kreis als geschlossener Kantenzug) und numpy, rundenweise, für die Messreihen.
- **Zeuge und Zerlegung:** `zab_witness.py`; eine unmögliche Bogenmenge per Löschfilter (jeden Bogen probeweise entfernen; inklusionsminimal und nicht eindeutig: aus ihr darf kein Bogen mehr fehlen, welche Menge übrig bleibt, hängt von der Bogenreihenfolge ab). Ob ein Plan einen **Zeitkreis** hat, zeigt der Test ohne alle Höchstabstände.
- **Klassische Rechnung gegen Höchstabstände:** dieselbe Rechnung mit allen Höchstabständen weggelassen (`critical_cpm`); Ereignisse, die nur mit Höchstabständen kritisch sind, zählt Experiment 3.
- **Brücke zum Takt und Grenzen des einmaligen Plans:** `zab_bridge.py` (CP-SAT, höchstens zwei Arbeiter): periodische Machbarkeit, freie Zugfolge, größter haltbarer Anteil der Nachfrage.
- **Messreihen:** `tools/sweep.py` rechnet vier Blöcke zu je 250 Netzen des Generators (Zugfolge, Takt und Löschfilter: vier Blöcke zu je 60 Netze; „größter haltbarer Anteil“: je 40, bei allen Anschlüssen und endlicher Höchstwartezeit je 10), Netz Nr = 250 · Block + i, Zufalls-Seed = 3000 + 100 · Nr (der Abstand 100 verhindert, dass die Seed-Suche des Generators, bis +49, dasselbe Netz zweimal liefert). Ausgewiesen: Mittel ± Standardabweichung über die vier Blöcke. Die Ergebnisse liegen in `data/zab_results.json` mit einem Hash des Rechenkerns; ändert sich der Kern, meldet `tests/test_claims.py` eine veraltete Datei.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen gelten für diesen Generator (20 Haltestellen, jede Linie 6 Halte, ein Umlauf je Linie, ganzzahlige Minuten, Nachfrage und Netz sind Annahmen) und für die genannten Einstellungen; übrige Regler auf Standard (keine Reserve, Haltezeit 1 bis 3 min, Mindest-Umsteigezeit 3 min, Wende unbegrenzt, Zugfolge aus). Die Zahlen der Experimente 1 bis 5 werden in `tests/test_claims.py` aus `data/zab_results.json` gelesen und mit dem Text verglichen; die Zellen, die hier stehen, werden dort mit dem Kern neu gerechnet.

### Experiment 1: Wie viele Anschlüsse verträgt das Netz?

Anteil möglicher Pläne, 6 Linien, 1000 Netze: Mit den 4 am stärksten nachgefragten **gerichteten** Umstiegen (je Richtung gezählt) und Höchstwartezeit 30 min (über der Mindest-Umsteigezeit gemessen) sind 55,6 % der Netze möglich; mit den 4 am stärksten nachgefragten Umstiegen **beider Richtungen** (je Richtung gezählt) und ohne Höchstwartezeit 61,7 % ± 3,2 (Mittel ± Standardabweichung über vier Blöcke), also schon **ohne Höchstwartezeit am Anschluss** sind 38,3 % der Pläne unmöglich. Der Grund ist der Zeitkreis: In Experiment 2 (240 Netze, dieselbe Einstellung) sind alle 108 unmöglichen Pläne schon ohne Höchstabstände unmöglich (Zeitkreis). Mit allen Anschlüssen beider Richtungen und ohne Höchstwartezeit war ein einmaliger Plan bei 5, 6, 8 und 10 Linien in 0 von je 1000 Netzen, bei 3 Linien in 11 von 1000 möglich. Die Richtung „gerichtet“ ohne Höchstwartezeit hat in allen 60 gemessenen Zellen (5 Linienzahlen, 12 Werte von *k*) den Anteil 1,000; das ist ein Satz und kein toter Zweig: Ein Kreis müsste von einer höheren zu einer niedrigeren Liniennummer zurückkehren, das können nur Höchstabstände am Anschluss, und innerhalb einer Linie ist der Plan allein möglich.

**Kein scharfer Phasenübergang.** Bei Richtung „alle“ und Höchstwartezeit 10 min fällt der Anteil ohne Sprung an einer bestimmten Zahl *k*, am stärksten von *k* = 1 auf 2 und danach etwa geometrisch; er erreicht 0,9 / 0,5 / 0,1 bei folgenden *k*: 3 Linien: 1,2 / 2,4 / 4,6; 6 Linien: 1,2 / 2,7 / 5,8; 10 Linien: 1,2 / 3,0 / 6,3 (linear zwischen den gemessenen *k* interpoliert). Der Übergang wird mit der Netzgröße nicht schärfer: Der Bereich zwischen 0,9 und 0,1 wird mit der Linienzahl breiter (3,4 / 4,6 / 5,1 Anschlüsse); die Lage des Anteils 0,5 (2,4 / 2,7 / 3,0) liegt innerhalb der Streuung der Blöcke (gemessen nur für diese Einstellung und 3, 6 und 10 Linien; bei unbegrenzter Höchstwartezeit liegt die Lage des Anteils 0,5 bei 5,2 / 6,1 / 5,9 und wandert nicht monoton).

**Die Höchstwartezeit wirkt vor allem zwischen unbegrenzt und 20 min, darunter ist der Anteil fast flach.** 6 Linien, „alle“, *k* = 4, Höchstwartezeit unbegrenzt / 40 / 30 / 20 / 15 / 0 min: 61,7 → 45,7 → 35,9 → 28,2 → 26,3 → 23,8 %.

### Experiment 2: Wer kippt den Plan?

Ein unmöglicher Plan hat einen **Zeitkreis**, wenn er schon ohne jeden Höchstabstand unmöglich ist; sonst wird er erst durch Höchstabstände unmöglich. Dieser Test hängt nicht von der Reihenfolge der Bögen ab. Zusätzlich liefert der Löschfilter zu jedem unmöglichen Plan eine unmögliche Bogenmenge, aus der kein Bogen mehr fehlen darf (inklusionsminimal, nicht eindeutig); bei einem Zeitkreis-Plan sucht er im Plan ohne Höchstabstände. 6 Linien, vier Blöcke zu je 60 Netzen (240 Netze je Zeile; *W* = Höchstwartezeit über der Mindest-Umsteigezeit):

| Einstellung | unmöglich | davon schon ohne Höchstabstand unmöglich (Zeitkreis) | davon erst durch Höchstabstände unmöglich |
|---|---|---|---|
| alle, k = 4, W unbegrenzt | 108 von 240 | 108 | 0 |
| alle, k = 4, W = 10 | 191 von 240 | 108 | 83 |
| alle, k = 8, W unbegrenzt | 150 von 240 | 150 | 0 |
| alle, k = 8, W = 10 | 235 von 240 | 150 | 85 |
| gerichtet, k = 4, W = 30 | 111 von 240 | 0 | 111 |
| gerichtet, k = 4, W = 10 | 152 von 240 | 0 | 152 |
| gerichtet, k = 8, W = 10 | 238 von 240 | 0 | 238 |

Ohne Höchstwartezeit (erste und dritte Zeile) sind alle unmöglichen Pläne (108 bzw. 150) schon ohne Höchstabstände unmöglich (Zeitkreis); mit Höchstwartezeit 10 min kommen 83 bzw. 85 Pläne hinzu, die erst durch Höchstabstände unmöglich werden. In der Richtung „gerichtet“ gibt es keinen Zeitkreis (0 von 111, 152 und 238 unmöglichen Plänen): dort enthält jeder Kreis eines unmöglichen Plans mindestens einen Höchstabstand. Erklärung: Kommt eine Linie auf dem Rückweg am Umsteigeort an und fährt die andere dort auf dem Hinweg ab, und umgekehrt, schließen die beiden Anschlüsse über die Fahrten beider Linien einen Kreis (Handrechnung: 10 + 3 + 10 + 3 = +26 min; `tests/conftest.py`). Gezählt an dem Kreis, den der Löschfilter in seiner unmöglichen Menge findet (inklusionsminimal, nicht eindeutig, die Zahl kann je nach Bogenreihenfolge anders ausfallen; 6 Linien, „alle“, Höchstwartezeit unbegrenzt, 240 Netze je Zeile), haben bei *k* = 4 102 von 108 Zeitkreisen zwei Anschlüsse und 6 vier, bei *k* = 8 haben 142 von 150 zwei, 1 drei und 7 vier.

**Welche Regler helfen?** Bei „alle“, *k* = 4, Höchstwartezeit unbegrenzt ändern **Fahrzeitreserve (0 bis 200 %), längste Haltezeit (1, 3, 10 min) und Mindest-Umsteigezeit (0 bis 12 min) den Anteil nicht** (gleiche Zahl in allen vier Blöcken: die Kreise laufen nicht über diese Rückkanten); die Regler sind nicht tot, bei „gerichtet“, *k* = 4, Höchstwartezeit 15 min steigt der Anteil mit der Reserve von 42,5 auf 45,4 % und mit der Mindest-Umsteigezeit von 42,3 auf 45,0 % (die Höchstwartezeit wird über der Mindest-Umsteigezeit gemessen, das absolute Fenster verschiebt sich also mit; die App zeigt es deshalb absolut). **Wirksam ist die Wende:** Höchstwende (min über 4 min) unbegrenzt / 60 / 30 / 15 / 5 / 0 bei „alle“, *k* = 4, Höchstwartezeit unbegrenzt: 61,7 / 55,4 / 40,6 / 27,8 / 21,4 / 18,9 %.

### Experiment 3: Spielraum gegen die klassische Rechnung

„Gerichtet“, *k* = 4, Höchstwartezeit 30 min, 6 Linien, 556 mögliche Pläne unter 1000 Netzen: **27,5 % ± 0,7 der Ereignisse kritisch** (Spielraum 0; Mittel ± Standardabweichung über die vier Blöcke), nur Mindestabstände 24,9 %: **+4,4 Prozentpunkte** der Ereignisse sind erst durch Höchstabstände kritisch und fehlen in der klassischen Rechnung; umgekehrt sind 1,8 Punkte der klassisch kritischen Ereignisse mit Höchstabständen nicht mehr kritisch (daher 27,5 statt 24,9 + 4,4 %). Bei „alle“, *k* = 4, Höchstwartezeit unbegrenzt nur +0,1 Prozentpunkte (ohne Höchstwartezeit und Höchstwende bleiben als Höchstabstände nur die von Fahrt, bei Reserve 0 also eine feste Fahrzeit, und Halt); bei 10 Linien +2,9 Prozentpunkte („gerichtet“, *k* = 4, Höchstwartezeit 30 min). Spielraum (Minuten, Quantile 0/10/25/50/75/90/100): 0/0/0/13/35/68/182 (6 Linien, „gerichtet“, *k* = 4, Höchstwartezeit 30 min, über alle Ereignisse möglicher Pläne).

### Experiment 4: Zugfolge – Zahl oder Reihenfolge?

Mit der Mindestzugfolge *h* bei **fester** Reihenfolge (kleinere Liniennummer zuerst, Planungsannahme) bricht der Anteil schon bei *h* = 2 min ein; ob *h* 2, 4 oder 10 min beträgt, ändert bei fester Reihenfolge den Anteil höchstens 3,4 Prozentpunkte, der kleinste Einbruch von *h* = 0 auf *h* = 2 beträgt mindestens 8,7 Prozentpunkte (5 Anschlusslisten, 6 Linien, vier Blöcke zu je 60 Netzen). Bei **freier** Reihenfolge (Entweder-oder je Abschnittspaar, CP-SAT, im Mittel 16,8 Abschnittspaare je Netz) liegt der Anteil höchstens 0,9 Prozentpunkte vom Anteil ohne Zugfolge. Für „alle“, *k* = 4, Höchstwartezeit unbegrenzt: 55,0 % ohne Zugfolge, 35,0 % bei fester Reihenfolge, 55,0 % bei freier. Die freie Reihenfolge war in 15 von 15 Zellen mit Zugfolge mindestens so gut wie die feste, in 15 besser (das ist erwartet: eine feste Wahl ist eine der freien). Entscheidend ist in diesen Messungen die **Reihenfolge** (fest gegen frei: 9 bis 26 Punkte je nach Anschlussliste), die Minutenzahl *h* = 2 bis 10 min ändert den Anteil um höchstens etwa 3 Punkte; die Reihenfolge zu wählen ist ein Job-Shop-Problem (`job-shop-demo`), deshalb bleibt die Zugfolge im Hauptplan ein Tab mit fester Reihenfolge, ausdrücklich so beschriftet.

### Experiment 5: Zum Takt

Dieselben Bögen periodisch (π_v − π_u + T·p = x, x in [l, h], *T* = 60, CP-SAT, ein Faden). **Satz:** Jede einmalige Lösung, modulo *T* genommen, löst das periodische System; einmalig möglich heißt also periodisch möglich. Gemessen in 36 Zellen mit je 240 Netzen, also bei 8640 Vergleichen: 2324 einmalig möglich, **0 davon periodisch unmöglich** (0 Zeitüberschreitungen). Umgekehrt rettet der Takt viele Pläne: „alle“, *k* = 4, Höchstwartezeit 10 min einmalig 20,4 % gegen 100,0 % periodisch (191 von 240 Plänen gerettet). **Auch der Takt rettet nicht alles:** mit *allen* Anschlüssen beider Richtungen ist periodisch bei Höchstwartezeit unbegrenzt 100,0 %, bei 30 min nur 11,2 % möglich (einmalig 0 %).

**Größter haltbarer Anteil.** Wie viel der verlangten Nachfrage kann ein einmaliger Plan halten, wenn Anschlüsse gestrichen werden dürfen? Alle Anschlüsse beider Richtungen unter den *k* am stärksten nachgefragten Umstiegen (je Richtung gezählt), 6 Linien, vier Blöcke zu je 40 Netzen (die drei letzten Zeilen mit *k* = alle und endlicher Höchstwartezeit je 10 Netze, Zeitlimit je Netz 10 s): CP-SAT mit optionalen Bögen gegen Greedy (Zeuge suchen, billigsten Anschluss im Kreis streichen, wiederholen):

| k | Höchstwartezeit (über der Mindest-Umsteigezeit) | größter gefundener Anteil (CP-SAT) | Greedy | periodisch: alle Anschlüsse haltbar | bewiesen optimal |
|---|---|---|---|---|---|
| 8 | unbegrenzt | 83,8 % ± 1,4 | 83,3 % ± 1,3 | 160 von 160 | 160 von 160 |
| 8 | 30 | 69,8 % ± 1,9 | 64,8 % ± 1,3 | 160 von 160 | 160 von 160 |
| 8 | 15 | 66,5 % ± 2,5 | 59,5 % ± 2,1 | 158 von 160 | 160 von 160 |
| 8 | 10 | 65,4 % ± 2,7 | 58,4 % ± 2,1 | 154 von 160 | 160 von 160 |
| 16 | unbegrenzt | 81,8 % ± 1,1 | 80,2 % ± 1,4 | 160 von 160 | 160 von 160 |
| 16 | 30 | 63,5 % ± 1,1 | 51,7 % ± 1,1 | 160 von 160 | 160 von 160 |
| 16 | 15 | 59,8 % ± 1,4 | 46,1 % ± 1,1 | 140 von 160 | 160 von 160 |
| 16 | 10 | 58,4 % ± 1,6 | 44,8 % ± 1,5 | 113 von 160 | 160 von 160 |
| alle | unbegrenzt | 73,7 % ± 1,0 | 68,5 % ± 1,5 | 160 von 160 | 160 von 160 |
| alle | 30 | 51,0 % ± 0,9 | 30,7 % ± 0,7 | 4 von 40 | 33 von 40 |
| alle | 15 | 46,9 % ± 0,8 | 25,1 % ± 2,1 | 1 von 40 | 34 von 40 |
| alle | 10 | 45,1 % ± 1,5 | 24,5 % ± 2,2 | 1 von 40 | 33 von 40 |

Wo das Zeitlimit nicht reichte (20 von 1560 Netzen in der gespeicherten Messung; die Zahl hängt von Rechner und Lauf ab, ein Neulauf lieferte 16), ist der Anteil des CP-SAT eine untere Schranke. Bei „alle“ mit endlicher Höchstwartezeit ändert sich die Zahl der bewiesenen Netze von Lauf zu Lauf (hier 33 bis 35 von 40), dort ist der CP-SAT-Anteil eine untere Schranke. Abstand exakt minus Greedy in Prozentpunkten, *k* = 16, Höchstwartezeit unbegrenzt / 30 / 15 / 10 min (alle bewiesen): 1,6 / 11,8 / 13,6 / 13,6; er wächst von unbegrenzt über 30 auf 15 min und ändert sich von 15 auf 10 min um weniger als 0,1 Prozentpunkte.

## Ehrliche Grenzen

- Die Anschlussliste „die *k* am stärksten nachgefragten Umstiege, je Richtung gezählt“ und die Richtung „gerichtet“ sind **Planungsannahmen**, kein Befund über echte Betriebe. Alle Anteile hängen an diesem Generator (20 Haltestellen, 6 Halte je Linie, ein Umlauf je Linie) und an den genannten Einstellungen, nicht an Netzen im Allgemeinen.
- Die Zugfolge verwendet eine **feste** Reihenfolge nach Liniennummer; mit freier Reihenfolge sind die Ergebnisse anders (Experiment 4).
- Ein Umlauf je Linie, ganzzahlige Minuten, keine Verspätungen, kein Fahrzeugumlauf über mehrere Linien.
- Negative Befunde stehen oben: kein scharfer Phasenübergang; Fahrzeitreserve, Haltezeit und Mindest-Umsteigezeit ohne Wirkung bei „alle“ ohne Höchstwartezeit; die Minutenzahl der Zugfolge ohne große Wirkung.
- Der Takt rettet nicht jeden Plan (Experiment 5).
- Die Literatur zu Distanzgraphen und Temporal Constraint Networks ist **nicht** im Volltext gelesen und wird hier nicht zitiert.
- Die Live-Rechnungen mit CP-SAT haben ein Zeitlimit von 10 s und melden „nicht bewiesen“, wenn es nicht reicht; die Rechenzeit hängt vom Rechner ab und steht nirgends als feste Zahl.

## Verifikation

- **Kern gegen Handrechnung:** Mini-Systeme in `tests/conftest.py` (Kette: früheste Lagen 0, 2, 5, Kreis +1; Raute: Spielraum 3 und mit Höchstabstand 2; Raute mit einem nur durch den Höchstabstand kritischen Ereignis; Zeitkreis +26), Mini-Netz mit 12 Ereignissen (`tests/test_model.py`); Randfälle in `tests/test_edge_cases.py`.
- **Orakel** (`tests/test_oracle_zeitabstaende.py`, anderer Rechenweg): Bellman-Ford gegen die **Aufzählung** aller Belegungen von 300 Zufallssystemen (Machbarkeit, früheste und späteste Lage, Gesamtende); Machbarkeit und frühe Lagen auf echten Netzen gegen **networkx** (negativer Kreis im negierten Graphen) und **CP-SAT**; Lagen gegen das **lineare Programm** (HiGHS); jeder Zeuge ein geschlossener Kantenzug positiver Länge, **aus den Bögen unabhängig nachgerechnet**; die Löschfilter-Menge ist unmöglich und inklusionsminimal; die Zeitkreis-Zählung (schon ohne jeden Höchstabstand unmöglich) und die gefundene Menge gegen die **Aufzählung aller Teilmengen** (300 Zufallssysteme, beide Bogenreihenfolgen); periodische Machbarkeit gegen die **Aufzählung aller Phasen** (120 Systeme, *T* = 6) und der Satz „einmalig ⇒ periodisch“ auf echten Netzen; größter haltbarer Anteil gegen **alle Teilmengen** der Anschlüsse; freie Zugfolge gegen **alle Reihenfolgen**.
- **Großer Lauf** (`tools/oracle_scratch.py`, nicht Teil der Suite): 3000 Zufallssysteme erzeugt, 2979 verglichen (der Rest passt nicht in die Wertebox 0 bis 8), davon 1310 möglich, 0 Abweichungen; 40 Netze × 15 Einstellungen = 600 Vergleiche (247 möglich, 353 unmöglich, alle Zeugen geprüft), 0 Abweichungen.
- **Zweig-Tests (Nullspalten-Regel)** in `tests/test_claims.py`: Höchstwartezeit, *k*, Richtung, Höchstwende und Reihenfolge ändern den Anteil; Reserve, Haltezeit und Mindest-Umsteigezeit sind bei „alle“ ohne Höchstwartezeit als **erwartet wirkungslos** getestet und bei „gerichtet“, Höchstwartezeit 15 min als wirksam; die Spalte „gerichtet ohne Höchstwartezeit“ muss überall 1,000 sein (Satz).
- **Messreihen:** Die Zellen der README werden mit dem Kern neu gerechnet und stimmen mit `data/zab_results.json` überein; die Zahlen der Experimente 1 bis 5 werden dort aus der Datei gelesen und im README-Text gesucht. Hash des Rechenkerns in der Datei.
- **Presets:** Jedes Preset wird durchlaufen: Verdikt und die Aussage seines Hilfetextes (z. B. „unmöglich, der Kreis enthält keinen Höchstabstand“) sind getestet (`tests/test_claims.py`, `tests/test_app.py`). Die Seeds fand `tools/preset_search.py`.
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler an der ersten und letzten Stufe, größtes Netz mit allen Anschlüssen, jeder ▶️-Knopf einzeln), Footer, Layout (Schnellstart oben in der Seitenleiste, fester Kopf, aktives Preset hervorgehoben, jede Regleränderung hebt die Markierung auf), Laufzeit-Importe, PDF-Bericht, Diagramme.
- **Generator-Kopie:** `tests/test_network.py` prüft SplitMix64-Referenzwerte, eingefrorene Referenzlinien des Originals und, wenn der Geschwisterordner `taktfahrplan-demo` da ist, Gleichheit der erzeugten Netze mit dem Original.
- **Testzahl:** 238 Tests (`pytest --collect-only -q tests`).

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App: Netz, Ergebnis, fünf Experimente, Grenzen, Formeln |
| `data/zab_results.json` | vorgerechnete Messreihen (Experimente 1 bis 5) mit Hash des Rechenkerns |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt): Streamlit, NumPy, Plotly, fpdf2, OR-Tools |
| `requirements-dev.txt` | Laufzeit plus pytest, networkx, SciPy (nur Gegenproben) |
| `tools/sweep.py` | rechnet die Messreihen vor und fügt sie zusammen |
| `tools/oracle_scratch.py` | großer Orakel-Lauf (Scratch) |
| `tools/preset_search.py` | Suche der Preset-Seeds |
| `zab_bridge.py` | Takt (CP-SAT), freie Zugfolge, größter haltbarer Anteil |
| `zab_constants.py` | Regler-Stufen, feste Annahmen, Presets, Farben |
| `zab_evaluation.py` | Analyse, Verdikte als reine Funktionen, Zusammenfassungen der Messreihen |
| `zab_graph.py` | Bedingungsgraph, Bellman-Ford (Python mit Zeuge, numpy) |
| `zab_layout.py` | fester Kopf (Stylesheet) |
| `zab_model.py` | Ereignisse, Bögen, verlangte Anschlüsse, Einstellungen |
| `zab_network.py` | Netzgenerator (aus `taktfahrplan-demo` kopiert, angepasst) |
| `zab_pdf_export.py` | PDF-Planbericht (fpdf2) |
| `zab_presets.py` | Permalink, Presets, Zufalls-Seed-Button |
| `zab_rng.py` | SplitMix64 (aus `taktfahrplan-demo` kopiert) |
| `zab_schedule.py` | früheste und späteste Lage, Spielraum, kritische Ereignisse, klassische Rechnung |
| `zab_sweeps.py` | Messreihen und Hash des Rechenkerns |
| `zab_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `zab_witness.py` | Zeuge, inklusionsminimale unmögliche Bogenmenge (Löschfilter), Klassifikation des Kreises |
| `tests/` | Handrechnung, Orakel, Randfälle, Verdikte, Messreihen und README-Zahlen, Presets, Layout, AppTest, Footer, Laufzeit-Importe |

## Bewusst nicht umgesetzt

- **Zeit-Kosten-Abwägung** (Beschleunigen gegen Geld, ein lineares Programm): kein tragfähiger Tab in dieser Kulisse; `kritischer-pfad-demo` führt sie als eigene Demo (bisher keine).
- **Zugfolge mit freier Reihenfolge im Hauptplan:** Die Wahl der Reihenfolge ist Job-Shop (`job-shop-demo`, `shifting-bottleneck-demo`); Experiment 4 prüft sie nur als Machbarkeit.
- **Anschlüsse streichen bis zur Machbarkeit als Planungswerkzeug:** Experiment 5 zeigt den größten haltbaren Anteil, die Wahl der gestrichenen Anschlüsse ist Feedback-Arc-Set (`kreise-aufloesen-demo`).
- **Verspätungen, Zufallsdauern, Fahrzeugumlauf, Echtdaten und Dateiimport:** nicht Thema; das Netz ist synthetisch.
- **Takt wählen:** Experiment 5 prüft nur, ob ein periodischer Plan existiert, und wählt keinen.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy und OR-Tools (CP-SAT).

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zur Reihe: [Takt und Periodizität: Fahrplan im Stundentakt](https://sebastianhanisch.net/konzepte-takt-periodizitaet.html).
