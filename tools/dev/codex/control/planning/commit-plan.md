> Integration 556: Diese Datei dokumentiert die übernommene Control-Fachbasis.
> Aktuelle Quell-/Betriebs-/Testregeln: SpecRoad-Spezifikation 2.5.4 und
> OFF-PLAN CONTROL-INTEGRATION-556 im gemeinsamen Implementierungsplan.
> Control025 blieb ohne Commit; sein vollständiger Rest wird hier übernommen.
> Frühere Dev-Testpflichten und getrennte Repositorypfade sind historisch.

# SpecRoad Control – bestaetigter W/R/C-Plan

## OFF-PLAN MIXED-BUNDLE-025 — drei echte getrennte Zustaende

Basis: natives sauberes Result 1278aa, SHA-256
4035fa668ed40565d19df92e11ebda5651164ce88248898b4bb5d5611324f4f3;
HEAD 8df145f6441d6d71bb6930a20ef75c5504d95609, Bundle 024 erfolgreich.
Zuerst wurde das separate SpecRoad-Bundle 555 an Exchange uebergeben;
dieses Control-Bundle ist auf seine eigene Repositorybindung beschraenkt.

W: Vertrag 4, optionale Mischklassifikation, nativer Projektmarker,
Planrollen-/Resultbelege, dauerhaftes Budget und gebundene Restfortsetzung
sowie kompatible Retry-/Recoverypfade. Normalfall ohne Klaerung positiv pruefen.
R: Manipulation, ungueltige Marker/Typen, wiederholte Resultuebernahme,
Fehler vor/nach Klaerungscommit, falsche Restrollen, unklassifizierte Handoffs,
Pause/Neustart, Altvertragsgrenzen und Recoverybelege vervollstaendigen.
C: reine Strukturtrennung der V4-Fortsetzungsbelege, identische W/R-Testbytes.
Jeder Zustand erhaelt seine eigene parallele Verhaltenssuite vor dem Commit.
Keine Produktzaehler-/Ledger-/Konfigurationsaenderung und kein Dienststart.

R-Nachweisgrenze: Die Dev-Sandbox stellt beschreibbare Wurzeln mit leeren,
schreibgeschuetzten .git-Platzhaltern bereit und sperrt Socketoperationen.
Der lokale Vollsuite-Versuch wurde ohne Erfolgsbehauptung beendet. Neue
Protokollpruefungen verwenden eigene, eng begrenzte Dateipfad-Fixtures und
native Container-/Modelldoubles, keinen Socket und keine echten Benutzerdaten.
Die bestehenden Tests fuer Verzeichniszulassung/Transport bleiben unveraendert.
Alle drei Apply-Vollsuite-Gates bleiben verpflichtend vor ihren Commits.

R prueft orphanisierte Fortsetzungszeilen, Altbelege mit additiven Markerfakten,
vollstaendige Restkorrekturbindungen, widerspruechliche Fehlerrecords und
tatsaechliche Start-/Snapshotbelege. Unbekannte Handoffs erhalten keine neue
Klassifikation; schon geschriebene unveraenderte Dokumentmarker erhalten keine
pauschale Ausnahme vom gelieferten SpecRoad-Apply-Vertrag.


C trennt die drei unveraenderten Funktionen fuer Fehler-/Fortschrittsbelege
nach mixed_progress.py. AST-Vergleich bestaetigt alle gleichen Funktionskoerper;
die R-Testdateien bleiben bytegleich. 49 neue Protokollfaelle bestanden parallel
in R; die Vollsuite umfasst 881 Faelle und bleibt das verpflichtende Apply-Gate.


## OFF-PLAN BLOCKED-CHAIN-024: belegte Korrekturkette nach dev_blocked

Quelle: nativ vollstaendig geprueftes sauberes Control-Result
`specroad-control_Result_203248_1102_e04b2a.zip`, HEAD
`5e1bbe06ad0346c9fc0c48204d9bb3d484f35c54`, SHA-256
`34a7ab88735600768d78f6a6aee294f21c9f6ca950d89fca93dd1cfccfff478c`.
Bundle 023 ist in W/R/C mit 743/758/758 parallelen Tests abgeschlossen.
Der ausdrueckliche Nutzerauftrag erweitert die vorhandene Recovery fuer
Teil-Apply, Fehler-Result und erfolgreich korrigierten Rest. Hauptplan bleibt 6/6.

Entscheidung vor Umsetzung: Die direkte blocked-Recovery verlangt einen
unmittelbaren sauberen Erfolg. Die bisherige Restlauf-Recovery verlangt einen
klassifizierten pending-Handoff, fehlendes Originalresult und identische
Restnutzdaten. Beides deckt die neue Kette nicht. Ein Austausch von Seed oder
pending-SHA wuerde die Provenienz verlieren. Gewaehlt ist deshalb eine explizite,
additive Version-2-Vormerkung im bestehenden Recoveryablauf mit vollstaendiger
nativer Kette, passiven Plan-/Snapshotbelegen und unbekannter Klassifikation.
Keine neue Modellschleife und kein Zuruecksetzen der Klaerungsbefugnis.

- BLOCKED-CHAIN-024.W: feat(control): reconcile blocked work through a proven correction chain
- BLOCKED-CHAIN-024.R: fix(control): guard correction proofs and recovery adoption
- BLOCKED-CHAIN-024.C: refactor(control): isolate passive recovery snapshot validation

