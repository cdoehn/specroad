# OFF-PLAN APPLY-ONLY-535 — Pflichtauswahl und Commit-Gates ausschließlich im Apply

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN APPLY-ONLY-535 — Pflichtauswahl und Commit-Gates ausschließlich im Apply

Autorität: ausdrücklicher Nutzerauftrag 1. November 2026, Spezifikation 2.5.2.
Diese Regel ersetzt für neue Arbeit alle älteren Dev-Testpflichten dieses
Plans; historische Ausführungsnachweise bleiben unverändert. Keine Testläufe
im Dev. Collection/Syntax/Paketprüfung sind keine bestandenen Verhaltenstests.
Produktfortschritt bleibt 655/900; 15.n.R ist weiterhin der nächste Produktcommit.

Ein Bundle mit drei echten Zuständen: W stellt Pflichtauswahl, Vereinigungs-
gate, Vorbereitung, Commitfolge und vollständigen Restbericht her. R sichert
falsche Eingaben, veränderte Belege, tatsächliche parallele Testmessung und
Teilfortschritt durch weitere Verhaltensfälle ab. C trennt den reinen
Bundle-Vertrag von der Host-Orchestrierung ohne Verhaltensänderung.
Jeder Zustand erhält seine Pflichtauswahl und wird erst im Apply parallel
geprüft und dann einzeln committed. Kein Vorab-Endzustand, kein Dev-Testlauf,
kein Push-/CI-/Dienststart. Bestehende Runtime-Historie bleibt erhalten.

W-Abnahme vorbereitet: langsame/gruppenfremde Pflichttests, Deduplizierung,
vollständige Dateiauswahl, unbekannte IDs, falsche Commit-ID, exakte v4-
Nachweise, drei Test/Commit-Schritte, Fehler im mittleren Schritt und
Fortsetzung mit vollständigem Rest ohne Wiederholung des ersten Commits.
Die bestehenden Rotations-, Laufzeit- und Beobachtungsregressionen gehören
zusätzlich zur Pflichtauswahl. Testerfolg bleibt bis zum Apply offen.

R-Abnahme vorbereitet: echte parallele Mini-Projekte mit N=3 plus langsamen
Pflichttests, alle dauerhaft erfassten Phasen, rote Gates ohne Commit,
veränderte Reports/Quellbindungen, defekte Pflichtpläne, untergeschobene
Restschritte und falsche Commitketten. Fremde Indexmodi bleiben gesperrt.
Kein Test wurde im Dev ausgeführt; die Abnahme erfolgt im Apply.

C trennt canonical/validate_bundle/public_plan/remaining_commits in den
reinen bundle_contract-Helfer. Der Hosttreiber und der generierte private
Entrypoint verwenden dieselben Funktionen; Verhalten und Pflichtauswahl
bleiben erhalten. Der Quellstand enthält 45 neue Verhaltenstests. Alle
drei Zwischenstände werden ausschließlich im Apply geprüft.

### C-Fortsetzung mit Korrekturbundle 536

Bundle 535 hat W mit 6.282 und R mit 6.326 bestandenen Apply-Tests
erfolgreich committed. Die 6.138 C-Tests bestanden ebenfalls; die
anschließende Git-Formatprüfung verhinderte den C-Commit wegen zusätzlicher
Leerzeilen am Ende von `bundle_contract.py`. W und R bleiben erhalten.

Korrekturbundle 536 bindet das Fehler-Result und übernimmt ausschließlich
die offene Commit-ID `APPLY-ONLY-535.C` samt vollständigem erhaltenem
C-Zwischenstand und Pflichtauswahl. Es entfernt die überzähligen Leerzeilen
ohne Verhaltensänderung. Das C-Gate wird vor dem Abschlusscommit erneut
ausgeführt; frühere Testerfolge ersetzen diesen Nachweis nicht. Im Dev
finden nur statische Prüfungen statt. Produktstand 655/900 und 15.n.R bleiben.
