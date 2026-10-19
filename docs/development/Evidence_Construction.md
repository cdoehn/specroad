# Immutable Evidence: Konstruktor (12.d.W/R)

`specroad.verification.prepare_evidence_record` erzeugt einen vollständigen,
unveränderbaren `RecordArtifact` in einem Schritt mit `evidence_state=recorded`,
`maturity=approved` und Revision 1. Ein veränderbarer Evidence-Draft entsteht
dabei nicht. Diese Kombination ist der Aufzeichnungszustand und keine
menschliche Freigabe oder bestandene Verifikation.

Die API erhält eine nichtleere Liste nativer Requirement-Subjects, einen
`VerificationContract` und gegebenenfalls den `VerificationTest` des konkreten
Checks. Revision, Vollhash und `verification_context_hash-v1` werden aus den
jeweiligen Artefaktbytes berechnet. Subject-IDs müssen im Contract und im
übergebenen aktuellen Identitätsinventar enthalten sein. Der ausgewählte Check
und dessen optionaler Test müssen exakt übereinstimmen. Die Evidence bindet nur
die ausdrücklich übergebenen Requirements, zusätzlich den Contract und Test;
weitere Contract-Subjects werden nicht automatisch aufgenommen.

Alle Messdaten sind explizite Schlüsselwortargumente: `title`, `result`,
`produced_at`, `producer`, `tool`, `environment`, `origin`, `run_context` sowie
Audit-`actor` und `planned_at`. `run_context` enthält den gelieferten geprüften
Gegenstand, Produktstandhash, bereits im Producer-Namensraum qualifizierten
Laufbezeichner, Check und optionalen Test. Der Konstruktor verändert diese Werte
nicht und behauptet keinen externen Testlauf aufgrund gelieferter Metadaten.
Testpfade, Oracles und Umgebungsdaten werden nicht ausgeführt oder als
Dateizugriff interpretiert.

Seit `12.d.R` bildet `run_context=None` zusammen mit einem ausdrücklich
übergebenen, nichtleeren `unbound_reason` unbekannte Herkunft ab. Der Grund wird
inhaltlich unverändert übernommen; alleiniger Leerraum genügt nicht.
Unvollständige Run-Objekte bleiben Fehler und werden weder vervollständigt noch
automatisch in `None` umgewandelt. Ein vollständiger Run und ein gleichzeitiger
Unbound-Grund widersprechen sich und werden zurückgewiesen.

Bei unbekanntem Lauf wird kein Check oder Test aus den Contract-Slots ausgewählt.
Ein ausdrücklich übergebener Test muss dennoch im Contract vorkommen und wird
mit seinen tatsächlichen Hashes gebunden. Unbekannte Angaben werden nicht aus
Git, Uhrzeit, Modellwurzel oder anderen Dateien ergänzt. Auch ein gespeichertes
`result=passed` wird damit nicht zum Nachweis eines aktuellen Pflichtlaufs.

Die `configuration_policy` stammt aus dem Contract. `configuration` ist eine
explizite `EffectiveConfiguration`; bei `bound` ist sie erforderlich. Ein
ausdrücklich unabhängiger Contract erlaubt `None`. Eine mitgelieferte
Konfiguration bleibt auch dann mit ihrem tatsächlichen Hash protokolliert.
Die API bewertet weder Konfigurationsanwendbarkeit noch die projektweite
Pflichtmenge oder maßgebliche Läufe.

Producer und Audit-Actor bleiben getrennte explizite Eingaben. KI-Herkunft wird
nicht in einen menschlichen Actor umgeschrieben. Die bestehenden Authoring-
und Review-Gates gelten weiterhin: Eine KI darf mit einem konstruierten
`recorded`/`approved`-Wert weder direkt schreiben noch einen Human-Review
erteilen. Eine Proposal-Route ist ebenfalls keine unmittelbare Schreibfreigabe.

`allocation` ist eine neue `IdentityAllocation` aus dem bestehenden
`allocate_artifact_identity('evidence', inventory)`. Aktuelle, archivierte und
reservierte IDs bleiben gesperrt. Der Aufrufer verwendet das zurückgegebene
Inventar für die nächste Messung; eine neue Messung erhält eine neue ID.
Identische Konstruktion mit derselben Reservierung und denselben Daten ergibt
dieselben Bytes. Sie ist kein Nachweis eines dauerhaft gespeicherten Requests
und erlaubt keine Änderung eines vorhandenen Nachweises.

Vorhandene Evidence bleibt auch bei später bekannt gewordener Herkunft
unverändert. Für einen ergänzten Nachweis ist eine neue ID erforderlich; der
spätere Erfassungsadapter muss außerdem den Herkunftsverweis erhalten. Generische
Updates, Lifecycle-Änderungen und Formatierung sind für recorded Evidence
weiterhin gesperrt. Die Konstruktion prüft Reservierungen erneut und weist eine
inzwischen aktuelle oder archivierte Evidence-ID zurück.

Dieser Baustein schreibt keine Dateien und erteilt keine Schreibberechtigung.
Die native Speicherung folgt in `12.e`: Dort werden Reservierung und tatsächliche
Inventare unter dem gemeinsamen Writer-Lock geprüft, Berechtigungen und
widersprechende Laufbindungen kontrolliert, Attachments gebunden und der
Nachweis atomar veröffentlicht. Persistente identische Wiederholungen müssen
über den bestehenden Idempotenzvertrag zum ursprünglichen Nachweis führen.
Importadapter und die vollständige Ergebnisaggregation folgen ihren eigenen
Planschritten. Die Requirement-Nachweise bleiben deshalb Teilnachweise.
