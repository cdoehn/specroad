# MERGE-INVENTORY-596 — Klärungspräfix und vollständiger Schritt 17.b

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MERGE-INVENTORY-596 — Klärungspräfix und vollständiger Schritt 17.b

Autorität: **delegiert gemäß SPECROAD-DECISION-1**, Vertrag 4 mit erlaubter
optionaler Klärung. Maßgebliches natives Result
`specroad-apply_Result_030929_1105_0a58cb.zip`, SHA-256
`7a2b1fb27ccd29edc6793f8a51e1fbb756af0214209a643c9b197958ff871801`,
sauberer Abschlusscommit `9a27a1e23e55bca4cdd22b9457285e06dd20bcbd`.
17.a.W/R/C sind durch drei echte Commits nach 7.263, 7.821 und 7.834
bestandenen Tests belegt. Produktstand: 696/900, nächste Position 17.b.W.
Diese gefilterten Gruppen mit Pflichtauswahl sind keine Vollsuite.

Geprüfte Grundlage: aktive Spezifikation 0.2.62, insbesondere 2.4.1–2.4.4,
10.15, 12.27, Anhang K; vollständige Abfolge 17.b–17.o; native Quellregistry,
Modell-/Ressourcen-/Relationsmodelle und deren Apply-Nachweise. Es fehlt
die geschlossene serialisierte Inventurhülle einschließlich Relationen,
Anwesenheits-/Hashdomänen und überprüfbarer gespeicherter Vollständigkeit.
Die vier endgültigen Zielklassifikationen sind dagegen bereits verbindlich.

Alternativen: (1) bloße Pfad-/Artefaktliste ohne native Identitäten verliert
Nebenbereiche und Relationsbindung; (2) fehlende Seiten direkt als Löschung
oder vollständige Change Plans auslegen überspringt Fach- und Writergates;
(3) vollständiger separater versionierter Inventurzwischenstand mit explizit
ausstehender semantischer Planung. Gewählt wird (3): vorhandene native
ResourceEntry-, Konfigurations-, Profil-/Mapping-, Relations- und Snapshot-
Verträge werden wiederverwendet, keine Ersatz-Modellwurzel erfunden.

Normative Festlegung zuerst in 10.15.1: `merge-inventory-v1`, explizite
MP-ID, unveränderte `merge-metadata-v1`, vollständige drei Quellbindungen,
eindeutige native Identitäten und Originalbyte-/Wertbindungen; jede Datei
genau einmal plus jede Relation. Abwesenheit beweist keine Löschabsicht.
Bytegleiche Ressourcen sind `unchanged_ours`, andere vorläufig `conflict`
mit ausdrücklichem `semantic_planning_required`, nicht endgültig unlösbar.
Adoption, Kombination und fachliche Konfliktauflösung folgen unverändert
17.c–17.h. Zielwurzel nur im nachgewiesenen vollständigen Gleichfall,
sonst null; keine ausführbare Freigabe. Gespeicherte Inventuren werden aus
allen gebundenen Quellen rekonstruiert, nicht anhand selbst behaupteter
Hashlisten akzeptiert. Artefakt-/Relationshistorie und Legacybytes bleiben.

Abgleich mit 2.4.1: ausschließlich fehlende Felder und Bindungen des offenen
17.b, keine neue CLI oder Änderung realer Projekte; keine abgeschwächten
Requirements oder menschlichen Reviews; keine neuen externen Fakten nötig.
Additives eigenes Format statt Änderung vorhandener Change Plans, kein
impliziter Fallback und keine neue Produktposition. Rücknahme über spätere
versionierte Vertragsänderung unter Erhalt gespeicherter Originale möglich.
W/R/C, Sicherheit, Scope und Folgeabnahmen bleiben vollständig erhalten.

Positive Abnahme: alle nativen Quellarten, Artefakte/Relationen und normativen
Ressourcen einschließlich Registry, Sprachpakete, Archiv/Legacy und Anhänge;
identische Bindungen und ID liefern identische Planbytes. Negative/Grenz-
abnahme: fehlende Pflicht-/referenzierte Quelle, fremde/partielle Eingabe,
duplizierte Identität, manipulierte/verkürzte Inventur oder Hashbehauptung,
geänderte Quelle, falsche Version/Feldmenge, Abwesenheit statt Löschauftrag,
null gegenüber fehlendem Wert, leere Binärbytes und Relationsumordnung.

Dieser Klärungszustand lässt 17.b.W/R/C offen. Anschließend enthält dieselbe
ZIP die drei vollständigen Implementierungszustände: W vollständige lesende
Inventur; R Quell-/Vollständigkeitsprüfung und gespeicherte Inventurprüfung;
C gemeinsame Snapshotinventur statt Merge-Parallelmodell. Jede Stage wird
erst nach eigenem N=3-plus-Pflichtgate committed. Kein vorgezogener Endstand.
Dev führt keine Verhaltenstests aus; Collection, Syntax und Paketvalidierung
sind keine Produktabnahme. SR-TC-0361/0364/0375 bleiben bis zu ihren gesamten
Fach-/CLI-/Abschlussnachweisen teilweise umgesetzt beziehungsweise offen.
Es gibt keinen neuen Budget-, Betriebs-, Freigabe- oder Automatikzustand.
