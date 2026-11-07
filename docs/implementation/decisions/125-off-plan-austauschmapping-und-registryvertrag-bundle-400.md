# OFF-PLAN – Austauschmapping- und Registryvertrag (Bundle 400)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Austauschmapping- und Registryvertrag (Bundle 400)

Revision 8 dokumentiert **EXCHANGE-MAPPING-CONTRACT**, **delegiert gemäß
SPECROAD-DECISION-1**. Spezifikation **0.2.13, Kapitel 10.12.1**, ergänzt
die bisher nicht festgelegten Feldmengen und Auswertungsregeln der bereits
geplanten Mappingressourcen und externen Registries. Der Entscheidungsbeleg
mit Alternativen und verbindlichen Verhaltensabnahmen steht unmittelbar
bei 14.a. Eine persönliche Einzelzustimmung oder ein externer Review wird
nicht behauptet.

- [x] **EXCHANGE-MAPPING-CONTRACT:** Passive Mappingtabellen, Ressourcenbindung und Registry-Namensräume verbindlich klären. Commit: `docs(spec): Austauschmappings und externe Registries präzisieren`.

**Übergabegrenze:** Genau ein OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und den notwendigen aktiven Katalog-Hashbindungen. Produktcode,
Verhaltenstests, stabile Testnummern, Runner und historische Evidence bleiben
unverändert. Der bestätigte Produktstand bleibt **570/900**, zuletzt
**13.h.C**, nächstens **14.a.W**. Erst nach erfolgreichem parallelem Apply-Gate
setzt der Entrypoint den obigen Offplan-Marker und die Bundlenummer auf 400.
Das bestätigt ausschließlich die Dokumentübergabe, keine Umsetzung von 14.a
und keine vollständige Meilenstein-/Release- oder Plattformabnahme.

**Prüfgrenze:** Keine Dokumentationstests oder fingierten Verhaltenstests.
Die vollständige Collection-/Katalogprüfung mit null Testkörpern und die
native Paketprüfung bleiben erhalten. Apply führt vor seinem Commit genau
die nächste feste Testgruppe parallel nach N=3 aus. Diese Übergabe endet
mit `spec_clarification`; 14.a.W bleibt offen für den nächsten gebundenen
Auftrag nach erfolgreichem Apply. Keine Änderung an Control, Watcher, CI,
Diensten oder deren Zustand; keine automatische Folgearbeit.
