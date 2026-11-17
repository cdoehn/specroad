# Bundle 732 — reine Authoring-Policy ohne Aufrufimport

Das native Result mit SHA-256
`fadde8d15b2debbdd001a1127a104537e34c004a548f3b7795cfc8120bbee236`
bestätigt `18.n.R` aus Bundle 731 mit 8.832 bestandenen Tests und Commit
`eb503dfc2c6b08d95aab690d216e175cf7fbd073`. Damit sind 788/918 Produktcommits
bestätigt. Das nachfolgende C-Gate meldet einen Fehler und 9.099 bestandene
Tests; C wurde nicht committed. Ausschließlich der vollständige Rest `18.n.C`
wird mit seiner ursprünglichen Rolle `implementation` und Commitnachricht
fortgeführt. Der erfolgreiche R-Commit wird nicht wiederholt.

Der Fehler liegt im Refactoring: `prepare_authoring_request` importiert den
ausgelagerten Proposalprüfer während jeder Anfrage. Die bestehende Prüfung
`test_policy_and_bindings_need_no_external_state` blockiert Imports und
Dateizugriffe ausdrücklich; bereits eine leere allgemeine Anfrage scheitert
dadurch mit `Unexpected import`. Der Test prüft zusätzlich einen frischen
Prozess, damit zufällige vorherige Modulinitialisierung keinen Erfolg vortäuscht.

Die unveränderte Operationsprüfung liegt nun im bereits geladenen reinen
Authoring-Policymodul unter `changes`. Der generische Requestaufbau ruft sie
ohne weiteren Import auf. Die bedingten Importe der nativen Proposal-
Spezialisten, ihre Prüfungen, Reihenfolge und Fehler bleiben gleich. Ein
unbedingtes Vorladen des Proposalpakets würde unnötige Abhängigkeiten am
Moduleingang schaffen; eine bloße Ausnahme für leere Listen würde allgemeine
nichtleere Anfragen weiterhin mit zusätzlichen Imports belasten. Die gewählte
Aufteilung erhält beide reinen Pfade und die eigentliche C-Bereinigung.

Die im fehlgeschlagenen C neu angelegte, noch uncommittete Hilfsdatei
`src/specroad/proposals/_authoring_policy.py` wird über den vorhandenen nativen
Löschvertrag entfernt. Ihr vollständiger Vorherinhalt und SHA-256 bleiben in
der Stage gebunden. Alle aktiven Aufrufer verwenden das bestehende Policymodul.
Keine direkte Apply-Änderung und keine Abschwächung der Löschprüfung.

Alle Testbytes bleiben identisch zum erfolgreich committeden R. Die gesamte
bisherige Pflichtauswahl, stabile Testnummern, fachliche Verträge, Review- und
Writergrenzen bleiben erhalten. Das eigene C-Gate führt die fällige gefilterte
N=3-Gruppe zusammen mit der ungefilterten Pflichtauswahl vor dem Commit aus.
Der Zielstand 789/918 und `18.o.W` als nächste Position gilt erst nach diesem
erfolgreichen Gate. Kein Test wird wegen des Fehlers abgeschwächt oder entfernt.

Die geprüfte nächste Gruppe 18.o verbindet persistierte Workfortsetzung mit
Inhalt, Basis, Engine und echten Reviewbelegen. Dafür gibt es im aktuellen
Workbestand noch keinen Proposaladapter mit geschlossenem Datenvertrag.
Diese Korrektur schließt den vollständigen gebundenen C-Rest; sie hängt keine
neue Detailentscheidung oder teilweise Workimplementierung an. 18.o und die
davon abhängige Gruppe 18.p bleiben offen. Keine Klärung oder Budgetänderung.

Dev prüft ausschließlich Syntax, statische Konsistenz, reine Collection und
native Paketverträge. Ein vorbereiteter Zielstand ist keine Verhaltensabnahme.
