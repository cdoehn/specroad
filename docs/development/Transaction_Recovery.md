# Recoverystatus und unveröffentlichter Discard

Planabschnitt 5.p, SR-REQ-0257 / 0262 / 0458, SR-VER-0019 / 0031.

## W: sicherer nutzbarer Kern

`inspect_recovery(root, expected_project_id=..., preflight=...)` liest aktive
Transaktionsjournale ohne regulären Modellload. Der maschinenlesbare Status
enthält Zustand, Journalhash, Basis-/Zielwurzel, bestätigte Veröffentlichungen
und nachgewiesene Discard-Kandidaten. Ohne unabhängigen Basisnachweis wird keine
Discard-Erlaubnis behauptet. Defekte Konfigurationen verhindern die reine
Journaldiagnose nicht. Die Diagnose erzeugt keine Dateien und erwirbt keinen
Writer-Lock; sie ist keine wiederverwendbare Schreibberechtigung.

`discard_unpublished_transaction(preflight, transaction_id, held_lock=...,
authority=..., actor=..., reason=..., expected_journal_sha256=...)` benötigt einen
aktuell gehaltenen nativen Recovery-Lock für `recover discard`, eine explizite
Host-Autorisierung und den erwarteten Journalhash. Ein Akteursname ist keine
Authentifizierung. Ein verwaister Lock wird nicht automatisch übernommen.

Der unabhängige `PublicationPreflight` enthält die bereits geprüften, eigenen
Basisbytes und die exakte geplante Inventur. Recovery prüft diese gegen ALLE
aktuellen Basisdateien und die aktuelle Inventur, ohne neu zu planen oder das
normale kanonische Modell vom Dateisystem zu laden. Eine bloß selbstkonsistente
Hashangabe aus dem Journal reicht nicht. Basisabweichung, nicht nachgewiesene
Inventur, veröffentlichte Einträge oder ein späterer Journalzustand sperren
Discard bereits im W-Kern.

W unterstützt eine alleinige `building`-Vorbereitung mit Journal und eine
vollständige `prepared`-Vorbereitung samt exakten Before-/Staging-Images.
Unbekannte oder unterbrochene Work-Inventuren bleiben zunächst erhalten und
blockieren die Mutation.

## Dauerhafte Beweise statt rekursiver Löschung

Unter `.specroad/recovery/transaction-audit/<event-id>/` werden zuerst das
Originaljournal und eine immutable `intent.json` exklusiv geschrieben und
synchronisiert. Erst danach wird das aktive Journal auf `rolled_back` gesetzt
und synchronisiert. Die gesamte geprüfte Vorbereitung wird innerhalb desselben
Projekts atomar nach `work/` im Audit verschoben; keine Zielbytes oder Beweisdatei
werden gelöscht. `completed.json` bindet den Abschluss an Originaljournal,
Intent, terminalen Journalhash und Basiswurzel. Frühere Audits werden niemals
überschrieben. Dateien und Verzeichnisse werden synchronisiert und zurückgelesen.

Die ausdrücklich reservierte passive Audit-Namensstelle blockiert nach dem
Discard keine normalen Modellleser oder neuen Writer. Aktive Journale und
unbekannte Recovery-Einträge bleiben dagegen Blocker. Ein später Fehler kann
bereits einen terminalen Journalstand oder ein archiviertes Work-Verzeichnis
hinterlassen; er wird nie als erfolgreicher Abschluss oder als „nichts passiert“
umgedeutet. Es gibt keinen automatischen destruktiven Rollback.

## Geltungsbereich und Nachweise

Native lokale Linux-Dateisysteme und kooperierende Writer gemäß bestehendem
Lock-/Storage-Kern. Descriptor- und Hashprüfungen erkennen beobachtete Änderungen;
sie sind kein Sandbox- oder CAS-Versprechen gegen böswillige gleichzeitige
Dateisystemmanipulation. Ein Ergebnis behauptet daher kein atomares Modellsnapshot.

Dies ist die fachliche Bibliotheksgrundlage, noch kein neu verdrahteter CLI-Befehl
oder vollständiger ChangeBackend. Eine Rekonstruktion des unabhängigen
Basisnachweises nach Prozessneustart, automatischer Transaktions-Preflight,
Zielabschluss, Restore und Rollback bleiben in ihren späteren Planabschnitten.

Für die Testausführung gilt die lokale `AGENTS.md`; die technische Anleitung
steht in [Testing.md](Testing.md). Die Recovery-Verhaltensfälle bleiben Teil
der Testsuite und begründen keine eigene Apply-Testauswahl.

