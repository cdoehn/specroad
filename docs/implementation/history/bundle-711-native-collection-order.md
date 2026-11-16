# Bundle 711 — Hostberechtigungen an native Collection binden

Datum: 16. November 2026. Grundlage ist ausschließlich das native Fehler-Result
`specroad-apply_Result_222240_1115_30f89a.zip`, SHA-256
`3ff127d0902b51821958982fb490cbcc6882af12ecb082c1544a20afbf9b9b63`,
Basiscommit `fc398fd4217296aa7832261f4ddb93549e023a64`, Fingerprint
`a47e6a3935ce1c7d` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

Bundle 710 meldet 14.402 bestandene Tests, anschließend aber Exit 4 wegen
host_pool_contract_error. Der Gatewayabschlussfehler aus Bundle 709 trat nicht
erneut auf. Ein erfolgreiches Gate liegt weiterhin nicht vor; kein Commit wurde
erzeugt. Die offenen IDs 18.u.W/R/C behalten ihre Rolle implementation und ihre
Reihenfolge. correction_of bindet den vollständigen alten Plan
`f8702beb5aa31688df9704754eadec297709b7f478bd15ccec46269f911d1781`.
Die vollständigen erhaltenen W-Dateien bilden die neuen Vorherbytes.

## Konkreter Nachweis und Korrektur

Die zum Lauf gehörende, an dieselbe Quellidentität und Hostbindung gebundene
Beobachtung enthält 14.402 eindeutige ausgewählte und 14.402 eindeutige beobachtete
Tests mit identischer Node-/Test-ID-Zuordnung. Der unveränderte native Prüfer
verweigert sie mit Speculative collection changed. Die Listenreihenfolgen
unterscheiden sich ab Index 12.883 bei den nach Modulparametern gruppierten
Transporttests. Pytest darf diese native Fixture-Reihenfolge herstellen; die
vorab gespeicherte JSON-Auswahl ist dagegen nach Namen sortiert.

Alle Berechtigungen verwenden die wirklichen xdist-Collection-Indizes. Bei
Interpretation anhand der Eingabeliste entstehen 170 falsche Zuordnungen;
anhand der wirklichen Collection stimmen sämtliche Berechtigungen und Leases.
Eine ausschließlich im Speicher abgeleitete Diagnose mit dieser Reihenfolge
erfüllt den vorhandenen strikten Prüfer. Das ist eine Ursachenanalyse, kein
nachträglicher Gate-Erfolg. Originalbeobachtung, Fehlerstatus und Historie bleiben
unverändert. Der Originalbeobachtungs-SHA-256 ist
`38deb43387e5cfe1af21ef1137721be2c8e01366ca9bfbaba6b5f8f9ca27f87b`.

Der Live-Hostbericht übernimmt deshalb die tatsächliche Collection des
Schedulers für seine indexbezogene Auswahl. Zusätzlich müssen deren Länge und
Identitätsmenge sowie die vollständige beobachtete Node-/Test-ID-Zuordnung exakt
der vorab gebundenen Auswahl entsprechen. Fehlende Collection, Duplikate,
fremde Identitäten oder geänderte Zuordnungen bleiben sperrende Fehler.
Die bestehenden unabhängigen Live-/MOVE-/Kopienprüfer bleiben bytegleich:
Reihenfolge, Berechtigungen, Leases, Gewinner, Abbrüche und Hostslots müssen
weiterhin zusammenpassen. Die Auswahl und die native Ausführungsreihenfolge
werden nicht verändert; keine Wiederholung, keine neue Beweis- oder Formatpolicy.

Vorhandene echte lokale/Proxy-Integrationstests für Poolformate 2, 3 und 4
lassen Pytest seine Collection vor dem Dispatch umordnen. Ihre bisherigen
Drain-/Resume-, MOVE-, Prozessbaum-, Fixture-, Kopien- und Historiennachweise
bleiben erhalten. Der Bericht muss die tatsächliche Reihenfolge bei unveränderter
Identitätszuordnung wiedergeben. Zurücktausch auf die Eingabereihenfolge und
falsche, weiterhin im Wertebereich liegende Grant-Indizes werden abgewiesen.
Die ursprüngliche Transportfamilie mit echten Modulparametern wird zusätzlich
vollständig als Pflichtregression gebunden. Alle Test-IDs und Nummern bleiben.

## Vollständige Fortsetzung

W behält den gesamten normalen Writer-/Preflight-Ausschnitt. R ergänzt weiterhin
die angekündigten Randfall- und Receiptbeweise. C behält alle Testbytes von R
und die vorbereitete strukturelle Konsolidierung. Die Korrektur gilt in allen
drei Zuständen; keine Phase und kein offener Commit entfällt. Jeder Zustand
benötigt sein eigenes gefiltertes N=3-Gate plus ungefilterte Pflichtauswahl vor
seinem Commit. Keine neue Klärung, kein Budgetwechsel und kein vorab installierter
Endstand. Der bestätigte Fortschritt bleibt 768/918; Ziel 771/918 und danach
18.v.W werden erst durch erfolgreiche getrennte Apply-Gates und Commits erreicht.

Dev führt ausschließlich statische Prüfung, reine Collection und native
Paket-/Fortsetzungsvalidierung durch. Keine Testkörper, Fixtures oder Test-
Unterprozesse werden hier ausgeführt. Verhaltensabnahme bleibt Apply vorbehalten.
Lokale Konfigurationen und Betriebsdaten bleiben außerhalb der Produkt-Payload.

Vorbereiteter Zustand **18.u.W**: Ziel nach eigenem Gate **769/918**, danach **18.u.R**.
