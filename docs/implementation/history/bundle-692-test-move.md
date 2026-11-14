# Bundle 692 — gezielte Testverlagerung

Quelle ist das vollständig erfolgreiche Result zu Bundle 691, SHA-256
`800e58d29280f6a5535eab47ae4f671e62a423b626db62f13a37fc8c9b9c6061`.
LIVE.W/R/C sind darin mit 7.586, 7.745 und 7.711 bestandenen Tests jeweils
committed. Der saubere Ausgangsstand endet bei
`ada987bf1f7943cf3b2e1380c37679e0e044fb22`; erfolgreiche IDs werden nicht wiederholt.

Die nächste bereits bestätigte vollständige Gruppe ist MOVE.W/R/C gemäß
[START-CURRENT-685](../decisions/control-start-test-control-685.md).
Keine neue normative Detailklärung und kein Klärungspräfix sind erforderlich.
Die drei Zustände werden einzeln installiert, geprüft und erst danach committed.
W liefert Verlagerung, Abbruchbestätigung, frische Fixtures und beide
Versuchskonten; R behandelt Rennen, Ausfälle und fremde Aufträge; C trennt
Prozessaufsicht, Versuchsnachweis und lesende Anzeige strukturell.

Ein eigener Linux-Subreaper überwacht genau einen Worker. Ein Abbruchauftrag
bindet dessen aktuellen Versuch, wartet auf das Ende seines Prozessbaums und
erlaubt erst danach den reservierten Zielworker. Der Zielhost gehört zum bereits
geprüften Pool; gemeinsame Hostslots und Nice-/IO-Vorgaben bleiben bestehen.
Ein SSH-/Workerverlust oder fehlender Endnachweis erzeugt keinen Retry-Erfolg.

Die Laufzeitdatenbank erhält bei der ersten bestätigten Verlagerung eine
transaktionale Migration auf Version 2. Alle bisherigen Versuch-IDs, Hosts,
Zeitpunkte und Phasen bleiben erhalten. Der abgebrochene Versuch bleibt ungültig;
nur sein ausdrücklich gebundener Nachfolger darf denselben Test im selben Lauf
neu beginnen. Ältere Schreiber lehnen die neue Version ab. Normale Läufe ohne
Verlagerung behalten Version 1. Die neuen Leser unterstützen beide Versionen.

In Dev erfolgen ausschließlich Syntax-/Vertragsprüfung und reine Collection.
Diese Vorbereitung behauptet keine bestandenen MOVE-Verhaltenstests. Jedes
Apply-Gate enthält die vollständigen betroffenen Tests und die fällige
N=3-Gruppe. Die Integration benutzt echte pytest-/execnet-Prozesse mit privaten
lokalen und Proxy-Snapshots; keine bestehenden Testhost-Anmeldungen oder
Messdatenbanken werden als Testfixture benutzt. Die gesamte START/CONFIG/LIVE-
Regression bleibt Bestandteil der Pflichtauswahl.

Diese Gruppe schließt einen eigenständigen, zusammenhängenden Betreiberauftrag
einschließlich Prozessbeendigung und Gate-Nachweis ab. Danach bleibt der getrennte
Produkt-Recovery-Rückbau ab 18.s.W; Produktzähler und Scope werden hier nicht
verändert. Kein Control-/Watcherstart und keine Installation durch Dev.
