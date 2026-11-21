# ANALYZER-WORK-774 — echte Analyzer-Fortsetzung

Datum: 21. November 2026. Delegierte Detailentscheidung nach
SPECROAD-DECISION-1 und 2.4.3.1, Vertrag 4 mit optionaler Klärungsfreigabe.

T.9 verlangt reale Subject-Checkpoints, identische Engines und identische
Fachergebnisse. Der bisherige Work-Pfad speichert nur offene Platzhalter; die
effektive Fehlerschwelle fehlt in seiner geschlossenen Konstruktion. Die echte
Detektion existiert bereits unabhängig davon.

Alternativen: Ein kompletter Bericht vor der ersten Subject-Sicherung verliert
bereits berechnete Subjects beim Absturz. Ein neuer Prozess je Subject lädt das
Modell wiederholt. Eine veränderte öffentliche Report-Schnittstelle würde
Dateikompatibilität unnötig betreffen. Gewählt wird der kleinste getrennte
interne serielle Kanal mit einem Modell je Aufruf, nativen Parent-Checkpoints,
Engine- und Schwellenbindung in v2 sowie erhaltener v1-Lesbarkeit. Er überträgt
nur inert geprüfte JSON-Werte; Projektinhalte erhalten keine Ausführungsbefugnis.

Normativ: Spezifikation T.9.1 (v0.2.101). Abnahme: 19.w über alle dauerhaften
Grenzen in neuen Prozessen, tatsächliche Request-/Engine-/Subject-Fachhashes,
keine Wiederberechnung abgeschlossener Subjects; Host-/Speicher-/Workerfehler
mit erhaltenem letzten Stand. 19.x prüft den anschließenden Dateiroundtrip.
Keine menschliche Korpusabnahme, Ressourcenfreigabe oder Tests werden durch
diese Entscheidung behauptet. 19.t und Reviews bleiben vor 19.y erforderlich.