W liefert den ausdruecklichen Befehl, die vollstaendige passive Kettenpruefung,
versionierte Vormerkung und atomare Worker-Uebernahme mit erhaltenen Originalen.
R vervollstaendigt Grenzen, Dateirennen, Korruptions-, Wiederanlauf- und echte
isolierte Workerpruefungen. C trennt unveraenderte Snapshot-/Diffvertraege vom
Kettenbeweis. Jeder Zustand wird einzeln ausgebracht, vollstaendig parallel
getestet und erst danach committed. Bei Fehlern bleiben Teilcommits erhalten.
Dev/Apply starten keine echten Dienste und aendern keine produktiven Settings.
Spec, Plan und README dokumentieren die neue Bedienung vor Codeuebergabe.

R-Praezisierung: Dateibelege werden ueber einen nicht folgenden, nicht blockierenden
Dateideskriptor gebunden. Version-2-Fortschrittsbelege sind geschlossen; bereits
beanspruchte Zwischenresults/Pakete bleiben gesperrt. Die Transaktion prueft auch
identische Uebernahmefakten. Neue Negativ- und Workerfaelle decken diese Grenzen ab.
Lokale Integrationspruefungen sind durch den schreibgeschuetzten Sandbox-Mount
`/tmp/.git` blockiert. Der Nutzer beauftragt die Uebergabe an den Watcher trotz
dieser Umgebungsgrenze. Kein lokaler Vollsuite-Erfolg wird behauptet. Alle drei
unveraendert verpflichtenden Apply-Vollsuite-Gates bleiben vor ihren Commits.

Dev-Nachweisgrenze fuer Bundle 024: Die Sandbox stellt `/tmp/.git` als leeren,
schreibgeschuetzten Mount bereit; vorhandene Control-Fixtures lehnen dadurch
lokale Betriebsdaten ab. Der volle W-Testversuch konnte hier keinen Abschluss-
nachweis liefern und wurde beendet. Isolierte passive Pruefungen liefen; der
native lesende Beweis der echten Teil-Apply-/Korrekturkette war erfolgreich.
Die vom Nutzer danach ausdruecklich beauftragte Exchange-Uebergabe verlagert
keine Gates: vollstaendige parallele Apply-Tests bleiben je W/R/C zwingend,
bei Fehler kein Commit und keine naechste Phase. Keine erfolgreiche lokale
Vollsuite, menschliche Abnahme oder bereits erfolgte Installation behaupten.

C trennt acht unveraenderte Snapshot-/Diff-Funktionen nach apply_snapshot.py.
AST-Vergleich belegt gleiche Funktionskoerper sowie unveraenderte restliche
Kettenfunktionen; alle R-Testdateien bleiben bytegleich. Die bisherigen Import-
namen bleiben vorhanden. Keine neue Bedienung oder Entscheidungsbefugnis.
Die 29 unabhaengig laufenden passiven und In-memory-Transaktionspruefungen
bestanden in R; die Vollabnahme bleibt wegen der dokumentierten Dev-Sandbox offen.

## OFF-PLAN DISK-SPACE-023: konfigurierbarer Speicherstopp

Quelle: vollstaendig nativ geprueftes sauberes
specroad-control_Result_195304_1102_174075.zip; HEAD
4ec40a0b9743568848c92832818230bf3865e9e8, 717/717 Tests.
Source-SHA-256: 009cdc568dec97049596749b9ac926654252ee197ffbab3ebe0f9fe0d9f83bf1.
Der Nutzer beauftragt einen konfigurierbaren Stopp unter 10 GB. Hauptplan bleibt 6/6.

Entscheidung vor Umsetzung: Eine reine Startpruefung bemerkt keinen spaeteren
Platzverbrauch. Ein Zwangsabbruch verletzt die bestehende Lebenszyklusregel.
Der vorhandene Worker misst daher regelmaessig und schliesst zusaetzlich das
letzte Dispatch-Gate. Die kleine externe Limits-Datei haelt Betriebsgrenzen von
bereits hashgebundener Hauptkonfiguration/Recovery getrennt; kein Umschreiben
bestehender Belege. Der Watcher bleibt ausserhalb der Control-Steuerung.

- DISK-SPACE-023.W: feat(control): stop automation below configured free disk space
- DISK-SPACE-023.R: fix(control): guard disk pressure races and lifecycle recovery
- DISK-SPACE-023.C: refactor(control): separate storage limits from disk monitoring

W liefert externe Grenze/Bedienung, Dateisystemmessung, kontrollierten Worker-
Stopp und letztes Dispatch-Gate samt Verhaltenstests. R sichert Konkurrenz,
fehlerhafte Belege/Messungen, laufende Arbeit und Wiederanlauf ab. C trennt
unveraenderte Vertraege. Jede Stufe einzeln ausbringen, vollstaendig parallel
testen und erst danach committen. Vor Verpackung auch git diff --check gegen
jeden Vorgaengerstand, damit der letzte Commit nicht an Formatfehlern scheitert.
Kein echter Dienststart/Modellaufruf und keine lokale Config/Session-ID im Bundle.

