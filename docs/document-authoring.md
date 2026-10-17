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
kann diese Prüfungen nicht ersetzen. Bei `document.create` und `section.add`
deckt der eingebaute Dokumentdienst Modelle ab, deren Dokumentfachobjekte
ausschließlich Dokumente und Abschnitte sind. Dort wird für Content Blocks und
Views ein tatsächlich implementierter, expliziter `document_model`-Dienst benötigt;
andere erforderliche Fachprüfungen,
etwa Lifecycle oder externe Ressourcen, bleiben ebenfalls verbindlich.

Die API registriert noch keinen CLI-Writer und übernimmt keine Projekt- oder
Historieninventur.
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

`preview_block_add` ergänzt einen vorbereiteten Content Block und seine
`contains`-Relation zu einem Abschnitt. Referenzierende Blöcke enthalten die
vorbereiteten nativen Referenzrelationen bereits in ihren Eingabefeldern.
`preview_block_update` akzeptiert eine mit `normalize_artifact_update_input`
vorbereitete, ausdrücklich revisions- beziehungsweise hashgebundene Operation.
`preview_block_remove` verwendet entsprechend `normalize_retire_input`.
Der gespeicherte `command_id` lautet `block.add`, `block.update` oder `block.remove`.

`preview_section_remove` erhält die Retire-Operation des Abschnitts. Ein leerer
Abschnitt benötigt keine weitere Strategie. `cascade=True` verlangt unter
`child_retirements` die vollständigen bewachten Retire-Operationen der Nachfahren
in der nativen Contains-Vorordnung. `move_children_to` bezeichnet einen anderen
aktiven Abschnitt außerhalb des Teilbaums. Für jedes direkte Kind enthält
`child_moves` in Contains-Reihenfolge genau `target`, `relation_identity`,
`position` und `expected_relation_sha256`. Fehlende, zusätzliche oder
widersprüchliche Angaben werden vor Veröffentlichung abgelehnt. Der gespeicherte
Befehl lautet `section.remove`; seine Operationen werden auch beim direkten
Einlesen eines Plans erneut gegen den tatsächlichen Ausgangsgraphen geprüft.

Entfernen bedeutet Retirierung: Artefaktdateien und IDs bleiben erhalten. Auch
ein retirierter Abschnitt behält seine ursprüngliche eingehende Eigentümerkante,
weil der gespeicherte Abschnittsvertrag genau einen Parent verlangt. Die Kaskade
erhält die historischen Contains-Kanten; die Verschiebestrategie ersetzt nur die
ausgehenden Kanten des entfernten Abschnitts und lässt Kindinhalte und Revisionen
unverändert. Neue Relations-IDs werden vom Host vorbereitet; entfernte IDs bleiben
reserviert. Freigegebener Inhalt folgt weiter der nativen Lifecycle-Policy:
Inhaltsänderung wird `proposed`, reine zulässige Retirierung wird `retired`.

Für diese vier Mutationsbefehle umfasst die verpflichtende native Dokumentprüfung
zusätzlich die vorhandenen Prosa-, Referenz-, Query-/Tabellen- und Include-Prüfer.
Ein permissiver Hostdienst kann sie nicht ersetzen. Allgemeine Views, externe
Anhangsressourcen und unveränderte nicht im Plan behandelte Lifecycle-Historie
benötigen weiterhin ihre wirklichen Fachdienste. Ein gespeicherter historischer
Reifegrad allein ist kein historischer Freigabenachweis. `document.create` und
`section.add` behalten ihren oben beschriebenen engeren Dienstumfang.

Mehrere Contains-Vorkommen desselben Blocks innerhalb der Kaskade erzeugen genau
eine Retire-Operation. Ihre Reihenfolge folgt dem ersten Vorkommen in der nativen
Vorordnung; sämtliche historischen Eigentümerkanten bleiben bestehen. Ein weiterer
Contains-Eigentümer außerhalb der Kaskade verhindert die Retirierung dieses
Teilbaums. Jede ursprüngliche Revisions-/Hashvorbedingung wird unverändert geprüft.
Ein I/O-Abbruch während der Veröffentlichung erhält den tatsächlichen Teilzustand
und das Recovery-Journal; ein weiterer Write bleibt bis zur Recovery gesperrt.

Die Komfortfunktionen teilen reine Operationserzeuger für Create-/Contains-Paare,
bewachte Relationsverschiebungen und vorbereitete Einzeloperationen. Die getrennten
Strategie-, Fach- und Lifecycle-Prüfungen sowie der gemeinsame Saved-Plan-Writer
bleiben dafür maßgeblich; die Erzeuger erteilen keine Schreibberechtigung.

`section.move` verwendet ebenfalls die vorhandenen nativen Blockprüfer. Sein
verpflichtendes Dokumentgate bindet zusätzlich den Revisionserhalt: Das
Artefaktinventar bleibt gleich, und außerhalb der tatsächlich geänderten alten
und neuen Relationseigentümer müssen sämtliche Artefaktquellen bytegleich bleiben.
Dadurch bleiben auch nichtkanonische Originalformatierung, referenzierte IDs und
Revisionen erhalten. Verschieben und Umordnen ändern allein die gespeicherten
Contains-Relationen und die nativen Metadaten ihrer betroffenen Eigentümer. Ein
weiterhin erforderlicher Lifecycle-, Evidence- oder Ressourcendienst wird durch
diesen Erhaltsnachweis nicht ersetzt.
