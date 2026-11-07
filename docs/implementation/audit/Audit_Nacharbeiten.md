# Audit-Nacharbeiten und ursprüngliche Abnahmen

Vollständiger übernommener Auditteil. Sein aktueller Gesamtstatus steht allein im [Fortschrittsblock](../SpecRoad_Implementierungsplan.md); die einzelnen Entscheidungen, Grenzen und Nachweise bleiben erhalten.

<a id="audit-nacharbeiten"></a>
## Audit-Nacharbeiten vor Fortsetzung mit 5.t

### Grundlage, Geltung und Fortschritt

Der Grobaudit vom 2. Oktober 2026 bewertet den bis **5.s.C** abgeschlossenen Produktstand insgesamt als **AUFFÄLLIG**. Die Grundlagen, Graph- und SRX-Kerne sowie große Teile des Schreibpfads erscheinen schlüssig; insbesondere die vollständige Recovery-Inventur und der Rollbackabschluss erfüllen aber bereits zugesagte Verträge nicht vollständig. Diese Nacharbeiten sind Bestandteil dieses einzigen Implementierungsplans. Der externe Prüfbericht bleibt eine unveränderte Befundquelle, kein zweiter Arbeitsplan.

| Bindung der Auditgrundlage | Wert |
|---|---|
| Result | `specroad-apply_Result_151409_1002_817f46.zip` |
| Geprüfter HEAD | `f5534e50e74a701b4a5b29cdcfc39e792e21e542` |
| Result-SHA-256 | `b7a8aec9356fa50f2bd6f895078485501528bf16e8a19404ca66ae81fc619229` |
| Prüfbericht im Exchange unter `reports/` | `SpecRoad_Grobaudit_2026-10-02_f5534e50.md` |
| Bericht-SHA-256 | `b9776b86d52851b02d2b116f88e1f817e90eda90504fb3c3c1e387ed982f4079` |

Die Prüfung war statisch; sie führte keine Tests aus. Das Result enthält keine Execution-Logs einer Apply-Ausführung und keine historischen W/R/C-Zwischenstände. Die Bindung oben dokumentiert den untersuchten Ausgangsstand; jedes Reparaturbundle verwendet ausschließlich die Bindung aus seinem dann neuesten Result.

**Aktueller Arbeitsauftrag:** Der Audit-Abschluss ist durch Result von Bundle 088 bestätigt. Die reguläre Fortsetzung richtet sich wieder nach `next_plan_commit` im Fortschrittsblock. Die 885 ursprünglichen Produktpositionen, ihre Kennungen, Reihenfolge und historischen Checkboxen bleiben erhalten; der Zähler bleibt während der Nacharbeiten bei **237/885**. Eine gesetzte alte Checkbox beseitigt keinen hier ausdrücklich offenen Befund.

Die Kennungen `AUDIT-*` sind Nacharbeitskennungen außerhalb der 885 Produktpositionen. Bei Umsetzung wird eine genau einem ursprünglichen Plan-Commit zuordenbare Reparatur als `FIX` mit dessen Kennung geführt; übergreifende Korrekturen werden als `OFF-PLAN` geführt. Die tatsächlichen Commitkennungen und Messages werden vor der jeweiligen Auslieferung passend zum dann aktuellen Result festgelegt und mit dem Nacharbeitsschritt verknüpft. Es gibt keine durch diese Liste vorgeschriebene Bundleanzahl. Mehrere geordnete Commits dürfen in einem Bundle liegen.

Die organisatorischen W/R/C-, Test- und PatchHarbor-Regeln werden in der lokalen **AGENTS.md des Codex-Arbeitsbereichs** gepflegt. Technische Testaufrufe beschreibt [Testing.md](../../development/Testing.md). Die folgenden Abnahmen beschreiben fachliches Verhalten, keine gezielte Apply-Testauswahl und keine zusätzlichen Testausführungsregeln. C erhält jeweils die Ergebnisse, Fehlerverträge und erlaubten Seiteneffekte aus W/R. Ein fehlender sinnvoller C-Delta wird nachvollziehbar dokumentiert, wie bereits im W/R/C-Abschnitt geregelt; es entsteht kein Alibi-Commit.

### Befunde und eindeutige Zuständigkeit

| Befund | Einordnung / Priorität | Ursprünglicher Bezug | Zuständige Nacharbeit | Stand dieser Planrevision |
|---|---|---|---|---|
| F01 – Recovery prüft nur journalbekannte Dateien | statisch nachgewiesene Lücke / hoch | 5.q–5.s; SR-REQ-0258/0459/0511 | AUDIT-REC-01 | W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F02 – Rollback ohne vorgeschriebenen Receipt und nutzbaren Abschluss-/Bereinigungspfad | nachgewiesener Vertragsfehler / hoch | 5.n, 5.r, 5.s; SR-REQ-0259/0462 | AUDIT-REC-02 | U bestätigt; W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F03 – falsches `mutation_possible` nach Receiptfehler | statisch nachgewiesener Fehler / mittel | 5.q.R, 5.n.R; SR-REQ-0258 | AUDIT-REC-03 | W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F04 – kurze eigene Hilfsdateien blockieren Wiederanlauf | dynamisch bestätigte Wiederanlauflücke / mittel | 5.q.R, 5.r.R; SR-REQ-0258/0459/0511; terminale Belege aus AUDIT-REC-02 | AUDIT-REC-04 | U bestätigt; W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F05 – veraltete Schema-/Versionsselbstbeschreibung | Schemaanteil und getrennte SRX-Bibliotheksreichweite geklärt / mittel | 1.i, 1.n, 2.q; SR-REQ-0194/0376/0392 | AUDIT-CONTRACT-01 | W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F06 – Change-Plan-Schema fehlt im Katalog | nachgewiesene Kataloglücke / mittel | 2.q, 5.a; SR-REQ-0377/0378 | AUDIT-CONTRACT-02 | W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F07 – nichtliterale Core-Lintanteile nicht durchgehend belegt | begrenzte Lücke bestätigt / mittel | 4.l, 4.o, 4.r; SR-REQ-0096 | AUDIT-VALIDATION-01 | W/R/C durch Results bestätigt; Abschlussentscheidung unten |
| F08 – produktive M4-Gateverbindung nicht durchgehend belegt | begrenzte Lücke bestätigt / mittel | 4.o–4.r, 5.f/5.g; SR-REQ-0086/0100 | AUDIT-VALIDATION-02 | W/R/C bestätigt; fehlende spätere Currentness-Dienste bleiben unvollständig |
| F09 – widersprüchliche Testanweisungen | Dokumentationswiderspruch / mittel | allgemeine Arbeitsanweisungen, TD-002 | AUDIT-DOC-01 | aktive Hinweise beim Abschluss abgeglichen; Historie erhalten |
| F10 – veraltete `open_items` und unvollständige Fixturebeschreibung | Nachweisdaten inkonsistent / niedrig | 3.h–3.j, 4.e/4.g/4.i; SR-REQ-0288/0412 | AUDIT-EVIDENCE-01 | W/R/C durch Results bestätigt; bestehende Partial-Grenzen erhalten |

Ein vorhandener Testverweis oder der Katalogstatus `partial` beweist keine vollständige Erfüllung. Die 293 als `partial` und 437 als `open` erfassten Anforderungen des Auditstands werden durch diese Planung nicht hochgestuft. Für jede spätere Schließung werden tatsächlicher Result-/Commitbezug, betroffene Testkennungen und beobachtete Abnahme dokumentiert; geplante Läufe zählen nicht als Nachweis.

### Verbindliche Bearbeitungsreihenfolge

`AUDIT-REC-01` → `AUDIT-REC-02.U` → `AUDIT-REC-02.W/R/C` → `AUDIT-REC-03` → `AUDIT-REC-04.U` mit gegebenenfalls bestätigter Korrektur → `AUDIT-REC-05.U` mit gegebenenfalls bestätigter Korrektur → `AUDIT-CONTRACT-01` → `AUDIT-CONTRACT-02` → `AUDIT-VALIDATION-01.U` → `AUDIT-VALIDATION-02.U` → `AUDIT-VALIDATION-03.U` → bestätigte und konkretisierte Validierungskorrekturen → `AUDIT-EVIDENCE-01` → `AUDIT-CLOSE`.

Eine U-Position ist eine Untersuchungsentscheidung, kein künstlicher W/R/C-Produktcommit. Ihr Ergebnis lautet **bestätigt**, **widerlegt** oder **nachweislich einer konkreten späteren Planposition zugehörig**. Bei Bestätigung werden die unten beschriebenen bedingten W/R/C-Schritte auf den tatsächlich festgestellten Fall eingegrenzt. Bei Widerlegung wird der Gegenbeleg dokumentiert; eine Produktänderung entfällt. Eine bereits fällige Abnahme darf nicht durch bloßes Verschieben auf einen späteren Schritt verschwinden. Wesentliche ungelöste Vertragswidersprüche bleiben offen und sperren `AUDIT-CLOSE`.

### AUDIT-REC-01 – vollständige Recovery-Inventur und Wurzelbindung

**F01; Voraussetzung:** 5.s.C. **Bezug:** 5.q/5.r/5.s; SR-REQ-0258/0459/0511; SR-VER-0019/0031; SR-TC-0258/0459/0511; Spezifikation §10.7 und Anhang C.3.

**Istgrenze:** `_recovery_target.py` prüft nur `target_inventory`; `_recovery_rollback.py` gibt nach vergleichbarer Teilprüfung die gespeicherte Basiswurzel zurück. Ein zusätzliches normatives Artefakt kann damit aus dem Vollständigkeitsnachweis fallen. Betroffene Nachweise: `test_transaction_recovery_completion_right.py` und `test_transaction_recovery_rollback*.py`.

- [x] **AUDIT-REC-01.W:** Aktuelle vollständige Pfadmenge und Bytes der bereits unterstützten normativen Ressourcen gegen gebundene Basis-/Zielinventur prüfen. **Abnahme:** Ein zusätzliches gültiges Artefakt verhindert bei sonst passenden Journaldateien den falschen Vollziel-/Basisnachweis; der unveränderte Positivfall ergibt exakt die unabhängig bestimmte gebundene Wurzel. Fremde Dateien bleiben erhalten.
- [x] **AUDIT-REC-01.R:** Fehlende, zusätzliche und veränderte Ressourcen sowie beobachtete Änderungen zwischen Prüfung und Abschluss einbeziehen. **Abnahme:** Zielabschluss, Rollback und Corruptdiagnose liefern konsistente Vollständigkeitsentscheidungen; kein Erfolg durch bloße Wiederholung derselben unvollständigen Inventur, kein geratener Ersatz und kein regulärer Modellload trotz aktivem Recoveryblocker.
- [x] **AUDIT-REC-01.C:** Gemeinsame Inventur-/Wurzelprüfung strukturell zusammenführen. **Abnahme:** W-/R-Ergebnisse, Fehlerklassen, Beweiserhalt und Seiteneffekte unverändert.


**W-Umsetzung (Bundle 048, OFF-PLAN `AUDIT-REC-01.W`):** Die unabhängig
aufgezählte aktuelle JSON-Pfadmenge wird gegen die journalgebundene Konfiguration
geprüft; sämtliche gebundenen Basis-/Zielbytes bleiben Teil der Prüfung.
Rollback verweigert unbekannte Pfade oder nicht rückführbare Ressourcen vor
einer eigenen Mutation. Vollständige Pfad- und Bytegleichheit bindet transitiv
die bereits im PublicationPreflight bestimmte Modellwurzel; Recovery erfindet
keine Profilauswahl und behauptet keine neue semantische Wurzelberechnung.
Die Verhaltenstests in `tests/test_recovery_inventory.py` vergleichen unabhängig
vorbereitete Modell-/Zielbytes und Wurzeln und prüfen den Erhalt fremder Dateien.
Commit: `fix(recovery): prove complete journal-bound inventories`.
Dieser Status wird erst durch die erfolgreichen Volltests und den W-Commit im
zurückgegebenen Apply-Result zum Ausführungsnachweis.


**R-Umsetzung (Bundle 048, OFF-PLAN `AUDIT-REC-01.R`):** Corruptdiagnose und
schreibende Recovery berücksichtigen dieselbe vollständige Pfadmenge.
Fehlende, zusätzliche und geänderte Ressourcen, Konfigurationsabweichungen,
Änderungen während Inventur/Autorisierung/Abschluss sowie terminale Wiederaufrufe
bleiben blockierend. Sprachpakete und gebundene Payloads behalten ihre Bytebindung.
Ein bloßer Fehler einer Vollzielprüfung wählt keinen Rollback: Die Auswahl erfolgt
aus tatsächlich beobachteten, vollständig gebundenen Basis-/Zielbytes.
Verhaltenstests: `tests/test_recovery_inventory_right.py`; die zugehörigen
SR-TC-0258/0459/0511-Manifeste beschreiben ausschließlich diesen Teilnachweis.
Commit: `fix(recovery): align inventory diagnosis and retry guards`.
Receipt-/Cleanup-Lücken, automatische Recovery und Restore bleiben offen.


**C-Umsetzung (Fortsetzung in Bundle 049, OFF-PLAN `AUDIT-REC-01.C`):** Gemeinsame
Inventurgrenzen stehen in `_recovery_inventory.py`, die unveränderte sichere
Bytebeobachtung in `_recovery_bytes.py`. Ziel-, Basis- und Zwischenbeweise nutzen
denselben Vor-/Nachcheck; Diagnose importiert den Bytebeobachter direkt statt
aus dem mutierenden Rollbackmodul. W-/R-Tests und fachliche Verträge bleiben
unverändert. Commit: `refactor(recovery): share inventory observation boundaries`.
Bundle 048 hat W und R nach jeweils beiden erfolgreichen Volltests committed.
Der vorbereitete C-Zustand bestand ebenfalls beide Volltests; sein Commit
wurde jedoch wegen zusätzlicher Leerzeilen am Ende von `_recovery_bytes.py`
durch die Git-Whitespace-Prüfung verhindert. Bundle 049 entfernt diese
Leerzeilen, erhält die gestagten C-Änderungen und wiederholt vor dem
C-Commit beide Volltests. Nach erfolgreichem Abschluss dieser Fortsetzung folgt
`AUDIT-REC-02.U`. Der Produktzähler bleibt 237/885; 5.t bleibt gesperrt.

### AUDIT-REC-02 – vollständiger terminaler Abschluss und Rollbackbelege

**F02; Voraussetzung:** AUDIT-REC-01. **Bezug:** 5.n/5.q/5.r/5.s; SR-REQ-0258/0259/0462; SR-VER-0019/0031; SR-TC-0258/0259/0462; §10.7 und Anhang N.2.

**Istgrenze:** Ein dauerhafter terminaler `RolledBackJournal` mit Ursprungsbindung existiert bereits. Es fehlen jedoch der vorgeschriebene Receipt unter `.specroad/transactions/receipts/` und ein nutzbarer Abschluss-/Bereinigungspfad; das aktive Verzeichnis blockiert neue Writer. Betroffen: `_recovery_rollback.py`, `receipt_read.py`, `receipt_cleanup.py`, `_receipt_work.py`, `locking.py` und `test_transaction_recovery_rollback*.py`.

- [x] **AUDIT-REC-02.U:** Zusätzlich den Zielabschluss nach Ende des ursprünglichen Writerprozesses über öffentliche Recovery-/Cleanup-APIs verfolgen. **Entscheidung:** Bestätigt; terminaler Cleanup ist nach Freigabe des ursprünglichen Writerlocks nicht erreichbar, Zielabschluss und Rollback besitzen keinen eigenen Recoveryaktionsbeleg, Rollback und Discard keinen Abschlussreceipt am Pflichtort. Ein echter abrupt beendeter Writer mit aktivem Journal blockiert bereits den öffentlichen Recoveryzugang. Der unten gebundene Bericht enthält Prozessnachweise und funktionierende Gegenproben; W/R/C bleiben offen.
- [x] **AUDIT-REC-02.W:** Den erfolgreichen Rollback durch vollständigen Basisnachweis, unveränderlichen Abschlussreceipt am Pflichtort, Recoveryaktionsbeleg und kontrollierten expliziten Abschluss der Arbeitsreste führen. **Abnahme:** Nach partieller Veröffentlichung wird die exakte Basis erreicht; Abschlussbeweise bleiben erhalten; ein neuer normaler Leser beziehungsweise autorisierter Writer kann wieder beginnen. Wiederaufruf erzeugt keine zweite normative Rückführung. Einen in U bestätigten gemeinsamen Cleanup-Zugangsfehler auf demselben Abschlussweg beheben.
- [x] **AUDIT-REC-02.R:** Verlorene Rückgaben und Fehler bei Beleganlage, Archivierung und Bereinigung absichern. **Abnahme:** Wiederaufnahme erhält bereits bewiesene Ergebnisse, Belegbindungen und fremde aktive Blocker; kein zweiter Fachwrite und keine Entsperrung durch bloßes Entfernen unbewiesener Journale. Teilweise Bereinigung darf keinen falschen vollständigen Erfolg ausgeben.
- [x] **AUDIT-REC-02.C:** Terminale Ergebnisnachweise und entbehrliche Arbeitsreste strukturell konsistent verwalten. **Abnahme:** Commit- und Rollbackresultate bleiben fachlich unterscheidbar; W-/R-Verträge und Byteerhalt ändern sich nicht.

**U-Ergebnis (Bundle 050, OFF-PLAN `AUDIT-REC-02.U`):**
[Untersuchung und Reproduktion](../../reviews/SpecRoad_AUDIT_REC_02_U.md), gebunden
an Result `specroad-apply_Result_202135_1002_5d8e5f.zip` und dessen vollständigen
Basiscommit `33461a60ca916d78210939e99268501095d515a6`. Acht isolierte
Untersuchungsfälle verwenden öffentliche APIs, temporäre Projekte und echte
Folgeprozesse; Testautorisierungen sind synthetisch. Der positive Discardfall
verwendet weiterhin einen erhaltenen Preflight und schließt `AUDIT-REC-05.U`
ausdrücklich nicht ab. Der Bericht ist ein Befundnachweis, keine Produktreparatur
und keine Hochstufung der Requirementmanifeste. Commit-Message:
`docs(recovery): document terminal recovery audit and repair scope`.
Der U-Status und Bundleabschluss werden erst mit dem tatsächlich nach beiden
Volltests erstellten Apply-Commit zum Übergabenachweis. Der nächste Schritt ist
`AUDIT-REC-02.W`; der Produktzähler bleibt 237/885.

