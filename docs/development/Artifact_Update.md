# Nativer Artefakt-Updatedienst

`specroad.authoring.update` verbindet RFC-6902-Patches und geordnete
Feldoptionen mit dem bestehenden vollständigen Change-Plan-, Lifecycle- und
Transaktionspfad. Der Dienst schreibt echte Projektdateien. Er ist eine
Einbettungsschnittstelle; die öffentliche CLI-/Dry-run-/stdout-Anbindung und
eine vollständige Produktionsmodellbeladung sind damit noch nicht vorhanden.

`normalize_artifact_update_input(artifact, ...)` erhält das ursprüngliche
Artefakt und genau eine Eingabeform: `patch` als RFC-6902-Array oder `options`
als geordnete Paare `('--set', '/pointer=JSON')` und `('--unset', '/pointer')`.
`read_artifact_update_input(artifact, input=...)` liest ein solches Patch-Array
aus einer ausdrücklich genannten Datei; nur `input='-'` liest binäres stdin.
Dateiinhalte bleiben Daten. Es gibt keine implizite Eingabequelle, Typkonversion
oder Erzeugung fehlender Elternobjekte.

Mindestens `expected_revision` oder `expected_sha256` ist ausdrücklich
erforderlich. Der Hash bezieht sich auf das kanonische vollständige Artefakt.
Sind beide vorhanden, müssen beide passen. Explizites `None` gilt als ungültiger
Wert. Die Eingabeschnittstelle prüft die Form und geschützte Felder; der native
Planer prüft die tatsächlichen Vorbedingungen und den vollständigen Zielzustand.
Die Eingabe allein ist weder eine Live-Prüfung noch eine Schreibberechtigung.

Das Ergebnis der Eingabeaufbereitung ist ein unveränderlich besessener
`ChangeOperation`. Für einen erneuten Aufruf muss genau dieser ursprüngliche
Vorgang erhalten bleiben. Erneutes Übersetzen von Feldoptionen gegen ein später
verändertes Artefakt kann beispielsweise aus `add` ein `replace` machen und ist
kein Nachweis desselben historischen Auftrags.

`update_artifact(model, operation, ...)` verlangt einen vollständigen
`TargetModel`, eine `PublicationAuthority` und ausdrückliche Werte für `actor`,
`planned_at`, `change_plan_id` sowie `transaction_id`. Der Host verantwortet
Modell-/Historienbeladung und seine Berechtigungsprüfung. `request_id` ist für
Human und Tool optional, für CI Pflicht; direkte AI-Writes sind ausgeschlossen.
`gates`, `strict` und `package_files` entsprechen dem nativen Schreibpfad.
Fehlende fachliche Prüfdienste verhindern die Veröffentlichung.

Der Dienst prüft einen bestätigten Request vor neuer Planung und wiederholt
die Prüfung unter dem echten Writer-Lock. Er verwendet anschließend den
vorhandenen Planer einschließlich Lifecycle und Metadaten, Live-Prüfung,
Journal, Staging, atomarem Dateiaustausch, Abschlussbelegen und Cleanup.
Sprach-, Normativitäts- und Textänderungen erhalten dieselbe Behandlung als
Fachinhalt. Mehrere Feldänderungen in einem Update erhöhen die Revision einmal;
Identität und Erstellungsmetadaten bleiben erhalten.

Bei einem No-op wird das unveränderte Ergebnis unter dem nativen Lock samt
Hostberechtigung und aktuellen Dateibindungen erneut geprüft. Es entstehen
keine neuen Artefaktbytes, Revisionen, Journale oder Receipts. Die zeitweilige
Schreibsperre wird regulär entfernt. Ein fehlender Receipt reserviert keine
Request-ID. Fehler beim Schreiben behalten ihren nativen tatsächlichen
Schreibstatus und vorhandene Recovery-Belege; der Dienst wiederholt oder
repariert eine fehlgeschlagene Veröffentlichung nicht automatisch.

Das Ergebnisobjekt trägt `format_version: 1.0.0`, `command_id: artifact.update`,
`artifact_id`, `no_change`, `write_state`, `replayed` und `completion`.
Ein No-op hat `no_change: true`, `write_state: not_committed`, `completion: null`.
Ein tatsächlicher oder historisch bestätigter Abschluss enthält die native
`completion`; Commit und Cleanup bleiben getrennt ausgewiesen. Ein Replay
bestätigt ursprüngliche Transaktion und Zielwurzel, nicht den heutigen Zustand.
Der Dienst erfindet daraus keine aktuelle Artefaktrevision.

Die Nachweise verwenden einen realen lokalen Dateibaum mit vollständigem
geladenem Goal-/Requirement-Modell. Sie bestätigen keine allgemeine
Produktionsbeladung, vollständige Kontextbindungsabnahme oder Plattformfreigabe.
SR-REQ-0232 und SR-REQ-0657 bleiben partiell.

## Bindung der Eingabe und Fehlerverhalten

Beim Lesen eines gespeicherten Patches werden Ziel-ID und ausdrückliche
Vorbedingungen vor dem ersten Eingaberead in einem eigenen `ChangeOperation`
festgehalten. Ändert der Aufrufer währenddessen sein Artefaktobjekt, etwa in
einem Stream-Callback, bindet das den begonnenen Auftrag nicht an ein anderes
Ziel. Der Patch wird über denselben nativen Operationsprüfer ergänzt.

Ohne ausdrücklich übergebenen Lifecycle-Prüfdienst verbindet der Adapter den
vorhandenen Lifecycle-Kern über `changes.update_lifecycle_gate` mit der
vollständigen Modellprüfung. Dieser Prüfer besitzt ursprüngliches Modell,
Operation und Auditparameter. Bei jedem Aufruf berechnet er deren Ergebnis
erneut und vergleicht es mit dem vollständigen vorgelegten Zielmodell.
Einziger abgedeckter Nicht-Draft-Prüfling ist dabei das aktualisierte Artefakt
im Zustand `proposed`. Andere Nicht-Draft-Artefakte und andere Zielzustände
benötigen weiterhin einen ausdrücklich bereitgestellten echten Fachdienst.
Eine Host-Prüfung wird weder ersetzt noch ihre Ablehnung übergangen. Der
gebundene Prüfer bescheinigt keine bestehende Freigabe oder Historienvollständigkeit.

Die R-Abnahme umfasst echte Änderungen strukturell gespeicherter
Approved-Requirements: Sprache, Normativität, Text und das Entfernen einer nur
für Approved erforderlichen Rationale ergeben `proposed` mit einer neuen
Revision. Das begründet keine historische Freigabe dieser Testartefakte.
No-ops in Draft und Proposed erhalten auch nichtkanonische Originalbytes und
Dateimodi. Sie benötigen weiterhin Hostberechtigung und passende Live-Dateien.

Veraltete Vorbedingungen, geschützte Identitäts-/Zustandsfelder und nachträglich
manipulierte Operationscontainer bleiben abgewiesen. Ein vorhandener Writer
oder ein abweichender physischer Ausgangsstand verhindert den Write.
Injizierte Fehler vor und nach dem realen Dateiaustausch erhalten jeweils die
tatsächlich vorhandenen alten oder neuen Bytes sowie das native Journal.
Ein blinder Wiederholungsversuch wird vor weiterer Veröffentlichung blockiert.
Der Dienst meldet daraus keinen sicheren Nicht-Write oder abgeschlossenen Commit.
