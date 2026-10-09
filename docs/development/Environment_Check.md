# Environment-Check

`environment check` erzeugt eine betriebliche Momentaufnahme. Ohne `--project`
wird kein Projekt gesucht. Mit `--project PATH` werden die aktuelle
Konfiguration und die begrenzten Betriebsmetadaten geprüft; Artefakte, Gitdaten,
Anhänge, historische Receipts und Journalbodies bleiben ungelesen. Ein kaputtes
Fachmodell verhindert diese Diagnose nicht. Ein erkannter aktiver Konflikt
ergibt Code 5 und einen vollständigen Bericht, ohne Recovery oder Fachoperation.
Ein unklassifizierter Betriebseintrag oder ein nicht inspizierter Writer-Lock
blockiert ebenfalls, lässt `recovery_required` aber ausdrücklich `null`. Erst
ein erkannter aktiver Journaleintrag begründet `true`; eine konsistente aktuelle
Metadatenbeobachtung ergibt `false`. Der Bericht liest keinen Lock- oder Journalbody,
um eine nicht belegte Gewissheit zu erzeugen.

`--for-command COMMAND-ID` akzeptiert die kanonische Kennung oder eine registrierte
Schreibweise. Der Zielhandler wird nicht ausgeführt. Fehlende Zielargumente,
fehlende ausdrückliche Projektauswahl, ungeprüfte Gitvoraussetzungen und
Schreibfähigkeiten werden als `unknown` ausgewiesen. Das ergibt Code 0 mit
`compatible=null` und `operation_readiness=unknown`, solange kein wirklicher
Blocker erkannt wurde. Ohne Zielbefehl ist der Bereitschaftswert `not_requested`.

Der JSON-Envelope enthält das abrufbare Schema `environment-v1` mit
`environment_format_version=1.0.0`, sortierten Checks, Runtime- und
Distributionsdaten sowie qualifizierten Beobachtungen. Ein endliches
`RLIMIT_AS` ist ausschließlich eine Prozessadressraum-Obergrenze. CPU-Zuteilung,
nicht belegte Speicherquoten und Datenträgerquoten bleiben unbekannt. Der Bericht
behauptet weder verfügbaren RAM noch erfolgreiche spätere Allokationen oder
Schreiboperationen. Ein fehlender Build-Datensatz einer Moduldistribution bleibt
ehrlich `unrecorded`; ein beschädigter Datensatz ist ein Blocker.

`--resource-profile constrained|standard` wählt die weichen Arbeitsziele aus
Anhang O.1 mit Herkunft; ohne Auswahl gilt `constrained`. `--cpu-budget-ms`,
`--wall-budget-ms`, `--memory-budget-mib`, `--scratch-budget-mib`, `--step-cpu-ms`
und `--step-wall-ms` überschreiben jeweils genau das benannte Ziel. Nur positive
Ganzzahlen sind erlaubt. Ein explizites Schrittfenster darf größer als sein
übergeordnetes Ziel sein. Der Bericht weist jeden effektiven Wert und seine
Herkunft aus; MiB werden in Bytes umgerechnet, ohne diese Bytes zu reservieren.

Die gemeinsame reine Auflösung steht in `runtime.budget_policy`. Intern halten
`RuntimeResourceOptions` die Profilwahl und die geordneten betriebsbezogenen
Überschreibungen; `SemanticResourceConstraints` hält getrennt davon die
Scope- und Sicherheitsprojektionen. Die öffentlichen Mapping-Eingaben und
JSON-Berichte bleiben erhalten. Die Auflösung klassifiziert
ausdrücklich übergebene Ressourcengrenzen und gebundene Scope Descriptors getrennt
von den Arbeitszielen. Hostbeobachtungen erhalten ihre eigenen Werte, Quellen und
Unknowns; ein größeres Arbeitsziel erhöht keine Hostgrenze. Environment-Check
aktiviert keine Modell-/Profilauflösung. Bei explizitem `--project` übernimmt er
die deklarierten `resource_limits` aus der bereits schema- und aktuell geprüften
Konfiguration. Kleine Mengenziele werden ausgewiesen, ohne Modellgröße oder
Anzahl ungelesener Objekte zu schätzen oder daraus einen Blocker abzuleiten.
Ungültige beziehungsweise unbekannte Projektgrenzen ergeben Modellfehler 3;
konkurrierend geänderte Metadaten behalten Konfliktcode 6. Aktive Journale und
unklare Locks bleiben unabhängig davon Blocker. Fehlende Fach-/Strukturvorgaben
werden nicht erfunden, Hostwerte bleiben gesonderte Beobachtungen.
Die SRX-Bibliothek akzeptiert `EvaluationContext(..., resource_options=...)` als
Betriebsoptionen außerhalb ihrer vier fachlichen Kontextwurzeln. Der ausgewählte
Grapharbeitswert wird im bestehenden SRX-Zähler verwendet; ausdrückliche bisherige
SRX-Vorgaben und harte Strukturprüfungen bleiben erhalten.

