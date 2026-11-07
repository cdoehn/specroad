# PY310-REPAIR – OFF-PLAN-Portabilitaetskorrektur (Bundle 012)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

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
Pruefdetails: [`Python_310_Compatibility.md`](../../development/Python_310_Compatibility.md).
