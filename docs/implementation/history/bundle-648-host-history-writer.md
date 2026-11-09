# Bundle 648 — Hostpool-Laufzeitschreiber und offener 18.b.R/C-Rest

9. November 2026. Maßgebliches Fehler-Result:
`cb8b7311ba16d3813e2df0a79de9e71eac08cb96448ca7b6ae35c398122a5c69`,
Base-Commit `b292024d2d4f375e577dbf3ab7d6a7b853c08914`.
Bundle 647 erzeugte **keinen neuen Commit**: 18.b.R brach mit internem
pytest-/xdist-Fehler ab, nachdem sieben Tests bestanden hatten. Es gibt keinen
bestandenen R-Gate-Nachweis. Der erfolgreiche W-Commit aus Bundle 646 bleibt
erhalten; nur die offenen IDs 18.b.R und 18.b.C mit Rolle `implementation`
werden in ihrer ursprünglichen Reihenfolge fortgesetzt.

Diese Datei beschreibt den vorbereiteten Zielzustand **18.b.C**. Sein
Planfortschritt gilt erst nach dem erfolgreichen eigenen Apply-Gate und Commit.
Die Vorherbytes entsprechen vollständig dem erhaltenen R-Stand aus Result 647.
Keine neue Detailklärung und keine Änderung des Klärungsbudgets.

## Befund und Korrektur

Die Beobachtung enthält `worker_nonzero_exit`, `pytest_internal_error` und
`host_pool_contract_error`; die History-Kanäle meldeten dreimal `OSError` und
einmal `ValueError`. Ein Worker endete mit noch ausstehendem Test, worauf xdist
abbrach. Die Fehlerausgabe nennt nur die Exceptionklasse des History-Fehlers;
seine konkrete Meldung wurde im ursprünglichen Lauf nicht gespeichert.

Die damals rund 1,67 GB große Laufzeitdatenbank wurde bislang pro Worker im
ersten synchronen History-Aufruf neu geöffnet und vollständig geprüft. Alle
14 Öffnungen konkurrierten um dieselbe Initialisierungssperre mit 30 Sekunden
Wartefrist; der Client wartet höchstens 60 Sekunden auf Bestätigung. Die
Datenbank zeigt über mehr als 30 Sekunden versetzte erste Starts, fehlende
Phasen und einen Worker ohne gespeicherten Start. Diese Befunde passen zur
konkurrierenden Initialisierung; ein fachlicher Assertionfehler ist durch
diesen Lauf nicht belegt.

Der Koordinator öffnet und prüft jetzt vor den Worker-Aufrufen genau einen
gemeinsamen History-Schreiber. Ein eigener Thread besitzt die SQLite-Verbindung
und serialisiert die kurzen nativen FULL-Transaktionen. Jeder Workerkanal
prüft weiter seine eigene Sequenz, Testidentität und Hostbindung; ACK folgt erst
nach Commit. Das Schließen eines Kanals schließt nicht den gemeinsamen Writer.
Sessionabschluss und Unconfigure schließen ihn nach den eingereihten Writes;
Speicher-/Integritätsfehler bleiben Fehler. Ein bereits abgebrochener Kanal
bleibt in der Gate-Beobachtung fehlerhaft, ohne beim Zurücksenden der Ablehnung
eine zweite unbehandelte Sendeexception auszulösen. Keine Timeout-Erhöhung,
Integritätslockerung, Messwertlöschung oder Änderung der ausgewählten Tests.

## Vollständiger Rest und Nachweise

Alle in [Bundle 647](bundle-647-correction-and-access.md) vorbereiteten Proposal-
Fixturekorrekturen und die ausdrücklich beauftragte Control-Vollzugriffswahl
bleiben enthalten. Der R-Zustand ergänzt diese Runnerkorrektur. C behält die
bereits angekündigte Proposal-Scope- und Codex-CLI-Policy-Bereinigung ohne neues
Verhalten. Die frühere System-Git-Korrektur am Remote-Host ist kein Testnachweis;
alle ursprünglichen Pflichtfälle bleiben erneut ausgewählt.

Neue Regressionen prüfen einen und vierzehn gleichzeitige Workerkanäle,
Threadbesitz und einmalige Vorabinitialisierung, unabhängig sichtbare dauerhafte
Writes vor ACK, getrennte Kanal-/Pool-Lebensdauer, Integritäts- und Speicherfehler
sowie Verbindungsverlust. Kleine native Datenbanken und synchronisierte Events
ersetzen Größenattrappen und Wartezeiten. Vorhandene echte execnet-/xdist-
Proxytests, Workerabbruch, Apply-Gate, lokale Historie und Runtime-Regressionen
gehören zusätzlich vollständig zur Pflichtauswahl beider Stages. Die gesamte
bisherige Proposal-/Git-/Control-Pflichtauswahl bleibt erhalten.

Dev prüft ausschließlich Syntax, reine Collection, stabile Testnummern,
exakte Stageübergänge und das native Paket. Alle Verhaltenstests laufen erst
im Apply. Keine Dienste, CI, direkten Apply-Schreibzugriffe oder Git-Commits.
Full Access ist weiterhin erst nach erfolgreichem Apply, geprüftem Offline-
Deploy und ausdrücklicher lokaler Konfiguration aktivierbar. 18.c und alle
späteren Produktpositionen bleiben offen.
