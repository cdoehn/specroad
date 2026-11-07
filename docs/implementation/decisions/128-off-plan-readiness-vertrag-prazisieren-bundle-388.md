# OFF-PLAN – Readiness-Vertrag präzisieren (Bundle 388)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Readiness-Vertrag präzisieren (Bundle 388)

Revision 5 schließt auf ausdrücklichen Nutzerauftrag die Vertragslücke vor
**13.f.W**. Spezifikation **0.2.10, Kapitel 10.5.6** definiert die geschlossene
Readiness-Policy, feste Pflichtgates, Risiko-/Issue-Status und gebundene
menschliche Abschlussentscheidungen einschließlich lesbarem Legacy-Bestand.
Die Verifikationsprioritäten aus 10.5 und der vollständige Release-Scope aus
13.e bleiben maßgeblich. Die aktive Katalogbindung folgt dem neuen Dokumenthash;
historische Evidence wird nicht umgebunden oder als neue Abnahme ausgegeben.

- [x] **READINESS-CONTRACT:** Spezifikation und Abnahmekriterien konsistent präzisieren. Commit: `docs(spec): Release-Readiness-Vertrag und Blockerregeln präzisieren`.

**Umfang:** Genau ein OFF-PLAN-Commit mit Spezifikation, Implementierungsplan
und notwendigen maschinellen Katalogbindungen. Keine Produktimplementierung,
keine Änderung an ausführbaren Tests, Testnummern, Runnern oder der Testpolicy.
Der abgeschlossene Produktstand bleibt **561/900**, letzter regulärer Commit
**13.e.C**, nächster regulärer Commit **13.f.W**. Die W/R/C-Positionen 562–567
bleiben offen. Der Übergabe-Entrypoint setzt diesen Offplan-Marker und die
abgeschlossene Bundlenummer erst nach dem erfolgreichen parallelen Apply-Gate.
Das erzeugte ZIP allein belegt keinen entstandenen Commit.

**Vertragsprüfung:** Policyfelder und Gate-Geltung sind abschließend; offene
Risiken und Issues blockieren. Terminalstatus benötigt den passenden aktuellen
Abschlussreview, Risikoakzeptanz eine ausdrückliche menschliche Entscheidung.
Fehlende, stale oder unklassifizierte Daten bleiben unvollständig. Warnungsfilter
und Waiver heben diese Pflichten nicht auf. Gespeicherte Bewertung, identische
CLI-Wiederholung, Konfliktcode 6 und ausschließlich vorläufige externe Auswahl
bleiben nach 10.5.4 erhalten. Migration schreibt nur über einen ausdrücklich
beauftragten normalen Change Plan; Lesen verändert keine Bestandsdaten.