R-Praezisierung: Dezimale Grenzwerte werden ohne binaere Rundungsueberhoehung
in ganze Bytes aufgerundet. Ein beim Messen gewechseltes Dateisystem oder ein
ungueltiger Workspace ist ein belegter Messfehler, keine Freigabe. Eine bereits
ausgeloeste Sperre bleibt auch bei Thread-Uebergabe erhalten; danach gemessene
Pfade folgen der neuen bestaetigten Workspace-Konfiguration. Grenzenwechsel
veraendern weder den vorgemerkten Apply-Nachweis noch die Hauptkonfiguration.
Die W-Suite bestand lokal 743/743 Tests; die echten Commit-Gates folgen im Apply.

C trennt die vier unveraenderten Konfigurationsfunktionen nach disk_limits.py.
Die bisherigen disk_space-Importnamen bleiben kompatibel. AST-Vergleich belegt
die unveraenderten Funktionskoerper; Verhalten und Bedienung bleiben gleich.
R bestand lokal 758/758 Tests. C durchlaeuft dieselbe volle Suite vor dem Commit.

## OFF-PLAN APPLY-RECONCILE-021: erfolgreichen Restlauf uebernehmen

Quelle: nativ geprueftes sauberes specroad-control_Result_173238_1102_377b93.zip,
HEAD 0d88a30adde4c5a9b3406a8f0e9ab6f4c309d1c8, 659 parallele Tests.
Source-SHA: 81ef3182f3d6c4e4ada9cbdda4d9cc3c6d797d271ff844f2b1e86555778c75c1.
Nutzerauftrag: zuerst die nach Datentraegermangel unterbrochene Kette reparieren;
Automatik noch nicht starten. Hauptplan bleibt 6/6.

Entscheidung vor Umsetzung: Reset oder Austausch der alten pending SHA wuerden
Belege und Budgets umdeuten. Ein ungeprueftes Erfolgssignal reicht nicht. Ein
expliziter enger Fortsetzungsnachweis mit additiver Vormerkung erhaelt dagegen
die gesamte Historie und funktioniert aus dem aktiven Chat ohne Modellschleife.
Der bestehende Worker darf ihn erst nach gesondertem Start und bei Inaktivitaet
abschliessen. Keine neue Dienst-/Timerstruktur oder automatische Fortsetzung.

- APPLY-RECONCILE-021.W: feat(control): queue proven Apply continuation recovery
- APPLY-RECONCILE-021.R: fix(control): guard continuation proofs and recovery races
- APPLY-RECONCILE-021.C: refactor(control): isolate Apply reconciliation history

W liefert den engen passiven Planvergleich, native Artefaktkette, Bedienbefehl,
private Vormerkung, atomare Worker-Uebernahme und Verhaltenstests.
R haertet Beleg-, Restart-, Ressourcen- und Transaktionsgrenzen mit Negativtests.
C trennt dieselbe Persistenzlogik ohne neues Verhalten. Jede Stufe einzeln
ausbringen, vollstaendig parallel testen, committen; erst danach die naechste.
Kein Live-Status, Konfiguration, Zugangsdaten oder Session-IDs im Payload.

R-Abnahme ergaenzt Vollstaendigkeit des minimalen ZIP-Payloads, exakte
Literalgrenzen, geschlossene Vormerkbelege, erneute Pruefung am Uebergang und
Wiederanlauf nach atomarem Rollback. Neue Modellarbeit darf auch nach einer
abgeschlossenen Uebernahme nur aus weiterhin belegten Artefakten beginnen.
Die W-Verhaltenssuite bestand lokal 689/689; Zielcommits belegt erst Apply.

C trennt die unveraenderten History-/Transaktionsfunktionen in
apply_reconcile_history.py. Bestehende Importnamen bleiben kompatibel.
AST-Vergleich bestaetigt alle sieben verschobenen Funktionskoerper. Die
R-Suite bestand lokal 717/717 Tests; C hat dieselben Verhaltensvertraege.
Keine neue Bedienfaehigkeit, kein Config-/Status-/Dienstzugriff durch Apply.

### Technische C-Fortsetzung, Bundle 022
Result specroad-control_Result_194315_1102_2bf215.zip ist vollstaendig nativ
geprueft (SHA-256 0bf1418a74bdac70f04a75842b8526c959d504a10f7caa1a96a344aeb616297c).
W wurde als 27766199fab03a99aa41bb1f980495edba41c1ae committed (689/689),
R als 6c9d44302bc74ba5290eb25be7c3c43185d6ae83 (717/717). Auch C bestand
717/717; allein git diff --check sperrte den C-Commit wegen einer zusaetzlichen
Leerzeile am Dateiende von apply_reconcile.py. Der erhaltene uncommittete
C-Zustand bleibt Basis. Bundle 022 entfernt nur diese Leerzeile und dokumentiert
den Befund; kein neues Verhalten und kein erneutes W/R. C wird nochmals
vollstaendig parallel getestet und erst danach als APPLY-RECONCILE-021.C committed.

## OFF-PLAN THREAD-WORKSPACE-020: stabiler Workspace mit Schreibzugriff

