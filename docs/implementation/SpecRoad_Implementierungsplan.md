# SpecRoad – vollständiger W/R/C-Implementierungsplan

**Status:** aktive Implementierung; verbindlicher Fortschritt im folgenden Fortschrittsblock.  
**Planrevision:** 255 · **Stand:** 18. November 2026 · **Zielrelease:** 0.2.0 · **Spezifikationsstand:** 0.2.94

Dieser Plan konkretisiert die vom Nutzer bestätigten **20 Meilensteine in 306 Schritte und 918 einzeln beschriebene W/R/C-Commits**. Bei seiner Anlage enthielt er keine abgeschlossene Produktimplementierung; der folgende Fortschrittsblock wird commitweise nach erfolgreicher Verhaltensabnahme aktualisiert. Die Meilensteinreihenfolge bleibt erhalten; die früher genehmigte lesende Voraussetzung RESTORE-PROPOSAL-PREREQUISITE wurde nach der damaligen Spezifikation innerhalb von 15.l.R vorgezogen und bleibt als normaler Prüfkern erhalten. Jeder Schritt behält seinen konkreten Arbeitsumfang und seine eigene Verhaltensabnahme.

Die Aufteilung vom 6. November 2026 ist ein reiner OFF-PLAN-Dokumentationsschritt. Die fachliche Planrevision, Produktpositionen und ihre Abnahmen werden dadurch nicht geändert. Zähler werden nur anhand erfolgreicher Apply-Commits fortgeschrieben.

Vor der Arbeit: [Projektregeln](../../DEVELOPMENT.md), [Grundlagen](rules/Grundlagen.md), [gemeinsame Arbeitsregeln](../development/Plan_Arbeitsregeln.md) und [Planpflege](AGENTS.md) lesen. Danach nur den betroffenen Meilenstein, seine verlinkten Ergänzungen und benötigten Matrizen lesen. Die Dateien bilden gemeinsam den vollständigen Plan.

Detailentscheidungen für 17.l: [MERGE-WORK-627](decisions/merge-work-627.md) und [MERGE-CLI-633](decisions/merge-cli-633.md).
Die zweite Ergänzung bindet ausschließlich die öffentliche Übergabe an den vorhandenen nativen Writer; Produktzähler und Freigabegates bleiben im Klärungsstand unverändert.

OFF-PLAN-Auftrag: [Hostgrenze für identische Tests](decisions/test-host-once.md).

OFF-PLAN-Auftrag: [Remote-Testhosts und W/R/C-Abnahmen](decisions/remote-test-hosts-637.md).

OFF-PLAN-Ergänzung: [Hostdaten für lokale Testläufe](decisions/local-test-history-640.md).

Detailentscheidung für 18.a: [PROPOSAL-DATA-645](decisions/proposal-data-645.md).

Korrektur und ausdrückliche OFF-PLAN-Ergänzung: [Bundle 647 — 18.b.R/C und Control-Vollzugriff](history/bundle-647-correction-and-access.md).

Korrektur des weiterhin offenen R/C-Rests: [Bundle 648 — Hostpool-Laufzeitschreiber](history/bundle-648-host-history-writer.md).

OFF-PLAN-Bedienauftrag: [Expliziter Control-Budgetreset 661](decisions/control-budget-reset-661.md).

Detailentscheidung für 18.h: [REVIEW-START-662](decisions/review-start-662.md).

Detailentscheidung 18.i und ausdrückliche Control-Vorgaben: [PROPOSAL-REVIEW / CONTROL-DEFAULTS-666](decisions/review-decision-control-666.md).

Korrektur und vollständiger Rest: [Bundle 667](history/bundle-667-control-defaults-correction.md).

Korrektur des Budgetstopps: [Bundle 668](history/bundle-668-correction-budget-stop.md).

Proposal-Review-Korrektur und offener W/R/C-Rest: [Bundle 669](history/bundle-669-proposal-review-correction.md).

Korrektur des exakten Commitumfangs: [Bundle 670](history/bundle-670-proposal-scope-correction.md).

Korrektur der Review-Pfadübergabe und Beispielbindung: [Bundle 671](history/bundle-671-proposal-review-path-correction.md).

Detailentscheidung für 18.j: [PROPOSAL-NEGATIVE-672](decisions/proposal-negative-672.md).

Korrektur des 18.j-Testadapters und vollständiger Rest: [Bundle 673](history/bundle-673-negative-test-correction.md).

Detailentscheidung für 18.k: [PROPOSAL-APPLY-674](decisions/proposal-apply-674.md).

Korrektur des Laufprofils und vollständiger 18.k-Rest: [Bundle 675](history/bundle-675-host-profile-correction.md).

Korrektur der Proposal-Schemata und Registrierungsabnahmen: [Bundle 676](history/bundle-676-proposal-schema-correction.md).

Korrektur der Profilprüfung für angewendete Proposals: [Bundle 677](history/bundle-677-proposal-profile-correction.md).

Korrektur der Ergebnisschema-Registrierung für Proposal Apply: [Bundle 678](history/bundle-678-proposal-result-schema.md).

Unabhängige Katalogerwartung vervollständigt: [Bundle 679](history/bundle-679-catalog-expectation.md).

Offene R/C-Korrektur nach erfolgreichem W: [Bundle 680](history/bundle-680-proposal-apply-correction.md).

Korrektur der Prozessabbruchtests: [Bundle 681](history/bundle-681-process-crash-deadline.md).

## Abgeschlossene OFF-PLAN-Folge: spekulative Testkopien

START/CONFIG/LIVE/MOVE ist im erfolgreichen Result von Bundle 696 vollständig
übernommen; MOVE.C wurde mit 8.901 bestandenen Tests committed. Darauf baut
der ausdrückliche Nutzerauftrag [SPECULATE-697](decisions/speculative-tests-697.md)
mit drei echten W/R/C-Ständen auf. Dieser Zielstand gilt erst nach dem eigenen
erfolgreichen Apply-Gate bis **SPECULATE.C**; die OFF-PLAN-Folge ist damit vollständig,
anschließend der unveränderte Produkt-Recovery-Rückbau. Produktzähler bleiben 762/918.

Korrektur nach fehlgeschlagenem W: [Bundle 698](history/bundle-698-speculative-correction.md).
Bundle 697 erzeugte keinen Commit; dieser Fortschrittsblock ist weiterhin
der erst nach dem eigenen erfolgreichen Gate gültige Zielstand.

Fortsetzung nach bestätigtem W und fehlgeschlagenem R:
[Bundle 699](history/bundle-699-speculative-ack-handshake.md).
W bleibt committed; ausschließlich der offene R/C-Rest wird korrigiert.
Die Zielwerte dieser Stage gelten weiterhin erst nach ihrem eigenen Gate.