**Konkretisierung der offenen Abschlusskorrektur aus U:**

- **W:** Zuerst den expliziten Abschluss bei bereits freigegebenem altem Lock
  ermöglichen: Rollbackreceipt am Pflichtort, unveränderlicher Recoveryaktionsbeleg
  für Rollback und Zielabschluss, passender Receipt für Discard sowie ein öffentlich
  erreichbarer Cleanup unter korrekt gebundenem Recoverylock. Der Abschluss muss
  ohne fortlebenden ursprünglichen Writerlock bis zum normalen Folgezugriff führen.
  Ein normaler `committed`-Stand mit unterbrochener Bereinigung benutzt denselben
  beleggeprüften Abschlussweg. Recovery-Cleanup darf keinen neuen Fachwrite ausführen.
- **R:** Neben Beleg-/Archivierungs-/Bereinigungsfehlern und verlorenen Rückgaben
  den in U bestätigten Fall eines abrupt beendeten Writers mit erhaltenem Lock
  behandeln. Ein expliziter, transaktionsgebundener Recoveryzugang muss echten
  nativen Mutex, vollständige Eigentümer-/Root-/Journalbindung und unveränderlichen
  Übernahmebeleg prüfen. Die Abnahme aus 5.i.R, dass `lock recover --force` kein
  Journal umgeht, bleibt erhalten: kein pauschales Entfernen von Locks oder Journals,
  keine automatische Übernahme, keine Abschwächung bei lebenden, fremden oder
  unprüfbaren Eigentümern. Vorhandene Risiko- und Autorisierungsgrenzen bleiben
  wirksam. Wiederholte Unterbrechungen dürfen weder Fremdblocker freigeben noch
  einen bereits belegten Fachwrite wiederholen.
- **C:** Erst nach diesen Verhaltensänderungen gemeinsame Abschlussbeweis-,
  Arbeitsrest- und Lockbindungsprüfungen konsolidieren; keine neue Recoverypolicy.

**Grenze:** Explizite bestehende Bibliotheks-/Recoverywege; kein automatischer Preflight, keine anschließende neue Fachoperation im selben Lauf, keine allgemeine Cachelösch- oder Restorefunktion.

**W-Ergebnis (Bundle 051, OFF-PLAN `AUDIT-REC-02.W`):** Rollback und Discard
erhalten unveränderliche Receipts am Pflichtort; Rollback und Zielabschluss
erhalten gebundene Recoveryaktionsbelege. Der öffentliche
`cleanup_recovered_transaction` prüft vollständige Basis-/Zielbytes und
Abschlussbelege unter einem exakt gebundenen Recoverylock. Er archiviert die
geprüften Arbeitsreste erhaltend, führt keinen neuen Fachwrite aus und lässt
fremde aktive Blocker bestehen. Derselbe Weg schließt normale `committed`-Reste
ab. Unabhängige Folgeprozesse prüfen den Weg vom bereits beendeten Writer über
Recovery und Cleanup bis zum normalen Lesen und neuen Writerlock. API und
Grenzen: [Transaction_Recovery.md](../../development/Transaction_Recovery.md).
Commit-Message: `fix(recovery): persist terminal evidence and enable explicit cleanup`.
Der W-Status und Bundleabschluss werden erst mit dem nach beiden erfolgreichen
Volltests erzeugten Apply-Commit zum Übergabenachweis. R/C bleiben offen; die
Produktzählung bleibt 237/885, der nächste Auditschritt ist `AUDIT-REC-02.R`.

**R-Ergebnis (Bundle 052, OFF-PLAN `AUDIT-REC-02.R`):** Vollständige Belege
werden nach verlorenen Synchronisationsrückgaben geprüft und erneut synchronisiert.
Ein aktiver Pending-Marker erhält die Sperre während unterbrochener Archivierung;
erst vollständige Abschluss-, Archiv- und Ergebnisnachweise erlauben seine
Entfernung. Cleanup und terminaler Discard setzen denselben belegten Abschluss
fort, erhalten Originalaudit und Fremdblocker und wiederholen keinen Fachwrite.
Der neue explizite `transaction_recovery_lock` übernimmt einen verwaisten,
transaktionsgebundenen Eigentümer unter echtem nativen Mutex und Host-Autorisierung.
Journal, alte/neue Eigentümerbindung und Risikoentscheidung bleiben unveränderlich
belegt; die atomare Übernahme verlangt einen erneuten aktuellen Eigentümercheck.
Das bestehende `lock recover --force` behält sein Journalveto. Lebende Eigentümer
bleiben gesperrt; fremde, unprüfbare und PID-wiederverwendete Eigentümer behalten
ihre ausdrückliche Risikogrenze. Echte Prozessabbrüche bei Writer, Übernahme und
Archivierung sowie Fehler- und Konfliktfälle prüfen den belegten Wiederanlauf.
Verhaltenstests: `tests/test_terminal_recovery_right.py` und
`tests/test_transaction_recovery_lock.py`; SR-TC-0258/0259/0462/0506/0569 bleiben
Teilnachweise. Kurze eigene Belege werden erhalten und nicht überschrieben;
AUDIT-REC-03/04/05 bleiben gesondert offen. API und Grenzen stehen in
[Transaction_Recovery.md](../../development/Transaction_Recovery.md).
Commit-Message: `fix(recovery): harden terminal retries and audited orphan takeover`.
Der R- und Bundleabschluss wird erst durch beide erfolgreichen Volltests und den
zugehörigen Apply-Commit zum Ausführungsnachweis. Als Nächstes folgt
`AUDIT-REC-02.C`; Produktzählung 237/885 und Sperre vor 5.t bleiben bestehen.

**C-Ergebnis (Bundle 053, OFF-PLAN `AUDIT-REC-02.C`):** Die identische native
Lockbindung für Zielabschluss, Rollback, Cleanup und Discard steht in
`_recovery_binding.py` mit fest zugeordneten Recoverykommandos. Schreibfreie
terminale Journal-/Receipt-/Ergebnisprüfungen stehen in `_recovery_terminal.py`;
Cleanup und Lockübernahme teilen die kanonische Journal-/Markerauflösung.
`_recovery_work.py` bündelt die Prüfung bekannter terminaler Arbeitsreste und
die unveränderte Datei-Inventur der Belege. Cleanup und Discard verwenden
dieselbe Pending-Marker-Anlage mit erneuter aktiver Mengenprüfung. Ihre
Mutationsabfolgen, Autorisierungsgrenzen, Fehlerverträge und Byteerhaltung
bleiben erhalten. Die W-/R-Verhaltenstests und ihre Oracles bleiben unverändert;
SR-TC-0258/0259/0462/0506/0569 werden nicht zu Vollnachweisen hochgestuft.
Commit-Message: `refactor(recovery): share terminal proof and lock checks`.
Der C- und Bundleabschluss wird erst durch beide erfolgreichen Volltests und
den zugehörigen Apply-Commit zum Ausführungsnachweis. Als Nächstes folgt
`AUDIT-REC-03.W`; die weiteren Nacharbeiten und die Sperre vor 5.t bleiben
bestehen. Der Produktzähler bleibt bei 237/885.

### AUDIT-REC-03 – wahrheitsgemäßer Mutationsstatus bei Receiptfehlern

**F03; Voraussetzung:** abgestimmte Abschlussfolge aus AUDIT-REC-02. **Bezug:** 5.q.R/5.n.R; SR-REQ-0258; SR-VER-0019; SR-TC-0258 und bestehender `RecoveryError`-Vertrag.

**Istgrenze:** `_recovery_completion.py` setzt `mutated` erst nach erfolgreicher Rückkehr aus `ensure_recovery_record`; `_recovery_receipts.py` und `_staging_files.py` können vorher bereits Betriebsdateien anlegen. Betroffen: `test_transaction_recovery_completion_right.py`.

- [x] **AUDIT-REC-03.W:** Mögliche Betriebsdateimutationen auch bei Fehler im ersten Receiptaufruf korrekt bilanzieren. **Abnahme:** Fehler nach Dateianlage, während Schreiben oder `fsync` ergeben keinen falschen `mutation_possible=False`-Befund; zurückgelassene Betriebsdateien bleiben erhalten.
- [x] **AUDIT-REC-03.R:** Verzeichnisanlage, Teilwrite, vollständiger Write mit Synchronisationsfehler und spätere Markerfehler abdecken. **Abnahme:** Ablehnung vor Mutationsbeginn bleibt von möglichen Dateieffekten unterscheidbar; normative Zielwrites oder Erfolg werden nicht erfunden.
- [x] **AUDIT-REC-03.C:** Mutationsbilanz und Fehlerübersetzung zusammenführen. **Abnahme:** Strukturierte Fehler und reale Dateieffekte aus W/R bleiben gleich.

**W-Ergebnis (Bundle 055, OFF-PLAN `AUDIT-REC-03.W`):** Der Zielabschluss
merkt eine mögliche Betriebsdateimutation nach der schreibfreien Receiptprüfung
und vor dem Anlegen eines fehlenden Receipts samt Elternverzeichnissen vor.
Dadurch verlieren Fehler im ersten Receiptaufruf ihre bereits möglichen
Dateiwirkungen nicht mehr. Verhaltenstests erzeugen eine leere Datei, einen
17-Byte-Teilwrite und einen vollständigen Write mit verlorener
Synchronisationsrückgabe. Die Fehler melden `mutation_possible=true`, erhalten
die tatsächlichen Receiptbytes und das unveränderte Journal und wiederholen
keinen normativen Write. Ein vorhandener widersprüchlicher Receipt bleibt eine
schreibfreie Ablehnung. Nachweis: `tests/test_recovery_mutation_accounting.py`
und SR-TC-0258 als Teilnachweis. Verzeichnis- und spätere Markergrenzen werden in
R weiter abgesichert; kurze Hilfsdateien werden hier nicht repariert.
Commit-Message: `fix(recovery): track mutation before creating recovery receipts`.
Die ausdrücklich beauftragte Testpolicy wird mit diesem Bundle im Apply-Runner
und seiner technischen Anleitung umgesetzt; die zentrale lokale AGENTS.md ist
entsprechend aktualisiert. Der W-Zustand ist hier der einzige und damit letzte
Bundle-Zustand. Sein Commit entsteht erst nach erfolgreichem parallelem und
zusätzlichem seriellem Apply-Volltest des zuvor lokal parallel geprüften Zustands.
Als Nächstes folgt `AUDIT-REC-03.R`; der Produktzähler bleibt 237/885.

**R-Ergebnis (Bundle 056, OFF-PLAN `AUDIT-REC-03.R`):** Die Mutationsbilanz
unterscheidet schreibfreie Markerprüfungen von tatsächlichen Schreibzweigen.
Ein bereits vorhandener widersprüchlicher Abschlussmarker meldet keine Mutation
dieses Aufrufs, sofern zuvor auch kein Receipt angelegt wurde. Markeranlage und
Journalersetzung markieren dagegen vor ihrem Aufruf mögliche Dateieffekte.
Beim Wiederaufnehmen eines bereits abgeschlossenen Journals bleibt eine neu
erzeugte Auditdatei auch in späteren Fehlern des Aufrufs bilanziert. Ein vor dem
Schreibzweig auftauchender fremder Auditdatensatz wird erhalten und nicht als
eigene Mutation gezählt.

24 zusätzliche Verhaltenstests decken Verzeichnisanlage und Elternsynchronisation,
den zweiten Receipt, leere und teilweise Markerwrites, Synchronisationsfehler,
Fehler vor/nach Journalersetzung sowie spätere Prüfungen und explizite Wiederholung
des terminalen Abschlusses ab. Sie vergleichen erhaltene Betriebsbytes und
Verzeichnisse mit dem tatsächlichen Fehlerpunkt und unabhängig erwarteten
normativen Zielbytes. Zwei Regressionen waren vor der Korrektur reproduzierbar.
SR-TC-0258 bleibt Teilnachweis; kurze Hilfsdateien und die vollständige spätere
Fault-Injection-Matrix werden nicht als erledigt ausgegeben.
Commit-Message: `fix(recovery): preserve mutation accounting across completion boundaries`.
Als Nächstes folgt `AUDIT-REC-03.C`; der Produktzähler bleibt 237/885.

**C-Ergebnis (Bundle 057, OFF-PLAN `AUDIT-REC-03.C`):**
`_recovery_mutation.py` bündelt die lokale Mutationsbilanz, die Weitergabe des
Mutationsbeginns an den umgebenden Abschlussaufruf und die Übersetzung von
Fehlergrund, Pfad und Exitcode. Abschluss und Belegpersistenz verwenden diesen
gemeinsamen Helfer an denselben Schreibgrenzen wie in W/R. Ihre bisherigen
Unterschiede bleiben ausdrücklich erhalten: Der Abschluss reicht vorhandene
`RecoveryError`-Objekte mit ergänzter Mutationsbilanz weiter; die Belegpersistenz
bindet übersetzte Fehler weiterhin an den ausgewählten Belegpfad und erhält
bereits gemeldete Mutationen.

Fachliche Ergebnisse, Belegbytes, Fehlerverträge, Prüf-/Schreibreihenfolge und
zulässige Dateieffekte bleiben erhalten. Die vorhandenen W/R-Verhaltenstests
werden unverändert verwendet. Die betroffenen Requirementmanifeste führen
AUDIT-REC-02/03 nicht länger als offene Nacharbeit, behalten aber ihren
Teilnachweisstatus und die übrigen offenen Abnahmen.
Commit-Message: `refactor(recovery): centralize mutation state and error translation`.
Als Nächstes folgt `AUDIT-REC-04.U`; der Produktzähler bleibt 237/885.

### AUDIT-REC-04 – kurze eigene Recovery-Hilfsdateien untersuchen

**F04; Voraussetzung:** AUDIT-REC-02/03. **Bezug:** 5.q.R/5.r.R; SR-REQ-0258/0459/0511; SR-VER-0019/0031; zugehörige SR-TC-Manifeste. Betroffen: `_recovery_rollback.py`, `_recovery_receipts.py`, `_recovery_completion.py` und Recovery-Right-Tests.

- [x] **AUDIT-REC-04.U:** Unterbrechungen während eigener `journal.rollback`-, Rollbackkopie-, Receipt- und Abschlussmarkerwrites prüfen. **Entscheidung:** Ist ein eindeutig gebundener eigener Teilzustand trotz intakter Quelle regulär nicht mehr fortsetzbar, oder ist die Ablehnung aufgrund des tatsächlichen Vertrags erforderlich? Kurze eigene Präfixe und fremde widersprüchliche Bytes getrennt nachweisen.

**U-Ergebnis (Bundle 058, OFF-PLAN `AUDIT-REC-04.U`): bestätigt.**
Die [Untersuchung](../../reviews/SpecRoad_AUDIT_REC_04_U.md) und ihre gebundenen
maschinellen Beobachtungen zeigen an zehn Schreibstellen jeweils fünf Varianten:
20 selbst erzeugte leere/kurze Dateien blockieren beide expliziten Wiederholungen,
obwohl ursprüngliche Images und Journalquellen erhalten sind. Zehn vollständige
Dateien mit verlorener `fsync`-Rückgabe erlauben beide Wiederholungen und keinen
zweiten normativen Write. Zehn widersprüchliche Fremddateien und zehn unabhängig
ersetzte Dateien mit gleichem kurzen Präfix bleiben ebenfalls erhalten und
blockieren. Die Diagnoseproben laufen mit vier xdist-Workern; sie schreiben
keine Defekte als dauerhafte Regressionserwartung fest.

Die Fremdpräfix-Gegenprobe ist wesentlich: Pfad und Präfix allein beweisen keine
eigene Herkunft. Die Lücke liegt im unterbrechbaren Hilfsdatei-Schreibprotokoll;
eine pauschale Freigabe kurzer vorhandener Dateien wäre keine sichere Reparatur.
Die folgenden Schritte müssen einen fortsetzbaren eigenen Versuch von fremdem
oder ungebundenem Bestand unterscheiden beziehungsweise verhindern, dass ein
unterbrochener eigener Versuch als solcher ungebundener Bestand veröffentlicht
wird. Bereits vorhandene zweifelhafte Reste bleiben ohne zusätzlichen belastbaren
Nachweis Blocker. Originalimages, Journale und abgeschlossene Belege bleiben erhalten.

- [x] **AUDIT-REC-04.W:** Den kleinsten bestätigten Fall am initialen `journal.rollback`-Write unter exakt gebundenem Recoverylock sicher fortsetzbar machen. **Abnahme:** Unterbrechung nach exklusiver Anlage und während des Writes lässt einen erneuten expliziten Aufruf mit intakten Quellen auf die vollständige gebundene Basis abschließen; ein weiterer Aufruf schreibt keine normativen Bytes. Fremde, widersprüchliche oder nur präfixgleiche ungebundene Dateien werden weder übernommen noch überschrieben. Der eigene Schreibversuch braucht einen überprüfbaren Herkunfts-/Inhaltsnachweis oder eine Veröffentlichung, die solche ungebundenen Teilzustände vermeidet; die konkrete Umsetzung wird im W-Commit begründet.
- [x] **AUDIT-REC-04.R:** Die übrigen bestätigten Varianten vervollständigen: Rollbackkopie, Cursorjournal nach bereits erfolgter Restauration, terminales Rollbackjournal, Transaktions-/Requestreceipt, `journal.complete` sowie terminale Recoveryaktionsbelege und Rollbackreceipt. **Abnahme:** Erneute Unterbrechung bleibt fortsetzbar; bereits restaurierte beziehungsweise veröffentlichte normative Bytes werden nicht erneut geschrieben. Basis/Vollziel, Originalbelege und frühere Autoritätszuordnung bleiben gebunden. Veränderte Quellen, fremde beziehungsweise ungebundene Reste und unsichere Dateitypen bleiben Blocker; bereits vollständige Dateien behalten ihre geprüfte Wiederverwendung. Zulässige eigene Arbeitsreste müssen mit dem vorhandenen beleggeprüften Abschluss-/Bereinigungspfad vereinbar sein.
- [x] **AUDIT-REC-04.C:** Nach W/R gemeinsame Bindungsprüfung, Hilfsdatei-Wiederaufnahme und Konfliktklassifikation strukturieren. **Abnahme:** Fachresultate, strukturierte Fehler, Mutationsbilanz, Beweiserhalt und zulässige Seiteneffekte bleiben gegenüber R unverändert; kein neues Reparaturverhalten.

