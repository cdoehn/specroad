# Evidence erfassen (12.e.W/R/C)

`specroad.authoring.evidence` verbindet vorbereitete native Evidence mit dem
bestehenden gespeicherten Change Plan und dessen Writer. Der kleinste nutzbare
Ausschnitt veröffentlicht genau einen neuen, unveränderbaren Nachweis. Die
globale CLI-Registrierung ist noch offen; die API setzt einen Host mit
vollständigem `TargetModel`, expliziten IDs und realen Berechtigungen voraus.

```python
preview = preview_evidence_record(
    model, verification_id, record,
    actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
    configuration_id=configuration_id, request_id=request_id,
    gates=host_gates,
)
# Erst nach erfolgreicher Zielprüfung den gespeicherten Plan verwenden.
plan = ChangePlan(canonical_json_bytes(preview["plan"]))
result = record_evidence(
    plan, model, transaction_id=transaction_id,
    authority=publication_authority, gates=host_gates,
)
```

`record` ist ein vollständiger `RecordArtifact` aus dem Konstruktor in
`specroad.verification`, ergänzt um gegebenenfalls ausdrücklich deklarierte
Anhänge. Der Planner rekonstruiert diesen Wert aus den tatsächlichen
Requirement-, Contract- und optionalen Testbytes. Actor und Planzeit müssen zu
den Auditfeldern passen. Die explizit ausgewählte Konfiguration wird aus dem
gelieferten Modell aufgelöst. Gelieferte Hashlabels ersetzen keine Eingänge.

Der Host führt aktuelle, reservierte und historische IDs im `TargetModel`.
Eine bekannte ID darf nicht wiederverwendet werden. Der W-Adapter erzeugt keine
Identität und entdeckt keine Historie. Die unter Writer-Lock überprüften
Projektdateien müssen zum vollständigen gelieferten Inventar passen.

Attachments sind zunächst vorhandene Projektressourcen mit exaktem Pfad,
Medientyp, Größe und SHA-256. Ihre Bytes sind im `TargetModel` enthalten und
werden vor der Veröffentlichung erneut geprüft. Externe Dateien werden von
dieser API nicht importiert. Die vorhandenen Ressourcen bleiben unverändert.

`read_evidence_record_input` liest vollständiges Record-JSON und optional eine
explizite Run-JSON-Datei. `parse_evidence_record_input` bindet dafür
`VERIFICATION-ID --input FILE|- [--run-context FILE] [--configuration ID]` als
Argumentteil eines Hosts. Standardinput wird nur bei ausdrücklichem `-`
verwendet. Eine Run-Datei darf fehlenden `run_context` liefern oder denselben
Wert wiederholen; eine widersprüchliche Herkunft wird mit Exit 3 abgewiesen.
Unbekannte Herkunft bleibt `null` mit ausdrücklichem Grund. Ein vorhandener
gleichnamiger Lauf mit widersprüchlichem Produkt oder Produktstand ist ein
Konflikt. Gemeldete Ergebnisse werden weder verbessert noch ausgeführt.

Seit `12.e.R` darf das vollständige `run_context`-Feld in der Quelldatei fehlen,
wenn keine Run-Datei gewählt wurde und ein ausdrücklich übergebener, nichtleerer
`unbound_reason` vorliegt. Nur dann materialisiert der Eingabeadapter `null`.
Ein teilweise gefülltes Run-Objekt wird weder ergänzt noch in `null` umgewandelt.
Andere fehlende Mess- oder Auditfelder bleiben Fehler. Begründungen werden nicht
erfunden; Git-HEAD, Modellwurzel, Uhrzeit und vorhandene Contract-Slots liefern
keine Ersatzwerte. Eine gebundene Konfiguration muss auch dann ausdrücklich
ausgewählt werden, wenn das Modell genau eine Konfiguration enthält.

Syntaktisch ungültige Verification-/Konfigurations-IDs und falsche Artefakttypen
werden vor dem Lesen der Eingabedateien oder von Standardinput zurückgewiesen.
Dateifehler lösen keinen Standardinput-Fallback aus. Ein explizites `null` darf
nicht durch eine Run-Datei überschrieben werden. Für später bekannt gewordene
Herkunft bleibt ein neuer Nachweis mit eigener ID erforderlich.

Vorschau und Ausführung verwenden denselben nativen Plan. Die Vorschau schreibt
nichts. Die Ausführung übernimmt Autorisierung, Writer-Lock, erneute Eingangs-
und Zielprüfung, Journal, atomare Veröffentlichung, Receipts und Cleanup des
vorhandenen Writers. Der Request-Receipt nennt die neue Evidence-ID; eine
identische bestätigte Wiederholung liefert den ursprünglichen Beleg ohne
zweiten Nachweis. Derselbe Request mit anderem Inhalt scheitert. Eine historische
Wiederholung behauptet keine erneute Aktualitätsprüfung.

Ein im Eingang ausgelassenes, ausdrücklich begründetes Run-Feld und ein
gleichbedeutendes explizites `null` ergeben dieselbe normalisierte Request-Absicht.
Eine andere Begründung ist dagegen anderer Inhalt und bei derselben Request-ID
ein Konflikt. Historisches Replay schreibt inzwischen veränderte Subjects nicht
zurück. Neue Erfassung verändert weder deren Revision noch
`verification_plan_status`; auch ursprüngliche nichtkanonische Datei-Bytes
bleiben erhalten. Ein alter Nachweis wird nicht automatisch an inzwischen
geänderte Subject-, Contract- oder Testrevisionen neu gebunden.

Der obligatorische Gate `extension:evidence-record` bindet das gesamte Ziel.
Mitgelieferte Standardgates decken ausschließlich den neuen Nachweis und dessen
konkrete Eingänge ab. Für weitere vorhandene Lifecycle-, Currentness- oder
Ressourcen-Subjects muss der Host die wirklichen Dienste bereitstellen; fehlende
Dienste blockieren die Veröffentlichung. Eine KI erhält durch vorbereitete
`recorded`/`approved`-Felder keine direkte Schreibfreigabe. CI benötigt weiterhin
eine Request-ID. Bestehende Subjects und Nachweise werden nicht umgeschrieben.

Der W-Nachweis umfasst echte Speicherung und Replay auch im isolierten Core und
PYZ. Er belegt keine vollständige CLI-Integration, authentische externe
Testausführung, bestandene Projektverifikation oder Release-Freigabe. Die
R-Nachweise prüfen zusätzlich Eingabegrenzen, unbekannte Herkunft sowie den
Erhalt bestehender Revisionen und Planungszustände.

In `12.e.C` sind das Lesen und Normalisieren des Record-Inputs, die Auflösung
der tatsächlichen Subject-Bytes und die Bindung vorhandener Attachments in
kleine interne Helfer getrennt. Referenzprüfung und Fehlerübersetzung bleiben
am öffentlichen Eingaberand. Vorschau und Speicherung delegieren weiterhin
direkt an den gemeinsamen Change-Plan-/Writer-Pfad; es gibt keinen eigenen
Datei-Writer. Prüfungsreihenfolge, Gate-Bindungen, Request-Absicht und zulässige
Seiteneffekte bleiben unverändert. Die bestehenden W/R-Nachweise und ihre
Testidentitäten werden für diese Bereinigung unverändert wiederverwendet.
