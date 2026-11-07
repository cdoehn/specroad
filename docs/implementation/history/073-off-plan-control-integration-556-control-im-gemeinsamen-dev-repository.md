# OFF-PLAN CONTROL-INTEGRATION-556 — Control im gemeinsamen Dev-Repository

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-INTEGRATION-556 — Control im gemeinsamen Dev-Repository

Vorbereiteter Zustand CONTROL-INTEGRATION-556.C; Abschluss ausschließlich nach
seinem tatsächlichen Apply-Gate und Commit. Produktstand bleibt 669/900,
nächster Produktcommit 16.d.W. Vollständiger Nutzerauftrag vom 3. November 2026:
Control zunächst pushen und sichern, danach Quell-/Betriebsstruktur integrieren.
Push und private Sicherung sind Bedienaktionen außerhalb der Payload.

Geprüfte SpecRoad-Basis: Result 3faa88, SHA-256
`2e5dd14d257575d86f5b6a1e9c5bfc0bcac149ca1f38f88bb847bbb841c99173`,
sauberer Abschluss `0883e7f919c6c1fbce921db59802e1813e330173`.
Control-Quelle: Result d56e7a, SHA-256
`d170766ec4c66690fbfcbd90be68761535330bce8e488675757b94cb88aba229`.
Control025 scheiterte ohne Commit nach 859/860 bestandenen W-Tests an einem
veralteten _enqueue-Testdouble. Seine authentisch gebundenen geplanten W/R/C-
Payloads werden vollständig übernommen, einschließlich der Signaturkorrektur.
Die alten Control025-Commits werden dadurch nicht als abgeschlossen erklärt;
der vollständige fachliche Rest erhält hier neue gemeinsame Apply-Gates.
Herkunft: tools/dev/codex/control/provenance.json. Kein Reset der alten Kopie.

W: vollständiger Quellimport, gemeinsame Testidentitäten/Pflichtauswahl,
zentraler Datenpfad, Releasebindung und offline gesicherte byteerhaltende
Migration. Abnahmen: alle bisherigen Control-Protokolle, optionale Klärung,
History-/Pause-/Budgeterhalt, Dienst-inaktiv-/Lockgrenzen, privates Backup,
Ablehnung geänderter Releases und Daten, unterbrochene Kopie bleibt gesperrt.
R: fortsetzbarer unterbrochener Releasewechsel, Erstinstallation ohne alte
Unit, schärfere Typ-/Pfad-/Archivgrenzen und Fehler-/Rollbacknachweise.
C: reine Trennung des Release-Datenvertrags von Dateischreiben/Systemd,
W/R-Verhalten und Tests bytegleich erhalten. Kein neuer fachlicher Umfang.

Alternativen: dauerhaft zweites Repository erhält doppelte Übergabe und
uneinheitliche Tests; Dienst direkt aus Dev führt unvollständige Zustände aus;
Betriebsdaten im Git gefährden private Daten und Recovery. Gewählt: ein
Quellrepository, ein externer Datenbaum und Result-gebundene Releasekopien.
Belegbare Migration benötigt erfolgreichen Apply-Abschluss; der Bundle-
Entrypoint führt keine Betriebsmigration und keinen Dienststart aus.
Dev-Verhaltenstests nicht ausgeführt; Collection/AST/Paketprüfung ersetzen
kein Apply-Gate. Neue/geänderte Tests und alle Control-Regressionen sind für
jede Stage ungefiltert Pflicht. Vorhandene Nummern bleiben erhalten.
