# MIGRATION-LOSS-574 — optionale Detailklärung und vollständiges 16.h

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## MIGRATION-LOSS-574 — optionale Detailklärung und vollständiges 16.h

Autorität: delegiert gemäß SPECROAD-DECISION-1/2.4.3.1, erteilter Vertrag 4
mit clarification_allowed=true und drei verfügbaren Plätzen. Genau ein
OFF-PLAN-Klärungspräfix, danach echte 16.h.W/R/C-Implementierung. Kein
Control-Zustand, Budget oder Review wird verändert. Technische Basis:
Result-SHA 58326e08934ce8fd5a857dcec62e2b8abcffdb1eb13d4bb60820731faaea337f,
sauberer Abschlusscommit 4a96a3f5241f8e9d1a96122842b197bb5ec1accb.
16.g.W/R/C ist durch echte Gates mit 7195/7241/7205 erfolgreichen Tests
und drei Commits belegt. Produktstand vor diesem Bundle: 681/900.

Lücke: SR-REQ-0268/0269/0512 verlangen Erhalt und Einzelzustimmung, definieren
aber keine stabilen gebundenen LOSS-IDs, maschinenlesbare Inventur oder
Grenze der Zustimmung gegenüber SR-REQ-0272/Q. Geprüft wurden der gebundene
Quellvertrag 1.0.1, 12.20.1/2, Q, Source-/Plan-/Manifestcode und bestehende
Importverluste. Deren Zustimmung bleibt gesondert und wird nicht erweitert.

Alternativen: Laufende Nummern wären von Sortierung/anderen Verlusten abhängig;
pauschale Zustimmung oder freie verlustbehaftete Referenztransformation würde
den Originalschutz abschwächen; ein neues allgemeines Migrationsformat wäre
unnötig. Gewählt ist die vollständige native source-/target-/input-gebundene
Inventur aus 12.20.3 mit SHA-256-IDs und passivem Einzelzustimmungsgate.
Der vorhandene Change Plan bleibt unverändert. Der Referenzpfad bleibt
verlustfrei; fehlerhafte Kandidaten erhalten keinen ausführbaren Plan.

Grenzprüfung 2.4.1: Die Entscheidung liegt vollständig in 16.h, ändert
keine Nutzerentscheidung, reale Daten oder öffentliche Pfadunterstützung.
IDs, Anhänge, Originale, Audit, Kompatibilität, Sicherheit und menschliche
Reviews bleiben erhalten. Neue Diagnose-/Beobachtungswerte sind versioniert;
eine spätere Rücknahme betrifft nur diesen Vertrag und Code, niemals alte
Originale, Nachweise oder Results. Es fehlen keine externen Pflichtfakten.
Einzelfreigabe oder reale Risikoakzeptanz wird nicht erfunden.

W liefert den vollständigen schreibfreien Erhaltungsvergleich samt gebundener
Verlustinventur und verhindert stille Konfigurations-Extensionverluste im
nativen Planer. R vervollständigt das explizite Einzelzustimmungsgate,
Bindungs-/Alias-/Typ-/Manipulationsgrenzen und negative Abnahmen. C teilt
die strukturelle JSON-Verlustinventur mit Import, erhält aber dessen
bestehenden Bericht und unveränderte Verweigerung nicht akzeptierter Verluste.
Unabhängige Sollwerte, mehrere Verluste, Quellen-/Zielwechsel, fehlende
Zustimmungen, leere Inventur und vollständig passive Zustimmung werden
abgenommen. Öffentliche CLI, Writer/Recovery, Abschlussbericht und globale
Zielverification bleiben in ihren bestätigten späteren M16-Schritten.

Vorbereiteter Stand: 16.h.C; die nachfolgenden Planphasen bleiben offen. Keine Testkörper oder Fixtures
in Dev. Jede Stage erhält ein eigenes Apply-Gate (Rotation 1/2/0/1) plus
ungefilterte vollständige Pflichtauswahl. Häkchen und Produktzähler gelten
erst nach ihrem Gate; Dokumentänderung ist kein Produktabschluss.