Der U-Commit verändert keine Produktlogik und stuft keine Requirementabnahme hoch.
Commit-Message: `docs(recovery): confirm interrupted helper restart gaps`.
Als Nächstes folgt `AUDIT-REC-04.W`; der Produktzähler bleibt 237/885.
Automatischer Preflight (5.t), die umfassende Fault-Injection-Matrix (5.v),
Vollquellen-Restore (M15) und Discard-Neustart (`AUDIT-REC-05.U`) bleiben getrennt.

**W-Ergebnis (Bundle 059, FIX `5.r.R-FIX1`, Nacharbeit `AUDIT-REC-04.W`):**
Der initiale Wechsel von `committing` nach `rolling_back` schreibt seinen
Journalnachfolger zunächst in eine namenlose Datei desselben Dateisystems
(`O_TMPFILE`). Erst nach vollständigem Write, Dateisynchronisation und geprüftem
Readback wird genau diese Inode atomar und ohne Ersetzung fremden Bestands als
`journal.rollback` veröffentlicht. Danach folgen die bestehende Journalersetzung
und Verzeichnissynchronisation. Lock, aktuelles Inventar, Arbeitsverzeichnis und
Vorgängerjournal werden vor Veröffentlichung und vor Journalersetzung erneut
geprüft. Andere Rollbackjournal-, Kopie- und Receiptwrites behalten bis R ihr
bisheriges Verhalten.

Ein abgebrochener namenloser Versuch hinterlässt keinen kurzen kanonischen
Hilfsdateinamen; das originale Journal und alle Before Images bleiben verfügbar.
Ein bereits veröffentlichter vollständiger Nachfolger kann nach verlorener
Link-/Synchronisationsrückgabe bytegenau wiederverwendet werden. Vorhandene leere,
kurze, widersprüchliche oder unsicher verlinkte Dateien bleiben Blocker. Das
Verfahren benötigt Linux-Dateisystemunterstützung für `O_TMPFILE` und einen
nutzbaren `/proc/self/fd`-Link; fehlende Unterstützung liefert Code 5 ohne
Rückfall auf den unterbrechbaren benannten Write. Technische Erläuterung und
Grenzen: [Transaction_Recovery.md](../../development/Transaction_Recovery.md).

24 neue Verhaltenstests prüfen reale Teilwrites, zwei echte Prozessabbrüche,
verlorene Synchronisations-/Linkrückgaben, Fremdbestand einschließlich gleicher
Präfixe, Konkurrenz am Link, geänderte Quellen und fehlerhaften Readback. Die
explizite Wiederholung erreicht die unabhängig gebundene Basis; weiterer Retry
schreibt keine normativen Bytes, Cleanup erhält die Belege und erlaubt neuen
Writerzugriff. SR-TC-0459/0511 binden diese Abnahmen als Teilnachweise.
Diese begrenzte Reparatur ist 5.r.R eindeutig zugeordnet; der Produktzähler
bleibt 237/885. Commit-Message:
`Fix: publish initial rollback successors only after complete staging`.
Als Nächstes folgt `AUDIT-REC-04.R`; die übrigen bestätigten Schreibstellen und
die umfassende Crashmatrix bleiben offen.

**R-Ergebnis (Bundle 060, OFF-PLAN `AUDIT-REC-04.R`):**
Die übrigen neun bestätigten Schreibstellen verwenden jetzt dieselbe vollständige
namenlose Vorbereitung wie W: Rollbackkopie, Cursor-/Terminaljournal,
Transaktions-/Requestreceipt, Abschlussmarker, beide terminalen Aktionsbelege und
Rollbackreceipt. Native Writes, Dateisynchronisation und stabiler Readback gehen
dem exklusiven Link voraus; eigene leere oder kurze Dateien werden nicht unter
ihrem späteren Hilfsdateinamen sichtbar. Vollständige vorhandene Dateien werden
exakt geprüft und vor ihrer Verwendung erneut synchronisiert.

Vor der Veröffentlichung werden nativer Lock, Vorgängerjournal, aktuelle
vollständige Projektbytes und benötigte Quellen erneut geprüft. Rollbackkopien
halten ihr Originalimage an Bytes und Inode gebunden; Receipts prüfen bereits
gebundene Vorgängerbelege. Fremde Präfixe, unsichere Dateitypen und konkurrierende
Anlagen bleiben Blocker. Vollständige Aktionsbelege behalten Bytes, Inode und
Autoritätszuordnung bei einem späteren autorisierten Aufruf.

205 zusätzliche Verhaltenstests binden die neun Schreibstellen: wiederholte
native Write-/Synchronisations-/Linkfehler, 18 echte Prozessabbrüche mit nativer
auditierter Lockübernahme, fremde Präfixe und Dateitypen, Quellen-/Lockänderungen,
Readbackintegrität und ungültige Write-Rückgaben. Wiederaufnahme erreicht die
unabhängig bestimmte Basis beziehungsweise das Vollziel ohne doppelte normative
Ersetzung. Der bestehende Cleanup erhält den Arbeitsbestand und ermöglicht den
nächsten Writer. Die bisherigen Mutationsbilanztests injizieren ihre Fehler an
den neuen realen Schreibgrenzen; die Erwartung eines eigenen kurzen benannten
Rests entfällt, die Fremdrest-Gegenprobe bleibt erhalten.

Die Korrektur betrifft 5.q.R, 5.r.R und terminale Belege aus AUDIT-REC-02 und wird
deshalb gemeinsam als OFF-PLAN geführt. Die fünf betroffenen SR-TC-Manifeste
bleiben `partial`; der Produktzähler bleibt 237/885. Linux-`O_TMPFILE` und ein
nutzbarer `/proc/self/fd`-Link bleiben Voraussetzung; fehlende Hostunterstützung
führt zu Code 5 ohne unsicheren Ersatzwrite. Discard-/Cleanup-Schreibprotokolle,
automatischer Preflight, Vollquellen-Restore und die umfassende Crashmatrix werden
nicht auf diesen Ausschnitt vorgezogen.
Commit-Message: `fix(recovery): resume all bound auxiliary writes after interruptions`.
Als Nächstes folgt `AUDIT-REC-04.C`: gemeinsame Bindungsprüfung, Wiederaufnahme
und Konfliktbehandlung strukturieren, bei unveränderten W-/R-Verträgen.

**C-Ergebnis (Bundle 062, OFF-PLAN `AUDIT-REC-04.C`):**
Das gemeinsame Modul `_recovery_files.py` bündelt die namenlose Vorbereitung,
die exakte Wiederverwendung von Rollbackhilfsdateien und die Synchronisation
einer gebundenen Inode mit ihrem Verzeichniseintrag. Rollback und Completion
verwenden dieselbe Synchronisationsfunktion. Ihre jeweils davor und danach
liegenden Inhalts- und Veröffentlichungsprüfungen behalten die bisherige
Reihenfolge. Der initiale Rollbacknachfolger delegiert mit seinen unveränderten
W-Fehlerkennungen an den gemeinsamen Writer.

`_recovery_binding.py` bündelt zusätzlich die Verzeichnisidentitätsprüfung und
die Prüfung des exakten Vorgängerjournals. Journalwechsel, Rollbackkopien und
Receiptveröffentlichung verwenden diese Prüfungen mit ihren bisherigen
Fehlergründen und Pfaden. Operationsspezifische Inventur-, Lock-, Quellen- und
Vorgängerbelegprüfungen bleiben an ihren bisherigen Aufrufgrenzen.

Die vorhandenen W/R-Verhaltenstests bleiben bytegleich. Das Refactoring erhält
Fachresultate, Belegbytes und Autoritätszuordnung, Fehlercodes und Mutationsbilanz
sowie die zulässigen Dateieffekte. Die fünf betroffenen Requirementmanifeste
führen die Strukturkonsolidierung nicht länger als offene Nacharbeit; ihre
Teilnachweise und übrigen offenen Abnahmen bleiben erhalten. Dieser Schritt
führt kein neues Reparaturverhalten ein und erhöht den Produktzähler nicht.

**Korrektur der Übergabe 061:** Das Result
`specroad-apply_Result_104253_1004_8ac543.zip` bestätigt jeweils 5.545 bestandene
Tests parallel und seriell. Danach scheiterte `git diff --cached --check` an
einer zusätzlichen Leerzeile am Ende der neuen `_recovery_files.py`.
Es entstand kein Commit; die 14 vorgesehenen Dateien blieben im Index erhalten.
Bundle 062 bindet diesen tatsächlichen Zustand und korrigiert die Leerzeile
sowie den Bundle-Verweis. Die gesamte C-Änderung bleibt derselbe Commitumfang;
der Abschluss folgt erst nach erneuten erfolgreichen vorgeschriebenen Tests.

Commit-Message: `refactor(recovery): centralize auxiliary file bindings and durability`.
Als Nächstes folgt `AUDIT-REC-05.U`; der Produktzähler bleibt 237/885.

### AUDIT-REC-05 – unveröffentlichter Discard nach echtem Neustart

**Bestätigte Neustart-/Integrationslücke; Voraussetzung:** AUDIT-REC-01 bis 04. **Bezug:** 5.p.W/R; SR-REQ-0257/0262/0458; SR-VER-0019/0031; SR-TC-0257/0262/0458; §10.7 und Anhang C.3/N.1. Betroffen: `recovery.py`, `_recovery_inputs.py`, die persistente Nachweisgrundlage und die vorhandenen Discardtests.

- [x] **AUDIT-REC-05.U:** Building/Prepared in einem Prozess erzeugen und den Folgeprozess ausschließlich mit persistenten Eingaben starten. **Entscheidung: bestätigt.** Der vorhandene Discardkern schützt unzureichende Eingaben korrekt, aber der Produktpfad rekonstruiert seinen unabhängigen Basisnachweis nicht aus dem eigenen persistenten Transaktionsbestand. Ein zusätzlich extern gespeicherter Originalplan plus fixturebegrenzter Rekonstruktionsadapter ermöglicht den Neustartfall; dieses Gegenbeispiel ist kein vorhandener Produktadapter. Die bereits fällige Abnahme aus 5.p bleibt als konkrete Nacharbeit offen.

**U-Ergebnis (Bundle 063, OFF-PLAN `AUDIT-REC-05.U`):**
[Untersuchung](../../reviews/SpecRoad_AUDIT_REC_05_U.md), reproduzierbare Prozessprobe
und maschinenlesbare Beobachtungen binden Result
`specroad-apply_Result_131124_1004_93e82b.zip`, Basiscommit
`762f8900ec183c5870ffba9b118fe50b6af913d0` und die unveränderte Spezifikation.
Dieses Result bestätigt den erfolgreichen C-Abschluss von Bundle 062 nach
je 5.545 bestandenen parallelen und seriellen Apply-Tests bei sauberem Zustand.

Die 16 parallelen Diagnosefälle verwenden getrennte Writer-/Recoveryprozesse;
sechs Writer enden abrupt mit erhaltenem nativen Lock. Fünf Fälle ohne zusätzlichen
Originalplan bleiben mit `recovery_base_preflight_required` blockiert. Fünf
Gegenbeispiele mit extern gespeichertem Plan rekonstruieren aus vollständig
aufgezählten aktuellen Fixturedateien einen unabhängigen Preflight und schließen
Discard ab, einschließlich eines 17-Byte-Stagingrests. Sechs negative Fälle
verweigern geänderte Basis, zusätzliches gültiges Artefakt oder falsche Planbindung.
Alle Beobachtungen erhalten die normativen Bytes und die ursprünglichen
Transaktionsbeweise. Das Probeprogramm ist kein allgemeiner Produktloader.

5.t betrifft den automatischen Transaktionspreflight, 5.v die umfassende
Fehlerinjektionsmatrix. Die Resume-/Snapshotpositionen aus Meilenstein 6 und
Restore aus 15.j übernehmen nicht die bereits in 5.p zugesagte Discardfähigkeit.
Eine konkrete spätere Zuständigkeit für deren fehlenden expliziten Neustartweg
ist damit nicht belegt. Die drei Requirementmanifeste bleiben `partial`; ihre
bisher pauschale Verschiebung der Rekonstruktion auf spätere Schritte entfällt.
Commit-Message: `docs(recovery): confirm unpublished discard restart dependency`.
Der U-Abschluss wird erst mit dem passenden erfolgreichen Apply-Result zum
Übergabenachweis. Produktstand 237/885 und Sperre von 5.t.W bleiben erhalten.

**Konkretisierte Korrektur, in dieser Reihenfolge:**

- [x] **AUDIT-REC-05.W:** Einen öffentlich nutzbaren expliziten Neustartweg für eine vollständig vorbereitete unveröffentlichte Transaktion bereitstellen. Der neue Prozess erhält ausschließlich die dokumentierten persistenten Recoveryeingaben und eine frische Hostautorisierung; kein erhaltener oder serialisierter `PublicationPreflight`, kein nur vom Test ergänzter Originalplan. Benötigte zusätzliche Nachweisdaten müssen Bestandteil des definierten persistenten Transaktionsvertrags sein. **Abnahme:** Vollständige aktuelle Basisinventur und Basiswurzel unabhängig vom bloßen Journalanspruch prüfen, Journal-/Projekt-/Quellenbindung vor Mutation erneut sichern, unter neuem nativen Recoverylock verwerfen, alle ursprünglichen Beweise erhalten und einen neuen Writer erlauben. Normative Bytes bleiben unverändert. Ein aktives Journal wird nicht durch einen regulären Modellload umgangen; keine erneute Fachplanung als versteckte Discardvoraussetzung.
- [x] **AUDIT-REC-05.R:** Beide unveröffentlichten Zustände, die bestätigte unterbrochene Building-Vorbereitung mit eigenem kurzem Stagingrest sowie Wiederanläufe nach unterbrochenem Discardabschluss behandeln. **Abnahme:** Getrennte Prozesse mit freigegebenem oder tatsächlich verwaistem Writerlock; vollständige Basisbindung auch bei zusätzlichem gültigem Artefakt, geänderten/fehlenden Ressourcen und widersprüchlichen persistenten Eingaben. Publikation, falsche Bindung, unvollständiger Nachweis, fremde Workreste oder unzulässige Eigentümer bleiben Blocker. Originalbytes, abgeschlossene Belege und tatsächliche Zwischenzustände bleiben bei Fehler erhalten; eine Wiederholung führt keinen normativen Write aus.
- [x] **AUDIT-REC-05.C:** Nachweisrekonstruktion, schreibfreie Diagnose und autorisierte Mutation strukturell trennen beziehungsweise gemeinsame Prüfungen konsolidieren. **Abnahme:** Die W-/R-Ergebnisse, Fehlerverträge, Autoritätsgrenzen und zulässigen Dateieffekte bleiben unverändert; kein neues Fachverhalten.

**Grenze:** Expliziter Bibliotheks-/Recoveryweg und dessen persistente Nachweise.
Kein automatischer Preflight, Vollquellen-Restore oder Vorziehen eines allgemeinen
CLI-/ChangeBackend-Adapters.

**W-Umsetzung (Bundle 064, OFF-PLAN `AUDIT-REC-05.W`):** Das erfolgreiche Result
`specroad-apply_Result_152751_1004_3a508f.zip` bestätigt Bundle 063 mit Commit
`2558feb44857f32c7c0f33b2ee8be1326b4d6e47`, sauberem Zustand und je 5.545
bestandenen parallelen/seriellen Tests. Darauf aufbauend speichert der native
Journalpfad die explizite Profilauswahl, Anhangdeskriptoren und Sprachpaketpfade
als geschlossenes `discard-basis-v1`-Dokument im Feld `discard_basis`.
Es enthält keinen Change Plan und kein serialisiertes Laufzeitobjekt.

`prepare_discard_recovery` prüft einen vollständigen Prepared-Bestand schreibfrei
gegen Projekt-ID und erwarteten Journalhash. Es zählt die aktuelle normative
JSON-Inventur unabhängig auf, prüft sämtliche gebundenen Basisbytes, komponiert
die tatsächlich gespeicherten Profile/Sprachressourcen und berechnet die
vollständige Basiswurzel aus deren semantischen Ressourcen neu. Ein lediglich
selbstkonsistenter Before-Hash genügt nicht. Die resultierende `DiscardPreflight`
ist eine Diagnose, keine Schreibberechtigung. Der bestehende Discardweg prüft
ihre exakte Journal-/Rootbindung und alle Basisbytes unter dem frischen nativen
Recoverylock erneut, auch nach Autorisierung und vor dem Abschluss.

Die Verhaltenstests in `tests/test_discard_restart.py` verwenden separate
Writer- und Recoveryprozesse für Änderung, Neuanlage, Noop, mehrere Profile mit
Anhang und ein gebundenes Sprachpaket, jeweils mit normal freigegebenem oder
tatsächlich verwaistem Writerlock. Der Folgeprozess benötigt ausschließlich den
Projekt-/Transaktionsbestand und frische explizite Hostautorisierung. Unabhängige
Byte-/Wurzeloracles, native Writebeobachtung, Audit-/Receiptprüfung und ein neuer
Writer belegen den Abschluss. Negativfälle schützen geänderte/unvollständige
Inventuren, Images, fremde Workdateien, falsche Bindung und abgelehnte Autorität.

