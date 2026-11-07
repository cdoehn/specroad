# OFF-PLAN TRANSPORT-OPEN-543 — Öffnungsvertrag präzisieren

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN TRANSPORT-OPEN-543 — Öffnungsvertrag präzisieren

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_071220_1102_9a204a.zip`, SHA-256
`95b7fada43879e3eba6bec68d034f83c4f74a0c02aee4c42ccd42a047c9cb522`,
sauberer HEAD `e5dd00bab638b002a2c6dba58413451dfda0c480`.
Bundle 542 schloss die echten Commits 15.n.R und 15.n.C mit 7.123 und 7.133
bestandenen Apply-Tests ab. Das sind gefilterte Gruppen plus Pflichtauswahl,
kein Vollsuite-, Offline-Rundweg- oder Plattformfreigabenachweis.

Der folgende Dokumentzustand enthält genau einen OFF-PLAN-Commit:
`TRANSPORT-OPEN-543` mit Nachricht
`OFF-PLAN TRANSPORT-OPEN-543 docs(spec): Sandbox-Öffnungsvertrag präzisieren`.
Entscheidungsbeleg, Alternativen und sämtliche offenen W/R/C-Abnahmen stehen
bei 15.o. Die normative Regel ist Spec 0.2.47/W.4.1. Produktfortschritt bleibt
**657/900**, nächster Produktcommit **15.o.W**. Keine Checkbox von 15.o wird
geschlossen. Die neue Bundlenummer gilt erst nach erfolgreichem Apply-Gate
und tatsächlichem Dokumentcommit; Log und Commitpräfix bleiben maßgeblich.

Geändert sind nur Spezifikation, Plan und die 743 aktiven Spezifikationshash-
Bindungen im Katalog. Produktcode, Tests, Fixtures, Oracles, Testnummern,
Runner, Messhistorie und alte Evidence bleiben bytegleich. Dev führt keine
Tests aus. Reine Collection/Katalogprüfung und native Paketvalidierung sind
keine Verhaltensabnahme. Apply prüft einmal seine fällige gefilterte Gruppe
**1 von 3** plus die ungefilterte, begründete maschinenlesbare Katalog-Pflicht-
auswahl; erst danach erfolgt der Commit. Hostabhängige Worker/Nice-Regeln
bleiben erhalten. Keine automatische CI und kein Dienststart.

Diese Übergabe ist `spec_clarification` nach SPECROAD-DECISION-1-V3 und dem
aktuellen Control-Vertrag 3 mit Restbudget 3/3. Sie erneuert das Budget nicht,
startet kein Apply und erlaubt keine eigene Folgeschleife. Nach der einen
atomaren Exchange-Übergabe endet der Auftrag; erst Control beauftragt auf dem
zugehörigen geprüften Result die vollständige 15.o-Umsetzung.
