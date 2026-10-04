# AUDIT-REC-05.U – unveröffentlichter Discard nach echtem Neustart

**Entscheidung vom 4. Oktober 2026: bestätigt, begrenzt auf den fehlenden
Produktweg zur Rekonstruktion des unabhängigen Discardnachweises.** Der bestehende
Discardkern verweigert unzureichende Eingaben sicher. Aus dem eigenen erhaltenen
Projekt-/Transaktionsbestand stellt das Produkt den verlangten
`PublicationPreflight` jedoch nicht wieder her. Der notwendige zusätzliche
Originalplan wird vom untersuchten Journal-/Stagingpfad nicht gespeichert.

Ein Gegenbeispiel grenzt den Befund ein: Mit einem zusätzlich extern gespeicherten
Originalplan und einem eigens für die kleine Fixture gebauten Adapter lässt sich
der Preflight aus persistenten Daten neu erzeugen. Discard funktioniert dann in
einem echten Folgeprozess. Weder ist das Pythonobjekt prinzipiell unreproduzierbar,
noch ist seine Schutzprüfung der zu beseitigende Fehler. Es fehlt der belegte
öffentliche Neustartweg aus der vorgesehenen persistenten Recoverygrundlage.

Dieser U-Schritt ändert kein Produktverhalten. Er konkretisiert
`AUDIT-REC-05.W/R/C` im [Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Die Requirementnachweise bleiben `partial`, der Produktstand bleibt 237/885.

## Bindung und Ausgangsstand

- Result: `specroad-apply_Result_131124_1004_93e82b.zip`.
- Result-SHA-256: `9ab58d3a5772bf9f8ef7edd6ff8fd291e3aca172357b851f3797f3cb97729c6a`.
- Basiscommit: `762f8900ec183c5870ffba9b118fe50b6af913d0`.
- Repository-ID: `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.
- Fingerprint: `7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.
- Spezifikation 0.2.7, SHA-256: `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.

Das Result bestätigt Bundle 062 einschließlich C-Commit
`refactor(recovery): centralize auxiliary file bindings and durability`, sauberem
Apply-Zustand und je 5.545 erfolgreichen Tests parallel und seriell. Alle 1.431
Base-Dateien wurden gegen Größe, Git-Blobhash und lokale Bytes abgeglichen;
staged/unstaged Änderungen und untracked Nutzdateien liegen im Result nicht vor.

[Beobachtungen](SpecRoad_AUDIT_REC_05_U_observations.json) binden Result,
Spezifikation, Probeprogramm und untersuchte Quellen per SHA-256. Projektwurzeln,
Journalhashes und Autorisierungen der Diagnose gehören ausschließlich zu eigenen
synthetischen temporären Projekten. Sie autorisieren kein Nutzerprojekt.

## Methode

Das [Probeprogramm](SpecRoad_AUDIT_REC_05_U_probe.py) verteilt 16 Fälle auf vier
pytest-xdist-Worker. Jeder Fall startet einen frischen Writerprozess und erst
nach dessen Ende einen separaten frischen Recoveryprozess. Keine Pythonobjekte
oder laufenden Writerdeskriptoren werden übernommen; beide Kinder starten über
`python -I -B` mit neu importierten Produktmodulen.

Der Writer verwendet die vorhandene öffentliche Publikations-/Journalstrecke
für ein gültiges Goal und ein Coreprofil. Er hinterlässt entweder `building`,
vollständig `prepared` oder ein natives 17-Byte-Präfix der ersten Stagingdatei
bei weiterhin `building`. Der letzte Fall endet unmittelbar nach dem echten
Write und `fsync` mit `os._exit(23)`. Building und Prepared werden jeweils mit
ordnungsgemäßer Lockfreigabe und abruptem Prozessende untersucht. Insgesamt
bleiben in sechs Fällen echte verwaiste Writerlocks zurück.

Für jede dieser fünf Vorbereitungsvarianten gibt es zwei Eingabemengen:

1. `journal_only`: erhaltene Projektdateien und der vom Produkt hinterlassene
   Transaktionsbestand; kein Originalplan, kein Preflight.
2. `saved_plan`: dieselben Daten plus die vom Diagnosewriter ausdrücklich
   außerhalb des Projekts gespeicherten Originalbytes des Change Plans.

Der zusätzliche Adapter im zweiten Fall zählt die aktuellen normativen
JSON-Pfade selbst auf, liest deren Bytes, komponiert das Coreprofil und bindet
`TargetModel` an den tatsächlichen Projektroot. Er verwendet weder die im Journal
behauptete Pfadliste noch das Elternprozess-Oracle als Inventur. Anschließend
ruft er den öffentlichen `prepare_publication_check` mit dem gespeicherten Plan
und einer explizit registrierten Testpolicy auf. Dies führt erneut Fachplanung
aus und ist ausschließlich ein Gegenbeispiel für diese Goal/Core-Fixture;
es ist kein allgemeiner Recoveryloader oder vorhandener Produktadapter.

Der Elternprozess behält unabhängige ursprüngliche Byte-/Wurzelhashes nur zur
Ergebnisprüfung. Der Recoveryprozess liest dieses Oracle nicht. Er erwirbt einen
neuen nativen Recoverylock beziehungsweise übernimmt den tatsächlich als `dead`
ermittelten Eigentümer mit `transaction_recovery_lock`, erwartetem Lock-/Journalhash
und frischer synthetischer Autorisierung. Er ruft Discard explizit auf und prüft
danach den Zugang eines neuen Writers. Eine auditierte Lockübernahme kann eigene
Betriebsbelege erzeugen, auch wenn der anschließende Discard abgewiesen wird.

Sechs weitere Fälle kombinieren Building/Prepared mit einer veränderten Basis,
einem zusätzlichen gültigen Goal oder einem anderen gültigen Plan mit abweichender
Request-ID. Die ersten beiden Änderungen erfolgen nach Writerende. Der dritte
Plan besitzt dieselbe Basis und Zielwirkung, aber eine andere Transaktionsbindung.

Der finale Diagnoselauf erhob **16 Fälle parallel in 6,32 s** auf CPython 3.14.4
unter Linux. Ein grüner Diagnoselauf bestätigt die Erhebung und den Aufbau,
keine Reparatur des beobachteten Produktstands. Das Programm friert die gefundenen
Ablehnungsgründe nicht als permanente Fehlererwartungen ein und gehört nicht zur
regulären, auf `tests/` begrenzten Produktsuite.

Reproduktion mit installierten Dev-Abhängigkeiten:

```sh
.venv/bin/python -I -B docs/reviews/SpecRoad_AUDIT_REC_05_U_probe.py --output /tmp/specroad-audit-rec-05-new.json
```

Die Ausgabedatei muss neu und außerhalb des Repositorys sein. Die Probe akzeptiert
keinen frei angegebenen Produktprojektpfad; sie erzeugt und verändert nur eigene
temporäre Fixtures. Spätere Produktstände dürfen andere Beobachtungen liefern.

## Ergebnisse

| Eingaben und Zustand | Anzahl | Beobachtung |
|---|---:|---|
| Eigener Projekt-/Transaktionsbestand, unveränderte Basis | 5 | Discard verweigert mit Code 2, `recovery_base_preflight_required`; neuer Writer bleibt blockiert |
| Zusätzlich gespeicherter Originalplan, unveränderte Basis | 5 | Preflight aus Dateien neu erzeugt; Discard abgeschlossen, Archiv und Receipt erzeugt, neuer Writer zugelassen |
| Zusätzlich gespeicherter Plan, vorhandenes Goal geändert | 2 | Rekonstruktion verweigert mit Code 3, `target_base_root_mismatch` |
| Zusätzlich gespeicherter Plan, gültiges Goal hinzugefügt | 2 | Vollständige Inventur verändert die Basiswurzel; Code 3, `target_base_root_mismatch` |
| Anderer gültiger Plan, unveränderte Basis | 2 | Rekonstruktion möglich, Discard verweigert mit Code 6, `recovery_inventory_unproven` |

In allen Fällen meldet das geladene Journal null veröffentlichte Ziele. Die
schreibfreie Diagnose ohne Preflight behauptet keine Discarderlaubnis. In den
fünf erfolgreichen Fällen entspricht die unabhängig rekonstruierte Basiswurzel
dem ursprünglichen Writer-Oracle; das Result meldet `normative_writes: 0`.
Die eigenständigen Vor-/Nachhashes bestätigen in allen 16 Fällen unveränderte
normative Bytes während Recovery. Alle ursprünglichen Workdateien einschließlich
des Originaljournals und des kurzen Stagingpräfixes bleiben bytegenau erhalten,
bei Erfolg im gebundenen Auditarchiv. Eine vollständige Syscall-Writezählung ist
nicht Teil dieser Probe.

## Ursache und Einordnung

`discard_unpublished_transaction` und `_recovery_inputs._unchanged_base` verlangen
einen echten `PublicationPreflight`. Letztere Funktion rekonstruiert das erwartete
Journal aus diesem unabhängigen Objekt, vergleicht sämtliche gebundenen Werte
und prüft danach die vollständige aktuelle Inventur und ihre Bytes. Das verhindert
zu Recht Erfolg durch bloße Selbstkonsistenz unzureichender Journalangaben.

`_journal_inventory.prepare_building_journal` bindet Planhashes, Quellen-/Zielhashes
und Inventuren, speichert aber keinen vollständigen Originalplan.
`PublicationPreflight.data` ist ein Diagnoseformat mit Hash-/Pfadangaben, keine
Serialisierung des gesamten Nachweises. Der öffentliche Konstruktionseinstieg
`prepare_publication_check` erwartet wieder Modell, Change Plan und Policy.
Ein nachgelagerter Produktaufrufer, der diese Eingaben aus dem Recoverybestand
rekonstruiert, ist nicht vorhanden. Die bisherigen positiven Discardtests erhalten
das von der ursprünglichen Vorbereitung erzeugte Objekt im Speicher.

Die Scopegrenze ist fachlich fällig: 5.p.W sagt das Verwerfen unveröffentlichter
Vorbereitung bei unveränderter Basis zu. SR-REQ-0257/0458, §10.7 und Anhang C.3
grenzen dessen Zulässigkeit ein. Anhang N.1 behandelt den Prozessneustart bei
erhaltenen Dateien ausdrücklich und verlangt für laufende Transaktionen Journal,
Staging und Before Images; ein fortlebendes Speicherobjekt ist keine Grundlage.
Die fünf erfolgreichen Gegenbeispiele zeigen einen möglichen Datenweg, aber
gerade seine zusätzliche externe Eingabe und Testintegration bleiben ungedeckt.

5.t plant den automatischen read-only Transaktionspreflight, 5.v die umfassende
Crashmatrix. Die späteren Snapshot-/Resumeaufgaben in Meilenstein 6 und
Vollquellen-Restore in 15.j beschreiben andere Eingaben und Operationen. Keine
dieser Positionen übernimmt konkret den bereits zugesagten expliziten Discard
aus 5.p. Die pauschale Verschiebung in den drei Requirementmanifests und der
Entwicklungsbeschreibung wird deshalb durch `AUDIT-REC-05.W/R/C` ersetzt.

Die Folge beginnt mit einem belegten Neustartfall für vollständiges Prepared,
erweitert anschließend Building, unterbrochene Vorbereitung und sichere
Wiederholung und trennt zuletzt die Struktur. Die genaue API und persistente
Nachweisform werden bei der Umsetzung bestimmt. Vollständigkeit, unabhängige
Basisbindung, frische Autorisierung und Beweiserhalt werden nicht abgeschwächt.

## Grenzen des Nachweises

Die Probe untersucht ein kleines gültiges Goal/Coreprojekt auf dem aktuellen
nativen Linux-Dateisystem. Sie beweist keine allgemeine Profil-/Ressourcenladung,
keine Hostmigration, keinen Stromausfall und keine vollständige Crashmatrix.
Abbrüche erfolgen im Writer; Abbrüche während des Discardabschlusses werden hier
nicht neu untersucht. Fehlende Dateien, Symlinks, weitere Planoperationen und
Publikationszustände sind keine zusätzlichen dynamischen Fälle dieser U-Probe.
Die bestehenden Schutzverträge bleiben für die Korrektur verbindlich.

Die vollständige Produktsuite wird für dieses Bundle separat parallel geprüft.
Der Apply-Entrypoint muss für den einzigen Bundlezustand den parallelen und
zusätzlich den seriellen Volltest bestehen, bevor er den U-Commit erstellt.
Weder ZIP-Erstellung noch dieser Bericht ersetzen den späteren Apply-Nachweis.
