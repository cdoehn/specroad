# Lebensdauer ausdrücklich gestarteter Kindprozesse

`specroad.runtime.children.run_child(arguments, cwd=..., environment=...,
input_bytes=None)` ist eine synchrone Host-API für einen ausdrücklich erlaubten,
vertrauenswürdigen direkten Kindprozess. Die Argumente sind ein Tupel aus Strings
mit absolutem Executablepfad; Arbeitsverzeichnis und vollständige Umgebung werden
ausdrücklich als String beziehungsweise Dictionary übergeben. Der Adapter löst
keinen Befehl aus Work- oder Projektinhalt auf. Welche Distribution und Operation
zulässig sind, muss der aufrufende vertrauenswürdige Fachadapter separat prüfen.

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

Bei einer im Aufruf behandelten Ausnahme wird ein noch laufendes direktes Kind
beendet und eingesammelt, bevor die Ausnahme weitergereicht wird. Eigene Pipes
werden geschlossen. Diese Bereinigung besitzt keine Work-, Snapshot-, Journal-
oder Ergebnisdateien und löscht keine davon. Native Start-/I/O-Fehler werden
weitergereicht; ein fehlgeschlagener Start wird nicht zu Erfolg oder Code 8 erklärt.

Der erste Ausschnitt verarbeitet vollständige Ein-/Ausgaben im Speicher auf
POSIX-Systemen. Er ist für vertrauenswürdige direkte Kinder vorgesehen, die keine
eigenständigen Nachkommen oder Daemons hinterlassen. Er ist keine Sandbox für
beliebige Programme. SIGKILL, OOM oder anderer unbehandelter Hostverlust kann
Python-Cleanup verhindern. Große fortsetzbare Streamprotokolle, automatische
Verbrauchsintegration, konkrete Git-/Analyzer-Adapter und umfassende Behandlung
wiederholter Abbruch-/Cleanupfehler bleiben gesonderte Schritte.

Die bisherigen Work-Abläufe laufen weiterhin synchron im Core. Der neue Adapter
startet beim Import nichts und ist derzeit nicht aus Workdaten oder einem neuen
CLI-Befehl erreichbar. Die Nachweise umfassen echte direkte Prozesse, Pipes,
Returncodes, native `waitpid`-Eigentumsprüfung, eine reale Unterbrechung in einem
isolierten Elternprozess und erhaltene Workbytes. Daraus folgt keine allgemeine
Freigabe aller späteren Prozessadapter.
