# CONTROL-RECOVERY-593 — ausdrückliche Ergänzung vom 5. November 2026

Für die neue opt-in Bedienaktion `reconcile-blocked --extended-chain` und den
nativen Watcher-Timeoutadapter gilt die übergeordnete SpecRoad-Spezifikation
0.2.62, Abschnitt 2.5.4.3, einschließlich der W/R/C-Abnahmen im aktiven
Implementierungsplan. Die historische Ein-Korrektur-Regel unten bleibt für
`reconcile-blocked` ohne diesen Schalter unverändert. Eine nachgewiesene
Timeout-/Mehrkorrekturkette verlangt explizit Version 3 der Vormerkung;
alte Belege werden weder migriert noch als neue Befugnis ausgelegt.

> CONTROL-SOURCE-SELECTION-566: exakte Result-SHA nach SpecRoad 2.5.4.2;
> keine History-Umschreibung oder Budgeterneuerung durch Paketzuordnung.

> CONTROL-START-DELAY-564: aktuelle normative Startfrist und Statusvertrag
> in SpecRoad-Spezifikation 2.5.4.1; Standard 60 s, konfigurierbar 0..86400.

> CONTROL-CLARIFICATION-560: Zusätzlich gilt SpecRoad-Spezifikation 2.4.3.2
> für den ausdrücklichen budgeterhaltenden Übergang auf einen neuen V4-Auftrag.
> Alte Versuche bleiben unverändert; Recovery/Installation allein geben nichts frei.

> Integration 556: Diese Datei dokumentiert die übernommene Control-Fachbasis.
> Aktuelle Quell-/Betriebs-/Testregeln: SpecRoad-Spezifikation 2.5.4 und
> OFF-PLAN CONTROL-INTEGRATION-556 im gemeinsamen Implementierungsplan.
> Control025 blieb ohne Commit; sein vollständiger Rest wird hier übernommen.
> Frühere Dev-Testpflichten und getrennte Repositorypfade sind historisch.

# SpecRoad Control – Spezifikation

## OFF-PLAN MIXED-BUNDLE-025: Vertrag 4 mit optionaler Klaerung

Ausdruecklicher Nutzerauftrag vom 3. November 2026: normale Spezifikations-
luecken nach gepruefter Empfehlung klaeren und danach sinnvolle vollstaendige
Plancommits in derselben ZIP liefern. Der Klaerungscommit bleibt OPTIONAL.
Ohne notwendige normative Klaerung gibt es ausschliesslich Plan-/Korrektur-
commits und patch_ready. Bei zulaessiger Klaerung genau ein Dokumentcommit
zuerst, danach echte Umsetzung; Status patch_ready_with_clarification.

Die Projektbefugnis stammt aus SpecRoad SPECROAD-DECISION-1 und dessen neuer
Regel 2.4.3.1, nicht aus Control. Native Resultvalidierung muss die installierte
Unterstuetzung anhand verification/development_contract.json belegen. Der
Marker ist streng typisiert: Format 1, decision_rule SPECROAD-DECISION-1,
decision_contract_version 4, bundle_plan_format_version 2, mixed_status
patch_ready_with_clarification, clarification_limit 3, max_clarification_stages
1, clarification_position prefix, implementation_required true. Fehlender
Marker erlaubt kein v4; falscher vorhandener Marker ist keine stille Freigabe.

Vertrag 4 enthaelt version=4, clarification_allowed (Boolean),
clarification_limit=3, clarifications_remaining (Ganzzahl 0..3, kein Boolean)
und clarification_continuation (Boolean). Fortsetzung und neue Erlaubnis
schliessen sich aus. Rest 0 erlaubt keine neue Klaerung. Die Fortsetzung gilt
nur fuer den aus einem authentischen Fehler-Result belegten noch offenen
Klaerungspraefix, dessen angekuendigte Zieldateien bytegleich bleiben muessen.
Vier Antwortfelder bleiben. spec_clarification bleibt den Altvertraegen 2/3
vorbehalten. V4 hat patch_ready, optional patch_ready_with_clarification,
blocked und no_work. Kein reines automatisches Klaerungsbundle unter v4.

Apply-Plan v2 ergaenzt v1 um handoff_kind und role je Stage. Rollen:
clarification, implementation, correction. Normale Bundles haben keinen
Klaerungscommit. Gemischte Bundles haben genau eine clarification an Position
0 und anschliessend mindestens eine echte implementation. Klaerung aendert
nur Spec, Implementierungsplan und aktive Katalogbindungen, mindestens Spec
und Plan wirklich; leere oder rein kosmetische Implementierungsmarker reichen
nicht. Die Pruefung klassifiziert technische Belege, keine fachliche Qualitaet.

Vor Annahme werden exakte vierfache Resultbindung, Quell-/Patchhash, typed Plan,
Dateivorherbindungen und alle Stages passiv geprueft. Keine Ausfuehrung von
Code aus ZIPs oder Snapshots. Nach Apply werden exakter oeffentlicher Plan,
Fortschrittsrecord, Gate-/Commitpraefix und tatsaechlicher Result-Snapshot
zugeordnet. Ein Fehler erhaelt alle erfolgreichen Commits. Folgekorrekturen
muessen alle offenen IDs/Rollen in Reihenfolge erhalten; kein Replay und keine
neue Klaerung unter dem Namen einer Korrektur. Fehlen eindeutige Belege, keine
Budgetschaetzung oder Annahme eines Erfolgs.

Eine erstmalige gemischte Uebergabe verbraucht bei Uebernahme ihres gebundenen
Folge-Results genau einen Platz, auch bei Fehler. Eine belegte bytegleiche
Restfortsetzung desselben offenen Klaerungspraefixes verbraucht keinen zweiten
Platz. Erst vollstaendig erfolgreicher, sauberer Abschluss aller angekuendigten
Stages mit Abschlusscommit erneuert drei Plaetze. Erfolgreicher Dokumentcommit
mit nachfolgendem Fehler erneuert nichts. Unklassifizierte Handoffs, Retry,
Overload, Pause, Neustart und Recovery erteilen keine neue Befugnis.

Bestehende Attempts, Antworten und Vertrag-1/2/3-Ketten bleiben unveraendert.
Ein neues initiales Mandat darf bei sauberem erfolgreichem Result mit Marker
v4 erhalten; eine bestehende alte Kette wechselt erst nach einem belegten
normalen erfolgreichen Abschluss mit installierter Unterstuetzung. Bereits
gebundene Auftraege werden nicht umgeschrieben. Recovery prueft auch typisierte
Mischbundles, erfindet jedoch keine Klassifikation fuer manuelle unbekannte
Uebergaben. Konfiguration, Thread, Ledger, Pause und Dienste bleiben durch
Installation unveraendert; keine automatische Reaktivierung alter Blockaden.

Die Ausgabe bleibt genau eine native ZIP pro Auftrag/Result. Bestehender
Watcher, PatchHarbor, ein Testgate pro echtem Commit und sofortiges Ende des
Dev-Auftrags nach Uebergabe bleiben. Keine neue Modellschleife, kein Dienst-
start, keine CI, kein eigener Apply. Control waehlt keine feste Commitzahl.


## OFF-PLAN BLOCKED-CHAIN-024: explizite Recovery nach korrigiertem Teil-Apply

Nutzerauftrag vom 3. November 2026: Eine manuell fortgesetzte Entwicklung nach
`dev_blocked` darf auch nach einem belegten fehlgeschlagenen Teil-Apply und
seinem erfolgreichen Korrekturbundle uebernommen werden. Der bisherige direkte
`recover` und die byteidentische Fortsetzung `reconcile-apply` bleiben erhalten.

`control reconcile-blocked --result ABSOLUTER_RESULTPFAD` ist eine eigene
explizite Bedienaktion bei gestopptem Worker. Sie darf im aktiven Dev-Chat eine
hashgebundene Vormerkung anlegen, startet aber weder Modell noch Dienst und
schaltet die History nicht weiter. Der vorhandene Worker wartet nach einem
separaten Start bei bekannter Aktivitaet und uebernimmt erst nach erneuter
Inaktivitaetspruefung. Pause, Stop und Speichergrenze gelten unveraendert.

Unterstuetzt wird die geschlossene Kette: bisherige saubere Quellbasis -> genau
ein manuelles Patch -> genau ein fehlgeschlagenes dirty Apply-Result -> genau
ein korrigierendes Patch -> genau ein sauberer erfolgreicher Apply-Abschluss.
Alle fuenf Artefakte werden vom installierten nativen Core vollstaendig validiert;
Paket-SHA, Result-SHA, Repository und alle vier Basiswerte muessen verbinden.
Keine Auswahl nach Dateinamen oder nach dem neuesten Erfolg. Fremde/neue Results,
Mehrdeutigkeit, fehlende Archive oder bekannte/verarbeitete Nachfolger sperren.

Der alte Auftrag muss `uncertain/dev_blocked` ohne bereits registrierte Paket-
zuordnung sein. Vollstaendige originale Attempt-/Abschlussdateien, exakte
Blockadeantwort und unveraenderter Entscheidungsvertrag bleiben erforderlich.
Die kryptographischen Hashbindungen sind Integritaetsbelege, keine Aussage ueber
menschliche Freigaben. Es werden weder neue Reviews noch erfolgreiche Modell-
antworten oder eine nachtraegliche `patch_ready`-Klassifikation erfunden.

Beide Patch-Entrypoints haben den bestehenden geschlossenen DATA-Literalvertrag.
Ihr gesamtes Programm ausserhalb dieses Literals ist bytegleich. Control fuehrt
keinen darin enthaltenen Code aus. Der Fehlerlog muss genau den Originalplan,
den erfolgreichen Commitpraefix mit Elternkette und bestandenen Testgates sowie
den fehlgeschlagenen ersten Restschritt ausweisen. `correction_of` bindet diesen
Plan und exakt alle restlichen Commit-IDs und Nachrichten in gleicher Reihenfolge.
Die Korrektur darf Nutzdaten und Preimages reparieren und Regressionen ergaenzen;
urspruengliche Pfadumfaenge und verpflichtende Testselektoren bleiben enthalten.
Jede geaenderte sammelbare `test_*.py`-Testdatei ist vollstaendig Pflicht;
Testhilfen bleiben durch die erhaltenen/ergaenzten Pflicht-Testdateien abgedeckt. Bereits erfolgreiche Commits
werden nicht wiederholt. Alle Korrekturcommits brauchen eigene belegte Gates.