## R: Unterbrechungen und Abwehrgrenzen

Building-Work darf nun fehlende Verzeichnisse, Teilmengen und kurze Präfixe der
unabhängig erwarteten Before-/Staging-Bytes enthalten. Auch ein teilweise
geschriebenes `journal.prepared` wird nur als passendes Präfix akzeptiert und
vollständig archiviert. Fremde Namen, ungebundene Bytes oder überlange Images
bleiben Blocker. Prepared verlangt weiterhin die vollständigen Images. Die
Intent-Datei bindet zusätzlich Länge und SHA-256 jedes tatsächlich vorgefundenen
Work-Files; die Abschlusskontrolle verifiziert die archivierten Bytes erneut.

Eine ausgewählte Vorbereitung kann neben anderen aktiven Einträgen verworfen
werden, sofern die vollständige Basis unverändert ist. Alle anderen Einträge
bleiben bytegleich und aktive Blocker; die aktive Menge wird erneut geprüft.
Status zeigt auch beobachtete spätere Zustände, aber markiert noch nicht
implementierte Journalschemata ausdrücklich als nicht validiert und gewährt
keine Mutation. `state_actions` sind zustandsabhängige *bedingte* Aktionen aus
Anhang C.3, `permitted_actions` enthält nur einen unabhängig bewiesenen Discard-
Kandidaten. Beides ist keine aktuelle Schreibberechtigung.

Die R-Tests erzeugen echte veröffentlichte Zielbytes, falsche Basisdateien,
gefälschte Zähler/Inventuren, harte und symbolische Links, Journal-/Imagewechsel
während der Beobachtung sowie Fehler beim Synchronisieren und Archivieren.
Abgelehnte Vorprüfungen schreiben keinen Audit. Fehler nach Mutationsbeginn
behalten den tatsächlichen Arbeitsstand und behaupten weder Erfolg noch einen
automatischen Rollback. Auch ein vorhandener Audit wird niemals überschrieben.

## C: Struktur ohne neue Fachfunktion

`recovery_read.py` bietet ausschließlich die schreibfreie Diagnose an;
`recovery.py` enthält nur die explizite Mutation und eine kompatible
Weiterexportierung der Diagnose. `_recovery_inputs.py` bündelt die gemeinsamen
read-only Beobachtungen. Öffentliche API, Zustände, Abwehrbedingungen, Audit-
Reihenfolge und Fehlerfolgen bleiben gegenüber W/R unverändert. Die W-/R-
Testfälle und ihre erwarteten Werte werden dafür nicht angepasst.

## 5.s.W: Schreibfreie Corrupt-Diagnose

Der Status kennzeichnet fehlende oder ungültige aktive Journale sowie fehlende,
veränderte oder unsichere Pflichtimages einer `prepared`-Transaktion als
beobachtetes `corrupt`. `observed_state` bleibt die ursprüngliche Behauptung;
`blockers` enthält konkrete logische Pfade und maschinenlesbare Gründe.
`critical_resources` bindet erwartete und beobachtete Längen/Hashes.

Die Diagnose schreibt keinen Marker, löscht keine Betriebsdaten und lädt kein
normales Modell. Der bestehende aktive Transaktionsbereich blockiert normale
Modellzugriffe und Writer unabhängig von der behaupteten Journalgültigkeit.
Ein fehlendes ausdrücklich ausgewähltes, aber nicht aktives Journal wird nicht
als neue Projektkorruption ausgegeben. `critical_inputs_verified` gilt nur für
den angegebenen `integrity_scope`, nie als allgemeine Modellfreigabe.

Unvollständige Building-Vorbereitung wird nicht allein aufgrund fehlender Images
als korrupt behandelt. Andere Zustände sind im W-Integritätsausschnitt noch
ausdrücklich `not_assessed`. Vollquellen-Restore bleibt Meilenstein 15; die
spätere autorisierte automatische Preflight-Recovery gehört zu 5.t. Bestehende
mutierende Recovery-APIs behalten ihre eigenen Lock-, Audit- und Recheckregeln.

## 5.s.R: Pflichtbytes und unverlierbare Schutzinventur

Die Integritätsprüfung unterscheidet nun Building-Präfixe, vollständige
Prepared-Images, verbrauchte Stages, auf Basis oder Ziel beobachtete Dateien,
benötigte Rollback-Before-Images und dauerhafte Commit-Receipts. Ein vollständig
belegtes Ziel wird nicht wegen regulär verbrauchter Stages als corrupt gemeldet.
Ein fehlendes Before Image für einen tatsächlich zurückzuführenden Zielstand
bleibt hingegen ein konkreter Blocker. Hashgültige vollständige Building-Images
werden geprüft; kurze Images sind ohne unabhängige Basis nur unbestätigte
Präfixe. Alle Eingaben werden erneut beobachtet, ohne Atomsnapshot zu versprechen.

