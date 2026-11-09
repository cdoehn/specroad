# Bundle 660 — Proposal-Test und Auslastung langsamer Testhosts korrigieren

09.11.2026. Maßgebliches Result `38da9a8ec4271118c84fdac299b2951395fa2961a930ae1ad00b8b641244e776`,
Base-Commit `e4c7e72791a9385a898036e3eeb73f75c3bd770f`.
Bundle 659 endete in 18.g.W mit 10.300 bestandenen Tests und genau einem
Fehler bei 10.301 ausgewählten Identitäten. Kein Commit entstand; R/C wurden
nicht installiert. Der erhaltene Snapshot entspricht vollständig dem zuvor
angekündigten W. Die bereits committed Detailklärung bleibt erhalten.

## Korrektur des fehlgeschlagenen Tests

`test_native_query_and_render_read_proposed_values` erwartete den rohen
Text `Reduce setup effort.` im Markdown. Der native Renderer maskiert den
Punkt korrekt als `Reduce setup effort\.`. Die positive Basisprüfung und die
negative Zielprüfung verwenden jetzt ausdrücklich diese erwarteten Bytes.
Die rohe Queryzelle, der geänderte Zielwert, der Vergleich mit dem nativen
Renderhash, beidseitiger Impact und das unveränderte Originalinventar bleiben
geprüft. Der Proposal-Produktcode und der Renderer werden nicht verändert.

## Beauftragte Scheduler-Reparatur

Die zuvor nur in Dev vorbereitete Reparatur wird nach Abgleich ihrer vollständigen
Vorherbytes in R übernommen. Der bisherige Scheduler beendete einen langsameren
Worker bereits mit einem zugeteilten Test, wenn kein kurzfristig optimaler
Folgetest gefunden wurde. Ein bekannter kurzer Folgetest darf ihn künftig weiter
beschäftigen, wenn die hostbezogene Fertigstellung in die prognostizierte
Restlaufzeit des ganzen Pools passt. Lange Nachläufe und unbekannte Fülltests
auf schwachen Hosts bleiben begrenzt; Abschalten liefert weiterhin das benötigte
xdist-Endsignal. Abgeschaltete Worker erhalten keine neue Arbeit.

Elf zusätzliche Fälle prüfen mehrere Arbeitswellen, unterschiedliche Hostleistung,
hostbezogen teure Nachfolger, ausschließlich unbekannte Aufgaben und kurze/letzte
Queues. Eine native synthetische Proxy-/xdist-Integration prüft den zweiten Test
des langsameren Workers, vollständige Auswahl und dauerhafte Setup-/Call-/Teardown-
Phasen. Keine externen Zugangsdaten oder realen Testhost-Installationen als Fixture.
Die vorhandenen Abbruch-, Host-, ACK-, Ressourcen- und Historienregressionen bleiben.
Es wird keine gemessene Beschleunigung behauptet; Verhaltenstests laufen erst in Apply.

## Vollständige Fortsetzung

18.g.W/R/C behalten IDs, Rollen, exakte Commitnachrichten und bisherige
Pflichtdateien. W korrigiert die Assertion; R enthält zusätzlich die vollständige
Scheduler-Reparatur. C übernimmt alle R-Testbytes unverändert und behält seine
bereits angekündigte strukturelle Bereinigung. So bleiben auch die bisher für R
angekündigten Testnummern erhalten; die elf neuen Identitäten werden erst dort
angehängt. Rotation, Filter, Messdatenbanken und normative Spec bleiben unverändert.
Jede Stage erhält ein eigenes Apply-Gate vor ihrem Commit; kein Endstand vor W.
Der erste Scope enthält sämtliche 28 erhaltenen dirty Pfade samt vollständigen
Vorherbytes. Historische Berichte werden nicht umgeschrieben.

Die committed Basis bleibt bis zum erfolgreichen W-Gate bei 747/900. Die
vorbereiteten W/R/C-Zielstände tragen erst durch ihre erfolgreichen Commits
748/749/750 von 900; nur C schließt Bundle 660. Dev prüft Syntax, reine Collection,
Vorherbytes, native Restbindung und Paket, führt keine Verhaltenstests aus.
Keine neue Klärung oder Budgetänderung. Die manuell beauftragte Übergabe startet
keine Control-Automatik und keine CI; nach bestätigter Apply-Übernahme endet der Turn.
