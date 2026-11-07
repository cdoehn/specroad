# OFF-PLAN – Entwicklungsworkflow vereinfachen (Bundle 514)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Entwicklungsworkflow vereinfachen (Bundle 514)

**WORKFLOW-514**, ausdrücklicher Nutzerauftrag vom 28. Oktober 2026. Eine
gemeinsame ZIP liefert feste Laufzeiten/Ausschlüsse und die neue BD-001-Regel.
Produktfortschritt bleibt **649/900**, nächster Schritt **15.l.R**. Quelle ist
das erfolgreiche saubere Result von Bundle 513 mit 7.399 bestandenen Tests.
Die einmalige vollständige parallele Einmessung ist ausdrücklich Teil dieses
Auftrags; sie ersetzt keine späteren commitgebundenen Apply-Gates.

- [x] **WORKFLOW-514.W:** Laufzeiten erfassen, eine feste langsamste Fünftelmenge bilden und nur die automatische N=3-Auswahl filtern; Arbeitsregeln gemeinsam aktualisieren. Commit: `test(workflow): Feste Laufzeitauswahl und vollständige Arbeitspakete einführen`.
- [x] **WORKFLOW-514.R:** Unvollständige/mehrdeutige Messungen, unveränderliche Listen, explizite ungefilterte Auswahl und Laufbindung robust prüfen. Commit: `test(workflow): Laufzeitfilter und ungefilterte Prüfwege absichern`.
- [x] **WORKFLOW-514.C:** Gemeinsame Timing-Verträge ohne Verhaltensänderung bereinigen. Commit: `refactor(testing): Laufzeitverträge gemeinsam nutzen`.

**W-Nachweis:** 215 gezielte parallele Verhaltenstests bestanden; darunter
echte erfolgreiche und fehlgeschlagene Messläufe in isolierten kleinen
Testprojekten. Dies ist keine Vollmessung der Produktsuite. Der W-Stand ist
als eigener unveränderter Payload-Zwischenstand für Apply gesichert.

**Ergänzter Nutzerauftrag, dauerhafte Messung:** Der erste Messlauf endete
ohne Abschlussdateien; 22.208 Erfolgsmarker sind keine erhaltenen Einzellaufzeiten.
R ergänzt sofortige dauerhafte Phasen-Commits, frei kombinierbare Nachholgruppen,
fehlende-Tests-Auswahl und quellgebundene Zusammenführung. Vorherige Logs und
W-Payload bleiben erhalten. Keine Liste aus unvollständigen Daten erzeugen.
Abbruchtests müssen belegen, dass gespeicherte Einzeltests erhalten bleiben
und nur fehlende Tests erneut laufen; Teilmessungen sind kein Vollsuite-Nachweis.

**SQLite-Sperrkorrektur:** Der dauerhafte Versuch endete nach 1.628 vollständig
gespeicherten Tests mit `database is locked`. Nutzerauftrag: korrigieren und
fortsetzen. R ergänzt native begrenzte Wartezeit, kurze Snapshot-Lesezugriffe und
belegt parallele Statusabfragen. Die 1.628 historischen Messungen werden nur
nach bytegenau geprüfter Messcode-Korrektur mit Herkunft in eine getrennte
Fortsetzungsbasis übernommen. Produktcode und bereits gemessene Testdateien
bleiben unverändert; neue Regressionstests werden zusätzlich gemessen.

**Einmalige reale Einmessung:** 22263 Einzeltests vollständig
parallel und dauerhaft erfasst. Aggregierte Messabdeckung ist kein Vollsuite-Nachweis.
Beginn 2026-10-28T15:13:42.803165+00:00, Ende 2026-10-28T21:51:29.666725+00:00.
Gemessener Quellstand `3efa4de94cb2da67fa40384b780d00ac91bcf6fcc9a7f6c6d37908ff55f80927`;
Rohmessung SHA-256 `97db15a09716f3c4bc9796080f3e47f8d1a9b018c0e182f49ff9ae25be15a4bd`.
Die feste Liste enthält 4452 ausgeschlossene Identitäten;
Listen-SHA-256 `ebf60e61ff731f5144dae5ad05d98879acc66563f6247cf520d088bd47ef006b`.
Die Liste enthält 1.628 ausdrücklich gekennzeichnete historische Messwerte aus der
belegten Messcode-Korrektur. Originalquellen und Übernahme sind in der Liste gebunden.
Der Messstand liegt vor Aufnahme der Liste; die aktuelle R-Fassung
wird anschließend gezielt geprüft. C ändert nur Struktur. Dieser
Messbeleg wird nicht als Vollsuite-Nachweis späterer Stände ausgegeben.

**R-Nachweis:** Die eingefrorene reale Liste und ihre aktuelle Einbindung
sind durch die gezielte parallele Verhaltenssuite geprüft. C trennt
Messbeobachtung und feste Auswahl; AST-Vergleich bestätigt unveränderte
Funktions- und Klassenkörper. Bestehende Tests bleiben bytegleich.

**Abnahme:** Vollständige echte Messung mit eindeutigen parametrisierten
Identitäten und drei Phasen; floor(N/5) feste Ausschlüsse, stabile Tie-Breaks;
N=3-Nummern/Anker unverändert; neue Tests zugelassen; gezielte Dev-Prüfungen
und manuelle Vollsuite ungefiltert; spätere Läufe verändern die Liste nicht;
Apply-Berichte prüfen tatsächlich ausgeführte Identitäten und Listenhash.
Einmessung und aktuelle Verhaltenstests werden getrennt belegt. Nur tatsächliche
erfolgreiche Apply-Commits schließen die obigen Zwischenstände ab.
