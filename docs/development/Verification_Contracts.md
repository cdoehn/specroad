# Verification Contracts und direkte Testziele

`specroad.verification` stellt die Daten-API für Planstand `12.a.R` bereit.
Sie arbeitet ausschließlich mit übergebenen Originalbytes und einem vollständigen
supplied `TargetModel`; sie öffnet oder startet keinen referenzierten Testcode.

- `VerificationContract(raw, path=...)` liest einen vorhandenen Verification-Record.
  Native Feld- und Relationsverträge gelten. Jede deklarierte Dimension braucht
  mindestens einen Slot, jeder `check_id` bleibt eindeutig. Der Reader ergänzt
  keine fehlenden Daten.
- `VerificationTest(raw, path=...)` prüft Testidentität, Typ und Oracle. Externe
  Testbezeichner und projektinterne Pfade bleiben passive Metadaten.
- `prepare_verification_contract(value, path=...)` bereitet ausschließlich einen
  neuen Entwurf mit Revision 1 vor. Nur bei fehlendem `evidence_slots` und ohne
  zusätzliche Dimensionen materialisiert er den normativen `overall`-Slot.
  Explizit leere oder ungültige Slots werden abgewiesen. Der Kandidat wird weder
  geschrieben noch als Change Plan oder Freigabe behandelt.
- `resolve_verification_contract(model, subject_id, contract_id)` bindet ein
  konkretes `verified_by`-Paar an den tatsächlichen Contract, seine deklarierten
  Subjects und vorhandenen Testrecords. Alle Slots erscheinen als Pflichtprüfungen
  mit `(subject_artifact_id, contract_id, test_id, check_id)` und Dimension.
  Mehrere Checks desselben Tests bleiben getrennt. Die Ausgabe sortiert die
  Pflichtprüfungen deterministisch; die Quelldeklaration bleibt unverändert.
- `resolve_verification_target(model, subject_id, target_id)` löst entweder einen
  expliziten Contract mit identischem Ergebnis zur bestehenden API oder einen
  direkt über `verified_by` gebundenen Test auf. Dessen eigener Artefaktbezeichner
  wird `contract_id` und `test_id`, der einzige Slot ist `overall`. `contract`
  bindet den tatsächlichen Testrecord; `implicit_contract` beschreibt die
  abgeleiteten Slots und Dimensionen. Es entsteht kein Verification-Record und
  keine aus dem Testtyp geratene Methode oder Konfigurationspolicy.

Die Auflösung enthält Revisionen, Pfade, Originalbyte- und kanonische Recordhashes,
die konkrete Relation sowie die Modellbindung. Rückgaben sind vom Eingabeobjekt
getrennt; ihre Wahrheit als boolescher Erfolgswert ist nicht definiert.
`validation_scope=supplied_model_explicit_subject_contract` beziehungsweise
`supplied_model_implicit_test_contract` begrenzt den Nachweis auf dieses Paar.
Die Ausgabe behauptet weder Live-Dateiprüfung noch vollständige
Modellvalidierung, Projektpflichtmenge, Konfigurationsanwendbarkeit, aktuelle
Evidence, Testausführung oder Schreib-/Freigabeautorität.

Der spezialisierte Reader `resolve_verification_contract` akzeptiert weiterhin
ausschließlich explizite Verification-Records. Für beide Zielarten verwendet
der Aufrufer `resolve_verification_target`. Fehlende Pflichtdimensionen, fremde
oder ungültige Test-IDs, unvollständige Contracts/Testmetadaten und ungültige
Relationen werden mit nativen maschinenlesbaren Diagnosen abgewiesen. Es gibt
keinen Fallback über Titel, externe Testnamen oder Pfade.
Projektweite Aggregation, Evidence-Auswertung und Transaktionen bleiben den
folgenden Planschritten vorbehalten.
