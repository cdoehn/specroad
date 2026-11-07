# Korrekturbundle 609 — Bootstrap und native CLI-Beispiele, Rest 17.g.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 609 — Bootstrap und native CLI-Beispiele, Rest 17.g.W/R/C

Maßgeblich ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_194409_1105_6d1651.zip`, SHA-256
`2fe99cf4d522bab64dd3963db00be4974389b77ccdbf96f5f5cef991240a1a3d`,
HEAD `2317b0421e85e706636350bf1dbd1415b8b62411` und Dirty-Fingerprint
`f3eaaded55a94a4d`. Der Klärungscommit MERGE-CONFLICTS-608 ist
nach 6955 bestandenen Tests bereits committed. Seine normative Spezifikation
0.2.68 und aktiven Bindungen bleiben unverändert; keine neue Klärung oder
Budgetänderung. Die folgenden Abschnitte zu Bundle 608 bleiben historische
Entscheidungs- und Umfangsbelege, nicht die neue technische Patchbasis.

17.g.W ist mit sechs Fehlern und 7583 bestandenen Tests gescheitert, ohne
Produktcommit. Bestätigt bleiben 711/900 und 17.f.C; der erhaltene W-Stand
ist die vollständige Vorherbasis. Die drei Ursachen sind vorzeitige Fach-
und Sicherheitsimporte bei der CLI-Registrierung (drei Bootstrap-/Identity-
Regressionen), die unvollständige strikte Befehlsliste (eine Regression)
und fehlende reale Eingaben für den neuen Befehl in den Schema-Beispielen
(zwei Regressionen). Es handelt sich um Integrationsfehler, nicht um eine
offene normative Entscheidung.

609 verschiebt die Fachimporte in den tatsächlichen Handler, ergänzt
`merge.conflicts` in der weiterhin exakten Befehlsliste und bindet die
veröffentlichten Beispielpfade an einen realen gespeicherten Konfliktplan.
Die Fixture verwendet vollständig qualifizierte synthetische Projekte,
bekannte ausdrücklich synthetische Herkunft und die nativen Erzeuger.
Sie ersetzt weder Parser noch Quellprüfung, Hashes, Handler oder Ergebnisse.
Die vorhandenen Bootstrap-, Identity-, Request-, Schema- und Description-
Verhaltenstests behalten ihre strikten Oracles und werden Pflichtauswahl.

Alle offenen IDs und Rollen bleiben in Reihenfolge erhalten: 17.g.W,
17.g.R, 17.g.C, jeweils implementation. W korrigiert die vollständige
CLI-Integration, R behält die angekündigte Daten-/Quell-/Sicherheitshärtung,
C die reine Extraktion des passiven Datenvertrags. Alle ursprünglichen
Pflichttests bleiben enthalten; die vollständigen betroffenen Testdateien
kommen hinzu. Jede Stage hat ihr eigenes gefiltertes N=3-plus-Pflichtgate
vor dem Commit. Der W/R/C-Endstand wird nicht vorab installiert.

Vorbereiteter Zielstand dieser Stage: 17.g.C, 714/900, danach
`17.h.W`. Zähler und Checkboxen werden nur durch ihr eigenes
erfolgreiches Apply-Gate mit Commit wirksam. Dev führt keine Verhaltenstests
aus; Syntax, reine Collection und native Paketprüfung sind keine Abnahme.
17.h–17.l, endgültige M17-Abnahme und Produktfreigabe bleiben offen.
Kein CI-, Watcher- oder Control-Start und keine lokale Betriebsdaten-Payload.
