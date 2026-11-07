# KORREKTUR 547 — manipulierbare PYZ-Testpakete, vollständiger 15.o.R/C-Rest

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## KORREKTUR 547 — manipulierbare PYZ-Testpakete, vollständiger 15.o.R/C-Rest

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_110304_1102_b24d5b.zip`, SHA-256
`a3b195e29f4b1776f128ce5c955fd5ba0e731dcc04e14ce70217ccd77578a1d3`,
HEAD `a2929c3eaceefbd3376099c3324d43fd4c805edc`, Dirty-Fingerprint
`f954caa79e0fa77b`. Der native Base-Snapshot entspricht exakt dem W-Zustand
von Bundle 546, das Effective-Inventar exakt dessen erhaltenem R-Zustand.

**Belegter Commitpräfix:** 15.o.W wurde nach 7.414 bestandenen Tests der
Gruppe 2 plus Pflichtauswahl tatsächlich als
`a2929c3eaceefbd3376099c3324d43fd4c805edc` committed, Elterncommit
`28470da477edb6c8f8d80807d0b2731f670e1741`. Dieser Commit bleibt erhalten und
wird nicht wiederholt. Der tatsächliche Produktfortschritt ist **658/900**.

15.o.R scheiterte danach mit **4 fehlgeschlagenen und 7.523 bestandenen**
Tests in 1.364,19 Sekunden; die Auswahl umfasste 7.527 Tests. Die zwei
Warnungen betreffen absichtlich doppelte ZIP-Member in separaten Negativfällen.
Es entstand kein R-Commit; die fällige Rotationsgruppe bleibt 0.
SPECROAD_APPLY_PLAN/PROGRESS bindet ausschließlich den vollständigen offenen
Rest `15.o.R`, `15.o.C` an Plan-SHA-256
`d79f1300610a607519e61617e36872db6b4f3fc2108f5033f0cad1882c98c2b9`.

**Diagnose und gezielte Korrektur:** Die Fälle `foreign-core` und
`forged-build`, jeweils für Repositoryroot und Unterprojekt, scheiterten
bereits beim Erzeugen des manipulierten Testeingangs. Der SpecRoad-Bundle-
Writer `encode_zip` erlaubt ausschließlich reguläre Dateipayloads; die echte
Python-ZIP enthält auch Verzeichniseinträge wie `specroad/`. Seine Ablehnung
`unsafe_archive_path` verhinderte den eigentlichen Öffnungsaufruf und war kein
Nachweis der vorgesehenen passiven Codevertrauensprüfung nach W.4.1.

Die Testkonstruktion verwendet für die innere PYZ nun den Standardbibliotheks-
ZIP-Writer und kopiert die ursprünglichen Member einschließlich ihrer
Verzeichnisse und Metadaten. Nur der gezielt gewählte Python-Member erhält den
bereits vorgesehenen nicht auszuführenden Code. Der äußere Artefakthash,
Eintragsgrößen/-hashes und Paket-ID werden konsistent neu gebunden. Die Tests
verlangen zusätzlich den konkreten Sicherheitsfehler für fremde Corebytes
beziehungsweise einen ausführbaren Buildrecord. Die bestehenden Nachweise
für unveränderte Eingaben, fehlenden Prüfbereich und fehlendes Sandboxziel
bleiben erhalten. Weder Produktionswriter noch Import-/Pfad-/Schemavertrag
werden gelockert; die Produktbytes bleiben je R-/C-Zustand unverändert.

Bundle 547 übernimmt den erhaltenen vollständigen R-Zustand mit dieser
technischen Testkorrektur und anschließend den vollständigen bereits
vorbereiteten C-Refactor. Beide ursprünglichen Commit-IDs und Nachrichten
bleiben erhalten. C wird erst nach erfolgreichem R-Gate UND tatsächlichem
R-Commit ausgebracht. Keine Teilung, kein Reset, kein zusätzlicher Alibicommit
und keine Wiederholung von W. Alle 121 Tests der geänderten R-Datei und die
bisherigen Pflichtregressionen bleiben in beiden Zuständen ungefiltert
verpflichtend; insbesondere alle vier belegten Fehlerfälle. Testidentitäten,
Testnummern, gespeicherte Fixturebytes, Katalog-Oracles und Messhistorie bleiben
erhalten. Diese gezielte Korrektur ersetzt keine offene Sicherheitsabnahme.

Vorbereitete R-/C-Fortschrittsmarker gelten erst nach ihrem erfolgreichen
Apply-Gate und Commit. Bundle 546 ist nur teilweise angewendet; das letzte
vollständig abgeschlossene Bundle bleibt 543. Bundle 547 ist erst nach seinem
vollständigen R-/C-Abschluss erledigt. Spec 0.2.47 bleibt bytegleich; es gibt
keine Spezifikationsklärung oder Erneuerung des gesperrten Klärungsbudgets.
Dev führt keine Verhaltenstests aus. Syntax, reine Collection und native
Paketvalidierung sind keine Verhaltensabnahme. M15-Vollsuite, Integration,
Plattformfreigaben sowie 18.q/18.r und die Rundwegabnahme bleiben offen.
