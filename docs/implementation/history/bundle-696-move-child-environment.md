# Bundle 696 — Isolierte MOVE-Kindprozessumgebung

14. November 2026. Quelle: natives Fehler-Result mit SHA-256
`22e62a820d6ecd01a3b069791a6fd0af9e4ffdbb7058afabc864b98d64bc9b6f`,
HEAD `0d9ef4c473c7722c394fb13a96ab430b50400002`.
Bundle 695 endete in MOVE.C mit 8.911 bestandenen und zwei fehlgeschlagenen
Tests. Kein weiterer Commit entstand; MOVE.W/R bleiben bestätigt.

## Befund und Korrektur

Beide Varianten von `test_native_operator_move_reaps_source_and_runs_fresh_target`
scheitern in ihrer kleinen nativen Testumgebung beim Start des zu beendenden
Kindprozesses mit `OSError: [Errno 7] Argument list too long`. Die Argumente
selbst sind kurz. Pytest setzt jedoch `PYTEST_CURRENT_TEST` auf den vollständigen
280-KB-Testnamen; der Kindprozess erbt diese Umgebungsvariable bisher unverändert.
Damit erreicht der Test seine eigentliche MOVE-Anfrage noch nicht.

Der gemeinsame Testhelfer verwendet jetzt auch für diesen Kindprozess die
vorhandene `process_environment.test_environment`-Funktion. Sie erzeugt eine
separate Umgebung ohne geerbte Pytest-Zustandsvariablen und verändert die
Umgebung des laufenden Tests nicht. Lange Testidentität, Katalogbindung,
Supervisor-Nachrichten und gespeicherte Versuche bleiben vollständig erhalten.
Der echte Kindprozess und die bestehende Prüfung seiner Beendigung bleiben;
keine Mock-Erfolge, kürzeren Testnamen, geänderten Fristen oder Wiederholungen.
Das gilt für die lokale und die Proxy-Variante.

Der ursprüngliche lange Materialisierungstest, beide nativen Supervisorfälle
und alle sieben Protokolltests aus Bundle 695 haben bestanden. Der dortige
Supervisor-Fix bleibt bytegleich. Die neue Änderung betrifft ausschließlich
die Testvorbereitung und die verlinkten Plan-/Historieneinträge.

## Vollständiger Rest und Prüfung

`correction_of` bindet den Plan
`f6df1f0f7bb13370d3ef82eacfd4d8f26f34bbef4733fecba2bf8a08cfc05f96`
exakt an **MOVE.C**. ID, Rolle, Nachricht und die gesamte bisherige
Pflichtauswahl bleiben erhalten; die Vorherbytes stammen vollständig aus dem
neuen effektiven Result-Snapshot. Alle Aufrufer des geänderten Testhelfers
gehören zur Pflichtauswahl. Bestehende Testidentitäten und Nummern bleiben
unverändert. Apply ergänzt die fällige gefilterte N=3-Gruppe und committet
erst nach erfolgreichem Gate; keine zusätzliche Schluss-Suite.

Dev prüft Syntax, reine Collection, Stage-Fortsetzung und natives Bundleformat,
führt aber keine Verhaltenstests aus. Kein neuer Klärungspräfix, keine Änderung
von Spezifikation, Budgets oder Produktpositionen (762/918). 18.s.W folgt erst
nach erfolgreich abgeschlossener OFF-PLAN-Folge. Vorbereitet ist kein Apply-Erfolg.
