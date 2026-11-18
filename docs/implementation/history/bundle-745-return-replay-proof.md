# Bundle 745 — native historische Abschlussbelege beim Rücktransport

Datum: 18. November 2026. Quelle ist ausschließlich das native Fehler-Result
mit SHA-256 `031d5c153bff76e9add4ccaed7eb5cbe67d0242d273ef9a152678814208c9eda`.
Bundle 744 übernahm `18.q.W` mit 9.394, `18.q.R` mit 9.547, `18.q.C` mit
9.679 und `18.r.W` mit 9.416 bestandenen Tests. Bestätigter Produktfortschritt
ist 799/918. `18.r.R` scheiterte danach mit einem Fehler und 9.481 bestandenen
Tests. Offen bleiben exakt `18.r.R` und `18.r.C`, beide `implementation`.
Alle erfolgreichen Commits bleiben erhalten; die Korrektur bindet den
vollständigen tatsächlichen R-Arbeitsstand, nicht den älteren sauberen Stand.

## Ursache und Korrektur

`test_same_patch_replay_requires_actual_native_completion_and_writes_nothing`
erreichte die zweite Annahme einer tatsächlich erfolgreich empfangenen ZIP.
Die gespeicherten Receiptbytes enthielten die unmittelbare Schreibbeobachtung:
`current_target_verified=true`, `replayed=false`. Der native Abschlussreader
liefert beim späteren Lesen korrekt die historische Beobachtung mit
`current_target_verified=false`, `replayed=true`. Der Vergleich vollständiger
Beobachtungsbytes musste deshalb mit `return_receipt_mismatch` scheitern.

Der lokale Transportbeleg wird nun aus dem nach Veröffentlichung erneut
gelesenen nativen Request-/Abschlussnachweis erzeugt. Dieselbe native
historische Projektion wird beim Replay wieder geprüft. Die erste
Schreibantwort bleibt unverändert. Kein Flag wird aus Paketdaten ergänzt,
ignoriert oder auf einen gewünschten Erfolg gesetzt. Alle Receiptfelder
bleiben vollständig und kanonisch gebunden. Das erfolgreiche originale
PatchHarbor-Result, seine SHA-256, aktueller Repositoryzustand, Draftbytes,
Staging und native SpecRoad-Receipts bleiben zusätzlich verpflichtend.

Alternativen waren ein feldweiser Vergleich mit ausgelassenen Beobachtungsflags
oder eine manuell nachgebildete Projektion. Beide würden eine zweite Definition
des nativen Belegs schaffen. Die erneute native Lesung verwendet stattdessen
die schon vorhandene geprüfte Abschlusssemantik. Das ist eine Umsetzungskorrektur
innerhalb W.5.1/W.6, keine normative Detailentscheidung; Spezifikation 0.2.95
und ihre aktiven Hashbindungen bleiben unverändert.

## Vollständiger Rest und Abnahme

Der bestehende positive Replayfall prüft nun getrennt die unmittelbare
Schreibbeobachtung und den unabhängig gelesenen historischen Abschluss.
Ein zusätzlicher echter Unterprojektfall wiederholt den Empfang über Modul
und PYZ ohne zweiten Apply und ohne Änderungen. Vier Manipulationsfälle
verändern Transaktionskennung, Zielhash beziehungsweise beide Beobachtungsflags
und verlangen die genaue Ablehnung bei unverändert erhaltenem Zustand.
Die Fälle für fehlende oder geänderte originale PH-Results prüfen zusätzlich
ihren jeweiligen Fehlergrund, damit ein früherer Fehler sie nicht verdeckt.
Alle bisherigen Test-IDs, übrigen Assertions und Pflichtauswahlen bleiben erhalten.

Beide offenen Stufen erhalten ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem
Commit. C übernimmt sämtliche R-Testbytes unverändert und behält seine reine
Auslagerung des Paketlesers. Planrevision in Kopf und zentralem YAML-Block
wird konsistent geführt. Ziel 800 beziehungsweise 801/918 gilt erst nach dem
jeweiligen erfolgreichen Apply-Commit. Der nächste Schritt bleibt `19.a.W`.

Die priorisierte Anschlussfolge 19.a/19.b wurde mit Anhang T.2/T.3 geprüft.
T.2 nennt `dependency_requirements`, enthält aber noch keine geschlossene
Wertstruktur dieses Felds; T.3 beschreibt die Bindung je `analyzers`-Eintrag,
ohne dessen abschließende Feldmenge festzulegen. Ein neuer normativer
Analyzer-Datenvertrag wird nicht still im Anhang dieser bereits offenen
Korrekturfolge erfunden. Diese Fortsetzung liefert den vollständigen R/C-Rest;
die zusammenhängenden Analyzergruppen folgen nach einer eigenen zulässigen
Detailentscheidung samt Umsetzung, ohne künstlich verkürzte Teilstufe.

Dev führt nur Syntaxprüfung, statische Analyse, reine Collection mit aktiven
Katalogbindungen und native Paket-/Fortsetzungsvalidierung aus. Kein
Verhaltenstest läuft in Dev. Vollsuite, getrennte Python-/Plattformmatrix und
Meilensteinfreigabe bleiben eigenständige offene Nachweise.