Vollstaendige Dateikarten verbinden Source, Commitpraefix, erhaltenen Fehlerstand
und Endresult. Der passive Leser akzeptiert regulaere Snapshotdateien und den
bestehenden textuellen Git-Diff ohne Staging-Aenderungen; keine Binaerpatches,
Renames, Loeschungen, Moduswechsel oder Symlinks. Hinzugefuegte Dateien kommen
nur aus dem nativ gebundenen untracked-Inventar. Patch-Kontext, Git-Blobhashes,
Vorher-/Nachherbytes, Modi und gesamter Scope muessen exakt stimmen. Keine
Offsets, kein Fuzz, keine Ausfuehrung eines Patchprogramms oder Repositorycodes.
Unbekannte Formate bleiben explizit gesperrt. Archive, Eintraege, Datenliteral,
Stufen- und Dateimengen sind begrenzt: 512 MiB Archiv, 32 MiB je Datei,
64 MiB dekomprimiertes DATA fuer diesen Pfad, 256 MiB je Snapshot,
100000 Dateien und 128 Stufen. Version 1 behaelt sein bisheriges 32-MiB-DATA-Limit.

Vormerkungen Version 2 nutzen die bestehende additive apply_reconciliations-
Tabelle; Version 1 bleibt bytegleich auswertbar. Config, logische History,
Originalbelege und die ganze Kette werden vor Speicherung, nach Neustart und
unmittelbar vor atomarer Uebernahme erneut gebunden. Wiederholtes Vormerken
identischer Belege ist idempotent; andere Offline-Aenderungen bleiben gesperrt.
Fehler rollen Vormerkabschluss und neuen Claim gemeinsam zurueck.

Die Uebernahme beendet nur die alte offene Zuordnung und traegt den belegten
Endstand genau einmal als neue Quelle ein. Die alte Blockadeantwort, der Fehler,
die fehlende damalige Paketklassifikation und der Seed bleiben erhalten.
Zwischenresult und beide manuell gelieferten Pakete bleiben im additiven Beleg.
Der neue Entscheidungsvertrag behandelt diese manuelle Uebergabe als unbekannt:
kein Klaerungsbudget wird neu erteilt, vorhandenes Restbudget bleibt bei
`clarification_allowed=false`. Erst ein spaeterer regulaer klassifizierter
Umsetzungsabschluss kann nach der bestehenden Policy wieder Budget erteilen.
Vor erster neuer Modellarbeit wird die abgeschlossene Kette erneut geprueft.

Abnahme je echtem W/R/C-Zustand: gesamte parallele Control-Verhaltenssuite,
positiver Teilcommit-/Korrekturfall, erhaltene Originale/Budgets/Pause,
verfaelschte/mehrdeutige Artefakte und Logs, veraenderte Vorherbytes, fehlende
Restschritte oder Pflichtpruefungen, Worker-Aktivitaet, Pause/Stop, Disk-Gate,
Restart, Archivverschiebung, Transaktionsrollback und genau einmalige Fortsetzung.
Tests verwenden ausschliesslich isolierte synthetische Betriebsdaten. Apply
installiert Code, Tests und Dokumentation; keine echte Config-, Ledger-, Thread-
oder Dienstaenderung und kein Modellaufruf im Patch-Entrypoint.

## OFF-PLAN DISK-SPACE-023: vor vollem Datentraeger anhalten

Nutzerauftrag: Die Automatik soll bei weniger als 10 GB freiem Plattenplatz
stoppen; die Grenze ist konfiguriert und konfigurierbar. Standard sind exakt
10 000 000 000 Bytes (dezimal GB). Genau die Grenze reicht aus; darunter nicht.
Der bestehende kontrollierte Stopp gilt: keine neuen Auftraege, laufende Arbeit
regulaer abschliessen und den Control-Worker beenden. Kein Zwangsabbruch, kein
Stoppen/Umkonfigurieren des unabhaengigen Apply-Watchers, keine Dateien loeschen.
Ein schon laufender Dev-/Apply-Schritt kann deshalb weiter Speicher belegen.

Die externe Datei neben der Hauptkonfiguration heisst config.limits.toml
(bei --config NAME.toml entsprechend NAME.limits.toml). Geschlossener Vertrag:
format_version = 1 und min_free_gb = 10. Der Wert ist numerisch, endlich, groesser
als null und hoechstens 1 000 000 GB; boolesche Werte und unbekannte Felder sind
ungueltig. Der Bytewert wird aufgerundet. Fehlende Datei nutzt den Standard 10,
ungueltige/unsichere Datei erteilt keine Startfreigabe. Die Schutzdatei enthaelt
keine Thread-ID, Zugangsdaten oder Quellbindung. Bewusst getrennt von config.toml,
damit eine andere Betriebsgrenze keine bereits gebundene Recovery/History
umdeutet. Die bestehende Hauptkonfiguration und alle Belege bleiben bytegleich.

`control disk-space` zeigt Grenze, Messwerte und betroffene Dateisysteme ohne
Modell-/Dienststart. `control disk-space --min-free-gb ZAHL` schreibt die Grenze
privat und atomar unter Operation-/Worker-Lock; nur bei gestopptem Worker.
Die Aenderung erfordert weder inaktiven Dev-Chat noch neues Seed, Ledger-Edit
oder Rebind bestehender Auftraege. Ein laufender Worker laedt Grenzen beim
naechsten ausdruecklichen Start. Apply selbst schreibt keine echte Konfiguration.

Gemessen werden die fuer Nutzdaten verwendeten Dateisysteme von Workspace,
Dev, Apply, Control, Exchange, externem Control-State, Codex-Home und /var/tmp
(Apply-Testdateien). Mehrfach verwendete Dateisysteme erscheinen einmal; ihr
kleinster gemessener benutzbarer Freiplatz entscheidet. Fuer noch nicht angelegte
Unterordner gilt der naechste existierende Elternordner. Nicht der reservierte
Root-Anteil, sondern f_bavail * f_frsize ist massgeblich. Fluechtige Socket-
Verzeichnisse unter /run sind keine Nutzdaten-Datentraeger dieses Schutzes.

Der Linux-Worker misst beim Start, mindestens alle fuenf Sekunden auch beim
Warten, Pausieren und waehrend aktiver Arbeit, sowie direkt vor einem neuen
Dispatch bzw. einer gated Recovery/Handover-Mutation. Ein unterschrittener Wert
oder ein nicht zuverlaessig messbarer benoetigter Pfad schliesst das gemeinsame
Gate zuerst und loest kontrollierten Stopp aus. Bereits freigegebene Arbeit
wird nicht unterbrochen. Messfehler sind keine Freigabe. Der Stopp bleibt fuer
diesen Worker-Lauf wirksam, auch wenn wieder Platz frei wird; kein automatisches
Resume/Restart. Ein neuer ausdruecklicher Start prueft erneut. Normale Pause,
Stop, ungeklaerte Claims, Retry-/Klaerungsbudgets bleiben erhalten.

Status/Journal enthalten stop_reason (low_disk_space bzw. disk_space_unavailable),
Grenze, Messzeit und Freiplatz je Dateisystem. Livezustand und letzter gespeicherter
Stopp bleiben unterscheidbar. Es entsteht kein separater Dienst, Timer oder
Modellloop; der bestehende Event-Worker nutzt einen begrenzten Mess-Wecktermin.
Foundation-only ohne Entwicklungsautomatik startet weiterhin keine Entwicklung.

W/R/C-Abnahme: gesamte parallele Control-Suite je Zustand; positive/negative
Grenze inklusive Gleichheit, andere Dateisysteme, Konfigurationsfehler, echte
isolierte Worker/IPC, Stopp waehrend laufender Arbeit, Race am letzten Dispatch,
Pause/Stop, Restart ohne automatische Freigabe, unveraenderte Recovery-/History-
Belege und keine echten Modell-/Dienstaufrufe. C aendert kein Verhalten.

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

## OFF-PLAN APPLY-RECONCILE-021: belegte Fortsetzung nach fehlendem Result

Nutzerauftrag vom 2. November 2026: Vor dem erneuten Start die nach vollem
Datentraeger unterbrochene Verarbeitungskette reparieren. Ein erfolgreicher
manueller Restlauf ist nicht das Result der urspruenglich beauftragten ZIP.
Weder pending SHA umschreiben noch History/Seed zuruecksetzen oder ein fehlendes
Fehler-Result erfinden. Der Hauptplan bleibt unveraendert.

`control reconcile-apply --result ABSOLUTER_RESULTPFAD` ist eine ausdrueckliche
Offline-Bedienaktion. Worker-, Operation-, Repository- und Thread-Sperren gelten.
Der Befehl prueft und merkt nur eine exakte Belegkette dauerhaft vor; er startet
weder Dienst noch Modell und aendert weder aktuellen Auftrag noch Pause.
Ein aktiver, korrekt identifizierter Dev-Thread darf die Vormerkung ausfuehren.
Erst der spaeter ausdruecklich gestartete bestehende Worker darf bei nachgewiesen
inaktivem Thread und offenem Lifecycle-Gate die Uebernahme atomar abschliessen.
Aktivitaet bedeutet metadata-only Warten, unbekannte/fremde Belege eine Sperre.
Pause/Stop bleiben verbindlich; eine Vormerkung ist keine Resume-Freigabe.

Der enge V1-Vertrag erlaubt ausschliesslich einen waiting_result-Auftrag mit
unveraenderter belegter patch_ready-Antwort und ohne terminales Original-Result.
Originalresult, Originalpatch, Zwischenresult, Restpatch und Abschlussresult
muessen vollstaendig nativ geprueft und ueber SHA-256 und alle vier Bindungswerte
verbunden sein. Das Zwischenresult ist ein nicht trockener, schmutziger Snapshot
mit unveraendertem Basiscommit, der Restlauf ein sauberer erfolgreicher Apply
mit Abschlusscommit. Mehrdeutige oder neuere fremde Results sperren.

Nur SpecRoad-Commitplanformat 1 mit identischem Entrypointprogramm wird akzeptiert.
Daten werden passiv gelesen, nie importiert oder ausgefuehrt. Der Restpatch muss
alle Commit-IDs in unveraenderter Reihenfolge sowie alle Payloadbytes, Nachrichten,
Dateihashes und Testplaene erhalten. Aenderbar sind ausschliesslich neue
Quell-SHA/Bindung, Bundlenummer, correction_of und die Vorbedingung der bereits
vollstaendig materialisierten ersten Stufe (before entspricht deren after).
Der alte Planhash muss passen; kein bereits ausgefuehrter Commit darf fehlen.
Apply-Log muss genau diesen oeffentlichen Plan und den vollstaendigen Abschluss
mit Testgate-Hashes, Commitfolge, Elternkette und letztem HEAD belegen.

Vormerkung bindet Configbytes, logischen Historybestand, Originalattempt und
Originalantwort sowie alle fuenf Artefakthashes. Vor Uebernahme erneute Pruefung
unter Sperren und erneute Inaktivitaetspruefung. Beleg und Fortschaltung erfolgen
in einer SQLite-Transaktion. Originalauftrag, Originalpatch, Antwort und Seed
bleiben erhalten; der Abschluss wird einmal als neue Quelle eingetragen. Nur der
belegte normale erfolgreiche Restlauf erlaubt das vorhandene neue Dreierbudget.
Kein Umdeuten einer Klaerung. Neustart liest denselben Auftrag; Konflikte oder
fehlende/manipulierte Belege erlauben weder Reparaturversuch noch Modellaufruf.

