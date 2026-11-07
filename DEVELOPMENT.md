# SpecRoad entwickeln

Diese portablen Projektregeln ergänzen den bestätigten Implementierungsplan.
Explizite Nutzerentscheidungen und die für den Arbeitsort geltenden AGENTS.md
bleiben maßgeblich. Lokale Konfigurationen, Zugangsdaten und Sitzungskennungen
gehören nicht in das Repository oder in Produkt-Payloads.

## Vor einem Entwicklungsauftrag

1. Den Auftrag und das neueste vollständig geprüfte Result lesen. Seine vier
   Bindungswerte und sein vollständiger Snapshot einschließlich erhaltener
   Änderungen sind die technische Basis. Eine vorbereitete ZIP, ein Git-Commit
   allein oder eine Fortschrittszeile sind kein Test-/Apply-Nachweis.
2. Im [Planeinstieg](docs/implementation/SpecRoad_Implementierungsplan.md) den
   aktuellen Fortschritt und die nächste Position bestimmen. Danach den
   betroffenen Meilenstein, seine ausdrücklich verlinkten Ergänzungen und die
   benötigten Requirements, Regressionen und Spezifikationsabschnitte lesen.
   Historische Erfolgs- oder Offen-Aussagen gelten nur für ihre damalige Quelle.
3. Scope, Abhängigkeiten und vollständige Abnahmen des Schritts erhalten.
   Zusätzliche fachliche Detailklärungen richten sich ausschließlich nach
   SPECROAD-DECISION-1 und dem tatsächlich gültigen Entscheidungsvertrag;
   diese Dokumentationsstruktur erteilt keine zusätzliche Klärungsbefugnis.

## Umsetzung und Nachweis

W, R und C bleiben echte unterschiedliche Zustände mit ihrem jeweiligen
Apply-Testgate vor dem Commit. Eine Änderung ohne neues Produktverhalten,
wie die reine Aufteilung vorhandener Dokumente, wird als sachlich vollständiger
OFF-PLAN-Dokumentationscommit geführt; keine leeren W/R/C-Alibicommits und
keine Anrechnung auf eine Produktposition. Normale Produktarbeit behält ihre
vorgesehene W/R/C-Folge und vollständige Integrationsabnahme.

Die [gemeinsamen Planregeln](docs/development/Plan_Arbeitsregeln.md) beschreiben
die Phasen; [Apply-Commitpläne](docs/development/Apply_Commit_Plans.md) und
[Testing](docs/development/Testing.md) beschreiben die bestehenden Gates.
Dev entwickelt Verhaltenstests und deren Pflichtauswahl, führt aber keine
Testkörper, Fixtures oder Test-Unterprozesse aus. Reine Collection, Syntax-
und Paketprüfungen sind keine Verhaltensabnahme. Dokumentations-, Markdown-
und Darstellungstests werden gemäß TD-001 nicht als Produkttests eingeführt.
Die bestehende Apply-Rotation, Laufzeithistorie und stabile Testnummerierung
bleiben unverändert; GitHub-CI wird nur vom Nutzer manuell gestartet.

## Dokumentation fortschreiben

- **Fortschritt:** Der YAML-Block im Planeinstieg ist die einzige zentrale
  Fortschrittsstelle. Die Checkliste der betroffenen Detailposition wird im
  selben Commit konsistent gepflegt. Erfolgreiche und noch offene Teile einer
  unterbrochenen Folge bleiben getrennt. Geplante Zielwerte eines Bundles sind
  vor erfolgreichem Apply keine bestätigten aktuellen Ergebnisse.
- **Fachlicher Plan:** Umfang, Voraussetzungen und Abnahmen direkt beim Schritt
  ändern. Wiederkehrende allgemeine Regeln an ihrer gemeinsamen Stelle pflegen
  und verlinken; keine Kopien in jedem W/R/C-Abschnitt.
- **Entscheidungen:** Eine notwendige Detailentscheidung erhält einen kurzen
  Beleg mit Lücke, Alternativen, Wahl, Begründung, Befugnis und betroffenen
  Spezifikations-/Planstellen. Normative Spezifikation und aktive Bindungen
  werden weiterhin gemeinsam fortgeschrieben. Ein Beleg ersetzt keine Freigabe.
- **Ausführung:** Ein kurzer eigener Nachweis nennt Quelle, Bundle-/Commit-IDs,
  tatsächlich beobachteten Ausgang und offenen Rest. Umfangreiche Logs bleiben
  in den ursprünglichen Result-Artefakten; sie werden nicht in den aktiven Plan
  kopiert. Vom betroffenen Schritt und vom Nachweisverzeichnis aus verlinken.
- **Erhaltung:** Historische Belege nicht als heutige Regeln oder Erfolge
  umdeuten. Änderungen an der Ablage müssen alle Inhalte, Kennungen, Abnahmen
  und benötigten Verweise erhalten. Keine Löschung allein wegen Dokumentgröße.

Die konkreten Ablageregeln stehen in [docs/implementation/AGENTS.md](docs/implementation/AGENTS.md).

Die [Laufzeitbereinigung der Merge-Tests](docs/development/Test_Runtime_20261106.md)
dokumentiert die getrennt vorbereitete Testoptimierung und ihre erhaltene Abdeckung.
Die [anschließende Laufzeitbereinigung](docs/development/Test_Runtime_20261107.md)
beschreibt lokale Journalwert-Wiederverwendung, Release-Testdaten und die
Reihenfolge der unveränderten Apply-Testauswahl.

## Control und manuelle Vorbereitung

Control steuert die automatische Folge gebundener Einzelaufträge. Dev betreibt
keine eigene Apply-, Status-, Warte- oder Fortsetzungsschleife. Die alten
Chat-Kurzbefehle S und N bleiben aufgehoben; Testrotation N=3 bleibt bestehen.
Manuelle Entwicklungsarbeit setzt pausiertes/gestopptes Control ohne aktiven
Automatikauftrag voraus. Ein bereits laufendes Apply wird dadurch nicht beendet.

Ist ausdrücklich private Vorbereitung während eines laufenden Apply beauftragt,
bleibt das Ergebnis als solche gekennzeichnet außerhalb von Exchange. Ein
erwarteter Zielstand ist keine bestätigte Result-Bindung. Vor späterer Übergabe
müssen das neue maßgebliche Result, seine vollständigen Vorherbytes und der offene
Rest geprüft, der Commitplan neu gebunden und die fertige PatchHarbor-ZIP nativ
validiert werden. Ein vorbereiteter Arbeitsstand startet weder Dienst noch Apply.
