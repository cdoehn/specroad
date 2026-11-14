# Bundle 699 — SPECULATE.R/C nach erfolgreichem W

Maßgeblich ist das native Fehler-Result von Bundle 698, SHA-256
`96ef85b5027ed87fa1493b2f2f08e9041bbd1c036ad9fe298a5607511cdf132f`.
SPECULATE.W bestand sein eigenes Gate mit 8.873 Tests und wurde als
`e9d272dea5195968ae8d7ec2ae52ebb40d65704b` committed. SPECULATE.R
scheiterte anschließend mit einem fehlgeschlagenen und 8.945 bestandenen
Tests. Nur SPECULATE.R und SPECULATE.C sind offen; W wird nicht wiederholt.
Der vollständig erhaltene R-Arbeitsstand bildet die neue Korrekturbasis.

Der negative Integrationstest zur fehlenden Abbruchbestätigung gab den
laufenden Verlierer bereits beim Eintritt in den asynchronen Abbruchaufruf
frei. Dieser Eintritt belegt noch keine Verarbeitung des Fehlers durch den
Controller. Der Verlierer konnte deshalb vor der nächsten Verarbeitung
regulär vollständig enden und den zulässigen Nachweis eines natürlichen
Konkurrenzabschlusses liefern. Der beobachtete Erfolg des inneren Pools
prüfte damit einen anderen Ablauf als die beabsichtigte Fehlerabnahme.

Die Korrektur synchronisiert die Fixture auf die tatsächlich vom nativen
Controller erkannte fehlende Bestätigung: Der unveränderte Controller-Tick
läuft vollständig; erst danach wird sein Fehler-/Stoppzustand atomar als
Testsignal veröffentlicht. Vor Freigabe des Originals prüft der Test, dass
dieses noch läuft und der andere Versuch bereits vollständig mit bestandenen
Setup-, Call- und Teardown-Phasen abgeschlossen ist. Anschließend müssen
der Prozess fehlschlagen, der maschinenlesbare Poolfehler erhalten bleiben
und die native Nachweisprüfung den Gate-Erfolg verweigern.

Der getrennte positive Integrationstest für einen natürlich vollständig
beendeten Verlierer bleibt unverändert. Alle Testidentitäten, Parametervarianten,
Nummern, Auswahlregeln, Produktionsdateien und normativen Spezifikationsbytes
bleiben erhalten. Keine zeitbasierte Erfolgssimulation, keine längeren
Timeouts und keine zusätzliche fachliche Klärung.

Die Korrektur enthält den vollständigen alten R/C-Rest mit unveränderten IDs,
Rollen und Commitnachrichten. C behält seine eigene strukturelle Bereinigung
und übernimmt die korrigierte Testabnahme bytegleich. Jede Stage erhält ihr
eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit, einschließlich aller
bisherigen Pflichtabnahmen. Produktfortschritt bleibt 762/918; danach 18.s.W.

Dev prüft ausschließlich Syntax, reine Collection, native Paketvalidierung
und die vollständige Fortsetzungsbindung. Ein vorbereitetes Bundle ist kein
Verhaltenstest-Erfolg. Keine Dienste, CI, Budgetänderungen oder direkten
Apply-/Git-Änderungen gehören zu dieser Korrektur.