Apply installiert nur Code, Tests und Dokumentation. Echte Vormerkung und spaeterer
Dienststart sind gesonderte Bedienaktionen. W/R/C durchlaufen jeweils die gesamte
parallele Control-Verhaltenssuite vor dem eigenen Commit. Abnahme umfasst
byteidentische Fortsetzung, fehlende/falsche/mehrdeutige Artefakte, falschen Plan,
ausgelassene Tests/Commits, Aktivitaet, Pause/Stop, Restart, Archivverschiebung,
Transaktionsrollback, Belegkorruption und genau einmalige Fortschaltung.

R-Praezisierung: Der enge Entrypointvertrag besteht ausschliesslich aus
patch.json, run.sh und dem nativen PATCHHARBOR_META-Paar. Zusatzausgaben im
DATA-Statement oder weitere Payloaddateien werden nicht normalisiert, sondern
abgelehnt. Alle Vormerkfelder und Hashbelege sind typ- und schemafest. Auch
nach erfolgreicher atomarer Uebernahme wird die Belegkette vor erster neuer
Modellarbeit erneut nativ gelesen. Neue normale Folge-Results bleiben dabei
Aufgabe der bisherigen Engine; die Recovery erzeugt keinen zweiten Claim.
Waehrend einer Vormerkung sperren Config-, Handover- und andere Offline-
Bedienaktionen vor eigenen Seiteneffekten; Status und Worker-Lifecycle bleiben
verfuegbar. Unbekannter Threadstatus blockiert statt als Aktivitaet zu warten.

C trennt die unveraenderten History-/Transaktionsfunktionen in
apply_reconcile_history.py. Bestehende Importnamen bleiben kompatibel.
AST-Vergleich bestaetigt alle sieben verschobenen Funktionskoerper. Die
R-Suite bestand lokal 717/717 Tests; C hat dieselben Verhaltensvertraege.
Keine neue Bedienfaehigkeit, kein Config-/Status-/Dienstzugriff durch Apply.

## OFF-PLAN THREAD-WORKSPACE-020: Thread-Workspace beibehalten

Ausdruecklicher Nutzerauftrag vom 2. November 2026: Der vorhandene Thread
soll im konfigurierten Workspace-Elternordner bleiben und auf dessen gesamten
Inhalt Schreibzugriff erhalten, einschliesslich Apply und Control. Diese
Freigabe ersetzt fuer explizit konfigurierte Elternordner die engeren
cwd-/Schreibwurzelregeln von 018/019 und Bundle 2. Sie erteilt keine neue
fachliche Aufgabe, keinen Dienststart und keine direkte Apply-Umgehung.

`develop.thread_cwd` ist sowohl der bestaetigte Metadatenpfad als auch der
Arbeitsstamm aller neuen Control-Turns. Ohne dieses optionale Feld bleibt
das Dev-Repository Arbeitsstamm. Erlaubt bleiben ausschliesslich Dev und sein
direkter kanonischer Elternordner; fremde, relative oder verlinkte Pfade
erteilen keine Freigabe. Die bestehende Config und ihr Ledger-Scope werden
nicht migriert oder umgeschrieben.

App-Server-Turns setzen cwd explizit auf diesen Stamm. exec resume setzt
denselben Stamm mit --cd und als Prozess-cwd. Produktive Turns verwenden
workspaceWrite mit diesem Stamm und Exchange als expliziten Schreibwurzeln,
networkAccess=false und approvalPolicy=never. Ein Eltern-Workspace umfasst
damit auch seine benachbarten Repositories. Die ueblichen Codex-Schutzregeln
fuer Git-/Konfigurationsmetadaten bleiben bestehen; keine unbeschraenkte Sandbox.
Das Dev-Repository bleibt das fachliche Entwicklungsziel und Git-Guard-Ziel.

Ein ausdruecklich beauftragter Probe-Turn bleibt readOnly, verwendet aber
denselben Arbeitsstamm. Codex-Turnwerte gelten laut lokalem 0.166.0-Protokoll
auch fuer Folgeturns; Control sendet deshalb bei jedem normalen N-Turn wieder
die produktive Policy. Ein Probe-Erfolg beweist keine Remote-Sichtbarkeit.

Neue produktive Dispatch-Belege binden zusaetzlich das exakte cwd. Fortsetzung
verlangt passende cwd- und Policybelege. Historische Belege ohne cwd gelten
weiter nur bei unveraenderter enger Dev-Policy; insbesondere wird ein alter
Dev-Dispatch nicht in eine Eltern-Workspace-Freigabe umgedeutet. Originale,
Retry-/Klaerungsbudgets, aktive Arbeit und Pausen bleiben erhalten. Bestehende
strengere Aktionsnachweise fuer automatische Overload-Fortsetzungen bleiben
Dev/Exchange-bezogen; breitere Schreibrechte sind kein neuer Recovery-Beweis.

Abnahme je W/R/C: gesamte parallele Control-Suite. Beide Transporte, Eltern-
und Dev-Konfiguration, alte Konfiguration ohne thread_cwd, readOnly-Probe,
exakte Schreibwurzeln/Netzwerk-/Approval-Policy, fortbestehende Thread-ID,
Dispatch-Belege und keine neuen Threads oder Modell-/Denkstufenvorgaben.
Apply installiert nur Code, Tests und Dokumentation. Keine echte Config,
History, Dienste oder Session-IDs in der Payload; kein automatischer Neustart.
Die lokale Schemaerzeugung liest nur den installierten Protokollvertrag und
startet weder App-Server noch Modell. Ein Live-Remote-Nachweis bleibt offen.

R-Abnahme: Den expliziten Workspace vor der Metadatenanbindung und nach der
Dispatch-Freigabe erneut gegen dieselben kanonischen Pfadgrenzen pruefen.
Ein inzwischen fehlender oder verlinkter Stamm blockiert mit
invalid_thread_workspace vor Turnstart/exec. Unveraenderte alte Dev-Belege
bleiben lesbar; fehlendes cwd bei Eltern-Rechten, fremdes cwd und geaenderte
Policy sind keine Freigabe. Tests verwenden ausschliesslich isolierte
Dateien und Protokolldoubles, keine echte lokale Konfiguration.

C zentralisiert execution_directory, writable_roots und policy unveraendert
in execution_scope.py. Die bisherigen Importnamen bleiben kompatibel.
AST-Vergleich der drei Funktionskoerper und unveraenderte R-Tests sichern die
rein strukturelle Aenderung ab; keine neue Befugnis oder Bedienaktion.

## OFF-PLAN DEFERRED-HANDOVER-019: wartende Uebergabe

Nutzerauftrag vom 2. November 2026: Korrektur von 018, Uebergabe aus dem
aktiven Dev-Chat, Bundle bauen und ueber Exchange anwenden. Der vorhandene
Control-Dienst uebernimmt das Warten. Kein neuer Dienst, Timer, Cron, Autostart,
Thread oder Modellturn waehrend des Wartens. Die bisherigen Regeln von 018
bleiben fuer den unmittelbaren Offline-Wechsel bestehen.

`handover --thread-id UUID --thread-cwd ABSOLUT --from-thread-cwd ABSOLUT`
bindet optional das exakte heutige cwd des bisherigen Threads. Dieses darf
vom alten Dev-cwd abweichen. Der bestehende Ledger-Scope wird nicht umgedeutet;
Identitaet, echte Metadaten, ruhender Auftrag und Inaktivitaet beider Threads
bleiben vor dem Commit Pflicht. Ohne Option bleibt die alte cwd-Pruefung.
Der neue Thread muss weiterhin zum Dev-Verzeichnis oder direkten Elternordner
passen; produktive cwd und Schreibwurzeln bleiben Dev und Exchange.

Mit `--defer` darf der Befehl bei aktivem Thread einen privaten dauerhaften
Auftrag vormerken. Nur bekannte Statuswerte active, idle und notLoaded sind
zulaessig. Auftrag bindet alte Config/Scope, beide IDs und cwd, Ziel-Scope,
aktuellen Quelljob und Hash der gesamten logischen History. Vorhandene
unaufgeloeste Arbeit, fremde/veraenderte Dateien und abweichende Auftraege
bleiben gesperrt. Der Befehl startet selbst keinen Dienst. `--resume-after`
ist nur mit --defer erlaubt und autorisiert normale Entwicklung erst nach
erfolgreichem Wechsel. Ohne diese Option bleibt der neue Betrieb pausiert.

`control start` erkennt den vorgemerkten Auftrag und startet ausschliesslich
dessen Beobachtung im bestehenden Worker. Alle zwei Sekunden duerfen die
gebundenen Threadmetadaten gelesen werden. Solange einer aktiv ist, entstehen
keine Modellaufrufe, neuen Claims, Versuche oder Bundles. Normale Offline-
Config-, Check-, Probe- und Recover-Aufrufe bleiben waehrenddessen gesperrt.
Status unterscheidet Warten, Durchfuehrung, Sperre und normalen Betrieb.
Pause sperrt weitere Uebergabeversuche; Resume setzt den beauftragten Ablauf
fort. Stop wartet einen bereits begonnenen Wechsel kontrolliert ab und
beendet den Worker. Ein Neustart ohne ausdruecklichen Auftrag erfolgt nie.

Ein initialer vorgemerkter Auftrag darf die bisherige Pause ausschliesslich
fuer die Beobachtung verlassen. Spaetere Pause/Stop-Bedienung bleibt ueber
Neustarts erhalten. Erst erfolgreiche Uebergabe plus --resume-after UND weiter
laufender Lifecycle erlauben den normalen Worker. Pause/Stop waehrend eines
bereits autorisierten Wechsels verhindern danach jede neue Entwicklung.

Der Worker haelt die bestehende Worker-Sperre durchgaengig; fuer den Wechsel
kommen Operation-, Repository- und beide Thread-Sperren hinzu. Das alte
Transaktionsjournal bleibt verbindlich. Belege Version 2 ergaenzen das alte
Metadaten-cwd und optional den Hash des unveraenderlichen Vormerkauftrags.
Bei einer Worker-Uebergabe bindet lifecycle_sha256 diesen Auftrag, waehrend
der eigene validierte Lifecycle Pause/Stop weiter speichern darf. Nur der
Worker des passenden Auftrags darf diesen Pfad verwenden. V1-Belege bleiben
bytegleich und gueltig. Keine Aenderung an alten Jobs, Attempts oder Budgets.

