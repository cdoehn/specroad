# OFF-PLAN – Importstrategien und Revisionsgrenze (Bundle 407)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Importstrategien und Revisionsgrenze (Bundle 407)

Revision 9 dokumentiert **IMPORT-CONFLICT-POLICY**, **delegiert gemäß
SPECROAD-DECISION-1**. Spezifikation **0.2.14, Kapitel 10.12.2**, präzisiert
die vier bereits geplanten Importstrategien mit derselben nativen Identität,
der bestehenden Fünf-Fälle-Tabelle und regulären Revisionen nach K.2.
Entscheidungsbeleg, Alternativen und offene Verhaltensabnahmen stehen bei
14.c. Es wird keine persönliche Einzelzustimmung oder ein Review behauptet.

- [x] **IMPORT-CONFLICT-POLICY:** Importstrategien, Divergenz und Revisionsgrenze verbindlich klären. Commit: `docs(spec): Importstrategien und Revisionsgrenze präzisieren`.

**Übergabegrenze:** Ein OFF-PLAN-Dokumentcommit mit Spezifikation, Plan und
notwendigen aktiven Katalog-Hashbindungen. Produktcode, Verhaltenstests,
stabile Testnummern, Runner und historische Evidence bleiben unverändert.
Produktstand **576/900**, zuletzt **14.b.C**, nächstens **14.c.W**, bleibt
erhalten. Erst nach erfolgreichem parallelem Apply-Gate setzt der Entrypoint
den Offplan-Marker und die Bundlenummer auf 407. Das bestätigt ausschließlich
die Dokumentübergabe, keine Umsetzung oder Abnahme von 14.c.

**Prüfgrenze:** Kein verändertes Produktverhalten und keine erfundenen
Dokumentationstests. Vollständige Collection-/Katalogprüfung mit null
Testkörpern und native Paketprüfung bleiben erhalten. Apply prüft vor dem
Commit genau die fällige Gruppe 1/3, Commitfolge 115, parallel. Danach endet
diese Übergabe mit `spec_clarification`; der nächste gebundene Auftrag kann
14.c.W umsetzen. Kein Start oder Eingriff in Control, Watcher, CI oder Dienste.
