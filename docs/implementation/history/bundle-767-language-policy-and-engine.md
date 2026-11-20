# Bundle 767 — Sprachpolicy und Enginebindung

20. November 2026. Das vollständig nativ geprüfte Quell-Result mit SHA-256
`097ad2ac0bc17bdd38f9d301c2e92cd0b675a74fbb5123bb4a6cd5116558eed7`
bestätigt sämtliche fünf Stufen des Bundles 766: 19.p.R/C und 19.q.W/R/C.
Der saubere Abschlusscommit ist `5d6b8a1850c0e8665ba0b2bdcd944b3e434e6f51`.
Bestätigter Ausgangsstand: **852/918**, nächster Schritt **19.r.W**, kein
offener Korrekturrest. Erfolgreiche Commits und historische Belege bleiben erhalten.

## 19.r.W/R/C — Policy und getrennte Erfolgsaussagen

W materialisiert und prüft die vier erlaubten Ergebnisaktionen und führt die
vorhandenen Text-, Score- und Vergleichswerte in einen vollständigen T.4-Bericht
zusammen. Alle ursprünglichen Subjectbindungen bleiben erhalten. Ignorierte
Beobachtungen behalten Status und Coverage, erhalten lediglich kein Finding.
Die ausdrückliche Workerfunktion `analyze_language` liefert den vollständigen
Bericht und eine getrennte Policybewertung. Technische Vollständigkeit,
Sprachbestätigung, fachliche Fail-Schwelle und Gate werden unabhängig berechnet.
Ein vollständiger Lauf mit info-Nichtentscheidungen hat Code 0, ohne eine
Sprachbestätigung zu erfinden. Die CLI verwendet dieselbe Auswertung für ihre
vorhandenen Package-Ergebnisse; der generische Show/Evaluate-Vertrag bleibt erhalten.

R prüft Aktions- und Schwellenfehler vor dem Modellzugriff, erhält Code 5 für
technisch nicht ausführbare Aufträge und priorisiert diesen gegenüber Code 1
für fachliche Findings. `compatible_coarse`, `unverifiable`, `undetermined`
und opake externe Payloads begründen keine volle Sprachbestätigung. Die
Work-Ausgabe prüft ihre getrennte Bewertung gegen den vorhandenen gebundenen
Abschlusscode; sie erzeugt keinen Ersatzabschluss. C trennt die unveränderte
gemeinsame Aktions-/Erfolgsberechnung von der Berichtserzeugung. Alle W/R-
Testbytes sowie die verschobenen Funktionsdefinitionen bleiben unverändert.

## 19.s.W/R/C — tatsächliche Enginefakten und Reproduzierbarkeit

W bindet den bereits verifizierten Modellstand, geordnete Kandidaten,
Library-, Adapter-, Vorverarbeitungs- und Unicode-Version an tatsächlich
beobachtete Runtime- und NumPy-Inventare. Dazu gehören Interpreterhash, ABI,
numerische Eigenschaften, NumPy-Binärhashes und beobachtete CPU-Dispatchdaten.
Die Inventare werden ohne lokale Pfade, Konfigurationsdateien oder Zugangsdaten
im namespaced Erweiterungsbereich des Berichts transportiert. Unbekannte
Fakten bleiben null mit Grund; sie begründen keine Reproduzierbarkeitszusage.

R bindet zusätzlich bereits geladene numerische Bibliotheken, tatsächlich
beobachtete OpenBLAS-Threadzahl und Gleitkomma-Rundungsmodus. Es wird kein
Projektplugin geladen. Nicht lesbare oder nicht verfügbare Messinformationen
bleiben unbekannt. Eine JSON-only Fortsetzungsbindung umfasst Request-ID,
Snapshot, Analyzer und vollständige Engineidentität. Fehlende Identität ist
unavailable (5), eine veränderte bekannte Komponente Konflikt (6). Es werden
keine Modelle serialisiert. Gleiche Entscheidungen anderer Runtimes bedeuten
ausdrücklich keine bytegleichen Reports. C isoliert die unveränderte einmalige
Inventarerfassung vom Enginewert; die Worker-Pipeline transportiert dieselben
beobachteten Fakten durch sämtliche Subjectentscheidungen und den Bericht.

## Abnahmen und verbleibender Plan

Neue reine Verhaltenstests beschreiben Default-/Aktionsgrenzen, unveränderte
Coverage bei ignore, Codepriorität, konservative Sprachbestätigung, CLI-
Erfolgsauswertung, deterministische Beobachtungsprojektion und Bindungswechsel
aller Enginekomponenten. Synthetische Inventare sind ausdrücklich Testdaten.
Die vorhandenen fünf echten Offlinefälle unter CPython 3.10 bis 3.14 bleiben
je Stage verpflichtend. Sie prüfen zusätzlich die Policyberichte, ab 19.s.W
die tatsächlichen Inventare und den vollständigen ausdrücklichen Workeraufruf,
ab 19.s.R auch die genaue Fortsetzungsbindung. Originalscores, Modellprüfung,
Kandidatenfilterverbote und alle negativen Bibliotheksfälle bleiben erhalten.
Statische Symbolprüfung der gebundenen Original-NumPy-Wheels bestätigt den
vorbereiteten OpenBLAS-Auskunftseinstieg; sie ist kein Runtime-Testnachweis.

Der vorhandene generische Dispatcher und dauerhafte Work-Subjectpfad behalten
ihren ehrlichen bisherigen Unavailable-Vertrag. Die Integration der tatsächlichen
Subjectausführung an allen dauerhaften Unterbrechungsgrenzen bleibt 19.w;
die vollständige Angriffsabnahme bleibt 19.u. Der neue direkte Workeraufruf
startet keinen Hintergrundprozess und erteilt keine Releasefreigabe. Ein
menschlich geprüfter eingefrorener Korpus, Ressourcenabnahme und allgemeine
Sprachqualität werden hier nicht behauptet; sie behalten ihre eigenen
folgenden Planpositionen und unabhängigen Nachweise.

Dev führt nur Syntax-/statische Prüfungen, reine Collection und native passive
Paket-/Handoffvalidierung aus. Keine Testkörper, Fixtures oder Test-Unterprozesse
laufen in Dev. Jede Stage besitzt vor ihrem eigenen Commit ein eigenes Gate
aus gefilterter N=3-Gruppe und vollständiger ungefilterter Pflichtauswahl.
Erst nach erfolgreichem Gate wird committed und der nächste Zustand ausgebracht.

| Stage | Ziel nach eigenem erfolgreichen Gate und Commit |
| --- | --- |
| 19.r.W | 853/918 |
| 19.r.R | 854/918 |
| 19.r.C | 855/918 |
| 19.s.W | 856/918 |
| 19.s.R | 857/918 |
| 19.s.C | 858/918 |

Danach folgt **19.t.W** mit seinen eigenständigen Herkunfts-, Lizenz- und
menschlichen Reviewanforderungen. Die Spezifikation 0.2.99, SPECROAD-DECISION-1
und Entwicklungsvertrag 4 bleiben unverändert. Die bestehenden T.4/T.8/T.9-
Regeln decken diese Umsetzung ab; es ist kein Klärungspräfix erforderlich.
Kein Budgetreset, kein Replay erfolgreicher Commits und keine Betriebsänderung.