`inspect_recovery_protection(root)` inventarisiert Journale, Before Images,
Staging, Rollbackreste, unbekannte Transaktionsdateien, Receipts und Recovery-
Audits. Die gesamten drei Namensräume bleiben geschützt, auch bei fehlendem
Journal oder einer unbewiesenen terminalen Behauptung. Fehlende Pflichtpfade
bleiben mit unbekannten Bytes sichtbar. Links werden nicht verfolgt.

`check_cache_removal(root, paths)` ist die schreibfreie Policy-Grenze für eine
explizite Cache-Dateiauswahl. Recovery- und Belegpfade, ihre Eltern, Verzeichnisse,
Symlinks und Hardlinks sind keine Cache-Löschkandidaten. Nur einzeln benannte
reguläre Dateien unter `.specroad/cache/` können die Auswahlprüfung bestehen.
Sie erteilt keine Schreibberechtigung, löscht selbst nichts und verlangt bei
einer späteren autorisierten Wartungsoperation einen frischen Write-Recheck.
Eine allgemeine Cache-Löschfunktion oder ein CLI-Befehl wird hier nicht
eingeführt. Die bestehende receipt-gebundene Work-Bereinigung ist ausdrücklich
keine Cachebereinigung und behält ihre eigenen strengen Abschlussnachweise.

Read-only-Diagnose erzeugt keinen Audit, da sie keine Recovery-Aktion ausführt.
Tatsächliche Discard-/Completion-/Rollback-Aktionen behalten ihre bestehenden
Audit- und Journalnachweise. Vollquellen-Restore wird nicht aus diesem Inventar
erfunden und bleibt Meilenstein 15 vorbehalten.

## 5.s.C: Eine gemeinsame Ressourcenkennzeichnung

`model/operational_paths.py` hält die recoverykritischen Namensräume, die
Receipt-/Auditrollen und die exakt passiven Verzeichnisse an einer Stelle.
Pfadklassifikation, Lock-Scan, schreibfreier Betriebs-Preflight und
Schutzinventur nutzen dieselbe Kennzeichnung. Die tatsächliche Verzeichnistyp-
und Byteprüfung bleibt bei den bestehenden Sicherheitsgrenzen. Gegenüber W/R
ändern sich weder Ressourcenrollen noch Blocker, zulässige Kandidaten,
Nebenwirkungen oder Testerwartungen. Es entsteht keine Restore-Funktion.


## AUDIT-REC-01: vollständige aktuelle Recovery-Inventur

Zielabschluss, Rollback und die Diagnose ab `committing` prüfen die vollständige
aktuelle JSON-Pfadmenge in den konfigurierten normativen Bäumen. Zuerst werden
die Bytes von `specroad.json` gegen die Journalbindung geprüft; eine geänderte
Konfiguration darf den betrachteten Bereich nicht verkleinern. Danach folgen
sichere Enumeration, vollständige Byteprüfung und erneute Inventurbeobachtung.
Die unterstützten Sprachpaketdateien und ausdrücklich gebundenen Nicht-JSON-
Ressourcen, etwa Anhänge und Sprachregistry, behalten ihre vollständige Bytebindung.
Unreferenzierte Payloads, generierte Daten und fremde nichtverwaltete Dateien
werden weder zur Modellinventur hinzugerechnet noch zur Reparatur entfernt.

Das Vollziel verlangt alle Zielpfade. Die Vollbasis schließt ausschließlich
bekannte, durch die Transaktion neu angelegte Pfade aus. Ein rückführbarer
Zwischenzustand enthält alle Basispfade und optional bekannte neue Zielpfade;
jede vorhandene Ressource muss dabei den gebundenen Basis- oder Zielbytes
entsprechen. Unbekannte Pfade oder veränderte unveränderte Ressourcen verhindern
eine Recoverymutation. Technische Fehler einer Zielprüfung sind kein Beweis für
eine Teilveröffentlichung und dürfen keinen Rollback eines Vollziels auswählen.

