# Korrekturbundle 604 — deklarierte Anhänge im vollständigen Rest 17.d.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 604 — deklarierte Anhänge im vollständigen Rest 17.d.W/R/C

Manueller Korrekturauftrag vom 5. November 2026. Maßgeblich ist das native
Fehler-Result `specroad-apply_Result_130938_1105_2d00df.zip`, SHA-256
`410dcec8c0a308ef2a2d88d901d9c65fdb787698e492cce18104e0f66d7cdf4c`,
HEAD `59473dea8df503bae58e99945a3e303b50b9c903`, Zustandsfingerprint
`cbb384c1f99f3b69` nach `patchharbor-state-v1`.

Der Klärungspräfix MERGE-COLLECTIONS-603 wurde nach 6.861 erfolgreichen Tests
committed und bleibt vollständig erhalten. 17.d.W wurde ausgebracht, aber
nicht committed: 7.409 von 7.410 ausgewählten Tests bestanden; der konkrete
Integrationstest `test_qualified_project_sources_feed_collection_and_attachment_candidates_without_writes`
scheiterte mit `KeyError: attachments/ours.bin`. R/C wurden noch nicht
begonnen. Die bestätigte Produktposition bleibt 702/900; Checkboxen und Zähler
in den folgenden Stage-Zielständen werden erst mit erfolgreichem Gate und
echtem Commit wirksam. Die gemessenen Testgruppen sind kein Vollsuite-Nachweis.

Ursache: Die neue Fixture legte die beiden zusätzlichen Binärdateien nur im
Dateisystem ab. Der vorhandene native Projektsnapshot übernimmt deklarierte
Anhänge aus Artefakt-Deskriptoren; ohne Deklaration gehören diese Dateien nicht
zur qualifizierten Quellmenge. Das Merge-Ergebnis konnte sie daher nicht
enthalten. Die vorhandene Quell-/Scope-Policy und der Mergealgorithmus werden
nicht gelockert. Die Fixture erhält je Seite einen eigenen ausdrücklich
synthetischen Evidence-Datensatz mit eindeutiger ID und korrektem
AttachmentDescriptor (Pfad, Medientyp, Größe, tatsächlich berechneter Hash).
Bestehende recorded Evidence und deren Anhänge bleiben bytegleich.

Das ursprüngliche Integrationsorakel bleibt bestehen und wird verstärkt:
Die vollständig qualifizierten Dateien müssen vor dem Merge mit den
vorbereiteten Quelldateien übereinstimmen. Für jeden neuen Anhang prüft die
Inventur tatsächliche Anwesenheit ausschließlich auf seiner Seite, Pfad,
Größe, Rohbyte-/Werthash und bytes-v1. Danach bleiben die exakten ursprünglichen
Merge- und Seiteneffektprüfungen bestehen. Alle Testidentitäten/Nummern,
Fachregeln und Pflichtdateien aus Bundle 603 werden erhalten; passende
Projektbundle-/Quellregressionen ergänzen die Pflichtauswahl.

Bundle 604 enthält ausschließlich den vollständigen offenen Rest mit den
ursprünglichen IDs und Rollen 17.d.W/R/C. Die erste Stage übernimmt alle
19 erhaltenen dirty Pfade einschließlich der vier untracked Dateien, mit
vollständigen Vorherbytes aus diesem Fehler-Result. Kein erfolgreicher
Commit wird wiederholt, nichts zurückgesetzt und keine neue Detailklärung
angelegt. Normative Spezifikation und aktive Katalogbindungen bleiben
bytegleich zu den jeweiligen ursprünglichen 603-Zuständen. Nach dem bereits
committeten Klärungspräfix ist diese Übergabe normales `patch_ready`.

Dev führt ausschließlich Syntax, reine Collection und native Paketprüfung
aus; keine Verhaltenstests und keine erfundene Abnahme. Jede Stage erhält
vor ihrem Commit ihr eigenes gefiltertes N=3-Gate plus ungefilterte vollständige
Pflichtauswahl. Erst danach folgt der nächste reale Zustand. Das Paket wird
atomar an Exchange übergeben; kein Dienststart, keine eigene Apply-/Warte-
oder Fortsetzungsschleife. Endziel bleibt 705/900, danach offen 17.e.W.
