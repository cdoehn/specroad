# Planbundle 572 — 16.g: Legacy-Manifest und Hashdomänen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Planbundle 572 — 16.g: Legacy-Manifest und Hashdomänen

Basis ist das vollständig nativ geprüfte saubere Result mit SHA-256
`ea561f4d30f5fb6b8363ef50dfeb60f57920b998750b6852e62f61d52cdd5888`
und Abschlusscommit `1759ac767dadbbc9ecdfe4f8fa45c65976e1f15b`.
16.f.W/R/C ist mit drei eigenen Gates (6992, 7007 und 6963 bestandene Tests)
und allen drei Commits abgeschlossen. Ausgangspunkt: 678/900 Produktcommits.
Erfolgreiche Vorgänger werden nicht wiederholt. Q.0/Q.2/Q.3 und 12.20.2
bestimmen den Vertrag vollständig; keine normative Lücke und kein Klärungs-
präfix. Spezifikation und bestehende Freigabegrenzen bleiben unverändert.

W vervollständigt den vorhandenen Manifestgenerator um die tatsächliche
Lesebindung. Das vollständige registrierte Originalinventar wird aus den
Archivbytes rekonstruiert und durch den eingebauten Referenzleser 0.1/1.0.1
qualifiziert. Der gemeinsame native Generator rekonstruiert alle Manifest-
felder einschließlich Quellvertrag, Originalhashes, Identitäts-/Relations-
projektionen, Payloads, Provenienz und Proposal-Transitions; der geschlossene
Vergleich erlaubt keine frei behaupteten Projektionen oder Quellschemata.

Projektgebundene Common-/Record-/Domain-Leser liefern qualifizierte Originale
mit storage_class legacy_immutable und unveränderten Quellbytes. Separat
abfragbare Navigation ergänzt Identitäten; sie behält schema_version 0.1.0
und ist kein materialisiertes 0.2-Original. Reguläre Relationsleser und Show
nutzen diese Projektionen und geben das historische Artefakt unverändert
zurück. Inventarisierung und explizite Modellroot-Erfassung integrieren den
Manifestvertrag. Auch ein eingeschränkter expliziter Ressourcensatz bindet
Manifest und vollständiges registriertes Originalarchiv. Artefaktrows verwenden
legacy-original-bytes-v1, Originalbytehash und Manifest-JCS-Hash; aktuelle
Artefakte behalten ihre bestehende JCS-Domäne. Historische Baselinehashes
werden nicht neu geschrieben. Die Qualifikation beginnt erst beim Modelllesen.

R ergänzt explizite Konflikte bei abweichenden Originalbytes derselben
Identität/Revision, projektgebundene Hashprojektionen und frische Write-Target-
Prüfung. Gegenproben decken falsche Source-/Target-Verträge, fehlende Originale,
unzulässige Pfade/Symlinks, entfernte/duplizierte/umgeordnete Einträge,
gefälschte Projektionen und nachträglich geänderte Bytes ab. Registrierte
Original-, Archiv- und Manifestpfade sind keine regulären Schreibziele.
C trennt owned Original-/Manifestwerte von Qualifikation und Dateizugriff.
Funktions-/Klassen-ASTs bleiben identisch zu R, ebenso Tests und Kataloge.

Jeder echte W/R/C-Zustand erhält seine eigene fällige N=3-Gruppe (1/2/0)
plus vollständige ungefilterte Pflichtauswahl vor seinem Commit. Keine
Testkörper, Fixtures oder Test-Unterprozesse in Dev. Collection, Syntax und
native Paketrekonstruktion sind keine Verhaltensabnahme. Alle neuen Tests
sowie betroffene Source-, Plan-, Lese-, Hash-, Graph- und Sicherheits-
regressionen sind Pflicht. Keine Vollsuite- oder Releasebehauptung.
Vorbereiteter Zwischenstand: C; Häkchen gelten erst nach Apply-Gate.

Die weiteren M16-Gates bleiben offen: Verlustbehandlung, öffentliche
Migrationsregistrierung und Writer, volle globale Zielvalidierung, historische
Verification/Readiness, CLI/Restore, Audit und Recovery. Insbesondere erzeugt
die Lesbarkeit weder aktuelle Nachweisgültigkeit noch menschliche Freigabe.
Der bestehende Restore-Formatblock bleibt erhalten. Nach erfolgreichem C
wäre 681/900 erreicht; nächster Schritt ist 16.h.W.
