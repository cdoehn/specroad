# Bundle 713 — Trace-Sperrvertrag und vollständiger Rest 18.u.R/C

Datum: 16. November 2026. Ausschließliche Grundlage ist Result
`specroad-apply_Result_023002_1116_d9010d.zip`, SHA-256
`d77ed9c306832caf2f1358e84c3b99c83547c2035cfc4cd77133534c3d0d0b31`,
Basiscommit `1083d8392ae654ee7e7b550db25d5879766dbfdd`, Fingerprint
`5fde211274f41f73` nach `patchharbor-state-v1`, Repository
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`.

## Belegter Fehler und Korrektur

Bundle 712 hat 18.u.R ausgeführt: 15.507 Tests bestanden, ein Test scheiterte.
Kein neuer Commit entstand; 18.u.C wurde noch nicht installiert. Der bestätigte
Planstand bleibt 769/918 mit dem zuvor erfolgreich committeden 18.u.W.
Die originale R-Beobachtung hat SHA-256
`c412a6c287d50a0278ac232be423a3718ce29823b17e2c133ee4108e9f8c1728`.
Sie enthält 15.508 eindeutige Testausgänge und genau diesen fehlgeschlagenen Test:
`tests/test_query_trace.py::test_writer_and_unresolved_journal_block_before_model_loading`.
Der unveränderte native Hostprüfer meldet `Failed or unresolved copy outcome`;
die Hostfehlerliste selbst ist leer. Das fehlgeschlagene Gate bleibt fehlgeschlagen.

Der Test erwartet für einen nachweislich aktiven Writer noch Exitcode 5.
Die native Trace-Implementierung liefert bereits den in Anhang C.3/N.3
verlangten Konfliktcode 6. Der andere Fall derselben Testfunktion, eine
ungelöste Transaktion, muss dagegen weiterhin Code 5 und Korruption melden.
Die verwandten Why-/Impact-Sperrtests unterscheiden diese beiden Zustände
bereits. Native Mutex-Fehler der direkten Schreibadapter sind andere Prüfpfade
und werden nicht pauschal umklassifiziert.

Die Korrektur erhält beide Fälle und prüft nun jeden über Bibliotheksaufruf,
öffentliche CLI und strukturierten Request. Die Ergebnisse müssen 6/Writer
beziehungsweise 5/Korruption eindeutig unterscheiden. Die strukturierten
Vorprüfungsdaten müssen den Zustand und Grund, das unverändert verweigerte
Schreibrecht sowie den nicht begonnenen normalen Zugriff belegen. Beim aktiven
Writer darf weder Korruption noch eine Git-Wiederherstellung behauptet werden;
beim ungelösten Journal bleiben beide Diagnoseflags gesetzt. Modellzugriff,
Schreib-/Prozessversuche und jede Änderung der Originalbytes bleiben verboten.
Die ursprüngliche Writersperre muss nach den lesenden Aufrufen noch gelten.

Es entsteht keine neue Produktregel: Spezifikation, Entwicklungskontrakt und
aktive Katalogbindungen bleiben unverändert. Kein Produktfehler wird durch
Herabsetzen einer richtigen Sperre verdeckt, kein Test entfernt oder übersprungen.
Die vorhandene Testidentität, ihre Nummer und alle bisherigen Fälle bleiben.

## Vollständige Fortsetzung und Abnahme

`correction_of` bindet den vorherigen Plan
`9195ddf613d3cc2dd868933f4a38c75a7063e7cc19efaad78b47ba83ee768798`
und exakt seinen vollständigen offenen Rest `18.u.R`, `18.u.C`, jeweils Rolle
`implementation`. Sämtliche 32 erhaltenen Dirty-Dateien aus dem Result gehören
zur neuen Vorherbindung. Bereits erfolgreiche Commits werden nicht wiederholt.
C behält die vorbereitete strukturelle Konsolidierung und übernimmt die
korrigierten R-Testbytes unverändert. Es gibt keinen leeren Korrekturcommit.

Alle bisherigen R/C-Pflichten einschließlich der vollständigen Trace-, Query-,
Export-, Bundle-, Retry-, Receipt-, Sperr- und Hostnachweisfamilien bleiben in
beiden Gates verpflichtend. Die ausgewählten Tests werden erst in Apply
zusammen mit der fälligen gefilterten N=3-Gruppe ausgeführt, jeweils einmal vor
dem zugehörigen Commit. Kein Endstand wird vorab installiert. Nach erfolgreichen
R/C-Gates ist das Ziel 771/918; 18.v.W/R/C und danach 18.w.W/R/C bleiben die
anschließende priorisierte Planfolge. Keine offene R/C-Arbeit wird verschoben.

Dev beschränkt sich auf statische Prüfung, reine Collection und native Paket-/
Fortsetzungsvalidierung; es führt keine Testkörper, Fixtures oder Testprozesse aus.
Ein vorbereiteter Zustand ist keine Verhaltensabnahme. Keine neue Klärung,
Budgetänderung, lokale Konfiguration oder Sessiondaten gelangen in die Payload.

Vorbereiteter Zustand **18.u.R**: Ziel nach eigenem Gate **770/918**, danach **18.u.C**.
