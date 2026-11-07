# OFF-PLAN – Delegierte Spezifikationsklärung (Bundle 389)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Delegierte Spezifikationsklärung (Bundle 389)

**Historischer Vertragsstand:** Die folgende Einführung und ihre Abnahmen
beschreiben **Vertrag 2 mit der Einerregel** und bleiben dafür erhalten.
Für neue gültige Verträge 3 gelten zusätzlich die ausdrücklich beauftragte
Erweiterung und Verfahrensabnahmen unter **SPECROAD-DECISION-1-V3 / Bundle 498**
sowie die Übergangsgrenze aus 2.4.3. Die damaligen Nachweise belegen keine
Vertrag-3-Ausführung; alte Aufträge und Antworten werden nicht umgedeutet.

Revision 6 setzt den ausdrücklichen Nutzerauftrag vom 22. Oktober 2026 als
**SPECROAD-DECISION-1** um. Spezifikation **0.2.11, Kapitel 2.4** erteilt die
begrenzte Entwicklungsbefugnis; Control-Bundle 014 stellt den getrennten
versionierten Auftragsvertrag bereit. Dies ist die ausdrücklich beauftragte
Einführung der Befugnis, keine eigenmächtige Delegation durch einen Dev-Turn.
Das vorhandene Readiness-Ergebnis aus Bundle 388 bleibt erhalten.

- [x] **SPECROAD-DECISION-1:** Delegierte Detailklärung, ihre Grenzen und die gebundene Übergabe verbindlich festlegen. Commit: `docs(spec): Begrenzte Entscheidungsbefugnis für Spezifikationslücken festlegen`.

**Entscheidung und Alternativen:** Eine pauschale Fortsetzung jedes
`blocked` würde echte Freigaben und fehlende Tatsachen verdecken; eine
Rückfrage bei jeder Detaillücke würde die beauftragte Selbstständigkeit
verhindern. Gewählt ist die vorher ausdrücklich delegierte, begründete
Präzisierung innerhalb vorhandener Anforderungen mit anschließender
Umsetzung und einer Grenze von einem gesonderten Klärungsbundle in Folge.
Autorität dieser Einführung ist der unmittelbare Nutzerauftrag, während
spätere einzelne Detailentscheidungen als `delegiert gemäß
SPECROAD-DECISION-1` gekennzeichnet werden. Eine persönliche Einzelzustimmung
zu späteren Entscheidungen wird nicht behauptet.

**Umfang und Erhaltung:** Genau ein OFF-PLAN-Dokumentcommit mit
Spezifikation, Plan und notwendigen aktiven Katalog-Hashbindungen. Keine
Produktimplementierung, neue Requirement-ID oder vorgezogene Planposition.
Produktcode, ausführbare Tests, Testnummern, Runner und lokale Arbeitsregeln
bleiben erhalten. Historische Evidence wird nicht umgebunden. Der
Produktstand bleibt **561/900**, letzter regulärer Commit **13.e.C**,
nächster regulärer Commit **13.f.W**. Der Entrypoint setzt nur diesen
Offplan-Abschluss und die Bundlenummer nach dem erfolgreichen parallelen
Apply-Gate; ein erzeugtes ZIP ist kein Commitnachweis. Spätere Änderungen
der Befugnis benötigen einen Nutzerauftrag und eine neue Dokumentfassung,
keinen Reset oder Verlust bestehender Arbeit.

**Verbindliche Abnahmen des Entscheidungsverfahrens:**

1. Eine im bestätigten Scope fehlende Detailregel wird anhand der aktuellen
   Quellen und geeigneten Alternativen entschieden; Spec, Begründung und
   positive/negative Grenzfall-Abnahmen sind vor abhängiger Umsetzung
   nachvollziehbar. Bei mehreren sicheren Lösungen wird begründet gewählt,
   nicht allein wegen der Auswahlmöglichkeit erneut gefragt.
2. Bestehende ausdrückliche Regeln, insbesondere 10.5.5/10.5.6 sowie
   TD-001/BD-001, bleiben bindend. Eine neue Erleichterung darf keine
   Pflichtgates, Review-/Evidence-Bindung, Scope- oder Kompatibilitätszusage
   umgehen. Ein angeblich konservativer Dauerfehler ersetzt kein Feature.
3. Fehlende Human-Reviews/Risikoakzeptanzen, unverzichtbare externe Fakten
   und unauflösbare gleichrangige Anforderungskonflikte führen zu `blocked`
   mit konkreter Frage, Empfehlung und Befugnisgrenze; kein erfundener Pass.
4. Nur Vertrag 2 mit `clarification_allowed=true` gestattet die automatische
   Übergabe als `spec_clarification`: genau eine nativ geprüfte gebundene
   ZIP, korrekte Quell-/Paket-SHA und sofortiger Abschluss ohne eigene
   Apply-/Warte-/Modellschleife. Der normale Planschritt bleibt offen.
5. Nach erfolgreicher Klärung folgt Umsetzung. Bei
   `clarification_allowed=false` kein weiteres Klärungsbundle und keine
   Umbenennung in `patch_ready`; nur echte Umsetzung/technische Korrektur
   oder begründetes `blocked`. Fehlgeschlagene und unklassifiziert
   übernommene Pakete geben keine neue Klärungsbefugnis.
6. Neue Dokumentbytes und aktive Katalogbindungen werden gemeinsam
   fortgeschrieben, alte Evidence bleibt historisch. Alte Aufträge,
   Pausen und `dev_blocked` werden durch Apply nicht freigegeben. Keine
   Änderung an Control-Konfiguration, Dienstzustand oder Watcher.

**Prüfgrenze:** Diese Abnahmen sind verbindliche Reviewkriterien des externen
Entwicklungsprozesses, keine neue SpecRoad-CLI-Funktion. Dokumentations- oder
Modelltests werden dafür nicht erfunden. Vollständige Collection-/Katalog-
und Paketprüfung bleiben erforderlich; Apply führt vor dem einen Commit
die nächste feste Testgruppe bei unverändertem N=3 parallel aus. Das
Ergebnis wird als Teiltestnachweis ausgewiesen. Ein tatsächlicher künftiger
Dev-Klärungsfall ist erst durch seinen eigenen Lauf und Result nachgewiesen.
