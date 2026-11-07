# OFF-PLAN CONTROL-START-DELAY-564 — Startfrist vor Automation

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-START-DELAY-564 — Startfrist vor Automation

Nutzerauftrag vom 3. November 2026: konfigurierbare Verzögerung, Standard 60 s;
nach Apply installieren, danach ambiguous_patch separat reparieren und erst
dann die Automatik starten. Höchstens vier Korrekturbundles als ausdrückliche
manuelle Ausnahme; Fehler anhand des jeweiligen nativen Results korrigieren.
Keine generelle Änderung der Control-Entscheidungs-/Budgetverträge.

Basis: erfolgreiches sauberes Result 563, SHA-256
`1ac02454e9b0002e43bd385e6b11c741609b2771fb24662e68659043c225f862`.
4c45d6e041a143dd19ac1232b858c2432374a830 beendet 16.d.C. Produktfortschritt
bleibt 672/900, 16.e.W offen. Die Auswahl eines externen systemd-Timers würde
weiter eine separate Bedienaktion erfordern; ein blockierendes Sleep würde
Status/Stop verzögern. Gewählt ist eine einmalige monotone Schranke im
vorhandenen Event-Loop; konfigurierte Null ist der explizite Sofortstart.

W: vollständige konfigurierte Startfrist, Legacy-Default ohne Config-Rewrite,
monotone Deadline, Statusrestzeit, IPC/Stop/Pause, Exchange-/Resume-Schranke,
laufende Speicherkontrolle. Abnahmen: Default 60, 0 und Bruchteile, kein früher
Tick/Modell/History-Wechsel, automatischer Ablauf, keine Folgeauftragspause.
R: strenger persistierter Statusvertrag, ungültige Grenzwerte und unveränderte
Fehlerbytes, Neustart unter Pause, Pause über Ablauf, SIGTERM und Speicherstop
während langer Startfrist. Kein Warten von 60 Sekunden in den Verhaltenstests.
C: Fristberechnung vom Event-Loop trennen; alle R-Tests und Fachregeln erhalten.

Vorbereitete Phase: C. Der Marker gilt ausschließlich nach ihrem eigenen
erfolgreichen Apply-Gate. Jeder Zustand erhält die volle Control-Suite plus
Katalog-/Apply-Regressionsauswahl ungefiltert zusätzlich zur N=3-Gruppe.
Dev führt nur Syntax, Collection und native Paketprüfung aus; keine Testkörper.
Der Entrypoint installiert keine Releasekopie und verändert keinen Dienst.
Diese Bedienaktionen folgen erst nach nativ bestätigtem vollständigem Erfolg.
