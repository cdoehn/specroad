# Öffentliche Migration und M16-Integration

Unterstützt wird ausschließlich der neu festgelegte, eingefrorene synthetische
Quellvertrag reference-0.1-v1 v1.0.1 nach Q.0. Es gibt keine Zusage für reale
Altprojekte oder undokumentierte 0.2-Entwürfe; --from-spec wird nicht geraten.

`specroad migrate plan` liest den vollständigen expliziten Projektroot und die
explizite Mappingdatei (--inputs-root/--inputs). Actor, geplanter Zeitpunkt,
Plan-ID und optional Request-ID stammen vom Aufrufer. --output-root/--output
veröffentlicht den vollständigen Planungsbericht mit Change-Plan außerhalb des
Projekts ohne Überschreiben. Fehlende Mappings bleiben konkrete Blocker.

`specroad migrate apply --to 0.2.0` verwendet entweder dieses Planfile mit
--expected-plan-sha256 und --expected-inputs-sha256, vollständige neue
Planungseingaben oder ein abgeschlossenes --work-dir. --backup-root/--backup
benennt die vor jedem ersten Schreiben nativ verifizierte vollständige
Source-Sicherung; vorhandene andere Bytes werden nie überschrieben.
--transaction-id bindet die gemeinsame native Writer-/Journal-/Recoverykette.
Die vertraute Host-Anbindung liefert PublicationAuthority und erforderliche
ModelGates in InvocationContextBuilder frisch. Projektdateien, CLI-Flags und
Work speichern keine Autorität. Derselbe bereits bestätigte Request gibt nur
den historischen Ausgang zurück; ein erreichtes Ziel wird nicht erneut migriert.

`specroad migrate verify` benötigt Originalplan/-bericht, vollständiges
Source-ZIP und explizite Plan-/Input-/Report-/Backuphashes sowie die ursprüngliche
Transaktion. Es prüft die tatsächlichen Zielbytes, das aktuelle Zielmodell und
die native abgeschlossene Operation lesend. Historische Integrität ist keine
aktuelle Evidence, menschliche Freigabe oder Releasebereitschaft.

--work-dir beziehungsweise explizite Schrittbudgets bei plan/verify liefern eine
native passive Fortsetzung. work resume/export/restore/cancel behalten alle
ursprünglichen Eingaben und bestätigten Phasen. Das abgeschlossene Planungs-
ergebnis kann mit migrate apply --work-dir und frischen Projekt-/Backup-/
Transaktions- und Hostbindungen ausgeführt werden. Ein portables Verify-Ergebnis
ist eine Prüfung bereitgestellter Zielbytes, kein späterer Live-Snapshot.

Vollständige aktuelle Projektbundles bewahren die nativ qualifizierten alten
Originale und abgeschlossenen Migrationsreceipts. Restore liest diese mit den
passenden Quellalgorithmen und erhält ihre Bytes. Ein isolierter alter Baseline-
Snapshot wird dadurch nicht zu einem aktuellen 0.2-Restore-Ausgang erklärt.

Die Tests verwenden ausschließlich synthetische Projekte und tatsächliche
Datei-, Backup-, Journal-, Work- und Restore-Pfade. Keine Verhaltensausführung
in Dev. Jede Stage hat ein eigenes Apply-Gate; C verlangt die gesamte verfügbare
Suite ungefiltert. M16 ist erst nach diesem tatsächlichen Abschluss abgenommen.
