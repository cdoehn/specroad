# Gebundene Authoring-Vorschau und native Planausführung

`specroad.authoring.plans.preview_authoring_request` erzeugt aus einem übergebenen
`TargetModel` und genau einer vorbereiteten Operation einen vollständigen
speicherbaren Change Plan. Unterstützt sind `artifact.create`, `artifact.update`,
`lifecycle.transition` (Transition und Retirement), `relation.add`,
`relation.remove` und `relation.review` (confirmed/rejected mit den gebundenen
Rücknahmen). Alle sechs bisherigen nativen Fachadapter verwenden dieselbe
Planvorbereitung. Ihre bisherigen Ergebnisformen bleiben erhalten.

Der Aufrufer liefert normalisierte Operationswerte, IDs, Actor, Zeitpunkt und
Plan-/Request-ID. Die Vorschau vergibt und reserviert keine Identität, nimmt
keinen Writer-Lock, ruft keine Write-Autorisierung auf und verändert weder
Projektdateien noch `.specroad/`. Unvollständige oder ungültige Ziele bleiben
als solche erkennbar. `fail_on_change` liefert bei einem gültigen geänderten Ziel
Code 1, bei einem gültigen No-op Code 0. Das ist kein ausgeführter Write.

Der Bericht enthält `plan`, `plan_sha256`, vollständige Zielbewertung,
semantischen Diff, Impact, Diagnosen und erwartete Modellwurzel. `audit` bindet
Befehlsklasse, Actor, Request, Plan, Operationsgründe, Zeitpunkt, Basis/Ziel und
prospektive IDs. Aus `plan` kann ein `ChangePlan` gespeichert und später gelesen
werden. Die Vorschau allein verleiht weder Schreibrecht noch fachliche Freigabe.

`specroad.authoring.execution.apply_authoring_plan` führt diesen gespeicherten
Plan aus. Die Befehlsklasse wird vom Host explizit ausgewählt und gegen die eine
Operationsfamilie geprüft; Planinhalte registrieren keinen ausführbaren Code.
Der Dienst allokiert keine neuen IDs und plant nicht still neu. Er verwendet
native Authoringpolicy, aktuelle Eingabeprüfung, vollständige Zielgates,
Writer-Lock, Hostautorisierung, Journal, Staging, Veröffentlichung, Receipt und
Cleanup. Ein No-op wird unter Lock frisch autorisiert und erzeugt kein Receipt.
Fehler bleiben Fehler des bestehenden Protokolls; erreichte Zustände und
Recoverybelege werden erhalten.

`execute_authoring_plan` verwendet denselben nativen Pfad und liefert für
erwartete Modell-, Sicherheits- und I/O-Fehler einen maschinenlesbaren
Fehlerbericht. Die bisherige werfende API bleibt erhalten. Der Fehleraudit
bezeichnet den versuchten Plan (`audit_scope=failed_plan_attempt`); prospektive
IDs und Zielwurzel heißen ausdrücklich `planned_created_ids` und
`expected_model_root_sha256`. Es gibt dabei keinen erfundenen Abschlussbeleg,
keine behauptete aktuelle Zielprüfung und keine automatische Wiederholung oder
Rücknahme. Ein vorhandener nativer Schreib-/Recoveryzustand wird übernommen;
ohne eindeutigen Nachweis bleibt der Schreibzustand `unknown`. Eine erfolgreiche
Planintegritätsprüfung bestätigt nur Schema und Hash, keine Autorisierung.
Unklassifizierte OS-Fehler geben keine rohen Fehlermeldungen mit Nutzdaten aus.

Die vom Host gelieferte Gateauswahl wird vor externen Source-/Receiptzugriffen
übernommen. Das spätere Verändern der ursprünglichen Liste kann eine anfangs
erforderliche Verweigerung nicht entfernen. Gültige gespeicherte Plandaten
ersetzen weder die Hostgates noch die frische Schreibautorisierung.

Eine bestätigte Request-Wiederholung wird vor neuer Zielprüfung und Lock
aufgelöst. Der Auditbericht verwendet die ursprünglichen Plan-, Actor-, Zeit-,
Operations- und Wurzelwerte aus dem vollständig geprüften Abschlussbeleg.
`current_target_verified=false` unterscheidet historischen Erfolg von einer
neuen Prüfung des heutigen Projekts. Eine verlorene Ausgabe erzeugt keine
zweite Revision oder Identität. Lokale Hashkonsistenz authentifiziert weder
Personen noch die historische Vollständigkeit des vom Host gelieferten Modells.

Der W-Nachweis umfasst acht fachliche Varianten. Sowohl die native Ausführung
des gespeicherten Plans als auch die bisherigen direkten Fachadapter publizieren
die zu dessen Vorschau passenden Bytes und dieselbe Modellwurzel. Weitere Fälle
prüfen No-op, abgewiesene Actor-Writes, unzulässige Befehlsumdeklaration,
Hostverweigerung und zwischenzeitlich geänderte reale Eingaben.

Der R-Nachweis ergänzt Fehleraudits, Request-Konflikte, beschädigte
Abschlussbelege, fremde Änderungen und reale Ersetzungsfehler vor bzw. nach
einer bereits erfolgten Veröffentlichung. Eine echte native Kette erzeugt ein
Requirement, ändert dessen Statement, verknüpft es mit einem Goal, zeichnet das
Review auf und retirert das Requirement. Frisch eingelesene Zwischenstände und
Retries behalten die ursprünglichen IDs, Revisionen und historischen Audits.
Das Requirement erhält dabei keine Freigabe. Beim Retirement bestätigen
explizite vertrauenswürdige Fixturegates genau das unveränderte Review und den
unabhängig erwarteten vollständigen Zielzustand; die Core-Reviewprüfung bestimmt
seine Currentness erneut. Das ist kein Nachweis einer authentischen allgemeinen
Historien- oder Approvalbeschaffung.

Die gemeinsamen Testszenarien liegen in `tests/support/authoring_execution.py`.
Die Fachadapter liefern dieselbe vorbereitete Operation und den zugehörigen
nativen Direktaufruf; W- und R-Fälle verwenden gemeinsame Vorschau-, Ausführungs-
und Ergebnishelfer. Testkörper, Parametrisierungen, erwartete Werte und
Fixturegates bleiben bei dieser C-Bereinigung unverändert. Die bisherigen
Testkennungen bleiben erhalten; der Produktcode wird dabei nicht geändert.

Noch offen sind registrierte CLI-/stdout-Anbindung, eine Vorschau unmittelbar
aus Rohinputs einschließlich späterer ID-Übernahme, vollständige Fehler- und
Fortsetzungs-Auditberichte aller ursprünglichen Direktbefehle sowie authentische
Projekt-/Historienbeschaffung. Die vollständige Plattform-/Produktabnahme
bleibt gesondert nachzuweisen. Die API verwendet
vorbereitete Operationsdaten; sie behauptet keine bereits implementierten
`--dry-run`-Optionen der öffentlichen CLI. `init` bleibt Root-Erzeugung;
Relationsstatus bleibt eine schreibfreie Abfrage ohne Change Plan.
