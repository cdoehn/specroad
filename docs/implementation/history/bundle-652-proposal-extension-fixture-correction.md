# Bundle 652 — Extension-Testdaten und vollständiger 18.d-Rest

9. November 2026. Maßgeblich ist das native Fehler-Result
`498330ca770113905dda3ae5388cc363aaf73389f6b004de76bf750c98e0b5c4`,
HEAD `1011b828780b5b2db78e9074c3fa6dd818948df7`, Arbeitsfingerabdruck
`187adee2f8d9f4ed`. Der vollständige erhaltene Arbeitsstand entspricht dem
vorher angekündigten R-Zustand; seine neun uncommitteten Dateipfade bleiben
im ersten Commit-Scope. Die vollständigen Vorherbytes werden neu gebunden.

## Belegter Ausgang und Ursache

18.d.W wurde mit 8.131 bestandenen ausgewählten Tests committed. Bestätigt
sind deshalb 739/900 Planpositionen. R endete mit 22 fehlgeschlagenen und
7.951 bestandenen Tests; es entstand kein R-Commit. C wurde nicht ausgeführt.
Die im erhaltenen Arbeitsstand bereits vorbereiteten R-Fortschrittswerte
sind keine bestandene Abnahme. W wird nicht wiederholt.

Alle 22 Fehler liegen in den beiden Tiefenvarianten des Tests
`test_excluded_top_level_names_remain_content_at_every_nested_location`.
Die Testdaten verwendeten `test:projection` als Extension-Namespace. Nach
SR-REQ-0018 und dem vorhandenen `extensions_schema` muss der Name die Form
`<anbieter>.<name>` haben. Der native Validator wies die Daten mit
`schema_pattern` ab, bevor die beabsichtigte Hash-/Revisionsaussage erreichbar
war. Der Produktvalidator hat hier korrekt gearbeitet.

## Korrektur und unveränderte Abnahme

In den beiden betroffenen Datenstellen steht nun `test.projection`.
Der Zahlen-Grenzfall verwendet ebenso einen gültigen Namen `test.integer`,
damit seine Vorbereitung ausschließlich den beabsichtigten Zahlenfehler
enthält. Testnamen, Parametervarianten, sämtliche Assertions und erwarteten
Fehler bleiben unverändert. Die 22 Varianten prüfen weiterhin alle elf
ausgeschlossenen Top-Level-Namen sowohl innerhalb von Proposal-Extensions
als auch innerhalb von Operationsartefakten. Kein Validator wird umgangen
oder abgeschwächt, keine Fehlervariante entfernt, kein Produktverhalten geändert.

Das Bundle führt genau den belegten Rest mit den ursprünglichen IDs,
Commitnachrichten und Rollen fort: `18.d.R` und danach `18.d.C`, jeweils
`implementation`. R enthält die Testdatenkorrektur auf dem erhaltenen Stand;
C übernimmt das vollständige bereits angekündigte Projektionsrefactoring.
Der historische Vorbereitungsbeleg von Bundle 651 bleibt bytegleich zum
Fehlerstand; dieser neue Beleg erklärt dessen tatsächlichen Ausgang.
Die native `correction_of`-Bindung verweist auf den ursprünglichen Planhash
`57f65ec6e4f7c2835d29266ce4a2b36451f6e31a2c39298ce3dc1333b08590ce`.

Vorbereiteter R-Zustand: 740/900 und nächste Position 18.d.C gelten
erst nach erfolgreichem eigenem Gate und Commit; C bleibt offen.

Die bestehenden Requirement-Bindungen für SR-REQ-0643/0644 bleiben `partial`:
öffentliche Authoring-/Kontrollbefehle, menschliche Autorität und transaktionale
Publikation behalten ihre späteren Abnahmen. Neue Spezifikationsklärung ist
nicht erforderlich und in diesem Auftrag nicht freigegeben. Es gibt keine
Budgetänderung und keinen zusätzlichen Produktplanschritt.

Die vollständige geänderte Testdatei, alle W-/R-Fälle und die bisherige
Pflichtauswahl bleiben je Commit erhalten. Testnummern, Testauswahl-Policy und
Laufzeithistorie ändern sich nicht. Jede Stufe erhält vor dem Commit ihr eigenes
Apply-Gate aus fälliger gefilterter N=3-Gruppe und ungefilterter Pflichtunion.
Dev führt ausschließlich Syntax-, Collection- und native Paketprüfungen aus;
diese sind keine bestandenen Verhaltenstests. Nach atomarer Übergabe endet
der Auftrag ohne Apply-, Status- oder Warteschleife.
