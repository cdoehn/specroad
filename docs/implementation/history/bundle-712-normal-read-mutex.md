# Bundle 712 — Lesende Mutex-Prüfung und vollständiger Rest 18.u.R/C

Datum: 16. November 2026. Ausschließliche Grundlage ist das native Result
`specroad-apply_Result_234832_1115_c4b991.zip`, SHA-256
`f119986af9bc6fd5a5985a78bb58f7a3e270f11d25b2f3f948cb031fc3bbed8c`,
Basiscommit `1083d8392ae654ee7e7b550db25d5879766dbfdd`, Fingerprint
`437a49ff846211f4` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

## Belegter Stand

Bundle 711 hat 18.u.W nach einem erfolgreichen eigenen Gate mit 14.366 Tests
committed. Der bestätigte Planstand ist damit 769/918. Die originale
W-Beobachtung hat SHA-256
`c9096767274eb5f4d2d703c50b7b78aaeb4bff4f916d60aafb2fe921a5eccb62`;
ihr Hostnachweis besteht die unveränderte native Prüfung.

18.u.R ist dagegen fehlgeschlagen: Das Ausführungslog meldet 79 Fehler und
14.619 bestandene Versuche. Die Versuchszahlen einschließlich Untertests sind
kein erfolgreicher Gateabschluss. Die R-Beobachtung hat SHA-256
`8911b272bb4cd111ae27ee19cf528fee4c4559cf53a3a0b4316f5b01e3ed6dd2`;
der native Hostprüfer verweigert sie mit `Failed or unresolved copy outcome`.
Die Hostfehlerliste selbst ist leer. Keine Nachweise werden nachträglich
umgeschrieben oder als erfolgreich ausgegeben. C wurde noch nicht installiert.

`correction_of` bindet den ursprünglichen Plan
`7fda087101d42842f2f169ce9db520aacc4a630b0e5943060cfd73e8b2d12ca8`
und exakt seinen offenen Rest `18.u.R`, `18.u.C`. Beide behalten ihre Rolle
`implementation`. Der bereits erfolgreiche W-Commit wird nicht wiederholt.
Die vollständigen 22 erhaltenen R-Dateien sind Teil der neuen Vorherbindung;
die bestehende C-Konsolidierung wird auf den korrigierten R-Stand übertragen.

## Ursache und Korrektur

62 Fehlermeldungen betreffen erzeugte Export- oder Bundle-Dateien. Bei Ausgabe
im Quellroot hält die Publikation bereits dessen tatsächlichen exklusiven
Verzeichnismutex. Die verschärfte normale Vorprüfung erkennt diesen bei ihren
Quellnachprüfungen als unbekannten fremden Writer. Die Korrektur reicht nur für
denselben Root die vorhandene native Mutex-Fähigkeit in den bereits vorhandenen
lesenden Prüfkontext. Rootidentität, Eigentümer, Marker, Journal, Quellbytes und
Ausgabeziele werden weiterhin geprüft. Eine fremde oder abgelaufene Fähigkeit
ist unzulässig. Bei externer Ausgabe gilt deren Mutex nicht für das Quellprojekt.
Ausnahmen verlassen den Kontext vor Freigabe des Mutex; kein persistenter
Writerbeleg, keine Recovery und keine zusätzliche Schreibbefugnis entstehen.

Vier Fehler betreffen rein lesende öffentliche Aufrufe: Deren Vorprüfung
forderte selbst einen exklusiven Schreibmutex an. Sie beobachtet nun den
vorhandenen Rootdeskriptor mit einer nicht blockierenden geteilten Sperre.
Gleichzeitige Leser dürfen koexistieren, ein echter exklusiver Writer bleibt
erkennbar. Die kurze Beobachtung erteilt keine spätere Zugangs- oder
Schreibgarantie. Kein Ownerdatensatz wird erzeugt; `held` wird nicht gesetzt.
Ein eigener exklusiver oder geerbter Handle wird weder herabgestuft noch
entsperrt; verschachtelte Beobachtung und Aufwertung zum Writer sind gesperrt.
Auch bei Ausnahmen wird nur die selbst erworbene Lesesperre freigegeben.

Zwölf Fehler entstehen vor Ausführung der neuen Retry-/Receipt-Fälle: Die
native Projektfixture erwartet einen noch nicht vorhandenen Root. Beide
betroffenen Testfunktionen erhalten deshalb einen eigenen Unterordner unter
dem vorhandenen temporären Testverzeichnis. Die acht echten Domänen-Replays
und vier beschädigten Receipt-Fälle behalten ihren gesamten fachlichen Umfang,
ihre Identitäten, Originalbyte- und Keine-zweite-Revision-Nachweise.

Ein bestehender Artifact-show-Test erwartet für einen aktiven Writer noch
Exitcode 5. Gemäß dem bereits geltenden Anhang C.3/N.3 ist dies Konflikt 6.
Der Test prüft zusätzlich die strukturierte aktive-Writer-Diagnose, fehlende
Korruption und den ausgebliebenen normalen Modellzugriff. Keine neue
Spezifikationsentscheidung, Klärung oder Budgetänderung ist erforderlich.

## Abnahme und vollständige Fortsetzung

Vorhandene native Mutex-Tests prüfen zusätzlich parallele Leser, verweigerte
Schreibautorität, den blockierten exklusiven Konkurrenten sowie Freigabe nach
normaler und fehlgeschlagener Beobachtung. Tests aller öffentlichen Leser
behalten ihre Schreib-/Prozess-/Entropyfallen und prüfen auch, dass die echte
flock-Ausführung keine exklusive Sperre anfordert. Die bestehenden Nachweise
für unbekannte Eigentümer, nackten Mutex, Unterbrechungsmarker, fremde Roots,
veraltete Fähigkeiten, geänderte Quellen und erhaltene Ausgabebilder bleiben.

Alle ursprünglich angekündigten R/C-Pflichttests und geänderten Testdateien
bleiben verpflichtend. Die gesamten betroffenen Export-, Project-/Partial-
Bundle-, Receipt-, Query-/Why-/Impact-, Schema-/Description-, Sperr- und
Preflight-Familien werden zusätzlich gebunden. Die stabile Identitätszuordnung
und die vorhandenen Testnummern bleiben unverändert. Host-, MOVE-, Kopien- und
Laufzeitnachweisprüfer werden nicht geändert und Fehler nicht ausgeblendet.
C übernimmt die R-Testbytes unverändert und bereinigt weiterhin nur Struktur.

Beide Zustände erhalten jeweils genau ihr eigenes gefiltertes N=3-Gate plus
ungefilterte Pflichtauswahl vor dem Commit. Zielwerte 770/918 und 771/918 sind
vorbereitete Zustände, keine bereits erreichten Abnahmen. Der anschließende
geplante Ausschnitt bleibt 18.v.W/R/C (Migration, Merge und Rooterzeugung),
danach 18.w.W/R/C. Keine offenen R/C-Arbeiten werden in diesen Folgeausschnitt
verschoben; dieses Bundle liefert den vollständigen belegten Korrekturrest.

In Dev erfolgen nur Syntaxprüfung, reine Collection und native Artefakt- und
Fortsetzungsvalidierung. Keine Testkörper, Fixtures oder Test-Unterprozesse
laufen hier. Verhaltensabnahme bleibt Apply vorbehalten. Lokale Konfigurationen,
Zugangsdaten und Sessiondaten gehören nicht zur Produkt-Payload.

Vorbereiteter Zustand **18.u.R**: Ziel nach eigenem Gate **770/918**, danach **18.u.C**.
