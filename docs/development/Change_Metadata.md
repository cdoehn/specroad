# Gebundene Metadatenpolicy

`prepare_change_metadata` ist eine reine, explizit aufgerufene Umsetzung von
Anhang K.2 nach der geordneten Faltung. Policy, Actor, Planungszeit und die
konkreten IDs stammen aus den Eingaben, niemals aus Uhr, Anmeldung oder Zufall.
Der Aufrufer muss Eingaben während ihrer Übernahme stabil halten.

Bestehende, im Endergebnis geänderte Artefakte erhalten einmal `base.revision+1`,
`updated_by=actor` und `updated_at=max(planned_at, base.updated_at+1µs)`.
Erstellungsangaben bleiben unverändert. Regulär neu erzeugte Identitäten erhalten
Revision 1 und beide Zeit-/Akteursangaben aus dem gebundenen Plan. Ein Create mit
anschließenden Updates erzeugt ebenfalls nur Revision 1. Der Aufrufer kann die
Kandidaten danach in einen Change Plan aufnehmen, einschließlich ihrer Hashes.

Leere Pläne, echte No-ops und vollständig rückgängig gemachte Zwischenänderungen
stempeln nichts neu. Alle gespeicherten Werte bleiben erhalten. Geänderte
Relationslisten betreffen nur ihr Quellartefakt. Planweite Vorbedingungen gelten
für die Basis; Operationsvorbedingungen gelten für den jeweiligen vorläufigen,
noch ungestempelten Zwischenstand.

UTC-Bruchteile werden als Ziffernfolgen berechnet. Es gibt keine Rundung auf
Binary64 oder die sechs Nachkommastellen von datetime. Die Schreibweise von
`planned_at` bleibt erhalten, wenn dieser Wert das Maximum ist. Ein berechneter
Nachfolger verwendet großes T/Z und die benötigten Nachkommastellen. Die
bestehende UTC-Syntaxprüfung wird übernommen, einschließlich ihrer ausdrücklichen
Grenze: explizite Schaltsekundenangaben werden nicht gegen ein externes Register
beglaubigt. Nicht darstellbare Zeit- oder Revisionsnachfolger führen zum Fehler.

Das Ergebnis heißt `regular_metadata_candidates_only`. Es setzt
`metadata_applied=true`, jedoch `lifecycle_checked=false`,
`expected_result_root_verified=false`, `project_complete=false`,
`execution_ready=false` und `write_authorized=false`. Ein Array-Inhaltshash ist
nicht die spätere Projektmodellwurzel. Ein Actor-Objekt ist keine Authentifizierung.

Ausführbar sind die vier bereits vorhandenen normalen Faltoperationen. Die
acht spezialisierten Familien einschließlich representation_normalize brauchen
weiterhin ihre jeweiligen Planner. Die bestehende Repräsentationsnormalisierung
bleibt wert- und metadatenneutral. Spezialartefakte dürfen über diese normale
Metadatenpolicy nicht geändert werden. Merge- und Migrationskennungen werden
abgewiesen statt historische Revisionen als reguläre Neuanlage zu behandeln.

Wiederholte Vorbereitung gegen dieselbe Basis liefert dieselben Resultate,
auch bei anderer Laufzeit, Locale oder Decimal-Konfiguration. Das ist keine
Replay-Freigabe: erneut gegen das bereits geänderte Live-Modell anzuwenden
unterliegt weiterhin den ursprünglichen Vorbedingungen.

Lokal nur die neuen, direkt betroffenen Testdateien, vier xdist-Worker.
Vollständige Suite und Fünferzyklus bleiben in GitHub. Keine Tests auf
Darstellung oder Dokumentation und keine neue Core-/Entwicklungsabhängigkeit.

## R: Gespeicherte Pläne und ursprüngliche Ressourcen

`prepare_plan_metadata` prüft einen bereits selbstgehashten `ChangePlan` erneut
gegen die ausdrücklich gelieferten Basiswurzel- und Scopebeobachtungen. Danach
vergleicht es die gesamten resultierenden Artefaktwerte einschließlich Revision,
Zeit und Actor mit den deklarierten Ressourcenhashes. Falsche Metadaten ergeben
`SRV174`, keinen teilweise erfolgreichen Plan. Bei Übereinstimmung wird
`declared_artifacts_verified=true`; die vollständige Zielwurzel und Lifecycle-
Nachbedingungen bleiben ausdrücklich ungeprüft. Der gespeicherte Plan und seine
Originalbytes ändern sich niemals durch diese Prüfung.

`prepare_change_metadata_bytes` nimmt ausschließlich bereits gelesene Bytes an,
keine Dateinamen. Die originale Repräsentation wird bei berührten Artefakten
separat erhalten, auch bei wirkungslosen Operationen. Fehler in einem einzigen
Eingabedokument verhindern den gesamten vorbereiteten Rückgabewert. Unveränderte
historische Spezialartefakte bleiben im Bestand; ihre Änderung braucht weiterhin
einen zuständigen Fachplanner und ist in der normalen Metadatenpolicy verboten.

W/R-Funktionsgrenze: die vier normalen Faltoperationen und die reine K.2-Policy.
Vollständige Merge-/Migrationspläne, Spezialworkflows und Bytepublikation sind
nicht enthalten. Anforderungsnachweise bleiben daher partial, nicht passed.

## C: Explizite Policy-Schnittstelle

Die reguläre Policy ist als feste, interne Strategie von der Ergebnismaterialisierung
getrennt. Eingaben liefern nur eine bekannte Versionskennung und gebundene Daten,
keinen Funktionsnamen, Importpfad oder Callback. Unbekannte, Merge- und Migrations-
kennungen bleiben abgewiesen. Spätere Strategien benötigen ihre eigenen gebundenen
Historieneingaben und dürfen nicht still die K.2-Regeln wiederverwenden.
Die öffentlichen Funktionssignaturen und alle W-/R-Verhaltenstests bleiben erhalten.
