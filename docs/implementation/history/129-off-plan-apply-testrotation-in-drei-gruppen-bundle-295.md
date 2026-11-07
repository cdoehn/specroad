# OFF-PLAN – Apply-Testrotation in drei Gruppen (Bundle 295)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Apply-Testrotation in drei Gruppen (Bundle 295)

Auf Nutzerauftrag vom 17. Oktober 2026 wird der Test-Runner von zwei auf drei
feste Gruppen umgestellt. Die bestehenden Testnummern bleiben erhalten; der
neue Rotationsstart bindet den bestätigten Apply-HEAD vor der Umstellung.
Diese technischen Nacharbeiten erhöhen den Produktstand **468/900** nicht;
anschließend folgt unverändert **11.m.W**. Die Arbeitsregel steht in der lokalen
AGENTS.md, der ausführbare Vertrag in Runner und Registry.

- [x] **APPLY-THIRDS.W:** Registry-Version 2, gebundene Migration und Modulo-3-Auswahl samt explizitem Teiltestbericht implementieren; historische Version 1 erhalten. Commit: `test(apply): Drei feste Testgruppen an erfolgreiche Commits binden`.
- [x] **APPLY-THIRDS.R:** Den Auswahlbericht um überprüfbare Nummern-/Registrybelege ergänzen und Änderungen während des Laufs abweisen. Commit: `test(apply): Drittelauswahl und Wiederholungen vollständig belegen`.

**R-Beleg:** Der Bericht bindet die ursprünglichen Registrybytes sowie Testidentität,
Nummer, Gruppe und Commitbasis. Abweichende Beobachtungen, geänderte Eingaben und
Wiederverwendung eines Reportverzeichnisses bleiben ohne Erfolgsnachweis erhalten.

- [x] **APPLY-THIRDS.C:** Unveränderte Registry- und Auswahlregeln vom Prozessrunner trennen; sämtliche W-/R-Testbytes erhalten. Commit: `refactor(testing): Registryvertrag der Apply-Rotation isolieren`.

**C-Zustand:** Sämtliche Funktionskörper bleiben strukturell identisch; die reinen
Nummerierungs-, Auswahl- und Belegfunktionen liegen gemeinsam in einem privaten
Modul. Der Runner behält Git-, Prozess- und Beobachtungsbindung unverändert.
