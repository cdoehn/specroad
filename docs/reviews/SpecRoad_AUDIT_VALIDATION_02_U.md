# AUDIT-VALIDATION-02.U – produktive Verbindung der M4-Fachprüfungen

**Entscheidung vom 5. Oktober 2026: F08 ist für vorhandene M4-Prüfer bestätigt.**
Die öffentliche Projekt- und Zielvalidierung führt Sprachpolicy, Profil-SRX und
vorhandene formale Approvalprüfungen nicht selbst zusammen. Auch ein gültiges
Draft-Requirement mit ausgeliefertem Softwareprofil bleibt ohne zusätzliche
Aufrufergates unvollständig. Die Pipeline meldet dies ehrlich; es gibt keinen
beobachteten falschen Erfolg und keine unberechtigte Veröffentlichung.

Die Untersuchung gehört zum aktiven
[Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Sie ändert keine Produktquelle und keine Requirementbewertung. Produktstand
237/885 bleibt bestehen; 5.t.W bleibt bis AUDIT-CLOSE gesperrt. Als Nächstes
folgt AUDIT-VALIDATION-03.U, danach die bestätigten Validierungskorrekturen.

## Bindung und Methode

- Result: `specroad-apply_Result_235051_1004_72af87.zip`.
- Result-SHA-256: `8952cd71099185afaed215b7a71455dd8a399f043715f2353e5b3cccc037a85d`.
- Basiscommit: `b669fe16663eb88b48543cb55288cbecf494040d`.
- Spezifikations-SHA-256: `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.
- Alle 1.448 Snapshotdateien stimmen bezüglich Git-Objektkennung, Größe,
  Dateityp, Ausführbarkeitsmodus und lokalen Bytes überein. Das Result ist sauber.
- [Reproduktionsprogramm](SpecRoad_AUDIT_VALIDATION_02_U_probe.py): zwölf Fälle
  mit vier parallelen, per `spawn` isolierten Workerprozessen.
- [Gebundene Beobachtungen](SpecRoad_AUDIT_VALIDATION_02_U_observations.json):
  vollständige Rückgaben, Eingabehashes, Probe-/Quellbindung und Schreibkontrolle.

Jeder Fall legt ein eigenes wirklich gelesenes Projekt mit `specroad.json`,
Requirement und Goal an. Die reiferen Varianten enthalten zusätzlich eine
Verification, eine Herkunftsbeziehung und eine Verifikationsbeziehung. Die
Fixtures erzeugen Fachwerte; gespeichertes `approved` beweist keine menschliche
Freigabe. `core@0.2.0` und `software-en@0.2.0` beziehungsweise
`software-de@0.2.0` stammen aus dem ausgelieferten, hashgeprüften Profilbestand.
Diese Bytes werden ausdrücklich in das temporäre Projekt übernommen und über
`read_profile` erneut geprüft. Ebenso wird das ausgelieferte Offline-Sprachregister
ausdrücklich als Projektressource installiert und in der Konfiguration gebunden.
Der Fall ohne Register erhält weder Ressource noch stillen Fallback.

Beobachtet werden `validate_project_read_only`, `validate_model`,
`assess_validation`, `inspect_requirement_language`, der echte SRX-Auswerter
und `assess_requirement_approval`. Für 5.f/5.g liefert `capture_model_inputs`
die reale Root-/Bytebindung. `TargetModel` erhält die explizit vollständig
bereitgestellten Artefakt-, Profil- und Registerbytes. `prepare_change_target`
ändert nur das Goal im Speicher; `dry_run_change` bewertet denselben Plan.
Die explizit gelesenen Ressourcen werden anschließend erneut geprüft.

Es werden keine `ModelGate`-Callbacks injiziert, keine Voraussetzungen als
erfolgreich erfunden und kein menschlicher Reviewer authentifiziert. Die
Zielprüfung behauptet weiter nur `complete_supplied_project_target` und keine
atomare Dateiinventur. Die Probe setzt keinen Publikationsbackend ein.

## Beobachtete öffentliche Ergebnisse

| Fall | Einzelprüfer | Öffentliche Projektvalidierung und Zielpfad |
|---|---|---|
| Draft, Software-en, zulässiges `en` | Sprachprüfung Code 0; gelieferte SRX-Regel wahr | `language_policy` und `profile_lint` unverfügbar, Code 5. |
| Draft, Software-de, zulässiges `en` | Dieselben Ergebnisse; kein Sprachwechsel durch das Profil | Dieselben fehlenden Gates, Code 5. |
| Draft nur mit Coreprofil | Sprachprüfung Code 0; keine Profil-SRX-Regel | Nur `language_policy` unverfügbar, Code 5. |
| Draft, verbotenes `de` bei erlaubtem `en` | `SRV179`, `disallowed_language`, `/language`, error, Code 1 | Nur Unverfügbarkeit; kein SRV179 aus dem nicht aufgerufenen Prüfer. |
| Dieselbe Abweichung als warning | Einzelprüfung Code 0; mit strict Code 1, unveränderte Severity | Beide Projektläufe bleiben Code 5; strict startet keine fehlende Prüfung. |
| Draft ohne gebundenes Register | Einzelprüfung: `language_registry_required` | Unverfügbares Sprachgate, Code 5; kein Erfolg aus Distributionseinstellungen. |
| Draft ohne Statement | Gelieferte SRX-Regel falsch; Sprachleser erkennt das fehlende Pflichtfeld | Projektprüfung: `SRV002`, `/statement`, Code 3; Zielplanung lehnt das strukturell ungültige Artefakt ab. |
| Vollständiges in_review Requirement | Formale Approvaldaten gültig; menschlicher Review fehlt | Zusätzlich Lifecycle und Evidence unverfügbar; Code 5. |
| Vollständiges gespeichertes approved Requirement | Formale Approvaldaten gültig; Review und Dienstvoraussetzungen fehlen | Zusätzlich Review-Aktualität unverfügbar; Code 5. |
| Approved mit TODO im Statement | Approvalkern: `approval_open_placeholder`, SRV033 | Schema-/Relationsstufen bestehen; der konkrete Approvalbefund fehlt. |
| Approved mit Verification für ein anderes Subject | Approvalkern: `approval_verification_subject_mismatch`, SRV032 | Referenzen sind auflösbar; der konkrete Approvalbefund fehlt. |
| Approved ohne verified_by | Approvalkern erkennt Core- und Profilpflicht | Die echte Relationsstufe erkennt beide fehlenden Minima; zusätzlich bleiben Fachgates unverfügbar. |

In elf strukturell geeigneten Fällen stimmen Zielassessment und erneut
ausgeführtes Dry-Run-Assessment exakt überein. Beide bleiben unvollständig,
`target_validated=false`; der Dry-Run liefert Code 5 und
`write_state=not_committed`. Das fehlende Statement wird bereits beim
Vorbereiten des Ziels als `missing_field` mit Code 3 abgelehnt. Es wird kein
Dry-Run-Erfolg über ein ungültiges Modell behauptet.

Alle zwölf Projekte behalten Dateinamen, Verzeichnisse, Modi und Bytes. In den
beobachteten Produktfunktionen gab es keinen versuchten Write sowie keinen
Prozess- oder Netzwerkaufruf. Das Untersuchungsprogramm selbst erstellt nur
seine eigenen Fixtures und Worker. Die Beobachtungen sind historische Daten,
keine Regressionstests, die den Fortbestand dieser Lücken verlangen.

## Tatsächliche Verbindungen und Grenzen

Die folgenden Verbindungen bestehen bereits und sind keine Reparaturziele:

- `validate_model` führt Parsing, Feldschema, Identitäten, Referenzen, Graph,
  Profilfelder und Mindestbeziehungen tatsächlich aus. Die negative
  Statementkontrolle und die fehlende Profil-/Core-Verifikationsrelation zeigen
  reale Fehlerpfade, keine ausschließlich simulierten Gateantworten.
- `assess_validation` übernimmt beobachtete Stufendiagnosen, bindet bei
  gelieferten Dokumenten deren exakte Bytes und berechnet Fail-Policy und
  Exitcode. `validate_project_read_only` und `assess_change_target` benutzen
  diese Funktion bereits. Für diesen Anschluss ist kein neuer Adapter nötig.
- `prepare_change_target` und `dry_run_change` benutzen dieselbe Zielbewertung.
  Fehlende Gates verhindern einen validierten beziehungsweise vorbereiteten
  Schreibzustand. M5s lokale Lifecyclefaltung setzt unter anderem inhaltlich
  geänderte approved Artefakte auf proposed zurück; sie ist vorhanden.

Die fehlenden Verbindungen werden getrennt bewertet:

| Verbindung | Befund und zeitliche Einordnung |
|---|---|
| Sprachpolicy → gemeinsame Modell-/Projekt-/Zielprüfung | **Bereits fällig:** 4.m liefert echte Policy-/Register-/Paketprüfer, 4.o.C fordert die gemeinsame Pipeline und 4.r/5.f deren nutzbare Lesepfade beziehungsweise Zielprüfung. Die deklarierte Sprache und gebundene Konfiguration sind vorhanden. Eine spätere CLI rechtfertigt nicht den fehlenden Bibliotheksadapter. |
| Zusammengesetzte Profil-SRX-Regeln → gemeinsames Gate | **Bereits fällig:** SRX und Profile aus 4.a–4.k sind vorhanden. Der Dispatcher erkennt `profile_lint` als Pflicht, führt aber keinen gelieferten Regelsatz aus. 4.o/5.f brauchen die echte Auswertung mit Profil-, Regel-, Artefakt- und Kontextbindung. |
| Vorhandene formale Approvalbefunde → gemeinsame Diagnosemenge | **Bereits fällig im vorhandenen Umfang:** 4.q enthält die formalen Prüfer; Platzhalter und widersprüchliche Verification-Subjects sind an echten Daten feststellbar. Diese Befunde sollen über die gemeinsame Projekt-/Zielbewertung sichtbar werden. Ihre Aufnahme darf keine vollständige Lifecycle-, Review- oder Freigabeprüfung vortäuschen. |
| Vollständige menschliche Requirementfreigabe und Lifecyclekommando | **Keine automatische Freigabe nachrüsten:** Die API verlangt ausdrücklich gelieferte, aktuelle und authentifizierte Reviewbeobachtungen sowie alle Dienstvoraussetzungen. Die Probe liefert diese nicht. `eligible_for_human_approval=false` ist deshalb richtig. Der konkrete Authoringablauf folgt in 7.f; die bestehende Lifecyclefaltung verweigert einen Approvalübergang mit `approval_gate_required`. Ein Rollenlabel oder bestandener SRX-Ausdruck ersetzt den Review nicht. |
| Relationsreview und seine Aktualität | **Konkret später:** 7.g erstellt gebundene Reviewdatensätze, 7.h berechnet current/suspect/invalid und 7.j integriert Reviewpolicy. Das aktuelle Fehlen solcher Beobachtungen bleibt sichtbar; es wird nicht mit einer leeren Erfolgsantwort repariert. Das ist vom schon vorhandenen formalen Approvalkern zu unterscheiden. |
| Evidence-Aktualität und Verification-Gesamtvertrag | **Konkret später:** 12.a–12.c liefern Vertrag, Planung und Kontext; 12.t.W registriert echte Evidence-/Codezustände in der Validation. Eine vorhandene Verification mit gültigen Feldern beweist heute keine aktuelle Evidence. 4.o.R erlaubt und verlangt diese spätere Registrierung ausdrücklich. |
| Baseline-Integrität | **Konkret später, in diesen Fixtures nicht anwendbar:** 10.d prüft Objektbytes und Manifest, 10.d.C registriert den Baselineleser als Validator. Die Probe behauptet keinen Baseline-Nachweis. |

Historische Lifecycleaussagen bleiben ohne echte Vergleichs-/Reviewquellen
unverfügbar. Die Korrektur ersetzt sie weder durch die Gültigkeit eines
gespeicherten Status noch durch die rein lokale Lifecyclefaltung. Auch die
übrigen hier nicht anwendbaren Hooks für Dokumentmodelle, Konfigurationen und
externe Ressourcen sind durch diesen Ausschnitt nicht als vollständig geprüft
oder als neue Defekte nachgewiesen. Sie werden nicht künstlich aktiviert.

## Vertragsvergleich und vorhandene Nachweise

SR-REQ-0086 nennt unter anderem Lifecycle, Profile, Baseline-Integrität und
Evidence-Aktualität. Die Matrix ordnet ihn primär 4.o zu; dessen R-Abnahme
verschiebt echte Baseline-/Evidencegates ausdrücklich. Dieser Vorbehalt erlaubt
keine pauschale Verschiebung der bereits implementierten Sprach- und
Profilprüfer. SR-REQ-0100 verlangt Schreibfreiheit. Diese Eigenschaft besteht
in den beobachteten Bibliothekspfaden; der Befund betrifft den fachlichen
Integrationsumfang und keinen nachgewiesenen Verstoß gegen Schreibfreiheit.
SR-VER-0007 verlangt beobachtbare maschinenlesbare Diagnosen. Eine allgemeine
Unverfügbarkeitsdiagnose ersetzt keinen bereits lieferbaren Fachbefund.

Die SR-TC-Manifeste bleiben korrekt auf `partial`. Insbesondere
`test_missing_lifecycle_validator_is_not_synthetic_pass`,
`test_explicit_profile_lint_cannot_be_ignored` und
`test_absent_semantic_gate_is_not_passed` belegen fehlersicheres Dispatching,
keine fertigen Produktionsadapter. `tests/support/targets.py::gate` kann
standardmäßig immer erfolgreiche Antworten erzeugen; `tests/support/approval.py`
liefert ausdrücklich synthetische Voraussetzungen und Reviewer. Das ist für
gezielte Schnittstellen-/Bindungstests zulässig, aber kein Beleg einer echten
Gesamtvalidierung. Die vorliegende Probe benutzt diese Erfolgsdienste nicht.

## Bestätigte Nacharbeit

AUDIT-VALIDATION-02.W/R/C wird im einzigen Implementierungsplan konkretisiert:
vorhandene Sprachpolicy- und Profil-SRX-Kerne produktiv anschließen und formale
Approvalbefunde im vorhandenen Umfang übernehmen; danach Mehrfachbefunde,
Selektion, Profile/Severity, Ressourcenfrische und Ziel-/Dry-Run-Parität absichern;
anschließend gemeinsame Beobachtung und Diagnoseprojektion bereinigen.

Abnahme ist ein tatsächlich vollständiger, geeigneter Draftfall und die
sichtbare fachliche Ablehnung passender Negativfälle. Reifere Modelle mit noch
fehlenden Review-/Evidence-/Historyvoraussetzungen bleiben unvollständig.
Kein neues persisted Reviewformat, keine erfundene menschliche Authentifizierung,
kein optionaler Spracherkenner und keine vorgezogene vollständige CLI gehören
zu dieser Korrektur. U03 wird vorher abgeschlossen; dessen Diagnosefrage wird
nicht mit der funktionierenden vorhandenen Projektion vorentschieden.

Commit-Message dieses U-Bundles:
`docs(validation): record missing production gate adapters`.
Erst das erfolgreiche Apply-Result bestätigt den U-Commit.