## Aktuelle Produktfolge: Recovery zurückbauen

[RECOVERY-REMOVAL-006](decisions/recovery-removal-006.md) setzt die ausdrückliche
Nutzerentscheidung in Spezifikation 0.2.85 um. [18.s bis 18.x](milestones/M18.md#vorgezogener-umbau-nach-18k--recovery-removal-006)
werden unmittelbar nach abgeschlossenem 18.k.C und vor 18.l.W ausgeführt:
gemeinsame Prüfdienste, Schreibmarker/Receipts, normale Writer/Proposals,
Migration/Merge/Rooterzeugung, Recovery-/Restore-Workentfernung und abschließende
Format-/Git-/Integrationsabnahme. Das sind 18 neue Produktcommits.
SpecRoad bleibt bis zur ausdrücklichen Nutzerfreigabe unbenutzt.

Das aktuelle Spezifikations-/Planungsbundle ist genau ein OFF-PLAN-Commit
`RECOVERY-REMOVAL-PLAN-006` mit Nachricht
`docs(spec): Abbruchsperre und Recovery-Rueckbau vor 18.l planen`.
Es entfernt noch keinen Produktcode und schließt keine neue Produktposition.
Die historische Hauptlinien-Bundlekennung 681 bleibt im Fortschrittsblock;
die unabhängige Apply2-Übergabe heißt 006. Vorbereitet ist kein Apply-Erfolg.

OFF-PLAN-Nutzerauftrag: [Workerstandard12 und Control-Budgets20 — Bundle683](decisions/control-budget-20.md). Die Produktpositionen und der Recovery-Rückbau bleiben unverändert.

Korrektur und vollständiger OFF-PLAN-Rest: [Bundle 684 — Reset-Abnahme](history/bundle-684-budget-reset-receipt.md).

Aktuelle vollständige Gruppe: [18.s — gemeinsame native Qualifikation, Bundle 700](history/bundle-700-common-qualification.md). Die folgenden Zielwerte gelten erst nach dem erfolgreichen Gate dieser Stage; der Schreibmarker-/Abschlusswechsel folgt vollständig in 18.t.

[Korrektur 701](history/bundle-701-remote-temp-monitor.md) setzt ausschließlich den offenen C-Rest fort; W/R sind durch das Result bestätigt. Die Zielwerte unten werden erst mit dem erfolgreichen C-Gate und Commit bestätigt.

OFF-PLAN-Korrektur ohne zusätzlichen Produktfortschritt: [Bundle 702 — ungestartete Scheduler-Folgetests](history/bundle-702-scheduler-tail.md). Das erfolgreiche Result von Bundle 701 bestätigt 18.s.C; die nächste Produktposition bleibt 18.t.W.

Detailpräzisierung für 18.t: [WRITE-RECEIPTS-703](decisions/write-receipts-703.md). Die neue Belegstruktur ersetzt keine Produktfreigabe oder vorweggenommene Abnahme.

Aktuelle vollständige Gruppe: [18.t — Schreibmarker und normaler Abschluss, Bundle 703](history/bundle-703-guarded-writer.md). Die unten stehenden Zielwerte gelten erst nach erfolgreichem Apply-Gate der jeweiligen Stage. Die folgenden vollständigen Integrationsgruppen bleiben offen.

Korrektur des vollständigen 18.t-Rests und ausdrückliche OFF-PLAN-Optimierungen: [Bundle 704](history/bundle-704-writer-fixtures-test-overhead.md). Kein zusätzlicher Produktfortschritt; jeder Zielstand benötigt sein eigenes erfolgreiches Apply-Gate.

Nach erfolgreichem 18.t.W: [Korrektur 705](history/bundle-705-native-validation-receipt.md) setzt den vollständigen offenen R/C- und TEST-OVERHEAD-Rest fort. Die Zielwerte gelten erst nach ihrem eigenen Apply-Gate.

18.t.R/C sind bestätigt. [Korrektur 706](history/bundle-706-move-status-handshake.md) setzt ausschließlich den offenen TEST-OVERHEAD.W/R/C-Rest fort; kein zusätzlicher Produktfortschritt.

Ursprüngliche vollständige Gruppe: [18.u — normale Schreibadapter und Abbruchsperre, Bundle 707](history/bundle-707-normal-write-adapters.md). Die Zielwerte dieser Stage gelten erst nach ihrem eigenen erfolgreichen Apply-Gate und Commit.

Aktuelle Korrektur des vollständigen offenen Restes: [Bundle 708](history/bundle-708-normal-write-correction.md). Kein Commit aus Bundle 707 war erfolgreich.

Aktuelle Korrektur des vollständigen offenen Restes: [Bundle 709](history/bundle-709-normal-write-worker-correction.md). Kein Commit aus Bundle 708 war erfolgreich.

Aktuelle Korrektur des vollständigen offenen Restes: [Bundle 710](history/bundle-710-worker-proxy-join.md). Bundle 709 scheiterte beim Gatewayabschluss; kein Commit entstand.

Historische Korrektur: [Bundle 711](history/bundle-711-native-collection-order.md). Bundle 710 scheiterte an der Host-Nachweisbindung; damals entstand kein Commit.

Historische Korrektur: [Bundle 712](history/bundle-712-normal-read-mutex.md). Result 711 bestätigt 18.u.W und damit 769/918.

Historische Korrektur: [Bundle 713](history/bundle-713-trace-writer-contract.md).

Abgeschlossene Korrektur: [Bundle 714 — 18.u.C](history/bundle-714-completion-reader.md). Result 714 bestätigt 18.u.C mit 15.532 bestandenen Tests und Commit `6d11762a3df0b6a8435178eff2d26af270c286f8`; der technische Ausgangsstand ist sauber, 771/918.

Ausdrücklich bestätigte Fehlergarantie und ergänzende Feldbindungen für 18.v: [BOOTSTRAP-SNAPSHOT-715](decisions/bootstrap-snapshot-715.md). Result 714 bestätigt 18.u.C; der Klärungspräfix verändert keinen Produktzähler.

Ursprüngliche vollständige W/R/C-Gruppe: [Bundle 715](history/bundle-715-snapshot-bootstrap.md). Die folgenden Zielwerte dieser Stage 18.v.C gelten erst nach ihrem eigenen erfolgreichen Apply-Gate und Commit; kein Dev-Test- oder Vollsuiteerfolg wird vorweggenommen.

Historische Korrektur: [Bundle 716 — vollständiger Rest 18.v.W/R/C](history/bundle-716-snapshot-readers.md). Result 716 bestätigt 18.v.W, Commit `e0eebf6d4aa948ec6c59824416d07fc62df5c8fd`, und damit 772/918. R scheiterte anschließend mit drei Fehlern und 13.051 bestandenen Tests; C wurde nicht ausgebracht.

Abgeschlossene Korrektur: [Bundle 717 — Init-Abbruchoracles und vollständiger Rest 18.v.R/C](history/bundle-717-bootstrap-failure-oracles.md). Das erfolgreiche Result mit SHA-256 `8597e7388a5ef318d44c5ae43772f07b1e3e5cae88318fec157ec2c73c8e2d32` bestätigt beide Commits und den sauberen Endstand; 774/918, zuletzt 18.v.C.

Ursprüngliche Infrastrukturfolge: [Bundle 718 — gebundene Dateilöschungen](history/bundle-718-apply-deletion-contract.md). DELETE-CONTRACT.W/R/C erhalten getrennte Apply-Gates; der Produktzähler und die offene Position 18.w.W bleiben unverändert. Die unten angegebenen OFF-PLAN-Zielwerte gelten erst nach dem erfolgreichen Gate und Commit dieser Stage.

Aktuelle Korrektur: [Bundle 719 — Dateirechte der Löschfixtures](history/bundle-719-deletion-fixture-modes.md). Result 718 bestätigt sieben Fehler im W-Gate und keinen Commit. Der vollständige Rest DELETE-CONTRACT.W/R/C bleibt mit getrennten Gates erhalten; die Zielwerte gelten erst nach dem jeweiligen erfolgreichen Commit.

Aktuelle Folge: [Bundle 720 — Recovery-Rückbau und Git-Wiederanlauf](history/bundle-720-recovery-removal-git.md). Die folgenden Zielwerte gelten ausschließlich nach dem eigenen erfolgreichen Apply-Gate dieser Stage; alle späteren Stages bleiben bis dahin offen.

Historische Korrektur: [Bundle 721 — veraltete Recovery-CLI-Erwartungen](history/bundle-721-partial-read-expectations.md). Sein Ausgangs-Result bestätigte keinen Commit.

Aktueller vollständiger Rest: [Bundle 722 — Recovery-Rückbau fortsetzen](history/bundle-722-recovery-rest.md). Das Result von 721 bestätigt 18.w.W; 18.w.R/C und 18.x.W/R/C behalten ihre getrennten offenen Apply-Gates. Die folgenden Zielwerte gelten erst nach dem eigenen erfolgreichen Gate dieser Stage.

Aktuelle Korrektur: [Bundle 723 — Transportschemas und Lock-Regressionen](history/bundle-723-transport-schema-lock-oracles.md). Bundle 722 scheiterte in 18.w.R ohne weiteren Commit; alle fünf offenen Stages werden mit getrennten Gates fortgeführt.

Aktuelle Korrektur nach bestätigtem 18.w.R: [Bundle 724 — Work-Prüfimport und Publikationsabweisung](history/bundle-724-work-import-publication-oracle.md). 18.w.C und 18.x.W/R/C bleiben mit getrennten Gates offen; R wird nicht wiederholt.

Aktuelle Korrektur nach bestätigtem 18.w.C: [Bundle 725 — Git-Neubeginn-Testdaten](history/bundle-725-git-restart-qualification.md). Der vollständige Rest 18.x.W/R/C erhält getrennte Gates; das erfolgreiche C wird nicht wiederholt.

Detailentscheidung: [AUTHORING-PROPOSAL-726](decisions/authoring-proposal-726.md).

Aktuelle Zielstände und bestätigte Quelle: [Bundle 726](history/bundle-726-authoring-agents.md).

Stagegebundene Policy- und Gitabnahmen: [Bundle 729](history/bundle-729-proposal-policy.md).

Korrektur nach bestätigtem W: [Bundle 730](history/bundle-730-historical-proposal-policy.md). R/C bleiben bis zum jeweiligen erfolgreichen Gate offen; die folgenden Werte sind Stageziele.

Vollständige AI-Testeingabe im offenen R/C-Rest: [Korrektur 731](history/bundle-731-proposal-confidence.md). Bundle 730 erzeugte keinen weiteren Commit; die Stageziele bleiben an ihre eigenen Gates gebunden.

Nach bestätigtem R: [Korrektur 732 — importfreie Authoring-Anfragen](history/bundle-732-authoring-import.md) führt ausschließlich den offenen C-Rest fort. Bestätigt sind 788/918; die folgenden C-Zielwerte gelten erst nach dem eigenen erfolgreichen Gate.

Korrektur des Git-Scopes bei erfüllter Löschung: [Bundle 733](history/bundle-733-uncommitted-deletion-scope.md). Bundle 732 brach vor dem Testgate ohne Commit ab; der vollständige C-Rest bleibt offen.

Native Laufzeit der Treiberregressionen: [Korrektur 734](history/bundle-734-driver-test-runtime.md). Bundle 733 scheiterte im C-Gate an zwölf fehlenden Runtime-Imports; kein neuer Commit, vollständiger C-Rest erhalten.

Detailentscheidung für 18.o/18.p: [PROPOSAL-WORK-735](decisions/proposal-work-735.md).

Stagegebundene Quelle und Abnahmen: [Bundle 735](history/bundle-735-proposal-work.md).

Vollständiger offener Proposal-Workrest: [Korrektur 736](history/bundle-736-proposal-work-capabilities.md).

Nach bestätigtem 18.o.W: [Korrektur 737 — vollständiger R/C-Rest](history/bundle-737-proposal-work-build.md).

Detailvertrag und vollständige Dialogabnahmen für 18.p: [PROPOSAL-DIALOG-738](decisions/proposal-dialog-738.md).

Stagegebundene Quelle und Abnahmen: [Bundle 738](history/bundle-738-proposal-dialog.md).

Nach bestätigtem Klärungspräfix: [Korrektur 739 — vollständiger W/R/C-Rest](history/bundle-739-proposal-dialog-schema.md).

Explizite OFF-PLAN-Übernahme: [Bundle 740 — Hostgrenze und Dialoglaufzeit](history/bundle-740-host-once-dialog-performance.md).

## Fortschritt – einzige maßgebliche Planstelle

```yaml
plan_revision: 255
implementation_plan_commits_total: 918
implementation_plan_commits_completed: 795
last_completed_plan_commit: 18.p.C
next_plan_commit: 18.q.W
priority_off_plan: DIALOG-PERFORMANCE
next_off_plan_commit: DIALOG-PERFORMANCE.W
last_completed_numbered_bundle: 739
implementation_state: in_progress
audit_followup_status: closed
next_audit_step: null
plan_setup_kind: OFF-PLAN
plan_setup_id: PLAN-SETUP
plan_setup_message: "docs(plan): add detailed SpecRoad WRC implementation plan"
```

## Meilensteinübersicht

| Nr. | Meilenstein | Schritte | Plan-Commits | Positionen |
|---:|---|---:|---:|---|
| 1 | [Projektgerüst und CLI-Grundlage](milestones/M01.md#m1) | 14 | 42 | 1–42 |
| 2 | [Kanonisches Datenmodell und Speicherung](milestones/M02.md#m2) | 17 | 51 | 43–93 |
| 3 | [Relationsgraph und fachliche Modellumfänge](milestones/M03.md#m3) | 11 | 33 | 94–126 |
| 4 | [SRX-Regelsprache, Profile und Validierung](milestones/M04.md#m4) | 18 | 54 | 127–180 |
| 5 | [Sichere Änderungen, Transaktionen und Recovery](milestones/M05.md#m5) | 22 | 66 | 181–246 |
| 6 | [Ressourcensparsame und fortsetzbare Verarbeitung](milestones/M06.md#m6) | 21 | 63 | 247–309 |
| 7 | [Authoring, Lebenszyklen und Relationsreviews](milestones/M07.md#m7) | 12 | 36 | 310–345 |
| 8 | [Abfragen, Traceability, Änderungsanalyse und Git-Vergleich](milestones/M08.md#m8) | 12 | 36 | 346–381 |
| 9 | [Produktkonfigurationen und Varianten](milestones/M09.md#m9) | 8 | 24 | 382–405 |
| 10 | [Baselines und unveränderbare Referenzstände](milestones/M10.md#m10) | 9 | 27 | 406–432 |
| 11 | [Dokumentmodell, Ansichten und Berichtserzeugung](milestones/M11.md#m11) | 18 | 54 | 433–486 |
| 12 | [Verifikation, Evidence und Quellcode-Traceability](milestones/M12.md#m12) | 20 | 60 | 487–546 |
| 13 | [Releases, Meilensteine, Aufgaben und Roadmap](milestones/M13.md#m13) | 8 | 24 | 547–570 |
| 14 | [Import und Export](milestones/M14.md#m14) | 15 | 45 | 571–615 |
| 15 | [Projektbundles und portabler Austausch](milestones/M15.md#m15) | 15 | 45 | 616–660 |
| 16 | [Schema- und Datenmigration](milestones/M16.md#m16) | 11 | 33 | 661–693 |
| 17 | [Semantischer Dreiwege-Merge](milestones/M17.md#m17) | 12 | 36 | 694–729 |
| 18 | [Proposals, Schreibschutz und kontrollierte KI-Bearbeitung](milestones/M18.md#m18) | 24 | 72 | 730–801 |
| 19 | [Analyzer-Schnittstelle und echte Spracherkennung](milestones/M19.md#m19) | 25 | 75 | 802–876 |
| 20 | [Gesamtabnahme und Release](milestones/M20.md#m20) | 14 | 42 | 877–918 |
| **Gesamt** | **20 Meilensteine** | **306** | **918** | **1–918** |

## In Apply2 abgenommene Control-Erweiterung

[Control-Operations: Runtime-Voraussetzung und neun Control-Zustände](../development/Control_Operations.md).
Die zwölf W/R/C-Commits sind über Dev2-Bundles 001–004 vollständig abgenommen.
Der [Ausführungsnachweis](history/dev2-control-profiling-001-005.md) trennt den
erfolgreichen Repository-Stand von der noch offenen Control-Installation.
Produktfortschritt und Betriebsfreigaben bleiben unverändert.

## Manuelle Testoptimierung und Profiling

OFF-PLAN-Auftrag vom 10. November 2026:
[Testoptimierungen und Profiling mit sechs W/R/C-Abnahmen](../development/Test_Optimization_Profiling.md).
Alle sechs Commits sind mit Dev2-Bundle 005 erfolgreich abgenommen; siehe
[Ausführungsnachweis](history/dev2-control-profiling-001-005.md). Der Vergleich
der Vorher-/Nachher-Laufzeiten steht noch aus. Produktpositionen und Zähler
bleiben unverändert.

## Detaillierter Commitplan

Die Meilensteinlinks in der Übersicht öffnen die vollständigen W/R/C-Positionen. Ergänzende Abnahmen sind direkt beim jeweiligen Schritt verlinkt.


## Matrizen, Audit und Nachweise

- [Requirement-zu-Schritt-Matrix](matrices/Requirements.md)
- [Verifikationsregister](matrices/Verifikation.md)
- [Szenario-/E2E-Zuordnung](matrices/Szenarien.md)
- [Regressionen R-01 bis R-75](matrices/Regressionen.md)
- [Übernommene Übergabehinweise](matrices/Uebergabe.md)
- [Audit-Nacharbeiten](audit/Audit_Nacharbeiten.md)
- [Entscheidungen, Bundlehistorie und ergänzende Nachweise](history/README.md)

Neue Berichte werden dort verlinkt; sie werden nicht erneut in diesen Einstieg kopiert.

## Erhaltene Sprungmarken

Bestehende direkte Links führen weiterhin zum passenden Detailplan.

<a id="m1"></a>[Meilenstein 1](milestones/M01.md#m1)

<a id="m2"></a>[Meilenstein 2](milestones/M02.md#m2)

<a id="m3"></a>[Meilenstein 3](milestones/M03.md#m3)

<a id="m4"></a>[Meilenstein 4](milestones/M04.md#m4)

<a id="m5"></a>[Meilenstein 5](milestones/M05.md#m5)

<a id="m6"></a>[Meilenstein 6](milestones/M06.md#m6)

<a id="m7"></a>[Meilenstein 7](milestones/M07.md#m7)

<a id="m8"></a>[Meilenstein 8](milestones/M08.md#m8)

<a id="m9"></a>[Meilenstein 9](milestones/M09.md#m9)

<a id="m10"></a>[Meilenstein 10](milestones/M10.md#m10)

<a id="m11"></a>[Meilenstein 11](milestones/M11.md#m11)

<a id="m12"></a>[Meilenstein 12](milestones/M12.md#m12)

<a id="m13"></a>[Meilenstein 13](milestones/M13.md#m13)

<a id="m14"></a>[Meilenstein 14](milestones/M14.md#m14)

<a id="m15"></a>[Meilenstein 15](milestones/M15.md#m15)

<a id="m16"></a>[Meilenstein 16](milestones/M16.md#m16)

<a id="m17"></a>[Meilenstein 17](milestones/M17.md#m17)

<a id="m18"></a>[Meilenstein 18](milestones/M18.md#m18)

<a id="m19"></a>[Meilenstein 19](milestones/M19.md#m19)

<a id="m20"></a>[Meilenstein 20](milestones/M20.md#m20)

<a id="step-1-a"></a>[1.a](milestones/M01.md#step-1-a)

<a id="step-1-b"></a>[1.b](milestones/M01.md#step-1-b)

<a id="step-1-c"></a>[1.c](milestones/M01.md#step-1-c)

<a id="step-1-d"></a>[1.d](milestones/M01.md#step-1-d)

<a id="step-1-e"></a>[1.e](milestones/M01.md#step-1-e)

<a id="step-1-f"></a>[1.f](milestones/M01.md#step-1-f)

<a id="step-1-g"></a>[1.g](milestones/M01.md#step-1-g)

<a id="step-1-h"></a>[1.h](milestones/M01.md#step-1-h)

<a id="step-1-i"></a>[1.i](milestones/M01.md#step-1-i)

<a id="step-1-j"></a>[1.j](milestones/M01.md#step-1-j)

<a id="step-1-k"></a>[1.k](milestones/M01.md#step-1-k)

<a id="step-1-l"></a>[1.l](milestones/M01.md#step-1-l)

<a id="step-1-m"></a>[1.m](milestones/M01.md#step-1-m)

<a id="step-1-n"></a>[1.n](milestones/M01.md#step-1-n)

<a id="step-2-a"></a>[2.a](milestones/M02.md#step-2-a)

<a id="step-2-b"></a>[2.b](milestones/M02.md#step-2-b)

<a id="step-2-c"></a>[2.c](milestones/M02.md#step-2-c)

<a id="step-2-d"></a>[2.d](milestones/M02.md#step-2-d)

<a id="step-2-e"></a>[2.e](milestones/M02.md#step-2-e)

<a id="step-2-f"></a>[2.f](milestones/M02.md#step-2-f)

<a id="step-2-g"></a>[2.g](milestones/M02.md#step-2-g)

<a id="step-2-h"></a>[2.h](milestones/M02.md#step-2-h)

<a id="step-2-i"></a>[2.i](milestones/M02.md#step-2-i)

<a id="step-2-j"></a>[2.j](milestones/M02.md#step-2-j)

<a id="step-2-k"></a>[2.k](milestones/M02.md#step-2-k)

<a id="step-2-l"></a>[2.l](milestones/M02.md#step-2-l)

<a id="step-2-m"></a>[2.m](milestones/M02.md#step-2-m)

<a id="step-2-n"></a>[2.n](milestones/M02.md#step-2-n)

<a id="step-2-o"></a>[2.o](milestones/M02.md#step-2-o)

<a id="step-2-p"></a>[2.p](milestones/M02.md#step-2-p)

<a id="step-2-q"></a>[2.q](milestones/M02.md#step-2-q)

<a id="step-3-a"></a>[3.a](milestones/M03.md#step-3-a)

<a id="step-3-b"></a>[3.b](milestones/M03.md#step-3-b)

<a id="step-3-c"></a>[3.c](milestones/M03.md#step-3-c)

<a id="step-3-d"></a>[3.d](milestones/M03.md#step-3-d)

<a id="step-3-e"></a>[3.e](milestones/M03.md#step-3-e)

<a id="step-3-f"></a>[3.f](milestones/M03.md#step-3-f)

<a id="step-3-g"></a>[3.g](milestones/M03.md#step-3-g)

<a id="step-3-h"></a>[3.h](milestones/M03.md#step-3-h)

<a id="step-3-i"></a>[3.i](milestones/M03.md#step-3-i)

<a id="step-3-j"></a>[3.j](milestones/M03.md#step-3-j)

<a id="step-3-k"></a>[3.k](milestones/M03.md#step-3-k)

<a id="step-4-a"></a>[4.a](milestones/M04.md#step-4-a)

<a id="step-4-b"></a>[4.b](milestones/M04.md#step-4-b)

<a id="step-4-c"></a>[4.c](milestones/M04.md#step-4-c)

<a id="step-4-d"></a>[4.d](milestones/M04.md#step-4-d)

<a id="step-4-e"></a>[4.e](milestones/M04.md#step-4-e)

<a id="step-4-f"></a>[4.f](milestones/M04.md#step-4-f)

<a id="step-4-g"></a>[4.g](milestones/M04.md#step-4-g)

<a id="step-4-h"></a>[4.h](milestones/M04.md#step-4-h)

<a id="step-4-i"></a>[4.i](milestones/M04.md#step-4-i)

<a id="step-4-j"></a>[4.j](milestones/M04.md#step-4-j)

<a id="step-4-k"></a>[4.k](milestones/M04.md#step-4-k)

<a id="step-4-l"></a>[4.l](milestones/M04.md#step-4-l)

<a id="step-4-m"></a>[4.m](milestones/M04.md#step-4-m)

<a id="step-4-n"></a>[4.n](milestones/M04.md#step-4-n)

<a id="step-4-o"></a>[4.o](milestones/M04.md#step-4-o)

<a id="step-4-p"></a>[4.p](milestones/M04.md#step-4-p)

<a id="step-4-q"></a>[4.q](milestones/M04.md#step-4-q)

<a id="step-4-r"></a>[4.r](milestones/M04.md#step-4-r)

<a id="step-5-a"></a>[5.a](milestones/M05.md#step-5-a)

<a id="step-5-b"></a>[5.b](milestones/M05.md#step-5-b)

<a id="step-5-c"></a>[5.c](milestones/M05.md#step-5-c)

<a id="step-5-d"></a>[5.d](milestones/M05.md#step-5-d)

<a id="step-5-e"></a>[5.e](milestones/M05.md#step-5-e)

<a id="step-5-f"></a>[5.f](milestones/M05.md#step-5-f)

<a id="step-5-g"></a>[5.g](milestones/M05.md#step-5-g)

<a id="step-5-h"></a>[5.h](milestones/M05.md#step-5-h)

<a id="step-5-i"></a>[5.i](milestones/M05.md#step-5-i)

<a id="step-5-j"></a>[5.j](milestones/M05.md#step-5-j)

<a id="step-5-k"></a>[5.k](milestones/M05.md#step-5-k)

<a id="step-5-l"></a>[5.l](milestones/M05.md#step-5-l)

<a id="step-5-m"></a>[5.m](milestones/M05.md#step-5-m)

<a id="step-5-n"></a>[5.n](milestones/M05.md#step-5-n)

<a id="step-5-o"></a>[5.o](milestones/M05.md#step-5-o)

<a id="step-5-p"></a>[5.p](milestones/M05.md#step-5-p)

<a id="step-5-q"></a>[5.q](milestones/M05.md#step-5-q)

<a id="step-5-r"></a>[5.r](milestones/M05.md#step-5-r)

<a id="step-5-s"></a>[5.s](milestones/M05.md#step-5-s)

<a id="step-5-t"></a>[5.t](milestones/M05.md#step-5-t)

<a id="step-5-u"></a>[5.u](milestones/M05.md#step-5-u)

<a id="step-5-v"></a>[5.v](milestones/M05.md#step-5-v)

<a id="step-6-a"></a>[6.a](milestones/M06.md#step-6-a)

<a id="step-6-b"></a>[6.b](milestones/M06.md#step-6-b)

<a id="step-6-c"></a>[6.c](milestones/M06.md#step-6-c)

<a id="step-6-d"></a>[6.d](milestones/M06.md#step-6-d)

<a id="step-6-e"></a>[6.e](milestones/M06.md#step-6-e)

<a id="step-6-f"></a>[6.f](milestones/M06.md#step-6-f)

<a id="step-6-g"></a>[6.g](milestones/M06.md#step-6-g)

<a id="step-6-h"></a>[6.h](milestones/M06.md#step-6-h)

<a id="step-6-i"></a>[6.i](milestones/M06.md#step-6-i)

<a id="step-6-j"></a>[6.j](milestones/M06.md#step-6-j)

<a id="step-6-k"></a>[6.k](milestones/M06.md#step-6-k)

<a id="step-6-l"></a>[6.l](milestones/M06.md#step-6-l)

<a id="step-6-m"></a>[6.m](milestones/M06.md#step-6-m)

<a id="step-6-n"></a>[6.n](milestones/M06.md#step-6-n)

<a id="step-6-o"></a>[6.o](milestones/M06.md#step-6-o)

<a id="step-6-p"></a>[6.p](milestones/M06.md#step-6-p)

<a id="step-6-q"></a>[6.q](milestones/M06.md#step-6-q)

<a id="step-6-r"></a>[6.r](milestones/M06.md#step-6-r)

<a id="step-6-s"></a>[6.s](milestones/M06.md#step-6-s)

<a id="step-6-t"></a>[6.t](milestones/M06.md#step-6-t)

<a id="step-6-u"></a>[6.u](milestones/M06.md#step-6-u)

<a id="step-7-a"></a>[7.a](milestones/M07.md#step-7-a)

<a id="step-7-b"></a>[7.b](milestones/M07.md#step-7-b)

<a id="step-7-c"></a>[7.c](milestones/M07.md#step-7-c)

<a id="step-7-d"></a>[7.d](milestones/M07.md#step-7-d)

<a id="step-7-e"></a>[7.e](milestones/M07.md#step-7-e)

<a id="step-7-f"></a>[7.f](milestones/M07.md#step-7-f)

<a id="step-7-g"></a>[7.g](milestones/M07.md#step-7-g)

<a id="step-7-h"></a>[7.h](milestones/M07.md#step-7-h)

<a id="step-7-i"></a>[7.i](milestones/M07.md#step-7-i)

<a id="step-7-j"></a>[7.j](milestones/M07.md#step-7-j)

<a id="step-7-k"></a>[7.k](milestones/M07.md#step-7-k)

<a id="step-7-l"></a>[7.l](milestones/M07.md#step-7-l)

<a id="step-8-a"></a>[8.a](milestones/M08.md#step-8-a)

<a id="step-8-b"></a>[8.b](milestones/M08.md#step-8-b)

<a id="step-8-c"></a>[8.c](milestones/M08.md#step-8-c)

<a id="step-8-d"></a>[8.d](milestones/M08.md#step-8-d)

<a id="step-8-e"></a>[8.e](milestones/M08.md#step-8-e)

<a id="step-8-f"></a>[8.f](milestones/M08.md#step-8-f)

<a id="step-8-g"></a>[8.g](milestones/M08.md#step-8-g)

<a id="step-8-h"></a>[8.h](milestones/M08.md#step-8-h)

<a id="step-8-i"></a>[8.i](milestones/M08.md#step-8-i)

<a id="step-8-j"></a>[8.j](milestones/M08.md#step-8-j)

<a id="step-8-k"></a>[8.k](milestones/M08.md#step-8-k)

<a id="step-8-l"></a>[8.l](milestones/M08.md#step-8-l)

<a id="step-9-a"></a>[9.a](milestones/M09.md#step-9-a)

<a id="step-9-b"></a>[9.b](milestones/M09.md#step-9-b)

<a id="step-9-c"></a>[9.c](milestones/M09.md#step-9-c)

<a id="step-9-d"></a>[9.d](milestones/M09.md#step-9-d)

<a id="step-9-e"></a>[9.e](milestones/M09.md#step-9-e)

<a id="step-9-f"></a>[9.f](milestones/M09.md#step-9-f)

<a id="step-9-g"></a>[9.g](milestones/M09.md#step-9-g)

<a id="step-9-h"></a>[9.h](milestones/M09.md#step-9-h)

<a id="step-10-a"></a>[10.a](milestones/M10.md#step-10-a)

<a id="step-10-b"></a>[10.b](milestones/M10.md#step-10-b)

<a id="step-10-c"></a>[10.c](milestones/M10.md#step-10-c)

<a id="step-10-d"></a>[10.d](milestones/M10.md#step-10-d)

<a id="step-10-e"></a>[10.e](milestones/M10.md#step-10-e)

<a id="step-10-f"></a>[10.f](milestones/M10.md#step-10-f)

<a id="step-10-g"></a>[10.g](milestones/M10.md#step-10-g)

<a id="step-10-h"></a>[10.h](milestones/M10.md#step-10-h)

<a id="step-10-i"></a>[10.i](milestones/M10.md#step-10-i)

<a id="step-11-a"></a>[11.a](milestones/M11.md#step-11-a)

<a id="step-11-b"></a>[11.b](milestones/M11.md#step-11-b)

<a id="step-11-c"></a>[11.c](milestones/M11.md#step-11-c)

<a id="step-11-d"></a>[11.d](milestones/M11.md#step-11-d)

<a id="step-11-e"></a>[11.e](milestones/M11.md#step-11-e)

<a id="step-11-f"></a>[11.f](milestones/M11.md#step-11-f)

<a id="step-11-g"></a>[11.g](milestones/M11.md#step-11-g)

<a id="step-11-h"></a>[11.h](milestones/M11.md#step-11-h)

<a id="step-11-i"></a>[11.i](milestones/M11.md#step-11-i)

<a id="step-11-j"></a>[11.j](milestones/M11.md#step-11-j)

<a id="step-11-k"></a>[11.k](milestones/M11.md#step-11-k)

<a id="step-11-l"></a>[11.l](milestones/M11.md#step-11-l)

<a id="step-11-m"></a>[11.m](milestones/M11.md#step-11-m)

<a id="step-11-n"></a>[11.n](milestones/M11.md#step-11-n)

<a id="step-11-o"></a>[11.o](milestones/M11.md#step-11-o)

<a id="step-11-p"></a>[11.p](milestones/M11.md#step-11-p)

<a id="step-11-q"></a>[11.q](milestones/M11.md#step-11-q)

<a id="step-11-r"></a>[11.r](milestones/M11.md#step-11-r)

<a id="step-12-a"></a>[12.a](milestones/M12.md#step-12-a)

<a id="step-12-b"></a>[12.b](milestones/M12.md#step-12-b)

<a id="step-12-c"></a>[12.c](milestones/M12.md#step-12-c)

<a id="step-12-d"></a>[12.d](milestones/M12.md#step-12-d)

<a id="step-12-e"></a>[12.e](milestones/M12.md#step-12-e)

<a id="step-12-f"></a>[12.f](milestones/M12.md#step-12-f)

<a id="step-12-g"></a>[12.g](milestones/M12.md#step-12-g)

<a id="step-12-h"></a>[12.h](milestones/M12.md#step-12-h)

<a id="step-12-i"></a>[12.i](milestones/M12.md#step-12-i)

<a id="step-12-j"></a>[12.j](milestones/M12.md#step-12-j)

<a id="step-12-k"></a>[12.k](milestones/M12.md#step-12-k)

<a id="step-12-l"></a>[12.l](milestones/M12.md#step-12-l)

<a id="step-12-m"></a>[12.m](milestones/M12.md#step-12-m)

<a id="step-12-n"></a>[12.n](milestones/M12.md#step-12-n)

<a id="step-12-o"></a>[12.o](milestones/M12.md#step-12-o)

<a id="step-12-p"></a>[12.p](milestones/M12.md#step-12-p)

<a id="step-12-q"></a>[12.q](milestones/M12.md#step-12-q)

<a id="step-12-r"></a>[12.r](milestones/M12.md#step-12-r)

<a id="step-12-s"></a>[12.s](milestones/M12.md#step-12-s)

<a id="step-12-t"></a>[12.t](milestones/M12.md#step-12-t)

<a id="step-13-a"></a>[13.a](milestones/M13.md#step-13-a)

<a id="step-13-b"></a>[13.b](milestones/M13.md#step-13-b)

<a id="step-13-c"></a>[13.c](milestones/M13.md#step-13-c)

<a id="step-13-d"></a>[13.d](milestones/M13.md#step-13-d)

<a id="step-13-e"></a>[13.e](milestones/M13.md#step-13-e)

<a id="step-13-f"></a>[13.f](milestones/M13.md#step-13-f)

<a id="step-13-g"></a>[13.g](milestones/M13.md#step-13-g)

<a id="step-13-h"></a>[13.h](milestones/M13.md#step-13-h)

<a id="step-14-a"></a>[14.a](milestones/M14.md#step-14-a)

<a id="step-14-b"></a>[14.b](milestones/M14.md#step-14-b)

<a id="step-14-c"></a>[14.c](milestones/M14.md#step-14-c)

<a id="step-14-d"></a>[14.d](milestones/M14.md#step-14-d)

<a id="step-14-e"></a>[14.e](milestones/M14.md#step-14-e)

<a id="step-14-f"></a>[14.f](milestones/M14.md#step-14-f)

<a id="step-14-g"></a>[14.g](milestones/M14.md#step-14-g)

<a id="step-14-h"></a>[14.h](milestones/M14.md#step-14-h)

<a id="step-14-i"></a>[14.i](milestones/M14.md#step-14-i)

<a id="step-14-j"></a>[14.j](milestones/M14.md#step-14-j)

<a id="step-14-k"></a>[14.k](milestones/M14.md#step-14-k)

<a id="step-14-l"></a>[14.l](milestones/M14.md#step-14-l)

<a id="step-14-m"></a>[14.m](milestones/M14.md#step-14-m)

<a id="step-14-n"></a>[14.n](milestones/M14.md#step-14-n)

<a id="step-14-o"></a>[14.o](milestones/M14.md#step-14-o)

<a id="step-15-a"></a>[15.a](milestones/M15.md#step-15-a)

<a id="step-15-b"></a>[15.b](milestones/M15.md#step-15-b)

<a id="step-15-c"></a>[15.c](milestones/M15.md#step-15-c)

<a id="step-15-d"></a>[15.d](milestones/M15.md#step-15-d)

<a id="step-15-e"></a>[15.e](milestones/M15.md#step-15-e)

<a id="step-15-f"></a>[15.f](milestones/M15.md#step-15-f)

<a id="step-15-g"></a>[15.g](milestones/M15.md#step-15-g)

<a id="step-15-h"></a>[15.h](milestones/M15.md#step-15-h)

<a id="step-15-i"></a>[15.i](milestones/M15.md#step-15-i)

<a id="step-15-j"></a>[15.j](milestones/M15.md#step-15-j)

<a id="step-15-k"></a>[15.k](milestones/M15.md#step-15-k)

<a id="step-15-l"></a>[15.l](milestones/M15.md#step-15-l)

<a id="step-15-m"></a>[15.m](milestones/M15.md#step-15-m)

<a id="step-15-n"></a>[15.n](milestones/M15.md#step-15-n)

<a id="step-15-o"></a>[15.o](milestones/M15.md#step-15-o)

<a id="step-16-a"></a>[16.a](milestones/M16.md#step-16-a)

<a id="step-16-b"></a>[16.b](milestones/M16.md#step-16-b)

<a id="step-16-c"></a>[16.c](milestones/M16.md#step-16-c)

<a id="step-16-d"></a>[16.d](milestones/M16.md#step-16-d)

<a id="step-16-e"></a>[16.e](milestones/M16.md#step-16-e)

<a id="step-16-f"></a>[16.f](milestones/M16.md#step-16-f)

<a id="step-16-g"></a>[16.g](milestones/M16.md#step-16-g)

<a id="step-16-h"></a>[16.h](milestones/M16.md#step-16-h)

<a id="step-16-i"></a>[16.i](milestones/M16.md#step-16-i)

<a id="step-16-j"></a>[16.j](milestones/M16.md#step-16-j)

<a id="step-16-k"></a>[16.k](milestones/M16.md#step-16-k)

<a id="step-17-a"></a>[17.a](milestones/M17.md#step-17-a)

<a id="step-17-b"></a>[17.b](milestones/M17.md#step-17-b)

<a id="step-17-c"></a>[17.c](milestones/M17.md#step-17-c)

<a id="step-17-d"></a>[17.d](milestones/M17.md#step-17-d)

<a id="step-17-e"></a>[17.e](milestones/M17.md#step-17-e)

<a id="step-17-f"></a>[17.f](milestones/M17.md#step-17-f)

<a id="step-17-g"></a>[17.g](milestones/M17.md#step-17-g)

<a id="step-17-h"></a>[17.h](milestones/M17.md#step-17-h)

<a id="step-17-i"></a>[17.i](milestones/M17.md#step-17-i)

<a id="step-17-j"></a>[17.j](milestones/M17.md#step-17-j)

<a id="step-17-k"></a>[17.k](milestones/M17.md#step-17-k)

<a id="step-17-l"></a>[17.l](milestones/M17.md#step-17-l)

<a id="step-18-a"></a>[18.a](milestones/M18.md#step-18-a)

<a id="step-18-b"></a>[18.b](milestones/M18.md#step-18-b)

<a id="step-18-c"></a>[18.c](milestones/M18.md#step-18-c)

<a id="step-18-d"></a>[18.d](milestones/M18.md#step-18-d)

<a id="step-18-e"></a>[18.e](milestones/M18.md#step-18-e)

<a id="step-18-f"></a>[18.f](milestones/M18.md#step-18-f)

<a id="step-18-g"></a>[18.g](milestones/M18.md#step-18-g)

<a id="step-18-h"></a>[18.h](milestones/M18.md#step-18-h)

<a id="step-18-i"></a>[18.i](milestones/M18.md#step-18-i)

<a id="step-18-j"></a>[18.j](milestones/M18.md#step-18-j)

<a id="step-18-k"></a>[18.k](milestones/M18.md#step-18-k)

<a id="step-18-l"></a>[18.l](milestones/M18.md#step-18-l)

<a id="step-18-m"></a>[18.m](milestones/M18.md#step-18-m)

<a id="step-18-n"></a>[18.n](milestones/M18.md#step-18-n)

<a id="step-18-o"></a>[18.o](milestones/M18.md#step-18-o)

<a id="step-18-p"></a>[18.p](milestones/M18.md#step-18-p)

<a id="step-18-q"></a>[18.q](milestones/M18.md#step-18-q)

<a id="step-18-r"></a>[18.r](milestones/M18.md#step-18-r)

<a id="step-19-a"></a>[19.a](milestones/M19.md#step-19-a)

<a id="step-19-b"></a>[19.b](milestones/M19.md#step-19-b)

<a id="step-19-c"></a>[19.c](milestones/M19.md#step-19-c)

<a id="step-19-d"></a>[19.d](milestones/M19.md#step-19-d)

<a id="step-19-e"></a>[19.e](milestones/M19.md#step-19-e)

<a id="step-19-f"></a>[19.f](milestones/M19.md#step-19-f)

<a id="step-19-g"></a>[19.g](milestones/M19.md#step-19-g)

<a id="step-19-h"></a>[19.h](milestones/M19.md#step-19-h)

<a id="step-19-i"></a>[19.i](milestones/M19.md#step-19-i)

<a id="step-19-j"></a>[19.j](milestones/M19.md#step-19-j)

<a id="step-19-k"></a>[19.k](milestones/M19.md#step-19-k)

<a id="step-19-l"></a>[19.l](milestones/M19.md#step-19-l)

<a id="step-19-m"></a>[19.m](milestones/M19.md#step-19-m)

<a id="step-19-n"></a>[19.n](milestones/M19.md#step-19-n)

<a id="step-19-o"></a>[19.o](milestones/M19.md#step-19-o)

<a id="step-19-p"></a>[19.p](milestones/M19.md#step-19-p)

<a id="step-19-q"></a>[19.q](milestones/M19.md#step-19-q)

<a id="step-19-r"></a>[19.r](milestones/M19.md#step-19-r)

<a id="step-19-s"></a>[19.s](milestones/M19.md#step-19-s)

<a id="step-19-t"></a>[19.t](milestones/M19.md#step-19-t)

<a id="step-19-u"></a>[19.u](milestones/M19.md#step-19-u)

<a id="step-19-v"></a>[19.v](milestones/M19.md#step-19-v)

<a id="step-19-w"></a>[19.w](milestones/M19.md#step-19-w)

<a id="step-19-x"></a>[19.x](milestones/M19.md#step-19-x)

<a id="step-19-y"></a>[19.y](milestones/M19.md#step-19-y)

<a id="step-20-a"></a>[20.a](milestones/M20.md#step-20-a)

<a id="step-20-b"></a>[20.b](milestones/M20.md#step-20-b)

<a id="step-20-c"></a>[20.c](milestones/M20.md#step-20-c)

<a id="step-20-d"></a>[20.d](milestones/M20.md#step-20-d)

<a id="step-20-e"></a>[20.e](milestones/M20.md#step-20-e)

<a id="step-20-f"></a>[20.f](milestones/M20.md#step-20-f)

<a id="step-20-g"></a>[20.g](milestones/M20.md#step-20-g)

<a id="step-20-h"></a>[20.h](milestones/M20.md#step-20-h)

<a id="step-20-i"></a>[20.i](milestones/M20.md#step-20-i)

<a id="step-20-j"></a>[20.j](milestones/M20.md#step-20-j)

<a id="step-20-k"></a>[20.k](milestones/M20.md#step-20-k)

<a id="step-20-l"></a>[20.l](milestones/M20.md#step-20-l)

<a id="step-20-m"></a>[20.m](milestones/M20.md#step-20-m)

<a id="step-20-n"></a>[20.n](milestones/M20.md#step-20-n)

<a id="audit-nacharbeiten"></a>[Audit-Nacharbeiten](audit/Audit_Nacharbeiten.md#audit-nacharbeiten)

Off-Plan-Erweiterung: [CONTROL-HANDOFF-REBASE](../development/Handoff_Rebase.md); keine zusätzliche Produktposition.

Aktive Präzisierung für 18.g: [PROPOSAL-CHECK-657](decisions/proposal-check-657.md).

Korrektur des Hostprofileingangs und vollständiger offener Rest: [Bundle 727](history/bundle-727-host-profile-storage.md).

Korrektur der Agententest-Aufträge und vollständiger offener Rest: [Bundle 728](history/bundle-728-agent-request-binding.md).