Vor Mutation wird der Auftrag als applying markiert. Abbruch, Datenabweichung
oder unvollstaendige Publikation bleiben gesperrt; kein automatischer zweiter
Mutationsversuch. Erfolgreiche Auftraege werden privat archiviert, bevor
normale Entwicklung moeglich ist. Apply und Tests veraendern keine echten
Betriebsdaten. Abnahme: gesamte parallele Suite je W/R/C, aktive Threads,
abweichendes altes cwd, echte isolierte Worker/IPC, Pause/Stop/Neustart,
Belegkorruption, alte V1-History und ausbleibende doppelte Modellstarts.

R: Der abgeschlossene Auftrag bleibt bis zur dauerhaft gespeicherten
Fortsetzungs-/Pausenentscheidung eine Startsperre. Erst danach archiviert der
Lifecycle-Thread den Auftrag und entfernt die Vormerkung. Ein Abbruch in diesem
Fenster bleibt gesperrt; insbesondere kann --resume-after=false nicht durch
einen Neustart zur Fortsetzungsfreigabe werden. Veraenderte oder fremde
Vormerk-/Statusdateien werden auch im Fehlerpfad nicht ueberschrieben. Status
zeigt eine Vormerkung auch vor Dienststart und bei beschaedigten Belegen an.
Vor Entfernen der Startsperre werden passender Abschlussbeleg, neue Config und
unveraenderte Alt-History erneut geprueft. Verwaiste Statusdateien sperren den
normalen Start ebenfalls. Die unveraenderliche Vormerkung wird zuletzt entfernt.

## OFF-PLAN THREAD-HANDOVER-018: expliziter Threadwechsel

Nutzerauftrag vom 1. November 2026: einen Wechsel des vorhandenen Dev-Threads
mit unveraenderter Verarbeitungshistorie vorbereiten. Der neue Offline-Befehl
`control handover --thread-id UUID --thread-cwd ABSOLUTER_PFAD` ist ausschliesslich
eine ausdrueckliche Bedienaktion. `configure` behaelt seine bisherige Sperre
gegen einen abweichenden Ledger-Scope. Apply installiert nur den Code.

Der Worker muss gestoppt sein; Operation-, Worker-, Repository- und beide
Thread-Locks werden exklusiv gehalten. Alter und neuer Thread muessen genau
aufgeloest und nachweislich inaktiv sein. Es entstehen weder ein neuer Thread
noch ein Modellturn oder ein Dienststart. `running`, `uncertain`, `retry_wait`
und `overload_wait` sind keine Uebergabegrenzen. Erlaubt sind `waiting_result`,
`no_work` sowie ein noch nicht mit Attemptdateien begonnener `ready`-Auftrag.
Keine Uebergabe ersetzt Recovery fuer ungeklaerte Arbeit. Die gebundene aktuelle
Resultquelle wird vor der Transaktion erneut nativ geprueft.

`develop.thread_cwd` ist ein optionaler expliziter Metadatenpfad. Er darf nur
das bestehende Dev-Verzeichnis oder dessen unmittelbaren Workspace-Elternordner
bezeichnen. Ohne Feld bleibt die alte exakte cwd-Pruefung bestehen. Nach einer
Uebergabe darf genau dieser Pfad oder das Dev-Verzeichnis im selben Thread
beobachtet werden. Produktive Turns laufen weiterhin mit Dev als cwd und mit
den bestehenden ausschliesslichen Schreibwurzeln Dev und Exchange. Weder
Apply/Control noch der ganze Workspace werden dadurch beschreibbar. Fremde,
relative oder verlinkte Metadatenpfade werden abgelehnt.

Startquelle, aktueller Job, alle alten Auftraege/Antworten/Attemptdateien,
Fehler, Retrynummern, Termine, Entscheidungsvertraege, Klaerungsbudgets und
Pause bleiben erhalten. Die einzige Aenderung an bestehenden Ledgerdaten ist
die explizite Scope-Bindung. Ein additiver privater Uebergabebeleg dokumentiert
vorherige/nachfolgende Bindung und Hash des erhaltenen logischen Datenbestands.
Keine reale Thread-ID, Konfiguration oder Betriebsdatei gelangt in Git/Bundles.

Vor dem Wechsel entsteht ein privates, dauerhaft geschriebenes Intentjournal.
Solange es existiert, sperren normale Config-/Start-/Check-/Probe-/Recover-
Operationen; kontrollierter Stopp und lesender Status bleiben moeglich.
Ledger-Scope und Uebergabebeleg werden gemeinsam in einer SQLite-Transaktion
geschrieben, danach die Konfiguration atomar ersetzt. Der identische explizite
Befehl kann nach Abbruch ausschliesslich diesen belegten Wechsel fertigstellen.
Abweichende Argumente, veraenderte Historie/Config/Pause/Quelle oder unklare
Zwischenzustaende bleiben gesperrt. Das Journal verschwindet erst nach
vollstaendiger Nachpruefung und fsync. Ein abgeschlossener identischer Wechsel
ist idempotent. Es gibt keinen automatischen Wiederholungs- oder Repairloop.

Abnahme: parallele isolierte Verhaltenssuite je echtem W/R/C-Zustand, positive
Uebergabe mit anschliessendem normalen Dispatch, beide cwd-Varianten, Erhalt
aller Daten/Budgets und Pause, alte Scope-Sperre, aktive/unklare Threads und
Jobs, Unterbrechungen an Publikationsgrenzen, manipulierter Intent/Beleg und
Datei-/Lockgrenzen. Reale Konfiguration, History und Dienste bleiben beim
Entwickeln und Apply unangetastet; echte Bedienung folgt getrennt nach Apply.

R-Praezisierung: Beim eigentlichen Wechsel muss das neue Threadmetadatum exakt
dem angegebenen absoluten cwd entsprechen. Erst spaetere produktive Turns
duerfen es auf Dev setzen. Auch exec bindet seinen Arbeitsstamm ausdruecklich
mit `exec --cd DEV resume`; der Proxy nutzt weiterhin `turn/start.cwd=DEV`.
Uebergabebelege haben einen geschlossenen, typgeprueften Vertrag und bilden
eine Hashkette mit passender Scope-/Threadfolge. Jeder normale Ledgerzugriff
prueft diese Kette, soweit sie vorhanden ist. Vor und nach Configpublikation
muessen auch der genaue neue Scope und die genauen Receiptbytes noch stimmen.
Start und Offline-Bedienbefehle lesen Config erst unter ihrer Worker-/Operation-
Sperre. Ein noch ausstehender Wechsel darf auch bei fehlender Configdatei keine
neue Standardkonfiguration erzeugen.

C-Trennung: handover.py koordiniert Offline-Sperren, Metadaten und das private
Publikationsjournal. handover_history.py kapselt den unveraenderten logischen
Bestandshash, das Oeffnen beider belegter Scopes und die SQLite-Transaktion.
handover_evidence.py enthaelt den gemeinsamen geschlossenen Belegvertrag und
die Kettenpruefung. Fehlercodes, Reihenfolge, Grenzen und Bedienverhalten
entsprechen dem geprueften R-Zustand.

## Korrektur 015: persistentes Dreierbudget (FIX11)
Der Nutzerauftrag vom 26.10.2026 erweitert ausschliesslich Control auf maximal
drei aufeinanderfolgende Klaerungsbundles. Vertrag 3 bindet version=3,
clarification_limit=3, clarifications_remaining (Ganzzahl 0..3) und
clarification_allowed (Boolean; bei Null zwingend false). false sperrt auch
bei positivem Restbudget eine weitere Klaerung. Unbekannte Versionen, Felder,
Typen, fehlende Budgetbelege und nachtraegliche Vertragsaenderungen sperren.

Jeder neue Quellauftrag bindet sein Budget vor Dispatch. Eine klassifizierte
spec_clarification-Uebergabe verbraucht bei Uebernahme ihres Folge-Results genau
einen Platz, unabhaengig vom Apply-Erfolg. Der Handoff bleibt vorher dauerhaft
gebunden; wiederholte Beobachtung und Recovery verbrauchen keinen zweiten Platz.
Eine weitere Klaerung braucht ein erfolgreiches sauberes Apply mit exakt zum
Folgezustand passendem completed_commit und positives verbleibendes Budget.
Fehlgeschlagene Klaerung oder normales Apply sowie unbekannte Handoffs geben
keine neue Befugnis; Vertrag 3 sperrt dann Klaerung bei erhaltenem Restzaehler.
Regulaere Umsetzung bzw. technische Korrektur bleibt bei false erlaubt. Nur
klassifiziertes patch_ready mit erfolgreichem sauberem Apply und passendem
Abschlusscommit oeffnet wieder drei Plaetze. Kein kosmetischer Budgetreset.

Die private Zusatzrelation clarification_budgets bindet Maximum und Rest je
Quell-SHA atomar mit request_contracts, Result-Claim und aktuellem Job. Alte
Vertraege und Attempts werden weder ueberschrieben noch rueckwirkend erweitert.
Vertrag-2-Klaerungsketten behalten das alte Einerlimit. Ein neuer Vertrag 3 darf
bei alten Ketten erst nach eindeutig klassifiziertem normalem Erfolgsabschluss
entstehen. Unklassifizierte Altarbeit bleibt ohne neue Klaerungsbefugnis.
Legacy-Prompts, Replay-/Retrybelege und archivierte Quellbindungen bleiben exakt.
Alle modernen Vertragsversionen werden unmittelbar vor Dispatch und bei
Abschluss, Recovery und Overload auf unveraenderte Attemptbindung geprueft.

Der Prompt verlangt zuerst die separate ausdrueckliche SpecRoad-Projektregel
fuer Vertrag 3 und bis zu drei Klaerungsbundles. Der Controller prueft keine
Fachtexte heuristisch und erteilt selbst keine Delegation. Keine Ausweitung von
Scope, Sicherheitsgrenzen, menschlichen Reviews oder erforderlichen Nachweisen.
Pausen, alte dev_blocked-Auftraege und History bleiben bestehen. Die Lieferung
aendert keine externe Config/DB und startet oder stoppt weder Dienst noch Dev.
Die nachfolgende Korrektur 014 dokumentiert den unveraenderten Altvertrag 2.

C-Trennung: decision_policy.py berechnet den Folgevertrag ohne Dateisystem- oder
Datenbankzugriff. decision_history.py liest und bindet ihn weiterhin innerhalb
derselben Ledger-Transaktion. Fehler, Budgets und Altvertraege bleiben gleich.

## Korrektur 014: versionierte begrenzte Entscheidungsvertraege (FIX10)
Der Nutzerauftrag vom 22.10.2026 betrifft ausschliesslich das Control-Bundle.
Neue Auftraege tragen Vertrag 2 mit dem Boolean clarification_allowed. Eine
fehlende Version in alten Attempts bedeutet unveraendert Vertrag 1. Unbekannte
Versionen, malformed Werte und nachtraegliche Aufwertung werden abgewiesen.
Quelle, Vertrag und bisherige Fortsetzungsbelege bleiben ueber Archivverschiebung,
Neustart und Overload stabil. Alte Promptbytes werden weiter exakt rekonstruiert.

