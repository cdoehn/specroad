# AUDIT-VALIDATION-01.U – nichtliterale Core-Lintdiagnosen

**Entscheidung vom 5. Oktober 2026: bestätigt, auf den fehlenden Lintpfad
eingegrenzt.** Fehlende Begründung, Verifikation und Mindestbeziehungen werden
im vorhandenen öffentlichen Lintpfad nicht diagnostiziert. Die zugehörigen
Modell- und Relationsprüfungen bestehen bereits. Sie müssen nicht neu erfunden,
aber für die geschuldete Lintabnahme nutzbar gemacht werden.

Die Untersuchung gehört zum aktiven
[Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Sie ändert kein Produktverhalten und setzt kein Requirement auf `passed`.
Produktstand 237/885 und Sperre von 5.t.W bleiben bestehen. Als Nächstes folgen
AUDIT-VALIDATION-02.U und 03.U, danach die bestätigten Korrekturen.

## Bindung und Methode

- Result: `specroad-apply_Result_230658_1004_9dff6c.zip`.
- Result-SHA-256: `33122b5e7275a4ab8fd102721f5386a295209c0f540ed2b9016dfc58efa33e3e`.
- Basiscommit: `ee91f34df4bee63ea983680afa5412e601ba8185`.
- Spezifikations-SHA-256: `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.
- Alle 1.445 Snapshotdateien wurden gegen Git-Objektkennung, Größe, Dateityp,
  Ausführbarkeitsmodus und lokale Bytes geprüft. Das Result ist sauber.
- [Reproduktionsprogramm](SpecRoad_AUDIT_VALIDATION_01_U_probe.py): acht Fälle
  mit vier parallelen, per `spawn` isolierten Workerprozessen.
- [Vollständige Beobachtungen](SpecRoad_AUDIT_VALIDATION_01_U_observations.json):
  Eingabehashes, tatsächliche Resultate, Diagnosemengen, Prüfstufen,
  Schreibversuche und unveränderte Dateiinventur; Probe- und Quellbindung enthalten.

Die synthetischen Projekte verwenden ein Requirement, ein Herkunftsziel, eine
Verification und einen Term. Der reguläre Positivfall besitzt eine Begründung
sowie `addresses` und `verified_by`. Varianten entfernen jeweils genau die zu
prüfenden Daten. Die gespeicherte Reife `approved` aktiviert vorhandene
Feld-/Relationspflichten; sie ist kein Nachweis einer echten Freigabe.

Beobachtet werden `lint_literals`, `lint_project_read_only`,
`validate_domain_fields`, `RelationObligations` und
`validate_project_read_only`. Die Projektvalidierung erhält das tatsächlich
ausgelieferte `core@0.2.0`-Profil. Es gibt keine immer erfolgreichen
Gate-Callbacks und keine künstliche Review- oder Evidencefreigabe. `strict`
wird zusätzlich über dieselbe öffentliche Lintfunktion ausgewertet.

## Beobachtungen und Gegenproben

| Fall | Öffentlicher Lintpfad | Bestehende Feld-/Relationsprüfung |
|---|---|---|
| Vollständige Begründung und beide Pflichtrelationen | Keine Diagnose, Code 0; auch mit `strict` | Feldschema und beide Mindestbeziehungen erfüllt. |
| Begründung fehlt im approved Requirement | Keine Diagnose, Code 0; auch mit `strict` | Feldschema und Projektvalidierung scheitern mit `schema_any_of`; Projektcode 3. |
| `verified_by` fehlt | Keine Diagnose, Code 0; auch mit `strict` | `core:requirement-verification`, `missing_required_relation`, Ist 0 / Soll 1. |
| Herkunftsbeziehung fehlt | Keine Diagnose, Code 0; auch mit `strict` | `core:requirement-origin`, `missing_required_relation`, Ist 0 / Soll 1. |
| Beide Pflichtrelationen fehlen | Keine Diagnose, Code 0; auch mit `strict` | Beide unabhängigen Relationsbefunde werden gemeinsam ausgegeben. |
| `TODO` im approved Statement | `SRV033`, `open_placeholder`, Code 1; auch mit `strict` | Funktionierende Kontrolle des bestehenden Literalpfads. |
| Explizit verbotenes Synonym im Statement | `SRV053`, `forbidden_synonym`; Code 0 bei Fehlerschwelle error, Code 1 mit `strict` | Funktionierende Warnungs-/Fail-Policy-Kontrolle. |
| Draft ohne Begründung und Pflichtrelationen | Keine Diagnose, Code 0 | Feldschema gültig; die bestehenden approved-Mindestregeln sind nicht anwendbar. |

In allen acht Fällen bleiben Dateinamen, Verzeichnisse, Modi und Bytes des
jeweiligen Projekts unverändert. Es gab keinen versuchten Projektwrite und
keinen Prozess-/Netzwerkaufruf innerhalb der beobachteten Produktfunktionen.
Die Worker und temporären Fixturedateien werden ausschließlich vom
Untersuchungsprogramm angelegt.

`lint_project_read_only` bezeichnet seinen Umfang ausdrücklich als
`selected_literal_fields_only`; `project_complete` und `approval_granted`
bleiben falsch. Sein `checks_complete=true` gilt nur für diesen Teilumfang.
Die Beobachtung ist daher kein Nachweis einer vorgetäuschten Gesamtfreigabe.
Sie belegt den fehlenden nichtliteralen Lintanteil von SR-REQ-0096.

Auch die positive Relationskontrolle wird nicht als vollständige
Projektvalidierung ausgegeben: Ohne registrierte Fachgates bleiben
`evidence_currentness`, `language_policy`, `lifecycle` und `review_currentness`
im approved Fall `unavailable`; die Projektvalidierung liefert Code 5. Die
Relationsfehler erscheinen trotzdem in ihrer tatsächlich ausgeführten Stufe.
Diese Gateverbindung wird separat unter AUDIT-VALIDATION-02.U untersucht.

## Vertrag, vorhandene Nachweise und Ursache

SR-REQ-0096 verlangt vier Anteile: fehlende Begründung, fehlende Verifikation,
konfigurierte literale Verstöße und fehlende Mindestbeziehungen. Die
Requirementmatrix weist den Vertrag 4.l zu und nennt keine spätere
Sekundärposition. 4.l.W/R konkretisiert jedoch nur Literalregeln; 4.o liefert
die Modellpipeline und 4.r die schreibfreien Lesepfade. Diese engere historische
Umsetzung erledigt die anderen Bestandteile des zugeordneten Requirements nicht.
SR-VER-0007 verlangt beobachtbare Diagnosen; vorhandene Kernfunktionen oder
ein `partial`-Status ersetzen den Lintnachweis nicht.

`lint/core.py` prüft gemeinsame Artefaktfelder, Glossar, Platzhalter und
Termreferenzen. `storage/read_only.py::lint_project_read_only` ruft nur diese
Literalprüfung auf. Eine Ermittlung fehlender Begründung oder vollständiger
Relationsminima ist dort nicht angeschlossen. `strict` verändert die
Fehlerschwelle und aktiviert keinen solchen zusätzlichen Prüfpfad.

Vorhandene positive Gegenbelege bleiben gültig:

- `test_literal_lint.LiteralWorkTests.test_declared_forbidden_synonym_is_diagnosed`
  und `test_approved_core_placeholders_cannot_be_removed` belegen die Literalregeln.
- `test_requirement_approval.test_rationale_is_required_in_hypothetical_approved_schema`
  und `test_missing_verified_by_blocks_even_if_service_receipt_claims_passed`
  belegen Freigabegrenzen, keinen allgemeinen Lintpfad.
- `test_relation_obligations.ObligationWorkTests.test_approved_requirement_needs_origin_and_verification`,
  `test_each_origin_alternative_is_accepted` und
  `test_nonapproved_requirement_does_not_get_approval_minima` belegen die
  vorhandene Relationspolicy und ihre Reifegrenze.

SR-TC-0096 bleibt unverändert `partial`: Seine vier bisherigen Testreferenzen
decken Literalverstöße und Termreferenzen ab. Die dort offene spätere
Pipelineintegration erhält mit diesem Befund eine konkrete Korrekturposition;
sie wird nicht als bereits erfüllter Gesamtvertrag umgedeutet.

## Konkretisierte Korrektur

**AUDIT-VALIDATION-01.W:** Im öffentlichen Core-/Read-only-Lintpfad die bereits
geschuldeten, anwendbaren nichtliteralen Befunde zugänglich machen. Fehlende
Begründung sowie fehlende Verifikations-/Herkunfts- und sonstige anwendbare
Mindestbeziehungen müssen getrennte maschinenlesbare Befunde liefern. Bestehende
Feld- und Relationsregeln einschließlich ihrer Reife-/Profilgrenzen wiederverwenden.
Positive vollständige Daten bleiben befundfrei; Literaldiagnosen bleiben erhalten.

**AUDIT-VALIDATION-01.R:** Mehrere gleichzeitig fehlende Werte/Relationen,
eingehende und ausgehende Profilminima, Teilselektionen, fehlende Zielressourcen,
Reifegrenzen, unverfügbare Voraussetzungen und Änderungen während des Lesens
einbeziehen. Diagnosemenge, Code/Pointer/Artefaktbindung, Fail-Policy und Umfang
müssen zur tatsächlich ausgeführten Prüfung passen. Keine geänderte
Freigabepolicy, keine behauptete Vollprüfung bei fehlendem Kontext.

**AUDIT-VALIDATION-01.C:** Gemeinsame Feld-/Relationsbeobachtung und
Diagnoseprojektion konsolidieren. W-/R-Verträge und schreibfreie Wirkung erhalten.

Diese Folge erfüllt die bereits zugeordnete Core-Lintabnahme. Sie implementiert
keine Sprachverständnisfunktion, keinen Analyzer und keine neue CLI-Oberfläche.
Die Gateintegration und die Diagnoseaggregation bleiben den Untersuchungen
AUDIT-VALIDATION-02.U und 03.U vorbehalten. Deren Entscheidungen können die
technischen Abhängigkeiten der anschließenden Korrekturen weiter konkretisieren.

## Reproduktion und Testgrenzen

```sh
.venv/bin/python -I -B docs/reviews/SpecRoad_AUDIT_VALIDATION_01_U_probe.py "$PWD" --workers 4
```

Das Programm speichert Beobachtungen des jeweils untersuchten Stands. Es gehört
nicht zur Regressionssuite und verlangt nicht, dass ein später behobener Fehler
fortbesteht. Die gespeicherte JSON-Datei gehört ausschließlich zur oben genannten
Basis. Produktquellen, Tests und Requirementmanifeste bleiben in diesem
Untersuchungsbundle unverändert.

Für den Bundlezustand wird die vollständige vorhandene Suite in Development
parallel geprüft. Apply führt vor seinem einzigen Commit den vollständigen
parallelen und zusätzlich den seriellen Lauf aus. Erst dessen Result bestätigt
den Commit; die Untersuchung behauptet keinen zukünftigen Apply-Erfolg.
