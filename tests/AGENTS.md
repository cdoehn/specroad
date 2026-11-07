# Regeln für SpecRoad-Verhaltenstests

Vor Änderungen [DEVELOPMENT.md](../DEVELOPMENT.md) und die lokalen Anweisungen
des Arbeitsorts lesen. Für Testdaten, Fixture-Grenzen, erhaltene Abdeckung und
Laufzeitauswertung gelten die [gemeinsamen Testregeln](../docs/development/Testing.md#effiziente-testdaten-und-vorbereitung).
Diese maßgebliche Stelle fortschreiben, statt Regeln in Testdateien zu kopieren.

Dev erstellt Tests und Pflichtauswahl, führt aber keine Testkörper, Fixtures
oder Test-Unterprozesse aus. Reine Collection ist kein Verhaltenstest-Erfolg.
Jede neue/geänderte Testdatei und jede relevante Helferregression gehört gemäß
den bestehenden Regeln in das Apply-Gate. Keine Dokumentations-, Markdown-
oder Darstellungstests hinzufügen. Diese Datei enthält portable Projektregeln
und keine lokale Konfiguration oder Freigabe zum Start von Diensten/CI.
