# Bundle 629 — Nativer Dokumentprüfer für die Merge-Testvorlage

8. November 2026. Maßgeblich ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_053746_1108_70cf4e.zip`, SHA-256
`4efc475b675621aefbc537126690d123795ca135c1a1d0e8c4ff43b4eebebb11`.
HEAD bleibt `3a03be16a03524e140b948a7f4236f58ae8aaa0b`; der erhaltene
Arbeitsstand hat Fingerprint `2e12a3123bc57c18` mit `patchharbor-state-v1`.

## Beobachteter Fehler und Ursache

Bundle 628 hat keinen Commit erzeugt. Das Gate von `17.l.W` endete nach
ungefähr 69 Minuten mit Exit 1. Die nativen Beobachtungen enthalten 11.481
bestandene Identitäten, 41 Setupfehler und drei fehlgeschlagene Identitäten
einschließlich des `merge.plan`-Untertests der Befehlsbeispiele. Die abweichende
pytest-Untertestzählung ist kein zusätzlicher Erfolgsnachweis.

Die [vorige Korrektur](bundle-628-merge-work-correction.md) ergänzte das
erforderliche Hauptdokument. Der Fixture-Host übergab der nativen Baseline-
Vorbereitung dabei weiterhin keine `document_model`-Prüfung. Diese Prüfung ist
bei vorhandenen Dokumenten erforderlich; die korrekte Ablehnung
`VALIDATION_UNAVAILABLE` verhinderte deshalb bereits den Fixture-Aufbau und
die drei öffentlichen Beispielprüfungen. Die vorherigen Schema-, Registry-
und Git-Wächterkorrekturen bleiben unverändert erhalten.

## Korrektur und Abdeckung

Die kleine Testvorlage registriert ausdrücklich einen vertrauenswürdigen
Dokument-/Abschnittsprüfer. Er verwendet die vorhandenen nativen Kerne für
die Hauptdokumentrolle und die Abschnittszuordnung auf den tatsächlichen
Records des vorgeschlagenen Zielzustands. Die Abhängigkeiten umfassen dessen
gesamte geladene Modellmenge. Content-Blocks und Views werden ohne ihren
erforderlichen Spezialisten ausdrücklich abgelehnt. Es gibt keinen
Erfolgs-Stub, keine erfundene Freigabe und keine Änderung am Produktvalidator.
Der Baseline-Erzeuger prüft weiterhin selbst die vollständigen Objektbytes,
das neu versiegelte Artefakt und dessen Lifecycle.

Vier neue Fälle prüfen die native Baseline-Vorbereitung mit gültigen Daten,
fehlendem Hauptdokument, verwaistem Abschnitt und nicht unterstützter
Blocksemantik. Sie belegen zusätzlich die unverändert negative Antwort bei
fehlendem Dokumentprüfer und die Schreibfreiheit der Vorbereitung. Alle
bisherigen Test-IDs, Varianten und Pflichtdateien bleiben erhalten; neue
Testnummern werden angehängt. Die 44 nicht bestandenen Identitäten des
aktuellen Results sind ausdrücklich in der Pflichtauswahl enthalten.

## Übergabe und offener Rest

Die einzige Stage führt weiterhin die komplette offene ID `17.l.W`, ihre
Rolle `implementation` und die exakte Plan-Commitnachricht fort. Sie bindet
alle erhaltenen Vorherbytes an dieses neue Result und bewahrt den bereits
erfolgreichen Klärungscommit `MERGE-WORK-627`. Es gibt keine neue Klärung und
keine Wiederholung erfolgreicher Commits.

In Dev wurden ausschließlich statische Prüfung, reine Collection und native
Paketprüfung vorgenommen. Das Apply-Gate bleibt die Vereinigung aus der
weiterhin fälligen gefilterten N=3-Gruppe und sämtlichen Pflichtfällen.
727/900, `17.l.W` als abgeschlossen und Bundle 629 sind nur der vorbereitete
Zielzustand nach erfolgreichem Gate und tatsächlichem Commit; bestätigt
bleiben 726/900. `17.l.R/C` und die vollständige M17-Abnahme sind offen.
Control, Watcher, lokale Konfiguration und Timeout werden nicht verändert.
