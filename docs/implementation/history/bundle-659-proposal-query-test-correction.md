# Bundle 659 — Query-/Rendering-Test auf das geänderte Feld beziehen

9. November 2026. Maßgebliches Result `132166a79f9b78427ed1a63a54fb42d6c852457700d6e3b0dfad751ac6ece802`,
Base-Commit `e4c7e72791a9385a898036e3eeb73f75c3bd770f`.
Bundle 658 hat 18.g.W geprüft: 10.313 Tests bestanden, ein Test fehlgeschlagen,
10.314 ausgewählte Testidentitäten. Kein Commit entstand; R/C wurden nicht
installiert. Der erhaltene Arbeitsstand stimmt vollständig byte- und modusgleich
mit dem angekündigten W überein. Die committed Basis mit der bereits erfolgreichen
Detailklärung aus Bundle 657 bleibt unverändert; sie wird nicht wiederholt.

Die Testvorbereitung `planned_change` verwendet `support.folds.edit` und ändert
`/statement` auf `Native proposed change`. Die Queryspalte las dagegen `/title`;
der native Wert `Sample` war deshalb korrekt. Der Test projiziert jetzt das
wirklich geänderte `/statement`. Er belegt zusätzlich an der unveränderten Basis
den ursprünglichen Querywert und Renderinhalt und am Ziel den neuen Inhalt.
Hashvergleich mit dem unabhängigen nativen Renderer, beidseitiger Impact und
unverändertes Originalinventar bleiben erhalten. Kein Ersetzen des Orakels durch
den alten Titel, kein übersprungener Test und keine gelockerte Produktprüfung.
Produktcode, Spec, Schema, Testidentitäten und Testnummern bleiben gegenüber den
bereits angekündigten Stufen bytegleich; nur der fehlerhafte Test wird korrigiert.

Die drei vollständigen Reststufen 18.g.W/R/C behalten IDs, Rollen, exakte
Commitnachrichten und sämtliche bisher verpflichtenden Testdateien. Der erste
Scope enthält alle 27 erhaltenen dirty Pfade. Jeder Commit benötigt sein eigenes
Apply-Gate aus aktueller gefilterter N=3-Gruppe plus ungefilterter Pflichtauswahl.
C behält sämtliche R-Testbytes. Historische Berichte bleiben bytegleich.
Keine neue Klärung, Budgetänderung, Dienstaktion, lokale Konfiguration oder CI.

Der vorbereitete W-Stand trägt erst nach seinem erfolgreichen Gate und Commit
748/900 mit nächster Position 18.g.R. Nur der vollständige C-Abschluss schließt
Bundle 659. Die bestätigte committed Basis bleibt bis dahin bei 747/900 und
18.g.W offen. In Dev werden ausschließlich Syntax, reine Collection, vollständige
Vorherbytes, native Stufen-/Restbindung und Paket geprüft; keine Verhaltenstests.
Nach atomarer Übergabe endet der Auftrag ohne eigene Apply-/Resultschleife.
