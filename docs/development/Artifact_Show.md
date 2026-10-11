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
vollständig im Speicher berechnet. Plattformmatrix, Lastnachweise sowie weitere
Robustheits- und Fehlerfälle folgen der R-Phase und der späteren Produktabnahme.
