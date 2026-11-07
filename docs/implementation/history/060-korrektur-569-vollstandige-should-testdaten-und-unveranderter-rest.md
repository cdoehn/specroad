# Korrektur 569 — vollständige should-Testdaten und unveränderter Rest

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrektur 569 — vollständige should-Testdaten und unveränderter Rest

Das nativ geprüfte Result mit SHA-256
`d260ed25293d4fc40bc2f83c10403a70ba1e514382739b5e04242e733499030f`
belegt das fehlgeschlagene Gate von 16.e.W: 6955 Tests bestanden, ein Fehler
im neuen positiven should-Fall. Kein Commit entstand. Der tatsächliche
Produktstand bleibt 672/900; alle IDs 16.e.W, 16.e.R und 16.e.C sind offen.
Der erhaltene W-Arbeitsstand ist vollständig in der ersten Korrekturstufe
enthalten; bereits vorbereitete Häkchen sind kein Commit-Erfolgsnachweis.

Ursache: Der positive Test lieferte normative_force=should ohne die nach S.2
und SR-REQ-0071 zwingenden Abweichungsbedingungen und die zuständige Autorität.
Die vorhandene Zielvalidierung wies diesen unvollständigen Datensatz korrekt
mit schema_any_of ab. Die synthetische Quelle enthält diese Angaben jetzt
ausdrücklich vor der Vollhashbindung; der Test prüft ihre unveränderte
Übernahme. Keine Erweiterung des geschlossenen Mappings und keine erfundene
fachliche Freigabe. Drei negative Fälle verlangen weiterhin die Abweisung,
wenn jeweils ein Pflichtwert oder beide fehlen; die Quelle bleibt bytegleich.

Produktcode, normative Spezifikation und W/R/C-Verhalten bleiben unverändert.
Fortgesetzt wird der vollständige ursprüngliche Commitplan mit unveränderten
IDs, Messages und Rollen implementation. Korrekturbindung und sämtliche
Vorherbytes beziehen sich ausschließlich auf dieses neue Fehler-Result.
Jede Stufe erhält erneut ihr eigenes N=3-plus-Pflichtauswahl-Gate in Apply;
W bleibt in Gruppe 1, anschließend folgen 2 und 0. Dev führt keine Tests aus.
Nach einem erfolgreichen C-Commit wäre 675/900 erreicht, 16.f.W bleibt danach
offen. Keine neue Klärung und keine Änderung des Control-Budgets.
