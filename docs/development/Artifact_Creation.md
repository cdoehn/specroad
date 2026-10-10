# Nativer Artefakt-Erzeugungsdienst

`specroad.authoring.creation.create_artifact` verbindet die vorbereiteten
Eingaben aus `authoring.inputs` mit dem bestehenden Change-Plan- und
Transaktionskern. Es ist ein ausführbarer Einbettungsdienst mit tatsächlichen
Dateiwrites; ein registrierter CLI-Befehl ist damit noch nicht vorhanden.

Der Aufrufer übergibt einen `TargetModel`, einen `ArtifactCreateInput`, ein
vollständiges `IdentityInventory` sowie eine ausdrücklich registrierte
`PublicationAuthority`. Weitere Pflichtargumente sind `actor`, `planned_at`
als UTC-Text, `change_plan_id` und `transaction_id`. `request_id` ist für Human
und Tool optional, für CI Pflicht. AI-Direktwrites bleiben abgewiesen.
`gates`, `strict` und `package_files` entsprechen den vorhandenen nativen
Publikationsschnittstellen. Externe Programme werden nicht gestartet.

Das Modell muss die tatsächlichen Projektdateien vollständig enthalten. Das
ID-Inventar muss aktuelle, archivierte und reservierte IDs aufführen; seine
aktuellen IDs und sein Präfix werden gegen das Modell geprüft. Der Dienst
entdeckt keine historischen IDs und bestätigt nicht die Vollständigkeit eines
vom Host gelieferten historischen Inventars. Modellwerte, Actor-Deklarationen
und Eingabeobjekte ersetzen keine Schreibberechtigung.

Der Ablauf ist:

1. Typisierte Eingaben, Actor-Regeln und Metadaten prüfen; einen vorhandenen
   Request anhand seiner nativen Abschlussbelege vor neuer Planung auswerten.
2. Den exklusiven nativen Writer-Lock nehmen und die Request-Prüfung wiederholen.
3. Unter diesem Lock die zufällige Artefakt-ID gegen das übergebene Inventar
   vergeben, Draft und Revisions-/Auditfelder über die nativen Konstruktoren
   vorbereiten und das vollständige geladene Zielmodell validieren.
4. Dieselben Dateien und Ressourcen vor dem Write erneut prüfen, Journal
   erstellen, Bytes stagen und über den vorhandenen atomaren Dateiaustausch
   veröffentlichen. Erst die verifizierten Abschlussbelege bestätigen Erfolg.
5. Die dafür vorgesehenen temporären Transaktionsdaten bereinigen. Ein Fehler
   bewahrt den tatsächlichen Zustand und vorhandene Recovery-Belege.

Das Ergebnisobjekt `format_version: 1.0.0` enthält Artefakt-ID, Typ, relativen
Pfad, Revision, Reifegrad und die native `completion`. Bei einer Wiederholung
werden ursprüngliche ID und ursprünglicher Commitbeleg geliefert; sie bestätigen
einen historischen Abschluss, nicht den heutigen Zielzustand. Eine bereits
bestätigte Anfrage wird weder neu geplant noch erneut veröffentlicht.
`completion.cleanup_completed` und `completion.commit_completed` bleiben
unabhängige Aussagen. Dieser Dienst führt ausschließlich tatsächliche Erzeugung
aus; die öffentliche Dry-run-/CLI-Anbindung bleibt offen.

Der W-Nachweis umfasst echte Veröffentlichungen für 15 Drafttypen über Mapping,
Datei und stdin. Für neun weitere reguläre Typen fehlen derzeit vollständige
native Fachgates, unter anderem Dokumentmodell, Evidence-Currentness und externe
Ressourcen. Solche Ziele werden abgelehnt, nicht mit erfolgreichen Ersatzprüfern
freigegeben. Das betrifft auch ein Projekt mit einem Primärdokument, solange
der Host keinen tatsächlichen Dokumentmodell-Prüfer bereitstellt.

SR-REQ-0216, SR-REQ-0217 und SR-REQ-0240 bleiben daher partiell. Vollständige
Projekt-/Historienbeladung, öffentliche CLI samt Dry-run und stdout-Vertrag,
weitere Fachgates und Plattform-/Releaseabnahme sind hier nicht abgeschlossen.

## Fehler- und Wiederholungsgrenzen

Kollisionen mit aktuellen, archivierten oder reservierten IDs werden durch den
vorhandenen Zufallsallocator innerhalb derselben exklusiven Schreibsperre
übersprungen. Sie verändern weder bestehende Revisionen noch das übergebene
Inventar. Ein Ausfall der Zufallsquelle oder ein ungültiges Entropieergebnis
wird als Betriebsfehler mit Code 5 gemeldet. Es gibt dabei keinen automatischen
Wiederholungsversuch nach dem Fehler und noch kein Journal oder Fachfile.

Der Dienst prüft auch bereits typisierte Eingaben erneut: Fehlende oder ungültige
Draftfelder und Spezialrecords, die einen eigenen Fachservice benötigen, werden
vor Lock und ID-Vergabe mit Code 3 abgelehnt. Ein abweichendes aktuelles
ID-Inventar oder eine nicht abgedeckte Modellreservierung ergibt Code 6.

Fehler an der nativen Veröffentlichung behalten ihren tatsächlichen Schreibstatus.
Auch eine fehlgeschlagene Systemoperation kann die Zieldatei bereits verändert
haben. Der Dienst meldet dann weder einen sicheren Nicht-Write noch einen
abgeschlossenen Commit. Journal und vorhandene Dateien bleiben für Recovery
erhalten. Ein normaler erneuter Create-Aufruf wird durch dieses Journal vor
weiterer ID-Vergabe blockiert; er startet keine automatische Reparatur.

## Gemeinsame Draft-Konstruktion

Die reine Zusammenstellung der Draftfelder liegt in
`model.draft_factory.prepare_draft_fields`. Für Requirements delegiert sie an
den bestehenden M2-Konstruktor `prepare_requirement`; die Auditfelder kommen
weiterhin aus `new_artifact_audit`. Typ, normalisierte Felder, Identität, Actor,
Zeit und Projektkonfiguration werden ausdrücklich übergeben. Es entstehen dabei
weder neue IDs noch Zeitwerte, Dateien oder Schreibberechtigungen.

Der Erzeugungsdienst behält seine Eingabeprüfung, Actor-/Zeitkonvertierung,
Pfadberechnung und nativen Artefaktprüfer. Transaktion, Wiederholungsprüfung und
Fehlergrenzen bleiben unverändert. Die Feldkonstruktion allein bestätigt weder
einen gültigen Gesamtzustand noch die Erlaubnis zur Veröffentlichung.
