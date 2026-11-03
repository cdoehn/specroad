# ZIELBILD: Control für mehrere Projekte – NOCH NICHT UMGESETZT

**Status: ZIELBILD / NOCH NICHT UMGESETZT.**
Stand: 29. Oktober 2026. Dokumentationsauftrag: OFF-PLAN `MULTIPROJECT-TARGET`.

Dieses Dokument beschreibt einen möglichen künftigen Ausbau. Seine Aufnahme in
das Repository implementiert und aktiviert keinen Mehrprojektbetrieb. Es ist
weder ein ausführbarer Entwicklungsauftrag noch eine Erweiterung bestehender
Befugnisse. Die geltenden [Bedienregeln](../AGENTS.md), die
[Spezifikation](../spec/SPECIFICATION.md) und der
[Implementierungsplan](commit-plan.md) bleiben maßgeblich. Der bestehende
Planstand 6/6 wird durch dieses Dokument nicht erhöht.

Alle nachfolgenden Soll-Aussagen, Befehlsbeispiele und Abnahmepunkte beziehen
sich ausschließlich auf eine spätere, gesondert zu beauftragende Umsetzung.
Insbesondere existiert `--project` heute nicht.

## 1. Ziel und Umfang

Ein gemeinsamer Control-Programmstand soll mehrere Softwareprojekte bedienen,
die denselben bestehenden Ablauf verwenden:

```text
Projektprofil -> vorhandener Dev-Thread -> gebundenes Patch-Bundle
              -> bestehender PatchHarbor-Watcher -> Apply und Tests
              -> geprüftes Result -> nächster begrenzter Dev-Auftrag
```

Jedes Projekt soll unabhängig eingerichtet, geprüft, gestartet, pausiert,
fortgesetzt und kontrolliert gestoppt werden können. Vorgeschlagen wird eine
eigene Dienstinstanz je Projekt mit gemeinsamem Programmcode und getrennten
Laufzeitdaten. Ein Fehler oder Stopp in Projekt A darf keinen neuen Auftrag,
Budgetwechsel oder Lebenszykluswechsel in Projekt B verursachen.

Der erste Ausbau bleibt auf dem vorhandenen Linux-/systemd-Modell und dem
bestehenden Codex-/PatchHarbor-Ablauf. Andere Betriebssysteme, andere
Modellanbieter, direkte SSH-Prozesssteuerung, ein zentraler Scheduler und eine
grafische Oberfläche sind kein Bestandteil dieses Zielbilds. Auch die
gleichzeitige Ausführung mehrerer Applys wird damit nicht zugesagt.

## 2. Ausgangslage im untersuchten Code

| Bereich | Bereits vorhanden | Für mehrere Projekte noch erforderlich |
| --- | --- | --- |
| Konfiguration | Dev-Verzeichnis, Exchange, Thread, Core-Interpreter und Transport sind konfigurierbar. | Explizite Projektkennung, Apply-Ziel und versioniertes Projektprofil. |
| Erstquelle | Native Result-Prüfung und einmalige Initialisierung der Historie. | Die feste Erwartung eines benachbarten `specroad-apply` durch eine geprüfte Projektzuordnung ersetzen. |
| Lokale Daten | Private Konfiguration, Datenbank, Jobs, Status und IPC-Socket. | Vollständig getrennte Pfade je Projekt; `--config` allein trennt diese heute nicht. |
| Dienst | Ausschließlich `specroad-control.service`, manueller Lebenszyklus. | Explizit zugeordnete und überprüfte Dienstinstanzen je Projekt. |
| Dev-Vertrag | Begrenzter Auftrag, Result-/Patch-Bindung, Verträge 1/2/3. | Neue projektspezifische Aufträge ohne feste SpecRoad-Namen und ohne rückwirkende Änderung alter Verträge. |
| Sperren | Gemeinsame Sperren für Dev-Arbeitsverzeichnis und Thread. | Zusätzlich eindeutige Apply-Zielzuordnung über alle Projektprofile und Altinstanzen hinweg. |
| Fehlerbehandlung | Persistente Overload-, Recovery-, Pause- und Klärungsregeln. | Dieselben Garantien pro Projekt einschließlich belegter Migration. |

Relevante Ausgangsstellen sind [config.py](../specroad_control/config.py),
[local.py](../specroad_control/local.py), [bootstrap.py](../specroad_control/bootstrap.py),
[systemd_unit.py](../specroad_control/systemd_unit.py),
[service.py](../specroad_control/service.py),
[job_contract.py](../specroad_control/job_contract.py),
[readonly_evidence.py](../specroad_control/readonly_evidence.py) und
[automation.py](../specroad_control/automation.py).

