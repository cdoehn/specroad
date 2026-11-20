# Bundle 766 — Scorekorrektur und Sprachvergleich

20. November 2026. Maßgeblich ist das native Fehler-Result mit SHA-256
`a556dcb0ce1a3da871562c3de198cb6ab53c9cf943e53d1e4982f985fa049cb3`.
Bundle 765 hat 19.o.W/R/C und 19.p.W erfolgreich geprüft und committed:
9098, 9184, 9254 und 9163 bestandene Tests in den jeweiligen Gates.
Bestätigter HEAD: `5337287ac49aa3888faea22e7668845ddb336158`, **847/918**.
19.p.R scheiterte mit sechs Fehlern und 9212 bestandenen Tests. Sein
ausgebrachter Stand blieb erhalten und ist die vollständige Korrekturbasis.
Die nativen Basis-/Effektivsnapshots stimmen byte- und modusgleich mit den
angekündigten Ständen 19.p.W beziehungsweise 19.p.R überein.

## Vollständiger offener Rest und belegte Fehlerursache

19.p.R und 19.p.C bleiben mit ihren ursprünglichen IDs, Nachrichten und Rollen
`implementation` der exakte Korrekturpräfix. Die vier erfolgreichen Commits
werden nicht wiederholt. Anschließend folgt die bereits geplante vollständige
Gruppe 19.q.W/R/C; sie erweitert die Korrekturbindung nicht um neue alte IDs.
Kein Klärungspräfix und keine neue normative Detailentscheidung sind notwendig.

Die fünf tatsächlichen CPython-Integrationen 3.10 bis 3.14 scheiterten am
Vergleich der publizierten Scores. Die alte R-Summenprüfung berücksichtigte nur
die zwölfstellige Dezimalquantisierung. Das gebundene Original normalisiert
jedoch zuvor in binary32. Der statisch geprüfte Originalwheel-Hash lautet
`c25bd038147951ba3a89efe9ec12cc7d2116cb6f311ff8af84ade398a8bc0616`.
`py3langid/langid.py::_decide` berechnet exp, positive Summe und Division in
diesem Format und faltet danach Alias-Spalten. Das hashgeprüfte Modell hat
142 Spalten und 140 eindeutige Codes; `sr` und `uz` kommen jeweils zweimal
vor. Diese Aussagen stammen aus Originalquelltext und statisch gelesenen
NPY-Metadaten, nicht aus einem erfundenen Dev-Testlauf.

Die Korrektur berücksichtigt die unvermeidbare Arithmetik des fest gebundenen
Backends, ohne einen einzigen Score zu ersetzen oder nachzunormalisieren.
Mit binary32-Einheitsrundung u=2^-24 hat eine positive Reduktion aus
142 Spalten höchstens 141 Rundungsstufen. Division und höchstens eine
Aliasaddition je ausgegebener Zeile liefern zusammen 143. Für die positive
Gesamtsumme begrenzen (1-u)^143 und dessen Kehrwert die kumulierten Faktoren;
Bernoullis Ungleichung ergibt die konservative Schranke
gamma_143=143/(2^24-143). Hinzu kommen eine halbe publizierte Dezimaleinheit
je Zeile und eine Einheit für die wesentlich kleineren Subnormalfehler.
Der Vergleich geschieht ausschließlich mit Integern. Das ist eine aus der
Implementierung abgeleitete Rundungsgrenze, keine empirische Konfidenztoleranz.
Alle Nullsummen, grob falschen Summen, nichtendlichen Werte, Bereichsfehler,
Duplikate und ungültigen Labels bleiben Fehler. Die bisherigen Schwellen,
Half-even-Quantisierung, Gleichstandsordnung und Abstentionspriorität bleiben.

Der sechste Fehler war ein falsches Testorakel: Der erste Eintrag des
Modellverzeichnisses (`af`) ist nicht der alphabetisch kleinste Code (`ace`).
Das vollständige Ranking einschließlich eines letzten Spitzenkandidaten
wird weiter geprüft; das Orakel bestimmt den zweiten Code nun unabhängig
aus der alphabetischen Ordnung der übrigen Kandidaten.

