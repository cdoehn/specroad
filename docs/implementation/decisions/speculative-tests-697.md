# SPECULATE-697 — ausdrücklicher Nutzerauftrag

Quelle: die bestätigte Besprechung und der anschließende Auftrag „baue es nun
ein“ vom 14. November 2026. Grundlage ist das erfolgreiche native Result
von Bundle 696, SHA-256
`e18c9969fa949a0f0e1008b06ddcb620dbc6f56a80b5da13cc70c329cdc46141`.
Normativ: Spezifikation 2.4.3.8 und 2.5. Kein optionaler Klärungspräfix:
Auswahlregel, Vorrang neuer Tests und Gewinnerabschluss sind ausdrücklich
beauftragt. Gegenüber einer Prognose-/Geschwindigkeitsheuristik ist die
gewählte Regel deterministisch und benötigt keine neuen Schätzwerte.
Frische Prozesse statt Wiederverwendung laufender Fixture-Zustände erhalten
Isolation und den vorhandenen bestätigten Abbruchpfad. Keine Produktzähler ändern.

| ID | Exakte Commitnachricht | Umfang und Abnahme |
|---|---|---|
| SPECULATE.W | `OFF-PLAN SPECULATE.W feat(tests): Freie Worker fuer parallele Testkopien nutzen` | Nutzbare lokale und Proxy-/SSH-Poolkopien: Warteschlange zuerst, atomare minimale globale Kopienzahl, verschiedene geeignete Hosts zuerst, stabile Identität ohne Geschwindigkeitsgewicht, eigene Prozesse und dauerhafte Versuche. Erster vollständiger Abschluss entscheidet, Unterprozesse der übrigen Kopien bestätigt beenden; Fehler erhalten, Messungen und Abdeckung getrennt. Eigenes versioniertes Format, alte MOVE-/LIVE-Verträge erhalten. Native Integration mit echtem Prozessbaum und getrennten Versuchsdaten. |
| SPECULATE.R | `OFF-PLAN SPECULATE.R fix(tests): Kopienrennen und Nachweise absichern` | Gleichzeitiger Abschluss, Start-/Abbruchrennen, fehlende Bestätigungen, echter Fehler einer Kopie, vollständige und abgebrochene Verlierer, Hostpause/limits und MOVE-Wechsel. Nachweismanipulationen abweisen, Migration und aktuelle Laufzeitwahl ohne Rückgriff absichern; zusätzliche lokale/Proxy-Integration. |
| SPECULATE.C | `OFF-PLAN SPECULATE.C refactor(tests): Kopienabschluss und Nachweise entflechten` | Reine strukturelle Bereinigung der Lebenszyklus-/Nachweisadapter und knappe Bedienungsdokumentation, unveränderte Ergebnisse, Ressourcen, Auswahl und Fehlerverträge. Sämtliche W/R- sowie relevante MOVE-/LIVE-/Historienregressionen Pflichtauswahl. |

W, R und C sind getrennte Zielstände mit eigenem Apply-Gate und anschließendem
Commit. Vorbereitet ist kein Testnachweis; Dev führt nur Collection, Syntax
und native Paketvalidierung aus. Keine Dienststarts, Installationen oder CI.
Nach dem erfolgreichen W-Gate reicht der Zielstand dieser Stage bis W; R/C
bleiben offen. Danach gilt wieder die priorisierte Produktposition 18.s.W.

Fehler- und Fortsetzungsbeleg: [Bundle 698](../history/bundle-698-speculative-correction.md).
Die vollständige Folge bleibt bis zu ihren jeweiligen erfolgreichen Gates offen.
