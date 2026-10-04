# AUDIT-REC-04.U – Wiederanlauf nach kurzen Recovery-Hilfsdateien

**Entscheidung vom 4. Oktober 2026: bestätigt.** Das bestehende Schreibprotokoll
hinterlässt bei einer Unterbrechung eigene leere beziehungsweise kurze Dateien,
die den erneuten expliziten Recoveryaufruf trotz intakter Quellen blockieren.
Die konservative Ablehnung fremder oder ungebundener Dateien bleibt erforderlich.
Die Korrektur muss daher den eigenen unterbrochenen Schreibversuch nachweisbar
fortsetzbar machen; bloße Präfixgleichheit reicht dafür nicht.

Die Untersuchung erfüllt die U-Position im
[Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Sie verändert kein Produktverhalten. `AUDIT-REC-04.W/R/C` sind dort als konkrete
offene Folge eingetragen; der Produktstand bleibt 237/885 und `5.t.W` gesperrt.

## Bindung

- Maßgebliches Result: `specroad-apply_Result_064106_1004_c04f19.zip`.
- Basiscommit: `efe11768f6f5f7ffbe2c87af28e36a14713ba8aa`.
- Repository-ID: `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.
- Fingerprint: `7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.
- Result-SHA-256: `0add878b118440a43e053a33fb6c2973cbc6fb32a3e444f97ad07656f43ca6b4`.
- Spezifikation 0.2.7, SHA-256:
  `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.
- Alle 1.423 Base-Dateien stimmen in Größe, Git-Blobhash und lokalen Bytes
  überein. Das Result enthält keine staged/unstaged Patches und keine untracked
  Nutzdateien. Bundle 057 ist mit passender Patchprüfsumme und Abschlusscommit
  bestätigt: 5.316 Tests parallel und 5.316 seriell im Apply-Result erfolgreich.

[Beobachtungen](SpecRoad_AUDIT_REC_04_U_observations.json) binden Result,
Probeprogramm, untersuchte Dateien und Spezifikation per SHA-256. Die enthaltenen
Projektwurzeln und Journalhashes stammen aus synthetischen temporären Projekten;
sie sind keine Bindung eines Nutzerprojekts und keine menschliche Autorisierung.

## Methode und Grenzen

Das [Probeprogramm](SpecRoad_AUDIT_REC_04_U_probe.py) erzeugt 50 unabhängige
temporäre Projekte und verteilt die Fälle über vier pytest-xdist-Worker.
Die vorhandenen nativen Publikationsfixtures erstellen ein vollständig
veröffentlichtes Ziel beziehungsweise einen vor dem zweiten Ziel unterbrochenen
Zwei-Dateien-Commit. Öffentliche Recovery-APIs erwerben bei jedem Aufruf einen
neuen nativen Recoverylock; der erwartete Journalhash wird erneut aus dem
persistenten Journal geladen. Das ursprüngliche Modell dient nur als unabhängiges
Byteoracle und wird den Recoveryaufrufen nicht übergeben.

Je zehn Schreibstellen werden in fünf Varianten beobachtet:

1. `empty`: Fehler im ersten `os.write`, nach der echten exklusiven Dateianlage.
2. `prefix`: Der echte Write schreibt 17 Bytes und liefert diese Zahl zurück;
   der nächste Write schlägt fehl. Der unveränderte Produktionswriter hinterlässt
   dadurch ein echtes eigenes Präfix.
3. `full_sync_response_lost`: Alle Bytes werden geschrieben und `fsync` tatsächlich
   ausgeführt; danach geht seine Rückgabe als kontrollierter I/O-Fehler verloren.
4. `foreign_after_prefix`: Nach dem unterbrochenen Versuch verändert ausschließlich
   die Gegenprobe den Hilfsdateiinhalt in widersprüchliche fremde Bytes.
5. `foreign_same_prefix`: Die Gegenprobe erhält den ursprünglichen eigenen Rest
   außerhalb des Fixtureprojekts und erzeugt am selben Pfad eine unabhängige Datei
   mit identischem Präfix und anderer Inode. Damit ist Präfixgleichheit ausdrücklich
   von eigener Herkunft getrennt.

Nach dem ersten Fehler werden zwei explizite Wiederholungen ohne weitere
Fehlerinjektion ausgeführt. Erfasst werden strukturierte Fehler, Journalzustände,
Datei-/Inhaltshashes, native normative Ersetzungen, exakte Basis-/Zielbytes und
der Erhalt ursprünglicher Before-/Staging-Images. Die Probe prüft ihren eigenen
Aufbau, friert aber die gefundenen Fehler nicht als Regressionserwartungen ein.

Der finale Diagnoselauf führte **50 Fälle parallel in 11,14 s** aus. Ein grüner
Diagnoselauf bedeutet, dass alle Beobachtungen erhoben wurden, nicht dass die
beobachteten Produktfehler behoben sind. Die vollständige bestehende Produktsuite
wird für die Übergabe separat parallel geprüft. Die Probe gehört nicht zum
regulären Requirement-Testkatalog; dessen Status und Testkennungen werden nicht
um vermeintliche Erfolgsnachweise ergänzt.

Die Fehler sind kontrollierte I/O-Unterbrechungen, kein Stromausfall und kein
hart beendeter Recoveryprozess. Die Wiederholungen laufen im selben Worker mit
freigegebenem und neu erworbenem Lock. Unabhängige Prozesse, alle möglichen
Bytelängen, Datenträgermodelle und jede weitere Crashgrenze sind damit nicht
nachgewiesen. Die umfassende Matrix bleibt 5.v; Discard nach Neustart bleibt
`AUDIT-REC-05.U`. Es wird kein serieller Entwicklungstest benötigt oder gestartet.

Reproduktion aus einer Entwicklungskopie mit installierten Dev-Abhängigkeiten:

```sh
.venv/bin/python -I -B docs/reviews/SpecRoad_AUDIT_REC_04_U_probe.py --output /tmp/specroad-audit-rec-04-new.json
```

Der Ausgabepfad muss neu und außerhalb des Repositorys sein. Das Programm nimmt
keinen echten Projektpfad entgegen; alle Projektmutationen bleiben in eigenen
temporären Fixtures. Ein späterer Produktstand darf andere Beobachtungen liefern.

## Ergebnisse

| Schreibstelle | Zustand nach eigener kurzer Datei | Beide Wiederholungen bei leerem/eigenem kurzem/fremdem Rest | Vollständige Datei mit verlorener Synchronisationsrückgabe |
|---|---|---|---|
| Initiales `journal.rollback` | `committing`, Teilpublikation bleibt | `recovery_journal_successor_conflict`, Code 6 | Basis und Abschluss erreicht |
| Rollbackkopie `rollback/0.bin` | `rolling_back`, Teilpublikation bleibt | `recovery_restore_stage_conflict`, Code 6 | Basis und Abschluss erreicht |
| `journal.rollback` nach Restauration | `rolling_back`, Basisbytes bereits vollständig | `recovery_journal_successor_conflict`, Code 6 | Abschluss ohne erneute Restauration |
| Terminales `journal.rollback` | `rolling_back`, Basisbytes bereits vollständig | `recovery_journal_successor_conflict`, Code 6 | Abschluss ohne erneute Restauration |
| Transaktionsreceipt beim Zielabschluss | `committing`, vollständiges Ziel | `recovery_receipt_conflict`, Code 6 | Zielabschluss ohne normativen Write |
| Requestreceipt beim Zielabschluss | `committing`, vollständiges Ziel | `recovery_receipt_conflict`, Code 6 | Zielabschluss ohne normativen Write |
| `journal.complete` | `committing`, vollständiges Ziel | `recovery_completion_marker_conflict`, Code 6 | Zielabschluss ohne normativen Write |
| Recoveryaudit `complete.json` | `committed`, vollständiges Ziel | `invalid_json`, Code 5 | Abschlussbelege bestätigt |
| Recoveryaudit `rollback.json` | `rolled_back`, vollständige Basis | `invalid_json`, Code 5 | Abschlussbelege vervollständigt |
| Rollbackreceipt | `rolled_back`, vollständige Basis | `recovery_receipt_conflict`, Code 6 | Abschlussbelege bestätigt |

In den **20 eigenen leeren/kurzen Fällen** bleiben beide Wiederholungen blockiert.
Die **20 Fremdgegenproben** bleiben ebenfalls blockiert, einschließlich der zehn
bytegleichen fremden Präfixe. Alle 40 Fälle erhalten bei beiden Wiederholungen
sämtliche Dateibytes und den Kandidaten am selben Pfad. Ein bereits terminaler
Journalzustand ist dabei noch kein erfolgreicher Recoveryabschluss mit allen
Pflichtbelegen.

Die **zehn Vollbyte-Kontrollen** schließen beide Wiederholungen erfolgreich ab.
Die erste Wiederholung führt nur noch nötige Basisrestauration aus; keine normative
Datei wird über Erstversuch und Wiederholungen doppelt ersetzt. Die zweite
Wiederholung führt in allen zehn Fällen null normative Ersetzungen aus. Alle
50 Fälle erhalten sämtliche ursprünglichen Before-/Staging-Images.

## Ursache und Vertragsentscheidung

`_staging_files._write_new` legt den endgültig verwendeten Hilfsdateinamen exklusiv
an und schreibt anschließend dessen Bytes. Bei Fehler erhält es den tatsächlichen
Teilzustand. `_recovery_rollback._ensure_exact_file`,
`_recovery_receipts.existing_recovery_record` und
`_recovery_completion._commit_recovered_journal` akzeptieren vorhandene Dateien
nur bei vollständiger Gleichheit. `_recovery_evidence.recovery_action` muss einen
vorhandenen Aktionsbeleg zuerst als JSON lesen; kurze JSON-Reste scheitern davor.

Das Journal und die Originalimages binden die benötigten vollständigen Inhalte;
die Hilfsdatei enthält jedoch keinen unabhängigen dauerhaften Nachweis, dass ihr
kurzer Rest vom früheren eigenen Versuch stammt. Ein leerer oder 17 Byte langer
Rest trägt insbesondere nicht notwendig Projekt-, Request-, Journal- und
Autoritätsbindung. Die fremde Datei mit demselben Präfix zeigt die Grenze einer
rein bytebasierten Freigabe.

Die Lücke betrifft die bereits zugesagte Wiederholbarkeit in **5.r.R** und die
Receipt-/Zielabschlussfolge in **5.q.R**, §10.7 und Anhang C.3 sowie
SR-REQ-0258/0459/0511. Die ebenfalls betroffenen terminalen Pflichtbelege aus
AUDIT-REC-02 berühren SR-REQ-0259/0462. Ein bekannt eigener Schreibrest darf den
zugesagten Ablauf nicht dauerhaft blockieren, wenn die gebundenen Quellen noch
intakt sind. Die heutige Ablehnung eines beim Neustart nicht eindeutig gebundenen
Restes ist dennoch richtig. Die Reparatur muss diese Informationslücke im
Schreibprotokoll schließen, ohne fremden Bestand zu überschreiben oder alte
zweifelhafte Präfixe pauschal als eigene zu deklarieren.

## Konkretisierte Nacharbeit

- **W:** Kleinster belegter Fall: unterbrochener initialer `journal.rollback`-Write,
  überprüfbare eigene Versuchsbindung beziehungsweise sichere Veröffentlichung,
  erneuter expliziter Abschluss auf die vollständige Basis und unveränderte
  Ablehnung fremder/ungebundener Kandidaten.
- **R:** Die weiteren neun belegten Schreibstellen und wiederholte Unterbrechung;
  vorhandene vollständige Belege und ihre Autoritätszuordnung erhalten, keinen
  normativen Effekt wiederholen und zulässige eigene Arbeitsreste mit dem
  bestehenden erhaltenden Cleanup vereinbaren.
- **C:** Gemeinsame Bindungs-, Wiederaufnahme- und Konfliktlogik ordnen, ohne
  Verhalten, Fehlerverträge oder erlaubte Seiteneffekte zu erweitern.

Die verbindlichen Abnahmen stehen im einen Implementierungsplan. Die fünf
betroffenen Requirementmanifeste führen jetzt bestätigte offene Korrekturen
statt einer noch ausstehenden Untersuchung. Sie bleiben `partial`; weder
U-Beobachtungen noch geplante W/R/C-Tests sind eine erfüllte Produktabnahme.

Commit-Message: `docs(recovery): confirm interrupted helper restart gaps`.