Historische positive Gesamtmengenziele bleiben Betriebsdaten. Ihre Änderung
verändert die aktuelle semantische Konfigurations-/Modellwurzel nicht;
Paginationdefaults und harte Grenzen bleiben darin enthalten. Bereits erzeugte
Manifeste und Pläne werden nicht umgeschrieben. Die spätere Migrationsplanung
muss den Wechsel historischer Hashpolicies ausweisen. Das ist keine bereits
implementierte Migration. Tests mit vollständigen gelieferten Zielmodellen und
echter SRX-Auswertung prüfen Arbeit oberhalb kleiner Mengenziele; sie belegen
weder einen beliebig großen Auftrag auf jeder Runtime noch einen fertigen
Query-/Work-Engine. Die Budgetauflösung prüft außerdem, ob ihre Zahlen und
Qualifizierungen als tatsächliches UTF-8-JSON darstellbar sind. Ungültige
Betriebseingaben ergeben Code 2; daraus wird kein falscher Hostblocker.

`command describe environment.check` nennt `runtime-budget-v2`. Die Diagnose
meldet weiterhin `budget_engine_available=false`: Verbrauchsmessung, adaptive
Verarbeitung und persistente Fortsetzungen folgen in weiteren Planpositionen.
Der Bericht ist kein Modellbestandteil und erteilt keine Schreibberechtigung.

Alle Prüfungen bleiben lesend. Es gibt keine Probe-Writes, Benchmarks,
Netzwerkzugriffe oder ausgeführte Git-Unterprozesse. Normale frühe Syntax-,
Konfigurations- und Sicherheitsfehler behalten den bestehenden Core-Envelope;
die angeforderte Konfigurationsschema-Prüfung klassifiziert Formatfehler als
Code 3. Fehler innerhalb der Diagnose erhalten den vollständigen Bericht und
ihre tatsächliche Fehlerklasse. `semantic_validation_performed` bleibt false.

Das abrufbare Schema verlangt die Runtime-/Build-Identitätsfelder. Eine unbekannte
Ressourcenbeobachtung darf keinen numerischen Wert enthalten; ein beobachteter
Wert darf nicht `null` sein. Erfolgreiche Metadatenlesbarkeit ist keine
Schreibzusage, auch wenn der Root oder seine Dateien schreibgeschützt sind.

Der W-Nachweis umfasst echte CLI-/Request-Aufrufe, einen frischen isolierten
Prozess, native Zugriffsaufzeichnung, unveränderte Projektbytes und verbotene
Schreib-/Prozess-/Netzwerkversuche. R ergänzt tatsächliche chmod-Beschränkungen,
einen isolierten Start mit explizitem Root, unklare Betriebsmetadaten, native
Zugriffsfehler, Symlinkgrenzen und konkurrierende Metadatenänderungen. Ein regulärer
Konfigurationseintrag mit weiterem Hardlink wird nach dem bestehenden Lesevertrag
geprüft, ohne gemeinsame Bytes zu verändern oder daraus Schreibbefugnis abzuleiten.
Fehlerhafte
oder unermittelbare optionale Limits bleiben unbekannt; auch ein beobachtetes
Null-Limit behauptet keinen verfügbaren Speicher. Die optionale Ressourcenbeobachtung
ist in `runtime/resource_observations.py` von der Prüfung erforderlicher
Runtime-, Projekt- und Zielvoraussetzungen getrennt. Derselbe aktuelle Limitaufruf
liefert dieselben qualifizierten Werte und Unknowns; ihre optionale Einstufung
und die Bereitschaftsentscheidung bleiben im Diagnosebericht.
SR-TC-0565/0566/0567 bleiben partiell; eine
Runtime-/Plattformfreigabe oder ein Work-Engine-Nachweis wird nicht behauptet.
