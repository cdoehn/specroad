# Bundle 680 — offene Proposal-Apply-R/C-Korrektur

13. November 2026. Maßgeblich ist Result 679 mit SHA-256
`c9cd25e96a4e33a1b0444476993b2c83b7ec0b3f77b08295d6649c80da3b6a8a`.
18.k.W ist nach 13891 bestandenen Tests tatsächlich als
`306db567b8119b1933da0c34fbb5e55f1069aea9` committed. R meldet 13997
bestandene und vier fehlgeschlagene Tests, C wurde nicht ausgebracht.
Der bestätigte Produktstand ist deshalb 760/900. Die vorbereiteten
R-/C-Planwerte gelten jeweils erst nach ihrem eigenen erfolgreichen Apply-Gate.

## Ursachen und Korrektur

Die zwei echten Prozessabbruchtests erben mit fork den mehrthreadigen
xdist-Worker und erreichen die Abbruchgrenze nicht. Sie verwenden jetzt spawn.
Der frische Prozess erhält ausschließlich die tatsächlich vom Elternprozess
aufbewahrten Original- und Kontextbytes. Die rekonstruierten nativen Modelle,
Kontexthashes und dekodierten echten Reviewbeobachtungen müssen übereinstimmen.
Es entstehen weder Ersatzfreigaben noch vorgetäuschte Receipts. os._exit an
prepared/published, native Recovery, gesperrter Folgeaufruf, einmalige
Zielrevision und vollständiger Retry-/Fachobjektnachweis bleiben erhalten.

Der gemeinsame Proposalwriter las nach erlaubter Darstellungsnormalisierung
der Konfiguration mit der alten Bytebindung. Journal- und Abschlussprüfung
binden jetzt die exakt geprüften Zielbytes einschließlich ursprünglicher
Rootidentität und Projekt-ID. Fremde Änderungen werden weiterhin abgewiesen;
zwei neue Fälle prüfen sie nach Publikation und nach Abschluss. Die vorhandene
Normalisierungsabnahme prüft zusätzlich schreibfreies Request-Replay.

Die öffentliche Fehlerprojektion verlor den maschinenlesbaren Recoverygrund;
zusätzlich überschrieb die CLI die spätere Prüfung mit ihrem früheren
Eingangscheck. Ursache, Fehlerklasse und Audit bleiben jetzt erhalten, und
ein neuerer Handler-Preflight hat Vorrang vor dem Eingangscheck. Die vorhandene
Regression prüft diese Felder direkt statt den String einer Gesamtausgabe.

## Übergabe und Nachweisgrenze

Exakt die belegten offenen IDs 18.k.R und 18.k.C, Rollen implementation,
Commitnachrichten und vollständigen ursprünglichen Abnahmen werden fortgeführt.
W und der erfolgreiche Klärungspräfix werden nicht wiederholt. Der vorhandene
uncommittete R-Stand bleibt vollständig enthalten; C behält seine echte
Strukturtrennung ohne neues Fachverhalten. Jede Stage hat ihr eigenes
N=3-plus-Pflichtauswahl-Gate vor dem Commit, nie den Endstand vorab.
Alle bisherigen Testidentitäten/Nummern bleiben; neue Nummern werden angehängt.
Geänderte Tests, betroffene Helferaufrufer, CLI-/Preflight- und Writerregressionen
stehen zusätzlich zur bisherigen Pflichtauswahl ungefiltert im Gate.

Dev führt ausschließlich Syntax, reine Collection, vollständige Stage-/Commit-
Byteprüfung und native Paketvalidierung aus. Kein Verhaltenstest, keine Fixture
oder Test-Unterprozessausführung in Dev. Die tatsächliche fachliche Abnahme
steht noch aus. Historische Berichte und Spezifikation bleiben unverändert;
es ist keine neue Detailklärung erforderlich.

Die ausdrücklich beauftragte neue Control-Bedienfunktion zum Rücksetzen des
Korrekturbudgets ist ein separater OFF-PLAN-Auftrag. Der native Korrekturvertrag
dieses Fehlerstands erlaubt exakt R/C und keine angehängte neue W/R/C-Folge.
Diese Übergabe ändert daher weder Budgets noch Control-Betriebsdaten.