Alte Journale ohne `discard_basis` bleiben über die bisherige unabhängige
Preflight-Bindung lesbar und verwerfbar. Der neue Neustartweg lehnt fehlende
Auswahldaten ab und erfindet sie nicht. Building, unterbrochene Vorbereitung und
Rekonstruktion nach einem unterbrochenen Discardabschluss bleiben R. Die drei
Requirementmanifeste bleiben `partial`. Die Änderung betrifft den persistenten
Journalvertrag aus 5.j und den Discardkern aus 5.p und wird daher gemeinsam als
OFF-PLAN geführt. Commit-Message:
`fix(recovery): reconstruct prepared discard proof after restart`.
Der Abschluss wird erst durch den passenden erfolgreichen Apply-Commit bestätigt.
Nächster Schritt: `AUDIT-REC-05.R`; Produktzähler unverändert 237/885.

**R-Umsetzung (Bundle 065, OFF-PLAN `AUDIT-REC-05.R`):** Result
`specroad-apply_Result_162511_1004_801033.zip` bestätigt Bundle 064 mit Commit
`ee3f10f0d72159a40816b8e89fd2b64d590850d6`, sauberem Zustand und je 5.579
bestandenen parallelen und seriellen Apply-Tests. Der vollständige Snapshot
enthält 1.439 Dateien und entspricht der Entwicklungsbasis.

Neue Journale verwenden `discard-basis-v2`: Neben der expliziten Ressourcenauswahl
speichern sie die vorbereiteten Zielbytes als geschlossene, nach Pfad geordnete
Base64-Inventur. Pfade, Größen und Hashes müssen genau den Dateieinträgen entsprechen.
Die Recovery rekonstruiert unabhängig die vollständige Basiswurzel und prüft die
persistierten Zielbytes gegen die Zielwurzel. Sie führt keine neue Fachplanung aus.
Damit sind auch `building`, fehlende noch nicht geschriebene Images und eigene
kurze Before-/Staging-/Prepared-Marker nachweisbar. Fremde oder überlange Präfixe,
zusätzliche Ressourcen und widersprüchliche Nachweisdaten bleiben gesperrt.

Der explizite Neustarteinstieg prüft auch angefangene oder archivierte Discards:
Originaljournal, vollständige terminale Bindung, unveränderlicher Intent, Workinventur
und vorhandene Receipts/Abschlussbelege werden schreibfrei geprüft. Ein vollständig
gebundener `journal.discard` kann unter frischem Lock und frischer Autorisierung
übernommen werden. Discard-Hilfsdateien werden mit dem vorhandenen namenlosen
Recoverywriter vollständig gestaged, bevor sie einen Namen erhalten. Abbrüche
hinterlassen keine eigenen kurzen benannten Ableitungen. Bereits vorhandene fremde
oder unvollständige Belege werden niemals überschrieben. Eine Wiederholung erhält
den ursprünglichen Abschlussevent und schreibt keine normativen Dateien erneut.

Getrennte Writer-/Recoveryprozesse decken freigegebene und tatsächlich verwaiste
Locks, beide unveröffentlichten Zustände, native kurze Stagingwrites, 15 Grenzen
des Discardabschlusses und wiederholten Abschluss ab. Die Tests beobachten echte
native Writes und prüfen unveränderte normative Bytes, Originalbeweise und erneuten
Writerzugang. Negativfälle sichern Ressourcen, Links, Belegkonflikte, vollständige
Zielbindung, fremde Workreste, frische Autorisierung und Eigentümergrenzen.
Prepared-Journale mit `discard-basis-v1` bleiben rekonstruierbar; alte Journale ohne
Auswahl und Building-v1 ohne vollständigen Präfixnachweis werden nicht aufgewertet.
Der unabhängig gebundene historische PublicationPreflight-Weg bleibt erhalten.

Die drei Requirementmanifeste bleiben `partial`; der automatische Preflight aus
5.t, der allgemeine CLI-Adapter und die umfassende Umgebungs-/Crashmatrix werden
nicht vorgezogen. Commit-Message:
`fix(recovery): resume unpublished discard across interrupted preparation`.
Erst das passende erfolgreiche Apply-Result bestätigt den R-Abschluss.
Nächster Schritt: `AUDIT-REC-05.C`; Produktzähler unverändert 237/885.

**C-Umsetzung (Bundle 066, OFF-PLAN `AUDIT-REC-05.C`):** Result
`specroad-apply_Result_171714_1004_7b5c41.zip` bestätigt den R-Abschluss von Bundle
065 mit Commit `d79a5beb5be80bef87b70074a5f27e6b1398031a`, sauberem Zustand und
je 5.703 bestandenen parallelen/seriellen Apply-Tests. Seine 1.441 Snapshotdateien
bilden die vollständige unveränderte Ausgangsbasis dieses C-Schritts.

`_discard_inputs.py` fasst die bisherigen schreibfreien Prüfungen für archivierte
und noch nicht übernommene Discardmarker, Originaljournal und Intent sowie die
reine Projektion des Abschlussbelegs zusammen. Die vier extrahierten Funktionen
behalten ihre Prüfungen unverändert. Neustartdiagnose und mutierender Abschluss
teilen nun außerdem dieselbe Auswahl zwischen aktivem und archiviertem Workbestand
und dieselbe kanonische Inventurprüfung. Auch die initiale Intentanlage nutzt diese
Inventurprojektion. Autorisierung, frische Basis-/Lock-/Byteprüfungen, native
Schreiboperationen und deren Reihenfolge bleiben beim bisherigen Mutationspfad.

Die bestehenden 5.703 Verhaltenstests, einschließlich aller W/R-Prozessabbrüche,
bleiben unverändert. Es entsteht kein neues Fachverhalten und kein Test der
Modulstruktur oder Dokumentation. Formatversionen, Diagnosefelder, Fehlergrenzen,
zulässige Dateieffekte und Byteerhalt werden beibehalten. Die drei Requirement-
manifeste bleiben wegen der späteren CLI-/Preflight- und umfassenden Umgebungs-
integration `partial`. Commit-Message:
`refactor(recovery): share read-only discard evidence checks`.
Der erfolgreiche Apply-Commit bestätigt erst den C-Abschluss. Nächster Schritt:
`AUDIT-CONTRACT-01.W`; Produktstand 237/885 und Sperre von 5.t.W bleiben bestehen.

### AUDIT-CONTRACT-01 – aktuelle maschinenlesbare Selbstbeschreibung

**F05; Voraussetzung:** Recovery-Nacharbeiten entschieden und bestätigte Lücken behoben. **Bezug:** 1.i/1.n/2.q; SR-REQ-0194/0376/0392; SR-VER-0013/0027; zugehörige SR-TC-Manifeste. Betroffen: `_metadata.py`, `runtime/identity.py`, `cli/capabilities.py`, `model/versions.py`; `test_identity.py`, `test_capabilities.py`.

- [x] **AUDIT-CONTRACT-01.W:** Die bereits verfügbare Schemaunterstützung korrekt in Version-/Capabilities-Verträgen veröffentlichen. **Abnahme:** Vorhandene Artefaktschemas werden nicht mehr als leere Schemaunterstützung beschrieben; Testoracles prüfen den real implementierten Umfang.
- [x] **AUDIT-CONTRACT-01.R:** Die Reichweite von Bibliotheksfähigkeit, abrufbarem Schema und ausführbarem CLI-Befehl aus den bestehenden Verträgen bestimmen, insbesondere für SRX. **Abnahme:** Alle Angaben widerspruchsfrei; keine Werbung für noch nicht verfügbare Produktbefehle. Erforderliche Korrekturen bleiben innerhalb vorhandener Fähigkeiten; die Agentenintegration 18.m wird nicht vorgezogen.
- [x] **AUDIT-CONTRACT-01.C:** Quellen der Versions-/Fähigkeitsangaben konsolidieren. **Abnahme:** Dieselben fachlichen Listen, Werte und Ablehnungsgrenzen wie nach R, ohne neue Abhängigkeit des portablen Core.

**W-Umsetzung (Bundle 067, OFF-PLAN `AUDIT-CONTRACT-01.W`):** Das Result
`specroad-apply_Result_181602_1004_102394.zip` bestätigt den C-Abschluss von Bundle
066 mit Commit `2074a970a03281819435430dd4e6fe99a516654e`, sauberem Zustand und
je 5.703 bestandenen parallelen/seriellen Apply-Tests. Sämtliche 1.442 Dateien
dieses Snapshots stimmen vor der Änderung bytegenau mit der Entwicklung überein.

Die bisher leere Modell-Schemaliste in `_metadata.py` nennt nun die bereits
implementierte Version `0.2.0`. `version` und `capabilities` veröffentlichen
diese Angabe über ihre vorhandene gemeinsame Versionsabfrage. Die Aussage
betrifft das Core-Modellschema; separat versionierte Request-/Ergebnisformate
sind keine zusätzlichen Modellversionen. Alte Oracles für eine leere
Schemaunterstützung werden durch den tatsächlich implementierten Umfang ersetzt.

Zwei zusätzliche Verhaltenstests gleichen die Angabe mit der Annahme aller 28
Common-Artefakttypen und der Projektkonfiguration sowie mit `schema list/show`
für alle vorhandenen Artefakt-/Konfigurationsschemas ab. Bestehende Tests prüfen
die Angabe zusätzlich in isolierten Modul-/Zipapp-Distributionen und ihren
Erhalt nach Manipulation eines vorher zurückgegebenen Ergebnisobjekts. Die
Requirementmanifeste SR-TC-0194 und SR-TC-0376 binden diesen Teilumfang und bleiben
`partial`. SRX-/Proposal-Reichweite und die spätere vollständige Integration
werden dadurch nicht als abgeschlossen behauptet.

Commit-Message: `fix(core): advertise implemented model schema support`.
Erst das passende erfolgreiche Apply-Result bestätigt diesen W-Abschluss.
Nächster Schritt: `AUDIT-CONTRACT-01.R`; Produktzähler 237/885 und Sperre von
5.t.W bleiben unverändert.

**R-Umsetzung (Bundle 068, OFF-PLAN `AUDIT-CONTRACT-01.R`):** Das Result
`specroad-apply_Result_185856_1004_b69b90.zip` bestätigt Bundle 067 mit Commit
`891e7ffbb80fd524444f81600881c9f91692db44`, sauberem Zustand und je 5.705
bestandenen parallelen/seriellen Apply-Tests. Die 1.442 Snapshotdateien bilden
die bytegenau abgeglichene Ausgangsbasis.

Die Reichweite ergibt sich aus §9.9, SR-REQ-0194/0376/0392 sowie den bereits
abgenommenen Bibliothekskernen 4.a–4.i und der Registrygrenze aus 1.n. SRX 1.0
ist über `specroad.srx` ausführbar und wird nun als Sprachversion `1.0` mit der
Capability `python.srx.evaluate` ausgewiesen. Eine leere SRX-Liste wäre für
diese bestehende Bibliotheksfähigkeit falsch. Die CLI-Angaben bleiben dagegen
exakt aus der aktiven Befehlsregistry abgeleitet. Weder ein SRX-Fachbefehl noch
`query`, `validate` oder ein Proposalbefehl werden dadurch registriert.

[Die technische Selbstbeschreibungsgrenze](../../development/Self_Description.md)
unterscheidet außerdem Modellschema `0.2.0`, separat versionierte Request-/
Ergebnisverträge, vorhandene JSON-/SARIF-Serializer, aktivierte CLI-Formate und
Schema-IDs. Das verfügbare Proposal-Recordschema ist ein lokaler Feldvertrag;
die vollständige versionierte Proposalverarbeitung und 18.m bleiben offen.
SRX-Bibliotheksfähigkeit erzeugt keinen erfundenen eigenständigen Schemaeintrag.
Die bereits vorhandenen öffentlichen APIs und ihre Fehlergrenzen bleiben erhalten.

Neun zusätzliche Verhaltenstests binden die SRX-Angabe an reale programmatische
und Raw-JSON-Auswertung, Ablehnung nicht unterstützter Versionen, fehlende CLI-/
Requestbefehle, genaue Schema-Lookups, das Proposal-Recordschema und die getrennten
Serializer-/CLI-Verträge. Isolierte Modul- und Zipapp-Prozesse führen die
beworbene SRX-Bibliothek ohne Drittanbieterpakete und ohne Projektänderung aus.
Bestehende Tests sichern zusätzlich unabhängige zurückgegebene Listen und die
projektfreie deterministische Abfrage. Es gibt keine Tests auf Dokumentation
oder Konsolenwortlaut. SR-TC-0194/0376 bleiben mit diesen Nachweisen `partial`.

Commit-Message: `fix(core): distinguish SRX library support from CLI capabilities`.
Erst das passende erfolgreiche Apply-Result bestätigt den R-Abschluss.
Nächster Schritt: `AUDIT-CONTRACT-01.C`; Produktzähler 237/885 und Sperre von
5.t.W bleiben unverändert.

**C-Umsetzung (Bundle 069, OFF-PLAN `AUDIT-CONTRACT-01.C`):** Das Result
`specroad-apply_Result_194140_1004_39a4e9.zip` bestätigt Bundle 068 mit Commit
`8fd56dcd8a60bfbc8c55b873447cf0b762b2dbec`, sauberem Zustand und je 5.714
bestandenen parallelen/seriellen Apply-Tests. Die 1.444 Snapshotdateien sind
vor dem C-Delta bytegenau mit der Entwicklung abgeglichen.

Die reinen Konstanten für Modellschema und SRX-Sprache liegen nun gemeinsam
in `_metadata.py`. Unterstützungslisten und bestehende Validatoren beziehen
sich auf dieselben Werte: `model.versions.SCHEMA_VERSION` bleibt als Fassade
erhalten, der SRX-Parser verwendet die gemeinsame Sprachversion für Annahme
und Fehlervertrag, das View-Filterschema für seine unveränderte `const`-Angabe.
Auch die vorhandenen Python-Capability-IDs sind dort einmal deklariert. Die
CLI-Liste wird weiterhin aus der aktuellen Registry gebildet.

Das Modul enthält ausschließlich statische Daten und benötigt weder den
SRX-Evaluator noch Modellimporte, Buildwerkzeuge oder zusätzliche Corepakete.
Die fachlichen Versionen, Listen, Schemaobjekte, Ablehnungsgrenzen und erlaubten
Seiteneffekte bleiben exakt wie nach R. Die 5.714 bestehenden Verhaltenstests
werden unverändert übernommen; es entstehen keine neuen Struktur- oder
Dokumentationstests. Der offene C-Vermerk in SR-TC-0376 entfällt; der Status
bleibt wegen späterer Workflow-/Releaseintegration `partial`.

Commit-Message: `refactor(core): share model and SRX version identities`.
Erst das erfolgreiche Apply-Result bestätigt den C-Abschluss. Nächster Schritt:
`AUDIT-CONTRACT-02.W`; Produktzähler 237/885 und Sperre von 5.t.W bleiben bestehen.

### AUDIT-CONTRACT-02 – vorhandenes Change-Plan-Schema im Katalog

**F06; Voraussetzung:** AUDIT-CONTRACT-01. **Bezug:** 2.q/5.a; SR-REQ-0377/0378; SR-VER-0027; SR-TC-0377/0378. Betroffen: `changes/schema.py`, `changes/plan_contract.py`, `model/schema_sources.py`, `schema_identity.py`, `schema_catalog.py`; `test_schema_catalog.py`.

- [x] **AUDIT-CONTRACT-02.W:** Das tatsächlich verwendete `urn:specroad:schema:1.2.0:change-plan` über den bestehenden Schemakatalog anbieten. **Abnahme:** Listing und Lookup liefern den vom Change-Plan-Validator verwendeten strukturellen Vertrag.
- [x] **AUDIT-CONTRACT-02.R:** Kennungs-/Versionsbehandlung, unabhängige zurückgegebene Schemaobjekte und alle inzwischen verfügbaren öffentlichen strukturellen Schemas abgleichen. **Abnahme:** Unbekannte Kennungen bleiben Fehler; keine veraltete oder nur deklarierte Schemafamilie wird als implementiert ausgegeben.
- [x] **AUDIT-CONTRACT-02.C:** Katalogintegration und Schemaidentitäten strukturell bereinigen. **Abnahme:** Stabile Kennungen, Listeninhalte, validierte Daten und Fehlerverträge bleiben erhalten.

**W-Umsetzung (Bundle 070, OFF-PLAN `AUDIT-CONTRACT-02.W`):** Das Result
`specroad-apply_Result_204811_1004_642827.zip` bestätigt den C-Abschluss von Bundle
069 mit Commit `7468a78a696b5a9a0b248dcf9e0acd813dfcf968`, sauberem Zustand und
je 5.714 bestandenen parallelen/seriellen Apply-Tests. Seine 1.444 Snapshotdateien
stimmen vor dieser Änderung bytegenau mit der Entwicklung überein.

Der bestehende Schemakatalog registriert nun die tatsächlich implementierte
Kennung `urn:specroad:schema:1.2.0:change-plan` als `exchange` mit dem expliziten
Prüfumfang `change_plan_fields_only`. Der Provider ruft dieselbe
`change_plan_schema()`-Funktion auf, die der Change-Plan-Validator verwendet;
Schemafelder und fachliche Planvalidierung werden nicht dupliziert oder geändert.
`schema list`, `schema show` und strukturierter Schemaabruf liefern den echten
vollständigen Feldvertrag einschließlich seiner Metadaten und Hashbindung.

Vier zusätzliche Verhaltenstests prüfen den eindeutigen Katalogeintrag, CLI-/
Requestgleichheit, einen tatsächlich vorbereiteten Change Plan und abgewiesene
Format-/Policy-/Operations-/Actorwerte. Ein absichtlich veränderter Plan-Selbsthash
zeigt weiterhin die Grenze: Das Feldschema ersetzt keine Integritätsprüfung
oder Ausführungsberechtigung. Der bestehende portable Test ruft das Schema
zusätzlich in isolierten Modul- und Zipapp-Distributionen ab und prüft Byteerhalt.
SR-TC-0377/0378 verknüpfen die echten Fixtures und Tests; sie bleiben `partial`.