Die fachliche Befugnis ist an die ausdrueckliche Regel SPECROAD-DECISION-1 in
den massgeblichen SpecRoad-Projektvorgaben gebunden. Der Dev-Auftrag darf diese
Regel nicht selbst einfuehren oder die Produktvorgaben eigenmaechtig ersetzen.
Er verlangt bei delegierbaren Luecken Analyse, Alternativen, eine konservative
reversible Entscheidung, Begruendung und normative Spezifikations-/Planpraezisierung.
Explizite Nutzerentscheidungen, Sicherheitsgrenzen, menschliche Reviews, Scope,
Kompatibilitaetszusagen und erforderliche Nachweise bleiben unveraendert.
Unverzichtbare externe Fakten, unaufloesbare Widersprueche und Entscheidungen
ausserhalb der Befugnis verlangen blocked mit Frage, Empfehlung und Begruendung.

Vertrag 2 erweitert bei freiem Budget nur den Statusenum um spec_clarification.
Die vier Antwortfelder, Source-SHA, eindeutige native Paketpruefung und vier
Basisbindungen bleiben Pflicht. Klaerung liefert ein OFF-PLAN-Bundle, keine
S-Schleife; Planpositionen bleiben offen. Der Worker wartet normal auf Apply.
Ein solches gebundenes Folge-Result erlaubt den naechsten Auftrag, aber keine
zweite aufeinanderfolgende normative Klaerung. Technische Korrekturen behalten
die bisherigen Test-/Resultregeln; sie duerfen keine neue Klaerung verbergen.

Die additive private Tabelle request_contracts bindet je Quell-SHA Version,
Budget und Ausgabeklassifikation. Vertrag und Attempt werden vor Dispatch
festgehalten; Ausgabeart und waiting_result atomar, ebenso Budgetuebernahme und
naechster Result-Claim. Nach spec_clarification sowie unklassifiziert uebernommener
Ausgabe ist das Folge-Budget gesperrt. Nur ein als patch_ready klassifiziertes
Bundle mit erfolgreichem, sauberem nativen Apply und passendem completed_commit
kann es wieder oeffnen. Dies prueft Protokoll und Apply-Belege, nicht Semantik
oder tatsaechlichen Produktplanfortschritt. Die fachliche Delegation wird vom
Dev geprueft, nicht durch ein Control-Modell oder eine Schlagwortheuristik.
Bei clarification_limit oder defekter Vertragshistory kein automatisches Reset.

Pausen, kontrollierter Stopp, bestehende dev_blocked-Recovery und Overload-Budget
bleiben verbindlich. Keine eigene Operator-/Modellschleife, keine Configaenderung,
kein Dienst-/Dev-Start beim Apply. Tests verwenden ausschliesslich isolierte
Core-/Codex-Gegenstellen und pruefen Verhalten statt Promptformulierungen.

R-Absicherung: Unmittelbar an der Dispatch-Grenze werden gespeicherter Vertrag
und unveraenderter Attempt erneut geprueft. Moderne Read-only-Retries pruefen
auch die exakten Promptbytes; die Source allein reicht fuer neue Befugnisse
nicht aus. Recovery mit Vertrag 2 verlangt den passenden Originalattempt.
Paket und Klassifikation eines gespeicherten Handoffs sind unveraenderlich.
Kaputte Tabellen/Felder ergeben request_contract_invalid; widerspruechliche
Zuordnungen request_contract_changed. Transaktionsfehler erhalten sowohl alten
Result-Claim als auch Budget. Keine Teilfreigabe nach einem Fehler.

C-Trennung ohne neues Verhalten: decision_history.py kapselt Vertragspersistenz
und Budgetuebernahme innerhalb der bisherigen Ledger-Transaktionen;
legacy_job_contract.py bewahrt die alten Promptbytes. Die parallelen Tests
nutzen einen gemeinsamen isolierten Handoff-Aufbau. Alle Status-, Fehler-,
Versions-, Dispatch- und Recoveryvertraege bleiben gegenueber R unveraendert.

## Korrektur 013: persistentes Beobachten noch laufender Arbeit (FIX9)

Diese Erweiterung zu 012 erlaubt Beobachtung, keine Wiederholung von Tools.
Nach eigenem terminalem serverOverloaded mit willRetry=false und vollstaendigen
modernen Belegen wird `overload_wait` statt einer sofortigen Pause gespeichert,
wenn ausschliesslich bekannte lokale commandExecution noch inProgress sind.
Alle Voraussetzungen fuer Dispatch-Policy, Originalprompt, Source, Attemptnummer,
neueste Turn-Identitaet, Toolherkunft und vollstaendige History aus 012 gelten.
Ein inProgress-Befehl hat keinen Exitcode. Unbekannte Tools und Hintergrundarbeit
ohne einen bekannten offenen Befehl erlauben keine automatische Beobachtungsfreigabe.

Eine additive private SQLite-Tabelle bindet atomar mit dem Zustand Quell-SHA,
Attemptnummer, Fehlturn, Dispatch-/Attempt-Hashes, den erhaltenen Workspace-Guard
und normalisierte volle History. Nur status, exitCode, aggregatedOutput und
durationMs der anfangs offenen Befehle duerfen sich entwickeln. Bereits terminale
Items bleiben exakt erhalten, ebenso ID, command, cwd, source, processId und
sonstige Metadaten. Neue Items oder Turnwechsel sperren. Die begrenzte vollstaendige
Hintergrundliste wird vor/nach Itemlesen geprueft: feste Identitaeten duerfen
verschwinden, aber nicht neu erscheinen oder wechseln. processId, itemId, command
und cwd werden gebunden; itemId/command/cwd muessen zum eigenen anfangs offenen
Befehl passen, ein vorhandener processId im Item darf nicht widersprechen.
CPU-/RAM-Messwerte und osPid sind keine Freigabebelege und werden nicht gebunden. Keine fehlende API als leere Liste werten.

Der Linux-Worker beobachtet fruehestens alle 30 Sekunden; die Faelligkeit ist
persistiert und wird durch Dateiereignisse oder Neustarts nicht verschoben.
Laufende bekannte Terminals haben keinen Timeout. Nach der ersten leeren Liste
gibt es 120 Sekunden fuer nachlaufende terminale Item-/Exitbelege; weiterhin offene
Items fuehren danach zu overload_completion_unproven. Leere Terminals allein
sind kein Abschluss. Waehrend Beobachtung werden kein Modell und kein Tool gestartet,
keine Arbeit beendet, keine Dateien zurueckgesetzt und keine Retry-Nummer verbraucht.

Bei vollstaendigem Abschluss werden Quelle, neuester Turn, leere Terminals und
Checkpoint erneut geprueft. Ein einziges nativ gebundenes Bundle hat Vorrang.
Sonst wird genau einmal das bestehende gemeinsame Retry-Budget mit seinen
60/180/600/1800 Sekunden benutzt, danach der bestehende Fortsetzungsauftrag.
Kein Rebaseline eines waehrend der Wartephase veraenderten Arbeitsstands.
Pause/Stop sperren neue Modellstarts; Wait-Belege, Fristen und Budget bleiben.
Neustart setzt overload_wait fort, uncertain bleibt explizit zu behandeln.

Explizites offline recover darf einen alten uncertain/codex_turn_failed-Auftrag
mit eigenem modernem Attempt und Dispatch nach denselben strengen terminalen
Fortsetzungsbelegen auf retry_wait setzen. Nur dabei darf systemError mit genauem
neuestem Overload, vollstaendigen terminalen Aktionen und leerer Hintergrundliste
genutzt werden. Generisches check sowie Legacy-Recovery werden nicht gelockert.
Mehrdeutige/fehlende Belege sperren. Recovery startet nichts, erhaelt Originale
und Pause und kann denselben Fehlturn nicht erneut budgetieren.

Apply laedt nur den Code und fuehrt isolierte Verhaltenstests aus. Kein Zugriff
auf echte Konfiguration, Jobs oder Dienste, kein produktiver Modellaufruf,
keine Watcher-Aenderung, kein automatischer Restart oder Autostart.

R-Absicherung: Waiting-Fristen und alle gespeicherten Hash-/Identitaetsfelder
werden vor Verwendung validiert; Beschaedigung ergibt invalid_overload_wait.
Ein fehlgeschlagener atomarer Uebergang veroeffentlicht keinen halben Wartezustand.
Beobachtete terminale Exit-/Ausgabebelege duerfen nicht wieder zurueckfallen.
Auch am Uebergang zu retry_wait wird kein neuer Workspace-Guard erraten; Nummer
und Source muessen zum bestehenden Budget passen. Erneute Recovery erhoeht
weder Nummer noch Frist. Status und Journal nennen overload_check_at.
Die Tests umfassen Prozessneustart, Pause/Stop, automatische Timer-Fortsetzung,
verzoegerte Exitbelege, fremde Terminals/Aktionen, fehlende APIs, Quell-/Datei-
wechsel sowie Paketpublikation und Pause an der letzten Dispatch-Grenze.
Protokollbasis zusaetzlich: lokal erzeugtes Codex-App-Server-JSON-Schema mit
--experimental (20.10.2026), ThreadBackgroundTerminal und commandExecution.
Schemaerzeugung startet weder App-Server noch Modell. Alle Worker-/Protokoll-
Tests laufen gegen isolierte Gegenstellen; kein realer Capacity-Fehler simuliert.

C-Trennung ohne neues Verhalten: overload_runtime.py kapselt die Worker-
Warteentscheidungen; overload_wait.py prueft Belegfortschritt und Fristen,
wait_ledger.py die atomaren privaten Checkpoints. Engine behaelt Source-/Bundle-
Pruefung, Budget und Dispatch. Methoden, Fehlercodes, Fristen und Prioritaeten
bleiben gegenueber dem erfolgreich geprueften R-Zustand unveraendert.

## Korrektur 012: erhaltene Entwicklung nach terminalem Overload fortsetzen

Der Nutzerauftrag vom 20.10.2026 erweitert die Korrektur 009 um eine eigene
Fortsetzung teilweise ausgefuehrter lokaler Entwicklung. Die alte Read-only-
Wiederholung bleibt unveraendert. Produktive Aktionen werden nicht wiederholt:
ein neuer Turn im selben Thread erhaelt den Auftrag, den erhaltenen Zwischenstand
zuerst zu pruefen und denselben quellgebundenen Entwicklungsauftrag fortzusetzen.
Kein neuer N-Auftrag, kein Reset, kein Modell-/Denkstufenwechsel.

