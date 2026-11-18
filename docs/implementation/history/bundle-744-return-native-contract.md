# Bundle 744 — nativer Rückpaketvertrag und vollständiger offener Rest

Datum: 18. November 2026. Technische Basis ist ausschließlich das native Result
mit SHA-256 `21807cce51c60c72283bcbd4c197061e55b7c1a0cbb2aed1c0578ac7fd627aff`.
Der Klärungscommit `RETURN-TRANSPORT-743` wurde nach 7.301 bestandenen Tests
übernommen. `18.q.W` scheiterte anschließend mit acht Fehlern und 9.487
bestandenen Tests; kein weiterer Commit wurde erzeugt. Bestätigter
Produktfortschritt bleibt deshalb 795/918. Der frühere Bericht
[Bundle 743](bundle-743-return-transport.md) beschreibt die Vorbereitung,
nicht den erfolgreichen Vollzug seiner sechs Produktstufen.

## Belegte Ursache und zusammenhängende Korrektur

Alle acht fehlgeschlagenen Fälle sind reale Rückexporte über Modul/PYZ,
argv/strukturierte Anfrage und Repositorywurzel/Unterprojekt. Der feste
Entrypoint hatte keinen vorgeschriebenen `# PATCHHARBOR`-Marker; der native
Parser lehnt ihn bereits vor der Paketerzeugung ab. Der Marker wird ergänzt.

Die statische Prüfung der tatsächlich gebundenen PatchHarbor-1.8.0-Laufzeit
zeigt außerdem zwei automatisch erzeugte Begleitdateien unter
`PATCHHARBOR_META/`. Sie gehören zur öffentlichen Inspektionsrolle `handoff`,
nicht zum SpecRoad-Payload. Export, Empfangsvorprüfung und Admission unter
Repositorysperre unterscheiden diese native Rolle jetzt vom weiterhin
vollständig geschlossenen SpecRoad-Inventar. Pfadpräfixe allein gewähren keine
Ausnahme. Die native Prüfung des exakten Metadatenpaars, seiner Bindung und
seines Formats bleibt verpflichtend; die Byteprüfung umfasst weiterhin alle
ZIP-Einträge. Die Begleitdateien werden nicht ins Zielrepository geschrieben.

Dies korrigiert die Umsetzung des bereits festgelegten Vertrags W.5.1;
Spezifikation 0.2.95 und fachliche Entscheidung bleiben unverändert. Es gibt
keinen neuen Klärungspräfix. Proposal-Originalbytes, vierfache Herkunftsbindung,
separate lokale Transport-/Schreibbefugnis, Draft-only-Empfang, spätere echte
Reviews sowie vollständige Replay- und Prozessabbruchprüfungen bleiben erhalten.

## Vollständige Fortsetzung und Nachweise

Die offenen IDs und Rollen werden unverändert fortgeführt:
`18.q.W`, `18.q.R`, `18.q.C`, `18.r.W`, `18.r.R`, `18.r.C`, jeweils
`implementation`. Der erfolgreiche Klärungscommit wird nicht wiederholt.
Jeder Zustand wird erst nach dem eigenen Apply-Testgate committed; spätere
Zustände werden nicht vorab installiert. Zielzähler 796 bis 801 und die
Fortsetzung `19.a.W` gelten ausschließlich nach dem jeweiligen erfolgreichen
Gate. Die zwei vollständigen W/R/C-Gruppen bilden den gesamten offenen Rest.

Die vorhandenen positiven Tests prüfen das tatsächliche native ZIP samt
Metadatenbindung und weiterhin alle exakten Produktbytes. Der Empfang prüft
zusätzlich, dass native Begleitdateien nicht im Repository landen. In `18.r.R`
weisen zwei zusätzliche Fälle unerlaubte Einträge im reservierten Metadatenraum
und ein ungültiges Environment-Dokument vor jedem Payload-Schreiben zurück.
Alle bisherigen Testfälle und stabilen Nummern bleiben erhalten. C übernimmt
jeweils unveränderte Testbytes aus R und behält seine reine Strukturänderung.

Dev führt nur statische Prüfung, Python-/Shell-Syntaxprüfung, reine Collection
mit aktiven Katalogbindungen, genaue Rekonstruktion der sechs Zustände und
native Paket-/Fortsetzungsvalidierung durch. Kein Verhaltenstest wurde hier
ausgeführt. Die vorhandene ungefilterte Pflichtauswahl bleibt erhalten und
umfasst auch die ergänzten Fälle; Apply vereinigt sie vor jedem Commit mit
seiner fälligen N=3-Gruppe. Keine lokale Konfiguration oder Betriebsfreigabe
wird als Produkt-Payload übernommen.
