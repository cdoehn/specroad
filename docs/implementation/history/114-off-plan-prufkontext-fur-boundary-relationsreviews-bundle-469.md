# OFF-PLAN – Prüfkontext für Boundary-Relationsreviews (Bundle 469)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Prüfkontext für Boundary-Relationsreviews (Bundle 469)

Revision 19 dokumentiert **BOUNDARY-REVIEW-CONTEXT** gemäß ausdrücklicher
Nutzerentscheidung vom **25. Oktober 2026** und deren begrenzter
Ausgestaltung nach SPECROAD-DECISION-1. Spezifikation **0.2.24, E.3.2**,
legt die minimal nötigen hashgebundenen Originalzielbytes als getrennten
Prüfkontext fest; es entstehen keine zusätzlichen Scope-Mitglieder.
Entscheidungsbeleg, Alternativen und Abnahmen stehen bei **15.d.R**.

- [x] **BOUNDARY-REVIEW-CONTEXT:** Prüfkontext für Relationsreviews an Außenkanten verbindlich klären. Commit: `docs(spec): Prüfkontext für Boundary-Relationsreviews festlegen`.

**Übergabegrenze:** Genau ein OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und den notwendigen aktiven Spezifikationshashbindungen. Produktcode,
Tests, Oracles, Fixtures, Testnummern, Runner, Workflows und historische
Evidence bleiben unverändert. Der bestätigte Produktstand bleibt
**625/900**, zuletzt **15.d.W**, nächstens **15.d.R**. R und C bleiben
offen; der Dokumentcommit ist keine nominelle Produkt-W/R/C-Folge.
Die regulären Zwischenstände behalten ihre eigenen gezielten parallelen
Dev-Gates und commitgebundenen parallelen Apply-Gruppen.

Vor seinem Commit führt der Entrypoint ausschließlich die fällige
**Sequenz 174 / Gruppe 0/3** mit **6.873 Tests** und vier parallelen
Workern aus. Erst nach Erfolg setzt er den Offplan-Marker und die
Bundlenummer auf **469**. Fehler erhalten den tatsächlichen Zustand
und vorherige Commits. Die Übergabe erfolgt als `spec_clarification`;
die externe Apply-Steuerung übernimmt die ZIP. Kein Apply-/Test-Erfolg
wird vorweggenommen. Danach endet dieser Einzelauftrag; der offene
Planschritt wird gesondert beauftragt.

**Beobachtete gezielte Dev-Prüfungen.** Der abschließende Zustand besteht
**54/54** bestehende Verhaltenstests der maschinenlesbaren Katalog- und
Auswahlverträge in **9.27 s** mit **vier parallelen Workern**, Python
**3.14.4**, beobachtetem Prozessabschluss **0** und ausschließlich
`passed`-Outcomes. Ausgewählt wurden vollständig
`tests/test_catalog_check.py` und `tests/test_catalog_check_right.py`,
ausgeführt mit `tools/run_selected_tests.py --workers 4 --expected-tests 54`
in einem frischen ignorierten Berichtsverzeichnis. Dies prüft die von der
neuen Dokumenthashbindung betroffenen JSON-Verträge; es sind keine Tests
von Dokumentation, Formulierungen oder Darstellung.

Davor bestanden **1.042/1.042** gezielte bestehende Verhaltenstests in
**131.70 s** auf vier Workern. Sie decken Bundlecodec/-erzeugung/-prüfung,
Scope-Seeds/-Closure, Relationsreviewstatus, Konfiguration und Katalog ab.
Nach diesem Lauf wurde nur die normative Abgrenzung präzisiert, dass bereits
im ZIP erkannte doppelte Mitgliedsnamen/Pfadkollisionen unverändert Code 7
behalten; anschließend wurden alle aktiven Spezifikationshashbindungen
nachgeführt und die genannten 54 betroffenen Tests erneut ausgeführt.
Produktcode, Tests, Oracles, Fixtures und Testnummern blieben dabei bytegleich.
Die erste Quellbindung `f8a7170861364d9f5199b6a2edbb11c501267f066782ab2646c3eda046ae63e2`
ist ein eigener Zwischenstand, kein Ergebnis unter dem abschließenden Hash.
Sein Auswahlbericht-SHA-256 ist
`bc9cb43576f6c1ff885e961c0e4c0ae1b85c6899e8317fb4e8b9cab66171bdea`,
sein Einzeloutcomes-SHA-256
`cdbef0ccd482069e73c37563acd2d99e9c29c130fc2e6650ce7fb66becdaa1a2`.
Die erste Auswahl umfasste folgende vollständige Testdateien:

- `tests/test_bundle_verification.py`
- `tests/test_catalog_check.py`
- `tests/test_catalog_check_right.py`
- `tests/test_configuration_applicability.py`
- `tests/test_configuration_applicability_right.py`
- `tests/test_configuration_inheritance.py`
- `tests/test_configuration_inheritance_right.py`
- `tests/test_partial_bundle.py`
- `tests/test_partial_bundle_right.py`
- `tests/test_product_bundle.py`
- `tests/test_product_bundle_right.py`
- `tests/test_project_bundle.py`
- `tests/test_project_bundle_right.py`
- `tests/test_relation_review_status.py`
- `tests/test_relation_review_status_right.py`
- `tests/test_scope_closure.py`
- `tests/test_scope_closure_right.py`
- `tests/test_scope_seeds.py`
- `tests/test_scope_seeds_right.py`

Die abschließende vollständige Collection-/Katalogprüfung bestätigt
**20.617** unveränderte aktive Testidentitäten, keine Katalogfehler,
Exit **0** und **0 ausgeführte Testkörper**. Die **20.619** dauerhaft
reservierten Testnummern einschließlich zweier historisch entfernter
Identitäten bleiben unverändert. Die **743** aktiven Katalogdateien ändern
jeweils ausschließlich `specification_sha256`; historische Evidence bleibt
an ihren früheren Bytes gebunden. Zusammen mit Spezifikation und Plan enthält
das Bundle **745** geänderte Bestandsdateien und keine neue Produktdatei.

Abschließende Quellbindung:
`32372d164c776564207a2d28388ef26b58160aa300ff1d5b38569fdd131e3ebe`;
Katalogbindung: `2b359849c320db030fa6f57bd8198464d3f77a4787221788353f931575d46c05`;
Auswahlbericht-SHA-256:
`856b01d3567fc91c4ee88cf5ee42d2470d7c9b2fa5cb28d90ba67d42b5c78db5`;
Einzeloutcomes-SHA-256:
`25539f8dd38bd9107cf67827622016eda31970a901ee1b2c91ec249b128b81c5`.
Beide Dev-Läufe sind gezielte Teilprüfungen mit `full_suite_passed=null`;
keine vollständige oder serielle Testsuite wurde gestartet. Sie sichern
den unveränderten technischen Ausgangspunkt und die aktive Katalogbindung,
nicht die noch unimplementierte Prüfkontextfunktion. Der künftige parallele
Apply-Lauf und sein Commit werden nicht als bereits erfolgt behauptet.
