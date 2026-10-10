# Gespeicherte Modell- und SRX-Auswertungen

`specroad.work.evaluation` verbindet explizit gespeicherte Modell-/Profilbytes
mit den bestehenden Validierungs-, Graph- und SRX-Funktionen. Der vertrauenswürdige
Host registriert `analysis.evaluate` als `read_only`, `bootstrap`, Effekt `none`,
Ergebnisschema `work-evaluation-v1` und vollständige Ausgänge 0/1 mit den passenden
Diagnosecodes. Dieser Vertrag installiert keinen öffentlichen CLI-Befehl. Sein
Handler wird nicht aus Workdaten geladen oder vom Auswertungsadapter ausgeführt.

`prepare_evaluation_work(registry, inputs=..., jobs=...)` verlangt eine
aufgezeichnete Buildidentität und erstellt das unabhängige Anfangsmanifest.
Eingänge besitzen `root_id` (`model` oder `profiles`), relativen `path` und `raw`
als Bytes. Der vorhandene `InputSnapshotTask` kann diese expliziten Eingänge
zuvor unter den tatsächlichen Rootschutzprüfungen erfassen. Der Host bleibt für
die vollständige fachlich erforderliche Eingangsmenge verantwortlich.

Jeder Job hat einen eindeutigen `key` und genau eine der folgenden Formen:

- `kind=validate`, `core_profile` und `selected_ids` (null oder eindeutige IDs).
  Die native Modellprüfung untersucht alle gespeicherten Quellen und erweitert
  die semantische Auswahl um deren notwendige Abhängigkeiten. Originalbericht,
  tatsächlich geprüfter Umfang, normalisierte Diagnosen und Exit-Code bleiben
  vollständig erhalten. Fehlende Pflichtprüfungen liefern
  `WorkEvaluationBlocked` mit dem tatsächlichen vollständigen Befund; fehlende
  Profile behalten ihren nativen Fehlervertrag.
- `kind=srx`, `rule_id`, `program` und `context` als passive JSON-Daten. Die
  echte Graphauflösung und SRX-Auswertung verwenden die gespeicherten Modelle.
  Fehlend wird getrennt von null und false gespeichert. Native SRX-Fehler werden
  weitergegeben und niemals als falsches Prädikat oder erledigte Einheit gewertet.

Der Host veröffentlicht Generation 0 in einem externen `CheckpointStore` mit
aktuellen geschützten Roots. `advance_evaluation_work(store, call,
registry=..., max_units=1)` verlangt eine aktive `InvocationConsumption` und
prüft Build, Bindung und vorhandene vollständige Checkpointkette erneut.
Bereits bestätigte Auswertungen werden wiederverwendet. Ganze neue Auswertungen
werden unter der Work-Lease berechnet und zusammen dauerhaft gespeichert;
ein Fehler vor dieser Veröffentlichung bestätigt keine neue Einheit.

`max_units` und die aktuellen weichen Ressourcenfenster begrenzen den jeweiligen
Aufruf. Auch bei bereits überschrittenem weichem Ziel wird eine echte Einheit
versucht. Ein einzelner großer Validierungs-/Graphlauf besitzt hier noch keinen
dauerhaften inneren Cursor. Verbrauch und Workidentität gehören nicht zur
fachlichen Ergebnisprojektion.

`finalize_evaluation_work(store, registry=...)` reduziert erst nach allen Jobs
sämtliche gespeicherten Ergebnisse und Diagnosen in einer eigenen Generation.
Ein vollständiger fachlicher Fehler bleibt Code 1, `failed` und `complete=true`.
Wiederholter Abschluss liefert dieselben Ergebnisbytes ohne erneute Auswertung.
Die Projektion bezeichnet ihre Quelle ausdrücklich als `explicit_saved_model`;
`project_files_verified=false` behauptet keine aktuelle Projektverifikation.

Gleich gebaute Modul-/Zipapp-Distributionen können in neuen Prozessen und nach
Verschieben der Runtime-, Work- und geschützten Rootpfade fortsetzen. Rename
erhält dabei die Dateisystemidentität. Nach vollständiger Aufnahme werden die
ursprünglichen Quelldateien oder Projektcaches für diese Auswertungen nicht mehr
benötigt. Hashbindung beweist Datenkonsistenz, keine Echtheit fremder Workdaten.

Für normative Änderungen bleibt der vorhandene `work.publication`-Pfad zuständig:
getrennte dauerhafte Vorbereitung, frische Projektprüfung und echte native
Transaktion mit ursprünglicher Requestidentität. Der Paritätsnachweis vergleicht
diesen Weg mit einer direkten nativen Transaktion und deren Receiptwiederholung.

Allgemeine CLI-/Code-8-Anbindung, Workpaketexport/-restore dieses neuen Adapters,
andere Buildversionen, große speicherbegrenzte Auswertungen, sämtliche späteren
Fachbefehle sowie die vollständige Plattform-/Sandbox-/Release-Matrix bleiben
offen. Die zugehörigen Requirements sind nur teilweise umgesetzt.

## Gespeicherte Befunde und geänderte Voraussetzungen

Vor einer schreibenden Work-Lease prüft der Adapter gespeicherte native
Validierungsbefunde auf den vollständigen derzeit unterstützten Phasenvertrag.
Quellmanifest, Quellzahl, angeforderte Auswahl, tatsächlicher Prüfumfang,
Pflichtphasen, Status und Verweigerung von Freigabe-/Writebehauptungen müssen
zusammenpassen. Die vorhandene native Diagnoseprojektion wird auf den erhaltenen
Originalbericht angewendet und vollständig mit der gespeicherten Projektion
verglichen. Fehlende oder veränderte Diagnoseeinheiten, Summen und zusätzliche
Ergebnisfelder werden so als Code-6-Konflikte vor Fortsetzung oder Abschluss
abgewiesen. Auch neue Kandidaten durchlaufen diese Prüfung vor Veröffentlichung.

Dies prüft die Konsistenz gespeicherter Beobachtungen; Modellvalidierung,
Profilkomposition, Graph-/SRX-Auswertung und Fachgates werden für bestätigte
Einheiten nicht wiederholt. Der Leser authentifiziert keine fremden,
vollständig erfundenen Beobachtungen und ersetzt die unabhängige Anfangsbindung
und den geschützten Work-Store nicht.

Fehlende oder veränderte Snapshotobjekte ergeben `WorkEvaluationDataError`
(Code 6). Soweit das Objekt zu einem bekannten Eingang gehört, benennt
`as_dict().resource` dessen `root_id`, relativen `path` und `sha256`.
Andere Speicherbefunde behalten ihre logische Workressource. Noch vorhandene
Originaldateien werden nicht stillschweigend als Ersatz eingesetzt.
Die Ausnahme begründet keine Löschung, Reparatur oder Neuinterpretation des
tatsächlichen Checkpoints.

Ein Buildwechsel während der Auswertung oder nach tatsächlicher Veröffentlichung
liefert keinen Erfolg unter einer falschen Runtimebindung. Nach Wiederherstellung
der kompatiblen Runtime wird nur der tatsächlich gespeicherte Präfix wiederverwendet.
Aktuelle native Hostfehler, beispielsweise `EMFILE` bei unzureichendem
Dateideskriptorlimit, bleiben solche Fehler. Sie werden nicht als Softbudgetereignis,
fachliches Prädikat oder bestätigter Fortschritt umgedeutet. Ein späterer
Aufruf mit ausreichender aktueller Ausstattung kann denselben Auftrag fortsetzen.
