# Bundle 740 — getrennte Hostgrenze und Dialogoptimierung

Ausdrücklicher Nutzerauftrag vom 18. November 2026: die privat vorbereiteten
Änderungen jetzt über Apply übernehmen. Die Hostregel besitzt eine eigene
W/R/C-Commitfolge, getrennt von den drei Dialogoptimierungen.

## Bestätigte Grundlage

Result-SHA-256: `0b3c76ccb0cceb1808657b917463e5720812cdaa2739f090f95ad105a5144ff3`.
Sauberer HEAD: `bdf37464964d032b4a3f5fa0af015b5f0c1f0370`.
Bundle 739 hat 18.p.W, 18.p.R und 18.p.C vollständig committed; seine drei
Gates bestanden mit 13.967, 14.096 und 14.103 Tests. Kein offener Rest.
Der native Snapshot stimmt in allen 3.649 Dateien mit der vorbereiteten
Grundlage überein. Erfolgreiche Commits werden nicht wiederholt.

## Folge und Abnahmen

`TEST-HOST-ONCE.W` → `TEST-HOST-ONCE.R` → `TEST-HOST-ONCE.C` →
`DIALOG-PERFORMANCE.W` → `DIALOG-PERFORMANCE.R` → `DIALOG-PERFORMANCE.C`.

Alle Stages haben die Rolle `implementation` und ihr eigenes N=3-plus-
Pflichtauswahl-Gate vor dem Commit. Der Entrypoint installiert jede Stage
erst nach erfolgreichem Gate und Commit ihrer Vorgängerin.

- [Hostgrenze](../decisions/test-host-once.md): Original, reservierter Start,
  laufender und noch nicht bestätigt beendeter Versuch zählen pro Test/Host.
  Kopien auf anderen Hosts, Workerbudgets und Messhistorien bleiben erhalten.
- [Dialogoptimierung](../decisions/dialog-performance.md): öffentliche
  Registerrecords bedarfsgerecht und getrennt erzeugen; vollständige
  Schema-Vokabulare begrenzt wiederverwenden; reine native Projektmodelle
  aufruflokal mit tiefen eigenen Kopien nutzen. Aktuelle Gates bleiben frisch.

Der vollständige Dialogtest und seine bisherigen Helfer sind bytegleich;
27 zusätzliche Testfälle prüfen die neuen Grenzen. Alle vorhandenen IDs und
Testnummern bleiben erhalten. Dev hat Syntax, reine Collection, vollständige
Vorherbytes, native Stagerekonstruktion und unveränderte Parser-/Gatekörper
geprüft, aber keine Verhaltenstests ausgeführt. R-Testbytes und Pflichtauswahl
bleiben in C unverändert. Ein Nachher-Speedup ist noch nicht gemessen.

## Stagegebundener Zielstand

Dieser Dateistand gehört zu `TEST-HOST-ONCE.R`. Seine Abnahme gilt erst mit dem
tatsächlichen erfolgreichen Gate und Commit dieser Stage. Danach offen:
`TEST-HOST-ONCE.C`, `DIALOG-PERFORMANCE.W`, `DIALOG-PERFORMANCE.R`, `DIALOG-PERFORMANCE.C`.
Produktfortschritt bleibt 795/918, nächste Produktposition 18.q.W.
Die Automatik wird durch dieses Bundle nicht fortgesetzt; Dienste, lokale
Hostkonfigurationen, Zugangsdaten und Betriebsbudgets sind keine Payloads.