Vollständige Pfad- und Bytegleichheit bindet transitiv die im geprüften
PublicationPreflight unabhängig bestimmten Modellwurzeln. Recovery rekonstruiert
dafür weder eine ungespeicherte Profilauswahl noch lädt es ein reguläres Modell.
Die Journalbindung bleibt Voraussetzung; ein bloß selbstkonsistent manipuliertes
Journal authentifiziert seinen Ursprung nicht. Wiederholte Prüfungen erkennen
beobachtete Änderungen, versprechen aber kein atomares Snapshot gegen fremde
nichtkooperierende Writer.

Die Verhaltenstests `test_recovery_inventory.py` und
`test_recovery_inventory_right.py` prüfen zusätzliche/fehlende/veränderte Dateien,
unabhängige Basis-/Zieloracles, Änderungen während Autorisierung und Abschluss,
terminale Wiederaufrufe sowie schreibfreie Corruptdiagnose und Beweiserhalt.
Die SR-TC-0258/0459/0511-Manifeste weisen diesen Umfang als Teilnachweis aus.
Die weiteren Audit-Nacharbeiten bleiben gesondert offen. Die automatische
Recovery aus 5.t wird hier nicht eingeführt.

## AUDIT-REC-02.W: terminale Belege und Abschluss nach Writerende

Ein erfolgreicher Rollback schreibt einen unveränderlichen
`recovery-transaction-receipt-v1` unter
`.specroad/transactions/receipts/<transaktionshash>/transaction.json`. Er bindet
das vollständige terminale Journal, dessen Bytehash, die wiederhergestellte
Basiswurzel und den Recoveryaktionsbeleg. `outcome=rolled_back` ist ausdrücklich
kein erfolgreicher Request-Receipt. Discard verwendet dasselbe Receiptformat
mit `action=discard` und einer Hashreferenz auf seinen erhaltenen Audit-Intent.

Rollback und Zielabschluss schreiben außerdem einen unveränderlichen
`terminal-recovery-audit-v1` unter
`.specroad/recovery/transaction-audit/<transaktionshash>/<rollback|complete>.json`.
Dieser bindet Aktion, terminalen Journalhash, Projekt-/Request-/Rootidentität,
Basis-/Ziel-/Ergebniswurzel und die Host-Autorisierung. Ein Wiederaufruf prüft
den vorhandenen Nachweis und erhält seine ursprüngliche Autoritätszuordnung;
er erzeugt keine zweite normative Rückführung oder Veröffentlichung. Der Beleg
bestätigt das terminale Ergebnis, nicht die Anzahl zuvor unterbrochener Writes.

Nach Freigabe des ursprünglichen Writerlocks ist
`cleanup_recovered_transaction(transaction_id, held_lock=..., authority=...,
expected_journal_sha256=...)` öffentlich aufrufbar. Er verlangt einen aktuell
gehaltenen nativen Recoverylock mit `kind=recovery`, `command="recover run"`
und exakter Projekt-, Request- und Transaktionsbindung sowie eine registrierte
`RecoveryAuthority`, deren Callback die Aktion `cleanup` autorisiert. Der
Hash bezeichnet das jetzt terminale Journal. Es ist kein ursprüngliches
Preflightobjekt erforderlich. Ein normal abgeschlossener `committed`-Stand mit
verbliebener Arbeit benutzt denselben Weg.

Vor dem Archivieren werden der vollständige aktuelle Basis-/Zielstand, alle
Abschlussbelege und sämtliche vorhandenen bekannten Arbeitsdateien bytegenau
geprüft. Ein unveränderlicher `committed.json`- beziehungsweise
`rolled_back.json`-Marker am Receiptort und ein Cleanup-Intent werden dauerhaft
angelegt. Danach verschiebt ein atomarer Verzeichnis-Rename die geprüfte Arbeit
nach `transaction-audit/<transaktionshash>/cleanup-<journalhash>/work`; der
Abschlussbeleg bindet die dort erhaltene Inventur. Es wird nichts rekursiv
gelöscht. `cleanup_completed=true` bestätigt das Entfernen dieser Arbeit aus
dem aktiven Bereich. Fremde aktive Einträge bleiben erhalten und erscheinen in
`remaining_active_paths`; `recovery_required` bleibt dann wahr. Ein Folgeaufruf
prüft die Belege und Archivbytes ohne erneuten Fachwrite.

Die neuen Verhaltenstests verwenden unabhängige Writer-, Recovery- und
Cleanup-Prozesse bei bereits freigegebenem altem Lock. Sie prüfen anschließendes
normales Lesen und den Erwerb eines neuen Writerlocks, unveränderte normative
Bytes, kanonische Rollback-/Discard-Receipts, Auditbindung und schreibfreie
Ablehnung unbewiesener Eingaben. Die Requirementmanifeste bleiben Teilnachweise.
Die Fehlerabsicherung und der Zugang bei einem abrupt beendeten Writer sind
im folgenden R-Abschnitt beschrieben. Discard benötigt weiterhin seinen
unabhängigen Preflight; dessen Rekonstruktion bleibt `AUDIT-REC-05`.