Die Trennung von Control, Dev und Apply sowie die native Paketvalidierung
werden weiterverwendet. Der bestehende PatchHarbor-Watcher unterstützt bereits
mehrere registrierte Repositories; für dieses Zielbild ist kein zweiter Watcher
und keine Änderung seines Codes vorgesehen.

## 3. Projektprofil und Vertrauensgrenzen

Ein künftiges Profil soll mindestens folgende Angaben eindeutig binden:

| Angabe | Zweck und Bedingung |
| --- | --- |
| Stabile Projektkennung | Eindeutige interne Zuordnung; validierter Name für Pfade und Dienstinstanz. Ein Anzeigename ist keine Identität. |
| Dev-Arbeitsverzeichnis | Explizite lokale Arbeitskopie; muss zum konfigurierten Dev-Thread passen. |
| Apply-Repository | Expliziter Zielpfad plus nativ bestätigte PatchHarbor-Repository-ID. Keine Ableitung aus einem Verzeichnisnamen. |
| Exchange und Archiv | Expliziter zulässiger Übergabebereich. Gemeinsamer Exchange bleibt möglich; die Zuordnung erfolgt über Bindungen, nicht Dateinamen. |
| Vorhandener Dev-Thread | Vom Nutzer ausgewählte echte Thread-ID; kein neuer, geratener oder automatisch gewählter Thread. |
| Werkzeuganbindung | Bestehender Codex-Zugang, expliziter Transport und vorhandener PatchHarbor-Interpreter. Keine Installation weiterer Daemons. |
| Projektregeln | Eindeutige Verweise auf freigegebene AGENTS-, Spezifikations-, Plan-, Test- und Commitvorgaben. |
| Vertragsversion | Versionierter technischer Auftrag und zugehörige Projektregelbindung für neue Aufträge. |

Das maßgebliche Start-Result wird weiterhin nur bei der Ersteinrichtung nativ
geprüft und in der externen Historie gebunden. Result-Pfad, Result-ID und
Result-SHA werden keine dauerhaften Startschalter in der Konfiguration.
Eine bestehende Historie darf durch Umkonfigurieren nicht neu initialisiert
oder auf ein anderes Projekt umgebogen werden.

Profile und Laufzeitdaten bleiben außerhalb von Git-Repositories und Exchange.
Echte Konfigurationen, Thread-IDs, Zugangsdaten und private Auftragsbelege
gehören nicht in Dokumentations- oder Patch-Payloads. Pfadüberlappungen,
physische Aliase, unzulässige Links, fremde Eigentümer und unsichere Rechte
müssen nach den bestehenden Schutzregeln geprüft werden. Diese Regeln sind
auf alle konfigurierten Dev-/Apply-/Exchange-Ziele zu erweitern.

Änderungen an Zielidentität, Thread oder vertragsrelevanten Regeln müssen
explizit erfolgen. Ein laufender oder unklarer Auftrag behält seine ursprüngliche
Bindung; neue Profilwerte dürfen seine Recovery-Belege nicht nachträglich ändern.

## 4. Getrennte Instanzen, gemeinsame Zielsperren

Je Projekt werden eigene Konfiguration, `automation.sqlite3`, Statusdatei,
Jobs/Attempts, Probe-Belege, IPC-Socket und lokale Bedien-/Worker-Sperren benötigt.
Die genaue Verzeichnisstruktur und das neue Konfigurationsschema sind erst in
der späteren Umsetzungsspezifikation festzulegen.

Davon getrennt bleiben die Zielsperren gemeinsam für den angemeldeten Benutzer.
Zwei Profile dürfen nicht gleichzeitig denselben Thread, dieselbe physische
Dev-Arbeitskopie oder dasselbe registrierte Apply-Ziel für Entwicklung beanspruchen.
Die bestehende SpecRoad-Instanz muss in denselben Ausschluss einbezogen werden.
Projektlokale Sperrverzeichnisse allein würden diesen Schutz aufheben.

Ein künftiger Start prüft Profil, Historienzuordnung und Zielbelegung. Bei
Konflikten wird der konkrete Konflikt gemeldet; weder ein fremder Dienst noch
ein fremder Dev-Turn wird beendet. Sperren werden nicht durch Löschen ersetzt.
Andere manuelle Codex-Clients bleiben außerhalb einer universellen Sperre;
manuelle Entwicklung erfordert weiterhin vorheriges Pausieren und bestätigte
Inaktivität der betroffenen Automatik.

## 5. Projektbezogene Bedienung und Dienste

Mögliche spätere CLI, ausdrücklich noch nicht vorhanden:

```bash
# ZIELBILD – NICHT AUSFÜHREN: --project ist noch nicht implementiert.
./control --project specroad status
./control --project beispielprojekt start
./control --project beispielprojekt pause
./control --project beispielprojekt resume
./control --project beispielprojekt stop
```

