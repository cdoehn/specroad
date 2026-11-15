# Bundle 703 — dauerhafter Schreibmarker und normaler Abschluss (18.t)

Datum: 15. November 2026. Technische Basis ist das nativ geprüfte saubere Result
`specroad-apply_Result_112737_1115_cde23f.zip`, SHA-256
`2016d7f22252a3b8b95ae1ecd7b8278ce6da295fbd6ef25ccc474e7df3bf3d25`,
Commit `70c8ebbd82d30f62b09f9fbd7d2b6008c7483698`.
Das Result ist ein Checkpoint ohne Testausführung, kein neuer Testerfolg.
Es enthält keinen offenen Commitrest. Erfolgreiche ältere Commits bleiben erhalten.

## Folge und Umfang

Der notwendige delegierte Präfix [WRITE-RECEIPTS-703](../decisions/write-receipts-703.md)
schließt ausschließlich die in C.2 angekündigten neuen normalen Belegformate.
Er ist keine Produktumsetzung und ändert keinen Produktzähler. Danach folgt die
vollständige zusammenhängende Gruppe 18.t.W/R/C. Jede Stage erhält ihre eigene
fällige N=3-Gruppe plus ungefilterte Pflichtauswahl vor ihrem Commit. Ihre
Fortschrittswerte und Checklisten gelten erst nach diesem erfolgreichen Gate.
Der Endstand darf nicht vorab installiert werden.

| Stage | Vollständige Änderung |
| --- | --- |
| 18.t.W | Gemeinsamer Create/Replace/Delete-Writer mit nativer Zielqualifikation, exklusivem Lock, unveränderlichem dauerhaftem Marker, echten normalisierten Receipts und lesender Request-/Abschlusswiederholung. Der native Snapshotadapter benutzt dieselbe Engine für reale Löschungen; keine öffentlichen Default-Aufrufer werden vorgezogen. |
| 18.t.R | Native I/O-/Unlink-/Replace-/Sync-Grenzen, Prozessabbrüche, Teilwrites, Marker-/Receiptmanipulation, Root-/Elterntausch, Links, portable Pfade und Eigentümerprüfung. Ein lebender Prozess allein belegt keinen aktiven Writer; dafür ist zusätzlich der belegte Kernelmutex nötig. Native Fach- und Autoritätsprüfung werden erneut ausgeführt. |
| 18.t.C | Guard-Lebenszyklus, einzelne Dateiwirkungen, gemeinsame deskriptorrelative Lesefunktion und nativer Qualifikationsadapter getrennt. Alle W-/R-Testbytes bleiben identisch; dieselben Qualifikations-, Schutz-, Publikations- und Synchronisationsreihenfolgen. |

## Nachweise und Grenzen

`tests/test_write_guard.py` prüft echte normale Writes, Requestkonflikte,
Create/Replace/Delete, fehlende Originalbelege und Prozessverlust vor/nach dem
Marker sowie während einer Mehrdateipublikation. `tests/test_write_guard_right.py`
ergänzt konkrete Fehlergrenzen und echte Prozesse vor/nach Datei-fsync und
Löschwirkungen. Die bestehenden nativen Fixture- und Gateimplementierungen
werden verwendet; keine vorgegebenen Erfolgsbefunde. Ein abgeschlossener
Outputfehler wird durch lesende Wiederholung beantwortet, nie durch Reapply.
Auch vollständige Zielbytes oder Receipts entfernen keinen offenen Marker.
Bei fehlgeschlagener abschließender Markersynchronisation bleibt der eigene
ursprüngliche Lock als Sperrbeleg erhalten. Fremde Dateien werden nicht bereinigt.

Die Pflichtauswahl enthält sämtliche neuen Testdateien sowie die betroffenen
Lock-, Pfadschutz-, Publikations-, Staging-, Commit-, Receipt-, Preflight- und
nativen Snapshot-/Migrationsregressionen. Alte Testbytes und stabile Nummern
bleiben erhalten; neue Nummern werden nur angehängt. Aktive Katalogeinträge
binden den gemeinsamen implementierten Anteil als `partial`, ohne die noch
fehlende Umstellung aller Aufrufer als erledigt auszugeben.

18.u ist weiterhin der nächste vollständige Schritt: sämtliche normalen
Schreibwege, Proposals und Projekt-Preflights auf den gemeinsamen Vertrag
umstellen. 18.v stellt Spezialwriter und Bootstrap um; 18.w entfernt die alten
Recoverybefehle, 18.x vervollständigt Format-/Git-Wiederanlaufabnahmen. Die
bestehenden Defaultwriter bleiben bis dahin unverändert; der neue Writerpfad
besitzt keinen Recovery-Fallback. Diese bereits geplanten Integrationsgruppen
werden weder verkleinert noch als erledigt markiert. Insbesondere ist der
native Snapshotadapter noch kein öffentlicher Migration-/Merge-Defaultwechsel.

Dev führt ausschließlich Syntax, statische Strukturprüfung, reine vollständige
Collection und native Paketvalidierung aus. Keine Testkörper, Fixtures oder
Test-Unterprozesse in Dev. Tatsächliche Verhaltens-/Plattformnachweise stammen
erst aus Apply. Kein Dienststart, Budgetreset oder Produktfreigabe.
