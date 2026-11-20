# Bundle 765 — vollständige Texte und exakte Scoreentscheidung

20. November 2026. Das native Quell-Result mit SHA-256
`cbcf2236b006945f8d64d4263e6619a355b659511506c2561cd0b3bee96ef201`
bestätigt 19.n.R und 19.n.C aus Bundle 764. R bestand 9155 Tests, C 9159;
beide Pflichtauswahlen enthielten die fünf realen Runtimefälle. Der saubere
Abschlusscommit ist `487895a95a2c14df0984158905d7e06856b0f6a4`.
Bestätigter Ausgangsstand: **843/918**, nächster Schritt **19.o.W**, kein
offener Korrekturrest. Historische Berichte bleiben unverändert.

## 19.o.W/R/C — Textvollständigkeit und Abstentionsvorbereitung

W ergänzt neben dem erhaltenen Roh-Ranking einen ausdrücklich angeforderten
Vorbereitungspfad mit materialisierter Requestpolicy. `min_text_codepoints`
hat Default 20 und den Bereich 1 bis 10000; boolesche Werte sind keine Integer-
Konfiguration. Nur ASCII-Randzeichen U+0009 bis U+000D und U+0020 werden für
die Längenentscheidung entfernt. Das Backend erhält weiterhin den vollständigen
Originalstring, einschließlich seiner Ränder, und jeden Subject separat.
Leere und zu kurze Texte ergeben `undetermined/insufficient_text`, bevor eine
optionale Dependency geladen wird. Ein ausschließlich kurzer Auftrag benötigt
kein Modell. Ungültige Subjecttypen bleiben native Eingabefehler.

R vervollständigt die Fehlergrenzen: Modell-/Versionsfehler werden einmal pro
Aufruf ermittelt, lange Subjects bleiben sichtbar `unavailable`, kurze behalten
ihren vorrangigen Abstentionsgrund. Ungültige Rankings sind `failed`, ohne
unabhängige Subjects zu unterschlagen. Prozessabbruch und Speichermangel werden
nicht als normale Sprachentscheidungen verschleiert. Bibliotheksnormalisierung
bleibt auf einer Arbeitskopie; Originalbytes, Wert- und Snapshot-Hashes sowie
deklarierte Sprach-Tags werden nicht geändert. Library- und Unicode-Versionen
bleiben mit dem tatsächlichen Engine gebunden. Keine semantische Zerlegung von
Zitaten, Code oder gemischten Texten und keine Projektdateischreiboperation.

C isoliert diese unveränderte Vorverarbeitung unter der Version
`ascii-edge-codepoints-v1`. Die verschobenen Definitionen und alle R-Testbytes
bleiben unverändert. Der Roh-Ranking-Aufruf mit seinen bisherigen leeren
Einstellungen bleibt kompatibel und behält seine vollständigen Tests.

## 19.p.W/R/C — normalisierte Scores und geordnete Entscheidung

W konsumiert die vollständigen `norm_probs=True`-Rankings, quantisiert mit
Half-even auf zwölf Nachkommastellen und publiziert die beiden höchsten Werte
als Dezimalstrings. Gleiche publizierte Werte werden nach Sprachcode geordnet.
Nur diese Werte bestimmen die Entscheidung; der Abstand wird exakt in Einheiten
der letzten Dezimalstelle berechnet. Beide materialisierten Schwellen sind
inklusive: Default `min_score=0.900000000000`, `min_margin=0.100000000000`.
Ergebnisse bezeichnen diese Werte ausdrücklich als normalisierte, **nicht
kalibrierte Modellscores**. Es gibt keine Behauptung statistischer Sicherheit.

R vervollständigt die geordnete Tabelle aus Anhang T.7: sämtliche Scorezeilen
werden vor der Auswahl geprüft, einschließlich nicht publizierter niedriger
Ränge. Widersprüchliche Formen, Duplikate, unbekannte Codes, nichtendliche oder
außerhalb des Wertebereichs liegende Zahlen ergeben `invalid_backend_output`.
Eine unmögliche normalisierte Gesamtsumme wird ohne empirische Toleranz erkannt:
jeder quantisierte Wert kann höchstens eine halbe Einheit der letzten Stelle
vom Original abweichen. Das vollständige Ranking muss innerhalb genau dieser
abgeleiteten Rundungsgrenze zu eins summieren. Scores werden nicht nachträglich
reskaliert. Top-Labels `und`/`zxx` liefern `backend_abstention` beziehungsweise
`non_linguistic`, noch vor den fachlichen Score-/Abstandsschwellen. Bei jeder
Nichtentscheidung bleibt das Sprachfeld leer; es gibt kein erfundenes Match.

C trennt die numerischen Hilfsfunktionen von der Entscheidung. Quantisierung
verwendet einen vollständig expliziten Decimal-Kontext, Schwellen und Differenz
exakte Integerwerte. Globale Präzision, Rundung, Traps und Flags ändern weder
Werte noch Entscheidung. Verschobene Funktionsdefinitionen und R-Testbytes
bleiben identisch; C setzt keine fachlichen Grenzen neu.

## Abnahmen und unverändert offener Folgeumfang

Die neuen Unitfälle prüfen exakte Grenzlängen, Sonderleerzeichen, Unicode-
Codepoints, vollständige lange Texte, Hashbindungen, Fehlerpriorität, Half-even,
Schwellen- und Abstandsgleichheit, Ranggleichstand, ungültige Rankings, `und`/`zxx`
und veränderte globale Decimal-Kontexte. Synthetische Rankings sind klar als
kontrollierte Testdaten gekennzeichnet. Zusätzlich führen die fünf vorhandenen
Offline-Integrationsfälle unter CPython 3.10 bis 3.14 die neue Textvorbereitung
und ab 19.p.W die Entscheidung mit dem Originalmodell aus. Ihre unabhängigen
Vergleiche aller 140 Rohscores, Modell-/Versionsbindungen, Ausfallfälle und
Filterverbote bleiben erhalten. Kein Skip oder fehlendes Paket zählt als
erfolgreiche Runtimeintegration.

Dev führt ausschließlich statische Prüfungen, reine Collection und passive
native Paket-/Handoffvalidierung aus. Keine Testkörper, Fixtures oder
Test-Unterprozesse werden hier gestartet. Jede Stage wird erst einzeln
installiert, mit ihrer gefilterten N=3-Gruppe vereinigt mit der vollständigen
ungefilterten Pflichtauswahl geprüft und bei Erfolg committed. W/R/C werden
nicht zusammengelegt; der Endstand wird nicht vorab installiert.

Ziele nach den jeweiligen erfolgreichen Gates und Commits:

| Stage | Produktstand |
| --- | --- |
| 19.o.W | 844/918 |
| 19.o.R | 845/918 |
| 19.o.C | 846/918 |
| 19.p.W | 847/918 |
| 19.p.R | 848/918 |
| 19.p.C | 849/918 |

Danach folgt **19.q.W**. Sprach-Tag-Vergleich, endgültige Workerberichte,
Policy-/Exitaggregation, vollständiger Enginefingerprint, menschlich geprüfter
Korpus und Releaseabnahme bleiben ihren folgenden Planschritten zugeordnet.
Die neuen internen Entscheidungswerte sind weder Evidence noch eine bestätigte
Produktfreigabe. Der generische Worker erhält hier keine vorzeitige Erfolgs-
oder Kompatibilitätsbehauptung. Spezifikation 0.2.99, SPECROAD-DECISION-1 und
Entwicklungsvertrag bleiben unverändert: kein notwendiger Klärungspräfix,
keine Budgetänderung und keine Wiederholung erfolgreicher Commits.
