# Bundle 814 — Proposal-Aufruf und Force-Requestidentität

Das native Fehler-Result
`94a54609f67465b17bea13a42151d1a34d1fe958cce002cfa8d23cf56f195e72`
belegt den auf Nutzerauftrag unterbrochenen W-Testlauf von Bundle 813.
Pytest meldete 61 fehlgeschlagene Tests, 7.890 bestandene Hauptmeldungen und
52 Warnungen. Der Beobachtungsbericht zählt 7.889 erfolgreiche Testidentitäten,
61 fehlgeschlagene und 42 beim Abbruch noch laufende; ein fehlgeschlagener
unittest-Untertest darf trotz bestandener Hauptphasen keinen Erfolg begründen.
Das ist eine unvollständige Auswahl, kein bestandenes Gate. Kein Commit aus
813 entstand; HEAD bleibt `0520553c007e6edbf9237a81693d7e0da7be4d28`.
Der bereits erfolgreiche Klärungscommit FORCE-DOMAINS-812 bleibt erhalten.
Der vollständige offene Rest ist **21.e1.W/R/C**, jeweils Rolle implementation.

Die Fehleranalyse ergibt zwei Ursachen:

- 51 normale Proposal-Abnahmen oder deren abhängige Integration scheiterten,
  weil `apply_project` ein nur für Force bestimmtes `execution_binding` an
  `_apply` weitergab. Dessen normale Signatur erhält bereits die einzelnen
  gebundenen Werte und akzeptiert dieses zusätzliche Argument nicht. Die
  Korrektur entfernt ausschließlich das falsche Argument im normalen Aufruf;
  der Force-Aufruf behält seine vollständige Ausführungsbindung.
- Zehn Force-Abnahmen scheiterten bei der strikten JSON-Kanonisierung. Der
  native Adapter legte den typisierten `NormativeRequestId` direkt im passiven
  Plan ab. Er verwendet jetzt nach derselben unveränderten Eingabevalidierung
  dessen exakten Textwert oder null. Plan, Requestbeleg, Writervergleich und
  historische Wiederholung erhalten dadurch dieselbe Identität; keine
  Umbenennung, Lockerung der JSON-Typen oder Übernahme fremder Requests.

Die Meldung `gw33 invalid test_description` gehört zum fehlgeschlagenen
Untertest `command='proposal.apply'` in
`DescriptionWorkTests.test_each_published_example_runs_the_actual_command`.
Dieser führt das veröffentlichte native Befehlsbeispiel tatsächlich aus und
erhielt `CORE_INTERNAL`/Exit 4 statt Erfolg. Der Laufzeitschreiber markiert
einen fehlgeschlagenen Untertest als ungültig, auch wenn unittest für die
drei Hauptphasen passed meldet. Das ist keine beschädigte Testbeschreibung
und kein Anlass, den Laufzeitbeleg nachträglich als bestanden zu markieren.

Die vollständigen bisherigen Test-IDs, Pflichtauswahlen und Oracles bleiben.
Drei zusätzliche native Fälle prüfen Text-, typisierte und fehlende Request-ID
über Dry-run und echte Publikation; vorhandene IDs werden unverändert und
ohne zweite Änderung aus ihren Originalbelegen wiederholt. Sämtliche
beobachteten Fehlerdateien einschließlich Beschreibung, Schema, Proposal,
Transport und realer Python-/Distributionsmatrix bleiben Pflichtauswahl.
Die Korrektur wird in W eingeführt und in R/C mitgeführt. Jede Stage behält
ihr eigenes N=3-plus-Pflichtauswahl-Gate vor ihrem Commit. Ungeprüfte oder
unterbrochene Versuche sind keine Erfolge; die Laufzeithistorie bleibt erhalten.

Keine neue Detailentscheidung und kein neuer Klärungscommit sind erforderlich.
Spezifikation 0.2.108, vollständiger fachlicher Scope und genehmigte Aufteilung
bleiben unverändert. Neue Ressourcenmessungen bleiben bis zur finalen Abnahme
aufgeschoben, der finale Nachweis pending; Originalmessungen bleiben bytegleich.
Dev führt nur statische Prüfung, reine Collection und native Paketvalidierung
aus. Die Zielzähler 901/902/903 von 999 gelten erst nach dem jeweiligen Gate;
21.e2.W samt Gesamtintegration und alle menschlichen Endabnahmen bleiben offen.
