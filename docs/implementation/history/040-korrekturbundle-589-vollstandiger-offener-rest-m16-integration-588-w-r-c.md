# Korrekturbundle 589 — vollständiger offener Rest M16-INTEGRATION-588.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 589 — vollständiger offener Rest M16-INTEGRATION-588.W/R/C

Nativ geprüftes Fehler-Result:
`04f67b36428bd1d4664a6f72549988bf0ba22d2d1f4b7c44e25e017ac1ccb92f`,
HEAD `df4d8ca0a696a72a750a3219aab97076de192066`, Dirty-Fingerprint
`df1bdc49d54d7894`. M16-SCOPE-588 wurde nach 7307 bestandenen Tests
committed. W scheiterte mit 10 Fehlern bei 9485 bestandenen Tests; R/C
wurden nicht begonnen. Der vollständige Arbeitsstand entspricht der
angekündigten W-Stage. Der erfolgreiche Klärungscommit bleibt erhalten.

Die tatsächlichen Fehler betreffen die neue Integrationsgrenze:
- Das unabhängige Build-Inventar muss auch den neu installierten synthetischen
  Migrationsvektor binden; Bytes und fehlende Ressourcen bleiben geprüft.
- Registry-/Capability-Erwartungen enthalten die drei neuen Migrationsbefehle
  und ihre echten Plan-/Schreibklassen. Eine Registry ohne Work-fähige Befehle
  muss weiterhin fehlende Work-Fähigkeit melden.
- Bootstrap lädt den ModelGate-Typ erst für ausdrücklich übergebene Gates;
  leere Standardgates aktivieren keine Sicherheits-/Projektbausteine.
- Das handgeschriebene Vektor-Manifest verwendet die eingefrorene Vertrags-ID
  specroad-reference-0.1; Referenzordnername und Vertragsidentität sind verschieden.
  Vollständige unabhängige Zielbytes bleiben der Vergleichsmaßstab.
- Die öffentlichen Bundle-Aufrufe der Integrationstests wählen explizit den
  vollständigen Projektscope, bevor Restore beziehungsweise Ablehnung geprüft wird.
- Restore prüft die deklarierte Quellformatgrenze vor dem History-Fold, sodass
  eine unqualifizierbare Legacy-Registrierung den bestehenden Fehlervertrag behält.

Spezifikation 0.2.61 und aktive Katalogbindungen bleiben unverändert. Keine
neue Klärung, keine Freigabe und keine Budgetänderung. Alle offenen IDs und
Rollen W/R/C werden vollständig fortgeführt, mit Vorherbytes aus diesem Result.
Zusätzlich zu den ursprünglichen Pflichtauswahlen werden Build-Identität,
Registry, Capabilities und Bootstrap vollständig geprüft. Jede Stage erhält
ihr eigenes N=3-plus-Pflichtgate (Gruppen 2/0/1) vor ihrem Commit. C behält
alle verfügbaren Tests als ungefilterte Pflichtauswahl und bytegleiche R-Tests.
Dev führt keine Verhaltenstests aus. M16 bleibt bis zum tatsächlichen
erfolgreichen C-Commit und vollständigen Suite-Gate offen; Produktstand 693/900.
