# Bundle 698 — vollständige Korrektur von SPECULATE.W/R/C

Maßgeblich ist das native Fehler-Result von Bundle 697, SHA-256
`4a1c297ab65bb8ec19b6682def89ca124ad5f2c5b229742c06b1459afb332c3b`.
W scheiterte mit 33 fehlgeschlagenen und 8.850 bestandenen Tests. Es entstand
kein Commit; alle drei IDs, Rollen und Nachrichten bleiben offen. Die
vollständigen erhaltenen W-Dateien sind Vorherzustand, kein erfolgreicher W-Nachweis.

Die 31 Status-/Monitorfehler betreffen den neuen gemeinsamen Laufzeitleser:
Die isolierten Kurz-CLIs nehmen bisher nur ihr Status-Unterverzeichnis in den
Importpfad auf. Sie benötigen auch das eigene tools-Verzeichnis. Die kleinen
CLI-Testkopien erhalten die neue reale Abhängigkeit runtime_copies.py; ihre
Unabhängigkeit vom Entwicklungscheckout bleibt bestehen. Fehlende JSON-Ausgabe
legt in den Testdiagnosen nun auch den tatsächlichen stderr offen.

Die zwei Kopien-Integrationstests hielten das erste von sechs Testitems an,
während ein weiteres Item hinter ihm reserviert und noch nicht gestartet war.
Damit war die ausdrücklich verlangte Startvoraussetzung für Kopien nicht
gegeben. Der ursprüngliche Sechserfall bleibt als native Abnahme erhalten:
keine Kopie bei wartendem Original, danach vollständige einmalige Abdeckung.
Die Kopienabnahme nutzt zusätzlich zwei ursprüngliche Items, je eines pro
Worker, sodass beide vor dem Freiwerden des Zielworkers gestartet sind.
Echte Prozesse, frische Fixtures, Prozessbaumende, dauerhafte Phasen und der
volle lokale/Proxy-Nachweispfad bleiben erhalten. Dieselbe Voraussetzung
wird in sämtlichen abhängigen R/C-Kopien- und Rennabnahmen korrigiert.

Der Live-Pool startet während dieser Wartephase nur dann einen Ersatzworker,
wenn tatsächlich unzugewiesene Items vorhanden sind. Hinter einem laufenden
Item reservierte Nachfolger führen damit nicht mehr zu wiederholten leeren
Workerstarts. Die Sechserabnahme verlangt während dieser Wartephase die ursprünglichen
zwei Worker; danach zulässige Kopien bleiben erlaubt.
Alte Profile, Auswahlregeln, Hostlimits, Kopienfreigabe und Fehlergrenzen
bleiben unverändert. Kein neuer fachlicher Klärungspräfix.

Korrekturfolge: SPECULATE.W, SPECULATE.R, SPECULATE.C, jeweils mit eigenem
N=3-plus-Pflichtauswahl-Gate vor dem Commit. Alle fehlgeschlagenen Tests,
alle bisherigen Pflichtabnahmen und sämtliche Aufrufer der gemeinsamen
Pool-/Statushelfer bleiben enthalten. Testidentitäten und vorhandene Nummern
bleiben unverändert. Produktpositionen bleiben bei 762/918; danach 18.s.W.

Dev prüft Syntax, reine Collection und native Paket-/Fortsetzungsbindung.
Das ist keine Verhaltensabnahme; über den Erfolg entscheidet ausschließlich
Apply auf jedem tatsächlichen Zwischenstand. Keine Dienste, CI, Budgetänderung
oder direkten Änderungen an Apply als Nebenwirkung der Korrektur.
