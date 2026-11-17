# Bundle 733 — Dateiscope und tatsächlicher Git-Commitumfang

Das native Result mit SHA-256
`f2b78f8f328d037f797fc25b97bb62bdcf8f6b8a9bc0fd2e709ec24bfb4523dd`
meldet für Bundle 732 einen Abbruch während der Materialisierung:
`Stage scope differs from the intended commit`. Es wurden weder das C-Testgate
gestartet noch ein Commit erzeugt. Der zuvor bestätigte R-Commit
`eb503dfc2c6b08d95aab690d216e175cf7fbd073` bleibt erhalten; bestätigt sind
788/918 Produktcommits. Der vollständige offene Rest bleibt `18.n.C`, Rolle
`implementation`, mit unveränderter ursprünglicher Commitnachricht.

Alle angekündigten Zielbytes wurden ausgebracht, einschließlich der
Importkorrektur. Die Hilfsdatei `src/specroad/proposals/_authoring_policy.py`
wurde korrekt entfernt. Sie war nur im fehlgeschlagenen C-Arbeitsstand
vorhanden, nie im erfolgreichen R-Commit. Der Apply-Treiber setzte dennoch
die gesamte Vereinigung von Payload- und Löschpfaden mit dem Git-Diff gleich.
Damit verlangte er einen Git-Löschdiff für eine Datei, die Git im Elterncommit
nicht kennt. Die ursprüngliche statische Paketrekonstruktion prüfte Dateibytes,
aber noch nicht diese Gleichsetzung mit dem tatsächlichen Commitumfang.

Der Treiber bestimmt den Git-Commitumfang nun aus allen Zielpayloads und
denjenigen gebundenen Löschpfaden, die im exakten Elterncommit vorhanden sind.
Ein nur im Index vorhandener Zugang wird vor dem Gate zusätzlich geprüft:
regulärer Dateimodus und vollständiger Indexinhalt müssen zur gebundenen
Löschvorlage passen. Seine Entfernung hebt diesen Zugang auf. Kein fremder
Indexinhalt wird still verworfen. Bereits gestagte Löschungen regulärer
Bestandsdateien bleiben Teil des erwarteten Git-Diffs.

Die übrigen Grenzen bleiben erhalten: vollständige Vorherbytes, bestätigte
Löschfähigkeit, Abwesenheit vor und nach dem Gate, exakter Index- und
Commitbaum, unveränderter Elterncommit, fremde Änderungen und sauberes Ende.
Eine reine Bereinigung nie committeter Dateien darf keinen leeren Commit
ersetzen. Die bereits erfüllte Löschung bleibt im neuen Plan mit ihrem
ursprünglichen Hash und vollständigen Vorherbytes gebunden. Der erhaltene
Snapshot ist die neue Vorherbasis; nichts wird wiederhergestellt oder
direkt in Apply geändert.

Zusätzliche Treiberregressionen verwenden kleine echte Git-Repositories und
ausdrücklich injizierte Gatefixtures. Sie prüfen untracked und gestagte
Zugänge, Fortsetzung nach fehlgeschlagenem Gate, gemischte echte Löschungen,
abweichende Indexbytes, wieder auftauchende Dateien, fremde Arbeits-/Index-
änderungen und den Ausschluss leerer Ersatzcommits. Diese Fixturebelege sind
keine echten Produkt-Gatebelege. Alle bisherigen Testdateien bleiben bytegleich;
neue Nummern werden ausschließlich hinten angehängt. Die vollständige bisherige
Pflichtauswahl wird um die neue Datei sowie die relevanten Apply-Plan-,
Lösch- und passiven Control-Regressionen ergänzt.

Die Importkorrektur und alle fachlichen Proposalbytes aus Bundle 732 bleiben
erhalten. Es gibt keine neue Spezifikationsentscheidung, keine geänderte
Freigabe und keine Budgetänderung. Das eigene C-Gate prüft die fällige gefilterte
N=3-Gruppe zusammen mit allen ungefilterten Pflichttests vor dem Commit.
789/918 und die nächste Position `18.o.W` bleiben bis dahin Zielwerte.
18.o benötigt weiterhin seine vollständige Work-/Reviewintegration; keine
neue Detailklärung oder teilweise Folgegruppe wird an diesen Rest angehängt.

Dev führt ausschließlich Syntax-, statische, reine Collection- und native
Paketprüfungen aus. Zusätzlich wird der geplante Git-Diff aus dem vollständigen
committeten Snapshot und den Zielbytes mit dem angekündigten Scope verglichen.
