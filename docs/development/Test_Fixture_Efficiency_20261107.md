# Kleine native Fixtures und gezielte Testvorbereitung

Manueller Nutzerauftrag vom 7. November 2026, OFF-PLAN `TEST-FIXTURE-EFFICIENCY-625.C`.
Ein vollständiger Bereinigungscommit ohne neues Produktverhalten. Basis ist das
erfolgreiche Result von Bundle 624 mit SHA-256
`1e9b18ad60972fd183f345f44896f5efb5ff571d929079b20f7f5efc04892fe3`.
Es belegt 12.025 bestandene Tests in 97 Minuten 51 Sekunden und Commit
`8dcd6bc8f8dae56dde585b62287f569ab1b26ed0`. Das ist kein Nachweis dieses neuen Bundles.

## Änderungen

- Merge-Zielprüfungen wählen ausdrücklich das vorhandene kleine native
  Register für de-DE/en-GB. Der bisherige Seed mit vollständigem Register bleibt
  als eigener Einstieg unverändert verfügbar. Artefakte, Policies, echte
  Quellenwechsel, native Validatoren und Ergebnisprüfungen bleiben gleich.
- Die gemeinsamen Ausgangsprojekte der Merge-Auflösungs- und Metadatenfälle
  verwenden ebenfalls das kleine Register. Ihr kompletter übriger Inhalt mit
  Kontrollartefakten, binärem Anhang und passivem Mapping bleibt erhalten.
  Der Projektbundle-Helfer behält für alle bisherigen Aufrufer sein vollständiges
  Register; die verkleinerte Variante ist ausdrücklich optional.
- Dreizehn Eingabeablehnungen vor Quellenzugriff teilen ausschließlich native
  Plan-/Requestbytes, einmal je Modul und Worker erzeugt. Jeder Fall dekodiert
  seinen eigenen Request. Der doppelte Entscheidungsfall nutzt einen wirklich
  nativ aufgelösten Plan. An den geprüften Aufruf gehen weiterhin keine Quellen
  oder History; eine Quellenqualifikation darf den erwarteten Fehler nicht ersetzen.
- Die fünf Metadatenfälle mit ungültigem Eingabehash bereiten einen echten
  Quellenplan vor, aber kein für diese Aussage unnötiges Metadatenergebnis.
  Alle anderen Metadatenprüfungen behalten ihre vollständige Vorbereitung.
- Die neun Release-Blockerablehnungen und die Prüfung der erhaltenen originalen
  Auswertungsreihenfolge verwenden das kleine native Register. Reviews,
  Readiness, Writer, Versiegelung, Archivprüfung und Quellbyteprüfungen bleiben.

## Erhaltene vollständige Referenzen

Die Quellartenprüfungen in `test_merge_target_right.py` und
`test_merge_metadata_right.py` sowie die CLI-Quellenprüfung in
`test_merge_resolution_right.py` behalten ihre bisherigen vollständigen Daten
für lokale, Git-, Baseline- und Bundlequellen. Ebenso unverändert bleiben die
nativen Register-/Pakettests in `test_merge_sources.py`, alle bisherigen
Standardaufrufe in `test_project_bundle.py`, die allgemeine native
Release-Publikation und die drei vollständigen Merge-Publikationsreferenzen
`combined`, `effect:1` und `archived`. Writer-/Recovery-Abbrüche und Restore-CLI
bleiben unverändert. Keine Parametervariante oder fachliche Assertion entfällt.

## Regeln und Abnahme

Die [zentralen Testregeln](Testing.md#effiziente-testdaten-und-vorbereitung)
gelten für neue Tests und Überarbeitungen; DEVELOPMENT.md und tests/AGENTS.md
verweisen darauf. Der aktive Produktplan erhält keine Entwicklungsprotokolle.
Produktfortschritt bleibt 726/900, nächste Position 17.l.W. Nur die Bundlezahl
des vorbereiteten Zielstands wird nach erfolgreichem Apply wirksam.

Alle geänderten Testdateien, betroffene Helferaufrufer und die genannten
vollständigen Referenzen gehören zur ungefilterten Pflichtauswahl. Apply führt
deren Vereinigung mit seiner fälligen gefilterten N=3-Gruppe vor dem Commit aus.
Dev führt nur Syntax, reine Collection, statische Abdeckungserhaltung und native
Paketvalidierung durch. Die vorhandenen Testidentitäten, Nummern, Messhistorie,
Workerregeln und Gateprüfungen bleiben unverändert. Ein Laufzeitgewinn dieses
Bundles wird erst durch seine tatsächliche Ausführung belegt.
