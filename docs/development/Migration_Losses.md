# Migrationsverluste und Erhaltungsprüfung

Der native Planer prüft jeden vollständigen 0.1-Referenzkandidaten anhand
12.20.3. Originalarchive, unveränderbare Dateien, Payloads und übrige
übergebene Dateien müssen bytegleich bleiben. Veränderbare Artefakte werden
gegen die ausdrücklich gebundenen Transformationen und alle übrigen
unveränderten JSON-Werte geprüft. Unbekannte Extensions werden weder als
Code ausgeführt noch als bekannte Felder interpretiert. Die Zielkonfiguration
muss vorhandene Extension-Namespaces vollständig übernehmen; fehlende Werte
werden nicht still ergänzt. Ein abweichender Kandidat erhält keinen Plan.

assess_migration_preservation erhält ausschließlich owned Quell-/Zielbytes,
die vollständigen Planinputs, Akteur und Zeit. Es qualifiziert die Quelle
nativ und liefert MigrationLossReport mit getrennten Ist-/Sollwerten,
Originalbytehashes und vollständigen individuellen LOSS-IDs. Die IDs binden
Quelle, Kandidat, Mapping und Verträge; weder laufende Nummern noch ein
Versionsetikett sind dafür ausreichend. Das Objekt ist kein Write-Token.
Eine gespeicherte Behauptung kann nicht als native Inventur geladen werden.

check_loss_acceptance verlangt die native Beobachtung, deren ausdrücklich
erwarteten Hash und jede LOSS-ID einzeln. Es gibt bei fehlenden IDs keine
Teilzustimmung. Vollständige Zustimmung liefert alle Verlustdetails für
einen späteren Bericht, ohne Schreib- oder Reviewrecht. Insbesondere bleibt
der unterstützte Referenzpfad strikt verlustfrei: Zustimmung erlaubt dort
keine beschädigten Originale oder entfernten Fachwerte.

Die öffentliche CLI, gemeinsame Transaktion, Abschlussbericht und vollständige
Zielverifikation folgen in den weiteren M16-Schritten. Regulärer Import behält
seine bestehenden Verlustberichte und seine bisherige Zustimmungssperre.
Die gemeinsam verwendete strukturelle Inventur ändert keine Importrechte.
Verhaltenstests werden vor jeder einzelnen Stage ausschließlich durch Apply
ausgeführt; Collection und native Bundleprüfung sind keine Verhaltensabnahme.
