# Bundle 664 — Fortschrittsbalken im Test-Monitor

Datum: 10. November 2026. Ausdrücklicher manueller Nutzerauftrag; OFF-PLAN.
Die zunächst ausschließlich in Dev vorbereitete Änderung wird jetzt übergeben.
Quelle ist das erfolgreiche native Result von Bundle 663,
SHA-256 `5f4e27364edf681a6c002dceb973c7d77229c6f24902f05b52ec4d87560397be`.
Seine Basis ist `48939872c0286d6be8b17b60fa27b6d98cbe79b1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint `7c9d2a24e397e0e5`
mit `patchharbor-state-v1`; der Arbeitsstand ist sauber.
18.h.W/R/C wurden mit 9799, 10222 und 10051 bestandenen Testausführungen
committed. Der Produktplan bleibt bei 753/900, nächste Position 18.i.W.

## Änderung

Die Apply-Übersichtszeilen bilden bei laufenden Testgates den vorhandenen
beendet/ausgewählt-Zähler als Hintergrund über die gesamte Terminalbreite ab:
grün für den abgeschlossenen Anteil, gelb für den offenen Anteil. Der Text
enthält zusätzlich den Prozentwert. Freie Applies behalten auch ausgewählt
ihren normalen Hintergrund; Pfeil und Fettschrift kennzeichnen die Auswahl.
Fehler, fehlende Werte und veraltete Statusquellen bleiben unterscheidbar.
Eine alte Laufzeithistorie unterdrückt keinen aktuellen Statusfortschritt.
Der Balken ist weder eine Zeitprognose noch eine Erfolgsmeldung.
Bedienung und Grenzen stehen in [Test-Monitor](../../development/Test_Monitor.md).

## Echte Zustände und Nachweise

- `OFF-PLAN-TEST-MONITOR-PROGRESS-20261110.W`: vollständige nutzbare Darstellung,
  Zählerprüfung und Auswahl ohne invertierten Hintergrund freier Applies.
- `OFF-PLAN-TEST-MONITOR-PROGRESS-20261110.R`: zellengerechtes Zeichnen bei
  Größenänderungen und Unicode, rote Fehlerhinweise und Farb-Fallback.
- `OFF-PLAN-TEST-MONITOR-PROGRESS-20261110.C`: dieselben Darstellungsfunktionen
  unverändert in `monitor_overview.py` zusammenführen; kein neues Verhalten.

Alle drei erhalten je ihr eigenes Apply-Gate aus fälliger gefilterter N=3-
Gruppe und den vier bestehenden Monitor-/Status-Testdateien als Pflichtauswahl.
Keine neuen Farb-, Layout- oder Dokumentationstests. Datenquellen, Datenbanken,
Testauswahl, JSON-Vertrag und Aktualisierung sind nicht verändert. Dev prüft
Syntax, statische Struktur, reine Collection, Vorherbytes und native Verpackung;
keine Verhaltenstests in Dev. Ein erfolgreicher Apply-Abschluss dieses Bundles
wird erst durch dessen späteres Result belegt. Keine neue Klärung, keine
Änderung von Control-Budget, Diensten, Hostkonfiguration oder Produktpositionen.

Vorbereiteter Zustand dieser Stage: `C`.
