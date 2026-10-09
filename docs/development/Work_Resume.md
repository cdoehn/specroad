# Geprüfte Read-only-Fortsetzung

`specroad.work.resume.prepare_read_only_work(request)` erzeugt einen gebundenen
Plan für genau einen vollständigen eingebauten Bootstrap-Handler. Der erste
Umfang unterstützt `help`, `version`, `command.describe`, `capabilities`,
`schema.list` und `schema.show`, jeweils ohne Optionsüberschreibungen. Andere
Commands, externe Eingänge und beliebige deklarierte Einheiten werden nicht
automatisch zu ausführbarer Arbeit.

Die laufende Distribution muss eine aufgezeichnete Buildidentität besitzen.
Ein unversiegelter Entwicklungsbaum erfindet keinen kompatiblen Hash. Für eine
portable Entwicklungsdistribution dient der bestehende Builder
`tools/build_core.py --output <neues externes Verzeichnis>`. Gleiche gebaute
Bytes können über den Modulbaum oder die Zipapp an einem anderen Pfad laufen.
Buildgleichheit ist eine Kompatibilitätsbindung, keine Releasefreigabe.

Der Aufrufer hält das unabhängig vertrauenswürdige Anfangsmanifest, richtet
`WorkDirectory` mit den aktuellen geschützten Roots ein und veröffentlicht
Generation 0 über `CheckpointStore`. Eine bloße selbstkonsistente Anfangsdatei
aus demselben ungeprüften Work-Verzeichnis ersetzt diese Vertrauensbasis nicht.

`resume_read_only_work(store, cwd=...)` prüft die aktuelle Runtime, den Build,
den gespeicherten Datenvertrag und den vollständigen aktuellen Checkpoint.
Anschließend bleibt ein Work-Lock über erneutes Lesen, aktuelle Kontextprüfung,
echte Command-Ausführung und dauerhafte Speicherung der Ergebnisbytes gehalten.
Die neue interne Core-Transformation des Stores verwendet unverändert dessen
bisherige atomare Veröffentlichung. Fehler erhalten den realen Speicherzustand.

Die Ausführung benutzt die frisch erzeugte eingebaute Registry und den normalen
strukturierten Command-Einstieg. Gespeicherte Callables gibt es nicht; eine früher
am Datenmanifest verwendete Registry kann keinen anderen Handler einschleusen.
Die vollständige JSON-Ergebnishülle wird zusammen mit Command, Argumenten,
Einheit, Build und tatsächlichem Exit-Code als Completion-Evidence gespeichert.
Ein nicht vollständig ausgeführter Handler erzeugt keine bestätigte Einheit;
sein tatsächlicher Fehlercode bleibt am `WorkResumeError` erhalten.

Ein erneuter Aufruf prüft bereits gespeicherte Completion-Bytes, deren Bindung
und Ergebnisschema und liefert sie ohne erneute Handlerausführung. Auch dabei
werden Runtime, geschützte Roots, Work-Root und aktueller Berechtigungskontext
neu geprüft. Ein vorhandener verwaister Work-Owner wird nicht übernommen.

`ReadOnlyResumeStep` enthält das bestätigte Manifest, unveränderliche
`outcome_bytes`, `command_exit_code` und `executed`. `as_dict()` liefert eine
abgetrennte maschinenlesbare Projektion. Der Work-Zustand bleibt `running` mit
`next_action.operation=finalize_declared_work`; der vollständige Abschluss des
Work-Protokolls gehört zum folgenden Closure-Schritt. Die Ergebnisbytes des
ausgeführten Handlers sind bereits vollständig gespeichert.

Dies ist zunächst eine Python-Einbettung des Resume-Ausführungswegs. Die CLI-
Registry und ihre Angaben zur automatischen Fortsetzung bleiben beim bisherigen
Umfang. Code 8, automatische Budgetunterbrechung und allgemeine CLI-Anbindung
werden hier nicht freigegeben. Normative Actors, Request-IDs, Zielbasisprüfungen,
mehrteilige Fachpläne und die vollständige Work-Abschlussintegration bleiben
offen; die betreffenden Requirementstatus werden nicht als erfüllt markiert.

Die Verhaltensnachweise verwenden neben expliziten In-process-Buildfixtures
wirklich gebaute Modul-/Zipapp-Distributionen in unabhängigen isolierten
Prozessen. Runtime-, Work- und geschützte Rootpfade werden zwischen Aufrufen
verschoben. Ein solcher Rename erhält die geprüfte Dateisystemidentität;
Kopieren/Restore auf andere Inodes folgt dem späteren Restore-Vertrag.
