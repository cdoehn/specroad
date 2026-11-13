# Negative Proposalentscheidungen

Der bestehende Befehl `proposal review` unterstützt `--decision withdrawn`
mit `--expected-revision`, explizitem menschlichem Actor und nichtleerem
`--comment`. Er zieht nur die eigene Zustimmung zur aktuellen Inhaltsbindung
zurück. Bei in_review bleibt der Status, bei approved endet die Fassung als
rejected. `--decision rejected` funktioniert zusätzlich bei draft/approved.
Die unveränderten Actor-, Request-, Dry-run- und Host-Evidence-Verträge gelten.

Neue negative Fälle verwenden versionierte v2-Inlinebelege; vorhandene
v1-Zeilen werden unverändert gelesen. Nicht der Berichtshash, sondern echte
Originale mit ihrem installierten Herkunftsverifier tragen die Prüfung.
Fehlende oder inzwischen ungültige aktuelle Qualifikation wird nicht durch
Statuskorrekturen umgangen. Ein Widerruf kann eine alte menschliche Entscheidung
festhalten, aber weder fremde Zustimmung löschen noch Schreibrechte erzeugen.

Normativ: Spezifikation 10.3.5. Tests: test_proposal_negative und
test_proposal_negative_right; Ausführung ausschließlich in Apply. Die
öffentliche Apply-Transaktion gehört weiterhin zum folgenden Planschritt 18.k.
