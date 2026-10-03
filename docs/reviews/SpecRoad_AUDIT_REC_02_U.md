# AUDIT-REC-02.U – terminaler Recoveryabschluss

**Entscheidung vom 3. Oktober 2026: bestätigt.** Die vorhandenen öffentlichen
Bibliothekswege schließen Ziel-Recovery und Rollback fachlich ab, ermöglichen
danach aber keine vollständige Bereinigung mit normalem Folgezugriff ohne den
ursprünglichen Writerlock. Beim abrupten Ende des Writerprozesses blockiert
zusätzlich der erhaltene Lock bereits den Recoveryzugang. Rollback und Discard
haben keinen Abschlussbeleg am vorgeschriebenen Receiptort; Ziel-Recovery und
Rollback keinen gesonderten Nachweis der tatsächlich ausgeführten Recoveryaktion.

Dies ist die vorgeschaltete Untersuchungsentscheidung aus dem
[Implementierungsplan](../implementation/SpecRoad_Implementierungsplan.md#audit-nacharbeiten).
Sie repariert kein Produktverhalten. Die offenen W/R/C-Schritte erhalten unten
konkretisierte Abnahmen. Der Produktstand bleibt 237/885, `5.t.W` bleibt bis zum
Auditabschluss gesperrt.

## Bindung und Methode

- Result: `specroad-apply_Result_202135_1002_5d8e5f.zip`.
- Basiscommit: `33461a60ca916d78210939e99268501095d515a6`.
- Spezifikation: Version 0.2.7, SHA-256
  `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.
- Alle 1.406 Base-Dateien wurden gegen Git-Objektkennung und lokale Dateibytes
  abgeglichen; keine Abweichung, keine staged/unstaged Änderungen im Result.
- [Maschinenlesbare Beobachtungen](SpecRoad_AUDIT_REC_02_U_observations.json)
  enthalten die vollständige Resultprüfsumme, den Probehash und die untersuchte Bindung.
- [Reproduktionsprogramm](SpecRoad_AUDIT_REC_02_U_probe.py): acht Fälle unter
  Linux/CPython 3.14.4; ausschließlich eigene temporäre Projektverzeichnisse.
  Produktquellen, Tests und Apply-Repository wurden für die Untersuchung nicht verändert.

Die Fixtures stammen aus `tests/support/`; sie verwenden synthetische Akteure
und explizite Testautorisierung. Das ist kein Nachweis menschlicher Zustimmung
für echte Projekte. Recovery, Lockzugang, Cleanup und Folgezugriff erfolgen über
öffentliche APIs; es werden keine privaten Lockhandles gebaut, Lockdateien
entfernt oder terminale Journale für die Recovery erfunden.

Vier Fälle erzeugen ihren Ausgangsstand in einem echten Unterprozess und prüfen
ihn erst nach dessen Ende: vollständiges Ziel ohne Abschluss, partieller Commit,
normaler Commit ohne Cleanup und abruptes Writerende. Hinzu kommt die Gegenprobe
eines abrupt beendeten Lockeigentümers ohne Journal. `os._exit(23)` beendet den
jeweiligen Testprozess ohne Contextmanager-Freigabe; der native Eigentümercheck
beobachtete anschließend `dead`. Der partielle Commit wird vor dem zweiten
Zielwrite durch einen gezielten I/O-Fehler unterbrochen; sein Writerlock wird
beim regulären Verlassen des Prozesses freigegeben.

Die übrigen Fälle untersuchen die normale Cleanupfolge, den Zugriff mit
Recoverylock trotz erhaltenem Preflight sowie Discard mit erhaltenem Preflight.
Dieser letzte Fall ist ausdrücklich kein Nachweis einer unabhängigen
Preflightrekonstruktion nach Neustart; `AUDIT-REC-05.U` bleibt offen.

## Beobachtete Ergebnisse

| Fall | Tatsächliches Ergebnis | Bedeutung |
|---|---|---|
| Normaler Commit und Cleanup unter demselben Writerlock | `cleanup_completed=true`; Reader lädt das Modell, neuer Writerlock möglich; Transaktionsreceipt und archivierter Commitmarker vorhanden | Funktionierende Kontrolle; dieser Weg bleibt erhalten. |
| Vollständiges Ziel nach Ende des Writers ohne verwaisten Lock | Recovery liefert `commit_completed=true`, `current_target_verified=true`, `cleanup_completed=false`; normative Bytes bleiben gleich | Ziel- und Receiptrekonstruktion funktionieren, der terminale Arbeitsbereich bleibt aktiv. |
| Cleanup mit korrekt gebundenem Recoverylock und erhaltenem Originalpreflight | `ReceiptError`, Code 6, `cleanup_lock_binding_mismatch`; alle Dateibytes unverändert | Selbst der zusätzlich verfügbare Originalpreflight löst den Lockwiderspruch nicht. |
| Rollback nach partieller Veröffentlichung im beendeten Writerprozess | Exakte unabhängig gespeicherte Basisbytes wiederhergestellt; `rollback_completed=true`; Retry schreibt keine normativen Bytes und erhält sämtliche Dateibytes | Basisrückführung funktioniert. Receipt, Recoveryaktionsbeleg und terminaler Cleanup fehlen. |
| Discard eines Prepared-Journals mit erhaltenem Preflight | Keine normativen Writes; aktiver Bereich archiviert; sechs erhaltene Audit-/Arbeitsdateien; Reader und neuer Writer möglich | Funktionierender Archiv-/Freigabepfad; unter `transactions/receipts/` liegt dennoch kein Abschlussbeleg. |
| Normaler Commit, Writer endet vor Cleanup | Journal ist `committed`, Transaktionsreceipt vorhanden; Reader und neuer Writer blockieren | Der Cleanupzugang betrifft auch die reguläre Abschlussfolge nach Unterbrechung. |
| Abrupt beendeter Writer mit aktivem Journal | Eigentümer `dead`; Recoverylock scheitert an `lock_recovery_required`; explizite Lock-Recovery an `transaction_journal_blocks_lock`; alle Dateibytes unverändert | Sichere Einzelgrenzen bilden gemeinsam einen nicht auflösbaren öffentlichen Recoveryzugang. |
| Abrupt beendeter Lockeigentümer ohne Journal | Explizite Lock-Recovery entfernt den verifizierten toten Eigentümer mit Audit; Reader und neuer Writer möglich | Gegenbeleg gegen einen pauschalen Defekt der Lock-Recovery. |

Bei den blockierten terminalen Fällen liefert der normale Reader Code 5 mit
`model_loaded=false` und `normal_operation_started=false`. Ein neuer Writerlock
scheitert mit `transaction_journal_blocks_lock`; im Fall des erhaltenen alten
Locks mit `lock_recovery_required`. Es wurden nur die strukturierten Werte und
Dateieffekte ausgewertet, keine Konsolenformulierungen oder Darstellung.

Die erfolgreichen Readerkontrollen sind Aussagen über die kleinen synthetischen
Goal-Projekte und den erreichten Folgezugriff. Sie belegen keine vollständige
M4-Validierungsintegration für reale Requirementprojekte.

## Vertrag und Ursachen

**Abschluss und Cleanup:** SR-REQ-0259 verlangt einen unveränderbaren Beleg unter
`.specroad/transactions/receipts/` und anschließend mögliche Payloadbereinigung.
Anhang N.2 verlangt die Entfernung abgeschlossener Journale aus dem aktiven
Bereich beziehungsweise ihre beleggebundene Archivierung. Das aktive Journal
bleibt nach Ziel-Recovery, normalem Commit ohne Cleanup und Rollback stehen.

[`_CleanupSession.check_lock`](../../src/specroad/changes/_receipt_work.py)
akzeptiert ausschließlich `writer`/`change apply` und die ursprüngliche
Transaktions-/Requestbindung. [`project_lock`](../../src/specroad/changes/locking.py)
verweigert neue Writerlocks bei aktiven Journaleinträgen.
[`cleanup_completed_transaction`](../../src/specroad/changes/receipt_cleanup.py)
bietet keinen alternativen Abschluss unter Recoverylock;
[`_CompletionProof`](../../src/specroad/changes/receipt_read.py) verarbeitet nur
`CommittedJournal`, keinen terminalen Rollback. Das Erhalten einer passenden
Preflightinstanz ist daher allein keine Lösung.

**Belegort:** [`rollback_interrupted_transaction`](../../src/specroad/changes/_recovery_rollback.py)
schreibt den terminalen `RolledBackJournal` in den aktiven Arbeitsbereich.
[`discard_unpublished_transaction`](../../src/specroad/changes/recovery.py)
archiviert Journal, Intent und Abschlussdaten unter `.specroad/recovery/audit/`.
Discard erfüllt damit den hier geprüften Recoveryaudit-/Archivierungsanteil,
aber keiner der beiden Wege hinterlässt den Receipt an dem von SR-REQ-0259
vorgeschriebenen Ort. Ein vorhandenes Journal oder Auditarchiv ersetzt diese
konkrete Ablagepflicht nicht.

**Recoveryaktionsnachweis:** SR-REQ-0462 und §10.7 verlangen einen unveränderbaren
lokalen Datensatz der tatsächlich ausgeführten Recoveryaktion.
[`prepare_recovery_receipts`](../../src/specroad/changes/receipt_projection.py)
rekonstruiert die Receipts des ursprünglichen normativen Writes. Diese binden
dessen ursprüngliche Operationen und Akteur, aber keine neue Recoveryaktion
oder deren Autorisierung. Der Zielabschluss in
[`_recovery_completion.py`](../../src/specroad/changes/_recovery_completion.py)
erzeugt keinen zusätzlichen Aktionsnachweis; auch der Rollback legt keinen an.
Die Beobachtung stützt sich auf vollständige Betriebsdateiinventur und die
Erzeugerpfade, nicht allein auf das Fehlen eines bestimmten Auditverzeichnisses.
Die Spezifikation schreibt für diesen Aktionsnachweis keinen hier neu erfundenen
Dateinamen vor.

**Verwaister Writer:** `project_lock(kind='recovery', ...)` weist jeden bestehenden
Lockdatensatz zurück. `recover_project_lock(..., force=True)` verweigert bei
aktiven Journals schon vor der eigentlichen Eigentümerfreigabe. Diese einzelnen
Schutzgrenzen sind beabsichtigt; 5.i.R fordert ausdrücklich: „force umgeht kein
Journal“. Fehlend ist ihre sichere Zusammenschaltung für den transaktionsgebundenen
Recoveryzugang nach tatsächlich nachgewiesenem Prozessende. Ein pauschales
Entfernen dieser Prüfungen wäre keine zulässige Reparatur. SR-REQ-0205/0206/0221,
Anhang C.3 und N.3 bleiben maßgeblich; normale Modellloads bleiben bis zur
Klärung blockiert.

## Umfang der folgenden W/R/C-Reparatur

**W:** Den kleinsten nutzbaren expliziten Abschlussweg bei freigegebenem altem
Lock liefern. Er umfasst Rollbackreceipt, Recoveryaktionsbelege, den Receiptort
des Discards und beleggeprüfte Bereinigung unter korrekt gebundenem Recoverylock.
Ziel-Recovery, terminaler Rollback und regulärer Commit mit verbliebenen
Arbeitsresten müssen danach normale Folgezugriffe erlauben. Normative Bytes und
unveränderliche Abschlussbeweise bleiben erhalten. Ein wiederholter Abschluss
darf keinen zweiten Fachwrite ausführen.

**R:** Verlorene Rückgaben, Beleg-/Archivierungs-/Bereinigungsfehler und partielle
Cleanupzustände absichern. Zusätzlich den bestätigten toten Writer mit Journal
über einen expliziten, transaktionsgebundenen Recoveryzugang unter echtem nativen
Mutex behandeln. Vollständige Eigentümer-, Root-, Journal- und Ergebnisbindung
sowie ein unveränderlicher Übernahmebeleg sind erforderlich. Lebende, fremde,
unprüfbare oder geänderte Eigentümer und fremde aktive Transaktionen bleiben
gemäß ihrem jeweiligen Nachweis-/Risikovertrag geschützt. `lock recover --force`
darf weiterhin kein Journal umgehen.

**C:** Erst danach gemeinsame Abschluss-/Arbeitsrest-/Lockprüfungen strukturell
konsolidieren. Ergebnisse, Fehlerverträge und erlaubte Seiteneffekte bleiben erhalten.

Diese Abnahmen präzisieren die bereits offene `AUDIT-REC-02`-Folge. Sie beginnen
keine automatische Preflight-Recovery, keine neue Fachoperation, keinen Restore
und keine allgemeine Cachebereinigung. Die umfassende Crashmatrix aus 5.v und
die unabhängige Discard-Preflightrekonstruktion aus `AUDIT-REC-05.U` bleiben separat.
Kein Requirementmanifest wird durch diese Untersuchung auf `passed` gesetzt.

## Reproduktion und Ausführungsgrenzen

Vom Development-Repository aus:

```sh
python3 -I -B docs/reviews/SpecRoad_AUDIT_REC_02_U_probe.py "$PWD"
```

Das Programm legt ausschließlich frische temporäre Projekte an, beendet nur
eigene Unterprozesse und entfernt seine temporären Fixtures anschließend. Seine
JSON-Ausgabe enthält Beobachtungen, keine Assertion, dass die gefundenen Fehler
dauerhaft bestehen bleiben müssten. Die gespeicherten Ergebnisse gehören nur
zur oben genannten Basis; spätere Reparaturen dürfen die Beobachtungen ändern.
Das Programm wird nicht in die Produkttestsuite aufgenommen.

Die Untersuchung und ihre Gegenproben wurden im Development-Repository
ausgeführt. Für den OFF-PLAN-Apply-Commit sind über `tools/run_apply_tests.py`
die vollständige parallele und anschließend die vollständige serielle Testsuite
vorgesehen, einschließlich des seriellen Laufs bei parallelem Fehlschlag. Erst
beide erfolgreichen Läufe erlauben den Commit. Ein zukünftiger Apply-Erfolg wird
hier nicht vorweggenommen; maßgeblich bleibt das zurückgegebene Result.
