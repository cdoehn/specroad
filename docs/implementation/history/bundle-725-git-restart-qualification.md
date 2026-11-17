# Bundle 725 — Native Qualifikation der Git-Neubeginn-Testdaten

17. November 2026. Das native Result von Bundle 724 mit SHA-256
`abac3c1ec72125056a9794294830d5ec7c747d4e1ed012a4676d62f343701511`
bestätigt **18.w.C**, **12.267 bestandene Tests** und Commit
`f84c871324df5dce713914c2d4d8b82aeee3b8a5`. Damit sind 777/918
Produktpositionen bestätigt. Das folgende 18.x.W-Gate meldet fünf Fehler
und 13.913 bestandene Tests; W wurde nicht committed. Der vollständig
ausgebrachte W-Zustand ist die technische Korrekturbasis.

Alle fünf Fehler entstehen in `support.git_restart.new_write`, bevor der
erste gespeicherte Projektstand publiziert wird:
`prepare_publication_check` weist das Ziel mit
`publication_target_not_validated` ab. Die statische Rückverfolgung zeigt,
dass die vollständige Projektfixture Dokument- und Konfigurationsartefakte
enthält, der Helfer aber keine `document_model`-/`configuration`-Gates an
die native Zielprüfung übergibt. Feldgültige Artefakte ersetzen diese
verpflichtenden Fachprüfungen nicht.

Der Helfer bindet beide Dienste an das vollständige geladene Quellmodell
und validiert bei jedem Aufruf die tatsächlich übergebenen Kandidatendokumente
zusammen mit den Originalressourcen durch `qualification.project.validate_project`.
Dieselbe Gatefolge wird bei Preflight und geschützter Publikation übergeben,
einschließlich der dortigen erneuten Zielprüfung. Keine pauschale Freigabe,
kein Ersatzvalidator und keine Qualifikation nur des unveränderten Ausgangsstands.
Die Konfiguration und das Primärdokument werden nicht aus den Daten entfernt.

Produktcode, alle bestehenden Testkörper und Parameter bleiben gegenüber den
angekündigten Stages unverändert. Die Tests behalten echte native Writes,
Originalreceipts, lokale Git-Commits in ihren eigenen Testverzeichnissen,
separate Checkouts, Abbruchinjektion und den unveränderten beschädigten Root.
Die R-Fälle für fehlende Pflichtbelege, aktive Abbruchdaten und Archivobjekte
bleiben vollständig erhalten. Der korrigierte Helfer wird in alle drei
abhängigen Stages übernommen; C bleibt hinsichtlich sämtlicher Testbytes
identisch zu R. Historische Nachweise werden nicht umgeschrieben.

Der vollständige offene Rest lautet **18.x.W, 18.x.R, 18.x.C** mit den
ursprünglichen Rollen `implementation` und Commitnachrichten. `correction_of`
bindet genau diesen Rest des Plans von 724. Der bestätigte Schritt 18.w.C
wird nicht wiederholt. Alle Löschabsichten samt vollständigen Vorherbytes,
ursprüngliche Pflichtauswahlen und stabile Testnummern bleiben erhalten.
Die vollständigen Testdateien der fehlgeschlagenen Fälle und alle Verbraucher
des korrigierten Helfers sind verpflichtende Apply-Auswahl. Spezifikation,
aktive Katalogbindungen und Entscheidungsbudget ändern sich nicht.

Jede Stage behält ihr eigenes Gate vor dem Commit; danach erst folgt der
nächste Zustand. Dev führt ausschließlich statische Prüfung, reine Collection
und native Paketvalidierung aus. Verhaltenstests und Abnahmen bleiben Apply
vorbehalten. Die vollständige Abschlussgruppe 18.x enthält weiterhin alle
angekündigten Abnahmen; anschließend bleibt 18.l.W die nächste Planposition.
Die vorbereiteten Zielwerte sind noch keine erfolgreiche Apply-Abnahme.

Commitzielstand dieser Stage: **18.x.R**, **779/918**, danach **18.x.C**.
