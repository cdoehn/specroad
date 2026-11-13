# Bundle 676 — Proposal-Schemata und Registrierungsabnahmen korrigieren

13. November 2026. Quelle ist das native Fehler-Result 675 mit SHA-256
`631877e888fa07cd4230f9be16c5d41052061366a23c7bdd775f5541cba41356`.
Der Apply-Lauf erreichte nach der Laufprofilkorrektur die Verhaltenstests:
11534 bestanden, 17 schlugen fehl; pytest meldet 4090,49 Sekunden.
18.k.W wurde nicht committed. HEAD bleibt der bereits erfolgreiche
Klärungscommit `8af77c07279e1784a11de2809834723296940dc7`.
R/C wurden nicht ausgebracht. Die W-Checkliste im erhaltenen Fehlerstand
bezeichnet das vorbereitete Ziel, keinen bestätigten Produktfortschritt.

## Ursache und Korrektur

Der bereits freigegebene Vertrag 10.3.6 verlangt beim nativen Proposal-Apply
`proposal_status=applied` und `maturity=applied`. Die gemeinsame Feldprüfung
lehnt diesen Reifezustand bisher ab; der passive Recordvertrag kennt nur das
ältere Paar applied/approved. Dadurch scheitert die Zielvorbereitung mit
`schema_enum` vor der Publikation. Auch öffentliche Beispiele und Schema-
Integrationen erreichen deshalb nicht ihren erwarteten Abschluss.

Die gemeinsame Feldprüfung ergänzt applied ausschließlich für Proposals.
Der Recordvertrag akzeptiert zusätzlich das neue Paar applied/applied;
die ältere gespeicherte Darstellung bleibt gemäß der bestehenden passiven
Kompatibilitätsabnahme byteerhaltend lesbar. Andere Status-/Reifepaare bleiben
abgewiesen. Weder Format erteilt durch Lesen Schreibautorität, Freigabe oder
Publikationsnachweis. Native Apply-Reduktion und Abschlussprüfung binden weiter
exakt das neue Ziel und wirkliche Receipts. Generische Schreibwege bleiben
für beide terminalen Darstellungen gesperrt. Es gibt keine neue fachliche
Detailentscheidung und keine Änderung an Spezifikation oder Klärungsbudget.

Drei alte Registrierungsannahmen in Capability-/Requesttests behandeln
proposal.apply noch als nicht implementiert. Sie werden auf die tatsächlich
vorbereitete normative Schreiboperation mit proposal-apply-v1 aktualisiert.
Die bisherigen unbekannten Befehle, passiven Schema-Grenzen, exakten übrigen
Befehlsverträge und ausführbaren öffentlichen Beispielprüfungen bleiben.

## Erhaltene Abdeckung und offene Folge

Eine neue Regression liest die gemeinsame native Artefakthülle für alle
28 Typen und prüft die Proposal-exklusive Erweiterung. Bestehende Recordtests
decken sämtliche Proposal-Status-/Reife-Kombinationen, die byteerhaltende
Lektüre beider applied-Darstellungen und die weiterhin gesperrten generischen
Mutationen ab. Alle bisherigen Proposal-Apply-, Herkunfts-, Quorum-, Receipt-,
Crash-/Recovery- und passiven Completiontests bleiben unverändert enthalten.
Die Laufprofilkorrektur aus 675 einschließlich aller vier Regressionen bleibt.

Die vollständige Folge 18.k.W, 18.k.R, 18.k.C behält ursprüngliche IDs,
Nachrichten, Rollen implementation und sämtliche Abnahmen. W umfasst auch alle
erhaltenen uncommitteten Dateien. Jede Stage wird erst nach eigenem erfolgreichem
N=3-plus-Pflichtauswahl-Gate committed; erst danach folgt der nächste Zustand.
Die Pflichtauswahl enthält alle ursprünglichen Dateien sowie die betroffenen
gemeinsamen Modell-/Schema-/Recordregressionen. Keine Auswahlverkürzung,
kein vorab installierter Endstand und keine Wiederholung erfolgreicher Commits.

Alle bereits vergebenen Testnummern bleiben erhalten. Die neue Regression
wird angehängt; danach folgen die noch nicht ausgebrachten R-Identitäten.
Historische Berichte bleiben bytegleich. Dieser Nachweis ergänzt 675 um dessen
beobachteten Testfehler und korrigiert keine vergangenen Ergebnisse.
Vorbereitete Fortschrittszähler gelten erst nach erfolgreichem Apply-Gate.

Dev prüft ausschließlich Syntax, reine Collection, Katalog-/Stagebindungen
und das native Paket. Keine Verhaltenstests, Fixtures oder Test-Unterprozesse
werden in Dev ausgeführt. Nach erfolgreichem 18.k.C bleibt 18.l.W offen.
