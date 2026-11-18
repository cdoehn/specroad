# Bundle 741 — nativer Fehlervertrag und vollständiger Dialogrest

## Bestätigter Ausgang

Result-SHA-256: 72c0b55ed38084f8d060a40c9e12ae170c3437052eae4a8ad370a7edd5ef4adc.
Erhaltener HEAD: 0af311f79e59286b53ab6347bfd79bf5c2925db5.
Das native Fehler-Result bestätigt vier erfolgreiche Stages aus Bundle 740:

| Stage | Commit | Bestandene Tests im jeweiligen Gate |
|---|---|---:|
| TEST-HOST-ONCE.W | 3bba42203ab6a6615bac9defc69565f1be6d2d89 | 7559 |
| TEST-HOST-ONCE.R | 9bc2352d17f8cf5d99a6f956a5814dd6e51fe3d3 | 7641 |
| TEST-HOST-ONCE.C | 6c44465c85ed03e05857a7581946c75e37647bf4 | 7666 |
| DIALOG-PERFORMANCE.W | 0af311f79e59286b53ab6347bfd79bf5c2925db5 | 13965 |

DIALOG-PERFORMANCE.R scheiterte anschließend mit einem Fehler und 13.993
bestandenen Tests. DIALOG-PERFORMANCE.C wurde nicht ausgebracht. Der native
Snapshot stimmt vollständig mit den angekündigten W-/R-Zuständen überein.
Die erfolgreichen Stages werden nicht wiederholt. Der Produktplan bleibt
bei 795/918, nächste Produktposition 18.q.W.

## Ursache und Korrektur

test_changed_original_bytes_requalify_and_invalid_bytes_do_not_poison_cache
übergibt ein Artefakt mit den Originalbytes {}. Der bestehende native
Byte-Modellkonstruktor weist das fehlende artifact_type mit
BundleError(reason="bundle_artifact_type", code="SRV002", exit_code=3) ab.
Die neue Regression erwartete irrtümlich ModelError. Der Cache lässt den
nativen Fehler unverändert durch und speichert erst nach erfolgreicher Prüfung.

Nur die Testerwartung wird auf die konkrete bestehende Fehlerklasse korrigiert
und um den vollständigen maschinenlesbaren Fehlerbefund verschärft. Beide
ungültigen Versuche, erneute Prüfung veränderter Originalbytes, gültiger
Cachetreffer und die exakte Folge aller nativen Aufrufe bleiben erhalten.
Kein breites Abfangen, kein Skip und keine Änderung des Produktfehlervertrags.
Alle anderen Testkörper, Test-IDs, Nummern und bisherigen Pflichtdateien
bleiben erhalten; keine Spezifikationsänderung oder neue Klärung.

## Vollständige Fortsetzung

Die ZIP führt ausschließlich DIALOG-PERFORMANCE.R und DIALOG-PERFORMANCE.C
mit ihren ursprünglichen implementation-Rollen, Commitnachrichten und
vollständigen Pflichtauswahlen fort. correction_of bindet den Planhash
e80c7c96054528bde8e775d5724ee435d41fd56d2f28e03ce83d7e43bc479411 und genau diesen offenen Rest.
Vollständige Vorherbytes beziehen sich auf das neue Fehler-Result; alle
erhaltenen uncommitteten Pfade gehören zum ersten Commit-Scope.

R und C behalten jeweils ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem
Commit. Die angekündigte C-Strukturbereinigung bleibt vollständig erhalten;
ihre Testbytes und Pflichtauswahl sind identisch zu R. Dev führt nur statische,
Syntax-, reine Collection- und native Paketprüfungen aus. Die korrigierten
Verhaltenstests sind erst nach dem jeweiligen Apply-Gate abgenommen.

Dieser Dateistand gehört zu DIALOG-PERFORMANCE.R. Erst nach seinem erfolgreichen Gate
und Commit ist dessen Zielstand bestätigt. Danach bleibt
DIALOG-PERFORMANCE.C offen.
Der eigene Abschluss von Bundle 741 setzt beide erfolgreichen Gates voraus.