## AUDIT-REC-02.R: wiederholbarer Abschluss und explizite Lockübernahme

Bereits vollständig vorhandene Belege werden bei einer Wiederholung byte- und
inodegebunden geprüft und erneut synchronisiert. Ein verlorener Write-, Rename-
oder Synchronisationsrückgabewert begründet keinen zweiten Fachwrite. Kurze oder
widersprüchliche Belege bleiben erhalten und blockieren den Abschluss; sie werden
nicht überschrieben. Die Untersuchung gebundener eigener Teilwrites bleibt
`AUDIT-REC-04`, die Bilanzierung des ursprünglichen ersten Completion-Receipt-
Fehlers bleibt `AUDIT-REC-03`.

Vor dem Archivieren von terminaler Arbeit entsteht ein aktiver, an Journal und
Intent gebundener Marker unter `.specroad/recovery/pending-<action>-<txn-hash>.json`.
Er bleibt bei unterbrochener Archivierung oder fehlendem Abschlussbeweis ein
Blocker für normale Zugriffe. Erst nach erneuter Prüfung und Synchronisation der
Belege, Archivbytes und aktuellen Basis-/Zielbytes wird genau dieser Marker
entfernt. Fremde aktive Pfade bleiben erhalten. Ein bereits abgeschlossener
Wiederaufruf erzeugt keinen neuen Marker und schreibt keine Belegbytes erneut.

Ein unterbrochener Discard wird mit demselben unabhängigen Preflight und entweder
dem ursprünglichen oder dem terminalen Journalhash erneut explizit aufgerufen.
Der Folgeaufruf prüft den originalen Audit-Intent und dessen vollständige
Work-Inventur, erhält die Event-ID und ursprüngliche Autoritätszuordnung und
beendet nur den belegten Abschluss. Bei bereits archivierter Arbeit wählt er
ausschließlich den kanonischen Transaktionsreceipt; er durchsucht keine Historie.

Für einen abrupt beendeten Writer bietet die Bibliothek den Contextmanager
`transaction_recovery_lock(root, transaction_id, project_id=..., request_id=...,
expected_lock_sha256=..., expected_journal_sha256=..., authority=..., actor=...,
reason=..., force=True, command="recover run", accept_remote_risk=False)`.
`command="recover discard"` unterstützt den ausdrücklich angeforderten Discard.
Die beiden erwarteten Hashes müssen den aktuell beobachteten Lock und das
ausgewählte Journal bezeichnen. Nach bereits erfolgter Archivierung kann ein
kanonischer terminaler Marker beziehungsweise Discardreceipt das Journal binden.

Die Übernahme verlangt den echten nativen Mutex, exakte Projekt-, Root-, Request-
und Transaktionsbindung sowie eine aktuelle Host-Autorisierung für `takeover`.
Lebende Eigentümer werden auch mit Risikozustimmung abgewiesen. Fremde,
unprüfbare oder mit wiedervergebener PID beobachtete Eigentümer benötigen die
bestehende ausdrückliche Risikozustimmung; ein Hostname oder eine PID allein
beweist keinen beendeten Eigentümer. Der optionale `owner_probe` ist derselbe
vertrauenswürdige Beobachtungsadapter wie in der bestehenden Lockbibliothek.

Das Originaljournal und ein unveränderlicher Übernahme-Intent binden alten und
neuen Eigentümer, Autorität und Risikoentscheidung. Erst nach ihrer dauerhaften
Anlage und erneuter Eigentümerprüfung ersetzt ein atomarer Rename den alten
Lock durch den vollständig vorbereiteten Recoverylock. Ein Abschlussbeleg
bestätigt die Übernahme. Bei einer Unterbrechung bleiben der tatsächliche Lock
und alle Belege erhalten; ein Folgeprozess kann den nun beobachteten Stand
erneut ausdrücklich übernehmen. Der Contextmanager gibt ausschließlich den
eigenen unveränderten Lock frei. Er entfernt kein Journal und startet keine
normale Fachoperation. `recover_project_lock(..., force=True)` behält sein
uneingeschränktes Veto bei vorhandenen Transaktionsjournalen.

