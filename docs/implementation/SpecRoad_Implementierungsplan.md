# SpecRoad – vollständiger W/R/C-Implementierungsplan

**Status:** aktive Implementierung; verbindlicher Fortschritt im folgenden Fortschrittsblock.  
**Planrevision:** 2 · **Stand:** 2. Oktober 2026 · **Zielrelease:** 0.2.0 · **Spezifikationsstand:** 0.2.7

Dieser Plan konkretisiert die vom Nutzer bestätigten **20 Meilensteine in 295 Schritte und 885 einzeln beschriebene W/R/C-Commits**. Bei seiner Anlage enthielt er keine abgeschlossene Produktimplementierung; der folgende Fortschrittsblock wird commitweise nach erfolgreicher Verhaltensabnahme aktualisiert. Die Meilensteinreihenfolge bleibt erhalten; jeder Schritt besitzt einen konkreten Arbeitsumfang und eigene Verhaltensabnahme.

## Verbindliche Grundlagen und Rangfolge

Fachliche Grundlage ist [`docs/specification/SpecRoad_Spezifikation.md`](../specification/SpecRoad_Spezifikation.md), einschließlich aller konsolidierten Korrekturen, 730 Requirements, 50 Verifikationsverträge, 46 Szenario-/E2E-Identitäten sowie R-01 bis R-75 und Anhang U. Der [`Prüfbericht`](../reviews/SpecRoad_v0.2.7_Implementierungsreife_Pruefbericht.md) ist ein vorgelagerter Entwurfsreview, kein späterer Produktnachweis.

Gebundene Spezifikations-SHA-256: `128fed57c038ab1af4a3bdbf70d65024c62f09f92866094caf802b8b807bca93`.  
Planungsbasis: Commit `fe2661d02ecf2f7eb483b58a4487eb009c6b3846`; sauberes Result-Bundle `specroad_Result_120209_0914_df3504.zip`; Repository-ID `3d2576df-d611-46fc-9d2b-92869468aaca`. Diese Angaben dokumentieren die Entstehung des Plans, nicht die zukünftige Patchbindung. **Jedes spätere Patchpaket bindet den dann aktuellen tatsächlichen Result-Zustand.**

Die ausdrücklichen Nutzerentscheidungen TD-001 und BD-001 vom 14. September 2026 gelten zusätzlich und bei den nachfolgend benannten Konflikten vorrangig. Sonstige normative Spezifikationsinhalte werden nicht stillschweigend abgeschwächt. Neue fachliche Widersprüche, fehlende zwingende Angaben und Sicherheitsprobleme sind offen zu benennen, nicht durch erfundene Annahmen oder Scheinerfolge zu lösen.

## Fortschritt – einzige maßgebliche Planstelle

```yaml
plan_revision: 2
implementation_plan_commits_total: 885
implementation_plan_commits_completed: 237
last_completed_plan_commit: 5.s.C
next_plan_commit: 5.t.W
last_completed_numbered_bundle: 56
implementation_state: in_progress
audit_followup_status: open
next_audit_step: AUDIT-REC-03.C
plan_setup_kind: OFF-PLAN
plan_setup_id: PLAN-SETUP
plan_setup_message: "docs(plan): add detailed SpecRoad WRC implementation plan"
```

Der ursprüngliche OFF-PLAN-Setup legte dieses Dokument mit offenen Produktpositionen an. Revision 2 ergänzt die Audit-Nacharbeiten und bereinigt überholte Testanweisungen als **OFF-PLAN / AUDIT-PLAN-UPDATE**, Commit-Message `docs(plan): Audit-Nacharbeiten vor 5.t konkretisieren`. Sie implementiert keine Produktreparatur und erhöht den Produktzähler nicht. Die Bundle-Nummer 047 bezeichnet diese Übergabe und zählt keine zusätzliche Produktposition. Ein erzeugtes ZIP oder ein hier formulierter Test ist kein abgeschlossener Commit und keine Test-Evidence; maßgeblich sind der tatsächlich entstandene Commit und sein Apply-Result.

Nach tatsächlich erfolgreich ausgeführten, zum Commit passenden Verhaltenstests wird die betreffende Checkbox im selben Git-Commit gesetzt. Reguläre Produktcommits aktualisieren den Produktzähler; Audit-Nacharbeiten aktualisieren ausschließlich ihren Status und `next_audit_step`. Ein fehlgeschlagener Schritt bleibt offen. Git ist die Historie; das Dokument nimmt keinen eigenen noch unbekannten Commit-Hash auf. Vor dem nächsten Auftrag werden tatsächliche Git-Historie, Result-Logs und Planfortschritt abgeglichen. Bei Inkonsistenz nicht einfach weiterzählen.

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

**Aktueller Arbeitsauftrag:** zuerst die unten geordneten Nacharbeiten. **Nächster regulärer Produktpunkt:** weiterhin `5.t.W`, bis zum Abschluss von `AUDIT-CLOSE` gesperrt. Die 885 ursprünglichen Produktpositionen, ihre Kennungen, Reihenfolge und historischen Checkboxen bleiben erhalten; der Zähler bleibt während der Nacharbeiten bei **237/885**. Eine gesetzte alte Checkbox beseitigt keinen hier ausdrücklich offenen Befund.

Die Kennungen `AUDIT-*` sind Nacharbeitskennungen außerhalb der 885 Produktpositionen. Bei Umsetzung wird eine genau einem ursprünglichen Plan-Commit zuordenbare Reparatur als `FIX` mit dessen Kennung geführt; übergreifende Korrekturen werden als `OFF-PLAN` geführt. Die tatsächlichen Commitkennungen und Messages werden vor der jeweiligen Auslieferung passend zum dann aktuellen Result festgelegt und mit dem Nacharbeitsschritt verknüpft. Es gibt keine durch diese Liste vorgeschriebene Bundleanzahl. Mehrere geordnete Commits dürfen in einem Bundle liegen.

Die organisatorischen W/R/C-, Test- und PatchHarbor-Regeln werden in der lokalen **AGENTS.md des Codex-Arbeitsbereichs** gepflegt. Technische Testaufrufe beschreibt [Testing.md](../development/Testing.md). Die folgenden Abnahmen beschreiben fachliches Verhalten, keine gezielte Apply-Testauswahl und keine zusätzlichen Testausführungsregeln. C erhält jeweils die Ergebnisse, Fehlerverträge und erlaubten Seiteneffekte aus W/R. Ein fehlender sinnvoller C-Delta wird nachvollziehbar dokumentiert, wie bereits im W/R/C-Abschnitt geregelt; es entsteht kein Alibi-Commit.

### Befunde und eindeutige Zuständigkeit

| Befund | Einordnung / Priorität | Ursprünglicher Bezug | Zuständige Nacharbeit | Stand dieser Planrevision |
|---|---|---|---|---|
| F01 – Recovery prüft nur journalbekannte Dateien | statisch nachgewiesene Lücke / hoch | 5.q–5.s; SR-REQ-0258/0459/0511 | AUDIT-REC-01 | W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F02 – Rollback ohne vorgeschriebenen Receipt und nutzbaren Abschluss-/Bereinigungspfad | nachgewiesener Vertragsfehler / hoch | 5.n, 5.r, 5.s; SR-REQ-0259/0462 | AUDIT-REC-02 | U bestätigt; W/R/C umgesetzt; Apply-Nachweis maßgeblich |
| F03 – falsches `mutation_possible` nach Receiptfehler | statisch nachgewiesener Fehler / mittel | 5.q.R, 5.n.R; SR-REQ-0258 | AUDIT-REC-03 | W/R umgesetzt; C offen |
| F04 – kurze eigene Hilfsdateien blockieren Wiederanlauf | Untersuchungsverdacht / mittel | 5.q.R, 5.r.R; SR-REQ-0258/0459/0511 | AUDIT-REC-04.U | offen; Reparatur nur nach Bestätigung |
| F05 – veraltete Schema-/Versionsselbstbeschreibung | Schemaanteil nachgewiesen; SRX-Reichweite offen / mittel | 1.i, 1.n, 2.q; SR-REQ-0194/0376/0392 | AUDIT-CONTRACT-01 | offen |
| F06 – Change-Plan-Schema fehlt im Katalog | nachgewiesene Kataloglücke / mittel | 2.q, 5.a; SR-REQ-0377/0378 | AUDIT-CONTRACT-02 | offen |
| F07 – nichtliterale Core-Lintanteile nicht durchgehend belegt | Abdeckungsverdacht / mittel | 4.l, 4.o, 4.r; SR-REQ-0096 | AUDIT-VALIDATION-01.U | offen; keine pauschale Gesamtimplementierung zugesagt |
| F08 – produktive M4-Gateverbindung nicht durchgehend belegt | Integrationsverdacht / mittel | 4.o–4.r, 5.f/5.g; SR-REQ-0086/0100 | AUDIT-VALIDATION-02.U | offen; legitime spätere Adapter abgrenzen |
| F09 – widersprüchliche Testanweisungen | Dokumentationswiderspruch / mittel | allgemeine Arbeitsanweisungen, TD-002 | AUDIT-DOC-01 | Textkorrektur Teil dieses OFF-PLAN-Commits; Abschlusskontrolle in AUDIT-CLOSE |
| F10 – veraltete `open_items` und unvollständige Fixturebeschreibung | Nachweisdaten inkonsistent / niedrig | 3.h–3.j, 4.e/4.g/4.i; SR-REQ-0288/0412 | AUDIT-EVIDENCE-01 | offen |

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
[Untersuchung und Reproduktion](../reviews/SpecRoad_AUDIT_REC_02_U.md), gebunden
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
Grenzen: [Transaction_Recovery.md](../development/Transaction_Recovery.md).
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
[Transaction_Recovery.md](../development/Transaction_Recovery.md).
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
- [ ] **AUDIT-REC-03.C:** Mutationsbilanz und Fehlerübersetzung zusammenführen. **Abnahme:** Strukturierte Fehler und reale Dateieffekte aus W/R bleiben gleich.

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

### AUDIT-REC-04 – kurze eigene Recovery-Hilfsdateien untersuchen

**F04; Voraussetzung:** AUDIT-REC-02/03. **Bezug:** 5.q.R/5.r.R; SR-REQ-0258/0459/0511; SR-VER-0019/0031; zugehörige SR-TC-Manifeste. Betroffen: `_recovery_rollback.py`, `_recovery_receipts.py`, `_recovery_completion.py` und Recovery-Right-Tests.

- [ ] **AUDIT-REC-04.U:** Unterbrechungen während eigener `journal.rollback`-, Rollbackkopie-, Receipt- und Abschlussmarkerwrites prüfen. **Entscheidung:** Ist ein eindeutig gebundener eigener Teilzustand trotz intakter Quelle regulär nicht mehr fortsetzbar, oder ist die Ablehnung aufgrund des tatsächlichen Vertrags erforderlich? Kurze eigene Präfixe und fremde widersprüchliche Bytes getrennt nachweisen.

**Nur bei bestätigter Lücke:** W macht den kleinsten nachgewiesenen Fall sicher fortsetzbar; R ergänzt die weiteren bestätigten Varianten und erneute Unterbrechung; C trennt Bindungsnachweis, Wiederaufnahme und Konfliktklassifikation. **Abnahme:** Der erneute explizite Aufruf erreicht die gebundene Basis oder das belegte Vollziel ohne zweiten Fachwrite; Originalbeweise bleiben erhalten, fremde beziehungsweise ungebundene Bytes bleiben Blocker. Die bedingten Positionen heißen `AUDIT-REC-04.W/R/C` und werden erst nach U als konkrete offene Commitfolge eingetragen. Die umfassende Fault-Injection-Matrix aus 5.v wird nicht vorgezogen.

### AUDIT-REC-05 – unveröffentlichter Discard nach echtem Neustart

**Detailauditpunkt, kein bestätigter Fehler; Voraussetzung:** AUDIT-REC-01 bis 04. **Bezug:** 5.p.W/R; SR-REQ-0257/0262/0458; SR-VER-0019/0031; SR-TC-0257/0262/0458; §10.7 und Anhang C.3. Betroffen: `recovery.py`, `_recovery_inputs.py` und die vorhandenen Discardtests.

- [ ] **AUDIT-REC-05.U:** Building/Prepared in einem Prozess erzeugen und den Folgeprozess ausschließlich mit persistenten Eingaben starten. **Entscheidung:** Woher kommt der unabhängige `PublicationPreflight`, wie ist dessen vollständige Basisinventur gebunden und welche bereits vorgesehene öffentliche Integration rekonstruiert ihn? Ein zwischen Tests weitergereichtes Speicherobjekt genügt nicht. Einen tatsächlich später geplanten Adapter mit genauer Planposition belegen; ein für 5.p bereits nötiger Nachweis bleibt andernfalls offene Nacharbeit.

**Nur bei bestätigter bereits fälliger Lücke:** `AUDIT-REC-05.W/R/C` konkretisieren. W ermöglicht einen belegten expliziten Neustart-/Discardfall; R behandelt beide unveröffentlichten Zustände und bestätigte unterbrochene Vorbereitungen; C trennt Nachweisrekonstruktion, Diagnose und Mutation. **Abnahme:** Unveränderte vollständige Basis und null Veröffentlichungen erlauben Discard unter Beweiserhalt; Publikation, Basisabweichung oder unzureichende Eingaben verhindern ihn. Kein automatischer Preflight oder Vollquellen-Restore.

### AUDIT-CONTRACT-01 – aktuelle maschinenlesbare Selbstbeschreibung

**F05; Voraussetzung:** Recovery-Nacharbeiten entschieden und bestätigte Lücken behoben. **Bezug:** 1.i/1.n/2.q; SR-REQ-0194/0376/0392; SR-VER-0013/0027; zugehörige SR-TC-Manifeste. Betroffen: `_metadata.py`, `runtime/identity.py`, `cli/capabilities.py`, `model/versions.py`; `test_identity.py`, `test_capabilities.py`.

- [ ] **AUDIT-CONTRACT-01.W:** Die bereits verfügbare Schemaunterstützung korrekt in Version-/Capabilities-Verträgen veröffentlichen. **Abnahme:** Vorhandene Artefaktschemas werden nicht mehr als leere Schemaunterstützung beschrieben; Testoracles prüfen den real implementierten Umfang.
- [ ] **AUDIT-CONTRACT-01.R:** Die Reichweite von Bibliotheksfähigkeit, abrufbarem Schema und ausführbarem CLI-Befehl aus den bestehenden Verträgen bestimmen, insbesondere für SRX. **Abnahme:** Alle Angaben widerspruchsfrei; keine Werbung für noch nicht verfügbare Produktbefehle. Erforderliche Korrekturen bleiben innerhalb vorhandener Fähigkeiten; die Agentenintegration 18.m wird nicht vorgezogen.
- [ ] **AUDIT-CONTRACT-01.C:** Quellen der Versions-/Fähigkeitsangaben konsolidieren. **Abnahme:** Dieselben fachlichen Listen, Werte und Ablehnungsgrenzen wie nach R, ohne neue Abhängigkeit des portablen Core.

### AUDIT-CONTRACT-02 – vorhandenes Change-Plan-Schema im Katalog

**F06; Voraussetzung:** AUDIT-CONTRACT-01. **Bezug:** 2.q/5.a; SR-REQ-0377/0378; SR-VER-0027; SR-TC-0377/0378. Betroffen: `changes/schema.py`, `changes/plan_contract.py`, `model/schema_sources.py`, `schema_identity.py`, `schema_catalog.py`; `test_schema_catalog.py`.

- [ ] **AUDIT-CONTRACT-02.W:** Das tatsächlich verwendete `urn:specroad:schema:1.2.0:change-plan` über den bestehenden Schemakatalog anbieten. **Abnahme:** Listing und Lookup liefern den vom Change-Plan-Validator verwendeten strukturellen Vertrag.
- [ ] **AUDIT-CONTRACT-02.R:** Kennungs-/Versionsbehandlung, unabhängige zurückgegebene Schemaobjekte und alle inzwischen verfügbaren öffentlichen strukturellen Schemas abgleichen. **Abnahme:** Unbekannte Kennungen bleiben Fehler; keine veraltete oder nur deklarierte Schemafamilie wird als implementiert ausgegeben.
- [ ] **AUDIT-CONTRACT-02.C:** Katalogintegration und Schemaidentitäten strukturell bereinigen. **Abnahme:** Stabile Kennungen, Listeninhalte, validierte Daten und Fehlerverträge bleiben erhalten.

### AUDIT-VALIDATION-01 bis 03 – fällige M4-Abdeckung konkret entscheiden

**Voraussetzung:** AUDIT-CONTRACT-02. Die vorhandenen Kerne und ihre ehrlichen `unavailable`-/Teilumfangsresultate bleiben Ausgangsbasis. Fehlende zukünftige CLI-, Baseline-, Dokument-, Konfigurations- oder Evidencefunktionen werden nicht pauschal zum Fehler eines abgeschlossenen Grundlagenkerns erklärt.

- [ ] **AUDIT-VALIDATION-01.U / F07:** SR-REQ-0096, SR-VER-0007, SR-TC-0096 gegen 4.l/4.o/4.r verfolgen. `lint/core.py` und `storage/read_only.py` bieten bisher vor allem Literalprüfungen. **Entscheidung:** Für fehlende Begründung, Verifikation und Mindestbeziehungen jeweils tatsächlichen Diagnosepfad, positive/negative Verhaltensnachweise und ursprüngliche Abnahme bestimmen. Ein bestehender Approval-/Relationskern allein beweist den Lintpfad nicht. Bereits geschuldete fehlende Core-Lintdiagnosen zur Korrektur eintragen; echte spätere Integration mit konkreter offener Position belegen.
- [ ] **AUDIT-VALIDATION-02.U / F08:** SR-REQ-0086/0100, SR-VER-0007, SR-TC-0086/0100 gegen 4.o–4.r und 5.f/5.g verfolgen. Ein reales Requirementprojekt mit ausgeliefertem Softwareprofil durch die vorhandenen öffentlichen Bibliotheksgrenzen prüfen. **Entscheidung:** Tatsächliche Adapter für Sprachpolicy, Profil-SRX, Approval und Diagnoseauswertung von vertrauenswürdigen Testgates unterscheiden. `test_model_validation.py` und `test_read_only_validation.py` belegen bisher auch Nichtverfügbarkeit. Für jede fehlende Verbindung festhalten, ob sie bereits fällig oder konkret später vorgesehen ist; keine Vollvalidierung allein aus injizierten immer erfolgreichen Gates ableiten.
- [ ] **AUDIT-VALIDATION-03.U / Diagnoseaggregation:** 4.p.R und die dort zugeordneten SR-REQ-0087–0092/0098–0099 samt SR-TC-Manifeste und SR-VER-0007 prüfen. `graph/references.py` und `validation/core.py` beenden bei fehlendem Relationsziel den betreffenden Pfad. **Entscheidung:** Verlangt die bestehende Abnahme mehrere unabhängig fehlende Ziele gemeinsam, oder setzt sie einen erfolgreichen Strukturabschnitt voraus? Mehrere konkrete gleichzeitige Fehler und die strukturierte Diagnosemenge vergleichen; kein bloßes Fortsetzungsversprechen ohne Vertrag ergänzen.

**Nur für bestätigte, bereits geschuldete Lücken** konkrete `AUDIT-VALIDATION-01/02/03.W/R/C` eintragen: W liefert den kleinsten nutzbaren fehlenden Diagnose-/Adapterpfad; R vervollständigt dessen Negativ-, Mehrfachfehler-, Frische- und Ressourcenbindungen; C konsolidiert vorhandene Kerne. **Gemeinsame Abnahme:** Echte Daten ergeben die verlangten strukturierten Befunde; fehlende Voraussetzungen werden weiter ehrlich ausgewiesen, Lesen bleibt schreibfrei, bereits bestehende fachliche Grenzen werden nicht abgeschwächt. Keine vorgezogene vollständige CLI- oder spätere Produktintegration.

### AUDIT-DOC-01 und AUDIT-EVIDENCE-01 – Anweisungen und Nachweisdaten

**AUDIT-DOC-01 / F09:** Diese Planrevision ersetzt aktive überholte Testausführungsanweisungen durch Verweise auf die zentrale lokale AGENTS.md und die technische Testanleitung. Historische Bundle-/CI-Abläufe werden als historische, außer Kraft gesetzte Vorgaben kenntlich gehalten, nicht als nachträglich anders ausgeführte Tests umgeschrieben. Dies ändert weder Runner noch GitHub-Workflow. Die Abschlusskontrolle erfolgt in AUDIT-CLOSE, ohne Dokumentations- oder Darstellungstests einzuführen.

**AUDIT-EVIDENCE-01 / F10; Voraussetzung:** alle obigen Untersuchungsentscheidungen und bestätigten Korrekturen. **Bezug:** insbesondere 3.h–3.j, 4.e/4.g/4.i, 5.n; SR-REQ-0288/0412 sowie SR-TC-0241/0259/0383/0384/0385; SR-VER-0022/0029 und die jeweiligen Receipt-Nachweise.

- [ ] **AUDIT-EVIDENCE-01.W:** Überholte `scope`-/`open_items`-Angaben in SR-TC-0288 und SR-TC-0412 mit tatsächlichen Kernen und Tests abgleichen; die fehlende Beschreibung von `SR-FIX-TRANSACTION-RECEIPTS-v1` anhand ihres realen Providers ergänzen. **Abnahme:** Referenzen zeigen auf existierende fachliche Nachweise; nicht ausgeführte beziehungsweise noch unvollständige Abnahmen bleiben erkennbar offen.
- [ ] **AUDIT-EVIDENCE-01.R:** Alle von den Nacharbeiten betroffenen Requirementmanifeste, Tests und Fixturebezüge konsistent fortschreiben. **Abnahme:** Formale Sammlung und Bindung passen zur echten Testmenge; jeder Behauptung steht ihr tatsächlich geprüfter Teilumfang gegenüber. Keine pauschale Hochstufung von `partial` und keine erfundenen alten W/R/C-Erfolge.
- [ ] **AUDIT-EVIDENCE-01.C:** Gemeinsame Beschreibungen und Verweise konsolidieren, ohne Nachweisumfang oder Ausnahmen zu ändern. **Abnahme:** Inhaltliche Befundzuordnung und maschinenlesbare Katalogverträge bleiben wie nach R. Keine Tests auf Wortlaut, Markdown oder Dokumentation.

### AUDIT-CLOSE – Abschlussentscheidung vor 5.t

- [ ] Für F01 bis F10 sowie die zusätzlichen Recovery-/Diagnosefragen eine abschließende Entscheidung mit aktuellem Result-/Commitbezug dokumentieren. Bestätigte Fehler brauchen beobachtbare Verhaltensnachweise; widerlegte Verdachtsstellen brauchen ihren Gegenbeleg. Tatsächlich spätere Arbeit braucht eine genaue offene Planposition und die Begründung, warum sie keine schon fällige Abnahme ersetzt.
- [ ] Die betroffenen fachlichen Verträge nach den Korrekturen erneut prüfen, insbesondere vollständige Recoverywurzel, dauerhafte Abschlussbeweise und normaler Folgezugriff. Die tatsächlichen erfolgreichen Apply-Prüfungen anhand ihrer Results feststellen; dieses Planungsbundle belegt noch keine Reparatur.
- [ ] Aktuelle Testanweisungen auf Konsistenz zur zentralen Arbeitsregel prüfen. Historische Ausführungsaussagen und nicht verfügbare Nachweise bleiben historisch beziehungsweise offen; es werden keine vergangenen Testläufe nachträglich behauptet.
- [ ] Im Fortschrittsblock `audit_followup_status` erst nach erfüllter Abschlussentscheidung auf `closed` und `next_audit_step` auf `null` setzen. Der Produktzähler bleibt 237/885; erst der danach tatsächlich umgesetzte und abgenommene reguläre Schritt 5.t.W erhöht ihn. Solange fällige Korrekturen oder wesentliche Vertragsfragen offen sind, bleibt die Sperre bestehen.

### Rückverweise auf abgeschlossene Produktpositionen

Die Nacharbeiten präzisieren den heutigen Korrekturbedarf an diesen historischen Abschlüssen: 1.i/1.n → F05; 2.q/5.a → F06; 3.h–3.j und 4.e/4.g/4.i → F10; 4.l/4.o–4.r/5.f/5.g → F07/F08 und Diagnosefrage; 5.n/5.p–5.s → F01–F04 und Neustart-/Abschlussfragen. Die ursprünglichen Fachabnahmen und Requirementbezüge werden dadurch nicht still umdefiniert. Neue Produktanforderungen, automatische Recovery aus 5.t, die vollständige Crashmatrix aus 5.v und Vollquellen-Restore aus M15 bleiben ihren regulären Positionen vorbehalten.

## W/R/C und die Grenze jedes Commits

**W – Let it Work:** den konkret beschriebenen kleinsten nutzbaren, bereits sicheren Ausschnitt implementieren und sein Verhalten prüfen. W ist nicht absichtlich rot und darf keine scheinbar erfolgreiche Sicherheits-/Freigabeattrappe enthalten. Noch nicht unterstützte Teilfälle werden ausdrücklich zurückgewiesen. Grundlegende Sicherheits- und Datenintegritätsgrenzen werden nicht bis R verschoben.

**R – Make it Right:** denselben Ausschnitt vervollständigen; die jeweils genannten Fehlerfälle, Randbedingungen, vollständigen Mengen und Invarianten umsetzen. Kein fachlich nötiger Teil wird als bloß spätere Bereinigung aufgeschoben. W und R sind getrennte, jeweils grüne und nachvollziehbare Entwicklungsstände.

**C – Make it Clean:** die konkret genannte Struktur verbessern, ohne fachliche Verträge, Daten, Nebenwirkungen oder Testerwartungen zu verändern. Vorhandene Verhaltenstests laufen weiter; zusätzliche strukturelle Tests oder Tests auf interne Funktionsnamen sind kein Selbstzweck. Neue Anforderungen gehören nicht in C. Gibt es nach der tatsächlichen Umsetzung keinen sinnvollen Clean-Delta, wird der Plan nachvollziehbar angepasst statt einen leeren Alibi-Commit zu erfinden; nicht still einen geplanten Commit als erledigt markieren.

Für die ursprünglichen 885 Produktpositionen bleiben die Kennungen `Meilenstein.kleinbuchstabe.W|R|C`; ihre Schritte passen in a bis z, und exakte Commitnachrichten sowie absolute Positionen stehen direkt beim jeweiligen Produktcommit. Die zusätzlichen `AUDIT-*`-Kennungen und ihre Commitzuordnung sind oben geregelt. Größe und Zeilenanzahl müssen zwischen W, R und C nicht gleich sein. Die Reihenfolge lautet W, R, C, niemals alphabetisch C, R, W.

## TD-001 – Verhalten testen, nicht Ausgabe oder Dokumentation

Automatisierte Oracles sind fachliche Rückgabewerte, Exitcodes, Zustandsübergänge, tatsächliche Dateiwirkungen, unveränderte Originalbytes, Idempotenz, vollständige Ergebnis-/Pflichtmengen, Recovery, Ressourcenverbrauch und maschinenlesbare Verträge. Exaktheitsvektoren für JCS, Schemas, Hashdomänen, ZIP, CSV/NDJSON/ReqIF oder JSON-Reports sind erlaubt, soweit die Bytes selbst ein fachlicher Austausch-/Integritätsvertrag sind. Ein JSON-Resultat wird normalerweise geparst und fachlich geprüft, nicht wegen seiner Einrückung verglichen.

**Ausgeschlossen:** Tests auf Konsolenformulierungen, Farben, ANSI-Sequenzen, Symbole, Emojis, visuelle Reihenfolge, Tabellenlayout, Spinner, Ticker, Fortschrittsdarstellung, Pretty-/Helptext, HTML-/Markdown-Darstellung, Snapshot-/Golden-Files solcher Darstellung sowie Dokumentations-, Markdown-Lint-, Linkchecker- und Doctests. Auch ein Test, der nur die Vollständigkeit dieses Plans oder einer README behauptet, wird nicht in die Produktsuite aufgenommen. Hersteller-/Paketlizenz- und Payloadinventuren als tatsächliche Lieferdaten sind davon zu unterscheiden.

Fachliche Dokumentmodelle, vollständige ausgewählte Daten und sichere Verarbeitung von Text sind weiterhin testbar. Renderer implementieren die spezifizierten Formate, aber ihre erzeugte menschliche Darstellung wird nicht zum Testorakel. Sicherheitsprüfungen beobachten Rechte, tatsächliche unerlaubte Ausführung oder Dateizugriffe; sie werden nicht als kosmetische Output-Snapshots verkleidet. Ein manueller visueller Durchgang ist möglich und bleibt als solcher erkennbar.

**Explizite Spezifikationsabweichung:** SR-REQ-0215 wird nur für Verhalten und echte maschinenlesbare Golden-Vektoren umgesetzt. Der Output-Golden-Anteil von SR-REQ-0472 und die entsprechenden Darstellungsanteile unter anderem in SR-SCN-0012/SR-E2E-0012, SR-SCN-0019 und SR-SCN-0023 werden nach Nutzerentscheidung nicht automatisiert getestet. Dasselbe gilt für reine Dokumentationsnachweise. Die universellen Evidence-/Vollständigkeitsregeln SR-REQ-0491 bis SR-REQ-0494 und SR-REQ-0500 dürfen diese Ausnahme nicht über grüne Dummytests wieder einführen. Der Katalog hält solche Anteile explizit als `not_automated_by_user_policy: TD-001` fest, nicht als passed. Gemischte Requirements behalten ihre tatsächlich testbaren Verhaltensanteile. Der finale Bericht darf deshalb keine unveränderte, lückenlose Original-Spezifikationsabnahme ohne Erwähnung von TD-001 behaupten.

Die CLI wird dennoch von Anfang an **farbig, übersichtlich und ansprechend** umgesetzt: austauschbare Präsentationsschicht, deutlich erkennbare Phasen, fortlaufender Fortschritt, klare Warnungen und kompakter Abschluss. Es gibt keinen nachträglichen Riesenschritt, der sämtliche Bedienbarkeit erst am Ende erzeugt. Terminalbreite, TTY-/Plain-Modus, NO_COLOR und quiet werden bei der Implementierung berücksichtigt, aber ihre Darstellung nicht automatisiert festgeschrieben.

## TD-002 – parallele Volltests, serieller Bundle-Abschluss und manuelle GitHub-CI

Die Nutzerentscheidung vom 2. Oktober 2026 ersetzt die frühere Testauswahl und
CI-Auslösung. Die aktualisierte Ergänzung vom 3. Oktober 2026 verlangt lokale
Paralleltests, parallele Apply-Volltests und einen zusätzlichen seriellen Lauf
beim letzten Bundle-Zustand. Ihre operative Pflege erfolgt zentral in der lokalen AGENTS.md
des Codex-Arbeitsbereichs; ausführbare Aufrufe und Infrastruktur beschreibt
[Testing.md](../development/Testing.md), den manuellen Workflow
[Bundle_CI.md](../development/Bundle_CI.md). Dieser Plan enthält die fachlichen
Abnahmen und die expliziten Spezifikationsausnahmen aus TD-001.

Historische Testauswahl-/CI-Angaben in den folgenden abgeschlossenen Abschnitten
dokumentieren ausschließlich den damaligen Auftrag oder Ablauf. Sie sind keine
aktuellen Apply-Regeln und verlangen weder Teiltests anstelle der verbindlichen
Volltests noch automatische oder serielle GitHub-Läufe. Die frühere Fünferregel
bleibt aufgehoben. Kein historischer Text ersetzt tatsächliche Ausführungsnachweise.

## CI-WAIT – historische Implementierung, aktive Verwendung ab Bundle 041 manuell

- [x] `CI-WAIT.a.W` – damaliger Fünferzyklus, exakte CI-Beobachtung und Result-Logtransport.
- [x] `CI-WAIT.a.R` – vollständige Evidence-Artefakte, Wiederholungen und Ausfälle absichern.
- [x] `CI-WAIT.a.C` – GitHub-Transport, Beobachtung und Evidence-Kodierung trennen.

Die damals automatischen Aufrufe und der Fünferzyklus sind durch die neue TD-002
abgelöst. Bestehende read-only Observer bleiben für ausdrücklich angeforderte
manuelle Full-Runs und historische Recovery erhalten. Sie binden Ereignis,
Test-/Workflow-SHA, Repository, Branch, Run-ID und Attempt. Alte Push-Nachweise
verlangen einen explizit aus ihrem Result übernommenen Modus; die Bundle-Nummer
entscheidet auch beim Nachlesen nicht mehr darüber.

Manuelle CI und lokale Anwendung bleiben getrennt. Ein eigenständiger Observer
behauptet keinen erfolgreichen Pixel-Apply. Logs, Reports, Dateihashes und
Capture-/Nachweis-Vollständigkeit bleiben erhalten. Keine Rollbacks, keine
rekursiven Bundle-Aufrufe und keine erfundene Core-Anhangs-API.
Details: [CI-Nachweise](../development/CI_Wait.md).

## OFF-PLAN Bundle 041 – historischer Venv-Fix und damalige Full-Strategie

Damals zwei getrennte Änderungen mit jeweiligem gezielten Testgate vor dem Commit; diese Ausführungsregel ist durch TD-002 aufgehoben:

- `CI-VENV-RUNTIME`: `test: Basisinterpreter für isolierte Venv-Tests erhalten`.
  Frische no-pip-Venvs verwenden auf POSIX die normale symlinkbasierte Basisbindung;
  `-I -S -B` und die enge Prozessumgebung bleiben unverändert. Neue echte Venv-/
  Isolationstests, keine gelöschten oder übersprungenen Fehlerfälle.
- `CI-MANUAL-FULL`: `ci: Volltests ausschließlich manuell ausführen`.
  Damalige Vorgabe: normale Pixel-Bundles gezielt testen und pushen; Full-CI
  manuell, damals parallel + seriell + Vergleich; bindungsgeprüfte Evidence.

Produktstand unverändert 225/885, letzter Produktcommit 5.o.C, nächster 5.p.W.
Der auf Python 3.10 beobachtete Startfehler muss im nächsten bewusst gestarteten
Full-Run bestätigt korrigiert sein; vorbereitende Tests sind kein Zielsystemnachweis.
Bundle 041 startet diesen Full-Run nicht automatisch.

## 4.j.W-FIX1 – CI-Buildhash-Nachweis korrigieren (Bundle 018)

- [x] **4.j.W-FIX1** – `Fix: 4.j.W-FIX1 test(build): Profilressourcen im Buildhash-Nachweis berücksichtigen`

Der CI-Lauf für 444708919d391eba123c1f49871133eacf0349b4 zeigt in allen fünf
Python-Versionen denselben Fehler des unabhängigen Buildhash-Tests. Der Builder
bindet die in 4.j.W hinzugefügten vier Profil-JSON-Dateien ein; die Testinventur
berücksichtigte sie bisher nicht. Der Fix korrigiert die Testinventur und ergänzt
Rohbyte-/Dateimengenregressionen, ohne Builder, Produktdateien oder Hashvertrag
zu verändern. Keine Test-Skips, keine Hochstufung von Anforderungsreife.

Genau ein separat getesteter Fix-Commit; Produktfortschritt unverändert 165/885,
letzter Plan-Commit 4.m.C, nächster 4.n.W. Damals lokale Ausführung ausschließlich der
benannten Testdateien mit vier Workern; am Abschluss volle parallele GitHub-CI.
Bei Lieferressourcenänderungen sind test_identity.py und test_payload_identity.py
damals Teil der gezielten lokalen Regressionsauswahl; diese Auswahlregel ist durch TD-002 aufgehoben. Die Änderung der
abgeschlossenen Bundle-Nummer auf 18 erfolgt erst nach dem erfolgreichen Gate.
Details: [`CI_Payload_Identity_Repair.md`](../development/CI_Payload_Identity_Repair.md).

## PY310-REPAIR – OFF-PLAN-Portabilitaetskorrektur (Bundle 012)

CI-Logs von Commit `5f078a56f285ee4e5b62e45999643c75e90ba0c0`:
CPython 3.10 meldet 2 Fehler / 2.762 Erfolge; 3.11 bis 3.14 jeweils
2.764 Erfolge. Die Katalogvorpruefung ist auf allen fuenf Versionen gueltig.
Der Produktzaehler bleibt bei 150/885, naechster Plan-Commit 4.i.W.

- [x] `PY310-REPAIR.a.W`: Missing-Kopiervertrag und importfreie Mock-Zielaufloesung korrigieren.
- [x] `PY310-REPAIR.a.R`: Identitaet, verschachtelte Kopien und wirksame I/O-Sperren absichern.
- [x] `PY310-REPAIR.a.C`: Gemeinsame I/O-Testschutzfunktion extrahieren, Verhalten erhalten.

Damals lokal nur explizite Testdateien mit vier Workern; der bestehende Katalogcheck
sammelt zusaetzlich, fuehrt aber keine Vollsuite aus. Bundle 012 fordert ueber
die vorhandenen Trailer in GitHub parallel PLUS seriell und Nachweisvergleich.
Die betroffenen Tests und Python 3.10 bleiben aktiv, keine Versions-Skips.
Pruefdetails: [`Python_310_Compatibility.md`](../development/Python_310_Compatibility.md).

## CI-EVIDENCE-RETRY – OFF-PLAN-Korrektur (Bundle 022)

Der Result-Nachweis von Bundle 021 zeigt einen grünen Run 36022249397 für
`2f269d1831afa2f852b72439c6bba99b8833e072`, jedoch einen einzelnen fehlgeschlagenen
Artefaktabruf für Python 3.10 (`gh_api_exit_1`). Die Jobs und das Logarchiv sind
erfolgreich; der maschinenlesbare Bericht bleibt zu Recht unvollständig.
Der genaue externe Netzwerk-/API-Grund ist nicht aus diesem Fehlercode beweisbar.

- [x] `CI-EVIDENCE-RETRY`: Die vorhandene begrenzte Wiederholungslogik des
  Beobachters gilt auch für Artefaktliste und einzelne, identitätsgebundene
  ZIP-Downloads. Integritäts-/Reportfehler werden nicht durch Wiederholen
  verdeckt. Kein CI-Rerun und keine Ersetzung durch einen anderen Versuch.

Der Produktzähler blieb durch diesen Zwischencommit bei 174/885. Die damalige
Vorgabe sah nur neue und unmittelbar betroffene Beobachtertests vor. Details:
[`CI_Evidence_Retry.md`](../development/CI_Evidence_Retry.md).

## CI-REPAIR – OFF-PLAN-Korrektur der Testzuordnung (Bundle 011)

Am 22. September 2026 angeforderte Korrektur des gescheiterten GitHub-Laufs:
21 Referenzen nativer pytest-Funktionen in SR-TC-0295, SR-TC-0296 und
SR-TC-0523 werden auf die wirklich gesammelten IDs berichtigt. Der vorhandene
Produktstand bleibt 150/885, nächster Schritt 4.i.W. Es wird kein Produktplan-
Commit vorgezogen und keine Anforderungsreife erhöht.

Vor lokalen Teiltests und GitHub-Volltests wird die Katalogbindung durch echte
pytest-Sammlung geprüft: keine Testkörper/Fixtures und keine vollständige
lokale Testausführung. Neue Berichte benennen alle fehlenden Verweise. Der
Katalogcheck ist kein Volltestnachweis. Einzelheiten und Abnahmegrenzen:
[`CI_Catalog_Repair.md`](../development/CI_Catalog_Repair.md).

`CI-REPAIR.a.R` sichert den Abbruch vor Testkörpern, exakte Berichtsverträge
und vollständige Fehlerbeobachtungen auch bei direkter xdist-Ausführung ab.
`CI-REPAIR.a.C` trennt die stabilen Testidentitäten und Berichtsverträge von
Sammlung, Prozessstart und pytest-Hooks. Die damals verwendeten lokalen Gates
waren Teiltests; ihre Auswahlregel ist durch TD-002 aufgehoben.

## BD-001 – flexible Anzahl eigenständiger Commits pro Bundle

Die Nutzerfreigabe mehrerer Commits und W/R/C-Folgen pro Bundle gilt fortlaufend und wird in der lokalen AGENTS.md gepflegt. Die gewählte Strecke muss zum Auftrag und den tatsächlichen Abhängigkeiten dieses Plans passen. Für die Audit-Nacharbeiten gilt die vorgeschaltete Reihenfolge oben; danach folgt die reguläre Produktfolge. Bundlegröße und Produktfortschritt werden getrennt geführt.

Der Chatbot wählt eine sichere zusammenhängende Strecke ab der nächsten offenen Kennung anhand Umfang, Kopplung, Testkosten, Kontext und tatsächlicher Ausführbarkeit. Er kann mehrere Schritte gemeinsam liefern oder mitten in W/R/C nach einem grünen Commit enden. Die gewählte erste/letzte Kennung, Anzahl und die exakten Einzelmessages werden vor Auslieferung genannt. Kein Squash und keine Umnummerierung nur wegen der Bündelgröße. Verschiedene Meilensteine dürfen nur bei erfüllten vorausgehenden Gates zusammen im selben Bundle liegen.

**Technische Konsequenz für Format 1:** PatchHarbor kopiert normale Nutzdateien bereits vor dem Entrypoint in das Repository. Deshalb darf ein Mehr-Commit-Paket nicht einfach den gesamten letzten Produktstand als normale Payload vorinstallieren und danach mehrere leere oder gemischte Commits erzeugen. Commitweise Stände werden beispielsweise als inert eingebettete Patch-/Dateidaten im privat ausgeführten Entrypoint gehalten und dort einzeln materialisiert. Je Commit folgen Scopekontrolle, Verhaltenstests, Fortschrittsaktualisierung, gezieltes Staging und genau dessen Git-Commit. Alle eingebetteten Pfade bleiben genauso sicher und der zulässige Gesamtumfang wird vorher gebunden. Keine verdeckten Aufrufe von Projektcode, keine fremden Dateien und kein rekursiver PatchHarbor-Aufruf.

Bei Fehlern stoppt die Sequenz vor dem Commit des fehlerhaften Schritts. Zuvor in diesem Bundle tatsächlich grün abgeschlossene Commits bleiben erhalten; kein destruktives Rollback. Der Result-Zustand wird ausgewertet und ein gebundener FIX beziehungsweise Restauftrag erstellt. Die Aussage „bei Fehler kein Commit“ gilt für den gerade fehlgeschlagenen Commit, nicht als erfundene globale Transaktion über bereits bestätigte Commits. FIX-Commits verändern den Planzähler nicht. Auf einen noch nicht geprüften aktuellen Result-Zustand wird kein Folgepaket geraten.

**Die Planaktualisierung AUDIT-PLAN-UPDATE bleibt genau ein OFF-PLAN-Commit.** Sie verändert keine der 885 Produktpositionen und führt keine der neu geplanten Reparaturen aus.

## BN-001 – sichtbare fortlaufende Bundle-Nummer

Nutzerentscheidung vom 20. September 2026: Ab dem Bundle für `3.k.W` bis
`3.k.C` wird eine eigene laufende Bundle-Nummer geführt, beginnend mit `001`.
Sie zählt ausgelieferte nummerierte Pakete, nicht W/R/C-Commits. Der bisherige
Bestand wird nicht rückwirkend nummeriert. Bei erneuter Auslieferung derselben byteidentischen ZIP bleibt deren Nummer gleich.
Die höchste bereits ausgelieferte Nummer ist auch bei Fortsetzungsbundles zu berücksichtigen.

Der Abschlussblock der Chat-Antwort wiederholt den zutreffenden grünen, gelben oder roten Statusbalken. Bei einer Auslieferung stehen darunter `SPECRoad-PATCH-NR: NNN` und als allerletzte Zeile der tatsächliche Patch-Download-Link. SHA-256 und Backupstatus stehen davor. Bei STOP gibt es weder ein neues Paket noch einen erfundenen Download-Link. Diese Nutzerentscheidung vom 20. September 2026 ersetzt die ältere widersprechende Darstellungsregel der beigelegten statischen Chatvorlage, nicht deren Sicherheitsvertrag. Nur nach sämtlichen Gates,
allen vorgesehenen Commits und sauberem Endstand gibt der Entrypoint als seine
letzte Zeile `SPECRoad-PATCH-NR: NNN | APPLIED SUCCESSFULLY` aus. Bei einem
Abbruch darf diese Erfolgszeile nicht erscheinen. Der Fortschrittskopf hält die
letzte vollständig abgeschlossene nummerierte Bundle-Folge fest.

PatchHarbor selbst erzeugt **danach** seinen Result-Bericht und kann weitere
Terminalzeilen ausgeben. Die Kennung bestätigt den Entrypoint-Abschluss, nicht
einen erst danach möglicherweise scheiternden Result-Export. Run-Ergebnis,
Git-Stand und frisches Result bleiben die belastbaren Prüfquellen; die sichtbare
Nummer ersetzt keine SHA-256-, Repository- oder Replay-Bindung.

## Umsetzung, Pfade, Abhängigkeiten und Testgates

Die unten angegebenen Modulpfade sind konkrete vorgeschlagene Verantwortungsgrenzen, keine Pflicht zu einer Datei pro Schritt oder pro Requirement. Lokale, verhaltensneutrale Benennungs-/Zuschnittverbesserungen sind erlaubt und werden im betroffenen Planabschnitt mitgeführt. Eine neue Architektur oder fachliche Erweiterung ist keine unbemerkte Clean-Änderung. Ein Schritt umfasst jeweils Produktcode, passende Verhaltenstests und nötige Registry-/Schema-/Datenintegration; Testarbeit ist nicht auf M20 verschoben.

Die strikt lineare Commitposition ist der ausführbare Standard: jeder Commit setzt seinen unmittelbar vorhergehenden Plan-Commit und dessen tatsächlichen grünen Stand voraus. Die Meilensteingates beziehen sich nur auf die zu diesem Zeitpunkt aktivierten realen Fähigkeiten. Später geplante Adapter sind entweder nicht angeboten oder schlagen ausdrücklich als noch nicht unterstützt fehl, niemals als angeblich bestanden. Ein erster Test darf schon mit Standardbibliothek/kleinem temporären Projekt arbeiten; die gemeinsame Infrastruktur in M1 konsolidiert solche Tests, sie legitimiert kein vorheriges ungeprüftes Produktverhalten.

Wichtige Staffelung: Datenmodelle und Mehrsprachigkeit M2; Graph/Scopes und reine Diff-/Impactkerne M3; gemeinsame Validierung M4; alle normativen Writes über M5; Workunterbau M6 vor den großen Featureabläufen. Lokale/Git-Quellen M8, echte Baselinequelle M10, Bundlequelle M15. Release-Baselines sind in M10 ohne echtes Readiness-Gate blockiert und werden erst mit M12/M13 vollständig freigeschaltet. Dokument-/Viewanbieter für Verifikation und Roadmap wachsen in M12/M13 hinzu. Der sichere Archivkern entsteht für Work früh und wird in M14/M15 zu vollständigen Fachformaten ergänzt; XML-Sicherheit entsteht für Evidence in M12 und wird bei ReqIF wiederverwendet. Legacy-Originalreader werden in M16 wirklich implementiert. Der generische Analyzer und der **reale** erste Sprachadapter sind beide Pflichtumfang in M19.

Die je Schritt benannten Verhaltenstests konkretisieren dessen fachliche Abnahme; sie sind keine Auswahlregel für Apply. Für die Testausführung gilt die zentrale lokale AGENTS.md, für technische Aufrufe [Testing.md](../development/Testing.md). Ein zielruntimeabhängiger Referenznachweis erfordert die passende Plattform; ein Pixel-/aarch64-Lauf ist kein x86-64-Nachweis. Nicht verfügbare Nachweise bleiben offen. Fachliche Runtime-/Budget-/Abbruchsverträge bleiben Teil der jeweiligen Produktabnahme.

Keine unbeauftragten Tags, Releases, Pushes, externen Genehmigungen oder neuen Produktanforderungen. Kein pauschales git add -A, reset --hard oder git clean. Beabsichtigte Pfade stagen, Fremdänderungen erhalten, Exitstatus und reale Dateieffekte prüfen. Entwicklungstests dürfen Testakteure simulieren; produktive menschliche Freigaben dürfen daraus nicht abgeleitet werden.

## Meilensteinübersicht

| Nr. | Meilenstein | Schritte | Plan-Commits | Positionen |
|---:|---|---:|---:|---|
| 1 | [Projektgerüst und CLI-Grundlage](#m1) | 14 | 42 | 1–42 |
| 2 | [Kanonisches Datenmodell und Speicherung](#m2) | 17 | 51 | 43–93 |
| 3 | [Relationsgraph und fachliche Modellumfänge](#m3) | 11 | 33 | 94–126 |
| 4 | [SRX-Regelsprache, Profile und Validierung](#m4) | 18 | 54 | 127–180 |
| 5 | [Sichere Änderungen, Transaktionen und Recovery](#m5) | 22 | 66 | 181–246 |
| 6 | [Ressourcensparsame und fortsetzbare Verarbeitung](#m6) | 21 | 63 | 247–309 |
| 7 | [Authoring, Lebenszyklen und Relationsreviews](#m7) | 12 | 36 | 310–345 |
| 8 | [Abfragen, Traceability, Änderungsanalyse und Git-Vergleich](#m8) | 12 | 36 | 346–381 |
| 9 | [Produktkonfigurationen und Varianten](#m9) | 8 | 24 | 382–405 |
| 10 | [Baselines und unveränderbare Referenzstände](#m10) | 9 | 27 | 406–432 |
| 11 | [Dokumentmodell, Ansichten und Berichtserzeugung](#m11) | 18 | 54 | 433–486 |
| 12 | [Verifikation, Evidence und Quellcode-Traceability](#m12) | 20 | 60 | 487–546 |
| 13 | [Releases, Meilensteine, Aufgaben und Roadmap](#m13) | 8 | 24 | 547–570 |
| 14 | [Import und Export](#m14) | 15 | 45 | 571–615 |
| 15 | [Projektbundles und portabler Austausch](#m15) | 12 | 36 | 616–651 |
| 16 | [Schema- und Datenmigration](#m16) | 11 | 33 | 652–684 |
| 17 | [Semantischer Dreiwege-Merge](#m17) | 12 | 36 | 685–720 |
| 18 | [Proposals und kontrollierte KI-Bearbeitung](#m18) | 16 | 48 | 721–768 |
| 19 | [Analyzer-Schnittstelle und echte Spracherkennung](#m19) | 25 | 75 | 769–843 |
| 20 | [Gesamtabnahme und Release](#m20) | 14 | 42 | 844–885 |
| **Gesamt** | **20 Meilensteine** | **295** | **885** | **1–885** |

## Detaillierter Commitplan

<a id="m1"></a>
## Meilenstein 1 – Projektgerüst und CLI-Grundlage

**Ziel:** Ein schlanker ausführbarer Core und eine testbare Trennung zwischen Fachlogik und Darstellung.

**Vorgesehener Zuschnitt:** `src/specroad/cli/, src/specroad/runtime/, tests/, pyproject.toml, CI`. **Fachgrundlage:** §§ 1, 7, 11; Anhang N.

**Abschlussgate:** Modulaufruf und frühe CLI-Funktionen laufen ohne Drittpakete; die Tests prüfen Verhalten, nicht Help- oder Pretty-Texte. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-1-a"></a>
### 1.a – Core-Paket und unterstützte Python-Syntax

**Anforderungsbezug:** `SR-REQ-0223`–`SR-REQ-0225`, `SR-REQ-0229`.
**Verifikationsbezug:** `SR-VER-0017`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.a.W – Let it Work

- [x] **1.a.W** · Position **1/885** · Voraussetzung: `OFF-PLAN PLAN-SETUP (Plan im tatsächlichen Git-Stand vorhanden)`.
**Exakte Commit-Message:** `1.a.W build(core): Core-Paket und unterstützte Python-Syntax aufbauen`

**Umsetzung:** Paketstruktur und minimalen importierbaren Standardbibliotheks-Core mit Python-3.10-kompatibler Syntax anlegen.

**Verhaltensabnahme:** Core in isolierter Umgebung ohne installierte Fremdpakete importieren.

#### 1.a.R – Make it Right

- [x] **1.a.R** · Position **2/885** · Voraussetzung: `1.a.W`.
**Exakte Commit-Message:** `1.a.R build(core): Core-Paket und unterstützte Python-Syntax vervollständigen`

**Vervollständigung:** Importpfade, fehlende optionale Pakete und nicht aktivierte virtuelle Umgebungen berücksichtigen; keine Installation beim Start.

**Verhaltensabnahme:** Import und fachlicher Minimalaufruf funktionieren ohne Paketmanager oder Shellhilfen; ein manipuliertes Projekt-CWD liefert keine fremden Module. Die W-Nachweise bleiben zusätzlich grün.

#### 1.a.C – Make it Clean

- [x] **1.a.C** · Position **3/885** · Voraussetzung: `1.a.R`.
**Exakte Commit-Message:** `1.a.C refactor(core): Core-Paket und unterstützte Python-Syntax bereinigen`

**Bereinigung:** Bootstrap, Paketmetadaten und Fachmodule klar trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-b"></a>
### 1.b – Modul- und CLI-Einstieg

**Anforderungsbezug:** `SR-REQ-0209`, `SR-REQ-0226`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.b.W – Let it Work

- [x] **1.b.W** · Position **4/885** · Voraussetzung: `1.a.C`.
**Exakte Commit-Message:** `1.b.W build(core): Modul- und CLI-Einstieg aufbauen`

**Umsetzung:** Gemeinsamen Dispatcher für python -m specroad und installierten Einstieg aufbauen; Entwicklungs-Zipapp erzeugbar machen.

**Verhaltensabnahme:** Dieselbe zulässige Operation hat in den vorhandenen Aufrufformen dieselbe fachliche Wirkung und denselben Exitcode.

#### 1.b.R – Make it Right

- [x] **1.b.R** · Position **5/885** · Voraussetzung: `1.b.W`.
**Exakte Commit-Message:** `1.b.R build(core): Modul- und CLI-Einstieg vervollständigen`

**Vervollständigung:** Nichtinteraktive Fehlereingaben deterministisch beenden; portable Distribution nicht an das Entwicklungsverzeichnis binden.

**Verhaltensabnahme:** Fehlende Pflichtparameter führen zu Code 2 ohne Rückfrage und ohne Projektänderung. Die W-Nachweise bleiben zusätzlich grün.

#### 1.b.C – Make it Clean

- [x] **1.b.C** · Position **6/885** · Voraussetzung: `1.b.R`.
**Exakte Commit-Message:** `1.b.C refactor(core): Modul- und CLI-Einstieg bereinigen`

**Bereinigung:** Alle Einstiegspunkte auf genau einen anwendungsbezogenen Dispatcher reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-c"></a>
### 1.c – Command Registry und Befehlsklassen

**Anforderungsbezug:** `SR-REQ-0180`, `SR-REQ-0477`, `SR-REQ-0552`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0032`, `SR-VER-0036`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.c.W – Let it Work

- [x] **1.c.W** · Position **7/885** · Voraussetzung: `1.b.C`.
**Exakte Commit-Message:** `1.c.W feat(core): Command Registry und Befehlsklassen aufbauen`

**Umsetzung:** Deklarative Registry mit Command-ID, erlaubten Optionen, Befehlsklasse, Preflightprofil und Seiteneffektgrenzen einführen.

**Verhaltensabnahme:** Registry löst einen implementierten read_only- und einen Bootstrapbefehl auf.

#### 1.c.R – Make it Right

- [x] **1.c.R** · Position **8/885** · Voraussetzung: `1.c.W`.
**Exakte Commit-Message:** `1.c.R feat(core): Command Registry und Befehlsklassen vervollständigen`

**Vervollständigung:** Doppelte Kennungen, unzulässige Optionskombinationen und nicht implementierte Handler ablehnen; unfertige Fähigkeiten nicht als verfügbar ausweisen.

**Verhaltensabnahme:** Ungültige Registrierung beziehungsweise CLI-Kombination wird ohne Mutation zurückgewiesen. Die W-Nachweise bleiben zusätzlich grün.

#### 1.c.C – Make it Clean

- [x] **1.c.C** · Position **9/885** · Voraussetzung: `1.c.R`.
**Exakte Commit-Message:** `1.c.C refactor(core): Command Registry und Befehlsklassen bereinigen`

**Bereinigung:** Parser, Metadatenregistry und Handleraufruf aus derselben Definition speisen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-d"></a>
### 1.d – Globale Optionen und Präzedenz

**Anforderungsbezug:** `SR-REQ-0005`–`SR-REQ-0006`, `SR-REQ-0009`, `SR-REQ-0093`–`SR-REQ-0094`.
**Verifikationsbezug:** `SR-VER-0001`, `SR-VER-0007`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.d.W – Let it Work

- [x] **1.d.W** · Position **10/885** · Voraussetzung: `1.c.C`.
**Exakte Commit-Message:** `1.d.W feat(core): Globale Optionen und Präzedenz aufbauen`

**Umsetzung:** Rootauswahl, explizite Optionen und Konfigurationsherkunft als normalisierte Eingabedaten auflösen.

**Verhaltensabnahme:** Expliziter Projektpfad gewinnt gegen aufwärts gefundene Konfiguration; Herkunft ist fachlich auswertbar.

#### 1.d.R – Make it Right

- [x] **1.d.R** · Position **11/885** · Voraussetzung: `1.d.W`.
**Exakte Commit-Message:** `1.d.R feat(core): Globale Optionen und Präzedenz vervollständigen`

**Vervollständigung:** Fail-Schwelle, strict und unzulässige Optionen pro Command behandeln; strict startet keinen Analyzer.

**Verhaltensabnahme:** Falscher Root, falsche Option und Schwellwertwechsel liefern passende Statuswerte ohne heimliche Initialisierung. Die W-Nachweise bleiben zusätzlich grün.

#### 1.d.C – Make it Clean

- [x] **1.d.C** · Position **12/885** · Voraussetzung: `1.d.R`.
**Exakte Commit-Message:** `1.d.C refactor(core): Globale Optionen und Präzedenz bereinigen`

**Bereinigung:** Optionsauflösung von späterer Profil- und Variantenkomposition entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-e"></a>
### 1.e – Ergebnisobjekte und Exitcodes

**Anforderungsbezug:** `SR-REQ-0182`–`SR-REQ-0185`, `SR-REQ-0214`, `SR-REQ-0476`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.e.W – Let it Work

- [x] **1.e.W** · Position **13/885** · Voraussetzung: `1.d.C`.
**Exakte Commit-Message:** `1.e.W feat(core): Ergebnisobjekte und Exitcodes aufbauen`

**Umsetzung:** Versioniertes Fachresultat, Diagnoseobjekte und JSON-Envelope samt zentraler Exitcodezuordnung implementieren.

**Verhaltensabnahme:** JSON wird als Datenobjekt geparst; Ergebnisstatus, Pflichtfelder und Exitcode stimmen überein.

#### 1.e.R – Make it Right

- [x] **1.e.R** · Position **14/885** · Voraussetzung: `1.e.W`.
**Exakte Commit-Message:** `1.e.R feat(core): Ergebnisobjekte und Exitcodes vervollständigen`

**Vervollständigung:** Fehler-, Sicherheits-, Konflikt-, Blocker- und Fortsetzungszustände getrennt abbilden; kein Code 8 ohne bestätigten Checkpoint.

**Verhaltensabnahme:** Statuskombinationen und maschinenlesbare Pflichtfelder werden geprüft, nicht Text, Whitespace oder Farbcodes. Die W-Nachweise bleiben zusätzlich grün.

#### 1.e.C – Make it Clean

- [x] **1.e.C** · Position **15/885** · Voraussetzung: `1.e.R`.
**Exakte Commit-Message:** `1.e.C refactor(core): Ergebnisobjekte und Exitcodes bereinigen`

**Bereinigung:** Serialisierung als dünnen Adapter um typisierte Resultate halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-f"></a>
### 1.f – Darstellungsschicht für die farbige CLI

**Anforderungsbezug:** `SR-REQ-0181`, `SR-REQ-0186`–`SR-REQ-0187`, `SR-REQ-0222`.
**Verifikationsbezug:** `SR-VER-0013`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.f.W – Let it Work

- [x] **1.f.W** · Position **16/885** · Voraussetzung: `1.e.C`.
**Exakte Commit-Message:** `1.f.W style(core): Darstellungsschicht für die farbige CLI aufbauen`

**Umsetzung:** Gemeinsame übersichtliche Pretty-Darstellung mit Phasen, Fortschritt, Status, Warnungen und kompaktem Abschluss aufbauen.

**Verhaltensabnahme:** Keine automatisierten Darstellungsprüfungen; die Fachlogik wird unabhängig von einem Renderer aufrufbar.

#### 1.f.R – Make it Right

- [x] **1.f.R** · Position **17/885** · Voraussetzung: `1.f.W`.
**Exakte Commit-Message:** `1.f.R style(core): Darstellungsschicht für die farbige CLI vervollständigen`

**Vervollständigung:** TTY, NO_COLOR, no-color und quiet umsetzen; Status zusätzlich textuell unterscheiden und Maschinendaten frei von Dekoration halten.

**Verhaltensabnahme:** Fachresultate bleiben unabhängig von der gewählten Darstellung gleich; konkrete Ausgabe und Helptexte sind kein Testorakel. Die W-Nachweise bleiben zusätzlich grün.

#### 1.f.C – Make it Clean

- [x] **1.f.C** · Position **18/885** · Voraussetzung: `1.f.R`.
**Exakte Commit-Message:** `1.f.C refactor(core): Darstellungsschicht für die farbige CLI bereinigen`

**Bereinigung:** Layout, Farbauswahl, Symbole und Fortschrittsanzeigen in einer austauschbaren Präsentationsschicht bündeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-g"></a>
### 1.g – Verhaltenstest-Infrastruktur

**Anforderungsbezug:** `SR-REQ-0215`.
**Verifikationsbezug:** `SR-VER-0016`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.g.W – Let it Work

- [x] **1.g.W** · Position **19/885** · Voraussetzung: `1.f.C`.
**Exakte Commit-Message:** `1.g.W feat(core): Verhaltenstest-Infrastruktur aufbauen`

**Umsetzung:** Testgerüst mit temporären Projekten, kontrollierter Uhr, kontrolliertem Zufall und Subprozesshelfern für Verhalten aufbauen.

**Verhaltensabnahme:** Eine kleine echte Operation wird über öffentliche Schnittstelle sowie CLI-Exitcode geprüft.

#### 1.g.R – Make it Right

- [x] **1.g.R** · Position **20/885** · Voraussetzung: `1.g.W`.
**Exakte Commit-Message:** `1.g.R feat(core): Verhaltenstest-Infrastruktur vervollständigen`

**Vervollständigung:** Keine Pretty-Snapshots, Doku-Linter, Linkchecker, Doctests oder künstlich rote spätere Featuretests einführen.

**Verhaltensabnahme:** Testisolierung, Cleanup und reproduzierbare Fixtures selbst anhand ihrer Seiteneffekte nachweisen. Die W-Nachweise bleiben zusätzlich grün.

#### 1.g.C – Make it Clean

- [x] **1.g.C** · Position **21/885** · Voraussetzung: `1.g.R`.
**Exakte Commit-Message:** `1.g.C refactor(core): Verhaltenstest-Infrastruktur bereinigen`

**Bereinigung:** Gemeinsame Testhilfen von Produktcode trennen; nur Testabhängigkeiten dürfen optional sein.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-h"></a>
### 1.h – CI und Testfallzuordnung vorbereiten

**Anforderungsbezug:** `SR-REQ-0491`–`SR-REQ-0492`.
**Verifikationsbezug:** `SR-VER-0034`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.h.W – Let it Work

- [x] **1.h.W** · Position **22/885** · Voraussetzung: `1.g.C`.
**Exakte Commit-Message:** `1.h.W build(core): CI und Testfallzuordnung vorbereiten aufbauen`

**Umsetzung:** CI für tatsächlich vorhandene Tests und versionierten Requirement-Testfall-Katalog mit stabilen SR-TC-Kennungen aufbauen.

**Verhaltensabnahme:** Ein implementierter Verhaltenstest kann seine Requirement-, Fixture- und Verifikationsbindung liefern.

#### 1.h.R – Make it Right

- [x] **1.h.R** · Position **23/885** · Voraussetzung: `1.h.W`.
**Exakte Commit-Message:** `1.h.R build(core): CI und Testfallzuordnung vorbereiten vervollständigen`

**Vervollständigung:** Noch nicht implementierte Anforderungen als offen führen; ausgenommene Darstellung/Doku nicht mit grünen Dummytests vertreten.

**Verhaltensabnahme:** Fehlende echte Evidence ist nicht passed; keine Releasefreigabe allein durch einen vollständig ausgefüllten Katalog. Die W-Nachweise bleiben zusätzlich grün.

#### 1.h.C – Make it Clean

- [x] **1.h.C** · Position **24/885** · Voraussetzung: `1.h.R`.
**Exakte Commit-Message:** `1.h.C refactor(core): CI und Testfallzuordnung vorbereiten bereinigen`

**Bereinigung:** Testkatalog, Testausführung und Evidence-Erfassung ohne doppelte fachliche Wahrheit verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-i"></a>
### 1.i – Version und Distributionsidentität

**Anforderungsbezug:** `SR-REQ-0194`, `SR-REQ-0392`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.i.W – Let it Work

- [x] **1.i.W** · Position **25/885** · Voraussetzung: `1.h.C`.
**Exakte Commit-Message:** `1.i.W build(core): Version und Distributionsidentität aufbauen`

**Umsetzung:** Version, Buildidentität, Schema-/Formatunterstützung und deklarierte Pythonmatrix maschinenlesbar bereitstellen.

**Verhaltensabnahme:** Das Ergebnis nennt die tatsächlich verwendete Runtime und den vorliegenden Build.

#### 1.i.R – Make it Right

- [x] **1.i.R** · Position **26/885** · Voraussetzung: `1.i.W`.
**Exakte Commit-Message:** `1.i.R build(core): Version und Distributionsidentität vervollständigen`

**Vervollständigung:** Deklarierte und tatsächlich getestete Matrix unterscheiden; unbekannte Buildinformationen nicht erfinden.

**Verhaltensabnahme:** Versionsdaten sind strukturell gültig und beanspruchen keine noch nicht geprüften Plattformen. Die W-Nachweise bleiben zusätzlich grün.

#### 1.i.C – Make it Clean

- [x] **1.i.C** · Position **27/885** · Voraussetzung: `1.i.R`.
**Exakte Commit-Message:** `1.i.C refactor(core): Version und Distributionsidentität bereinigen`

**Bereinigung:** Buildmetadaten an einer Stelle erzeugen und von der Pretty-Ausgabe unabhängig halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-j"></a>
### 1.j – Feste Sicherheits- und Offlinegrenze

**Anforderungsbezug:** `SR-REQ-0195`–`SR-REQ-0201`, `SR-REQ-0393`–`SR-REQ-0394`, `SR-REQ-0544`–`SR-REQ-0545`.
**Verifikationsbezug:** `SR-VER-0014`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.j.W – Let it Work

- [x] **1.j.W** · Position **28/885** · Voraussetzung: `1.i.C`.
**Exakte Commit-Message:** `1.j.W feat(core): Feste Sicherheits- und Offlinegrenze aufbauen`

**Umsetzung:** Verbotene Netzwerk-, Telemetrie-, Fremdcode- und Multi-Projektpfade im Core-Design ausschließen; sichere Rootprüfung aufbauen.

**Verhaltensabnahme:** Git-unabhängiger Minimalbetrieb läuft offline für genau einen Root.

#### 1.j.R – Make it Right

- [x] **1.j.R** · Position **29/885** · Voraussetzung: `1.j.W`.
**Exakte Commit-Message:** `1.j.R feat(core): Feste Sicherheits- und Offlinegrenze vervollständigen`

**Vervollständigung:** Traversal, externe Symlinks, Geheimnisweitergabe und dynamische Projektausführung vor Verwendung verhindern.

**Verhaltensabnahme:** Mit bösartigen Projektdaten entstehen weder externe Writes noch Netzwerk- oder Fremdcodeausführung. Die W-Nachweise bleiben zusätzlich grün.

#### 1.j.C – Make it Clean

- [x] **1.j.C** · Position **30/885** · Voraussetzung: `1.j.R`.
**Exakte Commit-Message:** `1.j.C refactor(core): Feste Sicherheits- und Offlinegrenze bereinigen`

**Bereinigung:** Sichere I/O- und Prozessgrenzen zentralisieren; später nur ausdrücklich erlaubte Git-/Workeradapter anschließen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-k"></a>
### 1.k – Lazy Bootstrap und frischer Aufrufkontext

**Anforderungsbezug:** `SR-REQ-0549`–`SR-REQ-0551`, `SR-REQ-0554`–`SR-REQ-0556`, `SR-REQ-0581`.
**Verifikationsbezug:** `SR-VER-0035`, `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.k.W – Let it Work

- [x] **1.k.W** · Position **31/885** · Voraussetzung: `1.j.C`.
**Exakte Commit-Message:** `1.k.W feat(core): Lazy Bootstrap und frischer Aufrufkontext aufbauen`

**Umsetzung:** Pro Aufruf nur aktuelle Eingaben prüfen und erforderliche Module laden; Bootstrap ohne Projekt erlauben.

**Verhaltensabnahme:** Ein neuer Prozess funktioniert ohne Session oder vorausgesetztes vorheriges Arbeitsverzeichnis.

#### 1.k.R – Make it Right

- [x] **1.k.R** · Position **32/885** · Voraussetzung: `1.k.W`.
**Exakte Commit-Message:** `1.k.R feat(core): Lazy Bootstrap und frischer Aufrufkontext vervollständigen`

**Vervollständigung:** Fehlender Root bleibt ein Fehler; Hilfe und Betriebsdiagnose laden weder Vollmodell noch Analyzer.

**Verhaltensabnahme:** Instrumentierte Modul-/Dateizugriffe zeigen keinen Vollscan oder externen Prozess im Minimalstart. Die W-Nachweise bleiben zusätzlich grün.

#### 1.k.C – Make it Clean

- [x] **1.k.C** · Position **33/885** · Voraussetzung: `1.k.R`.
**Exakte Commit-Message:** `1.k.C refactor(core): Lazy Bootstrap und frischer Aufrufkontext bereinigen`

**Bereinigung:** Kontextaufbau und fachliche Laufzeitdienste als getrennte Abhängigkeiten injizieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-l"></a>
### 1.l – CLI-Integrationsbasis und Aliasregeln

**Anforderungsbezug:** `SR-REQ-0190`, `SR-REQ-0227`, `SR-REQ-0505`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0018`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.l.W – Let it Work

- [x] **1.l.W** · Position **34/885** · Voraussetzung: `1.k.C`.
**Exakte Commit-Message:** `1.l.W feat(core): CLI-Integrationsbasis und Aliasregeln aufbauen`

**Umsetzung:** Öffentliche Handler über strukturierte Eingaben ausführbar machen; vorhandene kompatible Aliase auf denselben Handler leiten.

**Verhaltensabnahme:** Ein unterstützter Alias erzeugt denselben normalisierten Fachauftrag wie sein Zielbefehl.

#### 1.l.R – Make it Right

- [x] **1.l.R** · Position **35/885** · Voraussetzung: `1.l.W`.
**Exakte Commit-Message:** `1.l.R feat(core): CLI-Integrationsbasis und Aliasregeln vervollständigen`

**Vervollständigung:** Nicht angebotene Aliase nicht behaupten; fehlende Eingaben beenden den Prozess ohne Interaktion.

**Verhaltensabnahme:** CLI-Integration prüft Exitcode und Wirkungen, nicht Usage-Text oder Konsolenlayout. Die W-Nachweise bleiben zusätzlich grün.

#### 1.l.C – Make it Clean

- [x] **1.l.C** · Position **36/885** · Voraussetzung: `1.l.R`.
**Exakte Commit-Message:** `1.l.C refactor(core): CLI-Integrationsbasis und Aliasregeln bereinigen`

**Bereinigung:** Keine zweite Fachimplementierung in Alias- oder Einstiegspunktcode zulassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-m"></a>
### 1.m – Maschinenlesbare Command-Beschreibung

**Anforderungsbezug:** `SR-REQ-0379`, `SR-REQ-0632`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.m.W – Let it Work

- [x] **1.m.W** · Position **37/885** · Voraussetzung: `1.l.C`.
**Exakte Commit-Message:** `1.m.W feat(core): Maschinenlesbare Command-Beschreibung aufbauen`

**Umsetzung:** command describe aus der realen Registry mit Typen, Pflichtfeldern, Ausschlüssen, Seiteneffekten und gültigem strukturiertem Beispiel erzeugen.

**Verhaltensabnahme:** Ein beschriebener tatsächlich implementierter Befehl akzeptiert den daraus gebildeten Auftrag.

#### 1.m.R – Make it Right

- [x] **1.m.R** · Position **38/885** · Voraussetzung: `1.m.W`.
**Exakte Commit-Message:** `1.m.R feat(core): Maschinenlesbare Command-Beschreibung vervollständigen`

**Vervollständigung:** Workfähigkeit, Grenzen und Checkpointalgorithmen pro Handler korrekt erklären; nicht implementierte Funktionen nicht anbieten.

**Verhaltensabnahme:** Geparste Daten stimmen mit realer Optionsannahme und Schreibwirkung überein; keine Helptext-/Dokutests. Die W-Nachweise bleiben zusätzlich grün.

#### 1.m.C – Make it Clean

- [x] **1.m.C** · Position **39/885** · Voraussetzung: `1.m.R`.
**Exakte Commit-Message:** `1.m.C refactor(core): Maschinenlesbare Command-Beschreibung bereinigen`

**Bereinigung:** Beschreibung und Parserdefinition aus einer Quelle speisen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-1-n"></a>
### 1.n – Frühe Capabilities ohne Modellscan

**Anforderungsbezug:** `SR-REQ-0376`, `SR-REQ-0381`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 1.n.W – Let it Work

- [x] **1.n.W** · Position **40/885** · Voraussetzung: `1.m.C`.
**Exakte Commit-Message:** `1.n.W feat(core): Frühe Capabilities ohne Modellscan aufbauen`

**Umsetzung:** Projektlose capabilities für tatsächlich verfügbare Formate, Versionen und Befehlsklassen aus der Registry erzeugen.

**Verhaltensabnahme:** Corefähigkeiten sind ohne Root, Netzwerk oder Analyzerimport maschinenlesbar ermittelbar.

#### 1.n.R – Make it Right

- [x] **1.n.R** · Position **41/885** · Voraussetzung: `1.n.W`.
**Exakte Commit-Message:** `1.n.R feat(core): Frühe Capabilities ohne Modellscan vervollständigen`

**Vervollständigung:** Fachliche deterministische Projektion von dynamischen Laufzeitgrenzen trennen; Featureliste wächst erst mit vorhandener Implementierung.

**Verhaltensabnahme:** Gleiche Tool-/Fachinputs ergeben identische kanonische Datenprojektion, Laufzeitdaten bleiben separat. Die W-Nachweise bleiben zusätzlich grün.

#### 1.n.C – Make it Clean

- [x] **1.n.C** · Position **42/885** · Voraussetzung: `1.n.R`.
**Exakte Commit-Message:** `1.n.C refactor(core): Frühe Capabilities ohne Modellscan bereinigen`

**Bereinigung:** Capabilities über vorhandene Registry- und Ergebnisadapter bündeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 1 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m2"></a>
## Meilenstein 2 – Kanonisches Datenmodell und Speicherung

**Ziel:** Alle 28 Typen, stabile Identität, explizite Sprache und Verbindlichkeit von Anfang an korrekt modellieren.

**Vorgesehener Zuschnitt:** `src/specroad/model/, src/specroad/storage/, schemas/, resources/`. **Fachgrundlage:** §§ 8–9; Anhänge S, U.

**Abschlussgate:** Modelle werden strikt und verlustfrei geladen; fachliche Hashes enthalten keine Runtime- oder Präsentationsdaten. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-2-a"></a>
### 2.a – Projektkonfiguration und Pfadklassen

**Anforderungsbezug:** `SR-REQ-0004`, `SR-REQ-0007`–`SR-REQ-0008`, `SR-REQ-0011`, `SR-REQ-0022`–`SR-REQ-0023`.
**Verifikationsbezug:** `SR-VER-0001`, `SR-VER-0002`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.a.W – Let it Work

- [x] **2.a.W** · Position **43/885** · Voraussetzung: `1.n.C`.
**Exakte Commit-Message:** `2.a.W feat(model): Projektkonfiguration und Pfadklassen aufbauen`

**Umsetzung:** Geschlossene Projektkonfiguration, ID-Präfix und normative/generierte/betriebliche Pfadklassen definieren.

**Verhaltensabnahme:** Ein minimales Modell lädt ausschließlich die freigegebenen normativen Ressourcen.

#### 2.a.R – Make it Right

- [x] **2.a.R** · Position **44/885** · Voraussetzung: `2.a.W`.
**Exakte Commit-Message:** `2.a.R feat(model): Projektkonfiguration und Pfadklassen vervollständigen`

**Vervollständigung:** Fremde Roots, unzulässige Präfixe und Schreibziele außerhalb managed_paths ablehnen.

**Verhaltensabnahme:** Zusätzliche Dateien unter generated oder Betriebsdaten verändern das geladene Fachmodell nicht. Die W-Nachweise bleiben zusätzlich grün.

#### 2.a.C – Make it Clean

- [x] **2.a.C** · Position **45/885** · Voraussetzung: `2.a.R`.
**Exakte Commit-Message:** `2.a.C refactor(model): Projektkonfiguration und Pfadklassen bereinigen`

**Bereinigung:** Pfadklassifikation als gemeinsame Funktion für Reader, Writer und spätere Bundles führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-b"></a>
### 2.b – Strikter JSON-Reader

**Anforderungsbezug:** `SR-REQ-0012`–`SR-REQ-0013`, `SR-REQ-0015`–`SR-REQ-0017`.
**Verifikationsbezug:** `SR-VER-0002`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.b.W – Let it Work

- [x] **2.b.W** · Position **46/885** · Voraussetzung: `2.a.C`.
**Exakte Commit-Message:** `2.b.W feat(model): Strikter JSON-Reader aufbauen`

**Umsetzung:** UTF-8-Objekte und unterstützte Schemaversionen strikt lesen; Parsepositionen verfügbar halten.

**Verhaltensabnahme:** Gültiges JSON liefert genau eine typisierte Ressource.

#### 2.b.R – Make it Right

- [x] **2.b.R** · Position **47/885** · Voraussetzung: `2.b.W`.
**Exakte Commit-Message:** `2.b.R feat(model): Strikter JSON-Reader vervollständigen`

**Vervollständigung:** Doppelschlüssel, nachgestellte Daten, unbekannte Top-Level-Felder, Nichtobjekte und ungültige Zahlen sicher zurückweisen.

**Verhaltensabnahme:** Fehlerhafte Eingaben werden ohne Teilmodell oder Dateiveränderung abgewiesen. Die W-Nachweise bleiben zusätzlich grün.

#### 2.b.C – Make it Clean

- [x] **2.b.C** · Position **48/885** · Voraussetzung: `2.b.R`.
**Exakte Commit-Message:** `2.b.C refactor(model): Strikter JSON-Reader bereinigen`

**Bereinigung:** Syntaxlesen und Modellvalidierung in klar getrennte Stufen teilen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-c"></a>
### 2.c – Typregister und gemeinsame Schemas

**Anforderungsbezug:** `SR-REQ-0014`, `SR-REQ-0038`–`SR-REQ-0040`.
**Verifikationsbezug:** `SR-VER-0002`, `SR-VER-0004`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.c.W – Let it Work

- [x] **2.c.W** · Position **49/885** · Voraussetzung: `2.b.C`.
**Exakte Commit-Message:** `2.c.W feat(model): Typregister und gemeinsame Schemas aufbauen`

**Umsetzung:** Alle 28 Artefakttypen, Präfixe und gemeinsame Pflichtfelder als versionierte Ressourcen bereitstellen.

**Verhaltensabnahme:** Jeder Kerntyp besitzt eine eindeutige Schema-/Präfixzuordnung.

#### 2.c.R – Make it Right

- [x] **2.c.R** · Position **50/885** · Voraussetzung: `2.c.W`.
**Exakte Commit-Message:** `2.c.R feat(model): Typregister und gemeinsame Schemas vervollständigen`

**Vervollständigung:** Unbekannte Typen, ungültige Pflichtwerte und unerlaubte Formatversionen ablehnen.

**Verhaltensabnahme:** Datengetriebene positive und negative Schemafälle prüfen Werte und Annahme/Ablehnung. Die W-Nachweise bleiben zusätzlich grün.

#### 2.c.C – Make it Clean

- [x] **2.c.C** · Position **51/885** · Voraussetzung: `2.c.R`.
**Exakte Commit-Message:** `2.c.C refactor(model): Typregister und gemeinsame Schemas bereinigen`

**Bereinigung:** Typdefinitionen aus einer konsistenten Registry ableiten, nicht in CLI und Reader duplizieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-d"></a>
### 2.d – Fach- und Planungstypen

**Lesevertrag dieses Schritts:** `DomainArtifact` und `domain_schema` ergänzen die gemeinsamen Felder für 13 Typen; `validation_scope=domain_fields_only`. Für die in §9.4 beschreibend benannten Felder werden `objective`, `done_criteria`, `target_date` und `reevaluation_condition` verwendet. Risiko-/Annahmenstatus bleiben nichtleere Fachlabels, da die Spezifikation dafür keine geschlossene Werteliste festlegt; numerische Wahrscheinlichkeit liegt in 0–1, alternativ bleibt eine nichtleere qualitative Einstufung erhalten. Strukturierte Semantik, Readiness-Policy, Waiver-Scope, Herkunft und Profile werden als Daten gelesen, nicht als vollständige fachliche Bewertung ausgegeben. Graphauflösung, Sprachregister, menschliche Freigaben, Done-/Evidence-Nachweise und Schreibautorisierung bleiben eigene spätere Gates. Task-Umsetzungsbeziehungen können eingehend sein; eine ausgehende `implemented_by`-Attrappe ist unzulässig. W unterstützt explizit Draftdaten; R ergänzt gespeicherte Reifegrade und deren lokale Pflichtfelder.

**Anforderungsbezug:** `SR-REQ-0041`, `SR-REQ-0049`–`SR-REQ-0050`, `SR-REQ-0118`–`SR-REQ-0120`.
**Verifikationsbezug:** `SR-VER-0004`, `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.d.W – Let it Work

- [x] **2.d.W** · Position **52/885** · Voraussetzung: `2.c.C`.
**Exakte Commit-Message:** `2.d.W feat(model): Fach- und Planungstypen aufbauen`

**Umsetzung:** Typspezifische Datenverträge für Ziele, Needs, Capabilities, Requirements, Szenarien, Entscheidungen, Risiken, Annahmen, Komponenten, Interfaces, Releases, Milestones und Tasks implementieren.

**Verhaltensabnahme:** Minimale gültige Draftdaten pro Typ laden; Implementierungs- und Verifikationsplanung bleiben getrennt.

#### 2.d.R – Make it Right

- [x] **2.d.R** · Position **53/885** · Voraussetzung: `2.d.W`.
**Exakte Commit-Message:** `2.d.R feat(model): Fach- und Planungstypen vervollständigen`

**Vervollständigung:** Pflichtfelder und zulässige Statuswerte typbezogen prüfen; Erfolgsstatus nicht aus bloßer Existenz ableiten.

**Verhaltensabnahme:** Unvollständige Daten und vermischte Statusachsen werden zurückgewiesen. Die W-Nachweise bleiben zusätzlich grün.

#### 2.d.C – Make it Clean

- [x] **2.d.C** · Position **54/885** · Voraussetzung: `2.d.R`.
**Exakte Commit-Message:** `2.d.C refactor(model): Fach- und Planungstypen bereinigen`

**Bereinigung:** Wiederverwendbare Feldtypen von typbezogenen Regeln trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-e"></a>
### 2.e – Dokument- und Nachweistypen

**Umsetzungszuschnitt:** `model/record_schemas.py` und `storage/record_artifact.py` tragen die 14 hier benannten Typen als passive, bytegetreu gelesene `record_fields_only`-Datensätze. Lokal werden Feldtypen, Referenzformen und gekoppelte gespeicherte Spezialzustände geprüft. Schemaakzeptanz und die Routing-Vorprüfung für generische Operationen sind weder Schreibautorisierung noch Nachweis einer echten Freigabe. Allgemeine Graphauflösung, Parent-/Scope-Closure, CommonMark-/SRX-Auswertung, Payload-Selbsthashes, Evidence-Bewertung und Fachtransaktionen bleiben in ihren zugeordneten späteren Meilensteinen. Abschnittseltern werden nicht aus fehlenden ausgehenden Kanten erfunden; sie sind eingehende Graphbeziehungen. Das Glossar wird nicht als zusätzlicher Typ in diesen Schritt vorgezogen.

**Anforderungsbezug:** `SR-REQ-0299`–`SR-REQ-0300`, `SR-REQ-0342`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.e.W – Let it Work

- [x] **2.e.W** · Position **55/885** · Voraussetzung: `2.d.C`.
**Exakte Commit-Message:** `2.e.W feat(model): Dokument- und Nachweistypen aufbauen`

**Umsetzung:** Datenverträge für Source, Verification, Test, Evidence, Baseline, Proposal, Issue, Document, Section, Block, View, Code-Ref, Review und Configuration vorbereiten.

**Verhaltensabnahme:** Referenzen und Payloaddaten sind ohne Ausführung späterer Fachbefehle ladbar.

#### 2.e.R – Make it Right

- [x] **2.e.R** · Position **56/885** · Voraussetzung: `2.e.W`.
**Exakte Commit-Message:** `2.e.R feat(model): Dokument- und Nachweistypen vervollständigen`

**Vervollständigung:** Spezialtypen nur nach ihrem Spezialvertrag erzeugbar machen; Schemaunterstützung ist keine Freigabe für generisches Erzeugen.

**Verhaltensabnahme:** Freie Spezialstatus-Manipulation ist ausgeschlossen; gültige gespeicherte Datensätze bleiben lesbar. Die W-Nachweise bleiben zusätzlich grün.

#### 2.e.C – Make it Clean

- [x] **2.e.C** · Position **57/885** · Voraussetzung: `2.e.R`.
**Exakte Commit-Message:** `2.e.C refactor(model): Dokument- und Nachweistypen bereinigen`

**Bereinigung:** Schemas und spätere Fachservices durch typisierte Modelle verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-f"></a>
### 2.f – Namespaced Extensions und Herkunft

**Anforderungsbezug:** `SR-REQ-0018`–`SR-REQ-0019`, `SR-REQ-0037`, `SR-REQ-0251`.
**Verifikationsbezug:** `SR-VER-0002`, `SR-VER-0003`, `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.f.W – Let it Work

- [x] **2.f.W** · Position **58/885** · Voraussetzung: `2.e.C`.
**Exakte Commit-Message:** `2.f.W feat(model): Namespaced Extensions und Herkunft aufbauen`

**Umsetzung:** Extensions, Provenienz und nicht identitätsstiftende display_id verlustfrei modellieren.

**Verhaltensabnahme:** Unbekannte zulässige Erweiterungswerte über einen Lade-/Speicherzyklus erhalten.

#### 2.f.R – Make it Right

- [x] **2.f.R** · Position **59/885** · Voraussetzung: `2.f.W`.
**Exakte Commit-Message:** `2.f.R feat(model): Namespaced Extensions und Herkunft vervollständigen`

**Vervollständigung:** Ungültige Namespaces und eine als Identität verwendete display_id zurückweisen.

**Verhaltensabnahme:** Tiefe Extensions und vorhandene Herkunft bleiben semantisch identisch. Die W-Nachweise bleiben zusätzlich grün.

#### 2.f.C – Make it Clean

- [x] **2.f.C** · Position **60/885** · Voraussetzung: `2.f.R`.
**Exakte Commit-Message:** `2.f.C refactor(model): Namespaced Extensions und Herkunft bereinigen`

**Bereinigung:** Transparente Erweiterungsdaten nicht in implizite Plugins oder Fachregeln verwandeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-g"></a>
### 2.g – Kryptografische Artefaktidentitäten

**Anforderungsbezug:** `SR-REQ-0026`–`SR-REQ-0032`, `SR-REQ-0244`–`SR-REQ-0246`, `SR-REQ-0249`, `SR-REQ-0501`, `SR-REQ-0504`, `SR-REQ-0508`.
**Verifikationsbezug:** `SR-VER-0003`, `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.g.W – Let it Work

- [x] **2.g.W** · Position **61/885** · Voraussetzung: `2.f.C`.
**Exakte Commit-Message:** `2.g.W feat(model): Kryptografische Artefaktidentitäten aufbauen`

**Umsetzung:** random128-v1 mit Standardbibliothekszufall, Crockford-Codierung und stabilen Pfaden implementieren.

**Verhaltensabnahme:** Neue IDs besitzen 128 Zufallsbits, korrekten Typ/Präfix und 26-stelligen Token.

#### 2.g.R – Make it Right

- [x] **2.g.R** · Position **62/885** · Voraussetzung: `2.g.W`.
**Exakte Commit-Message:** `2.g.R feat(model): Kryptografische Artefaktidentitäten vervollständigen`

**Vervollständigung:** Kollisionen gegen aktuelle, archivierte und reservierte IDs erneut auslosen; Identität und Schema später unveränderbar halten.

**Verhaltensabnahme:** Kontrollierter Zufall erzwingt Kollision und Retry ohne sichtbare Teiländerung oder sequentielle ID. Die W-Nachweise bleiben zusätzlich grün.

#### 2.g.C – Make it Clean

- [x] **2.g.C** · Position **63/885** · Voraussetzung: `2.g.R`.
**Exakte Commit-Message:** `2.g.C refactor(model): Kryptografische Artefaktidentitäten bereinigen`

**Bereinigung:** ID-Codec, Zufallsquelle und Reservierungsprüfung separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-h"></a>
### 2.h – Relationsidentität und Historienvergleich

**Anforderungsbezug:** `SR-REQ-0248`, `SR-REQ-0250`, `SR-REQ-0509`–`SR-REQ-0510`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.h.W – Let it Work

- [x] **2.h.W** · Position **64/885** · Voraussetzung: `2.g.C`.
**Exakte Commit-Message:** `2.h.W feat(model): Relationsidentität und Historienvergleich aufbauen`

**Umsetzung:** Unabhängige zufällige Relations-IDs und Vergleich gleicher Identitäten mit Provenienz vorbereiten.

**Verhaltensabnahme:** Zwei inhaltlich gleiche neue Relationen erhalten unabhängige Identitäten.

#### 2.h.R – Make it Right

- [x] **2.h.R** · Position **65/885** · Voraussetzung: `2.h.W`.
**Exakte Commit-Message:** `2.h.R feat(model): Relationsidentität und Historienvergleich vervollständigen`

**Vervollständigung:** Reguläre Ableitung aus Endpunkten untersagen; unabhängige Erzeugung unter gleicher ID als Konflikt klassifizieren.

**Verhaltensabnahme:** Kopie derselben Historie und echte Identitätskollision werden unterschieden. Die W-Nachweise bleiben zusätzlich grün.

#### 2.h.C – Make it Clean

- [x] **2.h.C** · Position **66/885** · Voraussetzung: `2.h.R`.
**Exakte Commit-Message:** `2.h.C refactor(model): Relationsidentität und Historienvergleich bereinigen`

**Bereinigung:** Identitätsvergleich von späterer Import-/Mergeentscheidung entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-i"></a>
### 2.i – Revisionen, Akteure und Zeitwerte

**Anforderungsbezug:** `SR-REQ-0033`–`SR-REQ-0036`.
**Verifikationsbezug:** `SR-VER-0003`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.i.W – Let it Work

- [x] **2.i.W** · Position **67/885** · Voraussetzung: `2.h.C`.
**Exakte Commit-Message:** `2.i.W feat(model): Revisionen, Akteure und Zeitwerte aufbauen`

**Umsetzung:** Positive Revisionen, Actor und UTC-Zeittypen implementieren; Metadaten als Fachinputs behandeln.

**Verhaltensabnahme:** Ein neues reguläres Artefakt beginnt bei Revision 1 mit vollständigem Akteursnachweis.

#### 2.i.R – Make it Right

- [x] **2.i.R** · Position **68/885** · Voraussetzung: `2.i.W`.
**Exakte Commit-Message:** `2.i.R feat(model): Revisionen, Akteure und Zeitwerte vervollständigen`

**Vervollständigung:** Ungültige Revisionen, Lokalzeiten und unvollständige Actorwerte ablehnen.

**Verhaltensabnahme:** Typ- und Grenzfälle verändern bestehende Ressourcen nicht. Die W-Nachweise bleiben zusätzlich grün.

#### 2.i.C – Make it Clean

- [x] **2.i.C** · Position **69/885** · Voraussetzung: `2.i.R`.
**Exakte Commit-Message:** `2.i.C refactor(model): Revisionen, Akteure und Zeitwerte bereinigen`

**Bereinigung:** Datentypen vorbereiten, Revisionsfortschreibung ausschließlich der späteren Metadatenpolicy überlassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-j"></a>
### 2.j – JCS und kanonische Hashes

**Anforderungsbezug:** `SR-REQ-0020`, `SR-REQ-0207`–`SR-REQ-0208`, `SR-REQ-0671`.
**Verifikationsbezug:** `SR-VER-0002`, `SR-VER-0015`, `SR-VER-0044`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.j.W – Let it Work

- [x] **2.j.W** · Position **70/885** · Voraussetzung: `2.i.C`.
**Exakte Commit-Message:** `2.j.W feat(model): JCS und kanonische Hashes aufbauen`

**Umsetzung:** RFC-8785-konforme kanonische JSON-Bytes und SHA-256 implementieren; originale Unicodewerte erhalten.

**Verhaltensabnahme:** Fachlich identische zulässige JSON-Werte liefern gleiche kanonische Hashes.

#### 2.j.R – Make it Right

- [x] **2.j.R** · Position **71/885** · Voraussetzung: `2.j.W`.
**Exakte Commit-Message:** `2.j.R feat(model): JCS und kanonische Hashes vervollständigen`

**Vervollständigung:** JCS-Zahlengrenzen, Schlüsselsortierung, Escapegrenzen und negative Null mit versionierten Datenvektoren abdecken.

**Verhaltensabnahme:** Nicht darstellbare Zahlen werden nicht gerundet; NFC/NFD-Fachtexte bleiben unterschiedliche Originalwerte. Die W-Nachweise bleiben zusätzlich grün.

#### 2.j.C – Make it Clean

- [x] **2.j.C** · Position **72/885** · Voraussetzung: `2.j.R`.
**Exakte Commit-Message:** `2.j.C refactor(model): JCS und kanonische Hashes bereinigen`

**Bereinigung:** Kanonisierung und Hashprojektionen von menschenlesbarer Serialisierung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-k"></a>
### 2.k – Repräsentation ohne Fachänderung

**Anforderungsbezug:** `SR-REQ-0010`, `SR-REQ-0021`, `SR-REQ-0024`–`SR-REQ-0025`.
**Verifikationsbezug:** `SR-VER-0001`, `SR-VER-0002`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.k.W – Let it Work

- [x] **2.k.W** · Position **73/885** · Voraussetzung: `2.j.C`.
**Exakte Commit-Message:** `2.k.W feat(model): Repräsentation ohne Fachänderung aufbauen`

**Umsetzung:** Menschenlesbare Normalform und generierte Kennzeichnung implementieren; Rückimport generierter Darstellungen ausschließen.

**Verhaltensabnahme:** Normalisierung erhält Werte, Revision und Fachhash; generierte Daten sind keine Fachquelle.

#### 2.k.R – Make it Right

- [x] **2.k.R** · Position **74/885** · Voraussetzung: `2.k.W`.
**Exakte Commit-Message:** `2.k.R feat(model): Repräsentation ohne Fachänderung vervollständigen`

**Vervollständigung:** Normative Originaltextbytes nicht vereinheitlichen; geschützte Originalressourcen von Normalisierung ausnehmen.

**Verhaltensabnahme:** Verhaltenstests prüfen Wert-/Hash-/Revisionsgleichheit, niemals Einrückung oder sichtbare Kennzeichnung. Die W-Nachweise bleiben zusätzlich grün.

#### 2.k.C – Make it Clean

- [x] **2.k.C** · Position **75/885** · Voraussetzung: `2.k.R`.
**Exakte Commit-Message:** `2.k.C refactor(model): Repräsentation ohne Fachänderung bereinigen`

**Bereinigung:** Pretty-JSON und normative Byte-/Wertverträge getrennt anbieten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-l"></a>
### 2.l – Ressourceninventur und Anhangsdaten

**Anforderungsbezug:** `SR-REQ-0134`–`SR-REQ-0135`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0014`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.l.W – Let it Work

- [x] **2.l.W** · Position **76/885** · Voraussetzung: `2.k.C`.
**Exakte Commit-Message:** `2.l.W feat(model): Ressourceninventur und Anhangsdaten aufbauen`

**Umsetzung:** Anhänge als sichere relative Pfade mit Medientyp, Größe und Bytehash laden; vollständige Inventur anbieten.

**Verhaltensabnahme:** Referenzierte Datei wird über ihren tatsächlichen Inhalt gebunden.

#### 2.l.R – Make it Right

- [x] **2.l.R** · Position **77/885** · Voraussetzung: `2.l.W`.
**Exakte Commit-Message:** `2.l.R feat(model): Ressourceninventur und Anhangsdaten vervollständigen`

**Vervollständigung:** Externe Symlinks, falsche Größe, fehlende Bytes und Hashabweichung abweisen.

**Verhaltensabnahme:** Manipulation eines Anhangs verändert die Bindung beziehungsweise löst den Integritätsfehler aus. Die W-Nachweise bleiben zusätzlich grün.

#### 2.l.C – Make it Clean

- [x] **2.l.C** · Position **78/885** · Voraussetzung: `2.l.R`.
**Exakte Commit-Message:** `2.l.C refactor(model): Ressourceninventur und Anhangsdaten bereinigen`

**Bereinigung:** Inventarisierung und blockweises Hashen für Baselines, Exchange und Work gemeinsam nutzbar machen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-m"></a>
### 2.m – Explizite Requirement-Verbindlichkeit

**Anforderungsbezug:** `SR-REQ-0066`–`SR-REQ-0069`, `SR-REQ-0071`, `SR-REQ-0073`–`SR-REQ-0076`, `SR-REQ-0651`–`SR-REQ-0653`, `SR-REQ-0656`.
**Verifikationsbezug:** `SR-VER-0006`, `SR-VER-0044`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.m.W – Let it Work

- [x] **2.m.W** · Position **79/885** · Voraussetzung: `2.l.C`.
**Exakte Commit-Message:** `2.m.W feat(model): Explizite Requirement-Verbindlichkeit aufbauen`

**Umsetzung:** language, normative_force, statement und strukturierte Semantik ab draft materialisieren; should verlangt Abweichungsfelder.

**Verhaltensabnahme:** Indikativsatz ohne Modalwort ist mit explizitem must gültig.

#### 2.m.R – Make it Right

- [x] **2.m.R** · Position **80/885** · Voraussetzung: `2.m.W`.
**Exakte Commit-Message:** `2.m.R feat(model): Explizite Requirement-Verbindlichkeit vervollständigen`

**Vervollständigung:** Force nicht aus Priorität, Keywords oder Detector ableiten; fehlende Sprache und leere Abweichungsangaben ablehnen.

**Verhaltensabnahme:** Jede Verpflichtungsart bleibt von Priorität unabhängig; Eingaben werden nicht umformuliert. Die W-Nachweise bleiben zusätzlich grün.

#### 2.m.C – Make it Clean

- [x] **2.m.C** · Position **81/885** · Voraussetzung: `2.m.R`.
**Exakte Commit-Message:** `2.m.C refactor(model): Explizite Requirement-Verbindlichkeit bereinigen`

**Bereinigung:** Gemeinsamen Requirement-Konstruktor für CLI, Import und Migration vorsehen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-n"></a>
### 2.n – Sprach-Tags und Offline-Register

**Anforderungsbezug:** `SR-REQ-0658`–`SR-REQ-0659`, `SR-REQ-0661`.
**Verifikationsbezug:** `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.n.W – Let it Work

- [x] **2.n.W** · Position **82/885** · Voraussetzung: `2.m.C`.
**Exakte Commit-Message:** `2.n.W feat(model): Sprach-Tags und Offline-Register aufbauen`

**Umsetzung:** BCP-47-Syntax und Registryzustand getrennt modellieren; eingefrorenen IANA-Snapshot als gebundene Ressource liefern.

**Verhaltensabnahme:** Syntaktisch gültige Tags einschließlich Private-use werden nach Registryzustand klassifiziert.

#### 2.n.R – Make it Right

- [x] **2.n.R** · Position **83/885** · Voraussetzung: `2.n.W`.
**Exakte Commit-Message:** `2.n.R feat(model): Sprach-Tags und Offline-Register vervollständigen`

**Vervollständigung:** Keine stille Makrosprachenalias-Auflösung oder Onlineaktualisierung; unbekannt ist nicht automatisch ungültig.

**Verhaltensabnahme:** Tagfälle unterscheiden Syntaxfehler, bekannte Kennzeichnung und zulässige unbekannte/private Kennzeichnung. Die W-Nachweise bleiben zusätzlich grün.

#### 2.n.C – Make it Clean

- [x] **2.n.C** · Position **84/885** · Voraussetzung: `2.n.R`.
**Exakte Commit-Message:** `2.n.C refactor(model): Sprach-Tags und Offline-Register bereinigen`

**Bereinigung:** Tagparser, Registrylookup und fachliche Sprachpolicy separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-o"></a>
### 2.o – Sprachpakete und Locale-Unabhängigkeit

**Anforderungsbezug:** `SR-REQ-0669`–`SR-REQ-0670`.
**Verifikationsbezug:** `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.o.W – Let it Work

- [x] **2.o.W** · Position **85/885** · Voraussetzung: `2.n.C`.
**Exakte Commit-Message:** `2.o.W feat(model): Sprachpakete und Locale-Unabhängigkeit aufbauen`

**Umsetzung:** Mindestlabelpakete und Sprachmetadaten als reine Ressourcen ausliefern; CLI-Locale separat halten.

**Verhaltensabnahme:** Fachmodell kann alle Mindestsprachen ohne installierte Betriebssystem-Locales verarbeiten.

#### 2.o.R – Make it Right

- [x] **2.o.R** · Position **86/885** · Voraussetzung: `2.o.W`.
**Exakte Commit-Message:** `2.o.R feat(model): Sprachpakete und Locale-Unabhängigkeit vervollständigen`

**Vervollständigung:** Unicode- und Richtungsmetadaten nicht mit Detektion oder Übersetzung verwechseln.

**Verhaltensabnahme:** Locale- und Zeitzonenwechsel verändern keine Fachwerte oder Hashes. Die W-Nachweise bleiben zusätzlich grün.

#### 2.o.C – Make it Clean

- [x] **2.o.C** · Position **87/885** · Voraussetzung: `2.o.R`.
**Exakte Commit-Message:** `2.o.C refactor(model): Sprachpakete und Locale-Unabhängigkeit bereinigen`

**Bereinigung:** Sprachlabels vollständig aus ausführbarer Fachlogik herauslösen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-p"></a>
### 2.p – Modellwurzel und Projektbindung

**Anforderungsbezug:** `SR-REQ-0393`–`SR-REQ-0394`, `SR-REQ-0413`, `SR-REQ-0544`, `SR-REQ-0562`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0029`, `SR-VER-0035`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.p.W – Let it Work

- [x] **2.p.W** · Position **88/885** · Voraussetzung: `2.o.C`.
**Exakte Commit-Message:** `2.p.W feat(model): Modellwurzel und Projektbindung aufbauen`

**Umsetzung:** Geordnete Ressourcenhashes, Scopebindung und semantische Konfigurationsprojektion zu einer Modellwurzel verbinden.

**Verhaltensabnahme:** Gleicher Fachsnapshot unter anderem absoluten Root liefert dieselbe Modellwurzel.

#### 2.p.R – Make it Right

- [x] **2.p.R** · Position **89/885** · Voraussetzung: `2.p.W`.
**Exakte Commit-Message:** `2.p.R feat(model): Modellwurzel und Projektbindung vervollständigen`

**Vervollständigung:** Betriebsdaten, Farbe, Laufzeitmesswerte und externe Workpfade ausschließen; mehrere project_id nicht mischen.

**Verhaltensabnahme:** Änderungen relevanter Ressourcen ändern die Wurzel, reine Runtimeänderungen nicht. Die W-Nachweise bleiben zusätzlich grün.

#### 2.p.C – Make it Clean

- [x] **2.p.C** · Position **90/885** · Voraussetzung: `2.p.R`.
**Exakte Commit-Message:** `2.p.C refactor(model): Modellwurzel und Projektbindung bereinigen`

**Bereinigung:** Projektion, Inventur und Hashbildung als wiederverwendbare reine Dienste führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-2-q"></a>
### 2.q – Schema-Katalog und vollständiger Schemaabruf

**Anforderungsbezug:** `SR-REQ-0377`–`SR-REQ-0378`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 2.q.W – Let it Work

- [x] **2.q.W** · Position **91/885** · Voraussetzung: `2.p.C`.
**Exakte Commit-Message:** `2.q.W feat(model): Schema-Katalog und vollständiger Schemaabruf aufbauen`

**Umsetzung:** schema list/show für sämtliche vorhandenen Artefakt-, Konfigurations-, Mapping-, Ergebnis- und Austauschschemas bereitstellen.

**Verhaltensabnahme:** Schema-ID, Version und Stabilität führen zu genau dem tatsächlich vom Validator verwendeten vollständigen Schema.

#### 2.q.R – Make it Right

- [x] **2.q.R** · Position **92/885** · Voraussetzung: `2.q.W`.
**Exakte Commit-Message:** `2.q.R feat(model): Schema-Katalog und vollständiger Schemaabruf vervollständigen`

**Vervollständigung:** Unbekannte IDs ablehnen; Beschreibungen, Defaults, Beispiele, Enums und deprecation als Vertragsdaten erhalten.

**Verhaltensabnahme:** Geparstes Schemasobjekt und tatsächliche Validierung passen zusammen; kein Doku- oder Textlayout-Oracle. Die W-Nachweise bleiben zusätzlich grün.

#### 2.q.C – Make it Clean

- [x] **2.q.C** · Position **93/885** · Voraussetzung: `2.q.R`.
**Exakte Commit-Message:** `2.q.C refactor(model): Schema-Katalog und vollständiger Schemaabruf bereinigen`

**Bereinigung:** Katalog und Validator laden dieselbe kanonische Ressource.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 2 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m3"></a>
## Meilenstein 3 – Relationsgraph und fachliche Modellumfänge

**Ziel:** Ein vollständiger typisierter Graph und ein gemeinsamer Scope-/Closurekern für alle späteren Funktionen.

**Vorgesehener Zuschnitt:** `src/specroad/graph/, src/specroad/scope/, src/specroad/model/`. **Fachgrundlage:** §§ 9.7, 10.8–10.9; Anhänge I, J.

**Abschlussgate:** Closure verliert keine Pflichtressource; unzulässige Kontrollabhängigkeiten werden nicht zu erfolgreichen Teilscopes abgeschwächt. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-3-a"></a>
### 3.a – Relationsdaten und unveränderbare Schlüssel

**Anforderungsbezug:** `SR-REQ-0052`–`SR-REQ-0053`, `SR-REQ-0418`, `SR-REQ-0453`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0021`, `SR-VER-0029`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.a.W – Let it Work

- [x] **3.a.W** · Position **94/885** · Voraussetzung: `2.q.C`.
**Exakte Commit-Message:** `3.a.W feat(graph): Relationsdaten und unveränderbare Schlüssel aufbauen`

**Umsetzung:** Relationsobjekte am Quellartefakt mit stabiler ID, Typ, Ziel und Extensions laden.

**Verhaltensabnahme:** Beziehung und ihre externen Identitäten bleiben vollständig erhalten.

#### 3.a.R – Make it Right

- [x] **3.a.R** · Position **95/885** · Voraussetzung: `3.a.W`.
**Exakte Commit-Message:** `3.a.R feat(graph): Relationsdaten und unveränderbare Schlüssel vervollständigen`

**Vervollständigung:** Direkte Updates der identitätsstiftenden Relationsfelder ablehnen.

**Verhaltensabnahme:** Gültige Metadatenänderung und verbotene Schlüsseländerung werden unterschieden. Die W-Nachweise bleiben zusätzlich grün.

#### 3.a.C – Make it Clean

- [x] **3.a.C** · Position **96/885** · Voraussetzung: `3.a.R`.
**Exakte Commit-Message:** `3.a.C refactor(graph): Relationsdaten und unveränderbare Schlüssel bereinigen`

**Bereinigung:** Relationswertmodell von Adjazenzindizes und Writeroperationen trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-b"></a>
### 3.b – Quell-Ziel-Matrix und Referenzen

**Anforderungsbezug:** `SR-REQ-0054`–`SR-REQ-0056`, `SR-REQ-0060`, `SR-REQ-0415`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.b.W – Let it Work

- [x] **3.b.W** · Position **97/885** · Voraussetzung: `3.a.C`.
**Exakte Commit-Message:** `3.b.W feat(graph): Quell-Ziel-Matrix und Referenzen aufbauen`

**Umsetzung:** Die vollständige Kernrelationsmatrix einschließlich Self-Link-Verbot als Datenvalidator implementieren.

**Verhaltensabnahme:** Zulässige Typkombinationen werden akzeptiert und Ziele aufgelöst.

#### 3.b.R – Make it Right

- [x] **3.b.R** · Position **98/885** · Voraussetzung: `3.b.W`.
**Exakte Commit-Message:** `3.b.R feat(graph): Quell-Ziel-Matrix und Referenzen vervollständigen`

**Vervollständigung:** Jede unzulässige Kombination und fehlende Referenz als Modellfehler behandeln.

**Verhaltensabnahme:** Parametrisierte Datenfälle decken die exakte Matrix und fehlende Ziele ab. Die W-Nachweise bleiben zusätzlich grün.

#### 3.b.C – Make it Clean

- [x] **3.b.C** · Position **99/885** · Voraussetzung: `3.b.R`.
**Exakte Commit-Message:** `3.b.C refactor(graph): Quell-Ziel-Matrix und Referenzen bereinigen`

**Bereinigung:** Ein einziges Matrixregister für Validation, Authoring und Import verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-c"></a>
### 3.c – Symmetrische und inverse Beziehungen

**Anforderungsbezug:** `SR-REQ-0057`–`SR-REQ-0058`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.c.W – Let it Work

- [x] **3.c.W** · Position **100/885** · Voraussetzung: `3.b.C`.
**Exakte Commit-Message:** `3.c.W feat(graph): Symmetrische und inverse Beziehungen aufbauen`

**Umsetzung:** Konflikt- und Duplikatbeziehungen kanonisch speichern; inverse Sichten berechnen.

**Verhaltensabnahme:** Beide Traversierungsrichtungen sehen dieselbe einmal gespeicherte Relation.

#### 3.c.R – Make it Right

- [x] **3.c.R** · Position **101/885** · Voraussetzung: `3.c.W`.
**Exakte Commit-Message:** `3.c.R feat(graph): Symmetrische und inverse Beziehungen vervollständigen`

**Vervollständigung:** Umordnung darf relation_id nicht ändern; doppelte normative inverse Kopien abweisen.

**Verhaltensabnahme:** Anzahl und Identität gespeicherter Relationen bleiben bei Umordnung stabil. Die W-Nachweise bleiben zusätzlich grün.

#### 3.c.C – Make it Clean

- [x] **3.c.C** · Position **102/885** · Voraussetzung: `3.c.R`.
**Exakte Commit-Message:** `3.c.C refactor(graph): Symmetrische und inverse Beziehungen bereinigen`

**Bereinigung:** Kanonisierung und inverse Projektion in kleine reine Funktionen aufteilen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-d"></a>
### 3.d – Zyklen und Dokumentpositionen

**Anforderungsbezug:** `SR-REQ-0059`, `SR-REQ-0417`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.d.W – Let it Work

- [x] **3.d.W** · Position **103/885** · Voraussetzung: `3.c.C`.
**Exakte Commit-Message:** `3.d.W feat(graph): Zyklen und Dokumentpositionen aufbauen`

**Umsetzung:** Zyklusprüfung für die vorgeschriebenen Hierarchien und Positionstypen implementieren.

**Verhaltensabnahme:** Gültige Hierarchien und Position null werden akzeptiert.

#### 3.d.R – Make it Right

- [x] **3.d.R** · Position **104/885** · Voraussetzung: `3.d.W`.
**Exakte Commit-Message:** `3.d.R feat(graph): Zyklen und Dokumentpositionen vervollständigen`

**Vervollständigung:** Direkte/indirekte Zyklen, negative Positionen und Grenzfälle deterministisch erkennen.

**Verhaltensabnahme:** Ein eingefügter Zyklus wird auch über mehrere Kanten hinweg entdeckt. Die W-Nachweise bleiben zusätzlich grün.

#### 3.d.C – Make it Clean

- [x] **3.d.C** · Position **105/885** · Voraussetzung: `3.d.R`.
**Exakte Commit-Message:** `3.d.C refactor(graph): Zyklen und Dokumentpositionen bereinigen`

**Bereinigung:** Gemeinsame Traversierung statt gesonderter zyklischer Sonderalgorithmen verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-e"></a>
### 3.e – Vollständige eingehende Indizes

**Anforderungsbezug:** `SR-REQ-0582`.
**Verifikationsbezug:** `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.e.W – Let it Work

- [x] **3.e.W** · Position **106/885** · Voraussetzung: `3.d.C`.
**Exakte Commit-Message:** `3.e.W feat(graph): Vollständige eingehende Indizes aufbauen`

**Umsetzung:** Vorwärts- und Rückwärtsindex auf vollständiger Datenbasis beziehungsweise nachweislich vollständigem Index aufbauen.

**Verhaltensabnahme:** Eingehende Beziehungen eines selektiv geladenen Artefakts werden vollständig gefunden.

#### 3.e.R – Make it Right

- [x] **3.e.R** · Position **107/885** · Voraussetzung: `3.e.W`.
**Exakte Commit-Message:** `3.e.R feat(graph): Vollständige eingehende Indizes vervollständigen`

**Vervollständigung:** Teilindizes ohne Vollständigkeitsnachweis nicht als vollständig verwenden.

**Verhaltensabnahme:** Späte Quelldateien und gelöschte Cacheeinträge führen nicht zu fehlenden Abhängigkeiten. Die W-Nachweise bleiben zusätzlich grün.

#### 3.e.C – Make it Clean

- [x] **3.e.C** · Position **108/885** · Voraussetzung: `3.e.R`.
**Exakte Commit-Message:** `3.e.C refactor(graph): Vollständige eingehende Indizes bereinigen`

**Bereinigung:** Indexaufbau und indexunabhängige Fallback-Lesepfade hinter dieselbe API stellen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-f"></a>
### 3.f – Scope-Descriptor und Seed-Mengen

**Anforderungsbezug:** `SR-REQ-0405`–`SR-REQ-0410`.
**Verifikationsbezug:** `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.f.W – Let it Work

- [x] **3.f.W** · Position **109/885** · Voraussetzung: `3.e.C`.
**Exakte Commit-Message:** `3.f.W feat(graph): Scope-Descriptor und Seed-Mengen aufbauen`

**Umsetzung:** Versionierte Descriptoren für specification, project, release, document, query und explicit definieren.

**Verhaltensabnahme:** Jede Seed-Menge entspricht dem gebundenen Selektor und ist deterministisch geordnet.

#### 3.f.R – Make it Right

- [x] **3.f.R** · Position **110/885** · Voraussetzung: `3.f.W`.
**Exakte Commit-Message:** `3.f.R feat(graph): Scope-Descriptor und Seed-Mengen vervollständigen`

**Vervollständigung:** Unbekannte Selektorfelder, Dubletten und rekursive Konfigurationshüllen abweisen.

**Verhaltensabnahme:** Derselbe Selektor liefert unabhängig von Dateisystemreihenfolge identische Seed-IDs. Die W-Nachweise bleiben zusätzlich grün.

#### 3.f.C – Make it Clean

- [x] **3.f.C** · Position **111/885** · Voraussetzung: `3.f.R`.
**Exakte Commit-Message:** `3.f.C refactor(graph): Scope-Descriptor und Seed-Mengen bereinigen`

**Bereinigung:** Selektorvalidierung von einzelnen späteren Fachresolvern trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-g"></a>
### 3.g – Starke Closure und Ressourcenbindungen

**Anforderungsbezug:** `SR-REQ-0412`.
**Verifikationsbezug:** `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.g.W – Let it Work

- [x] **3.g.W** · Position **112/885** · Voraussetzung: `3.f.C`.
**Exakte Commit-Message:** `3.g.W feat(graph): Starke Closure und Ressourcenbindungen aufbauen`

**Umsetzung:** Kleinsten Fixpunkt aus starken Relationen, Anhängen, Profilen, Regeln, Mappings und Nachweisbindungen berechnen.

**Verhaltensabnahme:** Transitive Pflichtabhängigkeiten erscheinen vollständig im Scope.

#### 3.g.R – Make it Right

- [x] **3.g.R** · Position **113/885** · Voraussetzung: `3.g.W`.
**Exakte Commit-Message:** `3.g.R feat(graph): Starke Closure und Ressourcenbindungen vervollständigen`

**Vervollständigung:** Fehlende Ressourcen nicht still ignorieren; zurückgezogene erreichte Artefakte bleiben erreichbar.

**Verhaltensabnahme:** Mehrstufige Verknüpfung und zyklisch erreichbare Graphteile enden vollständig ohne Doppelaufnahme. Die W-Nachweise bleiben zusätzlich grün.

#### 3.g.C – Make it Clean

- [x] **3.g.C** · Position **114/885** · Voraussetzung: `3.g.R`.
**Exakte Commit-Message:** `3.g.C refactor(graph): Starke Closure und Ressourcenbindungen bereinigen`

**Bereinigung:** Frontier und besuchte Identitäten so kapseln, dass M6 sie fortsetzen kann.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-h"></a>
### 3.h – Schwache Kanten und Boundary References

**Anforderungsbezug:** `SR-REQ-0416`, `SR-REQ-0483`.
**Verifikationsbezug:** `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.h.W – Let it Work

- [x] **3.h.W** · Position **115/885** · Voraussetzung: `3.g.C`.
**Exakte Commit-Message:** `3.h.W feat(graph): Schwache Kanten und Boundary References aufbauen`

**Umsetzung:** Closed- und Partial-Behandlung schwacher Relationen und vollständige Boundary-Tupel implementieren.

**Verhaltensabnahme:** Partial-Closure benennt jede ausgesparte schwache Zielbindung exakt.

#### 3.h.R – Make it Right

- [x] **3.h.R** · Position **116/885** · Voraussetzung: `3.h.W`.
**Exakte Commit-Message:** `3.h.R feat(graph): Schwache Kanten und Boundary References vervollständigen`

**Vervollständigung:** Fehlende starke Ziele nicht zu Boundaries abschwächen; falsche oder doppelte Boundaries ablehnen.

**Verhaltensabnahme:** Voll- und Teilumfang unterscheiden sich nur gemäß gewählter Grenzpolicy. Die W-Nachweise bleiben zusätzlich grün.

#### 3.h.C – Make it Clean

- [x] **3.h.C** · Position **117/885** · Voraussetzung: `3.h.R`.
**Exakte Commit-Message:** `3.h.C refactor(graph): Schwache Kanten und Boundary References bereinigen`

**Bereinigung:** Boundaryerzeugung und Referenzprüfung gemeinsam für spätere Bundleleser nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-i"></a>
### 3.i – Permanente Kontrollausschlüsse

**Anforderungsbezug:** `SR-REQ-0406`.
**Verifikationsbezug:** `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.i.W – Let it Work

- [x] **3.i.W** · Position **118/885** · Voraussetzung: `3.h.C`.
**Exakte Commit-Message:** `3.i.W feat(graph): Permanente Kontrollausschlüsse aufbauen`

**Umsetzung:** Proposal und Baseline im specification-Scope auch transitiv ausschließen.

**Verhaltensabnahme:** Normale Spezifikationsclosure bleibt von Proposal-Kontrollwrites unabhängig.

#### 3.i.R – Make it Right

- [x] **3.i.R** · Position **119/885** · Voraussetzung: `3.i.W`.
**Exakte Commit-Message:** `3.i.R feat(graph): Permanente Kontrollausschlüsse vervollständigen`

**Vervollständigung:** Starke oder closed-schwache Kontrollabhängigkeit mit SRV140/reason scope_control_dependency ablehnen.

**Verhaltensabnahme:** Ein indirekter Pfad zum Kontrollartefakt erzeugt Code 3 statt einer Modellwurzel. Die W-Nachweise bleiben zusätzlich grün.

#### 3.i.C – Make it Clean

- [x] **3.i.C** · Position **120/885** · Voraussetzung: `3.i.R`.
**Exakte Commit-Message:** `3.i.C refactor(graph): Permanente Kontrollausschlüsse bereinigen`

**Bereinigung:** Scopezulässigkeit vor jede Ressourcenaufnahme stellen, nicht nur vor Seeds.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-j"></a>
### 3.j – Scope-Hash und fachliche Vergleichsprimitiven

**Anforderungsbezug:** `SR-REQ-0113`, `SR-REQ-0115`–`SR-REQ-0116`.
**Verifikationsbezug:** `SR-VER-0008`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.j.W – Let it Work

- [x] **3.j.W** · Position **121/885** · Voraussetzung: `3.i.C`.
**Exakte Commit-Message:** `3.j.W feat(graph): Scope-Hash und fachliche Vergleichsprimitiven aufbauen`

**Umsetzung:** Scopehash sowie reine direkte Impact- und Felddiff-Kerne für sichere Change Plans bereitstellen.

**Verhaltensabnahme:** Hinzufügen, strukturierte Feldänderung und direkte Abhängigkeiten sind als Daten verfügbar.

#### 3.j.R – Make it Right

- [x] **3.j.R** · Position **122/885** · Voraussetzung: `3.j.W`.
**Exakte Commit-Message:** `3.j.R feat(graph): Scope-Hash und fachliche Vergleichsprimitiven vervollständigen`

**Vervollständigung:** Unstrukturierte Textänderung nur text_changed nennen; keine erfundene semantische Interpretation.

**Verhaltensabnahme:** Ein Textwechsel wird nicht als verstandene Timingverschärfung ausgegeben. Die W-Nachweise bleiben zusätzlich grün.

#### 3.j.C – Make it Clean

- [x] **3.j.C** · Position **123/885** · Voraussetzung: `3.j.R`.
**Exakte Commit-Message:** `3.j.C refactor(graph): Scope-Hash und fachliche Vergleichsprimitiven bereinigen`

**Bereinigung:** Primitive von der späteren Diff-/Impact-CLI und Berichtsformatierung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-3-k"></a>
### 3.k – Pflichtbeziehungen und Reviewkontexte

**Anforderungsbezug:** `SR-REQ-0061`–`SR-REQ-0063`, `SR-REQ-0065`, `SR-REQ-0514`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 3.k.W – Let it Work

- [x] **3.k.W** · Position **124/885** · Voraussetzung: `3.j.C`.
**Exakte Commit-Message:** `3.k.W feat(graph): Pflichtbeziehungen und Reviewkontexte aufbauen`

**Umsetzung:** Herkunfts-/Verifikationspflichten als Gategrundlage und relation_context_hash-v1 als reine Projektion implementieren.

**Verhaltensabnahme:** Fachinhaltswechsel ändert Kontext, reine Lifecycleänderung nicht.

#### 3.k.R – Make it Right

- [x] **3.k.R** · Position **125/885** · Voraussetzung: `3.k.W`.
**Exakte Commit-Message:** `3.k.R feat(graph): Pflichtbeziehungen und Reviewkontexte vervollständigen`

**Vervollständigung:** Profilabhängige Pflichten und sämtliche ausgeschlossenen Audit-/Statusfelder korrekt unterscheiden.

**Verhaltensabnahme:** Änderung einer fremden Relationsliste macht den Kontext nicht unbegründet stale. Die W-Nachweise bleiben zusätzlich grün.

#### 3.k.C – Make it Clean

- [x] **3.k.C** · Position **126/885** · Voraussetzung: `3.k.R`.
**Exakte Commit-Message:** `3.k.C refactor(graph): Pflichtbeziehungen und Reviewkontexte bereinigen`

**Bereinigung:** Kontextprojektion, Relationstypregeln und spätere Reviewauswahl getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 3 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m4"></a>
## Meilenstein 4 – SRX-Regelsprache, Profile und Validierung

**Ziel:** Deterministische Struktur-/Fachvalidierung und vollständige SRX-Semantik ohne ausführbaren Projektcode.

**Vorgesehener Zuschnitt:** `src/specroad/srx/, src/specroad/validation/, src/specroad/profiles/, resources/`. **Fachgrundlage:** §§ 9.8–9.10, 10.10, 12.6–12.7; Anhänge B, S, U.

**Abschlussgate:** Alle Operatorfamilien und Zahlenvektoren funktionieren; keine semantische Sprachkompetenz oder noch fehlende Prüfstufe wird behauptet. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-4-a"></a>
### 4.a – SRX-AST und Kontextgrenze

**Anforderungsbezug:** `SR-REQ-0286`–`SR-REQ-0287`, `SR-REQ-0517`.

**Umsetzungsgrenze 4.a:** Reine Python-API mit versioniertem JSON-AST; ausschließlich `literal` ist ausführbar. Alle weiteren Operatoren bleiben bis zu ihren Planschritten ausdrücklich nicht unterstützt. Vier explizite Kontextwurzeln gemäß §9.9; aktive Profile und Statistikwerte sind passive vom Aufrufer bereitgestellte Projektprojektionen. Kein neuer persistenter Profilvertrag, keine implizite Konfigurationsauflösung, kein I/O und keine vollständige SRX-Freigabe. W baut eingefrorene Daten und echte Literalauswertung; R ergänzt den strikten Rohbyte-Einlesepfad und Sicherheits-/Portabilitätsregressionen; C trennt Parser, Validator, Kontext und Auswertung ohne Vertragsänderung.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.a.W – Let it Work

- [x] **4.a.W** · Position **127/885** · Voraussetzung: `3.k.C`.
**Exakte Commit-Message:** `4.a.W feat(validation): SRX-AST und Kontextgrenze aufbauen`

**Umsetzung:** Versionierten JSON-AST mit explizitem Artefakt-/Konfigurations-/Graphkontext einlesen.

**Verhaltensabnahme:** Ein literal-Ausdruck wird in einem eingefrorenen Kontext ausgewertet.

#### 4.a.R – Make it Right

- [x] **4.a.R** · Position **128/885** · Voraussetzung: `4.a.W`.
**Exakte Commit-Message:** `4.a.R feat(validation): SRX-AST und Kontextgrenze vervollständigen`

**Vervollständigung:** Unbekannte Versionen und außerhalb der erlaubten Kontextobjekte liegende Daten ablehnen.

**Verhaltensabnahme:** Fremdcode- oder dynamische Kontextdeklarationen erzeugen keine Ausführung. Die W-Nachweise bleiben zusätzlich grün.

#### 4.a.C – Make it Clean

- [x] **4.a.C** · Position **129/885** · Voraussetzung: `4.a.R`.
**Exakte Commit-Message:** `4.a.C refactor(validation): SRX-AST und Kontextgrenze bereinigen`

**Bereinigung:** AST-Parsing, Validierung und Auswertung separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-b"></a>
### 4.b – Feldzugriff, Missing und strikte Typen

**Anforderungsbezug:** `SR-REQ-0289`–`SR-REQ-0291`, `SR-REQ-0518`–`SR-REQ-0520`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.b.W – Let it Work

- [x] **4.b.W** · Position **130/885** · Voraussetzung: `4.a.C`.
**Exakte Commit-Message:** `4.b.W feat(validation): Feldzugriff, Missing und strikte Typen aufbauen`

**Umsetzung:** RFC-6901-Felder, missing und exists samt exakter Typsemantik implementieren.

**Verhaltensabnahme:** Vorhanden, JSON-null und missing liefern unterschiedliche fachliche Werte.

#### 4.b.R – Make it Right

- [x] **4.b.R** · Position **131/885** · Voraussetzung: `4.b.W`.
**Exakte Commit-Message:** `4.b.R feat(validation): Feldzugriff, Missing und strikte Typen vervollständigen`

**Vervollständigung:** Keine implizite Konvertierung oder dynamischen Feldnamen; fehlerhafte Pointer abweisen.

**Verhaltensabnahme:** Boolean, Zahl, String und missing werden in Vergleichsgrenzfällen nicht gleichgesetzt. Die W-Nachweise bleiben zusätzlich grün.

#### 4.b.C – Make it Clean

- [x] **4.b.C** · Position **132/885** · Voraussetzung: `4.b.R`.
**Exakte Commit-Message:** `4.b.C refactor(validation): Feldzugriff, Missing und strikte Typen bereinigen`

**Bereinigung:** Pointerauflösung und Typsignaturen zentral für alle Operatoren führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-c"></a>
### 4.c – Logik und Vergleich

**Anforderungsbezug:** `SR-REQ-0288`, `SR-REQ-0294`, `SR-REQ-0522`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.c.W – Let it Work

- [x] **4.c.W** · Position **133/885** · Voraussetzung: `4.b.C`.
**Exakte Commit-Message:** `4.c.W feat(validation): Logik und Vergleich aufbauen`

**Umsetzung:** not, and, or und Vergleichsoperatoren mit stabiler Argumentreihenfolge implementieren.

**Verhaltensabnahme:** Zulässige boolesche und skalare Vergleiche ergeben den definierten Wert.

#### 4.c.R – Make it Right

- [x] **4.c.R** · Position **134/885** · Voraussetzung: `4.c.W`.
**Exakte Commit-Message:** `4.c.R feat(validation): Logik und Vergleich vervollständigen`

**Vervollständigung:** Kurzschluss verhindert die Auswertung eines nicht benötigten fehlerhaften Zweigs.

**Verhaltensabnahme:** Instrumentierte Auswertung weist Reihenfolge und Kurzschluss als Verhalten nach. Die W-Nachweise bleiben zusätzlich grün.

#### 4.c.C – Make it Clean

- [x] **4.c.C** · Position **135/885** · Voraussetzung: `4.c.R`.
**Exakte Commit-Message:** `4.c.C refactor(validation): Logik und Vergleich bereinigen`

**Bereinigung:** Gemeinsame Dispatch-/Fehlerlogik statt Operator-Sonderwege verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-d"></a>
### 4.d – Strings, Mengen und Aggregationen

**Anforderungsbezug:** `SR-REQ-0288`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.d.W – Let it Work

- [x] **4.d.W** · Position **136/885** · Voraussetzung: `4.c.C`.
**Exakte Commit-Message:** `4.d.W feat(validation): Strings, Mengen und Aggregationen aufbauen`

**Umsetzung:** in, contains, starts_with, ends_with, length und count implementieren.

**Verhaltensabnahme:** Gültige String-/Arrayoperationen liefern exakte Ergebnisse.

#### 4.d.R – Make it Right

- [x] **4.d.R** · Position **137/885** · Voraussetzung: `4.d.W`.
**Exakte Commit-Message:** `4.d.R feat(validation): Strings, Mengen und Aggregationen vervollständigen`

**Vervollständigung:** Operandentypen, leere Werte und Unicodewerte nach Anhang B behandeln.

**Verhaltensabnahme:** Randfälle liefern Werte oder präzise Typfehler ohne Localeabhängigkeit. Die W-Nachweise bleiben zusätzlich grün.

#### 4.d.C – Make it Clean

- [x] **4.d.C** · Position **138/885** · Voraussetzung: `4.d.R`.
**Exakte Commit-Message:** `4.d.C refactor(validation): Strings, Mengen und Aggregationen bereinigen`

**Bereinigung:** Wiederverwendbare typisierte Operatorbausteine schaffen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-e"></a>
### 4.e – Quantoren und Elementkontext

**Anforderungsbezug:** `SR-REQ-0292`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.e.W – Let it Work

- [x] **4.e.W** · Position **139/885** · Voraussetzung: `4.d.C`.
**Exakte Commit-Message:** `4.e.W feat(validation): Quantoren und Elementkontext aufbauen`

**Umsetzung:** any, all und none mit geordnetem lokalem Elementkontext implementieren.

**Verhaltensabnahme:** Mehrere Elemente werden unter dem korrekten Elementkontext ausgewertet.

#### 4.e.R – Make it Right

- [x] **4.e.R** · Position **140/885** · Voraussetzung: `4.e.W`.
**Exakte Commit-Message:** `4.e.R feat(validation): Quantoren und Elementkontext vervollständigen`

**Vervollständigung:** Leere Arrays, verschachtelte Quantoren und Kontextschatten nach der normativen Tabelle behandeln.

**Verhaltensabnahme:** Leere-Mengen-Oracles und verschachtelte Bindungen bleiben deterministisch. Die W-Nachweise bleiben zusätzlich grün.

#### 4.e.C – Make it Clean

- [x] **4.e.C** · Position **141/885** · Voraussetzung: `4.e.R`.
**Exakte Commit-Message:** `4.e.C refactor(validation): Quantoren und Elementkontext bereinigen`

**Bereinigung:** Quantoreniteration von AST-Rekursion entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-f"></a>
### 4.f – Begrenzte Graphoperatoren

**Anforderungsbezug:** `SR-REQ-0293`, `SR-REQ-0521`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.f.W – Let it Work

- [x] **4.f.W** · Position **142/885** · Voraussetzung: `4.e.C`.
**Exakte Commit-Message:** `4.f.W feat(validation): Begrenzte Graphoperatoren aufbauen`

**Umsetzung:** relation_count, has_relation, reachable und incoming_count über den vollständigen Graphkern auswerten.

**Verhaltensabnahme:** Richtung, Relationstyp und Tiefe beschränken die fachlich angeforderten Ergebnisse.

#### 4.f.R – Make it Right

- [x] **4.f.R** · Position **143/885** · Voraussetzung: `4.f.W`.
**Exakte Commit-Message:** `4.f.R feat(validation): Begrenzte Graphoperatoren vervollständigen`

**Vervollständigung:** Fehlende Tiefe, unvollständige Indizes und Zyklen korrekt behandeln.

**Verhaltensabnahme:** Ein durch inverse Kante erreichbares Ziel wird nicht unterschlagen; unbekannte Optionen sind Fehler. Die W-Nachweise bleiben zusätzlich grün.

#### 4.f.C – Make it Clean

- [x] **4.f.C** · Position **144/885** · Voraussetzung: `4.f.R`.
**Exakte Commit-Message:** `4.f.C refactor(validation): Begrenzte Graphoperatoren bereinigen`

**Bereinigung:** Graphzugriff über einen kleinen lesenden Auswertungskontext kapseln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-g"></a>
### 4.g – Exakte Arithmetik und Zahlenpolicy

**Anforderungsbezug:** `SR-REQ-0727`–`SR-REQ-0729`.
**Verifikationsbezug:** `SR-VER-0050`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.g.W – Let it Work

- [x] **4.g.W** · Position **145/885** · Voraussetzung: `4.f.C`.
**Exakte Commit-Message:** `4.g.W feat(validation): Exakte Arithmetik und Zahlenpolicy aufbauen`

**Umsetzung:** srx-decimal-v1 mit expliziter Präzision 34 sowie add, subtract, multiply und divide implementieren.

**Verhaltensabnahme:** Endliche exakt darstellbare Ergebnisse bleiben unverändert.

#### 4.g.R – Make it Right

- [x] **4.g.R** · Position **146/885** · Voraussetzung: `4.g.W`.
**Exakte Commit-Message:** `4.g.R feat(validation): Exakte Arithmetik und Zahlenpolicy vervollständigen`

**Vervollständigung:** Nichtterminierende Division, precision_exceeded und JCS-Roundtripverletzung getrennt abweisen; kein globaler Decimal-Kontext.

**Verhaltensabnahme:** 1/8 mit Präzision 2 und 3 sowie 1/3 mit 34 liefern die exakt spezifizierten Wert-/Fehlerklassen. Die W-Nachweise bleiben zusätzlich grün.

#### 4.g.C – Make it Clean

- [x] **4.g.C** · Position **147/885** · Voraussetzung: `4.g.R`.
**Exakte Commit-Message:** `4.g.C refactor(validation): Exakte Arithmetik und Zahlenpolicy bereinigen`

**Bereinigung:** Exakte Zahlendarstellung, Policy und JCS-Übergang als eigenständige Schichten führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-h"></a>
### 4.h – SRX-Ressourcen und Sicherheitsgrenzen

**Anforderungsbezug:** `SR-REQ-0295`–`SR-REQ-0296`, `SR-REQ-0523`.
**Verifikationsbezug:** `SR-VER-0022`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.h.W – Let it Work

- [x] **4.h.W** · Position **148/885** · Voraussetzung: `4.g.C`.
**Exakte Commit-Message:** `4.h.W feat(validation): SRX-Ressourcen und Sicherheitsgrenzen aufbauen`

**Umsetzung:** Harte AST-Strukturgrenzen von weichen Auswertungsschritten unterscheiden; Messpunkte einbauen.

**Verhaltensabnahme:** Zulässiger großer Ausdruck kann über ein Arbeitsziel hinaus vollständig ausgewertet werden.

#### 4.h.R – Make it Right

- [x] **4.h.R** · Position **149/885** · Voraussetzung: `4.h.W`.
**Exakte Commit-Message:** `4.h.R feat(validation): SRX-Ressourcen und Sicherheitsgrenzen vervollständigen`

**Vervollständigung:** Reflection, Regex, Datei/Netzwerk/Zeit/Zufall und unbekannte Operatoren vor Ausführung sperren.

**Verhaltensabnahme:** Sicherheitsfehler bleiben hart; weiches Budget wird nicht zu falschem Fachfehler. Die W-Nachweise bleiben zusätzlich grün.

#### 4.h.C – Make it Clean

- [x] **4.h.C** · Position **150/885** · Voraussetzung: `4.h.R`.
**Exakte Commit-Message:** `4.h.C refactor(validation): SRX-Ressourcen und Sicherheitsgrenzen bereinigen`

**Bereinigung:** Zählung und spätere Checkpointadapter außerhalb der Operatorsemantik halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-i"></a>
### 4.i – SRX-Diagnosen und Vektorkorpus

**Anforderungsbezug:** `SR-REQ-0297`–`SR-REQ-0298`, `SR-REQ-0730`.
**Verifikationsbezug:** `SR-VER-0022`, `SR-VER-0050`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.i.W – Let it Work

- [x] **4.i.W** · Position **151/885** · Voraussetzung: `4.h.C`.
**Exakte Commit-Message:** `4.i.W feat(validation): SRX-Diagnosen und Vektorkorpus aufbauen`

**Umsetzung:** Versionierte Operator- und Zahlen-Testvektoren einschließlich Fehlerpointer ausführen.

**Verhaltensabnahme:** Jeder Operator besitzt beobachtbare positive und negative Datenfälle.

#### 4.i.R – Make it Right

- [x] **4.i.R** · Position **152/885** · Voraussetzung: `4.i.W`.
**Exakte Commit-Message:** `4.i.R feat(validation): SRX-Diagnosen und Vektorkorpus vervollständigen`

**Vervollständigung:** Unterschiedliche Prozessdefaults und alternative Reihenfolgen dürfen die Ergebnisse nicht ändern.

**Verhaltensabnahme:** Vollständiger Anhang-U-Korpus bleibt bei verändertem Decimal-Kontext gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 4.i.C – Make it Clean

- [x] **4.i.C** · Position **153/885** · Voraussetzung: `4.i.R`.
**Exakte Commit-Message:** `4.i.C refactor(validation): SRX-Diagnosen und Vektorkorpus bereinigen`

**Bereinigung:** Gemeinsame Vektorharness nutzen; keine Ausgabe-Golden-Files einführen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-j"></a>
### 4.j – Profilressourcen und Fachprofile

**Anforderungsbezug:** `SR-REQ-0079`–`SR-REQ-0080`.
**Verifikationsbezug:** `SR-VER-0006`, `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.j.W – Let it Work

- [x] **4.j.W** · Position **154/885** · Voraussetzung: `4.i.C`.
**Exakte Commit-Message:** `4.j.W feat(validation): Profilressourcen und Fachprofile aufbauen`

**Umsetzung:** Deklarative Profile core, software-de und software-en mit Version und Hash bereitstellen.

**Verhaltensabnahme:** Fachprofile wirken auf die angegebenen Artefakte ohne globale Inhaltssprachenpflicht.

#### 4.j.R – Make it Right

- [x] **4.j.R** · Position **155/885** · Voraussetzung: `4.j.W`.
**Exakte Commit-Message:** `4.j.R feat(validation): Profilressourcen und Fachprofile vervollständigen`

**Vervollständigung:** Ausführbare Profilteile und inkompatible Versionen ablehnen.

**Verhaltensabnahme:** Profilwahl ändert Fachregeln, startet aber keinen Code und keinen Analyzer. Die W-Nachweise bleiben zusätzlich grün.

#### 4.j.C – Make it Clean

- [x] **4.j.C** · Position **156/885** · Voraussetzung: `4.j.R`.
**Exakte Commit-Message:** `4.j.C refactor(validation): Profilressourcen und Fachprofile bereinigen`

**Bereinigung:** Profilresolver und reine Profilwerte von CLI-Auswahl trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-k"></a>
### 4.k – Profilkomposition und Konflikte

**Anforderungsbezug:** `SR-REQ-0419`–`SR-REQ-0425`.
**Verifikationsbezug:** `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.k.W – Let it Work

- [x] **4.k.W** · Position **157/885** · Voraussetzung: `4.j.C`.
**Exakte Commit-Message:** `4.k.W feat(validation): Profilkomposition und Konflikte aufbauen`

**Umsetzung:** Core zuerst, CLI-Ersetzung, Vereinigungen, Schnittmengen, Regelidentitäten und Severity-Overrides umsetzen.

**Verhaltensabnahme:** Eine zulässige geordnete Kette ergibt dieselbe materialisierte Mergeprojektion und denselben Hash.

#### 4.k.R – Make it Right

- [x] **4.k.R** · Position **158/885** · Voraussetzung: `4.k.W`.
**Exakte Commit-Message:** `4.k.R feat(validation): Profilkomposition und Konflikte vervollständigen`

**Vervollständigung:** Leere Schnittmenge, Pflicht/Verbot-Konflikt, Regelhashkonflikt und abgesenkte Sicherheitsfehler blockieren.

**Verhaltensabnahme:** Jede Konfliktklasse wird ohne teilweise gültiges Modell erkannt. Die W-Nachweise bleiben zusätzlich grün.

#### 4.k.C – Make it Clean

- [x] **4.k.C** · Position **159/885** · Voraussetzung: `4.k.R`.
**Exakte Commit-Message:** `4.k.C refactor(validation): Profilkomposition und Konflikte bereinigen`

**Bereinigung:** Kompositionsregeln datenorientiert zentralisieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-l"></a>
### 4.l – Glossar und literale Lintregeln

**Anforderungsbezug:** `SR-REQ-0081`–`SR-REQ-0082`, `SR-REQ-0095`–`SR-REQ-0097`, `SR-REQ-0673`.
**Verifikationsbezug:** `SR-VER-0006`, `SR-VER-0007`, `SR-VER-0044`, `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.l.W – Let it Work

- [x] **4.l.W** · Position **160/885** · Voraussetzung: `4.k.C`.
**Exakte Commit-Message:** `4.l.W feat(validation): Glossar und literale Lintregeln aufbauen`

**Umsetzung:** Terms, verbotene Synonyme und explizite Platzhalter sprachbezogen literal prüfen.

**Verhaltensabnahme:** Definierte Begriffe und erlaubte Fachtexte passieren die passenden Regeln.

#### 4.l.R – Make it Right

- [x] **4.l.R** · Position **161/885** · Voraussetzung: `4.l.W`.
**Exakte Commit-Message:** `4.l.R feat(validation): Glossar und literale Lintregeln vervollständigen`

**Vervollständigung:** Offene Platzhalter in approved sowie undefinierte Termreferenzen diagnostizieren; keine Widerspruchs- oder Übersetzungsbehauptung.

**Verhaltensabnahme:** Ein nicht erkanntes semantisches Problem wird nicht als geprüfte Sprachqualität bezeichnet. Die W-Nachweise bleiben zusätzlich grün.

#### 4.l.C – Make it Clean

- [x] **4.l.C** · Position **162/885** · Voraussetzung: `4.l.R`.
**Exakte Commit-Message:** `4.l.C refactor(validation): Glossar und literale Lintregeln bereinigen`

**Bereinigung:** Literalregeln und menschliche Qualitätsbewertung klar trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-m"></a>
### 4.m – Sprachzulässigkeit und Paketkomposition

**Anforderungsbezug:** `SR-REQ-0660`, `SR-REQ-0662`–`SR-REQ-0663`, `SR-REQ-0665`–`SR-REQ-0668`.
**Verifikationsbezug:** `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.m.W – Let it Work

- [x] **4.m.W** · Position **163/885** · Voraussetzung: `4.l.C`.
**Exakte Commit-Message:** `4.m.W feat(validation): Sprachzulässigkeit und Paketkomposition aufbauen`

**Umsetzung:** Vollständige language-policy-v1, Basic Filtering und Sprachpaketauflösung implementieren.

**Verhaltensabnahme:** en-IN wird unter en zugelassen; projektspezifische Schweregrade greifen.

#### 4.m.R – Make it Right

- [x] **4.m.R** · Position **164/885** · Voraussetzung: `4.m.W`.
**Exakte Commit-Message:** `4.m.R feat(validation): Sprachzulässigkeit und Paketkomposition vervollständigen`

**Vervollständigung:** cmn nicht automatisch unter zh zulassen; fehlende Lintcapability als unavailable und Registerwechsel nur über Change Plan.

**Verhaltensabnahme:** Alias-, Private-use-, primary/exact- und Schwellwertfälle folgen der festgelegten Policy. Die W-Nachweise bleiben zusätzlich grün.

#### 4.m.C – Make it Clean

- [x] **4.m.C** · Position **165/885** · Voraussetzung: `4.m.R`.
**Exakte Commit-Message:** `4.m.C refactor(validation): Sprachzulässigkeit und Paketkomposition bereinigen`

**Bereinigung:** Registry, Sprachfilter und Severityentscheidung getrennt komponieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-n"></a>
### 4.n – Containerbezogene Sprachmischung

**Anforderungsbezug:** `SR-REQ-0664`.
**Verifikationsbezug:** `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.n.W – Let it Work

- [x] **4.n.W** · Position **166/885** · Voraussetzung: `4.m.C`.
**Exakte Commit-Message:** `4.n.W feat(validation): Containerbezogene Sprachmischung aufbauen`

**Umsetzung:** Exakte deklarationsbasierte Requirementmengen pro Projekt, Dokument und Abschnitt ermitteln.

**Verhaltensabnahme:** Derselbe Inhalt kann nach Containerpolicy unterschiedliche Mischungsdiagnosen auslösen.

#### 4.n.R – Make it Right

- [x] **4.n.R** · Position **167/885** · Voraussetzung: `4.n.W`.
**Exakte Commit-Message:** `4.n.R feat(validation): Containerbezogene Sprachmischung vervollständigen`

**Vervollständigung:** Referenzduplikate, Include-Dokumente und primary/exact-Modi korrekt behandeln.

**Verhaltensabnahme:** en-US/en-IN versus de-DE liefert die normativ ausgewählten Mengen, nicht Dateifund-Reihenfolgen. Die W-Nachweise bleiben zusätzlich grün.

#### 4.n.C – Make it Clean

- [x] **4.n.C** · Position **168/885** · Voraussetzung: `4.n.R`.
**Exakte Commit-Message:** `4.n.C refactor(validation): Containerbezogene Sprachmischung bereinigen`

**Bereinigung:** Mischung auf Scope-/Dokumentprojektion aufsetzen statt Texte zu detektieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-o"></a>
### 4.o – Struktur- und Modellvalidation

**Anforderungsbezug:** `SR-REQ-0083`–`SR-REQ-0086`.
**Verifikationsbezug:** `SR-VER-0007`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.o.W – Let it Work

- [x] **4.o.W** · Position **169/885** · Voraussetzung: `4.n.C`.
**Exakte Commit-Message:** `4.o.W feat(validation): Struktur- und Modellvalidation aufbauen`

**Umsetzung:** Validierungspipeline für Parsing, Schema, Typen, IDs, Referenzen, Graph, Lifecycle und registrierte Fachgates implementieren.

**Verhaltensabnahme:** Gültiges vollständiges Modell und zulässiger abhängigkeitserweiterter Teilscope bestehen.

#### 4.o.R – Make it Right

- [x] **4.o.R** · Position **170/885** · Voraussetzung: `4.o.W`.
**Exakte Commit-Message:** `4.o.R feat(validation): Struktur- und Modellvalidation vervollständigen`

**Vervollständigung:** Fehlende Fachvalidatoren nicht durch passed-Stubs ersetzen; neue Baseline-/Evidencegates später verbindlich registrieren.

**Verhaltensabnahme:** Defektes Schema, Zyklus und fehlende Pflichtreferenz verhindern ein gültiges Ziel. Die W-Nachweise bleiben zusätzlich grün.

#### 4.o.C – Make it Clean

- [x] **4.o.C** · Position **171/885** · Voraussetzung: `4.o.R`.
**Exakte Commit-Message:** `4.o.C refactor(validation): Struktur- und Modellvalidation bereinigen`

**Bereinigung:** Eine gemeinsame Pipeline für CLI, Planner und Fachadapter verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-p"></a>
### 4.p – Strukturierte Diagnosen und Fail-Policy

**Anforderungsbezug:** `SR-REQ-0087`–`SR-REQ-0092`, `SR-REQ-0098`–`SR-REQ-0099`.
**Verifikationsbezug:** `SR-VER-0007`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.p.W – Let it Work

- [x] **4.p.W** · Position **172/885** · Voraussetzung: `4.o.C`.
**Exakte Commit-Message:** `4.p.W feat(validation): Strukturierte Diagnosen und Fail-Policy aufbauen`

**Umsetzung:** Vollständiges Diagnosedatenmodell mit Ursprüngen, Pointern, Severity und fachlicher Sortierung aufbauen.

**Verhaltensabnahme:** Parsefehler liefern verfügbare Positionsdaten und strukturierte Fehlerklasse.

#### 4.p.R – Make it Right

- [x] **4.p.R** · Position **173/885** · Voraussetzung: `4.p.W`.
**Exakte Commit-Message:** `4.p.R feat(validation): Strukturierte Diagnosen und Fail-Policy vervollständigen`

**Vervollständigung:** Unbekannte IDs und mehrere gleichzeitige Fehler vollständig erhalten; Warnung erst am Fail-Schwellwert bewerten.

**Verhaltensabnahme:** Tests vergleichen Codes, Orte, Mengen und Status, keine Meldungsformulierungen oder Ausgabetexte. Die W-Nachweise bleiben zusätzlich grün.

#### 4.p.C – Make it Clean

- [x] **4.p.C** · Position **174/885** · Voraussetzung: `4.p.R`.
**Exakte Commit-Message:** `4.p.C refactor(validation): Strukturierte Diagnosen und Fail-Policy bereinigen`

**Bereinigung:** Diagnoseerzeugung, Ordnung und Präsentation entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-q"></a>
### 4.q – Requirement-Approval-Gates

**Anforderungsbezug:** `SR-REQ-0070`, `SR-REQ-0072`, `SR-REQ-0077`–`SR-REQ-0078`, `SR-REQ-0499`, `SR-REQ-0674`.
**Verifikationsbezug:** `SR-VER-0006`, `SR-VER-0034`, `SR-VER-0044`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.q.W – Let it Work

- [x] **4.q.W** · Position **175/885** · Voraussetzung: `4.p.C`.
**Exakte Commit-Message:** `4.q.W feat(validation): Requirement-Approval-Gates aufbauen`

**Umsetzung:** Formale Pflichtdaten, messbare Qualitätsfelder, Interfacegrenzen und menschliche Reviewbindung vor Freigabe prüfen.

**Verhaltensabnahme:** Vollständige formale Daten erlauben nur den dafür vorgesehenen menschlichen Freigabeschritt.

#### 4.q.R – Make it Right

- [x] **4.q.R** · Position **176/885** · Voraussetzung: `4.q.W`.
**Exakte Commit-Message:** `4.q.R feat(validation): Requirement-Approval-Gates vervollständigen`

**Vervollständigung:** Coreprüfung und Detektion nicht als menschlichen Nachweis eines einzelnen prüfbaren Sachverhalts ausgeben.

**Verhaltensabnahme:** Fehlende Verification, Herkunft oder Review verhindert approved; menschlich bestätigter Compound-Befund blockiert. Die W-Nachweise bleiben zusätzlich grün.

#### 4.q.C – Make it Clean

- [x] **4.q.C** · Position **177/885** · Voraussetzung: `4.q.R`.
**Exakte Commit-Message:** `4.q.C refactor(validation): Requirement-Approval-Gates bereinigen`

**Bereinigung:** Formale Gateprüfung und fachliche Reviewentscheidung getrennt modellieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-4-r"></a>
### 4.r – Read-only-Validation und Diagnoseausnahmen

**Anforderungsbezug:** `SR-REQ-0100`, `SR-REQ-0117`, `SR-REQ-0188`.
**Verifikationsbezug:** `SR-VER-0007`, `SR-VER-0008`, `SR-VER-0013`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 4.r.W – Let it Work

- [x] **4.r.W** · Position **178/885** · Voraussetzung: `4.q.C`.
**Exakte Commit-Message:** `4.r.W feat(validation): Read-only-Validation und Diagnoseausnahmen aufbauen`

**Umsetzung:** validate, lint und diagnosebezogene Lesepfade ohne Projektwrites nutzbar machen.

**Verhaltensabnahme:** Gültiger schreibgeschützter Root wird ohne Cacheaufbau geprüft.

#### 4.r.R – Make it Right

- [x] **4.r.R** · Position **179/885** · Voraussetzung: `4.r.W`.
**Exakte Commit-Message:** `4.r.R feat(validation): Read-only-Validation und Diagnoseausnahmen vervollständigen`

**Vervollständigung:** Recoverybedarf und Profilkonflikt schreibfrei melden; Diagnosepfade bleiben ohne regulären Modellload möglich.

**Verhaltensabnahme:** Vorher-/Nachherinventur enthält keine neuen Projekt- oder Betriebsdateien. Die W-Nachweise bleiben zusätzlich grün.

#### 4.r.C – Make it Clean

- [x] **4.r.C** · Position **180/885** · Voraussetzung: `4.r.R`.
**Exakte Commit-Message:** `4.r.C refactor(validation): Read-only-Validation und Diagnoseausnahmen bereinigen`

**Bereinigung:** Lesepipeline und spätere Writeautorisierung explizit trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 4 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m5"></a>
## Meilenstein 5 – Sichere Änderungen, Transaktionen und Recovery

**Ziel:** Jede echte Fachänderung wird gebunden, vollständig geprüft und kontrolliert veröffentlicht.

**Vorgesehener Zuschnitt:** `src/specroad/change/, src/specroad/transactions/, src/specroad/recovery/`. **Fachgrundlage:** §§ 7.1, 9.6, 10.1–10.7, 11.7; Anhänge C, K.

**Abschlussgate:** Fault-Injection beweist Basis oder vollständiges Ziel; keine Zwischenzustände werden als gültig veröffentlicht. Vollquellen-Restore wird mit M15 ergänzt. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-5-a"></a>
### 5.a – Change-Plan-Schema und Operationen

**Anforderungsbezug:** `SR-REQ-0231`, `SR-REQ-0502`–`SR-REQ-0503`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.a.W – Let it Work

- [x] **5.a.W** · Position **181/885** · Voraussetzung: `4.r.C`.
**Exakte Commit-Message:** `5.a.W feat(changes): Change-Plan-Schema und Operationen aufbauen`

**Umsetzung:** Versionierten gemeinsamen Change Plan und alle typisierten Kernoperationen definieren.

**Verhaltensabnahme:** Ein gültiger create/update-Plan lässt sich normalisieren und unverändert wieder einlesen.

#### 5.a.R – Make it Right

- [x] **5.a.R** · Position **182/885** · Voraussetzung: `5.a.W`.
**Exakte Commit-Message:** `5.a.R feat(changes): Change-Plan-Schema und Operationen vervollständigen`

**Vervollständigung:** Unbekannte Operationen und generische Umgehung spezieller Fachwrites ablehnen.

**Verhaltensabnahme:** Unzulässige Operation verändert weder Zwischenstand noch Dateien. Die W-Nachweise bleiben zusätzlich grün.

#### 5.a.C – Make it Clean

- [x] **5.a.C** · Position **183/885** · Voraussetzung: `5.a.R`.
**Exakte Commit-Message:** `5.a.C refactor(changes): Change-Plan-Schema und Operationen bereinigen`

**Bereinigung:** Planmodell und Fachoperationsadapter über ein explizites Register trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-b"></a>
### 5.b – RFC-6902 und Komfortpatches

**Anforderungsbezug:** `SR-REQ-0160`, `SR-REQ-0232`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.b.W – Let it Work

- [x] **5.b.W** · Position **184/885** · Voraussetzung: `5.a.C`.
**Exakte Commit-Message:** `5.b.W feat(changes): RFC-6902 und Komfortpatches aufbauen`

**Umsetzung:** JSON-Patch sowie set/unset nach JSON Pointer auf einem isolierten Stand auswerten.

**Verhaltensabnahme:** Gültiger Patch erzeugt exakt die geplanten Werte.

#### 5.b.R – Make it Right

- [x] **5.b.R** · Position **185/885** · Voraussetzung: `5.b.W`.
**Exakte Commit-Message:** `5.b.R feat(changes): RFC-6902 und Komfortpatches vervollständigen`

**Vervollständigung:** Erwartete Revision/Hash, Arraygrenzen, fehlende Pointer und geschützte Felder prüfen.

**Verhaltensabnahme:** Fehlerhafte Operation bricht vor Veröffentlichung ab; Originalstand bleibt gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 5.b.C – Make it Clean

- [x] **5.b.C** · Position **186/885** · Voraussetzung: `5.b.R`.
**Exakte Commit-Message:** `5.b.C refactor(changes): RFC-6902 und Komfortpatches bereinigen`

**Bereinigung:** Patchengine von CLI-Konvertierung und Spezialfeldschutz entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-c"></a>
### 5.c – Geordnete Auswertung und Faltung

**Anforderungsbezug:** `SR-REQ-0239`, `SR-REQ-0440`, `SR-REQ-0507`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.c.W – Let it Work

- [x] **5.c.W** · Position **187/885** · Voraussetzung: `5.b.C`.
**Exakte Commit-Message:** `5.c.W feat(changes): Geordnete Auswertung und Faltung aufbauen`

**Umsetzung:** Operationsfolge gegen Zwischenstände anwenden und je Artefakt ein Endresultat falten.

**Verhaltensabnahme:** Mehrere erlaubte Änderungen ergeben einen konsistenten Zielzustand.

#### 5.c.R – Make it Right

- [x] **5.c.R** · Position **188/885** · Voraussetzung: `5.c.W`.
**Exakte Commit-Message:** `5.c.R feat(changes): Geordnete Auswertung und Faltung vervollständigen`

**Vervollständigung:** Nach fehlgeschlagener Operation keine Folgeoperation auswerten.

**Verhaltensabnahme:** Instrumentierung weist ausbleibende Folgeeffekte und genau ein Endartefakt nach. Die W-Nachweise bleiben zusätzlich grün.

#### 5.c.C – Make it Clean

- [x] **5.c.C** · Position **189/885** · Voraussetzung: `5.c.R`.
**Exakte Commit-Message:** `5.c.C refactor(changes): Geordnete Auswertung und Faltung bereinigen`

**Bereinigung:** Faltung, Vorbedingungen und fachliche Operationen in getrennte reine Funktionen zerlegen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-d"></a>
### 5.d – Gebundene Metadatenpolicy

**Anforderungsbezug:** `SR-REQ-0034`, `SR-REQ-0435`–`SR-REQ-0439`.
**Verifikationsbezug:** `SR-VER-0003`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.d.W – Let it Work

- [x] **5.d.W** · Position **190/885** · Voraussetzung: `5.c.C`.
**Exakte Commit-Message:** `5.d.W feat(changes): Gebundene Metadatenpolicy aufbauen`

**Umsetzung:** change-metadata-v1 mit planned_at, Actor, IDs und genau einer Revisionsfortschreibung pro Artefakt implementieren.

**Verhaltensabnahme:** Derselbe Plan erzeugt unabhängig vom Applyzeitpunkt dieselben Metadaten und Hashes.

#### 5.d.R – Make it Right

- [x] **5.d.R** · Position **191/885** · Voraussetzung: `5.d.W`.
**Exakte Commit-Message:** `5.d.R feat(changes): Gebundene Metadatenpolicy vervollständigen`

**Vervollständigung:** No-op, mehrere Teiloperationen und historische Übernahmepolicies nicht vermischen.

**Verhaltensabnahme:** Zeitwechsel und wiederholtes Apply erzeugen keine neue geplante Revision. Die W-Nachweise bleiben zusätzlich grün.

#### 5.d.C – Make it Clean

- [x] **5.d.C** · Position **192/885** · Voraussetzung: `5.d.R`.
**Exakte Commit-Message:** `5.d.C refactor(changes): Gebundene Metadatenpolicy bereinigen`

**Bereinigung:** Reguläre Policy über eine explizite Schnittstelle für spätere Merge-/Migrationspolicies bereitstellen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-e"></a>
### 5.e – Lifecycle-Nachbedingungen im Plan

**Anforderungsbezug:** `SR-REQ-0042`–`SR-REQ-0048`, `SR-REQ-0051`.
**Verifikationsbezug:** `SR-VER-0004`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.e.W – Let it Work

- [x] **5.e.W** · Position **193/885** · Voraussetzung: `5.d.C`.
**Exakte Commit-Message:** `5.e.W feat(changes): Lifecycle-Nachbedingungen im Plan aufbauen`

**Umsetzung:** Vollständige Inhaltsprojektion gegen reine Lifecycleoperation unterscheiden und Endstatus vor Hashbildung bestimmen.

**Verhaltensabnahme:** Fachänderung an approved führt genau einmal zu proposed; reine Stilllegung zu retired.

#### 5.e.R – Make it Right

- [x] **5.e.R** · Position **194/885** · Voraussetzung: `5.e.W`.
**Exakte Commit-Message:** `5.e.R feat(changes): Lifecycle-Nachbedingungen im Plan vervollständigen`

**Vervollständigung:** Inhalt plus widersprüchliches Ziel ablehnen; retired bleibt final und frühere approved-Identität erhalten.

**Verhaltensabnahme:** Die Fälle aus §9.6.3 liefern Revision, Status und No-op exakt ohne verdeckten Reset. Die W-Nachweise bleiben zusätzlich grün.

#### 5.e.C – Make it Clean

- [x] **5.e.C** · Position **195/885** · Voraussetzung: `5.e.R`.
**Exakte Commit-Message:** `5.e.C refactor(changes): Lifecycle-Nachbedingungen im Plan bereinigen`

**Bereinigung:** Lifecyclepolitik nicht im Dateischreiber, sondern im sichtbaren Planner halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-f"></a>
### 5.f – Zielvalidation, Diff und Impact

**Anforderungsbezug:** `SR-REQ-0238`, `SR-REQ-0442`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.f.W – Let it Work

- [x] **5.f.W** · Position **196/885** · Voraussetzung: `5.e.C`.
**Exakte Commit-Message:** `5.f.W feat(changes): Zielvalidation, Diff und Impact aufbauen`

**Umsetzung:** Vollständiges isoliertes Ziel mit allen registrierten Gates prüfen und Plan-/Ressourcen-/Zielhash binden.

**Verhaltensabnahme:** Ein gültiger Plan liefert deterministisch Zielwurzel und fachlichen Unterschied.

#### 5.f.R – Make it Right

- [x] **5.f.R** · Position **197/885** · Voraussetzung: `5.f.W`.
**Exakte Commit-Message:** `5.f.R feat(changes): Zielvalidation, Diff und Impact vervollständigen`

**Vervollständigung:** Ungültiges Gesamtziel und manipulierte Planmetadaten verhindern prepared.

**Verhaltensabnahme:** Abhängiger Fehler außerhalb des direkt geänderten Artefakts wird gefunden. Die W-Nachweise bleiben zusätzlich grün.

#### 5.f.C – Make it Clean

- [x] **5.f.C** · Position **198/885** · Voraussetzung: `5.f.R`.
**Exakte Commit-Message:** `5.f.C refactor(changes): Zielvalidation, Diff und Impact bereinigen`

**Bereinigung:** Zielbewertung für direkten Write und spätere Proposal-/Importadapter wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-g"></a>
### 5.g – Dry-Run und Change-Apply

**Anforderungsbezug:** `SR-REQ-0237`, `SR-REQ-0243`, `SR-REQ-0443`, `SR-REQ-0489`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0030`, `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.g.W – Let it Work

- [x] **5.g.W** · Position **199/885** · Voraussetzung: `5.f.C`.
**Exakte Commit-Message:** `5.g.W feat(changes): Dry-Run und Change-Apply aufbauen`

**Umsetzung:** Dry-Run und gespeicherten change apply auf denselben gebundenen Plan aufsetzen.

**Verhaltensabnahme:** Dry-Runziel und echtes Applyziel sind bei unveränderter Basis fachlich identisch.

#### 5.g.R – Make it Right

- [x] **5.g.R** · Position **200/885** · Voraussetzung: `5.g.W`.
**Exakte Commit-Message:** `5.g.R feat(changes): Dry-Run und Change-Apply vervollständigen`

**Vervollständigung:** Dry-Run ohne Lock/Receipt/Projektwrite; fail-on-change bei tatsächlichem Unterschied behandeln.

**Verhaltensabnahme:** Byteinventur zeigt schreibfreien Dry-Run, No-op und passenden Exitcode. Die W-Nachweise bleiben zusätzlich grün.

#### 5.g.C – Make it Clean

- [x] **5.g.C** · Position **201/885** · Voraussetzung: `5.g.R`.
**Exakte Commit-Message:** `5.g.C refactor(changes): Dry-Run und Change-Apply bereinigen`

**Bereinigung:** Planung, Ausgabe und Veröffentlichung als getrennte Phasen führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-h"></a>
### 5.h – Akteure, Berechtigung und Request-ID

**Anforderungsbezug:** `SR-REQ-0236`, `SR-REQ-0382`, `SR-REQ-0543`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.h.W – Let it Work

- [x] **5.h.W** · Position **202/885** · Voraussetzung: `5.g.C`.
**Exakte Commit-Message:** `5.h.W feat(changes): Akteure, Berechtigung und Request-ID aufbauen`

**Umsetzung:** Actor und normative Request-ID normalisieren; AI/CI-Writepflichten und Proposalgrenze vorbereiten.

**Verhaltensabnahme:** Autorisierter menschlicher Write besitzt eine eindeutige Operationsbindung.

#### 5.h.R – Make it Right

- [x] **5.h.R** · Position **203/885** · Voraussetzung: `5.h.W`.
**Exakte Commit-Message:** `5.h.R feat(changes): Akteure, Berechtigung und Request-ID vervollständigen`

**Vervollständigung:** Direkte KI-Änderung ohne as-proposal und AI/CI ohne Request-ID vor Mutation abweisen.

**Verhaltensabnahme:** Verbotene Aufrufe liefern Code 7 beziehungsweise Nutzungsfehler ohne Dateien anzulegen. Die W-Nachweise bleiben zusätzlich grün.

#### 5.h.C – Make it Clean

- [x] **5.h.C** · Position **204/885** · Voraussetzung: `5.h.R`.
**Exakte Commit-Message:** `5.h.C refactor(changes): Akteure, Berechtigung und Request-ID bereinigen`

**Bereinigung:** Schreibautorisierung unabhängig von CLI-Anzeigen und Analyzeridentitäten halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-i"></a>
### 5.i – Exklusiver Projektlock

**Anforderungsbezug:** `SR-REQ-0205`–`SR-REQ-0206`, `SR-REQ-0221`, `SR-REQ-0506`, `SR-REQ-0569`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0035`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.i.W – Let it Work

- [x] **5.i.W** · Position **205/885** · Voraussetzung: `5.h.C`.
**Exakte Commit-Message:** `5.i.W feat(changes): Exklusiver Projektlock aufbauen`

**Umsetzung:** Writer- und Recovery-Locks mit vollständiger Eigentümer-/Startbindung einführen.

**Verhaltensabnahme:** Ein Writer erhält exklusiven Zugriff und gibt ihn zuverlässig frei.

#### 5.i.R – Make it Right

- [x] **5.i.R** · Position **206/885** · Voraussetzung: `5.i.W`.
**Exakte Commit-Message:** `5.i.R feat(changes): Exklusiver Projektlock vervollständigen`

**Vervollständigung:** Lebender Eigentümer, fremder/unprüfbarer Host und PID-Wiederverwendung verhindern unbegründete Übernahme.

**Verhaltensabnahme:** Parallele Zugriffe erzeugen keinen zweiten Writer; force umgeht kein Journal. Die W-Nachweise bleiben zusätzlich grün.

#### 5.i.C – Make it Clean

- [x] **5.i.C** · Position **207/885** · Voraussetzung: `5.i.R`.
**Exakte Commit-Message:** `5.i.C refactor(changes): Exklusiver Projektlock bereinigen`

**Bereinigung:** Eigentümerprüfung und jeweilige Lockart getrennt kapseln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-j"></a>
### 5.j – Prüfung unmittelbar vor Veröffentlichung

**Anforderungsbezug:** `SR-REQ-0161`, `SR-REQ-0192`, `SR-REQ-0557`, `SR-REQ-0564`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0013`, `SR-VER-0035`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.j.W – Let it Work

- [x] **5.j.W** · Position **208/885** · Voraussetzung: `5.i.C`.
**Exakte Commit-Message:** `5.j.W feat(changes): Prüfung unmittelbar vor Veröffentlichung aufbauen`

**Umsetzung:** Basis, erwartete Ressourcen, Lock und Rechte unter Writer-Lock erneut prüfen.

**Verhaltensabnahme:** Unveränderte Basis erlaubt Veröffentlichung des bereits geprüften Plans.

#### 5.j.R – Make it Right

- [x] **5.j.R** · Position **209/885** · Voraussetzung: `5.j.W`.
**Exakte Commit-Message:** `5.j.R feat(changes): Prüfung unmittelbar vor Veröffentlichung vervollständigen`

**Vervollständigung:** Änderung nach Preflight/Planung führt zu Konflikt ohne stilles Rebase.

**Verhaltensabnahme:** Racefixture verändert Basis zwischen Planung und Lock; Code 6 ohne normative Teiländerung. Die W-Nachweise bleiben zusätzlich grün.

#### 5.j.C – Make it Clean

- [x] **5.j.C** · Position **210/885** · Voraussetzung: `5.j.R`.
**Exakte Commit-Message:** `5.j.C refactor(changes): Prüfung unmittelbar vor Veröffentlichung bereinigen`

**Bereinigung:** Frühe Diagnose und verbindliche letzte Sicherheitsprüfung nicht vermischen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-k"></a>
### 5.k – Journal und Building-Zustand

**Anforderungsbezug:** `SR-REQ-0252`–`SR-REQ-0253`.
**Verifikationsbezug:** `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.k.W – Let it Work

- [x] **5.k.W** · Position **211/885** · Voraussetzung: `5.j.C`.
**Exakte Commit-Message:** `5.k.W feat(changes): Journal und Building-Zustand aufbauen`

**Umsetzung:** Journal mit Dateiinventur, Vorher-/Nachherhashes und Stagingbezügen vor erstem normativen Write erzeugen.

**Verhaltensabnahme:** Vollständige Änderungsdateiliste ist an Basis und Ziel gebunden.

#### 5.k.R – Make it Right

- [x] **5.k.R** · Position **212/885** · Voraussetzung: `5.k.W`.
**Exakte Commit-Message:** `5.k.R feat(changes): Journal und Building-Zustand vervollständigen`

**Vervollständigung:** Fehlende Einträge, widersprüchliche Existenzangaben und unzulässige Journalpfade abweisen.

**Verhaltensabnahme:** Fehler im Aufbau lässt den Fachstand unverändert und Recoveryinformationen erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 5.k.C – Make it Clean

- [x] **5.k.C** · Position **213/885** · Voraussetzung: `5.k.R`.
**Exakte Commit-Message:** `5.k.C refactor(changes): Journal und Building-Zustand bereinigen`

**Bereinigung:** Journalcodec, Inventur und transaktionale Zustandsmaschine trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-l"></a>
### 5.l – Staging, Before Images und Prepared

**Anforderungsbezug:** `SR-REQ-0254`.
**Verifikationsbezug:** `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.l.W – Let it Work

- [x] **5.l.W** · Position **214/885** · Voraussetzung: `5.k.C`.
**Exakte Commit-Message:** `5.l.W feat(changes): Staging, Before Images und Prepared aufbauen`

**Umsetzung:** Alle Zieldaten und nötigen Before Images vollständig schreiben, hashen und dauerhaft synchronisieren.

**Verhaltensabnahme:** prepared wird erst nach vollständiger prüfbarer Vorbereitung erreicht.

#### 5.l.R – Make it Right

- [x] **5.l.R** · Position **215/885** · Voraussetzung: `5.l.W`.
**Exakte Commit-Message:** `5.l.R feat(changes): Staging, Before Images und Prepared vervollständigen`

**Vervollständigung:** Platz-/Rechtefehler und manipulierte Stagingbytes verhindern vorbereiteten Erfolg.

**Verhaltensabnahme:** Abbruch vor prepared hinterlässt keine normativ veröffentlichte Datei. Die W-Nachweise bleiben zusätzlich grün.

#### 5.l.C – Make it Clean

- [x] **5.l.C** · Position **216/885** · Voraussetzung: `5.l.R`.
**Exakte Commit-Message:** `5.l.C refactor(changes): Staging, Before Images und Prepared bereinigen`

**Bereinigung:** Sichere Dateiprimitiven mit expliziten dauerhaften Grenzen kapseln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-m"></a>
### 5.m – Committing und atomare Dateiveröffentlichung

**Anforderungsbezug:** `SR-REQ-0175`, `SR-REQ-0189`, `SR-REQ-0204`, `SR-REQ-0255`, `SR-REQ-0478`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.m.W – Let it Work

- [x] **5.m.W** · Position **217/885** · Voraussetzung: `5.l.C`.
**Exakte Commit-Message:** `5.m.W feat(changes): Committing und atomare Dateiveröffentlichung aufbauen`

**Umsetzung:** Dauerhaft committing setzen und jede atomare Veröffentlichung einzeln quittieren.

**Verhaltensabnahme:** Alle vorgesehenen Dateien ergeben nach Abschluss exakt die Zielwurzel.

#### 5.m.R – Make it Right

- [x] **5.m.R** · Position **218/885** · Voraussetzung: `5.m.W`.
**Exakte Commit-Message:** `5.m.R feat(changes): Committing und atomare Dateiveröffentlichung vervollständigen`

**Vervollständigung:** I/O-Fehler und Prozessabbruch dürfen keinen regulär ladbaren Mischstand zurücklassen.

**Verhaltensabnahme:** Abbruchgrenzen liefern gesperrten Recoveryzustand statt falscher gültiger Teiländerung. Die W-Nachweise bleiben zusätzlich grün.

#### 5.m.C – Make it Clean

- [x] **5.m.C** · Position **219/885** · Voraussetzung: `5.m.R`.
**Exakte Commit-Message:** `5.m.C refactor(changes): Committing und atomare Dateiveröffentlichung bereinigen`

**Bereinigung:** Dateipublishing durch die Journalzustandsmaschine steuern, nicht umgekehrt.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-n"></a>
### 5.n – Audit und Abschlussreceipts

**Anforderungsbezug:** `SR-REQ-0241`, `SR-REQ-0259`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.n.W – Let it Work

- [x] **5.n.W** · Position **220/885** · Voraussetzung: `5.m.C`.
**Exakte Commit-Message:** `5.n.W feat(changes): Audit und Abschlussreceipts aufbauen`

**Umsetzung:** Unveränderbare Transaktions-/Auditbelege nach dauerhaftem Ergebnis anlegen.

**Verhaltensabnahme:** Erfolgreicher Write besitzt eine vollständige nachvollziehbare Ergebnisbindung.

#### 5.n.R – Make it Right

- [x] **5.n.R** · Position **221/885** · Voraussetzung: `5.n.W`.
**Exakte Commit-Message:** `5.n.R feat(changes): Audit und Abschlussreceipts vervollständigen`

**Vervollständigung:** Verlorene Ausgabe oder spätes Cleanupversagen erzeugen keinen zweiten Fachwrite.

**Verhaltensabnahme:** Wiederhergestellter Abschluss unterscheidet committed von nur angezeigt. Die W-Nachweise bleiben zusätzlich grün.

#### 5.n.C – Make it Clean

- [x] **5.n.C** · Position **222/885** · Voraussetzung: `5.n.R`.
**Exakte Commit-Message:** `5.n.C refactor(changes): Audit und Abschlussreceipts bereinigen`

**Bereinigung:** Belege und entbehrliche Arbeitsreste strikt getrennt verwalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-o"></a>
### 5.o – Normative Idempotenz

**Anforderungsbezug:** `SR-REQ-0383`–`SR-REQ-0385`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.o.W – Let it Work

- [x] **5.o.W** · Position **223/885** · Voraussetzung: `5.n.C`.
**Exakte Commit-Message:** `5.o.W feat(changes): Normative Idempotenz aufbauen`

**Umsetzung:** Request-Receipt mit Operationshash, Actor, Basis, Ergebnis und erzeugten IDs speichern und auswerten.

**Verhaltensabnahme:** Identischer Retry liefert dieselben IDs und dasselbe Fachresultat ohne erneute Änderung.

#### 5.o.R – Make it Right

- [x] **5.o.R** · Position **224/885** · Voraussetzung: `5.o.W`.
**Exakte Commit-Message:** `5.o.R feat(changes): Normative Idempotenz vervollständigen`

**Vervollständigung:** Gleiche Request-ID mit geändertem Operationshash als Code-6-Konflikt behandeln.

**Verhaltensabnahme:** Count/Hash/Revision zeigen genau einen Write; reine Analysekorrelation greift nicht auf diese Receipts zu. Die W-Nachweise bleiben zusätzlich grün.

#### 5.o.C – Make it Clean

- [x] **5.o.C** · Position **225/885** · Voraussetzung: `5.o.R`.
**Exakte Commit-Message:** `5.o.C refactor(changes): Normative Idempotenz bereinigen`

**Bereinigung:** Idempotenzentscheidung vor neuer Planung mit bereits bestätigtem Receipt ermöglichen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-p"></a>
### 5.p – Recoverystatus und Building-Discard

**Anforderungsbezug:** `SR-REQ-0257`, `SR-REQ-0262`, `SR-REQ-0458`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.p.W – Let it Work

- [x] **5.p.W** · Position **226/885** · Voraussetzung: `5.o.C`.
**Exakte Commit-Message:** `5.p.W feat(changes): Recoverystatus und Building-Discard aufbauen`

**Umsetzung:** Journalzustand und zulässige Aktionen ohne regulären Modellload bestimmen; unveröffentlichte Vorbereitung verwerfen.

**Verhaltensabnahme:** building/prepared bei unveränderter Basis kann sicher verworfen werden.

#### 5.p.R – Make it Right

- [x] **5.p.R** · Position **227/885** · Voraussetzung: `5.p.W`.
**Exakte Commit-Message:** `5.p.R feat(changes): Recoverystatus und Building-Discard vervollständigen`

**Vervollständigung:** Nach erfolgter Veröffentlichung oder Basisabweichung discard sperren.

**Verhaltensabnahme:** Kein unzulässiger Discard entfernt veröffentlichte Zielbytes oder nötige Beweise. Die W-Nachweise bleiben zusätzlich grün.

#### 5.p.C – Make it Clean

- [x] **5.p.C** · Position **228/885** · Voraussetzung: `5.p.R`.
**Exakte Commit-Message:** `5.p.C refactor(changes): Recoverystatus und Building-Discard bereinigen`

**Bereinigung:** Zustandsdiagnose und mutierende Recovery getrennt anbieten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-q"></a>
### 5.q – Recovery auf vollständiges Ziel

**Anforderungsbezug:** `SR-REQ-0258`.
**Verifikationsbezug:** `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.q.W – Let it Work

- [x] **5.q.W** · Position **229/885** · Voraussetzung: `5.p.C`.
**Exakte Commit-Message:** `5.q.W feat(changes): Recovery auf vollständiges Ziel aufbauen`

**Umsetzung:** Vollständig veröffentlichte Nachherhashes erkennen und fehlende Receipts rekonstruieren.

**Verhaltensabnahme:** Nach Crash hinter letzter Zieldatei wird die Zielwurzel committed statt zurückgerollt.

#### 5.q.R – Make it Right

- [x] **5.q.R** · Position **230/885** · Voraussetzung: `5.q.W`.
**Exakte Commit-Message:** `5.q.R feat(changes): Recovery auf vollständiges Ziel vervollständigen`

**Vervollständigung:** Fehlende Zielbytes oder inkonsistente Hashes erlauben keinen Erfolgsabschluss.

**Verhaltensabnahme:** Receiptrekonstruktion und Retry erzeugen keinen zweiten fachlichen Effekt. Die W-Nachweise bleiben zusätzlich grün.

#### 5.q.C – Make it Clean

- [x] **5.q.C** · Position **231/885** · Voraussetzung: `5.q.R`.
**Exakte Commit-Message:** `5.q.C refactor(changes): Recovery auf vollständiges Ziel bereinigen`

**Bereinigung:** Zielerkennung, Receiptreparatur und Abschlussfolge getrennt testen und strukturieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-r"></a>
### 5.r – Deterministischer Rollback

**Anforderungsbezug:** `SR-REQ-0459`, `SR-REQ-0511`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.r.W – Let it Work

- [x] **5.r.W** · Position **232/885** · Voraussetzung: `5.q.C`.
**Exakte Commit-Message:** `5.r.W feat(changes): Deterministischer Rollback aufbauen`

**Umsetzung:** Unvollständiges committing/rolling_back aus gesicherten Before Images vollständig auf Basis zurückführen.

**Verhaltensabnahme:** Recovery erreicht exakt die gebundene Basiswurzel.

#### 5.r.R – Make it Right

- [x] **5.r.R** · Position **233/885** · Voraussetzung: `5.r.W`.
**Exakte Commit-Message:** `5.r.R feat(changes): Deterministischer Rollback vervollständigen`

**Vervollständigung:** Wiederholte Unterbrechung beim Rollback bleibt erneut fortsetzbar.

**Verhaltensabnahme:** Crash in jedem Rollbackschritt führt nach Folge-Recovery nur zu Basis oder belegtem Vollziel. Die W-Nachweise bleiben zusätzlich grün.

#### 5.r.C – Make it Clean

- [x] **5.r.C** · Position **234/885** · Voraussetzung: `5.r.R`.
**Exakte Commit-Message:** `5.r.C refactor(changes): Deterministischer Rollback bereinigen`

**Bereinigung:** Rollback dieselben sicheren I/O-Primitiven wie Publishing verwenden lassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-s"></a>
### 5.s – Corrupt-Erkennung und Schutzinventur

**Anforderungsbezug:** `SR-REQ-0260`, `SR-REQ-0460`, `SR-REQ-0462`, `SR-REQ-0561`, `SR-REQ-0572`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0031`, `SR-VER-0035`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.s.W – Let it Work

- [x] **5.s.W** · Position **235/885** · Voraussetzung: `5.r.C`.
**Exakte Commit-Message:** `5.s.W feat(changes): Corrupt-Erkennung und Schutzinventur aufbauen`

**Umsetzung:** Manipulierte/unvollständige kritische Daten als corrupt erkennen und normale Zugriffe blockieren.

**Verhaltensabnahme:** Betriebsdiagnose kann Ursache ohne Löschung oder regulären Modellload feststellen.

#### 5.s.R – Make it Right

- [x] **5.s.R** · Position **236/885** · Voraussetzung: `5.s.W`.
**Exakte Commit-Message:** `5.s.R feat(changes): Corrupt-Erkennung und Schutzinventur vervollständigen`

**Vervollständigung:** Cachepflege darf Journale, Before Images oder Belege nicht beseitigen.

**Verhaltensabnahme:** Fehlende Pflichtbytes bleiben als konkreter Blocker sichtbar; Originaldaten werden nicht geraten. Die W-Nachweise bleiben zusätzlich grün.

#### 5.s.C – Make it Clean

- [x] **5.s.C** · Position **237/885** · Voraussetzung: `5.s.R`.
**Exakte Commit-Message:** `5.s.C refactor(changes): Corrupt-Erkennung und Schutzinventur bereinigen`

**Bereinigung:** Recoverykritische Ressourcen zentral kennzeichnen; Vollquellen-Restore bleibt M15 vorbehalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-t"></a>
### 5.t – Schreibfreie und automatische Preflight-Recovery

**Anforderungsbezug:** `SR-REQ-0256`, `SR-REQ-0558`–`SR-REQ-0560`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0035`, `SR-VER-0036`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.t.W – Let it Work

- [ ] **5.t.W** · Position **238/885** · Voraussetzung: `5.s.C`.
**Exakte Commit-Message:** `5.t.W feat(changes): Schreibfreie und automatische Preflight-Recovery aufbauen`

**Umsetzung:** Read-only-Befehle schreibfrei blockieren; autorisierte automatische Recovery mit getrenntem Abschluss/Wiederaufruf ausführen.

**Verhaltensabnahme:** Read-only-Aufruf meldet Recoverybedarf ohne Betriebswrite.

#### 5.t.R – Make it Right

- [ ] **5.t.R** · Position **239/885** · Voraussetzung: `5.t.W`.
**Exakte Commit-Message:** `5.t.R feat(changes): Schreibfreie und automatische Preflight-Recovery vervollständigen`

**Vervollständigung:** Normaler Fachauftrag darf nach Recovery nicht ungeprüft mit alter Basis weiterlaufen.

**Verhaltensabnahme:** Getrennte Aufrufe beweisen erneute Kontext-/Basisprüfung vor Fachänderung. Die W-Nachweise bleiben zusätzlich grün.

#### 5.t.C – Make it Clean

- [ ] **5.t.C** · Position **240/885** · Voraussetzung: `5.t.R`.
**Exakte Commit-Message:** `5.t.C refactor(changes): Schreibfreie und automatische Preflight-Recovery bereinigen`

**Bereinigung:** Preflightentscheidung und Recoveryausführung mit klarer Rückgabestruktur entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-u"></a>
### 5.u – Repräsentationsnormalisierung über Transaktionen

**Anforderungsbezug:** `SR-REQ-0441`, `SR-REQ-0463`–`SR-REQ-0466`.
**Verifikationsbezug:** `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.u.W – Let it Work

- [ ] **5.u.W** · Position **241/885** · Voraussetzung: `5.t.C`.
**Exakte Commit-Message:** `5.u.W feat(changes): Repräsentationsnormalisierung über Transaktionen aufbauen`

**Umsetzung:** format-Dateiumfang und representation_normalize mit Bytehashvorbedingungen über den Writer umsetzen.

**Verhaltensabnahme:** Formatierung ändert nur zulässige Repräsentation, niemals fachliche Werte oder Revision.

#### 5.u.R – Make it Right

- [ ] **5.u.R** · Position **242/885** · Voraussetzung: `5.u.W`.
**Exakte Commit-Message:** `5.u.R feat(changes): Repräsentationsnormalisierung über Transaktionen vervollständigen`

**Vervollständigung:** Evidence, Baselines, Reviews und immutable Proposal-Endstände ausschließen; check bleibt schreibfrei.

**Verhaltensabnahme:** Hash-/Wertinventur belegt Scope und Unveränderbarkeit, nicht Einrückung oder Formattext. Die W-Nachweise bleiben zusätzlich grün.

#### 5.u.C – Make it Clean

- [ ] **5.u.C** · Position **243/885** · Voraussetzung: `5.u.R`.
**Exakte Commit-Message:** `5.u.C refactor(changes): Repräsentationsnormalisierung über Transaktionen bereinigen`

**Bereinigung:** Normalisierungsplanung als spezialisierte Operation statt zweitem Schreibweg führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-5-v"></a>
### 5.v – Fault-Injection über jede dauerhafte Grenze

**Anforderungsbezug:** `SR-REQ-0261`.
**Verifikationsbezug:** `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 5.v.W – Let it Work

- [ ] **5.v.W** · Position **244/885** · Voraussetzung: `5.u.C`.
**Exakte Commit-Message:** `5.v.W feat(changes): Fault-Injection über jede dauerhafte Grenze aufbauen`

**Umsetzung:** Kontrollierten Prozessabbruch an jeder Journal-/Dateigrenze des vorhandenen Writers injizierbar machen.

**Verhaltensabnahme:** Ein Durchlauf mit Recovery endet auf gebundener Basis oder vollständigem Ziel.

#### 5.v.R – Make it Right

- [ ] **5.v.R** · Position **245/885** · Voraussetzung: `5.v.W`.
**Exakte Commit-Message:** `5.v.R feat(changes): Fault-Injection über jede dauerhafte Grenze vervollständigen`

**Vervollständigung:** Mehrdateiwrites, Receiptverlust und wiederholte Recoveryabbrüche in dieselbe Matrix aufnehmen.

**Verhaltensabnahme:** Kein Fall hinterlässt einen als gültig akzeptierten Mischzustand oder verlorene Nutzerdatei. Die W-Nachweise bleiben zusätzlich grün.

#### 5.v.C – Make it Clean

- [ ] **5.v.C** · Position **246/885** · Voraussetzung: `5.v.R`.
**Exakte Commit-Message:** `5.v.C refactor(changes): Fault-Injection über jede dauerhafte Grenze bereinigen`

**Bereinigung:** Fault-Hooks ausschließlich testbar einspeisen, Produktionslogik nicht an Testreihenfolge koppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 5 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m6"></a>
## Meilenstein 6 – Ressourcensparsame und fortsetzbare Verarbeitung

**Ziel:** Große Aufträge bleiben vollständig und können ohne Prozess- oder Chatgedächtnis fortgesetzt werden.

**Vorgesehener Zuschnitt:** `src/specroad/runtime/, src/specroad/work/, src/specroad/io/`. **Fachgrundlage:** §§ 7.4, 11.11–11.12; Anhänge N, O, P.

**Abschlussgate:** Einzellauf und vollständige Mehrschrittfolge liefern dieselben Fachresultate; Code 8 verlangt einen tatsächlich gesicherten Checkpoint. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-6-a"></a>
### 6.a – Begrenzte Preflightprofile

**Anforderungsbezug:** `SR-REQ-0553`, `SR-REQ-0555`, `SR-REQ-0570`.
**Verifikationsbezug:** `SR-VER-0035`, `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.a.W – Let it Work

- [ ] **6.a.W** · Position **247/885** · Voraussetzung: `5.v.C`.
**Exakte Commit-Message:** `6.a.W feat(work): Begrenzte Preflightprofile aufbauen`

**Umsetzung:** Pro Command ausschließlich benötigte Root-, Metadaten-, Lock- und aktive Journalprüfungen ausführen.

**Verhaltensabnahme:** Bootstrap und project_read benötigen keinen rekursiven Vollscan.

#### 6.a.R – Make it Right

- [ ] **6.a.R** · Position **248/885** · Voraussetzung: `6.a.W`.
**Exakte Commit-Message:** `6.a.R feat(work): Begrenzte Preflightprofile vervollständigen`

**Vervollständigung:** Metadaten-/Journalgrenzen einhalten und abgeschlossene Receipthistorie nicht zur Startprüfung durchsuchen.

**Verhaltensabnahme:** Zugriffsaufzeichnung belegt den begrenzten Prüfumfang auch bei großer Receipthistorie. Die W-Nachweise bleiben zusätzlich grün.

#### 6.a.C – Make it Clean

- [ ] **6.a.C** · Position **249/885** · Voraussetzung: `6.a.R`.
**Exakte Commit-Message:** `6.a.C refactor(work): Begrenzte Preflightprofile bereinigen`

**Bereinigung:** Preflightprofile aus derselben Command Registry wie CLI-Verträge ableiten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-b"></a>
### 6.b – Environment-Check ohne Nebenwirkungen

**Anforderungsbezug:** `SR-REQ-0565`–`SR-REQ-0567`.
**Verifikationsbezug:** `SR-VER-0036`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.b.W – Let it Work

- [ ] **6.b.W** · Position **250/885** · Voraussetzung: `6.a.C`.
**Exakte Commit-Message:** `6.b.W feat(work): Environment-Check ohne Nebenwirkungen aufbauen`

**Umsetzung:** environment check mit bekannten Rechten, Runtimevoraussetzungen und explizit unbekannten Hostgrenzen implementieren.

**Verhaltensabnahme:** Diagnose funktioniert auch ohne gültigen Fachmodellzustand.

#### 6.b.R – Make it Right

- [ ] **6.b.R** · Position **251/885** · Voraussetzung: `6.b.W`.
**Exakte Commit-Message:** `6.b.R feat(work): Environment-Check ohne Nebenwirkungen vervollständigen`

**Vervollständigung:** Keine Probe-Writes, Benchmarks, Netzwerkzugriffe oder Vollvalidierung ausführen.

**Verhaltensabnahme:** Ein schreibgeschützter Root und unbekannte Quoten bleiben ohne Dateien oder garantierte Ressourcenbehauptung. Die W-Nachweise bleiben zusätzlich grün.

#### 6.b.C – Make it Clean

- [ ] **6.b.C** · Position **252/885** · Voraussetzung: `6.b.R`.
**Exakte Commit-Message:** `6.b.C refactor(work): Environment-Check ohne Nebenwirkungen bereinigen`

**Bereinigung:** Messbare Voraussetzungen von bloßer Verfügbarkeitsschätzung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-c"></a>
### 6.c – Ressourcenprofile und Grenzklassen

**Anforderungsbezug:** `SR-REQ-0202`–`SR-REQ-0203`, `SR-REQ-0573`–`SR-REQ-0575`, `SR-REQ-0601`, `SR-REQ-0634`–`SR-REQ-0635`.
**Verifikationsbezug:** `SR-VER-0014`, `SR-VER-0037`, `SR-VER-0039`, `SR-VER-0040`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.c.W – Let it Work

- [ ] **6.c.W** · Position **253/885** · Voraussetzung: `6.b.C`.
**Exakte Commit-Message:** `6.c.W feat(work): Ressourcenprofile und Grenzklassen aufbauen`

**Umsetzung:** runtime-budget-v2 mit constrained/standard, expliziten Fachscopes, harten Sicherheitsgrenzen und weichen Arbeitszielen auflösen.

**Verhaltensabnahme:** Profilwechsel ändert Arbeitsweise, nicht Scope oder Operationshash.

#### 6.c.R – Make it Right

- [ ] **6.c.R** · Position **254/885** · Voraussetzung: `6.c.W`.
**Exakte Commit-Message:** `6.c.R feat(work): Ressourcenprofile und Grenzklassen vervollständigen`

**Vervollständigung:** Historische Gesamtmengenziele nicht zu harten Laufzeitverboten machen; echte Sicherheitsgrenzen niemals lockern.

**Verhaltensabnahme:** Großer gültiger Auftrag bleibt ausführbar; unzulässige Struktur bleibt gesperrt. Die W-Nachweise bleiben zusätzlich grün.

#### 6.c.C – Make it Clean

- [ ] **6.c.C** · Position **255/885** · Voraussetzung: `6.c.R`.
**Exakte Commit-Message:** `6.c.C refactor(work): Ressourcenprofile und Grenzklassen bereinigen`

**Bereinigung:** Semantische Konfiguration und Betriebsoptionen in getrennten Typen halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-d"></a>
### 6.d – Verbrauchsbilanz und Kontrollpunkte

**Anforderungsbezug:** `SR-REQ-0576`–`SR-REQ-0578`, `SR-REQ-0594`–`SR-REQ-0595`.
**Verifikationsbezug:** `SR-VER-0036`, `SR-VER-0037`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.d.W – Let it Work

- [ ] **6.d.W** · Position **256/885** · Voraussetzung: `6.c.C`.
**Exakte Commit-Message:** `6.d.W feat(work): Verbrauchsbilanz und Kontrollpunkte aufbauen`

**Umsetzung:** CPU, Wallzeit, gemessenen RSS und verbuchte Bytes unterscheiden und je Auftrag kumulieren.

**Verhaltensabnahme:** Mehrere Aufrufe addieren Verbrauch, ohne das neue Schrittfenster zu verbieten.

#### 6.d.R – Make it Right

- [ ] **6.d.R** · Position **257/885** · Voraussetzung: `6.d.W`.
**Exakte Commit-Message:** `6.d.R feat(work): Verbrauchsbilanz und Kontrollpunkte vervollständigen`

**Vervollständigung:** Unbekannte Messwerte als unknown/null führen; Kontrollintervalle gemäß O.2 instrumentieren.

**Verhaltensabnahme:** Graph-, SRX- und Payloadgrenzen lösen Kontrollen aus, aber keine erfundenen Verbrauchswerte. Die W-Nachweise bleiben zusätzlich grün.

#### 6.d.C – Make it Clean

- [ ] **6.d.C** · Position **258/885** · Voraussetzung: `6.d.R`.
**Exakte Commit-Message:** `6.d.C refactor(work): Verbrauchsbilanz und Kontrollpunkte bereinigen`

**Bereinigung:** Metrikadapter vom fachlichen Resultat und dessen Hash ausschließen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-e"></a>
### 6.e – Streaming und kleine Transferblöcke

**Anforderungsbezug:** `SR-REQ-0583`–`SR-REQ-0584`.
**Verifikationsbezug:** `SR-VER-0037`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.e.W – Let it Work

- [ ] **6.e.W** · Position **259/885** · Voraussetzung: `6.d.C`.
**Exakte Commit-Message:** `6.e.W feat(work): Streaming und kleine Transferblöcke aufbauen`

**Umsetzung:** Payloadhashing und große Datenverarbeitung in begrenzten Blöcken mit sparsamer Alternative ausführen.

**Verhaltensabnahme:** Ein großer Anhang wird ohne vollständige RAM-Kopie gehasht.

#### 6.e.R – Make it Right

- [ ] **6.e.R** · Position **260/885** · Voraussetzung: `6.e.W`.
**Exakte Commit-Message:** `6.e.R feat(work): Streaming und kleine Transferblöcke vervollständigen`

**Vervollständigung:** Reale Speicher-/Rechtefehler und nicht teilbare Mindestoperationen kontrolliert behandeln.

**Verhaltensabnahme:** Kleinere Puffer liefern denselben Bytehash und erhalten vorhandene kritische Daten bei Fehlern. Die W-Nachweise bleiben zusätzlich grün.

#### 6.e.C – Make it Clean

- [ ] **6.e.C** · Position **261/885** · Voraussetzung: `6.e.R`.
**Exakte Commit-Message:** `6.e.C refactor(work): Streaming und kleine Transferblöcke bereinigen`

**Bereinigung:** Streamingprimitiven für Archive, Snapshotaufbau und Import gemeinsam nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-f"></a>
### 6.f – Dateibasierte Sortierung und Diagnose-Spooling

**Anforderungsbezug:** `SR-REQ-0585`, `SR-REQ-0605`.
**Verifikationsbezug:** `SR-VER-0037`, `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.f.W – Let it Work

- [ ] **6.f.W** · Position **262/885** · Voraussetzung: `6.e.C`.
**Exakte Commit-Message:** `6.f.W feat(work): Dateibasierte Sortierung und Diagnose-Spooling aufbauen`

**Umsetzung:** Große geordnete Ergebnisse in gehashte Teilläufe mit Cursorzustand auslagern.

**Verhaltensabnahme:** Vollständige Ergebnismengen bleiben trotz kleiner In-Memory-Batches erhalten.

#### 6.f.R – Make it Right

- [ ] **6.f.R** · Position **263/885** · Voraussetzung: `6.f.W`.
**Exakte Commit-Message:** `6.f.R feat(work): Dateibasierte Sortierung und Diagnose-Spooling vervollständigen`

**Vervollständigung:** Keine Pflichtdiagnose und keinen kürzesten Pfad wegen Ausgabeschwelle verlieren.

**Verhaltensabnahme:** Große Mengen stimmen mit Referenzlauf vollständig überein; offene Mergecursor bleiben fortsetzbar. Die W-Nachweise bleiben zusätzlich grün.

#### 6.f.C – Make it Clean

- [ ] **6.f.C** · Position **264/885** · Voraussetzung: `6.f.R`.
**Exakte Commit-Message:** `6.f.C refactor(work): Dateibasierte Sortierung und Diagnose-Spooling bereinigen`

**Bereinigung:** Allgemeine Segment-/Cursorabstraktion statt befehlsspezifischer Tempformate verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-g"></a>
### 6.g – Optionale Caches ohne Fachwirkung

**Anforderungsbezug:** `SR-REQ-0588`–`SR-REQ-0591`.
**Verifikationsbezug:** `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.g.W – Let it Work

- [ ] **6.g.W** · Position **265/885** · Voraussetzung: `6.f.C`.
**Exakte Commit-Message:** `6.g.W feat(work): Optionale Caches ohne Fachwirkung aufbauen`

**Umsetzung:** cache off/read und vollständige Inhalts-/Versions-/Abhängigkeitsbindung vorhandener Einträge implementieren.

**Verhaltensabnahme:** Mit und ohne gültigen Cache entstehen dieselben fachlichen Daten.

#### 6.g.R – Make it Right

- [ ] **6.g.R** · Position **266/885** · Voraussetzung: `6.g.W`.
**Exakte Commit-Message:** `6.g.R feat(work): Optionale Caches ohne Fachwirkung vervollständigen`

**Vervollständigung:** Defekte, unlesbare, falsche oder zu teure Einträge ignorieren; mtime und Größe allein nicht vertrauen.

**Verhaltensabnahme:** Cachelöschung oder Manipulation verändert kein Fachresultat und löst keinen read_only-Write aus. Die W-Nachweise bleiben zusätzlich grün.

#### 6.g.C – Make it Clean

- [ ] **6.g.C** · Position **267/885** · Voraussetzung: `6.g.R`.
**Exakte Commit-Message:** `6.g.C refactor(work): Optionale Caches ohne Fachwirkung bereinigen`

**Bereinigung:** Cache als austauschbaren Beschleuniger hinter dem verbindlichen Reader halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-h"></a>
### 6.h – Sparsame Weiterarbeit und echter Blocker

**Anforderungsbezug:** `SR-REQ-0592`–`SR-REQ-0593`, `SR-REQ-0604`, `SR-REQ-0614`.
**Verifikationsbezug:** `SR-VER-0037`, `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.h.W – Let it Work

- [ ] **6.h.W** · Position **268/885** · Voraussetzung: `6.g.C`.
**Exakte Commit-Message:** `6.h.W feat(work): Sparsame Weiterarbeit und echter Blocker aufbauen`

**Umsetzung:** Vor Zurückstellung kleinere Chargen, Streaming und sichere kleinste Arbeitseinheit versuchen.

**Verhaltensabnahme:** Weiches Budget führt zu Fortschritt oder sicherem Fortsetzungspunkt.

#### 6.h.R – Make it Right

- [ ] **6.h.R** · Position **269/885** · Voraussetzung: `6.h.W`.
**Exakte Commit-Message:** `6.h.R feat(work): Sparsame Weiterarbeit und echter Blocker vervollständigen`

**Vervollständigung:** Tatsächliche Unausführbarkeit mit versuchten Alternativen belegen; Recoverydaten nicht für neuen Speicher löschen.

**Verhaltensabnahme:** Winziges Budget führt nicht zu Endlosschleife leerer Schritte oder falschem Fehler allein wegen des Ziels. Die W-Nachweise bleiben zusätzlich grün.

#### 6.h.C – Make it Clean

- [ ] **6.h.C** · Position **270/885** · Voraussetzung: `6.h.R`.
**Exakte Commit-Message:** `6.h.C refactor(work): Sparsame Weiterarbeit und echter Blocker bereinigen`

**Bereinigung:** Adaptionsentscheidung von Fachalgorithmus und Hostmessung entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-i"></a>
### 6.i – Work-Identität und geschlossenes Manifest

**Anforderungsbezug:** `SR-REQ-0602`–`SR-REQ-0603`, `SR-REQ-0615`, `SR-REQ-0632`.
**Verifikationsbezug:** `SR-VER-0039`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.i.W – Let it Work

- [ ] **6.i.W** · Position **271/885** · Voraussetzung: `6.h.C`.
**Exakte Commit-Message:** `6.i.W feat(work): Work-Identität und geschlossenes Manifest aufbauen`

**Umsetzung:** work-v1 mit stabiler Work-ID, Commandbindung, vollständigem Aufgaben-/Eingangsmanifest und Datensegmenten definieren.

**Verhaltensabnahme:** Ein gebundener Arbeitsauftrag benennt erledigte und vollständige offene Arbeit.

#### 6.i.R – Make it Right

- [ ] **6.i.R** · Position **272/885** · Voraussetzung: `6.i.W`.
**Exakte Commit-Message:** `6.i.R feat(work): Work-Identität und geschlossenes Manifest vervollständigen`

**Vervollständigung:** Pickle, Skripte, fremde Pythonobjekte und unbekannte auszuführende Command-IDs ablehnen.

**Verhaltensabnahme:** Manipuliertes Manifest kann keine andere Fachfunktion oder Schreibklasse starten. Die W-Nachweise bleiben zusätzlich grün.

#### 6.i.C – Make it Clean

- [ ] **6.i.C** · Position **273/885** · Voraussetzung: `6.i.R`.
**Exakte Commit-Message:** `6.i.C refactor(work): Work-Identität und geschlossenes Manifest bereinigen`

**Bereinigung:** Workcodec, Command Registry und Phasenzustand über schmale Verträge verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-j"></a>
### 6.j – Externer Work-Root und Locks

**Anforderungsbezug:** `SR-REQ-0619`, `SR-REQ-0627`.
**Verifikationsbezug:** `SR-VER-0039`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.j.W – Let it Work

- [ ] **6.j.W** · Position **274/885** · Voraussetzung: `6.i.C`.
**Exakte Commit-Message:** `6.j.W feat(work): Externer Work-Root und Locks aufbauen`

**Umsetzung:** Sicheren externen Work-Root explizit oder erst beim ersten nötigen Checkpoint automatisch erzeugen.

**Verhaltensabnahme:** Kleine vollständig abgeschlossene Befehle erzeugen keinen Work-Root.

#### 6.j.R – Make it Right

- [ ] **6.j.R** · Position **275/885** · Voraussetzung: `6.j.W`.
**Exakte Commit-Message:** `6.j.R feat(work): Externer Work-Root und Locks vervollständigen`

**Vervollständigung:** Pfadüberschneidung, Symlink, fremder Auftrag und unprüfbarer Lockowner verhindern Nutzung.

**Verhaltensabnahme:** Read-only- und Dry-Run-Aufträge erzeugen niemals Projekt- oder .specroad-Writes; Pause hält keinen Writer-Lock. Die W-Nachweise bleiben zusätzlich grün.

#### 6.j.C – Make it Clean

- [ ] **6.j.C** · Position **276/885** · Voraussetzung: `6.j.R`.
**Exakte Commit-Message:** `6.j.C refactor(work): Externer Work-Root und Locks bereinigen`

**Bereinigung:** Work-Lock und Projektlock strikt getrennt verwalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-k"></a>
### 6.k – Fortsetzbarer Eingangs-Snapshot

**Anforderungsbezug:** `SR-REQ-0603`, `SR-REQ-0605`, `SR-REQ-0630`.
**Verifikationsbezug:** `SR-VER-0039`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.k.W – Let it Work

- [ ] **6.k.W** · Position **277/885** · Voraussetzung: `6.j.C`.
**Exakte Commit-Message:** `6.k.W feat(work): Fortsetzbarer Eingangs-Snapshot aufbauen`

**Umsetzung:** Deterministische Enumeration, blockweises Hashen und schrittweise Versiegelung des Eingangsmanifests implementieren.

**Verhaltensabnahme:** Bereits gesicherte Bytes können vor Abschluss weiterverwendet werden.

#### 6.k.R – Make it Right

- [ ] **6.k.R** · Position **278/885** · Voraussetzung: `6.k.W`.
**Exakte Commit-Message:** `6.k.R feat(work): Fortsetzbarer Eingangs-Snapshot vervollständigen`

**Vervollständigung:** Veränderte/fehlende Quellen und Writeraktivität verhindern falsche Snapshotbestätigung.

**Verhaltensabnahme:** Teilaufbau wird nicht als vollständige Modellwurzel ausgegeben; fehlende Bytes werden konkret benannt. Die W-Nachweise bleiben zusätzlich grün.

#### 6.k.C – Make it Clean

- [ ] **6.k.C** · Position **279/885** · Voraussetzung: `6.k.R`.
**Exakte Commit-Message:** `6.k.C refactor(work): Fortsetzbarer Eingangs-Snapshot bereinigen`

**Bereinigung:** Snapshotzustand unabhängig von absoluten Pfaden und CLI-Laufzeit halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-l"></a>
### 6.l – Dauerhafte Checkpointgenerationen

**Anforderungsbezug:** `SR-REQ-0607`, `SR-REQ-0609`, `SR-REQ-0629`.
**Verifikationsbezug:** `SR-VER-0039`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.l.W – Let it Work

- [ ] **6.l.W** · Position **280/885** · Voraussetzung: `6.k.C`.
**Exakte Commit-Message:** `6.l.W feat(work): Dauerhafte Checkpointgenerationen aufbauen`

**Umsetzung:** Alle referenzierten Teile sichern und erst danach atomar die neue aktuelle Generation veröffentlichen.

**Verhaltensabnahme:** Nach Neustart wird genau der letzte vollständige Checkpoint verwendet.

#### 6.l.R – Make it Right

- [ ] **6.l.R** · Position **281/885** · Voraussetzung: `6.l.W`.
**Exakte Commit-Message:** `6.l.R feat(work): Dauerhafte Checkpointgenerationen vervollständigen`

**Vervollständigung:** Fehlende Segmente, falsche Hashes und Abbruch beim Generationenwechsel lassen keinen Teilcheckpoint gültig werden.

**Verhaltensabnahme:** Vorherige bestätigte Generation bleibt bei Fehler nutzbar und wird nicht als Cache entfernt. Die W-Nachweise bleiben zusätzlich grün.

#### 6.l.C – Make it Clean

- [ ] **6.l.C** · Position **282/885** · Voraussetzung: `6.l.R`.
**Exakte Commit-Message:** `6.l.C refactor(work): Dauerhafte Checkpointgenerationen bereinigen`

**Bereinigung:** Gemeinsame atomare Dateiprimitiven nutzen, Work- und Projektjournale dennoch getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-m"></a>
### 6.m – Resume und Kompatibilitätsprüfung

**Anforderungsbezug:** `SR-REQ-0608`, `SR-REQ-0610`–`SR-REQ-0611`, `SR-REQ-0616`–`SR-REQ-0617`.
**Verifikationsbezug:** `SR-VER-0040`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.m.W – Let it Work

- [ ] **6.m.W** · Position **283/885** · Voraussetzung: `6.l.C`.
**Exakte Commit-Message:** `6.m.W feat(work): Resume und Kompatibilitätsprüfung aufbauen`

**Umsetzung:** work resume aus geprüften Manifests mit unveränderten IDs, Actor, Request und Planmetadaten starten.

**Verhaltensabnahme:** Neuer Prozess und neuer kompatibler Pfad führen dieselbe Arbeit fort.

#### 6.m.R – Make it Right

- [ ] **6.m.R** · Position **284/885** · Voraussetzung: `6.m.W`.
**Exakte Commit-Message:** `6.m.R feat(work): Resume und Kompatibilitätsprüfung vervollständigen`

**Vervollständigung:** Unpassender Build-/Algorithmusvertrag, Actorwechsel oder stale Zielbasis erzeugen Konflikt statt Rebase.

**Verhaltensabnahme:** Veränderte Writebasis führt zu Code 6 ohne Verlust des gespeicherten Auftrags. Die W-Nachweise bleiben zusätzlich grün.

#### 6.m.C – Make it Clean

- [ ] **6.m.C** · Position **285/885** · Voraussetzung: `6.m.R`.
**Exakte Commit-Message:** `6.m.C refactor(work): Resume und Kompatibilitätsprüfung bereinigen`

**Bereinigung:** Zustandsrestauration und erneute lokale Rechte-/Basisprüfung getrennt ausführen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-n"></a>
### 6.n – Monotoner Fortschritt und kleinste Einheit

**Anforderungsbezug:** `SR-REQ-0606`, `SR-REQ-0612`–`SR-REQ-0613`, `SR-REQ-0631`.
**Verifikationsbezug:** `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.n.W – Let it Work

- [ ] **6.n.W** · Position **286/885** · Voraussetzung: `6.m.C`.
**Exakte Commit-Message:** `6.n.W feat(work): Monotoner Fortschritt und kleinste Einheit aufbauen`

**Umsetzung:** Abgeschlossene Einheiten wiederverwenden und bei kleinem Fenster mindestens sicheren kleinsten Fortschritt versuchen.

**Verhaltensabnahme:** Jede erfolgreiche Folgegeneration erledigt neue Arbeit statt den bestätigten Präfix neu zu rechnen.

#### 6.n.R – Make it Right

- [ ] **6.n.R** · Position **287/885** · Voraussetzung: `6.n.W`.
**Exakte Commit-Message:** `6.n.R feat(work): Monotoner Fortschritt und kleinste Einheit vervollständigen`

**Vervollständigung:** Doppelte Einheiten und endlose leere Checkpoints verhindern; echte Blocker separat behalten.

**Verhaltensabnahme:** Sehr kleine Fenster terminieren nach endlicher Schrittfolge mit vollständigem Resultat oder belegtem Blocker. Die W-Nachweise bleiben zusätzlich grün.

#### 6.n.C – Make it Clean

- [ ] **6.n.C** · Position **288/885** · Voraussetzung: `6.n.R`.
**Exakte Commit-Message:** `6.n.C refactor(work): Monotoner Fortschritt und kleinste Einheit bereinigen`

**Bereinigung:** Fortschrittsbeweis und Schedulerentscheidungen als eigene Komponenten gestalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-o"></a>
### 6.o – Globale Schlussprüfung und Abschlussstatus

**Anforderungsbezug:** `SR-REQ-0586`, `SR-REQ-0618`, `SR-REQ-0622`, `SR-REQ-0636`.
**Verifikationsbezug:** `SR-VER-0037`, `SR-VER-0039`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.o.W – Let it Work

- [ ] **6.o.W** · Position **289/885** · Voraussetzung: `6.n.C`.
**Exakte Commit-Message:** `6.o.W feat(work): Globale Schlussprüfung und Abschlussstatus aufbauen`

**Umsetzung:** Globale Closure-/Konsistenzarbeit und Pflichtdiagnosen vor fachlichem Abschluss vollständig zusammenführen.

**Verhaltensabnahme:** completed kann fachlich bestanden oder fehlgeschlagen sein, aber nie unvollständig.

#### 6.o.R – Make it Right

- [ ] **6.o.R** · Position **290/885** · Voraussetzung: `6.o.W`.
**Exakte Commit-Message:** `6.o.R feat(work): Globale Schlussprüfung und Abschlussstatus vervollständigen`

**Vervollständigung:** Lokale Teilfreigaben und noch offene Arbeit verhindern Erfolgsreceipt.

**Verhaltensabnahme:** Spät entdeckter globaler Fehler bleibt im vollständigen Ergebnis erhalten; Code 8 erst nach gültigem Checkpoint. Die W-Nachweise bleiben zusätzlich grün.

#### 6.o.C – Make it Clean

- [ ] **6.o.C** · Position **291/885** · Voraussetzung: `6.o.R`.
**Exakte Commit-Message:** `6.o.C refactor(work): Globale Schlussprüfung und Abschlussstatus bereinigen`

**Bereinigung:** Technischen Arbeitszustand von fachlichem Gateausgang trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-p"></a>
### 6.p – Atomarer Write über mehrere Vorbereitungsphasen

**Anforderungsbezug:** `SR-REQ-0620`–`SR-REQ-0621`.
**Verifikationsbezug:** `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.p.W – Let it Work

- [ ] **6.p.W** · Position **292/885** · Voraussetzung: `6.o.C`.
**Exakte Commit-Message:** `6.p.W feat(work): Atomarer Write über mehrere Vorbereitungsphasen aufbauen`

**Umsetzung:** Große Change Plans vor Veröffentlichung fortsetzen und den finalen Fachwrite ungeteilt ausführen.

**Verhaltensabnahme:** Mehrere Vorbereitungsaufrufe führen zu genau einer atomaren Fachtransaktion.

#### 6.p.R – Make it Right

- [ ] **6.p.R** · Position **293/885** · Voraussetzung: `6.p.W`.
**Exakte Commit-Message:** `6.p.R feat(work): Atomarer Write über mehrere Vorbereitungsphasen vervollständigen`

**Vervollständigung:** Kein freiwilliger Promptwechsel während committing; echter Abbruch geht ausschließlich durch Recovery.

**Verhaltensabnahme:** Nach Pause bleibt Basis regulär lesbar; Crash während Veröffentlichung folgt M5 statt normalen Work-Resume. Die W-Nachweise bleiben zusätzlich grün.

#### 6.p.C – Make it Clean

- [ ] **6.p.C** · Position **294/885** · Voraussetzung: `6.p.R`.
**Exakte Commit-Message:** `6.p.C refactor(work): Atomarer Write über mehrere Vorbereitungsphasen bereinigen`

**Bereinigung:** Worksteuerung vor und nach Transaktion anschließen, nicht in atomare Teilcommits zerlegen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-q"></a>
### 6.q – Große Ergebnisdateien und Abschlusslieferung

**Anforderungsbezug:** `SR-REQ-0623`.
**Verifikationsbezug:** `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.q.W – Let it Work

- [ ] **6.q.W** · Position **295/885** · Voraussetzung: `6.p.C`.
**Exakte Commit-Message:** `6.q.W feat(work): Große Ergebnisdateien und Abschlusslieferung aufbauen`

**Umsetzung:** Vollständige Ergebnisse über sichere Datei-/Manifestbindung statt abgeschnittener Inlinewerte liefern.

**Verhaltensabnahme:** Ergebnismanifest bindet alle tatsächlich erzeugten Datenbytes.

#### 6.q.R – Make it Right

- [ ] **6.q.R** · Position **296/885** · Voraussetzung: `6.q.W`.
**Exakte Commit-Message:** `6.q.R feat(work): Große Ergebnisdateien und Abschlusslieferung vervollständigen`

**Vervollständigung:** Ausgabeausfall nach Fachcommit darf keinen zweiten Apply auslösen; unvollständige Datei nicht als geliefert markieren.

**Verhaltensabnahme:** Datenumfang und Hashes stimmen vollständig; Tests vergleichen keine menschengelesenen Ergebnislayouts. Die W-Nachweise bleiben zusätzlich grün.

#### 6.q.C – Make it Clean

- [ ] **6.q.C** · Position **297/885** · Voraussetzung: `6.q.R`.
**Exakte Commit-Message:** `6.q.C refactor(work): Große Ergebnisdateien und Abschlusslieferung bereinigen`

**Bereinigung:** Ergebnislieferung und fachlichen Commitabschluss als getrennte überprüfbare Zustände führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-r"></a>
### 6.r – Work-Status, Prompt und Cancel

**Anforderungsbezug:** `SR-REQ-0571`, `SR-REQ-0624`–`SR-REQ-0627`.
**Verifikationsbezug:** `SR-VER-0036`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.r.W – Let it Work

- [ ] **6.r.W** · Position **298/885** · Voraussetzung: `6.q.C`.
**Exakte Commit-Message:** `6.r.W feat(work): Work-Status, Prompt und Cancel aufbauen`

**Umsetzung:** Status und next_action aus geprüfter Arbeit ableiten; Cancel nur für zulässig unveröffentlichte Arbeit ausführen.

**Verhaltensabnahme:** Abgebrochene Vorbereitung erhält den Projektstand und besitzt keinen fingierten Erfolg.

#### 6.r.R – Make it Right

- [ ] **6.r.R** · Position **299/885** · Voraussetzung: `6.r.W`.
**Exakte Commit-Message:** `6.r.R feat(work): Work-Status, Prompt und Cancel vervollständigen`

**Vervollständigung:** Fremde Projektanweisungen im Prompt bleiben Daten; keine Chats, LLMs oder Nachrichten selbst starten.

**Verhaltensabnahme:** Tests prüfen erlaubte nächste Operation und Seiteneffekte, nicht Promptformulierungen. Die W-Nachweise bleiben zusätzlich grün.

#### 6.r.C – Make it Clean

- [ ] **6.r.C** · Position **300/885** · Voraussetzung: `6.r.R`.
**Exakte Commit-Message:** `6.r.C refactor(work): Work-Status, Prompt und Cancel bereinigen`

**Bereinigung:** Maschinellen Fortsetzungsvertrag vom rein menschlichen Promptrenderer trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-s"></a>
### 6.s – Sicherer Work-Export und Restore

**Anforderungsbezug:** `SR-REQ-0563`, `SR-REQ-0628`.
**Verifikationsbezug:** `SR-VER-0035`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.s.W – Let it Work

- [ ] **6.s.W** · Position **301/885** · Voraussetzung: `6.r.C`.
**Exakte Commit-Message:** `6.s.W feat(work): Sicherer Work-Export und Restore aufbauen`

**Umsetzung:** Selbstenthaltenes gehashtes Arbeitspaket samt generischem sicheren Archivcodec implementieren.

**Verhaltensabnahme:** Exportierte Snapshot-/Checkpointbytes reichen für Restore im neuen kompatiblen Root.

#### 6.s.R – Make it Right

- [ ] **6.s.R** · Position **302/885** · Voraussetzung: `6.s.W`.
**Exakte Commit-Message:** `6.s.R feat(work): Sicherer Work-Export und Restore vervollständigen`

**Vervollständigung:** Traversal, Sonderdateien, fehlende Payloads und unzulässige Zielüberschneidung vor Restore abweisen.

**Verhaltensabnahme:** Restore erhält fachliche Bindungen und erkennt Verlust ungesicherter Bytes statt sie aus Hashes zu erfinden. Die W-Nachweise bleiben zusätzlich grün.

#### 6.s.C – Make it Clean

- [ ] **6.s.C** · Position **303/885** · Voraussetzung: `6.s.R`.
**Exakte Commit-Message:** `6.s.C refactor(work): Sicherer Work-Export und Restore bereinigen`

**Bereinigung:** Archivcodec als gemeinsame Basis für M14/M15 anbieten, Workmanifest fachlich separat halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-t"></a>
### 6.t – Prozesslebensdauer und Cleanupgrenzen

**Anforderungsbezug:** `SR-REQ-0579`–`SR-REQ-0580`.
**Verifikationsbezug:** `SR-VER-0037`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.t.W – Let it Work

- [ ] **6.t.W** · Position **304/885** · Voraussetzung: `6.s.C`.
**Exakte Commit-Message:** `6.t.W feat(work): Prozesslebensdauer und Cleanupgrenzen aufbauen`

**Umsetzung:** Keine Core-Workerpools; zulässige Kindprozesse kontrolliert abschließen und einsammeln.

**Verhaltensabnahme:** Ein beendeter Aufruf hinterlässt keine laufenden eigenen Kindprozesse.

#### 6.t.R – Make it Right

- [ ] **6.t.R** · Position **305/885** · Voraussetzung: `6.t.W`.
**Exakte Commit-Message:** `6.t.R feat(work): Prozesslebensdauer und Cleanupgrenzen vervollständigen`

**Vervollständigung:** Ausnahme-/Abbruchpfade und gesicherte Checkpoints bei Cleanup schützen.

**Verhaltensabnahme:** Kontrollierter Prozessabbruch hinterlässt weder Hintergrunddienst noch gelöschten gültigen Workstand. Die W-Nachweise bleiben zusätzlich grün.

#### 6.t.C – Make it Clean

- [ ] **6.t.C** · Position **306/885** · Voraussetzung: `6.t.R`.
**Exakte Commit-Message:** `6.t.C refactor(work): Prozesslebensdauer und Cleanupgrenzen bereinigen`

**Bereinigung:** Prozessadapter und Cleanupstrategie für spätere Git-/Analyzerverwendung bündeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-6-u"></a>
### 6.u – Endergebnisparität und Runtime-Wechsel

**Anforderungsbezug:** `SR-REQ-0587`, `SR-REQ-0596`, `SR-REQ-0599`, `SR-REQ-0633`.
**Verifikationsbezug:** `SR-VER-0035`, `SR-VER-0038`, `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 6.u.W – Let it Work

- [ ] **6.u.W** · Position **307/885** · Voraussetzung: `6.t.C`.
**Exakte Commit-Message:** `6.u.W feat(work): Endergebnisparität und Runtime-Wechsel aufbauen`

**Umsetzung:** Bestehende Graph-/SRX-/Validierungs-/Writepfade an die Workengine anschließen und Einzellaufparität nachweisen.

**Verhaltensabnahme:** Unterschiedliche Budgets, Caches, Roots und Prozesse liefern dieselbe Fachprojektion.

#### 6.u.R – Make it Right

- [ ] **6.u.R** · Position **308/885** · Voraussetzung: `6.u.W`.
**Exakte Commit-Message:** `6.u.R feat(work): Endergebnisparität und Runtime-Wechsel vervollständigen`

**Vervollständigung:** Unvollständige Eingänge, neue Hostgrenzen und veraltete Workdaten als konkrete Konflikte behandeln.

**Verhaltensabnahme:** Erforderliche Abhängigkeiten und Diagnosen bleiben über alle Schritte vollständig erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 6.u.C – Make it Clean

- [ ] **6.u.C** · Position **309/885** · Voraussetzung: `6.u.R`.
**Exakte Commit-Message:** `6.u.C refactor(work): Endergebnisparität und Runtime-Wechsel bereinigen`

**Bereinigung:** Wiederverwendbare Paritätsharness für jeden späteren Fachbefehl bereitstellen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 6 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m7"></a>
## Meilenstein 7 – Authoring, Lebenszyklen und Relationsreviews

**Ziel:** Ein erstes wirklich nutzbares CLI-Authoring auf dem sicheren Writer.

**Vorgesehener Zuschnitt:** `src/specroad/authoring/, src/specroad/reviews/, src/specroad/cli/`. **Fachgrundlage:** §§ 9.6, 11.13, 12.1, 12.17, 12.21; Anhang J.

**Abschlussgate:** Alle unterstützten Änderungen laufen über Change Plans; ein negativer menschlicher Relationsreview wird atomar mit seinen Freigabefolgen gespeichert. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-7-a"></a>
### 7.a – Atomare Projektinitialisierung

**Anforderungsbezug:** `SR-REQ-0001`–`SR-REQ-0003`, `SR-REQ-0480`.
**Verifikationsbezug:** `SR-VER-0001`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.a.W – Let it Work

- [ ] **7.a.W** · Position **310/885** · Voraussetzung: `6.u.C`.
**Exakte Commit-Message:** `7.a.W feat(authoring): Atomare Projektinitialisierung aufbauen`

**Umsetzung:** init mit Bootstrapjournal, Mindeststruktur und genau einem Primärdokument implementieren.

**Verhaltensabnahme:** Neues oder kollisionsfreies bestehendes Repository erhält ein gültiges Projekt.

#### 7.a.R – Make it Right

- [ ] **7.a.R** · Position **311/885** · Voraussetzung: `7.a.W`.
**Exakte Commit-Message:** `7.a.R feat(authoring): Atomare Projektinitialisierung vervollständigen`

**Vervollständigung:** Bestehende fremde Dateien erhalten; Konflikte und Abbruch führen zu Ausgang oder vollständig neuer Struktur.

**Verhaltensabnahme:** Fault-Injection weist nach, dass nur vom Bootstrap neu erzeugte Pfade rückgängig gemacht werden. Die W-Nachweise bleiben zusätzlich grün.

#### 7.a.C – Make it Clean

- [ ] **7.a.C** · Position **312/885** · Voraussetzung: `7.a.R`.
**Exakte Commit-Message:** `7.a.C refactor(authoring): Atomare Projektinitialisierung bereinigen`

**Bereinigung:** Root-Erzeugung vom Change Plan eines bereits vorhandenen Projekts trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-b"></a>
### 7.b – Strukturierte Authoring-Eingaben

**Anforderungsbezug:** `SR-REQ-0240`.
**Verifikationsbezug:** `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.b.W – Let it Work

- [ ] **7.b.W** · Position **313/885** · Voraussetzung: `7.a.C`.
**Exakte Commit-Message:** `7.b.W feat(authoring): Strukturierte Authoring-Eingaben aufbauen`

**Umsetzung:** Typspezifische Optionen und input-Datei/stdin in gemeinsame Fachinputs überführen.

**Verhaltensabnahme:** Gleiche Eingabedaten erzeugen denselben normalisierten Änderungsauftrag.

#### 7.b.R – Make it Right

- [ ] **7.b.R** · Position **314/885** · Voraussetzung: `7.b.W`.
**Exakte Commit-Message:** `7.b.R feat(authoring): Strukturierte Authoring-Eingaben vervollständigen`

**Vervollständigung:** Widersprüchliche Quellen, fehlende Pflichtfelder und falsche Datentypen vor Planung ablehnen.

**Verhaltensabnahme:** Ungültige Eingaben ändern keine Dateien und verbrauchen keine sichtbare fachliche Identität. Die W-Nachweise bleiben zusätzlich grün.

#### 7.b.C – Make it Clean

- [ ] **7.b.C** · Position **315/885** · Voraussetzung: `7.b.R`.
**Exakte Commit-Message:** `7.b.C refactor(authoring): Strukturierte Authoring-Eingaben bereinigen`

**Bereinigung:** Eingabekonvertierung aus den Handlerschritten herausziehen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-c"></a>
### 7.c – Artefakte erstellen

**Anforderungsbezug:** `SR-REQ-0216`–`SR-REQ-0217`.
**Verifikationsbezug:** `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.c.W – Let it Work

- [ ] **7.c.W** · Position **316/885** · Voraussetzung: `7.b.C`.
**Exakte Commit-Message:** `7.c.W feat(authoring): Artefakte erstellen aufbauen`

**Umsetzung:** Zulässige Drafttypen über ID-Vergabe, vollständige Validierung und Writer erzeugen.

**Verhaltensabnahme:** Ein gültiges Artefakt erscheint atomar unter dem berechneten ID-Pfad.

#### 7.c.R – Make it Right

- [ ] **7.c.R** · Position **317/885** · Voraussetzung: `7.c.W`.
**Exakte Commit-Message:** `7.c.R feat(authoring): Artefakte erstellen vervollständigen`

**Vervollständigung:** Kollision, fehlende Draftfelder und Spezialtypen ohne Fachservice abweisen.

**Verhaltensabnahme:** ID-/Datei-/Revisionseffekte und Retryverhalten werden geprüft, keine Konsolenausgabe. Die W-Nachweise bleiben zusätzlich grün.

#### 7.c.C – Make it Clean

- [ ] **7.c.C** · Position **318/885** · Voraussetzung: `7.c.R`.
**Exakte Commit-Message:** `7.c.C refactor(authoring): Artefakte erstellen bereinigen`

**Bereinigung:** Gemeinsamen Konstruktor aus M2 statt CLI-eigener Standardwerte verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-d"></a>
### 7.d – Artefakte aktualisieren

**Anforderungsbezug:** `SR-REQ-0232`, `SR-REQ-0657`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0044`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.d.W – Let it Work

- [ ] **7.d.W** · Position **319/885** · Voraussetzung: `7.c.C`.
**Exakte Commit-Message:** `7.d.W feat(authoring): Artefakte aktualisieren aufbauen`

**Umsetzung:** Updatekomfort und gespeicherte Patches mit erwarteter Revision oder Hash anbieten.

**Verhaltensabnahme:** Sprach-/Force-/Textänderung erzeugt genau eine neue Fachrevision.

#### 7.d.R – Make it Right

- [ ] **7.d.R** · Position **320/885** · Voraussetzung: `7.d.W`.
**Exakte Commit-Message:** `7.d.R feat(authoring): Artefakte aktualisieren vervollständigen`

**Vervollständigung:** Veraltete Vorbedingungen, direkte Identitätsänderung und freies Setzen von maturity verhindern.

**Verhaltensabnahme:** Approved-Inhaltsänderung wird proposed; No-op verändert keine Bytes. Die W-Nachweise bleiben zusätzlich grün.

#### 7.d.C – Make it Clean

- [ ] **7.d.C** · Position **321/885** · Voraussetzung: `7.d.R`.
**Exakte Commit-Message:** `7.d.C refactor(authoring): Artefakte aktualisieren bereinigen`

**Bereinigung:** Authoring nur als Adapter auf denselben Planer führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-e"></a>
### 7.e – Beziehungen hinzufügen und entfernen

**Anforderungsbezug:** `SR-REQ-0233`–`SR-REQ-0234`.
**Verifikationsbezug:** `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.e.W – Let it Work

- [ ] **7.e.W** · Position **322/885** · Voraussetzung: `7.d.C`.
**Exakte Commit-Message:** `7.e.W feat(authoring): Beziehungen hinzufügen und entfernen aufbauen`

**Umsetzung:** relation add/remove mit eigener Relation-ID, Grund und Quellrevision implementieren.

**Verhaltensabnahme:** Gültige Beziehung entsteht beziehungsweise genau die adressierte Beziehung entfällt.

#### 7.e.R – Make it Right

- [ ] **7.e.R** · Position **323/885** · Voraussetzung: `7.e.W`.
**Exakte Commit-Message:** `7.e.R feat(authoring): Beziehungen hinzufügen und entfernen vervollständigen`

**Vervollständigung:** Typfehler, fehlendes Ziel und falsche Relation-ID ohne Teilwrite behandeln.

**Verhaltensabnahme:** Audit, Quelle und Relationsanzahl weisen den exakten fachlichen Effekt nach. Die W-Nachweise bleiben zusätzlich grün.

#### 7.e.C – Make it Clean

- [ ] **7.e.C** · Position **324/885** · Voraussetzung: `7.e.R`.
**Exakte Commit-Message:** `7.e.C refactor(authoring): Beziehungen hinzufügen und entfernen bereinigen`

**Bereinigung:** Relationsoperationen nicht durch rohe Arraypatches in der CLI ersetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-f"></a>
### 7.f – Lifecycle und Stilllegung

**Anforderungsbezug:** `SR-REQ-0218`, `SR-REQ-0235`.
**Verifikationsbezug:** `SR-VER-0018`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.f.W – Let it Work

- [ ] **7.f.W** · Position **325/885** · Voraussetzung: `7.e.C`.
**Exakte Commit-Message:** `7.f.W feat(authoring): Lifecycle und Stilllegung aufbauen`

**Umsetzung:** transition und retire über die vollständigen Standard-/Spezialregeln anbieten.

**Verhaltensabnahme:** Reiner Übergang erhält Fachprojektion und schreibt Grund/Actor im Audit.

#### 7.f.R – Make it Right

- [ ] **7.f.R** · Position **326/885** · Voraussetzung: `7.f.W`.
**Exakte Commit-Message:** `7.f.R feat(authoring): Lifecycle und Stilllegung vervollständigen`

**Vervollständigung:** Rejected ohne Grund, unerlaubte Rückkehr aus retired und superseded ohne Nachfolger ablehnen.

**Verhaltensabnahme:** §9.6.3-Fälle bestätigen genau eine Revision und keinen versteckten Reset. Die W-Nachweise bleiben zusätzlich grün.

#### 7.f.C – Make it Clean

- [ ] **7.f.C** · Position **327/885** · Voraussetzung: `7.f.R`.
**Exakte Commit-Message:** `7.f.C refactor(authoring): Lifecycle und Stilllegung bereinigen`

**Bereinigung:** Statusparser, Gateprüfung und Writeroperation sauber trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-g"></a>
### 7.g – Reviewdatensatz und Kontextbindung

**Anforderungsbezug:** `SR-REQ-0275`, `SR-REQ-0434`.
**Verifikationsbezug:** `SR-VER-0021`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.g.W – Let it Work

- [ ] **7.g.W** · Position **328/885** · Voraussetzung: `7.f.C`.
**Exakte Commit-Message:** `7.g.W feat(authoring): Reviewdatensatz und Kontextbindung aufbauen`

**Umsetzung:** Menschlichen Relationsreview mit Relation, beiden Endpunkten und Kontext-/Vollhashes als immutable Datensatz planen.

**Verhaltensabnahme:** Review entsteht atomar als recorded/approved mit neuen Identitäten.

#### 7.g.R – Make it Right

- [ ] **7.g.R** · Position **329/885** · Voraussetzung: `7.g.W`.
**Exakte Commit-Message:** `7.g.R feat(authoring): Reviewdatensatz und Kontextbindung vervollständigen`

**Vervollständigung:** AI-Reviewer und strukturell ungültige Beziehung vor Write abweisen.

**Verhaltensabnahme:** Der Nachweis bindet exakt die geprüften Werte und lässt sich nicht generisch aktualisieren. Die W-Nachweise bleiben zusätzlich grün.

#### 7.g.C – Make it Clean

- [ ] **7.g.C** · Position **330/885** · Voraussetzung: `7.g.R`.
**Exakte Commit-Message:** `7.g.C refactor(authoring): Reviewdatensatz und Kontextbindung bereinigen`

**Bereinigung:** Reviewkonstruktion und generisches Authoring getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-h"></a>
### 7.h – Reviewstatus berechnen

**Anforderungsbezug:** `SR-REQ-0276`–`SR-REQ-0277`, `SR-REQ-0279`–`SR-REQ-0280`.
**Verifikationsbezug:** `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.h.W – Let it Work

- [ ] **7.h.W** · Position **331/885** · Voraussetzung: `7.g.C`.
**Exakte Commit-Message:** `7.h.W feat(authoring): Reviewstatus berechnen aufbauen`

**Umsetzung:** unreviewed/current/suspect/invalid aus Relation und passender Reviewhistorie berechnen.

**Verhaltensabnahme:** Passendes bestätigtes Review ist current; fachliche Endpunktänderung wird suspect.

#### 7.h.R – Make it Right

- [ ] **7.h.R** · Position **332/885** · Voraussetzung: `7.h.W`.
**Exakte Commit-Message:** `7.h.R feat(authoring): Reviewstatus berechnen vervollständigen`

**Vervollständigung:** Ungültige Struktur und jüngstes passendes rejected erhalten invalid-Vorrang.

**Verhaltensabnahme:** Lifecycle-/Auditänderung allein macht ein Review nicht suspect. Die W-Nachweise bleiben zusätzlich grün.

#### 7.h.C – Make it Clean

- [ ] **7.h.C** · Position **333/885** · Voraussetzung: `7.h.R`.
**Exakte Commit-Message:** `7.h.C refactor(authoring): Reviewstatus berechnen bereinigen`

**Bereinigung:** Reine Statusauswahl von historischen Reviewdaten und Diagnoserendering entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-i"></a>
### 7.i – Negativer Review mit Freigaberücknahme

**Anforderungsbezug:** `SR-REQ-0278`, `SR-REQ-0283`, `SR-REQ-0515`.
**Verifikationsbezug:** `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.i.W – Let it Work

- [ ] **7.i.W** · Position **334/885** · Voraussetzung: `7.h.C`.
**Exakte Commit-Message:** `7.i.W feat(authoring): Negativer Review mit Freigaberücknahme aufbauen`

**Umsetzung:** relation_review_record einschließlich aller erforderlichen Approval-Rücknahmen als einen Plan ausführen.

**Verhaltensabnahme:** Rejected einer Pflichtrelation erzeugt Review und setzt betroffenes approved Requirement einmal auf proposed.

#### 7.i.R – Make it Right

- [ ] **7.i.R** · Position **335/885** · Voraussetzung: `7.i.W`.
**Exakte Commit-Message:** `7.i.R feat(authoring): Negativer Review mit Freigaberücknahme vervollständigen`

**Vervollständigung:** Fachlich korrekt gespeichertes Negativurteil von ungültigem Write unterscheiden; Code 0 mit failed assessment versus später validate Code 1.

**Verhaltensabnahme:** R-35 bis R-39 prüfen atomare Kopplung, fehlende unbegründete Rücknahme und stabile Kontextbindung. Die W-Nachweise bleiben zusätzlich grün.

#### 7.i.C – Make it Clean

- [ ] **7.i.C** · Position **336/885** · Voraussetzung: `7.i.R`.
**Exakte Commit-Message:** `7.i.C refactor(authoring): Negativer Review mit Freigaberücknahme bereinigen`

**Bereinigung:** Eng definierte Review-Gateausnahme zentral und nicht als generelles Validierungsbypass implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-j"></a>
### 7.j – Reviewpolicy und Relationsstatus-CLI

**Anforderungsbezug:** `SR-REQ-0281`–`SR-REQ-0282`.
**Verifikationsbezug:** `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.j.W – Let it Work

- [ ] **7.j.W** · Position **337/885** · Voraussetzung: `7.i.C`.
**Exakte Commit-Message:** `7.j.W feat(authoring): Reviewpolicy und Relationsstatus-CLI aufbauen`

**Umsetzung:** Profilseverity und Relationsstatusdaten inklusive erforderlicher Reparatur bereitstellen.

**Verhaltensabnahme:** Unterschiedliche Reifegrade ergeben die vorgeschriebene Policybewertung.

#### 7.j.R – Make it Right

- [ ] **7.j.R** · Position **338/885** · Voraussetzung: `7.j.W`.
**Exakte Commit-Message:** `7.j.R feat(authoring): Reviewpolicy und Relationsstatus-CLI vervollständigen`

**Vervollständigung:** invalid bleibt Fehler unabhängig von Profil; keine automatische Wiederfreigabe nach Bestätigung.

**Verhaltensabnahme:** Wiederholtes confirmed macht Relation current, Requirement aber nicht selbständig approved. Die W-Nachweise bleiben zusätzlich grün.

#### 7.j.C – Make it Clean

- [ ] **7.j.C** · Position **339/885** · Voraussetzung: `7.j.R`.
**Exakte Commit-Message:** `7.j.C refactor(authoring): Reviewpolicy und Relationsstatus-CLI bereinigen`

**Bereinigung:** Statusprojektion für spätere Coverage/Readiness wiederverwendbar machen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-k"></a>
### 7.k – Authoring-Dry-Run und Wiederholung

**Anforderungsbezug:** `SR-REQ-0241`, `SR-REQ-0443`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.k.W – Let it Work

- [ ] **7.k.W** · Position **340/885** · Voraussetzung: `7.j.C`.
**Exakte Commit-Message:** `7.k.W feat(authoring): Authoring-Dry-Run und Wiederholung aufbauen`

**Umsetzung:** Alle vorhandenen Authoringbefehle mit einheitlicher Plan-/Audit-/Dry-Runbindung integrieren.

**Verhaltensabnahme:** Vorschauziel entspricht dem späteren autorisierten Ergebnis.

#### 7.k.R – Make it Right

- [ ] **7.k.R** · Position **341/885** · Voraussetzung: `7.k.W`.
**Exakte Commit-Message:** `7.k.R feat(authoring): Authoring-Dry-Run und Wiederholung vervollständigen`

**Vervollständigung:** Fehler, abgewiesene KI-Writes und stale Requests ohne unerwartete Dateiänderungen beenden.

**Verhaltensabnahme:** Reale E2E-Kette erzeugt, ändert, reviewt und retirert ohne doppelte IDs bei Retry. Die W-Nachweise bleiben zusätzlich grün.

#### 7.k.C – Make it Clean

- [ ] **7.k.C** · Position **342/885** · Voraussetzung: `7.k.R`.
**Exakte Commit-Message:** `7.k.C refactor(authoring): Authoring-Dry-Run und Wiederholung bereinigen`

**Bereinigung:** Gemeinsame Testszenarien über Fachadapter statt Kopien je Befehl verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-7-l"></a>
### 7.l – Projektinspektion mit getrenntem Laufzeitkontext

**Anforderungsbezug:** `SR-REQ-0380`–`SR-REQ-0381`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 7.l.W – Let it Work

- [ ] **7.l.W** · Position **343/885** · Voraussetzung: `7.k.C`.
**Exakte Commit-Message:** `7.l.W feat(authoring): Projektinspektion mit getrenntem Laufzeitkontext aufbauen`

**Umsetzung:** project inspect mit vollständigem semantic-/runtime-Vertrag aus vorhandenen Modelldiensten implementieren.

**Verhaltensabnahme:** Projekt, Schema, Profile, Artefakte, Hauptdokumente und Migrationsbedarf sind fachlich strukturiert abrufbar.

#### 7.l.R – Make it Right

- [ ] **7.l.R** · Position **344/885** · Voraussetzung: `7.l.W`.
**Exakte Commit-Message:** `7.l.R feat(authoring): Projektinspektion mit getrenntem Laufzeitkontext vervollständigen`

**Vervollständigung:** Root, Writerlock und Transaktion nicht in Fachdeterminismus einrechnen; offene Transaktion nicht als gesundes Projekt verstecken.

**Verhaltensabnahme:** Identische Modelle in anderem Pfad besitzen gleiche Fachprojektion, aber zutreffende verschiedene Runtimeinformationen. Die W-Nachweise bleiben zusätzlich grün.

#### 7.l.C – Make it Clean

- [ ] **7.l.C** · Position **345/885** · Voraussetzung: `7.l.R`.
**Exakte Commit-Message:** `7.l.C refactor(authoring): Projektinspektion mit getrenntem Laufzeitkontext bereinigen`

**Bereinigung:** Inspektion aus bestehenden Reader-/Preflightdaten aufbauen, nicht heimlich initialisieren oder reparieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 7 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m8"></a>
## Meilenstein 8 – Abfragen, Traceability, Änderungsanalyse und Git-Vergleich

**Ziel:** Fachliche Navigation und Änderungsbewertung auf den gemeinsamen Graph-/Scopekernen.

**Vorgesehener Zuschnitt:** `src/specroad/query/, src/specroad/diff/, src/specroad/git/, src/specroad/cli/`. **Fachgrundlage:** §§ 11.6, 12.8, 12.13; Anhang H.

**Abschlussgate:** Querytotal, alle kürzesten Why-Pfade und direkte Impactdaten bleiben vollständig; Git wird ausschließlich lesend und shellfrei verwendet. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-8-a"></a>
### 8.a – Show und inverse Relationssicht

**Anforderungsbezug:** `SR-REQ-0108`.
**Verifikationsbezug:** `SR-VER-0008`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.a.W – Let it Work

- [ ] **8.a.W** · Position **346/885** · Voraussetzung: `7.l.C`.
**Exakte Commit-Message:** `8.a.W feat(query): Show und inverse Relationssicht aufbauen`

**Umsetzung:** Vollständiges Artefakt und berechnete eingehende/ausgehende Beziehungen als Fachresultat anbieten.

**Verhaltensabnahme:** Show findet auch nur eingehend referenzierende Artefakte.

#### 8.a.R – Make it Right

- [ ] **8.a.R** · Position **347/885** · Voraussetzung: `8.a.W`.
**Exakte Commit-Message:** `8.a.R feat(query): Show und inverse Relationssicht vervollständigen`

**Vervollständigung:** Fehlende IDs und unvollständiger Index erhalten keine scheinbar vollständige Antwort.

**Verhaltensabnahme:** Fachresultat und Projektinventur belegen Vollständigkeit ohne Writes. Die W-Nachweise bleiben zusätzlich grün.

#### 8.a.C – Make it Clean

- [ ] **8.a.C** · Position **348/885** · Voraussetzung: `8.a.R`.
**Exakte Commit-Message:** `8.a.C refactor(query): Show und inverse Relationssicht bereinigen`

**Bereinigung:** Showprojektion von Pretty- und JSON-Rendering trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-b"></a>
### 8.b – Queryfilter und Projektion

**Anforderungsbezug:** `SR-REQ-0109`–`SR-REQ-0110`, `SR-REQ-0449`, `SR-REQ-0473`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.b.W – Let it Work

- [ ] **8.b.W** · Position **349/885** · Voraussetzung: `8.a.C`.
**Exakte Commit-Message:** `8.b.W feat(query): Queryfilter und Projektion aufbauen`

**Umsetzung:** Vollständige Query-Grammatik, Feldprojektion, Wertfilter und SRX-Filter kombinieren.

**Verhaltensabnahme:** Wiederholte Wertfilter sind ODER, unterschiedliche Arten und alle SRX-Filter UND.

#### 8.b.R – Make it Right

- [ ] **8.b.R** · Position **350/885** · Voraussetzung: `8.b.W`.
**Exakte Commit-Message:** `8.b.R feat(query): Queryfilter und Projektion vervollständigen`

**Vervollständigung:** Gespeicherten verification_plan_status und berechnetes verification_result getrennt behandeln; unbekannte Felder abweisen.

**Verhaltensabnahme:** Kombinationsfälle liefern exakt die erwarteten IDs und Werte. Die W-Nachweise bleiben zusätzlich grün.

#### 8.b.C – Make it Clean

- [ ] **8.b.C** · Position **351/885** · Voraussetzung: `8.b.R`.
**Exakte Commit-Message:** `8.b.C refactor(query): Queryfilter und Projektion bereinigen`

**Bereinigung:** Querynormalisierung, Auswertung und Ergebnisprojektion separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-c"></a>
### 8.c – Unicode-Volltextsuche

**Anforderungsbezug:** `SR-REQ-0474`.
**Verifikationsbezug:** `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.c.W – Let it Work

- [ ] **8.c.W** · Position **352/885** · Voraussetzung: `8.b.C`.
**Exakte Commit-Message:** `8.c.W feat(query): Unicode-Volltextsuche aufbauen`

**Umsetzung:** Sucharbeitskopien mit NFC und Casefold localeunabhängig vergleichen.

**Verhaltensabnahme:** Äquivalente Suchbegriffe finden dieselben passenden Fachtexte.

#### 8.c.R – Make it Right

- [ ] **8.c.R** · Position **353/885** · Voraussetzung: `8.c.W`.
**Exakte Commit-Message:** `8.c.R feat(query): Unicode-Volltextsuche vervollständigen`

**Vervollständigung:** Originaltext und Hash unverändert lassen; Normalisierung nur für Suche verwenden.

**Verhaltensabnahme:** Suchtreffer bleiben über Localewechsel gleich, gespeicherte NFC/NFD-Originale verschieden. Die W-Nachweise bleiben zusätzlich grün.

#### 8.c.C – Make it Clean

- [ ] **8.c.C** · Position **354/885** · Voraussetzung: `8.c.R`.
**Exakte Commit-Message:** `8.c.C refactor(query): Unicode-Volltextsuche bereinigen`

**Bereinigung:** Suchindex und kanonische Speicherung strikt trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-d"></a>
### 8.d – Sortierung und exakte Pagination

**Anforderungsbezug:** `SR-REQ-0475`.
**Verifikationsbezug:** `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.d.W – Let it Work

- [ ] **8.d.W** · Position **355/885** · Voraussetzung: `8.c.C`.
**Exakte Commit-Message:** `8.d.W feat(query): Sortierung und exakte Pagination aufbauen`

**Umsetzung:** items, total, offset, limit, returned und truncated aus vollständiger Querymenge berechnen.

**Verhaltensabnahme:** Limit 1 beschränkt nur items, nicht das exakte total.

#### 8.d.R – Make it Right

- [ ] **8.d.R** · Position **356/885** · Voraussetzung: `8.d.W`.
**Exakte Commit-Message:** `8.d.R feat(query): Sortierung und exakte Pagination vervollständigen`

**Vervollständigung:** Leere Menge, Offset jenseits Ende und große fortsetzbare Auswahl behandeln.

**Verhaltensabnahme:** Einzel- und Mehrschrittlauf ergeben dieselbe Gesamtzahl und Seite. Die W-Nachweise bleiben zusätzlich grün.

#### 8.d.C – Make it Clean

- [ ] **8.d.C** · Position **357/885** · Voraussetzung: `8.d.R`.
**Exakte Commit-Message:** `8.d.C refactor(query): Sortierung und exakte Pagination bereinigen`

**Bereinigung:** Sortier-/Paginglogik mit M6-Spooling statt verstecktem Frühabbruch umsetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-e"></a>
### 8.e – Trace in beide Richtungen

**Anforderungsbezug:** `SR-REQ-0111`.
**Verifikationsbezug:** `SR-VER-0008`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.e.W – Let it Work

- [ ] **8.e.W** · Position **358/885** · Voraussetzung: `8.d.C`.
**Exakte Commit-Message:** `8.e.W feat(query): Trace in beide Richtungen aufbauen`

**Umsetzung:** Gerichtete Traversierung für in/out/both mit expliziter Tiefe anbieten.

**Verhaltensabnahme:** Fachlich gewählte Tiefe und Relationsrichtung ergeben die erwarteten Knoten/Kanten.

#### 8.e.R – Make it Right

- [ ] **8.e.R** · Position **359/885** · Voraussetzung: `8.e.W`.
**Exakte Commit-Message:** `8.e.R feat(query): Trace in beide Richtungen vervollständigen`

**Vervollständigung:** Zyklen, Mehrfachpfade und weiche Arbeitsziele ohne Verlust offenen Scopes verarbeiten.

**Verhaltensabnahme:** Fortgesetzte Traversierung erreicht dieselbe Menge wie ungeteilter Lauf. Die W-Nachweise bleiben zusätzlich grün.

#### 8.e.C – Make it Clean

- [ ] **8.e.C** · Position **360/885** · Voraussetzung: `8.e.R`.
**Exakte Commit-Message:** `8.e.C refactor(query): Trace in beide Richtungen bereinigen`

**Bereinigung:** CLI-Traversierung auf vorhandene Frontierengine reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-f"></a>
### 8.f – Alle kürzesten Why-Pfade

**Anforderungsbezug:** `SR-REQ-0064`, `SR-REQ-0112`.
**Verifikationsbezug:** `SR-VER-0005`, `SR-VER-0008`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.f.W – Let it Work

- [ ] **8.f.W** · Position **361/885** · Voraussetzung: `8.e.C`.
**Exakte Commit-Message:** `8.f.W feat(query): Alle kürzesten Why-Pfade aufbauen`

**Umsetzung:** Sämtliche kürzesten gültigen Pfade zu Goals, Needs und Sources berechnen.

**Verhaltensabnahme:** Mehrere gleich kurze Herkunftswege erscheinen im vollständigen fachlichen Ergebnis.

#### 8.f.R – Make it Right

- [ ] **8.f.R** · Position **362/885** · Voraussetzung: `8.f.W`.
**Exakte Commit-Message:** `8.f.R feat(query): Alle kürzesten Why-Pfade vervollständigen`

**Vervollständigung:** Große Pfadanzahl checkpointen statt eine Stichprobe als vollständig ausgeben.

**Verhaltensabnahme:** Referenzgraph mit verzweigter Pfadzahl weist vollständige und minimale Pfade nach. Die W-Nachweise bleiben zusätzlich grün.

#### 8.f.C – Make it Clean

- [ ] **8.f.C** · Position **363/885** · Voraussetzung: `8.f.R`.
**Exakte Commit-Message:** `8.f.C refactor(query): Alle kürzesten Why-Pfade bereinigen`

**Bereinigung:** Vorgängergraph und Pfadmaterialisierung trennen und beide fortsetzbar halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-g"></a>
### 8.g – Direkte und reviewbezogene Impactanalyse

**Anforderungsbezug:** `SR-REQ-0113`, `SR-REQ-0284`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0021`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.g.W – Let it Work

- [ ] **8.g.W** · Position **364/885** · Voraussetzung: `8.f.C`.
**Exakte Commit-Message:** `8.g.W feat(query): Direkte und reviewbezogene Impactanalyse aufbauen`

**Umsetzung:** Direkte Abhängigkeiten nach Relationstyp und Reviewstatus auswerten.

**Verhaltensabnahme:** Geändertes Artefakt zeigt alle direkt betroffenen Nachbarn und invalid/suspect-Bindungen.

#### 8.g.R – Make it Right

- [ ] **8.g.R** · Position **365/885** · Voraussetzung: `8.g.W`.
**Exakte Commit-Message:** `8.g.R feat(query): Direkte und reviewbezogene Impactanalyse vervollständigen`

**Vervollständigung:** Fehlende fachliche Informationen nicht in eine erfundene Priorität oder Verifikation umdeuten.

**Verhaltensabnahme:** Betroffenheitsmengen stimmen unabhängig von Reihenfolge und Cachezustand. Die W-Nachweise bleiben zusätzlich grün.

#### 8.g.C – Make it Clean

- [ ] **8.g.C** · Position **366/885** · Voraussetzung: `8.g.R`.
**Exakte Commit-Message:** `8.g.C refactor(query): Direkte und reviewbezogene Impactanalyse bereinigen`

**Bereinigung:** Impactkalkulation für Planner und lesende CLI gemeinsam nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-h"></a>
### 8.h – Semantische Diffklassen

**Anforderungsbezug:** `SR-REQ-0115`–`SR-REQ-0116`, `SR-REQ-0403`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.h.W – Let it Work

- [ ] **8.h.W** · Position **367/885** · Voraussetzung: `8.g.C`.
**Exakte Commit-Message:** `8.h.W feat(query): Semantische Diffklassen aufbauen`

**Umsetzung:** Strukturierte Feld-, Timing-, Scope-, Konfigurations-, Relations-, Status- und Nachweisänderungen klassifizieren.

**Verhaltensabnahme:** Strukturierte Grenzwertänderung und reine Textänderung besitzen unterschiedliche Kategorien.

#### 8.h.R – Make it Right

- [ ] **8.h.R** · Position **368/885** · Voraussetzung: `8.h.W`.
**Exakte Commit-Message:** `8.h.R feat(query): Semantische Diffklassen vervollständigen`

**Vervollständigung:** Unbekannte Semantik bleibt text_changed; keine Sprachverständnisheuristik einsetzen.

**Verhaltensabnahme:** Wertebasierte Fixtures prüfen Klassifikation und Identität statt Ausgabetexte. Die W-Nachweise bleiben zusätzlich grün.

#### 8.h.C – Make it Clean

- [ ] **8.h.C** · Position **369/885** · Voraussetzung: `8.h.R`.
**Exakte Commit-Message:** `8.h.C refactor(query): Semantische Diffklassen bereinigen`

**Bereinigung:** Klassifikatoren pro Feldsemantik von allgemeinem Objektvergleich trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-i"></a>
### 8.i – Sichere Git-Objektquelle

**Anforderungsbezug:** `SR-REQ-0191`.
**Verifikationsbezug:** `SR-VER-0013`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.i.W – Let it Work

- [ ] **8.i.W** · Position **370/885** · Voraussetzung: `8.h.C`.
**Exakte Commit-Message:** `8.i.W feat(query): Sichere Git-Objektquelle aufbauen`

**Umsetzung:** Feste shellfreie Git-Plumbingaufrufe ohne Checkout, Hooks, Pager oder Filter anlegen.

**Verhaltensabnahme:** Ein Git-Ref liefert die gebundenen Projektdateien ohne Working-Treewechsel.

#### 8.i.R – Make it Right

- [ ] **8.i.R** · Position **371/885** · Voraussetzung: `8.i.W`.
**Exakte Commit-Message:** `8.i.R feat(query): Sichere Git-Objektquelle vervollständigen`

**Vervollständigung:** Bösartige Ref-/Konfigurationswerte und fehlendes Git kontrolliert behandeln; keine Quellcodeausführung.

**Verhaltensabnahme:** Branch, Index, Arbeitsbaum und fremde Dateien bleiben unverändert. Die W-Nachweise bleiben zusätzlich grün.

#### 8.i.C – Make it Clean

- [ ] **8.i.C** · Position **372/885** · Voraussetzung: `8.i.R`.
**Exakte Commit-Message:** `8.i.C refactor(query): Sichere Git-Objektquelle bereinigen`

**Bereinigung:** Git nur als expliziten Quellenadapter für Diff und später Merge halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-j"></a>
### 8.j – Vergleichsquellen und Projektidentität

**Anforderungsbezug:** `SR-REQ-0114`.
**Verifikationsbezug:** `SR-VER-0008`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.j.W – Let it Work

- [ ] **8.j.W** · Position **373/885** · Voraussetzung: `8.i.C`.
**Exakte Commit-Message:** `8.j.W feat(query): Vergleichsquellen und Projektidentität aufbauen`

**Umsetzung:** Lokale Projekt-/Gitquellen über gemeinsamen Snapshotvertrag auflösen; Schnittstellen für Baseline und Bundle vorbereiten.

**Verhaltensabnahme:** Zwei gültige Quellen derselben project_id ergeben denselben Vergleich wie direkte Daten.

#### 8.j.R – Make it Right

- [ ] **8.j.R** · Position **374/885** · Voraussetzung: `8.j.W`.
**Exakte Commit-Message:** `8.j.R feat(query): Vergleichsquellen und Projektidentität vervollständigen`

**Vervollständigung:** Fremdes Projekt, inkompatibles Schema oder noch nicht verfügbare Quellenart ausdrücklich abweisen.

**Verhaltensabnahme:** Keine Quelle wird ersatzweise vom aktuellen Arbeitsstand ergänzt. Die W-Nachweise bleiben zusätzlich grün.

#### 8.j.C – Make it Clean

- [ ] **8.j.C** · Position **375/885** · Voraussetzung: `8.j.R`.
**Exakte Commit-Message:** `8.j.C refactor(query): Vergleichsquellen und Projektidentität bereinigen`

**Bereinigung:** Quellenregistry halten; konkrete Baseline-/Bundleadapter erst in M10/M15 vollständig aktivieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-k"></a>
### 8.k – Changed-only mit Closure

**Anforderungsbezug:** `SR-REQ-0193`, `SR-REQ-0587`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.k.W – Let it Work

- [ ] **8.k.W** · Position **376/885** · Voraussetzung: `8.j.C`.
**Exakte Commit-Message:** `8.k.W feat(query): Changed-only mit Closure aufbauen`

**Umsetzung:** Geänderte IDs aus Gitvergleich bestimmen und notwendige Validierungs-/Lintabhängigkeiten mitprüfen.

**Verhaltensabnahme:** Änderung an Ziel oder Regel zieht abhängige betroffene Artefakte ein.

#### 8.k.R – Make it Right

- [ ] **8.k.R** · Position **377/885** · Voraussetzung: `8.k.W`.
**Exakte Commit-Message:** `8.k.R feat(query): Changed-only mit Closure vervollständigen`

**Vervollständigung:** Teilprüfung nie als Projektvollprüfung bezeichnen; fehlende Basis vor Prüfung melden.

**Verhaltensabnahme:** Ein außerhalb der direkt geänderten Datei ausgelöster Regelbruch wird gefunden. Die W-Nachweise bleiben zusätzlich grün.

#### 8.k.C – Make it Clean

- [ ] **8.k.C** · Position **378/885** · Voraussetzung: `8.k.R`.
**Exakte Commit-Message:** `8.k.C refactor(query): Changed-only mit Closure bereinigen`

**Bereinigung:** Geänderte Seedmenge und generische Closurekomposition wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-8-l"></a>
### 8.l – Lesende Funktionsintegration und Workparität

**Anforderungsbezug:** `SR-REQ-0117`, `SR-REQ-0213`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0015`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 8.l.W – Let it Work

- [ ] **8.l.W** · Position **379/885** · Voraussetzung: `8.k.C`.
**Exakte Commit-Message:** `8.l.W feat(query): Lesende Funktionsintegration und Workparität aufbauen`

**Umsetzung:** Show, Query, Trace, Why, Impact und Diff vollständig an Runtime und Resultatverträge anschließen.

**Verhaltensabnahme:** Jeder vorhandene Befehl arbeitet im schreibgeschützten Projekt und bei kleinem Schrittfenster.

#### 8.l.R – Make it Right

- [ ] **8.l.R** · Position **380/885** · Voraussetzung: `8.l.W`.
**Exakte Commit-Message:** `8.l.R feat(query): Lesende Funktionsintegration und Workparität vervollständigen`

**Vervollständigung:** Ausgabe-/Workfehler dürfen den fachlichen Scope nicht abschneiden.

**Verhaltensabnahme:** Fachresultate und Projektinventur sind in Einzellauf und vollständiger Fortsetzung gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 8.l.C – Make it Clean

- [ ] **8.l.C** · Position **381/885** · Voraussetzung: `8.l.R`.
**Exakte Commit-Message:** `8.l.C refactor(query): Lesende Funktionsintegration und Workparität bereinigen`

**Bereinigung:** Gemeinsame lesende Ausführungsfolge statt Handler-spezifischer Start-/Cleanupwege verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 8 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m9"></a>
## Meilenstein 9 – Produktkonfigurationen und Varianten

**Ziel:** Eine stabile Artefaktidentität wird in mehreren gültigen Produktkonfigurationen wiederverwendet.

**Vorgesehener Zuschnitt:** `src/specroad/configurations/, src/specroad/scope/, src/specroad/query/`. **Fachgrundlage:** §§ 10.18, 12.29–12.30; Anhang I.

**Abschlussgate:** Applicability wird vor Closure angewendet; ausgeschlossene Pflichtabhängigkeiten sind Fehler statt stiller Scopeverkleinerung. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-9-a"></a>
### 9.a – Dimensionen und Wertauswahl

**Anforderungsbezug:** `SR-REQ-0395`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.a.W – Let it Work

- [ ] **9.a.W** · Position **382/885** · Voraussetzung: `8.l.C`.
**Exakte Commit-Message:** `9.a.W feat(configuration): Dimensionen und Wertauswahl aufbauen`

**Umsetzung:** Konfiguration mit eindeutigen Namen, Dimensionen, zulässigen Werten und konkreter Auswahl validieren.

**Verhaltensabnahme:** Gültige Auswahl ergibt eine vollständige effektive Konfiguration.

#### 9.a.R – Make it Right

- [ ] **9.a.R** · Position **383/885** · Voraussetzung: `9.a.W`.
**Exakte Commit-Message:** `9.a.R feat(configuration): Dimensionen und Wertauswahl vervollständigen`

**Vervollständigung:** Unbekannte Dimensionen und falsche Werte einschließlich Typgrenzen abweisen.

**Verhaltensabnahme:** Datenfälle prüfen exakte Annahme/Ablehnung und materialisierte Auswahl. Die W-Nachweise bleiben zusätzlich grün.

#### 9.a.C – Make it Clean

- [ ] **9.a.C** · Position **384/885** · Voraussetzung: `9.a.R`.
**Exakte Commit-Message:** `9.a.C refactor(configuration): Dimensionen und Wertauswahl bereinigen`

**Bereinigung:** Konfigurationsmodell und Auflösungsalgorithmus separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-b"></a>
### 9.b – Vererbung und zyklusfreie Elternkette

**Anforderungsbezug:** `SR-REQ-0546`–`SR-REQ-0547`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.b.W – Let it Work

- [ ] **9.b.W** · Position **385/885** · Voraussetzung: `9.a.C`.
**Exakte Commit-Message:** `9.b.W feat(configuration): Vererbung und zyklusfreie Elternkette aufbauen`

**Umsetzung:** Genau einen optionalen Parent auflösen; applicability an Configuration selbst verbieten.

**Verhaltensabnahme:** Mehrstufige Vererbung ergibt die normativ kombinierte Auswahl.

#### 9.b.R – Make it Right

- [ ] **9.b.R** · Position **386/885** · Voraussetzung: `9.b.W`.
**Exakte Commit-Message:** `9.b.R feat(configuration): Vererbung und zyklusfreie Elternkette vervollständigen`

**Vervollständigung:** Selbst-/Mehrknotenzyklen und widersprüchliche Auswahl ohne teilweises Ergebnis abweisen.

**Verhaltensabnahme:** Zyklische Parentdaten terminieren mit Konfigurationsfehler. Die W-Nachweise bleiben zusätzlich grün.

#### 9.b.C – Make it Clean

- [ ] **9.b.C** · Position **387/885** · Voraussetzung: `9.b.R`.
**Exakte Commit-Message:** `9.b.C refactor(configuration): Vererbung und zyklusfreie Elternkette bereinigen`

**Bereinigung:** Elternauflösung auf die vorhandenen Graph-/Zyklusprimitiven setzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-c"></a>
### 9.c – Applicability-Auswertung

**Anforderungsbezug:** `SR-REQ-0396`–`SR-REQ-0397`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.c.W – Let it Work

- [ ] **9.c.W** · Position **388/885** · Voraussetzung: `9.b.C`.
**Exakte Commit-Message:** `9.c.W feat(configuration): Applicability-Auswertung aufbauen`

**Umsetzung:** SRX-Bedingungen ausschließlich auf ausgewählte Konfiguration und konstante Metadaten auswerten.

**Verhaltensabnahme:** Ohne Konfiguration bleibt ein bedingtes Artefakt potenziell anwendbar.

#### 9.c.R – Make it Right

- [ ] **9.c.R** · Position **389/885** · Voraussetzung: `9.c.W`.
**Exakte Commit-Message:** `9.c.R feat(configuration): Applicability-Auswertung vervollständigen`

**Vervollständigung:** Verbotene Kontextzugriffe und fehlende verpflichtende Auswahl verhindern falsche Gateentscheidung.

**Verhaltensabnahme:** Ausgewählt, ausgeschlossen und potenziell anwendbar sind getrennte fachliche Ergebnisse. Die W-Nachweise bleiben zusätzlich grün.

#### 9.c.C – Make it Clean

- [ ] **9.c.C** · Position **390/885** · Voraussetzung: `9.c.R`.
**Exakte Commit-Message:** `9.c.C refactor(configuration): Applicability-Auswertung bereinigen`

**Bereinigung:** Applicability als reine Scopevorstufe führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-d"></a>
### 9.d – Konfiguration vor Scope-Closure

**Anforderungsbezug:** `SR-REQ-0411`, `SR-REQ-0414`.
**Verifikationsbezug:** `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.d.W – Let it Work

- [ ] **9.d.W** · Position **391/885** · Voraussetzung: `9.c.C`.
**Exakte Commit-Message:** `9.d.W feat(configuration): Konfiguration vor Scope-Closure aufbauen`

**Umsetzung:** Gültigkeit vor Aufnahme von Seed-/Pflichtressourcen berücksichtigen.

**Verhaltensabnahme:** Unbedingte und passende Artefakte bilden den erwarteten Scope.

#### 9.d.R – Make it Right

- [ ] **9.d.R** · Position **392/885** · Voraussetzung: `9.d.W`.
**Exakte Commit-Message:** `9.d.R feat(configuration): Konfiguration vor Scope-Closure vervollständigen`

**Vervollständigung:** Ausgeschlossene starke Zielressource wird nicht aufgenommen oder zur Boundary abgeschwächt.

**Verhaltensabnahme:** Konfigurationskonflikt verhindert die Ausgabe einer gültigen Modellwurzel. Die W-Nachweise bleiben zusätzlich grün.

#### 9.d.C – Make it Clean

- [ ] **9.d.C** · Position **393/885** · Voraussetzung: `9.d.R`.
**Exakte Commit-Message:** `9.d.C refactor(configuration): Konfiguration vor Scope-Closure bereinigen`

**Bereinigung:** Vorfilter und Closurezulässigkeit gemeinsam verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-e"></a>
### 9.e – Pflichtabhängigkeiten und Erklärungspfad

**Anforderungsbezug:** `SR-REQ-0398`–`SR-REQ-0399`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.e.W – Let it Work

- [ ] **9.e.W** · Position **394/885** · Voraussetzung: `9.d.C`.
**Exakte Commit-Message:** `9.e.W feat(configuration): Pflichtabhängigkeiten und Erklärungspfad aufbauen`

**Umsetzung:** configuration evaluate mit anwendbarer Menge und kürzestem inkonsistentem Abhängigkeitspfad implementieren.

**Verhaltensabnahme:** Exakte ausgeschlossene Pflichtabhängigkeit lässt sich aus der Fachprojektion nachvollziehen.

#### 9.e.R – Make it Right

- [ ] **9.e.R** · Position **395/885** · Voraussetzung: `9.e.W`.
**Exakte Commit-Message:** `9.e.R feat(configuration): Pflichtabhängigkeiten und Erklärungspfad vervollständigen`

**Vervollständigung:** Mehrere gleichartige Pfade deterministisch behandeln, ohne unnötige Textsemantik.

**Verhaltensabnahme:** Graphfixture weist kürzesten vollständigen Fehlerpfad und unverändertes Projekt nach. Die W-Nachweise bleiben zusätzlich grün.

#### 9.e.C – Make it Clean

- [ ] **9.e.C** · Position **396/885** · Voraussetzung: `9.e.R`.
**Exakte Commit-Message:** `9.e.C refactor(configuration): Pflichtabhängigkeiten und Erklärungspfad bereinigen`

**Bereinigung:** Erklärungspfade auf denselben Traversierungskern wie Why stützen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-f"></a>
### 9.f – Explizite Gates und wiederverwendbare Identität

**Anforderungsbezug:** `SR-REQ-0402`, `SR-REQ-0548`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.f.W – Let it Work

- [ ] **9.f.W** · Position **397/885** · Voraussetzung: `9.e.C`.
**Exakte Commit-Message:** `9.f.W feat(configuration): Explizite Gates und wiederverwendbare Identität aufbauen`

**Umsetzung:** Konfigurationsgebundene Gates verlangen explizite Auswahl; Referenzen bleiben dieselben IDs.

**Verhaltensabnahme:** Dasselbe Requirement wird ohne Kopie in zwei Varianten verwendet.

#### 9.f.R – Make it Right

- [ ] **9.f.R** · Position **398/885** · Voraussetzung: `9.f.W`.
**Exakte Commit-Message:** `9.f.R feat(configuration): Explizite Gates und wiederverwendbare Identität vervollständigen`

**Vervollständigung:** Fehlende Auswahl darf keine willkürliche Defaultfreigabe erzeugen.

**Verhaltensabnahme:** ID-/Revisionsinventur bleibt bei reiner Variantenauswertung unverändert. Die W-Nachweise bleiben zusätzlich grün.

#### 9.f.C – Make it Clean

- [ ] **9.f.C** · Position **399/885** · Voraussetzung: `9.f.R`.
**Exakte Commit-Message:** `9.f.C refactor(configuration): Explizite Gates und wiederverwendbare Identität bereinigen`

**Bereinigung:** Gatekontext von gespeicherten Artefakten trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-g"></a>
### 9.g – Konfigurationsoption in vorhandenen Fachbefehlen

**Anforderungsbezug:** `SR-REQ-0400`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.g.W – Let it Work

- [ ] **9.g.W** · Position **400/885** · Voraussetzung: `9.f.C`.
**Exakte Commit-Message:** `9.g.W feat(configuration): Konfigurationsoption in vorhandenen Fachbefehlen aufbauen`

**Umsetzung:** Validate, Query/Viewschnittstelle und Scopebereitstellung mit gebundener configuration_id integrieren.

**Verhaltensabnahme:** Vorhandene Befehle verwenden dieselbe effektive Konfiguration.

#### 9.g.R – Make it Right

- [ ] **9.g.R** · Position **401/885** · Voraussetzung: `9.g.W`.
**Exakte Commit-Message:** `9.g.R feat(configuration): Konfigurationsoption in vorhandenen Fachbefehlen vervollständigen`

**Vervollständigung:** Später hinzukommende Baseline-, Evidence-, Export- und Bundleadapter müssen denselben Vertrag ausdrücklich übernehmen.

**Verhaltensabnahme:** Jede bereits vorhandene Operation liefert dieselbe Scopewurzel für denselben Konfigurationsinput. Die W-Nachweise bleiben zusätzlich grün.

#### 9.g.C – Make it Clean

- [ ] **9.g.C** · Position **402/885** · Voraussetzung: `9.g.R`.
**Exakte Commit-Message:** `9.g.C refactor(configuration): Konfigurationsoption in vorhandenen Fachbefehlen bereinigen`

**Bereinigung:** Eine gemeinsame Konfigurationsauflösung statt versteckter Defaultwerte je Handler nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-9-h"></a>
### 9.h – Varianten-Diff und Regression

**Anforderungsbezug:** `SR-REQ-0403`–`SR-REQ-0404`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 9.h.W – Let it Work

- [ ] **9.h.W** · Position **403/885** · Voraussetzung: `9.g.C`.
**Exakte Commit-Message:** `9.h.W feat(configuration): Varianten-Diff und Regression aufbauen`

**Umsetzung:** Scopeänderungen durch Parent-/Wert-/Applicabilitywechsel separat klassifizieren.

**Verhaltensabnahme:** Änderung zeigt die tatsächlich hinzugekommenen und entfallenen IDs.

#### 9.h.R – Make it Right

- [ ] **9.h.R** · Position **404/885** · Voraussetzung: `9.h.W`.
**Exakte Commit-Message:** `9.h.R feat(configuration): Varianten-Diff und Regression vervollständigen`

**Vervollständigung:** Verschachtelung, ungültige Werte und zyklische Vererbung im bestehenden Verhaltenstestkorpus schließen.

**Verhaltensabnahme:** Einzellauf-/Workparität und schreibfreie Auswertung bleiben für Varianten erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 9.h.C – Make it Clean

- [ ] **9.h.C** · Position **405/885** · Voraussetzung: `9.h.R`.
**Exakte Commit-Message:** `9.h.C refactor(configuration): Varianten-Diff und Regression bereinigen`

**Bereinigung:** Variantenvergleich in den allgemeinen Diffklassifikator integrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 9 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m10"></a>
## Meilenstein 10 – Baselines und unveränderbare Referenzstände

**Ziel:** Arbeitsbaselines als unveränderbare, Git-unabhängig verifizierbare Snapshots.

**Vorgesehener Zuschnitt:** `src/specroad/baselines/, src/specroad/archive/, src/specroad/diff/`. **Fachgrundlage:** §§ 10.8–10.11, 12.11; Anhänge E, L.

**Abschlussgate:** Working-Baselines sind vollständig nutzbar; Release-Baselines bleiben bis zum echten Readiness-Gate aus M13 fail-closed. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-10-a"></a>
### 10.a – Content-addressierter Objektspeicher

**Anforderungsbezug:** `SR-REQ-0143`, `SR-REQ-0145`, `SR-REQ-0148`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.a.W – Let it Work

- [ ] **10.a.W** · Position **406/885** · Voraussetzung: `9.h.C`.
**Exakte Commit-Message:** `10.a.W feat(baseline): Content-addressierter Objektspeicher aufbauen`

**Umsetzung:** Kanonische JSON- und unveränderte Anhangsbytes unter hashgebundenen Objektpfaden speichern.

**Verhaltensabnahme:** Derselbe Inhalt wird dedupliziert und bleibt byteidentisch verfügbar.

#### 10.a.R – Make it Right

- [ ] **10.a.R** · Position **407/885** · Voraussetzung: `10.a.W`.
**Exakte Commit-Message:** `10.a.R feat(baseline): Content-addressierter Objektspeicher vervollständigen`

**Vervollständigung:** Hashkollision im Zielpfad, manipulierter Inhalt und referenzierte Löschung abweisen.

**Verhaltensabnahme:** Mehrere Baselines können dasselbe unveränderte Objekt sicher teilen. Die W-Nachweise bleiben zusätzlich grün.

#### 10.a.C – Make it Clean

- [ ] **10.a.C** · Position **408/885** · Voraussetzung: `10.a.R`.
**Exakte Commit-Message:** `10.a.C refactor(baseline): Content-addressierter Objektspeicher bereinigen`

**Bereinigung:** Objektstore von Baselinefachmodell und Gitprovenienz trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-b"></a>
### 10.b – Baseline-Manifest und semantische Konfiguration

**Anforderungsbezug:** `SR-REQ-0144`, `SR-REQ-0146`–`SR-REQ-0147`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.b.W – Let it Work

- [ ] **10.b.W** · Position **409/885** · Voraussetzung: `10.a.C`.
**Exakte Commit-Message:** `10.b.W feat(baseline): Baseline-Manifest und semantische Konfiguration aufbauen`

**Umsetzung:** Art, Scope, Profile, Regeln, Mappings, Konfiguration und vollständige Objektliste binden.

**Verhaltensabnahme:** Manifestwurzel stimmt mit dem Snapshot vor Erzeugen des Baselineartefakts überein.

#### 10.b.R – Make it Right

- [ ] **10.b.R** · Position **410/885** · Voraussetzung: `10.b.W`.
**Exakte Commit-Message:** `10.b.R feat(baseline): Baseline-Manifest und semantische Konfiguration vervollständigen`

**Vervollständigung:** Eigene Baseline nicht rekursiv in ihre Basis aufnehmen; operative Daten nicht in Modellhash mischen.

**Verhaltensabnahme:** Laufzeitpfad-/Zeitwechsel beeinflusst die gebundene Fachwurzel nicht. Die W-Nachweise bleiben zusätzlich grün.

#### 10.b.C – Make it Clean

- [ ] **10.b.C** · Position **411/885** · Voraussetzung: `10.b.R`.
**Exakte Commit-Message:** `10.b.C refactor(baseline): Baseline-Manifest und semantische Konfiguration bereinigen`

**Bereinigung:** Manifestaufbau denselben Scope-/Hashkern wie Projektvergleich verwenden lassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-c"></a>
### 10.c – Working-Baseline atomar erzeugen

**Anforderungsbezug:** `SR-REQ-0149`, `SR-REQ-0433`.
**Verifikationsbezug:** `SR-VER-0011`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.c.W – Let it Work

- [ ] **10.c.W** · Position **412/885** · Voraussetzung: `10.b.C`.
**Exakte Commit-Message:** `10.c.W feat(baseline): Working-Baseline atomar erzeugen aufbauen`

**Umsetzung:** baseline create für working nach vollständiger Zielprüfung über Spezialwrite implementieren.

**Verhaltensabnahme:** Neuer Datensatz entsteht sealed/approved und ist unveränderbar.

#### 10.c.R – Make it Right

- [ ] **10.c.R** · Position **413/885** · Voraussetzung: `10.c.W`.
**Exakte Commit-Message:** `10.c.R feat(baseline): Working-Baseline atomar erzeugen vervollständigen`

**Vervollständigung:** Ungültiges Modell oder unvollständige Objektbytes verhindern Veröffentlichung.

**Verhaltensabnahme:** Fault-Injection hinterlässt keine gültig behauptete Teilbaseline. Die W-Nachweise bleiben zusätzlich grün.

#### 10.c.C – Make it Clean

- [ ] **10.c.C** · Position **414/885** · Voraussetzung: `10.c.R`.
**Exakte Commit-Message:** `10.c.C refactor(baseline): Working-Baseline atomar erzeugen bereinigen`

**Bereinigung:** Snapshotvorbereitung und transaktionale Baselinepublikation klar trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-d"></a>
### 10.d – Baseline-Integrität prüfen

**Anforderungsbezug:** `SR-REQ-0151`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.d.W – Let it Work

- [ ] **10.d.W** · Position **415/885** · Voraussetzung: `10.c.C`.
**Exakte Commit-Message:** `10.d.W feat(baseline): Baseline-Integrität prüfen aufbauen`

**Umsetzung:** Objektbytes, Ressourcenhashes, Manifest und rekonstruierte Modellwurzel schreibfrei prüfen.

**Verhaltensabnahme:** Intakter Snapshot ist ohne ursprünglichen Arbeitsstand verifizierbar.

#### 10.d.R – Make it Right

- [ ] **10.d.R** · Position **416/885** · Voraussetzung: `10.d.W`.
**Exakte Commit-Message:** `10.d.R feat(baseline): Baseline-Integrität prüfen vervollständigen`

**Vervollständigung:** Fehlendes Objekt, geänderter Hash oder manipulierte Konfiguration wird erkannt.

**Verhaltensabnahme:** Basisverifikation verändert weder Objekte noch Projektdaten. Die W-Nachweise bleiben zusätzlich grün.

#### 10.d.C – Make it Clean

- [ ] **10.d.C** · Position **417/885** · Voraussetzung: `10.d.R`.
**Exakte Commit-Message:** `10.d.C refactor(baseline): Baseline-Integrität prüfen bereinigen`

**Bereinigung:** Baselineleser als Validatorquelle in der gemeinsamen Pipeline registrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-e"></a>
### 10.e – Baseline anzeigen und materialisieren

**Anforderungsbezug:** `SR-REQ-0153`, `SR-REQ-0220`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.e.W – Let it Work

- [ ] **10.e.W** · Position **418/885** · Voraussetzung: `10.d.C`.
**Exakte Commit-Message:** `10.e.W feat(baseline): Baseline anzeigen und materialisieren aufbauen`

**Umsetzung:** Gespeichertes Manifest und neu berechneten Integritätsstatus liefern; verifizierten Snapshot isoliert materialisieren.

**Verhaltensabnahme:** Baseline funktioniert ohne Gitrepository.

#### 10.e.R – Make it Right

- [ ] **10.e.R** · Position **419/885** · Voraussetzung: `10.e.W`.
**Exakte Commit-Message:** `10.e.R feat(baseline): Baseline anzeigen und materialisieren vervollständigen`

**Vervollständigung:** Fehlende Originalbytes nicht aus aktuellem Modell ersetzen.

**Verhaltensabnahme:** Unabhängige Materialisierung erhält die gespeicherten Fachwerte und Hashes. Die W-Nachweise bleiben zusätzlich grün.

#### 10.e.C – Make it Clean

- [ ] **10.e.C** · Position **420/885** · Voraussetzung: `10.e.R`.
**Exakte Commit-Message:** `10.e.C refactor(baseline): Baseline anzeigen und materialisieren bereinigen`

**Bereinigung:** Anzeigenprojektion und sichere Materialisierung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-f"></a>
### 10.f – Baselinevergleich und Diffquellenadapter

**Anforderungsbezug:** `SR-REQ-0114`, `SR-REQ-0152`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.f.W – Let it Work

- [ ] **10.f.W** · Position **421/885** · Voraussetzung: `10.e.C`.
**Exakte Commit-Message:** `10.f.W feat(baseline): Baselinevergleich und Diffquellenadapter aufbauen`

**Umsetzung:** Baselines an die Quellenregistry und denselben semantischen Diff anschließen.

**Verhaltensabnahme:** Baseline-gegen-Baseline und materialisiertes Projekt ergeben gleichen Felddiff.

#### 10.f.R – Make it Right

- [ ] **10.f.R** · Position **422/885** · Voraussetzung: `10.f.W`.
**Exakte Commit-Message:** `10.f.R feat(baseline): Baselinevergleich und Diffquellenadapter vervollständigen`

**Vervollständigung:** Fremde project_id, fehlende Objekte und inkompatible Historienleser ablehnen.

**Verhaltensabnahme:** Kein Vergleich benötigt Checkout oder mutiert den Arbeitsstand. Die W-Nachweise bleiben zusätzlich grün.

#### 10.f.C – Make it Clean

- [ ] **10.f.C** · Position **423/885** · Voraussetzung: `10.f.R`.
**Exakte Commit-Message:** `10.f.C refactor(baseline): Baselinevergleich und Diffquellenadapter bereinigen`

**Bereinigung:** Baselineadapter liefert ausschließlich geprüfte Snapshots statt eigener Diffsemantik.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-g"></a>
### 10.g – Konfigurationsgebundene Baselines

**Anforderungsbezug:** `SR-REQ-0401`.
**Verifikationsbezug:** `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.g.W – Let it Work

- [ ] **10.g.W** · Position **424/885** · Voraussetzung: `10.f.C`.
**Exakte Commit-Message:** `10.g.W feat(baseline): Konfigurationsgebundene Baselines aufbauen`

**Umsetzung:** Auswahl-ID, Revision, Hash und resultierenden Artefaktumfang in der Baseline speichern.

**Verhaltensabnahme:** Zwei Variantenbaselines bewahren ihre jeweils konkrete Auswahl.

#### 10.g.R – Make it Right

- [ ] **10.g.R** · Position **425/885** · Voraussetzung: `10.g.W`.
**Exakte Commit-Message:** `10.g.R feat(baseline): Konfigurationsgebundene Baselines vervollständigen`

**Vervollständigung:** Veränderter Parent-/Konfigurationshash invalidiert nicht die Originalbaseline, sondern unterscheidet den aktuellen Arbeitsstand.

**Verhaltensabnahme:** Snapshot bleibt verifizierbar und zeigt die historisch gebundene Variante. Die W-Nachweise bleiben zusätzlich grün.

#### 10.g.C – Make it Clean

- [ ] **10.g.C** · Position **426/885** · Voraussetzung: `10.g.R`.
**Exakte Commit-Message:** `10.g.C refactor(baseline): Konfigurationsgebundene Baselines bereinigen`

**Bereinigung:** Variantensnapshot auf gemeinsamen Konfigurations-/Scopevertrag reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-h"></a>
### 10.h – Release-Baseline-Grenze vorbereiten

**Anforderungsbezug:** `SR-REQ-0150`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.h.W – Let it Work

- [ ] **10.h.W** · Position **427/885** · Voraussetzung: `10.g.C`.
**Exakte Commit-Message:** `10.h.W feat(baseline): Release-Baseline-Grenze vorbereiten aufbauen`

**Umsetzung:** Releaseart und Gateanschluss vorsehen, aber Veröffentlichung ohne implementierte gespeicherte Bewertungsauswahl verweigern.

**Verhaltensabnahme:** Working-Baseline ist nutzbar; nicht erfüllbares Releasegate bleibt geschlossen.

#### 10.h.R – Make it Right

- [ ] **10.h.R** · Position **428/885** · Voraussetzung: `10.h.W`.
**Exakte Commit-Message:** `10.h.R feat(baseline): Release-Baseline-Grenze vorbereiten vervollständigen`

**Vervollständigung:** Keine Stub-Readiness oder automatisch bestandene Bewertung als Ersatz zulassen.

**Verhaltensabnahme:** Releasecreate ohne echte M13-Readiness erzeugt keine Baseline. Die W-Nachweise bleiben zusätzlich grün.

#### 10.h.C – Make it Clean

- [ ] **10.h.C** · Position **429/885** · Voraussetzung: `10.h.R`.
**Exakte Commit-Message:** `10.h.C refactor(baseline): Release-Baseline-Grenze vorbereiten bereinigen`

**Bereinigung:** Gateinterface so kapseln, dass M13 die vollständige Releasebaseline freischaltet.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-10-i"></a>
### 10.i – Snapshot-Workparität und Crashregression

**Anforderungsbezug:** `SR-REQ-0143`, `SR-REQ-0148`–`SR-REQ-0149`.
**Verifikationsbezug:** `SR-VER-0011`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 10.i.W – Let it Work

- [ ] **10.i.W** · Position **430/885** · Voraussetzung: `10.h.C`.
**Exakte Commit-Message:** `10.i.W feat(baseline): Snapshot-Workparität und Crashregression aufbauen`

**Umsetzung:** Große Baselines mit blockweiser Objektsicherung und Workfortsetzung integrieren.

**Verhaltensabnahme:** Geteilter Aufbau liefert dasselbe vollständige Manifest wie ein Einzellauf.

#### 10.i.R – Make it Right

- [ ] **10.i.R** · Position **431/885** · Voraussetzung: `10.i.W`.
**Exakte Commit-Message:** `10.i.R feat(baseline): Snapshot-Workparität und Crashregression vervollständigen`

**Vervollständigung:** Abbruch, veraltete Basis und verloren gegangene Objekte erhalten vorhandene Baselines.

**Verhaltensabnahme:** Hashinventur beweist immutable Bestände und vollständiges neues Ergebnis oder keinen Abschluss. Die W-Nachweise bleiben zusätzlich grün.

#### 10.i.C – Make it Clean

- [ ] **10.i.C** · Position **432/885** · Voraussetzung: `10.i.R`.
**Exakte Commit-Message:** `10.i.C refactor(baseline): Snapshot-Workparität und Crashregression bereinigen`

**Bereinigung:** Wiederverwendbare Snapshottests statt paralleler Baseline-Speicherlogik führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 10 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m11"></a>
## Meilenstein 11 – Dokumentmodell, Ansichten und Berichtserzeugung

**Ziel:** Dokumente und Ansichten verwenden das eine Fachmodell; keine zweite manuell gepflegte Datenbasis.

**Vorgesehener Zuschnitt:** `src/specroad/documents/, src/specroad/views/, src/specroad/rendering/`. **Fachgrundlage:** §§ 10.14, 12.8, 12.23, 12.26, 12.35; Anhang S.

**Abschlussgate:** Komposition und sichere Datenprojektion sind getestet; Markdown-/HTML-/Diagrammdarstellung wird implementiert, aber nicht durch Ausgabe- oder Doku-Tests festgezurrt. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-11-a"></a>
### 11.a – Dokumentrolle und Primärdokument

**Anforderungsbezug:** `SR-REQ-0299`, `SR-REQ-0312`, `SR-REQ-0467`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.a.W – Let it Work

- [ ] **11.a.W** · Position **433/885** · Voraussetzung: `10.i.C`.
**Exakte Commit-Message:** `11.a.W feat(documents): Dokumentrolle und Primärdokument aufbauen`

**Umsetzung:** Document-Daten und genau ein aktives primary_specification im Vollprojekt validieren.

**Verhaltensabnahme:** Ein gültiges Vollprojekt besitzt genau eine eindeutige Primärspezifikation.

#### 11.a.R – Make it Right

- [ ] **11.a.R** · Position **434/885** · Voraussetzung: `11.a.W`.
**Exakte Commit-Message:** `11.a.R feat(documents): Dokumentrolle und Primärdokument vervollständigen`

**Vervollständigung:** Fehlendes/mehrfaches Primärdokument und unzulässige Rollen blockieren; Partial/Legacy-Fallback bleibt ausdrücklich getrennt.

**Verhaltensabnahme:** Datenfixtures prüfen Rollenanzahl und Annahme/Ablehnung statt gerenderter Überschriften. Die W-Nachweise bleiben zusätzlich grün.

#### 11.a.C – Make it Clean

- [ ] **11.a.C** · Position **435/885** · Voraussetzung: `11.a.R`.
**Exakte Commit-Message:** `11.a.C refactor(documents): Dokumentrolle und Primärdokument bereinigen`

**Bereinigung:** Dokumentinvarianten in die gemeinsame Validation registrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-b"></a>
### 11.b – Abschnittseigentum und Ordnung

**Anforderungsbezug:** `SR-REQ-0300`, `SR-REQ-0303`, `SR-REQ-0524`, `SR-REQ-0526`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.b.W – Let it Work

- [ ] **11.b.W** · Position **436/885** · Voraussetzung: `11.a.C`.
**Exakte Commit-Message:** `11.b.W feat(documents): Abschnittseigentum und Ordnung aufbauen`

**Umsetzung:** Eine eingehende contains-Beziehung je Abschnitt und fachliche position-/ID-Ordnung auswerten.

**Verhaltensabnahme:** Verschachtelte Abschnitte bilden dieselbe Datenkomposition unabhängig von Dateireihenfolge.

#### 11.b.R – Make it Right

- [ ] **11.b.R** · Position **437/885** · Voraussetzung: `11.b.W`.
**Exakte Commit-Message:** `11.b.R feat(documents): Abschnittseigentum und Ordnung vervollständigen`

**Vervollständigung:** Mehrfache Eltern, negative Position und Ordnungsdubletten nach Vertragsregeln behandeln.

**Verhaltensabnahme:** Tests vergleichen gespeicherte Relation/Position und Kompositions-IDs, nicht visuelle Reihenfolge einer Ausgabe. Die W-Nachweise bleiben zusätzlich grün.

#### 11.b.C – Make it Clean

- [ ] **11.b.C** · Position **438/885** · Voraussetzung: `11.b.R`.
**Exakte Commit-Message:** `11.b.C refactor(documents): Abschnittseigentum und Ordnung bereinigen`

**Bereinigung:** Kompositionsbaum aus Graphdaten ableiten statt separat speichern.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-c"></a>
### 11.c – Exakte Inhaltsblockschemas

**Anforderungsbezug:** `SR-REQ-0301`, `SR-REQ-0468`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.c.W – Let it Work

- [ ] **11.c.W** · Position **439/885** · Voraussetzung: `11.b.C`.
**Exakte Commit-Message:** `11.c.W feat(documents): Exakte Inhaltsblockschemas aufbauen`

**Umsetzung:** Alle sieben Blockarten mit genau ihrem zugehörigen Payloadschema implementieren.

**Verhaltensabnahme:** Gültige prose/artifact_ref/query/table/admonition/page_break/include_document-Daten sind ladbar.

#### 11.c.R – Make it Right

- [ ] **11.c.R** · Position **440/885** · Voraussetzung: `11.c.W`.
**Exakte Commit-Message:** `11.c.R feat(documents): Exakte Inhaltsblockschemas vervollständigen`

**Vervollständigung:** Fremde Felder, gemischte Payloadarten und unvollständige Referenzen ablehnen.

**Verhaltensabnahme:** Schemafälle sichern Datenvertrag ohne Rendering-Snapshots. Die W-Nachweise bleiben zusätzlich grün.

#### 11.c.C – Make it Clean

- [ ] **11.c.C** · Position **441/885** · Voraussetzung: `11.c.R`.
**Exakte Commit-Message:** `11.c.C refactor(documents): Exakte Inhaltsblockschemas bereinigen`

**Bereinigung:** Blocktypregister und Payloadvalidatoren zentralisieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-d"></a>
### 11.d – Artefaktreferenzen ohne Kopien

**Anforderungsbezug:** `SR-REQ-0302`, `SR-REQ-0310`, `SR-REQ-0525`, `SR-REQ-0530`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.d.W – Let it Work

- [ ] **11.d.W** · Position **442/885** · Voraussetzung: `11.c.C`.
**Exakte Commit-Message:** `11.d.W feat(documents): Artefaktreferenzen ohne Kopien aufbauen`

**Umsetzung:** artifact_ref ausschließlich über genau eine references-Relation auflösen.

**Verhaltensabnahme:** Dasselbe Artefakt wird in mehreren Dokumenten mit derselben Identität verwendet.

#### 11.d.R – Make it Right

- [ ] **11.d.R** · Position **443/885** · Voraussetzung: `11.d.W`.
**Exakte Commit-Message:** `11.d.R feat(documents): Artefaktreferenzen ohne Kopien vervollständigen`

**Vervollständigung:** Doppelte Target-ID oder Fachkopie im Payload abweisen.

**Verhaltensabnahme:** Aktualisierung des Fachartefakts wird in allen Datenprojektionen sichtbar ohne Referenzrevisionen zu fälschen. Die W-Nachweise bleiben zusätzlich grün.

#### 11.d.C – Make it Clean

- [ ] **11.d.C** · Position **444/885** · Voraussetzung: `11.d.R`.
**Exakte Commit-Message:** `11.d.C refactor(documents): Artefaktreferenzen ohne Kopien bereinigen`

**Bereinigung:** Referenzauflösung von Formatausgabe und Dokumentownership trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-e"></a>
### 11.e – Sicheres CommonMark-Kernsubset

**Anforderungsbezug:** `SR-REQ-0304`, `SR-REQ-0469`, `SR-REQ-0527`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.e.W – Let it Work

- [ ] **11.e.W** · Position **445/885** · Voraussetzung: `11.d.C`.
**Exakte Commit-Message:** `11.e.W feat(documents): Sicheres CommonMark-Kernsubset aufbauen`

**Umsetzung:** Prosa/Admonition auf die erlaubten deklarativen Inhaltsknoten parsen.

**Verhaltensabnahme:** Zulässiger Text wird als inert strukturierte Inhaltsdaten verarbeitet.

#### 11.e.R – Make it Right

- [ ] **11.e.R** · Position **446/885** · Voraussetzung: `11.e.W`.
**Exakte Commit-Message:** `11.e.R feat(documents): Sicheres CommonMark-Kernsubset vervollständigen`

**Vervollständigung:** Aktives HTML, Skripte und externe Includes nicht in ausführbare Knoten übernehmen.

**Verhaltensabnahme:** Parser-/Sicherheitsfälle prüfen erlaubte Knoten und verbotene Effekte, nicht resultierende Markdown-/HTMLbytes. Die W-Nachweise bleiben zusätzlich grün.

#### 11.e.C – Make it Clean

- [ ] **11.e.C** · Position **447/885** · Voraussetzung: `11.e.R`.
**Exakte Commit-Message:** `11.e.C refactor(documents): Sicheres CommonMark-Kernsubset bereinigen`

**Bereinigung:** Parser, sichere Knoten und Renderer als getrennte Schichten führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-f"></a>
### 11.f – Query- und Tabellenblöcke

**Anforderungsbezug:** `SR-REQ-0305`–`SR-REQ-0306`, `SR-REQ-0528`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.f.W – Let it Work

- [ ] **11.f.W** · Position **448/885** · Voraussetzung: `11.e.C`.
**Exakte Commit-Message:** `11.f.W feat(documents): Query- und Tabellenblöcke aufbauen`

**Umsetzung:** Datenquellen, Spalten, Sortierung und SRX/Querybindung aus dem gewählten Snapshot auflösen.

**Verhaltensabnahme:** Ein Tabellenblock enthält fachlich die erwarteten Datensätze aus demselben Modellstand.

#### 11.f.R – Make it Right

- [ ] **11.f.R** · Position **449/885** · Voraussetzung: `11.f.W`.
**Exakte Commit-Message:** `11.f.R feat(documents): Query- und Tabellenblöcke vervollständigen`

**Vervollständigung:** Templatecode, fremde Datenquellen und fehlende View-ID ablehnen.

**Verhaltensabnahme:** Datensatz-/Scopevergleich und Sicherheitsgrenzen werden geprüft, keine Tabellenoptik. Die W-Nachweise bleiben zusätzlich grün.

#### 11.f.C – Make it Clean

- [ ] **11.f.C** · Position **450/885** · Voraussetzung: `11.f.R`.
**Exakte Commit-Message:** `11.f.C refactor(documents): Query- und Tabellenblöcke bereinigen`

**Bereinigung:** Bestehende Queryengine statt eigener Blockabfragesprache verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-g"></a>
### 11.g – Include-Graph und Zyklusprüfung

**Anforderungsbezug:** `SR-REQ-0307`, `SR-REQ-0470`, `SR-REQ-0529`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.g.W – Let it Work

- [ ] **11.g.W** · Position **451/885** · Voraussetzung: `11.f.C`.
**Exakte Commit-Message:** `11.g.W feat(documents): Include-Graph und Zyklusprüfung aufbauen`

**Umsetzung:** Include-Dokumente und contains-Komposition vor Materialisierung auf Zyklen prüfen.

**Verhaltensabnahme:** Azyklische Mehrfachverwendung ergibt vollständige Datenkomposition.

#### 11.g.R – Make it Right

- [ ] **11.g.R** · Position **452/885** · Voraussetzung: `11.g.W`.
**Exakte Commit-Message:** `11.g.R feat(documents): Include-Graph und Zyklusprüfung vervollständigen`

**Vervollständigung:** Direkter/transitiver Selbstinclude wird vor Rendering abgewiesen.

**Verhaltensabnahme:** Ein Mehrdokumentzyklus terminiert als Modellfehler ohne externe Ausführung. Die W-Nachweise bleiben zusätzlich grün.

#### 11.g.C – Make it Clean

- [ ] **11.g.C** · Position **453/885** · Voraussetzung: `11.g.R`.
**Exakte Commit-Message:** `11.g.C refactor(documents): Include-Graph und Zyklusprüfung bereinigen`

**Bereinigung:** Gemeinsame Graphprüfung für Dokument- und Includeabhängigkeiten nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-h"></a>
### 11.h – Dokument- und Abschnittsauthoring

**Anforderungsbezug:** `SR-REQ-0308`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.h.W – Let it Work

- [ ] **11.h.W** · Position **454/885** · Voraussetzung: `11.g.C`.
**Exakte Commit-Message:** `11.h.W feat(documents): Dokument- und Abschnittsauthoring aufbauen`

**Umsetzung:** document create, section add und section move über den gemeinsamen Writer anbieten.

**Verhaltensabnahme:** Verschieben aktualisiert genau die betroffenen Dokumentrelationen.

#### 11.h.R – Make it Right

- [ ] **11.h.R** · Position **455/885** · Voraussetzung: `11.h.W`.
**Exakte Commit-Message:** `11.h.R feat(documents): Dokument- und Abschnittsauthoring vervollständigen`

**Vervollständigung:** Ungültiger Parent, Kreisbildung und stale Vorbedingung ohne Teilwrite ablehnen.

**Verhaltensabnahme:** Artefakt-/Relationsinventur weist atomare Umordnung nach. Die W-Nachweise bleiben zusätzlich grün.

#### 11.h.C – Make it Clean

- [ ] **11.h.C** · Position **456/885** · Voraussetzung: `11.h.R`.
**Exakte Commit-Message:** `11.h.C refactor(documents): Dokument- und Abschnittsauthoring bereinigen`

**Bereinigung:** CLIkomfort ausschließlich in typisierte Graphoperationen übersetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-i"></a>
### 11.i – Entfernen und Blockauthoring

**Anforderungsbezug:** `SR-REQ-0308`, `SR-REQ-0471`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.i.W – Let it Work

- [ ] **11.i.W** · Position **457/885** · Voraussetzung: `11.h.C`.
**Exakte Commit-Message:** `11.i.W feat(documents): Entfernen und Blockauthoring aufbauen`

**Umsetzung:** block add/update/remove und section remove mit cascade oder move-children-to implementieren.

**Verhaltensabnahme:** Explizite Strategie ergibt das erwartete gültige Zielmodell.

#### 11.i.R – Make it Right

- [ ] **11.i.R** · Position **458/885** · Voraussetzung: `11.i.W`.
**Exakte Commit-Message:** `11.i.R feat(documents): Entfernen und Blockauthoring vervollständigen`

**Vervollständigung:** Nichtleeren Abschnitt ohne eindeutige Strategie sowie widersprüchliche Optionen abweisen.

**Verhaltensabnahme:** Fehlversuch lässt Kinder und Beziehungen vollständig bestehen. Die W-Nachweise bleiben zusätzlich grün.

#### 11.i.C – Make it Clean

- [ ] **11.i.C** · Position **459/885** · Voraussetzung: `11.i.R`.
**Exakte Commit-Message:** `11.i.C refactor(documents): Entfernen und Blockauthoring bereinigen`

**Bereinigung:** Gemeinsame Operationserzeuger für Abschnitts- und Blockmutation nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-j"></a>
### 11.j – Revisionserhalt bei Komposition

**Anforderungsbezug:** `SR-REQ-0309`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.j.W – Let it Work

- [ ] **11.j.W** · Position **460/885** · Voraussetzung: `11.i.C`.
**Exakte Commit-Message:** `11.j.W feat(documents): Revisionserhalt bei Komposition aufbauen`

**Umsetzung:** Inhaltsartefakte beim Umordnen von Referenzen unverändert erhalten.

**Verhaltensabnahme:** Move betrifft nur tatsächlich geänderte Dokumentressourcen.

#### 11.j.R – Make it Right

- [ ] **11.j.R** · Position **461/885** · Voraussetzung: `11.j.W`.
**Exakte Commit-Message:** `11.j.R feat(documents): Revisionserhalt bei Komposition vervollständigen`

**Vervollständigung:** Referenzierter Inhalt und seine Freigabe dürfen keine künstliche Revision erhalten.

**Verhaltensabnahme:** Vorher-/Nachherhashes belegen unveränderte Requirements, Tests und Code-Refs. Die W-Nachweise bleiben zusätzlich grün.

#### 11.j.C – Make it Clean

- [ ] **11.j.C** · Position **462/885** · Voraussetzung: `11.j.R`.
**Exakte Commit-Message:** `11.j.C refactor(documents): Revisionserhalt bei Komposition bereinigen`

**Bereinigung:** Ownership- und Referenzkanten im Writer explizit auseinanderhalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-k"></a>
### 11.k – Viewdefinition und Relationsprojektion

**Anforderungsbezug:** `SR-REQ-0349`–`SR-REQ-0353`, `SR-REQ-0538`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.k.W – Let it Work

- [ ] **11.k.W** · Position **463/885** · Voraussetzung: `11.j.C`.
**Exakte Commit-Message:** `11.k.W feat(documents): Viewdefinition und Relationsprojektion aufbauen`

**Umsetzung:** Deklarative View mit Scope, Spalten, Filter, Gruppierung und begrenzten Relationsprojektionen implementieren.

**Verhaltensabnahme:** Viewdaten ergeben die erwarteten fachlichen Werte für denselben Snapshot.

#### 11.k.R – Make it Right

- [ ] **11.k.R** · Position **464/885** · Voraussetzung: `11.k.W`.
**Exakte Commit-Message:** `11.k.R feat(documents): Viewdefinition und Relationsprojektion vervollständigen`

**Vervollständigung:** Fremde Funktionen, Templates und unzulässige Projektionspfade zurückweisen.

**Verhaltensabnahme:** Daten-/Sicherheitsfälle sichern Quellen und Graphgrenzen ohne Layoutassertions. Die W-Nachweise bleiben zusätzlich grün.

#### 11.k.C – Make it Clean

- [ ] **11.k.C** · Position **465/885** · Voraussetzung: `11.k.R`.
**Exakte Commit-Message:** `11.k.C refactor(documents): Viewdefinition und Relationsprojektion bereinigen`

**Bereinigung:** Viewplanung von Renderingformaten entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-l"></a>
### 11.l – Stabile Viewdaten und Varianten

**Anforderungsbezug:** `SR-REQ-0400`, `SR-REQ-0539`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0028`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.l.W – Let it Work

- [ ] **11.l.W** · Position **466/885** · Voraussetzung: `11.k.C`.
**Exakte Commit-Message:** `11.l.W feat(documents): Stabile Viewdaten und Varianten aufbauen`

**Umsetzung:** ID-Tie-Breaker und Konfigurationsbindung in der fachlichen Viewprojektion einsetzen.

**Verhaltensabnahme:** Gleiche Werte und Auswahl ergeben dieselben geordneten Datensätze.

#### 11.l.R – Make it Right

- [ ] **11.l.R** · Position **467/885** · Voraussetzung: `11.l.W`.
**Exakte Commit-Message:** `11.l.R feat(documents): Stabile Viewdaten und Varianten vervollständigen`

**Vervollständigung:** Fehlende Werte und verschachtelte Relationsprojektionen nach deklarierter Policy behandeln.

**Verhaltensabnahme:** Prüfung erfolgt am Datenmodell, nicht an Reihenfolge visueller Konsoleninformationen. Die W-Nachweise bleiben zusätzlich grün.

#### 11.l.C – Make it Clean

- [ ] **11.l.C** · Position **468/885** · Voraussetzung: `11.l.R`.
**Exakte Commit-Message:** `11.l.C refactor(documents): Stabile Viewdaten und Varianten bereinigen`

**Bereinigung:** Viewprojektion auf Query-/Scope-/Konfigurationsdienste reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-m"></a>
### 11.m – Markdown- und HTML-Renderer

**Anforderungsbezug:** `SR-REQ-0101`–`SR-REQ-0106`, `SR-REQ-0311`, `SR-REQ-0354`–`SR-REQ-0355`, `SR-REQ-0357`, `SR-REQ-0472`, `SR-REQ-0540`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.m.W – Let it Work

- [ ] **11.m.W** · Position **469/885** · Voraussetzung: `11.l.C`.
**Exakte Commit-Message:** `11.m.W feat(documents): Markdown- und HTML-Renderer aufbauen`

**Umsetzung:** Sichere selbstenthaltene Dokument-/Viewausgaben samt Ankern, Metadaten, Admonition und Seitenumbrüchen implementieren.

**Verhaltensabnahme:** Keine automatisierten Tests des gerenderten Texts; fachliche Komposition stammt aus bereits getesteter Datenprojektion.

#### 11.m.R – Make it Right

- [ ] **11.m.R** · Position **470/885** · Voraussetzung: `11.m.W`.
**Exakte Commit-Message:** `11.m.R feat(documents): Markdown- und HTML-Renderer vervollständigen`

**Vervollständigung:** Formatausgaben deterministisch halten, HTML ohne aktive/externe Inhalte; vorhandene Darstellungsbeispiele höchstens manuell sichten.

**Verhaltensabnahme:** Keine Golden-File-, Snapshot-, Format- oder Doku-Tests; Testpolicy-Abweichung zu 0472 ausdrücklich erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 11.m.C – Make it Clean

- [ ] **11.m.C** · Position **471/885** · Voraussetzung: `11.m.R`.
**Exakte Commit-Message:** `11.m.C refactor(documents): Markdown- und HTML-Renderer bereinigen`

**Bereinigung:** Formatemitter klein halten; sichere Datenknoten statt frei ausführbarer Templates verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-n"></a>
### 11.n – CSV/JSON-Viewdaten und Ausgabeziele

**Anforderungsbezug:** `SR-REQ-0356`, `SR-REQ-0479`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.n.W – Let it Work

- [ ] **11.n.W** · Position **472/885** · Voraussetzung: `11.m.C`.
**Exakte Commit-Message:** `11.n.W feat(documents): CSV/JSON-Viewdaten und Ausgabeziele aufbauen`

**Umsetzung:** Maschinenlesbare Viewexporte mit verlustbewusster Serialisierung und atomarem erlaubtem Ausgabeziel implementieren.

**Verhaltensabnahme:** Exportdaten lassen sich gemäß ihrem Schema wieder einlesen.

#### 11.n.R – Make it Right

- [ ] **11.n.R** · Position **473/885** · Voraussetzung: `11.n.W`.
**Exakte Commit-Message:** `11.n.R feat(documents): CSV/JSON-Viewdaten und Ausgabeziele vervollständigen`

**Vervollständigung:** Verschachtelte Werte ohne deklarierte Serialisierung und unerlaubte Projekt-/Betriebsziele abweisen.

**Verhaltensabnahme:** Datenroundtrip und atomare Seiteneffekte prüfen, keine Pretty- oder HTMLausgabe. Die W-Nachweise bleiben zusätzlich grün.

#### 11.n.C – Make it Clean

- [ ] **11.n.C** · Position **474/885** · Voraussetzung: `11.n.R`.
**Exakte Commit-Message:** `11.n.C refactor(documents): CSV/JSON-Viewdaten und Ausgabeziele bereinigen`

**Bereinigung:** Gemeinsam nutzbare Datenserializer und Ausgabezielprüfung bereitstellen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-o"></a>
### 11.o – Diagrammquellen

**Anforderungsbezug:** `SR-REQ-0358`–`SR-REQ-0360`.
**Verifikationsbezug:** `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.o.W – Let it Work

- [ ] **11.o.W** · Position **475/885** · Voraussetzung: `11.n.C`.
**Exakte Commit-Message:** `11.o.W feat(documents): Diagrammquellen aufbauen`

**Umsetzung:** Trace-, Architektur- und Releasediagramme als Mermaid/DOT aus den geprüften Knoten-/Kantenprojektionen erzeugen.

**Verhaltensabnahme:** Fachliche Diagrammprojektion enthält die ausgewählten Graphidentitäten.

#### 11.o.R – Make it Right

- [ ] **11.o.R** · Position **476/885** · Voraussetzung: `11.o.W`.
**Exakte Commit-Message:** `11.o.R feat(documents): Diagrammquellen vervollständigen`

**Vervollständigung:** Keine externen Renderer/Browser starten; Labels sicher behandeln und explizite Graphgrenzen respektieren.

**Verhaltensabnahme:** Tests prüfen Graphumfang und fehlende Fremdausführung, nicht DOT-/Mermaidtexte oder deren Layout. Die W-Nachweise bleiben zusätzlich grün.

#### 11.o.C – Make it Clean

- [ ] **11.o.C** · Position **477/885** · Voraussetzung: `11.o.R`.
**Exakte Commit-Message:** `11.o.C refactor(documents): Diagrammquellen bereinigen`

**Bereinigung:** Graphauswahl und rein textuelle Diagrammemitter vollständig trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-p"></a>
### 11.p – Sprache, Verbindlichkeit und Schreibrichtung

**Anforderungsbezug:** `SR-REQ-0654`–`SR-REQ-0655`, `SR-REQ-0672`.
**Verifikationsbezug:** `SR-VER-0044`, `SR-VER-0045`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.p.W – Let it Work

- [ ] **11.p.W** · Position **478/885** · Voraussetzung: `11.o.C`.
**Exakte Commit-Message:** `11.p.W feat(documents): Sprache, Verbindlichkeit und Schreibrichtung aufbauen`

**Umsetzung:** Deklarierte Force getrennt vom unveränderten Statement und explizite Sprach-/Richtungsmetadaten darstellen.

**Verhaltensabnahme:** Fachliche Renderdaten erhalten Originalstatement und Force als getrennte Werte.

#### 11.p.R – Make it Right

- [ ] **11.p.R** · Position **479/885** · Voraussetzung: `11.p.W`.
**Exakte Commit-Message:** `11.p.R feat(documents): Sprache, Verbindlichkeit und Schreibrichtung vervollständigen`

**Vervollständigung:** Keine automatische Negation, Übersetzung, Region-/Schriftdetektion oder normative Textnormalisierung.

**Verhaltensabnahme:** Tests prüfen Datenverlustfreiheit vor Präsentation; konkrete Darstellung bleibt ohne Ausgabeassertions. Die W-Nachweise bleiben zusätzlich grün.

#### 11.p.C – Make it Clean

- [ ] **11.p.C** · Position **480/885** · Voraussetzung: `11.p.R`.
**Exakte Commit-Message:** `11.p.C refactor(documents): Sprache, Verbindlichkeit und Schreibrichtung bereinigen`

**Bereinigung:** Sprachlabels über Ressourcen einsetzen statt Requirementsätze umzuschreiben.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-q"></a>
### 11.q – Eingebaute Ansichten und Fallback

**Anforderungsbezug:** `SR-REQ-0107`, `SR-REQ-0531`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0023`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.q.W – Let it Work

- [ ] **11.q.W** · Position **481/885** · Voraussetzung: `11.p.C`.
**Exakte Commit-Message:** `11.q.W feat(documents): Eingebaute Ansichten und Fallback aufbauen`

**Umsetzung:** Specification-/Traceability-Grundansicht und typbasierten Partial-/Legacy-Fallback anschließen.

**Verhaltensabnahme:** Fachprojektion verweist auf dieselben IDs und gespeicherten Modellinhalte.

#### 11.q.R – Make it Right

- [ ] **11.q.R** · Position **482/885** · Voraussetzung: `11.q.W`.
**Exakte Commit-Message:** `11.q.R feat(documents): Eingebaute Ansichten und Fallback vervollständigen`

**Vervollständigung:** Verification-/Roadmap-Berechnungen erst nach M12/M13 vollständig aktivieren; fehlende Ergebnisse nicht als passed ausgeben.

**Verhaltensabnahme:** Fallback bleibt lesend und erzeugt kein erfundenes Primärdokument. Die W-Nachweise bleiben zusätzlich grün.

#### 11.q.C – Make it Clean

- [ ] **11.q.C** · Position **483/885** · Voraussetzung: `11.q.R`.
**Exakte Commit-Message:** `11.q.C refactor(documents): Eingebaute Ansichten und Fallback bereinigen`

**Bereinigung:** Eine gemeinsame Projektionsschnittstelle für die späteren berechneten Berichtsdaten anbieten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-11-r"></a>
### 11.r – Große Dokumente und fortsetzbare Projektion

**Anforderungsbezug:** `SR-REQ-0605`, `SR-REQ-0623`.
**Verifikationsbezug:** `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 11.r.W – Let it Work

- [ ] **11.r.W** · Position **484/885** · Voraussetzung: `11.q.C`.
**Exakte Commit-Message:** `11.r.W feat(documents): Große Dokumente und fortsetzbare Projektion aufbauen`

**Umsetzung:** Komposition, Queryblöcke und Ergebnislieferung an Work-Frontier/Spooling anschließen.

**Verhaltensabnahme:** Vollständige Datenprojektion entsteht auch über mehrere Prozesse.

#### 11.r.R – Make it Right

- [ ] **11.r.R** · Position **485/885** · Voraussetzung: `11.r.W`.
**Exakte Commit-Message:** `11.r.R feat(documents): Große Dokumente und fortsetzbare Projektion vervollständigen`

**Vervollständigung:** Noch offene Includes oder Tabellenzeilen dürfen nicht als fertiges Dokument gelten.

**Verhaltensabnahme:** Datenmengen-/Hash-/Seiteneffektprüfung weist vollständige Lieferung ohne Layouttests nach. Die W-Nachweise bleiben zusätzlich grün.

#### 11.r.C – Make it Clean

- [ ] **11.r.C** · Position **486/885** · Voraussetzung: `11.r.R`.
**Exakte Commit-Message:** `11.r.C refactor(documents): Große Dokumente und fortsetzbare Projektion bereinigen`

**Bereinigung:** Dokumentfortsetzung auf dieselbe generische Workengine setzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 11 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m12"></a>
## Meilenstein 12 – Verifikation, Evidence und Quellcode-Traceability

**Ziel:** Nachweise sind unveränderbar; aktuelle Ergebnisse entstehen aus gebundener Auswahl statt aus dem neuesten Erfolg.

**Vorgesehener Zuschnitt:** `src/specroad/verification/, src/specroad/evidence/, src/specroad/code_refs/`. **Fachgrundlage:** §§ 10.5, 10.13, 12.10, 12.25, 12.33; Anhänge D, H, L.

**Abschlussgate:** Fehlschläge, fehlende Läufe, stale Evidence und unbekannter Produktstand können nicht still in passed übergehen; kein Testcode wird von SpecRoad gestartet. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-12-a"></a>
### 12.a – Verification Contracts und Testreferenzen

**Anforderungsbezug:** `SR-REQ-0129`–`SR-REQ-0131`.
**Verifikationsbezug:** `SR-VER-0010`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.a.W – Let it Work

- [ ] **12.a.W** · Position **487/885** · Voraussetzung: `11.r.C`.
**Exakte Commit-Message:** `12.a.W feat(verification): Verification Contracts und Testreferenzen aufbauen`

**Umsetzung:** Methoden, Verfahren, Oracle, Testidentität und vollständige evidence_slots implementieren.

**Verhaltensabnahme:** Gültiger Contract hat eine eindeutige Pflichtmenge; overall-Default nur ohne ausdrücklich weitere Slots.

#### 12.a.R – Make it Right

- [ ] **12.a.R** · Position **488/885** · Voraussetzung: `12.a.W`.
**Exakte Commit-Message:** `12.a.R feat(verification): Verification Contracts und Testreferenzen vervollständigen`

**Vervollständigung:** Fehlende Pflichtdimensionen, ungültige Test-ID und unvollständige Contracts abweisen.

**Verhaltensabnahme:** Direkter verified_by-Test ergibt den normativen impliziten overall-Contract. Die W-Nachweise bleiben zusätzlich grün.

#### 12.a.C – Make it Clean

- [ ] **12.a.C** · Position **489/885** · Voraussetzung: `12.a.R`.
**Exakte Commit-Message:** `12.a.C refactor(verification): Verification Contracts und Testreferenzen bereinigen`

**Bereinigung:** Contractauflösung und Testmetadaten als reine Datenfunktionen führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-b"></a>
### 12.b – Verifikationsplanung und Waiver

**Anforderungsbezug:** `SR-REQ-0138`, `SR-REQ-0444`–`SR-REQ-0445`, `SR-REQ-0447`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.b.W – Let it Work

- [ ] **12.b.W** · Position **490/885** · Voraussetzung: `12.a.C`.
**Exakte Commit-Message:** `12.b.W feat(verification): Verifikationsplanung und Waiver aufbauen`

**Umsetzung:** Ausschließlich verification_plan_status speichern und gebundene menschliche Waiver validieren.

**Verhaltensabnahme:** Gültiger zeit-/scopegebundener Waiver wird als waiver, nicht als passed bewertet.

#### 12.b.R – Make it Right

- [ ] **12.b.R** · Position **491/885** · Voraussetzung: `12.b.W`.
**Exakte Commit-Message:** `12.b.R feat(verification): Verifikationsplanung und Waiver vervollständigen`

**Vervollständigung:** Abgelaufene/fremde Bindung und Speicherung von verification_result verhindern.

**Verhaltensabnahme:** Datenmutation kann kein berechnetes Ergebnis als normative Wahrheit festschreiben. Die W-Nachweise bleiben zusätzlich grün.

#### 12.b.C – Make it Clean

- [ ] **12.b.C** · Position **492/885** · Voraussetzung: `12.b.R`.
**Exakte Commit-Message:** `12.b.C refactor(verification): Verifikationsplanung und Waiver bereinigen`

**Bereinigung:** Workflowwerte und Ergebnisberechnung strikt trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-c"></a>
### 12.c – Verification-Kontextprojektion

**Anforderungsbezug:** `SR-REQ-0137`, `SR-REQ-0451`–`SR-REQ-0452`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.c.W – Let it Work

- [ ] **12.c.W** · Position **493/885** · Voraussetzung: `12.b.C`.
**Exakte Commit-Message:** `12.c.W feat(verification): Verification-Kontextprojektion aufbauen`

**Umsetzung:** verification_context_hash-v1 aus fachlich relevanten Subject-/Konfigurationsdaten bilden.

**Verhaltensabnahme:** Fachänderung macht Evidence stale, reine Audit-/Workflowänderung nicht.

#### 12.c.R – Make it Right

- [ ] **12.c.R** · Position **494/885** · Voraussetzung: `12.c.W`.
**Exakte Commit-Message:** `12.c.R feat(verification): Verification-Kontextprojektion vervollständigen`

**Vervollständigung:** Contract-unabhängige Konfiguration nur bei explizitem independent zulassen.

**Verhaltensabnahme:** Kontextvektoren prüfen exakte enthaltene/ausgeschlossene Werte. Die W-Nachweise bleiben zusätzlich grün.

#### 12.c.C – Make it Clean

- [ ] **12.c.C** · Position **495/885** · Voraussetzung: `12.c.R`.
**Exakte Commit-Message:** `12.c.C refactor(verification): Verification-Kontextprojektion bereinigen`

**Bereinigung:** Eine gemeinsame Projektion für Record, Import, Coverage und Baselines verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-d"></a>
### 12.d – Immutable Evidence und Laufkontext

**Anforderungsbezug:** `SR-REQ-0132`–`SR-REQ-0133`, `SR-REQ-0142`, `SR-REQ-0432`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0025`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.d.W – Let it Work

- [ ] **12.d.W** · Position **496/885** · Voraussetzung: `12.c.C`.
**Exakte Commit-Message:** `12.d.W feat(verification): Immutable Evidence und Laufkontext aufbauen`

**Umsetzung:** Nachweise mit vollständiger Origin-, Producer-, Subject- und run_context-Bindung konstruieren.

**Verhaltensabnahme:** Neue Messung erhält neue ID und entsteht atomar recorded/approved.

#### 12.d.R – Make it Right

- [ ] **12.d.R** · Position **497/885** · Voraussetzung: `12.d.W`.
**Exakte Commit-Message:** `12.d.R feat(verification): Immutable Evidence und Laufkontext vervollständigen`

**Vervollständigung:** Unbekannter Produktstand bleibt unbound; KI-Herkunft erzeugt keine menschliche Freigabe.

**Verhaltensabnahme:** Updateversuch an recorded Evidence wird abgewiesen; Originalbytes bleiben gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 12.d.C – Make it Clean

- [ ] **12.d.C** · Position **498/885** · Voraussetzung: `12.d.R`.
**Exakte Commit-Message:** `12.d.C refactor(verification): Immutable Evidence und Laufkontext bereinigen`

**Bereinigung:** Evidencekonstruktor und Aktualitätsberechnung entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-e"></a>
### 12.e – Manuelle und werkzeuggestützte Erfassung

**Anforderungsbezug:** `SR-REQ-0333`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.e.W – Let it Work

- [ ] **12.e.W** · Position **499/885** · Voraussetzung: `12.d.C`.
**Exakte Commit-Message:** `12.e.W feat(verification): Manuelle und werkzeuggestützte Erfassung aufbauen`

**Umsetzung:** evidence record mit explizitem run-context, Attachments und gemeinsamen Writegates implementieren.

**Verhaltensabnahme:** Autorisierter Nachweis wird einmalig mit tatsächlichen Eingangsbindungen gespeichert.

#### 12.e.R – Make it Right

- [ ] **12.e.R** · Position **500/885** · Voraussetzung: `12.e.W`.
**Exakte Commit-Message:** `12.e.R feat(verification): Manuelle und werkzeuggestützte Erfassung vervollständigen`

**Vervollständigung:** Fehlende Werte nicht aus Git-HEAD oder aktueller Modellwurzel erraten.

**Verhaltensabnahme:** Record verändert weder Subject-Revision noch dessen Verifikationsplanung. Die W-Nachweise bleiben zusätzlich grün.

#### 12.e.C – Make it Clean

- [ ] **12.e.C** · Position **501/885** · Voraussetzung: `12.e.R`.
**Exakte Commit-Message:** `12.e.C refactor(verification): Manuelle und werkzeuggestützte Erfassung bereinigen`

**Bereinigung:** Erfassungsadapter nutzt vorhandenen Writer statt eigener Dateizugriffe.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-f"></a>
### 12.f – Sicherer XML-Kern für Evidence

**Anforderungsbezug:** `SR-REQ-0324`, `SR-REQ-0334`.
**Verifikationsbezug:** `SR-VER-0024`, `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.f.W – Let it Work

- [ ] **12.f.W** · Position **502/885** · Voraussetzung: `12.e.C`.
**Exakte Commit-Message:** `12.f.W feat(verification): Sicherer XML-Kern für Evidence aufbauen`

**Umsetzung:** DTD-/Entity-freien begrenzten XML-Parser für das JUnit-Kernprofil implementieren.

**Verhaltensabnahme:** Unterstützte Suite-/Testcase-Daten werden ohne Testausführung gelesen.

#### 12.f.R – Make it Right

- [ ] **12.f.R** · Position **503/885** · Voraussetzung: `12.f.W`.
**Exakte Commit-Message:** `12.f.R feat(verification): Sicherer XML-Kern für Evidence vervollständigen`

**Vervollständigung:** DTD, externe Schemas/Entitäten, Tiefe und Expansionsangriffe vor gefährlicher Verarbeitung abweisen.

**Verhaltensabnahme:** Angriffsfixtures erzeugen weder Netzwerk- noch Fremdprozesszugriff. Die W-Nachweise bleiben zusätzlich grün.

#### 12.f.C – Make it Clean

- [ ] **12.f.C** · Position **504/885** · Voraussetzung: `12.f.R`.
**Exakte Commit-Message:** `12.f.C refactor(verification): Sicherer XML-Kern für Evidence bereinigen`

**Bereinigung:** Sicheren XML-Reader später für ReqIF in M14 wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-g"></a>
### 12.g – JUnit-Mapping und Ergebnisklassen

**Anforderungsbezug:** `SR-REQ-0334`–`SR-REQ-0335`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.g.W – Let it Work

- [ ] **12.g.W** · Position **505/885** · Voraussetzung: `12.f.C`.
**Exakte Commit-Message:** `12.g.W feat(verification): JUnit-Mapping und Ergebnisklassen aufbauen`

**Umsetzung:** Testcase-Schlüssel und failure/error/skipped/results nach explizitem Mapping auflösen.

**Verhaltensabnahme:** Gültige Testidentität liefert den vorgesehenen Evidence-Kandidaten.

#### 12.g.R – Make it Right

- [ ] **12.g.R** · Position **506/885** · Voraussetzung: `12.g.W`.
**Exakte Commit-Message:** `12.g.R feat(verification): JUnit-Mapping und Ergebnisklassen vervollständigen`

**Vervollständigung:** Nicht gemappte, mehrdeutige und widersprüchliche Ergebnisse getrennt behandeln.

**Verhaltensabnahme:** Identische Testnamen mit unterschiedlichem Class-/Filekontext werden nicht versehentlich verschmolzen. Die W-Nachweise bleiben zusätzlich grün.

#### 12.g.C – Make it Clean

- [ ] **12.g.C** · Position **507/885** · Voraussetzung: `12.g.R`.
**Exakte Commit-Message:** `12.g.C refactor(verification): JUnit-Mapping und Ergebnisklassen bereinigen`

**Bereinigung:** Parserwerte und fachliche Evidencezuordnung separieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-h"></a>
### 12.h – SARIF- und generischer Evidenceimport

**Anforderungsbezug:** `SR-REQ-0336`–`SR-REQ-0337`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.h.W – Let it Work

- [ ] **12.h.W** · Position **508/885** · Voraussetzung: `12.g.C`.
**Exakte Commit-Message:** `12.h.W feat(verification): SARIF- und generischer Evidenceimport aufbauen`

**Umsetzung:** Nur ausdrücklich gemappte SARIF-Daten sowie das versionierte generische Exchange-Schema lesen.

**Verhaltensabnahme:** Unterstützte Eingaben liefern gebundene Producer-, Run-, Subject- und Ergebnisdaten.

#### 12.h.R – Make it Right

- [ ] **12.h.R** · Position **509/885** · Voraussetzung: `12.h.W`.
**Exakte Commit-Message:** `12.h.R feat(verification): SARIF- und generischer Evidenceimport vervollständigen`

**Vervollständigung:** Fremde SARIF-Einträge nicht automatisch zu bestandener Evidence erklären.

**Verhaltensabnahme:** Schema-/Mappingfehler verändern keine fachlichen Ressourcen. Die W-Nachweise bleiben zusätzlich grün.

#### 12.h.C – Make it Clean

- [ ] **12.h.C** · Position **510/885** · Voraussetzung: `12.h.R`.
**Exakte Commit-Message:** `12.h.C refactor(verification): SARIF- und generischer Evidenceimport bereinigen`

**Bereinigung:** Gemeinsame Kandidatenstruktur für alle Importformate verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-i"></a>
### 12.i – Originalbindung und Importpolicy

**Anforderungsbezug:** `SR-REQ-0338`–`SR-REQ-0339`, `SR-REQ-0535`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.i.W – Let it Work

- [ ] **12.i.W** · Position **511/885** · Voraussetzung: `12.h.C`.
**Exakte Commit-Message:** `12.i.W feat(verification): Originalbindung und Importpolicy aufbauen`

**Umsetzung:** Originalbytes, Hash, Mapping und Parserprofil erhalten; abort_import versus skip_invalid_with_diagnostic explizit umsetzen.

**Verhaltensabnahme:** Gültige Kandidaten tragen einen nachvollziehbaren Originalnachweis.

#### 12.i.R – Make it Right

- [ ] **12.i.R** · Position **512/885** · Voraussetzung: `12.i.W`.
**Exakte Commit-Message:** `12.i.R feat(verification): Originalbindung und Importpolicy vervollständigen`

**Vervollständigung:** Ungültige Pflichtnachweise nur gemäß gewählter Policy behandeln; kein stilles Überspringen.

**Verhaltensabnahme:** Importmenge und Diagnosen erklären jeden ausgelassenen Kandidaten. Die W-Nachweise bleiben zusätzlich grün.

#### 12.i.C – Make it Clean

- [ ] **12.i.C** · Position **513/885** · Voraussetzung: `12.i.R`.
**Exakte Commit-Message:** `12.i.C refactor(verification): Originalbindung und Importpolicy bereinigen`

**Bereinigung:** Policyentscheidung und allgemeine Parserdiagnosen getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-j"></a>
### 12.j – Evidence-Idempotenz und Transaktion

**Anforderungsbezug:** `SR-REQ-0340`–`SR-REQ-0341`, `SR-REQ-0448`, `SR-REQ-0533`–`SR-REQ-0534`.
**Verifikationsbezug:** `SR-VER-0025`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.j.W – Let it Work

- [ ] **12.j.W** · Position **514/885** · Voraussetzung: `12.i.C`.
**Exakte Commit-Message:** `12.j.W feat(verification): Evidence-Idempotenz und Transaktion aufbauen`

**Umsetzung:** Gesamten Evidence-Satz in einem Change Plan publizieren und Retry an Quelle, Mapping, Laufkontext und Request binden.

**Verhaltensabnahme:** Gleicher Request importiert denselben Satz ohne neue IDs.

#### 12.j.R – Make it Right

- [ ] **12.j.R** · Position **515/885** · Voraussetzung: `12.j.W`.
**Exakte Commit-Message:** `12.j.R feat(verification): Evidence-Idempotenz und Transaktion vervollständigen`

**Vervollständigung:** Geänderter Kontext unter gleicher Request ist Konflikt; Duplikat ohne Request erkennbar, Subject unverändert.

**Verhaltensabnahme:** Wiederholung, Teilfehler und Crash erzeugen keine doppelte oder halbe Evidenzmenge. Die W-Nachweise bleiben zusätzlich grün.

#### 12.j.C – Make it Clean

- [ ] **12.j.C** · Position **516/885** · Voraussetzung: `12.j.R`.
**Exakte Commit-Message:** `12.j.C refactor(verification): Evidence-Idempotenz und Transaktion bereinigen`

**Bereinigung:** Alle Evidenceimporte über einen gemeinsamen Satzplanner führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-k"></a>
### 12.k – Bewertungsdescriptor und Produktstand

**Anforderungsbezug:** `SR-REQ-0136`, `SR-REQ-0446`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.k.W – Let it Work

- [ ] **12.k.W** · Position **517/885** · Voraussetzung: `12.j.C`.
**Exakte Commit-Message:** `12.k.W feat(verification): Bewertungsdescriptor und Produktstand aufbauen`

**Umsetzung:** verification-evaluation-v1 mit eigenem Eingangsmanifest und state_sha256 implementieren.

**Verhaltensabnahme:** Bewerteter Produktstand ist an tatsächliche Prüfeingangsbytes gebunden.

#### 12.k.R – Make it Right

- [ ] **12.k.R** · Position **518/885** · Voraussetzung: `12.k.W`.
**Exakte Commit-Message:** `12.k.R feat(verification): Bewertungsdescriptor und Produktstand vervollständigen`

**Vervollständigung:** Evidence, Ergebnisdateien und eigener Descriptor dürfen keine selbstreferenzielle Inputbindung bilden.

**Verhaltensabnahme:** Unbekannter Stand und fehlender Descriptor ergeben incomplete statt geratenem aktuellen Build. Die W-Nachweise bleiben zusätzlich grün.

#### 12.k.C – Make it Clean

- [ ] **12.k.C** · Position **519/885** · Voraussetzung: `12.k.R`.
**Exakte Commit-Message:** `12.k.C refactor(verification): Bewertungsdescriptor und Produktstand bereinigen`

**Bereinigung:** Bewertungsinput von SpecRoad-Projektmodell und Laufzeitmetrik unterscheiden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-l"></a>
### 12.l – Unabhängig gebildete Pflichtmenge

**Anforderungsbezug:** `SR-REQ-0130`, `SR-REQ-0446`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.l.W – Let it Work

- [ ] **12.l.W** · Position **520/885** · Voraussetzung: `12.k.C`.
**Exakte Commit-Message:** `12.l.W feat(verification): Unabhängig gebildete Pflichtmenge aufbauen`

**Umsetzung:** Pflichtschlüssel aus anwendbaren Subjects, verified_by und evidence_slots berechnen.

**Verhaltensabnahme:** Descriptor deckt diese Menge vollständig und ohne fremde Schlüssel ab.

#### 12.l.R – Make it Right

- [ ] **12.l.R** · Position **521/885** · Voraussetzung: `12.l.W`.
**Exakte Commit-Message:** `12.l.R feat(verification): Unabhängig gebildete Pflichtmenge vervollständigen`

**Vervollständigung:** Descriptor darf Scope nicht selbst erweitern/verkleinern; fehlende und zusätzliche Schlüssel unterscheiden.

**Verhaltensabnahme:** Manipulierte Auswahl kann keine notwendige Prüfung wegfiltern. Die W-Nachweise bleiben zusätzlich grün.

#### 12.l.C – Make it Clean

- [ ] **12.l.C** · Position **522/885** · Voraussetzung: `12.l.R`.
**Exakte Commit-Message:** `12.l.C refactor(verification): Unabhängig gebildete Pflichtmenge bereinigen`

**Bereinigung:** Pflichtmengenbildung vor Nachweisauswahl durchführen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-m"></a>
### 12.m – Vollständige Lauf- und Nachweisauswahl

**Anforderungsbezug:** `SR-REQ-0136`, `SR-REQ-0446`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.m.W – Let it Work

- [ ] **12.m.W** · Position **523/885** · Voraussetzung: `12.l.C`.
**Exakte Commit-Message:** `12.m.W feat(verification): Vollständige Lauf- und Nachweisauswahl aufbauen`

**Umsetzung:** Alle passenden beobachteten und erwarteten Läufe desselben Produktstands auswerten.

**Verhaltensabnahme:** Zusätzlicher gleichzeitiger Fehlschlag bleibt sichtbar, auch nach einem später importierten Erfolg.

#### 12.m.R – Make it Right

- [ ] **12.m.R** · Position **524/885** · Voraussetzung: `12.m.W`.
**Exakte Commit-Message:** `12.m.R feat(verification): Vollständige Lauf- und Nachweisauswahl vervollständigen`

**Vervollständigung:** historical_other_state, unbound, missing und stale getrennt führen.

**Verhaltensabnahme:** Importreihenfolge und Evidence-ID-Sortierung verändern keine Bewertung. Die W-Nachweise bleiben zusätzlich grün.

#### 12.m.C – Make it Clean

- [ ] **12.m.C** · Position **525/885** · Voraussetzung: `12.m.R`.
**Exakte Commit-Message:** `12.m.C refactor(verification): Vollständige Lauf- und Nachweisauswahl bereinigen`

**Bereinigung:** Auswahlregeln als reine Funktion über eingefrorene Eingangsdaten implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-n"></a>
### 12.n – Menschlich gebundene Laufablösung

**Anforderungsbezug:** `SR-REQ-0446`.
**Verifikationsbezug:** `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.n.W – Let it Work

- [ ] **12.n.W** · Position **526/885** · Voraussetzung: `12.m.C`.
**Exakte Commit-Message:** `12.n.W feat(verification): Menschlich gebundene Laufablösung aufbauen`

**Umsetzung:** Vollständige Replacement-Entscheidung mit Evidence-Set-Hash und azyklischen Ersatzläufen umsetzen.

**Verhaltensabnahme:** Gültiger Retest desselben Stands löst exakt den bezeichneten alten Lauf ab.

#### 12.n.R – Make it Right

- [ ] **12.n.R** · Position **527/885** · Voraussetzung: `12.n.W`.
**Exakte Commit-Message:** `12.n.R feat(verification): Menschlich gebundene Laufablösung vervollständigen`

**Vervollständigung:** AI-Entscheidung, neue alte Evidence, Zyklus und fehlender/staler Ersatz machen Ablösung ungültig.

**Verhaltensabnahme:** Ein fehlgeschlagener gültiger Ersatz bleibt failed; alte Evidencebytes werden nie geändert. Die W-Nachweise bleiben zusätzlich grün.

#### 12.n.C – Make it Clean

- [ ] **12.n.C** · Position **528/885** · Voraussetzung: `12.n.R`.
**Exakte Commit-Message:** `12.n.C refactor(verification): Menschlich gebundene Laufablösung bereinigen`

**Bereinigung:** Ablösungsgraph von Ergebnisaggregation getrennt berechnen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-o"></a>
### 12.o – Priorisierte Ergebnisaggregation

**Anforderungsbezug:** `SR-REQ-0136`, `SR-REQ-0446`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.o.W – Let it Work

- [ ] **12.o.W** · Position **529/885** · Voraussetzung: `12.n.C`.
**Exakte Commit-Message:** `12.o.W feat(verification): Priorisierte Ergebnisaggregation aufbauen`

**Umsetzung:** not_applicable/waived/not_evaluated/incomplete/failed/running/stale/passed nach §10.5 ordnen.

**Verhaltensabnahme:** Maßgeblicher aktueller Fehlschlag hat Vorrang vor running oder fehlenden anderen Nachweisen.

#### 12.o.R – Make it Right

- [ ] **12.o.R** · Position **530/885** · Voraussetzung: `12.o.W`.
**Exakte Commit-Message:** `12.o.R feat(verification): Priorisierte Ergebnisaggregation vervollständigen`

**Vervollständigung:** Kein unbekannter oder unvollständiger Pflichtlauf darf zum positiven Default werden.

**Verhaltensabnahme:** Vollständige Entscheidungstabelle und gemischte Nachweissätze ergeben exakt definierte Zustände. Die W-Nachweise bleiben zusätzlich grün.

#### 12.o.C – Make it Clean

- [ ] **12.o.C** · Position **531/885** · Voraussetzung: `12.o.R`.
**Exakte Commit-Message:** `12.o.C refactor(verification): Priorisierte Ergebnisaggregation bereinigen`

**Bereinigung:** Aggregation ohne Format-/CLIabhängigkeit halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-p"></a>
### 12.p – Coverage und Evaluation-Eingaben

**Anforderungsbezug:** `SR-REQ-0139`–`SR-REQ-0141`, `SR-REQ-0449`.
**Verifikationsbezug:** `SR-VER-0010`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.p.W – Let it Work

- [ ] **12.p.W** · Position **532/885** · Voraussetzung: `12.o.C`.
**Exakte Commit-Message:** `12.p.W feat(verification): Coverage und Evaluation-Eingaben aufbauen`

**Umsetzung:** Coverageachsen und expliziten evaluationsgebundenen Query-/Viewinput bereitstellen.

**Verhaltensabnahme:** Gleiche Auswahl liefert gleiche fachliche Coverage je Requirement, Kind und Dimension.

#### 12.p.R – Make it Right

- [ ] **12.p.R** · Position **533/885** · Voraussetzung: `12.p.W`.
**Exakte Commit-Message:** `12.p.R feat(verification): Coverage und Evaluation-Eingaben vervollständigen`

**Vervollständigung:** Fehlende Auswahl, fehlende Tests, fehlende Evidence und stale Evidence getrennt ausweisen.

**Verhaltensabnahme:** Tests prüfen Zähler/Mengen/Status und vollständig erhaltene Workbindung, keine Berichtstexte. Die W-Nachweise bleiben zusätzlich grün.

#### 12.p.C – Make it Clean

- [ ] **12.p.C** · Position **534/885** · Voraussetzung: `12.p.R`.
**Exakte Commit-Message:** `12.p.C refactor(verification): Coverage und Evaluation-Eingaben bereinigen`

**Bereinigung:** Evaluationsauflösung für Coverage, Query und spätere Readiness gemeinsam führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-q"></a>
### 12.q – Code-Referenzarten und sichere Quellen

**Anforderungsbezug:** `SR-REQ-0342`–`SR-REQ-0344`, `SR-REQ-0347`–`SR-REQ-0348`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.q.W – Let it Work

- [ ] **12.q.W** · Position **535/885** · Voraussetzung: `12.p.C`.
**Exakte Commit-Message:** `12.q.W feat(verification): Code-Referenzarten und sichere Quellen aufbauen`

**Umsetzung:** File, line_range, text_anchor, symbol_hint und generated_artifact als sprachneutrale Referenzen implementieren.

**Verhaltensabnahme:** Datei-/Gitbytes werden ohne Checkout oder Quellcodeausführung gebunden.

#### 12.q.R – Make it Right

- [ ] **12.q.R** · Position **536/885** · Voraussetzung: `12.q.W`.
**Exakte Commit-Message:** `12.q.R feat(verification): Code-Referenzarten und sichere Quellen vervollständigen`

**Vervollständigung:** Externe Pfade und fremde Symlinks verhindern Zugriff; symbol_hint beweist allein keine Aktualität.

**Verhaltensabnahme:** Sicherheitsfixtures starten keine Compiler, Parser oder Language Server. Die W-Nachweise bleiben zusätzlich grün.

#### 12.q.C – Make it Clean

- [ ] **12.q.C** · Position **537/885** · Voraussetzung: `12.q.R`.
**Exakte Commit-Message:** `12.q.C refactor(verification): Code-Referenzarten und sichere Quellen bereinigen`

**Bereinigung:** Quellenleser aus M8 und sicheren I/O aus M2 wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-r"></a>
### 12.r – Zeilenauswahl und exakte Relokation

**Anforderungsbezug:** `SR-REQ-0346`, `SR-REQ-0536`.
**Verifikationsbezug:** `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.r.W – Let it Work

- [ ] **12.r.W** · Position **538/885** · Voraussetzung: `12.q.C`.
**Exakte Commit-Message:** `12.r.W feat(verification): Zeilenauswahl und exakte Relokation aufbauen`

**Umsetzung:** Encoding, inklusive Zeilenbereiche und normalisierten Auswahlhash nach H.2 umsetzen.

**Verhaltensabnahme:** Änderung außerhalb unveränderter Auswahl erhält deren Aktualität.

#### 12.r.R – Make it Right

- [ ] **12.r.R** · Position **539/885** · Voraussetzung: `12.r.W`.
**Exakte Commit-Message:** `12.r.R feat(verification): Zeilenauswahl und exakte Relokation vervollständigen`

**Vervollständigung:** Mehrfachtreffer, fehlende Auswahl und ungültiges Encoding getrennt behandeln.

**Verhaltensabnahme:** Genau ein Treffer außerhalb der alten Position ergibt relocated, nicht automatische Datenänderung. Die W-Nachweise bleiben zusätzlich grün.

#### 12.r.C – Make it Clean

- [ ] **12.r.C** · Position **540/885** · Voraussetzung: `12.r.R`.
**Exakte Commit-Message:** `12.r.C refactor(verification): Zeilenauswahl und exakte Relokation bereinigen`

**Bereinigung:** Auswahlhash und Suchcursor für große Quellen getrennt kapseln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-s"></a>
### 12.s – Disjunkter Codezustand

**Anforderungsbezug:** `SR-REQ-0345`, `SR-REQ-0495`.
**Verifikationsbezug:** `SR-VER-0025`, `SR-VER-0034`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.s.W – Let it Work

- [ ] **12.s.W** · Position **541/885** · Voraussetzung: `12.r.C`.
**Exakte Commit-Message:** `12.s.W feat(verification): Disjunkter Codezustand aufbauen`

**Umsetzung:** Erste zutreffende Regel aus H.3 für missing/current/relocated/stale anwenden.

**Verhaltensabnahme:** Treffer an gespeicherter Position bleibt current auch bei anderem Dateiinhalt außerhalb der Auswahl.

#### 12.s.R – Make it Right

- [ ] **12.s.R** · Position **542/885** · Voraussetzung: `12.s.W`.
**Exakte Commit-Message:** `12.s.R feat(verification): Disjunkter Codezustand vervollständigen`

**Vervollständigung:** Kein Treffer und mehrdeutiger Treffer sind unterschiedliche stale-Gründe.

**Verhaltensabnahme:** Vollständige H.3-Matrix liefert genau einen Zustand pro Fall. Die W-Nachweise bleiben zusätzlich grün.

#### 12.s.C – Make it Clean

- [ ] **12.s.C** · Position **543/885** · Voraussetzung: `12.s.R`.
**Exakte Commit-Message:** `12.s.C refactor(verification): Disjunkter Codezustand bereinigen`

**Bereinigung:** Statusentscheidung unabhängig von Suchalgorithmus und Präsentation halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-12-t"></a>
### 12.t – Nachweis-/Codeintegration und Workparität

**Anforderungsbezug:** `SR-REQ-0284`, `SR-REQ-0537`.
**Verifikationsbezug:** `SR-VER-0021`, `SR-VER-0025`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 12.t.W – Let it Work

- [ ] **12.t.W** · Position **544/885** · Voraussetzung: `12.s.C`.
**Exakte Commit-Message:** `12.t.W feat(verification): Nachweis-/Codeintegration und Workparität aufbauen`

**Umsetzung:** Evidence- und Codezustände in Validation, Diff, Traceability und Verification-Ansichten registrieren.

**Verhaltensabnahme:** Alle vorhandenen Fachfunktionen verwenden dieselbe berechnete Aktualität.

#### 12.t.R – Make it Right

- [ ] **12.t.R** · Position **545/885** · Voraussetzung: `12.t.W`.
**Exakte Commit-Message:** `12.t.R feat(verification): Nachweis-/Codeintegration und Workparität vervollständigen`

**Vervollständigung:** Noch fehlende Readiness bleibt M13 vorbehalten; geteilte Arbeit erhält vollständige Evaluation und Nachweismenge.

**Verhaltensabnahme:** Einzellauf und Fortsetzung liefern dieselben Coverage-/Code-/Verifikationsdaten ohne Subjectwrites. Die W-Nachweise bleiben zusätzlich grün.

#### 12.t.C – Make it Clean

- [ ] **12.t.C** · Position **546/885** · Voraussetzung: `12.t.R`.
**Exakte Commit-Message:** `12.t.C refactor(verification): Nachweis-/Codeintegration und Workparität bereinigen`

**Bereinigung:** Gemeinsame berechnete Datenprovider statt voneinander abweichender Reportlogik verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 12 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m13"></a>
## Meilenstein 13 – Releases, Meilensteine, Aufgaben und Roadmap

**Ziel:** Planung und Releaseentscheidungen werden aus Fachgraph und belastbar ausgewählter Verifikation abgeleitet.

**Vorgesehener Zuschnitt:** `src/specroad/planning/, src/specroad/readiness/, src/specroad/views/`. **Fachgrundlage:** §§ 10.5.4, 12.9–12.11, 12.33.

**Abschlussgate:** Readiness kann weder durch Warnungsschwellen noch CLI-Override oder fehlende Evidence künstlich bestehen. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-13-a"></a>
### 13.a – Release-, Milestone- und Taskbeziehungen

**Anforderungsbezug:** `SR-REQ-0119`–`SR-REQ-0121`.
**Verifikationsbezug:** `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.a.W – Let it Work

- [ ] **13.a.W** · Position **547/885** · Voraussetzung: `12.t.C`.
**Exakte Commit-Message:** `13.a.W feat(roadmap): Release-, Milestone- und Taskbeziehungen aufbauen`

**Umsetzung:** part_of und scheduled_for mit Pflichtowner, Done-Kriterien und genau einem Release je Milestone integrieren.

**Verhaltensabnahme:** Gültige Planung verknüpft bestehende Fachidentitäten ohne Kopien.

#### 13.a.R – Make it Right

- [ ] **13.a.R** · Position **548/885** · Voraussetzung: `13.a.W`.
**Exakte Commit-Message:** `13.a.R feat(roadmap): Release-, Milestone- und Taskbeziehungen vervollständigen`

**Vervollständigung:** Mehrfachrelease, fehlende Zuordnung und unzulässige Relationstypen blockieren.

**Verhaltensabnahme:** Graph-/Schemafälle prüfen exakt die erlaubten Planungsbeziehungen. Die W-Nachweise bleiben zusätzlich grün.

#### 13.a.C – Make it Clean

- [ ] **13.a.C** · Position **549/885** · Voraussetzung: `13.a.R`.
**Exakte Commit-Message:** `13.a.C refactor(roadmap): Release-, Milestone- und Taskbeziehungen bereinigen`

**Bereinigung:** Planung auf generischem Authoring und Relationsmatrix aufbauen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-b"></a>
### 13.b – Task-Umsetzung und Done-Nachweis

**Anforderungsbezug:** `SR-REQ-0127`.
**Verifikationsbezug:** `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.b.W – Let it Work

- [ ] **13.b.W** · Position **550/885** · Voraussetzung: `13.a.C`.
**Exakte Commit-Message:** `13.b.W feat(roadmap): Task-Umsetzung und Done-Nachweis aufbauen`

**Umsetzung:** Übergang zu implemented an erfüllte und durch Review/Evidence belegte Done-Kriterien binden.

**Verhaltensabnahme:** Tatsächlicher passender Nachweis erlaubt den Statuswechsel.

#### 13.b.R – Make it Right

- [ ] **13.b.R** · Position **551/885** · Voraussetzung: `13.b.W`.
**Exakte Commit-Message:** `13.b.R feat(roadmap): Task-Umsetzung und Done-Nachweis vervollständigen`

**Vervollständigung:** Bloßes Setzen eines Status oder KI-Behauptung ohne Nachweis zurückweisen.

**Verhaltensabnahme:** Fehlender, stale oder falscher Scope verhindert implemented. Die W-Nachweise bleiben zusätzlich grün.

#### 13.b.C – Make it Clean

- [ ] **13.b.C** · Position **552/885** · Voraussetzung: `13.b.R`.
**Exakte Commit-Message:** `13.b.C refactor(roadmap): Task-Umsetzung und Done-Nachweis bereinigen`

**Bereinigung:** Done-Gate und allgemeine Statusmutation getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-c"></a>
### 13.c – Roadmap aus dem einen Fachmodell

**Anforderungsbezug:** `SR-REQ-0122`–`SR-REQ-0123`, `SR-REQ-0128`.
**Verifikationsbezug:** `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.c.W – Let it Work

- [ ] **13.c.W** · Position **553/885** · Voraussetzung: `13.b.C`.
**Exakte Commit-Message:** `13.c.W feat(roadmap): Roadmap aus dem einen Fachmodell aufbauen`

**Umsetzung:** Roadmapdaten ausschließlich aus Artefakten, Beziehungen, Priorität, Risiken und Terminen berechnen.

**Verhaltensabnahme:** Keine zweite normative Roadmapdatei ist erforderlich.

#### 13.c.R – Make it Right

- [ ] **13.c.R** · Position **554/885** · Voraussetzung: `13.c.W`.
**Exakte Commit-Message:** `13.c.R feat(roadmap): Roadmap aus dem einen Fachmodell vervollständigen`

**Vervollständigung:** Automatisch berechnete Aufwände/Termine nicht als normative Fakten zurückschreiben.

**Verhaltensabnahme:** Auswertung verändert keine Projektdatei und behält gespeicherte Termine unverändert. Die W-Nachweise bleiben zusätzlich grün.

#### 13.c.C – Make it Clean

- [ ] **13.c.C** · Position **555/885** · Voraussetzung: `13.c.R`.
**Exakte Commit-Message:** `13.c.C refactor(roadmap): Roadmap aus dem einen Fachmodell bereinigen`

**Bereinigung:** Roadmapprojektion von visueller Timeline/Tabellendarstellung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-d"></a>
### 13.d – Roadmap erklären

**Anforderungsbezug:** `SR-REQ-0124`.
**Verifikationsbezug:** `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.d.W – Let it Work

- [ ] **13.d.W** · Position **556/885** · Voraussetzung: `13.c.C`.
**Exakte Commit-Message:** `13.d.W feat(roadmap): Roadmap erklären aufbauen`

**Umsetzung:** Ziele, Herkunft der Zuordnung, Abhängigkeiten, Risiken und Annahmen als Datenpfade auswerten.

**Verhaltensabnahme:** Ein geplanter Task lässt sich bis zur zugehörigen Anforderung und zum Ziel zurückverfolgen.

#### 13.d.R – Make it Right

- [ ] **13.d.R** · Position **557/885** · Voraussetzung: `13.d.W`.
**Exakte Commit-Message:** `13.d.R feat(roadmap): Roadmap erklären vervollständigen`

**Vervollständigung:** Fehlende Planungsbezüge als offen statt erfundener Herkunft behandeln.

**Verhaltensabnahme:** Erwartete Knoten-/Pfadmengen sind vollständig und read-only. Die W-Nachweise bleiben zusätzlich grün.

#### 13.d.C – Make it Clean

- [ ] **13.d.C** · Position **558/885** · Voraussetzung: `13.d.R`.
**Exakte Commit-Message:** `13.d.C refactor(roadmap): Roadmap erklären bereinigen`

**Bereinigung:** Why-/Scopeprimitive für Planungserklärungen wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-e"></a>
### 13.e – Release-Scope und externe Pflichtabhängigkeiten

**Anforderungsbezug:** `SR-REQ-0126`, `SR-REQ-0408`.
**Verifikationsbezug:** `SR-VER-0009`, `SR-VER-0029`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.e.W – Let it Work

- [ ] **13.e.W** · Position **559/885** · Voraussetzung: `13.d.C`.
**Exakte Commit-Message:** `13.e.W feat(roadmap): Release-Scope und externe Pflichtabhängigkeiten aufbauen`

**Umsetzung:** Release, Milestones und darauf geplante Artefakte als Seedmenge auflösen und Pflichtnachbarn einbeziehen.

**Verhaltensabnahme:** Externe verpflichtende Abhängigkeit wird als solche erkannt.

#### 13.e.R – Make it Right

- [ ] **13.e.R** · Position **560/885** · Voraussetzung: `13.e.W`.
**Exakte Commit-Message:** `13.e.R feat(roadmap): Release-Scope und externe Pflichtabhängigkeiten vervollständigen`

**Vervollständigung:** Scope nicht auf direkt geplante IDs verkürzen; Variantenkonflikte verhindern gültige Freigabe.

**Verhaltensabnahme:** Graphfixture weist vollständige Releaseclosure einschließlich externer Blocker nach. Die W-Nachweise bleiben zusätzlich grün.

#### 13.e.C – Make it Clean

- [ ] **13.e.C** · Position **561/885** · Voraussetzung: `13.e.R`.
**Exakte Commit-Message:** `13.e.C refactor(roadmap): Release-Scope und externe Pflichtabhängigkeiten bereinigen`

**Bereinigung:** Releaseauflösung als einen Scopeprovider statt eigene Closure führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-f"></a>
### 13.f – Readinessgates und aktuelle Beziehungen

**Anforderungsbezug:** `SR-REQ-0125`, `SR-REQ-0450`, `SR-REQ-0516`.
**Verifikationsbezug:** `SR-VER-0009`, `SR-VER-0021`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.f.W – Let it Work

- [ ] **13.f.W** · Position **562/885** · Voraussetzung: `13.e.C`.
**Exakte Commit-Message:** `13.f.W feat(roadmap): Readinessgates und aktuelle Beziehungen aufbauen`

**Umsetzung:** Freigabe, Umsetzung, Verifikation, Coverage, Risiken, Issues und nur current Pflichtrelationen prüfen.

**Verhaltensabnahme:** Vollständig belegter Release kann eine positive Readinessentscheidung liefern.

#### 13.f.R – Make it Right

- [ ] **13.f.R** · Position **563/885** · Voraussetzung: `13.f.W`.
**Exakte Commit-Message:** `13.f.R feat(roadmap): Readinessgates und aktuelle Beziehungen vervollständigen`

**Vervollständigung:** failed/incomplete/stale bleibt blockierend unabhängig von Warnungsschwellwert; KI-Review ersetzt keinen Human-Nachweis.

**Verhaltensabnahme:** Jeder einzelne Blockertyp verhindert positive Readiness und bleibt im Datenresultat erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 13.f.C – Make it Clean

- [ ] **13.f.C** · Position **564/885** · Voraussetzung: `13.f.R`.
**Exakte Commit-Message:** `13.f.C refactor(roadmap): Readinessgates und aktuelle Beziehungen bereinigen`

**Bereinigung:** Gateresultate als typisierte Teilentscheidungen aggregieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-g"></a>
### 13.g – Gespeicherte Bewertung und Release-Baseline

**Anforderungsbezug:** `SR-REQ-0150`, `SR-REQ-0450`.
**Verifikationsbezug:** `SR-VER-0011`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.g.W – Let it Work

- [ ] **13.g.W** · Position **565/885** · Voraussetzung: `13.f.C`.
**Exakte Commit-Message:** `13.g.W feat(roadmap): Gespeicherte Bewertung und Release-Baseline aufbauen`

**Umsetzung:** Gespeicherte verification_evaluation priorisieren und echte Releasebaseline mit vollständigen Auswahlbytes/Hash freischalten.

**Verhaltensabnahme:** Identisch wiederholte CLI-Auswahl ist zulässig; gespeicherte gültige Auswahl trägt die Baseline.

#### 13.g.R – Make it Right

- [ ] **13.g.R** · Position **566/885** · Voraussetzung: `13.g.W`.
**Exakte Commit-Message:** `13.g.R feat(roadmap): Gespeicherte Bewertung und Release-Baseline vervollständigen`

**Vervollständigung:** Abweichender CLI-Descriptor ist Code 6; externe ungespeicherte Auswahl nur vorläufig read-only, nie Releasebaseline.

**Verhaltensabnahme:** End-to-End erzeugt eine echte versiegelte Releasebaseline nur nach allen Gates. Die W-Nachweise bleiben zusätzlich grün.

#### 13.g.C – Make it Clean

- [ ] **13.g.C** · Position **567/885** · Voraussetzung: `13.g.R`.
**Exakte Commit-Message:** `13.g.C refactor(roadmap): Gespeicherte Bewertung und Release-Baseline bereinigen`

**Bereinigung:** M10-Gateinterface durch tatsächlichen Readinessdienst erfüllen, keine parallele Sonderfreigabe.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-13-h"></a>
### 13.h – Roadmap-/Verification-Views und Workintegration

**Anforderungsbezug:** `SR-REQ-0101`, `SR-REQ-0107`, `SR-REQ-0122`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0009`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 13.h.W – Let it Work

- [ ] **13.h.W** · Position **568/885** · Voraussetzung: `13.g.C`.
**Exakte Commit-Message:** `13.h.W feat(roadmap): Roadmap-/Verification-Views und Workintegration aufbauen`

**Umsetzung:** Berechnete Planungs- und Verifikationsprovider in die bestehenden Ansichten integrieren.

**Verhaltensabnahme:** Fachprojektionen enthalten dieselbe Auswahl und dieselben Gatewerte wie direkte Befehle.

#### 13.h.R – Make it Right

- [ ] **13.h.R** · Position **569/885** · Voraussetzung: `13.h.W`.
**Exakte Commit-Message:** `13.h.R feat(roadmap): Roadmap-/Verification-Views und Workintegration vervollständigen`

**Vervollständigung:** Darstellung nicht als Testorakel verwenden und noch offene Arbeit nicht als fertige Readiness werten.

**Verhaltensabnahme:** Datenparität über direkte Abfrage, Viewprojektion und Fortsetzung bleibt erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 13.h.C – Make it Clean

- [ ] **13.h.C** · Position **570/885** · Voraussetzung: `13.h.R`.
**Exakte Commit-Message:** `13.h.C refactor(roadmap): Roadmap-/Verification-Views und Workintegration bereinigen`

**Bereinigung:** Renderer benutzen ausschließlich gemeinsame geprüfte Datenprovider.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 13 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m14"></a>
## Meilenstein 14 – Import und Export

**Ziel:** Explizit gemappter, verlustbewusster Austausch ohne stille Überschreibung oder externe Konverter.

**Vorgesehener Zuschnitt:** `src/specroad/exchange/, src/specroad/mappings/, src/specroad/cli/`. **Fachgrundlage:** §§ 10.12, 12.24, 12.34; Anhänge D, E, S.

**Abschlussgate:** Jedes Format besitzt echte semantische Roundtrips; Importpläne binden Quelle, Mapping, Basis und Ziel. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-14-a"></a>
### 14.a – Mappingressourcen und externe Registries

**Anforderungsbezug:** `SR-REQ-0313`, `SR-REQ-0316`, `SR-REQ-0455`.
**Verifikationsbezug:** `SR-VER-0024`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.a.W – Let it Work

- [ ] **14.a.W** · Position **571/885** · Voraussetzung: `13.h.C`.
**Exakte Commit-Message:** `14.a.W feat(exchange): Mappingressourcen und externe Registries aufbauen`

**Umsetzung:** Versionierte Typ-/Feld-/Relations-/Hierarchiemappings und Registry für externe Nichtartefaktidentitäten implementieren.

**Verhaltensabnahme:** Ein gültiges Mapping ordnet externe Werte reproduzierbar zu.

#### 14.a.R – Make it Right

- [ ] **14.a.R** · Position **572/885** · Voraussetzung: `14.a.W`.
**Exakte Commit-Message:** `14.a.R feat(exchange): Mappingressourcen und externe Registries vervollständigen`

**Vervollständigung:** Unbekannte Mappingversion und ausführbarer Konverter werden abgewiesen.

**Verhaltensabnahme:** Gleiche Eingabe mit demselben Mapping erzeugt dieselbe Importprojektion. Die W-Nachweise bleiben zusätzlich grün.

#### 14.a.C – Make it Clean

- [ ] **14.a.C** · Position **573/885** · Voraussetzung: `14.a.R`.
**Exakte Commit-Message:** `14.a.C refactor(exchange): Mappingressourcen und externe Registries bereinigen`

**Bereinigung:** Mappingauswertung von Formatparsern und Writer trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-b"></a>
### 14.b – External Identity und Importhistorie

**Anforderungsbezug:** `SR-REQ-0317`, `SR-REQ-0453`–`SR-REQ-0454`.
**Verifikationsbezug:** `SR-VER-0024`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.b.W – Let it Work

- [ ] **14.b.W** · Position **574/885** · Voraussetzung: `14.a.C`.
**Exakte Commit-Message:** `14.b.W feat(exchange): External Identity und Importhistorie aufbauen`

**Umsetzung:** Externe Identität an Artefakt/Relation samt letzter Quell-/Importprojektion und Payloadhash erhalten.

**Verhaltensabnahme:** Wiederholter Import findet dieselbe fachliche Identität.

#### 14.b.R – Make it Right

- [ ] **14.b.R** · Position **575/885** · Voraussetzung: `14.b.W`.
**Exakte Commit-Message:** `14.b.R feat(exchange): External Identity und Importhistorie vervollständigen`

**Vervollständigung:** Gleichnamige IDs verschiedener Quelldokumente nicht vermischen.

**Verhaltensabnahme:** Datenroundtrip erhält externe Identitäten und unknown Extensions vollständig. Die W-Nachweise bleiben zusätzlich grün.

#### 14.b.C – Make it Clean

- [ ] **14.b.C** · Position **576/885** · Voraussetzung: `14.b.R`.
**Exakte Commit-Message:** `14.b.C refactor(exchange): External Identity und Importhistorie bereinigen`

**Bereinigung:** Identitätsregistry und Importvergleich getrennt verwalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-c"></a>
### 14.c – Dreifachvergleich und Konfliktstrategien

**Anforderungsbezug:** `SR-REQ-0318`, `SR-REQ-0456`–`SR-REQ-0457`.
**Verifikationsbezug:** `SR-VER-0024`, `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.c.W – Let it Work

- [ ] **14.c.W** · Position **577/885** · Voraussetzung: `14.b.C`.
**Exakte Commit-Message:** `14.c.W feat(exchange): Dreifachvergleich und Konfliktstrategien aufbauen`

**Umsetzung:** error, skip, update_if_unchanged und create_new_revision anhand lokal/importiert/extern auswerten.

**Verhaltensabnahme:** Einseitige zulässige Quellenänderung kann ohne lokale Verlustüberschreibung übernommen werden.

#### 14.c.R – Make it Right

- [ ] **14.c.R** · Position **578/885** · Voraussetzung: `14.c.W`.
**Exakte Commit-Message:** `14.c.R feat(exchange): Dreifachvergleich und Konfliktstrategien vervollständigen`

**Vervollständigung:** Divergente lokale und externe Mappingprojektion erzeugt Konflikt.

**Verhaltensabnahme:** Alle Strategien prüfen beobachtbare Zielwerte und unveränderten Ausgang bei Ablehnung. Die W-Nachweise bleiben zusätzlich grün.

#### 14.c.C – Make it Clean

- [ ] **14.c.C** · Position **579/885** · Voraussetzung: `14.c.R`.
**Exakte Commit-Message:** `14.c.C refactor(exchange): Dreifachvergleich und Konfliktstrategien bereinigen`

**Bereinigung:** Vergleichskern für verschiedene Austauschformate gemeinsam führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-d"></a>
### 14.d – Importplan und Eingangsbindung

**Anforderungsbezug:** `SR-REQ-0314`, `SR-REQ-0331`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.d.W – Let it Work

- [ ] **14.d.W** · Position **580/885** · Voraussetzung: `14.c.C`.
**Exakte Commit-Message:** `14.d.W feat(exchange): Importplan und Eingangsbindung aufbauen`

**Umsetzung:** Read-only-Importplan mit Eingabe-/Mappinghash, Operationen, IDs, Anhängen, Konflikten, Verlusten und Zielwurzel erzeugen.

**Verhaltensabnahme:** Vollständig gültige Eingabe ergibt einen ausführbaren gebundenen Plan.

#### 14.d.R – Make it Right

- [ ] **14.d.R** · Position **581/885** · Voraussetzung: `14.d.W`.
**Exakte Commit-Message:** `14.d.R feat(exchange): Importplan und Eingangsbindung vervollständigen`

**Vervollständigung:** Plan nicht mit anderen Eingangsbytes oder anderer Basis wiederverwenden.

**Verhaltensabnahme:** Planer schreibt keine Projekt- oder Betriebsdateien. Die W-Nachweise bleiben zusätzlich grün.

#### 14.d.C – Make it Clean

- [ ] **14.d.C** · Position **582/885** · Voraussetzung: `14.d.R`.
**Exakte Commit-Message:** `14.d.C refactor(exchange): Importplan und Eingangsbindung bereinigen`

**Bereinigung:** Formatparser liefern Kandidaten an denselben Change-Plan-Adapter.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-e"></a>
### 14.e – Import anwenden und Verlustzustimmung

**Anforderungsbezug:** `SR-REQ-0315`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.e.W – Let it Work

- [ ] **14.e.W** · Position **583/885** · Voraussetzung: `14.d.C`.
**Exakte Commit-Message:** `14.e.W feat(exchange): Import anwenden und Verlustzustimmung aufbauen`

**Umsetzung:** Gültigen gespeicherten oder neu berechneten Plan über normalen Writer anwenden.

**Verhaltensabnahme:** Akzeptierte Objekte und Anhänge werden als eine Transaktion veröffentlicht.

#### 14.e.R – Make it Right

- [ ] **14.e.R** · Position **584/885** · Voraussetzung: `14.e.W`.
**Exakte Commit-Message:** `14.e.R feat(exchange): Import anwenden und Verlustzustimmung vervollständigen`

**Vervollständigung:** Nicht akzeptierte Verluste, stale Quelle und ungültiges Gesamtziel vor Veröffentlichung sperren.

**Verhaltensabnahme:** Fehler-/Crashfälle ergeben Basis oder Vollziel, nie eine halbe Importmenge. Die W-Nachweise bleiben zusätzlich grün.

#### 14.e.C – Make it Clean

- [ ] **14.e.C** · Position **585/885** · Voraussetzung: `14.e.R`.
**Exakte Commit-Message:** `14.e.C refactor(exchange): Import anwenden und Verlustzustimmung bereinigen`

**Bereinigung:** Keine Formatfamilie darf einen eigenen unsicheren Direktwriter besitzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-f"></a>
### 14.f – CSV-Datentypen und RFC-4180

**Anforderungsbezug:** `SR-REQ-0325`–`SR-REQ-0326`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.f.W – Let it Work

- [ ] **14.f.W** · Position **586/885** · Voraussetzung: `14.e.C`.
**Exakte Commit-Message:** `14.f.W feat(exchange): CSV-Datentypen und RFC-4180 aufbauen`

**Umsetzung:** CSV mit explizitem Mapping, UTF-8, Quotes, Listenregeln und eingebetteten Zeilenumbrüchen lesen/schreiben.

**Verhaltensabnahme:** Ein repräsentierbarer Datensatz überlebt den semantischen Export-/Importzyklus.

#### 14.f.R – Make it Right

- [ ] **14.f.R** · Position **587/885** · Voraussetzung: `14.f.W`.
**Exakte Commit-Message:** `14.f.R feat(exchange): CSV-Datentypen und RFC-4180 vervollständigen`

**Vervollständigung:** BOM nur beim Import, ungültige Typkonversion und Spaltenfehler nach Policy behandeln.

**Verhaltensabnahme:** Parserroundtrips prüfen Feldwerte und Schema, keine menschenlesbare Tabellenoptik. Die W-Nachweise bleiben zusätzlich grün.

#### 14.f.C – Make it Clean

- [ ] **14.f.C** · Position **588/885** · Voraussetzung: `14.f.R`.
**Exakte Commit-Message:** `14.f.C refactor(exchange): CSV-Datentypen und RFC-4180 bereinigen`

**Bereinigung:** Gemeinsamen CSV-Codec mit Viewexporten verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-g"></a>
### 14.g – NDJSON-Objektstrom

**Anforderungsbezug:** `SR-REQ-0327`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.g.W – Let it Work

- [ ] **14.g.W** · Position **589/885** · Voraussetzung: `14.f.C`.
**Exakte Commit-Message:** `14.g.W feat(exchange): NDJSON-Objektstrom aufbauen`

**Umsetzung:** Pro Zeile genau ein versioniertes Artefakt oder Change-Plan-Objekt streamen.

**Verhaltensabnahme:** Mehrere gültige Objekte werden vollständig in Reihenfolge verarbeitet.

#### 14.g.R – Make it Right

- [ ] **14.g.R** · Position **590/885** · Voraussetzung: `14.g.W`.
**Exakte Commit-Message:** `14.g.R feat(exchange): NDJSON-Objektstrom vervollständigen`

**Vervollständigung:** Leere Zeilen ignorieren, Kommentare und kaputte letzte Objekte ablehnen.

**Verhaltensabnahme:** Kleine Transferblöcke und Fortsetzung erhalten den vollständigen Objektstrom. Die W-Nachweise bleiben zusätzlich grün.

#### 14.g.C – Make it Clean

- [ ] **14.g.C** · Position **591/885** · Voraussetzung: `14.g.R`.
**Exakte Commit-Message:** `14.g.C refactor(exchange): NDJSON-Objektstrom bereinigen`

**Bereinigung:** Zeilenframing von JSON-Validierung und Fachmapping trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-h"></a>
### 14.h – ReqIF-Typen und Attribute

**Anforderungsbezug:** `SR-REQ-0320`–`SR-REQ-0321`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.h.W – Let it Work

- [ ] **14.h.W** · Position **592/885** · Voraussetzung: `14.g.C`.
**Exakte Commit-Message:** `14.h.W feat(exchange): ReqIF-Typen und Attribute aufbauen`

**Umsetzung:** ReqIF-1.2-Datentypen, Spec-Objects, unterstützte Attribute und Identitäten abbilden.

**Verhaltensabnahme:** Unterstützte Werte erhalten Bedeutung und externe Identität im Roundtrip.

#### 14.h.R – Make it Right

- [ ] **14.h.R** · Position **593/885** · Voraussetzung: `14.h.W`.
**Exakte Commit-Message:** `14.h.R feat(exchange): ReqIF-Typen und Attribute vervollständigen`

**Vervollständigung:** Nicht repräsentierbare Werte nicht still in Strings oder Defaults umwandeln.

**Verhaltensabnahme:** Datentyp-/Wertekorpus prüft exakte erhaltene Fachwerte und ausgewiesene Verluste. Die W-Nachweise bleiben zusätzlich grün.

#### 14.h.C – Make it Clean

- [ ] **14.h.C** · Position **594/885** · Voraussetzung: `14.h.R`.
**Exakte Commit-Message:** `14.h.C refactor(exchange): ReqIF-Typen und Attribute bereinigen`

**Bereinigung:** ReqIF-Objektmodell von XMLlesen und Spezifikationsartefakten trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-i"></a>
### 14.i – ReqIF-Hierarchien, Relationen und XHTML

**Anforderungsbezug:** `SR-REQ-0320`–`SR-REQ-0321`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.i.W – Let it Work

- [ ] **14.i.W** · Position **595/885** · Voraussetzung: `14.h.C`.
**Exakte Commit-Message:** `14.i.W feat(exchange): ReqIF-Hierarchien, Relationen und XHTML aufbauen`

**Umsetzung:** Specification/Spec-Hierarchy, Spec-Relation und erlaubte XHTML-Kerninhalte integrieren.

**Verhaltensabnahme:** Dokumenthierarchie und Beziehungen bleiben semantisch erhalten.

#### 14.i.R – Make it Right

- [ ] **14.i.R** · Position **596/885** · Voraussetzung: `14.i.W`.
**Exakte Commit-Message:** `14.i.R feat(exchange): ReqIF-Hierarchien, Relationen und XHTML vervollständigen`

**Vervollständigung:** Zyklen, externe Inhalte und unaufgelöste referenzierte Anhänge vor Apply erkennen.

**Verhaltensabnahme:** Wiederimport erhält Hierarchie- und Relationsidentität innerhalb des Schnittmengenprofils. Die W-Nachweise bleiben zusätzlich grün.

#### 14.i.C – Make it Clean

- [ ] **14.i.C** · Position **597/885** · Voraussetzung: `14.i.R`.
**Exakte Commit-Message:** `14.i.C refactor(exchange): ReqIF-Hierarchien, Relationen und XHTML bereinigen`

**Bereinigung:** Den sicheren XML-Kern aus M12 und Dokumentdaten aus M11 verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-j"></a>
### 14.j – Informationsverluste und Erweiterungserhalt

**Anforderungsbezug:** `SR-REQ-0322`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.j.W – Let it Work

- [ ] **14.j.W** · Position **598/885** · Voraussetzung: `14.i.C`.
**Exakte Commit-Message:** `14.j.W feat(exchange): Informationsverluste und Erweiterungserhalt aufbauen`

**Umsetzung:** Nicht unterstützte Inhalte entweder namespaced erhalten oder einzeln als Verlust identifizieren.

**Verhaltensabnahme:** Zulässige unbekannte Zusatzdaten bleiben unverändert über den Austausch erhalten.

#### 14.j.R – Make it Right

- [ ] **14.j.R** · Position **599/885** · Voraussetzung: `14.j.W`.
**Exakte Commit-Message:** `14.j.R feat(exchange): Informationsverluste und Erweiterungserhalt vervollständigen`

**Vervollständigung:** Kein pauschales success bei verschwiegenen Verlusten; fail-on-loss greift.

**Verhaltensabnahme:** Verlustliste entspricht sämtlichen nicht repräsentierten Fachwerten. Die W-Nachweise bleiben zusätzlich grün.

#### 14.j.C – Make it Clean

- [ ] **14.j.C** · Position **600/885** · Voraussetzung: `14.j.R`.
**Exakte Commit-Message:** `14.j.C refactor(exchange): Informationsverluste und Erweiterungserhalt bereinigen`

**Bereinigung:** Verlustklassifikation unabhängig von menschenlesbaren Meldungen gestalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-k"></a>
### 14.k – ReqIFZ und sicheres Archivprofil

**Anforderungsbezug:** `SR-REQ-0323`, `SR-REQ-0486`.
**Verifikationsbezug:** `SR-VER-0024`, `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.k.W – Let it Work

- [ ] **14.k.W** · Position **601/885** · Voraussetzung: `14.j.C`.
**Exakte Commit-Message:** `14.k.W feat(exchange): ReqIFZ und sicheres Archivprofil aufbauen`

**Umsetzung:** ReqIFZ auf den vorhandenen sicheren kanonischen Archivcodec aufsetzen.

**Verhaltensabnahme:** ReqIF-Daten und gebundene Anhänge überleben Containerroundtrip.

#### 14.k.R – Make it Right

- [ ] **14.k.R** · Position **602/885** · Voraussetzung: `14.k.W`.
**Exakte Commit-Message:** `14.k.R feat(exchange): ReqIFZ und sicheres Archivprofil vervollständigen`

**Vervollständigung:** Traversal, doppelte Ziele, Sonderdateien und harte Expansionsgrenzen vor Extraktion abweisen.

**Verhaltensabnahme:** Containerdaten-/Sicherheitsvektoren prüfen echte Byte-/Pfadverträge, keine Darstellung. Die W-Nachweise bleiben zusätzlich grün.

#### 14.k.C – Make it Clean

- [ ] **14.k.C** · Position **603/885** · Voraussetzung: `14.k.R`.
**Exakte Commit-Message:** `14.k.C refactor(exchange): ReqIFZ und sicheres Archivprofil bereinigen`

**Bereinigung:** ReqIFZ-Manifest und gemeinsames ZIP-Profil ohne zweite Archivimplementation verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-l"></a>
### 14.l – Exportumfang und deterministisches Manifest

**Anforderungsbezug:** `SR-REQ-0319`, `SR-REQ-0328`–`SR-REQ-0329`, `SR-REQ-0332`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.l.W – Let it Work

- [ ] **14.l.W** · Position **604/885** · Voraussetzung: `14.k.C`.
**Exakte Commit-Message:** `14.l.W feat(exchange): Exportumfang und deterministisches Manifest aufbauen`

**Umsetzung:** Project/document/query/release-Scopes, Mapping, Anhänge und deterministischen Snapshotzeitpunkt exportieren.

**Verhaltensabnahme:** Gleiche Fachinputs liefern gleiche Austauschbytes und dasselbe Exportmanifest.

#### 14.l.R – Make it Right

- [ ] **14.l.R** · Position **605/885** · Voraussetzung: `14.l.W`.
**Exakte Commit-Message:** `14.l.R feat(exchange): Exportumfang und deterministisches Manifest vervollständigen`

**Vervollständigung:** Laufzeit und absolute Pfade nicht in den Fachcontainer mischen; Export bleibt ohne normative Writes.

**Verhaltensabnahme:** Bytevergleich ausschließlich des maschinenlesbaren Austauschvertrags und Projektinventur. Die W-Nachweise bleiben zusätzlich grün.

#### 14.l.C – Make it Clean

- [ ] **14.l.C** · Position **606/885** · Voraussetzung: `14.l.R`.
**Exakte Commit-Message:** `14.l.C refactor(exchange): Exportumfang und deterministisches Manifest bereinigen`

**Bereinigung:** Scope-/Zeitprojektion zentral für alle Formate bereitstellen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-m"></a>
### 14.m – Mehrsprachiger Requirement-Austausch

**Anforderungsbezug:** `SR-REQ-0723`.
**Verifikationsbezug:** `SR-VER-0049`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.m.W – Let it Work

- [ ] **14.m.W** · Position **607/885** · Voraussetzung: `14.l.C`.
**Exakte Commit-Message:** `14.m.W feat(exchange): Mehrsprachiger Requirement-Austausch aufbauen`

**Umsetzung:** language und normative_force über explizite CSV-/NDJSON-/ReqIF-Felder erhalten.

**Verhaltensabnahme:** Mehrsprachige Requirements behalten Force und vollständiges Originalstatement.

#### 14.m.R – Make it Right

- [ ] **14.m.R** · Position **608/885** · Voraussetzung: `14.m.W`.
**Exakte Commit-Message:** `14.m.R feat(exchange): Mehrsprachiger Requirement-Austausch vervollständigen`

**Vervollständigung:** Fehlende Abbildung als Verlust statt Ableitung aus Keywords oder Detektor behandeln.

**Verhaltensabnahme:** Datenroundtrips mit de/en/hi/id/pt/es/ru/ja/zh und Kennzeichnungsvarianten bleiben verlustfrei. Die W-Nachweise bleiben zusätzlich grün.

#### 14.m.C – Make it Clean

- [ ] **14.m.C** · Position **609/885** · Voraussetzung: `14.m.R`.
**Exakte Commit-Message:** `14.m.C refactor(exchange): Mehrsprachiger Requirement-Austausch bereinigen`

**Bereinigung:** Sprach-/Force-Mapping auf denselben Requirement-Konstruktor aus M2 setzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-n"></a>
### 14.n – Netzwerk-/Konverterfreiheit und Archivangriffe

**Anforderungsbezug:** `SR-REQ-0324`, `SR-REQ-0532`.
**Verifikationsbezug:** `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.n.W – Let it Work

- [ ] **14.n.W** · Position **610/885** · Voraussetzung: `14.m.C`.
**Exakte Commit-Message:** `14.n.W feat(exchange): Netzwerk-/Konverterfreiheit und Archivangriffe aufbauen`

**Umsetzung:** Alle Parser ausschließlich lokal und deklarativ betreiben; negative Sicherheitskorpora integrieren.

**Verhaltensabnahme:** Zulässiger Import funktioniert in netzwerkisolierter Coreumgebung.

#### 14.n.R – Make it Right

- [ ] **14.n.R** · Position **611/885** · Voraussetzung: `14.n.W`.
**Exakte Commit-Message:** `14.n.R feat(exchange): Netzwerk-/Konverterfreiheit und Archivangriffe vervollständigen`

**Vervollständigung:** Entity-Auflösung, Shellkonverter und bösartige Dateipfade vor Nutzung blockieren.

**Verhaltensabnahme:** Angriffseingaben führen zu keinem externen Zugriff und zu keinem Teilwrite. Die W-Nachweise bleiben zusätzlich grün.

#### 14.n.C – Make it Clean

- [ ] **14.n.C** · Position **612/885** · Voraussetzung: `14.n.R`.
**Exakte Commit-Message:** `14.n.C refactor(exchange): Netzwerk-/Konverterfreiheit und Archivangriffe bereinigen`

**Bereinigung:** Wiederverwendbare Security-Fälle über die Formatadapter parametrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-14-o"></a>
### 14.o – Format-Roundtrips und Importfortsetzung

**Anforderungsbezug:** `SR-REQ-0285`, `SR-REQ-0330`.
**Verifikationsbezug:** `SR-VER-0021`, `SR-VER-0024`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 14.o.W – Let it Work

- [ ] **14.o.W** · Position **613/885** · Voraussetzung: `14.n.C`.
**Exakte Commit-Message:** `14.o.W feat(exchange): Format-Roundtrips und Importfortsetzung aufbauen`

**Umsetzung:** Vollständige Roundtripkorpora einschließlich Anhängen, Reviews und Konfigurationen je Format ausführen.

**Verhaltensabnahme:** Schnittmengenprofil erhält Identitäten, Werte, Hierarchie und passende Reviewkontexte.

#### 14.o.R – Make it Right

- [ ] **14.o.R** · Position **614/885** · Voraussetzung: `14.o.W`.
**Exakte Commit-Message:** `14.o.R feat(exchange): Format-Roundtrips und Importfortsetzung vervollständigen`

**Vervollständigung:** Veränderte Reviewbindung wird suspect/unreviewed; geteilte Verarbeitung verliert kein Objekt.

**Verhaltensabnahme:** Einzellauf und vollständige Workfolge ergeben denselben Importplan und Zielstand. Die W-Nachweise bleiben zusätzlich grün.

#### 14.o.C – Make it Clean

- [ ] **14.o.C** · Position **615/885** · Voraussetzung: `14.o.R`.
**Exakte Commit-Message:** `14.o.C refactor(exchange): Format-Roundtrips und Importfortsetzung bereinigen`

**Bereinigung:** Formatübergreifende Datenoracles nutzen statt Exportdarstellung zu testen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 14 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m15"></a>
## Meilenstein 15 – Projektbundles und portabler Austausch

**Ziel:** Verifizierbare Voll-/Teilprojekte, portierte Idempotenz und erhaltender Restore aus echten vollständigen Quelldaten.

**Vorgesehener Zuschnitt:** `src/specroad/bundles/, src/specroad/archive/, src/specroad/recovery/`. **Fachgrundlage:** §§ 10.7.1, 10.16, 12.28, 12.36; Anhänge C, E, P.

**Abschlussgate:** Bundleintegrität, root-sicheres Extrahieren und geschützte Geschichte werden nachgewiesen; ein Hash allein ist weder Originalbyte-Ersatz noch Authentizitätsbeweis. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-15-a"></a>
### 15.a – Kanonisches ZIP und Manifestdomäne

**Anforderungsbezug:** `SR-REQ-0387`–`SR-REQ-0388`, `SR-REQ-0485`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.a.W – Let it Work

- [ ] **15.a.W** · Position **616/885** · Voraussetzung: `14.o.C`.
**Exakte Commit-Message:** `15.a.W feat(bundle): Kanonisches ZIP und Manifestdomäne aufbauen`

**Umsetzung:** Vollständiges ZIP-Profil und Manifest mit exakt allen Payloads ohne eigene rekursive Aufnahme ausprägen.

**Verhaltensabnahme:** Derselbe Payloadsatz erzeugt kanonische Containerbytes.

#### 15.a.R – Make it Right

- [ ] **15.a.R** · Position **617/885** · Voraussetzung: `15.a.W`.
**Exakte Commit-Message:** `15.a.R feat(bundle): Kanonisches ZIP und Manifestdomäne vervollständigen`

**Vervollständigung:** Dubletten, Groß-/Kleinschreibungskollision, Sondertypen und nichtkanonische Parameter erkennen.

**Verhaltensabnahme:** Versionierte ZIP-Datenvektoren prüfen Bytes und Pfadsicherheit als Austauschvertrag. Die W-Nachweise bleiben zusätzlich grün.

#### 15.a.C – Make it Clean

- [ ] **15.a.C** · Position **618/885** · Voraussetzung: `15.a.R`.
**Exakte Commit-Message:** `15.a.C refactor(bundle): Kanonisches ZIP und Manifestdomäne bereinigen`

**Bereinigung:** Gemeinsamen M6-Archivcodec vervollständigen statt ein zweites Format zu erfinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-b"></a>
### 15.b – Vollprojektbundle erzeugen

**Anforderungsbezug:** `SR-REQ-0386`, `SR-REQ-0407`, `SR-REQ-0481`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0029`, `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.b.W – Let it Work

- [ ] **15.b.W** · Position **619/885** · Voraussetzung: `15.a.C`.
**Exakte Commit-Message:** `15.b.W feat(bundle): Vollprojektbundle erzeugen aufbauen`

**Umsetzung:** Project/closed-Bundle mit vollständig schreibbarem Modell und notwendigen Objekten erzeugen.

**Verhaltensabnahme:** Verifiziertes Bundle enthält die vollständige Projektclosure.

#### 15.b.R – Make it Right

- [ ] **15.b.R** · Position **620/885** · Voraussetzung: `15.b.W`.
**Exakte Commit-Message:** `15.b.R feat(bundle): Vollprojektbundle erzeugen vervollständigen`

**Vervollständigung:** Unvollständige Transaktion oder fehlende Pflichtressource verhindert normalen Vollbundleabschluss.

**Verhaltensabnahme:** Manifest-/Payload-/Scopeinventur weist keine ausgelassenen Fachbytes nach. Die W-Nachweise bleiben zusätzlich grün.

#### 15.b.C – Make it Clean

- [ ] **15.b.C** · Position **621/885** · Voraussetzung: `15.b.R`.
**Exakte Commit-Message:** `15.b.C refactor(bundle): Vollprojektbundle erzeugen bereinigen`

**Bereinigung:** Bundlefachmodell auf vorhandenen Scope-/Snapshotdienst aufsetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-c"></a>
### 15.c – Teilbundle und Boundarybindung

**Anforderungsbezug:** `SR-REQ-0482`–`SR-REQ-0483`.
**Verifikationsbezug:** `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.c.W – Let it Work

- [ ] **15.c.W** · Position **622/885** · Voraussetzung: `15.b.C`.
**Exakte Commit-Message:** `15.c.W feat(bundle): Teilbundle und Boundarybindung aufbauen`

**Umsetzung:** Document-/Release-Scope als partial/read_only mit Ursprungs- und Teilmodellwurzel speichern.

**Verhaltensabnahme:** Fehlende schwache Zielressource ist exakt durch erlaubte Boundary gebunden.

#### 15.c.R – Make it Right

- [ ] **15.c.R** · Position **623/885** · Voraussetzung: `15.c.W`.
**Exakte Commit-Message:** `15.c.R feat(bundle): Teilbundle und Boundarybindung vervollständigen`

**Vervollständigung:** Falsche Kind-/Read-only-/Scopekombination und fehlende starke Ziele ablehnen.

**Verhaltensabnahme:** Partials sind niemals als vollständige schreibbare Projekte ausgewiesen. Die W-Nachweise bleiben zusätzlich grün.

#### 15.c.C – Make it Clean

- [ ] **15.c.C** · Position **624/885** · Voraussetzung: `15.c.R`.
**Exakte Commit-Message:** `15.c.C refactor(bundle): Teilbundle und Boundarybindung bereinigen`

**Bereinigung:** Eine feste Kind-/Scope-Matrix für Erzeugen, Prüfen und Lesen verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-d"></a>
### 15.d – Bundleverifikation ohne Extraktion

**Anforderungsbezug:** `SR-REQ-0389`.
**Verifikationsbezug:** `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.d.W – Let it Work

- [ ] **15.d.W** · Position **625/885** · Voraussetzung: `15.c.C`.
**Exakte Commit-Message:** `15.d.W feat(bundle): Bundleverifikation ohne Extraktion aufbauen`

**Umsetzung:** ZIP, Payloadmengen, Hashes, Referenzen und optionale externe Gesamt-ZIP-Bindung schreibfrei prüfen.

**Verhaltensabnahme:** Intakter Container kann ohne Projektroot validiert werden.

#### 15.d.R – Make it Right

- [ ] **15.d.R** · Position **626/885** · Voraussetzung: `15.d.W`.
**Exakte Commit-Message:** `15.d.R feat(bundle): Bundleverifikation ohne Extraktion vervollständigen`

**Vervollständigung:** Bitmanipulation, zusätzliche/unaufgeführte Datei und ersetztes Archiv bei altem externem Hash erkennen.

**Verhaltensabnahme:** Verifikation erzeugt keine Extraktionsdateien und beansprucht ohne externe Bindung keine Erstellerauthentizität. Die W-Nachweise bleiben zusätzlich grün.

#### 15.d.C – Make it Clean

- [ ] **15.d.C** · Position **627/885** · Voraussetzung: `15.d.R`.
**Exakte Commit-Message:** `15.d.C refactor(bundle): Bundleverifikation ohne Extraktion bereinigen`

**Bereinigung:** Containerintegrität und fachliche Modellintegrität als getrennte überprüfbare Stufen führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-e"></a>
### 15.e – Atomare Extraktion und Zielschutz

**Anforderungsbezug:** `SR-REQ-0390`, `SR-REQ-0480`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0032`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.e.W – Let it Work

- [ ] **15.e.W** · Position **628/885** · Voraussetzung: `15.d.C`.
**Exakte Commit-Message:** `15.e.W feat(bundle): Atomare Extraktion und Zielschutz aufbauen`

**Umsetzung:** Ausschließlich verifiziertes Bundle in fehlendes oder leeres Ziel über Bootstrapjournal extrahieren.

**Verhaltensabnahme:** Vollständiges Projekt ist nach Abschluss regulär ladbar.

#### 15.e.R – Make it Right

- [ ] **15.e.R** · Position **629/885** · Voraussetzung: `15.e.W`.
**Exakte Commit-Message:** `15.e.R feat(bundle): Atomare Extraktion und Zielschutz vervollständigen`

**Vervollständigung:** Bestehende Zieldaten, Pfadtraversal und Abbruch niemals überschreiben beziehungsweise als Erfolg behandeln.

**Verhaltensabnahme:** Fault-Injection liefert Ausgang oder vollständige Rootstruktur unter Erhalt fremder Dateien. Die W-Nachweise bleiben zusätzlich grün.

#### 15.e.C – Make it Clean

- [ ] **15.e.C** · Position **630/885** · Voraussetzung: `15.e.R`.
**Exakte Commit-Message:** `15.e.C refactor(bundle): Atomare Extraktion und Zielschutz bereinigen`

**Bereinigung:** Rootcreationprimitiven aus init wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-f"></a>
### 15.f – Read-only-Befehle auf Partials

**Anforderungsbezug:** `SR-REQ-0484`.
**Verifikationsbezug:** `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.f.W – Let it Work

- [ ] **15.f.W** · Position **631/885** · Voraussetzung: `15.e.C`.
**Exakte Commit-Message:** `15.f.W feat(bundle): Read-only-Befehle auf Partials aufbauen`

**Umsetzung:** Zulässige lesende Funktionen und referenzielle Boundaryprüfung auf Partialmodellen aktivieren.

**Verhaltensabnahme:** Unterstützte Abfrage funktioniert ohne Vollprojektbehauptung.

#### 15.f.R – Make it Right

- [ ] **15.f.R** · Position **632/885** · Voraussetzung: `15.f.W`.
**Exakte Commit-Message:** `15.f.R feat(bundle): Read-only-Befehle auf Partials vervollständigen`

**Vervollständigung:** Jeder normative Write auf Partial wird mit Code 7 abgewiesen.

**Verhaltensabnahme:** Fehlendes Ziel ist nur bei exakt passender Boundary akzeptiert. Die W-Nachweise bleiben zusätzlich grün.

#### 15.f.C – Make it Clean

- [ ] **15.f.C** · Position **633/885** · Voraussetzung: `15.f.R`.
**Exakte Commit-Message:** `15.f.C refactor(bundle): Read-only-Befehle auf Partials bereinigen`

**Bereinigung:** Partialberechtigung im gemeinsamen Command-/Readerkontext führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-g"></a>
### 15.g – Receipts und portable Idempotenz

**Anforderungsbezug:** `SR-REQ-0487`–`SR-REQ-0488`, `SR-REQ-0490`.
**Verifikationsbezug:** `SR-VER-0033`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.g.W – Let it Work

- [ ] **15.g.W** · Position **634/885** · Voraussetzung: `15.f.C`.
**Exakte Commit-Message:** `15.g.W feat(bundle): Receipts und portable Idempotenz aufbauen`

**Umsetzung:** Abgeschlossene Request-/Transaktionsreceipts separat transportieren; Ausschluss setzt local_only.

**Verhaltensabnahme:** Retry nach Vollbundletransfer liefert dieselben IDs ohne neue Fachänderung.

#### 15.g.R – Make it Right

- [ ] **15.g.R** · Position **635/885** · Voraussetzung: `15.g.W`.
**Exakte Commit-Message:** `15.g.R feat(bundle): Receipts und portable Idempotenz vervollständigen`

**Vervollständigung:** Veränderte Operationsbindung bleibt Konflikt; ausgeschlossene Receipts nicht als portiert behaupten.

**Verhaltensabnahme:** Modellwurzel bleibt unabhängig vom Betriebssektionsinhalt. Die W-Nachweise bleiben zusätzlich grün.

#### 15.g.C – Make it Clean

- [ ] **15.g.C** · Position **636/885** · Voraussetzung: `15.g.R`.
**Exakte Commit-Message:** `15.g.C refactor(bundle): Receipts und portable Idempotenz bereinigen`

**Bereinigung:** Fachpayload und betriebliche Nachweise getrennt hashen und auswerten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-h"></a>
### 15.h – Bundle als Vergleichsquelle

**Anforderungsbezug:** `SR-REQ-0114`, `SR-REQ-0362`.
**Verifikationsbezug:** `SR-VER-0008`, `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.h.W – Let it Work

- [ ] **15.h.W** · Position **637/885** · Voraussetzung: `15.g.C`.
**Exakte Commit-Message:** `15.h.W feat(bundle): Bundle als Vergleichsquelle aufbauen`

**Umsetzung:** Verifizierte Bundles in die gemeinsame Diff-/Mergequellenregistry einbinden.

**Verhaltensabnahme:** Bundle und identischer lokaler Snapshot ergeben denselben fachlichen Vergleich.

#### 15.h.R – Make it Right

- [ ] **15.h.R** · Position **638/885** · Voraussetzung: `15.h.W`.
**Exakte Commit-Message:** `15.h.R feat(bundle): Bundle als Vergleichsquelle vervollständigen`

**Vervollständigung:** Teilbundle oder fremde project_id nicht als vollständige Mergequelle verwenden.

**Verhaltensabnahme:** Adapter greift nicht ergänzend auf zufällige aktuelle Dateien zurück. Die W-Nachweise bleiben zusätzlich grün.

#### 15.h.C – Make it Clean

- [ ] **15.h.C** · Position **639/885** · Voraussetzung: `15.h.R`.
**Exakte Commit-Message:** `15.h.C refactor(bundle): Bundle als Vergleichsquelle bereinigen`

**Bereinigung:** Quellenauflösung aus M8 nun mit tatsächlichem Bundleleser vollständig schließen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-i"></a>
### 15.i – Offene Transaktionen und externe Sicherung

**Anforderungsbezug:** `SR-REQ-0568`.
**Verifikationsbezug:** `SR-VER-0035`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.i.W – Let it Work

- [ ] **15.i.W** · Position **640/885** · Voraussetzung: `15.h.C`.
**Exakte Commit-Message:** `15.i.W feat(bundle): Offene Transaktionen und externe Sicherung aufbauen`

**Umsetzung:** Normales Projektbundle bei ungelöster Transaktion sperren; separat markierten Workexport zulassen.

**Verhaltensabnahme:** Intakter abgeschlossener Stand lässt sich sichern, offene Arbeit nur nach eigenem Workvertrag.

#### 15.i.R – Make it Right

- [ ] **15.i.R** · Position **641/885** · Voraussetzung: `15.i.W`.
**Exakte Commit-Message:** `15.i.R feat(bundle): Offene Transaktionen und externe Sicherung vervollständigen`

**Vervollständigung:** Verlorene lokale Bytes nicht als aus einer alten Chatbeschreibung wiederherstellbar darstellen.

**Verhaltensabnahme:** Verlust-/Pfadwechselkorpus weist tatsächlich benötigte Sicherungsdaten nach. Die W-Nachweise bleiben zusätzlich grün.

#### 15.i.C – Make it Clean

- [ ] **15.i.C** · Position **642/885** · Voraussetzung: `15.i.R`.
**Exakte Commit-Message:** `15.i.C refactor(bundle): Offene Transaktionen und externe Sicherung bereinigen`

**Bereinigung:** Sicherungsstatus ausdrücklich von aktuell laufender Arbeit unterscheiden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-j"></a>
### 15.j – Vollqualifizierter Restore-Plan

**Anforderungsbezug:** `SR-REQ-0461`.
**Verifikationsbezug:** `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.j.W – Let it Work

- [ ] **15.j.W** · Position **643/885** · Voraussetzung: `15.i.C`.
**Exakte Commit-Message:** `15.j.W feat(bundle): Vollqualifizierter Restore-Plan aufbauen`

**Umsetzung:** restore-preserve-v1 nur aus unfiltrierter geschlossener Vollprojekt-Baseline oder verifiziertem Vollbundle planen.

**Verhaltensabnahme:** Zielinventur bindet Quelle, neue Zielwurzel und erhaltene geschützte Geschichte.

#### 15.j.R – Make it Right

- [ ] **15.j.R** · Position **644/885** · Voraussetzung: `15.j.W`.
**Exakte Commit-Message:** `15.j.R feat(bundle): Vollqualifizierter Restore-Plan vervollständigen`

**Vervollständigung:** Release-/Specification-/gefilterte Quelle oder fehlende Originalbytes ohne Vorprüfungswrite zurückweisen.

**Verhaltensabnahme:** R-44/R-45 zeigen gültige Vollquelle versus unzureichende Quelle mit unverändertem Projekt. Die W-Nachweise bleiben zusätzlich grün.

#### 15.j.C – Make it Clean

- [ ] **15.j.C** · Position **645/885** · Voraussetzung: `15.j.R`.
**Exakte Commit-Message:** `15.j.C refactor(bundle): Vollqualifizierter Restore-Plan bereinigen`

**Bereinigung:** Restoreplanung als spezialisierte Recoveryoperation von normalem Import trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-k"></a>
### 15.k – Geschützte Historie beim Restore

**Anforderungsbezug:** `SR-REQ-0461`–`SR-REQ-0462`.
**Verifikationsbezug:** `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.k.W – Let it Work

- [ ] **15.k.W** · Position **646/885** · Voraussetzung: `15.j.C`.
**Exakte Commit-Message:** `15.k.W feat(bundle): Geschützte Historie beim Restore aufbauen`

**Umsetzung:** Jüngere gültige immutable Evidence/Baselines und ihre Referenzclosure bytegetreu im expliziten Restoreziel erhalten.

**Verhaltensabnahme:** Rückkehr zu altem Fachstand löscht keinen jüngeren geschützten Nachweis stillschweigend.

#### 15.k.R – Make it Right

- [ ] **15.k.R** · Position **647/885** · Voraussetzung: `15.k.W`.
**Exakte Commit-Message:** `15.k.R feat(bundle): Geschützte Historie beim Restore vervollständigen`

**Vervollständigung:** Gleiche ID mit anderem Inhalt oder fehlende notwendige Historienbytes als Konflikt behandeln.

**Verhaltensabnahme:** R-46 belegt Erhaltung und genaue Ablehnung bei Historienkonflikten. Die W-Nachweise bleiben zusätzlich grün.

#### 15.k.C – Make it Clean

- [ ] **15.k.C** · Position **648/885** · Voraussetzung: `15.k.R`.
**Exakte Commit-Message:** `15.k.C refactor(bundle): Geschützte Historie beim Restore bereinigen`

**Bereinigung:** Schutzinventur und Quellsnapshot zu einem sichtbaren Zielplan falten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-15-l"></a>
### 15.l – Restore veröffentlichen und Crashabsicherung

**Anforderungsbezug:** `SR-REQ-0461`–`SR-REQ-0462`.
**Verifikationsbezug:** `SR-VER-0031`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 15.l.W – Let it Work

- [ ] **15.l.W** · Position **649/885** · Voraussetzung: `15.k.C`.
**Exakte Commit-Message:** `15.l.W feat(bundle): Restore veröffentlichen und Crashabsicherung aufbauen`

**Umsetzung:** Gebundene Sicherung, Quellenprüfung und vollständige Recoverypublikation samt Audit ausführen.

**Verhaltensabnahme:** Erfolgreicher Restore erreicht genau die im Plan gebundene Zielwurzel.

#### 15.l.R – Make it Right

- [ ] **15.l.R** · Position **650/885** · Voraussetzung: `15.l.W`.
**Exakte Commit-Message:** `15.l.R feat(bundle): Restore veröffentlichen und Crashabsicherung vervollständigen`

**Vervollständigung:** Quellenwechsel, unvollständige Sicherung und Crash erhalten ursprüngliche Journale und Wiederherstellungsdaten.

**Verhaltensabnahme:** R-47 sowie Einzellauf-/Workparität weisen vollständigen Zustand oder gesperrten Recoveryfall nach. Die W-Nachweise bleiben zusätzlich grün.

#### 15.l.C – Make it Clean

- [ ] **15.l.C** · Position **651/885** · Voraussetzung: `15.l.R`.
**Exakte Commit-Message:** `15.l.C refactor(bundle): Restore veröffentlichen und Crashabsicherung bereinigen`

**Bereinigung:** Bestehende Transaktions-/Recoveryprimitiven verwenden, keine destruktive Sonderabkürzung.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 15 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m16"></a>
## Meilenstein 16 – Schema- und Datenmigration

**Ziel:** Unterstützte Altstände vollständig sichern, kontrolliert transformieren und historische Originalnachweise byteidentisch erhalten.

**Vorgesehener Zuschnitt:** `src/specroad/migration/, src/specroad/legacy/, src/specroad/schemas/`. **Fachgrundlage:** §§ 10.7, 12.20, 12.43; Anhänge K, Q, S.7.

**Abschlussgate:** 0.1.0 nach 0.2.0 ist anhand echter historischer Fixtures verlustfrei nachgewiesen; neue Pflichtangaben und aktuelle Freigaben werden nicht erfunden. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-16-a"></a>
### 16.a – Versionsgraph und Migrationsschrittvertrag

**Anforderungsbezug:** `SR-REQ-0263`–`SR-REQ-0265`, `SR-REQ-0274`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.a.W – Let it Work

- [ ] **16.a.W** · Position **652/885** · Voraussetzung: `15.l.C`.
**Exakte Commit-Message:** `16.a.W feat(migration): Versionsgraph und Migrationsschrittvertrag aufbauen`

**Umsetzung:** Versionierte Schritte mit Quelle, Ziel, Voraussetzungen, Transformation, Nachbedingungen und Reversibilität registrieren.

**Verhaltensabnahme:** Ein vollständig unterstützter Pfad ist geordnet auflösbar; unbekanntes Ziel bleibt unzulässig.

#### 16.a.R – Make it Right

- [ ] **16.a.R** · Position **653/885** · Voraussetzung: `16.a.W`.
**Exakte Commit-Message:** `16.a.R feat(migration): Versionsgraph und Migrationsschrittvertrag vervollständigen`

**Vervollständigung:** Lücken, Zyklen und nicht implementierte Rückwege ablehnen; kein pauschales Downgrade anbieten.

**Verhaltensabnahme:** Jeder registrierte Schritt besitzt eigene fachliche Eingabe-/Ergebnisvektoren. Die W-Nachweise bleiben zusätzlich grün.

#### 16.a.C – Make it Clean

- [ ] **16.a.C** · Position **654/885** · Voraussetzung: `16.a.R`.
**Exakte Commit-Message:** `16.a.C refactor(migration): Versionsgraph und Migrationsschrittvertrag bereinigen`

**Bereinigung:** Pfadauflösung von tatsächlicher Transformation und CLI trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-b"></a>
### 16.b – Quellinventur und historischer Core-Leser

**Anforderungsbezug:** `SR-REQ-0247`, `SR-REQ-0272`, `SR-REQ-0639`, `SR-REQ-0641`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0020`, `SR-VER-0042`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.b.W – Let it Work

- [ ] **16.b.W** · Position **655/885** · Voraussetzung: `16.a.C`.
**Exakte Commit-Message:** `16.b.W feat(migration): Quellinventur und historischer Core-Leser aufbauen`

**Umsetzung:** Eingebaute 0.1-Leser und Inventur mit mutable, immutable_legacy und referenced_payload bereitstellen.

**Verhaltensabnahme:** Gültige alte Projektfixture wird ohne Fremdpaket und ohne Änderung ihrer Bytes vollständig eingelesen.

#### 16.b.R – Make it Right

- [ ] **16.b.R** · Position **656/885** · Voraussetzung: `16.b.W`.
**Exakte Commit-Message:** `16.b.R feat(migration): Quellinventur und historischer Core-Leser vervollständigen`

**Vervollständigung:** Unbekannte Quellversion, fehlende referenzierte Bytes und unklare Unveränderbarkeit als Fehler behandeln.

**Verhaltensabnahme:** Evidence, Baselines, abgeschlossene Proposals und Reviews werden korrekt geschützt. Die W-Nachweise bleiben zusätzlich grün.

#### 16.b.C – Make it Clean

- [ ] **16.b.C** · Position **657/885** · Voraussetzung: `16.b.R`.
**Exakte Commit-Message:** `16.b.C refactor(migration): Quellinventur und historischer Core-Leser bereinigen`

**Bereinigung:** Versionsleser strikt von regulärem 0.2-Writer und In-memory-Projektion abgrenzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-c"></a>
### 16.c – Read-only-Migrationsplan

**Anforderungsbezug:** `SR-REQ-0263`–`SR-REQ-0264`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.c.W – Let it Work

- [ ] **16.c.W** · Position **658/885** · Voraussetzung: `16.b.C`.
**Exakte Commit-Message:** `16.c.W feat(migration): Read-only-Migrationsplan aufbauen`

**Umsetzung:** Transformation samt neuen Pflichtfeldern, Verlustkennungen, Operationen und erwarteter Zielwurzel schreibfrei planen.

**Verhaltensabnahme:** Derselbe Quellstand und dieselben expliziten Mappings liefern denselben Fachplan.

#### 16.c.R – Make it Right

- [ ] **16.c.R** · Position **659/885** · Voraussetzung: `16.c.W`.
**Exakte Commit-Message:** `16.c.R feat(migration): Read-only-Migrationsplan vervollständigen`

**Vervollständigung:** Übergebenes Planfile an aktuelle Quellenhashes, Versionspfad und Zielversion binden.

**Verhaltensabnahme:** Geänderte Quelle oder manipulierte Zielversion verhindert Apply vor Mutation. Die W-Nachweise bleiben zusätzlich grün.

#### 16.c.C – Make it Clean

- [ ] **16.c.C** · Position **660/885** · Voraussetzung: `16.c.R`.
**Exakte Commit-Message:** `16.c.C refactor(migration): Read-only-Migrationsplan bereinigen`

**Bereinigung:** Den gemeinsamen Change-Plan-Kern statt eines zweiten Änderungsformats verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-d"></a>
### 16.d – Vollständige verifizierte Quellsicherung

**Anforderungsbezug:** `SR-REQ-0266`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.d.W – Let it Work

- [ ] **16.d.W** · Position **661/885** · Voraussetzung: `16.c.C`.
**Exakte Commit-Message:** `16.d.W feat(migration): Vollständige verifizierte Quellsicherung aufbauen`

**Umsetzung:** Vor erster Migration den unfiltrierten Ausgangsstand in deterministischem Vollbundle sichern und Hash/Pfad binden.

**Verhaltensabnahme:** Sicherung lässt alle tatsächlich vorhandenen Originaldaten vollständig rekonstruieren.

#### 16.d.R – Make it Right

- [ ] **16.d.R** · Position **662/885** · Voraussetzung: `16.d.W`.
**Exakte Commit-Message:** `16.d.R feat(migration): Vollständige verifizierte Quellsicherung vervollständigen`

**Vervollständigung:** Fehlende Bytes, unverifiziertes Bundle und unvollständige Closure verhindern Veröffentlichung.

**Verhaltensabnahme:** Defekte Sicherung oder fehlender Speicher führt zu keiner Schemaänderung. Die W-Nachweise bleiben zusätzlich grün.

#### 16.d.C – Make it Clean

- [ ] **16.d.C** · Position **663/885** · Voraussetzung: `16.d.R`.
**Exakte Commit-Message:** `16.d.C refactor(migration): Vollständige verifizierte Quellsicherung bereinigen`

**Bereinigung:** Den M15-Bundlevertrag einschließlich Legacy-Rohdaten verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-e"></a>
### 16.e – Explizite Sprach- und Verbindlichkeitsmigration

**Anforderungsbezug:** `SR-REQ-0272`, `SR-REQ-0724`–`SR-REQ-0725`.
**Verifikationsbezug:** `SR-VER-0020`, `SR-VER-0049`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.e.W – Let it Work

- [ ] **16.e.W** · Position **664/885** · Voraussetzung: `16.d.C`.
**Exakte Commit-Message:** `16.e.W feat(migration): Explizite Sprach- und Verbindlichkeitsmigration aufbauen`

**Umsetzung:** Für alte veränderbare Requirements autorisierte Zuordnung von language, normative_force und Zielstatement verlangen.

**Verhaltensabnahme:** Vollständiges explizites Mapping erzeugt gültige 0.2-Requirements mit erhaltener Identität.

#### 16.e.R – Make it Right

- [ ] **16.e.R** · Position **665/885** · Voraussetzung: `16.e.W`.
**Exakte Commit-Message:** `16.e.R feat(migration): Explizite Sprach- und Verbindlichkeitsmigration vervollständigen`

**Vervollständigung:** Fehlende Zuordnung nicht aus shall, MUSS, Priorität oder Detektor schätzen; fachliche Änderungen widerrufen alte Inhaltsfreigaben.

**Verhaltensabnahme:** Alte immutable Nachweise werden nicht zur Aufnahme neuer Pflichtfelder verändert. Die W-Nachweise bleiben zusätzlich grün.

#### 16.e.C – Make it Clean

- [ ] **16.e.C** · Position **666/885** · Voraussetzung: `16.e.R`.
**Exakte Commit-Message:** `16.e.C refactor(migration): Explizite Sprach- und Verbindlichkeitsmigration bereinigen`

**Bereinigung:** Schemaergänzung und menschlich autorisierte Inhaltsentscheidung separat im Plan halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-f"></a>
### 16.f – Deterministische Relationsidentität

**Anforderungsbezug:** `SR-REQ-0273`, `SR-REQ-0512`–`SR-REQ-0513`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.f.W – Let it Work

- [ ] **16.f.W** · Position **667/885** · Voraussetzung: `16.e.C`.
**Exakte Commit-Message:** `16.f.W feat(migration): Deterministische Relationsidentität aufbauen`

**Umsetzung:** Bestehende 0.1-Relationen exakt nach Anhang Q.3 in derived128-v1-IDs überführen.

**Verhaltensabnahme:** Gleiche Quellbytes, Arrayposition und Projektidentität erzeugen in jeder Sandbox dieselbe REL-ID.

#### 16.f.R – Make it Right

- [ ] **16.f.R** · Position **668/885** · Voraussetzung: `16.f.W`.
**Exakte Commit-Message:** `16.f.R feat(migration): Deterministische Relationsidentität vervollständigen`

**Vervollständigung:** Kollision unterschiedlicher Ableitungsinputs ablehnen; Ausnahme auf diesen Migrationspfad beschränken.

**Verhaltensabnahme:** Original-ID, Namespace, JCS-Bytes und Crockfordkodierung stimmen mit unabhängigen Datenvektoren überein. Die W-Nachweise bleiben zusätzlich grün.

#### 16.f.C – Make it Clean

- [ ] **16.f.C** · Position **669/885** · Voraussetzung: `16.f.R`.
**Exakte Commit-Message:** `16.f.C refactor(migration): Deterministische Relationsidentität bereinigen`

**Bereinigung:** Ableitungshilfe vom normalen random128-v1-Erzeuger trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-g"></a>
### 16.g – Legacy-Manifest und Hashdomänen

**Anforderungsbezug:** `SR-REQ-0639`, `SR-REQ-0641`.
**Verifikationsbezug:** `SR-VER-0042`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.g.W – Let it Work

- [ ] **16.g.W** · Position **670/885** · Voraussetzung: `16.f.C`.
**Exakte Commit-Message:** `16.g.W feat(migration): Legacy-Manifest und Hashdomänen aufbauen`

**Umsetzung:** legacy-manifest.json mit allen Originalhashes, Quellschema, Identitäts-/Relationsprojektionen und Payloadbindungen erzeugen.

**Verhaltensabnahme:** Historische Objekte sind nur über eine intakte Manifestregistrierung regulär lesbar.

#### 16.g.R – Make it Right

- [ ] **16.g.R** · Position **671/885** · Voraussetzung: `16.g.W`.
**Exakte Commit-Message:** `16.g.R feat(migration): Legacy-Manifest und Hashdomänen vervollständigen`

**Vervollständigung:** Projektion nicht als neue Originaldatei akzeptieren; unterschiedliche Originalbytes unter gleicher Identität blockieren.

**Verhaltensabnahme:** Neue Modellwurzel bindet legacy-original-bytes-v1 und Manifest statt eines erfundenen 0.2-Originalhashes. Die W-Nachweise bleiben zusätzlich grün.

#### 16.g.C – Make it Clean

- [ ] **16.g.C** · Position **672/885** · Voraussetzung: `16.g.R`.
**Exakte Commit-Message:** `16.g.C refactor(migration): Legacy-Manifest und Hashdomänen bereinigen`

**Bereinigung:** Manifestvalidierung und Projektionsleser auf genau einen Vertrag reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-h"></a>
### 16.h – Verlustbehandlung und Erweiterungserhalt

**Anforderungsbezug:** `SR-REQ-0268`–`SR-REQ-0269`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.h.W – Let it Work

- [ ] **16.h.W** · Position **673/885** · Voraussetzung: `16.g.C`.
**Exakte Commit-Message:** `16.h.W feat(migration): Verlustbehandlung und Erweiterungserhalt aufbauen`

**Umsetzung:** Unbekannte gültige Extensions, Provenienz, Anhänge und Auditbezüge durch alle Transformationen erhalten.

**Verhaltensabnahme:** Verlustfreier Pfad besitzt identische geschützte Daten und semantisch äquivalente übrige Werte.

#### 16.h.R – Make it Right

- [ ] **16.h.R** · Position **674/885** · Voraussetzung: `16.h.W`.
**Exakte Commit-Message:** `16.h.R feat(migration): Verlustbehandlung und Erweiterungserhalt vervollständigen`

**Vervollständigung:** Jeden möglichen Informationsverlust einzeln benennen und vollständiges accept-loss verlangen.

**Verhaltensabnahme:** Fehlende Einzelzustimmung führt ohne Teilwrite zum Abbruch. Die W-Nachweise bleiben zusätzlich grün.

#### 16.h.C – Make it Clean

- [ ] **16.h.C** · Position **675/885** · Voraussetzung: `16.h.R`.
**Exakte Commit-Message:** `16.h.C refactor(migration): Verlustbehandlung und Erweiterungserhalt bereinigen`

**Bereinigung:** Verlustinventur wiederverwendbar mit Import gestalten, ohne Migrationsspezifika zu verwischen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-i"></a>
### 16.i – Migrationstransaktion und Metadaten

**Anforderungsbezug:** `SR-REQ-0267`, `SR-REQ-0270`.
**Verifikationsbezug:** `SR-VER-0020`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.i.W – Let it Work

- [ ] **16.i.W** · Position **676/885** · Voraussetzung: `16.h.C`.
**Exakte Commit-Message:** `16.i.W feat(migration): Migrationstransaktion und Metadaten aufbauen`

**Umsetzung:** Unterstützte Transformation atomar mit migration-metadata-v1 über den gemeinsamen Writer anwenden.

**Verhaltensabnahme:** Veränderbare Artefakte erhalten genau die vorgeschriebenen Revisionen; neue Begleitdaten Revision 1.

#### 16.i.R – Make it Right

- [ ] **16.i.R** · Position **677/885** · Voraussetzung: `16.i.W`.
**Exakte Commit-Message:** `16.i.R feat(migration): Migrationstransaktion und Metadaten vervollständigen`

**Vervollständigung:** Wiederholung bleibt No-op beziehungsweise gespeicherter Request; nach Abbruch kein regulär ladbarer Mischstand.

**Verhaltensabnahme:** Crashmatrix, Idempotenz und explizite Sicherungsbindung werden gemeinsam geprüft. Die W-Nachweise bleiben zusätzlich grün.

#### 16.i.C – Make it Clean

- [ ] **16.i.C** · Position **678/885** · Voraussetzung: `16.i.R`.
**Exakte Commit-Message:** `16.i.C refactor(migration): Migrationstransaktion und Metadaten bereinigen`

**Bereinigung:** Keine gesonderten Lock-, Journal- oder Publikationsabkürzungen zulassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-j"></a>
### 16.j – Historische Evidence und Baselines

**Anforderungsbezug:** `SR-REQ-0639`–`SR-REQ-0640`, `SR-REQ-0642`, `SR-REQ-0725`.
**Verifikationsbezug:** `SR-VER-0042`, `SR-VER-0049`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.j.W – Let it Work

- [ ] **16.j.W** · Position **679/885** · Voraussetzung: `16.i.C`.
**Exakte Commit-Message:** `16.j.W feat(migration): Historische Evidence und Baselines aufbauen`

**Umsetzung:** Historische Originalnachweise mit ihrem Quellalgorithmus verifizieren und aktuelle Evidence als getrennte neue Prüfung behandeln.

**Verhaltensabnahme:** Alte Baselinehashes und Originalbytes bleiben vor und nach Migration identisch.

#### 16.j.R – Make it Right

- [ ] **16.j.R** · Position **680/885** · Voraussetzung: `16.j.W`.
**Exakte Commit-Message:** `16.j.R feat(migration): Historische Evidence und Baselines vervollständigen`

**Vervollständigung:** Legacy-Evidence für transformiertes Subject bleibt ohne neuen Kontextnachweis stale mit migration_context_unverified.

**Verhaltensabnahme:** Format, Update und Lifecycle lehnen legacy_immutable-Writes ab; Projektion hebt keine Freigabe an. Die W-Nachweise bleiben zusätzlich grün.

#### 16.j.C – Make it Clean

- [ ] **16.j.C** · Position **681/885** · Voraussetzung: `16.j.R`.
**Exakte Commit-Message:** `16.j.C refactor(migration): Historische Evidence und Baselines bereinigen`

**Bereinigung:** Historische Gültigkeit und aktuelle Verifikationsfähigkeit als verschiedene Ergebnisse führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-16-k"></a>
### 16.k – Migrate verify und fortsetzbarer Abschluss

**Anforderungsbezug:** `SR-REQ-0271`, `SR-REQ-0285`, `SR-REQ-0639`–`SR-REQ-0642`.
**Verifikationsbezug:** `SR-VER-0020`, `SR-VER-0021`, `SR-VER-0042`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 16.k.W – Let it Work

- [ ] **16.k.W** · Position **682/885** · Voraussetzung: `16.j.C`.
**Exakte Commit-Message:** `16.k.W feat(migration): Migrate verify und fortsetzbarer Abschluss aufbauen`

**Umsetzung:** Quellbundle, Bericht, Zielwurzel, Referenzen, Legacy-Bytes und deklarierte Invarianten lesend verifizieren.

**Verhaltensabnahme:** Vollständiger Nachweis deckt jede Quelle und jedes geplante Zielobjekt ab.

#### 16.k.R – Make it Right

- [ ] **16.k.R** · Position **683/885** · Voraussetzung: `16.k.W`.
**Exakte Commit-Message:** `16.k.R feat(migration): Migrate verify und fortsetzbarer Abschluss vervollständigen`

**Vervollständigung:** Planung/Prüfung über Work fortsetzen, Abschluss aber als eine Transaktion veröffentlichen.

**Verhaltensabnahme:** Wiederholter Lauf, Sandboxwechsel und Unterbrechung liefern denselben Zielstand oder einen echten Blocker. Die W-Nachweise bleiben zusätzlich grün.

#### 16.k.C – Make it Clean

- [ ] **16.k.C** · Position **684/885** · Voraussetzung: `16.k.R`.
**Exakte Commit-Message:** `16.k.C refactor(migration): Migrate verify und fortsetzbarer Abschluss bereinigen`

**Bereinigung:** Migrationsnachweise über gemeinsame Inventur-/Workresultate erzeugen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 16 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m17"></a>
## Meilenstein 17 – Semantischer Dreiwege-Merge

**Ziel:** Vollständige Projektstände identitätsbasiert zusammenführen, echte Konflikte explizit lösen und nachvollziehbar veröffentlichen.

**Vorgesehener Zuschnitt:** `src/specroad/merge/, src/specroad/snapshots/, src/specroad/changes/`. **Fachgrundlage:** §§ 10.12, 12.26; Anhänge K.3, Q.

**Abschlussgate:** Alle vier Quelltypen funktionieren ohne Git-Checkout; Merge-Metadaten und unveränderbare Originalnachweise bleiben korrekt, unresolved conflicts verhindern Apply. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-17-a"></a>
### 17.a – Drei unveränderbar gebundene Quellen

**Anforderungsbezug:** `SR-REQ-0361`–`SR-REQ-0364`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.a.W – Let it Work

- [ ] **17.a.W** · Position **685/885** · Voraussetzung: `16.k.C`.
**Exakte Commit-Message:** `17.a.W feat(merge): Drei unveränderbar gebundene Quellen aufbauen`

**Umsetzung:** Base, Ours und Theirs aus lokalem Root, Git-Ref, Baseline oder verifiziertem Vollbundle laden und vollständig binden.

**Verhaltensabnahme:** Gleiches Projekt und unterstützte gleiche Schemaversion ergeben drei konsistente Snapshots.

#### 17.a.R – Make it Right

- [ ] **17.a.R** · Position **686/885** · Voraussetzung: `17.a.W`.
**Exakte Commit-Message:** `17.a.R feat(merge): Drei unveränderbar gebundene Quellen vervollständigen`

**Vervollständigung:** Partials, unterschiedliche project_id und Versionsmischung ablehnen; erforderliche Migration nicht heimlich ausführen.

**Verhaltensabnahme:** Lesen von Gitquellen ändert weder Branch, Index noch Arbeitsbaum. Die W-Nachweise bleiben zusätzlich grün.

#### 17.a.C – Make it Clean

- [ ] **17.a.C** · Position **687/885** · Voraussetzung: `17.a.R`.
**Exakte Commit-Message:** `17.a.C refactor(merge): Drei unveränderbar gebundene Quellen bereinigen`

**Bereinigung:** Die vervollständigte Snapshotregistry aus M8/M10/M15 wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-b"></a>
### 17.b – Ressourceninventur und Mergeplan

**Anforderungsbezug:** `SR-REQ-0361`, `SR-REQ-0364`, `SR-REQ-0375`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.b.W – Let it Work

- [ ] **17.b.W** · Position **688/885** · Voraussetzung: `17.a.C`.
**Exakte Commit-Message:** `17.b.W feat(merge): Ressourceninventur und Mergeplan aufbauen`

**Umsetzung:** Artefakte, Relationen, Regeln, Profile, Mappings, Konfigurationen und Anhänge in einen versionierten vollständigen Plan aufnehmen.

**Verhaltensabnahme:** Jede Ressource enthält ihre drei Bindungen und eindeutige Zielklassifikation.

#### 17.b.R – Make it Right

- [ ] **17.b.R** · Position **689/885** · Voraussetzung: `17.b.W`.
**Exakte Commit-Message:** `17.b.R feat(merge): Ressourceninventur und Mergeplan vervollständigen`

**Vervollständigung:** Fehlende Quellressource von bewusstem Löschen unterscheiden; kein unsichtbarer normativer Nebenbereich.

**Verhaltensabnahme:** Inventurvergleich weist vollständigen Scope und deterministischen Plan nach. Die W-Nachweise bleiben zusätzlich grün.

#### 17.b.C – Make it Clean

- [ ] **17.b.C** · Position **690/885** · Voraussetzung: `17.b.R`.
**Exakte Commit-Message:** `17.b.C refactor(merge): Ressourceninventur und Mergeplan bereinigen`

**Bereinigung:** Gemeinsame Ressourcenmodelle statt einer auf Artefakte verkürzten Parallelstruktur verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-c"></a>
### 17.c – Rekursiver Feldmerge und Skalarmatrix

**Anforderungsbezug:** `SR-REQ-0365`–`SR-REQ-0366`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.c.W – Let it Work

- [ ] **17.c.W** · Position **691/885** · Voraussetzung: `17.b.C`.
**Exakte Commit-Message:** `17.c.W feat(merge): Rekursiver Feldmerge und Skalarmatrix aufbauen`

**Umsetzung:** Unabhängige Änderungen verschiedener Objektfelder sowie identische Zielwerte automatisch vereinen.

**Verhaltensabnahme:** disjunkte Änderungen bleiben beide im Ergebnis, identische Änderungen erzeugen keinen Konflikt.

#### 17.c.R – Make it Right

- [ ] **17.c.R** · Position **692/885** · Voraussetzung: `17.c.W`.
**Exakte Commit-Message:** `17.c.R feat(merge): Rekursiver Feldmerge und Skalarmatrix vervollständigen`

**Vervollständigung:** Abweichende konkurrierende Skalaränderungen und inkompatible Typwechsel als Konflikt klassifizieren.

**Verhaltensabnahme:** Dreiwegematrix für missing, null, Wertänderung und Objektstruktur verwendet echte Fachwerte. Die W-Nachweise bleiben zusätzlich grün.

#### 17.c.C – Make it Clean

- [ ] **17.c.C** · Position **693/885** · Voraussetzung: `17.c.R`.
**Exakte Commit-Message:** `17.c.C refactor(merge): Rekursiver Feldmerge und Skalarmatrix bereinigen`

**Bereinigung:** Rekursion und Konfliktentstehung als reine Funktionen gestalten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-d"></a>
### 17.d – Mengen, geordnete Folgen und Anhänge

**Anforderungsbezug:** `SR-REQ-0365`, `SR-REQ-0367`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.d.W – Let it Work

- [ ] **17.d.W** · Position **694/885** · Voraussetzung: `17.c.C`.
**Exakte Commit-Message:** `17.d.W feat(merge): Mengen, geordnete Folgen und Anhänge aufbauen`

**Umsetzung:** Mengen nach schemafestem Schlüssel und Anhänge nach Pfad/Bytehash zusammenführen.

**Verhaltensabnahme:** Unabhängige Mengenergänzungen bleiben erhalten; identische Anhänge werden unverändert übernommen.

#### 17.d.R – Make it Right

- [ ] **17.d.R** · Position **695/885** · Voraussetzung: `17.d.W`.
**Exakte Commit-Message:** `17.d.R feat(merge): Mengen, geordnete Folgen und Anhänge vervollständigen`

**Vervollständigung:** Konkurrierende geordnete Folgen ohne stabile Elementidentität und remove-versus-edit nicht willkürlich sortieren oder gewinnen lassen.

**Verhaltensabnahme:** Fallmatrix erhält absichtliche Reihenfolge und weist echte Binärkonflikte aus. Die W-Nachweise bleiben zusätzlich grün.

#### 17.d.C – Make it Clean

- [ ] **17.d.C** · Position **696/885** · Voraussetzung: `17.d.R`.
**Exakte Commit-Message:** `17.d.C refactor(merge): Mengen, geordnete Folgen und Anhänge bereinigen`

**Bereinigung:** Feldsemantik aus dem Schema beziehen statt freie Arrayheuristiken einzubauen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-e"></a>
### 17.e – Relationsmerge und Identitätskollisionen

**Anforderungsbezug:** `SR-REQ-0368`, `SR-REQ-0370`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.e.W – Let it Work

- [ ] **17.e.W** · Position **697/885** · Voraussetzung: `17.d.C`.
**Exakte Commit-Message:** `17.e.W feat(merge): Relationsmerge und Identitätskollisionen aufbauen`

**Umsetzung:** Relation-ID als Vergleichsschlüssel verwenden und gemeinsame Identitätshistorie prüfen.

**Verhaltensabnahme:** Unabhängig neu angelegte Relationen werden beide übernommen.

#### 17.e.R – Make it Right

- [ ] **17.e.R** · Position **698/885** · Voraussetzung: `17.e.W`.
**Exakte Commit-Message:** `17.e.R feat(merge): Relationsmerge und Identitätskollisionen vervollständigen`

**Vervollständigung:** Ändern gegen Entfernen derselben Relation und gleiche ID bei anderer Provenienz oder id_scheme blockieren.

**Verhaltensabnahme:** Kollision wird nicht durch Zufallsumbenennung scheinbar repariert. Die W-Nachweise bleiben zusätzlich grün.

#### 17.e.C – Make it Clean

- [ ] **17.e.C** · Position **699/885** · Voraussetzung: `17.e.R`.
**Exakte Commit-Message:** `17.e.C refactor(merge): Relationsmerge und Identitätskollisionen bereinigen`

**Bereinigung:** Identitätsprüfung für Artefakte, Relationen und normative Ressourcen zusammenführen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-f"></a>
### 17.f – Lifecycle und unveränderbare Geschichte

**Anforderungsbezug:** `SR-REQ-0369`, `SR-REQ-0637`–`SR-REQ-0638`.
**Verifikationsbezug:** `SR-VER-0026`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.f.W – Let it Work

- [ ] **17.f.W** · Position **700/885** · Voraussetzung: `17.e.C`.
**Exakte Commit-Message:** `17.f.W feat(merge): Lifecycle und unveränderbare Geschichte aufbauen`

**Umsetzung:** Lifecyclekonflikte, unterschiedliche Supersessionziele und immutable Originalnachweise speziell behandeln.

**Verhaltensabnahme:** Identisches aufgezeichnetes Original darf bytegetreu übernommen werden.

#### 17.f.R – Make it Right

- [ ] **17.f.R** · Position **701/885** · Voraussetzung: `17.f.W`.
**Exakte Commit-Message:** `17.f.R feat(merge): Lifecycle und unveränderbare Geschichte vervollständigen`

**Vervollständigung:** Retirement gegen Fachänderung und abweichende Evidence-/Baseline-/Review-/abgeschlossene Proposalbytes derselben ID bleiben Konflikte.

**Verhaltensabnahme:** Keine automatische Kombination oder Freigabeübernahme für geschützte Geschichte. Die W-Nachweise bleiben zusätzlich grün.

#### 17.f.C – Make it Clean

- [ ] **17.f.C** · Position **702/885** · Voraussetzung: `17.f.R`.
**Exakte Commit-Message:** `17.f.C refactor(merge): Lifecycle und unveränderbare Geschichte bereinigen`

**Bereinigung:** Schutzregeln mit Migration, Restore und Writer teilen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-g"></a>
### 17.g – Konfliktobjekte und maschinenlesbarer Zugriff

**Anforderungsbezug:** `SR-REQ-0371`, `SR-REQ-0375`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.g.W – Let it Work

- [ ] **17.g.W** · Position **703/885** · Voraussetzung: `17.f.C`.
**Exakte Commit-Message:** `17.g.W feat(merge): Konfliktobjekte und maschinenlesbarer Zugriff aufbauen`

**Umsetzung:** Stabile Konfliktkennungen mit Pointer, drei Werten, Klasse, Impact und zulässiger Auflösung bereitstellen.

**Verhaltensabnahme:** Jeder offene Konflikt ist als vollständiges Datenobjekt adressierbar.

#### 17.g.R – Make it Right

- [ ] **17.g.R** · Position **704/885** · Voraussetzung: `17.g.W`.
**Exakte Commit-Message:** `17.g.R feat(merge): Konfliktobjekte und maschinenlesbarer Zugriff vervollständigen`

**Vervollständigung:** Fehlender Wert bleibt von JSON-null unterscheidbar; Konfliktliste verliert keine Zweige.

**Verhaltensabnahme:** JSON-Datenvertrag und Fachimpact werden geprüft, nicht Konflikttabellen oder Pretty-Texte. Die W-Nachweise bleiben zusätzlich grün.

#### 17.g.C – Make it Clean

- [ ] **17.g.C** · Position **705/885** · Voraussetzung: `17.g.R`.
**Exakte Commit-Message:** `17.g.C refactor(merge): Konfliktobjekte und maschinenlesbarer Zugriff bereinigen`

**Bereinigung:** Konfliktmodell von der später frei gestaltbaren Darstellung abkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-h"></a>
### 17.h – Explizite auditierte Konfliktauflösung

**Anforderungsbezug:** `SR-REQ-0372`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.h.W – Let it Work

- [ ] **17.h.W** · Position **706/885** · Voraussetzung: `17.g.C`.
**Exakte Commit-Message:** `17.h.W feat(merge): Explizite auditierte Konfliktauflösung aufbauen`

**Umsetzung:** take ours/theirs/base und expliziten gültigen JSON-Wert an genau einen gebundenen Konflikt anwenden.

**Verhaltensabnahme:** Auflösung ändert nur den gewählten Konflikt und daraus abgeleitete Zielwerte.

#### 17.h.R – Make it Right

- [ ] **17.h.R** · Position **707/885** · Voraussetzung: `17.h.W`.
**Exakte Commit-Message:** `17.h.R feat(merge): Explizite auditierte Konfliktauflösung vervollständigen`

**Vervollständigung:** Unbekannter Konflikt, ungültiger Wert und nachträglich veränderte Basis verhindern Übernahme.

**Verhaltensabnahme:** Restplan bleibt fachlich unverändert; Akteur und Auflösungsentscheidung sind nachvollziehbar gebunden. Die W-Nachweise bleiben zusätzlich grün.

#### 17.h.C – Make it Clean

- [ ] **17.h.C** · Position **708/885** · Voraussetzung: `17.h.R`.
**Exakte Commit-Message:** `17.h.C refactor(merge): Explizite auditierte Konfliktauflösung bereinigen`

**Bereinigung:** Auflösungen als deklarative Planänderungen ohne direkte Projektwrites behandeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-i"></a>
### 17.i – Exakte Merge-Metadaten

**Anforderungsbezug:** `SR-REQ-0403`, `SR-REQ-0540`–`SR-REQ-0542`, `SR-REQ-0637`–`SR-REQ-0638`.
**Verifikationsbezug:** `SR-VER-0023`, `SR-VER-0026`, `SR-VER-0028`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.i.W – Let it Work

- [ ] **17.i.W** · Position **709/885** · Voraussetzung: `17.h.C`.
**Exakte Commit-Message:** `17.i.W feat(merge): Exakte Merge-Metadaten aufbauen`

**Umsetzung:** unchanged_ours, adopt_existing, combined und conflict exakt nach merge-metadata-v1 behandeln.

**Verhaltensabnahme:** Kombinieren von Revision 3 und 7 ergibt 8; unveränderte Übernahme von Theirs bleibt 7.

#### 17.i.R – Make it Right

- [ ] **17.i.R** · Position **710/885** · Voraussetzung: `17.i.W`.
**Exakte Commit-Message:** `17.i.R feat(merge): Exakte Merge-Metadaten vervollständigen`

**Vervollständigung:** Niedrigere historische Revision nicht still übernehmen; Ursprungsmetadaten und Zeitmaxima korrekt binden.

**Verhaltensabnahme:** Planner und Writer berechnen unabhängig dieselbe Zielwurzel und identische Metadaten. Die W-Nachweise bleiben zusätzlich grün.

#### 17.i.C – Make it Clean

- [ ] **17.i.C** · Position **711/885** · Voraussetzung: `17.i.R`.
**Exakte Commit-Message:** `17.i.C refactor(merge): Exakte Merge-Metadaten bereinigen`

**Bereinigung:** Policy ausschließlich im zentralen autorisierten Metadatenmechanismus implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-j"></a>
### 17.j – Zielvalidierung und semantische Konflikte

**Anforderungsbezug:** `SR-REQ-0365`, `SR-REQ-0373`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.j.W – Let it Work

- [ ] **17.j.W** · Position **712/885** · Voraussetzung: `17.i.C`.
**Exakte Commit-Message:** `17.j.W feat(merge): Zielvalidierung und semantische Konflikte aufbauen`

**Umsetzung:** Vollständigen zusammengeführten Zielstand einschließlich Profilen, Scopes und Referenzen vor Apply validieren.

**Verhaltensabnahme:** Ein syntaktisch konfliktfreier und fachlich gültiger Merge ist anwendbar.

#### 17.j.R – Make it Right

- [ ] **17.j.R** · Position **713/885** · Voraussetzung: `17.j.W`.
**Exakte Commit-Message:** `17.j.R feat(merge): Zielvalidierung und semantische Konflikte vervollständigen`

**Vervollständigung:** Erst durch Kombination entstandene Zyklus-, Policy- oder Integritätsverletzung verhindert Veröffentlichung.

**Verhaltensabnahme:** Unaufgelöster oder semantisch ungültiger Plan führt zu keinem Teilwrite. Die W-Nachweise bleiben zusätzlich grün.

#### 17.j.C – Make it Clean

- [ ] **17.j.C** · Position **714/885** · Voraussetzung: `17.j.R`.
**Exakte Commit-Message:** `17.j.C refactor(merge): Zielvalidierung und semantische Konflikte bereinigen`

**Bereinigung:** Normale Validierungsengine auf virtuellen Zielsnapshot anwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-k"></a>
### 17.k – Atomarer Apply und aktuelle Nachweisbindung

**Anforderungsbezug:** `SR-REQ-0373`–`SR-REQ-0374`.
**Verifikationsbezug:** `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.k.W – Let it Work

- [ ] **17.k.W** · Position **715/885** · Voraussetzung: `17.j.C`.
**Exakte Commit-Message:** `17.k.W feat(merge): Atomarer Apply und aktuelle Nachweisbindung aufbauen`

**Umsetzung:** Final aufgelösten Merge nur auf passende aktuelle Oursbasis transaktional publizieren und Abschlussbericht binden.

**Verhaltensabnahme:** Geänderte Kontexte aktualisieren die berechnete Freshness von Relationsreviews, Evidence und Codebezügen.

#### 17.k.R – Make it Right

- [ ] **17.k.R** · Position **716/885** · Voraussetzung: `17.k.W`.
**Exakte Commit-Message:** `17.k.R feat(merge): Atomarer Apply und aktuelle Nachweisbindung vervollständigen`

**Vervollständigung:** Basiswechsel während Planung/Lockphase und manipulierte Auflösungsdaten führen zu Konflikt statt blindem Apply.

**Verhaltensabnahme:** Crash-/Idempotenzfälle erhalten Originale und niemals künstlich aktuelle Freigaben. Die W-Nachweise bleiben zusätzlich grün.

#### 17.k.C – Make it Clean

- [ ] **17.k.C** · Position **717/885** · Voraussetzung: `17.k.R`.
**Exakte Commit-Message:** `17.k.C refactor(merge): Atomarer Apply und aktuelle Nachweisbindung bereinigen`

**Bereinigung:** Merge als spezialisierten Planproduzenten auf dem allgemeinen Writer halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-17-l"></a>
### 17.l – Fortsetzung und Quelltypenparität

**Anforderungsbezug:** `SR-REQ-0285`, `SR-REQ-0362`, `SR-REQ-0375`.
**Verifikationsbezug:** `SR-VER-0021`, `SR-VER-0026`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 17.l.W – Let it Work

- [ ] **17.l.W** · Position **718/885** · Voraussetzung: `17.k.C`.
**Exakte Commit-Message:** `17.l.W feat(merge): Fortsetzung und Quelltypenparität aufbauen`

**Umsetzung:** Große Inventur, Vergleich und Prüfung in vollständigen Workumfang integrieren.

**Verhaltensabnahme:** Lokale, Git-, Baseline- und Bundlequellen identischer Daten führen zum gleichen fachlichen Mergeergebnis.

#### 17.l.R – Make it Right

- [ ] **17.l.R** · Position **719/885** · Voraussetzung: `17.l.W`.
**Exakte Commit-Message:** `17.l.R feat(merge): Fortsetzung und Quelltypenparität vervollständigen`

**Vervollständigung:** Nach Resume müssen dieselben Quellhashes, Auflösungen und Engineverträge gelten.

**Verhaltensabnahme:** Monolithischer Lauf und alle fortgesetzten Teilmengen liefern dieselben Konflikte und Zielbytes. Die W-Nachweise bleiben zusätzlich grün.

#### 17.l.C – Make it Clean

- [ ] **17.l.C** · Position **720/885** · Voraussetzung: `17.l.R`.
**Exakte Commit-Message:** `17.l.C refactor(merge): Fortsetzung und Quelltypenparität bereinigen`

**Bereinigung:** Gemeinsame Testfallmatrix über Quellenadapter und Workmodi parametrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 17 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m18"></a>
## Meilenstein 18 – Proposals und kontrollierte KI-Bearbeitung

**Ziel:** Vollständig gebundene Änderungsvorschläge sicher prüfen, menschlich freigeben und atomar anwenden; KI erhält keine implizite Schreib- oder Freigabeberechtigung.

**Vorgesehener Zuschnitt:** `src/specroad/proposals/, src/specroad/agents/, src/specroad/cli/`. **Fachgrundlage:** §§ 10.3, 11.10, 12.11, 12.32; Anhang R.

**Abschlussgate:** Inhaltsbindung bleibt trotz Kontrollrevision stabil; jede Inhaltsänderung entwertet ältere Freigaben. Check führt keinen Projektcode aus, Resume ersetzt niemals echte menschliche Reviewakteure. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-18-a"></a>
### 18.a – Proposalobjekt und Provenienz

**Anforderungsbezug:** `SR-REQ-0154`–`SR-REQ-0157`, `SR-REQ-0162`–`SR-REQ-0163`.
**Verifikationsbezug:** `SR-VER-0012`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.a.W – Let it Work

- [ ] **18.a.W** · Position **721/885** · Voraussetzung: `17.l.C`.
**Exakte Commit-Message:** `18.a.W feat(proposal): Proposalobjekt und Provenienz aufbauen`

**Umsetzung:** Proposal mit ID, Akteur, vollständigem Change Plan und nachvollziehbarer Änderungserläuterung erzeugen.

**Verhaltensabnahme:** Jede Änderung besitzt Ziele, Rationale und die geforderten Herkunfts-/Annahmenfelder.

#### 18.a.R – Make it Right

- [ ] **18.a.R** · Position **722/885** · Voraussetzung: `18.a.W`.
**Exakte Commit-Message:** `18.a.R feat(proposal): Proposalobjekt und Provenienz vervollständigen`

**Vervollständigung:** KI-Provenienz bindet Provider, Modell, Version, Template und Runner beziehungsweise unknown mit Grund.

**Verhaltensabnahme:** Fehlende Pflichtprovenienz wird nicht durch erfundene Angaben ergänzt; Proposal bleibt reine Datenstruktur. Die W-Nachweise bleiben zusätzlich grün.

#### 18.a.C – Make it Clean

- [ ] **18.a.C** · Position **723/885** · Voraussetzung: `18.a.R`.
**Exakte Commit-Message:** `18.a.C refactor(proposal): Proposalobjekt und Provenienz bereinigen`

**Bereinigung:** Proposalinhalt und betriebliche Steuerinformationen als getrennte Modelle führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-b"></a>
### 18.b – Feste Proposalbasis und Kontrollausschluss

**Anforderungsbezug:** `SR-REQ-0158`, `SR-REQ-0426`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.b.W – Let it Work

- [ ] **18.b.W** · Position **724/885** · Voraussetzung: `18.a.C`.
**Exakte Commit-Message:** `18.b.W feat(proposal): Feste Proposalbasis und Kontrollausschluss aufbauen`

**Umsetzung:** Basis ausschließlich aus specification/closed/unconfigured mit kanonischer Wurzel berechnen.

**Verhaltensabnahme:** Proposalbasis enthält genau den zulässigen Spezifikationsumfang ohne Selbstbezug.

#### 18.b.R – Make it Right

- [ ] **18.b.R** · Position **725/885** · Voraussetzung: `18.b.W`.
**Exakte Commit-Message:** `18.b.R feat(proposal): Feste Proposalbasis und Kontrollausschluss vervollständigen`

**Vervollständigung:** Konfiguration, Partialscope, Baseline/Proposal-Kontrollabhängigkeit und unzulässige Overrides abweisen.

**Verhaltensabnahme:** CLI-Fehler Code 2, ungültige gespeicherte Daten Code 3 und definierte SRV1403-Diagnose bleiben unterscheidbar. Die W-Nachweise bleiben zusätzlich grün.

#### 18.b.C – Make it Clean

- [ ] **18.b.C** · Position **726/885** · Voraussetzung: `18.b.R`.
**Exakte Commit-Message:** `18.b.C refactor(proposal): Feste Proposalbasis und Kontrollausschluss bereinigen`

**Bereinigung:** Basisdescriptor als feste spezialisierte Nutzung des Scopedienstes implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-c"></a>
### 18.c – Geordnete Change-IDs und Positionsoperationen

**Anforderungsbezug:** `SR-REQ-0159`, `SR-REQ-0427`–`SR-REQ-0428`, `SR-REQ-0649`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0030`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.c.W – Let it Work

- [ ] **18.c.W** · Position **727/885** · Voraussetzung: `18.b.C`.
**Exakte Commit-Message:** `18.c.W feat(proposal): Geordnete Change-IDs und Positionsoperationen aufbauen`

**Umsetzung:** Stabile CHG-IDs und exakt geordnete append-/insert-/move-Operationen des vollständigen Plans unterstützen.

**Verhaltensabnahme:** Änderungen sind einzeln referenzierbar und erzeugen die angegebene Zielreihenfolge.

#### 18.c.R – Make it Right

- [ ] **18.c.R** · Position **728/885** · Voraussetzung: `18.c.W`.
**Exakte Commit-Message:** `18.c.R feat(proposal): Geordnete Change-IDs und Positionsoperationen vervollständigen`

**Vervollständigung:** Indexgrenzen, gleiche Position und Verschiebung vor/nach Entnahme exakt nach Kapitel 11.10 behandeln.

**Verhaltensabnahme:** Positionsmatrix und Wiederholung verlieren oder duplizieren keinen Change. Die W-Nachweise bleiben zusätzlich grün.

#### 18.c.C – Make it Clean

- [ ] **18.c.C** · Position **729/885** · Voraussetzung: `18.c.R`.
**Exakte Commit-Message:** `18.c.C refactor(proposal): Geordnete Change-IDs und Positionsoperationen bereinigen`

**Bereinigung:** Änderungsidentität von Arrayposition und menschenlesbarer Nummerierung trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-d"></a>
### 18.d – Inhaltsrevision und Hashprojektion

**Anforderungsbezug:** `SR-REQ-0643`–`SR-REQ-0644`.
**Verifikationsbezug:** `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.d.W – Let it Work

- [ ] **18.d.W** · Position **730/885** · Voraussetzung: `18.c.C`.
**Exakte Commit-Message:** `18.d.W feat(proposal): Inhaltsrevision und Hashprojektion aufbauen`

**Umsetzung:** content_revision und content_sha256 unabhängig von physischer Artefaktrevision führen.

**Verhaltensabnahme:** Inhaltshash bindet alle fachlichen Felder, Basis und vollständigen Plan, aber keine ausdrücklich ausgeschlossenen Kontrollfelder.

#### 18.d.R – Make it Right

- [ ] **18.d.R** · Position **731/885** · Voraussetzung: `18.d.W`.
**Exakte Commit-Message:** `18.d.R feat(proposal): Inhaltsrevision und Hashprojektion vervollständigen`

**Vervollständigung:** Top-level-Ausschlussliste exakt implementieren; gleichnamige fachliche Unterfelder und Extensions nicht versehentlich ausblenden.

**Verhaltensabnahme:** Reiner Reviewkontrollwrite lässt Inhaltshash/-revision unverändert, echte Änderung verändert beides. Die W-Nachweise bleiben zusätzlich grün.

#### 18.d.C – Make it Clean

- [ ] **18.d.C** · Position **732/885** · Voraussetzung: `18.d.R`.
**Exakte Commit-Message:** `18.d.C refactor(proposal): Inhaltsrevision und Hashprojektion bereinigen`

**Bereinigung:** Eine feste Hashprojektionsfunktion für Erstellen, Prüfen und Freigeben verwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-e"></a>
### 18.e – Proposal-Authoring und Endzustandsgrenzen

**Anforderungsbezug:** `SR-REQ-0160`–`SR-REQ-0161`, `SR-REQ-0426`, `SR-REQ-0430`–`SR-REQ-0431`, `SR-REQ-0648`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0030`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.e.W – Let it Work

- [ ] **18.e.W** · Position **733/885** · Voraussetzung: `18.d.C`.
**Exakte Commit-Message:** `18.e.W feat(proposal): Proposal-Authoring und Endzustandsgrenzen aufbauen`

**Umsetzung:** Fachliche Änderungen in erlaubten offenen Zuständen ausführen und dabei auf draft zurücksetzen.

**Verhaltensabnahme:** Inhaltsergänzung erhöht Inhalts- und physische Revision und erhält historische Reviews als nun unwirksam.

#### 18.e.R – Make it Right

- [ ] **18.e.R** · Position **734/885** · Voraussetzung: `18.e.W`.
**Exakte Commit-Message:** `18.e.R feat(proposal): Proposal-Authoring und Endzustandsgrenzen vervollständigen`

**Vervollständigung:** No-op stempelt keine Revision; rejected, stale und applied dürfen nicht frei weitereditiert werden.

**Verhaltensabnahme:** Neues fachliches Vorhaben nach Endzustand verlangt neue Proposal-ID. Die W-Nachweise bleiben zusätzlich grün.

#### 18.e.C – Make it Clean

- [ ] **18.e.C** · Position **735/885** · Voraussetzung: `18.e.R`.
**Exakte Commit-Message:** `18.e.C refactor(proposal): Proposal-Authoring und Endzustandsgrenzen bereinigen`

**Bereinigung:** Lifecycle- und Revisionsregeln über den gemeinsamen Plan-/Writervertrag laufen lassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-f"></a>
### 18.f – Strukturvalidierung ohne Kontrollwrite

**Anforderungsbezug:** `SR-REQ-0164`–`SR-REQ-0165`, `SR-REQ-0645`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.f.W – Let it Work

- [ ] **18.f.W** · Position **736/885** · Voraussetzung: `18.e.C`.
**Exakte Commit-Message:** `18.f.W feat(proposal): Strukturvalidierung ohne Kontrollwrite aufbauen`

**Umsetzung:** proposal validate als read_only-Prüfung ausschließlich von Proposal-Schema, internen Referenzen und Anwendbarkeit gegen die deklarierte Basis anbieten.

**Verhaltensabnahme:** Validiertes Proposal wird nicht allein durch Prüfen persistiert auf validated gesetzt.

#### 18.f.R – Make it Right

- [ ] **18.f.R** · Position **737/885** · Voraussetzung: `18.f.W`.
**Exakte Commit-Message:** `18.f.R feat(proposal): Strukturvalidierung ohne Kontrollwrite vervollständigen`

**Vervollständigung:** Tatsächlich festgestellter observed_status bleibt Resultat statt normativer Nebenmutation.

**Verhaltensabnahme:** Vollständige Projektinventur vor/nach gültigem und ungültigem Check bleibt gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 18.f.C – Make it Clean

- [ ] **18.f.C** · Position **738/885** · Voraussetzung: `18.f.R`.
**Exakte Commit-Message:** `18.f.C refactor(proposal): Strukturvalidierung ohne Kontrollwrite bereinigen`

**Bereinigung:** Validierungsresultat und zustandsändernde Kommandos strikt entkoppeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-g"></a>
### 18.g – Isolierter Proposal-Check

**Anforderungsbezug:** `SR-REQ-0166`–`SR-REQ-0170`, `SR-REQ-0178`, `SR-REQ-0195`, `SR-REQ-0645`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0014`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.g.W – Let it Work

- [ ] **18.g.W** · Position **739/885** · Voraussetzung: `18.f.C`.
**Exakte Commit-Message:** `18.g.W feat(proposal): Isolierter Proposal-Check aufbauen`

**Umsetzung:** Virtuellen Zielstand in kontrolliertem temporärem Arbeitsbereich mit internen Validator-/Query-/Render-/Diff-/Impactdiensten prüfen.

**Verhaltensabnahme:** Gegenüber der Basis bleiben Originaldateien unverändert; Fachresultate beziehen sich auf das geplante Ziel.

#### 18.g.R – Make it Right

- [ ] **18.g.R** · Position **740/885** · Voraussetzung: `18.g.W`.
**Exakte Commit-Message:** `18.g.R feat(proposal): Isolierter Proposal-Check vervollständigen`

**Vervollständigung:** Keine Tests, Builds, Shellbefehle, Plugins oder Netzaufrufe aus Projektinhalten starten; temporäre Daten standardmäßig entfernen.

**Verhaltensabnahme:** Bösartige Text-/Dateiinhalte erzeugen keine Ausführungsrechte; Cleanup und explizites Debugretain werden über Dateizustand geprüft. Die W-Nachweise bleiben zusätzlich grün.

#### 18.g.C – Make it Clean

- [ ] **18.g.C** · Position **741/885** · Voraussetzung: `18.g.R`.
**Exakte Commit-Message:** `18.g.C refactor(proposal): Isolierter Proposal-Check bereinigen`

**Bereinigung:** Interne Prüfdienste direkt aufrufen statt unkontrollierte CLI-/Shellketten aufzubauen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-h"></a>
### 18.h – Review start als atomare Kontrollfolge

**Anforderungsbezug:** `SR-REQ-0426`, `SR-REQ-0431`, `SR-REQ-0646`.
**Verifikationsbezug:** `SR-VER-0030`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.h.W – Let it Work

- [ ] **18.h.W** · Position **742/885** · Voraussetzung: `18.g.C`.
**Exakte Commit-Message:** `18.h.W feat(proposal): Review start als atomare Kontrollfolge aufbauen`

**Umsetzung:** Nach frischen vollständigen Prüfungen draft bis validated, checked und in_review atomar mit gebundener control_history publizieren.

**Verhaltensabnahme:** Persistierter Abschluss ist in_review mit zusammenpassender Inhalts-/Basis-/Planbindung.

#### 18.h.R – Make it Right

- [ ] **18.h.R** · Position **743/885** · Voraussetzung: `18.h.W`.
**Exakte Commit-Message:** `18.h.R feat(proposal): Review start als atomare Kontrollfolge vervollständigen`

**Vervollständigung:** Fehlgeschlagene Teilprüfung darf keinen Zwischenfreigabestatus hinterlassen.

**Verhaltensabnahme:** Ein Kontrollwrite erhöht nur physische Revision; Hash und Inhaltsrevision bleiben stabil. Die W-Nachweise bleiben zusätzlich grün.

#### 18.h.C – Make it Clean

- [ ] **18.h.C** · Position **744/885** · Voraussetzung: `18.h.R`.
**Exakte Commit-Message:** `18.h.C refactor(proposal): Review start als atomare Kontrollfolge bereinigen`

**Bereinigung:** Prüfen, Entscheiden und atomar Veröffentlichen als nachvollziehbare Stufen trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-i"></a>
### 18.i – Menschlicher Review und Freigabequorum

**Anforderungsbezug:** `SR-REQ-0171`–`SR-REQ-0173`, `SR-REQ-0643`, `SR-REQ-0674`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0043`, `SR-VER-0044`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.i.W – Let it Work

- [ ] **18.i.W** · Position **745/885** · Voraussetzung: `18.h.C`.
**Exakte Commit-Message:** `18.i.W feat(proposal): Menschlicher Review und Freigabequorum aufbauen`

**Umsetzung:** Echte menschliche Entscheidungen an Proposal-ID, Inhaltsrevision/-hash, Basiswurzel und Planhash binden.

**Verhaltensabnahme:** Erforderliche unterschiedliche menschliche actor_ids ergeben approved; unzureichende Zahl bleibt in_review.

#### 18.i.R – Make it Right

- [ ] **18.i.R** · Position **746/885** · Voraussetzung: `18.i.W`.
**Exakte Commit-Message:** `18.i.R feat(proposal): Menschlicher Review und Freigabequorum vervollständigen`

**Vervollständigung:** Doppelte Entscheidung desselben Menschen und actor_type ai erfüllen keine zusätzliche menschliche Freigabe.

**Verhaltensabnahme:** Inhaltliche Beurteilung von normative_force und statement wird nicht durch Detektor oder grünen Automatismus ersetzt. Die W-Nachweise bleiben zusätzlich grün.

#### 18.i.C – Make it Clean

- [ ] **18.i.C** · Position **747/885** · Voraussetzung: `18.i.R`.
**Exakte Commit-Message:** `18.i.C refactor(proposal): Menschlicher Review und Freigabequorum bereinigen`

**Bereinigung:** Quorumprüfung als zentrale Policy ohne UI-Abhängigkeit implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-j"></a>
### 18.j – Ablehnung, Widerruf und veraltete Freigaben

**Anforderungsbezug:** `SR-REQ-0171`, `SR-REQ-0173`, `SR-REQ-0429`–`SR-REQ-0430`, `SR-REQ-0648`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0030`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.j.W – Let it Work

- [ ] **18.j.W** · Position **748/885** · Voraussetzung: `18.i.C`.
**Exakte Commit-Message:** `18.j.W feat(proposal): Ablehnung, Widerruf und veraltete Freigaben aufbauen`

**Umsetzung:** Negative Entscheidungen, autorisierten Widerruf und Wirksamkeit historischer Reviews exakt modellieren.

**Verhaltensabnahme:** Gegen aktuelle Inhaltsbindung unwirksame Reviews zählen nicht zum Quorum.

#### 18.j.R – Make it Right

- [ ] **18.j.R** · Position **749/885** · Voraussetzung: `18.j.W`.
**Exakte Commit-Message:** `18.j.R feat(proposal): Ablehnung, Widerruf und veraltete Freigaben vervollständigen`

**Vervollständigung:** Nachträglich bearbeiteter Vorschlag darf alte Zustimmung nicht automatisch übernehmen.

**Verhaltensabnahme:** Freigabeentzug, Inhaltsänderung und alter Basisstand blockieren Apply unabhängig von angezeigtem Status. Die W-Nachweise bleiben zusätzlich grün.

#### 18.j.C – Make it Clean

- [ ] **18.j.C** · Position **750/885** · Voraussetzung: `18.j.R`.
**Exakte Commit-Message:** `18.j.C refactor(proposal): Ablehnung, Widerruf und veraltete Freigaben bereinigen`

**Bereinigung:** Reviewhistorie erhalten und effektiven Freigabestatus daraus ableiten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-k"></a>
### 18.k – Anwenden ohne veralteten Basiswrite

**Anforderungsbezug:** `SR-REQ-0173`–`SR-REQ-0175`, `SR-REQ-0178`, `SR-REQ-0429`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0019`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.k.W – Let it Work

- [ ] **18.k.W** · Position **751/885** · Voraussetzung: `18.j.C`.
**Exakte Commit-Message:** `18.k.W feat(proposal): Anwenden ohne veralteten Basiswrite aufbauen`

**Umsetzung:** Vollständig geprüftes und aktuell freigegebenes Proposal samt Zieländerungen, applied-Status und Receipt in einer Transaktion anwenden.

**Verhaltensabnahme:** Proposal und Fachänderung werden gemeinsam sichtbar, mit genau den geprüften Identitäten.

#### 18.k.R – Make it Right

- [ ] **18.k.R** · Position **752/885** · Voraussetzung: `18.k.W`.
**Exakte Commit-Message:** `18.k.R feat(proposal): Anwenden ohne veralteten Basiswrite vervollständigen`

**Vervollständigung:** Stale Basis oder fehlende aktuelle Freigabe führt lesend zum Fehler; kein automatisches Umschreiben des gespeicherten Proposals auf stale.

**Verhaltensabnahme:** Manipulierte Plan-/Reviewbindung, Crash und Retry erzeugen weder Teilapply noch doppelte Fachobjekte. Die W-Nachweise bleiben zusätzlich grün.

#### 18.k.C – Make it Clean

- [ ] **18.k.C** · Position **753/885** · Voraussetzung: `18.k.R`.
**Exakte Commit-Message:** `18.k.C refactor(proposal): Anwenden ohne veralteten Basiswrite bereinigen`

**Bereinigung:** Proposal-Apply als autorisierte Writerquelle ohne Sondertransaktion ausführen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-l"></a>
### 18.l – Authoring als Proposal und KI-Schreibschutz

**Anforderungsbezug:** `SR-REQ-0177`, `SR-REQ-0219`, `SR-REQ-0426`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0030`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.l.W – Let it Work

- [ ] **18.l.W** · Position **754/885** · Voraussetzung: `18.k.C`.
**Exakte Commit-Message:** `18.l.W feat(proposal): Authoring als Proposal und KI-Schreibschutz aufbauen`

**Umsetzung:** Unterstützte Änderungsbefehle mit as-proposal in denselben fachlich vollständigen Plan umleiten.

**Verhaltensabnahme:** Geplante Erzeugung enthält alle Defaults und liefert dasselbe beabsichtigte Ziel wie autorisiertes direktes Authoring.

#### 18.l.R – Make it Right

- [ ] **18.l.R** · Position **755/885** · Voraussetzung: `18.l.W`.
**Exakte Commit-Message:** `18.l.R feat(proposal): Authoring als Proposal und KI-Schreibschutz vervollständigen`

**Vervollständigung:** Standardmäßig unerlaubter KI-Direktwrite endet mit Code 7; Umleitung hebt Fach-/Scopegrenzen nicht auf.

**Verhaltensabnahme:** Rechteänderungen entstehen nicht durch Benutzertext oder frei gesetzte Metadaten allein. Die W-Nachweise bleiben zusätzlich grün.

#### 18.l.C – Make it Clean

- [ ] **18.l.C** · Position **756/885** · Voraussetzung: `18.l.R`.
**Exakte Commit-Message:** `18.l.C refactor(proposal): Authoring als Proposal und KI-Schreibschutz bereinigen`

**Bereinigung:** Normalen Authoringplanner verwenden und nur die Publikationsart wechseln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-m"></a>
### 18.m – Agenten-Selbstbeschreibung und strukturierte Abläufe

**Anforderungsbezug:** `SR-REQ-0179`–`SR-REQ-0180`, `SR-REQ-0228`, `SR-REQ-0242`, `SR-REQ-0376`–`SR-REQ-0381`, `SR-REQ-0632`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0017`, `SR-VER-0018`, `SR-VER-0027`, `SR-VER-0040`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.m.W – Let it Work

- [ ] **18.m.W** · Position **757/885** · Voraussetzung: `18.l.C`.
**Exakte Commit-Message:** `18.m.W feat(proposal): Agenten-Selbstbeschreibung und strukturierte Abläufe aufbauen`

**Umsetzung:** Tatsächlich implementierte Befehle, Parameter, Schemas, Datenverträge und Seiteneffektklassen für Agenten vollständig bereitstellen.

**Verhaltensabnahme:** Ein Agent kann gültige strukturierte Aufträge aus dem maschinenlesbaren Vertrag bilden.

#### 18.m.R – Make it Right

- [ ] **18.m.R** · Position **758/885** · Voraussetzung: `18.m.W`.
**Exakte Commit-Message:** `18.m.R feat(proposal): Agenten-Selbstbeschreibung und strukturierte Abläufe vervollständigen`

**Vervollständigung:** Unfertige Fähigkeiten und menschlich erforderliche Schritte nicht als autonom ausführbar ausweisen.

**Verhaltensabnahme:** JSON-Verträge und reale Handlerwirkung werden geprüft, keine Hilfetexte oder Dokuauszüge. Die W-Nachweise bleiben zusätzlich grün.

#### 18.m.C – Make it Clean

- [ ] **18.m.C** · Position **759/885** · Voraussetzung: `18.m.R`.
**Exakte Commit-Message:** `18.m.C refactor(proposal): Agenten-Selbstbeschreibung und strukturierte Abläufe bereinigen`

**Bereinigung:** Registry, Schemas und Capabilities aus den tatsächlichen Implementierungsquellen ableiten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-n"></a>
### 18.n – Policygrenzen ohne Git-Automatik

**Anforderungsbezug:** `SR-REQ-0176`–`SR-REQ-0177`, `SR-REQ-0201`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0014`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.n.W – Let it Work

- [ ] **18.n.W** · Position **760/885** · Voraussetzung: `18.m.C`.
**Exakte Commit-Message:** `18.n.W feat(proposal): Policygrenzen ohne Git-Automatik aufbauen`

**Umsetzung:** Freigabe, Policyautorität und Schreibrechte auch bei nichtinteraktiver Agentennutzung erhalten.

**Verhaltensabnahme:** Zulässige Projektänderung bleibt unabhängig von Git vorhanden.

#### 18.n.R – Make it Right

- [ ] **18.n.R** · Position **761/885** · Voraussetzung: `18.n.W`.
**Exakte Commit-Message:** `18.n.R feat(proposal): Policygrenzen ohne Git-Automatik vervollständigen`

**Vervollständigung:** Proposalworkflow führt selbst keinen commit, branch, push oder freie Fremdbefehle aus.

**Verhaltensabnahme:** Gitstand und externe Ressourcen bleiben bei allen rein fachlichen Proposaloperationen unverändert. Die W-Nachweise bleiben zusätzlich grün.

#### 18.n.C – Make it Clean

- [ ] **18.n.C** · Position **762/885** · Voraussetzung: `18.n.R`.
**Exakte Commit-Message:** `18.n.C refactor(proposal): Policygrenzen ohne Git-Automatik bereinigen`

**Bereinigung:** Produktrechte von der externen PatchHarbor-Entwicklungsautomatik klar trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-o"></a>
### 18.o – Proposalfortsetzung mit echten Reviews

**Anforderungsbezug:** `SR-REQ-0285`, `SR-REQ-0647`.
**Verifikationsbezug:** `SR-VER-0021`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.o.W – Let it Work

- [ ] **18.o.W** · Position **763/885** · Voraussetzung: `18.n.C`.
**Exakte Commit-Message:** `18.o.W feat(proposal): Proposalfortsetzung mit echten Reviews aufbauen`

**Umsetzung:** Planung, isolierte Prüfung und Arbeitsfortsetzung an dieselbe Inhalts-/Basis-/Enginebindung anschließen.

**Verhaltensabnahme:** Geteilter Ablauf erreicht denselben geprüften Vorschlag und dieselben gültigen Reviewvoraussetzungen.

#### 18.o.R – Make it Right

- [ ] **18.o.R** · Position **764/885** · Voraussetzung: `18.o.W`.
**Exakte Commit-Message:** `18.o.R feat(proposal): Proposalfortsetzung mit echten Reviews vervollständigen`

**Vervollständigung:** Sandboxwechsel, neue Inhaltsrevision oder andere Basis erzwingen Neubewertung statt Wiederverwendung unpassender Zustimmung.

**Verhaltensabnahme:** Fortgesetztes Apply ohne echte erforderliche Menschen bleibt blockiert; frühere nachgewiesene Zustimmung nur bei identischer Bindung gültig. Die W-Nachweise bleiben zusätzlich grün.

#### 18.o.C – Make it Clean

- [ ] **18.o.C** · Position **765/885** · Voraussetzung: `18.o.R`.
**Exakte Commit-Message:** `18.o.C refactor(proposal): Proposalfortsetzung mit echten Reviews bereinigen`

**Bereinigung:** Workstatus und Proposal-Lifecycle getrennt halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-18-p"></a>
### 18.p – Ende-zu-Ende-Änderungsdialog

**Anforderungsbezug:** `SR-REQ-0154`–`SR-REQ-0178`, `SR-REQ-0643`–`SR-REQ-0649`.
**Verifikationsbezug:** `SR-VER-0012`, `SR-VER-0014`, `SR-VER-0019`, `SR-VER-0043`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 18.p.W – Let it Work

- [ ] **18.p.W** · Position **766/885** · Voraussetzung: `18.o.C`.
**Exakte Commit-Message:** `18.p.W feat(proposal): Ende-zu-Ende-Änderungsdialog aufbauen`

**Umsetzung:** Vollständigen realen Ablauf Entwurf, Check, Review, Überarbeitung, erneute Freigabe und Apply über öffentliche Schnittstellen prüfen.

**Verhaltensabnahme:** Bewusst genehmigter aktueller Vorschlag ändert exakt die geplanten Fachdateien.

#### 18.p.R – Make it Right

- [ ] **18.p.R** · Position **767/885** · Voraussetzung: `18.p.W`.
**Exakte Commit-Message:** `18.p.R feat(proposal): Ende-zu-Ende-Änderungsdialog vervollständigen`

**Vervollständigung:** Rejection, stale-Basis, Scopeangriff und Abbruch erhalten Originaldaten und auditierbare Entscheidungen.

**Verhaltensabnahme:** Fachliche Szenarien SR-SCN-0009 und SR-SCN-0010 werden ohne erfundene menschliche Runtimefreigabe implementiert; Testakteure sind explizite Fixtures. Die W-Nachweise bleiben zusätzlich grün.

#### 18.p.C – Make it Clean

- [ ] **18.p.C** · Position **768/885** · Voraussetzung: `18.p.R`.
**Exakte Commit-Message:** `18.p.C refactor(proposal): Ende-zu-Ende-Änderungsdialog bereinigen`

**Bereinigung:** Wiederholte Ablaufhilfen bündeln, Testoracles und tatsächliche Freigabebindung unverändert lassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 18 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m19"></a>
## Meilenstein 19 – Analyzer-Schnittstelle und echte Spracherkennung

**Ziel:** Generische datengebundene Analyse und tatsächlich ausführbare lokale Spracherkennung mit py3langid 0.4.0, ohne den dependency-freien Core aufzublähen.

**Vorgesehener Zuschnitt:** `src/specroad/analyzers/, src/specroad/language_worker/, packaging/language/, tests/corpora/`. **Fachgrundlage:** §§ 12.45–12.47, 14.11; Anhänge S, T, R-48 bis R-75.

**Abschlussgate:** Echter Referenzadapter, vollständige Subjects, sichere Workergrenze, korrekte Nichtentscheidungen und ID-stabile Fortsetzung sind nachgewiesen; fehlende Pakete sind kein erfolgreicher Detektortest. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-19-a"></a>
### 19.a – Generischer Analyzer- und Descriptorvertrag

**Anforderungsbezug:** `SR-REQ-0675`–`SR-REQ-0677`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.a.W – Let it Work

- [ ] **19.a.W** · Position **769/885** · Voraussetzung: `18.p.C`.
**Exakte Commit-Message:** `19.a.W feat(analyzer): Generischer Analyzer- und Descriptorvertrag aufbauen`

**Umsetzung:** Versionierte Descriptoren mit Analyzeridentität, Capabilities, Subjectmodi und Datenverträgen implementieren.

**Verhaltensabnahme:** Bekannter eingebauter und gültiger externer Descriptor lassen sich strukturell unterscheiden.

#### 19.a.R – Make it Right

- [ ] **19.a.R** · Position **770/885** · Voraussetzung: `19.a.W`.
**Exakte Commit-Message:** `19.a.R feat(analyzer): Generischer Analyzer- und Descriptorvertrag vervollständigen`

**Vervollständigung:** Ein Projekt-/Importdescriptor erzeugt niemals Ausführungsrecht oder dynamischen Import.

**Verhaltensabnahme:** Unbekannte Vertragsversionen und unerlaubte Felder werden abgewiesen, zulässige Erweiterungen bleiben Daten. Die W-Nachweise bleiben zusätzlich grün.

#### 19.a.C – Make it Clean

- [ ] **19.a.C** · Position **771/885** · Voraussetzung: `19.a.R`.
**Exakte Commit-Message:** `19.a.C refactor(analyzer): Generischer Analyzer- und Descriptorvertrag bereinigen`

**Bereinigung:** Descriptorvalidierung und vertrauenswürdige Ausführungsregistry strikt trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-b"></a>
### 19.b – Requestidentität und Snapshotbindung

**Anforderungsbezug:** `SR-REQ-0678`–`SR-REQ-0679`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.b.W – Let it Work

- [ ] **19.b.W** · Position **772/885** · Voraussetzung: `19.a.C`.
**Exakte Commit-Message:** `19.b.W feat(analyzer): Requestidentität und Snapshotbindung aufbauen`

**Umsetzung:** Datentragenden Analyzerrequest mit stabiler AnalysisRequestId und exakt projiziertem Snapshothash erzeugen.

**Verhaltensabnahme:** Automatische AN-ID wird einmal vor Arbeitsbeginn gebildet; explizite analysis-id bleibt unverändert.

#### 19.b.R – Make it Right

- [ ] **19.b.R** · Position **773/885** · Voraussetzung: `19.b.W`.
**Exakte Commit-Message:** `19.b.R feat(analyzer): Requestidentität und Snapshotbindung vervollständigen`

**Vervollständigung:** Betriebsmetadaten nicht in Fachhash aufnehmen; request_id der Schreibidempotenz nicht damit vermischen.

**Verhaltensabnahme:** Gleiche Analyse-ID plus anderer Snapshot und umgekehrt werden getrennt erkannt. Die W-Nachweise bleiben zusätzlich grün.

#### 19.b.C – Make it Clean

- [ ] **19.b.C** · Position **774/885** · Voraussetzung: `19.b.R`.
**Exakte Commit-Message:** `19.b.C refactor(analyzer): Requestidentität und Snapshotbindung bereinigen`

**Bereinigung:** Eigene Typen für AnalysisRequestId und WriteRequestId einführen, trotz ähnlicher Stringsyntax.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-c"></a>
### 19.c – Vollständige Subjects und Kontextminimierung

**Anforderungsbezug:** `SR-REQ-0680`–`SR-REQ-0681`, `SR-REQ-0706`.
**Verifikationsbezug:** `SR-VER-0046`, `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.c.W – Let it Work

- [ ] **19.c.W** · Position **775/885** · Voraussetzung: `19.b.C`.
**Exakte Commit-Message:** `19.c.W feat(analyzer): Vollständige Subjects und Kontextminimierung aufbauen`

**Umsetzung:** Jeden gewählten Statement-/Pointerwert vollständig und separat mit Originalhash exportieren.

**Verhaltensabnahme:** Zwei Statements ergeben zwei gebundene Subjects, nicht eine zusammengefügte oder gekürzte Probe.

#### 19.c.R – Make it Right

- [ ] **19.c.R** · Position **776/885** · Voraussetzung: `19.c.W`.
**Exakte Commit-Message:** `19.c.R feat(analyzer): Vollständige Subjects und Kontextminimierung vervollständigen`

**Vervollständigung:** Nur ausdrücklich gewählten Kontext freigeben; fehlender String und fremder Pointer sind Eingabefehler.

**Verhaltensabnahme:** Lange Unicode-/Mehrsprachentexte und anweisungsähnlicher Inhalt bleiben unveränderte Analysedaten. Die W-Nachweise bleiben zusätzlich grün.

#### 19.c.C – Make it Clean

- [ ] **19.c.C** · Position **777/885** · Voraussetzung: `19.c.R`.
**Exakte Commit-Message:** `19.c.C refactor(analyzer): Vollständige Subjects und Kontextminimierung bereinigen`

**Bereinigung:** Subjectauswahl auf vorhandene Scope-/Pointer-/Snapshotdienste setzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-d"></a>
### 19.d – Findings, Coverage und Ergebnisprojektion

**Anforderungsbezug:** `SR-REQ-0682`–`SR-REQ-0684`, `SR-REQ-0697`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.d.W – Let it Work

- [ ] **19.d.W** · Position **778/885** · Voraussetzung: `19.c.C`.
**Exakte Commit-Message:** `19.d.W feat(analyzer): Findings, Coverage und Ergebnisprojektion aufbauen`

**Umsetzung:** Generische Findings mit Herkunft und exakte expected/done/undetermined/failed/open-Coverage modellieren.

**Verhaltensabnahme:** Jeder ausgewählte Subjectstatus trägt nachvollziehbar zur Gesamtdeckung bei.

#### 19.d.R – Make it Right

- [ ] **19.d.R** · Position **779/885** · Voraussetzung: `19.d.W`.
**Exakte Commit-Message:** `19.d.R feat(analyzer): Findings, Coverage und Ergebnisprojektion vervollständigen`

**Vervollständigung:** Doppelte/fremde Subjects und widersprüchliche Summen ablehnen; unbekannte gültige Namespaces erhalten.

**Verhaltensabnahme:** Fachliche Ergebnisprojektion bleibt bei anderen Messzeiten und Prozesskennungen gleich. Die W-Nachweise bleiben zusätzlich grün.

#### 19.d.C – Make it Clean

- [ ] **19.d.C** · Position **780/885** · Voraussetzung: `19.d.R`.
**Exakte Commit-Message:** `19.d.C refactor(analyzer): Findings, Coverage und Ergebnisprojektion bereinigen`

**Bereinigung:** Betriebsmetriken, Provenienz und deterministische Fachbeobachtung sauber schichten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-e"></a>
### 19.e – Reportpackage und sichere Importprüfung

**Anforderungsbezug:** `SR-REQ-0691`–`SR-REQ-0692`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.e.W – Let it Work

- [ ] **19.e.W** · Position **781/885** · Voraussetzung: `19.d.C`.
**Exakte Commit-Message:** `19.e.W feat(analyzer): Reportpackage und sichere Importprüfung aufbauen`

**Umsetzung:** Package mit vollständigem datentragendem Request und sämtlichen ausgewählten Reports lesen und verifizieren.

**Verhaltensabnahme:** Reports passen gleichzeitig zur Analyse-ID und zum Request-Snapshothash.

#### 19.e.R – Make it Right

- [ ] **19.e.R** · Position **782/885** · Voraussetzung: `19.e.W`.
**Exakte Commit-Message:** `19.e.R feat(analyzer): Reportpackage und sichere Importprüfung vervollständigen`

**Vervollständigung:** Manipulierte Hashes, fehlende Pflichtsubjects, unzulässige Felder und einzelne fremde Reports blockieren.

**Verhaltensabnahme:** Ein zufällig gleicher Snapshot ersetzt keine passende Analyse-ID; Verifikation ist projektlos möglich. Die W-Nachweise bleiben zusätzlich grün.

#### 19.e.C – Make it Clean

- [ ] **19.e.C** · Position **783/885** · Voraussetzung: `19.e.R`.
**Exakte Commit-Message:** `19.e.C refactor(analyzer): Reportpackage und sichere Importprüfung bereinigen`

**Bereinigung:** Request-/Reportvalidatoren auch beim Workerresultat wiederverwenden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-f"></a>
### 19.f – Read-only-Auswertung und Nachweisgrenze

**Anforderungsbezug:** `SR-REQ-0685`–`SR-REQ-0688`, `SR-REQ-0693`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.f.W – Let it Work

- [ ] **19.f.W** · Position **784/885** · Voraussetzung: `19.e.C`.
**Exakte Commit-Message:** `19.f.W feat(analyzer): Read-only-Auswertung und Nachweisgrenze aufbauen`

**Umsetzung:** Aktualität current/stale/unavailable/invalid berechnen und mehrere Reports mit abweichender Provenienz vollständig auswerten.

**Verhaltensabnahme:** Fehlende aktuelle Bindung ist von beschädigtem Report unterscheidbar.

#### 19.f.R – Make it Right

- [ ] **19.f.R** · Position **785/885** · Voraussetzung: `19.f.W`.
**Exakte Commit-Message:** `19.f.R feat(analyzer): Read-only-Auswertung und Nachweisgrenze vervollständigen`

**Vervollständigung:** Kein Import verändert Requirementfelder, Reviews, Reifegrade oder Verification Results und gilt nicht automatisch als Evidence.

**Verhaltensabnahme:** Reportbytes bleiben auch bei neuer Aktualitätsbewertung identisch; widersprechende Beobachtungen werden nicht weggefiltert. Die W-Nachweise bleiben zusätzlich grün.

#### 19.f.C – Make it Clean

- [ ] **19.f.C** · Position **786/885** · Voraussetzung: `19.f.R`.
**Exakte Commit-Message:** `19.f.C refactor(analyzer): Read-only-Auswertung und Nachweisgrenze bereinigen`

**Bereinigung:** Analysebeobachtung ausdrücklich außerhalb des normativen Artefakt-/Evidencemodells halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-g"></a>
### 19.g – Analyzer-CLI und Dateiseiteneffekte

**Anforderungsbezug:** `SR-REQ-0689`–`SR-REQ-0690`.
**Verifikationsbezug:** `SR-VER-0046`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.g.W – Let it Work

- [ ] **19.g.W** · Position **787/885** · Voraussetzung: `19.f.C`.
**Exakte Commit-Message:** `19.g.W feat(analyzer): Analyzer-CLI und Dateiseiteneffekte aufbauen`

**Umsetzung:** list, request, run, import, show und evaluate mit echten Handlern und korrekter Befehlsklasse anbieten.

**Verhaltensabnahme:** Generierte Report-/Requestdaten liegen außerhalb des kanonischen Modells; read_only-Befehle verändern nichts.

#### 19.g.R – Make it Right

- [ ] **19.g.R** · Position **788/885** · Voraussetzung: `19.g.W`.
**Exakte Commit-Message:** `19.g.R feat(analyzer): Analyzer-CLI und Dateiseiteneffekte vervollständigen`

**Vervollständigung:** Gleiche Zieldateibytes sind No-op, abweichende Bytes Konflikt 6; unzulässige actor/request-id/dry-run/as-proposal-Optionen liefern Code 2.

**Verhaltensabnahme:** Strukturierte Daten und Dateizustand sind das Oracle, nicht stdout-Layout oder Diagnosewortlaut. Die W-Nachweise bleiben zusätzlich grün.

#### 19.g.C – Make it Clean

- [ ] **19.g.C** · Position **789/885** · Voraussetzung: `19.g.R`.
**Exakte Commit-Message:** `19.g.C refactor(analyzer): Analyzer-CLI und Dateiseiteneffekte bereinigen`

**Bereinigung:** Alle Analyzeroptionen über die bestehende Command Registry beschreiben.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-h"></a>
### 19.h – Externe Analyzer als reine Dateischnittstelle

**Anforderungsbezug:** `SR-REQ-0694`–`SR-REQ-0696`.
**Verifikationsbezug:** `SR-VER-0046`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.h.W – Let it Work

- [ ] **19.h.W** · Position **790/885** · Voraussetzung: `19.g.C`.
**Exakte Commit-Message:** `19.h.W feat(analyzer): Externe Analyzer als reine Dateischnittstelle aufbauen`

**Umsetzung:** Gültige Requests/Reports eines nicht ausführbaren externen Backends bereits austauschen und execution_supported false führen.

**Verhaltensabnahme:** Import/Auswertung funktioniert ohne externen Workerstart.

#### 19.h.R – Make it Right

- [ ] **19.h.R** · Position **791/885** · Voraussetzung: `19.h.W`.
**Exakte Commit-Message:** `19.h.R feat(analyzer): Externe Analyzer als reine Dateischnittstelle vervollständigen`

**Vervollständigung:** strict, validate, lint und Anweisungstexte starten niemals Analyse, Modelle oder freie Kommandos.

**Verhaltensabnahme:** Ein bösartiger Descriptor oder Subjecttext löst weder Prozess noch Netzwerk aus. Die W-Nachweise bleiben zusätzlich grün.

#### 19.h.C – Make it Clean

- [ ] **19.h.C** · Position **792/885** · Voraussetzung: `19.h.R`.
**Exakte Commit-Message:** `19.h.C refactor(analyzer): Externe Analyzer als reine Dateischnittstelle bereinigen`

**Bereinigung:** Dateiadapter und bekannte interne Ausführungsadapter getrennt implementieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-i"></a>
### 19.i – Frühe Analyse-ID und Workinitialisierung

**Anforderungsbezug:** `SR-REQ-0715`–`SR-REQ-0716`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.i.W – Let it Work

- [ ] **19.i.W** · Position **793/885** · Voraussetzung: `19.h.C`.
**Exakte Commit-Message:** `19.i.W feat(analyzer): Frühe Analyse-ID und Workinitialisierung aufbauen`

**Umsetzung:** AnalysisRequestId vor erstem Snapshot-/Workschritt persistierbar binden, auch bei automatisch gewähltem Workverzeichnis.

**Verhaltensabnahme:** Resume während noch unvollständiger Snapshoterzeugung behält dieselbe AN-ID.

#### 19.i.R – Make it Right

- [ ] **19.i.R** · Position **794/885** · Voraussetzung: `19.i.W`.
**Exakte Commit-Message:** `19.i.R feat(analyzer): Frühe Analyse-ID und Workinitialisierung vervollständigen`

**Vervollständigung:** Actor, WriteRequestId und operations_sha256 bleiben bei Analyse-Work null; analysis_id steht in normalized_arguments.

**Verhaltensabnahme:** R-64 bis R-75 prüfen Optionszulassung, frühe Kennung, nicht verwechselte Identitäten und fehlende Schreibreceipts. Die W-Nachweise bleiben zusätzlich grün.

#### 19.i.C – Make it Clean

- [ ] **19.i.C** · Position **795/885** · Voraussetzung: `19.i.R`.
**Exakte Commit-Message:** `19.i.C refactor(analyzer): Frühe Analyse-ID und Workinitialisierung bereinigen`

**Bereinigung:** Analysearbeit als eigenen Workauftragstyp statt fingierten Change Plan führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-j"></a>
### 19.j – Dauerhafte Checkpoints und Ergebnisfortsetzung

**Anforderungsbezug:** `SR-REQ-0715`–`SR-REQ-0716`, `SR-REQ-0719`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.j.W – Let it Work

- [ ] **19.j.W** · Position **796/885** · Voraussetzung: `19.i.C`.
**Exakte Commit-Message:** `19.j.W feat(analyzer): Dauerhafte Checkpoints und Ergebnisfortsetzung aufbauen`

**Umsetzung:** Große Analyseaufträge mit oder ohne explizites work-dir durch bestätigte dauerhafte Fortschrittseinheiten fortsetzen.

**Verhaltensabnahme:** Fertige Subjects werden wiederverwendet; winziger vollständig beendbarer Auftrag benötigt kein Workverzeichnis.

#### 19.j.R – Make it Right

- [ ] **19.j.R** · Position **797/885** · Voraussetzung: `19.j.W`.
**Exakte Commit-Message:** `19.j.R feat(analyzer): Dauerhafte Checkpoints und Ergebnisfortsetzung vervollständigen`

**Vervollständigung:** Kein Code 8 vor dauerhaftem Checkpoint; unmöglicher sicherer Abschluss ohne Speicher ist echter Blocker 5.

**Verhaltensabnahme:** Engine-/Snapshotwechsel führt zu Konflikt 6 oder explizit neuem Auftrag, nie stiller Fortsetzung. Die W-Nachweise bleiben zusätzlich grün.

#### 19.j.C – Make it Clean

- [ ] **19.j.C** · Position **798/885** · Voraussetzung: `19.j.R`.
**Exakte Commit-Message:** `19.j.C refactor(analyzer): Dauerhafte Checkpoints und Ergebnisfortsetzung bereinigen`

**Bereinigung:** Analysecheckpointzustand in bestehende Workjournale integrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-k"></a>
### 19.k – Optionale Sprachdistribution und Offlinepakete

**Anforderungsbezug:** `SR-REQ-0699`–`SR-REQ-0701`.
**Verifikationsbezug:** `SR-VER-0047`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.k.W – Let it Work

- [ ] **19.k.W** · Position **799/885** · Voraussetzung: `19.j.C`.
**Exakte Commit-Message:** `19.k.W build(analyzer): Optionale Sprachdistribution und Offlinepakete aufbauen`

**Umsetzung:** Extra specroad[language] und separate Offlinepakete je Linux-x86-64-/CPython-ABI mit py3langid 0.4.0 definieren.

**Verhaltensabnahme:** Ein passendes Paket enthält Adapter, kompatibles NumPy, Referenzmodell, Lizenzdaten und Hashmanifest.

#### 19.k.R – Make it Right

- [ ] **19.k.R** · Position **800/885** · Voraussetzung: `19.k.W`.
**Exakte Commit-Message:** `19.k.R build(analyzer): Optionale Sprachdistribution und Offlinepakete vervollständigen`

**Vervollständigung:** CPython 3.10 bis 3.14 tatsächlich getrennt prüfen; keinen universellen NumPy-Pin oder ARM-Nachweis für x86-64 behaupten.

**Verhaltensabnahme:** Core-Modul und Core-Zipapp funktionieren ohne Zusatzinstallation und enthalten kein verborgenes NumPy-Binary. Die W-Nachweise bleiben zusätzlich grün.

#### 19.k.C – Make it Clean

- [ ] **19.k.C** · Position **801/885** · Voraussetzung: `19.k.R`.
**Exakte Commit-Message:** `19.k.C refactor(analyzer): Optionale Sprachdistribution und Offlinepakete bereinigen`

**Bereinigung:** Core- und Zusatzpackaging bei gemeinsamer Releaseidentität sauber trennen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-l"></a>
### 19.l – Vertrauenswürdiger shellfreier Workerstart

**Anforderungsbezug:** `SR-REQ-0702`–`SR-REQ-0703`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.l.W – Let it Work

- [ ] **19.l.W** · Position **802/885** · Voraussetzung: `19.k.C`.
**Exakte Commit-Message:** `19.l.W feat(analyzer): Vertrauenswürdiger shellfreier Workerstart aufbauen`

**Umsetzung:** Genau den bekannten Distributionsworker über expliziten Interpreter, stdin-Request und JSON-Bericht starten.

**Verhaltensabnahme:** Explizite Analyse erreicht den echten bekannten Worker mit dem vollständig gebundenen Request.

#### 19.l.R – Make it Right

- [ ] **19.l.R** · Position **803/885** · Voraussetzung: `19.l.W`.
**Exakte Commit-Message:** `19.l.R feat(analyzer): Vertrauenswürdiger shellfreier Workerstart vervollständigen`

**Vervollständigung:** Keine Shell, Projekt-CWD-Imports, fremde Entry-point-Suche oder aus Projektdaten gewählten Modellpfade verwenden.

**Verhaltensabnahme:** Manipulierte Umgebung/Projektdateien ersetzen weder Worker noch Modell; ungeeigneter Start bleibt konkreter Fehler. Die W-Nachweise bleiben zusätzlich grün.

#### 19.l.C – Make it Clean

- [ ] **19.l.C** · Position **804/885** · Voraussetzung: `19.l.R`.
**Exakte Commit-Message:** `19.l.C refactor(analyzer): Vertrauenswürdiger shellfreier Workerstart bereinigen`

**Bereinigung:** Prozessadapter und Trustkonfiguration an einer schmalen Schnittstelle bündeln.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-m"></a>
### 19.m – Lazy Loading, Offlinegrenze und Prozesslebensdauer

**Anforderungsbezug:** `SR-REQ-0704`–`SR-REQ-0705`, `SR-REQ-0717`–`SR-REQ-0718`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.m.W – Let it Work

- [ ] **19.m.W** · Position **805/885** · Voraussetzung: `19.l.C`.
**Exakte Commit-Message:** `19.m.W feat(analyzer): Lazy Loading, Offlinegrenze und Prozesslebensdauer aufbauen`

**Umsetzung:** Modell erst beim expliziten Run einmal je Worker laden, Analyzer seriell mit höchstens einem Modell betreiben.

**Verhaltensabnahme:** help/version/validate/show/list laufen ohne NumPy- oder Modellinitialisierung.

#### 19.m.R – Make it Right

- [ ] **19.m.R** · Position **806/885** · Voraussetzung: `19.m.W`.
**Exakte Commit-Message:** `19.m.R feat(analyzer): Lazy Loading, Offlinegrenze und Prozesslebensdauer vervollständigen`

**Vervollständigung:** Training, URL/Webservice, Telemetrie, automatische Installation und Hintergrunddienst nicht exponieren; Kinder bei behandeltem Ende einsammeln.

**Verhaltensabnahme:** Normalende, Fehler und behandelter Abbruch hinterlassen keinen laufenden Worker; harte Hostverluste nur über echte Recoverability bewerten. Die W-Nachweise bleiben zusätzlich grün.

#### 19.m.C – Make it Clean

- [ ] **19.m.C** · Position **807/885** · Voraussetzung: `19.m.R`.
**Exakte Commit-Message:** `19.m.C refactor(analyzer): Lazy Loading, Offlinegrenze und Prozesslebensdauer bereinigen`

**Bereinigung:** Prozesscleanup in einem gemeinsamen garantiert ausgeführten Kontrollpfad führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-n"></a>
### 19.n – Realer py3langid-Referenzadapter

**Anforderungsbezug:** `SR-REQ-0698`–`SR-REQ-0699`, `SR-REQ-0707`.
**Verifikationsbezug:** `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.n.W – Let it Work

- [ ] **19.n.W** · Position **808/885** · Voraussetzung: `19.m.C`.
**Exakte Commit-Message:** `19.n.W feat(analyzer): Realer py3langid-Referenzadapter aufbauen`

**Umsetzung:** py3langid 0.4.0 mit hashgebundenem mitgeliefertem Modell und vollständigem geordnetem Kandidatenraum integrieren.

**Verhaltensabnahme:** Ein echter Bibliotheksaufruf analysiert repräsentative vollständige Texte und liefert gebundene Ranglisten.

#### 19.n.R – Make it Right

- [ ] **19.n.R** · Position **809/885** · Voraussetzung: `19.n.W`.
**Exakte Commit-Message:** `19.n.R feat(analyzer): Realer py3langid-Referenzadapter vervollständigen`

**Vervollständigung:** Fehlendes Paket, Modellhashfehler und unerlaubter Kandidatenfilter sind keine erfolgreiche Ersatzdetektion.

**Verhaltensabnahme:** Mindestens ein echter nicht gemockter Integrationslauf wird je unterstützter Zusatzruntime ausgeführt. Die W-Nachweise bleiben zusätzlich grün.

#### 19.n.C – Make it Clean

- [ ] **19.n.C** · Position **810/885** · Voraussetzung: `19.n.R`.
**Exakte Commit-Message:** `19.n.C refactor(analyzer): Realer py3langid-Referenzadapter bereinigen`

**Bereinigung:** Referenzbackend hinter dem generischen Workerprotokoll kapseln, ohne eine Wortlistenattrappe einzubauen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-o"></a>
### 19.o – Textvollständigkeit und Abstentionsvorbereitung

**Anforderungsbezug:** `SR-REQ-0706`, `SR-REQ-0709`.
**Verifikationsbezug:** `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.o.W – Let it Work

- [ ] **19.o.W** · Position **811/885** · Voraussetzung: `19.n.C`.
**Exakte Commit-Message:** `19.o.W feat(analyzer): Textvollständigkeit und Abstentionsvorbereitung aufbauen`

**Umsetzung:** min_text_codepoints mit Default 20 und Bereich 1 bis 10000 sowie ausschließlich ASCII-Randentfernung zur Längenentscheidung implementieren.

**Verhaltensabnahme:** Jeder nicht zu kurze String erreicht vollständig den Backendaufruf; kurzer Text ergibt insufficient_text.

#### 19.o.R – Make it Right

- [ ] **19.o.R** · Position **812/885** · Voraussetzung: `19.o.W`.
**Exakte Commit-Message:** `19.o.R feat(analyzer): Textvollständigkeit und Abstentionsvorbereitung vervollständigen`

**Vervollständigung:** Unicodeoriginal nicht normalisieren oder speichern; interne Bibliotheksnormalisierung nur auf Arbeitskopie binden.

**Verhaltensabnahme:** Grenzlängen, Sonderleerzeichen, Zitate, Code und gemischte Texte ändern keine normativen Originalbytes. Die W-Nachweise bleiben zusätzlich grün.

#### 19.o.C – Make it Clean

- [ ] **19.o.C** · Position **813/885** · Voraussetzung: `19.o.R`.
**Exakte Commit-Message:** `19.o.C refactor(analyzer): Textvollständigkeit und Abstentionsvorbereitung bereinigen`

**Bereinigung:** Vorverarbeitung als kleine versionierte Policy ohne semantische Segmentierung halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-p"></a>
### 19.p – Normalisierte Scores und exakte Entscheidung

**Anforderungsbezug:** `SR-REQ-0708`–`SR-REQ-0709`.
**Verifikationsbezug:** `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.p.W – Let it Work

- [ ] **19.p.W** · Position **814/885** · Voraussetzung: `19.o.C`.
**Exakte Commit-Message:** `19.p.W feat(analyzer): Normalisierte Scores und exakte Entscheidung aufbauen`

**Umsetzung:** norm_probs=True, Top-zwei-Rangliste und Dezimalstrings mit zwölf Stellen und half-even verwenden.

**Verhaltensabnahme:** min_score 0.900000000000 und min_margin 0.100000000000 entscheiden auf publizierten quantisierten Werten inklusiv.

#### 19.p.R – Make it Right

- [ ] **19.p.R** · Position **815/885** · Voraussetzung: `19.p.W`.
**Exakte Commit-Message:** `19.p.R feat(analyzer): Normalisierte Scores und exakte Entscheidung vervollständigen`

**Vervollständigung:** Nichtendliche/ungültige Scores, Code-Tiebreak, und/zxx und niedriger Abstand folgen der geordneten Abstentionstabelle.

**Verhaltensabnahme:** Grenzwerte und Backendfehler werden mit kontrollierten Scorefixtures geprüft; echte Backendtests bleiben zusätzlich erhalten. Die W-Nachweise bleiben zusätzlich grün.

#### 19.p.C – Make it Clean

- [ ] **19.p.C** · Position **816/885** · Voraussetzung: `19.p.R`.
**Exakte Commit-Message:** `19.p.C refactor(analyzer): Normalisierte Scores und exakte Entscheidung bereinigen`

**Bereinigung:** Scorequantisierung und Entscheidungsfunktion unabhängig vom globalen Decimal-Kontext betreiben.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-q"></a>
### 19.q – Sprachvergleich ohne erfundene Präzision

**Anforderungsbezug:** `SR-REQ-0710`–`SR-REQ-0712`.
**Verifikationsbezug:** `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.q.W – Let it Work

- [ ] **19.q.W** · Position **817/885** · Voraussetzung: `19.p.C`.
**Exakte Commit-Message:** `19.q.W feat(analyzer): Sprachvergleich ohne erfundene Präzision aufbauen`

**Umsetzung:** primary_language-Vergleich und einzig vorgesehene cmn-declared/zh-detected-Grobkompatibilität umsetzen.

**Verhaltensabnahme:** Passender Primärcode ist compatible, cmn/zh nur compatible_coarse und macrolanguage_only.

#### 19.q.R – Make it Right

- [ ] **19.q.R** · Position **818/885** · Voraussetzung: `19.q.W`.
**Exakte Commit-Message:** `19.q.R feat(analyzer): Sprachvergleich ohne erfundene Präzision vervollständigen`

**Vervollständigung:** Region, Script und Mandarin nicht als erkannt ausweisen; unbekannte/private Tags bleiben unverifiable.

**Verhaltensabnahme:** en-US/en-IN sowie chinesische Varianten erhalten ihre Originaldeklaration ohne automatische Korrektur. Die W-Nachweise bleiben zusätzlich grün.

#### 19.q.C – Make it Clean

- [ ] **19.q.C** · Position **819/885** · Voraussetzung: `19.q.R`.
**Exakte Commit-Message:** `19.q.C refactor(analyzer): Sprachvergleich ohne erfundene Präzision bereinigen`

**Bereinigung:** Vergleichsvertrag getrennt von Sprachzulässigkeit und Detektorentscheidung führen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-r"></a>
### 19.r – Policy, Erfolgsbegriffe und Exitcodes

**Anforderungsbezug:** `SR-REQ-0713`–`SR-REQ-0714`.
**Verifikationsbezug:** `SR-VER-0047`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.r.W – Let it Work

- [ ] **19.r.W** · Position **820/885** · Voraussetzung: `19.q.C`.
**Exakte Commit-Message:** `19.r.W feat(analyzer): Policy, Erfolgsbegriffe und Exitcodes aufbauen`

**Umsetzung:** Materialisierte Severitydefaults und execution_complete, all_languages_confirmed und gate_passed separat berechnen.

**Verhaltensabnahme:** Ein vollständiger Lauf mit info-Nichtentscheidungen kann Code 0 haben, ohne alle Sprachen bestätigt zu haben.

#### 19.r.R – Make it Right

- [ ] **19.r.R** · Position **821/885** · Voraussetzung: `19.r.W`.
**Exakte Commit-Message:** `19.r.R feat(analyzer): Policy, Erfolgsbegriffe und Exitcodes vervollständigen`

**Vervollständigung:** Technisch nicht verfügbarer angeforderter Analyzer liefert Code 5; Findings am Fail-Schwellwert Code 1.

**Verhaltensabnahme:** ignore verändert keine Coverage, compatible_coarse setzt keine volle Sprachbestätigung. Die W-Nachweise bleiben zusätzlich grün.

#### 19.r.C – Make it Clean

- [ ] **19.r.C** · Position **822/885** · Voraussetzung: `19.r.R`.
**Exakte Commit-Message:** `19.r.C refactor(analyzer): Policy, Erfolgsbegriffe und Exitcodes bereinigen`

**Bereinigung:** Fachliche Findings, technische Ausführbarkeit und CLI-Exitzuordnung zentral aber getrennt auswerten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-s"></a>
### 19.s – Enginefingerprint und Ergebnisreproduzierbarkeit

**Anforderungsbezug:** `SR-REQ-0697`, `SR-REQ-0722`.
**Verifikationsbezug:** `SR-VER-0046`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.s.W – Let it Work

- [ ] **19.s.W** · Position **823/885** · Voraussetzung: `19.r.C`.
**Exakte Commit-Message:** `19.s.W feat(analyzer): Enginefingerprint und Ergebnisreproduzierbarkeit aufbauen`

**Umsetzung:** Bibliothek, Modell, Kandidaten, Vorverarbeitung, Unicode, NumPy und numerisch relevante Runtime an Engineidentität binden.

**Verhaltensabnahme:** Identische Engine-/Eingangsdaten liefern identische deterministische Ergebnisprojektion.

#### 19.s.R – Make it Right

- [ ] **19.s.R** · Position **824/885** · Voraussetzung: `19.s.W`.
**Exakte Commit-Message:** `19.s.R feat(analyzer): Enginefingerprint und Ergebnisreproduzierbarkeit vervollständigen`

**Vervollständigung:** Cross-Runtime-Unterschiede nicht mit Core-Bytedeterminismus verwechseln; nur spezifizierte Entscheidungsparität fordern.

**Verhaltensabnahme:** Wechsel einer relevanten Enginekomponente macht alte Fortsetzungsbindung unpassend. Die W-Nachweise bleiben zusätzlich grün.

#### 19.s.C – Make it Clean

- [ ] **19.s.C** · Position **825/885** · Voraussetzung: `19.s.R`.
**Exakte Commit-Message:** `19.s.C refactor(analyzer): Enginefingerprint und Ergebnisreproduzierbarkeit bereinigen`

**Bereinigung:** Fingerprintquelle im Worker einmal erzeugen und über alle Resultate transportieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-t"></a>
### 19.t – Eingefrorener mehrsprachiger Referenzkorpus

**Anforderungsbezug:** `SR-REQ-0720`.
**Verifikationsbezug:** `SR-VER-0047`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.t.W – Let it Work

- [ ] **19.t.W** · Position **826/885** · Voraussetzung: `19.s.C`.
**Exakte Commit-Message:** `19.t.W feat(analyzer): Eingefrorener mehrsprachiger Referenzkorpus aufbauen`

**Umsetzung:** Vor Adapterabnahme unabhängigen kuratierten Korpus für de/en/hi/id/pt/es/ru/ja/zh mit je mindestens 20 Requirements von 80 bis 500 Codepoints einfrieren.

**Verhaltensabnahme:** Korpus bindet Herkunft, Lizenz, Sprachlabel, unveränderte Texte und Hash vor der Auswertung.

#### 19.t.R – Make it Right

- [ ] **19.t.R** · Position **827/885** · Voraussetzung: `19.t.W`.
**Exakte Commit-Message:** `19.t.R feat(analyzer): Eingefrorener mehrsprachiger Referenzkorpus vervollständigen`

**Vervollständigung:** Je Sprache mindestens fünf zusätzliche Kurz-/Techniktexte; nicht nach Fehlklassifikation auf günstigere Texte umstellen.

**Verhaltensabnahme:** Tatsächlicher py3langid-Lauf erreicht mindestens 18 von 20 korrekte Entscheidungen je Hauptsprache; übrige nur undetermined, nicht falsch erkannt. Die W-Nachweise bleiben zusätzlich grün.

#### 19.t.C – Make it Clean

- [ ] **19.t.C** · Position **828/885** · Voraussetzung: `19.t.R`.
**Exakte Commit-Message:** `19.t.C refactor(analyzer): Eingefrorener mehrsprachiger Referenzkorpus bereinigen`

**Bereinigung:** Korpusdaten, Prüfharness und Ergebnisbelege trennen; kein Markdown-/Dokutest.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-u"></a>
### 19.u – Fehl-, Grenz- und Angriffsabnahme

**Anforderungsbezug:** `SR-REQ-0692`, `SR-REQ-0695`, `SR-REQ-0706`–`SR-REQ-0714`, `SR-REQ-0720`.
**Verifikationsbezug:** `SR-VER-0046`, `SR-VER-0047`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.u.W – Let it Work

- [ ] **19.u.W** · Position **829/885** · Voraussetzung: `19.t.C`.
**Exakte Commit-Message:** `19.u.W feat(analyzer): Fehl-, Grenz- und Angriffsabnahme aufbauen`

**Umsetzung:** Ungültige Reports, fremde Subjects, manipulierte Scores und Prompt-Injection-artige Texte über den vollständigen Adapterweg prüfen.

**Verhaltensabnahme:** Syntaktisch gültiger Anweisungstext bleibt reines Subject und kann keine Rechte erlangen.

#### 19.u.R – Make it Right

- [ ] **19.u.R** · Position **830/885** · Voraussetzung: `19.u.W`.
**Exakte Commit-Message:** `19.u.R feat(analyzer): Fehl-, Grenz- und Angriffsabnahme vervollständigen`

**Vervollständigung:** Backendunverfügbarkeit, kurze Texte, sehr lange Strings, Gleichstand und grobe Sprachlabels korrekt klassifizieren.

**Verhaltensabnahme:** Originalprojekt bleibt byteidentisch; Umfang und alle nicht erfolgreichen Resultate sind vollständig erfasst. Die W-Nachweise bleiben zusätzlich grün.

#### 19.u.C – Make it Clean

- [ ] **19.u.C** · Position **831/885** · Voraussetzung: `19.u.R`.
**Exakte Commit-Message:** `19.u.C refactor(analyzer): Fehl-, Grenz- und Angriffsabnahme bereinigen`

**Bereinigung:** Gemeinsame generische Vertragsfixtures um echte Workerfehler ergänzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-v"></a>
### 19.v – Analyzer-Ressourcenabnahme

**Anforderungsbezug:** `SR-REQ-0719`, `SR-REQ-0721`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.v.W – Let it Work

- [ ] **19.v.W** · Position **832/885** · Voraussetzung: `19.u.C`.
**Exakte Commit-Message:** `19.v.W feat(analyzer): Analyzer-Ressourcenabnahme aufbauen`

**Umsetzung:** Referenzlauf mit 1000 vollständigen Strings von 100 bis 500 Codepoints samt Parent-/Workerverbrauch messen.

**Verhaltensabnahme:** Gemessene gesamte CPU-Zeit ist höchstens 120 Sekunden und Peak-RSS gemäß T.10 höchstens 512 MiB auf der Referenzplattform.

#### 19.v.R – Make it Right

- [ ] **19.v.R** · Position **833/885** · Voraussetzung: `19.v.W`.
**Exakte Commit-Message:** `19.v.R feat(analyzer): Analyzer-Ressourcenabnahme vervollständigen`

**Vervollständigung:** Nicht messbare Plattform nicht als bestanden ausweisen; kleiner Host darf echten Blocker melden, aber niemals Text kürzen.

**Verhaltensabnahme:** Belege enthalten Runtime, Modellhash, Inputhash, Prozessmenge und getrennte Ressourcenwerte. Die W-Nachweise bleiben zusätzlich grün.

#### 19.v.C – Make it Clean

- [ ] **19.v.C** · Position **834/885** · Voraussetzung: `19.v.R`.
**Exakte Commit-Message:** `19.v.C refactor(analyzer): Analyzer-Ressourcenabnahme bereinigen`

**Bereinigung:** Messharness außerhalb der produktiven Abhängigkeiten halten und Corebudgets nicht vermischen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-w"></a>
### 19.w – Analyse-Wiederaufnahme und Hostfehler

**Anforderungsbezug:** `SR-REQ-0715`–`SR-REQ-0719`, `SR-REQ-0722`.
**Verifikationsbezug:** `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.w.W – Let it Work

- [ ] **19.w.W** · Position **835/885** · Voraussetzung: `19.v.C`.
**Exakte Commit-Message:** `19.w.W feat(analyzer): Analyse-Wiederaufnahme und Hostfehler aufbauen`

**Umsetzung:** Reale Analyse an allen dauerhaften Subject-/Checkpointgrenzen unterbrechen und in neuem Prozess fortsetzen.

**Verhaltensabnahme:** Identische AN-ID, vollständiger Request und Engine führen zum vollständigen gleichen Fachresultat.

#### 19.w.R – Make it Right

- [ ] **19.w.R** · Position **836/885** · Voraussetzung: `19.w.W`.
**Exakte Commit-Message:** `19.w.R feat(analyzer): Analyse-Wiederaufnahme und Hostfehler vervollständigen`

**Vervollständigung:** Voller Scratch, Workercrash, fehlende Workdaten und bindungswidrige Engine erzeugen echte Fehler statt endlosen Retry.

**Verhaltensabnahme:** Bereits abgeschlossene Subjects bleiben nachweisbar erhalten; Code 8 benötigt Fortschritt und belastbaren Fortsetzungszustand. Die W-Nachweise bleiben zusätzlich grün.

#### 19.w.C – Make it Clean

- [ ] **19.w.C** · Position **837/885** · Voraussetzung: `19.w.R`.
**Exakte Commit-Message:** `19.w.C refactor(analyzer): Analyse-Wiederaufnahme und Hostfehler bereinigen`

**Bereinigung:** Worker- und Workfehlerzustände über definierte Resultate verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-x"></a>
### 19.x – Mehrsprachiger Ende-zu-Ende-Roundtrip

**Anforderungsbezug:** `SR-REQ-0723`, `SR-REQ-0726`.
**Verifikationsbezug:** `SR-VER-0049`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.x.W – Let it Work

- [ ] **19.x.W** · Position **838/885** · Voraussetzung: `19.w.C`.
**Exakte Commit-Message:** `19.x.W feat(analyzer): Mehrsprachiger Ende-zu-Ende-Roundtrip aufbauen`

**Umsetzung:** Mehrsprachige Requirements über Authoring, Darstellung, Export/Import, Bundle und Analyzer-Dateiaustausch führen.

**Verhaltensabnahme:** language, normative_force, vollständige Statements und ihre Fachhashes bleiben über verlustfreie Verträge erhalten.

#### 19.x.R – Make it Right

- [ ] **19.x.R** · Position **839/885** · Voraussetzung: `19.x.W`.
**Exakte Commit-Message:** `19.x.R feat(analyzer): Mehrsprachiger Ende-zu-Ende-Roundtrip vervollständigen`

**Vervollständigung:** Reports bleiben extern; Darstellung fügt keine vermeintlich erkannten Wörter, Regionen oder neue Verbindlichkeit ein.

**Verhaltensabnahme:** Fach-/Datei-/Hashoracles prüfen den Roundtrip ohne HTML-/Markdown-/Konsolensnapshots. Die W-Nachweise bleiben zusätzlich grün.

#### 19.x.C – Make it Clean

- [ ] **19.x.C** · Position **840/885** · Voraussetzung: `19.x.R`.
**Exakte Commit-Message:** `19.x.C refactor(analyzer): Mehrsprachiger Ende-zu-Ende-Roundtrip bereinigen`

**Bereinigung:** Bestehende Featuretests zu einem echten zusammenhängenden Szenario verbinden.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-19-y"></a>
### 19.y – Core-/Zusatzmatrix und vollständige Analyzerfreigabe

**Anforderungsbezug:** `SR-REQ-0698`–`SR-REQ-0705`, `SR-REQ-0720`–`SR-REQ-0722`, `SR-REQ-0726`.
**Verifikationsbezug:** `SR-VER-0047`, `SR-VER-0048`, `SR-VER-0049`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 19.y.W – Let it Work

- [ ] **19.y.W** · Position **841/885** · Voraussetzung: `19.x.C`.
**Exakte Commit-Message:** `19.y.W feat(analyzer): Core-/Zusatzmatrix und vollständige Analyzerfreigabe aufbauen`

**Umsetzung:** Gesamte reale Adaptermatrix für CPython 3.10 bis 3.14 und Core ohne Zusatzpakete getrennt durchlaufen.

**Verhaltensabnahme:** Zusatzruntime erfüllt echte Sprach-/Ressourcen-/Fortsetzungsverträge; Core bleibt überall unabhängig verwendbar.

#### 19.y.R – Make it Right

- [ ] **19.y.R** · Position **842/885** · Voraussetzung: `19.y.W`.
**Exakte Commit-Message:** `19.y.R feat(analyzer): Core-/Zusatzmatrix und vollständige Analyzerfreigabe vervollständigen`

**Vervollständigung:** Fehlende Offlinewheels oder reale Adapterfehler bleiben offene Releaseblocker statt optionalem Skip.

**Verhaltensabnahme:** Alle R-48 bis R-75 sowie SR-VER-0047 bis SR-VER-0050 erhalten aktuelle konkrete Evidence gemäß ihrer tatsächlichen Zuordnung. Die W-Nachweise bleiben zusätzlich grün.

#### 19.y.C – Make it Clean

- [ ] **19.y.C** · Position **843/885** · Voraussetzung: `19.y.R`.
**Exakte Commit-Message:** `19.y.C refactor(analyzer): Core-/Zusatzmatrix und vollständige Analyzerfreigabe bereinigen`

**Bereinigung:** Testmatrix bündeln, ohne verschiedene Nachweisarten oder Plattformen zu einem Scheinerfolg zusammenzufassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 19 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.


<a id="m20"></a>
## Meilenstein 20 – Gesamtabnahme und Release

**Ziel:** Bereits implementierte Funktionen gemeinsam abnehmen und ein nachweisbar verwendbares Release 0.2.0 mit ehrlichen offenen Grenzen ausliefern.

**Vorgesehener Zuschnitt:** `tests/acceptance/, tests/security/, tests/performance/, packaging/, CI, docs/`. **Fachgrundlage:** §§ 14–16; Anhang R-01 bis R-75, Anhang U.3.

**Abschlussgate:** 730 Requirements sind zugeordnet; alle erforderlichen ausführbaren Verhaltensverträge und die fachlichen Anteile aller 46 Szenarien sind tatsächlich geprüft. Ausgenommene Darstellungs-/Dokutests bleiben explizite Testpolicyabweichung, kein erfundener Nachweis. Die hier beschriebenen Gates sind Sollkriterien, keine behaupteten Messergebnisse.

<a id="step-20-a"></a>
### 20.a – Abnahmekatalog und ehrliche Nachweisvollständigkeit

**Anforderungsbezug:** `SR-REQ-0491`–`SR-REQ-0496`, `SR-REQ-0500`, `SR-REQ-0650`.
**Verifikationsbezug:** `SR-VER-0034`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.a.W – Let it Work

- [ ] **20.a.W** · Position **844/885** · Voraussetzung: `19.y.C`.
**Exakte Commit-Message:** `20.a.W test(acceptance): Abnahmekatalog und ehrliche Nachweisvollständigkeit aufbauen`

**Umsetzung:** Tatsächliche Tests, Spezifikationshash, Fixtures und Requirement-/Verifikationszuordnung in einen ausführbaren Abnahmekatalog zusammenführen.

**Verhaltensabnahme:** Jedes implementierte Verhalten besitzt echte zuordenbare Evidence; fehlende Ergebnisse bleiben offen.

#### 20.a.R – Make it Right

- [ ] **20.a.R** · Position **845/885** · Voraussetzung: `20.a.W`.
**Exakte Commit-Message:** `20.a.R test(acceptance): Abnahmekatalog und ehrliche Nachweisvollständigkeit vervollständigen`

**Vervollständigung:** Die 730er-Zuordnung nicht als Ausführung ausgeben und reine Darstellung/Doku gemäß TD-001 ausdrücklich ausnehmen.

**Verhaltensabnahme:** Keine Dummytests, stillen xfail-/skip-Erfolge oder Rückdatierung alter Belege zur neuen Spezifikation. Die W-Nachweise bleiben zusätzlich grün.

#### 20.a.C – Make it Clean

- [ ] **20.a.C** · Position **846/885** · Voraussetzung: `20.a.R`.
**Exakte Commit-Message:** `20.a.C refactor(acceptance): Abnahmekatalog und ehrliche Nachweisvollständigkeit bereinigen`

**Bereinigung:** Katalog aus bestehenden Testmarkierungen konsolidieren, ohne Dokumentation automatisiert zu testen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-b"></a>
### 20.b – Fachliche Gesamtszenarien

**Anforderungsbezug:** `SR-REQ-0204`, `SR-REQ-0217`, `SR-REQ-0493`–`SR-REQ-0494`, `SR-REQ-0650`.
**Verifikationsbezug:** `SR-VER-0018`, `SR-VER-0019`, `SR-VER-0034`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.b.W – Let it Work

- [ ] **20.b.W** · Position **847/885** · Voraussetzung: `20.a.C`.
**Exakte Commit-Message:** `20.b.W test(acceptance): Fachliche Gesamtszenarien aufbauen`

**Umsetzung:** Alle 46 spezifizierten SR-SCN-/E2E-Identitäten über die tatsächlichen öffentlichen Funktionswege ausführen.

**Verhaltensabnahme:** Authoring bis Release-Readiness, Varianten, Dokumentdaten, Evidence und Änderungen greifen fachlich zusammen.

#### 20.b.R – Make it Right

- [ ] **20.b.R** · Position **848/885** · Voraussetzung: `20.b.W`.
**Exakte Commit-Message:** `20.b.R test(acceptance): Fachliche Gesamtszenarien vervollständigen`

**Vervollständigung:** Negative, veraltete, unvollständige und verbotene Abläufe dürfen nicht als vollständiger Erfolg enden.

**Verhaltensabnahme:** Zustands-, Daten-, Datei-, Prozess- und Exitcodeoracles verwenden, keine Pretty-/Reportlayout-Snapshots. Die W-Nachweise bleiben zusätzlich grün.

#### 20.b.C – Make it Clean

- [ ] **20.b.C** · Position **849/885** · Voraussetzung: `20.b.R`.
**Exakte Commit-Message:** `20.b.C refactor(acceptance): Fachliche Gesamtszenarien bereinigen`

**Bereinigung:** Szenariohelpers auf vorhandene Fixtures bündeln, Einzelverhaltenstests nicht ersetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-c"></a>
### 20.c – Kontraktregression R-01 bis R-47

**Anforderungsbezug:** `SR-REQ-0650`.
**Verifikationsbezug:** `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.c.W – Let it Work

- [ ] **20.c.W** · Position **850/885** · Voraussetzung: `20.b.C`.
**Exakte Commit-Message:** `20.c.W test(acceptance): Kontraktregression R-01 bis R-47 aufbauen`

**Umsetzung:** Vollständige gekoppelten Regressionen zu Scope, Kontext, Lebenszyklus, Reviews, Merge, Migration, Restore und Work aus Anhang R ausführen.

**Verhaltensabnahme:** Jeder normative Tabellenfall besitzt das spezifizierte Ergebnis und erhaltene Seiteneffektgrenzen.

#### 20.c.R – Make it Right

- [ ] **20.c.R** · Position **851/885** · Voraussetzung: `20.c.W`.
**Exakte Commit-Message:** `20.c.R test(acceptance): Kontraktregression R-01 bis R-47 vervollständigen`

**Vervollständigung:** Keine Beschränkung auf positive Algorithmenmodelle; echte CLI-, Datei- und Prozesspfade prüfen.

**Verhaltensabnahme:** Alle R-01 bis R-47 einschließlich geschützter Historie und nichtrekursivem Manifestbereich nachweisen. Die W-Nachweise bleiben zusätzlich grün.

#### 20.c.C – Make it Clean

- [ ] **20.c.C** · Position **852/885** · Voraussetzung: `20.c.R`.
**Exakte Commit-Message:** `20.c.C refactor(acceptance): Kontraktregression R-01 bis R-47 bereinigen`

**Bereinigung:** Fälle nach vorhandenen Fachfixtures ordnen und Duplikate ohne Verlust der unabhängigen Oracles reduzieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-d"></a>
### 20.d – Mehrsprachen-, Analyzer- und Zahlenregression

**Anforderungsbezug:** `SR-REQ-0650`, `SR-REQ-0726`–`SR-REQ-0730`.
**Verifikationsbezug:** `SR-VER-0041`, `SR-VER-0049`, `SR-VER-0050`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.d.W – Let it Work

- [ ] **20.d.W** · Position **853/885** · Voraussetzung: `20.c.C`.
**Exakte Commit-Message:** `20.d.W test(acceptance): Mehrsprachen-, Analyzer- und Zahlenregression aufbauen`

**Umsetzung:** R-48 bis R-75, SRX-U.3-Vektoren und Sprach-/Analyzerverträge gemeinsam durchlaufen.

**Verhaltensabnahme:** Fachhashes, exakte Zahlenpolicy und getrennte Analysekennungen bleiben über Featuregrenzen konsistent.

#### 20.d.R – Make it Right

- [ ] **20.d.R** · Position **854/885** · Voraussetzung: `20.d.W`.
**Exakte Commit-Message:** `20.d.R test(acceptance): Mehrsprachen-, Analyzer- und Zahlenregression vervollständigen`

**Vervollständigung:** Geänderter globaler Decimal-Kontext, Region-/Scriptverwechslung und vorzeitige Work-ID-Erzeugung dürfen keine falschen Ergebnisse erzeugen.

**Verhaltensabnahme:** Reale Librarynachweise bleiben von rein deterministischen Score-/Datenvektoren getrennt erkennbar. Die W-Nachweise bleiben zusätzlich grün.

#### 20.d.C – Make it Clean

- [ ] **20.d.C** · Position **855/885** · Voraussetzung: `20.d.R`.
**Exakte Commit-Message:** `20.d.C refactor(acceptance): Mehrsprachen-, Analyzer- und Zahlenregression bereinigen`

**Bereinigung:** Kleine reine Vertragsoracles und vollständige Integrationsläufe komplementär halten.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-e"></a>
### 20.e – Transaktions- und Recoverygesamtmatrix

**Anforderungsbezug:** `SR-REQ-0252`–`SR-REQ-0262`, `SR-REQ-0462`, `SR-REQ-0570`, `SR-REQ-0650`.
**Verifikationsbezug:** `SR-VER-0019`, `SR-VER-0031`, `SR-VER-0038`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.e.W – Let it Work

- [ ] **20.e.W** · Position **856/885** · Voraussetzung: `20.d.C`.
**Exakte Commit-Message:** `20.e.W test(acceptance): Transaktions- und Recoverygesamtmatrix aufbauen`

**Umsetzung:** Jeden tatsächlich implementierten dauerhaften Journal-/Publikationspunkt mit echten Abbrüchen und Folgerecovery prüfen.

**Verhaltensabnahme:** Ergebnis ist unveränderter Ausgang, vollständiges Ziel oder nachvollziehbar gesperrter Recoveryfall.

#### 20.e.R – Make it Right

- [ ] **20.e.R** · Position **857/885** · Voraussetzung: `20.e.W`.
**Exakte Commit-Message:** `20.e.R test(acceptance): Transaktions- und Recoverygesamtmatrix vervollständigen`

**Vervollständigung:** Dateisystemfehler, fremde Locks, Korruption, verlorene Sandbox und wiederholter Request erhalten Daten statt sie blind zu überschreiben.

**Verhaltensabnahme:** Genau ein semantisches Receipt pro erfolgreichem Request und keine beschädigt gültig wirkenden Zwischenstände. Die W-Nachweise bleiben zusätzlich grün.

#### 20.e.C – Make it Clean

- [ ] **20.e.C** · Position **858/885** · Voraussetzung: `20.e.R`.
**Exakte Commit-Message:** `20.e.C refactor(acceptance): Transaktions- und Recoverygesamtmatrix bereinigen`

**Bereinigung:** Fault-Injectionpunkte zentral katalogisieren und Transaktionskunden darüber parametrieren.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-f"></a>
### 20.f – Work-, Cache- und Sandboxparität

**Anforderungsbezug:** `SR-REQ-0557`–`SR-REQ-0578`, `SR-REQ-0582`–`SR-REQ-0605`.
**Verifikationsbezug:** `SR-VER-0035`, `SR-VER-0036`, `SR-VER-0037`, `SR-VER-0038`, `SR-VER-0039`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.f.W – Let it Work

- [ ] **20.f.W** · Position **859/885** · Voraussetzung: `20.e.C`.
**Exakte Commit-Message:** `20.f.W test(acceptance): Work-, Cache- und Sandboxparität aufbauen`

**Umsetzung:** Alle großen Fachoperationen unter constrained/standard, cache off/on und frischer kompatibler Sandbox vollständig abschließen.

**Verhaltensabnahme:** Geteilte Ausführung behält sämtliche Ergebnisse, Pflichtdiagnosen und dieselbe Zielmodellwurzel.

#### 20.f.R – Make it Right

- [ ] **20.f.R** · Position **860/885** · Voraussetzung: `20.f.W`.
**Exakte Commit-Message:** `20.f.R test(acceptance): Work-, Cache- und Sandboxparität vervollständigen`

**Vervollständigung:** Veränderte Bytes bei gleicher Größe/mtime, manipulierte Caches und reine Preflightwiederholung als vermeintlichen Fortschritt erkennen.

**Verhaltensabnahme:** Fortsetzen bis abgeschlossen oder echter Blocker; keine willkürliche Maximalzahl weicher Budgetschritte. Die W-Nachweise bleiben zusätzlich grün.

#### 20.f.C – Make it Clean

- [ ] **20.f.C** · Position **861/885** · Voraussetzung: `20.f.R`.
**Exakte Commit-Message:** `20.f.C refactor(acceptance): Work-, Cache- und Sandboxparität bereinigen`

**Bereinigung:** Gemeinsame Paritätsprojektion auf Fachdaten anwenden, Betriebsmetriken separat vergleichen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-g"></a>
### 20.g – Sicherheits- und Offlinegesamtprüfung

**Anforderungsbezug:** `SR-REQ-0195`–`SR-REQ-0201`, `SR-REQ-0216`, `SR-REQ-0324`, `SR-REQ-0532`, `SR-REQ-0544`–`SR-REQ-0545`, `SR-REQ-0702`–`SR-REQ-0704`.
**Verifikationsbezug:** `SR-VER-0014`, `SR-VER-0018`, `SR-VER-0024`, `SR-VER-0027`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.g.W – Let it Work

- [ ] **20.g.W** · Position **862/885** · Voraussetzung: `20.f.C`.
**Exakte Commit-Message:** `20.g.W test(acceptance): Sicherheits- und Offlinegesamtprüfung aufbauen`

**Umsetzung:** Core und Zusatzworker mit bösartigen Pfaden, Archiven, XML, Texten und Deskriptoren in netzwerkisolierter nichtprivilegierter Umgebung prüfen.

**Verhaltensabnahme:** Zulässige Arbeit benötigt keine heimlichen Downloads, fremde Shell oder Projektcodeausführung.

#### 20.g.R – Make it Right

- [ ] **20.g.R** · Position **863/885** · Voraussetzung: `20.g.W`.
**Exakte Commit-Message:** `20.g.R test(acceptance): Sicherheits- und Offlinegesamtprüfung vervollständigen`

**Vervollständigung:** Geheimnisse, fremde Dateien, Gitzustand und unerlaubte Prozess-/Netzwerkressourcen bleiben geschützt.

**Verhaltensabnahme:** Sicherheitsblockaden werden als Verhalten nachgewiesen, nicht durch Behauptung in Dokumentation. Die W-Nachweise bleiben zusätzlich grün.

#### 20.g.C – Make it Clean

- [ ] **20.g.C** · Position **864/885** · Voraussetzung: `20.g.R`.
**Exakte Commit-Message:** `20.g.C refactor(acceptance): Sicherheits- und Offlinegesamtprüfung bereinigen`

**Bereinigung:** Angriffskorpus mit gemeinsamen I/O-Grenzen abgleichen und redundant gefährliche Sonderpfade entfernen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-h"></a>
### 20.h – Python- und Distributionsmatrix

**Anforderungsbezug:** `SR-REQ-0223`–`SR-REQ-0227`, `SR-REQ-0229`–`SR-REQ-0230`, `SR-REQ-0392`.
**Verifikationsbezug:** `SR-VER-0017`, `SR-VER-0027`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.h.W – Let it Work

- [ ] **20.h.W** · Position **865/885** · Voraussetzung: `20.g.C`.
**Exakte Commit-Message:** `20.h.W test(acceptance): Python- und Distributionsmatrix aufbauen`

**Umsetzung:** Dependency-freies Modul und Core-Zipapp unter CPython 3.10 bis 3.14 auf Linux x86-64 tatsächlich prüfen.

**Verhaltensabnahme:** Beide Distributionsformen funktionieren ohne venv-Aktivierung, Paketmanager, Rootrechte oder Netz.

#### 20.h.R – Make it Right

- [ ] **20.h.R** · Position **866/885** · Voraussetzung: `20.h.W`.
**Exakte Commit-Message:** `20.h.R test(acceptance): Python- und Distributionsmatrix vervollständigen`

**Vervollständigung:** Fehlende Plattform-/ABI-Prüfung bleibt offen; Ubuntu/aarch64-Pixeltests sind Zusatznachweis und kein Ersatz der Referenzmatrix.

**Verhaltensabnahme:** Öffentliche Operationen zeigen gleiche Fachwirkung unabhängig von Aufrufform und frischem Arbeitsverzeichnis. Die W-Nachweise bleiben zusätzlich grün.

#### 20.h.C – Make it Clean

- [ ] **20.h.C** · Position **867/885** · Voraussetzung: `20.h.R`.
**Exakte Commit-Message:** `20.h.C refactor(acceptance): Python- und Distributionsmatrix bereinigen`

**Bereinigung:** Matrixjobs mit gemeinsamem Testharness und getrennten aussagekräftigen Evidenceobjekten erzeugen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-i"></a>
### 20.i – Standardperformance messen

**Anforderungsbezug:** `SR-REQ-0210`–`SR-REQ-0213`, `SR-REQ-0497`–`SR-REQ-0498`.
**Verifikationsbezug:** `SR-VER-0015`, `SR-VER-0034`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.i.W – Let it Work

- [ ] **20.i.W** · Position **868/885** · Voraussetzung: `20.h.C`.
**Exakte Commit-Message:** `20.i.W test(acceptance): Standardperformance messen aufbauen`

**Umsetzung:** Referenzfixtures mit 1000 Artefakten/5000 Relationen/10 MiB und 10000/50000/100 MiB bereitstellen und messen.

**Verhaltensabnahme:** Validierung hält die spezifizierten 2-/10-Sekunden-Ziele und RSS-Grenzen ein; Abfrage-/Trace-/Impactziele bleiben separat prüfbar.

#### 20.i.R – Make it Right

- [ ] **20.i.R** · Position **869/885** · Voraussetzung: `20.i.W`.
**Exakte Commit-Message:** `20.i.R test(acceptance): Standardperformance messen vervollständigen`

**Vervollständigung:** Referenzplattform, Messmethode, Governor, LC_ALL=C, TZ=UTC und Fixturehashes dokumentierte Messdaten statt Annahmen.

**Verhaltensabnahme:** Tatsächliche Zahlen nach §14 erfassen; Benchmarkziel nicht als produktiven pauschalen Hardtimeout implementieren. Die W-Nachweise bleiben zusätzlich grün.

#### 20.i.C – Make it Clean

- [ ] **20.i.C** · Position **870/885** · Voraussetzung: `20.i.R`.
**Exakte Commit-Message:** `20.i.C refactor(acceptance): Standardperformance messen bereinigen`

**Bereinigung:** Datengeneratoren und Messadapter testseitig bündeln, nicht in den Core ziehen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-j"></a>
### 20.j – Constrained-Start und Low-Resource-Abnahme

**Anforderungsbezug:** `SR-REQ-0579`–`SR-REQ-0581`.
**Verifikationsbezug:** `SR-VER-0037`, `SR-VER-0038`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.j.W – Let it Work

- [ ] **20.j.W** · Position **871/885** · Voraussetzung: `20.i.C`.
**Exakte Commit-Message:** `20.j.W test(acceptance): Constrained-Start und Low-Resource-Abnahme aufbauen`

**Umsetzung:** Bootstrap, reinen Preflight und kleine Vollvalidierung exakt gegen §14.6 messen.

**Verhaltensabnahme:** Bootstrap <=200 ms CPU/300 ms Wall/64 MiB; Preflight <=100 ms CPU/150 ms Wall/+16 MiB; kleine Validierung <=2000/3000 ms und 256 MiB.

#### 20.j.R – Make it Right

- [ ] **20.j.R** · Position **872/885** · Voraussetzung: `20.j.W`.
**Exakte Commit-Message:** `20.j.R test(acceptance): Constrained-Start und Low-Resource-Abnahme vervollständigen`

**Vervollständigung:** Median aus fünf Läufen nach Warm-up, kein Einzellauf über doppelter Zeitgrenze; Receiptinventur mit 0 und 100000 Einträgen nicht scannen.

**Verhaltensabnahme:** Low-Resource-Funktionen auf einem Kern, 512-MiB-Hostlimit und 256-MiB-Budget vollständig prüfen, nicht einfach Softbudget-Abbruch als bestanden zählen. Die W-Nachweise bleiben zusätzlich grün.

#### 20.j.C – Make it Clean

- [ ] **20.j.C** · Position **873/885** · Voraussetzung: `20.j.R`.
**Exakte Commit-Message:** `20.j.C refactor(acceptance): Constrained-Start und Low-Resource-Abnahme bereinigen`

**Bereinigung:** Instrumentierung vom eigentlichen Preflight trennen und Ausgabeinhalte ungetestet lassen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-k"></a>
### 20.k – Reale Offline-Sprachpakete abnehmen

**Anforderungsbezug:** `SR-REQ-0700`–`SR-REQ-0701`, `SR-REQ-0720`–`SR-REQ-0722`.
**Verifikationsbezug:** `SR-VER-0047`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.k.W – Let it Work

- [ ] **20.k.W** · Position **874/885** · Voraussetzung: `20.j.C`.
**Exakte Commit-Message:** `20.k.W test(acceptance): Reale Offline-Sprachpakete abnehmen aufbauen`

**Umsetzung:** Pro unterstützter x86-64-Python-ABI Offlinepaket in frischer Umgebung installieren und realen Sprachkorpus ausführen.

**Verhaltensabnahme:** Paketmanifest, Modellhash, Lizenzzuordnung und tatsächliche Entscheidungs-/Ressourcenresultate stimmen zusammen.

#### 20.k.R – Make it Right

- [ ] **20.k.R** · Position **875/885** · Voraussetzung: `20.k.W`.
**Exakte Commit-Message:** `20.k.R test(acceptance): Reale Offline-Sprachpakete abnehmen vervollständigen`

**Vervollständigung:** Fehlendes Wheel, inkompatibles NumPy und falsches Modell verhindern Zusatzreleasefreigabe.

**Verhaltensabnahme:** Parent-/Worker-RSS und Gesamt-CPU separat gegenüber T.10 prüfen; keine Core-only-Prüfung als Spracherkennungsnachweis verwenden. Die W-Nachweise bleiben zusätzlich grün.

#### 20.k.C – Make it Clean

- [ ] **20.k.C** · Position **876/885** · Voraussetzung: `20.k.R`.
**Exakte Commit-Message:** `20.k.C refactor(acceptance): Reale Offline-Sprachpakete abnehmen bereinigen`

**Bereinigung:** Pakettests und Adaptertests gemeinsam parametrisieren, ohne reale Installation durch Mock zu ersetzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-l"></a>
### 20.l – Bedienbarkeit und Betriebsdokumentation abschließen

**Anforderungsbezug:** `SR-REQ-0181`, `SR-REQ-0186`–`SR-REQ-0187`, `SR-REQ-0191`–`SR-REQ-0193`, `SR-REQ-0221`–`SR-REQ-0222`.
**Verifikationsbezug:** `SR-VER-0013`, `SR-VER-0019`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.l.W – Let it Work

- [ ] **20.l.W** · Position **877/885** · Voraussetzung: `20.k.C`.
**Exakte Commit-Message:** `20.l.W style(acceptance): Bedienbarkeit und Betriebsdokumentation abschließen aufbauen`

**Umsetzung:** Farbige CLI mit konsistenten Phasen, verständlichen Statusangaben und übersichtlichen Abschlüssen manuell durchsehen; Betriebshinweise und Beispiele fertigstellen.

**Verhaltensabnahme:** Kein automatisierter Darstellungs-/Dokutest; fachliche Handler bleiben durch bestehende Verhaltenstests abgesichert.

#### 20.l.R – Make it Right

- [ ] **20.l.R** · Position **878/885** · Voraussetzung: `20.l.W`.
**Exakte Commit-Message:** `20.l.R style(acceptance): Bedienbarkeit und Betriebsdokumentation abschließen vervollständigen`

**Vervollständigung:** Plain-/TTY-/quiet-Nutzung, Fehlerorientierung und kleine Displays praktisch durchsehen; keine Freigabe aus ungeprüfter Darstellung behaupten.

**Verhaltensabnahme:** Manuelle Durchsicht ersetzt weder Fachtests noch den explizit ausgenommenen Output-Golden-Nachweis. Die W-Nachweise bleiben zusätzlich grün.

#### 20.l.C – Make it Clean

- [ ] **20.l.C** · Position **879/885** · Voraussetzung: `20.l.R`.
**Exakte Commit-Message:** `20.l.C refactor(acceptance): Bedienbarkeit und Betriebsdokumentation abschließen bereinigen`

**Bereinigung:** Redundante Präsentations-/Hilfetexte konsolidieren, ohne neue Fachanforderungen in Clean zu verstecken.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-m"></a>
### 20.m – Releaseartefakte und reproduzierbare Verpackung

**Anforderungsbezug:** `SR-REQ-0226`, `SR-REQ-0391`–`SR-REQ-0392`, `SR-REQ-0659`, `SR-REQ-0669`, `SR-REQ-0701`.
**Verifikationsbezug:** `SR-VER-0027`, `SR-VER-0045`, `SR-VER-0048`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.m.W – Let it Work

- [ ] **20.m.W** · Position **880/885** · Voraussetzung: `20.l.C`.
**Exakte Commit-Message:** `20.m.W build(acceptance): Releaseartefakte und reproduzierbare Verpackung aufbauen`

**Umsetzung:** Releaseversion 0.2.0, Coreartefakte, eingefrorenes Sprachregister, Labelpakete und getrennte Sprachzusatzpakete erzeugen.

**Verhaltensabnahme:** Gepackte Programme enthalten die tatsächlich versionierten Ressourcen und lassen sich offline starten.

#### 20.m.R – Make it Right

- [ ] **20.m.R** · Position **881/885** · Voraussetzung: `20.m.W`.
**Exakte Commit-Message:** `20.m.R build(acceptance): Releaseartefakte und reproduzierbare Verpackung vervollständigen`

**Vervollständigung:** Paketinhalt, Hashmanifest und erlaubte Dateitypen verifizieren; keine privaten Projektdateien, Caches oder Secrets einschleusen.

**Verhaltensabnahme:** Reproduzierbare maschinenlesbare Distributionsbytes und Dateiinventur sind Daten-/Liefervertragsprüfung, keine Dokuprüfung. Die W-Nachweise bleiben zusätzlich grün.

#### 20.m.C – Make it Clean

- [ ] **20.m.C** · Position **882/885** · Voraussetzung: `20.m.R`.
**Exakte Commit-Message:** `20.m.C refactor(acceptance): Releaseartefakte und reproduzierbare Verpackung bereinigen`

**Bereinigung:** Ein Release-Rezept statt abweichender manueller Verpackungspfade nutzen.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

<a id="step-20-n"></a>
### 20.n – Abschlussnachweis und Freigabeentscheidung

**Anforderungsbezug:** `SR-REQ-0493`–`SR-REQ-0496`, `SR-REQ-0500`, `SR-REQ-0650`.
**Verifikationsbezug:** `SR-VER-0034`, `SR-VER-0041`. Die exakten SR-TC-Identitäten stehen in der vollständigen Matrix.

#### 20.n.W – Let it Work

- [ ] **20.n.W** · Position **883/885** · Voraussetzung: `20.m.C`.
**Exakte Commit-Message:** `20.n.W test(acceptance): Abschlussnachweis und Freigabeentscheidung aufbauen`

**Umsetzung:** Ergebnisse aller Gates gegen konkrete Source-/Spec-/Fixture-/Runtimebindungen zusammentragen und offene Punkte explizit ausweisen.

**Verhaltensabnahme:** Produktfreigabe nur bei erfüllten tatsächlich geforderten Verhaltensgates und explizit behandelter TD-001-Abweichung vorbereiten.

#### 20.n.R – Make it Right

- [ ] **20.n.R** · Position **884/885** · Voraussetzung: `20.n.W`.
**Exakte Commit-Message:** `20.n.R test(acceptance): Abschlussnachweis und Freigabeentscheidung vervollständigen`

**Vervollständigung:** Keine autonome menschliche Approvalentscheidung, kein bestandener Test ohne Evidence und kein ungewünschter Gitpush/Tag.

**Verhaltensabnahme:** Planfortschritt, tatsächliche Testnachweise und autorisierte Releaseentscheidung bleiben getrennte Zustände. Die W-Nachweise bleiben zusätzlich grün.

#### 20.n.C – Make it Clean

- [ ] **20.n.C** · Position **885/885** · Voraussetzung: `20.n.R`.
**Exakte Commit-Message:** `20.n.C refactor(acceptance): Abschlussnachweis und Freigabeentscheidung bereinigen`

**Bereinigung:** Abschlussbericht und Freigabedaten aus vorhandenen Nachweisen ableiten; C ändert keine Produktentscheidung.

**Unveränderlich:** Die oben beschriebenen Fachresultate, Fehlerklassen, zulässigen Seiteneffekte und Invarianten bleiben gleich. Keine neuen Features, Sicherheitsausnahmen oder Darstellungs-/Dokumentationstests.

**Regressionsabnahme:** Alle vorhandenen W-/R-Verhaltenstests dieses Schritts und die vom Refactoring betroffenen bisherigen Verhaltenstests erneut ausführen; erwartete Fachwerte nicht passend zum Refactoring umschreiben. Bei reinen Präsentations-/Dokuschritten keine solchen Tests erfinden.

**Meilenstein 20 abgeschlossen erst nach:** letztem C-Commit, bestandenem oben genannten Integrationsgate, vollständiger verfügbarer Verhaltenssuite und nachvollziehbarer Ergebnisbindung. Noch fehlende plattformgebundene Nachweise bleiben als offen markiert und blockieren die jeweilige Freigabe, nicht still die bereits korrekt abgeschlossene lokale Arbeit.

## Anhang A – vollständige Requirement-zu-Schritt-Matrix

Jede der 730 unveränderten Requirement-IDs ist mindestens einem konkreten Schritt zugeordnet. „Federführung“ benennt den fachnahen Hauptschritt, nicht die Behauptung, dass ein querschnittliches Requirement dort bereits releaseweit vollständig bewiesen wäre. Weitere Beiträge, die exakte primäre SR-TC-ID sowie der unveränderte SR-VER-Bezug machen Integrations- und Abnahmearbeit auffindbar. Das sind **Soll-Zuordnungen, keine Coverage-Messergebnisse**. TD-001 gilt auch dort, wo die ursprüngliche SR-TC-Identität einen ausgeschlossenen Darstellungs-/Dokuanteil enthält.

| Requirement | Federführung | Weitere Schritte | Primärer Testfall laut Spec | Verifikationsvertrag laut Spec |
|---|---|---|---|---|
| `SR-REQ-0001` | [7.a](#step-7-a) | — | `SR-TC-0001` | SR-VER-0001 |
| `SR-REQ-0002` | [7.a](#step-7-a) | — | `SR-TC-0002` | SR-VER-0001 |
| `SR-REQ-0003` | [7.a](#step-7-a) | — | `SR-TC-0003` | SR-VER-0001 |
| `SR-REQ-0004` | [2.a](#step-2-a) | — | `SR-TC-0004` | SR-VER-0001 |
| `SR-REQ-0005` | [1.d](#step-1-d) | — | `SR-TC-0005` | SR-VER-0001 |
| `SR-REQ-0006` | [1.d](#step-1-d) | — | `SR-TC-0006` | SR-VER-0001 |
| `SR-REQ-0007` | [2.a](#step-2-a) | — | `SR-TC-0007` | SR-VER-0001 |
| `SR-REQ-0008` | [2.a](#step-2-a) | — | `SR-TC-0008` | SR-VER-0001 |
| `SR-REQ-0009` | [1.d](#step-1-d) | — | `SR-TC-0009` | SR-VER-0001 |
| `SR-REQ-0010` | [2.k](#step-2-k) | — | `SR-TC-0010` | SR-VER-0001 |
| `SR-REQ-0011` | [2.a](#step-2-a) | — | `SR-TC-0011` | SR-VER-0002 |
| `SR-REQ-0012` | [2.b](#step-2-b) | — | `SR-TC-0012` | SR-VER-0002 |
| `SR-REQ-0013` | [2.b](#step-2-b) | — | `SR-TC-0013` | SR-VER-0002 |
| `SR-REQ-0014` | [2.c](#step-2-c) | — | `SR-TC-0014` | SR-VER-0002 |
| `SR-REQ-0015` | [2.b](#step-2-b) | — | `SR-TC-0015` | SR-VER-0002 |
| `SR-REQ-0016` | [2.b](#step-2-b) | — | `SR-TC-0016` | SR-VER-0002 |
| `SR-REQ-0017` | [2.b](#step-2-b) | — | `SR-TC-0017` | SR-VER-0002 |
| `SR-REQ-0018` | [2.f](#step-2-f) | — | `SR-TC-0018` | SR-VER-0002 |
| `SR-REQ-0019` | [2.f](#step-2-f) | — | `SR-TC-0019` | SR-VER-0002 |
| `SR-REQ-0020` | [2.j](#step-2-j) | — | `SR-TC-0020` | SR-VER-0002 |
| `SR-REQ-0021` | [2.k](#step-2-k) | — | `SR-TC-0021` | SR-VER-0002 |
| `SR-REQ-0022` | [2.a](#step-2-a) | — | `SR-TC-0022` | SR-VER-0002 |
| `SR-REQ-0023` | [2.a](#step-2-a) | — | `SR-TC-0023` | SR-VER-0002 |
| `SR-REQ-0024` | [2.k](#step-2-k) | — | `SR-TC-0024` | SR-VER-0002 |
| `SR-REQ-0025` | [2.k](#step-2-k) | — | `SR-TC-0025` | SR-VER-0002 |
| `SR-REQ-0026` | [2.g](#step-2-g) | — | `SR-TC-0026` | SR-VER-0018 |
| `SR-REQ-0027` | [2.g](#step-2-g) | — | `SR-TC-0027` | SR-VER-0003 |
| `SR-REQ-0028` | [2.g](#step-2-g) | — | `SR-TC-0028` | SR-VER-0003 |
| `SR-REQ-0029` | [2.g](#step-2-g) | — | `SR-TC-0029` | SR-VER-0003 |
| `SR-REQ-0030` | [2.g](#step-2-g) | — | `SR-TC-0030` | SR-VER-0018 |
| `SR-REQ-0031` | [2.g](#step-2-g) | — | `SR-TC-0031` | SR-VER-0003 |
| `SR-REQ-0032` | [2.g](#step-2-g) | — | `SR-TC-0032` | SR-VER-0003 |
| `SR-REQ-0033` | [2.i](#step-2-i) | — | `SR-TC-0033` | SR-VER-0003 |
| `SR-REQ-0034` | [2.i](#step-2-i) | [5.d](#step-5-d) | `SR-TC-0034` | SR-VER-0003 |
| `SR-REQ-0035` | [2.i](#step-2-i) | — | `SR-TC-0035` | SR-VER-0003 |
| `SR-REQ-0036` | [2.i](#step-2-i) | — | `SR-TC-0036` | SR-VER-0003 |
| `SR-REQ-0037` | [2.f](#step-2-f) | — | `SR-TC-0037` | SR-VER-0003 |
| `SR-REQ-0038` | [2.c](#step-2-c) | — | `SR-TC-0038` | SR-VER-0004 |
| `SR-REQ-0039` | [2.c](#step-2-c) | — | `SR-TC-0039` | SR-VER-0004 |
| `SR-REQ-0040` | [2.c](#step-2-c) | — | `SR-TC-0040` | SR-VER-0004 |
| `SR-REQ-0041` | [2.d](#step-2-d) | — | `SR-TC-0041` | SR-VER-0004 |
| `SR-REQ-0042` | [5.e](#step-5-e) | — | `SR-TC-0042` | SR-VER-0004 |
| `SR-REQ-0043` | [5.e](#step-5-e) | — | `SR-TC-0043` | SR-VER-0004 |
| `SR-REQ-0044` | [5.e](#step-5-e) | — | `SR-TC-0044` | SR-VER-0004 |
| `SR-REQ-0045` | [5.e](#step-5-e) | — | `SR-TC-0045` | SR-VER-0004 |
| `SR-REQ-0046` | [5.e](#step-5-e) | — | `SR-TC-0046` | SR-VER-0004 |
| `SR-REQ-0047` | [5.e](#step-5-e) | — | `SR-TC-0047` | SR-VER-0004 |
| `SR-REQ-0048` | [5.e](#step-5-e) | — | `SR-TC-0048` | SR-VER-0004 |
| `SR-REQ-0049` | [2.d](#step-2-d) | — | `SR-TC-0049` | SR-VER-0004 |
| `SR-REQ-0050` | [2.d](#step-2-d) | — | `SR-TC-0050` | SR-VER-0004 |
| `SR-REQ-0051` | [5.e](#step-5-e) | — | `SR-TC-0051` | SR-VER-0004 |
| `SR-REQ-0052` | [3.a](#step-3-a) | — | `SR-TC-0052` | SR-VER-0021 |
| `SR-REQ-0053` | [3.a](#step-3-a) | — | `SR-TC-0053` | SR-VER-0005 |
| `SR-REQ-0054` | [3.b](#step-3-b) | — | `SR-TC-0054` | SR-VER-0005 |
| `SR-REQ-0055` | [3.b](#step-3-b) | — | `SR-TC-0055` | SR-VER-0005 |
| `SR-REQ-0056` | [3.b](#step-3-b) | — | `SR-TC-0056` | SR-VER-0005 |
| `SR-REQ-0057` | [3.c](#step-3-c) | — | `SR-TC-0057` | SR-VER-0021 |
| `SR-REQ-0058` | [3.c](#step-3-c) | — | `SR-TC-0058` | SR-VER-0005 |
| `SR-REQ-0059` | [3.d](#step-3-d) | — | `SR-TC-0059` | SR-VER-0005 |
| `SR-REQ-0060` | [3.b](#step-3-b) | — | `SR-TC-0060` | SR-VER-0005 |
| `SR-REQ-0061` | [3.k](#step-3-k) | — | `SR-TC-0061` | SR-VER-0005 |
| `SR-REQ-0062` | [3.k](#step-3-k) | — | `SR-TC-0062` | SR-VER-0005 |
| `SR-REQ-0063` | [3.k](#step-3-k) | — | `SR-TC-0063` | SR-VER-0005 |
| `SR-REQ-0064` | [8.f](#step-8-f) | — | `SR-TC-0064` | SR-VER-0005 |
| `SR-REQ-0065` | [3.k](#step-3-k) | — | `SR-TC-0065` | SR-VER-0005 |
| `SR-REQ-0066` | [2.m](#step-2-m) | — | `SR-TC-0066` | SR-VER-0006 |
| `SR-REQ-0067` | [2.m](#step-2-m) | — | `SR-TC-0067` | SR-VER-0006 |
| `SR-REQ-0068` | [2.m](#step-2-m) | — | `SR-TC-0068` | SR-VER-0044 |
| `SR-REQ-0069` | [2.m](#step-2-m) | — | `SR-TC-0069` | SR-VER-0044 |
| `SR-REQ-0070` | [4.q](#step-4-q) | — | `SR-TC-0070` | SR-VER-0006 |
| `SR-REQ-0071` | [2.m](#step-2-m) | — | `SR-TC-0071` | SR-VER-0044 |
| `SR-REQ-0072` | [4.q](#step-4-q) | — | `SR-TC-0072` | SR-VER-0006 |
| `SR-REQ-0073` | [2.m](#step-2-m) | — | `SR-TC-0073` | SR-VER-0006 |
| `SR-REQ-0074` | [2.m](#step-2-m) | — | `SR-TC-0074` | SR-VER-0006 |
| `SR-REQ-0075` | [2.m](#step-2-m) | — | `SR-TC-0075` | SR-VER-0006 |
| `SR-REQ-0076` | [2.m](#step-2-m) | — | `SR-TC-0076` | SR-VER-0006 |
| `SR-REQ-0077` | [4.q](#step-4-q) | — | `SR-TC-0077` | SR-VER-0006 |
| `SR-REQ-0078` | [4.q](#step-4-q) | — | `SR-TC-0078` | SR-VER-0006 |
| `SR-REQ-0079` | [4.j](#step-4-j) | — | `SR-TC-0079` | SR-VER-0006 |
| `SR-REQ-0080` | [4.j](#step-4-j) | — | `SR-TC-0080` | SR-VER-0045 |
| `SR-REQ-0081` | [4.l](#step-4-l) | — | `SR-TC-0081` | SR-VER-0006 |
| `SR-REQ-0082` | [4.l](#step-4-l) | — | `SR-TC-0082` | SR-VER-0045 |
| `SR-REQ-0083` | [4.o](#step-4-o) | — | `SR-TC-0083` | SR-VER-0007 |
| `SR-REQ-0084` | [4.o](#step-4-o) | — | `SR-TC-0084` | SR-VER-0007 |
| `SR-REQ-0085` | [4.o](#step-4-o) | — | `SR-TC-0085` | SR-VER-0007 |
| `SR-REQ-0086` | [4.o](#step-4-o) | — | `SR-TC-0086` | SR-VER-0007 |
| `SR-REQ-0087` | [4.p](#step-4-p) | — | `SR-TC-0087` | SR-VER-0007 |
| `SR-REQ-0088` | [4.p](#step-4-p) | — | `SR-TC-0088` | SR-VER-0007 |
| `SR-REQ-0089` | [4.p](#step-4-p) | — | `SR-TC-0089` | SR-VER-0007 |
| `SR-REQ-0090` | [4.p](#step-4-p) | — | `SR-TC-0090` | SR-VER-0007 |
| `SR-REQ-0091` | [4.p](#step-4-p) | — | `SR-TC-0091` | SR-VER-0007 |
| `SR-REQ-0092` | [4.p](#step-4-p) | — | `SR-TC-0092` | SR-VER-0007 |
| `SR-REQ-0093` | [1.d](#step-1-d) | — | `SR-TC-0093` | SR-VER-0007 |
| `SR-REQ-0094` | [1.d](#step-1-d) | — | `SR-TC-0094` | SR-VER-0007 |
| `SR-REQ-0095` | [4.l](#step-4-l) | — | `SR-TC-0095` | SR-VER-0007 |
| `SR-REQ-0096` | [4.l](#step-4-l) | — | `SR-TC-0096` | SR-VER-0007 |
| `SR-REQ-0097` | [4.l](#step-4-l) | — | `SR-TC-0097` | SR-VER-0007 |
| `SR-REQ-0098` | [4.p](#step-4-p) | — | `SR-TC-0098` | SR-VER-0007 |
| `SR-REQ-0099` | [4.p](#step-4-p) | — | `SR-TC-0099` | SR-VER-0007 |
| `SR-REQ-0100` | [4.r](#step-4-r) | — | `SR-TC-0100` | SR-VER-0007 |
| `SR-REQ-0101` | [11.m](#step-11-m) | [13.h](#step-13-h) | `SR-TC-0101` | SR-VER-0008 |
| `SR-REQ-0102` | [11.m](#step-11-m) | — | `SR-TC-0102` | SR-VER-0008 |
| `SR-REQ-0103` | [11.m](#step-11-m) | — | `SR-TC-0103` | SR-VER-0008 |
| `SR-REQ-0104` | [11.m](#step-11-m) | — | `SR-TC-0104` | SR-VER-0008 |
| `SR-REQ-0105` | [11.m](#step-11-m) | — | `SR-TC-0105` | SR-VER-0008 |
| `SR-REQ-0106` | [11.m](#step-11-m) | — | `SR-TC-0106` | SR-VER-0008 |
| `SR-REQ-0107` | [11.q](#step-11-q) | [13.h](#step-13-h) | `SR-TC-0107` | SR-VER-0008 |
| `SR-REQ-0108` | [8.a](#step-8-a) | — | `SR-TC-0108` | SR-VER-0008 |
| `SR-REQ-0109` | [8.b](#step-8-b) | — | `SR-TC-0109` | SR-VER-0008 |
| `SR-REQ-0110` | [8.b](#step-8-b) | — | `SR-TC-0110` | SR-VER-0008 |
| `SR-REQ-0111` | [8.e](#step-8-e) | — | `SR-TC-0111` | SR-VER-0008 |
| `SR-REQ-0112` | [8.f](#step-8-f) | — | `SR-TC-0112` | SR-VER-0008 |
| `SR-REQ-0113` | [3.j](#step-3-j) | [8.g](#step-8-g) | `SR-TC-0113` | SR-VER-0008 |
| `SR-REQ-0114` | [8.j](#step-8-j) | [10.f](#step-10-f), [15.h](#step-15-h) | `SR-TC-0114` | SR-VER-0008 |
| `SR-REQ-0115` | [3.j](#step-3-j) | [8.h](#step-8-h) | `SR-TC-0115` | SR-VER-0008 |
| `SR-REQ-0116` | [3.j](#step-3-j) | [8.h](#step-8-h) | `SR-TC-0116` | SR-VER-0008 |
| `SR-REQ-0117` | [4.r](#step-4-r) | [8.l](#step-8-l) | `SR-TC-0117` | SR-VER-0008 |
| `SR-REQ-0118` | [2.d](#step-2-d) | — | `SR-TC-0118` | SR-VER-0009 |
| `SR-REQ-0119` | [2.d](#step-2-d) | [13.a](#step-13-a) | `SR-TC-0119` | SR-VER-0009 |
| `SR-REQ-0120` | [2.d](#step-2-d) | [13.a](#step-13-a) | `SR-TC-0120` | SR-VER-0009 |
| `SR-REQ-0121` | [13.a](#step-13-a) | — | `SR-TC-0121` | SR-VER-0009 |
| `SR-REQ-0122` | [13.c](#step-13-c) | [13.h](#step-13-h) | `SR-TC-0122` | SR-VER-0009 |
| `SR-REQ-0123` | [13.c](#step-13-c) | — | `SR-TC-0123` | SR-VER-0009 |
| `SR-REQ-0124` | [13.d](#step-13-d) | — | `SR-TC-0124` | SR-VER-0009 |
| `SR-REQ-0125` | [13.f](#step-13-f) | — | `SR-TC-0125` | SR-VER-0009 |
| `SR-REQ-0126` | [13.e](#step-13-e) | — | `SR-TC-0126` | SR-VER-0009 |
| `SR-REQ-0127` | [13.b](#step-13-b) | — | `SR-TC-0127` | SR-VER-0009 |
| `SR-REQ-0128` | [13.c](#step-13-c) | — | `SR-TC-0128` | SR-VER-0009 |
| `SR-REQ-0129` | [12.a](#step-12-a) | — | `SR-TC-0129` | SR-VER-0010 |
| `SR-REQ-0130` | [12.a](#step-12-a) | [12.l](#step-12-l) | `SR-TC-0130` | SR-VER-0010 |
| `SR-REQ-0131` | [12.a](#step-12-a) | — | `SR-TC-0131` | SR-VER-0010 |
| `SR-REQ-0132` | [12.d](#step-12-d) | — | `SR-TC-0132` | SR-VER-0025 |
| `SR-REQ-0133` | [12.d](#step-12-d) | — | `SR-TC-0133` | SR-VER-0025 |
| `SR-REQ-0134` | [2.l](#step-2-l) | — | `SR-TC-0134` | SR-VER-0010 |
| `SR-REQ-0135` | [2.l](#step-2-l) | — | `SR-TC-0135` | SR-VER-0014 |
| `SR-REQ-0136` | [12.k](#step-12-k) | [12.m](#step-12-m), [12.o](#step-12-o) | `SR-TC-0136` | SR-VER-0010 |
| `SR-REQ-0137` | [12.c](#step-12-c) | — | `SR-TC-0137` | SR-VER-0010 |
| `SR-REQ-0138` | [12.b](#step-12-b) | — | `SR-TC-0138` | SR-VER-0010 |
| `SR-REQ-0139` | [12.p](#step-12-p) | — | `SR-TC-0139` | SR-VER-0010 |
| `SR-REQ-0140` | [12.p](#step-12-p) | — | `SR-TC-0140` | SR-VER-0010 |
| `SR-REQ-0141` | [12.p](#step-12-p) | — | `SR-TC-0141` | SR-VER-0010 |
| `SR-REQ-0142` | [12.d](#step-12-d) | — | `SR-TC-0142` | SR-VER-0010 |
| `SR-REQ-0143` | [10.a](#step-10-a) | [10.i](#step-10-i) | `SR-TC-0143` | SR-VER-0011 |
| `SR-REQ-0144` | [10.b](#step-10-b) | — | `SR-TC-0144` | SR-VER-0011 |
| `SR-REQ-0145` | [10.a](#step-10-a) | — | `SR-TC-0145` | SR-VER-0011 |
| `SR-REQ-0146` | [10.b](#step-10-b) | — | `SR-TC-0146` | SR-VER-0011 |
| `SR-REQ-0147` | [10.b](#step-10-b) | — | `SR-TC-0147` | SR-VER-0011 |
| `SR-REQ-0148` | [10.a](#step-10-a) | [10.i](#step-10-i) | `SR-TC-0148` | SR-VER-0011 |
| `SR-REQ-0149` | [10.c](#step-10-c) | [10.i](#step-10-i) | `SR-TC-0149` | SR-VER-0011 |
| `SR-REQ-0150` | [10.h](#step-10-h) | [13.g](#step-13-g) | `SR-TC-0150` | SR-VER-0011 |
| `SR-REQ-0151` | [10.d](#step-10-d) | — | `SR-TC-0151` | SR-VER-0011 |
| `SR-REQ-0152` | [10.f](#step-10-f) | — | `SR-TC-0152` | SR-VER-0011 |
| `SR-REQ-0153` | [10.e](#step-10-e) | — | `SR-TC-0153` | SR-VER-0011 |
| `SR-REQ-0154` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0154` | SR-VER-0012 |
| `SR-REQ-0155` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0155` | SR-VER-0012 |
| `SR-REQ-0156` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0156` | SR-VER-0012 |
| `SR-REQ-0157` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0157` | SR-VER-0012 |
| `SR-REQ-0158` | [18.b](#step-18-b) | [18.p](#step-18-p) | `SR-TC-0158` | SR-VER-0012 |
| `SR-REQ-0159` | [18.c](#step-18-c) | [18.p](#step-18-p) | `SR-TC-0159` | SR-VER-0012 |
| `SR-REQ-0160` | [18.e](#step-18-e) | [5.b](#step-5-b), [18.p](#step-18-p) | `SR-TC-0160` | SR-VER-0012 |
| `SR-REQ-0161` | [18.e](#step-18-e) | [5.j](#step-5-j), [18.p](#step-18-p) | `SR-TC-0161` | SR-VER-0012 |
| `SR-REQ-0162` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0162` | SR-VER-0012 |
| `SR-REQ-0163` | [18.a](#step-18-a) | [18.p](#step-18-p) | `SR-TC-0163` | SR-VER-0012 |
| `SR-REQ-0164` | [18.f](#step-18-f) | [18.p](#step-18-p) | `SR-TC-0164` | SR-VER-0012 |
| `SR-REQ-0165` | [18.f](#step-18-f) | [18.p](#step-18-p) | `SR-TC-0165` | SR-VER-0012 |
| `SR-REQ-0166` | [18.g](#step-18-g) | [18.p](#step-18-p) | `SR-TC-0166` | SR-VER-0012 |
| `SR-REQ-0167` | [18.g](#step-18-g) | [18.p](#step-18-p) | `SR-TC-0167` | SR-VER-0012 |
| `SR-REQ-0168` | [18.g](#step-18-g) | [18.p](#step-18-p) | `SR-TC-0168` | SR-VER-0014 |
| `SR-REQ-0169` | [18.g](#step-18-g) | [18.p](#step-18-p) | `SR-TC-0169` | SR-VER-0012 |
| `SR-REQ-0170` | [18.g](#step-18-g) | [18.p](#step-18-p) | `SR-TC-0170` | SR-VER-0012 |
| `SR-REQ-0171` | [18.i](#step-18-i) | [18.j](#step-18-j), [18.p](#step-18-p) | `SR-TC-0171` | SR-VER-0012 |
| `SR-REQ-0172` | [18.i](#step-18-i) | [18.p](#step-18-p) | `SR-TC-0172` | SR-VER-0012 |
| `SR-REQ-0173` | [18.i](#step-18-i) | [18.j](#step-18-j), [18.k](#step-18-k), [18.p](#step-18-p) | `SR-TC-0173` | SR-VER-0012 |
| `SR-REQ-0174` | [18.k](#step-18-k) | [18.p](#step-18-p) | `SR-TC-0174` | SR-VER-0012 |
| `SR-REQ-0175` | [18.k](#step-18-k) | [5.m](#step-5-m), [18.p](#step-18-p) | `SR-TC-0175` | SR-VER-0019 |
| `SR-REQ-0176` | [18.n](#step-18-n) | [18.p](#step-18-p) | `SR-TC-0176` | SR-VER-0012 |
| `SR-REQ-0177` | [18.l](#step-18-l) | [18.n](#step-18-n), [18.p](#step-18-p) | `SR-TC-0177` | SR-VER-0012 |
| `SR-REQ-0178` | [18.g](#step-18-g) | [18.k](#step-18-k), [18.p](#step-18-p) | `SR-TC-0178` | SR-VER-0012 |
| `SR-REQ-0179` | [18.m](#step-18-m) | — | `SR-TC-0179` | SR-VER-0013 |
| `SR-REQ-0180` | [1.c](#step-1-c) | [18.m](#step-18-m) | `SR-TC-0180` | SR-VER-0013 |
| `SR-REQ-0181` | [1.f](#step-1-f) | [20.l](#step-20-l) | `SR-TC-0181` | SR-VER-0013 |
| `SR-REQ-0182` | [1.e](#step-1-e) | — | `SR-TC-0182` | SR-VER-0013 |
| `SR-REQ-0183` | [1.e](#step-1-e) | — | `SR-TC-0183` | SR-VER-0013 |
| `SR-REQ-0184` | [1.e](#step-1-e) | — | `SR-TC-0184` | SR-VER-0013 |
| `SR-REQ-0185` | [1.e](#step-1-e) | — | `SR-TC-0185` | SR-VER-0013 |
| `SR-REQ-0186` | [1.f](#step-1-f) | [20.l](#step-20-l) | `SR-TC-0186` | SR-VER-0013 |
| `SR-REQ-0187` | [1.f](#step-1-f) | [20.l](#step-20-l) | `SR-TC-0187` | SR-VER-0013 |
| `SR-REQ-0188` | [4.r](#step-4-r) | — | `SR-TC-0188` | SR-VER-0013 |
| `SR-REQ-0189` | [5.m](#step-5-m) | — | `SR-TC-0189` | SR-VER-0019 |
| `SR-REQ-0190` | [1.l](#step-1-l) | — | `SR-TC-0190` | SR-VER-0013 |
| `SR-REQ-0191` | [8.i](#step-8-i) | [20.l](#step-20-l) | `SR-TC-0191` | SR-VER-0013 |
| `SR-REQ-0192` | [5.j](#step-5-j) | [20.l](#step-20-l) | `SR-TC-0192` | SR-VER-0013 |
| `SR-REQ-0193` | [8.k](#step-8-k) | [20.l](#step-20-l) | `SR-TC-0193` | SR-VER-0013 |
| `SR-REQ-0194` | [1.i](#step-1-i) | — | `SR-TC-0194` | SR-VER-0013 |
| `SR-REQ-0195` | [1.j](#step-1-j) | [18.g](#step-18-g), [20.g](#step-20-g) | `SR-TC-0195` | SR-VER-0014 |
| `SR-REQ-0196` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0196` | SR-VER-0014 |
| `SR-REQ-0197` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0197` | SR-VER-0014 |
| `SR-REQ-0198` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0198` | SR-VER-0014 |
| `SR-REQ-0199` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0199` | SR-VER-0014 |
| `SR-REQ-0200` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0200` | SR-VER-0014 |
| `SR-REQ-0201` | [1.j](#step-1-j) | [18.n](#step-18-n), [20.g](#step-20-g) | `SR-TC-0201` | SR-VER-0014 |
| `SR-REQ-0202` | [6.c](#step-6-c) | — | `SR-TC-0202` | SR-VER-0014 |
| `SR-REQ-0203` | [6.c](#step-6-c) | — | `SR-TC-0203` | SR-VER-0014 |
| `SR-REQ-0204` | [5.m](#step-5-m) | [20.b](#step-20-b) | `SR-TC-0204` | SR-VER-0019 |
| `SR-REQ-0205` | [5.i](#step-5-i) | — | `SR-TC-0205` | SR-VER-0019 |
| `SR-REQ-0206` | [5.i](#step-5-i) | — | `SR-TC-0206` | SR-VER-0019 |
| `SR-REQ-0207` | [2.j](#step-2-j) | — | `SR-TC-0207` | SR-VER-0015 |
| `SR-REQ-0208` | [2.j](#step-2-j) | — | `SR-TC-0208` | SR-VER-0015 |
| `SR-REQ-0209` | [1.b](#step-1-b) | — | `SR-TC-0209` | SR-VER-0027 |
| `SR-REQ-0210` | [20.i](#step-20-i) | — | `SR-TC-0210` | SR-VER-0015 |
| `SR-REQ-0211` | [20.i](#step-20-i) | — | `SR-TC-0211` | SR-VER-0015 |
| `SR-REQ-0212` | [20.i](#step-20-i) | — | `SR-TC-0212` | SR-VER-0015 |
| `SR-REQ-0213` | [8.l](#step-8-l) | [20.i](#step-20-i) | `SR-TC-0213` | SR-VER-0015 |
| `SR-REQ-0214` | [1.e](#step-1-e) | — | `SR-TC-0214` | SR-VER-0013 |
| `SR-REQ-0215` | [1.g](#step-1-g) | — | `SR-TC-0215` | SR-VER-0016 |
| `SR-REQ-0216` | [7.c](#step-7-c) | [20.g](#step-20-g) | `SR-TC-0216` | SR-VER-0018 |
| `SR-REQ-0217` | [7.c](#step-7-c) | [20.b](#step-20-b) | `SR-TC-0217` | SR-VER-0018 |
| `SR-REQ-0218` | [7.f](#step-7-f) | — | `SR-TC-0218` | SR-VER-0018 |
| `SR-REQ-0219` | [18.l](#step-18-l) | — | `SR-TC-0219` | SR-VER-0012 |
| `SR-REQ-0220` | [10.e](#step-10-e) | — | `SR-TC-0220` | SR-VER-0011 |
| `SR-REQ-0221` | [5.i](#step-5-i) | [20.l](#step-20-l) | `SR-TC-0221` | SR-VER-0019 |
| `SR-REQ-0222` | [1.f](#step-1-f) | [20.l](#step-20-l) | `SR-TC-0222` | SR-VER-0013 |
| `SR-REQ-0223` | [1.a](#step-1-a) | [20.h](#step-20-h) | `SR-TC-0223` | SR-VER-0027 |
| `SR-REQ-0224` | [1.a](#step-1-a) | [20.h](#step-20-h) | `SR-TC-0224` | SR-VER-0027 |
| `SR-REQ-0225` | [1.a](#step-1-a) | [20.h](#step-20-h) | `SR-TC-0225` | SR-VER-0017 |
| `SR-REQ-0226` | [1.b](#step-1-b) | [20.h](#step-20-h), [20.m](#step-20-m) | `SR-TC-0226` | SR-VER-0027 |
| `SR-REQ-0227` | [1.l](#step-1-l) | [20.h](#step-20-h) | `SR-TC-0227` | SR-VER-0027 |
| `SR-REQ-0228` | [18.m](#step-18-m) | — | `SR-TC-0228` | SR-VER-0017 |
| `SR-REQ-0229` | [1.a](#step-1-a) | [20.h](#step-20-h) | `SR-TC-0229` | SR-VER-0017 |
| `SR-REQ-0230` | [20.h](#step-20-h) | — | `SR-TC-0230` | SR-VER-0027 |
| `SR-REQ-0231` | [5.a](#step-5-a) | — | `SR-TC-0231` | SR-VER-0018 |
| `SR-REQ-0232` | [5.b](#step-5-b) | [7.d](#step-7-d) | `SR-TC-0232` | SR-VER-0018 |
| `SR-REQ-0233` | [7.e](#step-7-e) | — | `SR-TC-0233` | SR-VER-0018 |
| `SR-REQ-0234` | [7.e](#step-7-e) | — | `SR-TC-0234` | SR-VER-0018 |
| `SR-REQ-0235` | [7.f](#step-7-f) | — | `SR-TC-0235` | SR-VER-0018 |
| `SR-REQ-0236` | [5.h](#step-5-h) | — | `SR-TC-0236` | SR-VER-0018 |
| `SR-REQ-0237` | [5.g](#step-5-g) | — | `SR-TC-0237` | SR-VER-0018 |
| `SR-REQ-0238` | [5.f](#step-5-f) | — | `SR-TC-0238` | SR-VER-0018 |
| `SR-REQ-0239` | [5.c](#step-5-c) | — | `SR-TC-0239` | SR-VER-0018 |
| `SR-REQ-0240` | [7.b](#step-7-b) | — | `SR-TC-0240` | SR-VER-0018 |
| `SR-REQ-0241` | [5.n](#step-5-n) | [7.k](#step-7-k) | `SR-TC-0241` | SR-VER-0018 |
| `SR-REQ-0242` | [18.m](#step-18-m) | — | `SR-TC-0242` | SR-VER-0018 |
| `SR-REQ-0243` | [5.g](#step-5-g) | — | `SR-TC-0243` | SR-VER-0018 |
| `SR-REQ-0244` | [2.g](#step-2-g) | — | `SR-TC-0244` | SR-VER-0018 |
| `SR-REQ-0245` | [2.g](#step-2-g) | — | `SR-TC-0245` | SR-VER-0018 |
| `SR-REQ-0246` | [2.g](#step-2-g) | — | `SR-TC-0246` | SR-VER-0018 |
| `SR-REQ-0247` | [16.b](#step-16-b) | — | `SR-TC-0247` | SR-VER-0018 |
| `SR-REQ-0248` | [2.h](#step-2-h) | — | `SR-TC-0248` | SR-VER-0018 |
| `SR-REQ-0249` | [2.g](#step-2-g) | — | `SR-TC-0249` | SR-VER-0018 |
| `SR-REQ-0250` | [2.h](#step-2-h) | — | `SR-TC-0250` | SR-VER-0026 |
| `SR-REQ-0251` | [2.f](#step-2-f) | — | `SR-TC-0251` | SR-VER-0018 |
| `SR-REQ-0252` | [5.k](#step-5-k) | [20.e](#step-20-e) | `SR-TC-0252` | SR-VER-0019 |
| `SR-REQ-0253` | [5.k](#step-5-k) | [20.e](#step-20-e) | `SR-TC-0253` | SR-VER-0019 |
| `SR-REQ-0254` | [5.l](#step-5-l) | [20.e](#step-20-e) | `SR-TC-0254` | SR-VER-0019 |
| `SR-REQ-0255` | [5.m](#step-5-m) | [20.e](#step-20-e) | `SR-TC-0255` | SR-VER-0019 |
| `SR-REQ-0256` | [5.t](#step-5-t) | [20.e](#step-20-e) | `SR-TC-0256` | SR-VER-0019 |
| `SR-REQ-0257` | [5.p](#step-5-p) | [20.e](#step-20-e) | `SR-TC-0257` | SR-VER-0019 |
| `SR-REQ-0258` | [5.q](#step-5-q) | [20.e](#step-20-e) | `SR-TC-0258` | SR-VER-0019 |
| `SR-REQ-0259` | [5.n](#step-5-n) | [20.e](#step-20-e) | `SR-TC-0259` | SR-VER-0019 |
| `SR-REQ-0260` | [5.s](#step-5-s) | [20.e](#step-20-e) | `SR-TC-0260` | SR-VER-0019 |
| `SR-REQ-0261` | [5.v](#step-5-v) | [20.e](#step-20-e) | `SR-TC-0261` | SR-VER-0019 |
| `SR-REQ-0262` | [5.p](#step-5-p) | [20.e](#step-20-e) | `SR-TC-0262` | SR-VER-0019 |
| `SR-REQ-0263` | [16.a](#step-16-a) | [16.c](#step-16-c) | `SR-TC-0263` | SR-VER-0020 |
| `SR-REQ-0264` | [16.a](#step-16-a) | [16.c](#step-16-c) | `SR-TC-0264` | SR-VER-0020 |
| `SR-REQ-0265` | [16.a](#step-16-a) | — | `SR-TC-0265` | SR-VER-0020 |
| `SR-REQ-0266` | [16.d](#step-16-d) | — | `SR-TC-0266` | SR-VER-0020 |
| `SR-REQ-0267` | [16.i](#step-16-i) | — | `SR-TC-0267` | SR-VER-0020 |
| `SR-REQ-0268` | [16.h](#step-16-h) | — | `SR-TC-0268` | SR-VER-0020 |
| `SR-REQ-0269` | [16.h](#step-16-h) | — | `SR-TC-0269` | SR-VER-0020 |
| `SR-REQ-0270` | [16.i](#step-16-i) | — | `SR-TC-0270` | SR-VER-0020 |
| `SR-REQ-0271` | [16.k](#step-16-k) | — | `SR-TC-0271` | SR-VER-0020 |
| `SR-REQ-0272` | [16.b](#step-16-b) | [16.e](#step-16-e) | `SR-TC-0272` | SR-VER-0020 |
| `SR-REQ-0273` | [16.f](#step-16-f) | — | `SR-TC-0273` | SR-VER-0020 |
| `SR-REQ-0274` | [16.a](#step-16-a) | — | `SR-TC-0274` | SR-VER-0020 |
| `SR-REQ-0275` | [7.g](#step-7-g) | — | `SR-TC-0275` | SR-VER-0021 |
| `SR-REQ-0276` | [7.h](#step-7-h) | — | `SR-TC-0276` | SR-VER-0021 |
| `SR-REQ-0277` | [7.h](#step-7-h) | — | `SR-TC-0277` | SR-VER-0021 |
| `SR-REQ-0278` | [7.i](#step-7-i) | — | `SR-TC-0278` | SR-VER-0021 |
| `SR-REQ-0279` | [7.h](#step-7-h) | — | `SR-TC-0279` | SR-VER-0021 |
| `SR-REQ-0280` | [7.h](#step-7-h) | — | `SR-TC-0280` | SR-VER-0021 |
| `SR-REQ-0281` | [7.j](#step-7-j) | — | `SR-TC-0281` | SR-VER-0021 |
| `SR-REQ-0282` | [7.j](#step-7-j) | — | `SR-TC-0282` | SR-VER-0021 |
| `SR-REQ-0283` | [7.i](#step-7-i) | — | `SR-TC-0283` | SR-VER-0021 |
| `SR-REQ-0284` | [8.g](#step-8-g) | [12.t](#step-12-t) | `SR-TC-0284` | SR-VER-0021 |
| `SR-REQ-0285` | [14.o](#step-14-o) | [16.k](#step-16-k), [17.l](#step-17-l), [18.o](#step-18-o) | `SR-TC-0285` | SR-VER-0021 |
| `SR-REQ-0286` | [4.a](#step-4-a) | — | `SR-TC-0286` | SR-VER-0022 |
| `SR-REQ-0287` | [4.a](#step-4-a) | — | `SR-TC-0287` | SR-VER-0022 |
| `SR-REQ-0288` | [4.c](#step-4-c) | [4.d](#step-4-d) | `SR-TC-0288` | SR-VER-0022 |
| `SR-REQ-0289` | [4.b](#step-4-b) | — | `SR-TC-0289` | SR-VER-0022 |
| `SR-REQ-0290` | [4.b](#step-4-b) | — | `SR-TC-0290` | SR-VER-0022 |
| `SR-REQ-0291` | [4.b](#step-4-b) | — | `SR-TC-0291` | SR-VER-0022 |
| `SR-REQ-0292` | [4.e](#step-4-e) | — | `SR-TC-0292` | SR-VER-0022 |
| `SR-REQ-0293` | [4.f](#step-4-f) | — | `SR-TC-0293` | SR-VER-0022 |
| `SR-REQ-0294` | [4.c](#step-4-c) | — | `SR-TC-0294` | SR-VER-0022 |
| `SR-REQ-0295` | [4.h](#step-4-h) | — | `SR-TC-0295` | SR-VER-0022 |
| `SR-REQ-0296` | [4.h](#step-4-h) | — | `SR-TC-0296` | SR-VER-0022 |
| `SR-REQ-0297` | [4.i](#step-4-i) | — | `SR-TC-0297` | SR-VER-0022 |
| `SR-REQ-0298` | [4.i](#step-4-i) | — | `SR-TC-0298` | SR-VER-0022 |
| `SR-REQ-0299` | [2.e](#step-2-e) | [11.a](#step-11-a) | `SR-TC-0299` | SR-VER-0023 |
| `SR-REQ-0300` | [2.e](#step-2-e) | [11.b](#step-11-b) | `SR-TC-0300` | SR-VER-0023 |
| `SR-REQ-0301` | [11.c](#step-11-c) | — | `SR-TC-0301` | SR-VER-0023 |
| `SR-REQ-0302` | [11.d](#step-11-d) | — | `SR-TC-0302` | SR-VER-0023 |
| `SR-REQ-0303` | [11.b](#step-11-b) | — | `SR-TC-0303` | SR-VER-0023 |
| `SR-REQ-0304` | [11.e](#step-11-e) | — | `SR-TC-0304` | SR-VER-0023 |
| `SR-REQ-0305` | [11.f](#step-11-f) | — | `SR-TC-0305` | SR-VER-0023 |
| `SR-REQ-0306` | [11.f](#step-11-f) | — | `SR-TC-0306` | SR-VER-0023 |
| `SR-REQ-0307` | [11.g](#step-11-g) | — | `SR-TC-0307` | SR-VER-0023 |
| `SR-REQ-0308` | [11.h](#step-11-h) | [11.i](#step-11-i) | `SR-TC-0308` | SR-VER-0023 |
| `SR-REQ-0309` | [11.j](#step-11-j) | — | `SR-TC-0309` | SR-VER-0023 |
| `SR-REQ-0310` | [11.d](#step-11-d) | — | `SR-TC-0310` | SR-VER-0023 |
| `SR-REQ-0311` | [11.m](#step-11-m) | — | `SR-TC-0311` | SR-VER-0023 |
| `SR-REQ-0312` | [11.a](#step-11-a) | — | `SR-TC-0312` | SR-VER-0023 |
| `SR-REQ-0313` | [14.a](#step-14-a) | — | `SR-TC-0313` | SR-VER-0024 |
| `SR-REQ-0314` | [14.d](#step-14-d) | — | `SR-TC-0314` | SR-VER-0024 |
| `SR-REQ-0315` | [14.e](#step-14-e) | — | `SR-TC-0315` | SR-VER-0024 |
| `SR-REQ-0316` | [14.a](#step-14-a) | — | `SR-TC-0316` | SR-VER-0024 |
| `SR-REQ-0317` | [14.b](#step-14-b) | — | `SR-TC-0317` | SR-VER-0024 |
| `SR-REQ-0318` | [14.c](#step-14-c) | — | `SR-TC-0318` | SR-VER-0024 |
| `SR-REQ-0319` | [14.l](#step-14-l) | — | `SR-TC-0319` | SR-VER-0024 |
| `SR-REQ-0320` | [14.h](#step-14-h) | [14.i](#step-14-i) | `SR-TC-0320` | SR-VER-0024 |
| `SR-REQ-0321` | [14.h](#step-14-h) | [14.i](#step-14-i) | `SR-TC-0321` | SR-VER-0024 |
| `SR-REQ-0322` | [14.j](#step-14-j) | — | `SR-TC-0322` | SR-VER-0024 |
| `SR-REQ-0323` | [14.k](#step-14-k) | — | `SR-TC-0323` | SR-VER-0024 |
| `SR-REQ-0324` | [12.f](#step-12-f) | [14.n](#step-14-n), [20.g](#step-20-g) | `SR-TC-0324` | SR-VER-0024 |
| `SR-REQ-0325` | [14.f](#step-14-f) | — | `SR-TC-0325` | SR-VER-0024 |
| `SR-REQ-0326` | [14.f](#step-14-f) | — | `SR-TC-0326` | SR-VER-0024 |
| `SR-REQ-0327` | [14.g](#step-14-g) | — | `SR-TC-0327` | SR-VER-0024 |
| `SR-REQ-0328` | [14.l](#step-14-l) | — | `SR-TC-0328` | SR-VER-0024 |
| `SR-REQ-0329` | [14.l](#step-14-l) | — | `SR-TC-0329` | SR-VER-0024 |
| `SR-REQ-0330` | [14.o](#step-14-o) | — | `SR-TC-0330` | SR-VER-0024 |
| `SR-REQ-0331` | [14.d](#step-14-d) | — | `SR-TC-0331` | SR-VER-0024 |
| `SR-REQ-0332` | [14.l](#step-14-l) | — | `SR-TC-0332` | SR-VER-0024 |
| `SR-REQ-0333` | [12.e](#step-12-e) | — | `SR-TC-0333` | SR-VER-0025 |
| `SR-REQ-0334` | [12.f](#step-12-f) | [12.g](#step-12-g) | `SR-TC-0334` | SR-VER-0025 |
| `SR-REQ-0335` | [12.g](#step-12-g) | — | `SR-TC-0335` | SR-VER-0025 |
| `SR-REQ-0336` | [12.h](#step-12-h) | — | `SR-TC-0336` | SR-VER-0025 |
| `SR-REQ-0337` | [12.h](#step-12-h) | — | `SR-TC-0337` | SR-VER-0025 |
| `SR-REQ-0338` | [12.i](#step-12-i) | — | `SR-TC-0338` | SR-VER-0025 |
| `SR-REQ-0339` | [12.i](#step-12-i) | — | `SR-TC-0339` | SR-VER-0025 |
| `SR-REQ-0340` | [12.j](#step-12-j) | — | `SR-TC-0340` | SR-VER-0025 |
| `SR-REQ-0341` | [12.j](#step-12-j) | — | `SR-TC-0341` | SR-VER-0025 |
| `SR-REQ-0342` | [2.e](#step-2-e) | [12.q](#step-12-q) | `SR-TC-0342` | SR-VER-0025 |
| `SR-REQ-0343` | [12.q](#step-12-q) | — | `SR-TC-0343` | SR-VER-0025 |
| `SR-REQ-0344` | [12.q](#step-12-q) | — | `SR-TC-0344` | SR-VER-0025 |
| `SR-REQ-0345` | [12.s](#step-12-s) | — | `SR-TC-0345` | SR-VER-0025 |
| `SR-REQ-0346` | [12.r](#step-12-r) | — | `SR-TC-0346` | SR-VER-0025 |
| `SR-REQ-0347` | [12.q](#step-12-q) | — | `SR-TC-0347` | SR-VER-0025 |
| `SR-REQ-0348` | [12.q](#step-12-q) | — | `SR-TC-0348` | SR-VER-0025 |
| `SR-REQ-0349` | [11.k](#step-11-k) | — | `SR-TC-0349` | SR-VER-0023 |
| `SR-REQ-0350` | [11.k](#step-11-k) | — | `SR-TC-0350` | SR-VER-0023 |
| `SR-REQ-0351` | [11.k](#step-11-k) | — | `SR-TC-0351` | SR-VER-0023 |
| `SR-REQ-0352` | [11.k](#step-11-k) | — | `SR-TC-0352` | SR-VER-0023 |
| `SR-REQ-0353` | [11.k](#step-11-k) | — | `SR-TC-0353` | SR-VER-0023 |
| `SR-REQ-0354` | [11.m](#step-11-m) | — | `SR-TC-0354` | SR-VER-0023 |
| `SR-REQ-0355` | [11.m](#step-11-m) | — | `SR-TC-0355` | SR-VER-0023 |
| `SR-REQ-0356` | [11.n](#step-11-n) | — | `SR-TC-0356` | SR-VER-0023 |
| `SR-REQ-0357` | [11.m](#step-11-m) | — | `SR-TC-0357` | SR-VER-0023 |
| `SR-REQ-0358` | [11.o](#step-11-o) | — | `SR-TC-0358` | SR-VER-0023 |
| `SR-REQ-0359` | [11.o](#step-11-o) | — | `SR-TC-0359` | SR-VER-0023 |
| `SR-REQ-0360` | [11.o](#step-11-o) | — | `SR-TC-0360` | SR-VER-0023 |
| `SR-REQ-0361` | [17.a](#step-17-a) | [17.b](#step-17-b) | `SR-TC-0361` | SR-VER-0026 |
| `SR-REQ-0362` | [15.h](#step-15-h) | [17.a](#step-17-a), [17.l](#step-17-l) | `SR-TC-0362` | SR-VER-0026 |
| `SR-REQ-0363` | [17.a](#step-17-a) | — | `SR-TC-0363` | SR-VER-0026 |
| `SR-REQ-0364` | [17.a](#step-17-a) | [17.b](#step-17-b) | `SR-TC-0364` | SR-VER-0026 |
| `SR-REQ-0365` | [17.c](#step-17-c) | [17.d](#step-17-d), [17.j](#step-17-j) | `SR-TC-0365` | SR-VER-0026 |
| `SR-REQ-0366` | [17.c](#step-17-c) | — | `SR-TC-0366` | SR-VER-0026 |
| `SR-REQ-0367` | [17.d](#step-17-d) | — | `SR-TC-0367` | SR-VER-0026 |
| `SR-REQ-0368` | [17.e](#step-17-e) | — | `SR-TC-0368` | SR-VER-0026 |
| `SR-REQ-0369` | [17.f](#step-17-f) | — | `SR-TC-0369` | SR-VER-0026 |
| `SR-REQ-0370` | [17.e](#step-17-e) | — | `SR-TC-0370` | SR-VER-0026 |
| `SR-REQ-0371` | [17.g](#step-17-g) | — | `SR-TC-0371` | SR-VER-0026 |
| `SR-REQ-0372` | [17.h](#step-17-h) | — | `SR-TC-0372` | SR-VER-0026 |
| `SR-REQ-0373` | [17.j](#step-17-j) | [17.k](#step-17-k) | `SR-TC-0373` | SR-VER-0026 |
| `SR-REQ-0374` | [17.k](#step-17-k) | — | `SR-TC-0374` | SR-VER-0026 |
| `SR-REQ-0375` | [17.b](#step-17-b) | [17.g](#step-17-g), [17.l](#step-17-l) | `SR-TC-0375` | SR-VER-0026 |
| `SR-REQ-0376` | [1.n](#step-1-n) | [18.m](#step-18-m) | `SR-TC-0376` | SR-VER-0027 |
| `SR-REQ-0377` | [2.q](#step-2-q) | [18.m](#step-18-m) | `SR-TC-0377` | SR-VER-0027 |
| `SR-REQ-0378` | [2.q](#step-2-q) | [18.m](#step-18-m) | `SR-TC-0378` | SR-VER-0027 |
| `SR-REQ-0379` | [1.m](#step-1-m) | [18.m](#step-18-m) | `SR-TC-0379` | SR-VER-0027 |
| `SR-REQ-0380` | [7.l](#step-7-l) | [18.m](#step-18-m) | `SR-TC-0380` | SR-VER-0027 |
| `SR-REQ-0381` | [1.n](#step-1-n) | [7.l](#step-7-l), [18.m](#step-18-m) | `SR-TC-0381` | SR-VER-0027 |
| `SR-REQ-0382` | [5.h](#step-5-h) | — | `SR-TC-0382` | SR-VER-0027 |
| `SR-REQ-0383` | [5.o](#step-5-o) | — | `SR-TC-0383` | SR-VER-0027 |
| `SR-REQ-0384` | [5.o](#step-5-o) | — | `SR-TC-0384` | SR-VER-0027 |
| `SR-REQ-0385` | [5.o](#step-5-o) | — | `SR-TC-0385` | SR-VER-0027 |
| `SR-REQ-0386` | [15.b](#step-15-b) | — | `SR-TC-0386` | SR-VER-0027 |
| `SR-REQ-0387` | [15.a](#step-15-a) | — | `SR-TC-0387` | SR-VER-0027 |
| `SR-REQ-0388` | [15.a](#step-15-a) | — | `SR-TC-0388` | SR-VER-0027 |
| `SR-REQ-0389` | [15.d](#step-15-d) | — | `SR-TC-0389` | SR-VER-0027 |
| `SR-REQ-0390` | [15.e](#step-15-e) | — | `SR-TC-0390` | SR-VER-0027 |
| `SR-REQ-0391` | [20.m](#step-20-m) | — | `SR-TC-0391` | SR-VER-0027 |
| `SR-REQ-0392` | [1.i](#step-1-i) | [20.h](#step-20-h), [20.m](#step-20-m) | `SR-TC-0392` | SR-VER-0027 |
| `SR-REQ-0393` | [1.j](#step-1-j) | [2.p](#step-2-p) | `SR-TC-0393` | SR-VER-0027 |
| `SR-REQ-0394` | [1.j](#step-1-j) | [2.p](#step-2-p) | `SR-TC-0394` | SR-VER-0027 |
| `SR-REQ-0395` | [9.a](#step-9-a) | — | `SR-TC-0395` | SR-VER-0028 |
| `SR-REQ-0396` | [9.c](#step-9-c) | — | `SR-TC-0396` | SR-VER-0028 |
| `SR-REQ-0397` | [9.c](#step-9-c) | — | `SR-TC-0397` | SR-VER-0028 |
| `SR-REQ-0398` | [9.e](#step-9-e) | — | `SR-TC-0398` | SR-VER-0028 |
| `SR-REQ-0399` | [9.e](#step-9-e) | — | `SR-TC-0399` | SR-VER-0028 |
| `SR-REQ-0400` | [9.g](#step-9-g) | [11.l](#step-11-l) | `SR-TC-0400` | SR-VER-0028 |
| `SR-REQ-0401` | [10.g](#step-10-g) | — | `SR-TC-0401` | SR-VER-0028 |
| `SR-REQ-0402` | [9.f](#step-9-f) | — | `SR-TC-0402` | SR-VER-0028 |
| `SR-REQ-0403` | [8.h](#step-8-h) | [9.h](#step-9-h), [17.i](#step-17-i) | `SR-TC-0403` | SR-VER-0028 |
| `SR-REQ-0404` | [9.h](#step-9-h) | — | `SR-TC-0404` | SR-VER-0028 |
| `SR-REQ-0405` | [3.f](#step-3-f) | — | `SR-TC-0405` | SR-VER-0029 |
| `SR-REQ-0406` | [3.f](#step-3-f) | [3.i](#step-3-i) | `SR-TC-0406` | SR-VER-0029 |
| `SR-REQ-0407` | [3.f](#step-3-f) | [15.b](#step-15-b) | `SR-TC-0407` | SR-VER-0029 |
| `SR-REQ-0408` | [3.f](#step-3-f) | [13.e](#step-13-e) | `SR-TC-0408` | SR-VER-0029 |
| `SR-REQ-0409` | [3.f](#step-3-f) | — | `SR-TC-0409` | SR-VER-0029 |
| `SR-REQ-0410` | [3.f](#step-3-f) | — | `SR-TC-0410` | SR-VER-0029 |
| `SR-REQ-0411` | [9.d](#step-9-d) | — | `SR-TC-0411` | SR-VER-0029 |
| `SR-REQ-0412` | [3.g](#step-3-g) | — | `SR-TC-0412` | SR-VER-0029 |
| `SR-REQ-0413` | [2.p](#step-2-p) | — | `SR-TC-0413` | SR-VER-0029 |
| `SR-REQ-0414` | [9.d](#step-9-d) | — | `SR-TC-0414` | SR-VER-0029 |
| `SR-REQ-0415` | [3.b](#step-3-b) | — | `SR-TC-0415` | SR-VER-0029 |
| `SR-REQ-0416` | [3.h](#step-3-h) | — | `SR-TC-0416` | SR-VER-0033 |
| `SR-REQ-0417` | [3.d](#step-3-d) | — | `SR-TC-0417` | SR-VER-0029 |
| `SR-REQ-0418` | [3.a](#step-3-a) | — | `SR-TC-0418` | SR-VER-0029 |
| `SR-REQ-0419` | [4.k](#step-4-k) | — | `SR-TC-0419` | SR-VER-0029 |
| `SR-REQ-0420` | [4.k](#step-4-k) | — | `SR-TC-0420` | SR-VER-0029 |
| `SR-REQ-0421` | [4.k](#step-4-k) | — | `SR-TC-0421` | SR-VER-0029 |
| `SR-REQ-0422` | [4.k](#step-4-k) | — | `SR-TC-0422` | SR-VER-0029 |
| `SR-REQ-0423` | [4.k](#step-4-k) | — | `SR-TC-0423` | SR-VER-0029 |
| `SR-REQ-0424` | [4.k](#step-4-k) | — | `SR-TC-0424` | SR-VER-0029 |
| `SR-REQ-0425` | [4.k](#step-4-k) | — | `SR-TC-0425` | SR-VER-0029 |
| `SR-REQ-0426` | [18.b](#step-18-b) | [18.e](#step-18-e), [18.h](#step-18-h), [18.l](#step-18-l) | `SR-TC-0426` | SR-VER-0030 |
| `SR-REQ-0427` | [18.c](#step-18-c) | — | `SR-TC-0427` | SR-VER-0030 |
| `SR-REQ-0428` | [18.c](#step-18-c) | — | `SR-TC-0428` | SR-VER-0030 |
| `SR-REQ-0429` | [18.j](#step-18-j) | [18.k](#step-18-k) | `SR-TC-0429` | SR-VER-0030 |
| `SR-REQ-0430` | [18.e](#step-18-e) | [18.j](#step-18-j) | `SR-TC-0430` | SR-VER-0030 |
| `SR-REQ-0431` | [18.e](#step-18-e) | [18.h](#step-18-h) | `SR-TC-0431` | SR-VER-0030 |
| `SR-REQ-0432` | [12.d](#step-12-d) | — | `SR-TC-0432` | SR-VER-0030 |
| `SR-REQ-0433` | [10.c](#step-10-c) | — | `SR-TC-0433` | SR-VER-0030 |
| `SR-REQ-0434` | [7.g](#step-7-g) | — | `SR-TC-0434` | SR-VER-0030 |
| `SR-REQ-0435` | [5.d](#step-5-d) | — | `SR-TC-0435` | SR-VER-0030 |
| `SR-REQ-0436` | [5.d](#step-5-d) | — | `SR-TC-0436` | SR-VER-0030 |
| `SR-REQ-0437` | [5.d](#step-5-d) | — | `SR-TC-0437` | SR-VER-0030 |
| `SR-REQ-0438` | [5.d](#step-5-d) | — | `SR-TC-0438` | SR-VER-0030 |
| `SR-REQ-0439` | [5.d](#step-5-d) | — | `SR-TC-0439` | SR-VER-0030 |
| `SR-REQ-0440` | [5.c](#step-5-c) | — | `SR-TC-0440` | SR-VER-0030 |
| `SR-REQ-0441` | [5.u](#step-5-u) | — | `SR-TC-0441` | SR-VER-0031 |
| `SR-REQ-0442` | [5.f](#step-5-f) | — | `SR-TC-0442` | SR-VER-0030 |
| `SR-REQ-0443` | [5.g](#step-5-g) | [7.k](#step-7-k) | `SR-TC-0443` | SR-VER-0030 |
| `SR-REQ-0444` | [12.b](#step-12-b) | — | `SR-TC-0444` | SR-VER-0030 |
| `SR-REQ-0445` | [12.b](#step-12-b) | — | `SR-TC-0445` | SR-VER-0030 |
| `SR-REQ-0446` | [12.k](#step-12-k) | [12.l](#step-12-l), [12.m](#step-12-m), [12.n](#step-12-n), [12.o](#step-12-o) | `SR-TC-0446` | SR-VER-0030 |
| `SR-REQ-0447` | [12.b](#step-12-b) | — | `SR-TC-0447` | SR-VER-0030 |
| `SR-REQ-0448` | [12.j](#step-12-j) | — | `SR-TC-0448` | SR-VER-0031 |
| `SR-REQ-0449` | [8.b](#step-8-b) | [12.p](#step-12-p) | `SR-TC-0449` | SR-VER-0032 |
| `SR-REQ-0450` | [13.f](#step-13-f) | [13.g](#step-13-g) | `SR-TC-0450` | SR-VER-0030 |
| `SR-REQ-0451` | [12.c](#step-12-c) | — | `SR-TC-0451` | SR-VER-0030 |
| `SR-REQ-0452` | [12.c](#step-12-c) | — | `SR-TC-0452` | SR-VER-0030 |
| `SR-REQ-0453` | [3.a](#step-3-a) | [14.b](#step-14-b) | `SR-TC-0453` | SR-VER-0031 |
| `SR-REQ-0454` | [14.b](#step-14-b) | — | `SR-TC-0454` | SR-VER-0031 |
| `SR-REQ-0455` | [14.a](#step-14-a) | — | `SR-TC-0455` | SR-VER-0031 |
| `SR-REQ-0456` | [14.c](#step-14-c) | — | `SR-TC-0456` | SR-VER-0031 |
| `SR-REQ-0457` | [14.c](#step-14-c) | — | `SR-TC-0457` | SR-VER-0031 |
| `SR-REQ-0458` | [5.p](#step-5-p) | — | `SR-TC-0458` | SR-VER-0031 |
| `SR-REQ-0459` | [5.r](#step-5-r) | — | `SR-TC-0459` | SR-VER-0031 |
| `SR-REQ-0460` | [5.s](#step-5-s) | — | `SR-TC-0460` | SR-VER-0031 |
| `SR-REQ-0461` | [15.j](#step-15-j) | [15.k](#step-15-k), [15.l](#step-15-l) | `SR-TC-0461` | SR-VER-0031 |
| `SR-REQ-0462` | [5.s](#step-5-s) | [15.k](#step-15-k), [15.l](#step-15-l), [20.e](#step-20-e) | `SR-TC-0462` | SR-VER-0031 |
| `SR-REQ-0463` | [5.u](#step-5-u) | — | `SR-TC-0463` | SR-VER-0031 |
| `SR-REQ-0464` | [5.u](#step-5-u) | — | `SR-TC-0464` | SR-VER-0031 |
| `SR-REQ-0465` | [5.u](#step-5-u) | — | `SR-TC-0465` | SR-VER-0031 |
| `SR-REQ-0466` | [5.u](#step-5-u) | — | `SR-TC-0466` | SR-VER-0031 |
| `SR-REQ-0467` | [11.a](#step-11-a) | — | `SR-TC-0467` | SR-VER-0032 |
| `SR-REQ-0468` | [11.c](#step-11-c) | — | `SR-TC-0468` | SR-VER-0032 |
| `SR-REQ-0469` | [11.e](#step-11-e) | — | `SR-TC-0469` | SR-VER-0032 |
| `SR-REQ-0470` | [11.g](#step-11-g) | — | `SR-TC-0470` | SR-VER-0032 |
| `SR-REQ-0471` | [11.i](#step-11-i) | — | `SR-TC-0471` | SR-VER-0032 |
| `SR-REQ-0472` | [11.m](#step-11-m) | — | `SR-TC-0472` | SR-VER-0032 |
| `SR-REQ-0473` | [8.b](#step-8-b) | — | `SR-TC-0473` | SR-VER-0032 |
| `SR-REQ-0474` | [8.c](#step-8-c) | — | `SR-TC-0474` | SR-VER-0032 |
| `SR-REQ-0475` | [8.d](#step-8-d) | — | `SR-TC-0475` | SR-VER-0032 |
| `SR-REQ-0476` | [1.e](#step-1-e) | — | `SR-TC-0476` | SR-VER-0032 |
| `SR-REQ-0477` | [1.c](#step-1-c) | — | `SR-TC-0477` | SR-VER-0032 |
| `SR-REQ-0478` | [5.m](#step-5-m) | — | `SR-TC-0478` | SR-VER-0032 |
| `SR-REQ-0479` | [11.n](#step-11-n) | — | `SR-TC-0479` | SR-VER-0032 |
| `SR-REQ-0480` | [7.a](#step-7-a) | [15.e](#step-15-e) | `SR-TC-0480` | SR-VER-0032 |
| `SR-REQ-0481` | [15.b](#step-15-b) | — | `SR-TC-0481` | SR-VER-0033 |
| `SR-REQ-0482` | [15.c](#step-15-c) | — | `SR-TC-0482` | SR-VER-0033 |
| `SR-REQ-0483` | [3.h](#step-3-h) | [15.c](#step-15-c) | `SR-TC-0483` | SR-VER-0033 |
| `SR-REQ-0484` | [15.f](#step-15-f) | — | `SR-TC-0484` | SR-VER-0033 |
| `SR-REQ-0485` | [15.a](#step-15-a) | — | `SR-TC-0485` | SR-VER-0033 |
| `SR-REQ-0486` | [14.k](#step-14-k) | — | `SR-TC-0486` | SR-VER-0033 |
| `SR-REQ-0487` | [15.g](#step-15-g) | — | `SR-TC-0487` | SR-VER-0033 |
| `SR-REQ-0488` | [15.g](#step-15-g) | — | `SR-TC-0488` | SR-VER-0033 |
| `SR-REQ-0489` | [5.g](#step-5-g) | — | `SR-TC-0489` | SR-VER-0033 |
| `SR-REQ-0490` | [15.g](#step-15-g) | — | `SR-TC-0490` | SR-VER-0033 |
| `SR-REQ-0491` | [1.h](#step-1-h) | [20.a](#step-20-a) | `SR-TC-0491` | SR-VER-0034 |
| `SR-REQ-0492` | [1.h](#step-1-h) | [20.a](#step-20-a) | `SR-TC-0492` | SR-VER-0034 |
| `SR-REQ-0493` | [20.a](#step-20-a) | [20.b](#step-20-b), [20.n](#step-20-n) | `SR-TC-0493` | SR-VER-0034 |
| `SR-REQ-0494` | [20.a](#step-20-a) | [20.b](#step-20-b), [20.n](#step-20-n) | `SR-TC-0494` | SR-VER-0034 |
| `SR-REQ-0495` | [12.s](#step-12-s) | [20.a](#step-20-a), [20.n](#step-20-n) | `SR-TC-0495` | SR-VER-0034 |
| `SR-REQ-0496` | [20.a](#step-20-a) | [20.n](#step-20-n) | `SR-TC-0496` | SR-VER-0034 |
| `SR-REQ-0497` | [20.i](#step-20-i) | — | `SR-TC-0497` | SR-VER-0034 |
| `SR-REQ-0498` | [20.i](#step-20-i) | — | `SR-TC-0498` | SR-VER-0034 |
| `SR-REQ-0499` | [4.q](#step-4-q) | — | `SR-TC-0499` | SR-VER-0034 |
| `SR-REQ-0500` | [20.a](#step-20-a) | [20.n](#step-20-n) | `SR-TC-0500` | SR-VER-0034 |
| `SR-REQ-0501` | [2.g](#step-2-g) | — | `SR-TC-0501` | SR-VER-0018 |
| `SR-REQ-0502` | [5.a](#step-5-a) | — | `SR-TC-0502` | SR-VER-0012 |
| `SR-REQ-0503` | [5.a](#step-5-a) | — | `SR-TC-0503` | SR-VER-0012 |
| `SR-REQ-0504` | [2.g](#step-2-g) | — | `SR-TC-0504` | SR-VER-0018 |
| `SR-REQ-0505` | [1.l](#step-1-l) | — | `SR-TC-0505` | SR-VER-0018 |
| `SR-REQ-0506` | [5.i](#step-5-i) | — | `SR-TC-0506` | SR-VER-0019 |
| `SR-REQ-0507` | [5.c](#step-5-c) | — | `SR-TC-0507` | SR-VER-0018 |
| `SR-REQ-0508` | [2.g](#step-2-g) | — | `SR-TC-0508` | SR-VER-0018 |
| `SR-REQ-0509` | [2.h](#step-2-h) | — | `SR-TC-0509` | SR-VER-0018 |
| `SR-REQ-0510` | [2.h](#step-2-h) | — | `SR-TC-0510` | SR-VER-0026 |
| `SR-REQ-0511` | [5.r](#step-5-r) | — | `SR-TC-0511` | SR-VER-0019 |
| `SR-REQ-0512` | [16.f](#step-16-f) | — | `SR-TC-0512` | SR-VER-0020 |
| `SR-REQ-0513` | [16.f](#step-16-f) | — | `SR-TC-0513` | SR-VER-0020 |
| `SR-REQ-0514` | [3.k](#step-3-k) | — | `SR-TC-0514` | SR-VER-0021 |
| `SR-REQ-0515` | [7.i](#step-7-i) | — | `SR-TC-0515` | SR-VER-0021 |
| `SR-REQ-0516` | [13.f](#step-13-f) | — | `SR-TC-0516` | SR-VER-0021 |
| `SR-REQ-0517` | [4.a](#step-4-a) | — | `SR-TC-0517` | SR-VER-0022 |
| `SR-REQ-0518` | [4.b](#step-4-b) | — | `SR-TC-0518` | SR-VER-0022 |
| `SR-REQ-0519` | [4.b](#step-4-b) | — | `SR-TC-0519` | SR-VER-0022 |
| `SR-REQ-0520` | [4.b](#step-4-b) | — | `SR-TC-0520` | SR-VER-0022 |
| `SR-REQ-0521` | [4.f](#step-4-f) | — | `SR-TC-0521` | SR-VER-0022 |
| `SR-REQ-0522` | [4.c](#step-4-c) | — | `SR-TC-0522` | SR-VER-0022 |
| `SR-REQ-0523` | [4.h](#step-4-h) | — | `SR-TC-0523` | SR-VER-0022 |
| `SR-REQ-0524` | [11.b](#step-11-b) | — | `SR-TC-0524` | SR-VER-0023 |
| `SR-REQ-0525` | [11.d](#step-11-d) | — | `SR-TC-0525` | SR-VER-0023 |
| `SR-REQ-0526` | [11.b](#step-11-b) | — | `SR-TC-0526` | SR-VER-0023 |
| `SR-REQ-0527` | [11.e](#step-11-e) | — | `SR-TC-0527` | SR-VER-0023 |
| `SR-REQ-0528` | [11.f](#step-11-f) | — | `SR-TC-0528` | SR-VER-0023 |
| `SR-REQ-0529` | [11.g](#step-11-g) | — | `SR-TC-0529` | SR-VER-0023 |
| `SR-REQ-0530` | [11.d](#step-11-d) | — | `SR-TC-0530` | SR-VER-0023 |
| `SR-REQ-0531` | [11.q](#step-11-q) | — | `SR-TC-0531` | SR-VER-0023 |
| `SR-REQ-0532` | [14.n](#step-14-n) | [20.g](#step-20-g) | `SR-TC-0532` | SR-VER-0024 |
| `SR-REQ-0533` | [12.j](#step-12-j) | — | `SR-TC-0533` | SR-VER-0025 |
| `SR-REQ-0534` | [12.j](#step-12-j) | — | `SR-TC-0534` | SR-VER-0025 |
| `SR-REQ-0535` | [12.i](#step-12-i) | — | `SR-TC-0535` | SR-VER-0025 |
| `SR-REQ-0536` | [12.r](#step-12-r) | — | `SR-TC-0536` | SR-VER-0025 |
| `SR-REQ-0537` | [12.t](#step-12-t) | — | `SR-TC-0537` | SR-VER-0025 |
| `SR-REQ-0538` | [11.k](#step-11-k) | — | `SR-TC-0538` | SR-VER-0023 |
| `SR-REQ-0539` | [11.l](#step-11-l) | — | `SR-TC-0539` | SR-VER-0023 |
| `SR-REQ-0540` | [11.m](#step-11-m) | [17.i](#step-17-i) | `SR-TC-0540` | SR-VER-0023 |
| `SR-REQ-0541` | [17.i](#step-17-i) | — | `SR-TC-0541` | SR-VER-0026 |
| `SR-REQ-0542` | [17.i](#step-17-i) | — | `SR-TC-0542` | SR-VER-0026 |
| `SR-REQ-0543` | [5.h](#step-5-h) | — | `SR-TC-0543` | SR-VER-0027 |
| `SR-REQ-0544` | [1.j](#step-1-j) | [2.p](#step-2-p), [20.g](#step-20-g) | `SR-TC-0544` | SR-VER-0027 |
| `SR-REQ-0545` | [1.j](#step-1-j) | [20.g](#step-20-g) | `SR-TC-0545` | SR-VER-0027 |
| `SR-REQ-0546` | [9.b](#step-9-b) | — | `SR-TC-0546` | SR-VER-0028 |
| `SR-REQ-0547` | [9.b](#step-9-b) | — | `SR-TC-0547` | SR-VER-0028 |
| `SR-REQ-0548` | [9.f](#step-9-f) | — | `SR-TC-0548` | SR-VER-0028 |
| `SR-REQ-0549` | [1.k](#step-1-k) | — | `SR-TC-0549` | SR-VER-0035 |
| `SR-REQ-0550` | [1.k](#step-1-k) | — | `SR-TC-0550` | SR-VER-0035 |
| `SR-REQ-0551` | [1.k](#step-1-k) | — | `SR-TC-0551` | SR-VER-0035 |
| `SR-REQ-0552` | [1.c](#step-1-c) | — | `SR-TC-0552` | SR-VER-0036 |
| `SR-REQ-0553` | [6.a](#step-6-a) | — | `SR-TC-0553` | SR-VER-0035 |
| `SR-REQ-0554` | [1.k](#step-1-k) | — | `SR-TC-0554` | SR-VER-0035 |
| `SR-REQ-0555` | [1.k](#step-1-k) | [6.a](#step-6-a) | `SR-TC-0555` | SR-VER-0035 |
| `SR-REQ-0556` | [1.k](#step-1-k) | — | `SR-TC-0556` | SR-VER-0035 |
| `SR-REQ-0557` | [5.j](#step-5-j) | [20.f](#step-20-f) | `SR-TC-0557` | SR-VER-0035 |
| `SR-REQ-0558` | [5.t](#step-5-t) | [20.f](#step-20-f) | `SR-TC-0558` | SR-VER-0035 |
| `SR-REQ-0559` | [5.t](#step-5-t) | [20.f](#step-20-f) | `SR-TC-0559` | SR-VER-0035 |
| `SR-REQ-0560` | [5.t](#step-5-t) | [20.f](#step-20-f) | `SR-TC-0560` | SR-VER-0036 |
| `SR-REQ-0561` | [5.s](#step-5-s) | [20.f](#step-20-f) | `SR-TC-0561` | SR-VER-0035 |
| `SR-REQ-0562` | [2.p](#step-2-p) | [20.f](#step-20-f) | `SR-TC-0562` | SR-VER-0035 |
| `SR-REQ-0563` | [6.s](#step-6-s) | [20.f](#step-20-f) | `SR-TC-0563` | SR-VER-0035 |
| `SR-REQ-0564` | [5.j](#step-5-j) | [20.f](#step-20-f) | `SR-TC-0564` | SR-VER-0035 |
| `SR-REQ-0565` | [6.b](#step-6-b) | [20.f](#step-20-f) | `SR-TC-0565` | SR-VER-0036 |
| `SR-REQ-0566` | [6.b](#step-6-b) | [20.f](#step-20-f) | `SR-TC-0566` | SR-VER-0036 |
| `SR-REQ-0567` | [6.b](#step-6-b) | [20.f](#step-20-f) | `SR-TC-0567` | SR-VER-0036 |
| `SR-REQ-0568` | [15.i](#step-15-i) | [20.f](#step-20-f) | `SR-TC-0568` | SR-VER-0035 |
| `SR-REQ-0569` | [5.i](#step-5-i) | [20.f](#step-20-f) | `SR-TC-0569` | SR-VER-0035 |
| `SR-REQ-0570` | [6.a](#step-6-a) | [20.e](#step-20-e), [20.f](#step-20-f) | `SR-TC-0570` | SR-VER-0038 |
| `SR-REQ-0571` | [6.r](#step-6-r) | [20.f](#step-20-f) | `SR-TC-0571` | SR-VER-0036 |
| `SR-REQ-0572` | [5.s](#step-5-s) | [20.f](#step-20-f) | `SR-TC-0572` | SR-VER-0035 |
| `SR-REQ-0573` | [6.c](#step-6-c) | [20.f](#step-20-f) | `SR-TC-0573` | SR-VER-0037 |
| `SR-REQ-0574` | [6.c](#step-6-c) | [20.f](#step-20-f) | `SR-TC-0574` | SR-VER-0037 |
| `SR-REQ-0575` | [6.c](#step-6-c) | [20.f](#step-20-f) | `SR-TC-0575` | SR-VER-0037 |
| `SR-REQ-0576` | [6.d](#step-6-d) | [20.f](#step-20-f) | `SR-TC-0576` | SR-VER-0037 |
| `SR-REQ-0577` | [6.d](#step-6-d) | [20.f](#step-20-f) | `SR-TC-0577` | SR-VER-0037 |
| `SR-REQ-0578` | [6.d](#step-6-d) | [20.f](#step-20-f) | `SR-TC-0578` | SR-VER-0037 |
| `SR-REQ-0579` | [6.t](#step-6-t) | [20.j](#step-20-j) | `SR-TC-0579` | SR-VER-0037 |
| `SR-REQ-0580` | [6.t](#step-6-t) | [20.j](#step-20-j) | `SR-TC-0580` | SR-VER-0037 |
| `SR-REQ-0581` | [1.k](#step-1-k) | [20.j](#step-20-j) | `SR-TC-0581` | SR-VER-0038 |
| `SR-REQ-0582` | [3.e](#step-3-e) | [20.f](#step-20-f) | `SR-TC-0582` | SR-VER-0038 |
| `SR-REQ-0583` | [6.e](#step-6-e) | [20.f](#step-20-f) | `SR-TC-0583` | SR-VER-0037 |
| `SR-REQ-0584` | [6.e](#step-6-e) | [20.f](#step-20-f) | `SR-TC-0584` | SR-VER-0037 |
| `SR-REQ-0585` | [6.f](#step-6-f) | [20.f](#step-20-f) | `SR-TC-0585` | SR-VER-0037 |
| `SR-REQ-0586` | [6.o](#step-6-o) | [20.f](#step-20-f) | `SR-TC-0586` | SR-VER-0037 |
| `SR-REQ-0587` | [6.u](#step-6-u) | [8.k](#step-8-k), [20.f](#step-20-f) | `SR-TC-0587` | SR-VER-0038 |
| `SR-REQ-0588` | [6.g](#step-6-g) | [20.f](#step-20-f) | `SR-TC-0588` | SR-VER-0038 |
| `SR-REQ-0589` | [6.g](#step-6-g) | [20.f](#step-20-f) | `SR-TC-0589` | SR-VER-0038 |
| `SR-REQ-0590` | [6.g](#step-6-g) | [20.f](#step-20-f) | `SR-TC-0590` | SR-VER-0038 |
| `SR-REQ-0591` | [6.g](#step-6-g) | [20.f](#step-20-f) | `SR-TC-0591` | SR-VER-0038 |
| `SR-REQ-0592` | [6.h](#step-6-h) | [20.f](#step-20-f) | `SR-TC-0592` | SR-VER-0037 |
| `SR-REQ-0593` | [6.h](#step-6-h) | [20.f](#step-20-f) | `SR-TC-0593` | SR-VER-0037 |
| `SR-REQ-0594` | [6.d](#step-6-d) | [20.f](#step-20-f) | `SR-TC-0594` | SR-VER-0036 |
| `SR-REQ-0595` | [6.d](#step-6-d) | [20.f](#step-20-f) | `SR-TC-0595` | SR-VER-0036 |
| `SR-REQ-0596` | [6.u](#step-6-u) | [20.f](#step-20-f) | `SR-TC-0596` | SR-VER-0038 |
| `SR-REQ-0597` | [20.f](#step-20-f) | — | `SR-TC-0597` | SR-VER-0038 |
| `SR-REQ-0598` | [20.f](#step-20-f) | — | `SR-TC-0598` | SR-VER-0037 |
| `SR-REQ-0599` | [6.u](#step-6-u) | [20.f](#step-20-f) | `SR-TC-0599` | SR-VER-0035 |
| `SR-REQ-0600` | [20.f](#step-20-f) | — | `SR-TC-0600` | SR-VER-0036 |
| `SR-REQ-0601` | [6.c](#step-6-c) | [20.f](#step-20-f) | `SR-TC-0601` | SR-VER-0039 |
| `SR-REQ-0602` | [6.i](#step-6-i) | [20.f](#step-20-f) | `SR-TC-0602` | SR-VER-0039 |
| `SR-REQ-0603` | [6.i](#step-6-i) | [6.k](#step-6-k), [20.f](#step-20-f) | `SR-TC-0603` | SR-VER-0039 |
| `SR-REQ-0604` | [6.h](#step-6-h) | [20.f](#step-20-f) | `SR-TC-0604` | SR-VER-0039 |
| `SR-REQ-0605` | [6.f](#step-6-f) | [6.k](#step-6-k), [11.r](#step-11-r), [20.f](#step-20-f) | `SR-TC-0605` | SR-VER-0039 |
| `SR-REQ-0606` | [6.n](#step-6-n) | — | `SR-TC-0606` | SR-VER-0039 |
| `SR-REQ-0607` | [6.l](#step-6-l) | — | `SR-TC-0607` | SR-VER-0039 |
| `SR-REQ-0608` | [6.m](#step-6-m) | — | `SR-TC-0608` | SR-VER-0040 |
| `SR-REQ-0609` | [6.l](#step-6-l) | — | `SR-TC-0609` | SR-VER-0040 |
| `SR-REQ-0610` | [6.m](#step-6-m) | — | `SR-TC-0610` | SR-VER-0040 |
| `SR-REQ-0611` | [6.m](#step-6-m) | — | `SR-TC-0611` | SR-VER-0041 |
| `SR-REQ-0612` | [6.n](#step-6-n) | — | `SR-TC-0612` | SR-VER-0039 |
| `SR-REQ-0613` | [6.n](#step-6-n) | — | `SR-TC-0613` | SR-VER-0039 |
| `SR-REQ-0614` | [6.h](#step-6-h) | — | `SR-TC-0614` | SR-VER-0039 |
| `SR-REQ-0615` | [6.i](#step-6-i) | — | `SR-TC-0615` | SR-VER-0040 |
| `SR-REQ-0616` | [6.m](#step-6-m) | — | `SR-TC-0616` | SR-VER-0040 |
| `SR-REQ-0617` | [6.m](#step-6-m) | — | `SR-TC-0617` | SR-VER-0040 |
| `SR-REQ-0618` | [6.o](#step-6-o) | — | `SR-TC-0618` | SR-VER-0040 |
| `SR-REQ-0619` | [6.j](#step-6-j) | — | `SR-TC-0619` | SR-VER-0039 |
| `SR-REQ-0620` | [6.p](#step-6-p) | — | `SR-TC-0620` | SR-VER-0041 |
| `SR-REQ-0621` | [6.p](#step-6-p) | — | `SR-TC-0621` | SR-VER-0041 |
| `SR-REQ-0622` | [6.o](#step-6-o) | — | `SR-TC-0622` | SR-VER-0039 |
| `SR-REQ-0623` | [6.q](#step-6-q) | [11.r](#step-11-r) | `SR-TC-0623` | SR-VER-0039 |
| `SR-REQ-0624` | [6.r](#step-6-r) | — | `SR-TC-0624` | SR-VER-0040 |
| `SR-REQ-0625` | [6.r](#step-6-r) | — | `SR-TC-0625` | SR-VER-0040 |
| `SR-REQ-0626` | [6.r](#step-6-r) | — | `SR-TC-0626` | SR-VER-0040 |
| `SR-REQ-0627` | [6.j](#step-6-j) | [6.r](#step-6-r) | `SR-TC-0627` | SR-VER-0040 |
| `SR-REQ-0628` | [6.s](#step-6-s) | — | `SR-TC-0628` | SR-VER-0040 |
| `SR-REQ-0629` | [6.l](#step-6-l) | — | `SR-TC-0629` | SR-VER-0040 |
| `SR-REQ-0630` | [6.k](#step-6-k) | — | `SR-TC-0630` | SR-VER-0040 |
| `SR-REQ-0631` | [6.n](#step-6-n) | — | `SR-TC-0631` | SR-VER-0039 |
| `SR-REQ-0632` | [1.m](#step-1-m) | [6.i](#step-6-i), [18.m](#step-18-m) | `SR-TC-0632` | SR-VER-0040 |
| `SR-REQ-0633` | [6.u](#step-6-u) | — | `SR-TC-0633` | SR-VER-0039 |
| `SR-REQ-0634` | [6.c](#step-6-c) | — | `SR-TC-0634` | SR-VER-0041 |
| `SR-REQ-0635` | [6.c](#step-6-c) | — | `SR-TC-0635` | SR-VER-0040 |
| `SR-REQ-0636` | [6.o](#step-6-o) | — | `SR-TC-0636` | SR-VER-0039 |
| `SR-REQ-0637` | [17.i](#step-17-i) | [17.f](#step-17-f) | `SR-TC-0637` | SR-VER-0041 |
| `SR-REQ-0638` | [17.i](#step-17-i) | [17.f](#step-17-f) | `SR-TC-0638` | SR-VER-0041 |
| `SR-REQ-0639` | [16.b](#step-16-b) | [16.g](#step-16-g), [16.j](#step-16-j), [16.k](#step-16-k) | `SR-TC-0639` | SR-VER-0042 |
| `SR-REQ-0640` | [16.j](#step-16-j) | [16.k](#step-16-k) | `SR-TC-0640` | SR-VER-0042 |
| `SR-REQ-0641` | [16.g](#step-16-g) | [16.b](#step-16-b), [16.k](#step-16-k) | `SR-TC-0641` | SR-VER-0042 |
| `SR-REQ-0642` | [16.j](#step-16-j) | [16.k](#step-16-k) | `SR-TC-0642` | SR-VER-0042 |
| `SR-REQ-0643` | [18.d](#step-18-d) | [18.i](#step-18-i), [18.p](#step-18-p) | `SR-TC-0643` | SR-VER-0043 |
| `SR-REQ-0644` | [18.d](#step-18-d) | [18.p](#step-18-p) | `SR-TC-0644` | SR-VER-0043 |
| `SR-REQ-0645` | [18.f](#step-18-f) | [18.g](#step-18-g), [18.p](#step-18-p) | `SR-TC-0645` | SR-VER-0043 |
| `SR-REQ-0646` | [18.h](#step-18-h) | [18.p](#step-18-p) | `SR-TC-0646` | SR-VER-0043 |
| `SR-REQ-0647` | [18.o](#step-18-o) | [18.p](#step-18-p) | `SR-TC-0647` | SR-VER-0043 |
| `SR-REQ-0648` | [18.e](#step-18-e) | [18.j](#step-18-j), [18.p](#step-18-p) | `SR-TC-0648` | SR-VER-0043 |
| `SR-REQ-0649` | [18.c](#step-18-c) | [18.p](#step-18-p) | `SR-TC-0649` | SR-VER-0043 |
| `SR-REQ-0650` | [20.a](#step-20-a) | [20.b](#step-20-b), [20.c](#step-20-c), [20.d](#step-20-d), [20.e](#step-20-e), [20.n](#step-20-n) | `SR-TC-0650` | SR-VER-0041 |
| `SR-REQ-0651` | [2.m](#step-2-m) | — | `SR-TC-0651` | SR-VER-0044 |
| `SR-REQ-0652` | [2.m](#step-2-m) | — | `SR-TC-0652` | SR-VER-0044 |
| `SR-REQ-0653` | [2.m](#step-2-m) | — | `SR-TC-0653` | SR-VER-0044 |
| `SR-REQ-0654` | [11.p](#step-11-p) | — | `SR-TC-0654` | SR-VER-0044 |
| `SR-REQ-0655` | [11.p](#step-11-p) | — | `SR-TC-0655` | SR-VER-0044 |
| `SR-REQ-0656` | [2.m](#step-2-m) | — | `SR-TC-0656` | SR-VER-0044 |
| `SR-REQ-0657` | [7.d](#step-7-d) | — | `SR-TC-0657` | SR-VER-0044 |
| `SR-REQ-0658` | [2.n](#step-2-n) | — | `SR-TC-0658` | SR-VER-0045 |
| `SR-REQ-0659` | [2.n](#step-2-n) | [20.m](#step-20-m) | `SR-TC-0659` | SR-VER-0045 |
| `SR-REQ-0660` | [4.m](#step-4-m) | — | `SR-TC-0660` | SR-VER-0045 |
| `SR-REQ-0661` | [2.n](#step-2-n) | — | `SR-TC-0661` | SR-VER-0045 |
| `SR-REQ-0662` | [4.m](#step-4-m) | — | `SR-TC-0662` | SR-VER-0045 |
| `SR-REQ-0663` | [4.m](#step-4-m) | — | `SR-TC-0663` | SR-VER-0045 |
| `SR-REQ-0664` | [4.n](#step-4-n) | — | `SR-TC-0664` | SR-VER-0045 |
| `SR-REQ-0665` | [4.m](#step-4-m) | — | `SR-TC-0665` | SR-VER-0045 |
| `SR-REQ-0666` | [4.m](#step-4-m) | — | `SR-TC-0666` | SR-VER-0045 |
| `SR-REQ-0667` | [4.m](#step-4-m) | — | `SR-TC-0667` | SR-VER-0045 |
| `SR-REQ-0668` | [4.m](#step-4-m) | — | `SR-TC-0668` | SR-VER-0045 |
| `SR-REQ-0669` | [2.o](#step-2-o) | [20.m](#step-20-m) | `SR-TC-0669` | SR-VER-0045 |
| `SR-REQ-0670` | [2.o](#step-2-o) | — | `SR-TC-0670` | SR-VER-0045 |
| `SR-REQ-0671` | [2.j](#step-2-j) | — | `SR-TC-0671` | SR-VER-0044 |
| `SR-REQ-0672` | [11.p](#step-11-p) | — | `SR-TC-0672` | SR-VER-0045 |
| `SR-REQ-0673` | [4.l](#step-4-l) | — | `SR-TC-0673` | SR-VER-0044 |
| `SR-REQ-0674` | [4.q](#step-4-q) | [18.i](#step-18-i) | `SR-TC-0674` | SR-VER-0044 |
| `SR-REQ-0675` | [19.a](#step-19-a) | — | `SR-TC-0675` | SR-VER-0046 |
| `SR-REQ-0676` | [19.a](#step-19-a) | — | `SR-TC-0676` | SR-VER-0046 |
| `SR-REQ-0677` | [19.a](#step-19-a) | — | `SR-TC-0677` | SR-VER-0046 |
| `SR-REQ-0678` | [19.b](#step-19-b) | — | `SR-TC-0678` | SR-VER-0046 |
| `SR-REQ-0679` | [19.b](#step-19-b) | — | `SR-TC-0679` | SR-VER-0046 |
| `SR-REQ-0680` | [19.c](#step-19-c) | — | `SR-TC-0680` | SR-VER-0046 |
| `SR-REQ-0681` | [19.c](#step-19-c) | — | `SR-TC-0681` | SR-VER-0046 |
| `SR-REQ-0682` | [19.d](#step-19-d) | — | `SR-TC-0682` | SR-VER-0046 |
| `SR-REQ-0683` | [19.d](#step-19-d) | — | `SR-TC-0683` | SR-VER-0046 |
| `SR-REQ-0684` | [19.d](#step-19-d) | — | `SR-TC-0684` | SR-VER-0046 |
| `SR-REQ-0685` | [19.f](#step-19-f) | — | `SR-TC-0685` | SR-VER-0046 |
| `SR-REQ-0686` | [19.f](#step-19-f) | — | `SR-TC-0686` | SR-VER-0046 |
| `SR-REQ-0687` | [19.f](#step-19-f) | — | `SR-TC-0687` | SR-VER-0046 |
| `SR-REQ-0688` | [19.f](#step-19-f) | — | `SR-TC-0688` | SR-VER-0046 |
| `SR-REQ-0689` | [19.g](#step-19-g) | — | `SR-TC-0689` | SR-VER-0046 |
| `SR-REQ-0690` | [19.g](#step-19-g) | — | `SR-TC-0690` | SR-VER-0046 |
| `SR-REQ-0691` | [19.e](#step-19-e) | — | `SR-TC-0691` | SR-VER-0046 |
| `SR-REQ-0692` | [19.e](#step-19-e) | [19.u](#step-19-u) | `SR-TC-0692` | SR-VER-0046 |
| `SR-REQ-0693` | [19.f](#step-19-f) | — | `SR-TC-0693` | SR-VER-0046 |
| `SR-REQ-0694` | [19.h](#step-19-h) | — | `SR-TC-0694` | SR-VER-0048 |
| `SR-REQ-0695` | [19.h](#step-19-h) | [19.u](#step-19-u) | `SR-TC-0695` | SR-VER-0046 |
| `SR-REQ-0696` | [19.h](#step-19-h) | — | `SR-TC-0696` | SR-VER-0046 |
| `SR-REQ-0697` | [19.d](#step-19-d) | [19.s](#step-19-s) | `SR-TC-0697` | SR-VER-0046 |
| `SR-REQ-0698` | [19.n](#step-19-n) | [19.y](#step-19-y) | `SR-TC-0698` | SR-VER-0047 |
| `SR-REQ-0699` | [19.k](#step-19-k) | [19.n](#step-19-n), [19.y](#step-19-y) | `SR-TC-0699` | SR-VER-0047 |
| `SR-REQ-0700` | [19.k](#step-19-k) | [19.y](#step-19-y), [20.k](#step-20-k) | `SR-TC-0700` | SR-VER-0048 |
| `SR-REQ-0701` | [19.k](#step-19-k) | [19.y](#step-19-y), [20.k](#step-20-k), [20.m](#step-20-m) | `SR-TC-0701` | SR-VER-0048 |
| `SR-REQ-0702` | [19.l](#step-19-l) | [19.y](#step-19-y), [20.g](#step-20-g) | `SR-TC-0702` | SR-VER-0048 |
| `SR-REQ-0703` | [19.l](#step-19-l) | [19.y](#step-19-y), [20.g](#step-20-g) | `SR-TC-0703` | SR-VER-0048 |
| `SR-REQ-0704` | [19.m](#step-19-m) | [19.y](#step-19-y), [20.g](#step-20-g) | `SR-TC-0704` | SR-VER-0048 |
| `SR-REQ-0705` | [19.m](#step-19-m) | [19.y](#step-19-y) | `SR-TC-0705` | SR-VER-0048 |
| `SR-REQ-0706` | [19.c](#step-19-c) | [19.o](#step-19-o), [19.u](#step-19-u) | `SR-TC-0706` | SR-VER-0047 |
| `SR-REQ-0707` | [19.n](#step-19-n) | [19.u](#step-19-u) | `SR-TC-0707` | SR-VER-0047 |
| `SR-REQ-0708` | [19.p](#step-19-p) | [19.u](#step-19-u) | `SR-TC-0708` | SR-VER-0047 |
| `SR-REQ-0709` | [19.o](#step-19-o) | [19.p](#step-19-p), [19.u](#step-19-u) | `SR-TC-0709` | SR-VER-0047 |
| `SR-REQ-0710` | [19.q](#step-19-q) | [19.u](#step-19-u) | `SR-TC-0710` | SR-VER-0047 |
| `SR-REQ-0711` | [19.q](#step-19-q) | [19.u](#step-19-u) | `SR-TC-0711` | SR-VER-0047 |
| `SR-REQ-0712` | [19.q](#step-19-q) | [19.u](#step-19-u) | `SR-TC-0712` | SR-VER-0047 |
| `SR-REQ-0713` | [19.r](#step-19-r) | [19.u](#step-19-u) | `SR-TC-0713` | SR-VER-0047 |
| `SR-REQ-0714` | [19.r](#step-19-r) | [19.u](#step-19-u) | `SR-TC-0714` | SR-VER-0048 |
| `SR-REQ-0715` | [19.i](#step-19-i) | [19.j](#step-19-j), [19.w](#step-19-w) | `SR-TC-0715` | SR-VER-0048 |
| `SR-REQ-0716` | [19.i](#step-19-i) | [19.j](#step-19-j), [19.w](#step-19-w) | `SR-TC-0716` | SR-VER-0048 |
| `SR-REQ-0717` | [19.m](#step-19-m) | [19.w](#step-19-w) | `SR-TC-0717` | SR-VER-0048 |
| `SR-REQ-0718` | [19.m](#step-19-m) | [19.w](#step-19-w) | `SR-TC-0718` | SR-VER-0048 |
| `SR-REQ-0719` | [19.j](#step-19-j) | [19.v](#step-19-v), [19.w](#step-19-w) | `SR-TC-0719` | SR-VER-0048 |
| `SR-REQ-0720` | [19.t](#step-19-t) | [19.u](#step-19-u), [19.y](#step-19-y), [20.k](#step-20-k) | `SR-TC-0720` | SR-VER-0047 |
| `SR-REQ-0721` | [19.v](#step-19-v) | [19.y](#step-19-y), [20.k](#step-20-k) | `SR-TC-0721` | SR-VER-0048 |
| `SR-REQ-0722` | [19.s](#step-19-s) | [19.w](#step-19-w), [19.y](#step-19-y), [20.k](#step-20-k) | `SR-TC-0722` | SR-VER-0048 |
| `SR-REQ-0723` | [14.m](#step-14-m) | [19.x](#step-19-x) | `SR-TC-0723` | SR-VER-0049 |
| `SR-REQ-0724` | [16.e](#step-16-e) | — | `SR-TC-0724` | SR-VER-0049 |
| `SR-REQ-0725` | [16.e](#step-16-e) | [16.j](#step-16-j) | `SR-TC-0725` | SR-VER-0049 |
| `SR-REQ-0726` | [19.x](#step-19-x) | [19.y](#step-19-y), [20.d](#step-20-d) | `SR-TC-0726` | SR-VER-0049 |
| `SR-REQ-0727` | [4.g](#step-4-g) | [20.d](#step-20-d) | `SR-TC-0727` | SR-VER-0050 |
| `SR-REQ-0728` | [4.g](#step-4-g) | [20.d](#step-20-d) | `SR-TC-0728` | SR-VER-0050 |
| `SR-REQ-0729` | [4.g](#step-4-g) | [20.d](#step-20-d) | `SR-TC-0729` | SR-VER-0050 |
| `SR-REQ-0730` | [4.i](#step-4-i) | [20.d](#step-20-d) | `SR-TC-0730` | SR-VER-0050 |

## Anhang B – Verifikationsregister

Alle 50 ursprünglichen SR-VER-Verträge bleiben referenziert. Die nachfolgenden Meilensteine liefern Beiträge; M20 konsolidiert tatsächliche Ergebnisse, ersetzt aber keine früheren Einzeltests. Referenzplattformen, Messdaten und TD-001-Ausnahmen sind in der echten Evidence getrennt zu führen.

| Verifikationsvertrag | Requirements in diesem Vertrag | Beitragende Meilensteine |
|---|---:|---|
| `SR-VER-0001` | 10 | M1, M2, M7 |
| `SR-VER-0002` | 15 | M2 |
| `SR-VER-0003` | 10 | M2, M5 |
| `SR-VER-0004` | 14 | M2, M5 |
| `SR-VER-0005` | 12 | M3, M8 |
| `SR-VER-0006` | 12 | M2, M4 |
| `SR-VER-0007` | 18 | M1, M4 |
| `SR-VER-0008` | 17 | M3, M4, M8, M10, M11, M13, M15 |
| `SR-VER-0009` | 11 | M2, M13 |
| `SR-VER-0010` | 11 | M2, M12 |
| `SR-VER-0011` | 12 | M10, M13 |
| `SR-VER-0012` | 26 | M5, M18 |
| `SR-VER-0013` | 17 | M1, M4, M5, M8, M18, M20 |
| `SR-VER-0014` | 11 | M1, M2, M6, M18, M20 |
| `SR-VER-0015` | 6 | M2, M8, M20 |
| `SR-VER-0016` | 1 | M1 |
| `SR-VER-0017` | 3 | M1, M18, M20 |
| `SR-VER-0018` | 31 | M1, M2, M5, M7, M16, M18, M20 |
| `SR-VER-0019` | 19 | M5, M18, M20 |
| `SR-VER-0020` | 14 | M16 |
| `SR-VER-0021` | 16 | M3, M7, M8, M12, M13, M14, M16, M17, M18 |
| `SR-VER-0022` | 20 | M4 |
| `SR-VER-0023` | 37 | M2, M11, M17 |
| `SR-VER-0024` | 21 | M12, M14, M20 |
| `SR-VER-0025` | 23 | M2, M12 |
| `SR-VER-0026` | 19 | M2, M15, M17 |
| `SR-VER-0027` | 28 | M1, M2, M5, M7, M15, M18, M20 |
| `SR-VER-0028` | 13 | M8, M9, M10, M11, M17 |
| `SR-VER-0029` | 20 | M2, M3, M4, M9, M13, M15 |
| `SR-VER-0030` | 24 | M5, M7, M10, M12, M13, M18 |
| `SR-VER-0031` | 16 | M3, M5, M12, M14, M15, M20 |
| `SR-VER-0032` | 15 | M1, M5, M7, M8, M11, M12, M15 |
| `SR-VER-0033` | 11 | M3, M5, M14, M15 |
| `SR-VER-0034` | 10 | M1, M4, M12, M20 |
| `SR-VER-0035` | 18 | M1, M2, M5, M6, M15, M20 |
| `SR-VER-0036` | 9 | M1, M5, M6, M20 |
| `SR-VER-0037` | 15 | M6, M20 |
| `SR-VER-0038` | 10 | M1, M3, M6, M8, M20 |
| `SR-VER-0039` | 16 | M6, M11, M20 |
| `SR-VER-0040` | 16 | M1, M6, M18 |
| `SR-VER-0041` | 7 | M6, M17, M20 |
| `SR-VER-0042` | 4 | M16 |
| `SR-VER-0043` | 7 | M18 |
| `SR-VER-0044` | 13 | M2, M4, M7, M11, M18 |
| `SR-VER-0045` | 16 | M2, M4, M11, M20 |
| `SR-VER-0046` | 22 | M19 |
| `SR-VER-0047` | 11 | M19, M20 |
| `SR-VER-0048` | 15 | M19, M20 |
| `SR-VER-0049` | 4 | M14, M16, M19, M20 |
| `SR-VER-0050` | 4 | M4, M20 |

## Anhang C – Szenario-/E2E-Zuordnung

Die Bezeichnungen und Identitäten stammen aus der Spezifikation. Alle Szenarien wachsen mit den genannten Features und werden in `20.b` gekoppelt abgenommen. Reine Ausgabeanteile werden gemäß TD-001 nicht automatisiert geprüft; insbesondere ist der originale Darstellungs-Bytevergleich in Szenario 0012 ausdrücklich ausgenommen.

| Szenario / E2E | Gegenstand | Führende Meilensteine |
|---|---|---|
| `SR-SCN-0001` / `SR-E2E-0001` | Projekt initialisieren | 1, 2, 7 |
| `SR-SCN-0002` / `SR-E2E-0002` | Anforderung erfassen | 2, 4, 7, 12 |
| `SR-SCN-0003` / `SR-E2E-0003` | Qualitätsfehler erkennen | 4 |
| `SR-SCN-0004` / `SR-E2E-0004` | Traceability erklären | 3, 8, 12 |
| `SR-SCN-0005` / `SR-E2E-0005` | Änderung vergleichen | 8, 10, 15, 17 |
| `SR-SCN-0006` / `SR-E2E-0006` | Release Readiness prüfen | 12, 13 |
| `SR-SCN-0007` / `SR-E2E-0007` | Evidence veraltet | 12 |
| `SR-SCN-0008` / `SR-E2E-0008` | Baseline erzeugen | 10 |
| `SR-SCN-0009` / `SR-E2E-0009` | KI-Vorschlag prüfen | 18 |
| `SR-SCN-0010` / `SR-E2E-0010` | KI-Vorschlag übernehmen | 5, 18 |
| `SR-SCN-0011` / `SR-E2E-0011` | CI-Gate | 1, 4 |
| `SR-SCN-0012` / `SR-E2E-0012` | Spezifikation rendern | 11; TD-001 |
| `SR-SCN-0013` / `SR-E2E-0013` | Chatbot-Sandbox-Roundtrip | 15, 18, 20 |
| `SR-SCN-0014` / `SR-E2E-0014` | Bestehendes Artefakt direkt bearbeiten | 5, 7 |
| `SR-SCN-0015` / `SR-E2E-0015` | Parallel neue Artefakte erzeugen | 2, 17 |
| `SR-SCN-0016` / `SR-E2E-0016` | Prozessabbruch wiederherstellen | 5 |
| `SR-SCN-0017` / `SR-E2E-0017` | Projekt migrieren | 16 |
| `SR-SCN-0018` / `SR-E2E-0018` | Suspect Relation prüfen | 7 |
| `SR-SCN-0019` / `SR-E2E-0019` | Dokument komponieren | 11; TD-001 |
| `SR-SCN-0020` / `SR-E2E-0020` | ReqIF austauschen | 14 |
| `SR-SCN-0021` / `SR-E2E-0021` | Testergebnisse übernehmen | 12 |
| `SR-SCN-0022` / `SR-E2E-0022` | Quellcode verknüpfen | 12 |
| `SR-SCN-0023` / `SR-E2E-0023` | Eigene Sicht erzeugen | 11; TD-001 |
| `SR-SCN-0024` / `SR-E2E-0024` | Branches semantisch mergen | 17 |
| `SR-SCN-0025` / `SR-E2E-0025` | Agent erkundet und wiederholt sicher | 1, 2, 5, 7, 18 |
| `SR-SCN-0026` / `SR-E2E-0026` | Produktkonfiguration ableiten | 9, 10, 11, 12, 13 |
| `SR-SCN-0027` / `SR-E2E-0027` | Unabhängige Aufrufe und Pfadwechsel | 1, 6 |
| `SR-SCN-0028` / `SR-E2E-0028` | Sandbox aus Sicherungsstand ersetzen | 6, 15 |
| `SR-SCN-0029` / `SR-E2E-0029` | Preflight bei Recoverybedarf | 5, 6 |
| `SR-SCN-0030` / `SR-E2E-0030` | Weiches Budget überschritten | 5, 6 |
| `SR-SCN-0031` / `SR-E2E-0031` | Cache fehlt oder ist veraltet | 6 |
| `SR-SCN-0032` / `SR-E2E-0032` | Umgebung und tatsächlicher Verbrauch | 6, 20 |
| `SR-SCN-0033` / `SR-E2E-0033` | Vollständig trotz weichem Budget | 6, 20 |
| `SR-SCN-0034` / `SR-E2E-0034` | Fortsetzung über mehrere Prompts | 6, 20 |
| `SR-SCN-0035` / `SR-E2E-0035` | Prompt und Actor bleiben kontrolliert | 6, 18 |
| `SR-SCN-0036` / `SR-E2E-0036` | Wiederholung und veränderte Zielbasis | 5, 6 |
| `SR-SCN-0037` / `SR-E2E-0037` | Historische Nachweise unverändert migrieren | 16 |
| `SR-SCN-0038` / `SR-E2E-0038` | Merge- und Proposal-Verträge durchgängig | 17, 18 |
| `SR-SCN-0039` / `SR-E2E-0039` | Mehrsprachig authoren | 2, 7, 11 |
| `SR-SCN-0040` / `SR-E2E-0040` | Sprachpolicy anwenden | 4, 11 |
| `SR-SCN-0041` / `SR-E2E-0041` | Sprachen tatsächlich erkennen | 19 |
| `SR-SCN-0042` / `SR-E2E-0042` | Unsicherheit und Fehlkennzeichnung | 19 |
| `SR-SCN-0043` / `SR-E2E-0043` | Mehrere Analyzer austauschen | 19 |
| `SR-SCN-0044` / `SR-E2E-0044` | Core ohne Zusatzpakete | 1, 19, 20 |
| `SR-SCN-0045` / `SR-E2E-0045` | Analyzerarbeit fortsetzen | 6, 19 |
| `SR-SCN-0046` / `SR-E2E-0046` | Entwurfsmetadaten migrieren | 4, 14, 16, 19 |

## Anhang D – gekoppelte Regressionen R-01 bis R-75

Die genaue Vorbedingung und das vollständige Oracle stehen im versionierten Anhang R der Spezifikation und werden nicht durch die Kurztitel ersetzt. Die Fachschritte nehmen die Fälle früh auf; `20.c` und `20.d` sichern ihre tatsächliche gemeinsame Abnahme. Bei R-63 wird die Sicherheitswirkung geprüft, nicht das visuelle Erscheinungsbild des escaped Texts.

| Fall | Gegenstand | Verantwortliche Meilensteine | Abschlussgate |
|---|---|---|---|
| `R-01` | Reguläre und migrierte Relation | 2, 16 | 20.c |
| `R-02` | Merge-Metadaten | 17 | 20.c |
| `R-03` | Unveränderte Übernahme | 17 | 20.c |
| `R-04` | Relationsreview | 7 | 20.c |
| `R-05` | Review-Auswahl | 7 | 20.c |
| `R-06` | Proposal-Einfügen | 18 | 20.c |
| `R-07` | Legacy-Unveränderbarkeit | 16 | 20.c |
| `R-08` | Historische Evidence | 12, 16 | 20.c |
| `R-09` | Proposal-Komplettlauf | 18 | 20.c |
| `R-10` | Befehlsklassen | 1, 5, 6 | 20.c |
| `R-11` | Überzogenes Arbeitsziel | 6 | 20.c |
| `R-12` | Sehr kleine Schritte | 6 | 20.c |
| `R-13` | Globaler Graph | 3, 6 | 20.c |
| `R-14` | Query und Diagnose-Spooling | 6, 8 | 20.c |
| `R-15` | Frische Sandbox | 6, 15 | 20.c |
| `R-16` | Veränderte Zielbasis | 5, 6 | 20.c |
| `R-17` | Beschädigter Checkpoint | 6 | 20.c |
| `R-18` | Retry nach Ausgabeabbruch | 5, 6 | 20.c |
| `R-19` | Echter Commitabbruch | 5 | 20.c |
| `R-20` | Prompt-/Actorgrenze | 6, 18 | 20.c |
| `R-21` | Kein Platz / harte Policy | 6 | 20.c |
| `R-22` | Unbekannte Quota | 6 | 20.c |
| `R-23` | Permanente Scope-Grenze | 3, 18 | 20.c |
| `R-24` | Proposal-Basiszulässigkeit | 18 | 20.c |
| `R-25` | Neuer Produktstand | 12 | 20.c |
| `R-26` | Retest desselben Stands | 12 | 20.c |
| `R-27` | Pflichtmenge und widersprechende Läufe | 12 | 20.c |
| `R-28` | Ungültige Ablösung | 12 | 20.c |
| `R-29` | Selfdescription-Projektion | 1, 7 | 20.c |
| `R-30` | Query-Wahrheitstabelle | 4, 8 | 20.c |
| `R-31` | Bewertung und Fortsetzung | 6, 12 | 20.c |
| `R-32` | Bewertung und Release-Baseline | 10, 12, 13 | 20.c |
| `R-33` | Reiner Abschluss | 5, 7 | 20.c |
| `R-34` | Fachinhalt und gemischter Lifecycle | 5, 7 | 20.c |
| `R-35` | Pflichtrelation ablehnen | 7 | 20.c |
| `R-36` | Erneut bestätigen | 7 | 20.c |
| `R-37` | Draft, optionale Relation und Authority | 7 | 20.c |
| `R-38` | Review-Transaktion und Retry | 5, 7 | 20.c |
| `R-39` | Review-Kontextstabilität | 7 | 20.c |
| `R-40` | Bundle-Arten | 15 | 20.c |
| `R-41` | Nichtkanonisches Teilbundle | 15 | 20.c |
| `R-42` | Manifest-Hashdomäne | 15 | 20.c |
| `R-43` | Manipulationsabgrenzung | 15 | 20.c |
| `R-44` | Vollständiger Baseline-Restore | 15 | 20.c |
| `R-45` | Unvollständige Restore-Quelle | 15 | 20.c |
| `R-46` | Geschützte Geschichte | 15 | 20.c |
| `R-47` | Restore-Atomarität | 5, 15 | 20.c |
| `R-48` | Force ohne Keyword | 2, 7, 11 | 20.d |
| `R-49` | Verbot | 2, 4 | 20.d |
| `R-50` | Tag-Policy | 2, 4 | 20.d |
| `R-51` | Mischung | 4, 11 | 20.d |
| `R-52` | Echte Erkennung | 19 | 20.d |
| `R-53` | Unsicherheit | 19 | 20.d |
| `R-54` | Grobe Sprache | 19 | 20.d |
| `R-55` | Verbotene Sprache | 19 | 20.d |
| `R-56` | Fremdanalyzer | 19 | 20.d |
| `R-57` | Alter Bericht | 19 | 20.d |
| `R-58` | Fehlende Library | 1, 19 | 20.d |
| `R-59` | Promptfortsetzung | 6, 19 | 20.d |
| `R-60` | Echter Hostblocker | 19 | 20.d |
| `R-61` | Migration | 16 | 20.d |
| `R-62` | SRX-Präzision | 4 | 20.d |
| `R-63` | Output-Sicherheit | 11, 19 | 20.d |
| `R-64` | Automatischer Work-Root | 6, 19 | 20.d |
| `R-65` | Expliziter Work-Root | 6, 19 | 20.d |
| `R-66` | Kleiner Auftrag | 6, 19 | 20.d |
| `R-67` | Automatische Analysekennung | 6, 19 | 20.d |
| `R-68` | Manuelle Analysekennung | 6, 19 | 20.d |
| `R-69` | Projektloser Request | 6, 19 | 20.d |
| `R-70` | Getrennte Namensräume | 6, 19 | 20.d |
| `R-71` | Work-Bindung | 6, 19 | 20.d |
| `R-72` | Expliziter Request und Override | 6, 19 | 20.d |
| `R-73` | Request-/Report-Paar | 6, 19 | 20.d |
| `R-74` | Echter Speicherblocker | 6, 19 | 20.d |
| `R-75` | Unterbrochener Requestaufbau | 6, 19 | 20.d |

## Anhang E – konkrete Übergabe an die nächste Implementierung

**Als Nächstes:** die im Fortschrittsblock genannte offene Audit-Nacharbeit, derzeit `AUDIT-REC-03.C`. Zuerst das neueste Result nach dieser Planaktualisierung auswerten; weder die ursprüngliche Planungsbasis noch die historische Auditbindung als neue Patchbindung wiederverwenden. Die reguläre Fortsetzung `5.t.W` bleibt bis `AUDIT-CLOSE` gesperrt. Eine sichere zusammenhängende Anzahl freigegebener Folgeschritte darf nach BD-001 hinzugenommen werden; Kennungen, Messages und Prüfungen müssen zu den tatsächlichen Zwischenständen passen.

Die Planaktualisierung ändert diesen Plan und die nötigen bestehenden Entwicklungsanleitungen zur Bereinigung überholter Testvorgaben. Spezifikation, Prüfbericht, Produktcode, Tests und CI-Infrastruktur bleiben unverändert. Der Entrypoint verwendet die vorhandenen vollständigen Apply-Prüfungen vor seinem einen OFF-PLAN-Commit. Eine erfolgreiche Planaktualisierung ist kein Nachweis der erst geplanten Produktreparaturen.

**Offen bleiben 648 reguläre Produktpositionen sowie die ausdrücklich offenen Audit-Nacharbeiten.** Detaillierte Planung ist keine Zusage über Bundleanzahl, Dauer oder automatische Releasefreigabe. Die tatsächliche Bündelgröße wird während der Umsetzung flexibel und sicher gewählt.

## Historischer Testpolicy-Nachtrag vom 21. September 2026

Die folgenden damaligen Ausführungsvorgaben sind durch TD-002 abgelöst; die
beschriebenen historischen Ergebnisse werden nicht nachträglich umgedeutet.

`TEST-POLICY.a.W` setzt den lokalen Vier-Worker-Standard und den CI-Starter um.
`TEST-POLICY.a.R` sichert Fehlerfälle und isolierte CI-Nachweise ab.
`TEST-POLICY.a.C` führt die wiederverwendbare Ausführungskonfiguration zusammen.
Die Produktfolge bleibt unverändert; danach folgt 4.d.W.

Der letzte zurückgegebene Apply-Nachweis bestätigt Bundle 005. Die früheren
Auslieferungen 003/004 wurden nicht als vollständiger Erfolg nachgetragen.

CI-Nachweise verwenden frische exklusive Verzeichnisse. Fehler, fehlende/ungültige
Berichte und nicht äquivalente Eingangsbindungen verhindern den Gesamterfolg.
Ein gemeinsamer summary.json wird nur vom Controller veröffentlicht.

CI-Referenzsteuerung und CLI-Argumente sind getrennt; lokaler Runner und CI-
Starter verwenden denselben Vier-Worker-Default. Der einzige Scheduler bleibt xdist.

## Historischer Zusatzauftrag BUNDLE-CI (Bundle 009)

Die damalige Testauswahl, automatische CI-Auslösung und serielle GitHub-Referenz
sind aufgehoben. Aktuelle Ausführung siehe TD-002 und lokale AGENTS.md.

- BUNDLE-CI.a.W: gezielte lokale Testauswahl und Dev-Abschlussauslösung implementiert; OFF-PLAN, Produktzähler unverändert.
- BUNDLE-CI.a.R: ungültige Revisionen, Duplikate, unvollständige Teilnachweise und unsichere Berichtspfade abgesichert; keine Zählererhöhung.
- BUNDLE-CI.a.C: Auswahl-/Beobachtungsvertrag von Prozessausführung getrennt; W/R-Verhalten unverändert.

### Bundle 009 – lokaler Abschluss und CI-Übergabe

Die sechs Zwischenstände wurden damals jeweils durch die dokumentierte Auswahl kompletter Testdateien parallel mit vier Workern geprüft. Dies ist kein Vollsuite-, CI- oder Release-Nachweis. Der damalige Abschlusscommit trägt `SpecRoad-Bundle: 009` und `SpecRoad-Bundle-Final: true`; frühere Commits tragen `false`. Die damalige Planung sah nach Veröffentlichung auf `dev` automatische parallele GitHub-Vollprüfung und für Bundle 012 einen automatischen Parallel-/Seriell-Vergleich vor. Das sind keine aktuellen Ausführungsanweisungen und keine Behauptung, dass diese geplanten Läufe tatsächlich erfolgreich waren.
