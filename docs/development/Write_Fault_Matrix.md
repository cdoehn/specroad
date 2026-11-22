# Schreibschutzgesamtmatrix

Die Abnahme parametrisiert die echten Change-, Migrations- und Merge-Writer
über Schutzmarker, jedes vorbereitete Image, jede Ersetzung/Löschung samt Sync,
alle drei Receipts und den Abschluss einschließlich Markerlöschung und
Ausgabeverlust nach bestätigter Rückkehr. Die veränderten Dateipfade und alle
Indizes stammen aus dem jeweiligen echten Plan. Jeder Abbruch verwendet ein
eigenes ursprüngliches Projekt. Originalquellen und externe Backups bleiben
als unabhängiges Byte-Orakel erhalten.

Vor dem Schutzbeginn bleibt der ursprüngliche Zustand erhalten. Ein verwaister
Lock oder nicht bestätigter Write bleibt gesperrt, auch bei vollständigen
Zielbytes oder vorhandenen Receipts. Der Test prüft den exakten veröffentlichten
Präfix, die schreibfreie Sperrprüfung und die verweigerte Wiederholung. Er löscht
keine Sperren, repariert keine Marker und ruft keine Write-Recovery auf.
Nur ein tatsächlich bestätigter Abschluss liefert historisch dasselbe Receipt.

Ein separater Test startet nach einem echten Prozessverlust aus einem vollständigen
frischen Git-Checkout mit neuem Intent. Der beschädigte alte Root bleibt
bytegleich gesperrt. Bestehende Tests zu fehlenden Pflichtressourcen, unbekannten
Ownern, defekten Receipts, Dateisystemgrenzen und verlorenem Work bleiben Teil
der ungefilterten Pflichtauswahl; sie werden nicht durch die Matrix ersetzt.

Alle Testdaten und Identitäten sind synthetisch. Vorbereitung und Collection
sind kein Testergebnis; die jeweiligen Apply-Gates müssen jeden Zustand prüfen.
