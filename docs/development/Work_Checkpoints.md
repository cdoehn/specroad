# Dauerhafte Work-Generationen

`specroad.work.checkpoints.CheckpointStore(location, initial)` verbindet eine
vorhandene `WorkDirectory` mit ihrem unabhängig vertrauenswürdigen initialen
`WorkManifest` der Generation 0. Der Konstruktor erzeugt keine Dateien. Ein
Anfangsmanifest aus demselben ungeprüften Work-Root wäre keine unabhängige
Vertrauensbasis. Die Registry und Toolbindung stammen aus diesem Anfangswert.

`publish(manifest)` veröffentlicht zunächst genau diesen Anfangswert, danach
ausschließlich einen unmittelbar folgenden Kandidaten. Das bestehende
`read_work_successor` prüft die unveränderten Eingangs-/Aufgabenbindungen,
monotone Generation, zusätzliche deklarierte Abschlüsse und erhaltene frühere
Objekte. Selbstkonsistente Daten beweisen weiterhin keine Command-Ausführung.

Alle Rohbytes und Manifestsegmente liegen privat und content-addressiert unter
`objects/<sha256>`. Der vollständige Objektbestand jeder Generation hat einen
eigenen gehashten, maximal 64-fach verzweigten Segmentbaum. Er enthält keine
Selbstreferenz. `checkpoints/<sha256>.json` bindet das vollständige Work-Manifest,
den Objektinventarbaum und den vorherigen Checkpoint. Die Formatkennungen
`stored-work-checkpoint-v1` und `work-current-v1` bezeichnen diesen Speicheradapter;
der gespeicherte Work-Datenvertrag bleibt `1.0.0`.

Der Publisher hält den Work-Mutex. Neue Dateien entstehen exklusiv mit 0600;
bestehende identische Dateien werden geprüft und dauerhaft gesichert, andere
Bytes niemals überschrieben. Er verwendet die vorhandenen descriptorrelativen
Primitiven `_write_new` und `replace_bound_image`. Dateien und Elternverzeichnisse
werden synchronisiert. Erst nachdem sämtliche neuen Referenzen erneut aus den
gespeicherten Bytes geprüft wurden, wird `work.json` atomar ersetzt und die
Ersetzung einschließlich beider Verzeichnisse synchronisiert. Die vorherige
Pointerbindung wird unmittelbar vor der Ersetzung nochmals geprüft.

`read()` erfasst ausschließlich den aktuell veröffentlichten Pointer und prüft
die vollständige gehashte Vorgängerfolge bis zum vertrauenswürdigen Anfangswert.
Es lädt nur die jeweiligen Inventare und ihre Bytes; übrig gebliebene, nicht
referenzierte reguläre Teildateien werden nicht als aktuelle Generation behandelt.
Es liefert das letzte vollständige `WorkManifest`, oder `None`, wenn ein bereits
angelegter gebundener Root noch keine Generation veröffentlicht hat. Ein fehlender
Root wird beim Lesen nicht angelegt. Fehlende oder veränderte notwendige Dateien
ergeben `CheckpointStorageError` mit logischem Speicherpfad; Hashes ersetzen
keine Bytes. Vorhandene Work-/Schema-/Pfadsicherheitsfehler bleiben ebenfalls
blockierend.

Dieser Leseweg benutzt `inspect_checkpoint()` und schreibt keine Dateien. Nach
einem abrupten Publisherabbruch kann er unter dem freigewordenen Kernel-Mutex
die tatsächlich veröffentlichte vollständige Generation prüfen, während die
Ownerdatei erhalten bleibt. Weitere Veröffentlichungen bleiben wegen dieser
Ownerdatei gesperrt. Es gibt keine automatische Lockübernahme oder Recovery.

Fehler erhalten frühere Generationen, Objekte und den tatsächlichen Pointer.
Vor seiner Ersetzung bleibt die alte Generation aktuell. Nach einer bereits
erfolgten Ersetzung kann auch bei anschließendem I/O-Fehler die neue vollständige
Generation vorliegen; der Aufrufer muss den realen Stand prüfen. Es gibt keinen
Rollback, keine automatische Wiederholung und keine Cachebereinigung dieser Daten.
Die Tests beenden echte Publisherprozesse vor und nach der Pointerersetzung und
prüfen anschließend die tatsächlich erhaltenen Bytes in einer neuen Runtime.

Der erste Umfang speichert den vorhandenen inerten, vom Aufrufer deklarierten
Work-Plan. Lesen und Veröffentlichung sind noch synchrone Schritte; Objektbytes
und geladene Vorgänger werden im Speicher gehalten. Keine Gesamt-RSS-Grenze,
harte Zeitgrenze oder netzwerkübergreifende Dateisystem-Dauerhaftigkeit wird
behauptet. Die Nachweise gelten für die aktuelle native Linux-Umgebung und deren
Datei-/Verzeichnis-fsync. Tatsächliches Command-Resume, Code 8, operative
Abschlussbeweise, portabler Restore und vollständige Command-Integration folgen
in den jeweiligen Planschritten. Die zugeordneten Requirements bleiben partiell.
