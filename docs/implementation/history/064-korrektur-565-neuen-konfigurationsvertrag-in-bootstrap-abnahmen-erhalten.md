# Korrektur 565 — neuen Konfigurationsvertrag in Bootstrap-Abnahmen erhalten

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrektur 565 — neuen Konfigurationsvertrag in Bootstrap-Abnahmen erhalten

Das native Fehler-Result c158372ff3450354cebb64aa1eebfc711ea183ced5ca9e6ceb8cf8b797b62403
belegt 7309 bestandene und elf fehlgeschlagene W-Tests, ohne Commit.
Alle elf Fehler stammen aus drei noch unveränderten alten Feldmengenprüfungen:
start_delay_seconds war dort nicht enthalten. Der neue normative Vertrag bleibt;
die Prüfungen bleiben geschlossen und ergänzen das Feld samt Werterhaltung.
Ein gezielt erweiterter Fall belegt den Erhalt einer ausdrücklich gewählten Verzögerung
bei Legacy-Migration ohne History-Reset oder Modell-/Dienststart. Keine Tests
werden entfernt oder abgeschwächt, keine Laufzeitbehauptung ersetzt ein Gate.

Die vollständig erhaltenen W-Dateien sind die neue Vorherbasis. Alle offenen
IDs CONTROL-START-DELAY-564.W/R/C bleiben samt Rollen, Reihenfolge, vollständigem
Umfang und Pflichtauswahl erhalten. Bereits erfolgreiche Commits: keine.
Erstes Korrekturbundle innerhalb der einmaligen Grenze von höchstens vier.
Dev hat keine Testkörper ausgeführt; erneute Abnahme vollständig durch Apply.