Quelle: nativ vollstaendig geprueftes sauberes
`specroad-control_Result_063619_1102_1167dd.zip`, HEAD
`4ef37fdf5cbf892eca4839903dc1cfec49761f95`, Abschluss von 019.C mit
619/619 parallelen Tests. Source-SHA-256:
`fc829a3af898466d85cde70e9f7d8e50ee16374bae9f01e023941c174b7b3984`.
Nutzerauftrag vom 2. November 2026 einschliesslich der ausdruecklichen
Praezisierung: Schreibzugriff auf den gesamten konfigurierten Eltern-Workspace.
Der Produktplan bleibt 6/6; dies ist eine eigenstaendige OFF-PLAN-Korrektur.

- THREAD-WORKSPACE-020.W: fix(control): keep configured thread workspace and write access
- THREAD-WORKSPACE-020.R: fix(control): guard workspace dispatch and historical receipts
- THREAD-WORKSPACE-020.C: refactor(control): centralize thread execution scope

Entscheidung vor Umsetzung: Nur cwd zu verschieben wuerde alte Rechtebelege
mehrdeutig machen. Ein neuer Thread oder eine Config-/History-Migration ist
unnoetig. Der bereits explizit konfigurierte thread_cwd bestimmt daher cwd
und produktive Schreibwurzeln beider Transporte; neue Receipts binden beides.
Die freigegebene Elternwurzel umfasst auch Apply/Control. Fachliche Auftraege,
Apply-Uebergabe, bestehende Recovery-Nachweise und Bedienregeln bleiben getrennt.

W liefert den vollstaendigen nutzbaren Ablauf fuer beide Transporte und
Legacy-Konfigurationen. R sichert spaete Pfadwechsel, fehlerhafte Bindungen
und unveraenderte historische Belege ab. C trennt dieselben Scope-Funktionen
ohne neues Verhalten. Jeder Zustand wird einzeln ausgebracht, vollstaendig
parallel getestet und erst danach committed. Bei Fehler kein naechster Zustand.
Keine Dev-Commits, keine echte Konfigurationsaenderung oder Dienstbedienung.

R prueft die konfigurierte Pfadgrenze erneut vor der Anbindung und direkt
nach der Dispatch-Freigabe. Fehlende, fremde oder inzwischen verlinkte
Workspace-Verzeichnisse starten weder einen Turn noch einen exec-Prozess.
Neue und historische Dispatch-Belege bleiben bytegleich; Abweichungen bei
cwd, Schreibwurzeln, Approval oder Netzwerk sperren die Fortsetzung.

C zentralisiert execution_directory, writable_roots und policy unveraendert
in execution_scope.py. Die bisherigen Importnamen bleiben kompatibel.
AST-Vergleich der drei Funktionskoerper und unveraenderte R-Tests sichern die
rein strukturelle Aenderung ab; keine neue Befugnis oder Bedienaktion.

## OFF-PLAN DEFERRED-HANDOVER-019: Uebergabe aus dem laufenden Chat

Quelle: erfolgreiches `specroad-control_Result_051107_1102_5e4108.zip`,
HEAD f4ac34915c10b864468fa7bb153edd84e56d7004, 587 Tests. PLAN bleibt 6/6.
Nutzerauftrag vom 2. November: Korrektur bauen, ueber Exchange anwenden und
den bereits beauftragten Start nach Ende des aktiven Chats ermoeglichen.

- DEFERRED-HANDOVER-019.W: feat(control): defer thread handover until both threads are idle
- DEFERRED-HANDOVER-019.R: fix(control): preserve deferred handover authority across lifecycle boundaries
- DEFERRED-HANDOVER-019.C: refactor(control): isolate deferred handover evidence and worker policy

Entscheidung vor Umsetzung: keine Ruecksetzung der alten Threadmetadaten,
kein Aufweichen der neuen Dev-Grenzen und kein wartender Modellturn. Ein
explizit gebundenes altes cwd plus dauerhafter Auftrag im bestehenden Worker
loesen beide Blockaden. Neue Threads und externe Timer sind unnoetig.
W liefert Auftrag, Beobachtung, Uebergabe und isolierte Verhaltenstests.
R haertet Fehler, Wiederanlauf, Publikationsgrenzen und IPC-Races.
C trennt den geprueften Ablauf ohne neues Verhalten. Je Phase vollstaendige
parallele Control-Suite vor dem zugehoerigen Apply-Commit.

R konkretisiert die Reihenfolge am Abschluss: Freigabe/Pause speichern, Auftrag
archivieren, Startsperre entfernen, erst dann normaler Engine-Dispatch.
Fehlerpfade erhalten fremde Belege; Status ohne Worker bleibt aussagekraeftig.
Der Abschluss prueft die additive Receipt und die erhaltene History nochmals;
verwaiste Statusdateien bleiben gesperrt, die Startsperre faellt zuletzt.

C trennt die unveraenderten Belegfunktionen nach handover_request.py.
handover_queue.py behaelt Vormerkung und Worker-Policy; kein neues Verhalten.
AST-Vergleich bestaetigt alle unveraenderten Funktionskoerper und Schemas.

## OFF-PLAN THREAD-HANDOVER-018: sichere Dev-Thread-Uebergabe

Quelle: nativ geprueftes sauberes Result
`specroad-control_Result_122617_1029_7a318d.zip`, Abschluss
`709e8751ba905aa5736017ba83daaedfd25abda1`; Bundle 017, 536 parallele Tests.
Der Nutzerauftrag vom 1. November 2026 bereitet einen expliziten Threadwechsel
mit erhaltener Historie und gesonderter Metadaten-cwd-Bindung vor. PLAN bleibt 6/6.

