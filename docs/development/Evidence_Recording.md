# Evidence erfassen (12.e.W)

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

Vorschau und Ausführung verwenden denselben nativen Plan. Die Vorschau schreibt
nichts. Die Ausführung übernimmt Autorisierung, Writer-Lock, erneute Eingangs-
und Zielprüfung, Journal, atomare Veröffentlichung, Receipts und Cleanup des
vorhandenen Writers. Der Request-Receipt nennt die neue Evidence-ID; eine
identische bestätigte Wiederholung liefert den ursprünglichen Beleg ohne
zweiten Nachweis. Derselbe Request mit anderem Inhalt scheitert. Eine historische
Wiederholung behauptet keine erneute Aktualitätsprüfung.

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
Vervollständigung und Bereinigung folgen in den getrennten Schritten 12.e.R/C.
