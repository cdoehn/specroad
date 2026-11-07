# KORREKTUR 546 — Budget-Testoracle und vollständiger offener 15.o-Rest

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## KORREKTUR 546 — Budget-Testoracle und vollständiger offener 15.o-Rest

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_103419_1102_69b82a.zip`, SHA-256
`2ea77b1d8d2ee127d25310f3b6028fedeb8e34027f652dbca45db10327d228ef`,
HEAD `28470da477edb6c8f8d80807d0b2731f670e1741`, Dirty-Fingerprint
`23f1a18fe04f4d3b`. Das native Effective-Inventar entspricht exakt dem
ausgelieferten W-Zustand von Bundle 545; der Base-Snapshot blieb unverändert.

**Tatsächlicher Befund:** Bundle 545 scheiterte am 2. November 2026 vor dem
ersten Commit mit **1 fehlgeschlagenen und 7.341 bestandenen** Tests in
1.207,12 Sekunden. Die fällige Gruppe 2 plus Pflichtauswahl umfasste 7.342 Tests.
Die sechs ursprünglichen Fehler aus Bundle 544 sind in dieser Auswahl enthalten;
übrig blieb die neue falsche Null-Erwartung für die Budgetkennung von Verify.
Kein Commit entstand, die Rotation bleibt bei Gruppe 2. Der tatsächliche
Produktfortschritt beträgt weiterhin **657/900**, nicht den vorbereiteten
W-Marker im uncommitteten Working Tree. SPECROAD_APPLY_PLAN/PROGRESS bindet
den vollständigen offenen Rest `15.o.W`, `15.o.R`, `15.o.C` an Plan-SHA-256
`ab8e0962837759c34f911b047aee94fa3b5262482ef488d07a9a12905714ec81`.

**Diagnose und gezielte Korrektur:** Der in Bundle 545 ergänzte Metadatentest
erwartete für beide Öffnungsvarianten `budget_policy_version=null`. Das war
für `bundle.verify` falsch: Der bestehende lesende Command Contract trägt
`runtime-budget-v2`; die Transportvariante erhält diesen Vertrag. Nur
`bundle.extract` hat hier die Kennung `null`. W.4.1 erhält ausdrücklich die
allgemeinen Budgetregeln aus Anhang O und den bestehenden Anhang-E-Vertrag.
Auch die pauschale Nichtbudgetierungsannahme im historischen Abschnitt 545
ist damit berichtigt. Es besteht keine offene Spezifikationsentscheidung.

Der Test verwendet nun getrennte konkrete Erwartungswerte für Verify und
Extract und prüft sie sowohl an der öffentlichen Variantenbeschreibung als
auch am gebundenen Command und der normalen Beschreibung. Sämtliche
Negativprüfungen für zusätzliche/falsch typisierte oder fehlende Schemafelder
bleiben bestehen. Produktcode und normative Spezifikation werden gegenüber
den entsprechenden bereits gelieferten W-/R-/C-Zuständen nicht geändert.
Kein Produktverhalten wird zum Erfüllen eines falschen Tests abgeschwächt.

Bundle 546 ist eine echte technische Korrektur des durch Apply belegten
Testfehlers und erhält den gesamten bisher offenen Implementierungsumfang.
Alle drei Commit-IDs, Nachrichten und echten Zustände bleiben erhalten;
R folgt erst nach dem erfolgreichen W-Gate und Commit, C erst nach R.
Die geänderte Testdatei, alle bisherigen Pflichtregressionen und zusätzliche
Budgetpolicy-Regressionen sind in jedem Zustand ungefiltert verpflichtend.
Testidentitäten, Nummern, Fixtures, Katalog-Oracles und Messhistorie bleiben
erhalten. Keine Teilung, kein Reset und kein vorgezogener R-/C-Endzustand.

Die vorbereiteten Fortschrittsmarker gelten ausschließlich nach dem jeweiligen
erfolgreichen Apply-Gate UND tatsächlichen Commit. Das letzte vollständig
abgeschlossene Bundle bleibt 543; 546 ist erst nach der gesamten Folge
abgeschlossen. Dev führt keine Verhaltenstests aus. Syntax, reine Collection
und native Paketprüfung ersetzen keine Verhaltensabnahme. Spec 0.2.47 und ihr
Hash bleiben unverändert; dies ist keine `spec_clarification` und erneuert kein
Klärungsbudget. M15-Vollsuite, Integration, Plattformfreigaben, 18.q/18.r und
die spätere vollständige Rundwegabnahme bleiben offen.