Erforderlich sind der eigene gespeicherte App-Server-Dispatch mit workspaceWrite
nur fuer Dev/Exchange, networkAccess=false und approvalPolicy=never, der exakte
terminal fehlgeschlagene Turn mit serverOverloaded und willRetry=false sowie
vollstaendige Items dieses Turns. Der Turn muss der neueste sein; ein spaeterer
manueller Turn sperrt. thread/read darf idle, notLoaded oder systemError melden;
systemError allein ist weder Abschluss noch Freigabe. Unbekannte Statuswerte,
fehlende Belege, Benutzerabbruch und Codex-interner Retry erlauben keine Fortsetzung.

Die moderne History-API und thread/backgroundTerminals/list sind fuer diesen
Weg verbindlich. Die Verbindung meldet dafuer experimentalApi an. Vor und nach
dem Itemlesen muessen neueste Turn-Metadaten uebereinstimmen und die Liste
getrackter Hintergrundterminals leer sein. Keine Legacy-Vermutung bei fehlender
API. Laufende Turns werden nicht beendet; nach dem Backoff wartet der Linux-
Worker bei nachgewiesener Aktivitaet weiter, ohne ein Modell zu beauftragen.

Erlaubt sind der eine genaue Controller-Prompt, Reasoning, Agent-Text/Plan,
contextCompaction, terminale lokale commandExecution (completed/failed) mit bekanntem
Exitcode und Dev-cwd sowie abgeschlossene fileChange innerhalb Dev/Exchange.
Offene Agent-Fragen verlangen Nutzereingabe. Fehlerhafte Testausgaenge duerfen erhalten bleiben, gelten aber nicht als
erfolgreiche Tests. Unbekannte Tools, delegierte Arbeit, MCP-Aktionen und
unvollstaendige Befehle bleiben gesperrt. Dies ist keine Garantie fuer beliebige
externe Seiteneffekte eines Shellskripts: Control wiederholt keine Toolaktionen;
der Fortsetzungsprompt verlangt bei unklaren Wirkungen eine fachliche Blockade.

Nach dem Fehlschlag werden der aktuelle Git-/Datei-Guard und ein Hash der
vollstaendigen Turn-Belege dauerhaft an Source, Thread und Fehlturn gebunden.
Dateien, Index, Commits und vorhandene Test-/Bundle-Artefakte bleiben erhalten.
Ignorierte Dateien gehoeren weiterhin nicht zum Git-Guard und muessen vom Dev
geprueft werden. Fremde Aenderungen im Guard oder an den Belegen waehrend der
Wartephase sperren; auch unmittelbar vor Dispatch werden die Belege geprueft.
Jede Fortsetzung hat ein eigenes Attempt-Verzeichnis und bewahrt die alten Belege.

Read-only-Retries und Fortsetzungen teilen dasselbe persistente begrenzte
Budget (standardmaessig 60/180/600/1800 Sekunden). Pause/Stop, Neustart und
Reconfigure setzen es nicht zurueck. Bei erschopftem Budget oder unklarer Lage
pausiert nur die Automatik mit konkretem Fehler; kein Notstopp des Dev-Threads.
Ein bereits vorhandenes eindeutig gebundenes Bundle hat Vorrang, auch wenn der
Overload erst nach Veroeffentlichung auftrat. Der vorhandene Watcher bleibt fuer
Apply, Tests und Result zustaendig. Control erzeugt keinen zweiten Apply-Auftrag.

Apply dieses Bundles aendert weder Dienst-, Einrichtungs- noch Laufzeitzustand.
Bereits uncertain/pausierte Altauftraege werden nicht automatisch freigegeben;
die bisherigen expliziten Recovery-Regeln bleiben bestehen. Kein Modellaufruf,
kein Dienstneustart und kein Autostart durch die Lieferung. Die Protokolltests
verwenden nur isolierte lokale Gegenstellen, keinen produktiven Codex-Thread.
Protokollbasis: https://learn.chatgpt.com/docs/app-server (20.10.2026),
OpenAI Codex rust-v0.163.0: protocol/common.rs sowie generierte ThreadItem-,
UserInput- und CommandExecutionStatus-Typen. Leere text_elements sind normale
Text-Metadaten. commandExecution.source muss agent, unifiedExecStartup oder
unifiedExecInteraction sein; userShell und fehlende/unbekannte Herkunft sperren.

R-Absicherung: Originale Request-Source-Fakten werden im Attempt bewahrt, damit
normales Verschieben des Results ins Archiv die Turn-Bindung nicht zerstoert.
Der gespeicherte Checkpoint bindet zusaetzlich Hashes von Attempt und Dispatch.
Die Fortsetzungsart darf nicht in einen Read-only-N-Replay umgedeutet werden.
Startquelle, Nummer, History und Policy muessen bei Wiederaufnahme uebereinstimmen.
Die Request-Serialisierung ist kanonisch, auch nach Laden der privaten JSON-Dateien.
Bei einer Publikation an der letzten Dispatch-Grenze wird das gebundene Bundle
uebernommen und kein Modellturn gestartet. Neu aktive Turns/Terminals lassen
den vorgemerkten Versuch warten. Ein Crash nach dem dauerhaften Dispatch-Claim
ohne terminalen Beleg bleibt uncertain; niemals aus fehlenden Dateien replayen.
Status/Journal weisen retry_mode=continuation aus. Die Worker-Tests pruefen
echten Eventloop, Pause/Resume und kontrollierten Stopp ausschliesslich in
isolierten Testverzeichnissen und gegen eine synthetische Unix-Gegenstelle.
Die App-Server-API bietet keinen atomaren Compare-and-Start gegen fremde Clients.
Deshalb gilt weiterhin: vor manuellen Dev-Eingaben pausieren und active_job=false
pruefen. Die wiederholten lesenden Guards ersetzen diese Bedienkoordination nicht.

C-Trennung ohne neue Verhaltensregeln: continuation_history.py kapselt die
zusaetzliche lesende Beobachtung des neuesten Turns und der Hintergrundterminals.
continuation_evidence.py prueft reine Daten-/Prompt-/Aktionsvertraege;
continuation.py korreliert diese mit den privaten Receipts und dem Dateiguard.
Der produktive Dispatch und sein Receipt verwenden dieselbe Policy-Struktur.
Alle Grenzen, Fehlercodes, Wartezeiten und Bedienregeln bleiben die des R-Stands.

## Korrektur 011: explizite Wiederaufnahme nach fachlicher Blockade

Ein abgeschlossener `blocked`-Turn bleibt im Worker `uncertain/dev_blocked`.
Nur explizites offline `recover` darf spaeteres manuelles Ergebnis uebernehmen:
eine vollstaendige unveraenderte Blockadeantwort fuer den gebundenen Auftrag,
genau ein nativ validiertes, bisher nicht verarbeitetes Patch-Paket und genau
ein daran ueber Paket-SHA und alle vier Basiswerte gebundenes echtes Apply-Result.
Dieses Result muss erfolgreich, sauber und mit passendem Abschlusscommit belegt
sein. Fehlende, widerspruechliche, fremde oder mehrdeutige Belege bleiben gesperrt.

Recovery prueft den vorhandenen Dev-Thread ohne Modell und erhaelt Quellen,
Protokolle, Jobs, Startquelle und Pause. Sie uebernimmt nur die Paketbindung nach
`waiting_result`; sie setzt niemals den alten Auftrag auf `ready`. Erst eine
spaetere ausdrueckliche Fortsetzung verarbeitet das gebundene Folge-Result und
beansprucht dessen naechsten Auftrag. Recovery startet weder Modell noch Dienst.

Vor der Uebernahme werden Thread-Inaktivitaet, Quelle, eindeutige Paket-/Result-
Auswahl und unveraenderte Protokollbytes erneut geprueft. Paket-SHA, vollstaendige
Result-Referenz und Hash der erhaltenen Blockadeantwort werden mit dem Uebergang
atomar in einer additiven `blocked_recoveries`-Tabelle gespeichert. Keine alte
Antwort wird umgeschrieben oder als erfolgreicher Modellturn ausgegeben.
Nach Neustart darf der Worker nur genau dieses erneut nativ gepruefte Result
verarbeiten. Fehlende/geaenderte/mehrdeutige Belege sperren vor einem Modellaufruf.
`recovery_evidence_changed` und `invalid_recovery_history` verlangen Diagnose;
es gibt keine automatische Wiederholung oder Ruecksetzung.

Die Belegpruefung liegt in `blocked_recovery.py`, die additive atomare
Zuordnung in `recovery_ledger.py`. Bedienbefehle und Worker nutzen dieselben
Vertraege; diese Trennung fuehrt keine weiteren Freigaben oder Auftraege ein.

## Ziel und Rollen
Linux uebernimmt das Warten, nicht ein Modell. Das bestehende Dev-Repository
liefert Patches; der vorhandene PatchHarbor-Daemon erledigt Apply, Tests und
Results. Er wird nicht ersetzt, gestartet, gestoppt oder umkonfiguriert. Der alte
Apply-Codex-Thread bleibt stillgelegt. Ein separater Control-Thread bedient nur
lokale Befehle. Keine direkten Aenderungen an den benachbarten Repositories.

## Bundle 1: verbindlicher Umfang
Manuell installierbarer systemd-User-Dienst specroad-control.service. Befehle:
install, start, stop, pause, resume, status; run ist der interne Vordergrundworker.
Kein Autostart, kein automatischer Neustart, kein Notstopp. Keine [Install]-Sektion,
kein enable/linger/Timer/Cron. Installieren und Starten bleiben getrennt.
Stopp ist endgueltig fuer den aktuellen Lauf, laesst eine bereits begonnene Arbeit
fertig werden und verhindert neue Arbeit. Pause laesst laufende Arbeit ebenfalls
fertig werden. Resume waehrend eines Stopps ist unzulaessig. Keine Zwangssignale.
Nur eine Worker-Instanz; Steuerungsoperationen werden getrennt serialisiert.
Leerlauf wartet auf lokale Ereignisse ohne Modell und ohne Exchange-Polling.
JSON-Status kennzeichnet den Grundbetrieb explizit als foundation-only und
unterscheidet den Livezustand von einem bloss gespeicherten vergangenen Zustand.

## Lokale Daten
Echte Einstellungen in $XDG_CONFIG_HOME/specroad-control/config.toml, normalerweise
~/.config/specroad-control/config.toml. Enthalten Dev-Verzeichnis, explizite
session_id und Exchange. Nur eine IDs-freie Vorlage wird ausgeliefert.
Zustand in $XDG_STATE_HOME/specroad-control (normalerweise ~/.local/state).
Lokaler IPC-Socket unter $XDG_RUNTIME_DIR/specroad-control oder state/run.
Dienstdatei unter $XDG_CONFIG_HOME/systemd/user. Betriebslogs im Benutzerjournal.
Lokale Dateien sind privat (0600), eigene Zustands-/Runtimeverzeichnisse 0700.
Keine Konfiguration oder Laufzeitdaten im Repository, in Bundles oder in Exchange;
auch keine Verlagerung per XDG-Variablen/Symlinks in einen Git-Working-Tree.
Bestehende Konfiguration nie durch Installation/Update ueberschreiben.
Konfiguration wird beim Start gelesen. Aenderungen: kontrolliert stoppen und neu
starten. Stoppen muss auch mit einer beschaedigten Konfiguration moeglich bleiben.

