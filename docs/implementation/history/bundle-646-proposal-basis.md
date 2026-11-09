# Bundle 646 — Feste Proposalbasis und Kontrollausschluss

9. November 2026. Technische Basis: erfolgreiches Bundle 645, Result
`3b09b55b2ae12c7bc56badbe3f9ae566c2d63541c91c2bd3d9cfb9cb57d8dae2`,
Commit `8cd3f431974586ff61d59c00ecf5b4dd545b4bee`. Alle vier angekündigten
Stages einschließlich 18.a.W/R/C wurden committed; kein offener Rest.

Diese Datei beschreibt den vorbereiteten Zielzustand **18.b.R**.
Erst das jeweilige erfolgreiche Apply-Testgate und der native Commit machen
den zugehörigen Planfortschritt wirksam. Dev hat keine Verhaltenstests ausgeführt.
Die bestehende Spezifikation 10.8.1 und 11.10 genügt; keine neue Detailklärung.

W berechnet die öffentliche feste Basis aus tatsächlichen nativen Projektbytes
und verbindet die deklarative Proposal-Erzeugung mit der echten Rekonstruktion
des geplanten Zielstands. Proposal- und Baseline-Kontrollartefakte einschließlich
der ausschließlich zugehörigen Archivobjekte gehen nicht in die Basis ein.
R weist Konfiguration und andere Scope-Overrides ab, erhält die native
SRV140-Diagnose auch für erst im Zielstand entstehende Kontrollabhängigkeiten
und prüft Basisoptionen im gemeinsamen CLI-Aufrufpfad vor Projektzugriff.
Gespeicherte Datenfehler und Aufruffehler behalten verschiedene Exitcodes.
C zentralisiert den festen Descriptor und die vorhandene native Scope-Nutzung;
die W/R-Oracles und fachlichen Ergebnisse bleiben gleich.

Die CLI-Tests verwenden den echten Einbettungspunkt mit einem Basis-Handler.
Öffentliche Authoring-Befehle und Writer werden hier nicht als fertig ausgegeben;
ihre Registrierung und Integration bleiben Bestandteil der folgenden M18-Schritte.
Es entsteht keine Schreib-, Review- oder Freigabeberechtigung.

Pflichtauswahl: vollständige neue Testdateien, bestehende Proposal-/Restore-,
Scope-/Kontrollausschluss- und Katalogregressionen; ab R zusätzlich die
gemeinsamen CLI-, Options- und Bootstrapgrenzen. Kleine native Testprojekte,
echte Baseline-Archive, ein voller Registryfall und echte Target-Folds erhalten
die Integrationsabdeckung. Jeder Zustand erhält sein eigenes gefiltertes N=3-
plus-Pflichtauswahl-Gate vor dem Commit. Stabile Nummern werden nur angehängt.

18.c und spätere Schritte bleiben offen; kein M18-Gesamtabschluss.
