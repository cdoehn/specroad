# OFF-PLAN CONTROL-RECOVERY-593 — belegte Korrekturkette und Watcher-Timeout

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-RECOVERY-593 — belegte Korrekturkette und Watcher-Timeout

Ausdrücklicher manueller Nutzerauftrag vom 5. November 2026. Voraussetzungen
für den gewünschten Automatikstart: die CI-Reparaturen aus Bundle 592,
mehrstufige Recovery des tatsächlichen M16-Verlaufs und echte Timeoutübergabe
an den vorhandenen Watcher. Kein neuer Seed, keine umgeschriebene History,
kein Budgetreset und keine automatische Klärungsfreigabe. Gewählt wird der
zusätzliche explizite Befehl aus Spezifikation 2.5.4.3; die älteren Befehle
behalten ihre Grenzen. Produktstand bleibt 693/900, nächster Schritt 17.a.W.

W: geschlossene passive Kettenprüfung über Paket-/Result-SHA und vier Werte,
mehrere Fehler/Korrekturen einschließlich echtem äußeren Timeout und engem
zustandserhaltendem Push; vollständige Rest-IDs, Rollen, Pflichtauswahl,
Snapshotbytes und Gates. Additive V3-Vormerkung, idempotente Speicherung,
erneute Nachweise, atomare Übernahme erst bei inaktivem Thread. Bestehende
Blockade-, Pause-, Archiv-, Transaction- und Budgetregressionen bleiben
Pflicht. Watcheradapter delegiert an vorhandenen nativen Ereignisloop und
übergibt den konfigurierten Timeout ausdrücklich in den isolierten Worker
und `api.apply_next`, einschließlich leerem/fehlendem Scope.

R: fehlende oder widersprüchliche Timeoutbelege, manipulierte Pushnachweise,
ausgelassene Reste/Tests/Rollen, fremde Änderungen, Konkurrenz, Replay,
Grenzen und Änderungen nach Vormerkung sperren. Native Fehler, Signale,
Diagnosekanäle und ungewöhnliche Timeoutwerte werden erhalten/geprüft.
C: reine strukturelle Trennung von Fortschritts- und Historyvalidierung;
W-/R-Testdateien bleiben bytegleich. Keine Berechtigungs- oder Policyänderung.

Spezifikation 0.2.62, Planrevision 95 und sämtliche aktiven Katalogbindungen
werden mit W gemeinsam fortgeschrieben. Jede Stage erhält ihr eigenes
N=3-plus-Pflichtauswahl-Gate; keine vorgezogene Endstandinstallation.
Dev führt keine Verhaltenstests aus. Ergebnisse werden erst aus dem tatsächlichen
nativen Apply gemeldet. Lokale Konfigurationen, Sessions, Units und
Betriebsdaten fehlen in Payloads. Installation, Recovery-Vormerkung,
Watcherumstellung und Automatikstart sind anschließend ausdrücklich erlaubt,
bleiben aber an den geprüften Erfolgsnachfolger und die Betriebsgrenzen gebunden.