Die R-Verhaltenstests prüfen verlorene Rückgaben, Synchronisationsfehler,
konfligierende und kurze Belege sowie echte Prozessabbrüche bei Übernahme und
Archivierung. Sie vergleichen unabhängig vorbereitete normative Bytes und
verifizieren die erhaltenen Belege und Fremdblocker. Dies bleibt native lokale
Linux-Recovery; CLI-Verdrahtung, automatischer Preflight, die vollständige
Fault-Injection-Matrix und Restore sind weiterhin spätere Planpositionen.

## AUDIT-REC-02.C: gemeinsame Abschluss- und Lockprüfungen

`_recovery_binding.py` hält die identische Prüfung des nativen Recoverylocks
gegen Kommando, Projekt, Request und Transaktion. Zielabschluss, Rollback und
Cleanup verwenden die feste `recover run`-Bindung; Discard verwendet weiterhin
`recover discard`. Die Aufrufer behalten ihre bisherigen Vorprüfungen und
Zeitpunkte für erneute Beobachtungen.

`_recovery_terminal.py` bündelt die schreibfreie Auswahl kanonischer terminaler
Journale sowie deren Receipt- und Ergebnisnachweis. Cleanup und Lockübernahme
verwenden dieselbe Journal-/Markerauflösung. `_recovery_work.py` prüft die
bekannten terminalen Arbeitsreste und bildet die unveränderte Datei-Inventur
für Cleanup- und Discardbelege. `_recovery_barrier.py` enthält die gemeinsame
Anlage und aktive Mengenprüfung des Pending-Markers.

Die mutierenden Abläufe behalten ihre Reihenfolge für Autorisierung, Beleganlage,
Synchronisation, Archivierung und Markerentfernung. Öffentliche APIs,
Belegbytes, Fehlerverträge, normative Ergebnisse und erlaubte Seiteneffekte
bleiben gegenüber W/R unverändert. Die bestehenden Verhaltenstests werden
unverändert weiterverwendet; die Requirementmanifeste bleiben Teilnachweise.
Die weiteren Audit-Nacharbeiten beginnen mit `AUDIT-REC-03.W`.

## AUDIT-REC-03.W: Mutationsstatus vor der ersten Receiptanlage

Der Zielabschluss merkt mögliche Betriebsdateimutationen unmittelbar vor dem
Anlegen eines fehlenden Receipts einschließlich seiner Elternverzeichnisse vor.
Ein Fehler nach Dateianlage, während eines Teilwrites oder nach vollständigem
Write mit verlorener Synchronisationsrückgabe liefert dadurch
`mutation_possible=true`. Zurückgelassene Bytes bleiben erhalten; es gibt keine
automatische Löschung, Wiederholung oder zusätzliche normative Veröffentlichung.

Die schreibfreie Prüfung eines bereits vorhandenen Receipts liegt vor dieser
Grenze. Ein dort festgestellter Konflikt bleibt `mutation_possible=false`, wenn
dieser Aufruf noch keinen anderen Receipt angelegt hat. Das Flag bezeichnet die
Möglichkeit einer Betriebsdateimutation, keine Behauptung eines Fachwrites oder
erfolgreichen Abschlusses. Die Verhaltenstests vergleichen die erhaltenen
Receiptbytes, den unveränderten Journalstand und unabhängig erwartete Zielbytes.
Die erweiterte Abdeckung von Verzeichnis- und späteren Markerfehlern folgt in
`AUDIT-REC-03.R`; der Wiederanlauf kurzer Hilfsdateien bleibt `AUDIT-REC-04`.

## AUDIT-REC-03.R: Verzeichnisse, Abschlussmarker und terminaler Wiederanlauf

`mutation_possible` bilanziert die möglichen Betriebsdateieffekte des aktuellen
Aufrufs. Die schreibfreie Prüfung eines vorhandenen Abschlussmarkers setzt das
Flag nicht. Waren beide Receipts bereits exakt vorhanden, bleibt ein Konflikt
vor Markeranlage oder Journalersetzung deshalb schreibfrei. Wurde zuvor ein
Receipt angelegt, bleibt diese Mutation auch bei einem späteren Konflikt erhalten.
Markeranlage und Journalersetzung setzen das Flag vor dem jeweiligen Schreibzweig.

Fehler bei Verzeichnisanlage, Elternsynchronisation, dem zweiten Receipt oder
einem Markerwrite erhalten die tatsächlichen Verzeichnisse und Bytes. Ein Fehler
vor der Journalersetzung erhält das ursprüngliche Journal und den vorhandenen
Marker; eine verlorene Rückgabe nach Ersetzung erhält das bereits abgeschlossene
Journal. Die Fehler behaupten keinen erfolgreichen Abschluss des Aufrufs und
keinen normativen Recovery-Write.