Einrichtung, check, Probe und Recovery müssen dieselbe eindeutige Projektauswahl
verwenden. Fehlende oder mehrdeutige Auswahl darf keinen beliebigen Dienst
ansprechen. Eine optionale Gesamtübersicht liest nur Zustände.

Dienstnamen und Unit-Dateien werden aus validierten Projektidentitäten erzeugt
und auf Eigentümerschaft geprüft; keine frei übergebbaren systemd-Zielnamen.
Start, Pause, Fortsetzen und Stopp wirken nur auf die gewählte Instanz.
Installation erzeugt ausschließlich die freigegebenen privaten Dateien und
startet keine Entwicklung. Es gibt weiterhin kein enable, Autostart, Linger,
Timer-, Cron- oder Socket-Aktivierungssetup.

Ein kontrollierter Stopp verhindert Folgeaufträge und lässt bereits begonnene
Entwicklungsarbeit nach dem bestehenden Vertrag abschließen. Der globale
PatchHarbor-Watcher wird davon nicht gestoppt; ein bereits übergebenes Bundle
kann weiterhin Apply und Result-Erstellung durchlaufen.

Die heutigen Bedienregeln erlauben ausschließlich `specroad-control.service`.
Sie müssten für einen tatsächlich beauftragten Mehrprojektbetrieb gezielt um
die eigenen geprüften Projektinstanzen erweitert werden. Dieses Zielbild
erteilt diese Erweiterung ausdrücklich noch nicht.

## 6. Allgemeiner Auftrag und projektspezifische Regeln

Der gemeinsame Auftrag bindet genau ein maßgebliches Result und erlaubt
höchstens ein kanonisches Folgebundle pro Auftrag. Native Validierung,
vollständige Repositorybindung, atomare Übergabe und Abschluss ohne eigene
Warte-/Modellschleife bleiben erhalten. PatchHarbor übernimmt Apply und Tests;
Control veranlasst nach belegtem Abschluss den nächsten erlaubten Auftrag.

Projektspezifisch sind Spezifikation, Plan, W/R/C-/Commitregeln, Testauswahl,
zulässige Arbeitsaufteilung und Befugnisse zur fachlichen Klärung. Diese werden
nicht aus SpecRoad auf andere Projekte übertragen. Der Controller ersetzt keine
fachliche Prüfung und erfindet keine Test- oder Freigabepolitik.

Eine Klärungsregel braucht eine ausdrückliche Freigabe im jeweiligen Projekt.
Ein konfiguriertes technisches Budget erteilt diese Befugnis nicht selbst.
Der bestehende SpecRoad-Vertrag 3 mit bis zu drei aufeinanderfolgenden
Klärungsbundles bleibt inhaltlich unverändert. Eine frei konfigurierbare Anzahl
ist mit diesem Zielbild nicht beschlossen; das wäre eine gesonderte Vertragsfrage.

Neue Aufträge binden Profilidentität und Vertrags-/Regelversion dauerhaft.
Originalprompt, Quelle, Attempts und verbrauchtes Budget bleiben bei Retry,
Overload-Fortsetzung, Neustart und Recovery erhalten. Neue Modell- oder
Denkstufenvorgaben werden nicht implizit eingeführt. Status und check lösen
keinen Modellturn aus; eine Probe bleibt ein gesondert zu beauftragender Aufruf.

## 7. Verträglicher Übergang für SpecRoad

Empfohlen wird zunächst ein Kompatibilitätsprofil für SpecRoad mit den
bisherigen Pfaden, dem bisherigen Dienst und unveränderter Historie. Neue
Projekte erhalten eigene Instanzen. Eine spätere Umbenennung oder Verlagerung
des Bestands ist ein separater, belegter Migrationsschritt.

Zu erhalten sind insbesondere die gespeicherte Scope-Bindung der Datenbank,
Quell-/Result-Ketten, alte Promptbytes, Verträge 1/2/3, Klärungsbudgets,
Retryfristen, Checkpoints sowie `uncertain`, `dev_blocked` und gesetzte Pausen.
Die neue Profilkennung darf nicht einfach zur bisherigen Scope-Berechnung
hinzugefügt werden, wenn dadurch alle Bestandsdaten als fremd erscheinen.

Die gegenwärtige Legacy-Prüfung erkennt teilweise ausdrücklich SpecRoad-
Promptstrukturen. Deshalb kein globales Suchen/Ersetzen von Projektnamen:
alte Leser und Belege bleiben unverändert; neue Aufträge bekommen einen
eindeutig versionierten Vertrag. Unbelegte oder mehrdeutige Migration bleibt
gesperrt und bewahrt sämtliche vorhandenen Daten.

