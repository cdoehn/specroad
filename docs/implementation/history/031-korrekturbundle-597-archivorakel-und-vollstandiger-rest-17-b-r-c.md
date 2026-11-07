# Korrekturbundle 597 — Archivorakel und vollständiger Rest 17.b.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 597 — Archivorakel und vollständiger Rest 17.b.R/C

Maßgebliche Basis ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_041543_1105_b1b763.zip`, SHA-256
`26d928638b97ae0e80f53d1a301ac8af3f5df53d47eadb3512cb7be2561f21cf`.
Die Klärung MERGE-INVENTORY-596 ist nach eigenem Gate mit 6.920 Tests als
`a0b8e3fc3cb003a5908e9f5d30659aa5da91ad10` committed; 17.b.W ist nach
7.459 Tests als `672ee73d40c50de3190ef65141606111f24a5ef4` committed.
17.b.R scheiterte mit 7.529 bestandenen und einem fehlgeschlagenen Test.
Der tatsächliche abgeschlossene Produktstand ist 697/900; die erhaltenen
R-Checkboxen sind ausschließlich noch ungeprüfte Commitzielzustände.
Die erfolgreichen Commits werden weder wiederholt noch zurückgesetzt.

Ursache ist das neue Legacy-Inventurorakel: `role=artifact` im Legacy-Manifest
beschreibt den historischen Inhalt. Derselbe Originalinhalt kann sowohl
unter seinem qualifizierten `spec/...`-Pfad als auch als adressiertes
`archive/objects/...` vorkommen. Der Test behandelte beide physischen Arten
als aktuelle Legacy-Artefaktzeilen und erwartete überall `legacy_immutable`.
Nach dem bereits committeden Vertrag 10.15.1 und dem bestehenden nativen
`_original_archive` bleiben Archivdateien jedoch eigene Byteobjekte mit
`kind=archive`, `value_domain=bytes-v1` und Speicherklasse `current`; letzteres
ist ausdrücklich keine Änderungsfreigabe. Nur qualifizierte Artefakte unter
`spec/...` besitzen die Legacy-Artefaktklasse und separate Relationsnavigation.

Die Korrektur verändert keine Produktimplementierung und keine normative
Regel. Das Orakel prüft jetzt beide physischen Arten ausdrücklich, für alle
drei Quellen mit Originalgröße und Originalbytehash. Archivzeilen bleiben
an den vollständigen Pfad und Rohbytehash gebunden und erzeugen keine
scheinbaren aktuellen Relationen. Qualifizierte Artefakte und deren Relationen
behalten sämtliche bisherigen Legacy-/Wertprüfungen; positive Mengenprüfungen
verhindern ein unbemerktes Überspringen einer der beiden Fixturearten.
Die R/C-Testdateien bleiben untereinander bytegleich. Alle angekündigten
Testidentitäten, Pflichtdateien und vollständigen Stage-Umfänge bleiben erhalten.

Korrekturbindung: ursprünglicher öffentlicher Plan
`3663a1ba5f223c5005cd2a77751fd54a1bdb9228c7e4e2eb2adf4e16087d0e6d`,
offene IDs/Rollen unverändert `17.b.R` und `17.b.C` / `implementation`.
Der erste Zustand enthält auch alle erhaltenen Dirty-Pfade mit den exakten
Vorherbytes des neuen Results; kein C-Endstand vor dem R-Gate. Jede Stage
behält die fällige N=3-Gruppe plus ungefilterte Pflichtauswahl. Der Fehler
hat die Rotation nicht weitergeschaltet. Dev führt keine Verhaltenstests
aus, nur Syntax, Collection und native Paketvalidierung. Abschluss und
Budgeterneuerung bedürfen erst des vollständig erfolgreichen Folge-Results.
Keine erneute Klärung und kein neuer Produkt-/Alibicommit.
