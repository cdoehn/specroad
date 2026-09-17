# Sprachpakete: Metadaten, Labels und Locale-Unabhängigkeit

## Umfang von 2.o

Der Core liefert neun reine Metadaten-/Labelpakete als UTF-8-JSON-Ressourcen:
`de`, `en`, `hi`, `id`, `pt`, `es`, `ru`, `ja`, `zh-Hans`, jeweils `1.0.0`.
`zh-Hans` nennt ausdrücklich die beiden Bereiche `zh-Hans` und `cmn-Hans`;
sie werden nicht zu einer einzigen Sprachidentität umgeschrieben.
Die Ressourcen enthalten die sechs Felder aus Anhang S.6. `labels` ist eine
Abbildung von technischen Felddomänen auf Enum-Label-Abbildungen.
`capabilities` enthält deklarierte Bezeichner, keine erfolgreichen Testergebnisse.
Die gelieferten Pakete haben nur `metadata` und `labels`; `literal_rules` ist leer.
Nichtleere Regelpakete und andere Fähigkeiten werden in dieser Grundlagen-API
explizit als nicht unterstützt zurückgewiesen, nicht als geprüft ausgegeben.
Regelinterpretation und vollständige Profilkomposition gehören zum späteren
Sprachpolicy-Schritt. Das ist keine Erweiterung der Liste erlaubter Fachsprachen.

## Unabhängige Angaben

`language` beschreibt die deklarierte Inhaltssprache. Nur ein expliziter
`language_policy.default_language` kann neue Requirement-Sprache vorbelegen.
Die Anzeigesprache wird separat an `labels_for_locale` übergeben. Kein Code
liest dafür `LANG`, `LC_ALL`, eine installierte Locale oder den Inhaltstext.
`ContentLanguage` hält Sprache und Schreibrichtung als voneinander unabhängige
Deklarationen: `ltr`, `rtl` oder standardmäßig `auto`. `auto` ist eine spätere
Darstellungshilfe, kein Ergebnis einer Erkennung. Ein arabischer Tag erzwingt
nicht `rtl`; ein Mandarin-Tag liefert keine statistische Scriptdetektion.
Es wird noch kein Renderer und keine neue Kommandozeile implementiert.

## Ressourcen und Bindungen

`language_data/packages.json` beschreibt die tatsächlichen Paket-Bytehashes,
Identitäten, Versionen, Bereiche und sicheren relativen Dateinamen.
`load_bundled_package` liest genau die angeforderte Version und prüft die
Ressource gegen diese Bindung. Es gibt keinen Onlinebezug, kein Update und
keinen Import aus den Paketdaten. `packages_for_language` lädt nur passende,
explizit aktivierte Paketressourcen; das kleine Indexdokument ist vorgelagert.
Unbekannte Paketversionen werden nicht auf eine andere Version umgelenkt.
Fehlende Pakete werden als `unavailable` berichtet, nicht als Fachschemafehler.
Eine kaputte vorhandene Paketressource ist dagegen ein Integritätsfehler.

Diese API liest Distributionsdaten, keine gebundenen Projektkopien.
Projektinitialisierung, Change Plans, vollständige Sprachpolicy und ihr
semantischer Profilhash werden hier nicht vorweggenommen. Insbesondere darf
sie später nicht als stiller Ersatz für eine fehlende Projektressource dienen.

## Keine behauptete Sprachprüfung

Das Metadatenergebnis trennt `content_support=utf8`, `metadata_policy=not_evaluated`,
verfügbare Labels und `lint=not_available` / `detector=not_available`.
Diese letzten Angaben beschreiben diesen reinen Paketpfad, nicht die Fähigkeiten
eines künftig separat installierten Analyzers. Ein passendes Labelpaket ist
weder Textübersetzung noch Verifikation der Aussage gegen `normative_force`.
Fehlende Labels fallen auf den unveränderten technischen Enumwert zurück.
Kein Test vergleicht übersetzte Texte, Einrückungen oder menschenlesbare Ausgabe.

## Prüfung und Distributionsgrenze

Die strukturierten Tests behandeln Identität, Byteintegrität, unterstützte
Metadaten, fehlende Pakete, passive Daten, Locale-Unabhängigkeit sowie transportierte
Modul- und Zipapp-Ressourcen. Die ergänzte Build-Hash-Referenz zählt die neuen
Ressourcen mit; das Hashverfahren bleibt unverändert. Die Buildkennung muss sich
bei geänderten ausgelieferten Daten ändern, nicht nur bei Python-Codeänderungen.
Die erste Prüfung ändert keine Produktdateien und liefert keine Releasefreigabe.
Das SemVer-Format und Basic Matching folgen den unten genannten Primärquellen.
Die spätere vollständige Projekt-Erlaubnisprüfung wird hier nicht vorweggenommen.

- RFC 4647, §§ 2.1 und 3.3.1: https://www.rfc-editor.org/rfc/rfc4647.html
- Semantic Versioning 2.0.0: https://semver.org/spec/v2.0.0.html
- Projektvertrag: Spezifikation 0.2.7, Anhang S.3, S.4 und S.6.