Die Anlage einer fehlenden terminalen Auditdatei meldet den Mutationsbeginn an
den gesamten Abschlussaufruf zurück. Dadurch bleibt sie bei einer späteren
fehlgeschlagenen Prüfung bilanziert. Exakte vorhandene Auditdateien werden
wiederverwendet; fremde Dateien vor dem Schreibzweig werden erhalten und zählen
nicht als eigene Mutation. Eine spätere explizite Wiederholung bestätigt den
gebundenen Endstand ohne erneute normative Veröffentlichung.

Die Verhaltenstests in `test_recovery_mutation_accounting_right.py` vergleichen
Dateibytes, Verzeichnisse, Mutationseinstufung und unveränderte normative Zielbytes.
Die Strukturkonsolidierung folgt in `AUDIT-REC-03.C`; eine Reparatur kurzer
Hilfsdateien bleibt Gegenstand von `AUDIT-REC-04`.

## AUDIT-REC-03.C: gemeinsame Mutationsbilanz und Fehlerübersetzung

`_recovery_mutation.py` enthält den gemeinsamen lokalen Mutationszustand für
Abschluss und Belegpersistenz. Sein Schreibbeginn-Callback setzt zuerst die
lokale Bilanz und benachrichtigt anschließend einen vorhandenen umgebenden
Abschlussaufruf. Die Aufrufer verwenden ihn an den bisherigen W/R-Grenzen.

Die gemeinsame Fehlerübersetzung erhält Fehlergrund, Pfad und Exitcode. Die
Aufrufer behalten ihre bisherige Entscheidung über Mutationsflags und
Pfadzuordnung: Vorhandene Abschlussfehler werden weitergereicht, übersetzte
Belegfehler bleiben an den Belegpfad gebunden. Autorisierung, Prüfungen,
Dateiwrites, Synchronisation und Wiederanlauf folgen derselben Reihenfolge.
Die W/R-Verhaltenstests bleiben unverändert. Die nächste Audit-Nacharbeit ist
`AUDIT-REC-04.U`, die Untersuchung kurzer eigener Recovery-Hilfsdateien.

## AUDIT-REC-04.W: vollständiger initialer Rollbacknachfolger

Der erste Wechsel `committing` → `rolling_back` bereitet `journal.rollback`
in einer namenlosen Datei desselben Dateisystems vor. Ein vollständiger Write,
`fsync`, Readback und erneute Lock-/Inventar-/Journalbindung gehen der Veröffentlichung
voraus. Ein atomarer Link macht ausschließlich die geprüfte Inode sichtbar und
ersetzt keinen vorhandenen Pfad. Es folgt die bisherige Ersetzung von `journal.json`.
Der veröffentlichte Nachfolger hat genau einen Link; Projekt-Symlinks und Dateien
mit mehreren Links werden weiterhin abgelehnt.

