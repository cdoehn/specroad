# Korrekturbundle 595 — vollständiger offener Rest 17.a.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 595 — vollständiger offener Rest 17.a.W/R/C

Maßgebliche Basis ist das nativ geprüfte Fehler-Result
`specroad-apply_Result_024448_1105_18d4ba.zip`, SHA-256
`68060532980b795e1edaf3068caa12cc3456278d5d638453cab4bdd7c672bd74`.
HEAD bleibt `ce015ce3544a2a0ae96d813dc8d9cd6de6f917bd`, erhaltener
Dirty-Fingerprint `03d21dcd6d16ca7d`. Bundle 594 scheiterte vor dem ersten
Commit in 17.a.W: 7.268 Tests bestanden, sechs schlugen fehl. Die Apply-
Fortschrittsdaten belegen keinen Commit; 17.a.W/R/C sind vollständig offen.
Der tatsächlich abgeschlossene Produktstand bleibt damit 693/900. Die
bereits materialisierten Checkboxen und Zähler sind weiterhin ausschließlich
Commitzielzustände, kein Erfolgsnachweis des fehlgeschlagenen Versuchs.

Alle sechs Fehler stammen aus `read_only_sources`: Der Testschutz verbietet
`os.open` mit `O_RDWR`, womit Python beim Start eines lesenden Git-Prozesses
intern `/dev/null` öffnet. Der Adaptervertrag bleibt unverändert. Der Helfer
öffnet die Nullquelle vor dem Schutz ausdrücklich nur lesend und übergibt
den offenen Deskriptor. Während des Starts der schon erlaubten Git-Lesebefehle
darf außerdem ausschließlich ein mit `fstat` als Pipe erkannter Deskriptor
für deren `stdin=PIPE` gepuffert geöffnet werden; dies ist die Eingabe für
`cat-file --batch`, keine Projektdatei. Reguläre Deskriptoren, Dateipfade,
Dateischreiboperationen, Netzwerk und sonstige Prozesse bleiben gesperrt.

Die Korrektur ändert weder Produktcode noch Verhaltenstestkörper/Orakel.
W/R/C enthalten denselben korrigierten Helfer; alle bisher angekündigten
Testidentitäten und Pflichtdateien sowie die vollständigen Stage-Umfänge
bleiben erhalten. Der globale Schreibschutz wird nicht gelockert. Bestehende
Inventarvergleiche prüfen zusätzlich unveränderte Projektbytes sowie
Git-Branch, Index und Arbeitsbaum. Keine Spezifikationsklärung und kein
zusätzlicher Produkt- oder Alibicommit.

Die Korrekturbindung verweist auf den ursprünglichen Plan
`1e3f1a603b177c9f7a5b1ef0f898ba69f34edd00301829a45c29ea03b8de4f8b`
und übernimmt alle offenen IDs/Rollen unverändert. Die erste Stage enthält
auch sämtliche erhaltenen Dirty-Pfade mit ihren vollständigen aktuellen
Vorherdateien; kein Zurücksetzen, kein vorab ausgebrachter R/C-Endstand.
Apply prüft jede Stage mit fälliger gefilterter N=3-Gruppe plus vollständiger
Pflichtauswahl vor ihrem Commit. Die Rotation wurde durch den Fehler nicht
weitergeschaltet. Dev führt nur statische Prüfung, reine Collection und
native Paketvalidierung aus, keine Verhaltenstests. Ein erfolgreicher
Abschluss von 17.a ist erst durch das folgende Apply-Result belegbar.
