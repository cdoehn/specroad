# Bundle 687 — START abschließen und CONFIG umsetzen

Gebundener Ausgang: natives sauberes manuelles Result vom 14. November 2026,
SHA-256 `166e5b584e0364ee2c8b8df5e1fd7a43214c1c1c62957eb33ae50addbb901a66`,
Basiscommit `fc89d720691ee39b96dc38542edfc68f86c81af7`.
START.W und START.W-FIX1 bleiben erhalten. Kein fehlgeschlagener Apply-Rest,
kein offener Klärungspräfix und keine neue normative Detailentscheidung.
CONFIG konkretisiert den bereits ausdrücklich bestätigten Scope aus 2.4.3.7;
seine lokale Bedienung ersetzt keine fachliche Freigabe oder Budgetbindung.

## Vollständige Folge

1. START.R: Checkpoint bei Unterbrechung nativ wiederprüfen/wiederverwenden,
   fremde ausstehende Pakete abwarten, verdrängte Bedienvormerkungen erhalten,
   Status und expliziten Neustart von beschädigter alter Historie lösen.
   Echte native Adapterabnahme mit sauberem/dirty Git, Sperre und Fremd-ID.
2. START.C: private Zyklusdaten von der Ausführung trennen; unveränderte
   Übergänge, Sperren und Abnahmen; Betriebsdokumentation zentralisieren.
3. CONFIG.W: lokale CLI, persistente positive Budgets über zwanzig hinaus,
   explizite zyklusgebundene Overrides und Übernahme für neue Vertragsbindungen.
4. CONFIG.R: konkurrierende Bedienung, atomare Speicherung, beschädigte Datei,
   laufender Turn, Änderungen während nativer Vorprüfung und erschöpfter Rest.
5. CONFIG.C: gemeinsame Policyvalidierung und CLI-Zugriffe konsolidieren,
   gleiche Ergebnisse und alle vorherigen Verhaltensabnahmen erhalten.

Commitzielstand dieses Dokuments: **START.R**; danach **START.C**.
Dies ist eine Vorbereitung mit eigenen Apply-Gates, kein vorweggenommener
Erfolgsbericht. Jede Stage wird erst nach bestandenem Gate committed; erst
danach wird der nächste Zustand installiert. Alle Rollen sind implementation,
Übergabe patch_ready, correction_of null. Der Produktstand bleibt 762/918.

## Prüfung und Betrieb

Dev: Syntax, vollständige Collection, stabile Nummern, Katalog-/Specbindung,
Vorherbytes und native Paketvalidierung. Keine Testkörper/Fixtures ausgeführt.
Apply: je Stage fällige gefilterte N=3-Gruppe plus alle Control-Regressionen,
neue/geänderte Testdateien und relevante Commitplan-/Verifikationsregressionen.
Keine doppelte Schlusssuite. Verhaltensergebnisse stehen bis Apply aus.
Dieses Bundle installiert/startet keine Dienste und ändert keine lokalen
Betreiberdateien. LIVE.W/R/C und MOVE.W/R/C bleiben vollständiger geplanter Rest.