Commit-Message: `fix(model): expose the existing change plan schema in the catalog`.
Erst das erfolgreiche Apply-Result bestätigt diesen W-Abschluss. Nächster Schritt:
`AUDIT-CONTRACT-02.R`; Produktstand 237/885 und Sperre von 5.t.W bleiben bestehen.

**R-Abnahme (Bundle 071, OFF-PLAN `AUDIT-CONTRACT-02.R`):** Das Result
`specroad-apply_Result_214108_1004_04063c.zip` bestätigt Bundle 070 mit Commit
`2977923276e2b281e652ee5575c22be8274c891f`, sauberem Zustand und je 5.718
bestandenen parallelen/seriellen Apply-Tests. Alle 1.444 Snapshotdateien stimmen
vor dieser Änderung bytegenau mit dem Entwicklungsstand überein.

Die Inventur aller vorhandenen eigenständigen öffentlichen Schema-Fabriken
bestätigt die Katalogvollständigkeit nach W. Sie umfasst die gemeinsamen,
Domänen- und Record-Artefaktschemas, Projektkonfiguration, Change Plan, sämtliche
aktuellen Request-/Ergebnisschemas und die lokale SARIF-Projektion. Eingebettete
Operations-, Diagnose-, Policy- und Feldschemas besitzen keine eigene veröffentlichte
Ressourcenkennung; ihre bestehenden Verträge werden über die vollständigen
übergeordneten Schemas angeboten. Reine Parser-/Lifecycle-Verträge werden nicht
in erfundene JSON-Schema-Ressourcen umgedeutet.

Neun zusätzliche Verhaltenstests in `tests/test_schema_catalog_change_plan.py`
prüfen die vollständige Ressourcenmenge gegen die tatsächlichen Fabriken,
Kennungs-/Versionsgrenzen, unveränderte Fehlerverträge, isolierte tiefe
Rückgabeobjekte, Metadaten-/Referenzbindung, alle zwölf Operationsvarianten und
den Abruf bei leerer CLI-Registry. Der bestehende Prozess-Audit-Hook sichert
zusätzlich den Change-Plan-Abruf ohne Projekt-, Netzwerk- oder Schreibzugriff ab.
Die Produktimplementierung besteht diese Abnahmen bereits; R erweitert daher
die fachlichen Regressionsnachweise, ohne Ressourcen oder Laufzeitverhalten zu
ändern. SR-TC-0377/0378 referenzieren die neuen Nachweise und bleiben `partial`.

Commit-Message: `test(model): harden catalog identity and isolation coverage`.
Erst das erfolgreiche Apply-Result bestätigt diesen R-Abschluss. Nächster Schritt:
`AUDIT-CONTRACT-02.C`; Produktstand 237/885 und Sperre von 5.t.W bleiben bestehen.

**C-Umsetzung (Bundle 072, OFF-PLAN `AUDIT-CONTRACT-02.C`):** Das Result
`specroad-apply_Result_222356_1004_4cafee.zip` bestätigt den R-Abschluss mit Commit
`cd6216d45a24f3ae01bc0cb33ff4094e9cc6ad33`, sauberem Zustand und je 5.727
bestandenen parallelen/seriellen Apply-Tests. Alle 1.445 Snapshotdateien stimmen
vor dieser Änderung bytegenau mit dem Entwicklungsstand überein.

Die bestehende `model/schema_identity.py` hält nun die gemeinsame Change-Plan-
Formatversion, Familie, daraus zusammengesetzte Ressourcenkennung und den
Prüfumfang. Schema-Fabrik, Ressourcenmetadaten und Provider verwenden diese
Identität. Die bisherigen öffentlichen Namen `changes.schema.FORMAT_VERSION`
und `SCHEMA_ID` bleiben als Importe mit identischen Werten verfügbar. Die
Providerinventur benötigt für diese reinen Identitätsdaten keinen Import des
Change-Plan-Pakets; die reale Schema-Fabrik wird weiterhin erst beim Abruf geladen.

Alle veröffentlichten Schemawerte, Katalogeinträge, Hashbindungen, Fehlerverträge
und Annahme-/Ablehnungsgrenzen bleiben erhalten. W-/R-Verhaltenstests werden
unverändert übernommen; es entstehen keine Struktur- oder Dokumentationstests.
SR-TC-0377/0378 behalten ihren tatsächlichen Teilumfang und Status `partial`.

Commit-Message: `refactor(model): share change plan schema identity`.
Erst das erfolgreiche Apply-Result bestätigt diesen C-Abschluss. Danach folgt
`AUDIT-VALIDATION-01.U`; der Produktzähler bleibt 237/885, und 5.t.W bleibt bis
`AUDIT-CLOSE` gesperrt.

### AUDIT-VALIDATION-01 bis 03 – fällige M4-Abdeckung konkret entscheiden

**Voraussetzung:** AUDIT-CONTRACT-02. Die vorhandenen Kerne und ihre ehrlichen `unavailable`-/Teilumfangsresultate bleiben Ausgangsbasis. Fehlende zukünftige CLI-, Baseline-, Dokument-, Konfigurations- oder Evidencefunktionen werden nicht pauschal zum Fehler eines abgeschlossenen Grundlagenkerns erklärt.

- [x] **AUDIT-VALIDATION-01.U / F07:** SR-REQ-0096, SR-VER-0007, SR-TC-0096 gegen 4.l/4.o/4.r verfolgen. `lint/core.py` und `storage/read_only.py` bieten bisher vor allem Literalprüfungen. **Entscheidung:** Für fehlende Begründung, Verifikation und Mindestbeziehungen jeweils tatsächlichen Diagnosepfad, positive/negative Verhaltensnachweise und ursprüngliche Abnahme bestimmen. Ein bestehender Approval-/Relationskern allein beweist den Lintpfad nicht. Bereits geschuldete fehlende Core-Lintdiagnosen zur Korrektur eintragen; echte spätere Integration mit konkreter offener Position belegen.
- [x] **AUDIT-VALIDATION-02.U / F08:** SR-REQ-0086/0100, SR-VER-0007, SR-TC-0086/0100 gegen 4.o–4.r und 5.f/5.g verfolgen. Ein reales Requirementprojekt mit ausgeliefertem Softwareprofil durch die vorhandenen öffentlichen Bibliotheksgrenzen prüfen. **Entscheidung:** Tatsächliche Adapter für Sprachpolicy, Profil-SRX, Approval und Diagnoseauswertung von vertrauenswürdigen Testgates unterscheiden. `test_model_validation.py` und `test_read_only_validation.py` belegen bisher auch Nichtverfügbarkeit. Für jede fehlende Verbindung festhalten, ob sie bereits fällig oder konkret später vorgesehen ist; keine Vollvalidierung allein aus injizierten immer erfolgreichen Gates ableiten.
- [x] **AUDIT-VALIDATION-03.U / Diagnoseaggregation:** 4.p.R und die dort zugeordneten SR-REQ-0087–0092/0098–0099 samt SR-TC-Manifeste und SR-VER-0007 prüfen. `graph/references.py` und `validation/core.py` beenden bei fehlendem Relationsziel den betreffenden Pfad. **Entscheidung:** Verlangt die bestehende Abnahme mehrere unabhängig fehlende Ziele gemeinsam, oder setzt sie einen erfolgreichen Strukturabschnitt voraus? Mehrere konkrete gleichzeitige Fehler und die strukturierte Diagnosemenge vergleichen; kein bloßes Fortsetzungsversprechen ohne Vertrag ergänzen.

**Nur für bestätigte, bereits geschuldete Lücken** konkrete `AUDIT-VALIDATION-01/02/03.W/R/C` eintragen: W liefert den kleinsten nutzbaren fehlenden Diagnose-/Adapterpfad; R vervollständigt dessen Negativ-, Mehrfachfehler-, Frische- und Ressourcenbindungen; C konsolidiert vorhandene Kerne. **Gemeinsame Abnahme:** Echte Daten ergeben die verlangten strukturierten Befunde; fehlende Voraussetzungen werden weiter ehrlich ausgewiesen, Lesen bleibt schreibfrei, bereits bestehende fachliche Grenzen werden nicht abgeschwächt. Keine vorgezogene vollständige CLI- oder spätere Produktintegration.

**U-Ergebnis zu F07 (Bundle 073, OFF-PLAN `AUDIT-VALIDATION-01.U`): bestätigt.**
[Untersuchungsbericht](../../reviews/SpecRoad_AUDIT_VALIDATION_01_U.md),
[paralleles Reproduktionsprogramm](../../reviews/SpecRoad_AUDIT_VALIDATION_01_U_probe.py)
und [gebundene Beobachtungen](../../reviews/SpecRoad_AUDIT_VALIDATION_01_U_observations.json)
beziehen sich auf Result `specroad-apply_Result_230658_1004_9dff6c.zip`, Commit
`ee91f34df4bee63ea983680afa5412e601ba8185`. Dieses Result bestätigt Bundle 072
mit sauberem Zustand und je 5.727 erfolgreichen parallelen/seriellen Apply-Tests.
Alle 1.445 Snapshotdateien stimmen vor der Untersuchung mit der Entwicklung überein.

Acht parallel ausgeführte Fälle zeigen: Der öffentliche Lintpfad diagnostiziert
fehlende Begründung, Verifikation und Herkunftsrelation nicht, auch mit `strict`.
Bestehende Feld-/Relationsprüfungen erkennen diese Fehler; vollständige Minima,
Literalplatzhalter und konfigurierte Glossarverstöße bilden die Gegenproben.
Alle Projektbytes und Modi bleiben erhalten, kein Schreibversuch wird beobachtet.
Der vorhandene Lintumfang bleibt ehrlich `selected_literal_fields_only`; die
Lücke ist keine behauptete Vollfreigabe. Die Requirementmatrix ordnet SR-REQ-0096
bereits 4.l ohne spätere Sekundärposition zu. Seine nichtliteralen Anteile bleiben
fällig und erhalten die folgenden konkreten Korrekturen.

- [x] **AUDIT-VALIDATION-01.W:** Fehlende Begründung sowie fehlende Verifikation,
  Herkunfts- und sonstige anwendbare Mindestbeziehungen über den öffentlichen
  Core-/Read-only-Lintpfad diagnostizieren. Bestehende Feld-/Relationsregeln mit
  ihren Reife-/Profilgrenzen wiederverwenden. **Abnahme:** Die bestätigten
  Negativfälle liefern getrennte maschinenlesbare Befunde; vollständige positive
  Eingaben bleiben befundfrei; bestehende Literaldiagnosen bleiben erhalten.
- [x] **AUDIT-VALIDATION-01.R:** Gleichzeitige Fehler, eingehende/ausgehende
  Profilminima, Teilselektion, fehlende Zielressourcen, Reifegrenzen, unverfügbare
  Voraussetzungen und Änderungen während des Lesens einbeziehen. **Abnahme:**
  Vollständige Diagnosemenge und Code-/Pointer-/Artefaktbindung, konsistente
  Fail-Policy und ehrlicher Prüfumfang; unveränderte Projektbytes und keine
  neue Freigabe- oder Sprachverständnisbehauptung.
- [x] **AUDIT-VALIDATION-01.C:** Gemeinsame Feld-/Relationsbeobachtung und
  Diagnoseprojektion konsolidieren. **Abnahme:** W-/R-Ergebnisse, Fehlerverträge,
  anwendbare Regeln und schreibfreie Wirkung bleiben erhalten.

Diese Korrekturen beginnen erst nach den Untersuchungen
`AUDIT-VALIDATION-02.U` und `AUDIT-VALIDATION-03.U`. Bundle 073 verändert
keine Produktquelle, Regressionsprüfung oder Requirementbewertung. Nicht
registrierte Fachgates bleiben sichtbar unverfügbar; ihr Integrationsbefund wird
nicht durch die funktionierende Relationsstufe vorweggenommen.

Commit-Message: `docs(validation): record missing nonliteral lint diagnostics`.
Erst das erfolgreiche Apply-Result bestätigt den U-Commit. Die damalige Folgeposition
ist `AUDIT-VALIDATION-02.U`; Produktstand 237/885 und Sperre von 5.t.W bleiben erhalten.

**U-Ergebnis zu F08 (Bundle 074, OFF-PLAN `AUDIT-VALIDATION-02.U`): bestätigt und eingegrenzt.**
[Untersuchungsbericht](../../reviews/SpecRoad_AUDIT_VALIDATION_02_U.md),
[paralleles Reproduktionsprogramm](../../reviews/SpecRoad_AUDIT_VALIDATION_02_U_probe.py)
und [gebundene Beobachtungen](../../reviews/SpecRoad_AUDIT_VALIDATION_02_U_observations.json)
beziehen sich auf Result `specroad-apply_Result_235051_1004_72af87.zip`, Commit
`b669fe16663eb88b48543cb55288cbecf494040d`. Dieses Result bestätigt Bundle 073
mit sauberem Zustand und je 5.727 erfolgreichen parallelen/seriellen Apply-Tests.
Alle 1.448 Snapshotdateien stimmen vor der Untersuchung mit der Entwicklung überein.

Zwölf parallele Fälle lesen echte temporäre Projekte mit den ausgelieferten
Core-/Softwareprofilen und ausdrücklich gebundenem Offline-Sprachregister.
Schon gültige Draft-Requirements bleiben wegen unverfügbarer Sprach- und
Profil-SRX-Gates unvollständig. Einzelprüfer liefern echte Sprachpolicybefunde
und SRX-Ergebnisse; vorhandene formale Approvalbefunde zu Platzhaltern und
Verification-Subjects erreichen die gemeinsame Pipeline ebenfalls nicht.
Dagegen sind Schema, Profilfelder, Mindestbeziehungen und Diagnoseauswertung
bereits angeschlossen. Zielprüfung und Dry-Run stimmen in allen elf strukturell
geeigneten Fällen überein; ein fehlendes Statement verhindert schon die Planung.
Kein Projektwrite wird versucht, alle Bytes und Modi bleiben erhalten.

Die M4-Adapter sind im vorhandenen fachlichen Umfang bereits fällig. Echte
menschliche Review-/Historyvoraussetzungen bleiben erforderlich und dürfen nicht
synthetisch bestehen. Vollständiges Lifecycleauthoring bleibt 7.f, Relationsreview
7.g/7.h/7.j, Baselineintegration 10.d.C und Evidenceintegration 12.t.W zugeordnet.
Die tatsächliche Schreibfreiheit von SR-REQ-0100 wird durch diesen Befund nicht
widerlegt. Fehlende oder spätere Fachdienste sind weiter ehrlich unverfügbar.

- [x] **AUDIT-VALIDATION-02.W:** Vorhandene Sprachpolicy- und Profil-SRX-Prüfer
  über produktive, an echte Konfiguration und Ressourcen gebundene Adapter an
  Modell-, Read-only- und Zielvalidierung anschließen; vorhandene formale
  Approvalbefunde in deren gemeinsame Diagnosemenge übernehmen. **Abnahme:**
  Ein geeigneter gültiger Draftfall mit ausgeliefertem Softwareprofil besteht
  ohne immer erfolgreiche Testgates; unzulässige Sprache, falsche Profilregel
  und bereits prüfbarer Approvalfehler werden fachlich diagnostiziert. Fehlende
  menschliche Reviews, Evidence oder Historie bleiben sichtbar unverfügbar;
  formale Befunde verleihen keine Freigabe- oder Schreibberechtigung.
- [x] **AUDIT-VALIDATION-02.R:** Dieselben Adapter um Regelanwendbarkeit,
  abhängige Teilselektion, gleichzeitige Befunde, Severity-/Strict-Entscheidungen,
  ungültige oder fehlende Ressourcen und Änderungen während der Prüfung
  vervollständigen. **Abnahme:** Keine veraltete oder fremde Profil-, Register-,
  Konfigurations-, Artefakt- oder Reviewbeobachtung wird wiederverwendet;
  Projektprüfung, Zielprüfung und Dry-Run erhalten dieselben fachlichen
  Ergebnisse, erforderlichen Abhängigkeiten und ehrlichen Reichweitengrenzen.
  Kein neuer Persistenzvertrag, impliziter Reviewer oder optionaler Analyzer.
- [x] **AUDIT-VALIDATION-02.C:** Gemeinsame Ressourcenbindung, Fachbeobachtung
  und Diagnoseprojektion konsolidieren. **Abnahme:** Alle W-/R-Ergebnisse,
  Fehlerverträge und schreibfreien Wirkungen bleiben unverändert; vorhandene
  Kerne werden wiederverwendet und spätere Fachgates nicht durch Stubs ersetzt.

Diese Korrekturen beginnen nach `AUDIT-VALIDATION-03.U` und den zuvor angeordneten
Korrekturen aus `AUDIT-VALIDATION-01`. Dieses U-Bundle verändert keine
Produktquelle, Regressionsprüfung oder Requirementbewertung. Die konkrete
Mehrfachfehlerfrage aus 4.p.R bleibt Gegenstand von U03.

Commit-Message: `docs(validation): record missing production gate adapters`.
Erst das erfolgreiche Apply-Result bestätigt den U-Commit. Die damalige Folgeposition
ist `AUDIT-VALIDATION-03.U`; Produktstand 237/885 und Sperre von 5.t.W bleiben erhalten.

**U-Ergebnis zur Diagnoseaggregation (Bundle 075, OFF-PLAN `AUDIT-VALIDATION-03.U`): begrenzte Lücke bestätigt.**
[Untersuchungsbericht](../../reviews/SpecRoad_AUDIT_VALIDATION_03_U.md),
[paralleles Reproduktionsprogramm](../../reviews/SpecRoad_AUDIT_VALIDATION_03_U_probe.py)
und [gebundene Beobachtungen](../../reviews/SpecRoad_AUDIT_VALIDATION_03_U_observations.json)
beziehen sich auf Result `specroad-apply_Result_004435_1005_821734.zip`, Commit
`06d514f4f413e3bb595b911be51a2fc06e4be947`. Dieses Result bestätigt Bundle 074
mit sauberem Zustand und je 5.727 erfolgreichen parallelen/seriellen Apply-Tests.
Alle 1.451 Snapshotdateien stimmen vor der Untersuchung mit der Entwicklung überein.

