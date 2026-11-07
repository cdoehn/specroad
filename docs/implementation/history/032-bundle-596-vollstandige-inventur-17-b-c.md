# Bundle 596 — vollständige Inventur 17.b.C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Bundle 596 — vollständige Inventur 17.b.C

Technische Basis bleibt ausschließlich das nativ geprüfte erfolgreiche,
saubere Result `specroad-apply_Result_030929_1105_0a58cb.zip`, SHA-256
`7a2b1fb27ccd29edc6793f8a51e1fbb756af0214209a643c9b197958ff871801`, Abschlusscommit
`9a27a1e23e55bca4cdd22b9457285e06dd20bcbd`. Die eigene Klärungsstage
MERGE-INVENTORY-596 steht in derselben ZIP vor diesen Implementierungsstufen.
Sie lässt den Produktzähler unverändert und definiert ausschließlich die
fehlenden Formatdetails aus 10.15.1; alle späteren M17-Gates bleiben erhalten.

W erfasst sämtliche tatsächlichen normativen Dateien und jede Relation mit
nativer Identität, drei ursprünglichen Byte-/Wertbindungen, expliziter
Abwesenheit und vorläufiger Zielklasse. Dazu gehören auch inaktive Ressourcen,
Registry, Sprachpakete, Archive, Kontrollartefakte und qualifizierte Originale.
Die vollständigen nativen Quellen werden vor und nach der Erhebung geprüft.
Es werden keine impliziten Dateien, Löschungen oder Zielwurzeln erfunden.

R bindet die gemeinsame Quellinventur zusätzlich an deren Originalbyte- und
native Modellwurzelbelege. Der gespeicherte Plan wird aus den Originalquellen
vollständig rekonstruiert; selbst neu gehashte Kürzungen oder Manipulationen
bleiben ungültig. Fehlende Abhängigkeiten, geänderte Quellen, falsche Versionen,
Schlüssel oder Typen sind Fehler. Null, fehlend und leere Bytes bleiben getrennt;
Relationsumordnung ändert nicht die native Relationsidentität. Legacy-Originale
und ihre gesonderte qualifizierte Navigation behalten ihre bestehenden Grenzen.

C verschiebt ausschließlich die gemeinsame native Ressourcenbeobachtung nach
`snapshots/inventory.py` und verwendet bestehende ResourceEntry-/ResourceInventory-
Werte. Klassifikation und gespeicherter Mergeplan bleiben hinter der bestehenden
Merge-Fassade. Die vollständigen W/R-Testdateien und Fachverträge bleiben bytegleich.

Stand dieser Stage: 17.b.C, Folgeposition `17.c.W`. Checkboxen und Zähler
sind ausschließlich Commitzielzustände: Sie gelten erst nach bestandenem eigenem
Apply-Gate und echtem Commit. Jede Stage erhält gefilterte N=3-Auswahl plus
ungefilterte Pflichtauswahl; neue Testdateien vollständig und relevante native
Regressionsdateien zusätzlich. Die bisherige Nummerierung bleibt append-only.
Dev führt **keine Verhaltenstests** aus; Syntax, Collection und native Paketprüfung
sind keine Abnahme. SR-TC-0361/0364/0375 bleiben teilweise umgesetzt; spätere
Mergealgorithmen, Auflösungen, Zielvalidierung und CLI/Veröffentlichung bleiben offen.
