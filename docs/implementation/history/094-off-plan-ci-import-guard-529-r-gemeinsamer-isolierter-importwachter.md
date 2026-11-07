# OFF-PLAN CI-IMPORT-GUARD-529.R — gemeinsamer isolierter Importwächter

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CI-IMPORT-GUARD-529.R — gemeinsamer isolierter Importwächter

Ausdrücklicher Nutzerauftrag vom 31. Oktober 2026: die diagnostizierten
CPython-3.11-Fehler beheben und den mehrfach vorhandenen Importwächter in
einem gemeinsamen Testhelfer zusammenführen; Übergabe als Korrekturbundle.
Technische Basis ist das erfolgreiche, saubere Result von Bundle 528:
`specroad-apply_Result_174314_1031_ef35d5.zip`, SHA-256
`ea7a065082993169b399e9e4215edf43348261856efd5437422b86f9033d2186`,
Abschlusscommit `191af0702780d613262ce454b1271dfca392b631`.
Seine 6.075 Apply-Tests waren erfolgreich; die nächste fällige Gruppe ist 1.

Der tatsächliche manuelle GitHub-Lauf 41217093825, Job 124584106419
(CPython 3.11.17 / Paket 0), prüfte Commit
`52615c8543107dd3522411c0c3f76068686f6b28`: 4.449 bestanden, zwei
fehlgeschlagen. Beide Core-Fälle in `test_code_reference_sources.py` und
`test_code_reference_state_right.py` scheiterten mit `AssertionError` beim
Import von `org`. Die Python-3.11-Standardbibliothek `copy` versucht optional
`from org.python.core import PyStringMap` und behandelt das Fehlen durch
`except ImportError`. Der Testwächter ersetzte diesen normalen Fehlpfad
fälschlich durch einen nicht abgefangenen `AssertionError`.

Ein einzelner technischer Korrekturcommit zentralisiert den Wächter aus
allen sechs betroffenen Testdateien in `tests/support/import_guards.py`.
Er liefert gemeinsamen Quelltext für die weiterhin isolierten Kindprozesse,
ohne dort das Testpaket oder dessen Abhängigkeiten zu laden. Genau der
optionale Rootimport `org` meldet `ModuleNotFoundError`; er wird niemals
von einem vorhandenen Fremdpaket geladen. Jeder andere Nicht-Core-/Nicht-
Standardbibliotheksimport bleibt ein harter Fehler, auch innerhalb eines
`except ImportError`. Die bestehenden fachlichen Prüfungen und
Datei-/Prozess-/Netzwerk-Wächter bleiben erhalten. Keine Produkt-,
Spezifikations-, Workflow- oder Controländerung; Produktstand 654/900,
15.n.W bleibt offen. Historische CI-Belege werden nicht überschrieben.

Abnahme: vorhandene Core-/PYZ-Tests der sechs Nutzer des gemeinsamen
Helfers; zusätzlich echte frische Prozesse mit fehlendem `org`, einem
vorhandenen `org.py` und einem vorhandenen `org`-Paket, ohne Ausführung
fremden Codes. Andere fremde Namen, einschließlich `organization_probe`,
müssen unabhängig von ihrer Verfügbarkeit hart scheitern und dürfen
nicht durch optionale Importfehlerbehandlung verschwinden. Vollständige
Collection und unveränderte bisherige Testnummern; neue Nummern nur hinten.
Gezielte Dev-Ausführung parallel mit vier worksteal-Workern und sofortiger
Laufzeitpersistenz. Apply prüft seine aktuelle N=3-Gruppe vor dem Commit.
Die echte Python-Matrix bleibt ein separater manueller CI-Nachweis.

Lokaler Testnachweis CI-IMPORT-GUARD-529: **467 Tests bestanden**, Exit 0,
CPython 3.14.4, vier worksteal-Worker; Abschluss `2026-10-31T17:55:21.773173+00:00`.
Darunter die vorhandenen Core-/PYZ-Verhaltensfälle und sieben neue
Importgrenzfälle. Vollständige Collection: 22.624 Tests, Katalog gültig,
keine Testkörper während der Collection. Alle bisherigen Nummern bleiben
erhalten; sieben neue Nummern werden angehängt. Gemeinsame Messhistorie:
467 vollständig gültige Versuche mit 1.401 erfolgreichen Phasen.
Quellbindung `c2ffcf1362eb6a3fea72a0517b2b1f5a900703bd43a8ba161a0577256f99ff17`;
Auswahlbeleg `c3ff6f8e72660d5d391ec1af8e6c9ab53113e3233bad5ddea66c008d88fa9e52`,
Beobachtungsbeleg `bef30b442bb532b6e6082179b96d07a24c3bf128cc4ac29acdcf0766d9ceda33`,
Katalogbeleg `731463ecf8fad84d13f79ca76072ab146c813c1c5806bd96b95530e6d924bc2b`.
Der lokale Nachweis ist kein erneuter CPython-3.11-CI-Erfolg; die
versionsspezifische Vollmatrix bleibt ausdrücklich manuell.
Commit nach Apply: `OFF-PLAN CI-IMPORT-GUARD-529.R fix(tests): isolierten Importwächter zentralisieren und Jython-Probe korrekt sperren`.
Apply-Abschluss CI-IMPORT-GUARD-529: fällige Gruppe bestanden; Bundle 529 abgeschlossen.
