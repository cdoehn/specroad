# OFF-PLAN – Gebundener Restore-Plan (Bundle 489)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Gebundener Restore-Plan (Bundle 489)

Revision 23 dokumentiert **RESTORE-PLAN-CONTRACT**, delegiert gemäß
**SPECROAD-DECISION-1**. Spezifikation **0.2.28 / 10.7.2** präzisiert die
bereits geforderte Restoreplanhülle und ihre Byte-/Inventur-/Hashbindungen.
Entscheidungsbeleg, Alternativen, Grenzen und verbindliche offene Abnahmen
stehen bei **15.j.W**. Der reguläre Stand bleibt **642/900**, zuletzt
**15.i.C**, nächstens **15.j.W**.

- [x] **RESTORE-PLAN-CONTRACT:** Restoreplanformat verbindlich festlegen.
  Commit: `docs(spec): Gebundenen Restoreplanvertrag festlegen`.

Dies ist gemäß 2.4.3 ein echter OFF-PLAN-Dokumentcommit; es entstehen keine
künstlichen Produkt-W/R/C-Commits. Produktcode, Tests, Fixtures, Oracles,
Testnummern, Runner, Workflows und historische Evidence bleiben bytegleich.
Geändert werden Spezifikation, Plan und ausschließlich die aktiven
Spezifikationshashfelder der **743** Katalogdateien. Es wird keine
implementierte Restorefunktion oder erfüllte Produktabnahme behauptet.

Vor seinem Commit prüft der externe Entrypoint genau **Sequenz 195 /
Gruppe 0 von 3**, **7.139 Tests**, mit vier parallelen Workern. Erst nach
Erfolg setzt er den Offplan-Marker und die Bundle-Nummer **489**. Der
Produktzähler und sämtliche offenen 15.j–15.l-Checkboxen bleiben unverändert.
Fehler erhalten den tatsächlichen Zustand und vorherige Commits. Nach
nativer ZIP-Prüfung und atomarer Exchange-Veröffentlichung endet der
Einzelauftrag mit `spec_clarification`; kein eigenes Apply, Result-Warten,
CI-Start, Statuspolling oder zweites Bundle aus demselben Result.

**Beobachtete gezielte Dev-Prüfung.** Die abschließende Dokument- und
Katalogfassung besteht **54/54** bestehende Verhaltenstests aus
`tests/test_catalog_check.py` und `tests/test_catalog_check_right.py` in
**6.74 s**, mit **vier parallelen Workern**, CPython **3.14.4**, Exit
**0** und ausschließlich `passed`-Einzeloutcomes. Ausgeführt wurde
`tools/run_selected_tests.py --workers 4 --expected-tests 54` mit den beiden
genannten vollständigen Dateien in einem frischen ignorierten Berichtsroot.
Geprüft werden die von der neuen Spezifikationshashbindung betroffenen
maschinenlesbaren Katalog- und Auswahlverträge; keine Dokumentation,
Darstellung oder noch nicht implementierte Restorefunktion.

Die vollständige Collection-/Katalogprüfung bestätigt **21.414** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **21.418** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`05c9ce32c0a86fec1a59203659e457f5e2b2c2ed845b3594df78c499e83fb5bd`;
Katalogvertrag-SHA-256:
`6d58a657318d2df41b12318f7fe0fe714ceff72065422aa90f2ae7a7557863d6`;
Auswahlbericht-SHA-256:
`822b17e1707b1f06e267770974cb0e2fa117e74c3c9f054b56b7fa1bca58763b`;
Einzeloutcomes-SHA-256:
`d0aa0e6393a9cf9bc241e7975134b9f28c85aeb728ef68a28ea7d538a5929177`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Ein früherer Dokumentstand bestand dieselben **54/54** Tests in **6.63 s**
auf vier Workern. Die anschließende Durchsicht präzisierte ausschließlich
die Unterscheidung zwischen normativen Erhaltungsobjekten und operativen
Receipts sowie den Feldvergleich mit der Zieldateiinventur. Danach wurden
alle aktiven Spezifikationshashbindungen nachgeführt und die betroffenen
54 Tests im oben ausgewiesenen abschließenden Zustand erneut geprüft.
Der frühere Quellhash
`0c276589aea4762f5ee8537940914940de49e20a1decc2de8db0d3f2983d94f4`,
Auswahlbericht-SHA-256 `79280efacb88c982ef9861ca606d33f460e34327f6fef8020d424e9e8a0c8dcd`
und Einzeloutcomes-SHA-256 `2523548005b347ffd66856d7068ea8b0de374a50c6508701ace2e6678f837185`
bleiben diesem früheren Zustand zugeordnet; sie werden nicht als
Prüfung unter dem abschließenden Quellhash umgedeutet.

Der bestätigte vorherige Apply-Nachweis ist davon getrennt:
Auswahlbindungs-SHA-256 `80234c01aa0945fef06d029e0518956dfe0d244f5751834355493b2fd47cc6bf`,
Bericht-SHA-256 `0db30616ab957cb3cf35918519fd1efd70dfbe0e3bdeb2909a6e0261630a958a` und
Einzeloutcomes-SHA-256 `85e107e7955768e0e09403e0d802c0fc66b957372870fb14d4f0ac8a20d5579a`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.j.W bleibt offen.
