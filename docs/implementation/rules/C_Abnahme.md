# Gemeinsame C-Abnahme

Die folgenden zwei wortgleichen Klauseln standen bisher jeweils 294-mal im Plan. Sie gelten über den ausdrücklichen Verweis bei jeder betroffenen C-Position weiterhin vollständig und schrittbezogen. Abweichende individuelle Klauseln bleiben direkt bei ihrem Schritt. Ausführung weiterhin nur gemäß der aktuellen [Apply-Testregel](../../development/Testing.md).

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.
