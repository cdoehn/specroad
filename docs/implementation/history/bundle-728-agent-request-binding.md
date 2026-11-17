# Bundle 728 — Agentenaufträge korrekt binden

## Belegter Ausgang

Quelle: natives Result vom 17. November 2026, SHA-256
`721fa0f52c5f35f8cc81fd6abf2d9f330cb3b33b606516c989b2ce7702d904d9`.

Das native Fehler-Result von Bundle 727 bestätigt `18.l.W`, `18.l.R` und
`18.l.C`. Deren Gates enthalten 15.017, 15.139 und 15.118 Testidentitäten.
Damit sind 783/918 Produktcommits bis einschließlich `18.l.C` bestätigt.
Diese drei erfolgreichen Commits sowie der bereits früher abgeschlossene
Klärungscommit `AUTHORING-PROPOSAL-726` werden nicht wiederholt.

`18.m.W` wurde installiert, aber nicht committed. Sein Gate meldet einen
Fehler bei 15.087 ausgewählten Tests: Der Agententest übergibt ein JSON-Dict
direkt an `CommandRegistry.bind_request`, obwohl diese Schnittstelle einen
`CommandRequest` verlangt. 15.086 bestandene Tests ergeben keinen bestandenen
W-Schritt. Die erhaltenen W-Dateien sind die vollständige Vorherbasis.

## Korrektur und abhängiger Rest

Der Test validiert das veröffentlichte Beispiel weiterhin gegen sein
Request-Schema. Anschließend verwendet er `CommandRequest.from_mapping`,
bevor er das Beispiel an die Registry bindet. Schema-, Befehls-, Ergebnis-
und Schreibschutzprüfungen bleiben erhalten. Die Produktschnittstelle wird
nicht erweitert und akzeptiert weiterhin keine untypisierten Registry-Aufträge.

Die Durchsicht der noch offenen R- und C-Stände findet denselben Fehler im
Variantentest; dort gilt dieselbe Korrektur. Der Test für die Ablehnung eines
AI-/CI-Reviews erhält außerdem einen expliziten synthetischen Hostadapter.
Ohne ihn würde der Handler schon wegen fehlender Hostautorität abbrechen,
bevor er den nichtmenschlichen Akteur prüft. Der Adapter darf im Test niemals
aufgerufen werden. Exitcode 7, der konkrete Grund `human_review_required`,
kein Autoritätsaufruf und vollständig unveränderte Projektbytes prüfen den
beabsichtigten realen Ablehnungspfad. Dies erteilt keine menschliche Freigabe.

Die Korrektur wird in allen drei abhängigen Zielständen fortgeführt. Der
vollständige offene Präfix bleibt `18.m.W`, `18.m.R`, `18.m.C`, jeweils mit
der bisherigen Rolle `implementation` und der exakten Plan-Commitnachricht.
Die Fachumfänge aus [Bundle 726](bundle-726-authoring-agents.md) und die
bestätigte Hostprofilkorrektur aus [Bundle 727](bundle-727-host-profile-storage.md)
bleiben erhalten. Keine neue Detailklärung, Budgetänderung oder Betriebsaktion.

## Abnahmen und Folgearbeit

Jeder Zwischenstand erhält sein eigenes Apply-Testgate vor seinem Commit.
Die beiden betroffenen Testdateien, alle bisherigen Pflichtprüfungen und
ihre relevanten Verbraucher bleiben vollständig ausgewählt. R führt zusätzlich
die Varianten- und tatsächlichen Handlerprüfungen aus; C hält sämtliche
R-Testbytes unverändert und bewahrt seine ursprünglich geplante Bereinigung.
Stabile Testnummern und die native Rotation bleiben unverändert.

Die vorbereiteten Zielstände entsprechen 784, 785 und 786/918. Diese Werte
sind erst nach dem jeweiligen erfolgreichen Apply-Gate bestätigt. Anschließend
folgt `18.n.W` mit den eigenständigen Abnahmen zu Policy- und Gitgrenzen.
Der Richtwert zweier Gruppen rechtfertigt keine zusätzlichen Produktcommits
allein für bereits vorhandene Schutzmechanismen oder Dokumentationsänderungen.
Diese Übergabe enthält den vollständigen offenen Rest, keinen Teil eines
neuen Planschritts.

In Dev werden ausschließlich reine Collection, Syntax-, statische und native
Paketprüfungen durchgeführt. Testkörper, Fixtures und Test-Unterprozesse
werden nicht ausgeführt. Die Verhaltensabnahme bleibt Aufgabe von Apply.
Lokale Konfigurationen, Zugangsdaten und Betriebsnachweise sind keine Payload.
