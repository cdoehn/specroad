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

## Verhaltenstests effizient gestalten

Für neue und überarbeitete Tests gelten die [gemeinsamen Regeln für effiziente
Testdaten und Vorbereitung](docs/development/Testing.md#effiziente-testdaten-und-vorbereitung).
Das kleinste vollständige native Projekt verwenden, das die jeweilige Aussage
trägt. Große Ressourcen gezielt durch vollständige Integrationsreferenzen
abdecken; veränderliche Projektzustände bleiben pro Fall getrennt. Die Regeln
ändern weder fachliche Abnahmen noch die Apply-Auswahl oder Teststartbefugnis.
Der [Testbereich](tests/AGENTS.md) verweist auf dieselbe maßgebliche Regelstelle.

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
Die [Fixture-Bereinigung](docs/development/Test_Fixture_Efficiency_20261107.md)
erweitert kleine native Testdaten auf passende Merge-/Release-Fälle und trennt
die Vorbereitung reiner Eingabeprüfungen von Prüfungen lebender Quellen.

## Control und manuelle Vorbereitung

Der versionierte [Test-Monitor](docs/development/Test_Monitor.md) verbindet
mehrere Apply-Ziele, laufbezogene Testphasen und ihre getrennten Laufzeithistorien
in einer lesenden TUI: `python3 tools/test-monitor --all`. Für Skripte:
`python3 tools/test-monitor --all --once --json`. Die Anzeige startet keine Dienste.

Die versionierten [Statushelfer](docs/development/Status_Helpers.md) zeigen
Apply-Fortschritt, Belegung und gemessene Testlaufzeiten:
`python3 tools/apply_status.py --all` beziehungsweise
`python3 tools/test_time.py -n 10`. Sie wählen standardmäßig die zur aufgerufenen
Kopie gehörende Apply-Linie. Pfadoptionen überschreiben nur die lesenden Quellen.
Eine Freimeldung ist eine Momentaufnahme, keine Reservierung oder Freigabe für
ein ungebundenes Bundle. Die Skripte starten keine Tests oder Dienste.

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

## Lokale Arbeitsabstimmung zwischen Entwicklungs-Chats

Vor der ersten Änderung `CURRENT_WORK.txt` im Root der eigenen Dev-Kopie
prüfen und für die eigene Arbeit anlegen beziehungsweise aktualisieren.
Aufgabe, Entwicklungslinie/Branch, Zeitpunkt, Status und voraussichtlich
betroffene Dateien oder eng abgegrenzte Bereiche nennen. Bei einer zweiten
Entwicklungslinie auch deren vorhandene Notiz lesen, soweit sie zugänglich ist;
Überschneidungen vor der Änderung abstimmen. Eine fremde aktive Notiz nicht
überschreiben. Fehlende oder veraltete Notizen gelten nicht als Freigabe.
Die Notiz ist eine Orientierung und ersetzt weder tatsächliche Diff-/Status-
prüfung noch Sperren, Result-Bindung oder getrennte Apply-Zuständigkeiten.

Die eigene Notiz bei Scopewechsel sowie unmittelbar vor Übergabe, Pause oder
Abschluss aktualisieren; danach offene Arbeit und den aktuellen Status
ausdrücklich benennen. Keine Zugangsdaten oder Session-IDs aufnehmen.
`/CURRENT_WORK.txt` bleibt über `.gitignore` ausgeschlossen und darf weder
in Git noch in Produkt-/Patch-Payloads kopiert werden. Die lokale Datei ist
kein zu commitender Entwicklungsnachweis.


### Aufgabenhistorie mit Zeitstempeln

Zusätzlich `CURRENT_WORK_HISTORY.txt` im Root der eigenen Dev-Kopie führen.
Bei Beginn, Scopewechsel, Übergabe, Pause und Abschluss jeweils einen neuen
Eintrag mit aktuellem ISO-8601-Zeitstempel einschließlich Zeitzone, Anlass und
der vollständigen Aufgabenübersicht aus `CURRENT_WORK.txt` anhängen. Vor dem
Ersetzen einer bisher nicht protokollierten Übersicht auch deren gelesenen
Stand als Übernahme festhalten; der Zeitstempel bezeichnet die Protokollierung,
nicht einen erfundenen früheren Arbeitsbeginn. Erledigte und offene Arbeiten
sowie tatsächlich geprüfte Ergebnisse klar unterscheiden. Bestehende Einträge
nicht überschreiben oder löschen; Fehler durch einen neuen Eintrag korrigieren.
Kein automatisches Nachtragen unbelegter früherer Tätigkeiten.

Beide Dateien bleiben lokale Abstimmungsdaten: `/CURRENT_WORK.txt` und
`/CURRENT_WORK_HISTORY.txt` über `.gitignore` ausschließen, niemals als Payload
oder Entwicklungsnachweis committen. Keine Zugangsdaten, Konfigurationen oder
Session-IDs aufnehmen. Die Historie ersetzt keine Sperre, Git-Historie oder
Apply-Abnahme und bezieht sich ausschließlich auf die eigene Entwicklungslinie.

## Abgewiesene oder überholte Patch-Übergaben

Eine Ablehnung der Übergabe nach Exchange beendet den fachlichen Auftrag nicht.
Ablehnungsgrund, bisherige ZIP, Quell-Result und offene Commitfolge erhalten und
prüfen. Bei belegter bloßer Belegung des richtigen Apply bleibt die vorhandene
ZIP bestehen; Control/Watcher übernehmen das Warten. Kein zweiter Patch für
dasselbe Result und keine eigene Warteschleife im Dev-Chat.

Weicht der maßgebliche native Apply-Zustand inzwischen ab, zunächst dessen neues
vollständiges Result prüfen. Die vorbereiteten Änderungen inhaltlich mit dessen
Snapshot abgleichen und auf dieser Basis erneut vorbereiten: sämtliche Vorherbytes,
alle vier Bindungswerte, exakter Quell-Result-SHA und Korrekturbezug aktualisieren.
Fremde Änderungen erhalten, erfolgreiche Commits nicht wiederholen, alle offenen
IDs/Rollen und Pflichtabnahmen fortführen. Nur Bindungsfelder auszutauschen reicht
nicht. Ein belegter offener Klärungspräfix bleibt bytegleich; keine neue Entscheidung
oder Budgetänderung durch diesen Wiederanlauf. Bei Konflikten ohne fachliche
Befugnis oder unklarem aktuellen Result konkret blockieren.

Anschließend genau eine neue ZIP für dieses neue Result nativ validieren und
atomar nach Exchange übergeben. Bereits veröffentlichte ZIPs und Belege nicht
überschreiben oder löschen. Nach der Übergabe endet der Dev-Turn. Control erteilt
bei erneutem belegtem Zustandswechsel einen neuen gebundenen Einzelauftrag;
kein blindes Wiederholen derselben abgewiesenen Datei. Vorbereitungen während
eines laufenden Apply bleiben ausdrücklich vorläufig außerhalb von Exchange.
Ein noch nicht veröffentlichtes Bundle kann um einen neuen Nutzerauftrag ergänzt
werden; ein veröffentlichtes Bundle benötigt eine neue belegte Folgeübergabe.

## Remote-Testhosts entwickeln

Der ausdrücklich beauftragte Pool gilt ausschließlich für normale Apply-Gates.
[Hostvertrag und Bedienung](docs/development/Remote_Test_Hosts.md) sind maßgeblich.
Konfiguration, Schlüssel, SSH-Sockets, Messdatenbanken und Host-Arbeitsverzeichnisse
bleiben lokal. Keine Einrichtung oder Dienstaktion als Nebenwirkung eines Bundles.
Testabdeckung und Prioritäten nach den [Testregeln](docs/development/Testing.md)
erhalten; echte W/R/C-Zustände bleiben getrennt.
