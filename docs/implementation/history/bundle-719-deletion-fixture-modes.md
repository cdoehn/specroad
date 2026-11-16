# Bundle 719 — Dateirechte der Löschfixtures und vollständige Fortsetzung

Datum: 16. November 2026.

## Belegter Fehlerstand

Das native Fehler-Result von Bundle 718 hat SHA-256
`50891a979eadbd759253a713657e5d3cfa706304eafdf7179efb149bc65972e8`.
DELETE-CONTRACT.W scheiterte mit sieben fehlgeschlagenen und 7.799 bestandenen
Tests. Es entstand kein Commit; W blieb im Arbeitsbaum, R und C wurden nicht
ausgebracht. Der bestätigte HEAD bleibt
`b85b680eaab6740c69f948156687ee2db78afa78`, der Produktfortschritt 774/918.

Die Korrektur bindet alle erhaltenen Vorherbytes und den ursprünglichen Plan
`8066ae3cb5c075297624c7e123cbe48119aeec0e4804c53388c343dae177403b`.
Der vollständige offene Rest DELETE-CONTRACT.W, DELETE-CONTRACT.R und
DELETE-CONTRACT.C sowie alle Rollen `implementation` bleiben erhalten.
Es gibt keinen Klärungspräfix, keinen Budgetwechsel und keine Produktplanstufe.

## Ursache und Korrektur

Die betroffenen Fixtures erzeugten Löschziele mit `Path.write_bytes`, ohne
die vom Löschvertrag vorausgesetzten Dateirechte 0644 ausdrücklich zu setzen.
Damit hing die Testvorbedingung von der Host-Umask ab. Die native Prüfung
verwarf die Dateien bereits an der Sicherheitsgrenze, bevor der vorgesehene
Lösch-, Gate- oder Commitablauf erreicht wurde. Der Fortsetzungstest bemerkte
dies daran, dass sein angeblich bereits gelöschtes Ziel noch vorhanden war.

Ein gemeinsamer Fixturehelfer erzeugt jetzt reguläre Dateien, setzt 0644 und
prüft Modus sowie Einzelverlinkung. Die Git-, Vorbereitungs- und direkten
Dateisystemtests verwenden ihn für ihre gültigen Ausgangsdateien. Die
abhängigen R-Zustände übernehmen dieselbe Korrektur, insbesondere für
Inode-/Elternwechsel und den Fehler beim zweiten Unlink. Die Wechseltests
prüfen zusätzlich, dass die injizierte Dateiersetzung tatsächlich erreicht
wurde. Ungültige Modi, Links, Sonderdateien und fremde Bytes bleiben gezielte
Fehlerfälle. Die tatsächliche Lösch- und Sicherheitsimplementierung bleibt
gegenüber dem jeweils angekündigten W/R/C-Zustand bytegleich.

## Getrennte Abnahme

Jeder Schritt behält sein eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.
Alle sieben fehlgeschlagenen Fälle, ihre vollständige Testdatei, die gesamte
bisherige Pflichtauswahl und die abhängigen Helferverbraucher bleiben Pflicht.
Stabile Testkennungen und Registrybytes ändern sich nicht. C übernimmt die
korrigierten R-Testbytes unverändert und behält seine angekündigte strukturelle
Bereinigung. Erst nach W-Gate und Commit folgt R, danach entsprechend C.

In Dev erfolgen nur statische Prüfung, reine Collection und native
Paket-/Fortsetzungsvalidierung. Kein Testkörper oder Fixture wird dort
ausgeführt; die Apply-Abnahme steht aus. Die Bundlenummer 719 im C-Zielstand
gilt erst nach dem erfolgreichen Abschluss der ganzen Folge. 18.w bleibt offen,
ebenso die separate Installation der erst noch erfolgreich abzunehmenden
Control-Releasekopie. Lokale Konfigurationen und Zugangsdaten sind kein Payload.
