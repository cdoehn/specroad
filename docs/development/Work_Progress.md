# Gemessenes kleinstes Fortschrittsfenster

`specroad.work.progress.advance_read_only_work(store, call, cwd=...)` verbindet
die bestehende [Read-only-Wiederaufnahme](Work_Resume.md) mit einer aktiven
`InvocationConsumption`. Der Aufrufer beginnt und beendet das Messfenster,
auch im Fehlerfall:

```python
call = consumption.begin({"--step-cpu-ms": 1, "--step-wall-ms": 1})
try:
    window = advance_read_only_work(store, call, cwd=current_root)
finally:
    measurement = call.finish()
```

Die unterstützte kleinste Einheit ist der vollständige sichere Bootstrap-
Handler des bereits gebundenen Einheitenplans. Ein weiches Ziel, das schon
vor diesem Aufruf überschritten wurde, verhindert dessen Versuch nicht.
Die Messgrenzen umfassen erneute Kompatibilitätsprüfung, wirkliche Ausführung
und dauerhafte Checkpointveröffentlichung. Es gibt keine präemptive Zeitgarantie
für den Handler oder native I/O und keine Unterbrechung der Veröffentlichung
aufgrund eines weichen Budgetereignisses.

`ReadOnlyWorkWindow` enthält den tatsächlichen `ReadOnlyResumeStep` und eine
abgetrennte Projektion mit vorherigem Checkpoint, neuen beziehungsweise
wiederverwendeten Einheiten-IDs und den beiden Messbeobachtungen. Neue Arbeit
muss ein gültiger unmittelbarer Nachfolger des unabhängigen Anfangsstands sein.
Eine bestätigte Ergebniseinheit wird erneut geprüft und wiederverwendet, ohne
den Handler erneut auszuführen oder eine leere Folgegeneration anzulegen.
Geänderte Ressourcenprofile beeinflussen weder Auftrag noch Ergebnisbytes.

Unbekannte Messwerte bleiben unbekannt. `consumption_persisted=false` und
`consumption_scope=caller_owned_in_process_invocation` weisen den tatsächlichen
Messumfang aus: Die bestehende Messbilanz gehört dem aufrufenden Prozess;
sie wird hier noch nicht in den Work-Checkpoint übernommen. Fehler erhalten
ihre bisherigen Codes und tatsächlichen Speicherzustände. Ein fehlgeschlagener
Mindestversuch liefert kein erfolgreiches Fenster und löst keinen Retry aus.

Die ergänzende API `advance_read_only_work_outcome(store, call, cwd=...)`
führt genau denselben Versuch aus und liefert ein maschinenlesbares
`read-only-work-outcome-v1`. Ein bestätigtes Handlerresultat ergibt
`state=unit_result_available`, den tatsächlichen Handlercode und das vollständige
Fenster. Ein beobachteter Speicher-, Dateideskriptor-, Zugriffs- oder I/O-Fehler
innerhalb der Wiederaufnahme ergibt `state=blocked`, Code 5 und einen getrennten
Blocker mit Ursache, nativer Fehlernummer und erforderlicher Abhilfe.

Der Blocker nennt weder eine erfundene Mindestressourcenmenge noch einen
unbelegten Handler-Versuch: Die Wiederaufnahme umfasst auch Prüfung und
Veröffentlichung. `minimum_resources_known=false` und
`smallest_unit_attempted=null` halten diese Grenze ausdrücklich fest. Fehler
der Messung oder Ergebnisprojektion, unbekannte Fehlernummern, Unterbrechungen,
Sicherheits-, Kompatibilitäts- und Fachfehler behalten ihren Ausnahmevertrag.
Eine Budgetüberschreitung allein erzeugt keinen Blocker.

Nach einem solchen Ressourcenfehler wird der tatsächliche gespeicherte Stand
einmal lesend geprüft. `retained.status=verified_storage_chain` enthält den
jetzt geprüften Checkpoint und seine Einheiten. Das kann bereits eine neue
Generation sein, wenn der Fehler erst nach dem atomaren Zeigerwechsel auftrat.
Ein fehlgeschlagener Readback ergibt `unavailable` mit eigenem Fehler und
`checkpoint=null`; ein nicht veröffentlichter Stand ergibt `unpublished`.
Diese Prüfung der Speicherkette erteilt keine Ausführungsbefugnis.

Es gibt keinen automatischen Retry, Rollback, keine Löschung kritischer Daten
und keinen neuen leeren Checkpoint allein für den Blocker. `blocker_persisted=false` weist aus, dass
der Blocker zum aktuellen Aufruf gehört. Nach Abhilfe muss ein neuer expliziter
Aufruf den Work-Zustand wieder vollständig prüfen; bereits bestätigte
Ergebnisbytes werden dabei wiederverwendet. Selbst vollständig neu gehashte
doppelte Einheiten oder leere Folgegenerationen scheitern am bestehenden
Manifest-/Nachfolgervertrag, bevor der Handler ausgeführt wird.

Dieser erste Fortschrittspfad ist eine Python-API für den geschlossenen
Ein-Handler-Plan. Die Fachausgabe dieses Handlers ist vollständig gespeichert;
der globale Work-Zustand bleibt bis zur gesonderten Schlussprüfung `running`.
Allgemeines Scheduling mehrteiliger Fachpläne, persistente Verbrauchssummen,
Code 8 und CLI-Integration sowie persistierte Blocker gehören zu den offenen
Integrationen. Die Requirements erhalten partielle Nachweise.