## Noch nicht in Bundle 1
Kein Codex-Aufruf, kein Prompt, kein Modell-/Denkstufenwechsel. Keine Result-
Zuordnung oder Verarbeitung. Die tatsaechliche Remote-Livesichtbarkeit ist offen
und wird erst mit Bundle 2 untersucht. Ein laufender Grunddienst beweist diese
Funktion ausdruecklich nicht. Keine automatische Dev-Endlosschleife beim Apply.

## Nachweise
Parallele funktionale Tests je W/R/C-Zustand, auch Fehlerfaelle. Echte Worker-
Prozesse in isolierten Benutzerverzeichnissen; systemctl-Aufrufe mit Testdoubles.
Keine Testinstallation an der produktiven systemd-Instanz waehrend Apply.
Kein UI-/Text-/Dokumentationstest und keine GitHub-CI.

## Bundle 2: externe Entwicklungsautomatik
Dieser Abschnitt erweitert den Grundbetrieb. Bestehende format_version=1-
Konfigurationen ohne automation.enabled bleiben bewusst foundation-only.
Konfigurationsvorlagen duerfen echte Dateien nie ueberschreiben.

Start liest einmal die externe Konfiguration. benoetigt werden Dev-Pfad,
Exchange, eindeutige Ziel-Repo-ID, explizite vorhandene Thread-ID im Feld
session_id, installierter Codex, dessen CODEX_HOME, der bereits installierte
PatchHarbor-Python. Ein ausdruecklich gewaehltes Seed-Result mit SHA-256 ist nur
zur erstmaligen Initialisierung des Laufzeitzustands erforderlich. Result-Pfad,
Result-run_id und Result-SHA stehen NIE in der dauerhaften Konfiguration.
Die bestehende automation.sqlite3 im externen State-Verzeichnis speichert die
Startquelle und den aktuellen Auftrag transaktional; state.json bleibt die
Lebenszyklus-/Statusansicht. Es entsteht keine zweite Bootstrap-Wahrheitsquelle.
Das Seed ist ein SpecRoad-Apply-Result, niemals das Control-Result dieses Patches.
Keine Zugangsdaten werden gelesen, uebertragen oder in den Code eingebettet.

Dateinamen/mtime/ZIP-Marker sind nur Suchhinweise. Ein isolierter subprocess des
lokal installierten PatchHarbor prueft vollstaendige Result-Struktur, Snapshot,
Pruefsummen und Patch-Bindung. Kein Runtime-Code aus Exchange-ZIPs wird gestartet.
Weder Registry noch Watcher werden geaendert; niemals apply/bundle aufrufen.
Nur Ziel-repo_id wird verarbeitet. Ein nachfolgendes Apply-Result muss sowohl
patch_sha256 als auch die erwartete Vierfachbindung des Ausgangsresults treffen.
Ein fehlgeschlagener Apply darf eine Korrektur ausloesen; Erfolg ist keine
Voraussetzung. Mehrdeutige oder unvollstaendige Nachweise loesen keine Entwicklung aus.

SQLite-Historie ausserhalb des Repos bindet jede Ausfuehrung an Result-run_id
und SHA-256. Vor Modellstart wird die Beanspruchung dauerhaft gespeichert.
Nach erfolgreicher Uebergabe wartet der Worker ereignisgesteuert auf ein Result;
keine Modell-Aufrufe fuer Wartezeiten, Status oder Exchange-Polling. Status
bleibt waehrend der Arbeit erreichbar. Stop/Pause verhindert eine neue
Dispatch-Grenze und beendet/unterbricht niemals bereits gestartete Dev-Arbeit.

Codex muss den bestehenden Thread mit passendem cwd und bekannt inaktivem Status
aufloesen. Kein --last, --worktree, ephemeral, thread/start oder thread/fork.
Keine Modell-/Denkstufenwechsel. Ein N-Auftrag erzeugt hoechstens ein Bundle und
endet danach, ohne S-Schleife. Das abschliessende JSON ist nur eine Behauptung;
die behauptete ZIP muss auch nativ korrekt gebunden vorliegen.

check prueft lokal/native Protokolle ohne Modellturn. probe startet nur auf
expliziten Nutzerbefehl einen einzelnen read-only Test im vorhandenen Thread.
Ein Protokollerfolg ist KEIN Beweis fuer die Livesichtbarkeit auf dem Handy.
Der Benutzer prueft den individuellen Marker dort. Die Automatik wird durch
configure, check oder probe niemals gestartet.

Eigenen parallelen Controllern werden pro Dev-Pfad und Thread prozessuebergreifende
Locks entgegengesetzt. Andere manuelle Codex-Clients muessen die Bedienvereinbarung
einhalten: Automatik pausieren, laufende Arbeit fertig werden lassen, erst dann
im Dev-Thread neue Arbeit beauftragen. Reines Anzeigen ist erlaubt.

## R: Wiederanlauf, Protokolle und Sicherheitsgrenzen
Die zwei Transporte sind explizite Alternativen: exec resume mit existierendem
App-Server-Preflight oder thread/resume + turn/start am bereits laufenden
App-Server via proxy. Nie automatisch umschalten, keinen neuen Daemon starten.
ApprovalPolicy never, Sandbox readOnly fuer Probe, workspaceWrite fuer N mit Dev
und Exchange als Schreibwurzeln; keine freie Shell-Argumentkonfiguration oder
Modell-/Denkstufenueberschreibung. Bestimmte App-Server-Turnwerte koennen dessen
spaetere Thread-Defaults beeinflussen, nicht jedoch ein Modellwechsel hier.

Ein Controllerabbruch ist kein Beweis, dass ein Codex-Turn beendet wurde. Direkte
Codex-Kinder behalten Ziel-Locks. Neue Dispatches benoetigen zudem eine aktuell
belegbar inaktive Thread-Identitaet. Ein unbekannter Ausgang bleibt uncertain.
recover arbeitet ausschliesslich offline/nach Stopp und ohne Modell: nur passende
Protokollabschlussbelege mit gueltiger Antwort oder ein eindeutiges nativ gebundenes
Patch koennen waiting_result/no_work nachweisen. Kein Reset auf ready nach einer
moeglicherweise ausgefuehrten Arbeit, keine geloeschte Historie als Reparaturweg.

Bereits verarbeitete Patches werden nach einem Apply-Fehler mit unveraenderter
Bindung nicht wieder adoptiert. Derselbe Result-run_id mit anderen Bytes ist ein
Konflikt. Die identischen, ins Archiv verschobenen Bytes bleiben auffindbar.
Ein neueres, nicht erklaertes Result wird konservativ als Veto behandelt, sofern
dessen nativ gepruefte Handoff-Zeit dies belegt; Zeit ist niemals die Grundlage
fuer die Auswahl eines Nachfolgers. Nachfolgebindung bleibt SHA- und Vierfachbezug.
Die Cachegroesse ist beschraenkt; inotify-Ueberlauf fuehrt zum erneuten Scan,
verschwundenes/ersetztes Exchange zum Halt. Ein nicht unterstuetzter Core-Vertrag
wird abgelehnt statt approximiert. Ausgaben, Antwortdateien und Protokollframes
sind groessenbegrenzt; aktive Dev-Prozesse werden dabei nicht zwangsbeendet.

Konfiguration/Probe/Recovery sind mit Start/Install-Bedienoperationen serialisiert.
Configupdates retargeten eine bestehende Ledger-Historie nicht still. Ein
beschraenkter Koordinationsschutz fuer eigene Prozesse ersetzt keine allgemeine
Codex-Sperre gegen zeitgleiche manuelle Befehle aus anderen Clients.

## Korrektur 005: Startquelle gehoert ausschliesslich zum Laufzeitzustand
Explizite Nutzerpraezisierung vom 18.10.2026, Vorrang vor alten Seed-in-Config-
Aussagen: configure --result initialisiert den Zustand EINMAL, ohne Modellturn
oder Dienststart. Die Konfiguration enthaelt nur die dauerhaften Ziel- und
Werkzeugeinstellungen. Der dauerhaft gespeicherte initiale SHA und erste Auftrag
stehen in der bereits vorhandenen SQLite-Historie, nicht in config.toml.

Ohne Historie benoetigt die Einrichtung ein explizites Result; es wird weder aus
Dateinamen noch aus mtime geraten. Nachfolgende gebundene Results und Neustarts
verwenden die bestehende aktuelle History. Die urspruengliche ZIP muss nicht mehr
existieren, sobald ein nachgewiesener Nachfolger massgeblich ist. Wiederholtes
configure ohne --result erhaelt die History; erneute Angabe derselben Startquelle
ist idempotent. Eine andere Quelle oder ein anderer Thread darf laufende,
abgeschlossene oder unklare Auftraege nicht still zuruecksetzen oder umbiegen.
Fehlender/beschaedigter State loest keine automatische Neuentwicklung aus.

State wird vor der aktivierten Konfiguration dauerhaft geschrieben. Ein Fehler
beim Config-Schreiben erlaubt denselben Einrichtungsauftrag erneut, niemals den
Reset schon erfasster Arbeit. Apply aendert weder echte Config noch State noch
die installierte Unit und startet weiterhin keinerlei Dienst oder Modell.

R-Vertrag zur Legacy-Uebernahme: Leere alte Seed-Felder sind bis zur expliziten
Einrichtung toleriert; neue Renderings enthalten sie nie. Nichtleere Felder werden
nur durch ausdrueckliches configure migriert, nie durch load/check/start oder Apply.
Existierende History muss zu dauerhaftem Ziel/Thread und altem Seed-SHA passen;
alle Jobs, Zustandsphasen und zugeordneten Patch-SHAs bleiben unveraendert. Ohne
History darf nur die exakte alte Startquelle nativ gelesen werden; Archivsuche
vergleicht SHA und Repo-ID, keine Auswahl des neuesten Dateinamens.

Neue History wird als vollstaendige Datenbank ueber den vorhandenen privaten
atomaren Dateischreiber exklusiv veroeffentlicht, nie ein vorhandener State ersetzt.
Ein altes Meta ohne Jobs darf nur nach expliziter, erfolgreicher Source-/Thread-
Pruefung mit dem bereits gespeicherten initialen SHA vervollstaendigt werden.
Fehler vor State-Publikation hinterlassen keine partielle autoritative History;
Fehler danach erhalten den State fuer einen idempotenten Einrichtungswiederanlauf.

## Transportkorrektur 006: bestehender Codex-Daemon

