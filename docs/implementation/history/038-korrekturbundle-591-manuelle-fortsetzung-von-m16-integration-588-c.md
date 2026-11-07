# Korrekturbundle 591 — manuelle Fortsetzung von M16-INTEGRATION-588.C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 591 — manuelle Fortsetzung von M16-INTEGRATION-588.C

Nativ geprüftes Timeout-Result:
`6ec936506276ce1a06427fad870344b1bf593afc9fa7edb145c50fd94d2ecbb8`,
HEAD `3a311f4052abe4402265f39dac270f21a1f955b3`, Dirty-Fingerprint
`6eac241ae102d1f8`. Bundle 590 schloss R nach 9614 bestandenen Tests ab.
PatchHarbor beendete den gesamten R/C-Versuch am 4. November 2026 um
21:32:56 UTC nach seinem 10800-Sekunden-Entrypointlimit. Im anschließenden
C-Volltest waren 24933 von 24935 Tests beendet: 24673 bestanden, 259
fehlgeschlagen und ein wegen fehlgeschlagener Subtests ungültiger Nachweis;
zwei Recovery-Tests blieben ohne Abschluss. Ein Vollsuite-Erfolg liegt nicht vor.

Der letzte originale Fortschrittsrecord lautet testing, nicht failed. Er wird
unverändert erhalten. Der native äußere Timeout, die Original-ZIP, der exakt
nachgewiesene R-Commit samt Gate und der bytegleiche angekündigte C-Snapshot
beweisen in dieser ausdrücklich beauftragten manuellen Fortsetzung den Rest.
Eine abgeleitete Wiederaufnahmeansicht ist als solche gekennzeichnet; sie
behauptet keinen vom Entrypoint ausgegebenen terminalen Record. Es werden
weder ein Result umgeschrieben noch Control-Betriebsdaten oder dessen
strengere automatische Prüfung verändert. Das Folgepaket bindet alle vier
aktuellen Werte und ausschließlich die offene C-ID mit ursprünglicher Rolle.
D/W/R werden nicht wiederholt. C erhält allein das unveränderte Apply-Zeitlimit.

Die phasenweise Messdatenbank bindet die beobachteten Fehler an den tatsächlichen
C-Quellhash. Der Timeout verhinderte Pytests abschließende Traceback-Ausgabe;
die Korrektur stützt sich auf diese realen Fehleridentitäten und die statisch
nachvollziehbaren Vertragsverletzungen, nicht auf erfundene Fehlermeldungen:

- Der vertrauenswürdige Runtime-Payloadvergleich berücksichtigt den bereits
  ausgelieferten unveränderten migration-vector.json mit exakten Bytes. Seine
  fehlende Aufnahme ließ die eigene Distribution vor dem Transport scheitern.
  Hash-, Fremddatei-, Versions- und Sicherheitsprüfungen bleiben vollständig.
- MigrationLockSource übernimmt vor dem Lock und bei jeder erneuten Beobachtung
  die bestehende vollständige Projektwurzelprüfung. Extrahierte Teilprojekte
  und veränderte Herkunftsmarker dürfen keine Schreibautorität erhalten.
- Die allgemeinen CLI-Vertragstests erhalten wirkliche synthetische Quellprojekte,
  originale Pläne und Backups sowie für Apply einen ausdrücklich eingebetteten
  synthetischen Hostgrant. Verify verwendet ein zuvor wirklich migriertes Ziel.
  Keine Validatoren, Writer, Recovery oder Ergebnisse werden gemockt.
- Exakte Befehls-/Resultkataloge und Work-/Lock-/Optionslisten enthalten die schon
  freigegebenen drei Migrationsbefehle. Der Test ohne Work-Engine entfernt auch
  die Migrations-Work-Befehle und prüft zusätzlich deren tatsächliche Deklaration.

Die ursprüngliche C-Strukturbereinigung bleibt erhalten. Dies repariert ihren
fehlgeschlagenen Integrationsstand nach 2.5; neue Features, neue Detailentscheidungen
oder abgeschwächte fachliche Testorakel werden nicht hinzugefügt. Insbesondere
bleibt der echte Teilprojekt-Abweisungstest unverändert. Die historischen
Ankündigungen bytegleicher R/C-Tests beschreiben Bundle 590; diese ausdrücklich
bezeichnete technische Korrektur führt zusätzlich veraltete allgemeine Fixtures
und Inventarlisten auf die bereits verbindlichen Q.5.3-Verträge nach.
Spezifikation 0.2.61, aktive Katalogbindungen, sämtliche 24935 Testidentitäten
und Nummern bleiben unverändert. C prüft erneut jeden gesammelten Test ungefiltert
vor dem Commit. Dev führt keine Verhaltenstests aus. M16 bleibt bis zu diesem
gebundenen erfolgreichen C-Commit und Vollsuite-Ergebnis offen; Stand 693/900.
