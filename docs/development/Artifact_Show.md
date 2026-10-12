# Artifact Show

`specroad artifact show <ID>` und der Kurzalias `specroad show <ID>` lesen ein
Artefakt einschließlich seiner berechneten eingehenden und ausgehenden
Beziehungen. `--project <ROOT>` wählt den Projektroot; `--format json` liefert
den bestehenden JSON-Envelope mit dem Resultatschema `artifact-show-v1`.
Die Python-Schnittstelle ist `specroad.query.show_artifact(root, artifact_id)`.

`artifact` enthält das vollständige gespeicherte JSON-Objekt. `incoming` und
`outgoing` sind berechnete Sichten. `source` bezeichnet jeweils das abgefragte
Artefakt, `target` den anderen Endpunkt. `inverse` unterscheidet die Richtung
gegenüber der Speicherung. `stored_source` und das vollständige
`stored_relation` erhalten die normative Quelle, Ziel-ID, Relations-ID und
Relationsmetadaten. Die inverse Sicht von `supersedes` heißt `superseded_by`.
Es wird keine zweite normative Relation gespeichert.

Der bestehende Projekt-Relationsreader liest sämtliche aktuellen Artefaktdateien
unter den konfigurierten Pfaden, einschließlich nur eingehend referenzierender
Quellen. Ein optionaler Python-Indexhinweis ersetzt diese Inventur nicht. Die
Sortierung folgt Relationstyp, Gegenstellen-ID und Relations-ID. Eine unbekannte
ID oder unlesbare Quelle ergibt ein fehlgeschlagenes Result ohne Fachpayload.

`coverage` nennt Quellen- und Relationszahl, Prüfbereich und lokale
`observation_sha256`. Diese bindet die beobachteten Bytes und den Projektroot;
sie ist keine Modellwurzel und keine portable Fachidentität. Gemeinsame
Artefaktfelder, Referenzen und kanonische Relationsspeicherung werden geprüft.
Show erteilt keine vollständige fachliche Validierung oder Freigabe.

Der reguläre Projekt-Lese-Preflight prüft Konfiguration und Betriebszustand vor
dem Modellzugriff und erneut nach dem Lesen. Writer-/Recovery-Metadaten blockieren
konservativ mit dem bestehenden Preflight-Fehlervertrag. Anschließend werden
Inventur und alle gebundenen Artefaktbytes erneut geprüft. Beobachtete Änderungen
verhindern die Ausgabe eines veralteten Fachresultats. Wiederholte Beobachtungen
gewähren keinen atomaren Snapshot gegen nicht kooperierende Schreiber.

Show verändert weder Projekt noch `.specroad/`, erzeugt keinen Cache, fordert
keinen Writer-Lock an und benötigt weder Git noch stdin. Das Ergebnis wird
vollständig im Speicher berechnet. Plattformmatrix, Lastnachweise und vollständige
Work-Engine-Integration bleiben Aufgaben der späteren Produktabnahme.


Die R-Nachweise prüfen vollständige aktuelle Antworten auch mit partiellen,
veralteten oder fremden Indexhinweisen. Entfernte Quellen und umgehängte
Relationen werden aus den aktuellen Dateien bestimmt. Gespeicherte Legacy-IDs
und Relationen von retired-Artefakten bleiben lesbar; Query-Paginationdefaults
beschneiden Show nicht.

Verschwindet bei der abschließenden Prüfung eine zuvor gebundene Quelle oder
Konfiguration, scheitert die Abfrage mit Änderungskonflikt 6. Tatsächliche
Berechtigungs-/I/O-Fehler bleiben Code 5, unsichere Pfade Code 7 und Modellfehler
Code 3. Alle diese Fehler liefern keinen scheinbar vollständigen Fachpayload.
Die Nachweise verändern Quellen gezielt zwischen den Beobachtungen und prüfen
den erhaltenen Dateizustand; Show führt weiterhin keine Reparatur durch.

Die reine Datenprojektion liegt in `_show_projection.py`. Sie übernimmt die
bereits geprüfte Beobachtung und erzeugt die bestehenden Artefakt-, Relations-
und Coveragefelder ohne Datei-, Preflight- oder Renderingzugriff. Die Abfrage
behält Ablauf, Quellenprüfungen, Fehlerklassen und Envelope-Erzeugung bei;
Pretty- und JSON-Ausgabe verwenden weiterhin dasselbe fachliche Resultat.
