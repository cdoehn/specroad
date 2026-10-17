# Dokument- und Viewdarstellung aus gelieferten Modelldaten

`specroad.documents.render_document(model, document_id, output_format="markdown")`
und `render_view(model, view_id, output_format="markdown", configuration_id=None)`
erhalten einen nativen `TargetModel` und liefern UTF-8-Bytes. Das Format ist ein
Keywordargument; unterstützt werden `markdown` und `html`. Bei Views muss es
zusätzlich in den tatsächlich gespeicherten `formats` stehen.

Die Dienste erstellen ihren eigenen Snapshot und verwenden die vorhandene
Komposition, Prosa-, Referenz-, Tabellen- und Viewauflösung. Querygrenzen,
Gruppierung, Fehlwerte, verschachtelte Projektionen und native Fehler bleiben
bei diesen Datenprovidern. Wiederholte Includes bleiben wiederholte Vorkommen;
ein Artefaktanker bezeichnet das erste Vorkommen seiner vollständigen ID.
Reine Linkreferenzen auf externe Kompositionsziele erhalten eine lokale
Zusammenfassung aus dem tatsächlichen Zielrecord. Es wird nichts nachgeladen.

Metadaten nennen Modellwurzel, Tool-/Schemaversion, aktive Profile und die
Dokument-/Viewrevision. Dokumentreihenfolge stammt aus der Komposition,
Viewreihenfolge aus der Query. Ergänzte Referenzziele werden nach Typ und ID
sortiert. HTML verwendet ausschließlich feste Elemente und eingebettete Styles;
Nutzdaten werden escaped. Seitenumbrüche sind Druckumbrüche. Admonitions erhalten
einen abgesetzten Hinweisbereich. Es gibt keinen ausführbaren Templatepfad.

Prosa-Anhangsreferenzen verwenden ausschließlich die `attachment_descriptors`
und `resource_files` des gelieferten Modells. Pfad, Größe und SHA-256 müssen zu
den Originalbytes passen. Der Renderer akzeptiert höchstens 8 MiB pro Anhang
und genau `image/png`, `image/jpeg`, `image/gif` oder `image/webp` mit passender
Dateisignatur. Ein Signaturcheck ist keine Bilddekodierung und kein Nachweis der
Darstellbarkeit. Beide Ausgabeformate betten die Bytes als Data-URI ein; es gibt
weder Pfadnachladen noch externe Ressourcen. Fehlende Deklarationen bleiben
`render_attachment_provider_required`, andere Medientypen werden mit
`render_attachment_media_provider_required` abgewiesen. SVG, HTML und PDF
erhalten keinen aktiven Einbettungspfad.

Eine leere Dokument-Renderpolicy verwendet die vorhandenen Formate. Die einzige
unterstützte nichtleere Policy lautet `{"formats": ["markdown", "html"]}`;
auch eine nichtleere Teilmenge ist zulässig. Jedes Format muss einmalig sein,
und das angeforderte Format muss enthalten sein. Dies gilt ebenso für alle
eingebundenen Dokumente. Unbekannte Policyfelder bleiben
`render_policy_provider_required`. Deklarationen erteilen keine Dateirechte.
Eine Darstellung ist kein Nachweis für Freigabe, aktuelle Verifikation oder
vollständige Modellvalidierung.

Die APIs führen keine Datei-, Prozess- oder Netzwerkoperationen aus. Atomare
Ausgabeziele und CSV/JSON gehören zu 11.n; die CLI-Anbindung bleibt offen.
13.h ergänzt berechnete Roadmap-/Verifikationsprovider. Fehlende Berichtsdaten
werden durch diesen Schritt nicht erfunden.

Die Verhaltenstests prüfen die Zulassung von Aufrufen, Fehlerverträge, erhaltene
Quelldaten und verbotene Seiteneffekte. Darstellung, Golden Files, Formatierung
und Dokumentation sind gemäß TD-001 keine automatischen Testorakel. Die
gezielten Entwicklungstests sowie das fällige parallele Apply-Drittel sind
Teilnachweise; ein Vollsuite- oder Release-Erfolg wird daraus nicht abgeleitet.
