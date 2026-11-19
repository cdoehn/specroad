# ANALYZER-EVALUATION-748 — Packages und aktuelle Beobachtungen

19. November 2026. Delegiert gemäß SPECROAD-DECISION-1, 2.4.3.1 und dem
gebundenen Vertrag 4 mit positivem Restbudget. Die bestätigten Gruppen 19.e/f
und SR-REQ-0685 bis 0688 sowie 0691 bis 0693 sind der vollständige Scope.

T.5 legt den Packageumschlag fest, lässt aber die Kardinalität mehrerer Läufe
und die Behandlung eines fehlenden ausgewählten Analyzers offen. T.8 verlangt
Aktualität und sichtbare Widersprüche, bestimmt aber noch nicht, wie explizite
aktuelle Kontext-/Settingswerte unabhängig vom alten Request zuzuführen sind
und wie ein Core unbekannte externe Beobachtungen generisch vergleichen kann.
Das geprüfte erfolgreiche Result 747 enthält bereits vollständige Request-,
Subject- und Reportvalidatoren; diese werden wiederverwendet.

Alternativen: ein einzelner Bericht je Analyzer würde vorhandene alternative
Läufe verlieren; eine freie Teilmenge würde vollständige Packageabdeckung
vortäuschen. Deshalb mindestens ein vollständiger Bericht je gewähltem
Analyzer, eindeutige Run-IDs, unveränderte Reihenfolge und keine Autoergänzung.
Aktuelle Settings aus dem gespeicherten Request zu kopieren wäre ein
zirkulärer Nachweis. Implizite Pfadsuche würde die Kontextminimierung aufheben.
Deshalb verlangt die wertbasierte API unabhängig gelieferte aktuelle JSON-
Eingaben und eine frische native Projekt-/Partialbeobachtung. Fehlende Daten
sind offen unavailable; spätere Bedienadapter müssen echte Quellen liefern.

Ein semantisches Gleichheitsurteil über unbekannte Payloads wäre erfunden;
ein Mehrheitswert würde Widersprüche verdecken. Gewählt ist ein explizit
struktureller Vergleich pro Subject und gemeinsamer Capability, mit sämtlichen
Varianten und Provenienzen. Betriebsmessungen und lokale Finding-IDs zählen
nicht als fachlicher Unterschied. Keine gemeinsame Wahrscheinlichkeit.

Die normative Präzisierung steht in T.5.1/T.8.1. Sie bleibt additiv und
versioniert rücknehmbar, erhält bestehende Originaldaten und 918 Planpositionen,
ändert keine Sicherheits-, Kompatibilitäts-, Human-Review- oder Evidencegrenze
und benötigt keine unbekannten externen Fakten. Keine behauptete individuelle
Nutzer-Fachfreigabe oder ausgeführte Engine. CLI, Work und Sprachpolicy behalten
die geplante spätere Umsetzung. Jede echte W/R/C-Stage benötigt ihr eigenes
Apply-Gate; Dokumentklärung, Vorbereitung und erfolgreicher Vollzug sind getrennt.
