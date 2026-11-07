# Korrekturbundle 610 — gültige Konfigurationsquelle, vollständiger Rest 17.g.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 610 — gültige Konfigurationsquelle, vollständiger Rest 17.g.R/C

Maßgeblich ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_201242_1105_4dacd0.zip`, SHA-256
`bf0be7d5f296df86be0872293bc747003b65f896f6adeb65873c4d870845149b`,
HEAD `100680afb336412f94cb15068196ba4ec31fa1c1` und Dirty-Fingerprint
`2d6b16c8e4bdcaaa`. 17.g.W wurde nach 7610 bestandenen
Tests erfolgreich committed. Der Klärungscommit MERGE-CONFLICTS-608 und
dieser W-Commit bleiben erhalten; bestätigt sind 712/900 und 17.g.W.
Die folgenden Abschnitte zu 608/609 dokumentieren die historische Grundlage.
Es gibt weder eine neue Klärung noch eine Budget- oder Specänderung.

17.g.R scheiterte mit einem Fehler und 7667 bestandenen Tests. Die Fixture
von `test_collection_conflict_keeps_whole_values_and_stable_keys` entfernte
in ours die Dimension platform, ließ aber selection.platform=linux stehen.
Die native Quellqualifizierung wies diesen widersprüchlichen Datensatz mit
unknown_dimension ab, bevor der eigentliche Collection-Merge geprüft wurde.
Anhang I verlangt bereits ausschließlich deklarierte Auswahlwerte;
der bestehende Konfigurationsvalidator bleibt vollständig erhalten.

Die Korrektur entfernt in derselben synthetischen Variante auch die Auswahl.
Base und theirs sowie alle bisherigen fachlichen Oracles bleiben erhalten:
genau ein Konflikt an /dimensions, stabiler Schlüssel platform, Klasse
set_element_conflict und die vollständigen drei originalen Dimensionslisten.
Weder native Quellqualifizierung noch Parser, Hashes, Konfliktumfang oder
Erwartungswerte werden durch Mocks, Sonderfreigaben oder Filter abgeschwächt.
Die zusätzlichen Konfigurationswert-Regressionsdateien sichern gültige leere
Konfiguration und die unveränderte Ablehnung unbekannter Dimensionen.

Der erhaltene R-Arbeitsstand ist die vollständige Vorherbasis. Genau die
noch offenen IDs 17.g.R und 17.g.C mit Rolle implementation folgen in
derselben Reihenfolge. R behält die vollständige angekündigte Härtung;
C extrahiert weiterhin nur den passiven Datenvertrag mit unveränderten
Funktions-/Klassen-ASTs und identischen R-Testbytes. Keine Wiederholung
erfolgreicher Commits und kein vorab installierter C-Endstand.

Vorbereiteter Commitzielstand dieser Stage: 17.g.C, 714/900, danach
`17.h.W`. Zähler und Checkboxen werden erst nach dem eigenen
erfolgreichen Apply-Gate mit echtem Commit wirksam. Jede Stage erhält
die gefilterte fällige N=3-Gruppe plus alle bisherigen Pflichtdateien,
die gesamte korrigierte Testdatei und die genannten Konfigurationsregressionen.
Dev führt keine Verhaltenstests aus; Syntax, Collection und native
Paketprüfung sind keine Verhaltensabnahme. 17.h–17.l und die endgültige
M17-Abnahme bleiben offen. Kein CI-, Apply-, Watcher- oder Control-Start;
keine lokale Konfiguration, Zugangsdaten oder Session-IDs in der Payload.
