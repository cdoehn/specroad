# OFF-PLAN TRANSPORT-PYZ-541 — Direkte PatchHarbor-1.8.0-Anbindung

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN TRANSPORT-PYZ-541 — Direkte PatchHarbor-1.8.0-Anbindung

Autorität: ausdrücklicher Nutzerauftrag vom 1. November 2026, die geprüfte
1.8.0-PYZ ohne vorgeschaltetes Runtime-Result zu verwenden, die Spezifikation
anzupassen und genau ein Offplan-Bundle an den bestehenden Watcher zu liefern.
Die CLI-/Work-Detailentscheidung erfolgt im beauftragten Umfang gemäß
SPECROAD-DECISION-1. Produktfortschritt bleibt **655/900**, nächster Produktcommit
**15.n.R**; die vollständige noch offene Hin-/Rück-/Hostabnahme wird nicht vorgezogen.

Basis: vollständig nativ geprüftes sauberes Result
`specroad-apply_Result_180715_1101_8a1715.zip`, SHA-256
`f9333169b5eb67a08a0b79f4332ae17bce4991f93a7ea70da71f6fb220bcd099`,
HEAD `1411d04545449c9a0eaeb64cd38f5458db15853a`, Bundle 540 mit 6.420
bestandenen Apply-Tests. Die nächste fällige Rotationsgruppe ist 2.

Geprüfte Quellen: Spec Anhang W, aktive Adapter/CLI/Work-Verträge, originale
1.4/1.6/1.7-Fixtures, PatchHarbor-dev-Commit
`2121d3abd2ca4b6c523d9e0698d997a86581d5bc`, dessen öffentliche Runtime-/API-
Dokumentation und offizieller lokaler Build. Die neue PYZ hat SHA-256
`050cc2d1dc3ecbb1478f6a40c9a5123d1d34d350215d5cc0303025ea08dc4f1e`.
Native Artefaktprüfung, offline API-/CLI-Exporte aus Wheel/sdist/PYZ, Bytegleichheit
mit dem vorhandenen Kandidaten desselben Commits und passive Prüfung des
aktuellen SpecRoad-Results wurden vor dieser Umsetzung auf Linux/CPython 3.14.4
belegt. Dies ist kein SpecRoad-Verhaltenstest und keine vollständige CI-Matrix.

Entscheidung: `--patchharbor-pyz` und `--patchharbor-pyz-sha256` sind explizite
Pflichtpaare. `PatchHarborRuntime` bindet den direkten Pfad und
`trusted_artifact_sha256`. Die geschlossene Work-Quellbindung verwendet
`patchharbor_pyz_sha256`, die Aufgabenkennung `source-safe-outbound-pyz-v2`.
Die vorherigen Optionen bleiben als historische Verträge dokumentiert und
werden nicht zu Aliasen umgedeutet. Bestehende Daten werden nicht migriert.
Ein neuer ausdrücklicher Export bleibt jederzeit möglich. Der öffentliche
Resultreader und die tatsächlichen Projekt-Results bleiben Bestandteil des
Rundwegs; die Kopplung zum Result als Codequelle entfällt vollständig.

Alternativen: Result-Optionen als Alias verschleierten die geänderte Bedeutung
alter Requests; Hostinstallation/pip machten die Codequelle umgebungsabhängig;
Import direkt aus einer veränderbaren Eingabe gäbe die private Lazy-Import-
Grenze auf. Gewählt ist eine explizit hashgebundene eigene Kopie mit bestehenden
SpecRoad-Pfad-/Dateiprüfern und ausschließlich öffentlicher PatchHarbor-API.
Norm, Tests und aktive Kataloghashes werden gemeinsam fortgeschrieben; Original-
Fixtures und historische Evidence bleiben unverändert. Keine neue Requirement-ID,
Produktposition, automatische Hostfreigabe oder zusätzliche Plattform entsteht.

Echte aufeinanderfolgende Zustände im selben Bundle:

- **TRANSPORT-PYZ-541.W:** vollständiger direkter Adapter, native 1.8.0-Fixture,
  CLI/Selbstbeschreibung/Work/Hinexport, Spec 0.2.46, aktive Katalogbindungen und
  positive/negative Import-, Snapshot- und Hinexportabnahmen.
- **TRANSPORT-PYZ-541.R:** fortlaufender Besitz-/Rechteschutz der privaten Kopie,
  Nachprüfung nach Imports, Unterbrechungs-/Austausch-/Capability-Grenzen und
  alte Work-Vertragsabnahmen desselben Ausschnitts.
- **TRANSPORT-PYZ-541.C:** Datei-/Importmechanik vom öffentlichen Adapter lösen,
  gebundene Fakten zentral verwenden; keine neue Funktion oder Formatsemantik.

Je Zustand vollständige geänderte Testdateien plus relevante Runtime-/Snapshot-,
Hinexport-, Work-/Checkpoint-, CLI-/Distributionsregression als ungefilterte
Pflichtauswahl. Apply vereinigt sie mit der aktuell gefilterten N=3-Gruppe,
prüft einmal parallel und committet erst danach. Dev führt ausschließlich
statische Prüfung, reine Collection und native Paketvalidierung aus. Historische
Testnummern bleiben unverändert; neue Identitäten werden hinten ergänzt.

Offen bis zu den tatsächlichen Gates: Apply-Verhaltensabnahme aller drei
Zustände, reale CPython-Matrix in der ausschließlich vom Nutzer gestarteten CI
und die übrigen Produktabnahmen aus 15.n.R/C, 15.o und späterer Rück-/Hostintegration.
Keine automatische CI, kein Dienststart, kein eigener Apply oder Wiederholungsloop.

**Vorbereiteter R-Zustand:** Die private Runtimekopie prüft vor jeder Nutzung
Besitz und Rechte von Datei und Verzeichnis zusätzlich zu Identität und Bytes.
Nach Import/Fähigkeitsabfrage werden die externe Quelle und private Kopie
nochmals geprüft, bevor eine API oder Prozesswiederverwendung freigegeben wird.
Die Work-Prüfung bindet explizite neue Optionen, gespeicherten Artefakthash und
festen 1.8.0-Pin gemeinsam. Austausch mit identischen Bytes, Rechteausweitung,
Teilimport/KeyboardInterrupt, alle vier Capability-Versionen sowie alte oder
vermischte Work-Bindungen erhalten eigene echte Verhaltenstests. Dev hat diese
nicht ausgeführt; die tatsächliche Abnahme erfolgt im R-Apply-Gate.

**Vorbereiteter C-Zustand:** Exklusive Runtimekopie und fortlaufende Dateiprüfung
liegen in `_runtime_files`; der öffentliche Adapter behält Auftrags-, Import-
und Fähigkeitssteuerung. Die Größenbegrenzung stammt aus demselben gebundenen
Vertrag. Die ungenutzte frühere Result-Bootstrap-Implementierung ist entfernt;
der alte private Modulpfad enthält nur noch den historischen Stilllegungshinweis.
Original-Resultate und deren geprüfte Helferbytes bleiben unverändert. Keine
Dateilöschung oder zusätzlicher Payloadmechanismus wird benötigt. Die gleichen
Tests und ihre Nummern gelten weiter; kein neues Fachverhalten, kein behaupteter
Dev-Test- oder Apply-Erfolg.
