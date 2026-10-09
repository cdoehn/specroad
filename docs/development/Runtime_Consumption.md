# Verbrauchsbilanz

`environment check --metrics --format json` ergänzt `summary.runtime` um die
ausdrücklich angeforderten betrieblichen Messwerte. Fachpayload, Diagnosen,
Projektbindung und Fehlerausgang behalten ihre bisherige Bedeutung. Ohne
`--metrics` startet diese Einbindung keine Verbrauchsmessung.

Der erste Ausschnitt misst den Abschnitt nach erfolgreichem Parsen des Befehls
bis zur Zusammenstellung seines Ergebnisses. Darin liegen die aktuelle
Runtime-/Optionsvorbereitung, die Projektmetadatenprüfung und der Handler.
Interpreterstart, vorheriges Parsen, abschließende Serialisierung/Lieferung und
Kindprozesse sind noch nicht abgedeckt. Der Bericht nennt diese Grenzen;
er ist kein vollständiger Startbenchmark oder Nachweis sämtlicher O.2-Phasen.

CPU-Zeit ist die User-/Systemzeit des aktuellen Prozesses einschließlich seiner
Threads; verstrichene Zeit stammt aus einer monotonen Uhr. Beide werden als
getrennte Nanosekundendifferenzen geführt. Unter Linux liefert RSS das native
Maximum des aktuellen Prozesses über dessen Lebensdauer, umgerechnet von KiB
in Bytes. Es ist keine isolierte Speicherbelegung dieses Aufrufs. Andere
RSS-Plattformadapter und Prozessbaummessung sind noch offen. Die Quellverträge
sind [Python time](https://docs.python.org/3.14/library/time.html#time.process_time_ns),
[Python resource](https://docs.python.org/3.14/library/resource.html#resource.getrusage)
und [Linux getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html).

Eine Messgröße enthält Wert, Einheit, Quelle, Geltungsbereich und Messart.
Fehlende oder widersprüchliche Beobachtungen erhalten `value=null` und
`measurement_kind=unknown`. Eine unbekannte Teilmessung macht auch ihre
Gesamtsumme unbekannt. Registrierte eigene Memory-/Scratchbytes tragen die
Messart `accounted`; sie behaupten weder gesamten RSS noch vollständigen
Dateisystemverbrauch. Nicht registrierte Objekte werden nicht geschätzt.
Hostkapazität wird aus diesen Verbrauchswerten nicht abgeleitet.

Eingebettete Aufrufer können denselben ausdrücklich gehaltenen Zustand verwenden:

```python
from specroad.cli.application import execute_request
from specroad.runtime.consumption import WorkConsumption

work = WorkConsumption()
request = {"command_id": "environment.check", "options": {"--metrics": True}}
first = execute_request(request, consumption=work)
second = execute_request(request, consumption=work)
```

Jeder Aufruf hat ein neues Messfenster. CPU und Wallzeit werden addiert; RSS und
registrierte Bytepeaks werden als Maxima geführt. Die Pause zwischen Aufrufen
geht nicht als Arbeitszeit in deren Summe ein. Ein anderes Ressourcenprofil
ändert die neuen Arbeitsziele, setzt die bisherige Bilanz aber nicht zurück.
Überschreitungen weicher Ziele werden betrieblich ausgewiesen und sperren kein
neues Arbeitsfenster. Fehlgeschlagene Fachaufrufe werden ebenfalls abgeschlossen
und bilanziert, ohne ihren Fehlerausgang zu ändern.

Für andere vertrauenswürdige eingebettete Arbeit stehen `work.begin(options)`,
`call.account_bytes("memory"|"scratch", count, release=False)` und `call.finish()`
bereit. Registrierungen gelten ausschließlich für bewusst verbuchte eigene
Bytes. Offene Registrierungen bleiben über Aufrufgrenzen erhalten, bis der
Aufrufer sie ausdrücklich freigibt. Doppelter Abschluss, überlappende Fenster,
negative Buchungen und Freigabe nicht registrierter Bytes werden zurückgewiesen.
Der Aufrufer schließt ein begonnenes Fenster auch im Fehlerfall in seinem
`finally`-Pfad ab. Die CLI-Einbindung erledigt dies für ihre regulären Ergebnisse.

Der Zustand bleibt prozesslokal und erteilt keine Fortsetzungs- oder
Schreibberechtigung. Native Messungen laufen außerhalb der reinen SRX-Auswertung.
Persistente Work-Identität, Wiederaufnahme, Phasensummen und vollständige
Runtime-/Plattformabnahme folgen in den dafür vorgesehenen Schritten. Die
Requirements 0576–0578, 0594 und 0595 enthalten begrenzte Teilnachweise.


## Kontrollierte eingebettete Arbeit

`specroad.runtime.controlled` bietet ausdrücklich angeforderte Adapter für
`evaluate_srx(program, context, call)`, `load_srx_graph(sources, call, rule_id=...)`,
`fingerprint_file(boundary, path, call, block_size=...)` und
`publish_prepared(preflight, journal, call, held_lock=..., authority=..., gates=...)`.
Sie verwenden ein begonnenes `InvocationConsumption`-Fenster. Der Aufrufer
schließt es auch bei einem Fachfehler mit `finish()` in seinem `finally`-Pfad ab.

SRX liefert reine Fortschrittssignale nach jeweils 512 Expression-Dispatches;
seine geladenen Graphzugriffe nach jeweils 128 Knotenentnahmen/Kantenverarbeitungen.
Der Payloadhasher fordert höchstens 64 KiB und höchstens die bis zum nächsten
Kontrollpunkt fehlenden Bytes an. Kurze Reads werden fortgezählt; jede 64-KiB-Grenze
wird vor dem nächsten Read beobachtet. Die bisherige deterministische SRX-
Verbrauchsrechnung behält ihre bisherigen Zähler, Ereignisse und Fachresultate.
Auch eine gefilterte Kante zählt als tatsächlich bearbeitete Kante.

Die reinen SRX-Generatoren rufen weder Uhr noch Messprovider auf. Nur der äußere,
synchrone Treiber nimmt bei einem Signal eine Messung vor. Phasengrenzen liegen
vor/nach SRX-Validierung und Ergebnisbildung, Graphladen, Auswahl/Sortierung der
Graphansichten, Payloadhashing und nativer vorbereiteter Veröffentlichung.
Ein Fehler erzeugt keinen erfolgreichen Endmarker der unvollendeten Phase.
Native Operationen werden erst nach ihrer Rückgabe wieder kontrolliert.

Die Veröffentlichung delegiert an den bestehenden nativen Writer und benötigt
weiterhin dessen Preflight, gehaltenen Lock und ausdrückliche Autorität. Ein
weiches Budget pausiert oder verweigert sie nicht. Ihr Ergebnis bleibt
`PublishedFiles` im Zustand `committing`: dauerhafte Receipts und Finalisierung
sind weiter nötig. Der Messadapter behauptet weder Rollback noch neue Schreibrechte.

`invocation.controls` enthält aggregierte Kontrollzahlen, keine wachsende Liste
aller Messungen. Intervallpositionen gelten für den jeweiligen Kernel; sie sind
keine globale Vollständigkeits- oder Wiederaufnahmekennung. Die kumulierte Zahl
abgeschlossener Kontrollen steht unter `cumulative.control_checks`.
`durable_checkpoint=false` bleibt ausdrücklich erhalten.

Fehlt eine Zwischenmessung, läuft ein Zähler rückwärts oder ändert sich seine
Quelle, bleibt diese Messgröße für das gesamte Fenster unbekannt. Andere gültige
Messgrößen bleiben nutzbar. Ein zuvor tatsächlich beobachtetes weiches
Überschreitungsereignis wird nicht durch einen späteren Messausfall gelöscht.
Kann die kumulierte Zahl nicht mehr im aktiven JSON-Zahlenvertrag dargestellt
werden, wird sie unbekannt; das bereits vollständig berechnete Fachresultat bleibt
verfügbar. Es wird weder ein Ersatzwert noch ein Hostlimit erfunden.

Diese Adapter decken die genannten vorhandenen Kerne ab. Der Environment-Check
misst weiterhin seinen beschriebenen W-Abschnitt. Eine allgemeine Einbindung in
sämtliche Command-/Snapshot-/Streaming-Verbraucher, persistente Work-Zustände,
Phasensummen, Kindprozesse und weitere Plattformadapter sind damit nicht abgenommen.


Die Implementierung trennt die Messung und Bilanzierung (`consumption`) von der
reinen maschinenlesbaren Metrikprojektion (`_consumption_projection`). Die
CLI-Anbindung (`cli._runtime_metrics`) ergänzt ausschließlich die bereits
vorgesehene betriebliche Zusammenfassung und verwendet bei Environment-Ergebnissen
die tatsächlich aufgelösten Projektbudgets. Fachpayloads, deren Hashbildung,
Kontrollintervalle und die qualifizierten Messquellen behalten ihren Vertrag.
