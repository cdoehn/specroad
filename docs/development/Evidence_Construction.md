# Immutable Evidence: Konstruktor (12.d.W)

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
`null` ist im W-Ausschnitt noch nicht unterstützt. Testpfade, Oracles und
Umgebungsdaten werden nicht ausgeführt oder als Dateizugriff interpretiert.

Die `configuration_policy` stammt aus dem Contract. `configuration` ist eine
explizite `EffectiveConfiguration`; bei `bound` ist sie erforderlich. Ein
ausdrücklich unabhängiger Contract erlaubt `None`. Eine mitgelieferte
Konfiguration bleibt auch dann mit ihrem tatsächlichen Hash protokolliert.
Die API bewertet weder Konfigurationsanwendbarkeit noch die projektweite
Pflichtmenge oder maßgebliche Läufe.

`allocation` ist eine neue `IdentityAllocation` aus dem bestehenden
`allocate_artifact_identity('evidence', inventory)`. Aktuelle, archivierte und
reservierte IDs bleiben gesperrt. Der Aufrufer verwendet das zurückgegebene
Inventar für die nächste Messung; eine neue Messung erhält eine neue ID.
Identische Konstruktion mit derselben Reservierung und denselben Daten ergibt
dieselben Bytes. Sie ist kein Nachweis eines dauerhaft gespeicherten Requests
und erlaubt keine Änderung eines vorhandenen Nachweises.

Dieser Baustein schreibt keine Dateien und erteilt keine Schreibberechtigung.
Die native Speicherung folgt in `12.e`: Dort werden Reservierung und tatsächliche
Inventare unter dem gemeinsamen Writer-Lock geprüft, Berechtigungen und
widersprechende Laufbindungen kontrolliert, Attachments gebunden und der
Nachweis atomar veröffentlicht. Persistente identische Wiederholungen müssen
über den bestehenden Idempotenzvertrag zum ursprünglichen Nachweis führen.
Importadapter und die vollständige Ergebnisaggregation folgen ihren eigenen
Planschritten. Die Requirement-Nachweise bleiben deshalb Teilnachweise.