Der vorhandene lokale Codex-App-Server wird ueber den zu `CODEX_HOME`
gehoerenden Unix-Daemon-Socket und RFC6455-WebSocket angesprochen. JSON-RPC-
Nachrichten sind WebSocket-Textnachrichten und keine ungerahmten JSON-Zeilen.
Die Steuerung eroeffnet dabei ausschliesslich eine Clientverbindung, weder
Subprozess/Daemon noch neue Codex-Threads. Der WebSocket-Zugang ist metadata-
only bei `check` und `configure`, ein Modellturn wird nur bei `probe` oder
ausdruecklich gestarteter Arbeit erzeugt. Ein fehlender, unpassender oder
unterbrochener Socket fuehrt ohne automatischen Fallback zum Fehler. Vor
jedem Auftrag gilt die explizite Thread-ID- und Repository-Pruefung; eine
Live-Anzeige in Codex Remote wird nicht allein aus Protokollerfolg behauptet.

## Ergaenzung: benutzereigene Codex-Socket-Links

Das lokale Codex-App-Server-Daemon-Protokoll darf ueber einen
benutzereigenen Symlink auf einen privaten Unix-Socket erreicht werden.
Der Link befindet sich im privaten Codex-Kontrollverzeichnis, das Ziel
in einem privaten `codex-daemon-<uid>`-Ordner unter einem vertrauenswuerdigen
Temporary-Root; der Socket muss demselben Benutzer gehoeren und privat sein.
Nach dem Verbindungsaufbau muss der Kernel denselben Peer-UID bestaetigen.
Pfadwechsel und beliebige bzw. fremde Symlink-Ziele werden abgelehnt.
Es gibt keinen Daemon-Start, keine Rechteaufweichung und keinen neuen Thread.

## Korrektur 009: begrenzte Wiederholung bestaetigter Modellueberlastung

Dieser ausdrueckliche Nutzerauftrag vom 19.10.2026 ersetzt die bisherige
pauschale No-Retry-Regel ausschliesslich fuer nachgewiesene terminale
`serverOverloaded`-Fehler des App-Server-Transports. Alle anderen Sicherheits-
und Bediengrenzen bleiben unveraendert. Kein Modell- oder Denkstufenwechsel.

Die Laufzeit eines Turns ist unbegrenzt. Stille, `idle`-Notifications, fehlende
Token-Ausgaben oder abgelaufene RPC-Fristen beweisen keinen Turn-Abschluss.
Nur der passende terminale Turn und ein aktuell eindeutig inaktiver Thread
duerfen eine Ersatzanfrage ermoeglichen. Codex-internes `willRetry=true` wird
nicht durch eine zweite Anfrage ueberlagert. Ohne passendes `failed` und
`serverOverloaded` samt `willRetry=false` bleibt der Auftrag ungeklärt.

Die Wiederholung braucht vollstaendige, quellgebundene Turn-Belege ohne
moegliche produktive Seiteneffekte: Text/Reasoning sowie die eng begrenzten
Cwd-Probes `pwd`/`pwd -P`/`git rev-parse --show-toplevel` sind zulaessig,
sonstige Tools, unbekannte Items, Dateioperationen, Subagents und unvollstaendige
Befehle nicht. Vorhandene gebundene Patches werden uebernommen, nicht neu gebaut.
Quell-, History-, Thread- und Scope-Pruefungen gelten auch unmittelbar vor Retry.

Die Wartefolge ist standardmaessig 60, 180, 600, 1800 Sekunden: vier zusaetzliche
Versuche je Quell-Result, danach gesperrt. Die optionale externe Einstellung
`automation.retry_delays_seconds` darf leer sein (keine Retries) oder bis zu
acht aufsteigende positive Ganzzahlwerte bis 86400 enthalten. Bestehende Config-
Dateien werden nicht veraendert. Versuchszahl und absolute naechste Faelligkeit
liegen ausschliesslich in der bisherigen externen SQLite-Historie. Neustarts,
Pause/Resume und configure setzen das Budget nicht zurueck. Alte Belege werden
nie ueberschrieben; jeder Folgeversuch hat sein eigenes privates Verzeichnis.
Wartezeiten nutzen nur den Linux-Eventloop, keinen Modellaufruf. Aktive Threads
bleiben bei der Statuspruefung nach dem Backoff weiter ungestoert.

Journal: strukturierte Ursache, Turn-Zustand, Codex-Retryflag, Source-SHA,
Versuchsnummer, Faelligkeit und Entscheidung. Kein Prompt, kein Tool-Output,
keine komplette Konfiguration oder Anmeldedaten. `runtime_error` und
Automatikfehler bleiben getrennt sichtbar. Journalfelder sind maschinenlesbare
Vertraege, keine zu testende menschliche Konsolendarstellung.

Protokollreferenz (oeffentliche OpenAI-Dokumentation, 19.10.2026):
https://developers.openai.com/codex/app-server
`thread/read` liefert den Runtime-Status; `thread/turns/list` kann ohne Resume
volle, paginierte Turn-Belege liefern. Nur bei explizit nicht unterstuetzter
History-API wird das dokumentierte `thread/read(includeTurns=true)` versucht.
Nicht unterstuetzte/unvollstaendige Antworten erlauben keine Wiederholung.
Das tatsaechlich installierte 0.163.0-Backend ist hier nicht direkt erreichbar;
kein lokaler Testdouble behauptet einen nachgewiesenen Live-Statusaufruf.

R-Absicherung 009: Neue Ausfuehrungen speichern einen read-only Git-/Worktree-
Guard vor dem Modellstart; fehlender Guard erlaubt keinen automatischen Retry.
Vor Planung und unmittelbar vor Dispatch muessen Source, Patch-Abwesenheit,
aktuell inaktiver Thread, genaue fehlgeschlagene Turn-ID, vollstaendige erlaubte
Turn-Items und unveraenderter Guard uebereinstimmen. Turn-/Item-Duplikate,
unvollstaendige Befehle, extra User-Input, Erfolgskonflikte oder fremde Arbeit
bleiben gesperrt. Nach Verbindungsverlust nur eine lesende Statusklaerung, kein
zweiter Modellstart, kein Abbruch und keine Erfolgserfindung.

Fuer alte Jobs ohne Guard darf ausschliesslich explizites offline `recover`
aus vollstaendigen privaten Ereignissen plus aktueller genauer Turn-Historie
einen eng begrenzten Read-only-Overload nachweisen und den jetzigen Guard fuer
die Wartephase sichern. Es schreibt keinen Erfolgsbeleg, aendert keinen alten
Attempt und startet nichts. Schon eingeplante oder verbrauchte Versuche bleiben
als additive Datenbankzeilen erhalten; ein Fehler vor Transaktionsabschluss
publiziert weder halbe Retry-Zustaende noch ein zurueckgesetztes Budget.

## Korrektur 010: begrenzte grosse Codex-Antworten
Der nachgewiesene 2-MiB-Empfangsfehler ist kein unbekannter Turn-Ausgang aus
Modellgruenden. Der Client darf groessere Antworten bis 32 MiB lesen. Ausgehende
RPCs, exec-JSONL und lokale Antwortdateien behalten ihre bisherigen Grenzen.
Uebergrosse Nachrichten werden VOR Empfang ihres angekuendigten Bodys abgelehnt;
keine stille Kuerzung oder Teilantwort wird fuer Recovery verwendet.
Fehlerklasse codex_response_too_large mit rpc_method, limit_bytes und
announced_bytes wird strukturiert geloggt, ohne Inhalte aus dem Gespraech.
Laufende Turns, unbegrenztes Warten auf deren Abschluss, Retry-Sicherheitsbelege
und alle externen Dateien bleiben unberuehrt. Apply startet weder Codex noch Dienst.

### Korrektur 010 R: begrenzte, zielgerichtete Beobachtung

Bei inaktivem Thread liest Control zuerst Turn-Metadaten ohne Items mit
`thread/turns/list` (`itemsView=notLoaded`, absteigend, 50 Eintraege pro Seite).
Danach werden nur Items des exakten Turns mit `thread/items/list` und `turnId`
aufsteigend gelesen. Erst die vollstaendige Pagination und erneut gleiche
Abschlussmetadaten sowie der abschliessend inaktive Thread erlauben eine
vollstaendige Beobachtung. `active` und `inProgress` bleiben unangetastet.

Die Grenzen bleiben explizit: maximal 20 Metadatenseiten / 1000 Turns,
128 Itemseiten / 4096 Items und 32 MiB normalisierte Item-JSON-Bytes insgesamt.
Ein WebSocket-JSON-Dokument ist auf 32 MiB begrenzt, ausgehende Auftraege und
Exec-JSONL bleiben auf 2 MiB begrenzt. Hoechstens 256 unaufgefordert empfangene
Benachrichtigungen und 8 MiB ihrer JSON-Daten werden waehrend einer RPC-Abfrage
aufbewahrt. Die Grenzen schuetzen Speicher und Verarbeitungsumfang; sie sind
KEINE Laufzeitgrenze eines aktiven Entwicklungsauftrags. Metadaten-RPCs haben
weiterhin ihre bisherige 15-Sekunden-Antwortfrist.

Nur ausdruecklich nicht unterstuetzte Methoden/Parameter (-32601/-32602) erlauben
einen Kompatibilitaetsweg: einzelne volle Turns ab der bereits gefundenen
Metadatenseite, bei fehlender Turn-Pagination die begrenzte bisherige
`thread/read(includeTurns=true)`-Abfrage. Niemals nach Verbindungsfehler,
Groessenfehler oder unvollstaendigen Daten den Beleg abschneiden oder eine
schwache Zusammenfassung als vollstaendige Aktionsliste ausgeben. Der alte
History-Kompatibilitaetsweg kann bei ueber 32 MiB weiterhin sicher blockieren.

Kurze Journal-Ereignisse nennen `codex_response_too_large`, RPC-Methode und
Bytegrenzen; bei zu vielen wartenden Ereignissen stattdessen
`codex_event_backlog` mit Anzahl. Inhalt, Prompts und Konfiguration werden nicht
kopiert. Es werden weder Thread-Eingaben noch automatische Recovery-Freigaben
durch den Patch selbst ausgeloest.

### Korrektur 010 C: Trennung ohne neue Verhaltensregeln

`codex_ws.py` ist fuer die begrenzten WebSocket-Rahmen zustaendig,
`codex_proxy.py` fuer JSON-RPC und Ereignisse, `codex_history.py` fuer die
vollstaendige zielgerichtete Turn-Beobachtung. Die Budgets und gemeinsame
JSON-Bytezaehlung stehen in `codex_limits.py`. Oeffentliche Bedienbefehle,
Fehlercodes, Grenzen und Retry-/Recovery-Entscheidungen bleiben gegenueber
dem erfolgreich geprueften R-Zustand unveraendert.