Zwölf parallele Fälle zeigen: Fehlende Ziele mehrerer Relationen oder
Interfacefelder werden bei vollständig lesbaren, strukturell gültigen und
eindeutig identifizierbaren Quellen nur bis zur ersten Fundstelle ermittelt.
Eine unabhängige typwidrige Relation bleibt hinter dem ersten fehlenden Ziel
verborgen; isoliert liefert sie tatsächlich SRV021. Der vorhandene Aggregator
erhält zwei tatsächlich gelieferte SRV020-Befunde dagegen vollständig.
Parse-/Schemafehler aus mehreren Dateien und mehrere unbekannte Auswahl-IDs
werden bereits gemeinsam gemeldet. Ein geschlossener Graph mit sieben
Artefakten besteht. Direkte und öffentliche Projektbewertung sowie umgekehrte
Dokumentreihenfolge liefern jeweils identische Assessments. Alle Projektbytes
und Modi bleiben erhalten, ohne versuchten Write.

4.p.R verlangt bereits vollständige gleichzeitige Befunde und Abnahme ihrer
Mengen. Die Korrektur betrifft die Ermittlung unabhängiger Referenzbefunde,
nicht einen anderen Summaryzähler oder unbeschränktes Weiterrechnen nach
kaputten Eingaben. Ein unlesbarer möglicher Zielbestand bleibt eine gesperrte
Voraussetzung, kein bewiesenes fehlendes Ziel. Die SR-TC-Manifeste 0087–0092
und 0098–0099 bleiben unverändert partial; ihr bestehender Diagnosekern wird
nicht durch eine vollständige Produktabnahme ersetzt.

- [x] **AUDIT-VALIDATION-03.W:** Alle unabhängig fehlenden Relations- und
  bekannten Feldziele einer strukturell gültigen, eindeutig indexierbaren
  Eingabemenge vor dem Abbruch der Referenzstufe sammeln. **Abnahme:** Zwei
  Quellen, zwei Kanten derselben Quelle und beide Componentfelder eines
  Interfaces liefern alle Fundstellen mit bestehendem Code, Artefakt, Datei
  und Pointer. Graph-/Fachstufen bleiben gesperrt; kein ungültiger Teilgraph
  wird als aufgelöster gültiger Relationswert angeboten.
- [x] **AUDIT-VALIDATION-03.R:** Gemischte fehlende/typwidrige Ziele,
  Identitätskonflikte, mehrere Fundstellen desselben fehlenden Ziels,
  Relations-/Feldkombinationen und Auswahlgrenzen vervollständigen. **Abnahme:**
  Deterministische vollständige Mengen sicher bewertbarer Befunde ohne
  erfundene Zielidentitäten; gleiche öffentliche Projekt-/Zielbewertung,
  stabile Codes und Orte, passende Summary und Code 3. Unlesbare, schemawidrige
  oder mehrdeutige Eingaben behalten ihre erforderlichen Abbruchgrenzen;
  Lesen bleibt schreibfrei und erzeugt keine Freigabe.
- [x] **AUDIT-VALIDATION-03.C:** Referenzbeobachtung, Fehlerprojektion und strikte
  Graphkonstruktion ohne doppelte Fachregeln strukturieren. **Abnahme:** W-/R-
  Diagnosemengen, Reihenfolge, Fehlerverträge und erlaubte Wirkungen bleiben
  gleich; eine gescheiterte Referenzprüfung erzeugt weiterhin keinen gültigen
  Gesamtgraphen.

Alle drei U-Untersuchungen sind damit fachlich ausgewertet. Nach erfolgreichem
Apply dieses Bundles folgen in der bestehenden Reihenfolge
`AUDIT-VALIDATION-01.W/R/C`, `AUDIT-VALIDATION-02.W/R/C` und
`AUDIT-VALIDATION-03.W/R/C`. Die Untersuchungen implementieren keine dieser
Reparaturen und verändern keine Produktquelle oder Regressionsprüfung.

Commit-Message: `docs(validation): record incomplete reference diagnostic sets`.
Erst das erfolgreiche Apply-Result bestätigt den U-Commit. Nächster Schritt ist
`AUDIT-VALIDATION-01.W`; Produktstand 237/885 und Sperre von 5.t.W bleiben erhalten.

### AUDIT-VALIDATION-01.W – fehlende Core-Lintdiagnosen (Bundle 076)

Basis ist das vollständig geprüfte erfolgreiche Result
`specroad-apply_Result_012756_1005_eb54a4.zip`, Commit
`804cdedf915805db3d14e9788dca2957d71a0a48`. Es bestätigt den vorherigen
Untersuchungszustand mit 5727 parallelen und 5727 seriellen Apply-Tests.
Die drei U-Untersuchungen sind damit durch ihre tatsächlichen Apply-Results
bestätigt; die historischen Beobachtungen bleiben unverändert.

Der öffentliche `lint_core` beobachtet jetzt die bestehenden Begründungsregeln
für approved Requirement/Need sowie Core- und explizit komponierte
Profil-Relationsminima. Er verwendet dieselben reifeabhängigen Pflichtfelder
und Feldschemas wie die Domainprüfung und dieselben `RelationObligations` wie
der Relationskern. Fehlende beziehungsweise ungültige Begründungen erhalten
SRV002 am Pointer `/rationale`, fehlende Herkunft SRV031, fehlende Verifikation
SRV032 und Profilminima SRV023 an `/relations`, jeweils mit Artefakt-/Pfadbindung.
Relationsbefunde enthalten Regelkennung, tatsächliche Anzahl und Minimum.
Die eigentliche Domain-Schemaausgabe wird durch die geteilte Pflichtfeldtabelle
nicht geändert.

`lint_project_read_only` verbindet diese Beobachtungen mit seinen unveränderten
Literalberichten und der bestehenden abschließenden Frischekontrolle.
Aktivierte Profile benötigen explizite Ressourcen; fehlende Ressourcen oder
nicht auflösbare Referenzen können keinen erfolgreichen Gesamtbefund ergeben.
Gebundene vollständige positive Eingaben bleiben befundfrei, Draft erbt keine
approved-Pflichten, und gleichzeitige Literalbefunde gehen nicht verloren.
Vierzehn neue Verhaltensfälle sichern den W-Umfang über die öffentlichen APIs
mit echten Profilen und Schreibversuchssperren ab. SR-TC-0096 und sein neuer
Fixturebezug beschreiben genau diesen Umfang und bleiben `partial`.

Die Core-Minima sind keine Prüfung aktueller Relationsreviews oder vollständiger
Verifikationsverträge; ebenso wenig wird aus dieser Beobachtung eine Freigabe,
ein vollständiger Schema-/Profilnachweis oder Sprachverständnis abgeleitet.
Die bereits vorhandene Unvollständigkeit bei nicht anwendbarer Literalpolicy
bleibt sichtbar. Vollständige Mehrfach-/Randfall-, Selektions-, Ressourcen- und
Frischeabnahmen folgen in R, die Konsolidierung in C. Die Adapterkorrekturen aus
AUDIT-VALIDATION-02 und die Referenz-Diagnoseaggregation aus AUDIT-VALIDATION-03
werden durch diesen W-Zustand nicht als erledigt verbucht.

Commit-Message: `fix(lint): report missing rationale and relation minima`.
Erst das erfolgreiche Apply-Result bestätigt diesen W-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-01.R`; Produktzähler 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-VALIDATION-01.R – Diagnoseumfang und Lesebindung (Bundle 077)

Basis ist das vollständig geprüfte erfolgreiche Result
`specroad-apply_Result_022149_1005_95d2e5.zip`, Commit
`60bcd2e75b2cb44c559568a6aa28f3141026ade9`. Die 1457 Snapshot-Dateien stimmen
mit dem W-Stand überein. Jeweils 5741 parallele und serielle Apply-Tests
bestätigen dessen tatsächlichen Commit.

Der Core-Lintstatus beachtet nun denselben Fail-Schwellwert wie der Projektleser;
Warnungen bleiben Warnungen, auch wenn `strict` oder `fail_on=warning` sie zum
Fehlschlag machen. Intrinsische Core-Fehler können durch Profilüberschreibungen
nicht abgesenkt werden. Pflicht und Inhalt von `rationale` kommen aus den
vorhandenen Domain-/Record-Schemas: fehlende optionale Felder werden nicht zu
Pflichtfeldern; vorhandene optionale Werte werden trotzdem geprüft, und die
unbedingten Decision-/Proposal-Pflichten gelten schon vor `approved`.
Ungültige beziehungsweise doppelte Quelllabels und falsche Selektionsargumente
liefern kontrollierte Fehler.

Fehlende deklarierte Sprache oder ausdrücklich ausgewählte, aber nicht geladene
Glossarbegriffe lassen sichere Core-Befunde im Read-only-Bericht sichtbar. Die
Literalvoraussetzung bleibt artefakt-/pfadgebunden unter `unavailable` und die
Gesamtprüfung unvollständig mit Code 5. Bekannte Fachfehler behalten dabei
`passed=false`; ohne solche Befunde bleibt das Ergebnis unentschieden. Eine
nicht anwendbare Literalprüfung wird ebenfalls nicht als bestanden ausgegeben.
Andere ungültige strukturelle Eingaben, insbesondere defekte Zielreferenzen,
stoppen weiterhin vor einem abgeschlossenen Lintbericht. Die separate vollständige
Referenz-Diagnoseaggregation bleibt AUDIT-VALIDATION-03 zugeordnet.

32 zusätzliche Verhaltensfälle prüfen vollständige unabhängige Befundmengen,
mehrfache Literalvorkommen, Eingangs-/Ausgangs-/beidseitige Profilminima,
Relationsidentitäten und Endpunktfilter, Teilselektion mit vollständigen
Referenzquellen, alle Reifegrade, Schwellen und Bindungen. Kontrollierte Änderungen
an Quellbytes bei gleicher Größe und wiederhergestellter mtime, Mitgliedschaft,
Konfiguration und Betriebszustand verwerfen den alten Bericht. Nicht verfügbare
oder unsichere Ressourcen werden nicht repariert; Schreibversuchssperren und
Byte-/Inventarvergleiche sichern den Lesevertrag. SR-TC-0096 bleibt `partial`,
weil daraus weder Vollmodell-/Profilprüfung noch spätere CLI-/Runtime-Abnahme
abgeleitet wird.

Commit-Message: `fix(lint): preserve bound findings and incomplete coverage`.
Erst das erfolgreiche Apply-Result bestätigt diesen R-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-01.C`; Produktzähler 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-VALIDATION-01.C – gemeinsame Lintprojektion (Bundle 078)

Basis ist das vollständig geprüfte erfolgreiche Result
`specroad-apply_Result_031556_1005_64501e.zip`, Commit
`b1f6b1ee52e23f768e75e0361dfb9d9762c315bc`. Alle 1458 Snapshot-Dateien stimmen
mit dem R-Stand überein. Jeweils 5773 parallele und serielle Apply-Tests
bestätigen den tatsächlichen R-Commit.

Die gemeinsame reine Projektion in `lint/reporting.py` sortiert vorhandene
Core-/kombinierte Befunde und bewertet ihren bereits validierten Fail-Schwellwert.
Core und Projektleser verwenden damit dieselbe Bewertung. Ob alle Prüfungen
verfügbar sind und ob die Quellen noch aktuell sind, entscheiden weiterhin die
bisherigen Aufrufer; aus der Befundprojektion entsteht keine zusätzliche
Freigabe. Der bestehende eigenständige Literalbericht bleibt erhalten.

`lint/nonliteral.py` trennt die rationale Feldbeobachtung und die Projektion der
vorhandenen Relationsprüfungen in kleine private Funktionen. Die öffentliche
Orchestrierung behält Eingabeprüfungen, deren Reihenfolge, Auswahl, Quelldigests
und Profilbindung bei. Regeln, Diagnosewerte und Reihenfolge, Fehlerschwellen,
unverfügbare Voraussetzungen und zulässige Seiteneffekte entsprechen dem
R-Zustand. Die vorhandenen 46 W-/R-Verhaltensfälle bleiben unverändert Teil der
5773 Tests umfassenden Suite; es werden keine neuen Fachregeln oder Abnahmen
behauptet. SR-TC-0096 bleibt mit seinen noch offenen Integrations- und
Runtime-Abnahmen `partial`.

Commit-Message: `refactor(lint): share finding assessment and rule projection`.
Erst das erfolgreiche Apply-Result bestätigt den C-Abschluss und damit diese
W/R/C-Folge. Nächster Schritt: `AUDIT-VALIDATION-02.W`; Produktzähler 237/885
und Sperre von 5.t.W bleiben erhalten.

### AUDIT-VALIDATION-02.W – produktive Prüfadapter (Bundle 079)

Basis ist das vollständig geprüfte erfolgreiche Result
`specroad-apply_Result_035946_1005_5a5f8b.zip`, Commit
`c48f8e581f4ba83cf925671e94ceffd1eb0f0b70`. Alle 1458 Snapshot-Dateien stimmen
mit dem bestätigten Stand überein. Je 5773 parallele und serielle Apply-Tests
bestätigen den tatsächlichen Abschluss von AUDIT-VALIDATION-01.C.

`ValidationResources` bindet exakte Projektkonfigurationsbytes und ein tatsächlich
vorliegendes, durch diese Konfiguration gebundenes Offline-Sprachregister. Der
Modellprüfer führt damit die vorhandene Sprachpolicy einschließlich der aktiven
Requirement-Sprachmischung und die tatsächlich komponierten Profil-SRX-Regeln aus.
SRX erhält die reale Projektkonfiguration, keinen ausgewählten Konfigurationsraum
und den vollständigen geladenen Relationsgraphen. Regeltyp und Reifegrad werden
beachtet; ein falsches Prädikat ist ein Profilbefund, ein nichtboolesches Ergebnis
ein SRX-Vertragsfehler. Ein bereitgestelltes Gate kann diese verfügbaren
Produktprüfer nicht ersetzen. Die W-Abhängigkeitsprojektion ist konservativ:
Sprach- und Profilprüfungen behalten das gesamte geladene Modell als Abhängigkeit.

Der Read-only-Projektleser bindet das explizite Register und prüft dessen Bytes
nach der Beobachtung erneut. Die Zielvalidierung baut ihre Ressourcen erneut aus
dem vorhandenen unveränderlichen Quellinventar auf; Direktauswertung und Dry-Run
benutzen denselben Modellpfad. Fehlendes Register hat keinen Distributionsfallback.
Explizit bereitgestellte Profilwerte bleiben Eingaben des Aufrufers, keine Aussage
über unveränderte Profildateien auf dem Datenträger.

Vorhandene formale Approvalbefunde werden über denselben Kern wie die bisherige
Approval-API übernommen. Platzhalter und unpassende Verification-Subjects sind
so in der gemeinsamen Diagnosemenge sichtbar. Eine bestandene Formalprüfung
ersetzt weder menschliche Reviews noch Evidence-Aktualität oder Historienprüfung;
die entsprechenden fehlenden Dienste bleiben unverfügbar. Sprachqualität,
optionale Analyzer, Freigabe und Schreibberechtigung werden nicht behauptet.

19 neue Verhaltenstests prüfen tatsächliche Softwareprofile, Sprachfehler,
falsche und nichtboolesche SRX-Prädikate, reale Projektwerte, formale Approvalfehler,
fehlende Dienste sowie die schreibfreie Projekt-/Ziel-/Dry-Run-Integration.
SR-TC-0086 und SR-TC-0100 bleiben mit ihrem abgegrenzten Nachweis `partial`.
Die vollständige Suite wird für diesen W-Zustand parallel geprüft; R ergänzt
Ressourcenfehler, Aktualitäts- und Auswahlgrenzen sowie Mehrfachbefunde.

Commit-Message: `fix(validation): connect productive language profile and approval checks`.
Erst das erfolgreiche Apply-Result bestätigt diesen W-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-02.R`; Produktzähler 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-VALIDATION-02.R – gebundene Ressourcen und vollständige Adapterbefunde (Bundle 080)

Basis ist das vollständig geprüfte erfolgreiche Result
`specroad-apply_Result_045412_1005_f5b80c.zip`, Commit
`3492260429e2ccddb56e8166fce10d44e3690ede`. Alle 1462 Snapshot-Dateien stimmen
mit dem bestätigten W-Stand überein. Je 5792 parallele und serielle Apply-Tests
bestätigen den tatsächlichen W-Abschluss; es besteht kein offener Applyfehler.

`ValidationResources` besitzt nun auch die tatsächlichen Profilbytes, die exakte
Core-Version, die explizite CLI-Auswahl und gegebenenfalls Sprachpaketbytes.
Jede Modellprüfung rekonstruiert diese Eingaben und komponiert das Profil erneut
gegen die gebundene Konfiguration. Fremde Kompositionen, fehlende Profilbytes,
geänderte Eingaben und nicht passende Registerbindungen werden abgewiesen.
Die Zielprüfung gewinnt dieselben Werte aus ihrem erneut geprüften Quellinventar;
abgeleitete Registermetadaten ersetzen dabei niemals die vorhandenen Bytes.

Die produktive Profilstufe meldet nicht passende Typen und Reifegrade als nicht
anwendbar. Bei anwendbaren Sprach-/Profilregeln bleibt die vollständige geladene
Modellmenge bewusst konservative Abhängigkeit einer Teilselektion: auch eingehende
Relationen, projektweite Sprachmischung und unveränderte Quellen werden geprüft.
Unabhängige Sprach-, Profil- und formale Approvalbefunde bleiben gemeinsam
sichtbar. Profilprädikate benutzen die komponierte Severity; Strict verändert
nur die Bewertung. SRX-Typ-/Zahlen-/Strukturfehler bleiben Eingabefehler mit Code 3,
keine gewöhnlich falschen Prädikate. Die strengeren komponierten SRX-Strukturgrenzen
werden mit der tatsächlichen Projektpolicy kombiniert; weiche Arbeitsziele
bleiben fortsetzbare Rechenziele und erzeugen keinen neuen Fehlschlag.

Der Projektleser akzeptiert zusätzlich `profile_paths`: eine vollständige explizite
Zuordnung aller ausgewählten Profilkeys zu Projektpfaden. Er prüft deren exakte
Bytes vor der Modellprüfung und erneut nach den Artefaktbeobachtungen. Fehlende,
fremde, veränderte oder verlinkte Ressourcen werden nicht ersetzt oder repariert.
Register-, Konfigurations- und Artefaktänderungen verhindern ebenso die Übernahme
eines alten Erfolgs. `resource_bindings` und `resource_files_verified` machen den
beobachteten Umfang maschinenlesbar; ohne explizite Profilpfade bleiben die
bereitgestellten Profilwerte reine Eingaben ohne behauptete Dateisystemaktualität.
Das ist weiterhin eine schreibfreie Bibliotheks-API, keine atomare Inventur oder
vorgezogene vollständige CLI-Integration.

38 neue Verhaltenstests ergänzen die 19 W-Fälle um Anwendbarkeit, abhängige Auswahl,
mehrere unabhängige Befunde, Severity/Strict, reale SRX-Relationsdaten, Profilgrenzen,
Ressourcenfehler und Änderungen während tatsächlicher Prüfungen. Projektprüfung,
Zielprüfung und Dry-Run stimmen im jeweils gebundenen fachlichen Umfang überein.
Ein fremd gebundener gespeicherter Gatebefund wird zurückgewiesen. Menschliche
Reviews, Evidence und Historie bleiben bei fehlendem Dienst unverfügbar; die
bekannten Formalbefunde erzeugen weder Freigabe noch Schreibberechtigung.
SR-TC-0086 und SR-TC-0100 bleiben `partial`; die komplette Suite umfasst jetzt
5830 Verhaltenstests und wird für diesen Zustand ausschließlich parallel geprüft.

Commit-Message: `fix(validation): harden resource binding and adapter coverage`.
Erst das erfolgreiche Apply-Result bestätigt diesen R-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-02.C`; Produktzähler 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-VALIDATION-02.C – gemeinsame gebundene Beobachtungen (Bundle 081)

