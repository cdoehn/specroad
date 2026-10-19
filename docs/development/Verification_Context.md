# Verification-Kontext und fachliche Aktualität

`specroad.verification` stellt die lesende Kontext-API aus 12.c bereit.
`verification_context_projection(subject)` und `verification_context_sha256(subject)`
verwenden lokal geprüfte `DomainArtifact`-Requirements, `VerificationContract`
oder `VerificationTest`. Die Projektion folgt Anhang L und wird mit dem
vorhandenen RFC-8785-Kanonisierer gehasht. Der Algorithmus heißt
`verification_context_hash-v1`; gehasht wird unmittelbar das projizierte
Artefaktobjekt.

Die öffentlichen Funktionen bleiben der gemeinsame Einstieg für Record-,
Import-, Coverage- und Baseline-Verbraucher. Intern bündelt
`_context_subject` die native Subjectprüfung, Projektion, Kontexthashbildung
und Audit-/Kontextbindung. Aktuelles Subject und ausdrücklich übergebener
Contract verwenden dieselbe Projektion. `_context_contract` kapselt die
bestehende Contract-/Prüfschrittbindung; `context` stellt die unveränderten
öffentlichen Wertobjekte und den Aktualitätsbericht bereit. Die fachliche
Integration weiterer Verbraucher erfolgt in deren jeweiligen Planschritten.

Ausgeschlossen sind die obersten Felder `revision`, `created_at`, `created_by`,
`updated_at`, `updated_by`, `maturity`, `implementation_status`,
`verification_plan_status`, `verification_waiver`, `relations` und `tags`.
Die Waiver-Entscheidung gehört zum Workflow. In Provenienzobjekten entfällt
deren reiner Erfassungszeitpunkt `captured_at`; Quelleninhalt, Quellenbindung
und Extensions bleiben erhalten. Die Filterung wird nicht rekursiv auf
gleichnamige Schlüssel in Oracles oder fachlichen Extensions angewendet.
Berechnete Ergebnisse und Laufdaten sind keine zulässigen gespeicherten
Felder dieser Subjecttypen und werden von deren nativen Schemas abgewiesen.

`VerificationContext(subject, configuration=...)` hält den Subject-Snapshot,
seinen ursprünglichen Bytehash, Vollhash, Revision und Kontexthash fest.
Die Konfiguration muss ausdrücklich als `EffectiveConfiguration` oder `None`
übergeben werden. Ihr Hash ist der bestehende Hash des effektiven
Konfigurationskettenmanifests. Er wird zusätzlich zum fachlichen Subjecthash
verglichen. Die reine Projektion entscheidet weder Anwendbarkeit noch
Scopezugehörigkeit.

`assess_verification_context(context, evidence)` nimmt ein lokal geprüftes
`RecordArtifact` vom Typ `evidence`. Dieser Zweiparameteraufruf verlangt explizite
`configuration_policy="bound"` und einen tatsächlichen `configuration_hash`.
Der bestehende Recordvertrag weist `bound` mit fehlendem oder `null`-Hash ab.
Ein ausdrücklich unkonfigurierter aktueller Kontext macht einen gebundenen
Nachweis stale. Ein `independent`-Label im Nachweis allein erteilt keine Ausnahme.

Für eine ausdrückliche Contract-Bindung dient
`assess_verification_context(context, evidence, contract=contract)`. Das Argument
muss ein nativer `VerificationContract` sein. Ein Requirement muss zu dessen
`subjects` gehören; ein Test muss einen passenden Slot haben. Ist das Subject
selbst ein Contract, müssen ID und fachlicher Kontexthash übereinstimmen.
Die `check_id` und `test_id` aus dem Evidence-Laufkontext müssen exakt einen
deklarierten Slot bezeichnen; ein Test-Subject darf keinen anderen Testslot
desselben Contracts übernehmen.

Nur ein Contract mit `configuration_policy="independent"`, dessen aktueller
Kontexthash in der Evidence als Subjectbindung vorliegt, erlaubt die Verwendung
über Konfigurationsgrenzen hinweg, auch bei ausdrücklich unkonfiguriertem
Auswertungskontext. Dies gilt auch für ursprünglich als `bound` aufgezeichnete
Evidence; ihr historischer Konfigurationshash bleibt erhalten. Ein fehlender
oder fachlich geänderter Contract gewährt keine Ausnahme. Eine geänderte
Subjectbindung bleibt auch unter einem unabhängigen Contract stale.

Der Teilbericht enthält `freshness=current|stale`, `context_current` und
maschinenlesbare Gründe: `subject_not_recorded`, `subject_context_changed`
und `configuration_changed`. Mehrdeutige doppelte Subject-IDs werden abgewiesen.
Evidence-Revision und Vollhash bleiben als historischer Auditbezug im Bericht,
entscheiden aber nicht über fachliche Aktualität. Der Bericht bindet auch die
tatsächlichen Evidencebytes und erhält deren Ergebnis und Laufkontext.

Bei übergebenem Contract ergänzt der Bericht dessen aktuelle Byte-, Voll- und
Kontexthashes, die historische Contractbindung, den aufgezeichneten Prüfschritt
und `contract_configuration_independent`. Zusätzliche Stale-Gründe sind
`contract_not_recorded`, `contract_context_changed` und
`independent_contract_required`. Reine Auditänderungen am Contract entwerten
dessen fachliche Bindung nicht. Ein fremder Contract, ein fehlender oder
abweichender Prüfschritt sowie widersprüchliche Contract-Subjectstände sind
Eingabefehler und werden nicht stillschweigend zugeordnet.

Ein kontextaktueller Nachweis kann fehlgeschlagen sein oder einem anderen
Produktstand angehören. Geprüft wird die lokale Deklaration des übergebenen
Contracts, keine unabhängig aufgelöste Pflichtmenge. Pflichtmenge, Produktstand,
maßgebliche Läufe, vollständige Verifikation und Release Readiness sind hier
nicht bewertet.
`verification_result` wird weder erzeugt noch ins Subject geschrieben.
Alle Eingaben bleiben unverändert; die API liest keine Dateien, führt keinen
Testpfad aus und erteilt keine Schreib- oder Freigabeberechtigung.
