# Bundle 639 — Remote-Host-Testkorrektur und offener R-/C-Rest

9. November 2026. Quelle: Result mit SHA-256
`04ac50fb10d12bb5c5e119a698f79323e39ac88bc905b3094629e8cf44487882`.
Bundle 638 hat `REMOTE-TEST-HOSTS.W` nach 7.355 bestandenen Tests als
`ec6cd322e17626cf7f5c800f0f81ee89381255c5` committed. In R bestanden 7.454
Tests, zwei scheiterten; R wurde nicht committed und C nicht ausgebracht.
Dies ersetzt die damalige Offen-Aussage aus dem [638-Bericht](bundle-638-remote-test-hosts-correction.md)
für W. Die neue Folge enthält ausschließlich die ursprünglichen offenen
Kennungen `REMOTE-TEST-HOSTS.R` und `REMOTE-TEST-HOSTS.C`, Rolle jeweils
`implementation`, gebunden an sämtliche erhaltenen R-Vorherbytes.

Beide Fehler betreffen Testannahmen:

- Die simulierte Remote-Schnittstelle erkannte jede Python-Quelle mit
  `hashlib.sha256` als Installer-Prüfsumme. Seit R verwendet auch die
  Umgebungsabfrage Hashing für die Hostkonto-Identität; die Simulation lieferte
  dafür irrtümlich eine Zeichenkette. Der Test unterscheidet den expliziten
  verwalteten Interpreter und prüft dessen Umgebungsabfrage nach Paketsynchronisation.
  Unbekannte Abfragen dürfen nicht durch einen pauschalen Erfolg verdeckt werden.
- Die echte Apply-Gate-Integration wies manipulierte Hostdaten bereits bei der
  Profilprüfung ab. Der Test erwartete jedoch den Text einer späteren Prüfung.
  Er prüft nun die vertragliche Ablehnung unabhängig von menschlichem Fehlertext.
  Zusätzlich wird eine intern konsistente Umbenennung aller Worker abgewiesen;
  das bytegleich wiederhergestellte Profil liefert anschließend den ursprünglichen
  Gate-Nachweis. Der synthetische echte Worker-/Apply-Lauf bleibt erhalten.

Keine produktive Validierung wird abgeschwächt. Die vollständigen bisherigen
Pflichtauswahlen und stabilen Testkennungen bleiben erhalten. Alle 16 im Result
uncommittierten R-Pfade gehören zum ersten Commit, auch unveränderte Dateien.
Erst nach erfolgreichem R-Gate und Commit wird die ursprüngliche strukturelle
C-Bereinigung hergestellt und separat geprüft. Die bereits in W übernommene
[Aufgabenhistorienregel](../../../DEVELOPMENT.md#aufgabenhistorie-mit-zeitstempeln)
bleibt bestehen; persönliche Aufgabenaufzeichnungen bleiben außerhalb der Payload.

Dev führt keine Verhaltenstests aus. Syntax, reine Collection und native
Paketvalidierung sind Vorbereitungsprüfungen. Apply übernimmt je Stage die
gefilterte N=3-Auswahl samt vollständiger Pflichtunion. Produktfortschritt
729/900 und nächste Position 18.a.W bleiben unverändert. Der Bundlezähler
wird ausschließlich im erfolgreichen C-Commit auf 639 gesetzt. Keine
Remote-Einrichtung, Dienststarts oder direkte Apply-Bearbeitung aus Dev.
