# Work-Manifest: Datenvertrag

`specroad.work.manifest` stellt den ersten geschlossenen `work-v1`-Codec bereit.
Er erstellt und prüft reine Datenkandidaten. Ein vertrauenswürdiger Aufrufer
liefert die registrierte Read-only-Anfrage, die explizite Tool-Bindung, sämtliche
Eingangsbytes und den vollständigen endlichen Einheitenplan. Der Codec ruft
keinen Command-Handler auf und führt keine Dateioperationen aus.

`create_work_manifest(registry, request, *, tool_build, source_bindings,
inputs, units)` bindet einen vorhandenen `CommandRequest` über die Registry.
Dieser erste Umfang akzeptiert keine Optionen; deren fachliche Normalisierung
gehört zum jeweiligen späteren Planer. Eingänge besitzen `root_id`, relativen
`path` und originale `raw`-Bytes. Einheiten besitzen einen eindeutigen `key`,
eine `phase` und ein JSON-Objekt `range`. Die Bindung verwendet Inhaltshashes
und logische Rootkennungen, keine absoluten Laufzeitpfade.

Die Work-ID entsteht einmal aus 128 Bit Betriebssystementropie. Die Identität
einer Einheit bindet Command, Argumente, Quellen, Eingangsmanifest, Phase und
deklarierten Bereich. Aufgaben-, Eingangs-, Erledigt- und Restmanifest bestehen
aus versionierten, gehashten Segmentbäumen mit höchstens 64 Einträgen oder
Kindreferenzen je Segment. Referenzen enthalten ID, Bytezahl, Hash und Anzahl.
Die Begrenzung betrifft Eintragszahlen; einzelne Eingänge und JSON-Werte sowie
der gesamte derzeitige In-Memory-Objektbestand sind noch nicht größenbegrenzt.

`partition_work_manifest(manifest, completions)` nimmt zusätzliche
Erledigterklärungen als Zuordnung bekannter Einheiten-IDs zu JSON-Objektbytes
entgegen. Es erzeugt einen neuen Kandidaten mit höherer Generation. Der
vollständige Plan, die Work-ID, Eingangsbindung und sämtliche bisherigen
Objektbytes bleiben erhalten. Erledigte und offene Einheiten bilden weiterhin
genau den ursprünglichen Plan. Doppelte, unbekannte oder leere Ergänzungen
werden abgewiesen. Ein vollständig aufgeteilter Plan bleibt `running` mit
`finalize_declared_work`; Ergebnislieferung und fachlicher Abschluss werden
damit noch nicht behauptet.

`read_work_manifest(raw, objects, *, registry, expected_tool_build)` prüft
geschlossene JSON-Felder, Versionen, registrierte Commandklasse, explizit
erwartete Tool-Bindung, alle referenzierten Bytes und Hashes sowie die
vollständige Partition. Fehlende Originalbytes werden nicht aus Hashes
rekonstruiert. Werte aus `as_dict()` und `entries(kind)` sind abgelöste Kopien;
Objektbytes sind unveränderlich. Ungültige Manifestdaten werden verworfen.

Die Prüfsummen belegen Datenkonsistenz, keine Herkunft oder Berechtigung.
Insbesondere ist eine Erledigterklärung ein Planerdatum und kein unabhängiger
Nachweis tatsächlich ausgeführter Facharbeit. Der Codec kann weder die
fachliche Vollständigkeit des gelieferten Plans noch die Wahrheit deklarierter
Projekt-, Build- oder Snapshotangaben feststellen. Eine neu berechnete,
in sich konsistente Fremddeklaration benötigt vor späterer Ausführung weiterhin
eine extern erwartete Auftragsbindung. Diese Daten erteilen keine
`VerifiedContinuation`-Freigabe und aktivieren keine CLI-Fortsetzung.

Die 43 neuen Verhaltensfälle prüfen echte temporäre Eingangsbytes, Roundtrips,
stabile Identität und vollständige Aufteilungen, Segmentbäume bis 4.097 Einheiten,
fehlende oder veränderte Daten, lokale Pfadgrenzen sowie ausbleibende
Handleraufrufe und Dateiänderungen. Entropie- und Erledigtfixtures sind als
solche gekennzeichnet. Bisherige Commandbeschreibungen bleiben unverändert.

Strengere Fremddaten-/Commandbindung folgt in 6.i.R. Work-Root und Locks (6.j),
konsistente Snapshotaufnahme (6.k), dauerhafte atomare Veröffentlichung (6.l),
tatsächliche Wiederaufnahme (6.m) und Ausführungs-/Abschlussnachweise (6.n/6.o)
bleiben eigene Schritte. Es wird kein veröffentlichter Checkpoint, Exitcode 8,
persistenter Wiederanlauf oder vollständiger Requirementabschluss behauptet.