Dies verwendet das Linux-Verfahren
[`O_TMPFILE` mit anschließender Veröffentlichung über `/proc/self/fd`](https://man7.org/linux/man-pages/man2/open.2.html)
und die Standardbibliotheksfunktion
[`os.link` mit gebundenem Zielverzeichnis](https://docs.python.org/3/library/os.html#os.link).
Ein Abbruch vor der Veröffentlichung lässt das Originaljournal und die Images
unverändert und keinen kurzen Hilfsdateinamen zurück. Ein Abbruch nach dem Link
erhält den vollständigen Nachfolger für die explizite Wiederholung. Die namenlose
abgeleitete Datei wird beim Schließen ihres letzten Deskriptors freigegeben;
Originalquellen und veröffentlichte Beweise werden nicht gelöscht.

Das Dateisystem muss `O_TMPFILE` unterstützen und der Prozess seinen eigenen
Deskriptor über `/proc/self/fd` verlinken können. Ein tatsächlicher Hostblocker
ergibt Code 5; es gibt keinen benannten Ersatzwrite. Bereits vorhandene kurze
Dateien werden ohne Herkunftsnachweis weiterhin abgelehnt, auch wenn sie dem
erwarteten Präfix gleichen. Vorhandene vollständig passende Nachfolger behalten
ihre bytegeprüfte Wiederverwendung.

`test_recovery_initial_successor.py` prüft Teilwrites, harte Prozessabbrüche mit
anschließender auditierter nativer Lockübernahme, vollständigen Basisabschluss,
Retry ohne weiteren normativen Effekt und den vorhandenen Cleanup. Fehlerfälle
prüfen Konflikte, Quellenänderung, Stagingintegrität und fehlende Hostfunktionen.
W gilt ausschließlich für den initialen Rollbacknachfolger; spätere Cursor-/Endjournale,
Rollbackkopien, Receipts und Aktionsbelege bleiben `AUDIT-REC-04.R`.

## AUDIT-REC-04.R: fortsetzbare übrige Recovery-Hilfswrites

Das in W geprüfte Verfahren gilt nun auch für Rollbackkopien, spätere
`journal.rollback`-Nachfolger, Transaktions-/Requestreceipts, `journal.complete`,
terminale Aktionsbelege und Rollbackreceipts. Erst ein vollständig geschriebener,
synchronisierter und stabil zurückgelesener Inhalt wird exklusiv verlinkt.
Ein Fehler vor dem Link hinterlässt keinen kurzen benannten Rest. Nach einem
erfolgreichen Link bleibt die vollständige Datei für den nächsten expliziten
Aufruf erhalten. Bereits vorhandene vollständige Inhalte werden erneut geprüft
und synchronisiert; sie werden nicht als neuer Versuch überschrieben.

Vor dem Link werden nativer Lock, aktuelle Journalbindung, vollständige normative
Inventur und benötigte Quellen frisch geprüft. Rollbackkopien prüfen ihr
Originalimage auch nach dem Staging erneut. Receipts prüfen ihre vorhergehenden
Belege und das aktuelle Ziel; das Rollbackreceipt bleibt an den unveränderten
Aktionsbeleg gebunden. Die finale Journalersetzung folgt erst nach erneuter
Prüfung des vollständigen Nachfolgers. Fehler erhalten das tatsächliche Journal,
alle veröffentlichten Belege und bereits restaurierte normative Dateien.

Ein späterer Aufruf lädt den vorhandenen Journalzustand und verwendet vollständige
Belege einschließlich ihrer ursprünglichen Autoritätszuordnung weiter. Schon
restaurierte oder veröffentlichte normative Bytes werden nicht erneut ersetzt.
Der bisherige erhaltende Cleanup kann danach den geschlossenen Arbeitsbestand
archivieren und den normalen Writerzugriff wieder freigeben.

`test_recovery_auxiliary_writes.py` prüft alle neun zusätzlichen Schreibstellen
mit wiederholten nativen Unterbrechungen, echten Prozessabbrüchen, auditierter
Lockübernahme, Fremdpräfixen, unsicheren Dateitypen, konkurrierender Anlage und
veränderten Quellen beziehungsweise Locks. Die getrennten Mutationsbilanztests
prüfen weiterhin den Fehlervertrag; eigene namenlose Teilbytes werden dabei
nicht mehr als dauerhaft sichtbarer benannter Rest erwartet. Fremde kurze
Dateien bleiben unverändert Blocker. Die Linux-Voraussetzungen aus W gelten
weiter; Discard- und Cleanup-Schreibprotokolle behalten ihr bisheriges Verhalten.

## AUDIT-REC-04.C: gemeinsame Bindungs- und Dateifunktionen

`_recovery_files.py` enthält den gemeinsamen Writer für vollständig vorbereitete
namenlose Hilfsdateien, die exakte Wiederaufnahme von Rollbackhilfsdateien und
die Synchronisation einer gebundenen Datei samt Verzeichniseintrag. Der initiale
Rollbacknachfolger bleibt ein dünner Aufrufer mit seinen bisherigen Fehlerkennungen.
Rollback und Completion teilen die Synchronisation; ihre Inhaltsprüfungen und
Veröffentlichungsprüfungen bleiben davor beziehungsweise danach an derselben Stelle.
Die Elternkettensynchronisation unveränderbarer Belege bleibt getrennt.

`_recovery_binding.py` prüft neben dem nativen Lock die Identität eines erneut
geöffneten Arbeitsverzeichnisses und das exakte Vorgängerjournal. Die Aufrufer
behalten ihre Konfliktgründe und betroffenen Pfade. Quellen-, Vollinventur- und
Vorgängerbelegprüfungen erfolgen weiterhin in der jeweiligen Recovery-Operation.
Ergebnisse, Fehlerverträge, Mutationsbilanz und Dateieffekte entsprechen W/R;
deren Verhaltenstests bleiben unverändert. Nächster Schritt ist die Untersuchung
des unveröffentlichten Discards nach Prozessneustart in `AUDIT-REC-05.U`.
