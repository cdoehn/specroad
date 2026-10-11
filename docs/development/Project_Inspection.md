# Projektinspektion

`specroad project inspect --project PATH --format json` beschreibt das tatsächlich
gelesene Projekt. Ohne `--project` gilt die bestehende Projektsuche. Wiederholtes
`--profile` wählt die explizite Profilfolge; Core bleibt zuerst. Die Python-API
ist `specroad.authoring.project_inspection.inspect_project`.

Der Envelope bleibt Version 2.0.0. Sein Payload `project-inspect-v1` enthält
exakt `format_version: "1.0.0"`, `semantic` und `runtime`. Projektidentität,
Modellwurzel, Schema, effektive Profile, Artefaktzahlen, Migrationsbedarf,
Diagnosezahlen und Hauptdokumente stammen aus den aktuellen Eingabebytes.
Nicht vorkommende Artefakttypen fehlen in der sortierten Zählung. Hauptdokumente
sind ausschließlich Dokumente mit `document_role: primary_specification`.

Der Reader inventarisiert die konfigurierten normativen JSON-Bäume, bindet
Registry, Profile, aktivierte Sprachpakete und referenzierte Anhänge und prüft
Inventur und gelesene Bytes vor der Ausgabe erneut. Fehlende Ressourcen werden
nicht durch Distributionsressourcen ersetzt. Die Prüfung schreibt keine Datei,
erwirbt keinen Lock und führt keine Recovery aus. Sie ist keine atomare
Lesegarantie gegenüber nicht kooperierenden Schreibern.

Runtime-Metadaten stammen aus den bestehenden operativen Readern und der nativen
Linux-Lockbeobachtung. Ein lebender Writer liefert Konfliktstatus 6; offene
Journale oder unbekannte operative Einträge blockieren mit Status 5. Dabei
bleiben die semantischen Angaben unbekannt (`null`). Nicht lesbare Metadaten
werden mit `observation_status: unknown` markiert, niemals als fehlender Lock
oder als fehlende Transaktion ausgegeben. Andere Plattformen bleiben bis zur
Implementierung ihrer sicheren Beobachter ausdrücklich ohne Vollnachweis.

Die vorhandene Validierung liefert die fachlichen Diagnosen. Fehlt ein
erforderlicher Spezialdienst, bleiben tatsächlich gelesene Modellangaben
sichtbar, aber `diagnostic_summary` ist `null`, `summary.complete` ist falsch und
der Aufruf scheitert entsprechend. Das betrifft derzeit insbesondere auch das
Hauptdokument eines frisch initialisierten Projekts. Es gibt keinen Ersatzdienst,
der pauschal Erfolg meldet. Vertrauenswürdige Python-Hosts können vorhandene
`ModelGate`-Dienste ausdrücklich bereitstellen. Eine vollständige Inspektion
erteilt keine Modell-, Schreib- oder Releasefreigabe.

Nur das geladene Schema 0.2.0 belegt aktuell `migration_needed: false`.
Unbekannte/ältere Schemata werden abgelehnt; aus ihnen wird weder eine
Migrationsmöglichkeit noch ein falscher Boolean abgeleitet. Ungültige Konfiguration
oder Projektauswahl kann bereits vor dem Handler im bestehenden CLI-Preflight
scheitern. Weitergehende Migrations- und Spezialdienstintegration bleibt offen.

Für Vergleiche gelten ausschließlich RFC-8785-Bytes von
`{format_version, semantic}`. Absolute Roots, Writer-/Transaktionsmetadaten,
Runtimefehler und äußerer Envelope gehören nicht zu dieser Gleichheitsgarantie.
