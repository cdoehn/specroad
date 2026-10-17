# Dokumente und Abschnitte vorbereiten und schreiben

`specroad.authoring.documents` bietet `preview_document_create`,
`preview_section_add` und `preview_section_move` für einen vollständig gelieferten
`TargetModel`. Die Funktionen liefern den bestehenden Authoring-Preview mit einem
speicherbaren nativen Change Plan. Sie lesen keine Projektdateien, reservieren
keine IDs und schreiben keine Dateien.

Der Host liefert vorbereitete `ArtifactIdentity`-/`RelationIdentity`-Werte,
vollständige aktuelle und historische Modellbindungen, Actor und Zeitpunkt.
Dokument- und Abschnittsfelder werden mit `normalize_artifact_create_input`
vorbereitet. Ein neues Dokument ist leer. Ein neuer Abschnitt wird im selben
Plan durch eine `contains`-Relation an einen Dokument- oder Abschnittsparent
gebunden. Positionen sind native Relationsdaten.

Beim Verschieben liefert der Aufrufer den beobachteten kanonischen Hash der
alten Eigentümerrelation und einen Grund. Der Plan entfernt genau diese Relation
und fügt eine neue `contains`-Relation mit frischer Identität hinzu. Der Abschnitt
selbst und seine Nachfahren werden dadurch nicht aktualisiert. Auch das Umordnen
innerhalb desselben Parents wird gemeinsam geplant; dessen Revision steigt nur
einmal.

Der gespeicherte Plan wird mit
`specroad.authoring.execution.apply_authoring_plan` und dem passenden
`command_id` ausgeführt. Die tatsächliche Veröffentlichung benötigt eine neue
Host-Autorisierung und verwendet den gemeinsamen exklusiven Writer-Lock,
die vollständige Zielprüfung, Journal, Receipts und Readback. Ein bestätigter
Request wird vor neuer Planung oder Lock-Aufnahme anhand seiner ursprünglichen
Completion-Proofs wiedererkannt. Ein Preview erteilt keine Schreibberechtigung.

Rollenprüfung, eindeutiger Abschnittsparent und der native Contains-/Include-Graph
werden für das gesamte gelieferte Zielmodell geprüft. Ein Host-Dokumentdienst
kann diese Prüfungen nicht ersetzen. Der eingebaute Dokumentdienst deckt zunächst
Modelle ab, deren Dokumentfachobjekte ausschließlich Dokumente und Abschnitte
sind. Für Content Blocks und Views wird ein tatsächlich implementierter,
expliziter `document_model`-Dienst benötigt; andere erforderliche Fachprüfungen,
etwa Lifecycle oder externe Ressourcen, bleiben ebenfalls verbindlich.

Die API registriert noch keinen CLI-Writer und übernimmt keine Projekt- oder
Historieninventur. Abschnittsentfernung und Blockauthoring folgen unter 11.i.
Gezielte Entwicklungstests und alternierende Apply-Testhälften sind Teilnachweise.

Fehlerantworten des gemeinsamen `execute_authoring_plan` behalten den tatsächlichen
Dokumentbefehl und die Bindung an den geprüften Plan. Ungültige Parents, Kreise,
veraltete Relationshashes und inzwischen geänderte Quelldateien werden vor der
Veröffentlichung abgelehnt. Eine erfolglose I/O-Operation während der Veröffentlichung
kann hingegen bereits Dateien geändert haben: Der reale Zustand und das native
Recovery-Journal bleiben erhalten. `write_state=unknown` ist kein Rollbacknachweis
und keine Erlaubnis für einen blinden Retry.

Die Komfortfunktionen übersetzen ihre Eingaben ausschließlich in die vorhandenen
typisierten Create-/Relationsoperationen. Diese reine Konstruktion ist von den
verpflichtenden nativen Dokumentprüfungen getrennt. Beide Wege münden weiterhin
in denselben Authoring-Plan und Saved-Plan-Writer.