Basis ist das vollständig geprüfte manuelle Result
`specroad-apply_Result_061427_1008_89b33f.zip`, Commit
`5080638795d9fd828b5ceb0b00b107c4980aea22`. Alle 1464 Snapshot-Dateien stimmen
mit Apply und der Entwicklung überein. Das Result erfasst den sauberen Zustand;
es behauptet keinen neuen Testlauf. Der ursprüngliche Apply-Lauf
`3e23c672-6bc8-48c1-a10c-d8f962308d5c` bestätigt Bundle 080 mit Exitcode 0,
5830 bestandenen parallelen Tests und dem damals zusätzlich ausgeführten
seriellen Lauf mit ebenfalls 5830 bestandenen Tests. Dessen fehlgeschlagener
Result-Export ist durch den frischen, vollständig geprüften Snapshot ergänzt;
Patchhash, Elterncommit, alle 15 Payload-Dateien und der Abschlusscommit passen.

Modellprüfung, Read-only-Validierung, Ressourcenbeobachtung und Diagnoseprojektion
verwenden dieselbe Bindung logischer Quellpfade an ihre tatsächlich gelesenen
Bytes. Die jeweilige etablierte Reihenfolge bleibt erhalten; vorhandene
Input-Hashes und Aktualitätsprüfungen ändern sich nicht. Die produktiven
Sprach-/Profiladapter gewinnen Quellen und Pfadzuordnung gemeinsam. Der SRX-Graph
verwendet diese bereits erfassten Quellen; Projektpolicy und komponierte harte
Grenzen werden weiterhin auf frischen abgelösten Konfigurationswerten kombiniert.

Die Diagnoseprojektion trennt Quellenabgleich, einzelne Befundprojektion und
operationelle Fehlerpriorität. Codes, Pointer, Ursprünge, Severity, Strict,
Befundreihenfolge und die Priorität der Exitcodes bleiben unverändert.
Alle W-/R-Fälle und die schreibfreien Wirkungen bleiben erhalten. Es entstehen
keine neuen Fachgates, Reviews, Evidence- oder Freigabebehauptungen;
SR-TC-0086 und SR-TC-0100 bleiben mit ihrem bisherigen Teilumfang `partial`.

Die bereits beauftragte technische Testpolicy-Korrektur entfernt zugleich den
seriellen Zusatzstart aus `tools/run_apply_tests.py`. Das bisherige Final-Argument
bleibt kompatibel und führt denselben einzelnen parallelen Volltest aus.
Die Prozess-/Fehlerregressionen prüfen Erfolg, Fehlschlag und Startfehler ohne
Wiederholung oder Moduswechsel. Die technischen Bedienungsanleitungen beschreiben
den aktuellen Runner; historische Testnachweise bleiben unverändert.

Commit-Message: `refactor(validation): consolidate bound resource observations`.
Erst das erfolgreiche Apply-Result bestätigt diesen C-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-03.W`; Produktzähler 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-VALIDATION-03.W – alle unabhängig fehlenden Referenzziele (Bundle 082)

Basis ist Result `specroad-apply_Result_075733_1008_17cdbe.zip`, Commit
`9a121a3535b336312019c88b3fdda9f0e00d4611`. Der vollständig geprüfte Apply-Lauf
bestätigt Bundle 081 mit 5829 erfolgreichen parallelen Tests und sauberem
Abschluss. Alle 1464 Snapshotdateien und die elf übergebenen Payloads stimmen
mit der Entwicklung und dem tatsächlichen Apply-Commit überein.

Nach erfolgreichem Parsing und Schemaaufbau sammelt die Referenzstufe unabhängig
fehlende Relationsziele und explizit bekannte Feldziele vor ihrem Abbruch.
Voraussetzung sind eindeutig indexierbare Artefakt-, Relations- und externe
Relationsidentitäten sowie ein gemeinsamer Projektpräfix. Die Ermittlung meldet
jede Fundstelle mit dem bestehenden Grund, SRV020, Quellartefakt, Datei und Pointer;
sie konstruiert keinen aufgelösten Teilgraphen. Abgeleitete Review-Endpunkte
bleiben an die erfolgreiche Auflösung ihrer gespeicherten Relation gebunden.

Die Verhaltensabnahme umfasst zwei Quellen, zwei Kanten derselben Quelle und
beide Componentfelder eines Interfaces. Direkte und öffentliche schreibfreie
Projektbewertung sowie umgekehrte Dokumentreihenfolge erhalten dieselbe Menge.
Graph-/Fachstufen bleiben gesperrt, der Exitcode ist 3, die Prüfung unvollständig
und ohne Freigabe. Das Laden aller tatsächlichen Ziele stellt die erfolgreiche
Prüfung wieder her. Unlesbare oder schemawidrige Bestände beweisen keine fehlenden
Ziele; mehrdeutige Artefaktidentitäten behalten ihre strikte Abbruchgrenze.

Gemischte fehlende/typwidrige Ziele und die weiteren R-Randfälle bleiben der
folgenden Phase zugeordnet. Die bestehenden SR-TC-Manifeste werden nicht zur
vollständigen Produktabnahme hochgestuft; 5.t.W bleibt gesperrt.

Commit-Message: `fix(validation): collect independently missing reference targets`.
Erst das erfolgreiche Apply-Result bestätigt diesen W-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-03.R`; Produktstand weiterhin 237/885.

### AUDIT-VALIDATION-03.R – vollständige sichere Referenzbefunde (Bundle 083)

Basis ist Result `specroad-apply_Result_083435_1008_5486e2.zip`, Commit
`7b0814660666f8f71584d13ab250c7ca7d2803e5`. Der vollständig geprüfte Apply-Lauf
bestätigt Bundle 082 mit 5837 erfolgreichen parallelen Tests und sauberem
Abschluss. Alle 1465 Snapshotdateien, vier Payloads, Elterncommit und Message
stimmen mit Apply und Entwicklung überein.

Die Referenzbeobachtung prüft zunächst eindeutige Artefakt-, Relations- und
externe Relationsidentitäten sowie den gemeinsamen Projektpräfix. Konflikte
werden vor jeder Zielzuordnung gemeldet, auch wenn eine frühere Quelle bereits
ein fehlendes Ziel enthält. Ein mehrdeutiger Bestand erzeugt keine erfundenen
Zielidentitäten oder daraus abgeleiteten fehlenden Ziele.

Bei eindeutiger Struktur werden alle unabhängig fehlenden, typwidrigen und
unzulässigen Selbstziele gemeinsam ermittelt. Die Quell-/Zielregeln stammen
weiterhin aus derselben strikten Relationsprüfung. Bekannte Feldziele und
fehlende gespeicherte Review-Relationen kommen mit ihren bisherigen Codes und
Fundstellen hinzu. Eine vorhandene, aber nicht auflösbare Relation erzeugt
keinen zusätzlichen vermeintlich fehlenden Review-Verweis. Schemawidrige
Feldtyp-IDs bleiben vor der Referenzstufe gesperrt.

37 zusätzliche Verhaltensfälle prüfen gemischte Quellen und Kanten, wiederholt
fehlende Ziele an verschiedenen Orten, Relations-/Feldkombinationen, Review-
Abhängigkeiten, Identitätskonflikte und Parse-/Schemabarrieren. Die vollständige
sowie auf betroffene oder unabhängige Artefakte eingeschränkte öffentliche
Projektbewertung liefern dieselben vollständigen Diagnosemengen wie die direkte
Prüfung. Reihenfolge, Summary und Code 3 bleiben deterministisch; Projektbytes
und Modi bleiben schreibfrei. Graph-/Fachprüfungen bleiben nach Fehlern gesperrt,
und die strikte Graphkonstruktion akzeptiert weiterhin keinen ungültigen Bestand.

Commit-Message: `fix(validation): complete reference diagnostic sets`.
Erst das erfolgreiche Apply-Result bestätigt diesen R-Abschluss. Nächster
Schritt: `AUDIT-VALIDATION-03.C`; Produktstand 237/885 und Sperre von 5.t.W
bleiben erhalten. Die SR-TC-Manifeste behalten ihren bisherigen Teilumfang.

### AUDIT-VALIDATION-03.C – gemeinsame Referenzregeln (Bundle 084)

Basis ist Result `specroad-apply_Result_090436_1008_f0b039.zip`, Commit
`81daac1f05b5cbc018ce363074de91a156d68503`. Der vollständig geprüfte Apply-Lauf
bestätigt Bundle 083 mit 5874 erfolgreichen parallelen Tests und sauberem
Abschluss. Alle 1466 Snapshotdateien und vier Payloads stimmen mit dem
Eltern-/Abschlusscommit und der Entwicklung überein.

Strikte Graphkonstruktion und sammelnde Modellvalidierung verwenden gemeinsame
Prädikate für Quellidentitäten, Relationsidentitäten, externe Identitäten,
vorhandene Ziele, zulässige Endpunkte und Fehlerorte. Die Auswertung der
Identitätsbefunde erfolgt schrittweise: Der strikte Konstruktor bricht weiterhin
beim bisherigen ersten Fehler ab; die Beobachtung sammelt ihre sicheren Befunde
innerhalb der bestehenden Phasengrenzen. Reihenfolge, Codes, Artefaktzuordnung,
Datei und Pointer bleiben erhalten. Es entsteht weiterhin kein ungültiger
aufgelöster Gesamtgraph.

Bekannte Feldziele und gespeicherte Review-Relationen nutzen jeweils eine
Fehlerprüfung sowohl für die Diagnosebeobachtung als auch für den strikten
Abhängigkeitsaufbau. W-/R-Verhalten, Auswahlgrenzen und erlaubte schreibfreie
Wirkungen bleiben unverändert. Die vorhandenen Verhaltenstests einschließlich
aller 45 neuen W-/R-Fälle werden unverändert übernommen; es gibt keine neue
fachliche Regel oder zusätzliche Freigabebehauptung.

Commit-Message: `refactor(validation): share strict reference predicates`.
Erst das erfolgreiche Apply-Result bestätigt diesen C-Abschluss. Nächster
Schritt: `AUDIT-EVIDENCE-01.W`; Produktstand 237/885 und Sperre von 5.t.W
bleiben erhalten. Die bestehenden SR-TC-Teilumfänge ändern sich nicht.

### AUDIT-DOC-01 und AUDIT-EVIDENCE-01 – Anweisungen und Nachweisdaten

**AUDIT-DOC-01 / F09:** Diese Planrevision ersetzt aktive überholte Testausführungsanweisungen durch Verweise auf die zentrale lokale AGENTS.md und die technische Testanleitung. Historische Bundle-/CI-Abläufe werden als historische, außer Kraft gesetzte Vorgaben kenntlich gehalten, nicht als nachträglich anders ausgeführte Tests umgeschrieben. Dies ändert weder Runner noch GitHub-Workflow. Die Abschlusskontrolle erfolgt in AUDIT-CLOSE, ohne Dokumentations- oder Darstellungstests einzuführen.

**AUDIT-EVIDENCE-01 / F10; Voraussetzung:** alle obigen Untersuchungsentscheidungen und bestätigten Korrekturen. **Bezug:** insbesondere 3.h–3.j, 4.e/4.g/4.i, 5.n; SR-REQ-0288/0412 sowie SR-TC-0241/0259/0383/0384/0385; SR-VER-0022/0029 und die jeweiligen Receipt-Nachweise.

- [x] **AUDIT-EVIDENCE-01.W:** Überholte `scope`-/`open_items`-Angaben in SR-TC-0288 und SR-TC-0412 mit tatsächlichen Kernen und Tests abgleichen; die fehlende Beschreibung von `SR-FIX-TRANSACTION-RECEIPTS-v1` anhand ihres realen Providers ergänzen. **Abnahme:** Referenzen zeigen auf existierende fachliche Nachweise; nicht ausgeführte beziehungsweise noch unvollständige Abnahmen bleiben erkennbar offen.
- [x] **AUDIT-EVIDENCE-01.R:** Alle von den Nacharbeiten betroffenen Requirementmanifeste, Tests und Fixturebezüge konsistent fortschreiben. **Abnahme:** Formale Sammlung und Bindung passen zur echten Testmenge; jeder Behauptung steht ihr tatsächlich geprüfter Teilumfang gegenüber. Keine pauschale Hochstufung von `partial` und keine erfundenen alten W/R/C-Erfolge.
- [x] **AUDIT-EVIDENCE-01.C:** Gemeinsame Beschreibungen und Verweise konsolidieren, ohne Nachweisumfang oder Ausnahmen zu ändern. **Abnahme:** Inhaltliche Befundzuordnung und maschinenlesbare Katalogverträge bleiben wie nach R. Keine Tests auf Wortlaut, Markdown oder Dokumentation.

### AUDIT-EVIDENCE-01.W – aktuelle Kernnachweise und Receipt-Fixture (Bundle 085)

Basis ist Result `specroad-apply_Result_092722_1008_f55178.zip`, Commit
`9fbbe807695b971bb874e852aca852f03f50c91a`. Der vollständig geprüfte Apply-Lauf
bestätigt Bundle 084 mit 5874 erfolgreichen parallelen Tests und sauberem
Abschluss. Alle 1467 Snapshotdateien und vier Payloads stimmen mit dem
Eltern-/Abschlusscommit und der Entwicklung überein.

SR-TC-0288 beschreibt die vorhandenen Quantoren und die exakte Arithmetik
einschließlich Anhang-U- und Konformitätsvektoren. Acht zusätzliche Verweise
binden bereits vorhandene Verhaltenstests. Die noch offenen öffentlichen
Query-/Filter- und Dokumentverbraucher bleiben ihren Positionen 8.b und 11.f
zugeordnet; Kernnachweise ersetzen keine vollständige Verbraucherintegration.

SR-TC-0412 berücksichtigt die vorhandenen schwachen Scope-Grenzen,
Kontrollausschlüsse und semantischen Scope-Hashes. Zwölf zusätzliche Verweise
belegen diese Kerne anhand vorhandener Tests. Tatsächliche Anwendbarkeit und
ihre Einbindung vor der Closure bleiben in 9.c/9.d offen. Explizit gebundene
Beobachtungen sind weiterhin kein Beleg für ein vollständiges Live-Inventar,
authentische Providerfrische, einen atomaren Snapshot oder eine Freigabe.

Der bereits verwendete Fixture-Identifier `SR-FIX-TRANSACTION-RECEIPTS-v1`
erhält seine fehlende Definition mit dem realen Provider
`tests/support/receipts.py:published`. Die Beschreibung trennt dessen gesperrten,
publizierten Transaktionszustand von der dauerhaften Receipt-Finalisierung im
zugehörigen `finish`-Helper und hält die reine Testautorität ausdrücklich fest.

Beide Requirementmanifeste bleiben `partial`; die Spezifikationsbindung und
sämtliche bestehenden Tests bleiben erhalten. Die 20 ergänzten Testidentitäten
sind in der tatsächlichen erfolgreichen Testsammlung von Bundle 084 vorhanden.
Das neue Bundle benötigt zusätzlich seinen eigenen vollständigen parallelen
Dev-/Apply-Nachweis. Es entstehen keine Tests auf Beschreibungswortlaut oder
Dokumentation und keine neue fachliche Implementierung.

Commit-Message: `docs(verification): align operator and scope evidence`.
Erst das erfolgreiche Apply-Result bestätigt diesen W-Abschluss. Nächster
Schritt: `AUDIT-EVIDENCE-01.R`; Produktstand 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-EVIDENCE-01.R – konsistente Auditbindungen (Bundle 086)

Basis ist Result `specroad-apply_Result_095456_1008_6973ba.zip`, Commit
`5ad36d921675f0ecb52ac5bfc10424c7bc3c1943`. Bundle 085 ist durch 5874 erfolgreiche
parallele Apply-Tests und einen sauberen Abschluss bestätigt. Alle 1467
Snapshotdateien und vier W-Payloads stimmen mit Commit und Entwicklung überein.

