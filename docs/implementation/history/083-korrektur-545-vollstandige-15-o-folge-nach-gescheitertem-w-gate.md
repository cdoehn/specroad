# KORREKTUR 545 — vollständige 15.o-Folge nach gescheitertem W-Gate

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## KORREKTUR 545 — vollständige 15.o-Folge nach gescheitertem W-Gate

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_095606_1102_b7d3c4.zip`, SHA-256
`c6926c562a62e5688346915a7da5d182ab99d026b011c0c142814581508c3249`,
HEAD `28470da477edb6c8f8d80807d0b2731f670e1741`, erhaltener Dirty-Fingerprint
`3b3f8712a244d0e2`. Das native Effective-Inventar entspricht vollständig dem
ausgelieferten W-Zustand von Bundle 544; der Base-Snapshot bleibt unverändert.

**Tatsächlicher Befund:** 15.o.W scheiterte am 2. November 2026 in der fälligen
Gruppe 2 plus Pflichtauswahl mit **6 fehlgeschlagenen und 7.306 bestandenen**
Tests. Kein Commit entstand; die Rotation blieb bei Gruppe 2. Der belegte
Commitpräfix ist leer, Produktfortschritt tatsächlich weiterhin **657/900**.
Die im erhaltenen Working Tree stehende W-Checkbox war eine vorbereitete
Fortschrittsmarkierung und wurde durch diesen fehlgeschlagenen Lauf nicht gültig.
SPECROAD_APPLY_PLAN/PROGRESS bindet den vollständigen offenen Rest
`15.o.W`, `15.o.R`, `15.o.C` an Plan-SHA-256
`6b75b3033f707da8144f45d977fc2a3e991ecc89b084b08971badf916857f079`.

**Diagnose und gezielte Korrektur:** Alle sechs Fehler betreffen die öffentliche
maschinelle `command.describe`-Ausgabe. Der Producer liefert in den Varianten
`result_schema` und `required_write_paths`; das geschlossene Beschreibungsschema
hatte diese Felder nicht aufgenommen. Zusätzlich besitzen die nicht budgetierten
Öffnungsvarianten rechtmäßig `budget_policy_version=null`, während der
Variantenteil ausschließlich Strings zuließ. Der normale Beschreibungsteil
erlaubte diesen Nullwert bereits. Die Folge war CORE_INTERNAL/Exit 4 bei
`bundle.create`, `bundle.verify` und `bundle.extract` samt abhängigen Katalog-
und Capability-Abfragen. Es handelt sich um einen technischen Vertragsfehler,
keine offene Spezifikationsentscheidung.

Die Korrektur ergänzt exakt die beiden bereits ausgegebenen typisierten
Pflichtfelder und übernimmt den vorhandenen nullable Budgetvertrag. Fremde
Felder, fehlende Pflichtfelder und falsche Typen bleiben unzulässig. Vorhandene
Verhaltenstests prüfen positive Metadaten und zusätzliche negative Maschinen-
verträge; Testidentitäten und ihre Nummern bleiben unverändert. Alle sechs
Fehlerfälle sind in jeder Phase verpflichtend, einschließlich der zuvor nur
über die Rotation ausgewählten Capability-Regression. Keine Darstellungstests.

Bundle 545 erhält den tatsächlichen W-Arbeitsstand und den gesamten noch nicht
ausgebrachten R-/C-Umfang. Es setzt dieselben drei Commit-IDs und Nachrichten
in echten aufeinanderfolgenden Zuständen fort. Erst nach Gate und Commit von W
folgt R, danach C. Keine Teilung, kein Reset, keine Wiederholung erfolgreicher
Commits und keine Vermischung von W mit dem R-/C-Endzustand. Die unten stehenden
Fortschrittsmarker gelten erst nach ihrem jeweiligen erfolgreichen Apply-Gate
UND tatsächlichen Commit. Das letzte vollständig abgeschlossene Bundle ist 543;
545 gilt erst nach vollständiger erfolgreicher Folge als abgeschlossen.

Spec 0.2.47/W.4.1 bleibt bytegleich. Diese Übergabe ist eine technische Korrektur,
keine `spec_clarification`; das gesperrte Klärungsbudget wird nicht benutzt oder
erneuert. Dev führt keine Verhaltenstests aus. Syntax, Collection und native
Paketprüfung sind keine Verhaltensabnahme. Apply prüft je Commit genau einmal
die aktuelle gefilterte N=3-Gruppe plus ungefilterte Pflichtauswahl. Messhistorie,
Hostworker und Nice-Regeln bleiben erhalten. M15-Vollsuite, Integrations- und
Plattformfreigaben sowie 18.q/18.r und der spätere Rundweg bleiben offen.