Ein Software-Apply darf weder bestehende Dienste starten/stoppen noch echte
Profile, Datenbanken oder Aufträge automatisch migrieren. Einrichtung und
Migration erfolgen später ausdrücklich und offline nach den festgelegten
Voraussetzungen. Sie starten keinen Dev-Turn und heben keine Pause auf.

## 8. Vorgeschlagene Umsetzungsschritte – sämtlich offen

Die folgenden Punkte sind eine Abhängigkeitsskizze, keine bereits freigegebene
Commit- oder Bundlefolge. Zusammengehörige, vollständig geprüfte Änderungen
können später gemeinsam geliefert werden; künstliche Teilpakete sind kein Ziel.

1. **Vertrag festlegen:** Profilfelder, Identitäten, Auswahlverhalten, Scope-
   Kompatibilität, Dienstzuordnung und Migrationsregeln spezifizieren. Geltende
   AGENTS-/Spezifikations-/Planvorgaben erst mit Umsetzungsauftrag ergänzen.
2. **Profil und Speichertrennung:** Konfigurationsschema, `Paths`, Bootstrap-
   Prüfung und gemeinsame Zielsperren erweitern; bestehendes SpecRoad erhalten.
3. **Bedienung und Lebenszyklus:** CLI, IPC, Status, Unit-Erzeugung und
   Dienstbedienung konsistent an dieselbe Projektidentität binden.
4. **Auftragsvertrag:** Allgemeine und projektspezifische Regeln trennen;
   Profilbindung durch Dispatch, Ledger, Retry, Overload und Recovery führen.
5. **Abnahme und Einführung:** Isolierte Mehrprojekt-/Bestandsprüfungen,
   native Paketprüfung und freigegebene Einrichtung eines zweiten Projekts.

## 9. Erforderliche Abnahme – NOCH NICHT DURCHGEFÜHRT

- [ ] Zwei Profile besitzen nachweislich getrennte Datenbanken, Jobs, Sockets und Dienste.
- [ ] Start/Pause/Fortsetzen/Stopp für A verändern weder Zustand noch Budget von B.
- [ ] Unbekannte/mehrdeutige Projektwahl führt zu keinem Dienst- oder Modellaufruf.
- [ ] Doppelte Threads, Dev-Arbeitskopien und Apply-Ziele werden auch über Aliasprofile und Altinstanzen gesperrt.
- [ ] Fremde Results/Patches im gemeinsamen Exchange werden nicht übernommen; alle nativen Bindungsprüfungen bleiben wirksam.
- [ ] Ein fehlgeschlagenes Apply wird nur innerhalb seiner eigenen Projektkette behandelt.
- [ ] Neustart, Verbindungsverlust, Overload und Recovery erhalten Zuordnung, Checkpoints, Pausen und verbrauchte Budgets.
- [ ] Historische SpecRoad-Verträge und exakte Promptbelege funktionieren ohne Umschreiben oder neues Seed weiter.
- [ ] Fehlende fachliche Delegation erlaubt keine automatische Klärung; neue Profile erhalten keine SpecRoad-Befugnisse durch Vererbung.
- [ ] Installation und Migration starten weder Dienste noch Modelle und aktivieren keinen Autostart.
- [ ] Vorhandener PatchHarbor-Watcher bleibt allein für Apply/Tests/Results zuständig.
- [ ] Die vollständige parallele Control-Verhaltenssuite und zusätzliche isolierte Mehrprojektszenarien sind erfolgreich.
- [ ] Ein ausdrücklich freigegebener echter Zweitprojektlauf bestätigt die Integration; Testdoubles werden nicht als Remote-Sichtbarkeitsnachweis ausgegeben.

Die Abnahmetests prüfen Verhalten und maschinenlesbare Verträge. Es werden keine
Tests nur für Dokumentformulierungen oder die Existenz dieses Zielbilds verlangt.
Echte Modell-/Probeaufrufe und produktive Dienststarts brauchen weiterhin einen
ausdrücklichen Auftrag; die automatischen Tests verwenden isolierte Gegenstellen.

## 10. Voraussetzung für die spätere Umsetzung

Vor Beginn sind der erste weitere Projektkandidat, dessen freigegebener
Entwicklungsworkflow und die genaue Profil-/Migrationsspezifikation festzulegen.
Es müssen keine echten Zugangsdaten in dieses Dokument eingetragen werden.
Unabhängige Bedienbarkeit ist von gleichzeitig laufenden Modellaufträgen und
der verfügbaren Testkapazität zu unterscheiden; globale Ressourcenplanung ist
hier nicht implementiert und nicht als Zusatzfunktion beauftragt.

**Abschlussstatus dieses Dokuments: ausschließlich ZIELBILD; Mehrprojekt-Control
ist NOCH NICHT UMGESETZT. Die bestehende Automatik wird dadurch nicht aktiviert.**
