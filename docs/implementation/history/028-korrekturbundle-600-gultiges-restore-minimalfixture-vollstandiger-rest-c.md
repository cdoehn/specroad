# Korrekturbundle 600 — gültiges Restore-Minimalfixture, vollständiger Rest (C)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 600 — gültiges Restore-Minimalfixture, vollständiger Rest (C)

Maßgebliche Basis ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_061443_1105_a9ad3c.zip`, SHA-256
`759af684b6f0311af40de0b2c41aa8f747a6eb7c5ea94ca41e99404b7ee20d19`, unveränderter HEAD
`1702704eb385f9ad1af5f401c58b1adc2ff828d6`, dirty Fingerprint
`64aae7ee9c1e874d`. Das Result entspricht bytegenau dem
ausgebrachten W-Zustand von Bundle 599. Das Gate endete mit 6.848 bestandenen
Tests und einem Fehler, bevor irgendein Commit entstand. R/C wurden noch
nicht ausgebracht; es gibt keinen erfolgreichen Commit zu wiederholen.

Ursache: Dem neuen leeren Minimalfixture fehlte das nach 10.14 / SR-REQ-0467
verpflichtende Primärdokument. Die native Restore-Qualifikation lehnte es
korrekt mit document_primary_missing ab. Das korrigierte Fixture ergänzt
genau ein echtes document mit document_role=primary_specification und
behält Konfiguration, Profil, kleine Registry und jeden öffentlichen Resume.
Sämtliche unabhängigen Plan-/Dateibyte- und Replay-Oracles bleiben unverändert;
keine Änderung von Produktcode, Spezifikation, Sicherheitsprüfung oder Timeout.
Die übrigen Beschleunigungen und die Aufhebung der lokalen Kurzbefehle bleiben.

Alle offenen IDs und Rollen werden in derselben Reihenfolge fortgeführt:
TEST-SPEED-CONTROL-599.W, TEST-SPEED-CONTROL-599.R,
TEST-SPEED-CONTROL-599.C, jeweils implementation. Die erste Stage umfasst den
vollständigen erhaltenen uncommitted Scope samt korrigiertem Fixture. R/C
behalten die angekündigten eigenen Zwischenstände. Korrekturbindung und
Vorherbytes stammen ausschließlich aus diesem Fehler-Result; kein Reset.
Stage C ist ein Commitziel, kein vorweggenommener Apply-Erfolg.

Die Pflichtauswahl enthält weiter alle bisherigen 132 Regressionen sowie die
bestehenden Dokumentrollen-Regressionsprüfungen für vollständige Projekte.
Jede Stage erhält ihr eigenes gefiltertes N=3-plus-Pflichtauswahl-Gate vor
Commit; in Dev nur Syntax, Collection und native Paketvalidierung. Nummern,
Messhistorie, Produktstand 702/900 und Folgeposition 17.d.W bleiben erhalten.
Kein neuer Klärungscommit, kein CI-, Apply-, Watcher- oder Control-Start.
