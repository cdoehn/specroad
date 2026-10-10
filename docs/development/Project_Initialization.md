# Projektinitialisierung

`specroad init [PATH]` erzeugt die Mindeststruktur aus §8.1. Ohne `PATH` gilt das
aktuelle Aufrufverzeichnis. Die strukturierte Schnittstelle verwendet
`command_id: init` und optional `arguments.path`; sie durchläuft denselben
Handler. `--format json` liefert `project-init-v1` im normalen Ergebnisumschlag.
Der Befehl benötigt weder ein vorhandenes SpecRoad-Projekt noch Git und startet
kein externes Programm. Er verändert keine Git-Metadaten.

Der Anfangsstand verwendet de-DE, Präfix SR, eine neue Projektidentität und eine
echte `random128-v1`-Identität für genau ein Primärspezifikationsdokument im
Zustand draft. Als Erzeuger ist der tatsächliche Toolpfad `specroad.init`
vermerkt; eine menschliche Prüfung wird nicht behauptet. Core-/Softwareprofile,
das eingefrorene Sprachregister und neun deklarative Sprachpakete stammen aus
der Distribution. Ihre vorhandenen nativen Leser prüfen die Bindungen vor dem
ersten Write. Die Projektkonfiguration bindet die materialisierte Registerkopie.

Das Ziel darf fehlen oder ein vorhandenes Repositoryverzeichnis sein. Sein
Elternverzeichnis muss bereits vorhanden sein. Fremde Repositorydateien bleiben
erhalten. Bereits vorhandene leere beanspruchte Rootverzeichnisse werden unter
Erhalt ihrer Inodes verwendet; belegte beanspruchte Verzeichnisse, Dateien,
Links und portable Namenskollisionen führen zum Konflikt vor der Vorbereitung.

Der native Linux-Pfad hält die vorhandenen Inode-Mutexe für Elternverzeichnis
und Ziel. Er baut Dateien und Verzeichnisse zunächst unter
`.specroad-bootstrap` im Ziel auf. Das dauerhafte Journal enthält den Rootbezug,
die wiederverwendeten Verzeichnisse, Veröffentlichungseinheiten und die exakten
Inodes, Modi, Größen und Bytehashes der vorbereiteten Inhalte. Native
No-Replace-Renames veröffentlichen ausschließlich fehlende Pfade.
`specroad.json` kommt zuletzt. Normale Fehler vor vollständiger Veröffentlichung
nehmen ausschließlich die noch exakt belegten eigenen Einheiten zurück.
Geänderte oder zusätzliche Inhalte werden erhalten und als Recoverybedarf
gemeldet. Ein bereits vollständig veröffentlichter gültiger Grundstand wird
bei einem späteren Bereinigungsfehler erhalten.

Der W-Stand übernimmt kein vorgefundenes Bootstrap-Journal. Nach einem harten
Prozessabbruch bleibt es als Konflikt erhalten; die sichere Wiederaufnahme und
weitere Fault-Injection gehören zum anschließenden R-Schritt. Die Mutexe sind
advisory; sie ersetzen keine Sandbox gegen unabhängige nichtkooperierende
Hostschreiber. Andere Plattformen und Dateisysteme ohne den nativen
No-Replace-Vertrag werden vor Writes abgewiesen.

Das Ergebnis weist Dateien und Bytebindungen sowie
`validation_scope: configuration_record_fields_and_distribution_bindings` aus.
`full_semantic_validation: false` trennt die tatsächlichen Feld-/Ressourcenprüfungen
von den noch nicht vollständigen späteren Dokument- und Projektgates. Es ist
keine Modell-, Freigabe- oder Releasebescheinigung. Die Bootstrapfunktion
liefert keinen Change Plan für ein schon bestehendes SpecRoad-Projekt.

Die neuen leeren Betriebsverzeichnisse `.specroad/tmp` und `.specroad/merge`
werden von den vorhandenen Preflights als leer erkannt. Inhalt darin bleibt
ungeklärt und blockiert den normalen Ablauf; die Initialisierung führt keine
allgemeine Bereinigungsregel für diese Verzeichnisse ein.
