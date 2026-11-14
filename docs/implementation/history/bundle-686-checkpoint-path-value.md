# Bundle 686 — START.W-FIX1: nativen Repositorypfad lesen

Nutzerauftrag vom 14. November 2026: gezieltes Korrekturbundle nach dem
fehlgeschlagenen Betriebsstart, anschließend Übergabe und Ende des Dev-Turns.

## Belegte Ausgangsbasis

Bundle 685 ist erfolgreich: START.W wurde als
`ddc56e3b404c7f6f5c18812790847b20980310f8` nach 8.404 bestandenen Tests
committed. Result-SHA-256:
`8a1e7ac732e0fb65cb02d2fa3f0aaf6cb1be0f948a6181922f9475e2a86e472b`.
Es gibt keinen fehlgeschlagenen Apply-Rest und keinen offenen Klärungspräfix.
Der spätere explizite Control-Start pausierte dagegen mit `checkpoint_failed`;
es entstand kein neuer Automatikzyklus und kein nachfolgender Dev-Auftrag.

## Ursache und vollständige Korrektur

PatchHarbors öffentliches `api.context` liefert `RepositoryPath(value=Path)`.
Dieses Wertobjekt implementiert kein `os.PathLike`; es direkt an `Path(...)`
zu übergeben löst `TypeError` aus. Die Checkpoint-Brücke liest jetzt `.value`
und vergleicht weiterhin die aufgelösten Pfade vor jedem Snapshot.
Repo-ID-Prüfung, native Erzeugung, Ergebnisprüfung und Fehlerverträge bleiben.
Die übrigen verwendeten Rückgabefelder wurden mit dem installierten API-Code
abgeglichen; lokale Konfigurationen werden nicht in dieses Bundle übernommen.

Der vorhandene Erfolgstest verwendete versehentlich einen nackten `Path`.
Sein API-Vertragsdouble bildet jetzt das native Wertobjekt ohne `__fspath__`
ab. Die bestehenden Testidentitäten und Fremd-ID-Abnahme bleiben erhalten;
der zusätzliche Fremdpfadfall prüft, dass vor dem Snapshot abgebrochen wird
und fremde Dateien unangetastet bleiben. Dies ist eine gezielte Adapter-
regression, kein behaupteter Nachweis einer laufenden installierten Automatik.

Ein eigener Korrekturcommit `START.W-FIX1` mit `role=correction` behebt den
bereits ausgelieferten W-Stand. `correction_of` bleibt null: Das Quell-Apply
war vollständig erfolgreich, ein erfundener fehlgeschlagener Rest wäre falsch.
START.R bis MOVE.C bleiben vollständig geplant und offen; Produktfortschritt
762/918 und Spezifikations-/Katalogbindungen ändern sich nicht.

## Abnahme und Betrieb

Dev führt nur Syntax-, Collection- und native Paketprüfungen aus. Apply prüft
vor dem Commit die fällige gefilterte N=3-Gruppe plus die vollständige
Pflichtauswahl der Start-/Control-Regressionen. Deren Ergebnis ist bei der
Vorbereitung offen. Dieses Bundle installiert oder startet keinen Dienst.
Nach erfolgreichem Apply muss die getestete korrigierte Releasekopie explizit
installiert werden, bevor der vorgemerkte Neustart wieder aufgenommen wird.
Die ausführliche native Integration bleibt Teil von START.R.
