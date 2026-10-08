# Environment-Check

`environment check` erzeugt eine betriebliche Momentaufnahme. Ohne `--project`
wird kein Projekt gesucht. Mit `--project PATH` werden die aktuelle
Konfiguration und die begrenzten Betriebsmetadaten geprüft; Artefakte, Gitdaten,
Anhänge, historische Receipts und Journalbodies bleiben ungelesen. Ein kaputtes
Fachmodell verhindert diese Diagnose nicht. Ein erkannter aktiver Konflikt
ergibt Code 5 und einen vollständigen Bericht, ohne Recovery oder Fachoperation.

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

`--resource-profile constrained|standard` projiziert die deklarierten weichen
Arbeitsziele aus Anhang O.1 mit Herkunft; ohne Auswahl gilt `constrained`. Diese
Diagnose meldet ausdrücklich `budget_engine_available=false`. Die tatsächliche
Budgetauflösung und Verarbeitung nach `runtime-budget-v2` folgen in 6.c und den
weiteren Ressourcenpositionen. Der Bericht ist kein Modellbestandteil und
erteilt keine Schreibberechtigung.

Alle Prüfungen bleiben lesend. Es gibt keine Probe-Writes, Benchmarks,
Netzwerkzugriffe oder ausgeführte Git-Unterprozesse. Normale frühe Syntax-,
Konfigurations- und Sicherheitsfehler behalten den bestehenden Core-Envelope;
die angeforderte Konfigurationsschema-Prüfung klassifiziert Formatfehler als
Code 3. Fehler innerhalb der Diagnose erhalten den vollständigen Bericht und
ihre tatsächliche Fehlerklasse. `semantic_validation_performed` bleibt false.

Der W-Nachweis umfasst echte CLI-/Request-Aufrufe, einen frischen isolierten
Prozess, native Zugriffsaufzeichnung, unveränderte Projektbytes und verbotene
Schreib-/Prozess-/Netzwerkversuche. R ergänzt weitere Rechte-, Quoten- und
Fehlergrenzen; C trennt die gemessenen Voraussetzungen strukturell von
Verfügbarkeitsschätzungen. SR-TC-0565/0566/0567 bleiben partiell; eine
Runtime-/Plattformfreigabe oder ein Work-Engine-Nachweis wird nicht behauptet.
