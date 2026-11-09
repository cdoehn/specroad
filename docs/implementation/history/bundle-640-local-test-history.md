# Bundle 640 — Hostdaten auch für lokale Testläufe

9. November 2026. Quelle ist das erfolgreiche saubere Result mit SHA-256
`fa0c5a96acb2e3e078816152e5e0bc5090575098651ec91578f18b63ed130c9f`.
Bundle 639 hat R mit 7.410 und C mit 7.414 bestandenen Tests abgeschlossen;
Endcommit `8c0816b9ac92810f09eea86deaf51bde61b65048`. Die vorherige Remote-
Testhost-Folge ist damit vollständig übernommen. Das belegt keine Einrichtung
externer Hosts oder schon erfolgte Messung auf solchen Hosts.

Der neue [ausdrückliche Auftrag](../decisions/local-test-history-640.md)
füllt die zuvor fehlende lokale Hostzuordnung. Die vorhandene Tabelle
`attempt_hosts` wird genutzt, ohne Schemawechsel oder Nachbeschriftung älterer
Messungen. Pro lokalem Runnerprozess wird die Identität einmal erfasst; jeder
neue Teststart speichert Host/Umgebung gemeinsam mit dem Versuch dauerhaft.
Die bestehende Pool-RPC-Zuordnung bleibt unabhängig und unverändert.

Die drei echten Zwischenstände ergänzen zunächst die lokale Speicherung,
dann Fehlergrenzen und Nachweisprüfung und zuletzt die gemeinsame
Umgebungsberechnung. Verteilungsstrategie, N=3, Laufzeitfilter, Testidentitäten,
Phasenmessungen, Datenbankpfade und getrennte Entwicklungslinien bleiben erhalten.
Der Test-Monitor nutzt seine bestehende Hostspalte und JSON-Felder.
Keine neue Vergleichsoberfläche, Remote-Einrichtung, Dienst-/CI-Starts oder
rückwirkende Änderung historischer Messungen gehören zu diesem Bundle.

Dev-Teststatus: nicht ausgeführt. Syntax, reine Collection und native
Paketvalidierung sind Vorbereitungsprüfungen. Die Verhaltenstests werden
jeweils im Apply vor dem W-, R- und C-Commit ausgeführt. Produktfortschritt
und nächste Position bleiben 729/900 und 18.a.W; nur der erfolgreiche
C-Commit setzt den letzten Bundlezähler auf 640.
