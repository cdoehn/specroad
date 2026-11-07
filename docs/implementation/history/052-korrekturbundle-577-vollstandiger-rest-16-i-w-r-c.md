# Korrekturbundle 577 — vollständiger Rest 16.i.W/R/C

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## Korrekturbundle 577 — vollständiger Rest 16.i.W/R/C

Das maßgebliche native Fehler-Result hat SHA-256
`2cbe7e5baa0be59cbb18d8286b8b617fe666da1696934903ebc7570a7d691a57`,
HEAD `eb91b55282e7a2ff9528412cfa60fd684a1d46bb` und den erhaltenen
Dirty-Fingerprint `19e5f87d2ee36b2f`. Bundle 576 stoppte erneut vor 16.i.W:
8643 Tests bestanden, einer scheiterte, kein Commit entstand. Der erhaltene
Arbeitsstand entspricht exakt der angekündigten W-Stage. Der erfolgreiche
Klärungscommit aus Bundle 575 bleibt erhalten; Produktstand tatsächlich
684/900. Alle drei Produktstufen bleiben vollständig offen.

Betroffen ist ausschließlich der partial-Fall von
test_old_publication_observation_cannot_survive_recovery_without_live_recheck.
Der Log zeigt einen Schreibversuch bei der Journalanlage nach durchlaufener
Publikationsprüfung. Diese vergleicht weiterhin frisch gelesene Bytes und
vollständige Dateibindungen mit der ursprünglichen Beobachtung. Die native
Recovery stellt Teilwrites durch neue Before-Image-Kopien wieder her. Der
Test nahm dabei ungeprüft an, dass die ursprüngliche, freigegebene Inode-Nummer
nicht wiederverwendet wird. Gleiche zurückgeführte Bytes und eine wieder
vergebene Inode-Nummer lassen diese beabsichtigte Konfliktvorbedingung entfallen.
Die Ableitung folgt aus Log und gebundenem Code; konkrete alte/neue Inodewerte
wurden im fehlgeschlagenen Lauf nicht protokolliert.

Die Testkorrektur hält deshalb ausschließlich lesende Originalhandles über
Writer, Recovery und erneute Publikationsprüfung offen. Kein Hardlink, keine
Produktmanipulation, kein Schlafen und kein Dateisystem-Mock. Die Original-
Dateiobjekte bleiben damit belegt. Der Test weist danach tatsächlich geänderte
Dateiidentität nach und prüft beim Teilrollback zusätzlich exakte Originalbytes.
Die ursprüngliche Write-Falle, Exitklasse 6, unveränderte Inventur und fehlendes
neues Requestreceipt bleiben erforderlich. Hinzu kommt der konkrete Fehlergrund:
publication_footprint_changed bei Teilrollback, publication_base_changed bei
vollständig publiziertem/committedem Ziel. Es wird kein beliebiger Fehler als
Erfolg akzeptiert. SR-TC-0256 dokumentiert diese überprüfbaren Voraussetzungen.

Normativer Bezug: 10.6/10.7 und N.2/N.3 verlangen echte Basis-/Zielwiederherstellung,
eine getrennte Folgeoperation und frische Prüfung unter dem Writerlock. Sie
verlangen keine globale Historie freigegebener Inode-Nummern. Der bestehende
Vertrag akzeptiert reine Zeitstempeländerungen bei gleichen Bytes/Identitäten;
eine neue timestampabhängige Produktverweigerung wäre keine passende Reparatur.
Alle Produktbytes bleiben je Stage bytegleich zu Bundle 576. Die bereits
enthaltene Importkorrektur bleibt erhalten. Spezifikation 0.2.59, Quellvertrag,
Testidentitäten und Testnummern bleiben unverändert; keine neue Detailklärung.

Die vollständigen IDs und Rollen bleiben 16.i.W, 16.i.R und 16.i.C mit
role=implementation. correction_of bindet den ursprünglichen Planhash
`7d8b257dc25caf25750aa48a84a3bc54267c49794c0047552eafc778e03b65a6`
und genau diesen Rest. Erste Stage und Vorherbytes umfassen den gesamten
erhaltenen Dirty-Stand. R und C bleiben die echten angekündigten Zustände;
C erhält unveränderte R-Tests und dieselbe Strukturänderung. Jede Stage
bekommt erneut Rotation 0/1/2 plus vollständige ungefilterte Pflichtauswahl,
einschließlich der gesamten geänderten Regressionstestdatei. Kein früherer
Gateerfolg wird für den neuen Stand verwendet. Verhaltenstests nur in Apply;
Dev prüft statisch, durch reine Collection und native Paketvalidierung.
Keine Dienst-, Control-, Budget- oder Betriebsdatenänderung und keine Schleife.
Vorbereiteter Zwischenstand: C; Häkchen und Zähler gelten erst nach
erfolgreichem Apply-Gate und echtem Commit. Nach vollständigem Abschluss
wäre 687/900 erreicht; nächster offener Schritt bleibt 16.j.W.