- THREAD-HANDOVER-018.W: feat(control): preserve history across explicit thread handover
- THREAD-HANDOVER-018.R: fix(control): guard interrupted handovers and thread boundaries
- THREAD-HANDOVER-018.C: refactor(control): separate handover history from orchestration

W liefert den Offline-Befehl, gepruefte ruhende Uebergabegrenzen, begrenzte
cwd-Zuordnung, Transaktionsjournal und isolierte Verhaltenstests.
R prueft und haertet Wiederaufnahme, Belegkorruption, Lock-/Datei-/Protokollgrenzen.
C trennt dieselben Vertraege ohne neues Verhalten. Jeder Zustand wird einzeln
parallel getestet und im Apply erst nach seinem Gate committed.

R konkretisiert die exakte Metadatenbestaetigung, bindet exec explizit an Dev,
validiert Belegschema und Hashkette bei normalen Ledgerzugriffen und prueft
Scope/Receipt auch nach der Konfigurationspublikation. Abbruch- und Race-Tests
muessen fehlende Belege weiterhin sperren, ohne Budgets/Altauftraege zu aendern.

C extrahiert die unveraenderten Datenbankfunktionen nach handover_history.py,
teilt Belegkodierung/Fehlervertrag und verwendet contextlib fuer die Lebensdauer
des Ledgers. Kein neuer Befehl, keine neue Befugnis und keine Live-Migration.

Entscheidung vor Umsetzung: Ein blosses Umschreiben der Config oder des
Ledger-Scope wuerde alte Thread-Belege umdeuten und Crashfenster verdecken.
Eine neue leere History wuerde Claims und Budgets verlieren. Gewaehlt ist ein
eigener expliziter Befehl mit unveraenderten Altauftraegen, additivem Beleg und
gesperrter Zwischenphase. Metadaten-cwd wird separat bestaetigt; das tatsaechliche
Dev-Verzeichnis und die Schreibwurzeln bleiben unveraendert. Kein Dienststart,
keine produktive Uebergabe und keine Live-Remote-Erfolgsbehauptung durch das Bundle.

## Korrekturlieferung 015: drei aufeinanderfolgende Klaerungen (FIX11)
Quelle: specroad-control_Result_073642_1022_9ddb31.zip; sauberer Abschluss
f05c6510d85a7269faf06dc5a38cf95a1e7ca51a. Nutzerauftrag vom 26.10.2026:
Control-Bundle mit Dreierbudget bauen und durch den bestehenden Watcher einspielen.
SpecRoad-Delegation und Dienst-/Dev-Neustart sind separate Schritte. PLAN bleibt 6/6.

- 2.W-FIX11: Fix: 2.W-FIX11 support three consecutive clarification bundles
- 2.R-FIX11: Fix: 2.R-FIX11 guard clarification budgets and legacy evidence
- 2.C-FIX11: Fix: 2.C-FIX11 isolate clarification budget transitions

W: Vertrag 3, persistent gebundene Restplaetze, begrenzte Folgeauftraege,
   Altvertraege erhalten und neue Befugnis nur nach nachgewiesenem normalen Apply.
R: Korruption, atomarer Rollback, Wiederanlauf, Overload und Recovery absichern.
C: dieselben Budgetvertraege strukturell trennen, ohne neues Verhalten.
Je Zustand: Aenderung, parallele Verhaltenssuite, eigener Commit. Drei echte
Zwischenstaende in einer ZIP. Kein Watcher-, Config-, Dienst- oder Dev-Eingriff.

## Korrekturlieferung 014: begrenzte Spezifikationsklaerung (FIX10)
Quelle: specroad-control_Result_200022_1020_244c13.zip, sauberer Stand
b58cbfe8776806b9f888590ce1c63e757b413255. Nutzerauftrag vom 22.10.2026:
Control-Seite der vereinbarten begrenzten Entscheidungsbefugnis als ein Bundle.
Die eigenstaendige SpecRoad-Delegation ist nicht Teil dieser Lieferung.
Planstand bleibt 6/6. Drei echte Zwischenstaende:

- 2.W-FIX10: Fix: 2.W-FIX10 support bounded specification clarification handoffs
- 2.R-FIX10: Fix: 2.R-FIX10 preserve decision authority across retries and recovery
- 2.C-FIX10: Fix: 2.C-FIX10 separate decision history from result lifecycle

W: versionierte Auftraege, bedingte fachliche Befugnis, eigener Handoff-Status,
   persistentes Folge-Budget und automatische normale Result-Verarbeitung.
R: alte Promptbelege, Neustart, atomare Uebergaenge, manipulierte Belege,
   Pause/Stopp sowie Overload-/Recovery-Grenzen absichern.
C: gepruefte Vertrags-/Historylogik trennen, ohne neues Verhalten.
Je Zustand Aenderung -> parallele Verhaltenstests -> eigener Commit.
Keine produktiven Modellaufrufe, Dienste oder externe Jobs veraendern.
Erfolg am Ziel erst nach dem folgenden Apply/Result bestaetigt.

