# Externes Work-Verzeichnis

`specroad.work.root.WorkDirectory` reserviert einen externen Speicherort für
ein vom Aufrufer bereits vertrauenswürdig gebundenes `WorkManifest`.
Der Aufrufer nennt explizit alle geschützten Projekt-, Eingangs- und
Ausgabeverzeichnisse als `ProjectBoundary`-Tupel. Bei Ausgabedateien schützt
er deren Elternverzeichnis. Das Modul ruft keinen Command-Handler auf.

Die Konstruktion erzeugt keine Dateien. Erst `with location.for_checkpoint()
as held:` reserviert den Speicher. `directory` wählt ein explizites fehlendes,
privates leeres oder zum selben initialen Manifest gehörendes Verzeichnis.
Ohne diesen Pfad entsteht ein exklusiv erzeugtes Zufallsverzeichnis unter
`temporary_directory`, sonst unter `TMPDIR` oder `/tmp`. Die Auswahl führt
keine vorausgehenden Schreibproben aus. `location.path` bezeichnet erst nach
erfolgreicher Bereitstellung den tatsächlichen Pfad.

Der erste native Umfang gilt für Linux mit sicheren descriptorrelativen
Dateioperationen und `flock`. Work-Root, Eingangs-/Ausgabegrenzen und sämtliche
Pfadkomponenten werden geprüft. Verzeichnisse werden mit Modus 0700 und
Kontrolldateien mit 0600 angelegt; bestehende zu offene Rechte werden abgewiesen,
niemals still repariert. Der Root-Inode trägt einen nichtblockierenden
Kernel-Lock. Projektlocks werden weder angelegt noch gehalten.

`root.json` bindet Work-ID, ursprünglichen Manifesthash und die lokale
Verzeichnisidentität. `checkpoints/`, `objects/` und `results/` sind private
Container. `work-lock.json` enthält den aktuellen Prozess samt Start-/Boot-/
PID-Namespace-Bindung und zufälligem Eigentümertoken. `held.check()` prüft die
weiterhin gleichen Pfade und Kontrolldateien. Eine reguläre Context-Beendigung
löst nur den eigenen Lock und erhält sämtliche Arbeitsdaten. Eine veränderte,
fremde oder verwaiste Lockdatei verhindert Nutzung; PID/Hostname oder ein freier
Kernel-Lock allein erlauben keine Übernahme. Native I/O-Fehler bleiben erhalten.

Nach der ersten Bereitstellung merkt sich die Location die Verzeichnisidentität.
Ein verlorener oder ausgetauschter Root wird bei erneuter Nutzung derselben
Location nicht neu erzeugt. Beim Erwerb werden auch vorhandene Containerinhalte
iterativ und descriptorrelativ auf sichere Namen, reguläre private Einträge,
fehlende Hardlinks und stabile Verzeichnisgrenzen geprüft. Es werden dabei keine
Payloadbytes als Programm gelesen oder ausgeführt. Spätere Payloadleser und
-schreiber benötigen weiterhin eigene aktuelle Pfad- und Inhaltsprüfungen.

Geänderte Kontrolldateien verhindern auch die automatische Entfernung des
Lockrecords beim Verlassen. Der Kernel-Lock und eigene Deskriptoren werden
dennoch freigegeben; die tatsächlichen fremden oder beschädigten Bytes bleiben
zur Diagnose erhalten. Ein geforkter Kindprozess darf den Eltern-Lock weder
nutzen noch freigeben. Es findet keine automatische Wiederholung oder Reparatur
eines fehlgeschlagenen Erwerbs statt.

Dies ist eine Speicher- und Lockgrundlage, noch keine Checkpointpublikation.
`work.json`, atomare Generationen, Eingangs-Snapshot, tatsächliches Resume,
automatische Pause und Code 8 folgen in den zugehörigen Planschritten. Das
Wiederöffnen akzeptiert vorerst genau dasselbe initiale Manifest am unverändert
gebundenen Root; ein neuer Generationenkandidat oder ein verschobener Root
benötigt später eine gesonderte geprüfte Fortsetzungs-/Restore-Bindung.
Dateien im Work-Verzeichnis werden weder als Code geladen noch automatisch
bereinigt. Ein fehlgeschlagener Aufbau bleibt zur Diagnose erhalten.

Der spätere Runtime-Aufrufer muss vor einem realen Blocker noch eine sichere
In-Memory-Fertigstellung beurteilen. Dieses Modul behauptet weder deren
Unmöglichkeit noch eine dauerhafte Fortsetzungsfreigabe. Kleine vorhandene
Metadatenbefehle und eine unbenutzte WorkDirectory erzeugen keine Work-Dateien.
