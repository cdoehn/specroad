# Work-Manifest: Datenvertrag

Der öffentliche Einstieg bleibt `specroad.work.manifest`. Die reinen
JSON-/Typprüfungen liegen intern in `_data_contract`, die Registry- und
Quellbindung in `_request_binding`. `_phase` berechnet dieselben Phasen-,
Frontier-, Fortschritts- und Aktionswerte für Erzeuger und Leser. Segmentprüfung,
Objektspeicher und Nachfolgebindung bleiben im Codec. Diese Strukturtrennung
ändert weder Datenformat noch zulässige Zustände oder Seiteneffekte.

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
Objektbytes sind unveränderlich. Der Objektspeicher akzeptiert ein natives
`dict` oder den bereits geprüften unveränderlichen Speicher dieses Codecs.
Auch unreferenzierte Einträge müssen native Bytes unter ihrem tatsächlichen
SHA-256 sein. Beliebige Mappings und Mapping-Proxys werden nicht ausgewertet.
Ungültige Manifestdaten werden mit `WorkManifestError` verworfen.

Die Prüfsummen belegen Datenkonsistenz, keine Herkunft oder Berechtigung.
Insbesondere ist eine Erledigterklärung ein Planerdatum und kein unabhängiger
Nachweis tatsächlich ausgeführter Facharbeit. Der Codec kann weder die
fachliche Vollständigkeit des gelieferten Plans noch die Wahrheit deklarierter
Projekt-, Build- oder Snapshotangaben feststellen. Eine neu berechnete,
in sich konsistente Fremddeklaration benötigt vor späterer Ausführung weiterhin
eine extern erwartete Auftragsbindung. Diese Daten erteilen keine
`VerifiedContinuation`-Freigabe und aktivieren keine CLI-Fortsetzung.

`read_work_successor(raw, objects, *, previous, registry, expected_tool_build)`
prüft einen unmittelbaren Nachfolgekandidaten gegen den vom Aufrufer bereits
vertrauenswürdig gebundenen Vorgänger. `previous` darf nicht erst aus demselben
fremden Paket übernommen werden. Work-ID, Command, Argumente, Schreibklasse,
Quellen, Tool, Gesamtplan und ursprüngliche Eingänge müssen gleich bleiben.
Die Generation steigt genau um eins; mindestens eine weitere Erledigterklärung
kommt beim Fortschreiben laufender Arbeit hinzu. Vorherige Erledigtnachweise und sämtliche bisher vorhandenen
Objektbytes müssen unverändert erhalten sein. Ein bloß erneut gehashtes,
in sich gültiges Ersatzpaket erfüllt diese Bindung nicht.

`complete_work_manifest(manifest, outcome, exit_code=...)` ergänzt einen
gesonderten inerten Abschlusskandidaten für Read-only-Arbeit. Jede deklarierte
Einheit muss bereits bestätigt sein, einschließlich expliziter globaler
Restphasen. Die vollständige Ergebnishülle muss zum Commandvertrag, Exit-Code
und Diagnosekatalog passen; unvollständige oder partielle Ergebnisse, externe
unbestätigte Ergebnisreferenzen und Code 8 sind kein Abschluss. Ein vollständiges
fachliches Fehlerergebnis bleibt `failed` mit seinem ursprünglichen Code,
während der technische Arbeitszustand `completed` lautet.

Der Abschluss erhöht die Generation um eins, bindet ausdrücklich die
Vorgängergeneration und deren Checkpointhash und erhält alle bisherigen
Einheiten und Bytes. `result_parts` bindet die vollständige Ergebnishülle,
`diagnostic_parts` sämtliche enthaltenen Diagnosen in ihrer gespeicherten
Reihenfolge. Diese gebundene Schlussreduktion ist der einzige erlaubte
Nachfolger ohne zusätzliche Erledigterklärung; leere laufende Generationen
bleiben verboten. `completed` hat keine weitere Folgegeneration.

Der allgemeine Codec prüft Daten und den vom vertrauenswürdigen Planer
deklarierten Umfang. Er beweist weiterhin weder tatsächliche Ausführung noch
die Vollständigkeit eines beliebigen Fachplans. Die ausführbare geschlossene
Read-only-Anbindung in `work.finalization` prüft dafür zusätzlich den bekannten
Core-Plan und dessen gespeichertes Handlerergebnis. Normative Writes und
semantische Erfolgsreceipts werden durch den Datenabschluss nicht freigegeben.

Beim Restore gelten zusätzlich die Kontrollinvarianten des typisierten
`CommandResult`: Eine vollständige Inline-Hülle darf keine reservierten
Teilumfangs-, externen Liefer- oder Fortsetzungsfelder in `summary` einschleusen.
Ein `failure_kind` gehört ausschließlich zu einem Fehlerstatus. Andere
zulässige Commanddetails bleiben erhalten. Diese Prüfung ergänzt das reine
Feldschema; selbst neue gültige Hashes machen eine widersprüchliche Hülle nicht
zu einem Vollabschluss oder einer Code-8-Freigabe. Gehashte Diagnoseteile müssen
weiterhin genau sämtliche Diagnosen des vollständigen Ergebnisses enthalten.

Der Leser weist außerdem wiederholte Segmentreferenzen vor erneuter Expansion
ab. Restaufgaben werden als kanonische JSON-Werte verglichen, damit etwa
`true` keinen numerischen Bereichswert `1` ersetzen kann. Erledigtnachweise
folgen der ursprünglichen Aufgabenreihenfolge. Fremde Pythonwerte werden vor
eigenen Hash-, Vergleichs-, Mapping- oder Serialisierungshooks abgewiesen.
Die Typzulassung vergleicht Identitäten; fremde Metaklassen gelangen auch bei
verschachtelten JSON-Werten nicht in Typvergleiche des gemeinsamen Encoders.
Die Registry bleibt vertrauenswürdiger Anwendungscode, keine Python-Sandbox.

Die 43 neuen Verhaltensfälle prüfen echte temporäre Eingangsbytes, Roundtrips,
stabile Identität und vollständige Aufteilungen, Segmentbäume bis 4.097 Einheiten,
fehlende oder veränderte Daten, lokale Pfadgrenzen sowie ausbleibende
Handleraufrufe und Dateiänderungen. Entropie- und Erledigtfixtures sind als
solche gekennzeichnet. Bisherige Commandbeschreibungen bleiben unverändert.

67 zusätzliche R-Fälle prüfen diese Bindungs- und Fremddatengrenzen, darunter
gültig neu gehashte Ersatzaufträge, verlorene oder umgeschriebene Nachweise,
Generationssprünge und einen vielfach geteilten Segmentbaum. Alle 43 W-Fälle
bleiben unverändert. JSON-Strings mit codeähnlichem Inhalt bleiben reine Werte;
kein Parser lädt daraus Module oder führt diese Strings aus.

Work-Root und Locks (6.j),
konsistente Snapshotaufnahme (6.k), dauerhafte atomare Veröffentlichung (6.l),
tatsächliche Wiederaufnahme (6.m) und Ausführungs-/Abschlussnachweise (6.n/6.o)
bleiben eigene Schritte. Es wird kein veröffentlichter Checkpoint, Exitcode 8,
persistenter Wiederanlauf oder vollständiger Requirementabschluss behauptet.