Der Abgleich umfasst die 17 seit der Auditbasis veränderten Requirementmanifeste
und die zusätzlich betroffenen Diagnose-, Receipt-, SRX-, Scope- und
Versionsnachweise: SR-TC-0086–0092, 0096, 0098–0100, 0194, 0241, 0257–0259,
0262, 0288, 0376–0378, 0383–0385, 0392, 0412, 0458–0459, 0462, 0506, 0511
und 0569. Von diesen 32 Manifesten benötigen 17 Änderungen; die übrigen
15 behalten ihre zutreffenden Teilumfänge und Verweise.

Die 45 bereits vorhandenen W-/R-Fälle zur Referenzaggregation werden ihren
tatsächlichen Abnahmen zugeordnet: vollständige sichere Befundmengen,
Artefakt-/Pfad-/Pointerzuordnung, stabile Codes und Reihenfolge, korrekte
Zusammenfassungen sowie schreibfreie Projektbeobachtung. Parametrisierte Fälle
verwenden ihre exakten gesammelten Kennungen. Strukturelle und mehrdeutige
Identitätsbefunde sperren weiterhin die Folgesemantik; der positive Kontrollfall
mit allen vorhandenen Zielen belegt den wieder gültigen Graphen. Bestehende
Fallbackcodes werden nicht nachträglich als neue spezifische Codes ausgegeben.

Neun bestehende Discard-Neustartfälle ergänzen die Receipt- und Auditbindung in
SR-TC-0259/0462. Sie belegen ausgewählte reale Prozessabbrüche, unveränderte
Basisbytes, bewahrte Originalnachweise, Wiederholung und normalen Folgezugriff.
Bereits abgeschlossene Neustartrekonstruktion und Validierungsadapter stehen
nicht länger als unerledigte Implementierung in den offenen Punkten. Alte
Journale ohne explizite Basisauswahl und Building-v1 ohne persistierten
Stagingnachweis bleiben abgegrenzt; bestehende Prepared-v1-Unterstützung wird
nicht ausgeschlossen. Automatischer Preflight (5.t), vollständige Fault-Injection
(5.v), Restore (15.j–15.l), öffentliche Befehlsintegration und authentische
Freigaben bleiben offen.

Zwei zusätzliche Fixturedefinitionen verweisen auf die realen produktiven
Validierungseingaben und Referenzfehlerfälle. Die Scope-Vergleichsfixture nennt
das tatsächliche Modul mit seinen getrennten Hash- und Vergleichshelfern.
Die Receiptdefinition aus W bleibt erhalten. Insgesamt entstehen 243 zusätzliche
Requirement-Testbindungen zu 54 vorhandenen Tests; keine Testimplementierung
oder Produktquelle wird geändert. Alle 730 Katalogeinträge werden gegen die
tatsächlich gesammelten Testidentitäten geprüft. Alle bisherigen
Requirementstatus und die Spezifikationsbindung bleiben erhalten; vollständige
Runtime-/Plattformabnahmen werden ausschließlich durch tatsächlich ausgeführte
Läufe belegt.

Commit-Message: `docs(verification): reconcile audit evidence bindings`.
Dieser R-Stand benötigt seinen eigenen vollständigen parallelen Dev-/Apply-Lauf;
erst das erfolgreiche Apply-Result bestätigt den Abschluss. Nächster Schritt:
`AUDIT-EVIDENCE-01.C`; Produktstand 237/885 und Sperre von 5.t.W bleiben erhalten.

### AUDIT-EVIDENCE-01.C – konsolidierte Teilumfangsbeschreibungen (Bundle 087)

Basis ist Result `specroad-apply_Result_101721_1008_305181.zip`, Commit
`da2ba9703569467856a69175976859e59621eedd`. Bundle 086 ist durch 5874 erfolgreiche
parallele Apply-Tests und einen sauberen Abschluss bestätigt. Alle 1467
Snapshotdateien und 19 R-Payloads stimmen mit Commit und Entwicklung überein.

Die über mehrere Auditphasen gewachsenen Recoverybeschreibungen sind nach
aktuellem Vorgang, erhaltenen Sicherheitsgrenzen und offenen Abnahmen geordnet.
Gleiche Teilverträge für vollständige Hilfsdateiveröffentlichung,
Originalnachweiserhalt und explizite Wiederaufnahme verwenden dieselbe
Beschreibung. Die Discard-Manifeste beschreiben gemeinsam den erhaltenen
Preflightpfad und die persistierte Neustartrekonstruktion. Historische
W-/R-Zuordnung verbleibt in den jeweiligen Planabschnitten; ihre Entfernung aus
der laufenden Teilumfangsprosa verändert keine Abnahme.

Die Diagnosemanifeste verwenden eine einheitliche Grundbeschreibung für
gebundene Beobachtung, stabile Reihenfolge und explizite Schwellenbewertung.
Die jeweiligen Ergänzungen zu Fundorten, Codes, Referenzmengen und
Zusammenfassungen bleiben erhalten. In insgesamt 16 Requirementmanifesten
ändert sich ausschließlich `oracle.scope`; alle anderen Felder, insbesondere
Status, Requirement-/Verifikationsidentitäten, Originalanforderung,
Test-/Fixturebindungen, Diagnose-/Exitverträge und offene Punkte, bleiben
identisch zum geprüften R-Stand. Fixturekatalog, Produktquellen und Tests bleiben
ebenfalls unverändert. Die 3886 Testbindungen aller 730 Katalogeinträge behalten
ihren tatsächlichen Nachweisumfang; es entstehen keine Wortlaut- oder
Dokumentationstests.

Commit-Message: `docs(verification): consolidate audit scope descriptions`.
Dieser C-Stand benötigt seinen eigenen vollständigen parallelen Dev-/Apply-Lauf;
erst das erfolgreiche Apply-Result bestätigt den Abschluss. Danach folgt
`AUDIT-CLOSE` mit seiner gesonderten Befund- und Vertragsentscheidung. Der
Auditstatus bleibt bis dahin offen; Produktstand 237/885 und Sperre von 5.t.W
bleiben erhalten.

### AUDIT-CLOSE – Abschlussentscheidung vor 5.t

- [x] Für F01 bis F10 sowie die zusätzlichen Recovery-/Diagnosefragen eine abschließende Entscheidung mit aktuellem Result-/Commitbezug dokumentieren. Bestätigte Fehler brauchen beobachtbare Verhaltensnachweise; widerlegte Verdachtsstellen brauchen ihren Gegenbeleg. Tatsächlich spätere Arbeit braucht eine genaue offene Planposition und die Begründung, warum sie keine schon fällige Abnahme ersetzt.
- [x] Die betroffenen fachlichen Verträge nach den Korrekturen erneut prüfen, insbesondere vollständige Recoverywurzel, dauerhafte Abschlussbeweise und normaler Folgezugriff. Die tatsächlichen erfolgreichen Apply-Prüfungen anhand ihrer Results feststellen; dieses Planungsbundle belegt noch keine Reparatur.
- [x] Aktuelle Testanweisungen auf Konsistenz zur zentralen Arbeitsregel prüfen. Historische Ausführungsaussagen und nicht verfügbare Nachweise bleiben historisch beziehungsweise offen; es werden keine vergangenen Testläufe nachträglich behauptet.
- [x] Im Fortschrittsblock `audit_followup_status` erst nach erfüllter Abschlussentscheidung auf `closed` und `next_audit_step` auf `null` setzen. Der Produktzähler bleibt 237/885; erst der danach tatsächlich umgesetzte und abgenommene reguläre Schritt 5.t.W erhöht ihn. Solange fällige Korrekturen oder wesentliche Vertragsfragen offen sind, bleibt die Sperre bestehen.

### AUDIT-CLOSE – beobachtete Abschlussentscheidung (Bundle 088)

Abschlussbasis ist das vollständig geprüfte Result
`specroad-apply_Result_103524_1008_f2793e.zip`, SHA-256
`4d65d7e3423a1b6fe1c9b0bb3a6c698c319bf2d31761aa926d82b29cd5bfdd68`,
Commit `2ace2fc325093a9fb8dab9795c762bf4d2ef7adb`. Seine 1467 Snapshotdateien und
17 Payloads aus Bundle 087 stimmen mit Git und Entwicklung überein. Der saubere
Apply-Abschluss enthält 5874 erfolgreiche Tests mit vier parallelen Workern in
413,17 Sekunden, Exit 0 und keine Warnungen.

Die [maschinell lesbare Nachweisübersicht](../../reviews/SpecRoad_AUDIT_CLOSE_evidence.json)
bindet 41 tatsächliche Nicht-Dry-Run-Results und die 40 aufeinanderfolgenden
Audit-Commits seit `f5534e50e74a701b4a5b29cdcfc39e792e21e542`. Der installierte
PatchHarbor-Reader prüfte alle Results mit seinen unveränderten Standardlimits.
Für jeden Snapshot stimmen vollständige Pfadmenge, Größe, Git-Blob und Modus mit
dem aufgezeichneten Commitbaum überein. Logmeldungen, Testgates, Commitnachrichten
und Elternfolge wurden abgeglichen. Die Übersicht ist ein Review vorhandener
Nachweise; sie ist selbst weder Testlauf noch Releasefreigabe.

| Befund | Abschließende Entscheidung und beobachtbarer Nachweis |
|---|---|
| F01 / REC-01 | Bestätigt und korrigiert. Vollständige normative Pfad-/Bytemengen binden die unabhängig vorbereitete Basis-/Zielwurzel. Zusätzliche, fehlende, geänderte und während der Prüfung beobachtete Ressourcen sperren; `test_recovery_inventory*` erhält unbeteiligte Dateien. Recovery behauptet keine erneute semantische Modellberechnung. |
| F02 / REC-02 | Bestätigt und korrigiert, einschließlich Zielabschluss und Discard-Receipt. `test_terminal_recovery*` prüft dauerhafte Receipts, Originalautorität, archivierte Work-Bytes und explizite Bereinigung. Unabhängige Prozesse lesen anschließend das Modell und erwerben einen neuen Writerlock; aktive fremde Blocker bleiben erhalten. |
| F03 / REC-03 | Bestätigt und korrigiert. `test_recovery_mutation_accounting*` prüft spätere Fehler nach Verzeichnis-, Receipt-, Marker- und Auditwrites. Vorbestehende Konflikte werden nicht als eigene Mutation ausgegeben. |
| F04 / REC-04 | Wiederanlauflücke bestätigt und korrigiert. `test_recovery_initial_successor` und `test_recovery_auxiliary_writes` prüfen vollständige gebundene Hilfsdateiveröffentlichung, echte Prozessabbrüche, Wiederaufnahme und Fremd-/Quelländerungsgrenzen. |
| F05 / CONTRACT-01 | Selbstbeschreibung korrigiert; SRX-Reichweite geklärt. `test_capabilities` und `test_capability_scope` verbinden angebotene Schemas und SRX-Bibliotheksversionen mit tatsächlicher Ausführung, ohne künftige CLI-Befehle oder Ausgabeformate zu behaupten. |
| F06 / CONTRACT-02 | Change-Plan-Kataloglücke korrigiert. `test_schema_catalog_change_plan` prüft abrufbare Version 1.2.0, Identität, Operationsgrenzen und isolierte Rückgabewerte. |
| F07 / VALIDATION-01 | Bereits fällige Rationale-/Relationsminima korrigiert. `test_core_lint*` prüft unabhängige Befunde, vollständige Mengen, Auswahl-/Profilgrenzen und ehrliche Unvollständigkeit; Literalbefunde bleiben erhalten. |
| F08 / VALIDATION-02 | Bereits verfügbare produktive Sprach-, Profil-/SRX- und Formalprüfungen eingebunden. `test_production_validation*` prüft echte Ressourcen, Projekt-/Zielpfade und gleichzeitige Befunde. Fehlende authentische Review-, Evidence- und Historiedienste bleiben ausdrücklich unavailable und erteilen keine Freigabe. |
| F09 / DOC-01 | Aktive Anweisungen manuell abgeglichen. TD-002 und Resource_Inventory verweisen auf ausschließlich parallele Dev-/Apply-Volltests; GitHub-CI startet allein der Nutzer. Historische Ausführung und überholte Vorgaben sind als solche erhalten. Keine Wortlaut-/Dokumentationstests. |
| F10 / EVIDENCE-01 | W/R/C durch Results 085–087 bestätigt. Aktuelle Scope-/Open-Item-Angaben, 3886 bisherige Testbindungen und reale Fixtureprovider stimmen überein; keine Partial-Anforderung wurde als vollständig erfüllt ausgegeben. |
| Zusätzlicher Discard-Neustart / REC-05 | Bestätigte Abhängigkeit korrigiert. `test_discard_restart*` prüft Prepared/Building, kurze Vorbereitungsbytes, vollständige Ressourcenbasis, eigene frische Prozesse und unterbrochene Abschlussgrenzen; archivierte Originalbytes und nächste Writer bleiben nachgewiesen. |
| Zusätzliche Diagnoseaggregation / VALIDATION-03 | Unabhängige Referenzfehler werden vollständig an sicheren Identitätsgrenzen gesammelt. `test_validation_missing_references` und `test_validation_reference_sets` prüfen Codes, Fundorte, Summary, Auswahl und Sperren. Sechs zusätzliche Abschlussfälle sichern Ziel-/Dry-Run-Parität und die bestehende strikte Planungsgrenze. |

Die sechs Abschlussfälle in `test_validation_target_reference_sets` vergleichen
zwei fehlende Interface-Componentfelder, einen verbliebenen Fehler, beide real
vorhandenen Ziele sowie zwei Fundstellen desselben fehlenden Ziels durch direkte
Modellprüfung, schreibfreien Projektleser, vollständige Zielbewertung und Dry-Run.
Ein unverändertes Interface kann die Änderung eines anderen Artefakts sperren.
Codes, Fundorte, Summary, Exit 3 beziehungsweise der echte Positivfall und fehlende
Schreib-/Freigabeberechtigung werden beobachtet. Zwei weitere Konstellationen
zeigen die notwendige Grenze: Ungültige gespeicherte Relationsgraphen werden
bereits vor Erstellung eines ChangePlans zurückgewiesen. Daraus wird keine
fiktive Zielbewertung und kein gültiger Teilgraph erzeugt. Die fünf betroffenen
Partial-Manifeste 0086/0088/0099/0100/0238 erhalten 24 zusätzliche Bindungen; ihre
Anforderungen und offenen Vollabnahmen bleiben erhalten.

Historische Ausnahmen bleiben ausdrücklich sichtbar:

- Bundle 048 lieferte erfolgreiche W-/R-Commits, scheiterte nach erfolgreichen
  C-Tests aber vor dem C-Commit. Bundle 049 bestätigt den tatsächlich späteren
  C-Abschluss; das fehlgeschlagene Result wird nicht umgedeutet.
- Bundle 061 bestand seine Tests, scheiterte dann am Whitespacegate ohne C-Commit.
  Bundle 062 korrigierte den erhaltenen Zustand und hat eigene erfolgreiche Gates.
- Bundle 080 bestand 5830 parallele und die damals vorgeschriebenen 5830 seriellen
  Tests; Commit `5080638795d9fd828b5ceb0b00b107c4980aea22` entstand. Danach scheiterte
  die Result-Veröffentlichung. Aufbewahrte Notfalllogs und der persistierte
  PatchHarbor-Applybeleg belegen die Ausführung; das spätere manuelle Result
  `specroad-apply_Result_061427_1008_89b33f.zip` bestätigt den Quellstand, enthält
  selbst jedoch keine Execution-Logs. Diese qualifizierte Beleglage bleibt benannt.
- Der historische Push-only-Lauf erzeugte keinen neuen Commit und keinen neuen
  Testnachweis. Frühere serielle Läufe werden nicht in parallele umgeschrieben.
  Der ursprüngliche statische Grobaudit belegt weiterhin keine damaligen
  Produkt-W/R/C-Zwischenstände und führte selbst keine Tests aus.

Die verbleibenden Arbeiten ersetzen keine bereits fällige Abnahme: Automatischer
Transaktionspreflight bleibt der nächste Produktpunkt 5.t; die vollständige
Crashmatrix bleibt 5.v. Authentische Lifecycle-/Review-, Baseline- und
Evidenceintegration bleibt 7.f/7.g/7.h/7.j, 10.d.C und 12.t.W zugeordnet;
ihre fehlenden Dienste erzeugen heute Unvollständigkeit. Öffentliche SRX-Query-
und Dokumentkonsumenten bleiben 8.b und 11.f, produktive Konfigurationsanwendbarkeit
9.c/9.d, Vollquellen-Restore 15.j–15.l und vollständige Runtime-/Dateisystem- und
Releaseabnahme M20. Die genaue Begründung pro Grenze steht in der Nachweisübersicht.
730 Requirements bleiben bei 433 open und 297 partial; Releasefreigabe bleibt false.

**Entscheidung:** Die bestätigten, bereits fälligen Auditkorrekturen sind durch
ihre tatsächlichen Apply-Results beziehungsweise die benannte qualifizierte
Belegquelle umgesetzt. Es verbleibt kein ungeklärter Audit-Vertragswiderspruch.
Dieser Abschlusszustand erhält seinen eigenen vollständigen parallelen Dev-/Apply-
Test vor dem Commit; erst sein erfolgreiches Apply-Result bestätigt `closed` und
hebt die Sperre von 5.t.W auf. Produktzähler und historische Produktcheckboxen
bleiben bei 237/885, der Fortschrittsblock setzt `next_audit_step` auf `null`.
Commit-Message: `test(audit): close verified findings and target reference coverage`.

### Rückverweise auf abgeschlossene Produktpositionen

Die Nacharbeiten präzisieren den heutigen Korrekturbedarf an diesen historischen Abschlüssen: 1.i/1.n → F05; 2.q/5.a → F06; 3.h–3.j und 4.e/4.g/4.i → F10; 4.l/4.o–4.r/5.f/5.g → F07/F08 und Diagnosefrage; 5.n/5.p–5.s → F01–F04 und Neustart-/Abschlussfragen. Die ursprünglichen Fachabnahmen und Requirementbezüge werden dadurch nicht still umdefiniert. Neue Produktanforderungen, automatische Recovery aus 5.t, die vollständige Crashmatrix aus 5.v und Vollquellen-Restore aus M15 bleiben ihren regulären Positionen vorbehalten.
