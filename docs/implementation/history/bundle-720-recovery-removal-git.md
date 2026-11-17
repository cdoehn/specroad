# Bundle 720 — Produkt-Recovery entfernen und Git-Wiederanlauf abnehmen

16. November 2026. Gebundenes Checkpoint-Result:
`d506b4fab0e7331c96059e978de828afd0d4f043db09febf4aa4692b9e3bc473`.
Die Basis `4de888c24651a589d5e5ef5c099c10168b9a6ec2` ist sauber; die
Löschvertragsfolge DELETE-CONTRACT.W/R/C ist im vorherigen nativen Apply-Result
vollständig bestätigt. Es gibt keinen offenen Korrekturpräfix und keine neue
normative Klärung. Maßgeblich bleibt RECOVERY-REMOVAL-006 mit 10.7/N/P.

| Stage | Umsetzung | Abnahmebezug |
| --- | --- | --- |
| 18.w.W | Öffentliche Recovery-Befehle und Restore-Ausführung entfernt; normale Work-Vorbereitung und Pakete erhalten. | vorheriges eigenes Gate erforderlich |
| 18.w.R | Legacy-Reparatur und Ownerübernahme gesperrt; native Checkpointleser, Transport und gemischte Regressionen erhalten. | vorheriges eigenes Gate erforderlich |
| 18.w.C | Normale Worköffnung klar benannt, tote Zweige vereinfacht; alle R-Testbytes unverändert. | vorheriges eigenes Gate erforderlich |
| 18.x.W | auto_recover aus aktuellen Konfigurationsverträgen entfernt; getrennten Git-Checkout mit Originalreceipts und neuem Fachauftrag integriert. | vorheriges eigenes Gate erforderlich |
| 18.x.R | Letzten Snapshot-Reparaturadapter entfernt; fehlende Pflichtdaten, ungültige Git-Stände und positive Writer-/Work-/Transportmatrix gebunden. | vorheriges eigenes Gate erforderlich |
| 18.x.C | Verbraucherfreie Reparaturhilfen und alten Servicealias entfernt; historische Prüfcodecs und alle R-Testbytes erhalten. | Zielstand dieser Stage |

Aktueller Commitzielstand: **18.x.C**, **780/918**, danach **18.l.W**.
Diese Angaben sind keine vorgezogene Testabnahme: Apply bringt jeden Zustand
separat aus und führt vor seinem Commit das eigene N=3-plus-Pflichtauswahl-Gate
nach [dem Apply-Verfahren](../../development/Apply_Commit_Plans.md) aus.

Die Vorarbeiten zu 18.w werden weiterverwendet. Native geschlossene Löschaktionen
binden vollständige Vorherbytes und Zustandsinventare. Keine globale Bereinigung
oder Entfernung fremder Dateien. Normale Workvorbereitung, Paketexport/-restore,
Checkpoints, fertige Ergebnisse, historische Originaldaten und Control-Recovery
bleiben erhalten. Nur reine obsolete Reparaturoracles entfallen; gemischte
Writer-, Receipt-, Lock-, Work- und Transportregressionen bleiben gebunden.
Stabile Testnummern werden nie wiederverwendet. Historische Messungen bleiben.

Git wird ausschließlich durch die expliziten temporären Testfixtures als
Nutzeraktion ausgeführt. Produktcode führt keinen Git-Reset/-Checkout aus.
Der beschädigte Root bleibt erhalten; fehlende Pflichtdaten oder Originalbelege
werden nicht rekonstruiert. Neue aktuelle Konfigurationen weisen auto_recover ab.

Dev führt ausschließlich statische Prüfung, reine Collection und native
Paketvalidierung aus. Verhaltenstests und echte Prozess-/Git-Fälle sind für Apply
vorbereitet. Eine bestandene Vollsuite, Zielplattformmatrix oder Releasefreigabe
wird nicht behauptet; die verbleibenden Nachweise gehören weiter nach M20.
