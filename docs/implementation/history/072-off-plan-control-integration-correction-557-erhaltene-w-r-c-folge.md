# OFF-PLAN CONTROL-INTEGRATION-CORRECTION-557 — erhaltene W/R/C-Folge

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-INTEGRATION-CORRECTION-557 — erhaltene W/R/C-Folge

Ausdrücklicher Korrekturauftrag vom 3. November 2026. Maßgeblich ist das
nativ geprüfte Fehler-Result da723a, SHA-256
`66ee61add2a2d98e3afbc45a7b2abc4af3bf08cca0ebf8009c347bed6db5c4b5`,
Basiscommit `0883e7f919c6c1fbce921db59802e1813e330173`,
Arbeitsstand-Fingerprint `cdc758925ed0bd99`. Bundle 556 erzeugte keinen
Commit: 6424 Tests bestanden, 788 scheiterten, drei Teardown-Fehler.
Der vollständige erhaltene W-Arbeitsstand wird übernommen. Alle drei IDs
CONTROL-INTEGRATION-556.W/R/C bleiben in derselben Reihenfolge offen;
jede erhält ihr eigenes N=3-plus-Pflichtauswahl-Gate vor dem Commit.

Die 788 Aufruffehler entstanden beim Fixture-Setup: Apply setzt TMPDIR in
seinen Git-Arbeitsbaum; Controls korrekte Betriebsdatengrenze lehnt diesen
Ort ab. Control-Testhomes verwenden deshalb exklusiv angelegte kurze private
Verzeichnisse außerhalb von Git, unabhängig von TMPDIR und tempfile-Cache.
Die echten Git-/Symlink-/Rechtegrenzen bleiben aktiv, einschließlich der
Protokollfixtures; Socketpfade passen in das Linux-Limit, Cleanup ist gebunden.
Die drei Teardown-Fehler stammen von sys.path-Mutationen des importierten
Capability-Lesers. Nur der separat gestartete Bridge-Entrypoint richtet
seinen Paketpfad ein; der wiederverwendbare Leser verändert ihn nicht.

Abnahmen: geerbter langer Git-TMPDIR mit gesetztem tempfile-Cache,
echtes Socket-Binden, private Rechte und Cleanup, unveränderte Prozessdaten,
gültige/fehlende/defekte Capability und falscher Hash; in R zusätzlich
Git-/Symlink-Ablehnung, privater Ersatzpfad und Cleanup nach Längenfehler.
Sämtliche bisherigen Control-Tests bleiben in jeder Stage Pflicht. Die
ursprünglichen R-Härtungen und der reine C-Refaktor bleiben vollständig
enthalten; C übernimmt Tests und Nummern aus R bytegleich.

Keine fachliche Klärung: Spezifikation 0.2.53, ihre Katalogbindungen und
Produktstand 669/900 (nächster Commit 16.d.W) bleiben unverändert.
Keine Dev-Verhaltenstests; statische Prüfung, Collection und native
ZIP-/Zustandsvalidierung sind kein bestandenes Apply-Gate. Betriebsmigration
und Dienststart sind nicht Bestandteil dieses Korrekturbundles.
