# Korrekturbundle 578 — vollständiger Rest 16.i.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 578 — vollständiger Rest 16.i.R/C

Das maßgebliche native Fehler-Result hat SHA-256
`22618ea1359d91370f6576fed0b5e3ee6c1d5ac36729e85f8570a86ae270297d`,
HEAD `b3e452022899f419b0a427017bb68abfc4ac3173` und den erhaltenen
Dirty-Fingerprint `e182f35e16bc62fc`. Bundle 577 hat 16.i.W nach 8634
bestandenen Tests tatsächlich committed. In 16.i.R bestanden 8725 Tests,
sieben scheiterten; R wurde nicht committed. Der erhaltene Arbeitsstand ist
bytegleich zur angekündigten R-Stage. Tatsächlicher Produktstand: 685/900.
Der erfolgreiche W-Commit und der frühere Klärungscommit bleiben erhalten;
ausschließlich R und C werden vollständig fortgeführt.

Zwei Fehler betreffen den bisherigen v1-Discard-Test mit verlinktem Journal.
Der neue read-only Formatdispatch lag vor der bestehenden Fehlerübersetzung:
JournalError beziehungsweise SafetyViolation entkamen dem öffentlichen
RecoveryError-Vertrag. Alle drei gemeinsamen Recovery-Einstiege verwenden
nun dieselbe ausschließlich lesende Probe mit der bereits vorhandenen
recovery_failure-Übersetzung. Vorliegende Gründe, Exitklassen und Pfade
bleiben erhalten; die Probe behauptet keine Mutation. Unsichere Journale
werden weiterhin abgelehnt, nicht als alter Writerzweig umgangen. Die
bestehende Linkregression prüft zusätzlich Completion und Rollback samt
unveränderten Bytes, ausbleibender Autorisierung und null Normativwrites.

Die übrigen fünf Fehler haben dieselbe Ursache: Nach einem tatsächlich
erfolgten, aber unquittierten Dateieffekt liegt der echte Zielpräfix genau
eins vor published_count. Die unabhängige Byteprüfung erkannte diesen Stand
bereits korrekt. Beim ersten Rollback-Marker fehlte jedoch dessen gültiger
Zähler in der Liste exakt belegbarer temporärer Journalbilder. Nur für
committing wird nun dieses eine deterministische rolling_back-Bild zusätzlich
anerkannt, begrenzt auf die wirkliche Anzahl geplanter Änderungen. Name,
Hash und sämtliche vorhandenen Bytes müssen weiterhin exakt zum erwarteten
Bild passen. Die eigenständige Source-/Target-Präfixprüfung, Ein-Schritt-
Grenze, Autorität, Sicherungsbindung und frischen Lockprüfungen bleiben.
Unbekannte oder abweichende Bilder werden weder überschrieben noch entfernt.

Die vollständige vorhandene Effekt-/Quittierungsmatrix, echte verlorene
Rename-/Unlink-Antworten, tote Writer und erneut unterbrochene Rollbacks
bleiben Pflicht. Sechs zusätzliche Testidentitäten prüfen leere, partielle
und vollständige unquittierte erste Rollback-Marker sowie manipulierte
Zähler, Bytes und Dateinamen. Bestehende Testnummern bleiben erhalten; neue
Nummern werden ausschließlich angehängt. SR-TC-0270 bindet diese Nachweise.
Normativer Bezug: 12.20.4 verlangt bereits genaue eigene Bytepräfixe und
belegte verlorene Effekte; die gemeinsamen Recovery-Fehlerverträge gelten
auch vor der Formatauswahl. Spezifikation 0.2.59 bleibt bytegleich. Dies ist
eine technische Korrektur, keine neue Detailklärung oder Budgetänderung.

Die offenen IDs 16.i.R und 16.i.C behalten role=implementation.
correction_of bindet Planhash
`4d608304dd027bc75b98e398269ba54c5b905adedf9f13b9691b2684b6b5cac3`
und genau diesen vollständigen Rest. Erste Stage und Vorherbytes umfassen
den gesamten erhaltenen Dirty-Stand. R erhält Gruppe 1, C anschließend
Gruppe 2; beide zusätzlich die vollständige ungefilterte Pflichtauswahl.
Die C-Stage behält ausschließlich die angekündigte Strukturbereinigung:
ausgelagerte Beweisfunktionen sind AST-gleich zum korrigierten R, Tests und
Katalogbindungen bytegleich. Keine vorab installierte Endfassung und kein
wiederholter erfolgreicher W-Commit.

Verhaltenstests wurden in Dev nicht ausgeführt; statische Prüfung, reine
Collection und native Paketvalidierung ersetzen die beiden Apply-Gates
nicht. Vorbereiteter Zwischenstand: C; Häkchen und Zähler gelten erst
nach erfolgreichem Gate und echtem Commit. Vollständiger Abschluss ergäbe
687/900, anschließend 16.j.W. Kein Dienst-, CI-, Watcher- oder Controlstart;
keine lokalen Betriebsdaten in der Payload und keine eigene Folgeschleife.
