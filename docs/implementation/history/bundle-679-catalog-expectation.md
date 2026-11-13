# Bundle 679 — unabhängige Katalogerwartung vervollständigen

13. November 2026. Quelle ist das native Fehler-Result 678 mit SHA-256
`ddf06deb8c742aaa77ed0adf504951bd6ff4ec306a57d366c682967c24c2c112`.
Der Lauf meldet 13932 bestandene Tests und einen Fehler bei 5649,15 Sekunden
pytest-Laufzeit. 18.k.W wurde nicht committed; R/C wurden nicht ausgebracht.
HEAD bleibt der bereits erfolgreiche Klärungscommit
`8af77c07279e1784a11de2809834723296940dc7`. Die W-Checkliste im erhaltenen
Arbeitsstand beschreibt weiterhin das vorbereitete Ziel, keinen bestätigten
Produktfortschritt.

## Ursache und Korrektur

Die Ergebnisregistrierung aus 678 funktioniert; der verbleibende Fehler liegt
in test_public_factory_inventory_equals_retrievable_catalog. Seine unabhängige,
explizite Liste öffentlich verfügbarer Ergebnisschemata enthält proposal-apply-v1
noch nicht. Der reale Katalog enthält dieses bereits in 10.3.6 spezifizierte und
implementierte Schema nun korrekt. Der Mengenvergleich meldet genau diese
zusätzliche ID.

Die Testliste wird um exakt proposal-apply-v1 ergänzt. Sie bleibt unabhängig
von der Produktregistrierung und wird nicht aus RESULT_IDS abgeleitet.
Gleichheits-, Anzahl-, Duplikat-, Metadaten-, vollständige Schema- und kanonische
Hashprüfungen bleiben unverändert. Weder unbekannte Schema-IDs noch fehlende
Katalogeinträge werden dadurch akzeptiert. Produktcode und alle bisherigen
Tests bleiben bis auf diesen einen Erwartungseintrag bytegleich zu den
jeweiligen angekündigten Ständen. Es gibt keine neue Spezifikationsklärung,
keine neue Testidentität und keine Änderung an Budgets oder Testgates.

## Erhaltener vollständiger Rest

Die ursprünglichen Implementierungszustände 18.k.W, 18.k.R und 18.k.C bleiben
mit IDs, Nachrichten, Rollen implementation, Scope und Abnahmen erhalten.
Sämtliche Korrekturen aus 675–678 bleiben enthalten. Der gesamte erhaltene
uncommittete W-Stand wird übernommen; erfolgreiche Commits werden nicht
wiederholt. Jede Stage hat vor ihrem Commit ein eigenes N=3-plus-Pflichtauswahl-
Gate. Erst danach wird die nächste Stage ausgebracht, niemals der Endstand
vorab. Die geänderte Testdatei und alle bisherigen Pflichtdateien bleiben
vollständig und ungefiltert enthalten; sämtliche vergebenen Testnummern und
noch offenen R-Testidentitäten bleiben unverändert.

Die bereits vorhandenen Katalogregressionen und tatsächlichen Proposal-Apply-,
Quorum-, Herkunfts-, Receipt-, Crash-/Recovery- und Retryabnahmen werden nicht
ersetzt oder verkürzt. Historische Berichte bleiben bytegleich. Vorbereitete
Planwerte gelten erst nach den jeweiligen erfolgreichen Apply-Gates; nach
18.k.C bleibt 18.l.W offen.

Dev prüft ausschließlich Syntax, reine Collection, stabile Katalog-/Stage-
bindungen und das native Paket. Keine Verhaltenstests, Fixtures oder Test-
Unterprozesse in Dev; eine erfolgreiche fachliche Abnahme bleibt Apply vorbehalten.
