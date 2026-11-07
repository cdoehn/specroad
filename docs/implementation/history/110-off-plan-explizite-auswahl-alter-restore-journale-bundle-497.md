# OFF-PLAN – Explizite Auswahl alter Restore-Journale (Bundle 497)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Explizite Auswahl alter Restore-Journale (Bundle 497)

Revision 25 dokumentiert **RESTORE-JOURNAL-SELECTION**, ausdrücklich manuell
beauftragt am **26. Oktober 2026**. Spezifikation **0.2.30 / 10.7.4** bindet
die betroffene alte aktive Journalmenge an eine aktuell autorisierte
Pfad-/Hashliste. Entscheidungsbeleg, Alternativen, Grenzen und offene
Verhaltensabnahmen stehen bei **15.l.W**. Der bestätigte reguläre Stand bleibt
**648/900**, zuletzt **15.k.C**, nächstens **15.l.W**.

- [x] **RESTORE-JOURNAL-SELECTION:** Betroffene Restore-Journale explizit binden.
  Commit: `docs(spec): Betroffene Restore-Journale explizit binden`.

Der vorherige N-Durchlauf erzeugte kein Bundle. Dieser zusätzliche manuelle
OFF-PLAN-Auftrag nach 2.4.3 ersetzt für diese konkrete Übergabe die dortige
Ablehnung einer weiteren automatischen Klärung. Er ändert weder den
gespeicherten Control-Vertrag noch dessen automatisches Klärungsbudget.
Das Bundle wird ehrlich als `spec_clarification` übergeben.

Dies ist ein echter OFF-PLAN-Dokumentcommit. Produktcode, Tests, Fixtures,
Oracles, Testnummern, Runner, Workflows und historische Evidence bleiben
bytegleich. Geändert werden Spezifikation, Plan und ausschließlich die
aktiven Spezifikationshashfelder der **743** Katalogdateien. Es entstehen
keine künstlichen Produkt-W/R/C-Commits oder vorgezogenen Produktabnahmen.
Die echte W/R/C-Folge des offenen 15.l bleibt unverändert beauftragt.

Vor diesem Dokumentcommit prüft der externe Entrypoint genau **Sequenz 203 /
Gruppe 2 von 3**, **7.202 Tests**, mit vier parallelen Workern. Erst nach
Erfolg setzt er den Offplan-Marker und die Bundle-Nummer **497**. Produktzähler
und offene 15.l.W/R/C-Checkboxen bleiben unverändert. Fehler erhalten den
tatsächlichen Zustand und vorherige Commits. Der Auftrag endet nach nativer
ZIP-Prüfung und atomarer Exchange-Veröffentlichung.

**Beobachtete gezielte Dev-Prüfung.** Die Dokument- und Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.56 s**, mit **vier
parallelen Workern**, CPython **3.14.4**, Exit **0** und ausschließlich
`passed`-Einzeloutcomes. Ausgeführt wurde `tools/run_selected_tests.py
--workers 4 --expected-tests 54` mit den beiden genannten vollständigen
Dateien in einem frischen ignorierten Berichtsroot. Geprüft werden die von
der Spezifikationshashbindung betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentation, Darstellung oder noch nicht
implementierte Restore-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **21.604** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **21.608** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`172ac9c7443375f885a013ed9d056c8cc22695bf8cf64520958ddba8d024b25f`;
Katalogvertrag-SHA-256:
`23099b468b9fd9620c9af13828380a676e817301b91702d5b8986783b8f85ee4`;
Auswahlbericht-SHA-256:
`53a2f15b8b5349e2fc4c62d3782a83c894ff30c61560647001540a4649b3c86b`;
Einzeloutcomes-SHA-256:
`d0aa0e6393a9cf9bc241e7975134b9f28c85aeb728ef68a28ea7d538a5929177`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Der bestätigte vorherige Apply-Nachweis für OFF-PLAN
RESTORE-EXECUTION-CONTRACT ist davon getrennt:
Auswahlbindungs-SHA-256 `165abfc48a06705ccd2f8c9fc000f32aa498c4023ebf11962c2b906455c21ff9`,
Bericht-SHA-256 `53abf1e576d195f3e2dc172bfd1ec4641a5b85a4bb6c5ef4b6da7e09ec1f850d` und
Einzeloutcomes-SHA-256 `4714da58ab0fdbaaab89bfad93147cda6444dd660932defd002c22ec1f7310cb`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.W bleibt offen.
