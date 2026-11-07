# OFF-PLAN CONTROL-SOURCE-SELECTION-566 — Korrekturen eindeutig zuordnen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-SOURCE-SELECTION-566 — Korrekturen eindeutig zuordnen

Basis ist das nativ geprüfte saubere Result 565 mit SHA-256
`ffb1a445d05513bcc1872a55ac299fcef44f0a838138e5d33e60c765704e81b9`.
CONTROL-START-DELAY-564.W/R/C ist durch drei Apply-Gates mit 7367, 7375 und
7324 bestandenen Tests abgeschlossen; Commit 20dd536eedb98b95d0997ddadd2b4cc3f7befef9
ist als Control-Release installiert. Standardwartezeit 60 s und 64-MiB-Grenze
sind erhalten; Betriebsdaten blieben bytegleich. Der Dienst ist gestoppt.

Die vorhandenen Korrekturen 562 und 563 teilen vier Zustandswerte, verweisen
aber auf verschiedene vollständige native Quell-Results. Die bisherige
Suche berücksichtigte deren exakte SHA im v2-Plan nicht. Gewählt ist die
gebundene Quellprüfung. Auswahl nach Datum/Name oder Löschen alter Pakete
wären unbelegte Umgehungen; eine Umschreibung der History wäre keine Reparatur.
Dies ist der ausdrücklich beauftragte technische Fehlerfix, keine neue
fachliche Klärung und keine zusätzliche Produktimplementierung.

W: passive v2-Zuordnung samt nativer Prüfung des fremden Quell-Results;
gleiche Vierfachbindung, Archiv/Duplikate, echte Konkurrenz und vollständige
manuelle Fehlerkette ohne Modellaufruf oder Budgeterneuerung abnehmen.
R: unvollständige/falsche Quellbelege, innere/äußere Bindung, Repository/Dirty,
Run-ID-Konflikte und Dateirennen absichern; Legacy-/opaque Kandidaten und
bestehende klare Umsetzung bewahren. Neustart setzt keine History zurück.
C: passive Auswahl aus Exchange in eigenes Modul trennen, alle R-Tests und
Fachregeln unverändert. Jeder echte Zustand erhält volle Control-Regression
plus Apply-/Katalog-Pflichtauswahl zusätzlich zur fälligen gefilterten N=3-Gruppe.

Vorbereitete Zuordnungsphase: C. Abnahme gilt erst nach dem eigenen Apply-Gate.
Produktstand bleibt 672/900, nächster Produktcommit 16.e.W. Danach geprüfte
Releasekopie installieren und wie beauftragt die Automatik starten. Die
manuelle Fehlergrenze von höchstens vier Korrekturbundles gilt weiter; bisher
wurde eines für den Bootstrap-Testvertrag benötigt. Kein Testkörper in Dev.
