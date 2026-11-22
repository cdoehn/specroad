# Bundle 787 — Prozessabbruch-Harness und Python-/Distributionsmatrix

22. November 2026. Das native Result mit SHA-256
`101ae2a84d65ec4ea0bf88b24bb2310ca7249e5a7a9ae9f95c95e1e6868db0d9`
bestätigt fünf erfolgreiche Stages von Bundle 786: 20.f.W/R/C und 20.g.W/R,
zusammen 64.388 bestandene Testausführungen. Der letzte bestätigte Commit ist
`6ba01c2cc907398277f8a0efb6516f1b3504020e`, damit 884/918 Produktpositionen.
20.g.C blieb uncommitted: 8.554 Tests bestanden, einer scheiterte. Der erhaltene
Dateistand entspricht vollständig dem angekündigten C-Zielstand; seine
Erledigtmarkierung ist noch kein erfolgreiches Gate.

Der Fehler betrifft
`test_real_process_loss_on_directory_sync_preserves_quarantine[after-marker_removal]`.
Der Test beendete sein Kind nach der festen 30-Sekunden-Frist, bevor dessen
Exitcode den erreichten Absturzpunkt bestätigte. Das Result belegt diesen
Harness-Abbruch, weder einen veränderten Produktvertrag noch die konkrete
Ursache der Verzögerung. Eine gemessene Beschleunigung wird nicht behauptet.

Die vier zusammengehörigen Crashfamilien starten jetzt einen frischen,
isolierten Python-Prozess über den vorhandenen Testprozesshelfer statt einen
vom pytest-Worker geerbten Fork mit fester 20-/30-Sekunden-Abbruchfrist.
Alle 35 Parametervarianten, native Injectorprogramme, echten `os._exit(91)`-
Grenzen und Oracles bleiben erhalten. Ein Ablauf ohne erwartete Grenze endet
weiterhin mit 92 und scheitert. Sperrdiagnose, verweigerte Freigabe, Originalbytes,
echte Löschungen und Backups bleiben verpflichtend. Die Korrektur verlängert
keine Produktfrist und ersetzt keinen Crash durch einen Mock.

Nur **20.g.C**, Rolle `implementation`, wird als exakter Korrekturpräfix des
öffentlichen Plans von 786 fortgesetzt. Die fünf bestätigten IDs erscheinen
nicht erneut. Anschließend folgen die bereits geplanten **20.h.W/R/C**, alle
mit eigenem Gate und ursprünglicher Commitnachricht. `correction_of` enthält
ausschließlich den belegten alten Rest. Eine normative Detailklärung ist nicht
nötig; Spezifikation und Entwicklungsvertrag bleiben bytegleich.

20.h.W bindet tatsächliche CPython-Binaries für 3.10–3.14 über die bestehende
lokale Runtime-Prüfung; ihre Konfiguration wird nicht mitgeliefert. Fehlende,
falsche oder unvollständige Laufzeiten erzeugen Fehler statt Skips. Beide
gebauten Distributionen laufen mit `-I -S -B`, ohne Aktivierung, Sitepakete,
Paketmanager oder Shellzugriff in einer nicht privilegierten Linux-x86-64-
Kindprozessumgebung mit realer Seccomp-Netzsperre. Die öffentlichen Entrypoints,
Selbstbeschreibung, native Validation, Query, Rendering und der vollständige
Hin-/Rückweg verwenden die ausgewählte Laufzeit. Vorhandene Git-/Entrypoint-
Voraussetzungen gelten ausschließlich auf der separaten lokalen Transportseite.
Der Empfang erzeugt nur einen Draft ohne Fachänderung oder Freigabe. Erst ein
explizites synthetisches Reviewfixture mit echten gespeicherten Originalen
führt über einen schreibfreien menschlichen Dry-Run zum tatsächlichen nativen
Apply; der erwartete Zielhash und die bekannte Zielaussage bleiben unabhängig.

20.h.R ergänzt vollständige Ergebnis-/Diagnoseparität aller sechs Projektleser
zwischen CLI und strukturiertem Request, beiden Distributionen und jeweils
frischem fremdem Arbeitsverzeichnis. Fehlende Eingaben bleiben strukturierte
Nutzungsfehler. Das nicht angebotene `python-bundled`-Profil darf weder eine
Runtime laden noch Dateien erzeugen. Jede Minor-Version wird zusätzlich über
eine tatsächlich erzeugte, nicht aktivierte venv ohne pip geprüft. Keine
fehlende ABI-/Plattformmessung wird als Erfolg oder als unterstütztes Profil
ausgegeben; Ubuntu/aarch64 ist weiterhin kein Ersatz der Referenzmatrix.

20.h.C zieht ausschließlich identische Prozessjobs, Konstanten und die
synthetische Host-Reviewfolge in einen gemeinsamen Testharness. Funktions-
und Decorator-AST sowie alle Testidentitäten bleiben gegenüber R erhalten.
Laufzeit-/Distributions-/Isolationsdaten und Host-Rundwegdaten sind getrennte
strukturierte Evidenceobjekte. Die Produktversionsauskunft erfindet daraus
keinen vollständigen Release- oder Python-Freigabenachweis.

Alle geänderten Testdateien, sämtliche statisch ermittelten Helferkonsumenten,
der vollständige alte C-Pflichtsatz und die vorhandenen Transport-, Core-,
Python-/ABI-, Paket- und Katalogregressionen werden unverändert beziehungsweise
ergänzend gebunden. Dev führt ausschließlich Syntax-/statische Prüfung,
reine Collection, native Stage-/Paketvalidierung aus: **tests_run=0**.

Jeder Zielstand gilt erst nach seinem eigenen erfolgreichen Apply-Gate. Nach
vollständigem Erfolg sind 888/918 erreicht; anschließend folgt **20.i.W** mit
den echten Referenzmessungen nach §14. Der normale parallele Testhost wird
hier nicht zum behaupteten Referenzmessplatz. Menschliche Reviews, vollständige
Releaseabnahme und bisher offene Plattform-/Leistungsnachweise bleiben offen.
[Bericht 786](bundle-786-distribution-fixture.md) bleibt historische Evidenz.