Neue Regressionen binden positive und negative binary32-Restfehler bei
Dritteln, ein vollständiges uniformes 140er-Ranking und weiterhin ungültige
Gesamtsummen außerhalb der Rundungsgrenze. Die fünf Originalruntimefälle
bleiben vollständig verpflichtend, einschließlich aller 140 Originalscores,
Ausfallmodi, Versions-/Modellbindungen und verbotener Filter. Keine alte
Assertion wird entfernt oder abgeschwächt. C übernimmt die korrigierten
R-Testbytes unverändert und verschiebt die reine numerische Funktion unter
Erhalt ihrer AST in den bereits vorgesehenen Zahlenhelfer.

## 19.q.W/R/C — Vergleich ohne erfundene Präzision

W implementiert `language-comparison-v1` auf einer entschiedenen Beobachtung
und einem ausdrücklich übergebenen nativen Registry-Snapshot. Gleiche bekannte
Primärcodes sind `compatible`. Ausschließlich declared primary `cmn` und
detected `zh` sind `compatible_coarse` mit `macrolanguage_only`; daraus wird
keine Mandarinbestätigung. Andere vergleichbare bekannte Codes sind
`mismatch`. Private, unbekannte und unspezifische Tags bleiben `unverifiable`.
Nichtentscheidungen werden nicht in Treffer oder Fehlkennzeichnungen verwandelt.
Region und Script werden ausdrücklich nicht als geprüft ausgewiesen.
Originaldeklaration und tatsächliche Registry-Version/Hash bleiben erhalten.
Sprachzulässigkeit, Preferred-Value-Umschreibung und automatische Korrekturen
sind nicht Teil des Vergleichs; die bestehende Erlaubnisliste bleibt getrennt.

R verbindet den Vergleich vollständig und stabil sortiert mit den vorhandenen
Subjectentscheidungen und ihrem unveränderlichen Request. Analyse-ID, Snapshot,
Descriptor, vorbereitete Policy, vollständige Subjectmenge und Werthashes müssen
passen. Andere, doppelte oder fehlende Subjects ergeben keinen Teil-Erfolg.
Originaldeklarationen einschließlich en-US/en-IN und chinesischer Varianten
sowie normative_force werden unverändert weitergegeben. Das Backend wird beim
Vergleich nicht erneut geladen. Unknown/private Präzision, Registrywechsel,
falsche Entscheidungstypen und fremde Bindungen erhalten eigene Negativfälle.
Die Originalruntime-Matrix prüft den Vergleich zusätzlich auf echten
Detektorentscheidungen, ab R auch die vollständige Subjectzuordnung.

C trennt unveränderliche Vergleichswerte von Vergleichs- und Zuordnungslogik.
Alle verschobenen Definitionen, Funktions-ASTs und R-Testbytes bleiben gleich.
Es entsteht kein neuer CLI-/Worker-/Wire-Vertrag. Endgültige Berichte,
Policy-/Exitaggregation, vollständiger Enginefingerprint, menschlich geprüfter
Korpus und Releasefreigabe bleiben in den folgenden Planschritten offen.

## Übergabe und Nachweisgrenze

Dev hat keine Testkörper, Fixtures oder Test-Unterprozesse ausgeführt.
Statische Syntax-/Lint-/Strukturprüfung, reine Collection und passive native
Bundleprüfung sind keine Verhaltensabnahme. Jede Stage wird einzeln ausgebracht,
mit ihrer fälligen gefilterten N=3-Gruppe plus ungefilterter Pflichtauswahl
geprüft und erst danach committed. Erst danach folgt die nächste Stage.

| Stage | Ziel nach eigenem erfolgreichem Gate und Commit |
| --- | --- |
| 19.p.R | 848/918 |
| 19.p.C | 849/918 |
| 19.q.W | 850/918 |
| 19.q.R | 851/918 |
| 19.q.C | 852/918 |

Danach folgt 19.r.W. Spezifikation 0.2.99, SPECROAD-DECISION-1,
Entwicklungsvertrag und Budget bleiben unverändert. Historische Berichte,
insbesondere die nun widerlegte Rundungsannahme in Bundle 765, bleiben als
Originalnachweise erhalten; diese Korrektur stellt ihren Fehler ausdrücklich klar.
