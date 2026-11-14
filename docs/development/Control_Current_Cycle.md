# Control vom aktuellen Stand starten

`control start --from-current` ist eine ausdrückliche neue Arbeitsfolge.
Der native Checkpoint erhält HEAD, Index und Arbeitsbaum; ein dirty Ausgang
ist kein Testnachweis. Neue Budgets stammen aus der lokalen Policy.
Ein gewöhnliches `start`, `resume` oder Dienstneustart behält den aktuellen
Zyklus und seine verbrauchten Budgets.

Vorgemerkte Neustarts warten auf den freien Dev-Thread, den nativen Apply-Lock
und ausstehende fremde Pakete. Sie ersetzen keine laufenden Tests.
Wiederholung einer Vormerkung verwendet dieselbe ID. Ein nach Unterbrechung
wiederverwendeter Checkpoint wird vor Aktivierung nativ erneut geprüft.
Ein inzwischen veränderter Arbeitsstand benötigt eine neue Momentaufnahme;
die alte bleibt im privaten Auftragsverzeichnis erhalten.

Der aktive Datenbankzeiger wird atomar veröffentlicht. Frühere Datenbanken
bleiben für vorhandene Leser erhalten. Verdrängte Threadwechsel-Vormerkungen
und der abgeschlossene Startauftrag werden vor Entfernung bytegleich unter
`state/start-requests/<ID>/superseded/` gesichert. Diese lokalen Daten gehören
nicht ins Repository. Ein Abbruch nach Veröffentlichung füllt kein Budget
erneut auf. `control status` zeigt `current_cycle` mit Vormerkung, Zyklus und
Quellhash; der lesende Status ist kein Auftrag und kein Apply-Erfolgsbeleg.

Ein Pfad-/Linienwechsel braucht eine passende lokale Konfiguration und einen
eigenen expliziten Start. Alte Aufträge werden nicht auf ein anderes Ziel
umgebunden. Installation, Entwicklung und Status starten keine Automatik.
