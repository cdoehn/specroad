# PLAN 15.o.W/R/C — Hinpaket prüfen und Sandbox öffnen (Bundle 544)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## PLAN 15.o.W/R/C — Hinpaket prüfen und Sandbox öffnen (Bundle 544)

Maßgebliche technische Basis: vollständig nativ geprüftes Result
`specroad-apply_Result_085321_1102_db582f.zip`, SHA-256
`dd00e7d5999040af83402b12cf2ed9ccd137734a7a4df3516dbd502cd483a030`,
sauberer HEAD `28470da477edb6c8f8d80807d0b2731f670e1741`.
Bundle 543 schloss TRANSPORT-OPEN-543 mit 6.192 bestandenen Apply-Tests ab;
die geklärte Spec 0.2.47/W.4.1 bleibt unverändert. Dies ist reguläre Umsetzung,
keine weitere Spezifikationsklärung und kein vorweggenommener Budget-Reset.

W implementiert den vollständigen ai-runtime-Öffnungsweg: passive äußere Prüfung,
explizite standalone 1.8.0-Codebindung, neue private Prüfdateien, vollständige
native Resultprüfung und exakte vollständige Projekt-/Receiptprojektion.
Verify und Extract besitzen getrennte geschlossene Erfolgsschemas. Extract
veröffentlicht Originalreferenzen und Runtimes sowie ein nativ extrahiertes
Projekt mit gültigem lokalem Receipt-Nachweis. Kein Projektcode wird geladen.

R sichert private Rechte und Identitäten, Fremddateien, unvollständige Quellen,
manipulierte Container, I/O-/Quellenwechsel und den nachweisgebundenen Bootstrap
ab. Prozessabbruch und Wiederaufnahme verwenden ausschließlich unabhängig
erneut geprüfte Paketbytes und tatsächliche lokale Dateiidentitäten. C trennt
die wiederverwendbare passive Referenz- und Bootstrapstruktur ohne Fachänderung.

Die ZIP enthält drei echte aufeinanderfolgende Zustände; jeder wird erst nach
dem erfolgreichen Gate und Commit seines Vorgängers ausgebracht. Die folgende
Fortschrittsmarkierung gilt ausschließlich nach dem entsprechenden Apply-Gate
UND tatsächlichem Commit. Bei Fehlern gelten Log und erhaltener Commitpräfix.
Dev führt keine Verhaltenstests aus; Syntax, Collection und native Paketprüfung
sind keine Verhaltensabnahme. Apply prüft je Commit genau einmal die gefilterte
fällige N=3-Gruppe (beginnend bei 2) plus ungefilterte Pflichtauswahl. Neue und
geänderte Testdateien sind vollständig verpflichtend, ergänzt um Runtime-,
Bundle-, Receipt-, Bootstrap-, CLI-, Schema-, Katalog- und Sicherheitsregressionen.
Hostworker, Nice, dauerhafte Phasenmessung und Testnummern bleiben erhalten.

M15 ist damit noch nicht freigegeben: Vollsuite, vollständiges Integrationsgate
und plattformgebundene Nachweise bleiben offen. 18.q/18.r und die spätere
Rundwegabnahme bleiben eigenständige offene Schritte. Kein CI-/Dienststart,
keine Apply-Ausführung im Dev und keine automatische Folgeschleife.
