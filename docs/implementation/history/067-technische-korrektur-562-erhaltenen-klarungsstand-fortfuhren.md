# Technische Korrektur 562 — erhaltenen Klärungsstand fortführen

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Technische Korrektur 562 — erhaltenen Klärungsstand fortführen

Nutzerauftrag vom 3. November 2026: „Repariere“. Maßgeblich ist das nativ
geprüfte Fehler-Result `7cf68464e9dbd1cc9520be63554b0c8d0092966266c7211ea8100d302bfbd6af`.
Bundle 561 scheiterte vor MIGRATION-BACKUP-561: 6.755 erfolgreiche Tests,
zwei Fehler in Control-Tests durch einen nachträglich erschienenen Git-Marker
über deren /tmp-Testverzeichnis; kein Commit. Die erhaltenen 745 Dateien
entsprechen exakt dem angekündigten Klärungsziel. Alle vier offenen IDs und
Rollen bleiben erhalten: MIGRATION-BACKUP-561, 16.d.W, 16.d.R, 16.d.C.

Der Klärungspräfix bleibt bytegleich, einschließlich dieses Plans in seinem
ersten Zustand. Er erhält nur neue Vorherbindung und Pflichtauswahl. Die
Erweiterung auf 64 MiB und die vollständige Quellsicherung bleiben enthalten.
Keine neue fachliche Entscheidung, kein neuer Klärungsplatz, kein Reset.

Der bisherige Formvalidator verweigerte auch bei belegter Fortsetzung einen
bereits vollständig ausgebrachten Klärungspräfix (Vorherbytes = Zielbytes).
Die technische Korrektur setzt die vorhandene Norm 2.4.3.1 um: nur dirty
Korrektur mit kompletter Korrekturbindung darf diesen Zustand darstellen.
Die separate Prüfung des nativen Fehler-Results, ursprünglichen Plans,
vollständigen Rests, identischen Klärungsziele und aktuellen Vorherbytes
bleibt zwingend. Neue unveränderte Klärungsmarker und reine Recovery-
Checkpoints bleiben unzulässig. Der gebündelte Apply-Treiber verwendet
diesen korrigierten Formvalidator bereits zur Darstellung des ersten
Zustands; Repository- und Control-Änderungen folgen erst in W.

W ergänzt die Vorherbindungskorrektur samt Apply-/Control-Regressionen und
verlegt Control-Testdaten während ihrer gesamten Lebensdauer nach /var/tmp.
Unbenutzbare oder unsichere Kandidaten führen weiterhin zum Fehler; kein
Zurückfallen auf das zeitweise durch Sandbox-Initialisierung berührte /tmp,
keine Änderung der produktiven Git-/Symlinkprüfung. Ein isolierter Test
erzeugt den nachträglichen Git-Marker ausschließlich in eigenen Verzeichnissen.
R ergänzt manipulierte Zielbytes, Vorherbytes, Rollen, Herkunft und Restfolgen.
C erhält sämtliche Tests und bereinigt weiterhin die vollständige 16.d-Implementierung.

Dev: keine Testkörper ausgeführt. Collection, Syntax und passive native
Paket-/Fortsetzungsprüfung sind keine Verhaltensabnahme. Der erste Gate prüft
den unveränderten Klärungsstand einschließlich beider zuvor fehlgeschlagener
Testdateien erneut; der Testverzeichnis-Fix wird regelkonform erst mit W
ausgebracht. Control bleibt gestoppt; keine Installation oder Änderung an
Betriebsdaten, Aufträgen oder Budgets. Jedes Gate entscheidet erst im Apply.