## Korrekturlieferung 013: Overload mit laufender Hintergrundarbeit (FIX9)

Quelle: specroad-control_Result_044558_1020_f7fe3a.zip, sauberer Stand
6f1311a3ffa5a06a557797868cf2014ac4c37df6. Ausdruecklicher Nutzerauftrag:
die geplante Korrektur als eine ZIP mit drei echten Zwischenstaenden nach Exchange.
Die sechs PLAN-Positionen bleiben abgeschlossen (6/6).

- 2.W-FIX9: Fix: 2.W-FIX9 observe pending overload work before continuation
- 2.R-FIX9: Fix: 2.R-FIX9 guard overload observation and recovery across restarts
- 2.C-FIX9: Fix: 2.C-FIX9 separate overload waiting from dispatch policy

W: dauerhafter Beobachtungszustand, begrenzte Nachlaufzeit fuer Exitbelege,
   bestehendes Backoff, Bundle-Vorrang, explizite moderne Offline-Recovery.
R: Restart, Pause/Stop, Belegkorruption, Budget, Publikations-/Dispatch-Races
   und echte isolierte Worker-/Unix-Socket-Ablaufe pruefen und absichern.
C: dieselben Vertraege strukturell trennen, ohne neues Verhalten.
Je Zustand Aenderung -> parallele Verhaltenstests -> Commit. Keine Dienste
bedienen, keine echten Modellaufrufe, keine externe Config oder Jobs aendern.
Erfolg am Ziel erst durch den folgenden Apply/Result-Lauf bestaetigt.

## Korrekturlieferung 012: erhaltene Entwicklung fortsetzen (FIX8)

Quelle: specroad-control_Result_161833_1019_63de35.zip, sauberer Stand
f0a5337e36ecc6ece8901b44ab769f9b876e24c4. Ausdruecklicher Nutzerauftrag:
teilweise fertige Entwicklung nach bestaetigtem Overload automatisch fortsetzen,
ohne alte Aktionen blind zu wiederholen oder Control dafuer manuell zu stoppen.
Die sechs PLAN-Positionen bleiben abgeschlossen; keine neue Produktentwicklung.

- 2.W-FIX8: Fix: 2.W-FIX8 continue preserved work after proven overload
- 2.R-FIX8: Fix: 2.R-FIX8 bind continuation checkpoints and dispatch races
- 2.C-FIX8: Fix: 2.C-FIX8 separate continuation observation and evidence

W: eigener Fortsetzungsprompt, strenge Inaktivitaetsbelege auch bei systemError,
erhaltene lokale Arbeit, persistentes gemeinsames Backoff-Budget, Bundle-Vorrang.
R: Restart-, Receipt-, History-, Publikations- und Dispatch-Races absichern.
C: dieselben Verhaltensvertraege strukturell trennen; kein neues Verhalten.
Jeder Zustand: Aenderung -> parallele Verhaltenstests -> Commit, erst dann
naechster Zustand. Eine ZIP, drei echte Zwischenstaende. Keine realen Modell-
oder Dienstaufrufe, kein Watcher-/Config-/State-Eingriff beim Entwickeln/Apply.

## Korrekturlieferung 011: gebundenes Ergebnis nach dev_blocked (FIX7)

Quelle: specroad-control_Result_095850_1019_4e2cda.zip, sauberer Stand
023d7f612e6c987b31f78d8735e1772d1e4b36be. Expliziter Nutzerauftrag:
Control-Korrektur zur beleggestuetzten Wiederaufnahme nach fachlicher Klaerung.
Die sechs PLAN-Positionen bleiben abgeschlossen. Geordnete Zwischenstaende:

- 2.W-FIX7: Fix: 2.W-FIX7 recover blocked work from a proven Apply chain
- 2.R-FIX7: Fix: 2.R-FIX7 preserve recovery evidence and recheck adoption
- 2.C-FIX7: Fix: 2.C-FIX7 separate blocked recovery proof from lifecycle

Je Zustand eigene Aenderung, `python3 -B tools/test_parallel.py`, dann Commit.
Kein produktiver Modellaufruf, keine Recovery oder Dienstbedienung im Entrypoint.
W implementiert den expliziten Erfolgsweg und negative Paket-/Resultgrenzen.
R sichert Abschlussbelege, erneute Inaktivitaetspruefung und dauerhafte Zuordnung.
C trennt die bestehenden Vertraege ohne neues Verhalten. Erfolg erst aus Apply.

Quelle: Nutzerauftrag im Chat vom 18.10.2026. Spezifikation: ../spec/SPECIFICATION.md.
Geplant: 2 Funktionspakete, 6 echte Zwischencommits. Die Grundsteuerung umfasst 1.W–1.C.
Korrekturlieferungen zaehlen als eigene PatchHarbor-ZIPs, nicht als neue Planpositionen.
Der Apply-Log und der danach erzeugte Result-Snapshot belegen den tatsaechlichen
Commitfortschritt, nicht die blosse Existenz dieser Planung.

