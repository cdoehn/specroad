# Bundle 752 — gebundener Projektvariantenvertrag

19. November 2026. Maßgebliches natives Fehler-Result:
SHA-256 `cc346e091abd05130d562f7879161c8f7faa222950ad335bcd98d13d915708c2`,
HEAD `83382391a0c1cac367d63840ce4b9f25e6b2b65b`.
19.g.W meldet einen fehlgeschlagenen und 10.893 bestandene Tests.
Bundle 751 erzeugte keinen Commit; der vollständige Rest 19.g.W/R/C und
19.h.W/R/C bleibt offen. Bestätigter Produktfortschritt: 819/918,
nächste Position 19.g.W. ANALYZER-CLI-749 bleibt bereits committed.

Die in Bundle 751 ergänzte Optionsprüfung greift mit requires_project auf
ein nicht vorhandenes Feld der Variantenbeschreibung zu. Die statische
Prüfung des geschlossenen command-description-v1-Schemas und seiner nativen
Projektion zeigt denselben Fehler auch für lock_kind. Das sind Eigenschaften
des gebundenen Registryvertrags; sie sind keine Felder des veröffentlichten
Variantenobjekts. Die frühere statische Vorbereitung belegte diesen Zugriff
nicht richtig. Das native Fehler-Result ist maßgeblich, kein Gate wird übernommen.

Die Korrektur bindet weiterhin das veröffentlichte Variantenbeispiel durch
den echten Registrybinder und prüft dieselbe registry-eigene Variante.
Projektpflicht wird an bound.command.requires_project geprüft, Sperrart
an bound.command.protocol.lock_kind. PROJECT_READ, projektloser Basisvertrag,
fehlende Workfortsetzung, leere Betriebseffekte und alle verbotenen Optionen
bleiben unverändert geprüft. Beide fehlerhaften Zugriffe werden zusammen
korrigiert. Kein neues Formatfeld, keine Specänderung, kein neuer Klärungspräfix.
Test-IDs, Parametervarianten, Nummern und sämtliche anderen Testbytes bleiben
gegenüber der jeweiligen ursprünglichen Stage erhalten.

Korrekturbindung: `7687a18ea97faee26022ed66b55c6e6178e107497ea507bd982d096a7e6dec02`.
Alle sechs offenen IDs, Rollen implementation, Nachrichten und Abnahmen
bleiben in ihrer ursprünglichen Reihenfolge erhalten. Alle 37 uncommitteten
Quellpfade gehören zum ersten Commitumfang; vollständige Vorherbytes und
Bindungen stammen aus dem neuen effektiven Snapshot. Erfolgreiche Commits
werden nicht wiederholt; das Entscheidungsbudget wird nicht verändert.
Historische Belege 749–751 bleiben bytegleich erhalten.

Zielstand **19.h.R** zählt erst nach seinem eigenen Apply-Gate und Commit
**824/918**; danach folgt **19.h.C**. Jedes Gate erhält alle bisherigen
ungefilterten Pflichtdateien einschließlich test_description.py zusätzlich
zur fälligen gefilterten N=3-Gruppe. C erhält die W/R-Testbytes unverändert.
Dev prüft ausschließlich Syntax, statische Verträge, reine Collection und
native Paketbindung; diese Vorbereitung ist kein bestandener Verhaltenstest.
Spätere Worker-/Work-Abnahmen, Vollsuites und menschliche Freigaben bleiben offen.
