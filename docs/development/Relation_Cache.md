# Optionaler Relationscache

`read_project_relation_views(source, id, cache="off"|"read",
cache_max_bytes=None)` bleibt an den vollständigen aktuellen Projektreader
gebunden. Standard ist `off`. Ein Cachetreffer ersetzt ausschließlich die
Sortierung der bereits vollständig aufgelösten Adjazenzlisten. Artefaktwerte,
Relationswerte, Identitäten und Inverssichten stammen immer aus den frisch
gelesenen Originaldateien. Vor Rückgabe prüft der Reader erneut deren Bytes
und Mitgliedschaft. Dies ist weiterhin keine atomare Mehrdatei-Snapshotgarantie.

`read` betrachtet nur die vorhandene Datei
`.specroad/cache/relation-index-v1.json`. `off`, die unabhängige Strategie `scan`
und ein Lesebudget von null öffnen diese Datei nicht. Ein bereits passender
Index im Speicher benötigt ebenfalls keinen persistenten Cache. Fehlende,
ungültige, inkompatible, unsicher erreichbare oder übergroße Einträge führen
zur vollständigen Neuberechnung. Der Reader legt keine Dateien oder Ordner an,
repariert nichts und löscht weder Cache- noch Recovery- oder Work-Daten.
Ungültige oder unlesbare Originalquellen bleiben Fehler.

Ein Eintrag bindet die aufgezeichnete Tool-Build-SHA-256 und deren Algorithmus,
Programmversion, Python-Laufzeit, Schemaversion und Relationspolicy. Die
Abhängigkeiten enthalten Projektidentität, vollständigen Konfigurationshash
und die vollständige geordnete Liste der Artefaktpfade mit ihren Inhaltshashes.
Der vollständige Build bindet auch die eingebauten Schema-/Policyimplementierungen.
Die Cache-Nutzdaten tragen zusätzlich ihren kanonischen SHA-256.
Ein unversiegelter Checkout mit `BUILD_METADATA=None` verwendet keinen
persistenten Cache; eine Versionsnummer allein ersetzt keine Buildbindung.

Selbst eine zu den aktuellen Eingaben passend behauptete Bindung mit neu
berechneter Cacheprüfsumme genügt nicht: beide Richtungstabellen müssen alle
aktuellen Quellen einschließlich isolierter Artefakte und jede aufgelöste
Relation exakt einmal enthalten. Quelle, Richtung und Sortierreihenfolge
werden gegen die aktuellen Relationswerte geprüft. Diese lineare Prüfung
vermeidet bei einem Treffer die beiden Adjazenzsortierungen. Sie umgeht keine
fachliche Quell-, Referenz- oder Kanonizitätsprüfung. Der Cache erhält keinen
Einfluss auf Modell-/Operationshashes oder auf die fachliche Resultatform.

`relation_index_cache_bytes(index)` ist ein reiner Encoder ohne Dateizugriff.
Er liefert für einen aufgezeichneten Build die Bytes eines zuvor beobachteten
`ProjectRelationIndex`, für einen unversiegelten Checkout `None`. Diese API
erteilt keine Schreibberechtigung und garantiert nicht, dass die Beobachtung
noch aktuell ist. Ein schreibender Cachebefehl wird hier nicht eingeführt.

Das optionale Lesebudget ist eine nichtnegative Bytezahl; `None` wählt das
konservative O.1-Ziel von 32 MiB. Der Adapter liest höchstens den zulässigen
beobachteten Dateiumfang in Blöcken bis 64 KiB und prüft die Dateibindung nach
dem Lesen. Das Budget betrifft ausschließlich entbehrliche Cachearbeit und
begrenzt weder normative Eingaben noch die vollständige Antwort. JSON-Decoding,
Validierung und deren Python-Objekte liegen zusätzlich im Speicher; dies ist
keine RSS-Obergrenze und noch keine Anbindung an fortsetzbare Work-Fenster.

Die W-Verhaltenstests vergleichen alle Richtungen mit dem unabhängigen Scan,
erzwingen echte Treffer ohne normale Indexneukonstruktion, prüfen rehashte
Manipulationen und binden reale verschobene Modul-/ZIP-Distributionen. Die
Unitfälle für Buildabweichungen kennzeichnen ihre aufgezeichnete Buildidentität
ausdrücklich als Fixture. Die breitere native Fehler-/Ressourcenabnahme folgt
in 6.g.R; CLI-weite Cacheintegration, andere Cachearten und die vollständige
Runtime-/Plattformabnahme bleiben offen. Es wird kein Geschwindigkeitsgewinn
oder Benchmarkstatus behauptet.