| Position | Kennung | Commit-Message | Inhalt |
| --- | --- | --- | --- |
| 1/6 | 1.W | feat(control): 1.W manual service lifecycle | Nutzbarer Grunddienst und Bedienung, externe Konfiguration |
| 2/6 | 1.R | fix(control): 1.R harden lifecycle and local state | Fehlervertraege, Wiederaufnahme, Prozess- und Dateisicherheit |
| 3/6 | 1.C | refactor(control): 1.C separate lifecycle boundaries | Struktur bereinigen, gleiches Fachverhalten |
| 4/6 | 2.W | feat(control): 2.W resume the configured Dev thread | Result-Ereignisse und explizite Dev-Session-Fortsetzung |
| 5/6 | 2.R | fix(control): 2.R guard result binding and recovery | Zuordnung, keine Doppelverarbeitung, sichere Wiederaufnahme |
| 6/6 | 2.C | refactor(control): 2.C simplify development automation | Bereinigung und finale Bedienanleitung |

Jeder Zwischenstand wird einzeln ausgebracht, parallel getestet und erst dann
committed. Ein fehlerhafter Zwischenstand stoppt die Folge. Vorherige Commits
bleiben erhalten. Kein vorab ausgebrachter Endzustand, kein Rollback, kein Push.
Die echte systemd-Installation erfolgt explizit per ./control install, nicht
waehrend Apply. Das installiert ohne enable und ohne Dienststart.

## Korrekturlieferung 003 zur Grundsteuerung
Quelle: specroad-control_Result_082403_1018_05c089.zip.
1.W wurde erfolgreich als ef32c66c38dd9aeaf31fc3d8c1164f21d6922e4a committed.
Die nicht committeden R-Aenderungen aus diesem Result bleiben Ausgangspunkt.
Diese Lieferung korrigiert deren Verzeichniserstellung und liefert genau die
noch offenen PLAN-Commits 1.R und 1.C. Kein erneuter W-Commit, kein zusaetzlicher
FIX-Commit und keine vorgezogene Codex-Automatisierung. Erfolg der beiden offenen
Commits wird ausschliesslich durch den folgenden Apply/Result-Lauf bestaetigt.

## Lieferung 004: Entwicklungsautomatik, 2.W -> 2.R -> 2.C
Quelle: specroad-control_Result_085555_1018_948f56.zip. Die Grundsteuerung ist dort
als 1.W ef32c66, 1.R 1163fc8 und 1.C 5685979 erfolgreich und sauber nachgewiesen.
Diese Lieferung fuehrt nur Positionen 4 bis 6 aus. Die drei Zwischenstaende
werden echt nacheinander geschrieben, parallel getestet und committed.

2.W: opt-in Konfiguration, native Result-/Patch-Pruefung, inotify, persistente
Zuordnung und genau ein expliziter exec-resume-Auftrag, dann Linux-Warten.
2.R: Fehler- und Wiederanlaufabsicherung, sichere manuelle Rekonstruktion ohne
Wiederholung unklarer Arbeit, bestehender App-Server als explizite Alternative.
2.C: gleiche Verhaltensvertraege bei getrennter Protokoll-/Ablaufstruktur.
Lokale Installation, Konfiguration, Probe und echter Dienststart sind getrennte
Nutzeraktionen nach Apply, niemals Bestandteil des Patch-Entrypoints.

## Korrekturlieferung 005: einmalige Startquelle nur im State
Quelle: specroad-control_Result_103350_1018_0a575c.zip, sauberer Stand efaa625.
Dort sind alle sechs PLAN-Commits abgeschlossen. Der explizite Nutzerauftrag
korrigiert nur die Trennung von dauerhafter Konfiguration und Laufzeitzustand.
Keine neue PLAN-Position; der erreichte Planstand bleibt 6/6.

Drei echte FIX-Zwischenstaende desselben Ausschnitts in einer ZIP:
- 2.W-FIX1 (Bezug 4/6): Fix: 2.W-FIX1 store initial Result in runtime state
- 2.R-FIX1 (Bezug 5/6): Fix: 2.R-FIX1 preserve bootstrap history on setup and migration
- 2.C-FIX1 (Bezug 6/6): Fix: 2.C-FIX1 separate bootstrap setup from persistent configuration

W: einmalige explizite State-Initialisierung, kein Seed in neuer Konfiguration,
   Fortsetzung ausschliesslich aus der vorhandenen History.
R: atomare Ersteroeffnung, sichere explizite Legacy-Uebernahme, Fehler-/Konflikt-
   und Wiederanlaufpruefungen ohne Reset bereits erfolgter Arbeit.
C: dieselben Vertraege mit getrennten Bootstrap-/Bediengrenzen; kein neues Verhalten.
Jeweils eigene Aenderungen, parallele Verhaltenstests, erst danach eigener Commit.
Der folgende Apply/Result-Lauf muss den Erfolg dieser FIX-Commits noch belegen.

## Korrekturlieferung 006: Codex-Daemon-Transport (2.W/R/C-FIX2)
Quelle: specroad-control_Result_161848_1018_ea2e5a.zip, sauberer Commit 9f2919f.
Die sechs geplanten Haupt-Commits und FIX1 bleiben unveraendert. Es folgen
nur drei echte, aufeinanderfolgende Korrektur-Zwischenstaende:
- 2.W-FIX2 (Bezug 4/6): Fix: 2.W-FIX2 connect to the existing Codex Unix WebSocket
- 2.R-FIX2 (Bezug 5/6): Fix: 2.R-FIX2 validate WebSocket frames and failures
- 2.C-FIX2 (Bezug 6/6): Fix: 2.C-FIX2 separate daemon wire transport from Codex RPC

