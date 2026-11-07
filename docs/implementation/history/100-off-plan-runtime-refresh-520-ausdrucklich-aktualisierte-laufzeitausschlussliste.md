# OFF-PLAN RUNTIME-REFRESH-520: ausdrücklich aktualisierte Laufzeitausschlussliste

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RUNTIME-REFRESH-520: ausdrücklich aktualisierte Laufzeitausschlussliste

**Nutzerauftrag vom 30. Oktober 2026:** Nach der abgeschlossenen gezielten
Nachholmessung wird die feste Ausschlussliste einmalig neu berechnet. Dies ist
eine ausdrücklich beauftragte Ausnahme für diesen Datenstand zu WORKFLOW-514;
keine automatische Neuberechnung und keine allgemeine Lockerung von 2.5.

- [ ] **RUNTIME-REFRESH-520:** Die neue Liste und diesen Nachweis nach dem
  erfolgreichen parallelen Apply-Gate gemeinsam committen.
- Historische vollständige Messungen: **22.263**, unverändert übernommen.
- Zusätzlich gemessene neue Tests: **215**, alle vollständig erfolgreich;
  keine bereits gemessenen Tests erneut zur Laufzeitbestimmung ausgeführt.
- Abdeckung: **22.478/22.478 Testidentitäten**. Dies ist eine Zusammenstellung
  historischer Laufzeiten verschiedener Quellstände, kein aktueller Vollsuitelauf
  und kein Nachweis, dass alte Laufzeiten auf dem neuen Stand unverändert wären.
- Auswahl: floor(22.478/5) = **4.495** langsamste Tests nach setup+call+teardown;
  Gleichstand weiterhin nach Testidentität. **17.983** bleiben zugelassen.
- Gegenüber der bisherigen Liste: **184** neu ausgeschlossen,
  **141** wieder zugelassen. Davon sind **184**
  neue Testidentitäten ausgeschlossen. Die Auswahlregel bleibt unverändert.
- Die drei ursprünglichen Messherkünfte bleiben mit Quellhash, Journalhash,
  Identitäten und Änderungsinventar gebunden. Die Originaljournale bleiben
  unverändert; alte Laufzeiten werden nicht als neu gemessen bezeichnet.
- Unverändert: N=3, Testnummern und Rotationsanker, ungefilterte gezielte
  Dev-Auswahl und manuelle Vollsuite. Dieser Commit schaltet nur nach seinem
  erfolgreichen Apply-Gate die bestehende Rotation regulär weiter.
- Produktstand bleibt **650/900**, zuletzt **15.l.R**, nächstens **15.l.C**.
  Es gibt keine Produktimplementierung, keine künstliche W/R/C-Folge und
  keinen Start oder Neustart eines Dienstes oder Dev-Modells.

Neue Messbasis: `080b0477f269c4d159cd39987e16aaab369364140a1afb2e668c690809fd9ff0`.

Zusammengesetzter Messbericht: `3450e1d5b21090ec55ca01aa6cd1e52aecd78ea4a6cc5a0afb0f928eecd2e0e3`.

Alte feste Liste: `ebf60e61ff731f5144dae5ad05d98879acc66563f6247cf520d088bd47ef006b`.

Neue feste Liste: `8ed182c83f7f36cdd850d527224d1521af96fcbcf95c67357dc2d325a7c79e95`.

Commit: `test(workflow): Laufzeitausschlussliste nach gezielter Nachholmessung aktualisieren`.

Der ursprüngliche OFF-PLAN-Setup legte dieses Dokument mit offenen Produktpositionen an. Revision 2 ergänzt die Audit-Nacharbeiten und bereinigt überholte Testanweisungen als **OFF-PLAN / AUDIT-PLAN-UPDATE**, Commit-Message `docs(plan): Audit-Nacharbeiten vor 5.t konkretisieren`. Sie implementiert keine Produktreparatur und erhöht den Produktzähler nicht. Die Bundle-Nummer 047 bezeichnet diese Übergabe und zählt keine zusätzliche Produktposition. Ein erzeugtes ZIP oder ein hier formulierter Test ist kein abgeschlossener Commit und keine Test-Evidence; maßgeblich sind der tatsächlich entstandene Commit und sein Apply-Result.

Revision 3 ergänzt auf ausdrücklichen Nutzerauftrag den portablen SpecRoad-/
PatchHarbor-Rundweg als **OFF-PLAN / PH-RUNTIME-PLAN**, Bundle **233**, mit der
Commit-Message `docs(spec): Portablen PatchHarbor-Rundweg spezifizieren und planen`.
Diese Übergabe enthält ausschließlich Spezifikation, Plan und notwendige
maschinelle Katalogbindungen. Sie implementiert das Feature nicht und erhöht
den abgeschlossenen Produktstand nicht: **380/900**, nächster Commit **8.l.C**.

Fünf neue Schritte ergänzen die bisherigen 295: **15.m–15.o** nach dem bestehenden
Bundlekern sowie **18.q–18.r** nach dem vollständigen Proposal-Lifecycle. Jeder
besitzt echte W/R/C-Zustände, insgesamt 15 zusätzliche Produktpositionen. Alle
alten Schrittkennungen bleiben erhalten. Die aktuellen Positionsnummern ab M16
verschieben sich um 9 und ab M19 um 15; historische Audit-/Ergebnisangaben mit
dem damaligen Nenner 885 werden nicht umgeschrieben. Die Meilensteine bleiben
in ihrer bisherigen Reihenfolge. M20 übernimmt die zusätzliche Gesamtmatrix
in seinen vorhandenen Schritten 20.f, 20.h und 20.m.

Nach tatsächlich erfolgreich ausgeführten, zum Commit passenden Verhaltenstests wird die betreffende Checkbox im selben Git-Commit gesetzt. Reguläre Produktcommits aktualisieren den Produktzähler; Audit-Nacharbeiten aktualisieren ausschließlich ihren Status und `next_audit_step`. Ein fehlgeschlagener Schritt bleibt offen. Git ist die Historie; das Dokument nimmt keinen eigenen noch unbekannten Commit-Hash auf. Vor dem nächsten Auftrag werden tatsächliche Git-Historie, Result-Logs und Planfortschritt abgeglichen. Bei Inkonsistenz nicht einfach weiterzählen.
