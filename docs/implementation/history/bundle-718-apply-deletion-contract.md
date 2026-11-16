# Bundle 718 — gebundene Dateilöschungen in Apply und Control

Datum: 16. November 2026. Ausdrücklich beauftragte Infrastrukturarbeit nach
der privaten Vorbereitung; kein neuer Produktplanschritt und keine Klärung.

## Belegter Ausgangspunkt

Das saubere native Result mit SHA-256
`17c77be9ef173f37fae728a3b339388bea6490820df82bdb54da67b9936c4a19`
bindet Commit `b85b680eaab6740c69f948156687ee2db78afa78`.
Der erfolgreiche Abschluss von Bundle 717 ist durch Result
`8597e7388a5ef318d44c5ae43772f07b1e3e5cae88318fec157ec2c73c8e2d32`
belegt: 18.v.R und 18.v.C sind committed, der Endstand ist sauber.
Die Produktposition bleibt deshalb 774/918, als Nächstes 18.w.W.
Der zuvor privat begonnene Rückbau 18.w wird hier nicht ausgeliefert.

## Getrennte Stufen

- DELETE-CONTRACT.W: optionale gebundene Einzeldateilöschung in Commitplan v2,
  vollständige Vorherbytes, Prüfungen von Datei, Index und Commit sowie passive
  Control-Rekonstruktion und passende Pflichtauswahl. Bestehende Bundles
  behalten ihre öffentlichen Planbytes.
- DELETE-CONTRACT.R: Eingabegrenzen, Inode- und Elternwechsel, teilweise
  ausgeführte Löschungen, gestagte Fortsetzungen, tatsächliche Git-Diffformate
  und der bereits committete Unterstützungsmarker werden abgesichert.
- DELETE-CONTRACT.C: der Dateisystemhelfer wird bei unverändertem Verhalten
  abgetrennt und im Entrypoint eingefroren. Die R-Testdateien bleiben bytegleich.

Jede Stufe erhält ihr eigenes Apply-Gate aus fälliger gefilterter N=3-Gruppe
und ungefilterter Pflichtauswahl vor ihrem Commit. Erst danach wird die
nächste Stufe ausgebracht. In dieser Bootstrapfolge gibt es ausschließlich
Schreibpayloads; die neue Löschfähigkeit wird nicht vor ihrer Abnahme benötigt.
Die genaue Schnittstelle und ihre Grenzen stehen im
[Löschvertrag](../../development/Apply_Commit_Deletions.md).

## Nachweise und Grenzen

Die reine Collection umfasst W 27.704 sowie R und C jeweils 27.752 Fälle.
Pflichtauswahlen: 510, 558 und 558 Fälle. Neue stabile Testnummern werden nur
angehängt; bestehende Nummern und Rotationsanker bleiben erhalten.
In Dev wurden keine Testkörper, Fixtures oder Test-Unterprozesse ausgeführt.
Collection, Syntaxprüfung und native Paketvalidierung sind keine bestandenen
Verhaltenstests. Die Zielwerte im Fortschrittsblock jeder Stage gelten erst
nach deren erfolgreichem Gate und Commit; die vollständige Bundlenummer 718
steht deshalb erst im C-Zustand.

Die geprüfte installierte Control-Releasekopie wird durch dieses Bundle nicht
umgestellt. Ihre separate Installation setzt einen vollständig erfolgreichen
Apply voraus. Lokale Konfigurationen, Zugangsdaten, Sessionkennungen und
Budgetänderungen sind nicht Teil der Payload. Anschließend kann 18.w auf dem
neuen bestätigten Result fertiggestellt werden.
