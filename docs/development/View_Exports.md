# Maschinenlesbare Viewexporte

`specroad.documents.export_view(model, view_id, output_format='json')` erzeugt
UTF-8-Bytes aus den nativen Viewdaten des eigenen `TargetModel`-Snapshots.
`configuration_id` wird unverändert an die vorhandene Viewauflösung übergeben.
Das gewählte Format muss in der View deklariert sein. Der Exportumfang heißt
`selected_view_columns`: ausgewählte Zeilen, ihre Reihenfolge, Quellbindungen
und deklarierte Zellen. Unausgewählte Felder, separate Gruppierungslisten und
nicht als Spalte gewählte Relationsprojektionen gehören nicht zu diesem Umfang.
Exportierte Werte werden weder normalisiert noch in das Modell zurückimportiert.

JSON verwendet `kind=view-export-v1`, `format_version=1` und
`cell_encoding=typed-json-v1`. `view_export_schema()` liefert sein lokales
geschlossenes Formschema; die native Viewauflösung prüft zusätzlich die
fachlichen Quell-, Spalten- und Typbindungen. Eine Zelle besitzt `type` und
`value`; eine fehlende Zelle ausschließlich `type=missing`. Null, leere Strings,
Zahlen, Wahrheitswerte, Arrays und Objekte bleiben unterscheidbar. `losses=[]`
gilt ausschließlich für den genannten Spaltenumfang, nicht als Behauptung eines
vollständigen Projekt- oder Viewdefinitions-Roundtrips.

Das initiale CSV-Profil heißt `view-csv-v1` / `csv-scalars-v1`. Ein gewöhnlicher
RFC-4180-Reader liest gleich breite Datensätze mit CRLF-Dateizeilen und UTF-8
ohne BOM. Die ersten beiden Spalten heißen `record_type` und `metadata`, danach
folgen die deklarierten Überschriften in ihrer Reihenfolge, auch bei gleichen
Überschriften. Der erste Nutzdatensatz hat Typ `metadata`: Seine zweite Zelle
enthält die JSON-Metadaten, die restlichen Zellen sind leer. Darin stehen auch
die Spaltentypen und geordneten `row_bindings`. Jeder weitere Datensatz hat Typ
`data`, eine leere Metadatenzelle und die eigentlichen Spaltenwerte. Strings
bleiben unverändert; andere skalare Werte verwenden ihre JSON-Skalarform. Zum
typisierten Einlesen werden Werte positionsweise anhand der Spaltentypen und
`row_bindings` zusammengesetzt. Auch eine leere View hat ihre Metadatenzeile.
CSV-Strings sind Datenaustauschwerte; dies ist kein Spreadsheet-Ausführungsprofil.

Beide Formate tragen Modellwurzel, Inputhash, View-/Quellrevision und Hashes,
Tool-/Schema-Version, aktive Profile sowie die explizite Generated-Kennzeichnung.
Sie gewähren weder Approval noch Schreibrechte. Eine Dateisystemaktualität des
ganzen Projekts wird aus einem gelieferten Snapshot nicht abgeleitet.

`write_view_export(model, view_id, source=source, path='generated/view.json')`
veröffentlicht genau eine neue Datei. `source` ist ein an denselben tatsächlichen
Projektroot und dieselben Konfigurationsbytes gebundener `ProjectSource`.
Das vorhandene Zielverzeichnis muss unter dem konfigurierten `generated_path`
liegen. Normative, betriebliche, reservierte und fremde Ziele werden abgewiesen.
Die vorhandene native Descriptor-Traversierung wird ohne Lock-Erwerb verwendet;
der bestehende bytegebundene Writer veröffentlicht erst vollständig vorbereitete
Bytes atomar und ohne Überschreiben. Symlinks, Spezialdateien, verschachtelte
Projektroots und vorhandene Ziele werden nicht verfolgt oder ersetzt.
Es entstehen weder Projektlock, Journal noch Receipt unter `.specroad/`.

Bei Fehlern bleiben tatsächliche Zustände erhalten: Eine unterbrochene
Vorbereitung kann eine private `.view-export-*.tmp` im gewählten generierten
Verzeichnis hinterlassen; vor Veröffentlichung fehlt das endgültige Ziel.
Ein Fehler nach Veröffentlichung kann die vollständige Zieldatei erhalten.
Keiner dieser Fehler erzeugt einen Erfolgsnachweis oder einen automatischen Retry.

Der W-Zustand unterstützt CSV zunächst nur für vorhandene skalare Zellen.
Array-/Objektspalten werden auch bei leerer Auswahl abgewiesen; fehlende Werte
werden nicht in Null oder Leerstring umgedeutet. Explizite verschachtelte
CSV-Serialisierung, weitere Fehlerszenarien und zusätzliche zulässige Zielarten
bleiben Gegenstand von 11.n.R. Externe Ziele, Verzeichniserzeugung, Ersetzen
vorhandener Dateien und die spätere CLI-Anbindung sind hier nicht implementiert.
Der native Dateiweg setzt Linux-Descriptoroperationen voraus; andere Plattformen
erhalten durch diesen Schritt keinen nachgewiesenen Schreibsupport.

Die Abnahme prüft ausschließlich maschinenlesbare Daten und tatsächliche
Seiteneffekte. Sie verwendet keine Pretty-, HTML-, Markdown- oder Dokumentoracles.
