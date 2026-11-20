# Bundle 764 — vollständige Referenzintegration auf fünf Runtimes

20. November 2026. Das native Quell-Result mit SHA-256
`2200d181950a28175fec0f4af1d83fcfcec5373262d44b9ebf11f8027bbb7fab`
bestätigt **19.n.W** aus Bundle 763 mit **8754** bestandenen Tests und dem
sauberen Commit `329d24f589d5c85ddbf85ada888ac35ba116bf7b`.
Damit sind **841/918** Produktpositionen bestätigt; es gibt keinen offenen
Korrekturrest. Der historische Bundle-763-Bericht bleibt erhalten. Seine
damalige fehlende Runtime-Vorbereitung wird durch die folgende Umsetzung
bearbeitet, nicht nachträglich in einen erfolgreichen Matrixlauf umgedeutet.

## 19.n.R — vollständige Abnahme des realen Referenzbackends

Fünf verpflichtende parametrisierte Integrationsfälle bauen aus dem jeweiligen
Apply-Quellstand eigene Offlinepakete für CPython 3.10, 3.11, 3.12, 3.13 und
3.14 unter Linux x86_64. Die Originalwheels bleiben exakt an den vorhandenen
Katalog gebunden: NumPy 2.2.6 für 3.10, NumPy 2.3.5 für 3.11–3.14 und
py3langid 0.4.0. Paketprüfung bindet Core, Modell, Wheels und Lizenzen.
Das Paket bleibt als ungetestet und nicht releasefreigegeben gekennzeichnet;
die spätere tatsächliche Testausführung ist der davon getrennte Laufnachweis.

Jeder Fall startet den ausdrücklich ausgewählten, hashgeprüften Interpreter
isoliert und prüft seine tatsächliche Version, ABI, Implementierung sowie den
Core-Build. Vier vollständige synthetische Texte werden vom Originalmodell
analysiert. Alle 140 Scores und deren Reihenfolge werden mit einem weiteren
echten Bibliotheksaufruf verglichen; Request-, Subject-, Originalwert-, Modell-,
Kandidaten- und Versionsbindungen bleiben vollständig. Keine Wortlistenattrappe,
globale Modellinstanz, Netzwerkoperation oder operative Upstream-Funktion.

Dieselben fünf Runtimes prüfen außerdem separat fehlendes NumPy, fehlendes
py3langid und veränderte Modellbytes: ausschließlich Fehler, keine erfolgreiche
Ersatzrangliste. Kandidaten-/Sprachfilter und fremde Modelle werden bereits
vor dem Laden abgelehnt. Zusätzliche Unit-Fälle sichern fehlende Modellattribute,
unvollständige Bibliotheksversionen, unbrauchbare Ausgaben und Fehler nach dem
ersten Subject ab. Prozessabbruch und Speichermangel werden nicht als normale
Backend-Ergebnisse verschleiert. Die vollständigen W-Testdateien bleiben erhalten.

Die Runtimeauswahl ist eine ausdrücklich vorbereitete lokale Testabhängigkeit,
kein Fachprojektinput und kein Produkt-Payload. Das portable Vorbereitungstool
prüft vorhandene Interpreter und Wheels, führt keine Produkttests aus und
ersetzt keine vorhandene Konfiguration. Fehlende oder abweichende Auswahl ist
ein Fehler, kein Skip oder automatischer Download. Die ausschließlich manuelle
CI erhält eine separate Abhängigkeitsvorbereitung vor ihrem Testlauf. Keine
konkreten Hostpfade, Betreiberkonfigurationen oder Zugangsdaten werden übertragen.

## 19.n.C — unverändertes Verhalten hinter der Request-Grenze

Die Originalbibliothek, ihre Versionsbindung, Modellzustandsprüfung und
Scoreprüfung liegen im privaten Referenzbackend. Der öffentliche Aufruf
`rank_request` erhält die generische AnalyzerRequest-Grenze und die bisherigen
unveränderlichen Ergebniswerte. Die sechs bisherigen Funktions-/Klassendefinitionen
werden unverändert verteilt; alle R-Testbytes bleiben identisch. C verändert
keine Entscheidung, Fehlerklasse, Rangfolge oder erlaubten Seiteneffekt.
Der endgültige Workerbericht und die Sprachentscheidung bleiben den folgenden
Planschritten zugeordnet; rohe Scores werden weiterhin nicht als finale
Detector-Observations oder Evidence ausgegeben.

## Getrennte Gates und verbleibender Umfang

Dev bereitet ausschließlich Code, Testpläne, reine Collection, statische
Prüfungen und passive native Paketvalidierung vor. Hier werden keine Testkörper,
Fixtures oder Test-Unterprozesse ausgeführt. Apply stellt erst R her, prüft
genau seine gefilterte N=3-Gruppe vereinigt mit der ungefilterten Pflichtauswahl
und committet nur bei Erfolg. Erst danach folgen C und dessen eigenes Gate.
Alle fünf realen Runtimefälle, sämtliche neuen Tests, erhaltene W-Tests und
relevante Analyzer-, Paket-, Core-, Sicherheits- und Runnerregressionen sind
in beiden Pflichtauswahlen enthalten. Ein übersprungener Fall ist kein Erfolg.

Die vorbereiteten Zielwerte **842/918** (R) und **843/918** (C) gelten erst
nach dem jeweiligen erfolgreichen Gate und Commit; anschließend **19.o.W**.
Die synthetischen Texte ersetzen keine menschliche Korpusprüfung, vollständige
Sprachqualitätsabnahme oder Releasefreigabe. 19.o/p/q, die abschließende
Workerintegration und die Releaseabnahmen bleiben offen. Spec 0.2.99,
SPECROAD-DECISION-1 und der Entwicklungsvertrag bleiben unverändert. Keine
normative Lücke, kein Klärungspräfix und keine Budgetänderung.
