# START/CONFIG/LIVE/MOVE — bestätigte OFF-PLAN-Folge

Ausdrücklicher Nutzerauftrag vom 14. November 2026; normative Grundlage:
[Spezifikation 2.4.3.7](../../specification/SpecRoad_Spezifikation.md#2437-aktueller-ausgangsstand-und-vorausschauende-entwicklung--start-current-685).
Keine delegierte neue Detailklärung und kein künstlicher Klärungspräfix.
Die Produktpositionen bleiben 762/918. Diese zwölf OFF-PLAN-Commits werden
vor 18.s.W bearbeitet; danach folgt der bereits bestätigte Recovery-Rückbau.

## Reihenfolge und Abnahmen

W liefert den vollständig definierten nutzbaren Ausschnitt, R dessen robuste
Fehler-/Randfallbehandlung, C ausschließlich strukturelle Bereinigung.
Jede Tabellenzeile enthält Code, passende Verhaltenstests und Integration.

| ID | Commitnachricht | Vollständiger Umfang und Abnahme |
|---|---|---|
| START.W | `OFF-PLAN START.W feat(control): Neustart vom aktuellen Stand und Folgeplan` | Bedienbefehl `start --from-current`; native Momentaufnahme von HEAD plus Arbeitsbaum; neue konfigurierte Budgets ohne alte Kettenprüfung; Vormerkung bei laufendem Dev/Apply; atomarer neuer Laufzeitstand; alle zwölf Schritte im Plan; erweiterbarer vollständiger Korrekturpräfix. Prüfungen: alte beschädigte/erschöpfte Daten, dirty Stand, Fremdziel, Pause, Wiederholung, separate Leser, echte Stage-Reihenfolge und Fehler in angehängter Gruppe. |
| START.R | `OFF-PLAN START.R fix(control): Wiederanlauf und konkurrierende Uebergaben absichern` | Vorhandene Start-/Resume-/Statuswege einheitlich an den aktuellen Zyklus anschließen; ausstehende fremde Übergabe und gleichzeitige Bedienaktionen ohne Doppelauftrag behandeln; wiederholte Starts, Absturzfenster, verspätete Ergebnisse, Belegarchivierung und Pfad-/Linienwechsel robust prüfen; vorhandene alte Daten dürfen expliziten Neustart nicht als Herkunftskette sperren. Native Integration mit sauberem und dirty Beispiel-Repository, belegten Sperren und installiertem Entrypoint; keine laufenden Tests abbrechen. |
| START.C | `OFF-PLAN START.C refactor(control): Aktuellen Betriebszustand konsolidieren` | Wiederanlauf-/Statusadapter und Betriebsdokumentation strukturieren, überflüssige historische Abhängigkeiten im neuen Bedienpfad entfernen; gleiche maschinenlesbare Ergebnisse, Budgets, Sperren und Seiteneffekte; START.W/R-Regressionen vollständig erhalten. |
| CONFIG.W | `OFF-PLAN CONFIG.W feat(control): Lokale Budgets per CLI konfigurieren` | Lokale Konfiguration mit CLI lesen/setzen und expliziten Aufruf-Overrides; Korrektur-/Klärungsbudget und Klärungswahl jederzeit bedienbar, Standard jeweils zwanzig, kein fachlich fest verdrahtetes Maximum zwanzig; Änderungen an neuen Aufträgen ohne Dienstdeployment/Bundle. Zuständigkeit der Workerzahlen bei test-control; klare explizite Bedienwirkung statt Umdeutung schon versandter Aufträge. Persistenz und Start aus bestehenden Repositories integriert. |
| CONFIG.R | `OFF-PLAN CONFIG.R fix(control): Laufende Konfigurationswechsel absichern` | Gleichzeitige CLI-Aufrufe, ungültige Werte, atomare Speicherung, Priorität Aufruf vor Datei vor Standard, fehlende/kaputte Datei, laufender Dev-Turn und erschöpftes Budget; Bedienänderung am nächsten Dispatch eindeutig sichtbar, vorhandene Arbeit bleibt erhalten; Status meldet effektive Werte. |
| CONFIG.C | `OFF-PLAN CONFIG.C refactor(control): Konfigurationszugaenge vereinheitlichen` | Gemeinsame Validierung, CLI und Konfigurationszugriffe bereinigen; Bedienungsbeispiele und Status zusammenführen, Verhalten und CONFIG.W/R-Abnahmen unverändert. |
| LIVE.W | `OFF-PLAN LIVE.W feat(test-control): Worker je Host live steuern` | Eigenständige CLI test-control mit lokaler Config; gewünschte lokale/SSH-Worker pro laufendem Apply und Host einstellen, persistente Vorgaben und Aufruf-Overrides; dynamisch zusätzliche Worker starten, beim Reduzieren auslaufen lassen, null sperrt neue Zuteilung. Gemeinsames Hostlimit für Apply1/Apply2 und atomare Zuteilung integrieren; test-monitor zeigt Soll/Ist und Host. Keine Abbrüche bei Zahlenänderung. |
| LIVE.R | `OFF-PLAN LIVE.R fix(test-control): Dynamische Hostwechsel und Grenzen absichern` | Mehrere gleichzeitige Applies/CLI-Aufrufe, getrennte Linien, tote/verlorene SSH-Verbindung, falsche Python-/Umgebung, abgelehnte Worker, Hostgrenzen, ungültige Werte und Wiederanlauf; laufende Versuche behalten Zuordnung und niedrige CPU-/IO-Priorität. Lokale und SSH-Integration mit ungleichen Hostgeschwindigkeiten; keine Überbuchung oder verlorenen Tests. |
| LIVE.C | `OFF-PLAN LIVE.C refactor(test-control): Scheduler und Anzeige entkoppeln` | Gemeinsame Steuerdaten/Hostmodelle und Scheduleradapter konsolidieren; test-monitor bleibt lesend; gleiche Zuteilungen, Messungen und Fehlerverträge ohne neue Fachfunktion. |
| MOVE.W | `OFF-PLAN MOVE.W feat(test-control): Einzelnen Test auf anderem Worker neu starten` | CLI adressiert genau einen laufenden Testversuch und ein freigegebenes Ziel. Ursprungsversuch und Unterprozesse gezielt beenden, Ende bestätigen, frische Fixtures und neues Versuchskonto auf Ziel; keine Stackmigration und kein Parallel-Duplikat. Phasenmessung des abgebrochenen Versuchs ungültig, vollständige Wiederholung erforderlich; echte Testfehler bleiben sichtbar. |
| MOVE.R | `OFF-PLAN MOVE.R fix(test-control): Testverlagerung gegen Rennen absichern` | Zeitgleiches Fertigwerden/Fehlschlagen, Setup/Call/Teardown, Worker-/SSH-Ausfall, Abbruchbestätigung fehlt, Ziel ausgelastet oder inkompatibel, wiederholter CLI-Aufruf und Mehr-Apply-Kollisionen; keine fremden Prozesse beenden, keine Ergebnisse verlieren oder Erfolge erfinden. Hostübergreifende Integration und unveränderte Gate-/Fail-fast-Regeln. |
| MOVE.C | `OFF-PLAN MOVE.C refactor(test-control): Versuchslifecycle und Bedienung bereinigen` | Steuerung, Versuchszustände und Monitoransicht entflechten; gleiche Outcomes, Fehler und Zeitmessung. Gesamte START/CONFIG/LIVE/MOVE-Regression plus gezielte native Integration als Pflichtauswahl, keine zusätzliche doppelte Schluss-Suite. |

## Aktueller Übergang

START.W, START.W-FIX1, START.R/C und CONFIG.W/R/C sind erfolgreich übernommen.
[Bundle 691](../history/bundle-691-live-worker-identity.md) repariert den
vollständigen offenen LIVE.W/R/C-Rest nach fehlgeschlagenem W-Gate.
Der Zielstand dieser Stage reicht nach ihrem eigenen Gate bis **LIVE.W**;
danach ist **LIVE.R** offen. MOVE.W/R/C bleibt als nächste vollständige Gruppe
geplant. Die Live-Zuteilung wird zuerst mit echten lokalen und Proxyworkern
abgenommen; die separate gezielte Abbruch-/Neustartfunktion behauptet dieses
Bundle nicht. Alle zwölf IDs und ihre unveränderten vollständigen Abnahmen
bleiben erhalten.

Nach erfolgreichem Apply und expliziter Installation der getesteten Control-
Releasekopie kann der Betreiber mit `control start --from-current` sofort die
Automatik für die restliche Folge aktivieren. Dafür ist kein zweites Bootstrap-
Bundle und keine historische Kettenreparatur nötig. Dieses Entwicklungsbundle
führt weder Installation noch Start aus.

Die nächsten Bundles bereiten nach Möglichkeit etwa zwei zusammenhängende
W/R/C-Gruppen vor. Bei Fehlern bleibt zuerst der gesamte offene Rest bestehen;
nachrückende bereits geplante Stages können angehängt werden. Ein angebrochener
Rest wird nicht künstlich gekürzt, und jeder Zustand wird einzeln im Apply
geprüft und committed. Statische Dev-Prüfung und reine Collection sind kein
Verhaltenstestnachweis. Allgemeine Arbeitsregeln stehen in DEVELOPMENT.md
und Apply_Commit_Plans.md; Laufprotokolle gehören nicht in diesen Plan.

## Adapterkorrektur nach START.W

[START.W-FIX1 / Bundle 686](../history/bundle-686-checkpoint-path-value.md) behebt den nach der
erfolgreichen Apply-Abnahme gefundenen nativen Pfadtypfehler. Der bereits
committete START.W wird nicht wiederholt. Seine ausführliche native
Betriebsintegration und die übrigen START.R-Abnahmen bleiben offen;
Der aktuelle Übergang oben führt diese Abnahmen stageweise fort.
