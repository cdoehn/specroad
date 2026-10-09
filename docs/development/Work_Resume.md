# Geprüfte Fortsetzung und normative Vorprüfung

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
und Ergebnisschema und liefert sie ohne erneute Handlerausführung. Gespeicherte
Exit-Codes und Diagnosen müssen zusätzlich zum aktuellen Handlervertrag passen.
Unpassende Schema-/Algorithmusverträge und manipulierte vollständige Ergebnisse
werden vor einer schreibenden Work-Lease als Konflikt mit Code 6 abgewiesen.
Die laufende Buildidentität wird auch vor der Bestätigung erneut geprüft. Dabei
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
werden hier nicht freigegeben. Normative Ausführung, mehrteilige Fachpläne und
die vollständige Work-Abschlussintegration bleiben offen; die betreffenden
Requirementstatus werden nicht als erfüllt markiert.

Die Verhaltensnachweise verwenden neben expliziten In-process-Buildfixtures
wirklich gebaute Modul-/Zipapp-Distributionen in unabhängigen isolierten
Prozessen. Runtime-, Work- und geschützte Rootpfade werden zwischen Aufrufen
verschoben. Ein solcher Rename erhält die geprüfte Dateisystemidentität;
Kopieren/Restore auf andere Inodes folgt dem späteren Restore-Vertrag.

## Ursprünglichen normativen Plan erneut prüfen

`specroad.work.manifest.create_normative_work_manifest(...)` bindet die
ursprünglichen `ChangePlan.source_bytes` samt Plan-ID, semantischem Planhash,
Actor, kanonischer Request-ID und fachlichem Operationshash. Diese Bindungen
gehen in die Einheitenidentität ein und bleiben in jedem Nachfolger erhalten.
Der vertrauenswürdige Host liefert seinen aktuellen registrierten `change.apply`-
Vertrag; die eingebaute CLI erhält dadurch keinen Platzhalter-Handler.
Unterstützt wird hier der geschlossene Projektumfang mit den drei expliziten
Authoringoptionen `--actor-type`, `--actor-id` und `--request-id`.

`specroad.work.resume_checks.prepare_normative_resume(store, registry=...,
model=..., policy=..., actor=..., request_id=...)` liest den vollständigen
Checkpoint unter dem nativen Work-Mutex und prüft ihn gegen den aktuellen
Build und Registryvertrag. Actor, Request-ID und Projektidentität müssen den
gespeicherten Werten entsprechen. Eine aktuelle Projektlokalisierung muss
ausdrücklich zu den geschützten Roots des Work-Verzeichnisses gehören.

Die vorhandene `prepare_publication_check` prüft danach den originalen Plan
gegen das aktuelle Modell und tatsächliche Projektbytes, Namen, Konfiguration
und Schreibrechte. Eine veränderte Zielbasis ist Code 6; ursprüngliche Planbytes,
Request und Work-Daten bleiben erhalten. Es gibt kein Rebase und keine
Probe-Schreibzugriffe. Ein Verschieben des Projekts mit einer neuen geprüften
Rootbindung ist zulässig, solange Identität und Basis weiterhin passen.

`NormativeResumeCheck` liefert den originalen Plan, das bestätigte Datenmanifest
und die aktuelle Vorprüfung. Die Projektion weist `write_authorized=false`,
`final_locked_check_required=true`, `normative_writes=0` und
`checkpoint_changed=false` aus. Dieser Aufruf führt keinen normativen Handler
aus und verändert weder Projekt noch Work-Verzeichnis. Die abschließende
Autorisierung, erneute Rechte-/Basisprüfung unter dem echten Projekt-Writer-Lock
und dauerhafte Veröffentlichung bleiben beim bestehenden Apply-Pfad. Ein
gespeicherter Actor ist keine Authentifizierung oder menschliche Freigabe.

Die interne Datenrestauration liegt getrennt in `_resume_restore`: Sie prüft
die unabhängige Anfangsbindung und liest den vollständigen aktuellen Checkpoint
gegen Registry und Build. Erst danach folgt die eigene aktuelle Actor-/Request-/
Projekt-, Zielbasis- und Rechteprüfung. Der aufrufende Resume-Pfad hält dabei
unverändert denselben Work-Mutex bis zur abschließenden Kontrolllesung. Diese
Trennung erweitert weder den unterstützten Befehlsumfang noch Schreibrechte.
