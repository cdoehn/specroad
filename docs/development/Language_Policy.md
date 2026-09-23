# Sprachzulässigkeit und Paketkomposition – 4.m

`LanguagePolicy` implementiert die vollständigen Defaults und Aktionswerte aus
S.5. Fehlende Werte werden ausschließlich in einer separaten effektiven Projektion
materialisiert; `ProjectConfiguration.data` und gespeicherte Requirements bleiben
unverändert. Fehlerhafte oder unbekannte explizite Angaben sind keine Defaults.
Der Konfigurationsschemaabruf enthält denselben geschlossenen Feldvertrag.

`evaluate_language` verwendet ein ausdrücklich übergebenes, bytegebundenes
`LanguageRegistry`. Basic Filtering ist ausschließlich ASCII-case-insensitiv an
Subtaggrenzen (RFC 4647, 3.3.1). Eine leere Erlaubnisliste ist gültig und passt nie;
`*` hebt weder Register- noch Unspecified-Prüfung auf. Keine Aliasersetzung, kein
Fallback und keine Textinterpretation. `allow` erzeugt keine Diagnose. SRV177
bleibt ein harter Fehler (Code 3); SRV178/179/181 behalten ihre Policy-Schwere,
auch wenn `strict` über den bestehenden Schwellwert Code 1 erzeugt.

`language_comparison_key` ist nur die deklarierte S.5-Vergleichsprimitve, noch
kein Mischungscheck eines Containers. Private und unverifizierte Tags bleiben
auch im primary-Modus vollständig unterscheidbar. `und`, `mul`, `zxx` sind keine
konkreten Sprachschlüssel. Die eigentliche Container-/Requirementmenge folgt 4.n.

Sprachpakete werden ausdrücklich ausgewählt, alle passenden Pakete in ihrer
Aktivierungsreihenfolge. Die Paketbytes bleiben an ihre Version und SHA gebunden.
Fehlende Pakete/Prüfungen sind `not_available` (SRV182), niemals `passed`.

Die bisher leere `literal_rules`-Liste darf nun die bereits vorhandenen Daten von
`LiteralPolicy` enthalten: format_version, policy_id, version, language, fields,
term_ids, placeholders, references. Es wird kein neuer Regelausführungsmechanismus
erfunden. policy_id/version benennen die Regel, deren vollständiger kanonischer
Hash bindet die Definition. Gleiche Identitäten fallen nur bei gleicher Version
und Definition zusammen. Widersprüche erzeugen keinen Teil-Erfolg. `literal_lint`
ist ausschließlich die Capability dieses vorhandenen exakten Literalvertrags,
keine Grammatik-, Modalitäts-, Widerspruchs- oder Übersetzungsprüfung. Der Lader
führt keine Regeln aus; die spezifische Regel-Sprache und expliziten Feldselektoren
bleiben erhalten. Die vollständige Lintpipeline muss sie später auswerten.

Die vorhandene Rückweisung von Callbackdaten bleibt getestet. Der Test für
ungültige Requirement-Defaults umfasst jetzt die früher greifende geschlossene
Konfigurationsprüfung, ohne fehlerhafte Defaults zu reparieren oder zu tolerieren.

## Abnahmegrenze

Auswertung: `declared_language_only`; Paketkomposition:
`supplied_language_resources_only`. Keine CLI-Befehle, automatische Inventur,
Containerdiagnose, Analyzer-Ausführung, Schreibtransaktion oder Projektfreigabe.
Noch kein Register-Updater; ein fachlicher Registerwechsel bleibt der späteren
Change-Plan-Engine vorbehalten, keine implizite neue Distributionskopie.

Lokal je W/R/C nur ausgewählte Dateien mit vier Workern und vorgeschalteter echter
Katalogsammlung. Keine lokale Vollsuite/serielle Referenz. Bundle 017 fordert die
parallele GitHub-Vollsuite an; der nächste Dualmodus ist Bundle 020. Erfolgreiche
Teiltests oder ein Push sind keine CI- oder Releasefreigabe.

## Projektgebundene Lesebeobachtung

`effective_language_configuration` liefert eine unabhängige vollständige
Sprachpolicy-Projektion, ohne die ursprüngliche partielle Konfiguration zu ändern.
Der neue `inspect_requirement_language` prüft genau eine gespeicherte Anforderung
mit ihrem tatsächlich deklarierten Tag und der bytegebundenen Projektregisterkopie.
Ein fehlender Requirement-Tag bleibt Schemafehler; default_locale oder Policydefaults
werden nicht nachträglich in vorhandene Anforderungen eingesetzt. Die vorhandene
Fail-Policy entscheidet über den Exitcode, nicht über die gespeicherte Schwere.

Die Paketreferenzen sind ein expliziter Bibliotheksinput mit package_id, version,
language_ranges, path und sha256, kein zusätzlich erfundener persistenter Index.
Aktivierungen stammen ausschließlich aus der Projektkonfiguration. Nur passende
aktivierte Payloads werden geöffnet. Fehlende Referenzmetadaten bedeuten
`not_available`; eine bekannte ausgewählte fehlende/kaputte Datei ist ein harter
Fehler. Nichtpassende Payloads werden nicht gelesen und ausdrücklich nicht als
bytegeprüft ausgegeben. Keine vollständige Projekt-/Referenzinventur wird behauptet.

Die Originalbytes von Anforderung, Register und allen geladenen Paketen werden
vor Rückgabe erneut kontrolliert. `atomic_snapshot=false` bleibt ausdrücklich
bestehen: Beobachtungen ersetzen keine Transaktionssperre. Fehler liefern keinen
teilweise erfolgreichen Bericht. Eine neuere Distribution ersetzt niemals die
Projektregisterkopie. Die rein semantische Sprachkonfiguration bindet effektive
Policy, Registerreferenz, Aktivierungsreihenfolge und die geladenen Paketfassungen.

Der bestehende Profile-Kompositor akzeptiert die geladenen Pakete als explizite
Werte. Tests kombinieren software-de und software-en mit unterschiedlichen
Requirement-Sprachen, ohne globale Gleichheit einzuführen. LiteralPolicy-Begriffe
und deren exakte Sprache bleiben unverändert. Der Paketbericht erklärt nur die
Ressourcenverfügbarkeit, keine bereits ausgeführte oder bestandene Lintprüfung.
