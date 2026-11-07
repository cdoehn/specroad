# OFF-PLAN MIGRATION-GRAPH-549 — Versionsgraph und Rückwege präzisieren

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN MIGRATION-GRAPH-549 — Versionsgraph und Rückwege präzisieren

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_180648_1102_32a595.zip`, SHA-256
`941d6cac954cb0efb1b2c74fefba98b84e36f2e9e1058105289e73f1587623fa`,
sauberer HEAD `ed49dcb6c2c5530b39ca05b05a83d19e88800b4f`.
Der echte Restlauf in Bundle 548 hat 15.o.R als
`a13846faa96ff0f4ea735c3039d57ad95b154f70` nach 7.508 bestandenen Tests
und 15.o.C als `ed49dcb6c2c5530b39ca05b05a83d19e88800b4f` nach 7.621
bestandenen Tests committed. SPECROAD_APPLY_PROGRESS meldet completed ohne
offene Commit-IDs. Es waren Gruppen 0/1 plus jeweils 1.713 Pflichttests,
keine Vollsuite- oder Meilensteinfreigabe. Die alten Fehler-Results und die
erhaltene Commitkette bleiben unverändert; die historische Markierung 547
in den identischen Produktbytes ersetzt nicht den tatsächlichen Restlauf 548.

Diese Übergabe enthält genau einen Dokumentcommit `MIGRATION-GRAPH-549` mit
Nachricht `OFF-PLAN MIGRATION-GRAPH-549 docs(spec): Versionsgraph und Rückwege präzisieren`.
Entscheidung, Alternativen und vollständige offene W/R/C-Abnahmen stehen
bei 16.a; normative Grundlage ist Spec 0.2.48/12.20.1. Der Produktstand bleibt
**660/900**, nächster Produktcommit **16.a.W**. Alle Produktcheckboxen bleiben
unverändert. Die vorbereitete Bundlenummer 549 gilt erst nach dem erfolgreichen
Apply-Gate und tatsächlichen Dokumentcommit. Bis dahin ist 548 der letzte
vollständig belegte Bundleabschluss.

Geändert sind ausschließlich Spezifikation, Plan und 743 aktive
Spezifikationshashbindungen im Katalog. Code, Tests, Fixtures, Oracles,
Testnummern, Runner, Messhistorie und historische Evidence bleiben erhalten.
Dev führt keine Tests aus. Reine Collection, statische Katalogprüfung und
native Paketvalidierung sind keine Verhaltensabnahme. Apply prüft vor dem
einen Commit genau einmal die fällige gefilterte Gruppe **2 von 3** plus
die begründete ungefilterte Pflichtauswahl. Hostworker und Nice-Regeln bleiben.
Keine CI, kein eigener Apply-, Watcher- oder Control-Start.

Klassifikation: `spec_clarification` unter SPECROAD-DECISION-1-V3 und gültigem
Control-Vertrag 3 mit Restbudget 3/3. Die Klärung verbraucht einen Platz;
sie ist kein normaler Produktpatch und erneuert kein Budget. Der Auftrag
endet nach genau einer atomaren Exchange-Übergabe. Nur ein neuer gebundener
Control-Auftrag auf dem zugehörigen Result setzt die Umsetzung fort.
