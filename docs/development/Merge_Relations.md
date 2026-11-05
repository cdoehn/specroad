# Lesende Relationskandidaten

`specroad.merge.merge_relations(sources, history=...)` verarbeitet drei
nativ qualifizierte `MergeSources`. Die Herkunftshülle nach Spezifikation
10.15.3 bindet `source_bindings_sha256=sources.sha256` und die ausdrücklichen
Ursprungsbeobachtungen des Aufrufers. Der Aufrufer muss sie aus seiner
wirklichen Ancestry/Provenienz beziehen; IDs oder gleiche Bytes reichen nicht.
`inspect_merge_identities` prüft denselben Herkunftsvertrag für Artefakte,
Relationen, Konfiguration und normative versionierte Ressourcen.

Das Ergebnis enthält ursprüngliche Quellbindungen, den Hash der kanonisch
geordneten Herkunftseingaben und alle Konfliktbeobachtungen. Nur ohne Konflikte
ist `result.relations` zugänglich: eine nach relation_id sortierte Liste aus
`owner_id` und `relation`. Eingabe- und Ausgabekopien sind unabhängig.
`result.ready` und `result.write_authorized` sind immer false; ein boolescher
Wahrheitswert ist kein Freigabeweg. Es wird keine Datei geschrieben.

Der R-Zielstand ergänzt die optionalen Listen `removed_ours` und
`removed_theirs`. Sie benennen bewusst fehlende Base-Relations-IDs auf der
jeweiligen Seite. Abwesenheit allein erlaubt keine Entfernung; Ändern gegen
Entfernen bleibt Konflikt. Herkunftskollisionen, Besitzerwechsel, geänderte
Erstellungsmetadaten und geschützte Originalrelationen werden nicht repariert
oder umbenannt. Inhalte werden erst nach den Identitätsprüfungen verglichen.

Diese API ist ein interner lesender M17-Baustein. Lifecycle, vollständiger
Originalbyteschutz, Metadaten K.3, Modellinvarianten, persistierte Auflösungen,
öffentliche CLI-Anbindung und Review-/Writerfreigaben bleiben weitere Gates.
Herkunftsbeobachtungen sind keine Signaturen oder erfundenen menschlichen Reviews.
