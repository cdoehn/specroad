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
Verlorene Rückgaben, die weitergehende Fehlerabsicherung sowie der explizite
Zugang bei einem abrupt beendeten Writer mit verwaistem Lock folgen in
`AUDIT-REC-02.R`. Discard benötigt weiterhin seinen unabhängigen Preflight;
dessen Rekonstruktion bleibt `AUDIT-REC-05`. Es entsteht kein neuer CLI- oder
automatischer Preflightablauf.
