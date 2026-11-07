# OFF-PLAN REFERENCE-SOURCE-551 — neuer vollständiger Referenzquellvertrag

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN REFERENCE-SOURCE-551 — neuer vollständiger Referenzquellvertrag

**Autorität:** ausdrückliche Nutzerentscheidung vom 3. November 2026,
„Wir legen ein neues Format fest“, mit anschließendem Auftrag zur erneuten
gründlichen Ausarbeitung. Technische Details werden innerhalb dieser
Entscheidung gemäß SPECROAD-DECISION-1 konkretisiert. Das ist keine behauptete
Einzelzustimmung zu jedem Feld und kein menschlicher Produktreview.

**Technische Basis:** nativ geprüftes Result
`specroad-apply_Result_215550_1102_1662e4.zip`, SHA-256
`6fd173d5778e8b153a3dbfc8324d5af50aa0439d226893e23a7d4db2ce5fef4b`,
sauberer HEAD `e17c8276ecaf9cb83f188aac0a8f556481386b81`.
Bundle 550 hat 16.a.W nach 6.310 Tests als
`e506617477a6510c1a1553584d358987bc2c07ee`, 16.a.R nach 6.426 Tests als
`81a978bd49eb8f4a219f5b1452a744ea02da535a` und 16.a.C nach 6.408 Tests als
`e17c8276ecaf9cb83f188aac0a8f556481386b81` abgeschlossen. Es waren Gruppen
0/1/2 mit 246/300/300 Pflichttests, keine Vollsuite. Fortschrittsrecord ist
completed; kompletter Snapshot entspricht exakt dem ausgelieferten C-Zustand.

Der vorherige N-Durchlauf blieb korrekt ohne Patch blockiert, weil Q.0s
Quellvertrag fehlte. Der manuelle Nutzerauftrag legt nun ausdrücklich einen
neuen Referenzvertrag fest. Seine Regeln werden nicht als alte externe Fakten
ausgegeben. Vorherige Blockade, Antworten, Laufzeitdaten und Control-Zustände
bleiben erhalten. Die hier vorbereitete Bundlenummer 551 gilt erst nach dem
erfolgreichen Apply-Gate UND tatsächlichen Dokumentcommit.

Genau ein Commit: `REFERENCE-SOURCE-551` mit Nachricht
`OFF-PLAN REFERENCE-SOURCE-551 docs(spec): Vollständiges 0.1-Referenzformat festlegen`.
Normative Grundlage ist Spec 0.2.49/Q.0.1 mit vollständig bytegebundenem
Vertrag `specroad-reference-0.1` / `1.0.0`. Produktstand bleibt **663/900**,
nächster Produktcommit **16.b.W**; keine Produktcheckbox wird abgeschlossen.

Klassifikation: **spec_clarification**, ausdrücklich manuell beauftragt.
Der Auftrag setzt kein Control-Restbudget, keinen Claim und keinen
`dev_blocked`-Zustand zurück und startet keine Automatik. Es gibt keinen
Alibi-Produktcommit, keine Runtime-Registrierung und keinen vorgezogenen Leser.
Geändert werden nur normative Dokument-/Schema-/Vektordaten, Plan und aktive
Spezifikationshashbindungen; Produktcode, vorhandene Tests/Fixtures/Oracles,
Testnummern, historische Nachweise und Messhistorie bleiben bytegleich.
Schema-Erzeugung dient der Erstellung normativer Dokumentartefakte; es ist
keine Ausführung von Validatoren, Testkörpern, Fixtures oder Migrationen.
Dev führt keine Verhaltenstests aus. Statische Schema-/Hashprüfung, reine
Collection und native ZIP-Prüfung sind keine Migrationsabnahme.

Apply prüft vor dem Dokumentcommit genau einmal die fällige gefilterte
N=3-Gruppe (erwartet 0) plus ungefilterte Katalog-, Graph- und Restore-
Schemagrenzregressionen. Hostworker, worksteal, Nice und dauerhafte Messung
bleiben unverändert. Die eine ZIP wird atomar auf Exchange übergeben.
Kein eigener Apply-, CI-, Watcher- oder Control-Start und kein Warten auf
ein Folge-Result. Die folgenden Produktarbeiten benötigen dessen neue Bindung.
