# OFF-PLAN RECOVERY-FIXTURE-533 — kleinere gültige Recovery-Testdaten

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN RECOVERY-FIXTURE-533 — kleinere gültige Recovery-Testdaten

Ausdrücklicher Nutzerauftrag vom 1. November 2026. Basis: erfolgreiches,
sauberes Result von Bundle 532, `specroad-apply_Result_021509_1101_f74f65.zip`,
SHA-256 `9db39accc99d140235a6a4549a9c06bd9967eaa5794da7c56e7b080d3f0aedee`,
Abschlusscommit `a4a7329f6d912d75d5af17cf7df0f64f1f4f6c0e`.
Ein vollständiger technischer OFF-PLAN-Testcommit; keine künstliche W/R/C-Folge.
Produktstand bleibt **655/900**, nächster Produktcommit **15.n.R**.

`small_restore_registry()` verwendet die bestehenden `registry_bytes()` und
`load_registry()` und den echten `LanguageRegistry`-Parser. Die ausdrücklich
synthetische Registry enthält genau `de`, `DE`, `en`, `GB`: Standardkonfiguration
`de-DE`, Baseline-Option `en-GB`. Ihre 346 Bytes (Version `2020-01-01`, SHA-256
`6139520dd6d9b32732e6893a20b9f6ee12734320f7e527a1d5600958fc474fcb`)
ersetzen gezielt die 777.560 Fixture-Bytes der Distributionsregistry.
`inspection_project()` und `restore_case()` erhalten einen optionalen Parameter
`language_registry`; ohne Parameter bleiben die vollständige Registry und alle
bisherigen Standardaufrufer unverändert. Profilkomposition, Konfigurationshash,
Versionsbindung und gespeicherte Registry-Datei verwenden dasselbe geprüfte
Objekt mit den vorhandenen nativen Funktionen. Projektbundle und Baseline
werden weiterhin nativ aus den tatsächlichen Fixture-Dateien erstellt.

Nur die vier Varianten von
`test_planning_work_keeps_exact_original_and_delivers_full_plan` und die
Recovery-Befehlsbeispiele in `_restore_example_inputs()` wählen explizit die
kleine Registry. Parametrisierung, Testidentitäten, vollständige
Fortsetzungsschleife, Fortschrittsprüfung pro Fortsetzung, native Planprüfung,
byteidentische Ergebnisse, unverändertes Ursprungsprojekt, Entfernen der Quelle
und schreibfreies Wiedergeben des abgeschlossenen Ergebnisses bleiben erhalten.
Die bestehenden Blockgrenzentests (zwei vollständige Blöcke plus Rest) und die
gezielten Tests der vollständigen Distributionsregistry bleiben unverändert.
Keine Produkt-, Spezifikations-, Blockgrößen-, Sicherheits-, Control-, Watcher-,
CI-, Rotations- oder Ausschlussregeländerung; keine neuen Tests oder Testnummern.

**Beobachteter Zeitvergleich, Sekunden mit einer Nachkommastelle:**

| Variante | nativ deklarierte Work-Einheiten vorher → nachher | historisch | aktuell | Ergebnis |
|---|---|---:|---:|---|
| alle veröffentlichten Befehlsbeispiele | — (Befehlssammeltest) | 624.5 | 48.3 | bestanden |
| argv-baseline | 49 → 27 | 2134.4 | 740.7 | bestanden |
| argv-project_bundle | 42 → 20 | 1605.5 | 344.2 | bestanden |
| mapping-baseline | 49 → 27 | 2142.7 | 745.4 | bestanden |
| mapping-project_bundle | 42 → 20 | 1690.2 | 352.9 | bestanden |

Die historischen Vergleichswerte stammen aus dem vollständig erfolgreichen
Dev-Lauf für Bundle 532 (CPython 3.14.4, zwölf Worker, Quellbindung
`e05cfc922d1854b8c3c114640f17d5ef31e6b4706f1f4b1df9dea786c944afa4`).
Der aktuelle Lauf nutzt CPython 3.14.4, vier worksteal-Worker. Die Tabellenzeiten
sind jeweils Setup + Call + Teardown aus derselben dauerhaften Exchange-
Messdatenbank. Andere Parallelität und unbekannte damalige Rechnerlast:
**kein kontrollierter Benchmark und keine garantierte Beschleunigungsquote**.
Der teure Altstand wurde nicht erneut ausgeführt. Die Work-Zahlen stammen aus
den nativen Capture-Deklarationen derselben tatsächlichen alten/neuen Fixtures;
alle jeweils deklarierten Einheiten werden im unveränderten Test durchlaufen.

**Lokale Abnahme:** zuerst die vier Varianten, danach die übrigen 363 betroffenen
Recovery-, Beispiel-, Registry-Bindungs-, Profil- und Capture-Tests, ohne
überlappende Gates oder erneute Ausführung der vier Varianten. **367 bestanden**,
beide Läufe Exit 0, vier worksteal-Worker; 1.101 erfolgreiche Phasen dauerhaft
in der bestehenden Messhistorie, keine zweite Messdatenbank. Vollständige
Collection: 22.718 unveränderte Testidentitäten, Katalog gültig, keine Testkörper
bei der Collection. Testkatalog, Nummerierung und historische Baseline bleiben
byteidentisch. Dies ist ein gezielter Teiltestnachweis, keine Vollsuite oder CI.

Geprüfte Quellbindung: `72f23fe85a125f91432629da875b118c13c74694253d131c22a1eea0f38027b8`.
first-four: 4 Tests, Abschluss `2026-11-01T07:48:53.407756+00:00`, Auswahl-SHA-256 `d6886be46010a820b225f6178add78cd250d7029d4617ec9534d161413710c4e`, Beobachtungs-SHA-256 `3eee63b2a569c11eba52c4e7955b75b231e13b13a46b842a154d99f2bb577e2a`.
regressions: 363 Tests, Abschluss `2026-11-01T07:58:05.741049+00:00`, Auswahl-SHA-256 `3392272ac24eee80f30b6eab0abef918b3fb1c45f359c2eb30100ccd02cee1e0`, Beobachtungs-SHA-256 `6412191f43d85fe5251f2c91d70c4f554674f96f3edfc88134a26fe9a5009332`.

Apply prüft unverändert seine fällige N=3-Gruppe 1 (Commitsequenz 244) mit der
aktuellen Laufzeitfilterung, bevor der einzige OFF-PLAN-Commit entsteht.
Die aktualisierten Zeiten wirken bereits beim nächsten regulären Auswahlsnapshot;
kein Eingriff in Auswahlpolicy oder Historie. Commit:
`OFF-PLAN RECOVERY-FIXTURE-533 perf(tests): Recovery-Testdaten gezielt verkleinern`.
Apply-Abschluss RECOVERY-FIXTURE-533: fällige Gruppe bestanden; Bundle 533 abgeschlossen.
