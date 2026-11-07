# OFF-PLAN Bundle 041 – historischer Venv-Fix und damalige Full-Strategie

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

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
