# Korrekturbundle 587 — vollständiger offener Rest 16.k.R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 587 — vollständiger offener Rest 16.k.R/C

Maßgeblich ist das nativ geprüfte Fehler-Result mit SHA-256
`8f4baf39ea1f80fe68e1c6822668506b489dca2ce55a6478eb6673e2936d420a`,
HEAD `5defc333804018dd62f6fc04a155d1ceeb9f72a6` und Dirty-Fingerprint
`390a7d858e50ff96`. 16.k.W wurde nach 7251 bestandenen Tests committed.
Der erfolgreiche W-Stand einschließlich Receipt-Korrektur bleibt erhalten;
auch der zuvor abgeschlossene Klärungscommit wird nicht wiederholt.
16.k.R scheiterte an einem Test, 8063 weitere Tests bestanden. Das erhaltene
Arbeitsinventar entspricht exakt der angekündigten R-Stage von Bundle 586.
Der tatsächliche Produktfortschritt ist 691/900; R/C sind noch offen.

Der Unterbrechungstest für den committed-Zustand verglich den nativen
Checkpointnamen mit dem bloßen Fallnamen committed. Der gemeinsame Writer
meldet nach dauerhafter Journalpublikation jedoch journal:committed:<Anzahl>,
wobei die Anzahl sämtliche tatsächlichen Planänderungen umfasst. Die
gewünschte Ausnahme wurde deshalb nicht ausgelöst; der Writer beendete die
Transaktion regulär. Der vorhandene direkte Writer-Regressionsfall verwendet
diese vollständige Checkpointbindung bereits.

Die Work-Abnahme bindet den committed-Fall jetzt an genau diesen nativen
Checkpoint mit der aus dem tatsächlichen Plan ermittelten Änderungsanzahl.
Sie weist für jeden der vier Fälle die wirklich ausgelöste Unterbrechung
genau einmal und den unbekannten Schreibzustand nach. Die anschließende
Prüfung der gesperrten Wiederholung, der expliziten nativen Recovery und des
Quell- beziehungsweise Zielstands bleibt vollständig erhalten. Testidentitäten,
Nummern und alle übrigen Testfälle bleiben unverändert; kein Fall entfällt.

Sämtlicher Produktcode und die Spezifikation 0.2.60 mit Q.5.2 bleiben je Phase
bytegleich zum angekündigten Stand. Keine neue normative Detailentscheidung,
Freigabe oder Budgetänderung. Alle Vorherbytes und Korrekturbindungen werden
an das neue Dirty-Result angepasst. Die vollständigen IDs 16.k.R und 16.k.C
behalten Reihenfolge, Rollen und Pflichtauswahlen. Apply prüft jede Stage
vor ihrem eigenen Commit mit N=3 plus voller Pflichtauswahl, Gruppen 2/0.
Dev hat keine Verhaltenstests ausgeführt. M16-Integrations-/Vollsuitegates
bleiben offen; vorbereitete Planhäkchen gelten erst nach tatsächlichem Commit.
