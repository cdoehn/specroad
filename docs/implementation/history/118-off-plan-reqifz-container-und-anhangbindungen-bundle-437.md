# OFF-PLAN – ReqIFZ-Container und Anhangbindungen (Bundle 437)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – ReqIFZ-Container und Anhangbindungen (Bundle 437)

Revision 15 dokumentiert **REQIFZ-CONTAINER-CONTRACT**, **delegiert gemäß
SPECROAD-DECISION-1**. Spezifikation **0.2.20, D.1.4**, legt explizite
Dokumentauswahl, dokumentrelative Anhangbindungen und ein aus tatsächlichen
Bytes abgeleitetes Transportmanifest für 14.k fest. Alternativen, geprüfte
Quellen, Grenzprüfung und offene W/R/C-Abnahmen stehen unmittelbar bei 14.k.
Keine persönliche Einzelzustimmung, technische Produktfreigabe oder
Fremdtool-Abnahme wird behauptet.

- [x] **REQIFZ-CONTAINER-CONTRACT:** ReqIFZ-Container und Anhangbindungen verbindlich klären. Commit: `docs(spec): ReqIFZ-Container und Anhangbindungen präzisieren`.

**Übergabegrenze:** Genau ein OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und ausschließlich notwendigen aktiven Katalog-Hashbindungen.
Produktcode, Tests, Testnummern, Fixtures, Runner, Workflow und historische
Evidence bleiben unverändert. Produktstand **600/900**, zuletzt **14.j.C**,
nächstens **14.k.W**, bleibt unverändert; alle drei 14.k-Phasen bleiben offen.
Erst nach dem erfolgreichen parallelen Apply-Gate setzt der Entrypoint den
Offplan-Marker und die Bundlenummer auf 437. Keine Produktposition wird erhöht.

**Prüfgrenze:** Keine Produktverhaltensänderung und keine erfundenen
Dokumentationstests. Vollständige Collection-/Katalogprüfung mit null
Testkörpern und native Paketprüfung bleiben erhalten. Apply führt vor
diesem Commit ausschließlich **Gruppe 1/3**, Commitfolge **145**, mit
**6.324 Tests** und vier parallelen Workern aus. Kein Vollsuite-/Release-
Nachweis; Ergebnisse dieser künftigen Gruppe werden nicht vorweggenommen.
Übergabe als `spec_clarification`, danach Ende des Einzelauftrags.
Control-/Watcher-/CI-Zustände werden nicht verändert. Der nächste
Produktauftrag setzt den geklärten Schritt um; keine zweite Phase hier.

**Beobachtete Dev-Katalogprüfung:** Vollständige Collection mit
**18.972 eindeutigen Testidentitäten**, Exit **0**, keine Katalogfehler,
**0 ausgeführte Testkörper**, `full_suite_passed=null`. Bestehende Tests,
Oracles, Fixtures und dauerhafte Testnummern bleiben bytegleich. Nur aktive
Spezifikations-Hashbindungen wurden konsistent fortgeschrieben; historische
Evidence bleibt unverändert. Dies ist kein neuer Produktverhaltensnachweis.
Gebundener Quellstand: `b35a1ac216782ea5c865ca2d3fdd9cd449ef3e2d1c17a8394b4443f42dd1c639`;
Katalog: `44e98fd26eed1e2d28fdd82c2b82d201672fe1ac37c96e8053f5b76806df14b6`.
