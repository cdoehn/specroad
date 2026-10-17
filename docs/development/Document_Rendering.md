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

Der erste W-Ausschnitt weist Prosa-Anhangsreferenzen mit
`render_attachment_provider_required` und nichtleere Dokument-Renderpolicies mit
`render_policy_provider_required` ab. Diese Deklarationen dürfen weder still
ignoriert noch als Erlaubnis zum Dateizugriff ausgelegt werden. Ein neuer sicherer
Anhangsprovider ist Gegenstand der Vervollständigung. Eine Darstellung ist kein
Nachweis für Freigabe, aktuelle Verifikation oder vollständige Modellvalidierung.

Die APIs führen keine Datei-, Prozess- oder Netzwerkoperationen aus. Atomare
Ausgabeziele und CSV/JSON gehören zu 11.n; die CLI-Anbindung bleibt offen.
13.h ergänzt berechnete Roadmap-/Verifikationsprovider. Fehlende Berichtsdaten
werden durch diesen Schritt nicht erfunden.

Die Verhaltenstests prüfen die Zulassung von Aufrufen, Fehlerverträge, erhaltene
Quelldaten und verbotene Seiteneffekte. Darstellung, Golden Files, Formatierung
und Dokumentation sind gemäß TD-001 keine automatischen Testorakel. Die
gezielten Entwicklungstests sowie das fällige parallele Apply-Drittel sind
Teilnachweise; ein Vollsuite- oder Release-Erfolg wird daraus nicht abgeleitet.
