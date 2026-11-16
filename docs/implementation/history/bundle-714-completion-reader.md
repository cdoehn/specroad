# Bundle 714 — gebundener Receipt-Reader, vollständiger Rest 18.u.C

Datum: 16. November 2026. Ausschließliche Grundlage ist Result
`specroad-apply_Result_041609_1116_fa2a9b.zip`, SHA-256
`ac85dec3e08db74045a188af1d0c9a633ec3d24e5ba92ec16085e50e5b860de7`,
Basiscommit `6b809ac96355b4c6388720e5c46e43b2363453f9`, Fingerprint
`1e701939c1d1a711` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

## Bestätigter Präfix und Fehler

Bundle 713 hat **18.u.R erfolgreich committed**: 15.432 Tests bestanden,
Commit `6b809ac96355b4c6388720e5c46e43b2363453f9`. Der bestätigte
Produktplanstand ist damit **770/918**. Die originale R-Beobachtung hat SHA-256
`2b4d5310f8a3fc3212856d2e75828f9f566a1e2a5e67875b6d39fc20aa8412c8`.

Anschließend scheiterte 18.u.C mit 15.665 bestandenen Tests und einem Fehler:
`tests/test_transaction_receipts_right.py::test_changed_receipt_during_readback_invalidates_observation`.
Die originale C-Beobachtung hat SHA-256
`21a95477b726eebd4e918c750ccb4293130cefa8f8979436d4e0f030df11c531`.
Das native Gate verweigerte den C-Commit; dessen vollständiger Arbeitszustand
blieb erhalten. Diese neuen Belege ersetzen die damalige Offen-Aussage zu R
im [Bericht zu Bundle 713](bundle-713-trace-writer-contract.md), ohne den
historischen Bericht zu ändern. C ist weiterhin nicht abgenommen.

## Ursache und vollständige Korrektur

C hat gemeinsame Datei-/Verzeichnisbeobachtung aus dem historischen
Receipt-Reader in `CompletionRecords` ausgelagert. Der unveränderte R-Test
bindet seine echte Dateiänderung an `receipt_read._read`; nach der Auslagerung
verwendete die gemeinsame Klasse jedoch direkt ihren eigenen Import. Die
Fehler-Injektion erreichte dadurch den Reader nicht mehr und löste keine
Änderung aus. Der Fehler belegt keine erfolgreiche Annahme manipulierter Bytes.

`CompletionRecords` bindet den Byte-Reader jetzt einmal im Konstruktor und
verwendet ihn sowohl für Erstlesen als auch für Nachprüfungen. Der historische
Reader übergibt seinen bestehenden nativen Leseadapter; der normale Reader
verwendet den gemeinsamen nativen Standard. Die doppelte Initialisierung der
Beobachtungsdaten entfällt. Der normale Reader bleibt unabhängig vom alten
Journal-/Recovery-Reader; die C-Konsolidierung wird nicht zurückgenommen.

Der vorhandene Test bleibt **bytegleich**, einschließlich echter Änderung der
Receipt-Datei und erwarteter `ReceiptError`. Sämtliche W-/R-Testdateien,
Testidentitäten und Nummern bleiben erhalten. Quellbindung, Datei- und
Verzeichnisidentitäten, Bytevergleich, aktuelle Zielprüfung, Sperrprüfung und
Fehlerweitergabe bleiben unverändert. Es gibt keinen neuen Reparaturpfad und
keine Abschwächung eines Sicherheitsgates.

## Gebundene Fortsetzung und Abnahme

Der v2-Commitplan führt ausschließlich den gesamten offenen Rest **18.u.C**
mit Rolle `implementation` und unveränderter Commitnachricht fort.
`correction_of` bindet den ursprünglichen öffentlichen Plan
`e45822230ea710bbab5aa4a3558057ad7e29080b4ab6df9653230faacd8ec2ab`
und genau `remaining_commit_ids=["18.u.C"]`. Alle 22 erhaltenen Dirty-Pfade
werden mit vollständigen Vorherbytes an dieses neue Result gebunden; der
bereits erfolgreiche R-Commit wird nicht wiederholt. Keine neue Klärung,
kein Budgetwechsel und keine neue Stage im offenen Präfix.

Das C-Gate erhält die vollständige vorherige Pflichtauswahl mit allen
Receipt-/Race-, Writer-, Authoring-, Proposal-, Publikations-, Preflight- und
Hostregressionen, einschließlich der fehlgeschlagenen Testdatei. Erst das
erfolgreiche Apply-Gate aus fälliger gefilterter N=3-Gruppe plus ungefilterter
Pflichtauswahl erlaubt den C-Commit. Dev führt nur Syntaxprüfung, reine
Collection sowie native Nachweis-/Paketvalidierung aus; keine Testkörper,
Fixtures oder Test-Unterprozesse und keine vorweggenommene Verhaltensabnahme.

Der Commitzielstand ist **771/918**, erst nach erfolgreichem C-Gate. Die
anschließende vollständige Gruppe **18.v.W/R/C** für Migration, Merge und
Rooterzeugung bleibt geplant und offen; danach folgt 18.w. Der gesamte
belegte Korrekturrest dieser Übergabe ist abgeschlossen vorbereitet, kein
Teil von 18.u.C wird als spätere Arbeit ausgeklammert.
