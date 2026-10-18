# Sprache und Verbindlichkeit in Dokumenten

`specroad.documents.resolve_requirement_presentation(model, requirement_id)`
liefert einen eigenen `RequirementPresentation`-Wert aus einem gebundenen
`TargetModel`-Snapshot. `.data` enthält abgelöste JSON-Daten;
`.sha256` bindet deren kanonische Bytes. `.source_bytes` erhält die vollständige
ursprüngliche Requirement-Datei einschließlich ihrer JSON-Formatierung.

Der Vertrag `requirement-presentation-v1` trennt `statement`,
`normative_force` und `content_language`. Das Statement bleibt unverändert,
einschließlich Unicode, Leerraum, Zeilenumbrüchen und bereits vorhandener
Negation. Der deklarierte Force-Wert gilt für diesen vollständigen Satz;
Priorität oder enthaltene Schlüsselwörter ändern ihn nicht. Identität, Revision,
relativer Quellpfad, Quell-/Recordhash, Statement-UTF-8-Hash, Modellwurzel,
Inputhash und Profilversionen binden die Daten an ihre tatsächliche Quelle.

`content_language.language` übernimmt das gespeicherte BCP-47-Tag mit seiner
ursprünglichen Schreibweise. `text_direction` übernimmt unabhängig davon
`ltr`, `rtl` oder `auto`; ohne Feld gilt `auto`.
`text_direction_source` unterscheidet Deklaration und Standardwert.
Es gibt keine Sprach-, Regions-, Schrift- oder Richtungsdetektion und keine
Übersetzung oder Normalisierung des Statements.

Die ausgewählte Requirement-Datei durchläuft die vorhandene Feldvalidierung,
einschließlich der Pflichtangaben für `should`. Der Datenvertrag bestätigt
keine semantische, Policy-, Registry- oder vollständige Projektvalidierung,
keine aktuelle Dateisystemprüfung, Freigabe oder Schreibberechtigung.

`display_locale` kommt ausdrücklich aus der Projektkonfiguration und betrifft
die Beschriftung. Ausschließlich die bereits im Modell gebundenen passiven
`language_packages` können ein `force_label` liefern. Die vorhandene
Basic-Filtering-Auswahl erhält ihre Aktivierungsreihenfolge; passende Pakete
stehen mit Version und Quellhash in `label_packages`. Fehlende Labels behalten
den technischen englischen Enumwert. Inhaltssprache und Display-Locale bleiben
unabhängig. Host-Locale und implizite Datei-/Ressourcensuche werden nicht benutzt.

`render_document` verwendet dieselben Daten bei Requirement-Referenzen in
`full` und `summary` sowie für die ergänzten Zielzusammenfassungen von `link`.
Jede wiederholte Include-Occurrence bleibt erhalten. Force-Label und
Originalstatement werden separat ausgegeben. Dokument-/Section-Überschriften,
Prosa und Artefaktreferenzen tragen ihre eigenen Sprach-/Richtungsmetadaten:
HTML erhält `lang` bei vorhandener Deklaration und `dir`; Markdown kennzeichnet
die Angaben als Metadaten. Eine Section ohne eigene Sprache übernimmt keinen
erfundenen Sprachwert aus Konfiguration oder übergeordnetem Dokument.

Dieser W-Ausschnitt verbindet Requirement-Referenzen und die genannten
Dokumentknoten mit den bestehenden Sprachverträgen. Zellweise Sprachannotationen
in View-/Query-Tabellen sowie weitere Randfallarbeit gehören zur anschließenden
Vervollständigung. Der Renderer liefert weiterhin nur UTF-8-Bytes und startet
keine Dateiausgabe, Templates, Programme oder Browser. Verhaltenstests prüfen
die Daten vor der Darstellung, Bindungen, Fehlerverträge und Seiteneffekte;
Markup, übersetzte Labels und Layout sind keine Testoracles.
