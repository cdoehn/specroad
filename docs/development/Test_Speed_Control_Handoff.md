# Testlaufzeit und eindeutige Entwicklungssteuerung — TEST-SPEED-CONTROL-599

Der Nutzerauftrag vom 5. November 2026 bündelt die besprochene Beschleunigung
der drei längsten aktuellen Testidentitäten und die Aufhebung der manuellen
Chat-Kurzbefehle. Produktcode, Prüfgrenzen und der nächste Produktplanschritt
bleiben unverändert. Die Produkt-Spezifikation 0.2.63 gilt weiterhin.

## Migration: alle Fehlerpositionen separat planen

Die bisherigen Varianten effect/ack führten sämtliche Schreibpositionen
innerhalb jeweils eines pytest-Items seriell aus. Jetzt sind beide Varianten
für jede der 13 Positionen separat parametrisiert (26 Items). Die echte
Planlänge muss exakt zur vollständigen deklarierten Indexmenge passen;
zusätzliche oder entfernte Effekte schlagen fehl, statt ungetestet zu bleiben.
Die Deklaration importiert oder startet keine Fixture während der Collection.

Jeder Fall erzeugt weiterhin ein eigenes synthetisches Projekt, einen echten
nativen Plan und eine externe Quellsicherung. Native Veröffentlichung,
Crash-Injektion, Bestätigungsstand, verweigerter erneuter Apply, vollständige
Recovery unter Lock und Vergleich aller Quell-/Zielbytes bleiben erhalten.
Der zusätzliche Seed-Aufbau entfällt. Bereits gelesener Recoverystatus wird
nicht noch einmal allein zur Auswahl der bekannten Recoveryaktion gelesen;
die native Recovery selbst prüft sämtliche aktuellen Voraussetzungen weiter.
R prüft außerdem acht Erzeugungen, vier Ersetzungen und eine Entfernung,
eindeutige Pfade, vollständige Zielqualifikation nur am letzten Präfix sowie
konsistenten Normalzugriff nach erfolgreicher Recovery.

Das beseitigt lange unteilbare Workeraufträge. Parallelisierung allein ist
keine entsprechende CPU-Ersparnis; die kleinen tatsächlichen Einsparungen
kommen vom entfallenen Seed und doppelten Statuslesen. Alle 26 Fälle sind
Pflichttests dieses Bundles, unabhängig von Laufzeitfilter und Rotation.

## Restore: vollständige öffentliche Referenz und größere Fachfälle

Ein eigenes kleines gültiges Projekt mit genau einem primären Spezifikations-
dokument, echter Konfiguration, Profil und kleiner expliziter Sprachregistry
durchläuft
weiterhin jeden einzelnen Planungsschritt über die öffentliche argv-CLI.
Es verwendet keinen Batch-Helfer. Source-Erfassung, Inventur, globale
Qualifikation, Lieferung, exakte native Planbytes und historischer Replay
nach Entfernung der Quelle bleiben vollständig integriert geprüft.

Die größere Bundle-Variante nutzt wie die Baseline-Variante den bestehenden
nativen Capture-Helfer ausschließlich für die mittlere Inventur. Alle
Quell-Captures, erster und letzter Inventurschritt, Qualifikation und Lieferung
bleiben öffentlich. Der Helfer erfasst tatsächliche Bytes und veröffentlicht
einen echten Checkpoint; er erfindet weder Plan noch Erfolg. Die bestehende
Mapping-Abdeckung bleibt erhalten. R prüft die Phasenfolge, den exakten
verbleibenden Rest, fehlende vorzeitige Ausgabe und unveränderte Projektbytes.
C teilt nur das identische Ausgabe-/Byte-/Replay-Oracle zwischen beiden Größen.

Weniger Wiederholungen derselben öffentlichen Verbindung am größeren Projekt
werden durch die vollständige kleine Referenz abgesichert. Langketten-,
Mehrblock-, Manipulations-, I/O- und Wiederanlauftests bleiben erhalten.
Keine fsync-, Hash-, Lock- oder native Sicherheitsprüfung wird abgeschaltet;
kein produktiver Cache und keine neue Runner-/Timeoutkonfiguration.

## Korrektur 600: vollständiges Minimalprojekt

Bundle 599 scheiterte in W mit document_primary_missing: Eine leere
Artefaktmenge genügt zwar dem Fixture-Aufbau, aber nicht der vollständigen
Restore-Qualifikation. Spezifikation 10.14 / SR-REQ-0467 verlangt genau ein
nicht retiertes primäres Spezifikationsdokument. Das korrigierte Fixture
enthält dieses native Dokument; alle öffentlichen Resumes und unveränderten
Byte-, Ausgabe- und Replay-Oracles bleiben bestehen. Es gibt keinen Stub,
keine Skip-/Xfail-Ausnahme und keine Abschwächung des Restore-Validators.
Die 6.848 bestandenen Tests aus dem fehlgeschlagenen Gate sind historische
Belege; sie ersetzen nicht die neuen Gates des korrigierten W/R/C-Rests.

## Nachweise und Vergleich

Ausgangsmessungen aus der gemeinsamen Laufzeitdatenbank, letzter gültiger
Stand bei der Analyse am 5. November 2026: ack 13:02,7; effect 12:44,2;
argv-project_bundle 8:26,0. Das sind historische Messungen, keine Prognose.
Nach Apply müssen für die Migration zusätzlich Summe und längster Einzeltest
aller 26 neuen Fälle betrachtet werden; für Restore der größere Fall und
die neue vollständige Referenz zusammen. Kleine neue Einzelwerte allein
beweisen keine Einsparung der Gesamtlaufzeit. Hostlast/Workerzahl mitbeachten.

Alte Testnummern, Laufzeitdatenbank, Baseline und Schätzwerte bleiben als
Historie erhalten. Neue Identitäten werden hinten angehängt; aktive
Anforderungskataloge referenzieren die vollständige neue Fallmenge.
Jeder W/R/C-Zustand hat sein eigenes N=3-plus-Pflichtauswahl-Gate vor Commit.
Dev führt nur statische Prüfung, Collection und native Paketvalidierung aus.
Erfolg und tatsächliche neue Laufzeiten müssen aus dem späteren Result kommen.

## Entwicklungsaufträge ausschließlich über Control

Nutzerauftrag vom 5. November 2026, OFF-PLAN TEST-SPEED-CONTROL-599:
Die bisherigen manuellen Chat-Kurzbefehle `S` und `N` sind aufgehoben.
Control beauftragt jeweils genau einen vollständig gebundenen Dev-Durchlauf;
Dev veröffentlicht höchstens eine ZIP und beendet den Turn. Watcher/Apply
übernehmen Ausführung und Tests; Control beobachtet das Result und veranlasst
bei freigegebener Automatik den nächsten Auftrag. Dev wartet nicht selbst.
Start/Fortsetzen/Pause/Stopp erfolgen über ausdrückliche Control-Bedienaktionen.
Manuelle Entwicklungsaufträge bleiben bei pausierter Automatik und ohne
aktiven Control-Auftrag möglich; alle Bindungs- und Apply-Regeln gelten weiter.

Die lokale Dev-AGENTS.md wird am Entwicklungsort bereinigt und gehört nicht
in Produkt-Payloads. Historische Prompt-/Auftragsbytes, alte Nachweise und
Recoverybindungen bleiben unverändert. Ein dort vorhandenes `N` ist keine
aktuelle Definition eines Chat-Kurzbefehls. Die Testrotation N=3 bleibt
unverändert. Dieses Bundle startet oder installiert keinen Dienst.
