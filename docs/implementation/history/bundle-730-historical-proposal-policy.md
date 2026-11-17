# Bundle 730 — historische Proposalbelege und aktuelle Apply-Policy

Das native Result mit SHA-256
`8c2ca74332951d1004c8bb4ecb0f8491bde4c85664a08811b0d2b52d85869ae0`
bestätigt `18.n.W`, Commit `88cd5f45fc563a59fb39b8c45096b42a73dfae27`,
nach 8.007 bestandenen Testidentitäten. Damit sind 787/918 Produktcommits
bestätigt. Das R-Gate endet mit acht Fehlern und 8.087 bestandenen Tests;
R wurde nicht committed. Der erhaltene R-Arbeitsstand ist die Vorherbasis.

Sieben Fehler beginnen beim Aufbau historischer Abschlussbelege: Der neue
aktuelle Apply-Eingang verlangt einen Apply-Nachweis, den diese alten Originale
nach ihrem ursprünglichen Vertrag nicht enthalten. Auch der historische
Receiptleser rekonstruierte diesen Wert über denselben aktuellen Eingang und
würde deshalb gültige alte Belege ablehnen. Nach Spezifikation 10.7.3.1 bleiben
solche Originale lesbar, aber niemals ausführbare neue Schreibaufträge.

Die bestehende historische Journalprüfung rekonstruiert daher ausschließlich
den geschlossenen Auditwert einer abschließenden Proposal-Veröffentlichung.
Actor-, Request-ID-, Options-, Hash-, Original-, Plan-, Ziel- und Receiptprüfungen
bleiben erhalten. Ein vorhandener Apply-Nachweis muss weiterhin gültig sein;
ein defekter Nachweis fällt nicht auf den historischen Vertrag zurück.
Mehrfache Kontrolloperationen, fremde Spezialoperationen und Reviewpayloads
erteilen keine historische Ausnahme. Der aktuelle Authoring-Eingang und
aktive Journale verlangen weiterhin vollständige aktuelle Nachweise.

Die Abschluss-Fixture beschreibt ihre synthetischen historischen Auditfelder
direkt, statt sie über einen heutigen Schreibauftrag zu erzeugen. Beide
positiven Fälle prüfen zusätzlich, dass derselbe historische Operationsinhalt
als neuer Apply-Auftrag abgewiesen wird und der lesende Beleg keine Berechtigung
ist. Alle fünf bisherigen Manipulationsfälle bleiben erhalten; vier weitere
prüfen gefälschte Schreibberechtigung, Route, Kontrollfolge und Nachweis.

Der achte Fehler ist eine unvollständige AI-Testeingabe. Der echte Git-/Entwurfs-
Integrationstest liefert die vorgeschriebenen Modellfelder als `unknown` samt
expliziten synthetischen Gründen. Die Rückgabe muss diese Angaben erhalten;
es wird keine tatsächlich beobachtete Modellprovenienz behauptet.

Der vollständige offene Rest bleibt `18.n.R`, `18.n.C`, mit den ursprünglichen
Rollen `implementation` und exakten Commitnachrichten. Der erfolgreiche W-Commit
wird nicht wiederholt. C bewahrt die vorgesehene Trennung der Proposalpolicy
und exakt die korrigierten R-Testbytes. Jede Stage erhält ihr eigenes Apply-Gate
mit bisheriger vollständiger Pflichtauswahl und den betroffenen Journal-,
Receipt-, Proposal- und lesenden Bundle-Regressionen. Testnummern bleiben stabil.
Es gibt keine neue Spezifikationsentscheidung, Budget- oder Betriebsänderung.

Die Zielzähler 788 und 789/918 gelten erst nach dem jeweiligen erfolgreichen
Gate und Commit. Anschließend folgt 18.o mit eigenständigem persistentem
Workvertrag und seinen vollständigen Fortsetzungsabnahmen. Hier wird der
komplette Korrekturrest geliefert; kein Teilstand einer neuen Gruppe und keine
ungeklärte zusätzliche Workstruktur werden angehängt.

Dev führt nur Syntax-, statische, reine Collection- und native Paketprüfungen
durch. Diese Prüfungen sind keine bestandenen Verhaltenstests.
