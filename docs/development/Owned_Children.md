# Lebensdauer ausdrücklich gestarteter Kindprozesse

`specroad.runtime.children.run_child(arguments, cwd=..., environment=...,
input_bytes=None)` ist eine synchrone Host-API für einen ausdrücklich erlaubten,
vertrauenswürdigen direkten Kindprozess. Die Argumente sind ein Tupel aus Strings
mit absolutem Executablepfad; Arbeitsverzeichnis und vollständige Umgebung werden
ausdrücklich als String beziehungsweise Dictionary übergeben. Der Adapter löst
keinen Befehl aus Work- oder Projektinhalt auf. Welche Distribution und Operation
zulässig sind, muss der aufrufende vertrauenswürdige Fachadapter separat prüfen.

Der öffentliche Adapter und seine Fehlerklassen bleiben in `runtime.children`.
Die interne Lebensdauerstrategie liegt in `runtime._child_cleanup`; der Adapter
übergibt ihr sein direktes Kind, die ursprüngliche Ausnahme und seine bestehende
Cleanupfehlerklasse. Die Strategie startet selbst keine Prozesse und definiert
keine neue Ausführungsberechtigung. Spätere vertrauenswürdige Git-/Analyzeradapter
können so denselben Einstieg nutzen, ohne eine zweite Cleanupimplementierung
einzuführen. Die bestehende Operationsfolge und sämtliche Fehlerdaten bleiben
bei dieser Aufteilung erhalten.

Der Aufruf verwendet keine Shell, keine PATH-Suche und keine implizit geerbte
Umgebung. Nicht ausdrücklich übergebene Eingabebytes bedeuten geschlossenes stdin.
Ausdrückliche Eingabe und beide Ausgabekanäle werden binär über Pipes übertragen;
andere Parent-Dateideskriptoren bleiben geschlossen. Der POSIX-Kindprozess läuft
in einer eigenen Session. Es entstehen keine Hintergrundthreads, Worker-Pools,
Watcher oder dauerhaften Dienste des Core.

`CompletedProcess` enthält den tatsächlichen Returncode und die vollständigen
stdout-/stderr-Bytes. Ein fachlicher Erfolg wird daraus nicht abgeleitet. Auch
ein negativer Signalstatus oder ein von null verschiedener Code bleibt erhalten;
es gibt keinen automatischen Wiederholungsversuch und keine voreingestellte
Laufzeitgrenze. Kleine abgeschlossene Aufrufe warten synchron bis zum Ende.

Bei einer im Aufruf behandelten Ausnahme wird versucht, ein noch laufendes
direktes Kind zu beenden und einzusammeln. Alle eigenen Pipes werden anschließend
einzeln zu schließen versucht, auch wenn ein vorheriger Cleanupschritt scheitert.
Wiederholte `KeyboardInterrupt`-/`SystemExit`-Unterbrechungen werden während der
nativen Cleanupoperationen zurückgestellt; `InterruptedError` wiederholt nur die
betroffene Operation. Nach erfolgreichem Cleanup bleibt eine ursprüngliche
Aufrufausnahme erhalten. Ohne ursprüngliche Ausnahme wird die erste während des
Cleanups behandelte Unterbrechung danach weitergereicht.

Ein anderer Cleanupfehler ergibt `ChildCleanupError` mit dem maschinenlesbaren
Grund `child_cleanup_incomplete` und Exitcode 5. `as_dict()` enthält den tatsächlich
beobachteten PID-/Returncodezustand, `child_reaped`, die noch offenen eigenen
Pipes, den Unterbrechungsstatus und fehlgeschlagene Operationen mit Exceptiontypen.
Die Daten enthalten keine Argumente, Umgebung oder nativen Fehlertexte; ihre
Listen sind vom Fehlerobjekt getrennt. Ein fehlgeschlagener Kill gegen ein noch
laufendes Kind führt nicht zu einem blockierenden Wait oder einem Erfolgsergebnis.
Der Fehlerzustand kann ausdrücklich ein noch lebendes Kind oder eine offene Pipe
ausweisen und erteilt keine neue Berechtigung zum späteren Signalisieren einer PID.

Diese Bereinigung besitzt keine Work-, Snapshot-, Journal- oder Ergebnisdateien
und löscht keine davon. Bei erfolgreichem Cleanup werden native Start-/I/O-Fehler
weitergereicht; ein fehlgeschlagener Start wird nicht zu Erfolg oder Code 8 erklärt.
Bei zusätzlichem Cleanupfehler bleibt die ursprüngliche Ausnahme dessen Ursache.

Der erste Ausschnitt verarbeitet vollständige Ein-/Ausgaben im Speicher auf
POSIX-Systemen. Er ist für vertrauenswürdige direkte Kinder vorgesehen, die keine
eigenständigen Nachkommen oder Daemons hinterlassen. Er ist keine Sandbox für
beliebige Programme. SIGKILL, OOM oder anderer unbehandelter Hostverlust kann
Python-Cleanup verhindern. Große fortsetzbare Streamprotokolle, automatische
Verbrauchsintegration und konkrete Git-/Analyzer-Adapter bleiben gesonderte
Schritte. Unbehandelter Hostverlust und beliebige Unterbrechungen außerhalb der
behandelten Python-/nativen Operationsgrenzen bleiben außerhalb dieser Zusage.

Die bisherigen Work-Abläufe laufen weiterhin synchron im Core. Der neue Adapter
startet beim Import nichts und ist derzeit nicht aus Workdaten oder einem neuen
CLI-Befehl erreichbar. Die Nachweise umfassen echte direkte Prozesse, Pipes,
Returncodes, native `waitpid`-Eigentumsprüfung, reale SIGINT-/behandelte SIGTERM-
Unterbrechungen in isolierten Elternprozessen und erhaltene Workbytes. Zusätzliche
Fehlerinjektionen um tatsächlich gestartete Prozesse prüfen wiederholte Abbrüche,
frühe und späte Pipefehler sowie fehlgeschlagenes Kill/Wait. Der Testharness sammelt
absichtlich am Produktcleanup gehinderte eigene Kinder selbst ein. Daraus folgt
keine allgemeine Freigabe aller späteren Prozessadapter.
