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
ausdrücklich als Fixture. CLI-weite Cacheintegration, andere Cachearten und die vollständige
Runtime-/Plattformabnahme bleiben offen. Es wird kein Geschwindigkeitsgewinn
oder Benchmarkstatus behauptet.

6.g.R ergänzt eine günstige Strukturvorprüfung während des blockweisen Lesens.
Sie verwirft Einträge mit mehr als acht Verschachtelungsebenen oder mehr als
`256 + 32 * Quellen + 8 * Relationen` Strukturzeichen außerhalb von Strings.
Diese konservative Schranke folgt dem festen Cacheformat und der bereits
vollständig gelesenen aktuellen Eingabemenge. Sie begrenzt ausschließlich
entbehrliche Cachearbeit. Stringgrenzen und Escapes bleiben über kurze native
Lesezugriffe hinweg erhalten; der strikte JSON-Decoder prüft weiterhin die
vollständige Syntax einschließlich doppelter Schlüssel und ungültiger Zahlen.
Originaleingaben und vollständige Antworten werden dabei nicht eingeschränkt.

Der Bytepuffer wächst mit den tatsächlich gelesenen Daten. Ein Dateiumfang löst
keine gleich große Voraballokation aus; ein kurzer Read erzeugt keinen dauerhaft
separat gespeicherten Teilpuffer. Der R-Nachweis liest einen echten 160-KiB-Eintrag
in Ein-Byte-Reads und misst ausschließlich diesen Python-Allokationsabschnitt
mit `tracemalloc` unter 1 MiB. Das ist keine Aussage über Gesamt-RSS, Hostquota,
Quellladen oder JSON-Objekte. Diese Grenzen aus W bleiben bestehen.

Die R-Fälle prüfen echte kurze Reads, exakte Bytebudgets, ungültige UTF-8-/JSON-
Werte, zu tiefe/breite Strukturen vor Decoding, ersetzte oder entfernte Cachedateien
und Änderungen bei gleicher Größe/mtime. Cachefehler schließen eigene Deskriptoren,
verwerfen den Eintrag ohne Retry oder Reparatur und berechnen aus Originaldaten
neu. Ein währenddessen verändertes Original bleibt ein Fehler. Programmierfehler
und Unterbrechungen werden nicht als Cachemiss verschluckt.

Isolierte Prozesse belegen echte `EACCES`- und `EMFILE`-Fälle. Eine gesonderte,
ausdrücklich injizierte Allokationsfunktion versucht unter einer echten
Adressraumgrenze eine unzulässige große Allokation; deren `MemoryError` führt
nach Wiederherstellung der Prozessgrenze zur vollständigen Neuberechnung.
Dies behauptet keinen Mindest-RAM-Bedarf des tatsächlichen Cacheinitialisierers.
Weitere gezielt injizierte Fehler bleiben als solche gekennzeichnet. Die
Read-only-Nachweise fangen Schreibversuche ab und vergleichen vorhandene Bytes,
Dateimodi und Einträge.

6.g.C trennt Cacheformat, Bindungsprojektion, Encoder und inkrementelle
Strukturvorprüfung in `storage._relation_cache_values` vom nativen Adapter
`storage._relation_cache`. Die bisherigen internen Importnamen bleiben dort
als Aliase verfügbar. Guarded Open, Leseaufrufe, Pufferallokation, striktes
Decoding und die optionale Fehlergrenze behalten ihren bisherigen Aufrufpfad.
Der verbindliche Projektreader und die vollständige Adjazenzprüfung ändern
sich nicht. Alle 79 W-/R-Verhaltenstests bleiben unverändert.
