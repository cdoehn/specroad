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
Persistente Work-Identität, Wiederaufnahme, Phasensummen, Kontrollintervalle und
vollständige Runtime-/Plattformabnahme folgen in den dafür vorgesehenen Schritten.
Die Requirements 0576, 0577, 0594 und 0595 erhalten begrenzte Teilnachweise;
0578 bleibt bis zur Kontrollpunktintegration offen.