W: Direkter lokaler WebSocket auf dem existierenden daemon Unix-Socket;
   konfigurierte thread.id und cwd bleiben bindend, kein Daemon-Start.
R: Handshake-, Frame-, Ping-/Fragment-, Laengen- und Fehlervertragspruefungen.
C: Trennung von RFC6455-Transport und Codex-RPC ohne Verhaltensaenderung.
Jeweils eigene Aenderungen, parallele Verhaltenstests, Commit erst nach gruenem
Gate. Der echte Laptop-Apply belegt erst spaeter den erreichten Commitstand.

## Korrekturlieferung 007: Codex-Socket-Link (2.W/R/C-FIX3)

Quelle: `specroad-control_Result_164305_1018_74094a.zip`, sauberer Commit
`b8ec97833c852b9879f1ce45a34271295fa43721`. Der Nutzer beauftragte
die Korrektur des unter Ubuntu real vorhandenen, benutzereigenen Symlinks
auf einen privaten Codex-Daemon-Socket in `/tmp/codex-daemon-<uid>/`.

- `2.W-FIX3` (Position 4/6): Codex-privaten Socket-Link erkennen und benutzen.
- `2.R-FIX3` (Position 5/6): Ziel-/Rechte-/Identitaetspruefung, Linux-
  Peer-Credentials und Schutz vor Pfadwechseln absichern.
- `2.C-FIX3` (Position 6/6): Socket-Sicherheitsgrenzen von WebSocket-
  Protokollgrenzen trennen ohne neues Verhalten.

Jeder Zustand ist eigenstaendig, parallel getestet und erst dann committet.
Die sechs Hauptpositionen bleiben abgeschlossen. Kein Systemstart, keine
Veraenderung bestehender lokaler Konfiguration oder Daemons.

## Korrekturlieferung 009: bestaetigte Modellueberlastung und Journal

Quelle: `specroad-control_Result_061712_1019_6efed4.zip`, sauberer Stand
`ae7e2917ead0f7adb72d1f8d264a93a490c4fc43`. Nutzerauftrag vom 19.10.2026:
mehrstuendige aktive Turns erhalten, bestaetigte Ueberlastungen sicher behandeln,
Fehlerursache und Entscheidungen im Journal sichtbar machen. PLAN bleibt 6/6.

- 2.W-FIX5 (Bezug 4/6): Fix: 2.W-FIX5 retry proven overloads and log decisions
- 2.R-FIX5 (Bezug 5/6): Fix: 2.R-FIX5 preserve evidence and guard recovery
- 2.C-FIX5 (Bezug 6/6): Fix: 2.C-FIX5 separate retry policy and observation

W: Terminalfehler getrennt von Stille erkennen, genaue Turn-Identitaet ohne
Modell pruefen, streng begrenzte Read-only-Turn-Wiederholung mit persistentem
Backoff und strukturierten Journal-Ereignissen. Jedes erneute Modellstarten ist
ein neuer dokumentierter Versuch desselben Auftrags, keine neue Result-Claim.
R: Beleg-/Datei-/Race-/Restart-Absicherung, explizite sichere Legacy-Recovery und
lesende Statusklaerung nach Verbindungsabbruch. Unbekannt bleibt blockiert.
C: dieselben Vertraege strukturell trennen; keine neue Faehigkeit.
Kein Daemon-Neustart, keine echte Config-/State-Aenderung beim Apply, kein
Modellwechsel und kein Autostart. Erfolg jedes Zwischenstands erst nach dessen
parallelem Gate und echtem Commit auf dem Zielrechner.

## Korrekturlieferung 010: grosse Codex-Antworten (2.W/R/C-FIX6)
Quelle: specroad-control_Result_085003_1019_91d4ee.zip, sauberer Stand
ed11794349044b1eb6db39e475e099b1a524b14f. Nutzerauftrag vom 19.10.2026:
Recovery bei langen Threads ohne 2-MiB-Abbruch, bevorzugt gezielte Status-/Turn-
Abfragen, weiterhin begrenzte Ressourcen und eindeutige Journalfehler.

- 2.W-FIX6 (Bezug 4/6): Fix: 2.W-FIX6 accept bounded large Codex responses
- 2.R-FIX6 (Bezug 5/6): Fix: 2.R-FIX6 read targeted turn evidence with bounded pagination
- 2.C-FIX6 (Bezug 6/6): Fix: 2.C-FIX6 separate turn history from wire limits

W: Empfangsbudget erweitern, Ausgabebudget unveraendert, spezifischen Fehler
und strukturierte Byte-Grenzen protokollieren.
R: Nur Turn-Metadaten suchen, Items des exakten Turns paginieren; explizit
nicht unterstuetzte APIs begrenzt kompatibel behandeln. Unvollstaendige Daten,
Seiteneffekte, Aktivitaet und Ressourcenfehler erlauben weiterhin keinen Retry.
C: dieselben Vertraege in getrennten Modulen, keine neue Funktionalitaet.
Jeder Zwischenstand: Aenderung, parallele Tests, Commit, erst dann naechster.
Planstand bleibt 6/6. Kein Reset, Modellaufruf, Dienststart oder Config-Update.
