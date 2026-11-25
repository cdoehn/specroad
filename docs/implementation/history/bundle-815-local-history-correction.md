# Bundle 815 — Lokale Historienleser und Force-Schemaabnahmen

Maßgebliche Quelle ist das native Fehler-Result
`9bec74af92177b17bd29a318a0fdfd8fd9224b71d6175eb08777a32221c8e01a`.
Der vollständige W-Testlauf von Bundle 814 endete mit **26.251 bestanden,
zehn fehlgeschlagen**, ohne Skip/XFail oder Abbruch. Alle 61 zuvor in 813
fehlgeschlagenen Testidentitäten bestanden, einschließlich des tatsächlichen
Description-Untertests für proposal.apply. Die zehn anderen Fehler verhindern
weiterhin das Gate. Kein Commit aus 814 entstand; HEAD bleibt
`0520553c007e6edbf9237a81693d7e0da7be4d28`. Der erfolgreiche Klärungscommit
FORCE-DOMAINS-812 bleibt erhalten. Der offene Rest ist vollständig
**21.e1.W/R/C**, jeweils Rolle implementation.

## Diagnose und begrenzte Korrektur

- Ein Git-Wiederanlauftest entfernt ausdrücklich die optionale lokale
  Requestgeschichte. Leere Transaktionsverzeichnisse bleiben zurück. Die
  neue Force-Historienanbindung behandelte sie wie unvollständige portable
  Receiptgruppen und blockierte dadurch eine neue Absicht. Gemäß 10.7.2 darf
  fehlende optionale Geschichte neu beginnen; alte Requests werden nicht als
  erneut ausgeführt oder als erfolgreich wiederholt ausgegeben.
- Drei normale Inspektionsfälle enthalten eine fremde lose Datei unter dem
  lokalen Receiptwurzelverzeichnis. Sie ist keine kanonische Receiptgruppe
  und kein aktueller Modellinput. Normale Inspektion und Impact beobachten
  solche losen Dateien und leeren Verzeichnisse jetzt ohne Herkunftsbehauptung.
  Verzeichnisbeobachtungen werden erneut geprüft. Kanonische nichtleere
  Gruppen bleiben vollständig byte-, Projekt-, Request- und Abschluss-gebunden;
  unvollständige oder geänderte Forcebelege bleiben Fehler gemäß X.12.2.
- Vier Quellenwechseltests für Impact hatten noch einen Test-Hook ohne den
  neuen force_provenance-Parameter. Der Hook reicht ihn jetzt an die echte
  Berechnung weiter. Alle ursprünglichen Änderungen und Konfliktabnahmen
  bleiben erhalten; die Produktionsberechnung wird nicht ersetzt.
- Zwei Schemaabnahmen erwarteten noch drei Exchange-Schemata beziehungsweise
  nur den normalen Proposal-Ergebniszweig. X.12.2 und die bereits gebundene
  Implementierung enthalten Change-Plan 1.4.0 sowie getrennte normale und
  Force-Ergebnisse. Die Abnahmen prüfen jetzt vier Exchange-Schemata inklusive
  1.4.0 sowie beide geschlossenen Ergebniszweige. Die normalen Pflichtfelder
  und approval_granted=false bleiben erhalten; Force muss ausdrücklich
  requested=true tragen. Keine Lockerung eines Produktschemas.

Der vollständige portable Bundle-/Importvertrag aus Anhang E bleibt streng.
Nur die lokalen normalen Leser wählen die begrenzte Beobachtungsart; die
Kombination mit einem importierten Manifest wird abgewiesen. Sichere
Pfadprüfung, aktive Marker, Locks, echte Hostautorität und notwendige
Originalbelege bleiben verbindlich. Es gibt keine nachträgliche Reparatur
von historischen Dateien oder Laufzeitnachweisen.

## Vollständiger Rest und Abnahme

Die Korrektur gilt in W und bleibt in R/C erhalten. R ergänzt tatsächliche
Forcepublikationen mit anschließender Inspektion und Impact: unveränderte
Herkunft trotz unbeanspruchter Einträge, fehlende/geänderte Originalreceipts,
nachträgliche Befüllung eines leeren Verzeichnisses, weiterhin strenge portable
Bundleauswahl sowie verlinkte oder falsch typisierte Receiptpfade. C behält
diese Oracles bytegleich. Bestehende Test-IDs und vorherige Pflichtauswahlen
bleiben erhalten; alle zehn Fehlerfälle sind erneut verpflichtend.

Jede Stage erhält ihr eigenes N=3-plus-Pflichtauswahl-Gate vor ihrem Commit.
Spezifikation 0.2.108 und genehmigter fachlicher Umfang bleiben unverändert;
eine neue Detailentscheidung oder Klärung ist nicht erforderlich. Bestätigt
bleiben 900/999 Positionen. Die Zielzähler 901/902/903 gelten erst nach dem
jeweiligen Gate. Danach bleibt 21.e2.W mit Gesamtintegration offen.
Neue Ressourcenmessungen bleiben bis zur finalen Abnahme aufgeschoben,
der finale Nachweis pending und die historischen Originalbelege bytegleich.
Dev führt ausschließlich statische Prüfung, reine Collection und native
Paketvalidierung aus; eine vorbereitete Korrektur ist kein bestandener Test.
