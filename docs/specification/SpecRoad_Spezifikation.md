# SpecRoad — Produktspezifikation
## Version 0.2.34

| Feld | Wert |
|---|---|
| Dokument-ID | `SR-SPEC-0001` |
| Dokumentversion | `0.2.34` |
| Zielrelease | `SpecRoad Single-Repository Workbench 0.2.0` |
| Status | **Fachlich konsolidierte Arbeitsgrundlage; technische Reviewentscheidung gesondert dokumentiert, formale Baseline-Freigabe und Produktabnahme nicht durch dieses Dokument erklärt** |
| Stand | 27. Oktober 2026 |
| Sprache | Deutsch; technische Feldnamen, Enum-Werte und CLI-Kommandos Englisch |
| Fachliche Quelle | **Diese Repositoryfassung v0.2.34 unter `docs/specification/SpecRoad_Spezifikation.md` ist die aktive fachliche Arbeitsgrundlage. Eine veröffentlichte PDF v0.2.34 liegt mit dieser Änderung nicht vor.** |
| Bearbeitbare Satzquelle | Diese Datei; eine spätere PDF muss denselben versionierten Inhalt wiedergeben. |
| Vorgängerversion | Repository-Spezifikation v0.2.33 vom 27. Oktober 2026; frühere PDF-/Reviewbelege bleiben an ihre historischen Fassungen gebunden. |
| Prüf- und Entscheidungsgrundlage | RESTORE-WORK-BINDING, delegiert gemäß SPECROAD-DECISION-1 unter gültigem Control-Vertrag 3; Entscheidungsbeleg und offene Verhaltensabnahmen im OFF-PLAN-Abschnitt des Implementierungsplans. Bestehende Nutzerentscheidungen und Produktfreigabegrenzen bleiben unverändert. |
| Änderungsart | Additive Präzisierung der passiven Restorebindung in Workcheckpoints und ihrer nativen Recoveryfortsetzung in 10.7.7; unveränderte Autorisierungs-, Owner-, Herkunfts- und Erhaltungsgates; keine neue Requirement-ID oder Produktposition. Umsetzung und Produktabnahme bleiben offen. |

> **Verbindlicher Quellenwechsel:** Die delegierte Detailentscheidung zur Restore-Workbindung schreibt die Repository-Spezifikation als v0.2.34 fort. Frühere PDF- und Reviewnachweise behalten ihre historische Bindung und belegen diese Präzisierung nicht. Der py3langid-Adapter bleibt Bestandteil des Zielreleases; der kleine Core bleibt ohne Analyzer-Abhängigkeiten nutzbar.

> **Fortbestehende Arbeitsprinzipien:** Weiche Budgets führen zu sparsamer vollständiger Weiterarbeit oder gesicherter Fortsetzung über mehrere Aufrufe beziehungsweise Prompts. Es werden keine erforderlichen Arbeiten stillschweigend ausgelassen. Reale Host-, Speicher-, Berechtigungs- und Sicherheitsgrenzen bleiben wirksam.

> **Freigabeabgrenzung:** Alle Requirement-IDs sind verbindliche Sollvorgaben; ihr formaler Reifegrad bleibt bis zur dokumentierten Baseline-Entscheidung `proposed`. Technische Nachweise müssen den tatsächlich geprüften Dokumenthash binden. Diese Planungsänderung erklärt weder eine PDF-Veröffentlichung noch eine Produkt- oder Baseline-Freigabe.

---

## 1. Zweck und Geltungsbereich

Diese Spezifikation definiert das Verhalten, das Datenmodell, die CLI-Verträge, die Qualitätsmerkmale und die Abnahmekriterien der **SpecRoad Single-Repository Workbench 0.2.0**.

SpecRoad ist ein lokales, Git-natives, offlinefähiges und sandbox-portables Spezifikationstool. Ein einzelner Benutzer oder ein externer KI-Agent bedient den Core ausschließlich über eine dokumentierte, nichtinteraktive CLI. Der Core verwaltet genau ein SpecRoad-Projekt in genau einem Repository beziehungsweise Projektroot, verwendet CPython 3.10 als Mindestlaufzeit und benötigt für nicht Git-spezifische Core-Funktionen keine extern zu installierenden Laufzeitpakete. Der zusätzlich verpflichtend gelieferte py3langid-Adapter ist eine getrennte Ausführungskomponente mit eigenen Abhängigkeiten und expliziter Verfügbarkeitsdiagnose nach Anhang T.

SpecRoad überführt Anforderungen und angrenzende Spezifikationsinformationen in ein typisiertes, verknüpftes und überprüfbares Modell. Es stellt dieselben Regeln für menschliches Authoring, KI-Proposals, Migration, Import, Merge, Baselines und CI bereit. Normative Änderungen werden nicht durch freie Textbearbeitung, sondern durch kontrollierte Change Plans veröffentlicht.

SpecRoad setzt keine fortbestehende KI-Sitzung voraus. Jeder Aufruf ermittelt seinen Kontext neu und verwendet einen kostengünstigen, befehlsspezifischen Preflight. Ressourcenprofile steuern den Aufwand über weiche Arbeitsziele und fortsetzbare Teilschritte, ohne den Gesamtauftrag oder fachliche Prüfungen zu verkürzen. Der Verlust der gesamten Sandbox kann nur durch extern erhaltene Distribution und Projektdateien beziehungsweise ein verifiziertes Vollbundle überbrückt werden; SpecRoad garantiert keine Erhaltung ungesicherter Daten.

### 1.1 Systemgrenze

Zum System SpecRoad 0.2 gehören:

- ein reines, nichtinteraktives CLI-Programm;
- eine entpackbare Python-Modul-Distribution und eine Python-Zipapp;
- ein portables Paket aus SpecRoad-Distribution, vollständigem Projekt und unverändertem PatchHarbor-Result sowie der gebundene Rückweg nach Anhang W;
- das kanonische JSON-Modell mit versionierten Schemas;
- vollständiges CLI-Authoring für Artefakte, Beziehungen, Lifecycle, Dokumente und Evidence;
- ein einheitliches Change-Plan-, Transaktions-, Recovery- und Idempotenzmodell;
- deterministische Validation, Linting und die deklarative Regelsprache SRX 1.0;
- Trace-, Query-, Why-, Impact-, Diff-, Coverage- und Readiness-Funktionen;
- Dokumente, Abschnitte, Inhaltsblöcke, deklarative Views und Diagrammquellen;
- Baselines, Bundles, Migration und semantischer Dreiwege-Merge;
- ReqIF-1.2-/ReqIFZ-, CSV- und NDJSON-Austausch;
- JUnit-, SARIF- und generischer Evidence-Import;
- sprachneutrale Quellcode-Traceability;
- explizite Inhaltssprachen und sprachunabhängige Verbindlichkeit mit versionierten Sprachpolicies;
- allgemeine Analyzer-Requests, Findings, Import-/Anzeigeverträge und einen tatsächlich implementierten py3langid-Adapter zur Spracherkennung;
- kontrollierte Proposals für KI- und menschlich vorbereitete Änderungen;
- benannte Produktkonfigurationen und SRX-basierte Gültigkeitsbedingungen;
- maschinenlesbare Selbstbeschreibung für CI- und KI-Agenten;
- aufrufbezogener, begrenzter Runtime-/Projekt-Preflight mit `environment check`;
- ressourcensparsame Ausführung mit weichen CPU-, Zeit-, Speicher- und Scratchzielen;
- vollständige, checkpointbasierte Arbeitsaufträge und dateibasierte Fortsetzung über mehrere Prozesse und Chat-Prompts ohne eingebauten Chatbot.

Nicht zum Systemkern 0.2 gehören ein eingebautes Sprachmodell, ein MCP-Server, eine Web- oder Desktop-Oberfläche, Benutzerkonten, Serverbetrieb, Echtzeit-Kollaboration, ein Multi-Repository-Graph, automatische Git-Commits, beliebige Shell- oder Projektcode-Ausführung, beliebige ausführbare Projekt-/Fremdplugins, tiefe semantische Textanalyse, sprachspezifische Codeparser, externe ALM-Adapter und ein eingebauter PDF-/DOCX-Renderer.

Der in Anhang T zugelassene Analyseworker bleibt die einzige automatisch startbare Analyzerkomponente. Die gesonderte PatchHarbor-Integration nach Anhang W verwendet ausschließlich vertrauenswürdig ausgelieferte Transportkomponenten und ist kein Projektplugin. Automatische Ausführung weiterer lokaler oder entfernter Analyzer bleibt außerhalb dieses Zielreleases; der Datenaustausch mit ihnen ist bereits generisch vorbereitet.

### 1.2 Produktgrenze Single-User / Single-Repository

`Single-User` bedeutet, dass SpecRoad keine Authentifizierung, Rechteverwaltung oder konkurrierende Online-Sitzungen bereitstellt. Ein einzelner Benutzer darf dennoch mit Git-Branches, Worktrees, getrennten Kopien und einer Chatbot-Sandbox parallel arbeiten. Deshalb sind kollisionsresistente Identitäten und semantischer Merge Bestandteil des Systems.

`Single-Repository` bedeutet, dass ein SpecRoad-Projekt genau einen Projektroot und eine `project_id` besitzt. Ein Repository darf genau ein aktives SpecRoad-Projekt enthalten. Mehrere unabhängige Projekte dürfen nicht innerhalb eines einzelnen Befehls zu einem gemeinsamen kanonischen Modell verbunden werden.

### 1.3 Explizite Nicht-Ziele

SpecRoad 0.2 ist ausdrücklich nicht:

- ein Chatverlauf als Spezifikation;
- ein Markdown-only-Editor ohne semantisches Modell;
- eine parallele Datenbank neben manuell gepflegten Dokumenten;
- ein autonomer KI-Agent mit eigener Freigabekompetenz;
- ein universelles Projektmanagement- oder Enterprise-ALM-System;
- ein Server, Benutzer- oder Kollaborationssystem;
- ein Build-, Test- oder Deployment-Orchestrator;
- ein Multi-Repository- oder Portfolio-Management-System;
- ein Werkzeug, das formale Korrektheit ohne ausführbaren Nachweis behauptet;
- ein Renderer, der externe Programme oder Browser als Core-Voraussetzung startet.

---

## 2. Normative Sprache, Widersprüche und Referenzen

Für die redaktionellen Vertragssätze **dieses Spezifikationsdokuments** sind die vollständig großgeschriebenen Schlüsselwörter `MUSS`, `MÜSSEN`, `DARF NICHT`, `DÜRFEN NICHT`, `SOLLTE`, `SOLLTEN`, `DARF` und `DÜRFEN` normativ. `SOLLTE` beziehungsweise `SOLLTEN` ist nur zulässig, wenn Abweichungsbedingungen und Abweichungsautorität explizit angegeben sind. Nicht großgeschriebene Formulierungen sind erläuternd.

Für Requirements im ausführbaren Produktmodell gilt dagegen `normative_force` nach Anhang S als strukturierte Verbindlichkeit; `statement` muss kein solches Schlüsselwort enthalten. Der Core erkennt daraus keine Textbedeutung. Ein fachlicher Widerspruch zwischen Feld und Sachverhalt ist ein Reviewthema und wird nicht durch automatisches Umschreiben verborgen.

### 2.1 Widerspruchsregel

Bei einem Widerspruch innerhalb dieser Dokumentversion gilt:

1. Eine explizite `SR-REQ-*`-Anforderung hat Vorrang vor normativen Tabellen, Architekturentscheidungen und erläuterndem Text.
2. Normative Tabellen, Grammatiken, Zustands-, Auswahl-, Closure- und Operationsverträge haben Vorrang vor `SR-DEC-*`.
3. `SR-DEC-*` hat Vorrang vor erläuterndem Text, Diagrammen und Beispielen.
4. Beispiele sind niemals normativ, sofern sie nicht ausdrücklich als Testvektor bezeichnet sind.
5. Zwei widersprüchliche `SR-REQ-*`-Anforderungen besitzen **keine implizite Rangfolge** nach Nummer, Position oder Spezifität. Ein solcher Fund ist ein Spezifikationsfehler, muss als Issue gelöst werden und verhindert die Freigabe.
6. Diese Dokumentversion 0.2.34 ersetzt die frühere fachliche Arbeitsgrundlage vollständig. Bis zur gesonderten PDF-Veröffentlichung ist diese versionierte Repositorydatei maßgeblich. Eine spätere PDF muss inhaltsgleich sein; frühere PDFs werden nicht als Nachweis der neuen Verträge ausgegeben. Inhalte verschiedener Fassungen dürfen nicht zu einer Mischspezifikation kombiniert werden.
7. Eine nachträgliche Änderung dieser veröffentlichten Datei erfordert mindestens eine neue Patch-Dokumentversion; stille Korrekturen unter derselben Dokumentversion sind unzulässig.
8. Eine normative Tabelle, auf die eine `SR-REQ-*`-Anforderung ausdrücklich als Algorithmus oder Matrix verweist, ist Bestandteil des Passkriteriums dieser Anforderung.

### 2.2 Verbindliche Begriffe

| Begriff | Verbindliche Definition |
|---|---|
| Artefakt | Ein typisiertes, durch eine stabile ID identifiziertes Objekt des kanonischen Modells. |
| Kanonisches Modell | Die aus `specroad.json`, normativen JSON-Ressourcen, aktiven Profilen, Regeln, Konfigurationen und referenzierten Anhängen gebildete einzige semantische Source of Truth. |
| Normativ | Für Konformität verbindlich. |
| Generierte Sicht | Eine reproduzierbar aus dem kanonischen Modell erzeugte, nicht normative Darstellung. |
| Semantische Änderung | Eine Änderung an normativen Werten oder Beziehungen, die Bedeutung, Gültigkeit, Status, Verifikation, Planung, Dokumentkomposition oder Herkunft beeinflussen kann. |
| Repräsentationsänderung | Eine bytebezogene Normalisierung ohne Änderung des durch JSON-Werte, Anhänge oder Beziehungen gebildeten semantischen Inhalts. |
| Relation | Eine gerichtete, typisierte Kante mit eigener stabiler `relation_id`, gespeichert am Quellartefakt. |
| Relationsreview | Ein unveränderbarer Nachweis, dass eine Relation für konkrete Quell- und Zielkontext-Hashes bestätigt oder verworfen wurde. |
| Arbeitsstand | Das aktuell im Projektroot geladene kanonische Modell außerhalb einer Baseline. |
| Change Plan | Eine geordnete, versionierte Beschreibung von Operationen mit erwarteter Basis, gebundenen Metadaten, Vorbedingungen, Akteur und exaktem Ergebnis. |
| Transaktion | Die journalbasierte Ausführung eines validierten Change Plans mit Staging, Before Images, Veröffentlichung und Recovery. |
| Scope Descriptor | Eine versionierte, kanonische Beschreibung von Scope-Art, Seed-Auswahl, Closure-Profil, Konfiguration und Grenzpolicy. |
| Seed-Menge | Die durch die Scope-Art unmittelbar ausgewählten Ressourcen vor Anwendung der Closure. |
| Scope-Closure | Der deterministische kleinste Fixpunkt, der aus einer Seed-Menge nach dem festgelegten Closure-Profil entsteht. |
| Modellumfang | Die durch einen Scope Descriptor bestimmte geordnete Menge normativer Ressourcen, Anhänge und deklarierter Boundary References. |
| Boundary Reference | Eine im Manifest eines partiellen Umfangs deklarierte, absichtlich nicht enthaltene Referenz auf eine Ressource des Ursprungsmodells. |
| Modellwurzel | Der deterministisch berechnete SHA-256-Hash eines normativen Modellmanifests einschließlich Scope Descriptor und Boundary References. |
| Baseline | Eine unveränderbare Momentaufnahme konkreter Ressourcen und ihrer Snapshotobjekte. |
| Proposal | Ein versionierter Änderungsvorschlag mit Basis, Change Plan, Begründung, Quellen und Review-Historie. |
| Evidence | Ein unveränderbarer, versions- und hashgebundener Prüfnachweis. |
| Verification Plan Status | Der gespeicherte Workflowzustand `not_planned`, `planned`, `running`, `waived` oder `not_applicable`. |
| Verification Result | Die nicht gespeicherte, für Modellumfang und Konfiguration berechnete Sicht `not_evaluated`, `incomplete`, `running`, `passed`, `failed`, `stale`, `waived` oder `not_applicable`. |
| suspect | Ein berechneter Zustand, in dem ein Relationsreview nicht mehr zum aktuellen Relationsinhalt oder zu den reviewrelevanten Kontextprojektionen seiner Endpunkte passt. |
| stale | Ein berechneter Zustand, in dem eine Basis, Evidence oder Code-Referenz nicht mehr zu den dafür definierten aktuellen Voll- oder Kontext-Hashes passt. |
| Dokument | Eine normative Komposition aus Abschnitten und Inhaltsblöcken; fachliche Artefakte werden referenziert und nicht dupliziert. |
| Primärspezifikation | Das genau einmal vorhandene, nicht retirierte Dokument mit `document_role = primary_specification`. |
| Partielles Bundle | Ein verifiziertes, extrahiertes, schreibgeschütztes Teilprojekt mit Boundary References und eigener partieller Modellwurzel. |
| View | Eine deklarative, versionierte Definition einer tabellarischen oder berichtsartigen Sicht. |
| Konfiguration | Eine benannte Auswahl von Variantendimensionswerten, gegen die `applicability` ausgewertet wird. |
| Menschliche Freigabe | Eine Entscheidung `approved` eines Akteurs vom Typ `human`, gebunden an exakte Identitäten, Revisionen und Hashes. |
| Kernfunktion | Eine eingebaute dependency-freie SpecRoad-Funktion; enthält auch Analyzer-Descriptor-/Dateiverträge, aber nicht die Auswertung im separat installierten py3langid-Worker; kein beliebiger externer Prozess, Plugin, Buildskript oder Projektcode. |
| Projektroot | Das Verzeichnis der ausgewählten `specroad.json`. |
| Managed Path | Ein projektroot-relativer Pfad, dessen Inhalte SpecRoad kontrolliert lesen oder schreiben darf. |
| Request-ID | Eine vom Aufrufer vergebene stabile Kennung zur idempotenten Wiederholung eines normativen Schreibbefehls; gilt ausschließlich im normativen Schreibnamensraum. |
| Analysekennung | Die nach Anhang T.3 vergebene Korrelation eines Analyseauftrags, im Analyzer-Request als `request_id` gespeichert; kein normativer Schreibrequest und keine Freigabe. |
| Normativer Schreibbefehl | Ein Befehl, der kanonische Modellressourcen oder deren formatierbare normative Bytes verändert. |
| Generierter Ausgabebefehl | Ein Befehl, der ausschließlich abgeleitete Dateien außerhalb des kanonischen Modells erzeugt. |
| Lokaler Betriebsbefehl | Ein Befehl, der ausschließlich `.specroad/`-Betriebsdaten oder Recovery-Auditdaten verändert. |
| Root-Erzeugungsbefehl | `init` oder `bundle extract`; der Befehl erfüllt die jeweilige Zielvorbedingung aus Kapitel 11.7 und veröffentlicht die neue Root-Struktur atomar. |
| Plan-Ausgabebefehl | Ein Befehl, der einen versionierten Import-, Migrations- oder Merge-Plan erzeugt oder explizit fortschreibt, ohne normative Projektressourcen zu verändern. |
| Recovery-Schreibbefehl | Ein ausschließlich zur Wiederherstellung zugelassener Befehl, der nach dem gebundenen Recovery-Vertrag normative Dateien auf einen verifizierbaren Basis-, Ziel- oder Restore-Zustand bringt. |
| Aufrufkontext | Die für einen einzelnen Prozesslauf aus aktuellen Eingaben und Dateien bestimmte Runtime-, Root-, Policy- und Betriebszustandsauswahl. |
| Preflight | Begrenzte Prüfung der unmittelbar für den konkreten Befehl benötigten Startvoraussetzungen; keine allgemeine Projektvalidierung. |
| Portabler Fortsetzungsstand | Entweder ein abgeschlossenes Projektvollbundle oder ein ausdrücklich als unvollständig gekennzeichnetes Arbeitspaket nach Anhang P mit gebundenem Eingangssnapshot, Cursor und Zwischenergebnissen; kein flüchtiger Prozesszustand. |
| Wiederherstellungskritische Betriebsdaten | Journal, Staging, Before Images und zugehörige Metadaten einer nicht abschließend belegten Transaktion; nicht als Cache löschbar. |
| Ressourcenprofil | Nicht normative betriebliche Auswahl weicher Arbeitsziele `constrained` oder `standard`; unabhängig von fachlichen Profilen und Produktkonfigurationen. |
| Weiches Arbeitsbudget | Optimierungs- und Teilungsziel; seine Überschreitung allein ist weder Fehler noch Berechtigung zum Auslassen von Arbeit. |
| Harte Grenze | Nachgewiesene Host-/Dateisystemgrenze oder explizite Sicherheits-/Formatpolicy; keine automatisch übergehbare Optimierungsvorgabe. |
| Fortsetzbare Arbeitseinheit | Vollständig beschriebener Teil eines gebundenen Gesamtauftrags mit Eingangsbindung, Cursor, Ergebnisnachweis und offenen Abhängigkeiten. |
| Arbeitsstand / Checkpoint | Versionierter, atomar veröffentlichter Betriebsstand eines Arbeitsauftrags außerhalb des normativen Projekts; keine fachliche Teilfreigabe. |
| Fortsetzung erforderlich | `continuation_required`, Exit Code 8; Auftrag bleibt offen und ist mit dem gespeicherten Checkpoint fortsetzbar. |
| Tatsächlicher Ressourcenblocker | Nach sparsamem Versuch nachgewiesene fehlende Voraussetzung; offene Arbeit und konkrete Abhilfe bleiben ausgewiesen, ohne falsche Erfolgsmeldung. |

### 2.3 Referenzierte Standards und Formate

| Referenz | Verwendung | Status |
|---|---|---|
| ISO/IEC/IEEE 29148:2018 | Requirements-Engineering-Struktur und Qualitätsprinzipien | informativ |
| ISO/IEC 25010:2023 | Produktqualitätsmodell | informativ |
| RFC 2119 und RFC 8174 | Normative Schlüsselwörter | normativ |
| RFC 8259 | JSON | normativ |
| RFC 6901 | JSON Pointer | normativ |
| RFC 6902 | JSON Patch | normativ |
| JSON Schema Draft 2020-12 | Schemasprache | normativ |
| RFC 8785 | JSON Canonicalization Scheme | normativ |
| FIPS PUB 180-4 | SHA-256 | normativ |
| RFC 3339 | Zeitstempel | normativ |
| RFC 4180 | CSV-Austauschprofil | normativ |
| OMG ReqIF 1.2 | Requirements Interchange Format und ReqIFZ-Inhalte | normativ für den unterstützten Schnittmengenvertrag |
| SARIF 2.1.0 | CI-Diagnosen und Evidence-Import | normativ |
| Semantic Versioning 2.0.0 | Schema-, Sprach- und Ausgabeformatversionen | normativ |
| CommonMark | Kernsubset für Prosa-Inhaltsblöcke | informativ; das unterstützte Subset wird durch SpecRoad definiert |
| JUnit XML | Evidence-Import | kein einheitlicher externer Standard; normativ ist ausschließlich das dokumentierte SpecRoad-JUnit-Kernprofil |
| Mermaid und Graphviz DOT | Erzeugte Diagrammquellen | informativ; normativ ist die von SpecRoad dokumentierte Ausgabesyntax |

### 2.4 Delegierte Spezifikationsklärung — SPECROAD-DECISION-1

**Autorität und Geltung:** Mit dem ausdrücklichen Nutzerauftrag vom
22. Oktober 2026 wird `SPECROAD-DECISION-1` als verbindliche Projektvorgabe
für die externe Entwicklung von SpecRoad erteilt. Der beauftragte Dev-Agent
MUSS eine nach den folgenden Grenzen zulässige fehlende fachliche Detailregel
selbst entscheiden, dokumentieren und anschließend umsetzen,
ohne für jede solche Entscheidung erneut eine Zustimmung einzuholen.
Dies ist eine vorab delegierte Entwicklungsentscheidung, keine vom Agenten
erfundene Einzelzustimmung des Nutzers. Nur der Nutzer darf diese Befugnis
erweitern oder widerrufen; ein normaler Entwicklungsauftrag ermächtigt den
Agenten nicht dazu, seine eigenen Grenzen umzuschreiben.

Diese Regel betrifft die Weiterentwicklung der Repository-Spezifikation und
des bestätigten Implementierungsplans. Sie verleiht dem SpecRoad-Produkt
oder seinen KI-Akteuren keine eigene Freigabekompetenz. Insbesondere bleiben
1.3, die Widerspruchsregel 2.1, die Human-Review-/Proposal-Verträge, Risiko-
und Waiverentscheidungen, Releasegates und formale Baseline-Abnahmen wirksam.
Ein Entwicklungsmandat ist kein `actor_type=human`-Nachweis und kein Ersatz
für eine konkrete menschliche Entscheidung im verwalteten Produktmodell.

#### 2.4.1 Zulässige Entscheidung und Auswahl

Vor einer Entscheidung MUSS der Agent das maßgebliche Result, die aktuelle
Spezifikation, den offenen Planschritt und vorhandene Nutzerentscheidungen
prüfen. Eine bereits ausdrücklich geklärte Frage DARF NICHT neu entschieden
werden, nur weil eine andere Lösung leichter zu implementieren wäre.

Eine Lücke DARF selbstständig geschlossen werden, wenn alle Bedingungen gelten:

1. Sie liegt im bereits bestätigten Funktionsumfang des offenen Schritts und
   ist eine fehlende Detailfestlegung, kein neues Feature, vorgezogener
   Planschritt oder Wechsel der zugesagten Architektur/Vertrauensgrenze.
2. Es gibt mindestens eine konkrete, überprüfbare Lösung, die alle geltenden
   Anforderungen und ausdrücklichen Nutzerentscheidungen gleichzeitig erfüllt.
   Niederrangiger erläuternder Text darf nach 2.1 an den eindeutigen Vertrag
   angeglichen werden; widersprüchliche gleichrangige Requirements dürfen nicht
   nach Bequemlichkeit ausgewählt oder still gestrichen werden.
3. Die Lösung erhält Scope, Sicherheitsniveau, Datenintegrität, Nachweis- und
   Reviewpflichten sowie zugesagte CLI-, Format- und Bestandskompatibilität.
   Ein gesondert freizugebender Datenverlust, inkompatibler Umbau oder eine
   Veränderung realer fremder Daten ist keine konservative Präzisierung.
4. Die Entscheidung ist nachvollziehbar rücknehmbar: versionierte Regel,
   klar begrenzte Auswirkungen und erhaltene Bestandsdaten/Nachweise.
   Reversibilität bedeutet nicht, dass spätere Git-Resets oder das Löschen
   von Daten, Jobs oder Evidence automatisch erlaubt wären.
5. Ihre Richtigkeit hängt nicht von unverfügbaren zwingenden externen Fakten,
   privaten Zugangsdaten oder einer noch ausstehenden realen menschlichen
   Fachentscheidung ab. Eine erfundene Annahme ersetzt keine solche Eingabe.

Der Agent MUSS die realistisch geeigneten Alternativen und ihre Auswirkungen
untersuchen. Er wählt die kleinste konsistente Lösung mit dem geringsten
zusätzlichen Risiko und Änderungsumfang. Bei mehreren gleichermaßen passenden
Möglichkeiten haben bestehende lokale Verträge und wiederverwendbare native
Mechanismen Vorrang. Die bloße Existenz mehrerer vertretbarer Optionen ist
kein Grund für `blocked`. Eine unabhängige unnötige Architekturvariante oder
ein neuer Fallback wird nicht allein für diese Auswahl eingeführt.

Typische zulässige Präzisierungen sind bisher fehlende Feldmengen,
deterministische Fehler-/Statusregeln oder eine selbstreferenzfreie
Hashprojektion, sofern sie die genannten Bedingungen erfüllen. Ein neuer
Default muss ausdrücklich spezifiziert werden und darf fehlende Evidence
oder Pflichtfreigaben niemals in einen positiven Status umdeuten. Ein
sicherer Fehlerfall darf nicht als Vorwand dienen, das zugesagte Feature
dauerhaft unbenutzbar zu lassen. Bereits festgelegte Regeln, insbesondere
10.5.5 und 10.5.6, bleiben Ausgangspunkt der Umsetzung.

#### 2.4.2 Entscheidungsbeleg und normative Fortschreibung

Vor der davon abhängigen Produktänderung MUSS ein nachvollziehbarer
Entscheidungsbeleg im betroffenen Abschnitt des Implementierungsplans stehen:

- eindeutige Entscheidungskennung, betroffener Planschritt und genaue Lücke;
- maßgebliche Spec-/Requirement-Bezüge und tatsächlich geprüfte Quellen;
- betrachtete Alternativen, gewählte Lösung und konkrete Begründung;
- Abgleich mit jeder Grenze aus 2.4.1 sowie Auswirkungen auf Kompatibilität,
  Daten, Sicherheit, Tests und mögliche Rücknahme;
- normative Zielregel und zugehörige beobachtbare positive, negative und
  relevante Grenzfall-Abnahmekriterien;
- Autorität `delegiert gemäß SPECROAD-DECISION-1`, ohne behauptete persönliche
  Einzelbestätigung des Nutzers oder fingierte Reviews;
- noch offene Umsetzung und Nachweise. Fachliche Klärung, Implementierung
  und beobachteter Apply-Erfolg bleiben unterscheidbar.

Die Entscheidung MUSS zuerst in dieser normativen Spezifikation und den
betroffenen Planabnahmen konsistent fortgeschrieben werden. Eine neue
normative Fassung erhält nach 2.1 eine neue Patch-Dokumentversion und passende
aktive Katalogbindungen; historische Resultate, Reviews und Evidence bleiben
unverändert an ihre ursprünglichen Bytes gebunden. Ein Entscheidungsbeleg
allein ersetzt weder die normative Regel noch ausführbare Verhaltensabnahme.
Keine zusätzliche Requirement-ID oder Produktposition entsteht allein für
das Dokumentieren dieser Arbeitsbefugnis.

#### 2.4.3 Übergabe an Control und Begrenzung der Klärung

**Ausdrücklich beauftragte Erweiterung.** Der manuelle Nutzerauftrag vom
26. Oktober 2026 erweitert `SPECROAD-DECISION-1` für Control-Vertrag 3 auf
höchstens drei aufeinanderfolgende Klärungsbundles. Diese Erweiterung folgt
unmittelbar aus diesem Nutzerauftrag, nicht aus der bisherigen Delegation.
Alle fachlichen Grenzen aus 2.4.1, Entscheidungsbelege aus 2.4.2 und
Blocker-/Erhaltungsregeln aus 2.4.4 bleiben uneingeschränkt verbindlich.
Die Erweiterung betrifft ausschließlich die Entwicklungsbefugnis; sie
ersetzt keine menschlichen Produktfreigaben, Reviews, Risikoentscheidungen
oder Nachweise.

Im automatisierten Betrieb gelten zusätzlich der tatsächlich gespeicherte
`CONTROL_DECISION_CONTRACT` und das Antwortschema des jeweiligen Auftrags.
Diese Projektregel aktualisiert keinen laufenden oder historischen Auftrag
und schreibt keinen Control-Zustand um. Ein ausdrücklicher manueller
Nutzerauftrag kann einen eigenen OFF-PLAN-Schritt beauftragen; daraus
entsteht keine automatische Erweiterung des bestehenden Control-Auftrags
oder seines Restbudgets.

**Gültiger Vertrag 3.** Er enthält die folgenden verbindlichen Felder mit
ihren tatsächlichen JSON-Typen, ohne implizite Typkonvertierung:

| Feld | Vertrag |
|---|---|
| `version` | Ganzzahl, exakt `3` |
| `clarification_limit` | Ganzzahl, exakt `3` |
| `clarifications_remaining` | Ganzzahl von `0` bis `3`, einschließlich beider Grenzen; Boolean ist keine Ganzzahl dieses Vertrags |
| `clarification_allowed` | Boolean, exakt `true` oder `false` |

Bei `clarifications_remaining=0` MUSS `clarification_allowed=false` gelten.
Die Kombination aus Restbudget 0 und `true` ist ungültig, keine Freigabe
und kein Anlass, den Vertrag still zu reparieren. Fehlende Pflichtfelder,
falsche Typen, andere Limits oder Werte außerhalb des Bereichs erlauben
keine automatische Klärungsübergabe. Fehlende oder unbekannte Verträge
werden ebenso wenig als Zustimmung ausgelegt; es gibt keinen impliziten
Fallback auf eine großzügigere Version oder ein erfundenes Startbudget.

Eine automatische Klärungsübergabe unter Version 3 ist nur bei gültigem
Vertrag, `clarification_allowed=true` **und** positivem Restbudget erlaubt.
`false` sperrt sie auch bei Restbudget 1, 2 oder 3. Der Dev-Agent MUSS das
tatsächlich erteilte Budget beachten und DARF es weder aus der Anzahl
sichtbarer Dateien rekonstruieren noch selbst erhöhen. Ein positiver
Restwert ersetzt weder die fachlichen Grenzen noch die nachfolgend
verlangten Apply-Nachweise.

**Eine Übergabe pro Auftrag und Result.** Ist zur Auflösung eine innerhalb
der erteilten Befugnis zulässige normative Entscheidung nötig, liefert der
Agent genau ein state-gebundenes OFF-PLAN-Spezifikationsbundle und meldet
`status=spec_clarification`, die SHA-256 des tatsächlichen Quell-Results,
die SHA-256 der fertig nativ geprüften ZIP und eine kurze Entscheidungserklärung.
Die vier Antwortfelder bleiben `source_result_sha256`, `status`,
`patch_sha256` und `message`. Je Auftrag und Quell-Result ist höchstens ein
Bundle zulässig. Das Restbudget erlaubt weder mehrere Bundles aus derselben
Quelle noch mehrere Klärungen innerhalb eines eigenen Fortsetzungsloops.
Nach atomarer Übergabe endet der Auftrag sofort; kein selbst gestartetes
Apply und keine eigene Warte-/Modellschleife. Apply, Tests und Result-Erzeugung
bleiben beim gesondert autorisierten externen Verfahren. Der reguläre
Planschritt bleibt bis zu seiner echten Umsetzung offen.

**Verbrauch und Folgeauftrag.** Jede als `spec_clarification` klassifizierte
Übergabe verbraucht bei der Übernahme ihres eindeutig zugeordneten
Folge-Results genau einen Platz, auch wenn Apply fehlgeschlagen ist.
Control MUSS diese Zuordnung und den Verbrauch dauerhaft und genau einmal
festhalten; die erneute Übernahme derselben Übergabe ist weder ein zweiter
Verbrauch noch eine Erneuerung des Budgets. Ohne eindeutig zugeordnetes
Result darf kein erfolgreicher Abschluss angenommen werden.

Eine weitere automatische Klärung setzt das zugehörige **erfolgreiche,
saubere Apply mit passendem Abschlusscommit**, verbleibendes positives
Budget und einen neuen gültigen, freigebenden Auftrag voraus. Ein fehlendes,
fehlgeschlagenes, unsauberes oder nicht passend abgeschlossenes Apply
genehmigt keine weitere Klärung, auch wenn noch Plätze übrig sind.
Der laufende, ausdrücklich zum Fortsetzen autorisierte Control-Worker darf
den offenen Planschritt auf Basis des zugeordneten Results erneut beauftragen.
Höchstens drei Klärungsbundles dürfen so über **getrennte Aufträge und
zugeordnete Apply-Results** aufeinanderfolgen. Dieser Vertrag startet oder
reaktiviert selbst keinen Worker.

Nach der dritten Klärung bleibt reguläre Umsetzung erlaubt; eine vierte
Klärung ist gesperrt. Bei `clarification_allowed=false` oder Restbudget 0
MUSS der Agent die bereits geklärte Vorgabe umsetzen, soweit sie klar und
beauftragt ist. Ist weitere notwendige Klärung nicht mehr erlaubt, meldet
er `blocked` mit konkreter Frage, Empfehlung und Befugnisgrenze gemäß 2.4.4.
Ein verbrauchtes Klärungsbudget ist kein Produktabschluss und kein `no_work`.

**Erneuerung ausschließlich durch normalen Abschluss.** Nur das
erfolgreiche, saubere Apply mit passendem Abschlusscommit eines als
`patch_ready` klassifizierten regulären Umsetzungs- oder echten technischen
Korrekturbundles eröffnet unter Vertrag 3 erneut drei Plätze. Die
Klassifikation allein ist kein Nachweis einer solchen Änderung.
Eine Spezifikationsklärung DARF NICHT als `patch_ready`, kosmetischer
Produkt-/Alibi-Commit oder scheinbare technische Korrektur verborgen werden.
Es gibt keine kosmetischen Budget-Resets. Fehler und unklassifizierte
Übergaben erteilen keine neue Befugnis; auch ein sauber angewendetes
Klärungsbundle erneuert das Budget nicht. Control prüft Bindung und
Klassifikation, nicht die fachliche Qualität oder tatsächlichen
Planfortschritt; die Reviewpflicht bleibt.

**Dauerhaftigkeit und Versionsübergang.** Control verwaltet das Budget
dauerhaft. Retry, Overload, Pause, Neustart und Recovery erneuern es nicht.
Alte Verträge, Aufträge, Antworten und Result-Nachweise DÜRFEN NICHT
nachträglich erweitert oder umklassifiziert werden. **Version 2 behält die
Einerregel:** höchstens ein Klärungsbundle in Folge, automatische Übergabe
nur bei gültigem Vertrag 2 mit `clarification_allowed=true`; `false`
sperrt weitere Klärung. Die bisherigen Abschluss- und Resetgrenzen für
Version 2 bleiben erhalten; fehlende Restbudgetfelder erzeugen dort keine
drei Plätze.

Der Wechsel einer alten Kette zu Vertrag 3 erfolgt erst nach dem belegten
erfolgreichen normalen Abschluss gemäß Control-Vertrag: ein passend
zugeordnetes `patch_ready`-Bundle mit echter Umsetzung oder technischer
Korrektur, erfolgreichem sauberem Apply und passendem Abschlusscommit.
Erst danach darf Control für einen neuen Auftrag Vertrag 3 mit drei
Plätzen ausstellen. Eine neue Spezifikationsfassung, dieser manuelle
OFF-PLAN-Auftrag, dessen erfolgreicher Dokumentcommit oder ein Neustart
sind kein solcher Übergang und kein nachträgliches Auffüllen einer alten
Kette. Bestehende Blockaden und Antworten bleiben erhalten.

Ein reiner Spezifikationsschritt ist ein echter OFF-PLAN-Dokumentcommit,
keine künstliche W/R/C-Produktfolge. Bei Produktimplementierung bleiben
echte W/R/C-Zwischenstände und ihre jeweiligen Tests/Commits Pflicht.
TD-001 und die lokale Testpolicy bleiben maßgeblich: keine erfundenen
Dokumentationstests, kein zusätzlicher Volltest, unveränderte parallele
Apply-Testrotation mit N=3 pro tatsächlichem Commit. Collection-, Katalog-,
Paket- und Result-Prüfungen bleiben bestehen. Ein Dokumentcommit erhöht
keinen regulären Produktzähler und erklärt keine Produktabnahme.


#### 2.4.4 Echte Blocker und Erhaltung des Betriebszustands

Ist keine Lösung innerhalb der Befugnis nachweisbar, MUSS der Agent stoppen
und `blocked` mit der konkreten offenen Frage, seinem Lösungsvorschlag,
den betroffenen Regeln und dem Grund melden, weshalb die delegierte
Entscheidung nicht ausreicht. Unverzichtbare unbekannte externe Tatsachen,
eine geforderte echte menschliche Freigabe, unauflösbare Anforderungskonflikte
und eine bereits verbrauchte Klärungsbefugnis dürfen nicht umgangen werden.
Ein Blocker ist kein `no_work` und kein abgeschlossener Planschritt.

Diese Delegation ist keine Start-, Resume-, Recovery- oder Retry-Anweisung.
Vorhandene Pausen, `dev_blocked`, unklare Claims, alte Antworten und
Overload-Belege bleiben erhalten. Kein Neu-Seed, kein Reset und keine
nachträgliche Umdeutung alter Aufträge. Ihre Übernahme erfolgt ausschließlich
nach dem bestehenden ausdrücklich beauftragten Control-Verfahren.

---

## 3. Produktziele

| ID | Ziel | Erfolgsaussage |
|---|---|---|
| SR-GOAL-0001 | Eine semantische Source of Truth | SpecRoad verwaltet Spezifikationswissen in genau einem kanonischen, maschinenlesbaren Modell; Dokumente und Berichte sind kontrolliert abgeleitete Sichten. |
| SR-GOAL-0002 | Hohe und überprüfbare Spezifikationsqualität | Struktur-, deklarierte Sprachpolicy-, Lifecycle- und Traceability-Regeln werden deterministisch geprüft; statistische Analyzerbeobachtungen bleiben davon getrennt und als begrenzte Hinweise erkennbar. |
| SR-GOAL-0003 | Durchgängige und reviewbare Traceability | Ziele, Bedürfnisse, Anforderungen, Entscheidungen, Code, Umsetzung, Tests, Evidenzen, Releases und Dokumente bleiben als typisierter Graph verbunden; geänderte Beziehungen werden als prüfbedürftig erkannt. |
| SR-GOAL-0004 | Git-native, lokale und CI-fähige Arbeitsweise | Projekte sind lokal, diffbar, branchfähig, reproduzierbar und ohne Cloud-Zwang automatisierbar. |
| SR-GOAL-0005 | Kontrollierte KI-Bedienung | KI-Agenten bedienen dieselbe CLI, erzeugen sichtbare Proposals und können keine fachliche Freigabe oder Evidence ersetzen. |
| SR-GOAL-0006 | Verifikation und Evidenz als Modellbestandteil | Prüfverträge und importierte oder erfasste Nachweise sind versions- und hashgebunden und machen Coverage sowie Veraltung sichtbar. |
| SR-GOAL-0007 | Erklärbare Planung und Dokumentation | Releases, Roadmaps, Spezifikationsdokumente, Ansichten und Berichte werden aus dem Modell abgeleitet und bleiben fachlich erklärbar. |
| SR-GOAL-0008 | Offene, portable und langfristig wartbare Grundlage | Der Core ist offline, dependency-frei, migrationsfähig und über offene Formate austauschbar. |
| SR-GOAL-0009 | Sichere Änderung langlebiger Projekte | Alle Schreibwege verwenden einen gemeinsamen Change Plan, crashsichere Recovery, Migration und nachvollziehbare Auditbelege. |
| SR-GOAL-0010 | Praxistaugliche Single-User-Workbench | Ein einzelner Benutzer oder Agent kann in genau einem Repository vollständig über die CLI authoren, vergleichen, mergen, dokumentieren und austauschen. |

---

## 4. Stakeholder und Bedarfe

| ID | Stakeholder/Rolle | Bedarf | Unterstützte Ziele |
|---|---|---|---|
| SR-NEED-0001 | Spezifikationsautor | Ein Autor benötigt eine lokale, verständliche und vollständige CLI zum Erzeugen, Ändern, Strukturieren und Rendern von Spezifikationsartefakten. | SR-GOAL-0001, SR-GOAL-0002, SR-GOAL-0010 |
| SR-NEED-0002 | Requirements Engineer | Ein Requirements Engineer benötigt verbindliche Qualitätsregeln, Profile, Glossare, Lifecycle, Relationsregeln und Baselines. | SR-GOAL-0002, SR-GOAL-0003, SR-GOAL-0008 |
| SR-NEED-0003 | Reviewer | Ein Reviewer benötigt semantische Diffs, Impact, suspect Relations, Quellen, Begründungen und nachvollziehbare Freigaben. | SR-GOAL-0002, SR-GOAL-0003, SR-GOAL-0009 |
| SR-NEED-0004 | Entwickler und Architekt | Entwickler und Architekten benötigen eindeutige Anforderungen sowie Traceability zu Komponenten, Aufgaben und konkreten Quellcodebereichen. | SR-GOAL-0003, SR-GOAL-0004, SR-GOAL-0006 |
| SR-NEED-0005 | Test und Qualität | Test- und Qualitätsverantwortliche benötigen Verifikationsverträge, standardisierten Evidence-Import, Coverage und revisionsgebundene Nachweise. | SR-GOAL-0002, SR-GOAL-0006 |
| SR-NEED-0006 | Release-Verantwortlicher | Ein Release-Verantwortlicher benötigt eine aus Anforderungen, Risiken, Code, Aufgaben und aktueller Evidence abgeleitete Readiness-Sicht. | SR-GOAL-0003, SR-GOAL-0006, SR-GOAL-0007 |
| SR-NEED-0007 | CI-System und Automation | Automation benötigt nichtinteraktive Befehle, stabile Formate, deterministische Ergebnisse, Idempotenz und eindeutige Exit Codes. | SR-GOAL-0002, SR-GOAL-0004, SR-GOAL-0009 |
| SR-NEED-0008 | KI-Agent | Ein KI-Agent benötigt maschinenlesbare Selbstbeschreibung, strukturierte Diagnosen, isolierte Proposal-Prüfung und einen portablen CLI-Roundtrip. | SR-GOAL-0004, SR-GOAL-0005, SR-GOAL-0010 |
| SR-NEED-0009 | Audit und Compliance | Audit-Rollen benötigen Herkunft, Identitäten, Reviews, Transaktionen, Migrationen, Baselines, Änderungen und Evidenzketten. | SR-GOAL-0003, SR-GOAL-0006, SR-GOAL-0009 |
| SR-NEED-0010 | Projektleitung | Projektleitung benötigt eine erklärbare, nicht separat gepflegte Roadmap und einen belastbaren Release-Umfang. | SR-GOAL-0003, SR-GOAL-0007 |
| SR-NEED-0011 | Datenschutz und lokale Sicherheit | Teams benötigen Kernfunktionen ohne Netzwerk, Telemetrie, Fremdcode, Cloudkonto oder Zugriff außerhalb des Projektroots. | SR-GOAL-0004, SR-GOAL-0005, SR-GOAL-0008 |
| SR-NEED-0012 | Maintainer und Integrator | Maintainer benötigen klar versionierte Modelle, Regeln, Schemas, Formate und kompatible, dependency-freie Distributionen. | SR-GOAL-0004, SR-GOAL-0008, SR-GOAL-0009 |
| SR-NEED-0013 | Authoring- und Transaktionsnutzer | Schreibende Nutzer benötigen einheitliche Dry-Runs, atomare Veröffentlichung, Recovery, Audit und wiederholbare Operationen. | SR-GOAL-0009, SR-GOAL-0010 |
| SR-NEED-0014 | Bestands- und Austauschdaten | Nutzer langlebiger Projekte benötigen Schema-Migration, Bundles und verlustbewussten Austausch über ReqIF, CSV und NDJSON. | SR-GOAL-0008, SR-GOAL-0009, SR-GOAL-0010 |
| SR-NEED-0015 | Dokument- und Berichtsnutzer | Leser und Autoren benötigen komponierte Dokumente, deklarative Ansichten, HTML/Markdown/CSV und deterministische Diagrammquellen. | SR-GOAL-0001, SR-GOAL-0007, SR-GOAL-0010 |
| SR-NEED-0016 | Parallel- und Integrationsnutzer | Ein einzelner Nutzer benötigt kollisionsresistente Identitäten, semantischen Branch-Merge, Code-Traceability und aktuelle Relationsreviews. | SR-GOAL-0003, SR-GOAL-0004, SR-GOAL-0009 |
| SR-NEED-0017 | Nutzer kurzlebiger KI-Runtimes | Ein Nutzer benötigt unabhängige CLI-Aufrufe, überprüfbare Startvoraussetzungen und Fortsetzung aus erhaltenen Projektdateien nach Prozess-, Pfad- oder Sandboxwechsel. | SR-GOAL-0004, SR-GOAL-0005, SR-GOAL-0008, SR-GOAL-0009 |
| SR-NEED-0018 | Nutzer begrenzter Rechenressourcen | Ein Nutzer benötigt schnelle Starts, sparsame CPU-/Speicher-/I/O-Arbeit und adaptive Fortsetzung bei weichen Budgetüberschreitungen ohne Abschwächung fachlicher Prüfergebnisse. | SR-GOAL-0002, SR-GOAL-0008, SR-GOAL-0009, SR-GOAL-0010 |
| SR-NEED-0019 | Nutzer großer KI-Arbeitsaufträge | Der vollständige Auftrag soll trotz kleiner Ausführungsfenster über mehrere CLI-Aufrufe und erforderlichenfalls mehrere Chat-Prompts erledigbar bleiben; Fortschritt, offene Arbeit, Grenzen und notwendige Freigaben bleiben nachvollziehbar. | SR-GOAL-0004, SR-GOAL-0005, SR-GOAL-0009, SR-GOAL-0010 |
| SR-NEED-0020 | Mehrsprachige Autoren und Reviewer | Anforderungen benötigen explizite Sprachen, sprachunabhängige Verbindlichkeit, nachvollziehbare Mischungsregeln und verlustfreien Austausch ohne Voraussetzung installierter Ubuntu-Locales. | SR-GOAL-0001, SR-GOAL-0002, SR-GOAL-0008, SR-GOAL-0010 |
| SR-NEED-0021 | Analyzer-Nutzer und Integratoren | Unterschiedliche Analyzer sollen gebundene Statements und Kontextdaten auswerten können; der erste reale Adapter erkennt mit py3langid die Sprache, ohne Fachinhalte zu ändern oder Sprachverständnis vorzutäuschen. | SR-GOAL-0002, SR-GOAL-0005, SR-GOAL-0008, SR-GOAL-0009 |

---

## 5. Leitende Nutzungsszenarien

| ID | Szenario | Erwartetes Ergebnis |
|---|---|---|
| SR-SCN-0001 | Projekt initialisieren | Ein Autor initialisiert in einem leeren oder bestehenden Git-Repository ein SpecRoad-Projekt und erhält eine gültige, sofort validierbare Grundstruktur. |
| SR-SCN-0002 | Anforderung erfassen | Ein Autor erzeugt eine Anforderung, ergänzt Quelle, Begründung, strukturierte Semantik und Verifikation und lässt sie validieren. |
| SR-SCN-0003 | Qualitätsfehler erkennen | SpecRoad meldet eine mehrdeutige oder unvollständige Anforderung mit ID, Pfad, Regel, Begründung und Reparaturhinweis. |
| SR-SCN-0004 | Traceability erklären | Ein Reviewer fragt ab, warum eine Anforderung existiert, wovon sie abhängt und welche Dokumente, Code-Referenzen, Tests, Tasks und Releases betroffen sind. |
| SR-SCN-0005 | Änderung vergleichen | Ein Reviewer vergleicht Arbeitsstand, Baseline, Bundle oder Git-Ref und erhält strukturellen und semantischen Diff samt Impact. |
| SR-SCN-0006 | Release Readiness prüfen | Ein Release-Verantwortlicher erzeugt einen Bericht über Freigaben, Umsetzung, Relationsreviews, Coverage, Evidence, Code-Referenzen, Risiken und Blocker. |
| SR-SCN-0007 | Evidence veraltet | Nach Änderung eines Subjects erkennt SpecRoad, dass frühere Evidence nicht mehr zur aktuellen Revision passt. |
| SR-SCN-0008 | Baseline erzeugen | Ein Requirements Engineer erzeugt eine unveränderbare Baseline und kann ihre Integrität später ohne Checkout prüfen. |
| SR-SCN-0009 | KI-Vorschlag prüfen | Ein KI-Agent erzeugt über die CLI ein Proposal; SpecRoad wendet es in einem isolierten Workspace an und liefert Diff, Impact und Diagnosen. |
| SR-SCN-0010 | KI-Vorschlag übernehmen | Nach menschlicher Freigabe wird ein weiterhin aktuelles Proposal transaktional angewendet, ohne automatisch einen Git-Commit zu erzeugen. |
| SR-SCN-0011 | CI-Gate | Eine CI-Pipeline validiert und lintet nichtinteraktiv und entscheidet anhand stabiler Exit Codes und JSON-/SARIF-Ausgaben. |
| SR-SCN-0012 | Spezifikation rendern | SpecRoad erzeugt aus denselben Eingaben byte-identische Markdown- und HTML-Ansichten. |
| SR-SCN-0013 | Chatbot-Sandbox-Roundtrip | Ein Nutzer exportiert ein portables SpecRoad-/Projekt-/PatchHarbor-Paket, öffnet es in einer isolierten Python-Umgebung und lässt die KI einen Proposal über die CLI vorbereiten. Derselbe Exportbefehl liefert ein an das ursprüngliche Result gebundenes Rückpaket; die lokale Übernahme führt über echte menschliche Prüfung und transaktionales Proposal-Apply. |
| SR-SCN-0014 | Bestehendes Artefakt direkt bearbeiten | Ein menschlicher Nutzer prüft mit Dry-Run eine Änderung, aktualisiert ein Requirement und erhält Auditbericht, Diff und neue Modellwurzel. |
| SR-SCN-0015 | Parallel neue Artefakte erzeugen | Lokaler Branch und Chatbot-Sandbox erzeugen unabhängig neue Artefakte, ohne eine zentrale ID-Sequenz und ohne Identitätskollision. |
| SR-SCN-0016 | Prozessabbruch wiederherstellen | Ein Prozess endet während einer Mehrdateiänderung; der nächste Zugriff stellt deterministisch Basis oder vollständiges Ziel wieder her. |
| SR-SCN-0017 | Projekt migrieren | Ein Nutzer plant und prüft die Migration eines 0.1-Projekts, erzeugt ein Sicherungsbundle und migriert verlustfrei auf 0.2. |
| SR-SCN-0018 | Suspect Relation prüfen | Nach einer Anforderungsänderung markiert SpecRoad abhängige Beziehungen als suspect; ein Reviewer bestätigt oder verwirft sie. |
| SR-SCN-0019 | Dokument komponieren | Ein Autor ordnet Prosa, Requirements, Queries und Tabellen in Abschnitten an und rendert ein zielgruppengerechtes Dokument. |
| SR-SCN-0020 | ReqIF austauschen | Ein Nutzer importiert ein ReqIFZ, prüft Mapping und Verluste, bearbeitet die Daten und exportiert den darstellbaren Schnittmengeninhalt erneut. |
| SR-SCN-0021 | Testergebnisse übernehmen | Eine CI liefert JUnit oder SARIF; SpecRoad importiert gemappte Ergebnisse als hashgebundene Evidence und meldet ungemappte Tests. |
| SR-SCN-0022 | Quellcode verknüpfen | Ein Requirement wird mit einem Codebereich verknüpft; nach einer Codeänderung erkennt SpecRoad aktuelle, relokalisierte oder stale Referenzen. |
| SR-SCN-0023 | Eigene Sicht erzeugen | Ein Nutzer definiert eine deklarative View und erzeugt daraus Markdown, HTML, CSV, JSON und eine deterministische Diagrammquelle. |
| SR-SCN-0024 | Branches semantisch mergen | Ein Nutzer plant einen Dreiwege-Merge, übernimmt unabhängige Feldänderungen automatisch, löst Konflikte explizit und wendet den validierten Plan an. |
| SR-SCN-0025 | Agent erkundet und wiederholt sicher | Ein Agent liest Capabilities, Schemas und Befehlsverträge, führt einen Request mit stabiler ID aus und erhält bei einem Retry dasselbe Ergebnis ohne Doppeländerung. |
| SR-SCN-0026 | Produktkonfiguration ableiten | Ein Nutzer wählt eine benannte Konfiguration; SpecRoad berechnet den gültigen Modellumfang, prüft Abhängigkeiten und erzeugt konfigurationsgebundene Dokumente, Coverage und Baselines. |
| SR-SCN-0027 | Unabhängige Aufrufe und Pfadwechsel | Zwei Aufrufe verwenden neue Prozesse und geänderte Arbeitsverzeichnisse; die explizite Root-Auswahl führt ohne Sitzungszustand zum identischen fachlichen Ergebnis. |
| SR-SCN-0028 | Sandbox aus Sicherungsstand ersetzen | Distribution und verifiziertes Vollbundle werden in eine frische kompatible Sandbox übertragen; Modellwurzel und idempotente Requests bleiben erhalten, ungesicherte Verluste werden nicht erfunden. |
| SR-SCN-0029 | Preflight bei Recoverybedarf | Ein lesender Aufruf meldet die unterbrochene Transaktion schreibfrei; zulässige Recovery stellt einen belegten Zustand her, bevor die Fachoperation erneut angefordert wird. |
| SR-SCN-0030 | Weiches Budget überschritten | Der Gesamtauftrag läuft mit kleineren Chargen weiter oder liefert einen gesicherten Fortsetzungspunkt; bei tatsächlichem Hostabbruch bleibt Recovery wirksam. |
| SR-SCN-0031 | Cache fehlt oder ist veraltet | Fehlender, gelöschter, manipulierter und aus einer anderen Runtime übernommener Cache führen zu denselben vollständigen Ergebnissen wie ein cachefreier Lauf. |
| SR-SCN-0032 | Umgebung und tatsächlicher Verbrauch | Ein Agent liest die begrenzte Umgebungsdiagnose und fordert explizite Messwerte an; unbekannte Hostquoten bleiben unbekannt, Startkosten und Ressourcenverbrauch werden im Referenztest gemessen. |
| SR-SCN-0033 | Vollständig trotz weichem Budget | Ein endlicher großer Auftrag überschreitet Arbeitsziele, wird sparsam aufgeteilt und erreicht ohne ausgelassene Pflichtarbeit dasselbe Ergebnis wie ein Einzellauf. |
| SR-SCN-0034 | Fortsetzung über mehrere Prompts | Ein extern gesichertes Arbeitspaket wird in einer neuen kompatiblen Sandbox über den generierten Fortsetzungsauftrag vollständig beendet. |
| SR-SCN-0035 | Prompt und Actor bleiben kontrolliert | Ein manipulierter Fortsetzungstext oder eine fehlende menschliche Freigabe darf keine zusätzlichen Schreibrechte erzeugen. |
| SR-SCN-0036 | Wiederholung und veränderte Zielbasis | Ein Retry nach verlorenem Ergebnis wird idempotent beendet; eine geänderte Basis wird dagegen ohne stilles Rebase zurückgewiesen. |
| SR-SCN-0037 | Historische Nachweise unverändert migrieren | Eine 0.1-Migration erhält Evidence- und Baseline-Bytes und weist nicht aktuell belegte 0.2-Verification ausdrücklich aus. |
| SR-SCN-0038 | Merge- und Proposal-Verträge durchgängig | Policygebundener Merge und vollständiger Proposal-Lifecycle erzeugen eindeutige Revisionen, Inhaltsbindungen und Reihenfolgen. |
| SR-SCN-0039 | Mehrsprachig authoren | Requirement-Sachverhalte der Mindestsprachen ohne modales Schlüsselwort speichern; explizite Sprache und Verbindlichkeit bleiben erhalten. |
| SR-SCN-0040 | Sprachpolicy anwenden | Erlaubte Sprachen und Mischungen getrennt nach Projekt, Dokument und Abschnitt als allow, warning oder error behandeln. |
| SR-SCN-0041 | Sprachen tatsächlich erkennen | Den ausgelieferten py3langid-Adapter auf gebundene Einzelstatements anwenden und erkannte Grundsprachen getrennt von Script und Region anzeigen. |
| SR-SCN-0042 | Unsicherheit und Fehlkennzeichnung | Kurzen, gemischten und anderssprachigen Text ohne gefälschte Sicherheit oder automatische Metadatenänderung behandeln. |
| SR-SCN-0043 | Mehrere Analyzer austauschen | Einen generischen Request exportieren, externe unterschiedliche Findings importieren und je Analyzer samt Aktualitätsbindung anzeigen. |
| SR-SCN-0044 | Core ohne Zusatzpakete | Ohne NumPy und py3langid alle Core-Operationen nutzen; angeforderte Detektion meldet unavailable statt Erfolg. |
| SR-SCN-0045 | Analyzerarbeit fortsetzen | Vollständige Subjectmenge mit kleinen weichen Budgets über mehrere Prozesse und einen portablen Work-Roundtrip auswerten. |
| SR-SCN-0046 | Entwurfsmetadaten migrieren | Alte Anforderungen mit explizitem Sprach-/Verbindlichkeitsmapping migrieren, historische Nachweise unverändert erhalten und SRX-Präzision projektgebunden auswerten. |

---

## 6. Architektur- und Produktentscheidungen

| ID | Entscheidung | Festlegung |
|---|---|---|
| SR-DEC-0001 | Kanonisches JSON-Modell | Normative semantische Projektdaten werden als versioniertes JSON gespeichert. Markdown, HTML, CSV und Diagrammquellen sind generierte Sichten. |
| SR-DEC-0002 | Ein Artefakt pro Datei | Jedes Artefakt wird in einer eigenen Datei gespeichert, um Diffs, Reviews und konfliktarme Änderungen zu ermöglichen. |
| SR-DEC-0003 | Stabile, branchfähige Identitäten | Neue Artefakte und Beziehungen erhalten 128-Bit-Zufallsidentitäten; migrierte Legacy-IDs bleiben unverändert. |
| SR-DEC-0004 | Getrennte Statusdimensionen | Reifegrad, Umsetzung, Verifikation sowie berechnete Aktualitäts- und Relationsreviewzustände werden getrennt modelliert. |
| SR-DEC-0005 | Gerichtete typisierte Beziehungen | Beziehungen besitzen Richtung, eigene ID und definierte Quell-/Zieltypen; inverse Sichten und Reviewstatus werden berechnet. |
| SR-DEC-0006 | Deterministische Prüfung vor KI | Schema-, Typ-, Referenz-, Lifecycle-, Regel-, Merge- und Migrationseigenschaften funktionieren vollständig ohne KI. |
| SR-DEC-0007 | KI nur über Proposals | KI-Änderungen werden als versionierte Proposals mit erwarteter Basis, Change Plan, Quellen und Review-Historie behandelt. |
| SR-DEC-0008 | Keine beliebige Codeausführung | Der Core führt weder Projektcode, Buildskripte, Templates, Plugins noch externe Renderer aus. |
| SR-DEC-0009 | Offline-Kern | Alle Kernfunktionen sind lokal, initiieren keine Netzwerkverbindung und erfassen keine Telemetrie. |
| SR-DEC-0010 | Deklarative Profile | Profile verschärfen Felder, Werte, Relations- und Lintregeln deklarativ und enthalten keinen ausführbaren Code. |
| SR-DEC-0011 | Kanonische Hashes | JSON-Inhalte verwenden RFC 8785 und SHA-256; Dateien und Anhänge werden über unveränderte Bytes gehasht. |
| SR-DEC-0012 | Kein eingebautes Sprachmodell | Version 0.2 stellt Agenten- und Proposal-Verträge bereit, enthält aber keinen LLM-Client und keinen MCP-Server. |
| SR-DEC-0013 | Linux als Referenzplattform | Die verbindliche Abnahme erfolgt auf Linux x86-64; Datenmodell und Austauschformate bleiben plattformneutral. |
| SR-DEC-0014 | Keine automatische Git-Historie | SpecRoad liest Git-Refs, erzeugt aber weder Commits noch Branches, Tags oder Pushes. |
| SR-DEC-0015 | Reines, nichtinteraktives CLI | Die CLI ist die einzige verbindliche Bedienoberfläche des Core; jede Kernfunktion ist ohne TTY, Menü oder Rückfrage vollständig parametrierbar. |
| SR-DEC-0016 | Python 3.10 als Mindestlaufzeit | Der Core wird in Python implementiert und bleibt unter CPython 3.10 ausführbar. |
| SR-DEC-0017 | Keine externen Core-Laufzeitabhängigkeiten | Nicht Git-spezifische Kernfunktionen benötigen nur eine unterstützte Python-Laufzeit, die ausgelieferten Dateien und Dateisystemzugriff. |
| SR-DEC-0018 | Zwei portable Distributionen | Jedes Release liefert eine entpackbare Modul-Distribution und eine funktional äquivalente Python-Zipapp. |
| SR-DEC-0019 | Single-User und Single-Repository | Version 0.2 verwaltet pro Projekt genau einen Root und eine Projekt-ID und setzt weder Server noch Benutzerverwaltung oder Multi-Repository-Graph voraus. |
| SR-DEC-0020 | Einheitlicher Change Plan | Direkte CLI-Änderungen, Proposals, Importe, Migrationen und Merges werden auf dasselbe versionierte Operationsmodell abgebildet. |
| SR-DEC-0021 | Journalbasierte Recovery | Mehrdateiänderungen werden über Write-ahead-Journal, Staging, Before Images und deterministische Recovery veröffentlicht. |
| SR-DEC-0022 | Explizite Schema-Evolution | Projektformate werden nur über versionierte, geplante und verifizierbare Migrationen verändert. |
| SR-DEC-0023 | Suspect Relations | Relationsreviews binden sich an den Relationsinhalt und reviewrelevante Kontextprojektionen beider Endpunkte; relevante Änderungen machen frühere Reviews automatisch suspect. |
| SR-DEC-0024 | SRX statt Skriptregeln | Profile und Views verwenden die begrenzte JSON-AST-Sprache SRX 1.0 ohne Regex, I/O oder Fremdcode. |
| SR-DEC-0025 | Dokumentmodell als Komposition | Dokumente, Abschnitte und Inhaltsblöcke ordnen vorhandene Artefakte, ohne deren normative Inhalte zu duplizieren. |
| SR-DEC-0026 | Offene Austauschformate | Der Core unterstützt ReqIF 1.2/ReqIFZ, RFC-4180-CSV und NDJSON mit explizitem Mapping und Verlustbericht. |
| SR-DEC-0027 | Evidence-Import ohne Testausführung | Evidence-Import startet weder Tests noch Analyzer. Die gesonderte explizite Analyzer-Ausführung folgt ausschließlich Anhang T und erzeugt nicht automatisch Evidence. |
| SR-DEC-0028 | Sprachneutrale Code-Traceability | Code-Referenzen binden Pfade und Hashes; sprachspezifische Resolver gehören nicht zum Core. |
| SR-DEC-0029 | Deklarative Views und Diagrammquellen | Berichte und Diagrammquellen werden deterministisch ohne ausführbare Templates oder externe Renderer erzeugt. |
| SR-DEC-0030 | Semantischer Dreiwege-Merge | Branches und Bundles werden anhand stabiler IDs und Feldsemantik zusammengeführt; Konflikte werden explizit gelöst. |
| SR-DEC-0031 | Maschinenlesbare Selbstbeschreibung und Idempotenz | Agenten können Capabilities, Schemas und Befehle abfragen; Request-Receipts verhindern Doppeländerungen. |
| SR-DEC-0032 | Konfiguration durch Gültigkeitsausdrücke | Produktvarianten innerhalb eines Repositorys werden als benannte Konfigurationen und SRX-basierte `applicability` modelliert; fachliche Artefakte werden nicht pro Variante kopiert. |
| SR-DEC-0033 | Versionierte Scope-Closure | Jeder Teilumfang wird durch einen kanonischen Scope Descriptor und einen kleinsten Fixpunkt statt durch implizite Dateiauswahl bestimmt. |
| SR-DEC-0034 | Deterministische Profilkomposition | Mehrere Profile werden durch einen geschlossenen Mergealgorithmus mit expliziten Konflikten und einem effektiven Profilhash aufgelöst. |
| SR-DEC-0035 | Getrennte Verifikationszustände | Nur der Verification Plan Status wird gespeichert; Verification Result und Coverage werden je Scope und Konfiguration berechnet. |
| SR-DEC-0036 | Typgebundene Spezial-Lifecycles | Proposal, Evidence, Baseline und Relationsreview koppeln ihren Spezialstatus deterministisch an `maturity` und umgehen keine Unveränderbarkeitsregeln. |
| SR-DEC-0037 | Abschließend klassifizierte CLI-Befehle | Normative Writes, generierte Ausgaben, Read-only-, lokale Betriebs- und Root-Erzeugungsbefehle besitzen die getrennten Options-, Lock- und Transaktionsverträge aus Kapitel 11.7. |
| SR-DEC-0038 | Partielle Bundles sind read-only | Dokument- und Release-Bundles dürfen deklarierte Grenzen besitzen, sind nach Extraktion jedoch kein schreibbares Vollprojekt. |
| SR-DEC-0039 | Ephemeral Runtime Safety | Jeder CLI-Aufruf ermittelt seine Voraussetzungen neu; Projekte und externe Work-Checkpoints benötigen keine fortbestehende Session. Vollverlust ist nur aus extern erhaltenen Daten rekonstruierbar. |
| SR-DEC-0040 | Resource-Constrained Runtime Design | Weiche Arbeitsziele steuern sparsame vollständige Verarbeitung; Überschreitungen führen zu adaptiver Fortsetzung, nicht zum Weglassen von Aufgaben oder zum automatischen Fehlerabbruch. |
| SR-DEC-0041 | Fortsetzbarer Gesamtauftrag | Große Fachaufträge werden durch externe gehashte Checkpoints vollständig über mehrere CLI-Aufrufe verarbeitet; kein Workflowfortschritt hängt ausschließlich an einer Chatbeschreibung. |
| SR-DEC-0042 | Weiche Arbeitsziele statt Budgetblockade | Ein weiches Ziel steuert Sparsamkeit und Teilung. Echte Sicherheits-/Hostgrenzen bleiben wirksam. Keine automatische Erfolgsmeldung für ausgelassene Arbeit. |
| SR-DEC-0043 | Inhaltsgebundene Proposal-Freigabe | Artefaktrevision und Inhaltsrevision sind getrennt; Kontrollwrites erhalten den freigegebenen Inhalt, tatsächliches Authoring invalidiert ihn. |
| SR-DEC-0044 | Unveränderbare historische Originale | Migration erhält geschützte Originalbytes; Legacy-Manifest und versionierter Leser ersetzen keine aktuelle Verification-Evidence. |
| SR-DEC-0045 | Language-Neutral Core | UTF-8-Fachtexte und BCP-47-Metadaten sind von Host-Locale und CLI-Anzeigesprache unabhängig. |
| SR-DEC-0046 | Explizite normative Stärke | Requirements speichern language und normative_force; Muss-/Verbot-/Soll-/Darf-Bedeutung wird nicht aus Freitext oder Priorität erraten. |
| SR-DEC-0047 | Deklaration ist nicht Detektion | Sprachpolicy prüft deklarierte Tags; Detektorbeobachtungen verändern weder Sprache noch Verpflichtungsart. |
| SR-DEC-0048 | Allgemeiner Analyzer-Datenvertrag | Versionierte Requests, Capabilities und Findings erlauben unterschiedliche Statements und Analysearten; externe Ergebnisse sind keine automatische Evidence. |
| SR-DEC-0049 | Erster ausführbarer py3langid-Adapter | py3langid gehört bereits zur ersten Implementierung, aber nur als optionale lokale Runtimekomponente; die Lieferung und Abnahme des Adapters sind verpflichtend. |
| SR-DEC-0050 | Kontrollierte Ausführungsgrenze | Nur ein vertrauenswürdiger ausgelieferter Worker ist automatisch startbar; generische externe Analyzer werden zunächst über Daten angebunden. |
| SR-DEC-0051 | Gebundene vollständige Analyzerarbeit | Modell-, Engine-, Input- und Scorepolicybindungen sowie explizite Coverage gewährleisten nachvollziehbare Fortsetzung ohne stilles Sampling. |
| SR-DEC-0052 | Explizite SRX-Zahlenpolicy | Projektgebundene signifikante Dezimalpräzision mit Default 34 und exakten Fehlerzuständen ersetzt den impliziten Python-Prozessdefault. |
| SR-DEC-0053 | Portabler Rundweg mit PatchHarbor | SpecRoad verantwortet Projektmodell und Proposalprüfung; PatchHarbor verantwortet Transportbindung und lokale Paketübernahme. Integration ausschließlich über die öffentliche Python-API, mit mitgelieferter kompatibler Runtime und getrenntem äußerem Hinpaket nach Anhang W. |

Die Entscheidungen begrenzen den Implementierungsspielraum, ersetzen aber keine Produktanforderung. Ein Konflikt zwischen einer Entscheidung und einer Anforderung wird nach Kapitel 2.1 zugunsten der Anforderung aufgelöst. Die Entscheidungen `SR-DEC-0016` bis `SR-DEC-0018` reduzieren keinen Standardvertrag: JSON-Schema-Prüfung, Canonicalization, ReqIF-/XML-Verarbeitung, SARIF, ZIP, Migration und Merge müssen innerhalb der ausgelieferten Python-Distribution implementiert werden.

---

## 7. Zielarchitektur und Vertrauensgrenzen

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Mensch · CI · externer KI-Agent                                     │
│ dieselbe nichtinteraktive CLI · JSON/SARIF · stdin/stdout/stderr    │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Application Layer                                                   │
│ Authoring · Documents · Views · Import/Export · Migration · Merge   │
│ Proposal · Baseline · Bundle · Release · Evidence                   │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Unified Change Plan                                                 │
│ Operations · Preconditions · Dry-Run · Diff · Impact · Validation   │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Transaction Engine                                                  │
│ Writer Lock · Journal · Staging · Before Images · Commit · Recovery │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌──────────────────────────────┐    ┌─────────────────────────────────┐
│ Validation / SRX Engine      │    │ Graph / Query / Diff / Merge    │
│ Schema · Types · Rules       │    │ Trace · Suspect · Coverage      │
└─────────────────────┬────────┘    └──────────────────┬──────────────┘
                      └──────────────┬─────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Canonical Specification Model                                       │
│ Artifacts · Relations · Documents · Configurations · Evidence       │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ JSON · Attachments · Git · Archive Objects · Generated Views        │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.1 Schreibpfad

Jeder normative Schreibweg verwendet dieselbe Reihenfolge:

```text
CLI-Eingabe oder Proposal/Import/Migration/Merge
        ↓
normalisieren und Akteur/Request-ID binden
        ↓
Change Plan erzeugen
        ↓
Vorbedingungen und Basis prüfen
        ↓
isolierten Zielstand berechnen
        ↓
vollständig validieren, linten, diffen, Impact bestimmen
        ↓
Dry-Run zurückgeben ODER Writer-Lock erwerben
        ↓
Journal + Staging + Before Images erzeugen
        ↓
prepared → committing → committed
        ↓
Audit- und Request-Receipt schreiben
```

Vor dieser Folge gelten der aufrufbezogene Preflight aus Anhang N und die Betriebsbudgets aus Anhang O. Ein gefundener Recoverybedarf wird nicht durch einen zusätzlichen normalen Schreiblauf verdeckt.

Direkte JSON-Bearbeitung durch externe Editoren ist technisch nicht verhindert. Sie gilt jedoch nicht als SpecRoad-Authoring-Operation, besitzt keinen Audit- oder Transaktionsnachweis und muss vor jeder weiteren kontrollierten Änderung vollständig validiert werden. KI-Agenten dürfen normative Managed-Path-Dateien nach dem Produktvertrag nicht direkt verändern.

### 7.2 KI-Vertrauensgrenze

```text
KI fragt Capabilities, Schemas und Command Contracts ab
        ↓
KI liest Projektmodell und Diagnosen
        ↓
KI erzeugt Proposal über CLI mit stabiler Request-ID
        ↓
SpecRoad validiert und checkt in isoliertem Workspace
        ↓
Mensch reviewt exakte Inhaltsrevision, Inhaltshash, Plan und Basis
        ↓
SpecRoad wendet den Change Plan transaktional an
```

Formale Gültigkeit bedeutet nicht fachliche Richtigkeit. Eine KI-Review zählt nicht als menschliche Freigabe. Eine KI-Aussage ersetzt weder Verification Contract noch Evidence.

### 7.3 Sicherheitsgrenze

Der Core darf:

- Dateien innerhalb des Projektroots und expliziter Ausgabeziele lesen oder schreiben;
- Git-Objekte über dokumentierte Git-Befehle lesen, wenn eine Git-spezifische Funktion angefordert wurde;
- ausschließlich bei `analyzer run` den vertrauenswürdigen mitgelieferten py3langid-Worker nach Anhang T starten;
- ZIP-, XML-, JSON-, CSV- und Textdaten innerhalb expliziter Sicherheits-/Formatgrenzen und mit adaptiven weichen Arbeitsbudgets parsen;
- eigene temporäre Workspaces innerhalb konfigurierter Pfade erzeugen.

Der Core darf nicht:

- Netzwerkverbindungen initiieren;
- Shellcode, Projektcode, Templates, Plugins oder Anhänge ausführen;
- Symlinks oder Archivpfade außerhalb erlaubter Roots folgen;
- externe Renderer, Browser, Compiler, Testtools oder Language Server starten;
- mehrere Projektroots in ein kanonisches Modell mischen.

---

### 7.4 Aufrufbezogene Runtime- und Ressourcensteuerung

Der Einstiegspunkt durchläuft den Bootstrap mit Budgetinitialisierung und anschließend den befehlsspezifischen Preflight, bevor die benötigten Fachmodule geladen werden. Der Preflight benutzt nicht selbst die gesamte Validation-/Rendering-/Index-Pipeline. Er bleibt auch für Diagnose und Hilfe nutzbar, wenn das Projekt nicht bearbeitbar ist. Die genauen Profile und Recovery-Ausnahmen stehen in Anhang N.

Betriebliche Budgets sind weiche Arbeitsziele über die gesamte Verarbeitung einschließlich Zielvalidierung und Ausgabe. Sie sind keine fachlichen Filter. Bei Überschreitung werden Puffer, Chargen und optionale Beschleuniger reduziert; ein großer Auftrag bleibt über Checkpoints vollständig fortsetzbar. Tatsächliche Host-/Sicherheitsfehler folgen dem Recoveryvertrag. CPU-/Speicherbeobachtung benötigt keine zusätzlichen Programme, Dienste oder Pakete.

Ein persistenter Cache ist lediglich eine optionale Beschleunigung; Transaktionsdaten und Receipts gehören nicht zum Cache. Ein read-only Aufruf erzeugt weder einen Cache noch ein Recovery-Write. Vorhandene fachlich notwendige Arbeit wird nicht ausgelassen, nur weil ein Befehl klein aussieht: beispielsweise benötigen eingehende Relationen einen nachweislich vollständigen Index oder die entsprechenden aktuellen Quelldaten.

---

## 8. Repository- und Dateimodell

### 8.1 Standardstruktur

```text
specroad-project/
├── specroad.json
├── spec/
│   ├── goals/
│   ├── needs/
│   ├── capabilities/
│   ├── requirements/
│   ├── scenarios/
│   ├── decisions/
│   ├── risks/
│   ├── assumptions/
│   ├── components/
│   ├── interfaces/
│   ├── sources/
│   ├── verifications/
│   ├── tests/
│   ├── evidence/
│   ├── releases/
│   ├── milestones/
│   ├── tasks/
│   ├── terms/
│   ├── proposals/
│   ├── baselines/
│   ├── issues/
│   ├── documents/
│   ├── sections/
│   ├── content-blocks/
│   ├── views/
│   ├── code-refs/
│   ├── relation-reviews/
│   └── configurations/
├── profiles/
├── rules/
├── mappings/
├── attachments/
├── archive/
│   └── objects/
├── generated/
└── .specroad/
    ├── cache/
    ├── locks/
    ├── tmp/
    ├── transactions/
    │   └── receipts/
    ├── requests/
    ├── merge/
    └── recovery/
```

`specroad.json`, JSON-Dateien unter `spec/`, `profiles/`, `rules/` und `mappings/` sowie referenzierte Payloads unter `attachments/` bilden den aktuellen normativen Projektstand. `archive/objects/` enthält unveränderbare content-addressierte Snapshotobjekte. `generated/` enthält abgeleitete Sichten. `.specroad/` enthält nicht fachlich normative Betriebsdaten. Cache und reine Arbeitsreste sind entbehrlich; aktive Journale, Staging und Before Images sind dagegen wiederherstellungskritisch und bis zum belegten Abschluss zu erhalten. Abgeschlossene Transaktions- und Request-Receipts sind audit- und idempotenzrelevant und werden im Vollbundle nach Kapitel 10.16 transportiert. Die pauschale Löschung von `.specroad/` ist kein zulässiger Cache-Reset.

### 8.2 Beispielkonfiguration

```json
{
  "schema_version": "0.2.0",
  "project_id": "specroad",
  "project_name": "SpecRoad",
  "id_prefix": "SR",
  "default_locale": "de-DE",
  "managed_paths": [
    "spec",
    "profiles",
    "rules",
    "mappings",
    "attachments",
    "archive"
  ],
  "profiles": [
    "core@0.2.0",
    "software-de@0.2.0"
  ],
  "generated_path": "generated",
  "transaction_policy": {
    "auto_recover": true,
    "retain_receipts": true
  },
  "resource_limits": {
    "artifact_file_bytes": 1048576,
    "model_bytes": 104857600,
    "relation_count": 50000,
    "trace_depth": 10,
    "diagnostic_count": 10000,
    "query_default_limit": 100,
    "query_result_count": 10000,
    "xml_depth": 128,
    "archive_uncompressed_bytes": 536870912,
    "srx_nodes": 10000,
    "srx_operations": 1000000
  },
  "validation_policy": {
    "fail_on": "error",
    "minimum_human_proposal_approvals": 1,
    "required_relation_review": "current"
  },
  "language_policy": {
    "version": "language-policy-v1",
    "default_language": "de-DE",
    "allowed_ranges": [
      "*"
    ],
    "disallowed_language": "error",
    "unverified_registry": "warning",
    "unspecified_language": "error",
    "mixed_languages": {
      "comparison": "primary_language",
      "project": "allow",
      "document": "warning",
      "section": "warning"
    }
  },
  "language_packages": [
    "de@1.0.0",
    "en@1.0.0",
    "hi@1.0.0",
    "id@1.0.0",
    "pt@1.0.0",
    "es@1.0.0",
    "ru@1.0.0",
    "ja@1.0.0",
    "zh-Hans@1.0.0"
  ],
  "analyzer_policy": {
    "language_detection": {
      "adapter": "specroad.py3langid",
      "adapter_version": "1.0.0",
      "mismatch": "warning",
      "undetermined": "info",
      "compatible_coarse": "info",
      "unverifiable": "info",
      "min_text_codepoints": 20,
      "min_score": "0.900000000000",
      "min_margin": "0.100000000000"
    }
  },
  "srx_policy": {
    "numeric_policy_version": "srx-decimal-v1",
    "decimal_precision": 34
  }
}
```

Die Beispielkonfiguration zeigt Fachpolicies; konkrete Hashbindungen des vom Release gelieferten Sprachregisters und der Pakete materialisiert `init`. Sprachdaten und Labelpakete sind nicht ausführbare Profilressourcen. Analyzerberichte liegen nur bei expliziter Ausgabe unter `generated/analysis/` oder einem ausdrücklich gewählten externen Ziel und bilden keine neue normative Datenbank.

### 8.3 Pfadklassen

| Pfadklasse | Normativ | Schreibweise | Verhalten |
|---|---:|---|---|
| Projektkonfiguration | ja | `specroad.json` | Genau eine Datei im Projektroot |
| Artefakte | ja | `spec/<type-dir>/<ID>.json` | Ein Artefakt pro Datei |
| Profile, Regeln, Mappings | ja | versionierte JSON-Ressourcen | Keine Traceability-Artefakte |
| Anhänge | als referenzierte Bytes | `attachments/**` | Pfad, Größe, Medientyp und Hash sind normativ |
| Archivobjekte | unveränderbar | `archive/objects/<hh>/<sha256>` | Nur über Baseline-/Bundle-Verträge |
| Generierte Ausgaben | nein | `generated/**` | Keine Rückübernahme in das Modell |
| Entbehrlicher Cache | nein | `.specroad/cache/**` | optional, inhaltsgeprüft, jederzeit löschbar; keine Recoveryfunktion |
| Wiederherstellungsdaten | betrieblich verbindlich | `.specroad/transactions/**`, `.specroad/recovery/**` | aktive Journale und Payloads bis zum belegten Abschluss schützen |
| Abgeschlossene Receipts | betrieblich verbindlich | `.specroad/requests/**`, `.specroad/transactions/receipts/**` | auditrelevant; im Vollbundle standardmäßig transportiert |
| Weitere Betriebsdaten | nein | übrige `.specroad/**` | Locks, kurzlebige Pläne und zulässige Arbeitsdaten nach ihrem jeweiligen Vertrag |

---

## 9. Kanonisches Metamodell

### 9.1 Artefakttypen und ID-Präfixe
| `artifact_type` | ID-Präfix | Bedeutung |
|---|---|---|
| goal | GOAL | Produktziel |
| need | NEED | Stakeholder-Bedarf |
| capability | CAP | Fähigkeit oder Feature |
| requirement | REQ | Normative Anforderung |
| scenario | SCN | Nutzungsszenario |
| decision | DEC | Architektur- oder Produktentscheidung |
| risk | RISK | Risiko |
| assumption | ASM | Annahme |
| component | COMP | Komponente |
| interface | IFC | Schnittstelle |
| source | SRC | Quelle |
| verification | VER | Verification Contract |
| test | TEST | Testreferenz |
| evidence | EVD | Prüfnachweis |
| release | REL | Release |
| milestone | MS | Milestone |
| task | TASK | Umsetzungsaufgabe |
| term | TERM | Glossarbegriff |
| proposal | PROP | Änderungsvorschlag |
| baseline | BASE | Unveränderbare Baseline |
| issue | ISSUE | Offener Punkt |
| document | DOC | Komponiertes Dokument |
| section | SEC | Dokumentabschnitt |
| content_block | BLOCK | Dokumentinhaltsblock |
| view | VIEW | Deklarative Sicht |
| code_ref | CODE | Quellcode-Referenz |
| relation_review | RREV | Relationsreview |
| configuration | CFG | Produktkonfiguration |

### 9.2 Identität

Für Artefakte gelten zwei ID-Schemata:

```text
random128-v1:
<PROJECT>-<TYPE>-<26 Crockford-Base32-Zeichen>
Erstes Tokenzeichen: 0..7

legacy-sequential-v1:
<PROJECT>-<TYPE>-<NNNN>

Relations-ID random128-v1:
REL-<26 Crockford-Base32-Zeichen>
Erstes Tokenzeichen: 0..7

Relations-ID derived128-v1 (nur Migration):
REL-<26 Crockford-Base32-Zeichen aus den ersten 128 SHA-256-Bits>
Erstes Tokenzeichen: 0..7
```

Neue Artefakte verwenden ausschließlich `random128-v1`. `legacy-sequential-v1` ist nur für unverändert migrierte Identitäten zulässig. Neue Beziehungen verwenden `random128-v1`; ausschließlich die Migration 0.1→0.2 darf reproduzierbare Relations-IDs nach `derived128-v1` bilden. Dokument-IDs dieser Spezifikation wie `SR-REQ-0231` sind redaktionelle Identifikatoren des Spezifikationsdokuments; bei späterer Überführung in ein ausführbares SpecRoad-Projekt dürfen sie als `display_id` oder External Identity erhalten werden.

### 9.3 Gemeinsame Artefaktfelder

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---:|---|
| `schema_version` | SemVer-String | ja | Formatversion des Artefakts |
| `id` | Artefakt-ID | ja | stabile projektweit eindeutige Identität |
| `id_scheme` | Enum | ja | `random128-v1` oder `legacy-sequential-v1` |
| `artifact_type` | Enum | ja | Kernartefakttyp |
| `title` | String | ja | kurzer menschenlesbarer Titel |
| `language` | BCP-47-Tag | bei requirement, document und term | explizite Inhaltssprache nach Anhang S; andere texttragende Artefakte dürfen sie deklarieren |
| `text_direction` | `ltr`, `rtl` oder `auto` | nein | Darstellungsmetadatum, Default auto; keine aus Sprache erzwungene Richtung |
| `maturity` | Enum | ja | fachlicher Reifegrad oder gekoppelte Spezialreife nach 9.6 |
| `revision` | Integer >= 1 | ja | monotone Artefaktrevision |
| `created_at`, `updated_at` | RFC-3339 UTC | ja | im Change Plan gebundene Erstellungs- und Änderungszeit |
| `created_by`, `updated_by` | Actor | ja | im Change Plan gebundener Akteur |
| `owner` | String oder Actor-Ref | typabhängig | verantwortliche Rolle |
| `tags` | String-Array | nein | Klassifikation |
| `applicability` | SRX-Expression | nein | konfigurationsabhängige Gültigkeit |
| `relations` | Relation-Array | ja | gerichtete typisierte Beziehungen |
| `provenance` | Provenance-Array | typabhängig | Herkunft |
| `external_identities` | External-Identity-Array | nein | externe, importgebundene Identitäten |
| `extensions` | Object | ja | namespaced Erweiterungsdaten |

Die Tabelle 9.3 gilt für reguläre 0.2-Artefakte. Unveränderbare Legacy-Ressourcen bleiben unter ihrer ursprünglichen unterstützten Schema-Version gespeichert und werden ausschließlich durch Anhang Q eingebunden. Abgeleitete Pflichtfeldprojektionen werden weder in ihre Originaldatei geschrieben noch als Originalnachweis ausgegeben.

### 9.4 Typspezifische Mindestfelder

| Artefakttyp | Pflicht beim ersten speicherbaren Zustand | Zusätzliches Freigabe- oder Unveränderbarkeitsgate |
|---|---|---|
| `goal` | `statement`, `owner` | für `approved` mindestens ein messbares `success_criterion` |
| `need` | `stakeholder`, `statement`, `owner` | für `approved`: `rationale`, `priority`, Beziehung zu einem Goal |
| `capability` | `description`, `owner`, `implementation_status`, `verification_plan_status` | für `approved`: `outcome`, `priority`, Herkunft |
| `requirement` | `requirement_kind`, `language`, `normative_force`, `statement`, `priority`, `criticality`, `implementation_status`, `verification_plan_status`; bei should außerdem Abweichungsbedingungen/-autorität | für `approved`: `rationale`, Herkunft, prüfbare Semantik, aktuelle Pflichtrelationen und `verified_by` |
| `scenario` | `actors`, `trigger`, `main_flow` | für `approved`: `preconditions`, `postconditions`, `exceptions` |
| `decision` | `context`, `decision`, `rationale`, `owner` | für `approved`: `alternatives`, `consequences` |
| `risk` | `description`, `probability`, `impact`, `risk_status`, `owner` | für `approved`: Mitigation oder begründete Akzeptanz |
| `assumption` | `statement`, `validation_status`, `owner` | für `approved`: `validation_method`, Neubewertungsbedingung |
| `component` | `description`, `responsibility`, `owner`, `implementation_status` | für `approved`: mindestens eine fachliche Relation |
| `interface` | `description`, `source_component`, `target_component`, `owner`, `implementation_status` | für `approved`: `contract` oder begründetes `contract_not_applicable` |
| `source` | `source_kind`, `title`, `locator`, `captured_at` | für `approved`: `content_sha256` oder unverändertes Excerpt |
| `verification` | Methode, Subjects, Vorbedingungen, Verfahren, Oracle, Evidence-Arten | für `approved`: vollständig prüfbarer Vertrag einschließlich `evidence_slots` nach 10.5.2 |
| `test` | Testidentität, Typ, Oracle | für `approved`: stabile externe oder interne Referenz |
| `evidence` | Ergebnis, Producer, Environment, Subjects, Origin, `run_context` nach 10.5.2, `evidence_state=recorded` | entsteht atomar mit `maturity=approved` und ist danach unveränderbar |
| `release` | Name, Ziel, Readiness-Policy nach 10.5.6 einschließlich dessen Legacy-Vertrag | für `approved`: genehmigter Scope Descriptor; eine Release-Baseline verlangt zusätzlich die gespeicherte `readiness_policy.verification_evaluation` nach 10.5.4 |
| `milestone` | Ziel, Owner, Release-Zuordnung | für `approved`: Done-Kriterien |
| `task` | Beschreibung, Owner, `implementation_status`, `verification_plan_status`, Done-Kriterien | für `approved`: Umsetzungsbeziehungen |
| `term` | Begriff, Definition, Sprache, Synonyme | für `approved`: Owner und freigegebene Terminologie |
| `proposal` | `proposal_status`, `content_revision`, `content_sha256`, `control_history`, Basis, Change Plan, Rationale | Status und `maturity` folgen 9.6; Freigaben binden den Fachinhalt nach 10.3; `applied` ist unveränderbar |
| `baseline` | Baseline-Art, Scope Descriptor, Manifest, Modellwurzel, `baseline_state=sealed` | entsteht atomar mit `maturity=approved` und ist danach unveränderbar |
| `issue` | Beschreibung, Status, Owner | für `approved`: Resolution Criteria oder begründeter Dauerstatus |
| `document` | Zweck, Zielgruppe, Sprache, `document_role`, Render-Policy | für `approved`: zyklusfreie Wurzelabschnitte über `contains` |
| `section` | Titel und genau eine eingehende `contains`-Relation | für `approved`: gültige Kind- und Blockordnung |
| `content_block` | Blockart und Payload nach 10.14 | für `approved`: alle Referenzen auflösbar |
| `view` | Scope Descriptor, SRX-Filter, Spalten, Sortierung, Formate | für `approved`: deterministische Ausgabedefinition |
| `code_ref` | Pfad, Referenzart, Datei-/Auswahlhashes | für `approved`: Zustand nach Anhang H berechenbar |
| `relation_review` | Relation, Endpunkthashes, Reviewer, Entscheidung, `review_state=recorded` | entsteht atomar mit `maturity=approved` und ist danach unveränderbar |
| `configuration` | Dimensionen, Auswahl, optionaler Parent | für `approved`: gültige Werte und zyklusfreie Vererbung |

### 9.5 Primitive und zusammengesetzte Kerntypen

| Typ | Normativer Vertrag |
|---|---|
| Actor | Objekt mit `actor_type = human\|ai\|ci\|tool` und nichtleerem `actor_id` |
| Artefakt-ID | Groß-/Kleinschreibung ist signifikant; Grammatik nach Kapitel 9.2 |
| Relation-ID | `REL-<TOKEN>` mit 128-Bit-Token nach `random128-v1` oder migriert nach `derived128-v1` |
| Hash | 64 kleingeschriebene Hexadezimalzeichen für SHA-256 |
| Relation | Objekt mit `relation_id`, `id_scheme`, `type`, `target`, `external_identities` und `extensions`; optional `rationale`, `created_at`, `created_by`; `contains` besitzt zusätzlich `position` |
| External Identity | Objekt nach Kapitel 10.12; an Artefakten und Relationen zulässig |
| Provenance | Quelle oder externer Locator, Zeitpunkt und mindestens Excerpt oder Hash |
| Confidence | JSON-Zahl im abgeschlossenen Intervall 0 bis 1 |
| Duration | ISO-8601-Duration oder Wert mit profilzulässiger UCUM-kompatibler Einheit |
| Revision | positive Ganzzahl; Revision 1 ist die erste gespeicherte Fassung |
| Formatversion | SemVer-kompatibler String ohne führendes `v` |
| Request-ID | String gemäß `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`; vom Aufrufer für einen normativen Schreibauftrag vergeben |
| Analysekennung (`AnalysisRequestId`) | String mit derselben Syntax, aber eigenständigem Analyse-Namensraum; Vergabe, Korrelation und Wiederaufnahme ausschließlich nach Anhang T.3, ohne Schreib-Receiptwirkung |
| Change-Plan-ID | `CP-` plus Token nach `random128-v1` |
| Change-ID | `CHG-` plus Token nach `random128-v1`; innerhalb eines Proposals stabil |
| Transaktions-ID | `TX-` plus Token nach `random128-v1` |
| Merge-Plan-ID | `MP-` plus Token nach `random128-v1` |
| Position | nichtnegative Ganzzahl; bei gleicher `position` ist die ID der deterministische Tie-Breaker |
| Scope Descriptor | Objekt nach Kapitel 10.8 |
| Boundary Reference | Objekt mit `source_id`, `relation_id` soweit vorhanden, `relation_type`, `target_id`, `target_type`, `reason` und `origin_target_sha256` |

### 9.6 Reifegrade und Spezial-Lifecycles

#### 9.6.1 Standardartefakte

Die allgemeine Tabelle gilt für alle Artefakttypen außer `proposal`, `evidence`, `baseline` und `relation_review`.

| Ausgang | Zulässige Ziele | Regel |
|---|---|---|
| `draft` | `proposed`, `rejected`, `retired` | erster Arbeitsstand |
| `proposed` | `draft`, `in_review`, `rejected`, `retired` | zur Prüfung vorgeschlagen |
| `in_review` | `draft`, `proposed`, `approved`, `rejected` | aktive fachliche Prüfung |
| `approved` | `proposed`, `superseded`, `retired` | Fachinhaltsänderung: `proposed`; reine Lifecycle-Operation: explizites Ziel nach 9.6.3 |
| `rejected` | `draft`, `retired` | ID bleibt reserviert |
| `superseded` | `retired` | durch Nachfolgeartefakt ersetzt |
| `retired` | — | Endzustand |

#### 9.6.2 Gekoppelte Spezialzustände

| Artefakttyp | Spezialstatus | Verbindliche `maturity` | Übergang/Unveränderbarkeit |
|---|---|---|---|
| `proposal` | `draft` | `draft` | authorierbar |
| `proposal` | `validated`, `checked` | `proposed` | Zwischenzustände der atomaren `proposal review start`-Kontrollfolge; Inhaltsänderungen erzeugen eine neue Inhaltsrevision |
| `proposal` | `in_review` | `in_review` | Reviews zulässig |
| `proposal` | `approved`, `applied` | `approved` | `applied` ist unveränderbar |
| `proposal` | `rejected` | `rejected` | Endstatus dieser Revision |
| `proposal` | `stale` | `retired` | Endstatus dieser Revision |
| `evidence` | `recorded` | `approved` | atomar erzeugt; vollständig unveränderbar |
| `baseline` | `sealed` | `approved` | atomar erzeugt; vollständig unveränderbar |
| `relation_review` | `recorded` | `approved` | atomar erzeugt; vollständig unveränderbar |

Ein direkter `lifecycle transition` auf einem Spezialartefakt ist unzulässig. Der Spezialbefehl setzt `maturity` atomar gemäß Tabelle.

#### 9.6.3 Eindeutige Inhalts- und Lifecycle-Nachbedingungen

Diese Regeln gelten je Standardartefakt und je vollständig gefaltetem Change Plan. „Semantische Änderung“ bleibt der Oberbegriff aus 2.2; nicht jede semantische Änderung ist eine **Fachinhaltsänderung**. Für diese Unterscheidung wird die Basis- mit der Zielprojektion des vollständigen Artefakts verglichen, wobei ausschließlich `revision`, `created_at`, `created_by`, `updated_at`, `updated_by` und `maturity` ausgeschlossen werden. Alle übrigen normativen Felder, insbesondere Titel, Aussage, Beziehungen, Herkunft, Owner, Gültigkeit, Planung und Extensions, gehören zum Fachinhalt. Reine Repräsentationsnormalisierung ist keine Wertänderung.

Ein reiner Lifecycle-Befehl verändert nur `maturity` und die von Anhang K abgeleiteten Revisions-/Akteurs-/Zeitmetadaten. Grund, Akteur, erwarteter Ausgang und gewünschtes Ziel werden in der gebundenen `transition`-/`retire`-Operation und ihrem Audit gespeichert, nicht als frei erfundene Fachfelder. Typspezifische Transition-Vorbedingungen, etwa die vorhandene Nachfolgerrelation bei `superseded`, bleiben vollständig wirksam.

| Basis und Operation für dasselbe Artefakt | Einziger zulässiger Endzustand |
|---|---|
| `approved`; ausschließlich zulässiger Übergang nach `retired` | `retired`; eine neue Revision; kein nachgeschalteter Reset |
| `approved`; ausschließlich zulässiger Übergang nach `superseded` | `superseded`; eine neue Revision; Nachfolger muss im vollständigen Ziel vorhanden sein |
| `approved`; ausschließlich expliziter Übergang nach `proposed` | `proposed`; eine neue Revision |
| `approved`; Fachinhaltsänderung ohne explizites anderes Ziel | `proposed`; eine neue Revision und dokumentierter Freigabeentzug |
| `approved`; Fachinhaltsänderung plus explizites Ziel `proposed` | `proposed`; genau eine Revision, nicht je Teiloperation eine |
| `approved`; Fachinhaltsänderung plus explizites Ziel ungleich `proposed`, auch `approved` | vor Veröffentlichung zurückweisen; CLI-Widerspruch Code 2, widersprüchlicher gespeicherter Plan Code 3 |
| reiner, wertgleicher No-op | unveränderte Bytes und Revision; keine fingierte Freigabe |

Ein allgemeiner Patch darf `maturity` nicht direkt setzen; der Writer verwendet die typisierte Transition oder die hier definierte abgeleitete Herabstufung. Gemischte Änderungen an **verschiedenen** Artefakten sind zulässig, etwa ein neues Nachfolgeartefakt und die reine Stilllegung des Vorgängers. Inhaltliche Änderung und erneute fachliche Freigabe desselben vormals freigegebenen Artefakts benötigen getrennte, jeweils gebundene Vorgänge. Für ein bereits `proposed` oder `in_review` vorliegendes Artefakt gelten Tabelle 9.6.1 und das vollständige Approval-Gate; ein freier Patch ersetzt kein Review.

Der Writer berechnet diese Nachbedingungen vor Ergebnis-Hash, Dry-Run und Autorisierung. Er ergänzt bei Apply keine zuvor unsichtbaren Statusänderungen. Mehrere Teiloperationen erhöhen die Revision derselben Identität nur einmal gemäß Anhang K. Migration und Merge behalten ihre ausdrücklich abweichende Metadatenpolicy; neu kombinierter Fachinhalt erhält keine geerbte Freigabe. Eine bytegetreue Übernahme einer bestehenden Historienrevision ist keine neue reguläre Inhaltsänderung. Spezialartefakte folgen ausschließlich 9.6.2 und 10.4. Die zusätzliche Rücknahme einer Freigabe nach negativem Relationsreview ist abschließend in 11.13 festgelegt.

### 9.7 Exakte Kernrelationsmatrix

| Relation | Exakt zulässige Quellen | Exakt zulässige Ziele | Zusatzregel |
|---|---|---|---|
| `addresses` | `need`, `capability`, `requirement` | `goal` | — |
| `refines` | `need` | `goal`, `need` | detaillierter → allgemeiner |
| `refines` | `capability` | `need`, `capability` | detaillierter → allgemeiner |
| `refines` | `requirement` | `need`, `capability`, `requirement` | detaillierter → allgemeiner |
| `refines` | `scenario` | `need`, `capability`, `requirement`, `scenario` | detaillierter → allgemeiner |
| `derived_from` | `goal`, `need`, `capability`, `requirement`, `scenario`, `decision`, `risk`, `assumption`, `component`, `interface`, `verification`, `test`, `release`, `milestone`, `task`, `term`, `document`, `section`, `content_block`, `view`, `code_ref`, `configuration` | `source`, `need`, `decision`, `assumption` | fachliche Herkunft |
| `depends_on` | `capability`, `requirement`, `component`, `interface`, `task`, `release`, `milestone`, `code_ref`, `configuration` | `capability`, `requirement`, `component`, `interface`, `task`, `release`, `milestone`, `code_ref`, `configuration` | kein Self-Link |
| `conflicts_with` | jeder der 28 Artefakttypen | jeder der 28 Artefakttypen | symmetrisch; genau einmal kanonisch gespeichert |
| `constrains` | `requirement`, `decision` | `capability`, `requirement`, `component`, `interface` | — |
| `allocated_to` | `requirement` | `component`, `interface` | — |
| `implemented_by` | `capability`, `requirement`, `decision` | `task`, `component`, `code_ref` | — |
| `verified_by` | `requirement`, `capability`, `task` | `verification`, `test` | — |
| `produces` | `verification`, `test` | `evidence` | — |
| `mitigates` | `requirement`, `decision`, `task` | `risk` | — |
| `scheduled_for` | `capability`, `requirement`, `task` | `release`, `milestone` | — |
| `part_of` | `milestone` | `release` | genau ein Release |
| `part_of` | `component` | `component`, `capability` | zyklusfrei |
| `part_of` | `interface` | `component`, `capability` | zyklusfrei |
| `part_of` | `task` | `release`, `milestone`, `capability` | zyklusfrei |
| `supersedes` | jeder Artefakttyp | exakt derselbe Artefakttyp wie die Quelle | zyklusfrei |
| `duplicates` | jeder Artefakttyp | exakt derselbe Artefakttyp wie die Quelle | symmetrisch; genau einmal kanonisch gespeichert |
| `contains` | `document` | `section` | Position im Dokument |
| `contains` | `section` | `section`, `content_block` | Position im Abschnitt; zyklusfrei |
| `references` | `content_block`, `view`, `verification`, `test`, `source` | jeder der 28 Artefakttypen | nicht besitzende Referenz |

`superseded_by` ist ausschließlich eine berechnete inverse Sicht. „Jeder der 28 Artefakttypen“ bezeichnet exakt die in 9.1 aufgeführten Typen. Eine Relation ist nur zulässig, wenn genau eine Tabellenzeile Quelle und Ziel akzeptiert. Pflichtrelationen freigegebener Artefakte erfüllen den profilabhängig geforderten Relationsreviewstatus.

### 9.8 Requirement-Qualitätsgate

Ein Requirement darf erst `approved` werden, wenn:

- genau eine normative Verpflichtung vorliegt;
- Scope, Actor, Trigger und Geltungsbereich eindeutig sind;
- das Verhalten beobachtbar oder messbar ist;
- Begründung und Herkunft vorhanden sind;
- strukturierte Semantik oder ein gleichwertiger prüfbarer Vertrag vorliegt;
- ein gültiger Verification Contract existiert;
- alle verpflichtenden Beziehungen gültig und `current` sind;
- keine offenen Platzhalter oder Fehlerdiagnosen bestehen;
- Konfigurationsabhängigkeiten konsistent sind;
- alle aktiven Profilregeln erfüllt sind.

### 9.9 SRX-1.0-Kernsemantik

SRX ist eine JSON-AST-Sprache. Ein Ausdruck besitzt keine textuelle Eval-Syntax.

```json
{
  "language": "srx",
  "version": "1.0",
  "expression": {
    "op": "and",
    "args": [
      {
        "op": "eq",
        "args": [
          {"op": "field", "context": "artifact", "pointer": "/artifact_type"},
          {"op": "literal", "value": "requirement"}
        ]
      },
      {
        "op": "exists",
        "arg": {"op": "field", "context": "artifact", "pointer": "/rationale"}
      }
    ]
  }
}
```

Zulässige Kontextobjekte sind `artifact`, `configuration`, `project`, `relations` und für Quantoren `item`. Die vollständige Operatorsemantik wird durch Anforderungen `SR-REQ-0286` bis `SR-REQ-0298` und versionierte Testvektoren bestimmt.

---

### 9.10 Mehrsprachen- und Analyzer-Abgrenzung

Requirements besitzen die expliziten Pflichtfelder aus Anhang S. Im Approval-Gate sind fachliche Einzelforderung und Widerspruchsfreiheit menschlich zu beurteilen; der Core prüft nur seine dokumentierten Struktur- und Policykriterien. Ein fehlendes Wort MUSS ist kein Fehler. Analyzerberichte sind externe, gebundene Beobachtungsressourcen nach Anhang T, keine zusätzliche Artefaktklasse. Die bestehende Matrix aus 28 Artefakttypen und ihre Relationsregeln bleibt unverändert.

---

## 10. Änderungs-, Baseline-, Transaktions- und Austauschmodelle

### 10.1 Gemeinsamer Change Plan

Ein Change Plan enthält mindestens:

```json
{
  "format_version": "1.2.0",
  "metadata_policy_version": "change-metadata-v1",
  "change_plan_id": "CP-0123456789ABCDEFGHJKMNPQRS",
  "request_id": "agent-run-42",
  "planned_at": "2026-09-01T18:00:00.000000Z",
  "actor": {
    "actor_type": "human",
    "actor_id": "local-user"
  },
  "base": {
    "scope_descriptor": {},
    "model_root_sha256": "..."
  },
  "operations": [],
  "preconditions": [],
  "result_artifacts": [],
  "expected_result": {
    "model_root_sha256": "..."
  },
  "change_plan_sha256": "..."
}
```

`change_plan_sha256` wird über den RFC-8785-kanonisierten Plan ohne dieses Feld gebildet. `planned_at`, Akteur, IDs, resultierende Revisionen, `created_at`, `updated_at`, `created_by`, `updated_by`, resultierende Ressourcenhashes und erwartete Modellwurzel sind unveränderbare Planbestandteile.

Die Metadaten werden ausschließlich durch die ausdrücklich ausgewählte Policy aus Anhang K berechnet: `change-metadata-v1` für reguläres Authoring und Proposal-Kontrolländerungen, `merge-metadata-v1` für semantischen Merge und `migration-metadata-v1` für Schema-Migration. Die Regeln werden nicht gleichzeitig auf dasselbe Ergebnis angewendet. Reguläres Authoring erhöht die Basisrevision einmal; Merge bindet Base/Ours/Theirs; Migration erhält unveränderbare Legacy-Bytes nach Anhang Q. Reine `representation_normalize`-Operationen ändern keine Artefaktwerte oder Revisionen.

### 10.2 Kernoperationen

| Operation | Mindestinhalt | Ergebnis |
|---|---|---|
| `create` | vollständiges neues Artefakt und gebundene Ergebnisidentität | neue Artefaktdatei |
| `update` | Ziel, erwartete Revision/Hash, RFC-6902-Patch | eine neue Artefaktrevision |
| `relation_add` | Quelle, Typ, Ziel, Relation-ID | neue Relation und eine Quellrevision |
| `relation_remove` | Quelle, Relation-ID, erwarteter Hash, Grund | Relation entfernt und eine Quellrevision |
| `transition` | Ziel, Ausgangsstatus, Zielstatus, Pflichtmetadaten | zulässiger Lifecycle-Übergang |
| `retire` | Ziel, erwartete Revision/Hash, Grund | Reifegrad `retired` |
| `evidence_record` | vollständiger Nachweisvertrag | neue unveränderbare Evidence |
| `attachment_add` | Ziel, Pfad, Medientyp, Größe, Hash | referenzierter Anhang |
| `attachment_remove` | Ziel, Pfad, erwarteter Hash, Grund | Referenz entfernt; Payload erst nach Reachability-Prüfung löschbar |
| `representation_normalize` | Pfad, erwarteter Byte-Hash, Ziel-Byte-Hash | bytebezogene JSON-Normalisierung ohne semantische Revision |
| `relation_review_record` | menschliche Entscheidung, Relations-/Kontextbindung und vollständige Freigaberücknahmen nach 11.13 | atomarer Review-Nachweis und konsistenter Approval-Zustand |

Operationen werden in Array-Reihenfolge auf einen isolierten Zwischenstand angewendet. Die gebundenen IDs und Metadaten bewirken, dass die Anwendung exakt des gespeicherten Plans unabhängig vom Apply-Zeitpunkt dasselbe normative Ergebnis erzeugt. `change apply` verweigert einen Plan bei abweichendem Planhash, Basis-Hash, Metadatenvertrag oder Ergebnis-Hash.

### 10.3 Proposal-Statusmodell und Authoring

Ein Proposal trennt seine physische Artefaktrevision `revision` von der zur fachlichen Freigabe gehörenden `content_revision`. Beide beginnen bei 1. Jeder persistierte semantische Artefaktwrite erhöht `revision` einmal nach Anhang K. Nur eine Änderung des vorgeschlagenen Fachinhalts erhöht zusätzlich `content_revision`. Die Option `--expected-revision` meint immer die aktuelle Artefaktrevision; Freigaben binden ausdrücklich die Inhaltsrevision.

`content_sha256` ist SHA-256 über die RFC-8785-Projektion des gesamten Proposals ohne die Top-Level-Felder `revision`, `created_at`, `created_by`, `updated_at`, `updated_by`, `content_revision`, `content_sha256`, `maturity`, `proposal_status`, `reviews` und `control_history`. Alle übrigen Fachfelder, insbesondere Basis, vollständiger gebundener Change Plan, Titel, Begründung, Quellen, Annahmen, Modellherkunft, Relationsinhalt und Extensions bleiben enthalten. Eine Änderung eines solchen Felds ist Authoring, keine reine Kontrolländerung.

| Ausgangsstatus | Zulässige Folgestatus | Verbindlicher Auslöser |
|---|---|---|
| `draft` | `validated`, `rejected`, `stale` | erster erfolgreicher Teil der Kontrollfolge von `proposal review start`, explizite Ablehnung oder nachgewiesene Basisabweichung |
| `validated` | `checked`, `rejected`, `stale` | vollständiger erfolgreicher Proposal-Check in derselben Kontrollfolge |
| `checked` | `in_review`, `rejected`, `stale` | atomarer Abschluss von `proposal review start` |
| `in_review` | `approved`, `rejected`, `stale` | Reviewentscheidung mit exakter Inhaltsbindung |
| `approved` | `applied`, `rejected`, `stale` | erfolgreiche transaktionale Übernahme, Widerruf vor Apply oder Basisabweichung |
| `rejected`, `stale`, `applied` | Endstatus dieser gespeicherten Fassung | keine direkte Mutation; erforderliche Neuvorlage erhält neue Proposal-ID mit Herkunftsreferenz |

Mehrere menschliche Freigaben werden nach unterschiedlichen `actor_id` gezählt; wiederholte Zustimmung derselben Person erhöht die Anzahl nicht. Solange die konfigurierte Mindestanzahl nicht erreicht ist, bleibt das Proposal `in_review`. Erst die ausreichende Zahl gültiger, nicht widerrufener Inhaltsfreigaben ergibt `approved`. Der Erfolgsvektor in Kapitel 11.10 verwendet ausdrücklich die Defaultpolicy mit einer menschlichen Freigabe.

Ein erfolgreicher `proposal review start` durchläuft `draft → validated → checked → in_review` atomar in genau einem kontrollierten Write. Jeder Zwischenschritt wird in `control_history` mit vorherigem/nachfolgendem Status, Inhaltsbindung und Prüfergebnis-Hash gespeichert. Es gibt keinen nach einem halben Check als geprüft geltenden Zwischenstand. `validated` und `checked` sind gültige aufgezeichnete Übergangszustände; die regulär zurückgegebene Endfassung des Startbefehls ist `in_review`.

`proposal validate` und `proposal check` sind dagegen rein lesende Prüfungen. Sie liefern `observed_status`, `eligible_transition` und hashgebundene Ergebnisse, persistieren aber keinen Status. Ein vom Aufrufer gelieferter JSON-Bericht ist kein vertrauenswürdiger Ersatz für die eingebauten Prüfungen. `proposal review start` führt die erforderlichen Prüfungen selbst gegen denselben gebundenen Inhalt vollständig aus; bei großer Arbeit nach Anhang P über mehrere Schritte.

Eine menschliche Freigabe bindet `(proposal_id, content_revision, content_sha256, base_model_root_sha256, change_plan_sha256)` sowie Reviewer und Entscheidung. Kontrolländerungen an Status, `maturity`, Review-/Kontrollhistorie und Auditmetadaten erhöhen die Artefaktrevision, erhalten aber Inhaltshash und Inhaltsrevision. Die Wirkung einer Freigabe bleibt dadurch bis zu Inhaltsänderung, Widerruf oder stale Basis erhalten. Die jeweils beim Review beobachtete Artefaktrevision wird zusätzlich für Audit gespeichert, ist aber nicht die Freigabegültigkeitsbedingung.

Authoring über `proposal change add|update|remove|move` ist für `draft`, `in_review` und `approved` zulässig. Es erhöht beide Revisionen einmal, setzt Status und `maturity` auf `draft` und entzieht allen älteren Inhaltsbindungen die Freigabewirkung. Frühere Reviews bleiben als unwirksame Historie lesbar. Bei nachweislich unverändertem Inhalt darf der Befehl als No-op enden, ohne IDs oder Revisionen zu verändern.

### 10.4 Spezial-Lifecycle-Vertrag

Die Zuordnung in Tabelle 9.6.2 gilt unverändert. Allgemeine Lifecycle- oder freie Feldpatches auf Spezialstatus sind unzulässig. Evidence, Baseline und Relationsreview entstehen atomar durch ihre Fachbefehle. Proposal-Kontrolländerungen sind ebenfalls `normative_write` und werden vom gemeinsamen Writer als typgeprüfte Spezialoperation `proposal_control` umgesetzt. Ihre Payload enthält Proposal-ID, erwartete Artefaktrevision/Vollhash, Inhaltsbindung, erlaubte Übergangsereignisse und deren geprüfte Begründung. Nur die in Kapitel 11.10 benannten Fachbefehle dürfen diese Operation planen; ein freier Proposal-Patch kann keine menschliche Entscheidung erzeugen.

Relationsreviews verwenden die ausschließlich vom menschlichen Review-Fachbefehl geplante Spezialoperation `relation_review_record` nach Kapitel 11.13. Sie umfasst den unveränderbaren Nachweis und sämtliche daraus erforderlichen Freigaberücknahmen; generische Artefakterzeugung oder freie Feldpatches dürfen diese Operation nicht umgehen.

Die Aktualisierung des übernommenen Proposals auf `applied`, die fachlichen Zieländerungen und der Request-Abschluss gehören zu derselben Transaktion. `specification` schließt Proposal- und Baseline-Dateien dauerhaft gemäß 10.8.1 aus; unzulässige Kontrollabhängigkeiten werden statt einer rekursiven Basisbildung abgewiesen; die Proposal-Datei wird zusätzlich über erwartete Revision und Vollhash in die Transaktion gebunden. Ein fehlgeschlagener oder stale Apply meldet den beobachteten Konflikt schreibfrei, statt dafür nachträglich die abgewiesene Datei verändern zu müssen. Ein später ausdrücklich autorisierter Kontrollwrite darf den passenden Endstatus dokumentieren.

### 10.5 Verification Plan Status und berechnetes Verification Result

Gespeichert wird ausschließlich `verification_plan_status` mit `not_planned`, `planned`, `running`, `waived` oder `not_applicable`. `verification_result` wird niemals in das fachliche Subject geschrieben. Vor der Ergebnisaggregation werden Bewertungsstand, Pflichtprüfungen und maßgebliche Prüfläufe nach 10.5.1–10.5.4 aufgelöst. „Aktuell“ nach Anhang L bezeichnet zunächst die fachliche Kontextgültigkeit eines Nachweises; **maßgeblich für eine konkrete Bewertung** ist er erst nach der hier definierten Auswahl.

`waived` erfordert ein Objekt `verification_waiver` nach 10.5.5 mit Grund, Scope Descriptor, UTC-Ablauffrist, Human-Review-ID und versioniert gebundenem Inhalts-/Konfigurationshash. Historische Waiver bleiben gemäß 10.5.5 lesbar, begründen aber keine wirksame Ausnahme. Ein Waiver ersetzt keine Ergebnisdaten und hebt die strengere Release-Abnahmepolicy nicht auf.

| Bedingung in Prioritätsreihenfolge | Ergebnis |
|---|---|
| Artefakt nach ausgewählter Konfiguration nicht anwendbar | `not_applicable` |
| gültiger, nicht abgelaufener Waiver für exakt den Scope | `waived` |
| `verification_plan_status = not_planned` | `not_evaluated` |
| kein vollständiger gültiger Bewertungsdescriptor, keine eindeutige Pflichtmenge oder unwirksame Laufablösung | `incomplete` |
| mindestens eine maßgebliche kontextaktuelle Pflicht-Evidence ist `failed` | `failed` |
| `verification_plan_status = running` | `running` |
| ein Pflichtcontract, Testbezug oder ein vollständig belegter erwarteter Pflichtlauf fehlt | `incomplete` |
| zu mindestens einer Pflichtprüfung existiert nur fachlich stale Evidence des gewählten Bewertungsstands | `stale` |
| alle Pflichtprüfungen und erwarteten Läufe besitzen aktuelle bestandene Evidence; keine maßgebliche aktuelle Pflicht-Evidence ist fehlgeschlagen oder unvollständig | `passed` |
| alle übrigen Fälle | `incomplete` |

Ein bekannter maßgeblicher Fehlschlag wird also nicht durch den Planstatus `running` oder einen anderen noch fehlenden Nachweis verdeckt. Ein strukturell ungültiger Descriptor wird bereits vor der fachlichen Aggregation mit SRV175 und Code 3 abgewiesen; eine nicht menschliche Ablösungsentscheidung ist SRV175 mit Code 7. Fehlende oder inzwischen unwirksame Bindungen erzeugen `incomplete` mit SRV176 und maschinenlesbarem `reason`; `evaluation_required`, `required_run_missing` und `replacement_binding_changed` sind verbindliche Gründe. Bei `release readiness` verhindert dieses fachliche Ergebnis die Readiness unabhängig vom Warnungsschwellwert. Ein vollständiger Bericht mit fachlichem `failed`, `stale` oder `incomplete` ist keine bestandene Readiness-Prüfung.

#### 10.5.1 Bewertungsdescriptor und geprüfter Produktstand

Der versionierte Eingabetyp `verification-evaluation-v1` ist ein Wertobjekt, kein neuer Artefakttyp. Er besitzt folgende Pflichtfelder; unbekannte Top-Level-Felder sind unzulässig:

| Feld | Exakter Inhalt |
|---|---|
| `format_version` | exakt `1.0.0`; Schemaidentität `verification-evaluation-v1` |
| `evaluation_id` | `EVAL-` plus 128-Bit-Token nach `random128-v1` |
| `evaluated_subject` | `{subject_id, manifest, state_sha256}`; `subject_id` ist ein nichtleerer stabiler Bezeichner des geprüften Produkts beziehungsweise Spezifikationsgegenstands |
| `configuration_hash` | Hash der effektiven gewählten Produktkonfiguration oder `null` bei unkonfigurierter Bewertung |
| `required_runs` | nichtleeres Array aus `{subject_artifact_id, contract_id, test_id, check_id, run_ids}`; der Schlüssel der ersten vier Felder ist eindeutig; `test_id` ist eine Test-ID oder `null`; `run_ids` ist eine nichtleere sortierte Menge |
| `replacements` | Array der vollständigen Ablösungsentscheidungen nach 10.5.3; darf leer sein |
| `created_at`, `created_by` | UTC-Zeitstempel und Actor der Festlegung; ändern keine historischen Nachweise |

`manifest` ist ein nichtleeres nach `logical_path` sortiertes Array aus `{logical_path, size, sha256}`. Logische Pfade sind relative eindeutige POSIX-Pfade ohne `..`, Größe ist eine nichtnegative Ganzzahl, `sha256` bindet die tatsächlich geprüften Eingangsbytes. `state_sha256` ist SHA-256 der RFC-8785-Kanonisierung von `{subject_id, manifest}`. Absolute Speicherorte, Ausgaben derselben Prüfung, Evidence, Bewertungsdescriptor und dessen Auswahlmetadaten gehören nicht in diesen Eingangsmanifest-Hash. Beim Prüfen einer Spezifikation bindet das Manifest die untersuchten Dokument-/Modellinputs, nicht die später erzeugten eigenen Nachweise. Dies verhindert eine Selbstabhängigkeit; es berechtigt nicht zum Auslassen fachlich erforderlicher Prüfinputs.

Der aufrufende Prüfer oder Importer liefert die tatsächliche Eingangsbindung. SpecRoad prüft Syntax, Selbsthash und verfügbare referenzierte Bytes, behauptet aber keinen externen Testlauf allein aufgrund mitgelieferter Metadaten. Fehlende Prüfeingänge werden niemals durch den aktuellen Git-HEAD oder die aktuelle SpecRoad-Modellwurzel erraten. Unbekannter Produktstand bedeutet nicht „gilt für jeden Stand“.

Vor der Hashbildung werden `required_runs` nach `(subject_artifact_id,contract_id,test_id,check_id)` und `replacements` zusätzlich nach `replaced_run_id` sortiert; bei `test_id` steht `null` vor ID-Strings. Alle Stringvergleiche verwenden UTF-8-Byteordnung, alle Lauf-ID-Arrays sind sortierte duplikatfreie Mengen. Die im Descriptor genannten Artefakt-IDs werden gegen die unabhängig gebildete Pflichtmenge geprüft und erweitern weder Seed noch Scope-Closure; insbesondere darf ein Descriptor seinen eigenen Prüfumfang nicht bestimmen. Ein gewählter Descriptor wird vollständig normalisiert und als `evaluation_sha256` über seine RFC-8785-Bytes gebunden. Eine neue Bewertung oder geänderte Laufablösung erhält eine neue `evaluation_id`; ein innerhalb des Projekts bereits bekannter Bezeichner mit anderem Inhalt ist ein Konflikt (Code 6). Alte Evidence und bereits versiegelte Baselines bleiben unverändert. Die konkrete Eingangsbindung, nicht ein Zeitstempel oder der Importzeitpunkt, entscheidet über den Produktstand.

#### 10.5.2 Pflichtprüfungen, Laufkontext und Auswahl

Jeder Verification Contract definiert `evidence_slots` als nichtleeres Array aus `{check_id, test_id, dimension}` mit eindeutigen `check_id`. `check_id` folgt `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`, `test_id` ist eine vorhandene Test-ID oder `null`, `dimension` eine im Contract erklärte Prüfdimension. Fehlt bei einem neu erzeugten Contract eine explizite Auswahl, materialisiert das Authoring den Default `[{"check_id":"overall","test_id":null,"dimension":"overall"}]`. Deklarierte weitere Pflichtdimensionen dürfen nicht durch den Default ersetzt werden. Alle Slots sind Pflicht; optionale Zusatzbeobachtungen werden separat berichtet. Ein direkt über `verified_by` gebundener Test bildet einen impliziten Contract mit `contract_id=test_id`, einem Slot `overall` und diesem Test als `test_id`.

Die Pflichtmenge entsteht deterministisch für jedes anwendbare zu bewertende Subject aus seinen gültigen `verified_by`-Zielen und deren Slots. Eine Pflichtelementidentität ist `(subject_artifact_id, contract_id, test_id, check_id)`. `required_runs` muss diese Menge vollständig und ohne fremde Schlüssel abdecken; kein Freitextselector darf Pflichtprüfungen wegfiltern. Fehlende Schlüssel ergeben `incomplete`; ungültige oder zusätzliche Schlüssel sind Descriptorfehler. Ein nicht benötigter Slot eines Contracts wird nicht stillschweigend ignoriert, sondern erfordert eine neue fachlich geprüfte Contract-Fassung.

Ein neuer Nachweis enthält `run_context`, entweder `null` mit dokumentiertem Grund für fehlende Herkunft oder `{subject_id, subject_state_sha256, run_id, check_id, test_id}`. `run_id` ist ein nichtleerer, im Producer-Namensraum stabiler Laufbezeichner; der gespeicherte Wert ist bereits namensraumqualifiziert. Gleiche Laufidentität mit widersprechendem geprüften Produktstand ist ein Eingabe-/Idempotenzkonflikt. Subject, Contract und gegebenenfalls Test sind über die vorhandenen Evidence-Subjects mit Kontext- und Audithashes gebunden. Ein Ergebnis zu mehreren Subject-Artefakten wirkt nur auf die explizit enthaltenen und passend gebundenen Subjects. Ein Lauf kann mehrere Evidence-Artefakte erzeugen; alle bleiben Teil desselben Laufs.

Für jede Pflichtprüfung werden zunächst **alle** im ausgewählten Modell vorhandenen Evidence-Artefakte mit exakt passendem `subject_id`, `subject_state_sha256`, Pflichtschlüssel und zulässiger Konfigurationsbindung ermittelt. Bei `bound` muss der Konfigurationshash gleich sein; `independent` erlaubt nur die ausdrücklich im Contract erklärte Unabhängigkeit. Alle so beobachteten Läufe sowie alle in `required_runs` erwarteten Läufe sind Kandidaten. Erst wirksame Ablösungen nach 10.5.3 entfernen einen Kandidaten aus der aktuellen Aggregation. Es gibt keine Auswahl „neuester Erfolg“, „letzter Import“ oder nur nach Evidence-ID. Ein zusätzlich importierter gleichzeitiger Fehlschlag desselben Stands bleibt dadurch sichtbar.

Evidence eines anderen Produktstands ist `historical_other_state`, Evidence ohne belastbaren Laufkontext `unbound`; beide Kategorien werden mit ihren IDs im Bericht ausgewiesen und tragen nicht zu `passed` bei. Sie sind nicht allein wegen ihres historischen Fehlschlags ein Fehler der neuen Bewertung. Fachlich stale Evidence des passenden Stands bleibt dagegen als stale Kandidat erkennbar. Eine Erwartung ohne überhaupt vorhandenen passenden Nachweis ist `missing`, nicht `stale`.

Innerhalb eines maßgeblichen Laufs werden sämtliche Evidence-Ergebnisse derselben Pflichtprüfung aggregiert: mindestens ein aktuelles `failed` ergibt einen fehlgeschlagenen Lauf; aktuelle bestandene Ergebnisse ergeben nur dann einen bestandenen Lauf, wenn keine nicht abgelöste stale, unvollständige oder widersprüchliche Pflichtbeobachtung dieses Laufs übrig ist. Ein ausdrücklich als solcher neu ausgeführter Retest erhält eine neue Lauf-ID. Doppelte Importe desselben Ursprungs bleiben nach dem bestehenden Idempotenzvertrag derselbe Nachweis. Nicht als `passed` oder `failed` aufgelöste Pflichtergebnisse sind unvollständig und niemals erfolgreicher Default.

#### 10.5.3 Nachvollziehbare Laufablösung

Eine Ablösungsentscheidung enthält exakt `subject_artifact_id`, `contract_id`, `test_id`, `check_id`, `replaced_run_id`, `replaced_evidence_set_sha256`, `replacement_run_ids`, `reason`, `authorized_at` und `authorized_by`. Der umgebende Descriptor bindet geprüften Gegenstand, Produktstand und Konfiguration. `authorized_by.actor_type` muss `human` sein; die Single-User-Akteursdeklaration folgt derselben Vertrauensgrenze wie ein Human-Review, ohne vorgetäuschte kryptografische Authentifizierung. Ein KI-Agent darf eine tatsächlich erklärte menschliche Entscheidung protokollieren, aber keine eigene Zustimmung erfinden.

`replaced_evidence_set_sha256` bindet die nach Evidence-ID sortierte nichtleere Liste `{id, sha256}` sämtlicher vorhandener Evidence-Artefakte des abgelösten Laufs für diese Pflichtprüfung und denselben Produktstand. Dabei ist `sha256` der vollständige unveränderbare Artefakthash. Ein späterer zusätzlicher Nachweis desselben alten Laufs verändert diese Menge: Die frühere Ablösung ist dann unwirksam und die Bewertung `incomplete`, bis eine neue begründete Auswahl vorliegt. So können nachträglich bekannt gewordene Fehler nicht unsichtbar bleiben.

`replacement_run_ids` ist eine nichtleere sortierte Menge anderer Lauf-IDs derselben Pflichtprüfung und desselben bewerteten Stands. Pro altem Lauf ist nur eine Entscheidung zulässig. Der Ablösungsgraph ist azyklisch. Eine Entscheidung wird erst wirksam, wenn die gesamte Bindung stimmt und alle erreichbaren Endläufe vorhanden, fachlich aktuell und vollständig sind. Endläufe dürfen ausdrücklich **fehlgeschlagen** sein; dann bleibt die Bewertung `failed`. Fehlende, stale oder unvollständige Ersatzläufe erlauben kein `passed`. Wirksam abgelöste Lauf-IDs werden auch in den Erwartungen aus `required_runs` durch ihre erreichbaren Endläufe ersetzt; der alte Lauf wird nicht zusätzlich nochmals als unbefriedigte Pflicht gezählt. Ablösung wirkt nie auf eine andere Pflichtprüfung oder einen anderen Produktstand und verändert niemals historische Evidence.

Für einen korrigierten Produktstand entsteht eine neue Bewertung mit neuem Zustandsmanifest. Dafür ist keine Ablösung fremder alter Produktstände erforderlich. Für einen Retest desselben Stands werden dagegen alte maßgebliche Läufe nur über die hier gebundene Entscheidung ersetzt. Reihenfolge von Ausführung und Import sowie lexikografische ID-Reihenfolge erzeugen keine eigenständige Auswahlwirkung.

#### 10.5.4 CLI-Auflösung, Berichte und Baselines

`coverage`, `query`, `release readiness`, die Verification-Ansichten von `render`, `view render` und `document render` akzeptieren optional `--evaluation <FILE>`. Dies ist ein semantischer Leseparameter; ohne ausdrücklichen stdin-Marker wird keine Eingabe angefordert. Er bindet den **Inhalt**, nicht den absoluten Dateipfad. Ein normalisiertes Query-Objekt enthält das Feld `evaluation` mit dem vollständigen kanonischen Descriptor oder `null`. In Work-Aufträgen wird dieser Eingabeinhalt samt Hash gesichert und bei Resume unverändert verwendet.

Für `release readiness` und `coverage --release <ID>` ist vorrangig `release.readiness_policy.verification_evaluation` maßgeblich. Die Auswahl ist ein optionales, schema-definiertes Wertobjekt im bestehenden Release-Artefakt und wird über dessen normalen Change Plan beziehungsweise KI-Proposal authoriert. Ein CLI-Descriptor darf eine dort gespeicherte Auswahl nur identisch wiederholen; eine abweichende Auswahl ergibt Code 6 und keine alternative Freigabe. Ohne gespeicherte Auswahl darf ein expliziter Descriptor eine als vorläufig gekennzeichnete Read-only-Bewertung liefern. Eine Release-Baseline verlangt jedoch eine gespeicherte Auswahl und bindet deren vollständige Bytes und Hash zusätzlich zum Scope Descriptor; sie darf keine externe ungespeicherte Auswahl als Releasefreigabe übernehmen.

Andere Abfragen verwenden den expliziten Descriptor. Ohne eindeutige Auswahl erfolgt kein Raten eines „aktuellen Builds“: nach den vorgelagerten Zuständen ergibt sich `incomplete` mit `evaluation_required`. Die Ausgabe in `summary` nennt `evaluation_sha256` oder `null`; Ergebnisberichte erklären maßgebliche, abgelöste, fremdständige, ungebundene, fehlende und stale Nachweise je Pflichtprüfung. Das bestehende Query-Result-Schema bleibt unverändert; dort steht die bewertungsbezogene Zusammenfassung im Envelope. Der Descriptor ist fachlicher Befehlsinput und Bestandteil der deterministischen Ergebnisbindung, aber keine Betriebsmetrik.

`evidence record` und `evidence import` akzeptieren `--run-context <FILE>` für einen expliziten Run-Kontext. Ein Importmapping kann denselben Kontext aus vorhandenen Ursprungsfeldern liefern; widersprechende Angaben sind Code 3. Fehlende Werte bleiben `null` mit Begründung; Import und Erfassung setzen keine Subjects oder Release-Policies um und behaupten keinen aktuellen Nachweis. Die spätere Ergänzung einer ungebundenen Herkunft ist ein neuer Nachweis mit eigener ID und Herkunftsverweis, keine Änderung recorded Evidence. Alle normalen Actor-, Request-, Dry-Run-, Schema- und Transaktionsregeln gelten unverändert.

Evidence-Import verändert weder Subject-Revisionen noch `verification_plan_status`. Die Auswahlregeln erweitern nicht die Ausführungsrechte: SpecRoad startet weiterhin keinen Testcode und keine externen Buildprozesse.


#### 10.5.5 Versionierter Waiver-Vertrag

Ein neu ausgestellter wirksamer Waiver verwendet genau folgende Felder. Er ist
weiterhin ein eingebettetes Objekt des Subjects, kein zusätzlicher Artefakttyp.

| Feld | Vertrag |
|---|---|
| `format_version` | exakt `1.0.0` |
| `content_hash_algorithm` | exakt `waiver-content-hash-v1` |
| `reason` | nichtleerer begründender Text |
| `scope_descriptor` | vollständiger gültiger `scope-v1`-Descriptor; kanonisch exakt gleich dem ausdrücklich ausgewerteten Descriptor |
| `expiry_condition` | exakt `{kind: "utc_deadline", expires_at: <UTC-Zeitstempel>}` |
| `human_review_id` | nichtleere Kennung der expliziten menschlichen Waiver-Entscheidung |
| `artifact_sha256` | 64 kleingeschriebene Hexzeichen; ausschließlich der unten definierte Waiver-Inhaltshash |
| `configuration_sha256` | ausdrücklich `null` bei unkonfiguriertem Scope, sonst der bestehende kanonische Manifesthash der aufgelösten effektiven Konfiguration einschließlich Elternkette |

Unbekannte oder fehlende Felder und unbekannte Versionen sind unzulässig. Die
bestehende Schreibweise `artifact_sha256` erhält durch `content_hash_algorithm`
eine eindeutige neue Hashdomäne. Ein historischer Vollartefakthash darf niemals
allein durch Umbenennung oder Ergänzung des Algorithmus zur aktuellen Bindung
werden. Waiver-Daten sind passive Werte; sie laden oder starten keinen Code.

**Exakte Hashprojektion.** Für Capabilities, Requirements und Tasks ist der Hash
SHA-256 der RFC-8785-Kanonisierung von
`{hash_algorithm: "waiver-content-hash-v1", artifact: <Projektion>}`.
Die Projektion enthält ausschließlich tatsächlich vorhandene Felder aus dieser
abschließenden Liste; fehlende optionale Werte werden nicht ergänzt, Arrays
nicht umsortiert, Texte nicht normalisiert:

| Geltung | Enthaltene Top-Level-Felder |
|---|---|
| alle drei Subjecttypen | `schema_version`, `id`, `id_scheme`, `artifact_type`, `title`, `language`, `text_direction`, `owner`, `tags`, `applicability`, `relations`, `extensions`, `provenance`, `external_identities`, `display_id` |
| Capability zusätzlich | `description`, `outcome`, `priority` |
| Requirement zusätzlich | `requirement_kind`, `normative_force`, `statement`, `priority`, `criticality`, `rationale`, `deviation_conditions`, `deviation_authority`, `scope`, `actor`, `trigger`, `preconditions`, `response`, `object`, `timing`, `thresholds`, `exceptions` |
| Task zusätzlich | `description`, `done_criteria` |

`verification_waiver`, `maturity`, `implementation_status`,
`verification_plan_status`, `revision`, `created_at`, `created_by`, `updated_at`
und `updated_by` sind ausgeschlossen. Innerhalb jedes `provenance`-Eintrags
werden ausschließlich `source_id`, `locator`, `excerpt`, `content_sha256` und
`extensions` übernommen; sein reiner Erfassungszeitpunkt `captured_at` entfällt.
Alle anderen enthaltenen Werte werden vollständig übernommen, auch Relations-
und Extensionwerte. Die Ausschlüsse sind pfadgebunden, kein rekursives Entfernen
gleichnamiger fachlicher Felder. Unbekannte Subjectfelder oder Typen werden
abgewiesen; zukünftige Erweiterungen dürfen nicht still aus der Projektion
fallen. Der Vollartefakthash für Audit, Diff, Writer und Baselines bleibt
unverändert und schließt weiterhin das gesamte Artefakt ein.

Jede Änderung an diesen fachlichen Projektionswerten entwertet den alten Waiver.
Das Speichern des Waivers selbst, ein reiner Workflowwechsel oder die genannten
Auditänderungen erzeugen keine Selbstreferenz. Scope und Konfiguration werden
zusätzlich exakt verglichen; ein anderer Scope, eine andere Konfigurations-ID,
eine geänderte Konfigurationskette oder ein anderer Konfigurationshash dürfen
keine Ausnahme erben. `null` ist kein Wildcard. Die Konfigurationsbindung benutzt
den vorhandenen Konfigurationshash; die Subjectprojektion definiert keine neue
Konfigurationsprojektion. Die Bewertung eines einzelnen Waivers ist kein
Nachweis der Scope-Mitgliedschaft, Anwendbarkeit oder Release Readiness.

**Zeitvertrag.** `expires_at` und der für jede Bewertung ausdrücklich übergebene
`evaluated_at` verwenden `YYYY-MM-DDTHH:MM:SS[.fffffffff]Z`: gültiges Datum,
Großbuchstaben `T`/`Z`, Sekunden 00–59, optional 1–9 Nachkommastellen. Offsets,
lokale Zeiten, Schaltsekunden und eine implizit gelesene Systemzeit sind in v1
unzulässig. Verglichen wird verlustfrei bis zur angegebenen Nanosekundenstelle;
fehlende Nachkommastellen entsprechen Nullen. Bei `evaluated_at >= expires_at`
ist der Waiver abgelaufen, auch exakt an der Grenze. Ereignisbedingungen und
freie Texte werden nicht als wirksame Ablaufregel interpretiert.

**Menschliche Bindung.** Der Review bestätigt die konkrete Waiver-Entscheidung,
nicht bloß das Bestehen einer Relation. Sein passiver Wert enthält genau
`review_id`, `subject_id`, `waiver_sha256`, `reviewer`, `reviewed_at`, `decision`.
`waiver_sha256` ist der vollständige kanonische Hash des Waiver-Objekts inklusive
Grund, Scope, Frist, Review-ID und beider Bindungshashes. `reviewer` ist ein
Actor mit `actor_type=human`; `decision=confirmed` ist für Wirksamkeit nötig.
`reviewed_at` folgt dem obigen Zeitvertrag und liegt nicht nach `evaluated_at`.
Die Kennung muss exakt `human_review_id` entsprechen. Die bestehenden
Relationsreview-Artefakte belegen allein keine Waiver-Freigabe.

Wie beim bestehenden Requirement-Approval-Adapter muss ein ausdrücklich vom
vertrauenswürdigen Host übergebener Reviewprüfer die menschliche Herkunft und
aktuelle Wirkung bestätigen. Seine Beobachtung bindet die vollständige
Bewertungseingabe und den vollständigen Reviewhash. Projekt-JSON kann diesen
Prüfer weder benennen noch importieren. Ohne Prüfer, bei Fehlern, Widerruf,
fremder Bindung oder nicht menschlicher Entscheidung bleibt der Waiver
unwirksam. Dies führt kein Benutzer-/Authentifizierungssystem ein.

**Bestandsdaten.** Unversionierte bisherige Waiver mit Freitext-
`expiry_condition` und Vollartefakthash bleiben unverändert strukturell lesbar.
Der alte Feldreferenzvertrag bleibt für diese historischen Daten erhalten.
Sie liefern den maschinenlesbaren Grund `legacy_waiver_unsupported` und niemals
ein wirksames `waived`. Es gibt keine automatische Migration, Fristverlängerung
oder erfundene Reviewentscheidung. Eine ausdrücklich neu ausgestellte Ausnahme
benötigt die aktuelle Projektion, exakten Scope/Konfiguration, eine UTC-Frist
und einen passend bestätigten menschlichen Review. Alte Quellbytes werden
beim Lesen nicht verändert.

**Bewertung und Speicherung.** Der gespeicherte Status bleibt ausschließlich
`verification_plan_status`. Ein gültiger aktiver Waiver liefert im getrennten
Waiver-Teilbericht `waiver_result=waived`, andernfalls `ineffective` mit Gründen;
nie `passed`. Dies ist kein vollständiges `verification_result`: dessen
Prioritäten, insbesondere Nichtanwendbarkeit, bleiben 10.5 vorbehalten. Der
Teilbericht und seine Prüferbeobachtung werden nicht im Subject gespeichert.
Ein vorbereiteter Workflowupdate enthält nur Status und gegebenenfalls Waiver,
bindet erwartete Revision/Vollhash und geht durch den vorhandenen gemeinsamen
Writer. Vorbereitung ist weder Schreibautorisierung noch vollständige Validation.

#### 10.5.6 Release-Readiness-Vertrag v1

Dieser Vertrag konkretisiert SR-REQ-0125/0126/0127/0141/0450/0516. Eine
Readinessentscheidung MUSS alle folgenden Pflichtgates auf derselben gebundenen
Eingabe auswerten. Warnungsschwellwerte, leere Listen, fehlende Provider und
unbekannte Statuswerte DÜRFEN keine Pflicht stillschweigend entfernen.

**Geschlossene Policy.** `release.readiness_policy` verwendet die Schemaidentität
`release-readiness-policy-v1`. Das Objekt enthält genau folgende Felder;
unbekannte Felder sind unzulässig:

| Feld | Vertrag |
|---|---|
| `format_version` | Pflicht, exakt `1.0.0` |
| `verification_evaluation` | optional; falls vorhanden vollständiger Descriptor nach 10.5.1, nicht `null`; Auswahlpriorität unverändert nach 10.5.4 |
| `blocker_decisions` | Pflicht; Array der unten definierten Entscheidungen, darf leer sein; höchstens ein Eintrag pro `subject_id`, normalisiert nach ID in UTF-8-Byteordnung |

Die Version legt alle Gates verbindlich fest. Es gibt in v1 keine
Abschaltflags, konfigurierbaren Risiko-Schwellen, Statusaliasse oder frei
ausführbaren Regeln in dieser Policy. Die kleinste neue Policy ist
`{"format_version":"1.0.0","blocker_decisions":[]}`. Sie gewährt ohne vollständige
Prüfeingaben keine positive Readiness. `policy_sha256` ist SHA-256 der
RFC-8785-Kanonisierung der normalisierten vollständigen Policy. Defaults dürfen
nur bei ausdrücklich beauftragtem Authoring materialisiert werden.

**Umfang und Pflichtgates.** Der gespeicherte Release-Scope wird mit dem
gemeinsamen Scope-/Konfigurationsdienst vollständig aufgelöst. Sämtliche
erreichten Pflichtabhängigkeiten außerhalb der Release-Seeds bleiben enthalten;
der Bericht kennzeichnet sie als extern. Auswahl und Closure folgen 10.8 und
werden weder aus vorhandenen Nachweisen noch aus `blocker_decisions` abgeleitet.
Nicht auflösbare Pflichtziele, unbekannte Anwendbarkeit und konfigurativ
ausgeschlossene Pflichtabhängigkeiten blockieren. Ein erforderlicher Rand darf
nicht zu einer optionalen Boundary Reference abgeschwächt werden.

| Gate-ID | Geltung und notwendiges Passkriterium |
|---|---|
| `scope` | Eine gültige v1-Policy sowie ein vollständiger, gültiger, geschlossener Release-Scope mit genehmigtem Descriptor und exakt aufgelöster Konfiguration; keine ungeklärten Pflichtgrenzen. Policybefunde gehören zu diesem Gate. |
| `approval` | Jedes anwendbare Scope-Artefakt erfüllt sein typspezifisches Gate nach 9.4/9.6 und hat `maturity=approved`. Das umfasst den Release selbst, externe Pflichtartefakte sowie die für Pflichtnachweise verwendeten Records; technische Profil-/Konfigurationsdateien sind keine zusätzlichen Artefakte. Bei Requirement-Freigaben bleibt der aktuelle menschliche Review nach 12.2 erforderlich. Ein gespeichertes Label allein ersetzt keine Gateprüfung; `retired` erfüllt eine aktuelle Pflicht nicht. |
| `implementation` | Jede anwendbare Capability, jedes Requirement, jede Component, jedes Interface und jeder Task besitzt `implementation_status=implemented`. Für Tasks sind zusätzlich sämtliche Done-Kriterien aktuell durch den bestehenden Done-Dienst belegt. `not_started`, `in_progress`, `blocked` und ein bloß gespeichertes `not_applicable` bestehen dieses Gate nicht. Andere Artefakttypen erhalten keine erfundene Umsetzungspflicht. |
| `verification` | Für alle anwendbaren Capabilities, Requirements und Tasks ist das berechnete Ergebnis nach 10.5 einschließlich aller Pflichtslots und maßgeblichen Läufe `passed`. Die bestehende Prioritätsfolge wird unverändert benutzt. `waived`, `not_evaluated`, `running`, `failed`, `incomplete` und `stale` bestehen das Gate nicht. Eine wirksame Verification-Ausnahme ist in dieser Release-Policy keine Freigabe. |
| `coverage` | Die unabhängig ermittelte Pflichtmenge aus dem vorigen Gate ist vollständig mit Contracts beziehungsweise zulässigen impliziten Testcontracts, erklärten Testbezügen und aktuellen bestandenen Nachweisen belegt. Fehlender Contract, fehlender erforderlicher Testbezug, fehlende Evidence und stale Evidence werden getrennt berichtet. Ein expliziter Slot mit zulässigem `test_id=null` verlangt keinen erfundenen ausführbaren Test. Weitere deklarierte Pflichtdimensionen dürfen nicht durch einen Overall-Slot ersetzt werden. |
| `risks` | Jeder anwendbare Risk im Scope erfüllt die unten definierte strikte Risikopolicy. Wahrscheinlichkeit, Impact, Owner, Freitextbegründung oder vorhandene Mitigationsrelation allein entfernen keinen Blocker. |
| `issues` | Jeder anwendbare Issue im Scope erfüllt den unten definierten Abschlussvertrag. Ein begründeter Dauerstatus erlaubt die Freigabe des Issue-Artefakts nach 9.4, aber keine Releasefreigabe bei offenem Issue. |
| `relations` | Jede für Scopezugehörigkeit, externe Pflichtabhängigkeit oder eines dieser Gates verwendete verpflichtende Relation hat nach dem bestehenden Relationsreview-Dienst exakt `current`. `unreviewed`, `stale`, `rejected`, fehlender Review und unbekannte Ergebnisse zählen nicht als erfüllt. Fehlende erforderliche Relationen bleiben fehlende Pflichten. |

Ein Gate ohne anwendbare Subjects wird ausdrücklich als `not_applicable` mit
leerer erwarteter Subjectmenge ausgewiesen; das ist nur nach vollständig
erfolgreicher Scope-/Anwendbarkeitsauflösung zulässig. Ein leeres oder teilweise
aufgelöstes Modell ist kein solcher Nachweis. Der Release selbst unterliegt
immer `scope` und `approval`. Bei korrekt konfigurationsbedingt ausgeschlossenen
optionalen Artefakten werden Ausschlussgrund und Konfigurationsbindung genannt;
das Verbot, ausgeschlossene Pflichtabhängigkeiten zu übergehen, bleibt bestehen.

**Risiko- und Issue-Status.** Die folgende Klassifikation ist abschließend und
exakt, ohne Groß-/Kleinschreibungs-, Sprach- oder Synonymnormalisierung:

| Feld und Wert | Readinesswirkung |
|---|---|
| `risk_status=open` oder `in_progress` | blockierend; auch bei niedriger Wahrscheinlichkeit oder geringer Auswirkung |
| `risk_status=mitigated` oder `closed` | nur mit gültiger Entscheidung `risk_eliminated` erfüllbar; diese bestätigt die vollständige Beseitigung. Bloße Reduktion mit Restrisiko verlangt stattdessen `accepted`. |
| `risk_status=accepted` | nur mit gültiger explizit menschlicher Entscheidung `risk_accepted` erfüllbar |
| `issue_status=open` oder `in_progress` | blockierend, auch mit `permanent_status_reason` |
| `issue_status=resolved` oder `closed` | nur mit gültiger Entscheidung `issue_resolved` erfüllbar, die sämtliche nichtleeren `resolution_criteria` bestätigt |
| jeder andere gespeicherte Status | `incomplete` mit `unclassified_status`; niemals implizit erledigt, akzeptiert oder nicht anwendbar |

Diese Klassifikation ändert weder die allgemeine Maturity noch beim Lesen den
gespeicherten Status. Ein Terminalwort allein ist kein Abschlussnachweis. Eine
gültige Risikoakzeptanz beseitigt nur diesen Risikoblocker; andere Gates,
insbesondere Verification und offene Issues, bleiben vollständig wirksam.

**Gebundene Blockerentscheidungen.** Eine Entscheidung ist ein passives
Wertobjekt innerhalb der Release-Policy, kein neuer Artefakttyp. Sie enthält
genau diese Pflichtfelder:

| Feld | Exakter Vertrag |
|---|---|
| `subject_id` | ID eines Risk oder Issue des unabhängig aufgelösten Release-Scopes |
| `subject_sha256` | vollständiger kanonischer Artefakthash des aktuell bewerteten Subjects, einschließlich Status, Revision und fachlichen Feldern; 64 kleine Hexzeichen |
| `decision` | exakt `risk_eliminated`, `risk_accepted` oder `issue_resolved`, passend zu Typ und Status aus der Tabelle |
| `reason` | nichtleere fachliche Begründung; keine automatische semantische Auswertung des Texts |
| `scope_descriptor` | vollständiger Descriptor, kanonisch exakt gleich dem bewerteten gespeicherten Release-Scope |
| `configuration_sha256` | bestehender effektiver Konfigurationsmanifesthash einschließlich Elternkette, beziehungsweise ausdrücklich `null` bei unkonfiguriertem Scope; kein Wildcard |
| `human_review_id` | nichtleere Kennung der ausdrücklichen menschlichen Entscheidung |

`decision_sha256` ist SHA-256 der RFC-8785-Kanonisierung von
`{format_version:"release-blocker-decision-v1", release_id:<ID>, decision:<Objekt>}`.
Die Entscheidung liegt im Release, nicht im gebundenen Risk/Issue; ihr Hash und
der Review werden nicht in das Subject geschrieben. Damit entsteht keine
Selbstreferenz. Jede Änderung des gebundenen Subjects, der Scopebeschreibung
oder der effektiven Konfiguration entwertet die bisherige Entscheidung. Alte
Nachweise werden nicht umgebunden; die neue Entscheidung braucht einen neuen
Review. Eine Entscheidung mit fremder Subject-ID erweitert den Scope nicht.

Der passive Review enthält exakt `review_id`, `subject_id`, `decision_sha256`,
`reviewer`, `reviewed_at`, `decision` und `criteria`. Die ersten drei Felder
müssen der aktuellen Entscheidung entsprechen; `reviewer` ist ein Actor mit
`actor_type=human`, `decision` ist `confirmed` oder `rejected`. `reviewed_at`
und der ausdrücklich übergebene Bewertungszeitpunkt `evaluated_at` folgen dem
UTC-Vertrag aus 10.5.5; zukünftige Reviews sind unwirksam. Für `risk_eliminated`
enthält `criteria` genau `{risk_eliminated:true}`, für `risk_accepted` genau
`{residual_risk_accepted:true}`. Für `issue_resolved` ist es genau
`{resolution_criteria:[true,...]}` mit einer Bestätigung pro gespeichertes
Kriterium in dessen Reihenfolge; ein einzelner Kriterienstring ergibt genau
einen Eintrag. Falsche, fehlende und zusätzliche Kriterien bestehen nicht.

Wie bei Requirement-, Task-Done- und Waiver-Reviews prüft ein ausdrücklich vom
vertrauenswürdigen Host übergebener Reviewprüfer die menschliche Herkunft und
die aktuelle Wirksamkeit. Seine Beobachtung bindet den Reviewhash sowie die
vollständige aktuelle Readinesseingabe. Projekt-JSON kann diesen Prüfer weder
benennen noch importieren. Ohne bestätigten Review, bei Widerruf, fehlendem
Prüfer, Prüferfehler oder falscher Bindung bleibt das Gate unerfüllt. Ein
KI-Label oder der Text einer Begründung erzeugt keine menschliche Autorität.
Der aktuelle menschliche Review ist in v1 der Abschlussnachweis für
Risikobeseitigung und Issue-Erledigung; beigefügte Testergebnisse können ihn
stützen, ersetzen aber weder diese Entscheidung noch eigene Pflichtprüfungen.
Ein reines `passed` ohne gebundenes Abschlusskriterium hebt keinen Blocker auf.

**Ergebnis und Bindung.** Die Readinesseingabe bindet `release_id`, den
vollständigen geladenen Modell-/Ressourcenstand, den aufgelösten Scope samt
externen Pflichtabhängigkeiten, effektive Konfiguration, `policy_sha256`,
`evaluation_sha256` beziehungsweise `null` und `evaluated_at`. Native
Provider-/Reviewbeobachtungen müssen zu genau dieser Eingabe passen; ein
ungebundenes `passed` oder ein boolesches Freigabeflag ist kein Nachweis.
Die Schemakennung der Ergebnisprojektion ist `release-readiness-v1`. Sie nennt
`ready` als Boolean, `status` als `ready|blocked|incomplete`, `provisional` als
Boolean, die Eingabebindung und alle acht Gates in obiger Reihenfolge. Jeder
Gateeintrag enthält `gate_id`, `status` aus
`passed|failed|incomplete|not_applicable`, erwartete `subject_ids`, verwendete
Nachweisbindungen und `findings`. Jedes Finding nennt `gate_id`, `subject_id`
oder `null` bei Scope-/Policybefunden, `reason`, `blocking=true` und die
betroffenen Nachweis-/Relations-IDs. Listen werden deterministisch nach
Gate-Reihenfolge, Subject-ID und Grund sortiert; IDs in UTF-8-Byteordnung.

`ready=true` gilt genau dann, wenn alle Gates `passed` oder nachgewiesen
`not_applicable` sind. Bei mindestens einem `failed` ist der Gesamtstatus
`blocked`, sonst bei mindestens einem `incomplete` ist er `incomplete`;
beides bedeutet `ready=false`. Alle weiteren Befunde bleiben erhalten.
Bekannte offene Blocker, negative Reviews, nicht aktuelle Pflichtrelationen
und fehlgeschlagene Pflichtprüfungen ergeben `failed`; fehlende oder stale
Nachweise, unklassifizierte Daten und nicht verfügbare Provider ergeben
`incomplete`. Eine bekannte unerfüllte Freigabe oder Umsetzung ergibt `failed`.
Im Verification-Gate ergibt `waived` den Status `failed`; `running` und
`not_evaluated` ergeben `incomplete`. Ein unerwartetes `not_applicable` für ein
nachgewiesen anwendbares Subject ist ebenfalls `incomplete`. Die Originalwerte
der Provider bleiben jeweils im Bericht erhalten.
Warnungsfilter beeinflussen diese Fachentscheidung nicht. Ein vollständig
berechnetes fachliches Negativergebnis von `release readiness` ergibt Code 3,
auch wenn alle zugrunde liegenden Diagnosen nur Warnungen sind. Vorrangige
Eingabe-/Konflikt-/Berechtigungsfehler behalten ihren bestehenden Code.

Gespeicherte `verification_evaluation` hat weiterhin Vorrang nach 10.5.4.
Eine identische CLI-Auswahl ist zulässig, eine abweichende Auswahl ist Code 6.
Ohne gespeicherte Auswahl ist eine explizite externe Bewertung höchstens
vorläufig (`provisional=true`), selbst wenn alle Gates bestanden sind. Nur
`ready=true` und `provisional=false` mit gespeicherter Auswahl erlauben später
das Release-Baselinegate. Readiness wird nicht in Artefakte zurückgeschrieben
und stellt selbst weder eine Lifecycle-Freigabe noch Schreibautorität dar.

**Bestandsdaten und Migration.** Bereits gespeicherte leere oder unversionierte
Policies sowie freie Risk-/Issue-Statuswerte bleiben unverändert lesbar.
Eine fehlende Policyversion ergibt `legacy_readiness_policy_unsupported` und
keine Readiness; ein vorhandener unbekannter Versionswert beziehungsweise
unzulässige Felder in einer v1-Policy sind ein Schemafehler (Code 3). Auch bei
Legacy-Daten bleibt die bestehende `verification_evaluation`-Auswahlpriorität
einschließlich Konfliktprüfung erhalten; sie allein gewährt keine Freigabe.
Es gibt kein automatisches Übersetzen von Statuswörtern, kein Auffüllen von
Reviews und keine Änderung vorhandener Evidence. Migration erfolgt nur
ausdrücklich über den normalen Change Plan mit geprüfter erwarteter Basis,
expliziter Policy-/Statusauswahl und gegebenenfalls neuen menschlichen Reviews.
Bis dahin bleiben die fachlichen Lücken maschinenlesbar `incomplete` und
`ready=false`. Bereits versiegelte Baselines und historische Resultate bleiben
an ihre damaligen unveränderten Bytes gebunden.

### 10.6 Transaktionszustände

| Zustand | Bedeutung | Zulässiger nächster Zustand |
|---|---|---|
| `building` | Journal und Payload werden aufgebaut | `prepared`, `rolled_back`, `corrupt` |
| `prepared` | Endstand vollständig validiert, befehlsspezifische Gates bestanden und dauerhaft gestaged; noch kein Zieleintrag veröffentlicht | `committing`, `rolled_back`, `corrupt` |
| `committing` | mindestens eine Zieldatei darf veröffentlicht sein | `committed`, `rolling_back`, `corrupt` |
| `committed` | vollständiger Zielstand und Receipt vorhanden | Endzustand |
| `rolling_back` | Before Images werden restauriert | `rolled_back`, `corrupt` |
| `rolled_back` | vollständiger Basisstand wiederhergestellt | Endzustand |
| `corrupt` | automatische Entscheidung nicht sicher möglich | nur verifizierte manuelle Restore-Transaktion |

Normale Projektbefehle dürfen ein Modell erst laden, wenn keine unvollständige oder korrupte Transaktion besteht. Betriebsdiagnosen dürfen die dafür notwendigen Metadaten nach Anhang N.3 schreibfrei untersuchen. Eine automatische Recovery ist ausschließlich für tatsächlich schreibberechtigte Aufrufe zulässig und führt in diesem Lauf noch keine neue Fachoperation aus.

### 10.7 Recovery-Entscheidung

`recover discard` ist nur für `building` oder `prepared` zulässig, wenn das Journal null veröffentlichte Zieleinträge nachweist und die aktuelle Projektwurzel der Basiswurzel entspricht. `committing` und `rolling_back` werden ausschließlich auf die vollständige Basis- oder Zielwurzel recovered. `corrupt` blockiert normale Projektbefehle. `recover restore --from <project-bundle|baseline>` verwendet ausschließlich den nach 10.7.1 vollständig qualifizierten und vor Write gebundenen Restore-Plan. Ein intern gültiger Teil-Snapshot ist keine hinreichende Restore-Quelle. Jede tatsächlich ausgeführte Recovery-Aktion erzeugt einen unveränderbaren lokalen Auditdatensatz; eine abgewiesene Vorprüfung liefert ihren Bericht schreibfrei.

#### 10.7.1 Vollständige Quelle und erhaltende Restore-Policy `restore-preserve-v1`

Ein Restore wird in zwei expliziten Aufrufen vorbereitet und ausgeführt: `recover restore --from <SOURCE> --dry-run --output <EXTERNAL-PLAN>` erstellt ohne Projekt-/Betriebswrite einen gebundenen Restore-Plan; `recover restore --plan <EXTERNAL-PLAN> --expected-target-root <SHA256>` führt genau diesen Plan aus. Die getrennte ausdrückliche Auswahl alter aktiver Journale für Ausführung und Fortsetzung folgt 10.7.4. Quelle und Plan dürfen nicht gleichzeitig angegeben werden. Ein Aufruf ohne Dry-Run und ohne geprüften Plan wird mit Code 2 abgewiesen. Der Plan ist ein Recovery-Fachformat, kein regulärer Change Plan eines vermeintlich konsistenten Arbeitsstands. Er enthält `policy_version=restore-preserve-v1`, `project_id`, Quellart, Quellbytehash, Quell-Snapshotwurzel, Quell-Descriptor, gebundene Bestandsinventur, zusätzliche Erhaltungsobjekte, erwartete vollständige Zielwurzel, Zielpfade/-bytes/-hashes und die separat gehashte Sicherungsinventur.

**Quellenqualifikation:** Zulässig sind ausschließlich (a) ein vollständig verifiziertes `project`-Bundle mit `read_only=false` oder (b) eine unveränderte `sealed` Baseline mit exakt `scope_kind=project`, Selector `{}`, `configuration_id=null`, `boundary_policy=closed`, vollständiger rekursiver Objektclosure und gültigem Manifest. Eine Baseline mit specification-, release-, document-, query-, explicit- oder konfiguriertem Scope ist auch bei gültigem Hash unzulässig. Der Baseline-Typ `working` oder `release` ersetzt diese Scopeprüfung nicht. Quellprojekt-ID und Zielprojekt-ID müssen gleich sein; bei beschädigter Konfiguration ist die ID aus unabhängig hashgebundenen Receipts, einer erhaltenen Baseline oder dem vorliegenden Recovery-Inventar zu bestätigen. Widersprüchliche oder nicht nachweisbare Identität wird nicht geraten.

Die Quelle muss alle fachlichen Dateien, semantische Konfiguration, aktiven Profile/Regeln/Mappings, notwendigen Anhänge, historischen Originalbytes, referenzierten Archive und Reservierungsinformationen des vollständigen Quellsnapshots liefern. Insbesondere muss das exakt eine Primärspezifikationsdokument rekonstruierbar sein. Nicht in der Quelle enthaltene mutable Projektdateien werden nicht stillschweigend als Füllmaterial aus dem beschädigten Arbeitsstand verwendet. Fehlende Bytes, Hashfehler oder Boundary References verhindern die Quellenqualifikation. Vorhandene gleichhashige Dateien dürfen ausschließlich als bytegeprüfte Speicheroptimierung dienen, nie als zusätzliche semantische Auswahl.

**Vollständiges Ziel und Historienerhaltung:** Ausgang des Zielplans ist der vollständig rekonstruierte Quellsnapshot. Bei einer Baselinequelle werden die Baseline-Datei selbst und ihre vollständigen Snapshotobjekte als explizite Erhaltungsobjekte hinzugefügt, soweit sie vor der Baseline-Erzeugung noch nicht in ihrem eigenen Snapshot vorhanden waren. Dies ist keine rekursive Erweiterung des gespeicherten Baseline-Manifests; dessen Originalbytes und Quellwurzel bleiben unverändert.

Zusätzlich bleiben alle noch bytegültig verfügbaren unveränderbaren Evidence-, Baseline-, Relationsreview-, abgeschlossenen Proposal- und Legacy-Ressourcen samt ihren referenzierten Original-/Archivbytes erhalten. Identische Identität/Bytes werden dedupliziert; gleiche Identität mit abweichenden unveränderbaren Bytes ist ein Konflikt, keine Überschreibungsentscheidung. Für eine erhaltene historische Ressource werden keine fehlenden aktuellen Fachartefakte erfunden. Fehlt eine zur strukturellen Gültigkeit notwendige Ressource auch in der vollständigen Quelle, wird der Restore abgewiesen. Ein historisch stale Nachweis ist dagegen nicht automatisch strukturell ungültig.

Aus aktuell lesbaren Artefakten, verifizierten vorhandenen Baselines und abgeschlossenen Receipts bekannte jemals freigegebene Standardartefakte dürfen nicht aus dem normativen Ziel verschwinden. Der Quellsnapshot muss ihre Identität weiter enthalten; eine nachweislich erfolgreich veröffentlichte höhere Revision darf nicht als normale Historienänderung durch eine niedrigere ersetzt werden. Wo die vorhandenen Belege keine sichere Unterscheidung zwischen veröffentlichtem Stand und unterbrochenem Zwischenstand erlauben, wird eine passendere vollständige Quelle verlangt statt Historie zu erraten. Das ist ein Integritäts-/Datenblocker, kein Budgetabbruch. Diese erhaltende Policy führt keinen automatischen semantischen Merge durch. Ein bloßer Wunsch, auf einen älteren fachlichen Stand zurückzukehren, wird als gesonderter autorisierter Change Plan im wiederhergestellten Projekt behandelt.

Der Plan weist `source_snapshot_root` und `expected_target_root` getrennt aus. Die Zielwurzel wird **nach** sämtlichen ausdrücklich gelisteten Historienergänzungen über den vollständigen project-Scope berechnet; sie muss nicht der Quell-Snapshotwurzel gleichen. Bereits konsistente, außerhalb der Zielinventur liegende Repositorydateien einschließlich `.git` und Quellcode werden nicht verändert. Abgeschlossene lokale Receipts werden nicht stillschweigend gelöscht; ihre erneute Verwendung unterliegt weiterhin Projekt-, Request- und Hashbindung. Eine alte Erfolgsquittung ist kein Nachweis, dass jede ihrer Wirkungen noch zum gewählten Zielstand gehört.

**Vor Veröffentlichung:** Der gesamte rekonstruierte Zielstand besteht Schema-, Identitäts-, Referenz-, Lifecycle-, Archiv-/Legacy- und Scope-Integritätsprüfungen. Er ist ein vollständiges Projekt, keine scheinbar reparierte Teilmenge. Fachlich negative, korrekt gespeicherte Reviews oder Testergebnisse dürfen erhalten bleiben; sie werden im Restore-Bericht als verbleibende fachliche Befunde gezeigt und nicht in bestandene Readiness umgedeutet. Vorhandene `approved`-Invarianten dürfen nicht verletzt bleiben; andernfalls ist eine passende Quelle notwendig. Es wird keine stillschweigende fachliche Statuskorrektur beim Restore erfunden.

**Sicherung und Commit:** Alle durch den Restore zu ersetzenden oder zu entfernenden bisherigen Bytes einschließlich beschädigter Dateien, sämtlicher betroffener Journale und historischer Zusatzinformationen werden vor Veröffentlichung unverändert in einer content-addressierten lokalen Sicherungssektion unter `.specroad/recovery/archive/` dauerhaft gesichert. Nicht lesbare notwendige Bestandsbytes, eine unvollständige Sicherung oder unzureichender echter Speicher verhindern den Commit; es gibt kein stilles Data-Loss-Flag. Die Sicherung ist ausdrücklich betrieblich und nicht Bestandteil der neuen fachlichen Modellwurzel. Sie ersetzt nicht die oben verlangte Erhaltung normativer unveränderbarer Ressourcen.

Der spezialisierte Recovery-Lock, vollständig synchronisiertes Staging, Before Images und ein separates Restore-Journal binden den Plan. Vor Write werden Quellen-, Inventur- und erwarteter Zielhash nochmals verglichen. Ein veränderter Input ergibt Code 6 ohne Veröffentlichung. Nach echtem Hostabbruch bleibt das Projekt gesperrt, bis das Restore-Journal entweder vollständig auf das geprüfte Ziel abgeschlossen oder auf die bytegetreue gesperrte Ausgangslage zurückgerollt ist. Erst wenn sämtliche Zielbytes und die vollständige Zielwurzel stimmen und das Audit dauerhaft vorliegt, werden normale Projektbefehle freigegeben. Das alte korrupte Journal bleibt archiviert.

Eine unvollständige/unzulässige Quelle ergibt Code 3 mit präzisem Quellen-/Vollständigkeitsbefund; eine widersprüchliche Projektidentität oder eine kollidierende geschützte Historie Code 6; Sicherheitsverletzung Code 7; tatsächliches I/O-/Sicherungsproblem Code 5. Weiche Arbeitsbudgets folgen unverändert Anhang O/P und erlauben sichere Vorbereitung in mehreren Schritten. Vor Abschluss der Quellenqualifikation und Stagingprüfung beginnt keine Veröffentlichung.

#### 10.7.2 Gebundener Restore-Plan `restore-plan-v1`

**Entscheidung RESTORE-PLAN-CONTRACT, delegiert gemäß SPECROAD-DECISION-1.**
Dieser additive Vertrag konkretisiert ausschließlich das bereits in 10.7.1
verlangte Recovery-Fachformat. Quellenqualifikation, Erhaltung geschützter
Geschichte, vollständige Zielvalidierung, Sicherung, Autorisierung und
Crashabsicherung aus 10.7.1 bleiben Voraussetzung. Ein Plan ist eine passive,
erneut zu prüfende Beschreibung und weder ein regulärer Change Plan noch
ein Erfolgs-, Freigabe- oder Authentizitätsnachweis.

**Geschlossene Hülle.** Der externe Plan besteht aus genau einem kanonischen
UTF-8-JSON-Objekt nach dem vorhandenen RFC-8785-Vertrag, ohne BOM, doppelte
Schlüssel oder nachgestellte Daten. Seine Pflichtfelder sind exakt:

| Feld | Vertrag |
|---|---|
| `format_version` | exakt `restore-plan-v1` |
| `policy_version` | exakt `restore-preserve-v1` |
| `project_id` | nach 10.7.1 unabhängig bestätigte, für Quelle und Ziel gleiche Projekt-ID |
| `project_root` | expliziter kanonischer absoluter Pfad des zu reparierenden Projektroots; ausschließlich lokale Ausführungsbindung, kein Bestandteil der semantischen Modellwurzel |
| `source` | Quellbindung nach dem folgenden Absatz |
| `source_snapshot_root` | unveränderte, aus den vollständigen Quellbytes rekonstruierte native Quellmodellwurzel |
| `source_descriptor` | exakt der qualifizierte unkonfigurierte geschlossene project-Scope nach 10.7.1 |
| `inventory` | vollständige gebundene Beobachtung des relevanten Zielbestands nach untenstehendem Inventurvertrag |
| `preserved` | nach Pfad sortierte zusätzliche Erhaltungsobjekte einschließlich Herkunftsgrund |
| `target` | vollständige Zieldateiinventur `{entries, sha256}` |
| `expected_target_root` | native vollständige project-Modellwurzel nach allen Erhaltungsobjekten, unabhängig vom Byteinventurhash |
| `backup` | separat gebundene Sicherungsdateiinventur `{entries, sha256}` |
| `objects` | deduplizierte Tabelle der tatsächlich benötigten Original- und Zielbytes |
| `restore_plan_sha256` | SHA-256 der kanonischen Hülle unter Ausschluss allein dieses Felds |

Alle hier definierten Objekte sind geschlossen; zusätzliche Felder sind kein
Erweiterungsmechanismus. SHA-256-Werte bestehen aus genau 64 kleingeschriebenen
Hexzeichen. Größen sind nichtnegative JSON-Ganzzahlen, keine booleschen Werte.
Es gibt keine optionalen Erfolgsflags und keine impliziten Null-Defaults.
`source_descriptor` ist vollständig ausgeschrieben: `scope_version=scope-v1`,
`scope_kind=project`, `selector={}`, `configuration_id=null`,
`closure_profile=core-closure-v1`, `boundary_policy=closed`.

**Quellbytes und Herkunft.** `source` hat exakt die Felder `kind`, `root`,
`path`, `size`, `sha256` und `dependencies`. `kind` ist `project_bundle`
oder `baseline`. `root` bezeichnet den expliziten kanonischen absoluten
Quellroot, `path` einen sicheren relativen Pfad darunter. Diese Herkunft
ist eine erneut zu prüfende lokale Bytebindung, keine Vertrauensaussage.
Beim Bundle binden `size` und `sha256` das gesamte unveränderte ZIP;
`dependencies` ist leer. Bei der Baseline binden sie die vollständige
unveränderte Baseline-Quelldatei, nicht nur ihr Manifest oder ihren
kanonischen semantischen Hash. `dependencies` enthält genau die vollständig
rekursiv benötigten Snapshotobjektdateien am nativen Objektpfad unter
demselben Quellroot. Jede Datei wird einmal als `{path, size, sha256}`
aufgeführt, nach UTF-8-Pfadbytes sortiert. Referenzzyklen, fehlende Bytes
und widersprüchliche Objektbindungen werden nicht durch Hashlisten ersetzt.

Der Plan enthält die gebundenen Quelldateibytes und sämtliche benötigten
Abhängigkeitsbytes in `objects`. Aus ihnen MUSS der Leser Quelle, Descriptor,
Closure und Quellwurzel unabhängig rekonstruieren. Ein gespeicherter
`bundle-verify-v1`- oder Baseline-Prüfbericht ersetzt weder diese Prüfung
noch die vollständigen Qualifikations- und Zielgates aus 10.7.1. Insbesondere
ist ein bloßer Container-/Closure-Erfolg ohne die erforderliche vollständige
Projektprüfung keine Restorequalifikation. Ein `release`-Baseline-Typ ist
nur bei dem unabhängig qualifizierten vollständigen project-Scope zulässig;
ein release-Scope wird dadurch niemals zugelassen.

Bei Baselines fehlen operative Konfigurationswerte gegebenenfalls bewusst
in der semantischen Snapshotprojektion. Zur Herstellung der vollständigen
Zieldatei `specroad.json` MÜSSEN diese Werte explizit für die Planung geliefert
und in den exakten Zielbytes gebunden werden. Sie DÜRFEN NICHT aus einem
beschädigten Arbeitsstand geraten oder zum Ergänzen semantischer Quellwerte
benutzt werden. Ihre vorhandene Klassifikation als operativ bleibt erhalten;
die semantische Konfiguration muss exakt zur Quelle passen. Bei einer
Bundlequelle bleiben deren bereits vorhandene Konfigurationsbytes erhalten.

**Bestandsinventur.** `inventory` enthält exakt `roots`, `entries`, `sha256`.
`roots` ist die sortierte, redundanzfreie Liste sicherer relativer Datei-
oder Teilbaumwurzeln im `project_root`. Sie umfasst `specroad.json`, die
Vereinigung der für Quelle und nachweisbaren bisherigen Projektbestand
geltenden `managed_paths` sowie die Recovery-/Receipt-Namensräume
`.specroad/transactions`, `.specroad/requests` und `.specroad/recovery`.
Überdeckte Unterwurzeln werden entfernt. Bei beschädigter Konfiguration
MÜSSEN die bisherigen Deklarationen aus unabhängig gebundenen erhaltenen
Projektbelegen ermittelt werden; eine frei gewählte Teilinventur ist kein
Ersatz. Ist die relevante Bestandsabdeckung nicht sicher bestimmbar, wird
kein vollständiger Plan ausgestellt. Quell- und Zielprojektidentität
werden weiterhin nach 10.7.1 geprüft, nicht allein aus einem Pfad oder
einer vom Aufrufer behaupteten ID übernommen.

Unter jeder Inventurwurzel werden sämtliche vorhandenen regulären Dateien
und Verzeichnisse einschließlich der Wurzel beobachtet. Ein vorhandener
Dateieintrag ist exakt `{path, kind: "file", size, sha256}`, ein Verzeichnis
exakt `{path, kind: "directory"}`. Eine fehlende Inventurwurzel wird als
`{path, kind: "missing"}` gebunden; sonstige fehlende Nachfahren folgen aus
der vollständigen Aufzählung und erhalten keine erfundenen Einträge.
Die Einträge sind eindeutig und nach UTF-8-Pfadbytes sortiert. Links,
Sonderdateien, Pfad-/Großkleinschreibungskollisionen und Durchqueren fremder
Roots behalten die vorhandenen Sicherheitsablehnungen. Beschädigte, aber
lesbare reguläre Bestandsdateien werden mit ihren tatsächlichen Rohbytes
erfasst und nicht durch eine erfolgreiche JSON-Interpretation ersetzt.
`inventory.sha256` ist SHA-256 der kanonischen Projektion `{roots, entries}`.
Auch hinzugefügte oder entfernte Bestandsdateien sind dadurch Eingabeänderungen.

Diese Inventur liest keine Git-Inhalte und erklärt unbekannte Dateien
nicht automatisch zu normativen Ressourcen oder zulässigen Löschzielen.
Ein in `managed_paths` enthaltener bisher nicht unterstützter Inhalt darf
nicht still ausgelassen werden. Nicht betroffene Repositorydateien bleiben
nach 10.7.1 erhalten. Lockdateien, Caches und generierte Ausgaben außerhalb
der gebundenen relevanten Namensräume gehören nicht zur Fachinventur;
ihre vorhandenen Host-/Sicherheitsprüfungen entfallen dadurch nicht.
Der bestehende native Root-/Pfadschutz muss während der Beobachtung und
erneut unter dem Recovery-Lock die tatsächliche Rootidentität prüfen.
Ein übereinstimmender Pfadstring allein genügt nicht.

**Ziel, Erhaltung und Sicherung.** `target.entries` und `backup.entries`
verwenden jeweils exakt `{path, size, sha256}` pro Datei, eindeutig und
nach UTF-8-Pfadbytes sortiert. Ihr jeweiliges `sha256` ist SHA-256 der
kanonischen `entries`-Liste. `target` enthält sämtliche tatsächlich geplanten
Zieldateien einschließlich des vollständigen normativen Projekts, seiner
Konfiguration und der rekursiv nötigen Archiv-/Originalbytes. Etwaige nach
den bestehenden Bundle-/Receiptverträgen zulässige transportierte Receipts
werden ausschließlich an ihren getrennten operativen Pfaden gebunden und
geprüft, niemals als Modellressourcen in die semantische Zielwurzel gehasht.
Der Plan erlaubt weder zusätzliche Receiptarten noch das Überschreiben
kollidierender vorhandener Receipts. Die Pflicht zur bytegetreuen Erhaltung
abgeschlossener lokaler Receipts bleibt auch außerhalb der Zieldateiliste.

`preserved` enthält genau die nach 10.7.1 gegenüber dem rekonstruierten
Quellsnapshot zusätzlich normativ zu erhaltenden Dateien als
`{path, size, sha256, reasons}`. Operative Receipts sind keine solchen
normativen Erhaltungsobjekte. `reasons` ist
eine nichtleere, sortierte, duplikatfreie Liste aus `source_baseline`,
`source_archive`, `protected_history`, `protected_dependency`. Die ersten
beiden Gründe bezeichnen die Quellbaseline selbst und ihre zusätzlich
erforderlichen Snapshotobjekte; die letzten beiden bezeichnen die nach
10.7.1 erhaltenen unveränderbaren historischen Ressourcen und deren nötige
Original-/Archivclosure. Mehrere belegte Gründe teilen sich genau einen
Eintrag. Für jeden Eintrag müssen `path`, `size` und `sha256` identisch
in `target.entries` enthalten sein; `reasons` gehört nur zu `preserved`.
Eine bereits im Quellsnapshot vorhandene Datei wird nicht zusätzlich
aufgeführt. Identitätskonflikte werden vor der Deduplizierung nach 10.7.1
erkannt; gleichnamige oder gleichhashige Pfade sind kein semantischer Merge.

`expected_target_root` wird mit der bestehenden Modellmanifest- und
project-Closure-Projektion aus allen Zielbytes neu berechnet. Weder der
Quellroot noch `target.sha256` darf dafür eingesetzt werden. Das gilt auch,
wenn die zusätzliche Quellbaseline oder jüngere geschützte Geschichte die
Zielwurzel verändert. Keine ursprüngliche Baseline, Evidence oder Review-
Hashbindung wird dafür umgeschrieben. Strukturell gültige negative fachliche
Befunde bleiben erhalten und werden im separaten Restorebericht ausgewiesen;
sie werden nicht als bestandene Readiness oder Freigabe interpretiert.

`backup` bindet die tatsächlichen bisherigen Bytes aller zu ersetzenden
oder zu entfernenden Dateien und sämtlicher nach 10.7.1 betroffenen Journale,
Vorher-/Stagingbilder und historischen Zusatzinformationen. Es ist aus der
vollständigen Bestandsbeobachtung und dem geprüften Ziel abzuleiten, keine
frei reduzierbare Auswahl. Die aufgeführten Dateiwerte müssen mit den
Bestandseinträgen übereinstimmen. Die abgeleiteten Lösch-/Ersetzungswirkungen
dürfen keine außerhalb des erlaubten Restoreumfangs liegende Datei betreffen.
Die spätere betriebliche Sicherung unter `.specroad/recovery/archive/`
bleibt zusätzlich zwingend: Planbytes allein sind weder ein dauerhaft
gesichertes lokales Backup noch eine Commitfreigabe.

**Byteobjekte und Hashdomänen.** Jeder Eintrag in `objects` hat exakt
`sha256`, `size`, `data_base64`. Die Tabelle ist nach Hash sortiert und
enthält jeden verschiedenen Byteinhalt genau einmal. `data_base64` ist
die RFC-4648-Standarddarstellung mit notwendigem Padding und ohne
Whitespace; Rückkodierung muss exakt denselben String ergeben. Dekodierte
Länge und Byte-SHA-256 müssen zu `size` und `sha256` passen. Gleiche Hashes
mit verschiedenen Bytes sind ein Fehler, keine Überschreibungsentscheidung.
Die Tabelle enthält exakt die Vereinigung aller durch `source` samt
`dependencies`, `target` und `backup` referenzierten Inhalte; keine
unreferenzierten Zusatzobjekte. Ein Bestandsfile, das weder Quelle noch
Ziel noch Sicherungsinhalt ist, benötigt nur seine Inventurbindung.

Damit binden die Inventurhashes die jeweiligen geordneten Metadaten,
die Objekthashes die wirklichen Bytes und `restore_plan_sha256` die gesamte
Hülle einschließlich Herkunft, operativem Zielroot und aller Byteobjekte.
Es gibt keine Selbstreferenz auf den eigenen Hash oder eine eigene
Plan-Ausgabedatei. Die bestehenden semantischen Hashprojektionen werden
nicht verändert. Hashkonsistenz authentifiziert keinen Ersteller.
Streaming, privates Spooling und checkpointbasierte Vorbereitung nach O/P
bleiben zulässig und nötig; das Format schreibt keine vollständige
In-Memory-Verarbeitung vor. Ein weiches Budget darf weder Objekte entfernen
noch einen Teilplan als vollständigen Plan veröffentlichen.

**Vorbereitung und erneute Prüfung.** Ein auslieferbarer vollständiger Plan
setzt alle Qualifikations-, Identitäts-, Erhaltungs- und Zielprüfungen aus
10.7.1 voraus. Unfertige Work-Zwischenstände sind kein `restore-plan-v1`-
Erfolgsartefakt. Die Vorbereitung verändert weder normative Projektdateien
noch Journale, Locks oder andere Betriebsdateien. Nur nach erfolgreicher
Vorprüfung darf sie den ausdrücklich benannten externen Plan gemäß den
bestehenden sicheren Generated-Output-Regeln veröffentlichen.

Vor jeder Restoreveröffentlichung werden der Plan selbst, seine Original-
Byteobjekte, die tatsächliche Quelle am gebundenen Herkunftsort samt
Abhängigkeiten, die vollständige Bestandsinventur, die geschützte Geschichte
und die vollständige Zielwurzel erneut geprüft. Eingebettete Planbytes
erlauben kein stilles Ignorieren inzwischen geänderter oder verschwundener
Herkunftsdateien. Eine Verlagerung von Quelle oder Ziel erfordert eine neue
explizite Planung; es gibt keinen Pfadfallback oder automatisch umgebundenen
Plan. Der vom Aufrufer separat bestätigte `--expected-target-root` muss
exakt mit der neu berechneten Zielwurzel übereinstimmen. Prüfung und Hash
verleihen keine Autorisierung; aktueller Recovery-Auftrag, sicherer Lock,
Sicherungsdurabilität, Journal und Audit bleiben getrennte Pflichtgates.

Ungültiges Format, unvollständige Quelle/Objekttabelle oder innere
Hash-/Inventurwidersprüche ergeben Code 3; fehlende explizite Pflichtangaben
im Aufruf Code 2. Eine seit der Planung geänderte Quelle, Inventur oder
Zielbindung sowie widersprüchliche Identität oder geschützte Historie ergibt
Code 6; unsichere Pfade/Dateitypen Code 7, tatsächliche I/O-Fehler Code 5.
Für erwartete, inzwischen fehlende Herkunftsdateien gilt die stale-Bindung
Code 6. Ablehnungen der schreibfreien Planung und Vorprüfung dürfen keine
Projekt- oder Betriebswrites erzeugen. Für Fehler nach ausdrücklich
begonnenem Restore gelten unverändert die
erhaltenden Journal-/Sicherungsregeln aus 10.7.1; kein globaler Rollback durch
Löschen von Nachweisen. Bestehende Change-Plan-, Bundle-, Baseline- und
Workformate bleiben unverändert und werden nicht implizit als Restoreplan
akzeptiert. Implementierung und Verhaltensevidence folgen in 15.j–15.l.


#### 10.7.3 Gebundene Restore-Ausführung und Fortsetzung `restore-execution-v1`

Diese Regel konkretisiert den bereits verlangten getrennten Restore-Journal-
und Sicherungsablauf aus 10.7.1. `restore-plan-v1`, seine geschlossene Hülle,
Quell-/Zielhashes und Bestandsinventur bleiben unverändert. Ein Restore ist
kein Change Plan eines vermeintlich gültigen Ausgangsmodells; für beschädigte
Ausgangsbytes DARF keine erfundene semantische Basiswurzel eingesetzt werden.
Die folgende Bindung ist eine betriebliche Ausführungsbindung, keine neue
normative Modellressource und keine Freigabe durch einen Planhash.

**Anfangsbindung und Autorisierung.** Vor dem ersten Restore-Betriebswrite
MÜSSEN der vollständige Plan, der separat bestätigte Zielroot, die aktuelle
Herkunft samt Abhängigkeiten, Projektidentität und gesamte Bestandsinventur
nach 10.7.1–10.7.2 geprüft sein. Ein eigens für diesen Restore gehaltener
nativer Recovery-Lock bindet den tatsächlichen Projektroot; derselbe Mutex
schließt normale Writer und andere Recovery-Aufrufe aus. Unter diesem Lock
MÜSSEN die Bindungen unmittelbar vor Beginn erneut stimmen. Ein bestehender
Owner wird niemals durch das Lesen eines Plans oder wegen einer fehlenden
PID entfernt; Übernahme, Risikozustimmung und Nachweise folgen unverändert
dem bestehenden Lockvertrag. Ein korrupter alter Transaktionsinhalt darf als
zu sichernde Originalbytefolge inventarisiert werden; er darf weder als
konsistentes Modell noch als Beweis einer freien Sperre dienen.

Jeder beginnende oder fortsetzende Write braucht einen aktuellen Recovery-
Auftrag und die bestehende gesonderte Autorisierungsprüfung. Der Auftrag
bindet mindestens Aktion, Projekt-/Rootidentität, Originalplanhash,
Originalquellhash, Inventurhash, Zielroot, Ziel- und Sicherungsinventurhash,
Akteur und die nach den bestehenden Regeln vorhandene Request-ID. Deren
bestehende Pflicht-/Optionalitätsregeln bleiben unverändert. Actorlabels,
Planfelder, Journalbytes oder ein gespeichertes `authorized=true` ersetzen
keine aktuelle Berechtigung. Ursprünglicher Akteur/Request und späterer
Recovery-Akteur werden getrennt auditiert; ein Resume schreibt die ursprüngliche
Auftragsidentität nicht um. Eine abweichend wiederverwendete Requestbindung
bleibt Code 6; es wird kein gewöhnliches Change-Plan-Erfolgsreceipt erfunden.

**Eigene Betriebswrites und dauerhafte Erhaltung.** Der Restore erhält eine
lokal eindeutige Ausführungskennung. Sein getrenntes Journal bindet diese
Kennung, die Regelversion, den unveränderten vollständigen Originalplan,
die geprüfte Auftragsbindung und die genaue eigene Dateiinventur. Es bleibt
für normale Projektbefehle als ungelöster Recoveryzustand sichtbar. Die
Implementierung MUSS die bestehende sichere, descriptorgebundene Lock-,
Datei-, Staging- und Sync-Infrastruktur wiederverwenden; eine allgemeine
Umgehung der Journal- oder Rootprüfung ist unzulässig.

Vor `committing` MÜSSEN alle zu ersetzenden/entfernenden Bestandsbytes,
betroffenen alten Journale, Before-/Stagingbilder und Zusatzinformationen
vollständig nach 10.7.1 in `.specroad/recovery/archive/` gesichert sein.
Eine content-addressierte Objektkopie MUSS Länge und Hash sowie die
bytegleiche Wiederlesung bestehen. Ein dazugehöriges dauerhaftes Manifest
ordnet jedes Original seinem Pfad und Byteobjekt zu; auch beschädigte,
leere und nicht als JSON lesbare Originale bleiben unverändert erhalten.
Der unveränderte Plan und alle geplanten Zielbytes werden ebenfalls
vollständig gestaged und wiedergeprüft. Neue Dateien und erforderliche
Verzeichnisse samt ihren Eltern werden nach dem bestehenden Durabilitäts-
vertrag synchronisiert. Eine erst begonnene oder nur im Plan enthaltene
Sicherung ist keine bestandene Sicherung. Reale I/O-/Speicherfehler bleiben
Code 5; Pflichtbytes oder Prüfungen werden nicht aus Budgetgründen entfernt.

Die ursprüngliche `inventory` DARF NICHT wegen eigener Writes neu
gehasht oder auf den aktuellen Mischstand umgebunden werden. Bei einer
laufenden Ausführung darf ausschließlich die genaue, separat journalgebundene
Menge ihrer eigenen neu erzeugten Betriebsdateien und benötigten Verzeichnisse
von der Originalinventur unterschieden werden. Keine pauschale Ausnahme für
`.specroad/`, `recovery/`, `archive/` oder einen ganzen Ausführungsordner:
zusätzliche, fremde, unlesbare oder abweichende Einträge sind kein eigener
Fortschritt. Bereits vor Beginn vorhandene Dateien bleiben durch die
Originalinventur gebunden. Eine angebliche Ausführungskennung oder ein frei
neu gehashtes Manifest allein authentifiziert keine eigenen Writes.

**Publikation und Sperre.** Erst nach dauerhafter Sicherung, vollständiger
Zielvalidierung und frischer Prüfung der unveränderten Herkunft und noch
unveröffentlichten Bestandsbindungen wird `committing` dauerhaft gesetzt.
Die exakt aus Plan und Bestand abgeleiteten Ersetzungen, Erzeugungen und
Entfernungen erfolgen in kanonischer UTF-8-Pfadreihenfolge über die vorhandenen
sicheren Primitiven; Verzeichniskollisionen oder fremde Einträge erlauben
kein rekursives Löschen. Der dauerhafte Fortschritt bindet für jeden Pfad
seine ursprünglichen Bytes beziehungsweise Abwesenheit und seine geplanten
Zielbytes beziehungsweise Abwesenheit. Eine Unterbrechung zwischen atomarem
Dateieffekt und Fortschrittswrite MUSS anhand dieser exakten Bindungen
auflösbar sein; ein Cursor allein beweist keinen Dateieffekt.

Alte aktive Journale dürfen erst nach bytegetreu überprüfter Archivierung,
vollständigem tatsächlichem Ziel und dauerhaftem Restore-Abschlussaudit aus
ihrem aktiven Namensraum überführt werden. Vorher und während dieses
Abschlusses hält mindestens ein nachweislich ungelöster Restorezustand normale
Befehle gesperrt. Alte abgeschlossene Receipts und Audits außerhalb der
explizit betroffenen aktiven Journalmenge bleiben an ihren vorhandenen Pfaden
unverändert; die Sicherung ersetzt ihre Erhaltung nicht. Nur die genaue,
geprüfte abgeschlossene Menge darf als passiv gelten. Fremde oder weitere
ungelöste Journale blockieren weiterhin. Ein Terminalmarker ohne passende
Ziel-, Sicherungs- und Auditnachweise hebt die Sperre nicht auf.

**Erneuter Aufruf nach tatsächlicher Unterbrechung.** Ein erneuter
`recover restore --plan <EXTERNAL-PLAN> --expected-target-root <SHA256>`
verwendet für dieselbe Ausführung unveränderte Originalplanbytes und
Auftragsbindungen. Nach aktueller Autorisierung und sicherem Recovery-Lock
wird zuerst genau die gebundene laufende Ausführung untersucht. Ein fehlender
oder geänderter Plan, mehrdeutige aktive Bindungen oder nicht erklärte
Bestandsänderungen beginnen keine neue Transaktion. Die ursprüngliche
Inventur wird mit den journalbelegten eigenen Betriebs- und Dateieffekten
verglichen, nicht durch die Annahme ersetzt, der Mischstand sei konsistent.

| Nachgewiesener Ausführungsstand | Zulässiger Abschluss desselben Aufrufs |
|---|---|
| `building`/`prepared`, keine Zielpublikation | Ausgangsbytes beibehalten, eigene Teilvorbereitung und Originalnachweise erhalten, als zurückgerollte Ausführung auditieren. Keine neue Fachoperation im selben Aufruf. |
| `committing`, sämtliche Zielbytes und geplanten Abwesenheiten bereits erreicht, vollständige Zielwurzel gültig, ursprüngliche Quellenqualifikation journalgebunden belegt, Sicherung und Auftragsbindung gültig | Fehlende Abschluss-/Auditnachweise dauerhaft ergänzen und die geprüften Journalmengen abschließen; keine erneute normative Publikation. |
| `committing` mit nur teilweise erreichtem Ziel; `rolling_back` | Ausschließlich anhand vollständiger überprüfter Before Images auf die bytegetreue ursprüngliche, weiterhin gesperrte Ausgangslage zurückrollen. Kein Vorwärts-Resume eines Teilziels. |
| Beschädigte/fehlende notwendige Journale oder Before Images, nicht erklärter Mischstand, fremde Änderung oder unsichere Pfade | Keine geratenen Writes; Zustand und Nachweise erhalten, Sperre beibehalten und konkreten Integritäts-, Konflikt-, I/O- oder Sicherheitsbefund melden. |

Für ein bereits vollständig veröffentlichtes, genau journalgebundenes Ziel
gilt **SR-REQ-0258**: Nachträgliche Änderung oder Verlust der externen Quelle
rechtfertigt weder das Zurückrollen dieses Ziels noch eine zweite
Publikation. Die fehlenden Abschlussnachweise werden aus den überprüften
ursprünglichen Journal-/Plan-/Sicherungsbytes ergänzt; eine inzwischen stale
Herkunft wird als gesonderte Beobachtung ausgewiesen, nicht als frisch
bestandene Quellenprüfung. Es werden dabei keine normativen Zielbytes mehr
geschrieben. Ein nur teilweise veröffentlichtes Ziel folgt **SR-REQ-0511**.

Ein Rollback aus eigenen dauerhaft gesicherten Originalbytes ist keine
Publikation eines Restore-Ziels aus einer inzwischen geänderten Quelle.
Vor jeder neuen Vorwärtspublikation bleiben sämtliche Herkunftsprüfungen aus
10.7.2 zwingend. Beim Rückrollen darf nur ein durch eigene protokollierte
Effekte erklärbarer Vorher-/Zielzustand verändert werden; fremde Bytes werden
nicht überschrieben. Ursprünglich fehlende Dateien werden nur entfernt,
wenn ihr jetziger Inhalt genau der eigenen veröffentlichten Datei entspricht.
Eine zurückgerollte Ausführung erhält alle alten Sperren sowie ihren
nachvollziehbaren Abschluss; sie ist kein erfolgreich wiederhergestelltes
Projekt. Für einen weiteren Restore ist eine neue ausdrückliche Planung der
nun tatsächlich vorhandenen Inventur erforderlich, keine automatische
Neubindung oder Ausführung im Recovery-Aufruf.

**Abschluss und Berichte.** Ein erfolgreicher Abschluss belegt die wirklichen
Zielbytes, Zielwurzel, Sicherungsobjekte, Erhaltungsinventur, Originalquell- und
Planbindung sowie den dauerhaften lokalen Audit. Der Audit trennt ursprünglichen
Auftrag, beobachtete Dateieffekte, Autorisierungs-/Lockübernahmebelege und
gegebenenfalls Rückroll-/Abschlussaktion. Historische negative fachliche
Befunde bleiben ausgewiesen. Er enthält weder erfundene menschliche Reviews
noch eine Releasefreigabe. Ein erneut vorgelegter bereits abgeschlossener
Auftrag wird nur anhand seines passenden unveränderbaren Abschlussbelegs
behandelt; er führt keine zweite normative Ausführung aus. Eine inzwischen
abweichende Zielinventur erlaubt keinen erneuten Restore unter der alten
Erfolgsbindung und wird als Konflikt Code 6 ausgewiesen.

Bei zurückgerolltem oder ungelöstem Restore wird kein Restore-Erfolg gemeldet;
`recovery_required=true` bleibt sichtbar. Fehlende Pflichtangaben ergeben 2,
ungültige/unvollständige Belege 3, tatsächliche I/O-Probleme oder notwendige
weitere Recovery 5, Bindungs-/Bestandskonflikte 6 und Sicherheits- oder
Berechtigungsverletzungen 7. Diese Präzisierung schafft weder eine
Read-only-Autorecovery noch eine neue Lock-Risikoausnahme. Workfortsetzung,
weiche Budgets und der Verzicht auf freiwillige Pausen während `committing`
folgen weiterhin Anhang N/O/P.

#### 10.7.4 Explizite Auswahl alter aktiver Journale `restore-journal-selection-v1`

**Entscheidung RESTORE-JOURNAL-SELECTION, ausdrücklich vom Nutzer am
26. Oktober 2026 beauftragt.** Die in 10.7.3 genannte „explizit betroffene
aktive Journalmenge“ MUSS durch eine gesonderte, aktuell autorisierte
Pfad-/Hashliste bestimmt werden. Weder das Vorhandensein in der vollständigen
Bestandsinventur noch eine Sicherung, ein Terminalmarker, ein Dateiname oder
ein gleicher Akteur/Request wählt ein altes Journal automatisch aus.

**Geschlossene Auswahl und CLI-Übergabe.** Der Ausführungs- und Wiederanlaufaufruf
aus 10.7.1/10.7.3 erhält die Auswahl über
`--affected-journals <EXTERNAL-SELECTION>`. Die externe Datei MUSS genau ein
kanonisches UTF-8-JSON-Objekt nach dem vorhandenen RFC-8785-Vertrag enthalten,
ohne BOM, doppelte Schlüssel oder nachgestellte Daten. Seine Felder sind exakt:

| Feld | Vertrag |
|---|---|
| `format_version` | exakt `restore-journal-selection-v1` |
| `restore_plan_sha256` | exakt der überprüfte gleichnamige innere Hash des unveränderten Originalplans nach 10.7.2 |
| `entries` | nach UTF-8-Pfadbytes sortierte, duplikatfreie Liste geschlossener Objekte `{path, sha256}` nach untenstehender Projektion |

Ohne die Option wird ausschließlich eine leere Liste normalisiert, mit der
gleichen Regelversion und dem geprüften Originalplanhash. Das bedeutet
„kein altes Journal ausgewählt“, niemals „alle gefundenen Journale“.
Eine ausdrücklich gelieferte leere Liste ist semantisch gleich. Die Option
gehört zur getrennten Ausführung, nicht zur schreibfreien Quellplanung;
sie darf weder den Plan noch dessen geschlossene Hülle erweitern.
Der nichtinteraktive Aufrufer MUSS eine nichtleere Auswahl ausdrücklich
liefern. Ein gespeichertes Journal darf sie nicht als neue Zustimmung
ergänzen. Ihre sichere Lektüre ist keine Erlaubnis zum Ausführen ihrer Inhalte.

**Einheit und Pfad-/Hashprojektion.** `path` MUSS einen vorhandenen, vom
bestehenden Metadatenpreflight als aktiv oder ungeklärt geführten unmittelbaren
Eintrag unter `.specroad/transactions/` oder `.specroad/recovery/` bezeichnen.
Die ganze Transaktions-/Recoverywurzel, Locks, Requests, passive Receipt-/
Audit-/Archivbereiche, gemeinsame Betriebscontainer und beliebige fachliche
Dateien sind keine auswählbaren Journale. Ein Verzeichnisname allein ist kein
Nachweis eines passiven Bereichs; die vorhandenen Typ-/Pfad- und Belegprüfungen
bleiben zwingend. Abgeschlossene Receipts und Audits DÜRFEN NICHT durch die
Auswahl zu löschbaren aktiven Journalen umgewidmet werden. Ungeklärte Einträge
außerhalb dieser auswählbaren Menge bleiben Sperrgründe.

Für einen zulässigen Pfad `p` ist `E_p` exakt die bereits kanonisch geordnete
Teilliste von `inventory.entries` des Originalplans mit `path == p` oder
`path` beginnend mit `p + "/"`. Sie MUSS den Eintrag `p` selbst enthalten,
mit `kind=file` oder `kind=directory`, niemals `missing`. Der Auswahlwert
`sha256` ist SHA-256 der RFC-8785-Bytes der vollständigen Liste `E_p`.
Er ist ausdrücklich ein Inventurhash, nicht der Rohbytehash allein von
`journal.json`. Die Pfade bleiben dabei vollständige projektrelative Pfade.
Damit sind sämtliche Dateinamen, Typen, Größen, Rohbytehashes und auch leere
Verzeichnisse dieses ursprünglichen Eintrags gebunden. Die Hashdarstellung
folgt 10.7.2; zusätzliche Felder und eigene Hashalgorithmen sind unzulässig.

Diese Projektion erlaubt eine eindeutige Auswahl auch bei beschädigten,
leeren oder nicht als JSON lesbaren Journalbytes, ohne deren Inhalt als
gültigen Transaktionsnachweis zu behandeln. Es gibt keine Glob-, Präfix-,
Zeitstempel- oder automatische Nachbarjournal-Auswahl. Die vollständige
Originalinventur bestimmt die Teilbaumgrenze; eine vom Aufrufer verkürzte
Dateiliste ist kein vollständiges `E_p`. Sichere Pfade, Rootidentität,
Links-/Sonderdateiverbote und Kollisionsprüfung gelten unverändert.

**Aktuelle Autorisierung und Sicherung.** Der Recovery-Auftrag nach 10.7.3
MUSS die gesamte normalisierte Auswahl und SHA-256 ihrer kanonischen Hülle
zusätzlich zu seinen bisherigen Projekt-, Originalplan-, Quell-, Inventur-,
Ziel-, Sicherungs-, Akteur- und Requestbindungen enthalten. Die bestehende
aktuelle Autorisierungsprüfung MUSS genau diese Auswahl prüfen; eine bloße
Hashübereinstimmung verleiht keine Befugnis. Die Auswahl wird unverändert im
getrennten Ausführungsjournal und Abschlussaudit gebunden. Aktiver Root-Mutex,
Ownerübernahme und notwendige menschliche Freigaben bleiben eigene Gates.

Vor dem ersten Restore-Betriebswrite und unmittelbar unter dem sicheren
Recovery-Lock MÜSSEN jede Auswahlprojektion und die gesamte Originalinventur
stimmen. Für jede Datei in jedem gewählten `E_p` MÜSSEN `backup` und `objects`
des Originalplans bereits die exakten Originalbytes nach 10.7.2 binden.
Fehlende Sicherungsabdeckung darf nicht erst während der Ausführung ergänzt
werden; dafür ist eine neue explizite Planung nötig. Eine darüber hinaus
gebundene Sicherung wählt keine weiteren Journale aus. Vor `committing`
MÜSSEN alle gewählten Dateien samt Before-/Stagingbildern und Zusatzbelegen
dauerhaft gesichert und bytegleich wiedergelesen sein; das Sicherungsmanifest
erhält auch die gebundene Verzeichnisinventur. Eine leere gewählte
Journalstruktur ist kein Anlass, ihre Typ-/Pfadbindung auszulassen.

**Nicht gewählte Journale und Abschluss.** Nicht gewählte aktive oder
ungeklärte Einträge bleiben unverändert und sperren weiterhin. Vor Beginn
einer neuen Restore-Ausführung verhindert ein solcher übriger Sperrgrund
jeden Restore-Betriebs- und Zielwrite; er wird mit Code 5 und
`recovery_required=true` ausgewiesen. Der Aufrufer muss ihn separat nach
dem bestehenden Recoveryvertrag behandeln oder eine neue ausdrückliche,
passend gebundene Auswahl autorisieren. Es gibt keine stille Erweiterung.

Nur die gewählte ursprüngliche Menge darf nach den vollständigen Sicherungs-,
Ziel- und Auditnachweisen aus 10.7.3 ihren aktiven Namensraum verlassen.
Jeder tatsächliche Überführungsschritt bindet Originalpfad/-inventur,
geprüfte Archivbytes und seinen eigenen Dateieffekt. Bis zum nachgewiesenen
Abschluss hält der eigene Restorezustand die Sperre aufrecht. Ein anderer
Eintrag unter demselben Elternpfad oder ein erst später hinzugefügter Pfad
wird dadurch nicht passiv. Eine nachweislich abgeschlossene Auswahl allein
erlaubt keine Freigabe, solange weitere Sperrgründe bestehen.

Bei Fortsetzung MUSS die normalisierte Auswahl exakt zum ursprünglichen
Auftrag passen; Weglassen einer zuvor nichtleeren Auswahl, Hinzufügen,
Austauschen oder Neu-Hashen verändert diese Bindung. Bereits belegte eigene
Archivierungseffekte werden ausschließlich nach 10.7.3 gegen die ursprüngliche
Auswahl geprüft; aus dem veränderten Arbeitsstand wird keine neue Auswahl
abgeleitet. Fremde Änderungen bleiben Konflikte. Die bestehenden Regeln
für vollständigen Zielabschluss nach SR-REQ-0258 und Teilziel-Rollback nach
SR-REQ-0511 gelten unverändert; ein Rollback erhält beziehungsweise restauriert
die ausgewählten Originale bytegetreu und hebt fremde Sperren nicht auf.

Fehlender Optionswert ergibt Code 2; ungültige Hülle, Sortierung, Dubletten,
Hashdarstellung oder unvollständige erforderliche Sicherung Code 3;
abweichender Originalplan, Auswahlhash, Bestand oder Wiederanlaufauftrag
Code 6; unzulässiger Auswahlbereich, unsicherer Pfad oder fehlende aktuelle
Berechtigung Code 7; echte I/O-Fehler Code 5. Vorprüfungsablehnungen bleiben
schreibfrei. Normale Read-only-Aufrufe erhalten keine neue Recoverykompetenz
und keine tiefe Archivinventur. Einzellauf und Workfortsetzung verwenden
dieselbe Auswahlbindung und dieselben weichen Budgets nach N/O/P.

Diese Auswahlregel ändert weder `restore-plan-v1` noch Modell-/Quell-/
Zielhashes, vorhandene erfolgreiche Receipts oder historische Belege.
Implementierung und Verhaltensabnahme bleiben in 15.l.W/R/C offen.


#### 10.7.5 Explizite Ownerübergabe für Restore `restore-owner-handoff-v1`

**Entscheidung RESTORE-OWNER-HANDOFF, delegiert gemäß SPECROAD-DECISION-1.**
Diese Regel konkretisiert die Ownerbindung aus 10.7.3 für 15.l.R. Ein
neu beginnender Restore hat einen eigenen Auftrag; er ist keine Fortsetzung
der beschädigten gewöhnlichen Transaktion. Die Wiederaufnahme eines bereits
begonnenen Restore behält dagegen dessen ursprüngliche Ausführungsbindung.
Die beiden Fälle DÜRFEN NICHT still ineinander umgedeutet werden. Ein
Planhash, eine Journalauswahl oder ein verwaister Owner allein erteilt
weder eine Übernahmebefugnis noch die Berechtigung zur Restore-Publikation.

**Ausdrücklicher Aufruf.** Ein Ausführungs-/Wiederanlaufaufruf nach
10.7.1/10.7.3/10.7.4 darf einen vorhandenen Owner nur mit zusätzlich
`--force --expected-lock-sha256 <SHA256> --reason <TEXT>` übernehmen.
`--accept-remote-risk` bleibt die bestehende gesonderte ausdrückliche
Risikozustimmung. Ohne diese Zustimmung gilt `false`, auch für eine lokale
KI oder einen früher bereits autorisierten Aufruf. `reason` ist ein
nichtleerer Grund nach dem bestehenden Recovery-Textvertrag; der erwartete
Hash bindet die vollständigen unveränderten Rohbytes des aktuell beobachteten
Lockrecords. Dies sind zusätzliche Bindungen des Recovery-Aufrufs, keine
Felder des geschlossenen `restore-plan-v1` oder der Journalauswahl.

Ohne Übernahmeoptionen bleiben ownerfreie Ausführung und Wiederaufnahme
unter dem aktuellen Recovery-Lock zulässig. Ein vorhandener Owner bleibt
ohne ausdrücklichen Übernahmeauftrag mit Code 5 gesperrt. Unvollständige
Optionskombinationen und Übernahmeoptionen beim schreibfreien `--from`-
Planungsaufruf ergeben Code 2. Ein erwarteter Owner, der fehlt oder inzwischen
andere Bytes hat, ist Code 6; die Erwartung wird nicht aus alten Audits neu
abgeleitet. Ein gültiger Übernahmeauftrag ist noch kein erfolgreicher
Lock- oder Restoreabschluss.

**Zwei getrennte Bindungsfälle.** Vor dem ersten Übernahmewrite MUSS der
Owner gültig lesbar und an dieselbe unabhängig bestätigte Projektidentität
und den tatsächlichen Root gebunden sein. Die folgende Zuordnung ist
zusätzlich zwingend:

| Fall | Erforderlicher Zusammenhang |
|---|---|
| Beginn eines neuen Restore; Owner einer gewöhnlichen alten Transaktion | Der Owner hat `kind=writer` oder `kind=recovery`, bezeichnet keinen `recover restore` und bindet eine sichere Transaktionskennung. Genau der kanonische unmittelbare Pfad `.specroad/transactions/<transaction_id>` dieser Kennung ist ein ausdrücklich ausgewählter Originaleintrag nach 10.7.4. Sein vollständiges `E_p` und dessen Auswahlhash stimmen mit der Originalinventur. Alter Owner einschließlich seiner Request-ID und neuer Restore-Auftrag werden getrennt gebunden; sie müssen nicht dieselbe Transaktions-/Requestidentität haben. |
| Fortsetzung eines begonnenen Restore | Der Owner hat `kind=recovery`, `command=recover restore` und bindet genau die nach 10.7.3 nachgewiesene ursprüngliche Restore-Ausführung sowie deren ursprüngliche Request-ID. Originalplanbytes, Originalauftrag, Auswahl und eigene bisherige Effekte passen. Die aktuelle Recovery-Person beziehungsweise der aktuelle Recovery-Akteur wird zusätzlich auditiert; ursprünglicher Akteur und ursprüngliche Request-ID werden nicht umgeschrieben. |

Im ersten Fall ist der ausgewählte Originaleintrag ausdrücklich auch als
beschädigte reguläre Bytefolge oder als leeres Verzeichnis zulässig, wie
bereits in 10.7.4 festgelegt. Seine Bytes werden gesichert, nicht als gültiges
gewöhnliches Transaktionsjournal interpretiert. Der Zusammenhang wird durch
den **gültigen Ownerrecord**, den kanonisch abgeleiteten Transaktionspfad
und die vollständig gebundene explizite Auswahl bewiesen. Ein ähnlich
benannter Eintrag, ein Requestlabel oder frei behauptete Journalfelder
genügen nicht. Andere ausgewählte Journale bleiben unter ihren bisherigen
Auswahl-/Sicherungsbedingungen; daraus entsteht keine zweite Ownerübernahme.

Ein Restore-Owner darf nicht als gewöhnlicher Altowner behandelt werden,
um einen anderen Restore-Auftrag zu beginnen. Unbekannte, unlesbare oder
widersprüchliche Ownerbindung, fehlende notwendige Ausführungsbelege oder
eine nicht herstellbare Zuordnung bleiben Blocker. Sie werden nicht durch
eine größere Auswahl, einen neuen Planhash oder `--force` geheilt. Gibt es
keinen zugehörigen aktiven Vorgang, bleibt ausschließlich der dafür bereits
zulässige separate Lock-Recovery-Weg maßgeblich; diese Regel ersetzt ihn nicht.

**Unveränderte Host- und Autoritätsgates.** Die Übernahme MUSS denselben
echten nativen Root-Mutex wie Writer und Recovery exklusiv halten. Ein
besetzter Mutex wird niemals umgangen. Der vorhandene native Ownerprüfer
und seine Host-/Prozessstartbindung bleiben maßgeblich: ein lebender Owner
wird auch mit `--accept-remote-risk` abgewiesen; fremde, unprüfbare oder
PID-wiederverwendete Owner benötigen weiterhin die ausdrückliche
Risikozustimmung. Eine fehlende PID allein beweist keine Übernahmereife.

Die aktuelle Host-Autorisierung MUSS die Übernahme als eigene Aktion
`takeover` mit `command=recover restore` prüfen. Sie bindet beide Seiten:
alten vollständigen Ownerrecord samt Rohbytehash, beobachteten Ownerzustand,
Grund, Force-/Risikoangaben, Projekt-/Rootidentität und vollständigen
Restore-Auftrag einschließlich Originalplan-, Quell-, Inventur-, Ziel-,
Sicherungs- und Auswahlbindung. Im ersten Fall kommt die oben bestimmte
alte Pfad-/Inventurbindung hinzu; im Fortsetzungsfall die überprüfte
ursprüngliche Ausführungsbindung. Aktueller Recovery-Akteur und ursprüngliche
Auftragsakteure bleiben unterscheidbar. Ein gespeichertes positives Ergebnis
oder Actorlabel ersetzt diese aktuelle Prüfung nicht. Die gesonderte
aktuelle Berechtigung für Beginn, Rückrollen oder Abschluss des Restore
nach 10.7.3 bleibt zusätzlich erforderlich; Übernahme erlaubt keinen
beliebigen normativen Write. Die Request-ID-Regeln und das Verbot
abweichender Wiederverwendung bleiben unverändert.

**Erhaltende Übergabe und Unterbrechung.** Die vorhandenen sicheren
descriptorgebundenen Owner-, Evidence-, Staging-, Rename- und Sync-Primitiven
sind wiederzuverwenden. Vor dem atomaren Ownerwechsel werden unveränderliche
Originalownerbytes und ein Übernahmeintent mit Regelversion
`restore-owner-handoff-v1`, beiden Ownerbindungen, den oben geprüften
Auftrags-/Ausführungsbindungen, aktueller Autoritätszuordnung und
Risikoentscheidung dauerhaft angelegt und bytegleich wiedergeprüft.
Der vollständig vorbereitete neue Owner ist ein Recovery-Owner für exakt
den neuen beziehungsweise fortgesetzten Restore. Unmittelbar vor seinem
atomaren Einsetzen werden alter Owner einschließlich Dateiidentität,
Root, Ownerbeobachtung, aktive Journalmenge und alle betroffenen Bindungen
erneut geprüft. Es gibt keine Lücke durch vorheriges Löschen des Owners.
Ein eigener dauerhafter Abschlussbeleg bestätigt den tatsächlichen Wechsel.

Diese zusätzlichen Betriebsbytes und benötigten Verzeichnisse werden vor
ihrem ersten Write genau im Übernahmeintent gebunden und mit der
unveränderten Originalausführung verknüpft. Bei einem neuen Restore bindet
der Intent auch die vollständigen Originalplanbytes und den autorisierten
neuen Auftrag, bevor der neue Owner eingesetzt wird. Bei Fortsetzung ist
der unveränderliche frühere Ausführungsbeleg zusätzlich gebunden. So sind
auch Abbrüche vor Anlage des eigentlichen Restore-Journals anhand einer
vollständigen Übernahmebindung unterscheidbar. Die Originalinventur wird
dafür nicht neu gehasht. Eine allgemeine Ausnahme für einen Recovery- oder
Auditordner und eine nachträglich frei ergänzte Liste eigener Dateien sind
unzulässig. Kurze, fremde oder abweichende Belege werden nicht überschrieben.

Die Übernahme verändert keine normativen Modellbytes und entfernt oder
archiviert kein ausgewähltes altes Journal. Alle bisherigen Sperren bleiben
bis zum nachgewiesenen Restoreabschluss aus 10.7.3/10.7.4 erhalten. Nach einem
Abbruch bleiben tatsächlicher Owner und sämtliche bereits geschriebenen
Belege bestehen. Ein erneuter ausdrücklich autorisierter Aufruf bindet den
dann tatsächlich beobachteten Owner; er prüft den alten oder neuen Stand
gegen den unveränderten Übernahmeintent und vollendet nur belegbare Schritte.
Ein vollständiger Intent allein behauptet weder ausgeführten Ownerwechsel
noch veröffentlichte Zielbytes. Kann bei einem belegten neuen Owner vor dem
Restore-Journal nachgewiesen werden, dass keine Zielpublikation begann, gilt
der `building`-Abschluss aus 10.7.3: erhaltener, auditierter Rückrollzustand,
keine neue Fachoperation im selben Aufruf. Andernfalls gelten dessen
Vollziel-/Teilziel-/Integritätsregeln unverändert. Ein Folgeprozess erbt
keine aktuelle Risikozustimmung oder Schreibberechtigung aus dem Intent.

Der allgemeine Befehl `lock recover --force` behält sein Journalveto.
Die bestehende gewöhnliche Transaktionsübernahme behält ihre exakte
Transaktions-/Request-/Journalbindung. Der hier zusätzlich gebundene
Restorefall ist keine globale Aufweichung dieser Wege. Der Lock wird nur
freigegeben, solange er noch der eigene unveränderte Owner ist.

Fehlende Pflichtangaben ergeben Code 2, ungültige oder unvollständige
notwendige Belege 3, echte I/O-Fehler oder ungelöster Recoverybedarf 5,
abweichende Bindungen 6 sowie unsichere Pfade, lebende Owner oder fehlende
Berechtigung/Risikozustimmung 7. Abgewiesene Vorprüfungen bleiben schreibfrei;
nach möglichem Write werden tatsächlicher Zustand und Recoverybedarf
ausgewiesen. Einzellauf und Workfortsetzung benutzen dieselben Bindungen
und Gates. Diese Präzisierung enthält keine menschliche Freigabe, keine
reale Risikoakzeptanz und keinen Implementierungs-/Abnahmenachweis.


#### 10.7.6 Explizite Restore-Aufrufbindung `restore-cli-binding-v1`

**Entscheidung RESTORE-CLI-BINDING, delegiert gemäß SPECROAD-DECISION-1.**
Diese Regel präzisiert die bisher nur schematischen Aufrufe aus 10.7.1.
Sie bildet deren Eingaben auf die expliziten Root-, Quell- und Dateibindungen
aus 10.7.2 ab. Die geschlossenen Plan-, Auswahl- und Ausführungsformate aus
10.7.2–10.7.5 sowie ihre Autorisierungs-, Erhaltungs- und Crashgates bleiben
unverändert. Ein Pfad, Actorlabel oder erfolgreicher Preflight erteilt keine
Recovery-Berechtigung.

**Zwei getrennte Modi.** Die nachstehend genannten Optionen sind jeweils
einmalig und werden nicht aus Projektprofilen, Umgebungsvariablen oder einem
vorherigen Aufruf ergänzt. Die vorhandenen allgemeinen Ausgabe- und weichen
Ressourcenoptionen behalten ihre gesonderten Regeln; sie ersetzen keine
dieser fachlichen Pflichtangaben.

| Modus | Pflichtangaben | Zusätzliche fachliche Angaben |
|---|---|---|
| Planung | `--project <ROOT> --from <PATH> --source-root <ROOT> --source-kind project_bundle\|baseline --dry-run --output-root <ROOT> --output <PATH>` | Bei `baseline` genau die expliziten operativen Werte `--default-locale <LOCALE>` und `--generated-path <PATH>` nach 10.7.2; bei `project_bundle` sind beide unzulässig. |
| Ausführung oder Wiederanlauf | `--project <ROOT> --plan-root <ROOT> --plan <PATH> --expected-target-root <SHA256> --actor-type <TYPE> --actor-id <ID>` | `--request-id <ID>` nach den unveränderten Pflicht-/Optionalitätsregeln aus 10.7.3; paarweise `--selection-root <ROOT> --affected-journals <PATH>` nach 10.7.4; Ownerübernahmeoptionen ausschließlich nach 10.7.5. |

Fehlende Pflichtoptionen, Wiederholungen, unbekannte Quellarten oder eine
Mischung der Modi sind Code 2. Insbesondere sind Plan-/Zielbestätigung,
Akteur/Request, Journalauswahl und Ownerübernahme in der Planung unzulässig;
Quell-, operative Baseline-, Dry-Run- und Planausgabeoptionen sind bei der
Ausführung unzulässig. Der Wiederanlauf verwendet denselben Ausführungsmodus,
keinen neuen Quellenaufruf. `--as-proposal` ist kein Restoremodus.

`--source-kind` wählt ausschließlich `project_bundle` oder `baseline`.
Dateiendung, ZIP-/JSON-Erkennung und Inhalt dürfen die ausdrücklich gewählte
Art nicht ändern oder eine zweite Art als Fallback ausprobieren. Ein syntaktisch
zulässiger Aufruf mit Bytes der falschen Art oder unvollständiger Quelle
scheitert an der Quellenqualifikation mit Code 3. Beide Baselinewerte werden
nach ihrem bestehenden Konfigurationsvertrag geprüft und nur in den operativen
Zielwerten verwendet. Es gibt keinen Default aus der beschädigten Konfiguration,
keine semantische Ergänzung und keinen Override von Bundle-Konfigurationsbytes.

**Root und relative Datei.** Die Rootoptionen bezeichnen ausdrücklich
vorhandene kanonische absolute Verzeichniswurzeln. Sie werden über den
vorhandenen nativen Rootschutz geprüft; eine lexikalische Normalisierung,
Symlinkauflösung oder ein gleicher Pfadstring ersetzt keine Rootidentität.
`--from`, `--plan`, `--affected-journals` und `--output` bezeichnen jeweils
einen sicheren relativen Dateipfad unter ihrer zugehörigen Rootoption.
Absolute Dateiwerte, Traversal, Links, Sonderdateien, unsichere Aliase und
fremde Rootdurchquerungen behalten die vorhandene Sicherheitsablehnung
Code 7. `--generated-path` ist dagegen ein operativer projektbezogener
Konfigurationswert und unterliegt dessen bestehendem Pfadvertrag.

Bei Baselines bezeichnet `--source-root` auch die Wurzel aller rekursiv
referenzierten nativen Snapshotobjektpfade. Ein Parent der Quelldatei wird
nicht als Objektroot geraten. Eine Quelle darf nach den bestehenden
Quellen-/Inventurregeln im ausgewählten Projekt liegen; das erteilt keine
Schreibbefugnis. Plan- und Auswahldatei werden als passive explizite Eingaben
gelesen. Ihr Speicherort authentifiziert weder Inhalt noch Auftrag. Ein
anderer Ort der externen Originalplandatei bindet weder `project_root` noch
`source.root/path` im Plan um; für deren Verlagerung gilt weiterhin 10.7.2.
Ohne beide Auswahloptionen gilt nur die leere Auswahl nach 10.7.4. Ein allein
angegebener Auswahlroot oder Auswahlpfad ist Code 2.

Der Ausgaberoot und sein Ziel bleiben außerhalb des ausgewählten Projekts
und anderer Projektroots gemäß den sicheren Generated-Output-Regeln. Nur
eine noch fehlende Zieldatei wird atomar veröffentlicht; auch identische
vorhandene Bytes werden nicht überschrieben. Ein bestehendes Ziel ergibt
Code 6. Erforderliche Eltern unter dem geprüften Ausgaberoot dürfen mit den
vorhandenen sicheren Primitiven angelegt werden; der Root selbst wird nicht
aus dem Aufruf heraus erzeugt. Reale I/O-/Durabilitätsfehler bleiben Code 5.
Der ausgegebene Plan und die erneut geprüften Quelldateien bleiben bytegebunden;
keine Ausgabedatei oder temporäre Datei wird als Autorisierung verwendet.

**Spezialisierter Preflight.** `recover restore` bleibt in beiden Modi die
Command-ID `recover.restore`, Klasse `recovery_write`, Preflight `recovery`.
Nur die tatsächliche Ausführung besitzt die deklarierten Recoverywrites;
die Planung schreibt weder ins Projekt noch in `.specroad/` und nimmt keinen
Projekt-Writer-/Recovery-Lock. Ihr einziger fachlicher Dateieffekt ist der
explizite externe Plan; offengelegte externe Workdaten folgen unverändert O/P.
Diese befehlsspezifische Dry-Run-/Actor-Unterstützung klassifiziert Restore
nicht als gewöhnlichen normativen Writer und erlaubt keine globale Erweiterung
der Optionen anderer Befehlsklassen.

Die explizite Projektauswahl prüft den wirklichen Root, aber setzt weder eine
lesbare/gültige `specroad.json` noch ein konsistentes Modell voraus. Sie
verwendet kein beschädigtes Modell als gültige Options-/Profilquelle und
ersetzt keinen Root durch einen früher ausgewählten Root. Erst die spezialisierte
Restoreprüfung ermittelt vollständige Bestandsabdeckung und Projektidentität
aus den unabhängig gebundenen Belegen nach 10.7.1–10.7.2. Unbestimmbare
Identität oder Abdeckung bleibt ein Befund, keine erlaubte Teilinventur.
Der Sonderweg gilt nur diesem expliziten Recoveryaufruf; normale Reader,
Dry-Runs anderer Befehle und Writer behalten ihre Recoverybarrieren.

Bei der Ausführung MUSS der ausdrücklich ausgewählte Projektroot exakt dem
gebundenen `project_root` entsprechen; ein abweichender sonst zulässiger Root
ist Code 6 ohne Projektwrite. Plan- und Auswahllektüre prüft zunächst die
Originalformate und deren Paarbindung. Sie erzwingt vor der Untersuchung einer
nachgewiesenen laufenden Ausführung keine frische ursprüngliche Bestandswurzel
oder inzwischen verschwundene Herkunft. Die native Ausführung unterscheidet
erst danach Neupublikation, Vollzielabschluss und Teilziel-Rollback gemäß
10.7.3. Das ist keine Ausnahme von den Frischeprüfungen vor Neupublikation.

**Autorisierung und gemeinsamer Adapter.** CLI und strukturierter Aufruf
verwenden dieselben gebundenen Fachparameter, native Datei-/Restoreadapter,
aktuelle gesonderte Autorisierungsprüfung und Owner-/Risikogates. Akteur und
Request werden nach den vorhandenen Regeln validiert; insbesondere bleibt
die Request-ID für `ai` und `ci` Pflicht. Kein Argument lädt ausführbaren
Projektcode oder registriert eine Berechtigungsfunktion aus einer Datei.
Fehlende, ablehnende, fehlerhafte oder nur gespeicherte Autorisierung bleibt
eine Ablehnung nach dem bestehenden Vertrag. Diese Präzisierung erfindet
weder eine reale Hostfreigabe noch eine neue Authentifizierungs-/Pluginarchitektur;
die verwendbare vertrauenswürdige CLI-Anbindung ist weiterhin nachzuweisen.

Selbstbeschreibung und maschinenlesbare Ergebnisse folgen 11.7: beide Modi,
Pflicht-/Ausschlussbeziehungen, Source-/Rootbindung, tatsächlich mögliche
Seiteneffekte und Fehlerklassen sind offenzulegen. Nur ein vollständig
veröffentlichter Plan gilt als Planungserfolg; ein zurückgerollter oder
gesperrter Wiederanlauf ist kein erfolgreich wiederhergestelltes Projekt.
Einzellauf und Workfortsetzung dürfen weder Optionen neu erraten noch alte
Berechtigung als aktuelle Zustimmung wiederverwenden. Alle übrigen Grenzen
aus N/O/P sowie 10.7.1–10.7.5 bleiben Pflichtabnahmen von 15.l.R.


#### 10.7.7 Restore in Workfortsetzungen `work-restore-binding-v1`

**Entscheidung RESTORE-WORK-BINDING, delegiert gemäß SPECROAD-DECISION-1.**
Diese Regel konkretisiert die zugesagte Einzellauf-/Workparität aus 10.7.3,
10.7.6 und Anhang N/O/P. Sie verwendet den externen `work-v1`-Checkpoint und
die vorhandene native Restoreausführung. Ein Restore wird weder zu einem
gewöhnlichen Change Plan noch zu einer frei ausführbaren Work-Unteroperation.
`work resume` bleibt `work_operational`; der gebundene innere Befehl ist
`recover.restore`, Klasse `recovery_write`, mit seinem speziellen Preflight.
Andere Workbefehle oder gespeicherte Command-IDs erhalten keine Recoverybefugnis.

**Passive Eingangsbindung.** Ein Workauftrag bleibt in genau dem ursprünglich
gewählten Planungs- oder Ausführungsmodus nach 10.7.6. Die vollständigen
Fachargumente, Quellart, operativen Baselinewerte und ausdrücklichen Ziele
bleiben gebunden; eine Fortsetzung wechselt nicht von Dry-Run zu Ausführung.
Für die Planung gelten Snapshotaufbau, vollständige Aufgabenmanifeste und
externe Planausgabe aus P.4/P.5 und 10.7.2. Noch nicht vollständig qualifizierte
Planbytes sind kein erfolgreicher Restoreplan und keine spätere Writefreigabe.
`actor`, `request_id`, `operations_sha256` und `plan_binding` sind dabei
`null`; ein fertig erzeugter Plan gehört zu den gehashten Ergebnisbytes.

Für einen Ausführungsauftrag gelten im vorhandenen Workmanifest zusätzlich
die folgenden eindeutigen Feldbedeutungen. Die Originalpläne und die Auswahl
behalten ihre geschlossenen Formate aus 10.7.2/10.7.4; sie werden nicht um
Workfelder erweitert.

| Workfeld | Verbindliche Restorebindung |
|---|---|
| `source_bindings` | Exakt `{project_id, scope, model_root_sha256}` mit der unabhängig geprüften Projekt-ID, `scope=["project"]` und `model_root_sha256=null`. Der beschädigte Ausgangsbestand wird durch die Originalinventur im Plan gebunden, nicht durch eine erfundene semantische Basiswurzel. |
| `actor`, `request_id` | Unveränderter ursprünglicher Ausführungsakteur und dessen Request-ID nach 10.7.3; die dortige Pflicht-/Optionalitätsregel bleibt erhalten. Ein Work-ID-/Generationswert ersetzt keine Request-ID. |
| `operations_sha256` | `null`: Restore besitzt keine gewöhnliche Change-Plan-Operationsfolge. Weder Inventur-, Plan- noch Zielhash werden als solcher Operationshash ausgegeben. |
| `plan_binding` | Geschlossenes Objekt mit exakt `format_version`, `restore_plan_sha256`, `plan_source`, `journal_selection` gemäß nachfolgendem Vertrag. |

`plan_binding.format_version` ist exakt `work-restore-binding-v1`.
`restore_plan_sha256` ist der geprüfte innere Hash des Originalplans.
`plan_source` und `journal_selection` sind jeweils exakt `{sha256, size}`:
SHA-256 der vollständigen referenzierten Bytes und deren nichtnegative
ganzzahlige Byte-Länge. `plan_source` referenziert die unveränderten
Originalplanbytes, `journal_selection` die kanonischen Auswahlbytes nach
10.7.4. Bei ursprünglich weggelassener Auswahl werden ausschließlich die
dort festgelegten kanonischen Bytes der leeren Auswahl gebunden. Eine
nichtleere Auswahl wird niemals aus gefundenen Journaldaten ergänzt.
Beide Bytefolgen MÜSSEN im content-addressierten Work-Objektbestand erhalten
und vollständig über das Eingangsmanifest gebunden sein. Ihr bloßer Pfad
oder Hash ersetzt keine fehlenden Bytes. Der innere Planhash und sein
äußerer Rohbytehash bleiben ausdrücklich verschiedene Hashdomänen.

Jede Wiederaufnahme prüft die geschlossene Bindung, Originalbytes, Auswahl,
Projektidentität, Actor-/Requestwerte und ihre Übereinstimmung mit den
normalisierten Fachargumenten. Die vorhandene Checkpointprojektion bindet
auch diese Variante; sie erhält keinen zweiten, widersprüchlichen Aufgaben-
oder Operationshash. Für bereits begonnene Ausführungen muss zusätzlich
genau die ursprüngliche Auftragsbindung des überprüften Restorejournals
passen. Ein neuer Workcontainer darf keinen anderen ursprünglichen Akteur,
Plan, Request oder Auswahl an eine bestehende Ausführung anhängen.
Ein unbekannter Bindungstyp wird vor Fortsetzung abgewiesen, niemals als
`work-change-plan-v1` oder ungebundener schreibfreier Auftrag interpretiert.
Bestehende Work-/Change-Plan-Checkpoints bleiben unverändert lesbar; ihre
Felder werden nicht nachträglich in Restorefelder umgedeutet.

Die allgemeine Rootlokalisierung aus P.3/P.7 darf externe Work- und
Plantransportorte neu zuordnen, aber keinen im Originalplan gebundenen
`project_root` oder `source.root/path` umschreiben. Für deren Verlagerung
bleibt die neue ausdrückliche Planung nach 10.7.2 erforderlich. Ein Workpaket
ist keine verifizierte Kopie einer laufenden Projekttransaktion und ersetzt
keine dort nötigen Journale, Before Images oder Root-/Ownernachweise.
Eingebettete Plan-/Quellbytes erlauben vor einer neuen Vorwärtspublikation
keine Ausnahme von den frischen Herkunfts- und Bestandsprüfungen.

**Aktuelle Berechtigung statt gespeicherter Freigabe.** Die Workbindung ist
passiver Auftragsnachweis, keine Berechtigung. Jeder tatsächliche Restorewrite
braucht dieselbe aktuelle, vertrauenswürdig angebundene Recoveryautorisierung,
den nativen Recovery-Lock und die Owner-/Risikogates wie der direkte Aufruf.
Die ursprünglichen Workfelder bleiben erhalten. Bei einer Recoveryaktion
wird der aktuelle Recoveryakteur nach 10.7.3 getrennt geprüft und auditiert;
dies erweitert oder ersetzt den ursprünglichen Actor nicht. Ein gespeicherter
Authorityname, früherer positiver Entscheid, Ownerbeleg oder Risikowert ist
keine neue Zustimmung. Eine benötigte aktuelle Übernahme muss erneut genau
nach 10.7.5 beauftragt und geprüft werden. Workdaten registrieren keine
Callbacks, laden keinen Code und erzeugen keinen Hostgrant. Fehlende echte
Autorisierung bleibt eine konkrete Sperre; der verwendbare positive CLI- und
strukturierte Pfad ist weiterhin nachzuweisen.

**Checkpoint und Journal.** Vor dem ersten Restore-Betriebswrite darf die
Vorbereitung an vollständigen, belegten Fortschrittsgrenzen pausieren, ohne
einen Projektwriter-/Recovery-Lock über den Aufruf hinweg zu halten. Beim
späteren Beginn werden Herkunft, Bestand, Ziel, Autorisierung und Auswahl
unter dem nativen Lock erneut geprüft. Bestätigte Vorbereitungsarbeit wird
nicht aus einem Textcursor oder einer erneut geladenen aktuellen Modellwurzel
erraten; weiche Budgets verkürzen weder Eingangs- noch Zielprüfung.

Ab dem ersten Restore-Betriebswrite ist das getrennte Restorejournal die
maßgebliche Ausführungswahrheit. Ein echter Abbruch wird als
`recovery_required` behandelt, auch wenn der letzte externe Workcheckpoint
noch einen früheren Vorbereitungsstand zeigt. `work resume` MUSS vor einem
neuen Write die genau gebundene vorhandene Ausführung prüfen und darf nur
deren native Recovery nach 10.7.3 ausführen. Es gibt keine zweite Publikation,
kein Vorwärts-Resume eines Teilziels und keinen normalen Promptcheckpoint
mit freiwillig freigegebenem Mischstand. Fehlen notwendige echte Belege oder
aktuelle Berechtigung, bleiben Zustand, Workdaten und Recoverybarrieren erhalten.

Ein vollständiges, journalgebundenes Ziel wird samt fehlendem Audit abgeschlossen,
auch wenn die externe Herkunft inzwischen fehlt; eine Teilpublikation wird
ausschließlich aus geprüften Before Images zurückgerollt. Work darf diese
beiden Fälle nicht durch eine vorgezogene frische Originalinventur-/Quellprüfung
oder durch allgemeines Laden eines gültigen Ausgangsmodells verdecken.
Der Rollback ist kein Restoreerfolg, hebt alte Sperren nicht auf und beginnt
im selben Aufruf weder Neuplanung noch neue Restoreausführung. `work cancel`
oder `work export` darf eine laufende Restoretransaktion nicht entsperren,
verwerfen oder als portabel gesichert erklären; P.6/P.7 bleiben verbindlich.

**Abschluss und Parität.** Ein verlorener äußerer Workabschluss nach bereits
dauerhaftem Restoreabschluss wird aus dem genau passenden nativen Abschluss-
beleg und den gemäß 10.7.3 erforderlichen aktuellen Prüfungen rekonstruiert,
ohne erneut Zielbytes zu veröffentlichen. Erst vollständige Ergebnislieferung
erlaubt `completed`; ein Workstatus allein beweist keinen Restoreerfolg.
Ein bereits vollständig abgeschlossener Workauftrag liefert nach 11.12
sein gespeichertes, an diesen Abschluss gebundenes Ergebnis. Er behauptet
damit keine neue Prüfung eines inzwischen geänderten Projekts; ein neuer
ausdrücklicher Restoreaufruf behält dessen aktuelle Konfliktprüfung.

Einzellauf, strukturierter Aufruf und Workfortsetzung müssen für denselben
gebundenen Auftrag dieselben Zielbytes, Erhaltungs-/Sicherungsbindungen,
fachlichen Ergebnisse, Fehlerklassen und zulässigen Dateieffekte erreichen.
Workgenerationen und Laufzeitverbrauch sind getrennte Betriebsdaten. Ungültige
oder fehlende gespeicherte Bindungsbytes ergeben 3, echte I/O-/Recoveryblocker
5, abweichende Auftrags-/Bestandsbindungen 6, Sicherheits-/Berechtigungsverstöße
7; fehlende explizite Aufrufangaben bleiben 2. Work wird weder zu einem neuen
Erfolgsreceipt noch zu einer Ausnahme von historischen Schutz-, Review-,
Lifecycle- oder Fachproviderprüfungen. Implementierung und vollständige
Verhaltensevidence dieser Bindung bleiben Bestandteil von 15.l.R.


### 10.8 Scope Descriptor und Scope-Closure

Jede Operation mit Modellumfang verwendet genau einen kanonischen Scope Descriptor:

```json
{
  "scope_version": "scope-v1",
  "scope_kind": "specification",
  "selector": {},
  "configuration_id": null,
  "closure_profile": "core-closure-v1",
  "boundary_policy": "closed"
}
```

Für Version 0.2 sind ausschließlich `scope_version=scope-v1` und `closure_profile=core-closure-v1` zulässig. `boundary_policy` ist exakt `closed` oder `partial`. Ein nicht kanonisch darstellbarer, unbekannter oder widersprüchlicher Descriptor ist ein Eingabemodellfehler.

| `scope_kind` | Exaktes `selector`-Schema | Seed-Menge vor Closure |
|---|---|---|
| `specification` | `{}` | alle im Arbeitsstand vorhandenen Artefakte außer `proposal` und `baseline`; die effektive semantische Projektkonfiguration; alle aktiven Profile, Regeln und Mappings |
| `project` | `{}` | alle im Arbeitsstand vorhandenen normativen Ressourcen einschließlich `proposal` und `baseline`; alle von Baselines referenzierten Archivobjekte; keine Locks, Journale, Receipts, Caches oder generierten Dateien |
| `release` | `{ "release_id": <REL-ID> }` | das bezeichnete Release; alle über `part_of` zugeordneten Milestones; alle Artefakte mit `scheduled_for` auf das Release oder einen dieser Milestones; alle Tasks mit `part_of` auf das Release oder einen dieser Milestones |
| `document` | `{ "document_id": <DOC-ID> }` | das bezeichnete Dokument; seine Abschnitte und Inhaltsblöcke entstehen anschließend ausschließlich durch die `contains`-Closure |
| `query` | `{ "query": <normalisiertes Query-Objekt nach 11.6> }` | exakt die geordnete, paginierte Ergebnismenge der gebundenen Query; alle Defaults sind im Selector materialisiert |
| `explicit` | `{ "artifact_ids": [<ID>...], "resource_ids": [<Ressourcenidentität>...] }` | exakt die beiden angegebenen Mengen; beide Arrays sind nach UTF-8-Bytes lexikografisch sortiert und enthalten keine Dubletten |
| `configuration` | `{ "base_scope_descriptor": <Descriptor> }` | die Seed-Menge des eingebetteten, nicht selbst konfigurationsgebundenen Basisscopes nach Anwendung der bezeichneten Konfiguration |

Für `specification`, `project`, `release`, `document`, `query` und `explicit` ist `configuration_id` entweder `null` oder die ID genau eines vorhandenen `configuration`-Artefakts. Für `configuration` ist `configuration_id` Pflicht; sein eingebetteter `base_scope_descriptor` besitzt einen anderen `scope_kind` und `configuration_id=null`. Eine rekursive Konfigurationshülle ist unzulässig. Nicht zum jeweiligen Tabellenschema gehörende Selector-Felder sind unzulässig.

Bei gebundener Konfiguration wird `applicability` nach Auflösung der Parent-Kette vor der Closure ausgewertet. Die Closure ist der kleinste Fixpunkt, der durch wiederholte Verarbeitung der jeweils noch nicht verarbeiteten Quellen in lexikografischer Ressourcen-ID-Reihenfolge entsteht. Für `core-closure-v1` gelten folgende Kanten:

- **starke Kanten:** `addresses`, `refines`, `derived_from`, `depends_on`, `constrains`, `allocated_to`, `implemented_by`, `verified_by`, `produces`, `mitigates`, `scheduled_for`, `part_of`, `supersedes`, `contains` und `references`; ihr Ziel wird nach erfolgreicher Scope-Zulässigkeitsprüfung aufgenommen;
- **gebundene Ressourcen:** Evidence-Subjects, Test-IDs aus `evidence_slots` enthaltener Contracts, zu einer enthaltenen Relation gehörende aktuelle Relationsreviews, referenzierte Anhänge sowie von enthaltenen Ressourcen verwendete Profile, Regeln und Mappings werden nach Scope-Zulässigkeitsprüfung aufgenommen;
- **schwache Kanten:** `conflicts_with` und `duplicates`; bei `closed` wird ihr Ziel aufgenommen, bei `partial` wird stattdessen genau eine Boundary Reference erzeugt.

Ein Ziel einer starken Kante oder gebundenen Ressource, das wegen der ausgewählten Konfiguration ausgeschlossen ist, erzeugt einen Konfigurationsfehler; es wird weder stillschweigend aufgenommen noch als Boundary Reference abgeschwächt. `rejected` und `retired` sind enthalten, wenn sie Seed sind oder durch eine starke Kante beziehungsweise gebundene Ressource erreicht werden. Eine fehlende Zielressource ist unabhängig von der Grenzpolicy ein Fehler. Der ausschließlich zur Prüfung einer schwachen Außenkante transportierte Kontext nach E.3.2 wird dadurch nicht zum fachlichen Zielmitglied; er ersetzt niemals ein erforderliches starkes Ziel oder eine gebundene Ressource.

Die Ergebnisreihenfolge ist für Artefakte deren ID, für Profile, Regeln und Mappings deren Identität plus Version, für Anhänge deren projektroot-relativer Pfad und für Boundary References das Tupel `(source_id, relation_id, target_id)`, jeweils lexikografisch nach UTF-8-Bytes. Der Scope-Hash bindet den RFC-8785-kanonisierten Descriptor, alle enthaltenen Ressourcenidentitäten und -hashes sowie die geordneten Boundary References.

#### 10.8.1 Permanente Ausschlüsse und zulässige Proposal-Basis

Für `scope_kind=specification` sind `proposal` und `baseline` **permanent ausgeschlossen**, nicht nur aus der Seed-Menge. Derselbe Ausschluss gilt für eine Konfigurationshülle mit `specification` als Basisscope. Vor jeder Aufnahme einer Ressource prüft die Closure deren Typ. Dies gilt gleichermaßen für starke Kanten, bei `closed` verfolgte schwache Kanten, explizite Ressourcenbindungen und indirekte Pfade beliebiger Länge.

Erfordert ein solcher Pfad ein ausgeschlossenes Kontrollartefakt, ist der Scope ungültig: Diagnose `SRV140` mit `reason=scope_control_dependency`, Quell-ID, Ziel-ID und Relations-ID beziehungsweise JSON Pointer; Exit Code 3. Es gibt weder eine erfolgreiche Modellwurzel noch eine automatische Herabstufung zur Boundary Reference. Bei `partial` nicht verfolgte schwache Kanten behalten ihren bestehenden Boundary-Vertrag; ein solcher Scope ist keine zulässige Proposal-Basis. Ein gewöhnlicher nicht referenzieller Freitext wird nicht als Artefaktkante interpretiert.

Damit bleibt eine `references`-Beziehung auf ein Proposal im **Projekt- oder Dokument-Scope** grundsätzlich darstellbar, ist aber ausdrücklich unzulässig, sobald sie zur vollständigen `specification`-Closure gehören würde. Ein Modell mit einer solchen Kante muss diese Abhängigkeit auflösen, bevor daraus eine Proposal-Basis gebildet werden kann. Dieses Verhalten ist eine bewusste Gültigkeitsregel, kein stilles Weglassen von Dokumentinhalten.

Ein Proposal und sein eingebetteter fachlicher Change Plan verwenden ausschließlich den folgenden Descriptor: `scope_version=scope-v1`, `scope_kind=specification`, `selector={}`, `configuration_id=null`, `closure_profile=core-closure-v1`, `boundary_policy=closed`. `--base-scope` darf diesen Descriptor explizit liefern, aber keinen anderen Scope, keine Konfigurationshülle und keinen Teilumfang. Unzulässige CLI-Auswahl ergibt Code 2; ein gespeichertes Proposal mit unzulässigem Descriptor ergibt Code 3. Ein expliziter Konfigurationsfilter für die Proposal-Basis ist ebenfalls Code 2; er wird nicht stillschweigend entfernt. Die Prüfung erfolgt vor Erzeugung von ID, Journal, Receipt oder normativer Datei. Baseline-/Git-Referenzen sind ausschließlich zusätzliche Provenienz und ändern diese Basisregel nicht.

Create, Authoring, Reviewstart, Review und Apply prüfen dieselbe Zulässigkeit. Sowohl Basis als auch das vollständig geplante fachliche Ziel müssen eine gültige `specification`-Closure besitzen. Vorschlagsoperationen dürfen kein `proposal` oder `baseline` als fachliches Ziel erzeugen, ändern oder stilllegen; Kontrollwrites und Baseline-Erzeugung bleiben ihren Fachbefehlen vorbehalten. Der separate äußere Kontrollwrite bindet das Proposal mit Vollhash und Artefaktrevision nach 10.4; er ist nicht Teil des eingebetteten Fachplans. Deshalb ändern reine Proposal-Kontrollwrites weder die gebundene Fachbasis noch deren Zielwurzel.

Eine nach außen bereits veröffentlichte Basis oder Freigabe wird durch diese Korrektur nicht stillschweigend umgebunden. Ein altes, nach dem präzisierten Vertrag unzulässiges Proposal muss neu geplant und erneut freigegeben werden. Bereits zulässige unveränderte Scopes behalten ihre Hashberechnung; es wird kein alter Hashstandard für historische Snapshotbytes überschrieben.


### 10.9 Modellwurzel

Für jede im Modellumfang enthaltene normative JSON-Ressource wird der RFC-8785-Hash gebildet. Anhänge werden durch Pfad, Byte-Länge, Medientyp und Byte-Hash repräsentiert. Das Manifest enthält Scope Descriptor, Scope-Hash, Artefakte nach ID, Ressourcen nach Identität und Version, Anhänge nach Pfad, Boundary References nach `(source_id, relation_id, target_id)` sowie den effektiven Konfigurations- und Profilhash. Das Manifest wird nach RFC 8785 kanonisiert und mit SHA-256 gehasht.

Absolute Pfade, lokale Zeitzone, Laufzeitstempel, Cache, Locks, Journale, Receipts, generierte Dateien und Darstellungseinstellungen fließen nicht in die fachliche Modellwurzel ein. Bei einem Projektbundle können Receipts als separat gehashte Betriebssektion im Bundlemanifest enthalten sein. Aufrufbezogene Ressourcenprofile, Budgets, Cachewahl, Runtime-Identität und explizite Messwerte sind ebenfalls keine Eingaben der fachlichen Modellwurzel, des Scope Descriptors oder der gebundenen Plan-/Operationshashes; die bestehenden semantischen Projekt- und Profilpolicies bleiben unverändert.

### 10.10 Profilkomposition

Profile werden in dieser Reihenfolge aufgelöst: exakte Version von `core` zuerst, danach die geordnete Projekt- oder CLI-Liste. Sobald mindestens ein `--profile` angegeben ist, ersetzt diese Liste die Projektliste; `core` wird automatisch vorangestellt. Doppelte Profilidentitäten sind unzulässig.

| Profilbestandteil | Mergevertrag |
|---|---|
| Pflichtfelder | Mengenvereinigung |
| Verbotene Felder | Mengenvereinigung; ein zugleich verpflichtendes Feld ist Konflikt |
| Zulässige Werte | Schnittmenge; leere Schnittmenge ist Konflikt |
| Relation Rules | gleiche Regel-ID nur bei gleicher Version und gleichem Hash; sonst Konflikt |
| Lint-Regeln | geordnete Vereinigung; identische Regelidentität wird beim ersten Auftreten behalten |
| Severity Overrides | spätes Profil gewinnt; Core-Sicherheitsdiagnosen dürfen nicht unter `error` abgesenkt werden |
| Inhaltssprachen und Sprachpakete | kein Gleichheitszwang über alle Artefakte; Policy und per Artefakt passende deklarative Pakete nach Anhang S |
| CLI-Anzeigelocale | unabhängig von der Inhaltssprache; wird nicht durch ein Sprachpaket erzwungen |
| Harte Struktur-/Sicherheitsgrenzen | der strengste, numerisch kleinste Wert gewinnt; weiche Mengen-/Rechenziele gehören nicht in diese Profilkomposition |
| sonstige skalare normative Policy | Werte müssen gleich sein; sonst Konflikt |

Der effektive Profilhash ist der RFC-8785-/SHA-256-Hash aus geordneten Profilidentitäten mit Ressourcenhash und der vollständig materialisierten Mergeprojektion. Sprachregister- und Sprachpaketidentitäten einschließlich ihrer Hashes werden darin nach Anhang S gebunden; `language_policy`, `analyzer_policy` und `srx_policy` gehören zur effektiven semantischen Projektkonfiguration. Ein Profilkonflikt verhindert jede Modelloperation außer `config show`, `profile explain` und Diagnoseausgabe einschließlich `environment check`; diese Ausnahmen dürfen kein fachlich gültiges Modell behaupten.

### 10.11 Baseline-Objektspeicher

Beim Erzeugen einer Baseline werden kanonische JSON-Bytes und unveränderte Anhangsbytes content-addressiert unter `archive/objects/<erste-zwei-hex>/<sha256>` gesichert. Das Baseline-Manifest enthält Scope Descriptor, logische Rolle, Artefakt-ID oder Quellpfad, Revision, Byte-Länge, Medientyp, Hash, Boundary References und optionalen Konfigurationshash. Ein Archivobjekt darf nicht verändert oder gelöscht werden, solange eine Baseline darauf verweist.

### 10.12 External Identity und Import-Dreifachvergleich

Eine External Identity ist an Artefakten und Relationen zulässig:

```json
{
  "source_system": "reqif",
  "source_document": "supplier-a.reqif",
  "external_id": "_1234",
  "external_revision": "7",
  "mapping_id": "reqif-core@1.0.0",
  "last_imported_projection_sha256": "...",
  "last_source_projection_sha256": "...",
  "last_source_payload_sha256": "...",
  "imported_at": "2026-09-01T18:00:00Z"
}
```

Die Kombination `(source_system, source_document, external_id)` ist projektweit für die jeweilige Objektklasse eindeutig. Mappings besitzen zusätzlich ein External-Identity-Registry für externe Typdefinitionen, Hierarchieobjekte und Metadaten, die kein eigenes SpecRoad-Artefakt bilden.

Für `update_if_unchanged` werden die aktuelle lokale Mappingprojektion, `last_imported_projection_sha256`, die neue Quellprojektion und `last_source_projection_sha256` verglichen; `last_source_payload_sha256` dient ausschließlich der Provenienz:

| Lokal gegenüber letzter Importprojektion | Neu gegenüber letzter Quellprojektion | Ergebnis |
|---|---|---|
| unverändert | unverändert | No-op; Importbaseline darf aktualisiert werden |
| unverändert | verändert | Update auf neue Quellprojektion |
| verändert | unverändert | lokale Änderung behalten; als lokal geändert melden |
| verändert | verändert und beide kanonischen Zielprojektionen gleich | Zielwert übernehmen und Importbaseline aktualisieren |
| verändert | verändert und Zielprojektionen verschieden | Importkonflikt; keine stille Auflösung |

#### 10.12.1 Deklarative Austauschmappings und externe Registries

**Entscheidung EXCHANGE-MAPPING-CONTRACT, delegiert gemäß
SPECROAD-DECISION-1:** Der folgende additive v1-Vertrag konkretisiert
SR-REQ-0316/0455 für Planschritt 14.a. Er legt passive Ressourcen und deren
reine Auswertung fest. Formatparser, Importhistorie, Verlustentscheidung,
Change Plans und Veröffentlichung behalten ihre gesonderten Verträge.

**Ressourcenhülle und Bindung.** Austauschmappings sind normative JSON-Dateien
unter `mappings/`. Ihre vollständige Pflichtfeldmenge lautet:

| Feld | Exakter Vertrag |
|---|---|
| `schema_version` | exakt `0.2.0` |
| `mapping_format_version` | exakt `exchange-mapping-v1` |
| `mapping_id` | Ressourcenkennung nach dem vorhandenen Profilkennungsprofil: `[A-Za-z][A-Za-z0-9._:-]{0,127}` |
| `mapping_version` | explizite SemVer-Version ohne führendes `v`, Bereiche oder Alias; dieselbe Syntax wie bei Profilversionen |
| `source_format` | exakt `reqif`, `reqifz`, `csv` oder `ndjson`; ReqIF bedeutet das Profil 1.2 nach Anhang D |
| `types` | Array von Typzeilen nach untenstehender Tabelle |
| `fields` | Array von Feldzeilen nach untenstehender Tabelle |
| `relations` | Array von Relationszeilen nach untenstehender Tabelle |
| `hierarchies` | Array von Hierarchiezeilen nach untenstehender Tabelle |
| `extensions` | Objekt mit namespaced Schlüsseln nach dem bestehenden Extensionsvertrag; ausschließlich passive Daten |

Alle Felder sind erforderlich; unbekannte Felder außerhalb von `extensions`
sind unzulässig. Leere Tabellen sind zulässig und bedeuten ausdrücklich
keine Abbildung in dieser Familie. Fehlende Tabellen sind kein Default.
Die Auswahl verwendet die exakte Kennung `mapping_id@mapping_version` und
bindet zusätzlich den RFC-8785-/SHA-256-Hash der **gesamten** Ressource.
Originalbytes werden daneben mit ihrem eigenen Bytehash erhalten. Ein Hash
beweist weder Urheberschaft noch Freigabe. Derselbe Schlüssel mit anderen
Inhalten ist kein stiller Ersatz; die erwartete Hashbindung muss passen.
Mehrere gelieferte Ressourcen desselben Schlüssels sind mehrdeutig, auch
bei identischen Bytes. Es gibt keine Auswahl nach Dateiname, Reihenfolge,
höchster Version oder Netzwerkauflösung. Ein eingebautes Profil muss dieselbe
eindeutig benannte, vollständig versionierte und gehashte Definition liefern.

`mapping_version` bezeichnet die vom Autor vergebene Inhaltsversion;
`mapping_format_version` bezeichnet die unterstützte Auswertungsgrammatik.
Eine neue gültige Inhaltsversion ist nicht allein wegen ihrer Nummer
unbekannt. Eine nicht bereitgestellte exakte Inhaltsversion, eine unbekannte
Grammatik oder abweichende erwartete Hashbindung werden abgewiesen.

**Tabellen.** Jede Zeile ist ein geschlossenes Objekt mit genau den genannten
Feldern. Externe Bezeichner sind nichtleere Unicode-Strings und werden exakt,
ohne Trimmen, Case-Folding, Normalisierung oder Interpretation als Pfad,
Ausdruck oder Muster verglichen. Die üblichen JSON-/Ressourcengrenzen gelten.

| Tabelle | Exakte Zeilenfelder | Bedeutung und Eindeutigkeit |
|---|---|---|
| `types` | `external_type`, `artifact_type` | Ein externer Typ auf genau einen bekannten nativen Artefakttyp; `external_type` ist innerhalb dieser Tabelle eindeutig. |
| `fields` | `external_type`, `external_field`, `target_field`, `value_map` | `external_type` muss in `types` vorkommen. `external_field` bezeichnet einen direkten Member des bereits geparsten externen Feldobjekts; `target_field` einen direkten Member der nativen Artefaktprojektion. Pro Typ sind sowohl Quellfeld als auch Zielfeld eindeutig. |
| `relations` | `external_type`, `relation_type`, `direction` | Ein externer Relationstyp auf einen bekannten gespeicherten Core-Relationstyp; `external_type` ist innerhalb der Tabelle eindeutig. `direction` ist exakt `forward` oder `reverse`. |
| `hierarchies` | `external_type`, `relation_type`, `direction` | Ein externer Hierarchietyp auf einen bekannten gespeicherten Core-Relationstyp; `external_type` ist innerhalb der Tabelle eindeutig. `direction` ist exakt `parent_to_child` oder `child_to_parent`. |

`target_field` ist ein nichtleerer literaler JSON-Membername, kein JSON-Pointer
oder Schreibbefehl. Die Projektion darf strukturierte Feldwerte einschließlich
eines vollständigen `extensions`-Objekts transportieren. Ein zusammengesetzter
Name wird nicht in verschachtelte Pfade zerlegt. `artifact_type` wird allein
von `types` bestimmt und ist deshalb kein zulässiges `target_field`.
Die native Artefakt-/Profilvalidierung entscheidet anschließend, ob die
vollständige Zielprojektion zulässig ist; ein Mapping erweitert kein Schema.

`value_map` ist entweder explizit `null` für unverändertes Kopieren des
vorhandenen JSON-Werts oder ein nichtleeres Array geschlossener Zeilen mit
genau `external_value` und `target_value`. Beide Werte sind gültige JSON-Werte
nach dem vorhandenen kanonischen Zahlen-/Stringvertrag. Die externen Werte
sind nach ihren RFC-8785-Bytes eindeutig. Damit sind `true`, `1` und `"1"`
verschiedene Schlüssel; numerisch äquivalente JSON-Schreibweisen sind kein
zweiter Schlüssel. Nicht gelistete Werte sind bei einer Tabelle ungemappt,
nicht durchgereicht. Status-, Enum- und Einheitenkennungen werden auf diese
Weise ausdrücklich abgebildet; es gibt keine automatische Statusaufwertung,
Textanalyse, Einheitenrechnung oder Typkonvertierung. Formatbezogene
CSV-Konvertierungen und Listenregeln bleiben Teil des expliziten CSV-Profils
nach SR-REQ-0326/D.2, nicht ausführbarer Code in dieser Tabelle.

**Reine Auswertung.** Eingaben sind die ausdrücklich gewählte Ressource und
bereits geparste Werte. Eine Artefaktabbildung erhält einen externen Typ und
ein Feldobjekt; sie liefert den gebundenen nativen Typ und die abgebildeten
Felder. Eine Relationsabbildung erhält Typ und zwei ausdrücklich übergebene
Endpunkte: `forward` erhält, `reverse` vertauscht die Reihenfolge. Für eine
Hierarchie sind die Eingabeendpunkte ausdrücklich Parent und Child; die
Richtung legt ihre Zielreihenfolge fest. Endpunkte werden nicht erzeugt,
erraten oder anhand von Text aufgelöst. Die spätere native Relationprüfung
prüft Typen, Identitäten, Zyklen und weitere Zielinvarianten unverändert.

Ein gewählter externer Typ muss genau eine Zeile seiner Familie treffen;
jede konfigurierte Feldzeile verlangt das tatsächliche Vorhandensein ihres
Quellmembers. Fehlend, leere Zeichenfolge und vorhandenes JSON-Null bleiben
verschieden. Ein unbekannter Typ, fehlendes Quellfeld, ungemappter Tabellenwert,
doppelte Zeile oder konkurrierendes Zielfeld erzeugt einen strukturierten
Mappingfehler (`SRV090`, Code 3), niemals First-/Last-Match oder Teilerfolg.
Alle nicht verwendeten Eingabefelder werden als unverändertes Restobjekt
zurückgegeben. Ein nichtleeres Restobjekt beweist keine Verlustfreiheit:
Der spätere Importplan muss diese Daten nach SR-REQ-0322 erhalten oder einzeln
als Verlust ausweisen. Der Mapper entscheidet keine Verlustakzeptanz.
Fehler nennen maschinenlesbaren Grund und betroffene Ressource/Feldposition,
ohne unkontrolliert Quellinhalte in Diagnosen zu kopieren.

Gleiche Eingaben mit derselben exakt gebundenen Ressource ergeben dieselben
fachlichen Projektionen. Auswertung verändert weder Eingabewerte noch
Projektdateien. Tabellenreihenfolge ist keine Priorität; doppelte Schlüssel
bleiben Fehler. Der vollständige Ressourcenhash folgt unverändert RFC 8785,
einschließlich Arrayreihenfolgen; semantisch gleich wirkende, anders geordnete
Tabellen erhalten nicht eigenmächtig denselben Ressourcenhash.

**Registry für Nichtartefaktidentitäten.** Ein Mapping kann ausdrücklich
gelieferte Begleitressourcen unter `mappings/` binden. Ihre Trennung verhindert,
dass jeder neue externe Registereintrag die Abbildungsregeln oder deren Hash
verändert. Ein Registry ist ebenfalls eine normative Mappingressource,
kein neues Artefakt und kein Cache. Seine exakte Pflichtfeldmenge lautet:

| Feld | Exakter Vertrag |
|---|---|
| `schema_version` | exakt `0.2.0` |
| `mapping_format_version` | exakt `external-identity-registry-v1` |
| `mapping_id`, `mapping_version` | eigene Ressourcenidentität nach obigem Kennungs-/Versionsprofil; nicht identisch mit dem Schlüssel der gebundenen Abbildungsressource |
| `mapping` | geschlossenes Objekt mit genau `mapping_id`, `mapping_version`, `sha256`; bindet den vollständigen kanonischen Hash einer tatsächlich gelieferten `exchange-mapping-v1`-Ressource |
| `entries` | Array der nachfolgend definierten Einträge, auch leer zulässig |
| `extensions` | passives Objekt mit namespaced Schlüsseln |

Unbekannte Felder und nicht passende Bindungen sind Fehler. Der eigene
Ressourcenhash umfasst das gesamte Registry einschließlich Einträge und
Mappingbindung; die Regelressource verweist nicht zurück auf den Registryhash.
Die allgemeine Modellwurzel umfasst beide ausgewählten Ressourcen nach 10.9;
ein neuer Registryeintrag verändert daher weiterhin den normativen Modellstand.
Die Einbindung verwendet tatsächliche Bytes und erwartete Identität/Hash,
keine automatisch gesuchte oder nachgeladene Datei.

Jeder Eintrag hat genau `object_class`, `source_system`, `source_document`,
`external_id`, `external_revision`, `data` und `extensions`.
`object_class` ist exakt `type`, `hierarchy`, `relation` oder `metadata`.
`source_system`, `source_document` und `external_id` sind nichtleere,
unverändert erhaltene Strings. `external_revision` ist ein nichtleerer String
oder ausdrücklich `null`; ein neuer Revisionswert erzeugt keine neue Identität.
`data` ist ein passives JSON-Objekt zur Erhaltung externer Eigenschaften;
`extensions` verwendet den bestehenden Namespaced-Vertrag. JSON-Null und
verschachtelte Werte innerhalb dieser Objekte bleiben erhalten. Quell-URLs,
Dateinamen und Textfragmente sind Daten, keine I/O-Anweisungen.

Der eindeutige Schlüssel lautet
`(object_class, source_system, source_document, external_id)`. Klassen und
Quelldokumente sind getrennte Namensräume. Doppelte Schlüssel innerhalb
eines Registry oder der gemeinsam ausgewerteten Registries sind Fehler,
auch bei gleichen Daten; keine stille Verschmelzung. Ein ausdrücklich
gesuchter, nicht vorhandener Schlüssel wird als fehlend zurückgegeben und
nicht angelegt. Änderungen und Importhistorie unterliegen weiterhin 10.12,
Planschritt 14.b und dem gemeinsamen Change-Plan-Vertrag; diese passive Registrierung
erzeugt weder SpecRoad-Artefakte noch Relationsreviews oder Human-Freigaben.

**Sicherheits- und Bestandsgrenze.** Beide v1-Formate werden mit dem vorhandenen
strikten JSON-Leser geprüft. Interpreter, Plugins, Skripte, Templates,
Konverter, Netzwerkzugriffe und Pfadauflösung aus Mapping-/Registrydaten sind
verboten. Zusätzliche ausführungsbezogene Steuerfelder werden durch die
geschlossene Grammatik abgewiesen. Beliebiger Text in passiven Daten wird
nicht ausgeführt und nicht anhand von Schlüsselwörtern umgeschrieben.
Ein abgebildeter Lifecyclewert oder ein Hash ist keine Schreib-/Freigabeautorität;
native Authoring-, Review-, Scope-, Transaktions- und Recovery-Gates bleiben
erforderlich. Ein passives Teilergebnis darf kein erfolgreiches Import-Apply
oder verlustfreies Gesamtformat behaupten.

Bestehende allgemeine Mappingressourcen, `legacy-manifest.json`, JUnit- und
andere Evidence-Mappings behalten ihre eigenen Verträge, Bytes und Hashes.
Ein historischer Ressourcenumschlag ohne obige Formatkennung bleibt für seine
bisherigen generischen Modell-/Archivfunktionen erhalten, wird aber nicht
stillschweigend als ausführbares Austauschmapping ausgewählt. Für seine Nutzung
als Austauschmapping ist eine neue explizite v1-Definition nötig, keine
automatische Migration oder Überschreibung. Die neue Form wird erst mit ihrer
tatsächlichen Implementierung als verfügbar beschrieben. Weitere Formatparser,
CLI, Roundtrips und Freigaben werden durch diese Präzisierung nicht vorgezogen.

#### 10.12.2 Importstrategien für bekannte native Identitäten

**Entscheidung IMPORT-CONFLICT-POLICY, delegiert gemäß
SPECROAD-DECISION-1:** `import-conflict-policy-v1` präzisiert
SR-REQ-0318/0456/0457 für 14.c. Die vier Strategien sind ausdrücklich
auszuwählen. Es gibt keinen impliziten Force-Modus und keinen aus der
Schreibweise eines externen Revisionswerts abgeleiteten Vorrang.

**Vergleich und Eingangsbindung.** Der reine Auswerter erhält die eindeutig
zugeordnete native External Identity, die exakte gewählte Mappingkennung
einschließlich Inhaltsversion und die aktuelle lokale sowie neue externe
fachliche Zielprojektion im selben Mappingraum. Beide Projektionen sind
explizit übergebene gültige JSON-Objekte; der Vergleich erfindet keine
fehlenden Felder, historischen Werte oder Mappingressourcen. Die Auflösung
und Hashbindung der verwendeten Mappingressource folgt weiterhin 10.12.1.
Die Hashes der beiden Projektionen werden aus ihren tatsächlichen RFC-8785-
Bytes berechnet. Ein vom Aufrufer behaupteter Änderungsstatus ersetzt diese
Berechnung nicht. Fehlend, Null, `true`, `1` und `"1"` bleiben nach dem
kanonischen JSON-Vertrag verschieden; Objektmemberreihenfolge ist irrelevant.

Für eine verwendbare Importhistorie müssen die fünf Historienfelder aus
10.12 vollständig und gültig vorliegen; `mapping_id` muss exakt zur gewählten
Mappingkennung passen. Verglichen werden `H(lokal)` mit
`last_imported_projection_sha256` und `H(neue Quelle)` mit
`last_source_projection_sha256`. Die Gleichheit der beiden aktuellen
Zielprojektionen wird ebenfalls kanonisch geprüft. Änderungen allein am
Originalpayload oder `external_revision` beweisen keine fachliche Änderung;
`last_source_payload_sha256` bleibt ein eigener Provenienzhash. Die fünf
Fälle aus 10.12 gelten unverändert, auch wenn die beiden historischen
Projektionshashes voneinander abweichen. Die External Identity und ihre
Historien-/Auditfelder werden nicht vom Auswerter in die übergebenen
fachlichen Projektionen hineinkopiert.

**Strategie und Ergebnis.** Für eine bekannte, eindeutig zugeordnete native
Identität gelten folgende Regeln:

| Strategie | Fachliches Ergebnis |
|---|---|
| `error` | Bekannte Identität zurückweisen; keine Zielübernahme und keine Historienänderung. Der maschinenlesbare Grund ist `known_identity`. |
| `skip` | Objekt ausdrücklich als übersprungen melden; lokale Projektion und Importhistorie unverändert erhalten. Das ist keine Übernahme oder neue Importbaseline. |
| `update_if_unchanged` | Genau die fünf Fälle aus 10.12 auswerten: unverändert, sichere Quellenübernahme, lokale Änderung behalten, konvergentes Ziel oder divergenter Konflikt. |
| `create_new_revision` | Dieselben fünf Fälle und Übernahmegrenzen anwenden; eine zulässige semantische Änderung als neue reguläre Revision derselben nativen Identität nach K.2 planen. Die ausgewählte Strategie bleibt im Ergebnis erkennbar. |

`create_new_revision` bezeichnet ausdrücklich keine neue native ID, kein
dupliziertes Objekt mit derselben External Identity und keinen eigenständigen
Historien-/Archivzweig. Die Strategie erlaubt insbesondere nicht, eine nur
lokal geänderte Projektion mit der unveränderten Quelle zurückzuschreiben.
In diesem Fall bleibt der lokale Wert erhalten, genau wie bei
`update_if_unchanged`. Für beide Strategien gilt bei sicherer Quellenübernahme
dieselbe native Revisionsregel; `update_if_unchanged` ändert ebenfalls niemals
Fachinhalt unter Beibehaltung der alten Revision. Diese bewusst gemeinsame
Übernahmegrenze ist Teil des v1-Vertrags, keine fehlende Implementierung
einer Force-Variante. Ein vollständig wertgleicher No-op erzeugt keine
künstliche Revision. Eine tatsächlich geänderte Importhistorie ist dagegen
Teil des vollständigen nativen Zielobjekts und unterliegt dessen regulären
Metadatenregeln, auch bei gleicher fachlicher Mappingprojektion. Bei einer
Relationsänderung bleibt die `relation_id` erhalten; K.2 erhöht gegebenenfalls
die Revision des enthaltenden Artefakts, keine zusätzliche Relationsrevision.

Die Vergleichsklassifikation und die gewählte Strategie bleiben getrennt
nachweisbar. Liegt eine verwendbare Historie vor, wird ein divergenter
beidseitiger Änderungsfall unabhängig von der Strategiewahl als
`SRV148`/Code 3 ausgewiesen. Auch `skip` oder `error` dürfen den vorhandenen
Konflikt nicht als gelöst oder die Quelle als übernommen markieren.
Das übersprungene beziehungsweise zurückgewiesene Objekt bleibt unverändert;
ein Importplan mit ungelöstem Konflikt erhält keine Apply-Freigabe.
Ein bekannter Identitätstreffer ohne Divergenz unter `error` wird mit
`SRV090`/Code 3 und obigem Grund zurückgewiesen. Ungültige Identitäten oder
Kollisionen werden vor jeder positiven Strategieentscheidung nach den
bestehenden Struktur-/`SRV147`-Regeln abgewiesen.

**Bestandsfälle und Baseline.** Eine gültige bestehende External Identity
ohne Importhistorie bleibt lesbar und kann ausdrücklich übersprungen oder
wegen `error` zurückgewiesen werden. `update_if_unchanged` und
`create_new_revision` dürfen daraus keine unveränderte Basis ableiten:
fehlende Historie ergibt `SRV090`/Code 3 mit `history_unavailable`, eine
abweichende historische Mappingkennung `mapping_mismatch`. Es gibt keine
automatische Migration, historische Hashnachbildung aus dem heutigen Stand
oder pauschale Freigabe. Eine unvollständige beziehungsweise ungültige
Historie bleibt ein Strukturfehler, kein solcher gültiger Bestandsfall.
Ein nicht bekannter Schlüssel ist kein bekannter Identitätskonflikt; die
Planung neuer Objekte bleibt dem normalen Importplan vorbehalten.

Nur tatsächlich übernommene beziehungsweise konvergente Ziele dürfen die
Importbaseline mit ihren gebundenen Projektionen fortschreiben. Im
unveränderten Fall gilt weiterhin die ausdrückliche Erlaubnis aus 10.12;
sie ist keine Verpflichtung zu einem unnötigen Write. Bei nur lokal veränderter
Projektion und unveränderter Quelle sowie bei Skip, Ablehnung oder Konflikt
bleibt die alte Historie erhalten. Insbesondere
darf ein lokal geänderter Wert nicht nachträglich als erfolgreich importierter
Stand gestempelt werden, um einen späteren Vergleich zu umgehen.

**Write- und Nachweisgrenze.** Der Vergleich liefert nur passive Ergebnisse
und zulässige Zielkandidaten. Er verändert keine Eingaben, Projektdateien,
Historie oder Betriebsdaten und erzeugt keine ID, Revision, Uhrzeit oder
Freigabe. Erst die nachfolgenden Schritte 14.d/14.e binden den vollständigen
Change Plan und wenden ihn über den gemeinsamen Writer an. Dabei gelten
K.2, 9.6.3, unveränderbare Nachweistypen, Scope-, Review-, Verlustzustimmungs-,
Transaktions- und Recovery-Gates unverändert. Eine Strategieauswahl oder
ein Kandidat ersetzt weder die erforderliche menschliche Entscheidung noch
eine Verlustakzeptanz; die Klärung verspricht keine zusätzliche Archivierung
jeder historischen Revision. Bestandsdaten und historische Evidence werden
durch diese Regel nicht umgeschrieben.

#### 10.12.3 Exportumfang und deterministisches Manifest v1

**Entscheidung EXPORT-MANIFEST-CONTRACT, delegiert gemäß SPECROAD-DECISION-1:**
Dieser additive Vertrag konkretisiert SR-REQ-0319/0328/0329/0332 für 14.l.
Die bestehenden Scope-, Mapping-, Format-, Verlust- und Sicherheitsverträge
bleiben wirksam. Ein Austauschmanifest ist weder ein Projektbundlemanifest
nach E.1 noch das ReqIFZ-Transportmanifest nach D.1.4.
Die nachfolgenden Auswahl-, Zeit-, Manifest-, Verlust- und Ausgabeverträge
einschließlich der geschlossenen Feldtabelle MÜSSEN eingehalten werden.

**Auswahl und Quellenbindung.** `project`, `document`, `query` und `release`
verwenden unverändert die Seeds, Konfiguration, Closure und Boundary References
nach 10.8. Der vollständige Descriptor einschließlich Grenzpolicy und aller
Query-Defaults wird gebunden; Formatname oder Ausgabepfad ersetzen ihn nicht.
Eine Query liefert ihre tatsächlich gebundene paginierte ID-Menge. Ihre
Anzeigespalten sind keine Erlaubnis, normative Felder still wegzulassen.
Vollständige native Ressourcen werden vor der Formatprojektion aufgelöst.
Starke Abhängigkeiten, historische Baselineobjekte und fehlende Ressourcen
dürfen nicht durch unvollständige Eingabesammlungen oder Formatverluste
umgangen werden. Bestehende Scope-Fehler bleiben Fehler.

Die Modellwurzel ist die nach 10.9 aus diesem aufgelösten nativen Umfang
berechnete Wurzel vor Formatprojektion oder Anhangtransport-Auswahl. Sie ist
nicht der Hash von CSV, XML, NDJSON, ZIP oder Exportmanifest. Mapping und
gegebenenfalls CSV-Profil werden über die bestehenden exakten Kennungs-,
Versions- und Hashbindungen ausgewählt. Mehrdeutige Auswahl, fehlende
Pflichtbindung oder ein geänderter Quellstand ergeben keinen Exporterfolg.
Ein Importmapping wird nicht durch Erraten einer inversen Zuordnung ersetzt;
die vorhandenen ausdrücklichen Format-/Mappingbindungen bleiben erforderlich.

Alle fachlichen Prüfungen und Ausgaben beziehen sich auf denselben vollständig
gebundenen Quellstand. Ein bloßer früherer Hash oder eine Teilbeobachtung
bescheinigt weder Vollständigkeit noch Aktualität. Vor erfolgreicher Ausgabe
müssen die verwendeten Quellen unverändert sein; vorhandene sichere Lese-,
Staging- und Fortsetzungsmechanismen bleiben zuständig. Normative Projektdateien
werden nicht verändert, auch nicht zur Vorbereitung eines Exports.

**Zeitprojektion.** Die vorhandene D.1-Regel wird für das gemeinsame
Exportmanifest aller vier Formate verwendet: `snapshot_at` ist das Maximum
der nativen `updated_at`-Werte der tatsächlich repräsentierten beziehungsweise
verlustfrei erhaltenen Artefakte aus `included_ids`. Außerhalb dieses
Exportinhalts liegende Artefakte liefern keinen Zeitwert. Ist diese Menge
leer, gilt exakt `1970-01-01T00:00:00Z`. Ein fehlendes oder ungültiges
Pflichtfeld in einem enthaltenen Artefakt wird nicht durch diesen Leerfall
ersetzt. `created_at`, Dateimtime, Git-Zeit, Laufzeit und lokale Zeitzone sind
keine Ersatzquellen. ReqIF-`CREATION-TIME` und `snapshot_at` stimmen überein.

Es wird nach den UTC-Kalenderkomponenten und dem exakten Dezimalbruchteil
verglichen, nicht nach Strings, Floatwerten oder gerundeten Mikrosekunden.
Die vorhandene UTC-Gültigkeitsprüfung einschließlich ihres Sekunden-60-Profils
bleibt erhalten; diese Regel behauptet keine neue externe Schaltsekundenprüfung.
Die Ausgabe verwendet großes `T` und `Z`, entfernt nur nachgestellte Nullen
des Sekundenbruchteils und lässt einen dadurch leeren Bruchteil samt Punkt weg.
Alle übrigen gültigen Stellen bleiben erhalten. Gleichwertige Schreibweisen
ergeben denselben abgeleiteten Zeitpunkt; native Quellwerte werden nicht geändert.

**Geschlossenes Manifest.** Ein erfolgreicher Export liefert ein separates,
nach RFC 8785 kanonisiertes JSON-Objekt mit genau diesen Pflichtfeldern:

| Feld | Vertrag |
|---|---|
| `manifest_version` | Exakt `exchange-export-v1`. |
| `format` | Exakt `reqif`, `reqifz`, `csv` oder `ndjson`. |
| `format_version` | `1.2` für ReqIF, `reqifz-container-v1` für ReqIFZ einschließlich ReqIF 1.2, `csv-profile-v1` für das gebundene RFC-4180-Profil, `1.0.0` für die NDJSON-Objekthülle. Dies ändert keine bestehenden Wireversionen, insbesondere nicht ReqIF-`REQ-IF-VERSION`. |
| `mapping` | Die bestehende Bindung mit genau `mapping_id`, `mapping_version`, `sha256`; der Hash bindet die gesamte kanonische Mappingressource. |
| `format_profile` | Bei CSV die bestehende CSV-Profilbindung mit genau `mapping_id`, `mapping_version`, `sha256`; sonst `null`. |
| `scope_descriptor` | Der vollständige gültige Descriptor der tatsächlichen Auswahl nach 10.8. |
| `boundary_references` | Genau die nach 10.8/10.9 gebundenen Boundary References in ihrer dort festgelegten Reihenfolge und Feldform. |
| `model_root_sha256` | Kleingeschriebene vollständige SHA-256 der gebundenen nativen Modellwurzel nach 10.9. |
| `snapshot_at` | Der oben definierte abgeleitete UTC-Zeitpunkt. |
| `tool_version` | Die tatsächliche vollständige SpecRoad-Toolversion; kein Lauf-, Host- oder Sitzungsidentifikator. |
| `options` | Genau die materialisierten booleschen Werte `include_attachments` und `fail_on_loss`. Formatabhängige Abbildungsoptionen bleiben im gebundenen Mapping/Profil. Ein Ausgabepfad ist keine fachliche Option. |
| `included_ids` | Duplikatfreie, nach ID-UTF-8-Bytes sortierte native Artefakt-IDs, deren Identität im tatsächlichen Austauschinhalt repräsentiert oder nach dem Formatprofil verlustfrei erhalten ist. Fehlende Felder solcher Artefakte bleiben einzeln als Verlust sichtbar. |
| `excluded_contents` | Liste von Objekten mit genau `resource_id`, `pointer`, `reason`, wie unten festgelegt. |
| `losses` | Liste von Objekten mit genau `resource_id`, `pointer`, `reason`, `format_details`, wie unten festgelegt. |
| `attachments` | Liste sämtlicher zum nativen Umfang gehörender Anhangdeskriptoren mit genau `path`, `size`, `media_type`, `sha256`, `included`; die ersten vier Felder behalten ihren bestehenden Vertrag, `included` ist boolesch und bezeichnet tatsächlich mitgelieferte vollständige Bytes. Sortierung nach Pfad-UTF-8-Bytes. |
| `output_sha256` | SHA-256 der tatsächlichen vollständigen primären Austauschbytes; bei ReqIFZ der gesamten ZIP-Datei. |

`resource_id` ist die vorhandene eindeutige Identität im gebundenen
Quellinventar, kein neu erratener Dateiname. `pointer` ist ein gültiger
JSON Pointer innerhalb dieser Ressource; `""` bezeichnet die ganze Ressource.
Bei Anhängen bezeichnet `resource_id` den validierten projektroot-relativen
Pfad und `pointer` ist leer. `reason` ist ein nichtleerer maschinenlesbarer
Grund nach `[a-z][a-z0-9_]*`, keine menschliche Meldung. Der Ausschluss
einer Anhangpayload durch die Transportoption heißt `attachments_disabled`;
Formatverluste behalten ihren konkreten maschinenlesbaren Grund.

Die beiden Listen sind nach den UTF-8-Bytes des Tupels
`(resource_id, pointer, reason)` sortiert und darin duplikatfrei.
`format_details` ist ein kanonisches JSON-Objekt: vorhandene gebundene
formatbezogene Verlustdaten einschließlich ihrer Identitäten werden darin
unverändert erhalten; ohne zusätzliche Formatdaten ist es `{}`. Konkurrierende
Bewertungen derselben Tupelidentität sind ein Konflikt, kein Last-write-wins.
Payloadtexte, absolute Hostpfade und Laufzeitdaten werden nicht als Diagnosen
hinzuerfunden. Formatbezogene Referenzen, etwa XML-Lokationen, bleiben in den
vorhandenen gebundenen Formatdaten und werden nicht als JSON Pointer ausgegeben.

**Vollständigkeit und Verluste.** Der Export bewertet den gesamten angeforderten
Umfang. Die bewusste Scope-/Konfigurationsauswahl wird vollständig durch
`scope_descriptor` und `boundary_references` erklärt; nicht angeforderte
Inhalte sind allein deshalb kein Formatverlust. Das übrige Ursprungsinventar
wird nicht als zusätzliche Ausschlussliste in den Export kopiert. Dadurch
verändern unabhängige Änderungen außerhalb des gebundenen Modellumfangs
nicht die Ausgabe. `excluded_contents` bezeichnet die konkreten Auslassungen
innerhalb des angeforderten Umfangs durch Formatprojektion oder Transportoption.
Im Umfang angeforderte, aber nicht repräsentierte oder nachweislich erhaltene
Inhalte sind dagegen konkrete Verluste. Ein vollständig ausgelassenes Artefakt
fehlt in `included_ids` und erscheint mit seinem Verlust auch in
`excluded_contents`. Eine bloße Erweiterungsablage ohne erforderlichen
Erhaltungsnachweis darf nicht als verlustfrei gelten. Bestehende ReqIF-
Verlustidentitäten, Erhaltungsbeweise und Freigabegrenzen bleiben wirksam.

`include_attachments=true` verlangt alle zum Umfang gehörenden tatsächlichen
Anhangbytes samt validierter Byte-/Hash-/Pfadbindung. Fehlende, geänderte oder
unsichere Bytes sind Fehler, keine akzeptierbaren Verluste. Bei `false` bleiben
die Deskriptoren mit `included=false` sichtbar; jede ausgelassene Anhangpayload
erzeugt einen Ausschluss und einen Verlust `attachments_disabled`. Die
Modellwurzel wird deshalb nicht als anhangfreier nativer Umfang neu berechnet.
`fail_on_loss=true` verhindert bei jedem verbleibenden Verlust erfolgreiche
Exportveröffentlichung; ein Diagnosebericht ist kein erfolgreicher Export.
`false` unterdrückt weder Verluste noch andere vorgeschriebene Freigaben und
erlaubt keine Sicherheits-, Integritäts- oder Modellverletzung.
Die CLI-Flags `--include-attachments` und `--fail-on-loss` materialisieren
beim Setzen jeweils `true`, ohne das jeweilige Flag `false`. Insbesondere
bleibt die bereits in D.1.3 festgelegte Bedeutung eines nicht gesetzten
Verlustverbots erhalten. Formatwahl und Ausgabeziel ändern diese Werte nicht.

Das Manifest wird aus tatsächlichen Quellen, Bewertungen und fertigen
Ausgabebytes abgeleitet. Vom Aufrufer behauptete Inventare oder Hashes ohne
diese Prüfungen reichen nicht. Es inventarisiert und hasht sich nicht selbst:
keine zusätzliche NDJSON-Zeile, CSV-Datenzeile, ReqIF-Nutzinformation oder
ReqIFZ-Pflichtdatei wird für dieses Manifest eingeführt. Es bleibt bei allen
Formaten separat; sein Speicherziel wird über die bestehende generierte
Ausgabeintegration gebunden, nicht in die fachlichen Bytes aufgenommen.
Alle tatsächlichen beigefügten Anhangbytes sind über die Deskriptoren gebunden.
Dies liefert keinen Ersatz für vollständige native Projektbundles nach E.

Gleicher Fachumfang, Mapping-/Profilinhalt, materialisierte Optionen und
Toolversion ergeben identische primäre Austauschbytes und Manifestbytes,
unabhängig von Uhrzeit, CWD, Inventariteration und Ausgabeziel. Die wirkliche
Ausführungszeit bleibt ausschließlich im nicht exportierten Auditbericht.
Bestehende Nutzungs-, Modell-, Konflikt-, Sicherheits- und Hostfehlerklassen
nach 11.8 bleiben erhalten; dieses Manifest führt keine Ausnahme davon ein.
Harte Parser-/Sicherheitsgrenzen und vollständige sparsame Fortsetzung nach
O/P bleiben wirksam. W/R/C, CLI-Integration und Verhaltensevidence folgen
gesondert; dieses Dokument behauptet keine fertige Exportfunktion.


### 10.13 Evidence-Origin

Evidence unterscheidet `recorded_manual`, `imported_junit`, `imported_sarif`, `imported_generic` und `generated_internal`. Der Origin bestimmt Provenienzpflichten, nicht das berechnete Verification Result. Evidence speichert Subject-Revisionen und Vollhashes für Audit sowie `verification_context_hash-v1` für fachliche Aktualität und `run_context` nach 10.5.2 für die Auswahl des geprüften Stands und Laufs. Konfigurationsgebundene Evidence gilt nur für denselben Konfigurationshash; eine unabhängig verwendbare Evidence verlangt eine ausdrückliche Contract-Policy.

### 10.14 Dokumentblöcke und CommonMark-Kernsubset

Ein vollständiges Projekt besitzt genau ein nicht retiriertes Dokument mit `document_role=primary_specification`; weitere Dokumente verwenden `supporting`.

| `block_kind` | Exakte Payload |
|---|---|
| `prose` | `{ "markdown": <CommonMark-Kernsubset-String> }` |
| `artifact_ref` | `{ "render_mode": "summary"\|"full"\|"link" }`; genau eine ausgehende `references`-Relation bezeichnet das Zielartefakt |
| `query` | entweder eingebettete `query` nach 11.6 oder `source="view"` mit genau einer ausgehenden `references`-Relation zu einem `view`; zusätzlich `columns` und `empty_policy=omit\|message\|error` |
| `table` | entweder `source="view"` mit genau einer ausgehenden `references`-Relation zu einem `view` oder `{ "columns": [...], "rows": [...] }`; Literaldaten sind typisiert und keine fachliche Artefaktkopie |
| `admonition` | `{ "level": "note"\|"tip"\|"important"\|"warning"\|"caution", "title": <optional>, "markdown": <String> }` |
| `page_break` | `{}` |
| `include_document` | `{ "mode": "content"\|"section" }`; genau eine ausgehende `references`-Relation zielt bei `content` auf ein `document` und bei `section` auf eine `section` |

Das CommonMark-Kernsubset umfasst Absätze, Emphasis, Strong, Inline-Code, Fenced-Codeblöcke, geordnete und ungeordnete Listen, Blockquotes, thematische Trennlinien, Links und Bilder auf projektinterne Anhänge. Raw HTML, HTML-Entities mit aktiver Semantik, Überschriften in Prose, Link-Referenzdefinitionen, eingebettete Daten-URLs und externe Includes sind unzulässig. Zeilenenden werden vor Parsing auf LF normalisiert. Abschnittsüberschriften stammen ausschließlich aus `section`.

`include_document`-Kanten werden vor Rendering als eigener Include-Graph geprüft; jeder direkte oder transitive Zyklus ist ein Fehler. `section remove` verlangt standardmäßig einen leeren Abschnitt. Für einen nichtleeren Abschnitt ist genau eine Option aus `--cascade` oder `--move-children-to <SECTION-ID>` erforderlich; alle Änderungen werden als Retire-/Relationsoperationen geplant, ohne verwaiste Kindobjekte zu hinterlassen.

### 10.15 Semantischer Merge-Plan

Ein Merge-Plan bindet `base`, `ours` und `theirs` jeweils an Projekt-ID, Scope Descriptor, Modellwurzel und Herkunft. Automatische Zusammenführungen und Konflikte werden feldweise dokumentiert. Eine Konfliktauflösung ist ein unveränderbarer Planbestandteil. Der Merge erzeugt keinen Git-Commit. Die Metadaten folgen Anhang K.

### 10.16 Projektbundle und partieller Umfang

Ein Bundle verwendet ausschließlich die kanonischen Werte `bundle_kind=project|partial` nach Anhang E.3; `document` und `release` sind Scope-Arten, keine Werte dieses Felds. Ein `project`-Bundle enthält einen geschlossenen, nicht konfigurationsgefilterten Projektscope und bildet nach Extraktion ein normales schreibbares SpecRoad-Projekt. Es enthält standardmäßig abgeschlossene Request- und Transaktionsreceipts in einer getrennten Betriebssektion, deren Hash im Bundlemanifest gebunden ist, aber nicht in die fachliche Modellwurzel eingeht.

Ein über `--scope document` oder `--scope release` gewähltes Bundle trägt `bundle_kind=partial`, `read_only=true`, Ursprungmodellwurzel, partiellen Scope Descriptor, partielle Modellwurzel und alle Boundary References. Nach Extraktion sind nur `validate --partial`, `show`, `query`, `trace`, `why`, `impact`, `diff`, `render`, `view render`, `diagram`, `bundle verify` und `project inspect` zulässig; zusätzlich sind die schreibfreien Metadatendiagnosen `environment check`, `recover status` und `lock status` sowie projektlose Bootstrapbefehle erlaubt. Normative Writes, Baselines, Migration, Merge, Import, vollständige Release Readiness und Re-Export als Vollprojekt sind bis zu einer expliziten Rehydrierung mit dem Ursprungsprojekt verweigert.

Das kanonische ZIP-Profil für Projektbundle und ReqIFZ lautet:

- keine Directory Entries, Symlinks oder Spezialdateien;
- Pfade sind NFC-normalisierte relative POSIX-UTF-8-Pfade ohne leere, `.`- oder `..`-Segmente;
- Einträge sind nach UTF-8-Bytes lexikografisch sortiert;
- Zeitstempel ist für jeden Eintrag `1980-01-01 00:00:00`;
- `create_system = 3` (UNIX), benötigte ZIP-Version 2.0;
- Kompressionsmethode `ZIP_STORED`;
- UTF-8-Flag wird für alle Namen konsistent gesetzt; Data Descriptor ist unzulässig;
- Extra Fields, Datei- und Archivkommentare sind leer;
- externe Attribute sind exakt `0o100644 << 16`, interne Attribute exakt `0`;
- Dateinamen und Payloads sind vor Aufnahme vollständig gehasht; doppelte Zielpfade sind unzulässig.

`bundle create --scope project --configuration <ID>` wird als widersprüchlicher Vollprojektauftrag mit Code 2 abgewiesen. Dokument-/Release-Teilbundles unterstützen die Konfigurationsauswahl gemäß SR-REQ-0400; sie bleiben partial. Ein Vollbundle wird nur aus einem abgeschlossenen, regulär lesbaren Projektstand erzeugt. Aktive Journale, Locks, Staging und Caches sind kein portabler Erfolgsstand und werden nicht als Ersatz für abgeschlossene Receipts gebündelt. Bei ungelöster Transaktion bricht `bundle create` schreibfrei mit Exit Code 5 ab; nach Recovery kann der Aufruf wiederholt werden. Ein Bundle in derselben verlorenen Sandbox ist keine externe Sicherung.

### 10.17 Formatierungsumfang

`specroad format` betrachtet ausschließlich `specroad.json`, Profile, Regeln, Mappings und aktuelle, veränderbare Artefakt-JSON-Dateien. Ausgeschlossen sind `archive/**`, `attachments/**`, `generated/**`, `.specroad/**`, recorded Evidence, sealed Baselines, recorded Relationsreviews und Proposals im Endstatus `applied`, `rejected` oder `stale`. `format --check` ist read-only. Eine tatsächliche Normalisierung verwendet `representation_normalize` mit erwartetem und resultierendem Byte-Hash; semantische Modellwurzel, Artefaktrevision und Zeit-/Akteursmetadaten bleiben unverändert.

### 10.18 Konfigurationsumfang

Eine ausgewählte `configuration` wird einschließlich Parent-Kette zu einer effektiven Wertemenge aufgelöst. `applicability` wird vor Scope-Closure deterministisch ausgewertet. Inkonsistente Pflichtabhängigkeiten sind Fehler. Verification Result und Coverage werden im Konfigurationsscope berechnet. Konfigurationsgebundene Evidence gilt nur für denselben Konfigurationshash; konfigurationsunabhängige Evidence ist nur bei ausdrücklicher Contract-Policy verwendbar.

---

### 10.19 Unveränderbare Legacy-Nachweise

Die verbindliche Migration geschützter historischer Ressourcen steht in Anhang Q. Der normative Manifestpfad ist `mappings/legacy-manifest.json`. Dieses Manifest und seine Originalhashes gehören zu jedem Scope, der eine darin registrierte Ressource einschließt. Originalbytes und historische Hashalgorithmen bleiben erhalten; aktuelle 0.2-Gültigkeit wird nicht aus ergänzten Metadaten erfunden.

### 10.20 Vollständige fortsetzbare Arbeitsaufträge

Der Arbeitsvertrag `work-v1` aus Anhang P zerlegt denselben gebundenen Gesamtauftrag in wiederholbare Schritte. `work_id`, Eingangsmanifest, fachliche Optionen, Actor, Request-ID und Planbindungen bleiben über alle Schritte gleich. Arbeitsdaten sind Betriebsdaten außerhalb des normativen Projekts, keine zweite fachliche Quelle und keine Projekterweiterung zu mehreren Repositories.

---

## 11. CLI-Vertrag

### 11.1 Verbindliche Aufrufformen

```text
specroad <command> ...
python3 -m specroad <command> ...
python3 specroad.pyz <command> ...
```

Die drei Aufrufformen sind für die jeweilige Distribution semantisch gleichwertig. In einer nicht installierten Sandbox sind die beiden Python-Aufrufe verbindlich.

### 11.2 Mindestbefehle

```text
specroad init [PATH]
specroad change apply <change-plan-file>
specroad config show
specroad profile explain
specroad language list|show ...
specroad analyzer list|describe|request|run|import|show|evaluate ...
specroad format [--check]
specroad artifact create|update|show ...
specroad relation add|remove|review|status ...
specroad lifecycle transition ...
specroad document create|show|render ...
specroad section add|move|remove ...
specroad block add|update|remove ...
specroad view create|show|render ...
specroad diagram trace|architecture|release ...
specroad validate [artifact-id ...]
specroad lint [artifact-id ...]
specroad render --view specification|traceability|roadmap|verification
specroad query [filters]
specroad trace <artifact-id> --direction in|out|both --depth <n>
specroad why <artifact-id>
specroad impact <artifact-id>
specroad diff --against <baseline-id|git-ref|bundle|path>
specroad coverage [--release <release-id>]
specroad roadmap explain <artifact-id>
specroad release readiness <release-id>
specroad evidence record|import ...
specroad baseline create|show|verify|compare ...
specroad proposal create|change|show|validate|check|review|apply ...
specroad proposal review start <PROP-ID> ...
specroad import plan|apply <reqif|reqifz|csv|ndjson> ...
specroad export <reqif|reqifz|csv|ndjson> ...
specroad migrate plan|apply|verify ...
specroad merge plan|conflicts|resolve|apply ...
specroad configuration evaluate <configuration-id>
specroad bundle create|verify|extract ...
specroad bundle create --profile ai-runtime --direction outbound --output <ZIP>
specroad bundle create --profile ai-runtime --direction return --reference <HINPAKET> --proposal <PROP-ID> --output <PATCH-ZIP>
specroad bundle verify --profile ai-runtime <ZIP> [--reference <HINPAKET>]
specroad bundle extract --profile ai-runtime <HINPAKET> --target <VERZEICHNIS>
specroad recover status|run|discard|restore ...
specroad lock status|recover ...
specroad capabilities
specroad schema list|show ...
specroad command describe ...
specroad project inspect
specroad environment check [--for-command <COMMAND-ID>]
specroad work status|resume|export|restore|prompt|cancel ...
specroad version
```

Kompatible Kurzaliase wie `specroad create`, `specroad show` und `specroad retire` dürfen Version-0.1-Aufrufe erhalten, verweisen jedoch auf die 0.2-Befehlsgruppe und besitzen keine abweichende Semantik.

Das explizite Profil `ai-runtime` folgt Anhang W. Ohne dieses Profil bleiben die
Projekt-/Teilbundlebefehle aus Anhang E unverändert. Hin- und Rückexport benutzen
`bundle create`; `--direction` legt Paketart und Voraussetzungen verbindlich fest.
`bundle create --profile ai-runtime --direction outbound` ist die ausdrücklich
Git-spezifische Transportvariante. Rückexport, Prüfung und Öffnen in der Sandbox
benötigen weder Git noch Shell. Die lokale Ausführung einer PatchHarbor-Übernahme
ist eine gesonderte, ausdrücklich autorisierte Hostoperation nach W.5 und kein
versteckter Seiteneffekt von `bundle verify` oder `proposal apply`.

### 11.3 Globale Optionen und Anwendbarkeit

```text
--project <path>
--format pretty|json|sarif
--profile <profile-id[@version]>
--configuration <configuration-id>
--strict
--fail-on error|warning
--no-color
--quiet
--actor-type human|ai|ci|tool
--actor-id <id>
--request-id <id>
--dry-run
--as-proposal
--fail-on-change
--changed-only --against <git-ref>
--accept-remote-risk
--resource-profile constrained|standard
--cpu-budget-ms <positive-integer>
--wall-budget-ms <positive-integer>
--memory-budget-mib <positive-integer>
--scratch-budget-mib <positive-integer>
--cache off|read
--metrics
--work-dir <path>
--step-cpu-ms <positive-integer>
--step-wall-ms <positive-integer>
```

`--project`, `--format`, `--profile`, `--configuration`, `--no-color` und `--quiet` sind nur anwendbar, wenn der maschinenlesbare Command Contract sie nennt. Normative Schreibbefehle unterstützen zusätzlich Akteur, Request-ID und Dry-Run. Unzulässige Optionen sind Nutzungsfehler und werden nie ignoriert. Betriebsoptionen aus Anhang O sind unabhängig von fachlichen Profilen; `--metrics` ist für ausführende und diagnostische Befehle optional. `environment check` besitzt den vollständigen Vertrag aus Anhang N.4.

### 11.4 Konfigurations- und Optionspräzedenz

Von niedriger zu höherer Priorität:

1. eingebaute Defaults;
2. `specroad.json`;
3. effektive Profilkomposition nach 10.10;
4. ausgewählte Produktkonfiguration;
5. explizite CLI-Optionen.

`--profile` darf wiederholt werden. Sobald mindestens ein `--profile` angegeben ist, ersetzt die geordnete CLI-Liste die Projektliste; die exakte Core-Version wird automatisch vorangestellt. `NO_COLOR` beeinflusst ausschließlich Darstellung. Die davon getrennte Auflösung rein betrieblicher Ressourcenbudgets steht in Anhang O.1; sie verändert keine semantische Konfigurationsprojektion.

### 11.5 stdout, stderr und JSON-Envelope

Ergebnisdaten gehen auf stdout; betriebliche Meldungen außerhalb des Ergebnisdokuments gehen auf stderr. `--format json` erzeugt genau ein vollständiges JSON-Objekt. Wegen der neuen Fortsetzungs- und Ergebnislieferzustände hat dieser Envelope die eigenständige Major-Formatversion `2.0.0`; Programm-/Zielreleaseversion und Artefaktschema werden dadurch nicht stillschweigend geändert.

```json
{
  "format_version": "2.0.0",
  "command": "validate",
  "status": "continuation_required",
  "project": null,
  "result": null,
  "result_ref": null,
  "diagnostics": [],
  "summary": {
    "complete": false,
    "work_id": "WORK-00000000000000000000000001",
    "completed_units": 128,
    "total_units": null,
    "remaining_manifest_sha256": "...",
    "checkpoint": "work/checkpoint.json",
    "next_action": {
      "command_id": "work.resume",
      "arguments": {"work_dir": "work"}
    }
  }
}
```

`command`, `status`, `project`, `result`, `result_ref`, `diagnostics` und `summary` sind Pflichtfelder. `project=null` bedeutet noch kein ausgewählter oder vollständig gebundener Projektroot; bei bekannter Auswahl ist es ein Objekt nach dem bisherigen Projektvertrag. Noch nicht berechnete Hashes sind `null`, niemals erfunden.

| Status | Exit Code | Semantik |
|---|---:|---|
| `success` | 0 | Der angeforderte Gesamtauftrag und seine Gates sind vollständig abgeschlossen. |
| `partial` | 0 | Nur bei ausdrücklich fachlich gewähltem Teilvertrag zulässig; nicht als Ersatz für ausgelassene Arbeit. |
| `continuation_required` | 8 | Ein vollständiger gültiger Checkpoint liegt vor; der Gesamtauftrag ist noch nicht fertig. |
| `failed` | 1–7 | Tatsächlich festgestellter Fach-, Eingabe-, Konflikt-, Sicherheits- oder Umgebungsfehler. Ein erhaltener Arbeitsstand und konkrete Abhilfe dürfen mitgeliefert werden. |

Die Statuswerte sind keine austauschbaren Erfolgscodes. Ein aufrufender Runner behandelt 8 als Fortsetzungsaktion, nicht als bestandenes Gate und nicht als endgültigen Fehler. `summary.complete=true` gilt erst nach Abschluss aller Pflichtarbeit des gebundenen Scopes. Bei einem Prüfkommando bleibt ein nachweislicher Fachfehler Code 1, auch wenn die gesamte Prüfung technisch vollständig durchgeführt wurde. Die erfolgreiche Aufnahme einer menschlichen negativen Relationsreview ist dagegen nach Kapitel 11.13 ein ausgeführter Schreibauftrag mit Code 0 und ausdrücklich negativem fachlichem Review-Ergebnis; sie behauptet keine bestandene Validierung. Ein solcher vollständiger Fehlerbericht darf `summary.complete=true` tragen, aber niemals `status=success`.

Ein kleines fachliches Resultat steht in `result` und `result_ref=null`. Ein großes Ergebnis wird vollständig in einer atomaren externen Ergebnisdatei geliefert: `result=null`, `result_ref={path,media_type,size,sha256,result_schema}`. Das unveränderte fachliche Ergebnisschema, zum Beispiel `items,total,offset,limit,returned,truncated` für Query, gilt dann für den Dateiinhalt. Diese Lieferung verkürzt weder Treffer noch Diagnosen; `summary` erklärt den Lieferweg. Bei mehrteiligen Ausgaben verweist `result_ref` auf ein vollständiges, sortiertes Manifest. Die Auswahl des Lieferwegs ist betriebliche Darstellung, keine Scopeänderung.

Fachliche Diagnosen werden stabil sortiert; übergroße vollständige Diagnosenlisten stehen in der Ergebnisdatei und der Envelope kennzeichnet seinen begrenzten Anzeigeausschnitt ausdrücklich. `--quiet` entfernt keine Pflichtfelder. Operational Checkpoints, Pfade, Verbrauchswerte und Fortsetzungsstände sind nicht Teil des fachlichen Byte-Determinismus. Der vollständige Fachpayload bleibt bei identischen fachlichen Eingaben einschließlich einer etwaigen Bewertungsauswahl identisch; für `project inspect` ist der Fachpayload ausdrücklich die Projektion nach 11.5.1 und nicht das gesamte Betriebsresultat. Nur `--metrics` ergänzt freiwillige gemessene Verbrauchswerte; Fortsetzungsstatus, offene Einheiten und Budgetereignisse zur Erklärung sind auch ohne diese Option erlaubt.

Kein Befehl liest oder wartet auf stdin ohne ausdrücklichen Marker wie `--input -` oder `--operation -`. SARIF enthält ausschließlich das abgeschlossene fachliche Diagnoseergebnis; solange eine Prüfung fortzusetzen ist, liefert die Runtime einen JSON-Kontrollenvelope 2.0.0 mit Code 8 statt einer scheinbar abgeschlossenen SARIF-Prüfung. `command describe` dokumentiert diesen Fall.

#### 11.5.1 Fachliche und betriebliche Projektselbstbeschreibung

`project inspect` verwendet innerhalb des Envelopes das Ergebnisformat `project-inspect-v1` mit exakt den Pflichtfeldern `format_version`, `semantic` und `runtime`. `format_version` ist die eigenständige SemVer `1.0.0`. Dieselbe Struktur gilt bei externer Lieferung über `result_ref`; es werden keine Pflichtinformationen entfernt.

| Teilbereich | Pflichtfelder und Bedeutung |
|---|---|
| `semantic` | `project_id`, `model_root_sha256`, `schema_version`, `active_profiles`, `artifact_counts`, `migration_needed`, `diagnostic_summary`, `primary_documents`; nur fachliche, deterministisch berechnete Werte |
| `runtime` | `project_root`, `open_transaction`, `writer_lock`, `consistency_state`; tatsächlicher aufrufbezogener Zustand, kein Cachewert aus einer früheren Sandbox |

`active_profiles` ist eine nach der effektiven Profilreihenfolge geordnete Liste `{profile_id,version}`; `artifact_counts` ist ein nach Artefakttyp geordnetes Objekt; `primary_documents` ist eine nach ID geordnete Liste `{id,title}`. `diagnostic_summary` zählt ausschließlich fachliche `error`, `warning` und `info` und verwendet projektrelative Fundstellen. `migration_needed` ist bei eindeutig geladenem Schema ein Boolean; noch nicht sicher bestimmte Werte einschließlich Modellwurzel und Artefaktzahlen sind `null`, nicht erfunden. `open_transaction` und `writer_lock` sind entweder die nach bestehenden Verträgen ermittelten Metadatenobjekte oder `null`; nicht prüfbare Informationen werden ausdrücklich als unbekannt gekennzeichnet, nicht als „kein Lock“ ausgegeben.

`consistency_state` ist `consistent`, `recovery_required`, `writer_active` oder `unknown`. Nur aus einem konsistenten lesbaren Snapshot wird eine abgeschlossene semantische Projektselbstbeschreibung behauptet. Bei Recoverybedarf oder aktivem Writer gelten die bisherigen Lese-/Recoveryregeln; nicht belastbare semantische Felder bleiben `null` und der Aufruf liefert den vorgesehenen Konflikt-/Recoverystatus. `project inspect` repariert oder sperrt dafür nicht heimlich das Projekt.

Die Determinismusgarantie gilt für die RFC-8785-Bytes von `{format_version,semantic}` bei identischem konsistentem Modell, identischen fachlichen Optionen, Profilen und Toolversion. Für `runtime`, den betrieblichen Teil des Envelope-`project`-Objekts, äußere Pfade, Status-/Diagnoseangaben zur Laufzeit und Messwerte wird keine Gleichheit allein aus der Modellsemantik versprochen. Vollständige JSON-Gleichheit setzt zusätzlich identische betriebliche Eingaben und identischen Lieferweg voraus. Hashes, Golden Tests und Vergleiche müssen genau diese Projektion benutzen; keine Implementierung darf dafür Projektroot, offenen Write oder Lock verschweigen.

Bei `capabilities`, `schema list`, `schema show` und `command describe` bleibt der vollständige fachliche Selbstbeschreibungs-Payload der identischen Distribution und der identischen semantischen Optionen deterministisch. Der Standard-Envelope 2.0.0 wird durch das hier erstmals vollständig festgelegte befehlsspezifische Resultat nicht neu definiert; unbekannte Resultatversionen sind explizit abzulehnen.


### 11.6 Query-Grammatik und Ergebnisschema

```text
specroad query
  [--type <TYPE>]...
  [--maturity <STATE>]...
  [--implementation-status <STATE>]...
  [--verification-plan-status <STATE>]...
  [--verification-result <STATE>]...
  [--owner <VALUE>]...
  [--tag <VALUE>]...
  [--release <ID>]...
  [--has-relation <TYPE>]...
  [--missing-relation <TYPE>]...
  [--full-text <TEXT>]...
  [--filter <SRX-JSON-FILE>]...
  [--evaluation <FILE>]
  [--select <JSON-POINTER>]...
  [--sort <KEY[:asc|desc]>]...
  [--offset <N>] [--limit <N>]
```

Wiederholte Werte eines Wertfilters (`--type`, `--maturity`, `--implementation-status`, `--verification-plan-status`, `--verification-result`, `--owner`, `--tag`, `--release`, `--has-relation`, `--missing-relation`, `--full-text`) sind innerhalb genau dieser Filterart ODER-verknüpft. Verschiedene Wertfilterarten sind UND-verknüpft. Davon ausdrücklich getrennt ist `--filter`: Alle wiederholten SRX-Ausdrücke sind untereinander und mit dem Ergebnis der Wertfilter UND-verknüpft. Eine nicht angegebene Filtergruppe trägt `true` bei; doppelt angegebene gleiche Werte ändern das Ergebnis nicht. `--evaluation`, `--select`, `--sort`, `--offset` und `--limit` sind keine Wertfiltergruppen. `--release` bedeutet Mitgliedschaft im geschlossenen Release-Scope nach Kapitel 10.8. Volltext wird durch Unicode-NFC und Unicode-Casefold locale-unabhängig normalisiert und über `title`, die typspezifische normative Hauptaussage, `description`, `term` und Dokument-Prose ausgewertet.

Ohne `--sort` gilt aufsteigend `(artifact_type, id)`. Ein Sortierschlüssel ist einer aus `artifact_type`, `id`, `title`, `maturity`, `revision`, `owner`, `implementation_status`, `verification_plan_status`, `verification_result` oder ein JSON Pointer, der je Item auf einen skalaren Wert oder einen fehlenden Wert auflöst. Objekt- oder Arraywerte als Sortierwert sind ein Nutzungsfehler. Aufsteigend gilt die Typreihenfolge `missing < null < boolean < number < string`; Zahlen werden numerisch, Strings nach Unicode-NFC als UTF-8-Bytes und Booleans `false < true` verglichen. `desc` kehrt die Reihenfolge des jeweiligen Schlüssels um. Die Artefakt-ID bleibt unabhängig von weiteren Schlüsseln der letzte aufsteigende Tie-Breaker.

`offset` und `limit` sind nichtnegative Ganzzahlen. Ohne `--offset` gilt 0. Die eingebauten effektiven Defaults sind `resource_limits.query_default_limit=100` und `resource_limits.query_result_count=10000`; Projektkonfiguration und Profile dürfen den fachlichen Paginationdefault ausdrücklich festlegen; der historische Wert `query_result_count` wird nur als nicht normative Betriebsvorgabe behandelt. Ohne `--limit` gilt der effektive Wert von `query_default_limit`. `query_result_count` ist ausschließlich ein weiches Spooling-/Chargenziel und begrenzt nicht das ausdrücklich angeforderte `--limit`; größere Resultate werden vollständig extern geliefert beziehungsweise fortgesetzt. `limit=0` ist zulässig und liefert keine Items. `total` ist die Treffermenge nach Filtern und vor Pagination, `returned` die tatsächliche Anzahl ausgegebener Items und `truncated` genau dann `true`, wenn `offset + returned < total`.

Ohne `--select` besitzt jedes Item mindestens `id`, `artifact_type`, `title`, `revision` und `maturity`; die für den Typ vorhandenen Felder `implementation_status` und `verification_plan_status` sowie das berechnete `verification_result` werden ergänzt. Mit `--select` besitzt jedes Item `id`, `artifact_type` und ein Objekt `values`, dessen Schlüssel die angeforderten JSON Pointer in CLI-Reihenfolge sind; ein fehlender Wert wird als `{ "state": "missing" }` ausgegeben. Das JSON-Result enthält exakt die Pflichtfelder `items`, `total`, `offset`, `limit`, `returned` und `truncated`; zusätzliche versionierte Felder sind nur in einer kompatiblen Minor-Version des Ergebnisformats zulässig.

Ein in einem Scope Descriptor gebundenes Query-Objekt enthält die normalisierten Filter, Projektionen, Sortierschlüssel, `evaluation` nach 10.5.4 sowie materialisierte Werte für `offset` und `limit`; Dateipfade zu SRX-Ausdrücken werden durch deren kanonischen Inhalt und Hash ersetzt.

### 11.7 Verbindliche Befehlsklassen

Jeder in Kapitel 11.2 aufgeführte Befehl gehört exakt einer der folgenden Klassen. Kurzaliase erben ohne Ausnahme die Klasse ihres Zielbefehls.

| Klasse | Exakt zugeordnete Befehle | Schreib-/Sicherheitsvertrag |
|---|---|---|
| `normative_write` | `change apply`; `format` ohne `--check`; `artifact create`, `artifact update`; `relation add`, `relation remove`, `relation review`; `lifecycle transition`; `document create`; `section add`, `section move`, `section remove`; `block add`, `block update`, `block remove`; `view create`; `evidence record`, `evidence import`; `baseline create`; `proposal create`, `proposal change`, `proposal review start`, `proposal review`, `proposal apply`; `import apply`; `migrate apply`; `merge apply` | Change Plan, exklusiver Projektwriter-Lock, Journal und Request-Receipt; `--dry-run`; Request-ID für AI/CI Pflicht und für Human/Tool optional |
| `plan_output` | `import plan`; `migrate plan`; `merge plan`; `merge resolve` | verändert keine normative Projektressource; schreibt ein ausdrücklich angegebenes Plan-Ziel atomar oder gibt den Plan auf stdout aus; kein Projektwriter-Lock und kein Request-Receipt |
| `generated_output` | `analyzer request`, `analyzer run`, `analyzer import`; `document render`; `view render`; `diagram trace`, `diagram architecture`, `diagram release`; `render`; `export reqif`, `export reqifz`, `export csv`, `export ndjson`; `bundle create` außer der unten benannten Hinexportvariante | erzeugt ausschließlich atomare Ausgaben außerhalb des kanonischen Modells oder unter `generated/`; kein Change Plan, Projektwriter-Lock, Request-Receipt oder `.specroad/`-Seiteneffekt |
| `read_only` | `language list`, `language show`, `analyzer list`, `analyzer describe`, `analyzer show`, `analyzer evaluate`; `config show`; `profile explain`; `format --check`; `artifact show`; `relation status`; `document show`; `view show`; `validate`; `lint`; `query`; `trace`; `why`; `impact`; `diff`; `coverage`; `roadmap explain`; `release readiness`; `baseline show`, `baseline verify`, `baseline compare`; `proposal show`, `proposal validate`, `proposal check`; `merge conflicts`; `migrate verify`; `configuration evaluate`; `bundle verify`; `recover status`; `lock status`; `capabilities`; `schema list`, `schema show`; `command describe`; `project inspect`; `environment check`; `version`; `work status`; `work prompt` | verändert weder Projektdateien noch `.specroad/`; funktioniert ohne Schreibberechtigung, sofern keine ausdrücklich externe Ausgabedatei angefordert wird |
| `local_operational` | `lock recover`; explizite Cache- oder Receipt-Inspektions-/Bereinigungsbefehle | verändert ausschließlich `.specroad/`-Betriebsdaten oder Recovery-Auditdaten unter einem Betriebslock und niemals normative Projektressourcen |
| `recovery_write` | `recover run`, `recover discard`, `recover restore` | verwendet den spezialisierten Recovery-Lock und den Zustandsvertrag aus 10.6–10.7; darf ausschließlich den im Journal gebundenen Basis- oder Zielzustand beziehungsweise den vollständig qualifizierten Restore-Zielstand nach 10.7.1 veröffentlichen; erzeugt immer Recovery-Audit |
| `root_creation` | `init`; `bundle extract` | verwendet ein Bootstrap-Journal im Ziel und veröffentlicht die geplante Root-Struktur vollständig oder gar nicht; ist kein Change Plan eines vorhandenen SpecRoad-Projekts |
| `transport_operational` | `bundle create --profile ai-runtime --direction outbound` | ausschließlich die nachfolgend benannten PatchHarbor-Betriebswirkungen und externe Ausgabe; keine normative Projektmutation, kein SpecRoad-Receipt und keine Git-Historienänderung |

Die Work-Steuerbefehle werden ergänzend exakt so klassifiziert: `work export` ist `generated_output`; `work restore` ist `work_operational`; `work cancel` ist `work_operational`; `work resume` ist `work_operational` mit der im gespeicherten Auftrag ausdrücklich gebundenen inneren Befehlsklasse. Die Klasse `work_operational` verändert ausschließlich den angegebenen externen Work-Root; eine normative Wirkung ist nur durch den gesondert autorisierten inneren `normative_write` oder `recovery_write` zulässig. Verschachtelte oder unbekannte Command-IDs werden nicht ausgeführt.

Die Laufzeitsteuerung darf für einen aufteilbaren Befehl einen externen Work-Root nach Anhang P erzeugen. Dies ändert niemals die Schreibrechte seiner Fachklasse: `read_only`, `plan_output`, `generated_output` und Dry-Runs verändern weiterhin weder kanonische Projektdateien noch `.specroad/`. Externe Snapshot-/Checkpointdateien sind offengelegte betriebliche Ausgaben, keine stillen Projektwrites. Bootstrap- und reine Metadatendiagnosen erzeugen keine Work-Daten. `command describe` nennt diese externen Laufzeitwirkungen ausdrücklich.

Für `init` darf das Ziel fehlen oder ein vorhandenes Repositoryverzeichnis sein. Vor dem ersten Write muss der Befehl für jeden geplanten Zielpfad nachweisen, dass keine Datei, kein Symlink und kein nichtleeres zu ersetzendes Verzeichnis existiert; bereits vorhandene, nicht von SpecRoad beanspruchte Repositorydateien bleiben unangetastet. `init` erzeugt insbesondere `specroad.json` und genau ein Primärspezifikationsdokument. Bei Fehler werden ausschließlich die durch denselben Bootstrap-Lauf neu erzeugten Pfade entfernt.

Für `bundle extract` muss das Ziel fehlen oder leer sein. Es wird erst nach vollständiger Bundle-Verifikation geschrieben; vorhandene Zielinhalte werden niemals überschrieben. Ein unterbrochener Root-Erzeugungslauf wird vor einer Wiederholung anhand seines Bootstrap-Journals zurückgerollt oder vollständig abgeschlossen.

Für `ai-runtime` ist `bundle create --direction return` wie das gewöhnliche
`bundle create` ein `generated_output`; `bundle verify` bleibt `read_only` und
`bundle extract` bleibt `root_creation`. Genau die ausdrücklich Git-spezifische
Variante `bundle create --profile ai-runtime --direction outbound` erhält die
zusätzliche Klasse `transport_operational`: Sie darf über die öffentliche API
PatchHarbor-Betriebsdaten des bereits registrierten Repositorys sowie das
ausdrücklich gewählte Ausgabeverzeichnis verändern. Normative Projektdateien,
SpecRoad-Betriebsdaten unter `.specroad/`, Git-Historie und Index bleiben
unverändert. Registrierung, Konfigurationswechsel, Apply, Commit und Push sind
keine impliziten Exportwirkungen. Die tatsächlichen PatchHarbor-Betriebspfade
und Wartungswirkungen werden vorab ausgewiesen; eine Konfiguration mit darüber
hinausgehenden Wirkungen wird verweigert. Öffnen veröffentlicht getrennte
Runtime-, Referenz- und Projektverzeichnisse unter dem neuen Zielroot; ein
Rückpaket darf darüber nicht als Projekt entpackt oder angewendet werden.
`command describe` weist die Varianten mit jeweils genau einer Klasse aus.

`command describe` weist Klasse, Optionen, Eingaben, Ausgaben, Exit Codes, Seiteneffekte, Lockart, JSON-Schema sowie Preflightprofil und Budgetpolicy aus Anhang N/O maschinenlesbar aus. Ein Preflight verändert die Befehlsklasse nicht; besonders erzeugt ein Read-only-Aufruf keine automatische Recovery oder Cachepflege. Eine Funktion, die in einer späteren kompatiblen Version neu hinzukommt, darf erst veröffentlicht werden, wenn ihr Command Contract genau eine dieser Klassen festlegt.

`language list` zeigt die mitgelieferten, getesteten Sprach-/Tag-/Capabilityfälle, nicht eine abschließende Erlaubnisliste. `language show <TAG>` validiert Tag und Registrybezug und zeigt deklarative Paket- sowie Detektorcapabilities ohne Modellinitialisierung. Der vollständige generische Analyzer-CLI-Vertrag einschließlich Zusatzruntime, Datei-Outputs und unveränderter Originalberichte steht in Anhang T.5; alle Analyzerbefehle sind in der Tabelle 11.7 ausdrücklich klassifiziert.

### 11.8 Exit Codes

| Code | Klasse | Bedeutung |
|---:|---|---|
| 0 | Erfolg | angeforderte Operation und ihre befehlsspezifischen Gates erfolgreich; ein korrekt gespeichertes negatives Relationsreview ist nach 11.13 kein bestandener fachlicher Nachweis |
| 1 | Prüf-/Policy-Fehlschlag | Diagnose am Schwellwert, Readiness nicht erfüllt oder `--fail-on-change` |
| 2 | Nutzung/Konfiguration | ungültige CLI-Nutzung, Profilkonflikt oder Konfiguration |
| 3 | Ungültiges Eingabemodell | JSON-, Schema- oder grundlegender Modellfehler |
| 4 | Interner Fehler | unerwarteter SpecRoad-Fehler |
| 5 | I/O/Umgebung/Recovery | Tatsächlicher Dateisystem-, Git-, Hostressourcen- oder Recoveryblocker; bloße weiche Budgetüberschreitung ist kein Fehler |
| 6 | Konflikt | stale Basis, Merge-, Import-, Request-ID-, External-Identity- oder Scope-Konflikt |
| 7 | Sicherheitsverweigerung | Pfad-, Fremdcode-, Netzwerk-, Actor-, Partial-Bundle-Write- oder harte Sicherheits-/Formatpolicy-Verletzung |
| 8 | Fortsetzung erforderlich | Gültiger Checkpoint vorhanden; Gesamtauftrag noch nicht vollständig; nächster Aufruf nach Anhang P |

### 11.9 Direkte Authoring-Beispiele

```bash
python3 -m specroad artifact update SR-REQ-7K3M9W2D8R4P0ABCDEF1234567 \
  --set /priority='"high"' \
  --expected-revision 3 \
  --actor-type human \
  --actor-id christian \
  --request-id update-priority-20260901 \
  --dry-run \
  --format json
```

```bash
python3 -m specroad relation add SR-REQ-7K3M9W2D8R4P0ABCDEF1234567 \
  --type verified_by \
  --target SR-VER-1AB2CD3EF4GH5JK6MNP7QRSTVW \
  --actor-type human \
  --actor-id christian \
  --request-id add-verification-20260901
```

Die Beispiele sind informativ; maßgeblich sind die Requirements, Tabellen und maschinenlesbaren Command Contracts.

### 11.10 Proposal-Authoring- und Freigabevertrag

Schreibende Befehle dieser Gruppe sind `normative_write`, unterstützen `--dry-run` und verlangen Akteursangaben. Für `ai` und `ci` ist eine stabile Request-ID erforderlich. `<PROP>` ist entweder eine im Projekt vorhandene Proposal-ID oder ein ausdrücklich angegebener verwalteter Proposal-Dateipfad; beide werden vor der Operation auf dieselbe ID aufgelöst. Externe Dateien sind nur für lesende Prüfung zulässig und erteilen keine Schreibrechte. `--expected-revision` bindet stets die Artefaktrevision.

| Befehl | Verbindliche Syntax und Vorbedingungen | Ergebnis |
|---|---|---|
| Create | `proposal create --title <TEXT> --rationale <TEXT> [--base-scope <FILE>]` | Neue ID, `revision=1`, `content_revision=1`, gültiger Inhaltshash, `draft`, leere Change-/Kontroll-/Reviewlisten; Einzige zulässige Basis ist der vollständige unkonfigurierte geschlossene `specification`-Scope nach 10.8.1; unzulässige `--base-scope`-Auswahl wird vor jedem Write abgewiesen. |
| Change add | `proposal change add <PROP> --expected-revision <N> --operation <FILE\|-> [--position <N>]` | Neue stabile Change-ID. Ohne Position: anhängen. Mit Position: Einfügen vor dem bisherigen Element an diesem Index. Zulässig ist `0 ≤ N ≤ Länge`; `N=Länge` hängt an. |
| Change update | `proposal change update <PROP> <CHANGE-ID> --expected-revision <N> --operation <FILE\|->` | Genau die bezeichnete Operation ersetzen, Change-ID erhalten. |
| Change remove | `proposal change remove <PROP> <CHANGE-ID> --expected-revision <N>` | Genau die bezeichnete Operation entfernen. |
| Change move | `proposal change move <PROP> <CHANGE-ID> --expected-revision <N> --position <N>` | Element zuerst entfernen, dann am angegebenen Index der Restliste wieder einfügen; zulässig bis einschließlich Restlistenlänge. |
| Show | `proposal show <PROP>` | Read-only Ausgabe von Inhalt, beiden Revisionen, Inhaltshash, Basis, Plan, Kontrollhistorie und Review-Wirksamkeit. |
| Validate | `proposal validate <PROP>` | Read-only Proposal-/Basisprüfung; kein persistierter Statuswechsel. |
| Check | `proposal check <PROP>` | Read-only vollständiger isolierter Check; keine fachliche Freigabe. |
| Review starten | `proposal review start <PROP> --expected-revision <N>` | Erforderliche Prüfungen vollständig ausführen und erfolgreiche Kontrollfolge nach 10.3 atomar bis `in_review` schreiben. Inhalt bleibt unverändert. |
| Entscheiden | `proposal review <PROP> --expected-revision <N> --decision approved\|rejected` | Entscheidung mit Inhaltsbindung speichern; `approved` zählt nur von `human`. `in_review` ist Voraussetzung einer Freigabe. Ablehnung/Widerruf folgt 10.3. |
| Apply | `proposal apply <PROP> --expected-revision <N>` | Aktuelle Inhaltsfreigabe, erwartete Basis und Plan prüfen; Zielmodell, Proposal-Endstatus und Receipt gemeinsam veröffentlichen. |

`--operation -` liest stdin. Ohne ausdrücklichen stdin-Marker wartet kein Befehl auf stdin. Eine fehlende Pflichtoption ist Code 2, ungültiges JSON/Schema Code 3, stale Revision/Basis Code 6, unzulässiger Actor Code 7 und tatsächlicher I/O-Fehler Code 5. Ein noch nicht vollständiger vorbereitender Check liefert Code 8 und verändert das Proposal noch nicht.

Das schreibende JSON-Result enthält mindestens `proposal_id`, `revision`, `content_revision`, `content_sha256`, `proposal_status`, `maturity`, `base_model_root_sha256`, `change_plan_sha256`, `changed_change_ids` und `review_validity`. Für Kontrollwrites ist `changed_change_ids=[]`. Reviews und Kontrollereignisse nennen Akteur, UTC-Zeit, Inhaltsbindung und Prüfergebnis-Hash.

Die KI darf Proposals erzeugen und authoren, Checks ausführen, das Review starten und ein bereits menschlich freigegebenes Proposal anwenden. Diese ausdrücklich begrenzten Fachbefehle sind Ausnahmen vom Verbot direkter KI-Änderung fachlicher Standardartefakte. Sie erlauben weder das Fälschen von Human-Reviews noch die Umdeklaration der KI zum Menschen. Die vorhandene Single-User-Akteursdeklaration ist keine kryptografische Authentifizierung; ein externer Agent darf eine tatsächlich vom Nutzer erklärte Freigabe protokollieren, aber nicht selbst erteilen.

**Normativer Erfolgsvektor:** Create ergibt `(revision=1, content_revision=1, draft)`. Ein Change add ergibt `(2,2,draft)`. Validate und Check verändern diese Werte nicht. Review start ergibt `(3,2,in_review)`. Menschliches approved-Review ergibt `(4,2,approved)`. Apply ergibt `(5,2,applied)`, denselben freigegebenen Inhaltshash und genau ein fachliches Erfolgsreceipt. Eine Inhaltsänderung statt Apply ergibt `(5,3,draft)` und keine wirksame Freigabe. Ein Retry mit derselben Request-ID erzeugt keine weitere Revision.

---

### 11.11 Runtime- und Ressourcenverträge

`environment check` ist eine betriebliche Momentaufnahme nach Anhang N.4, keine zusätzliche Vollvalidierung. Jeder reguläre Befehl besitzt den dort definierten kleinen automatischen Preflight auch ohne vorherigen `environment check`.

```bash
python3 specroad.pyz environment check --format json
python3 specroad.pyz environment check --project ./projekt \
  --for-command validate --format json
python3 specroad.pyz validate --project ./projekt \
  --resource-profile constrained --format json
python3 specroad.pyz validate --project ./projekt \
  --resource-profile standard --metrics --format json
```

Die Beispiele sind nicht normativ. `constrained` ist der betriebliche Default; `standard` erhöht Budgets und nicht die fachliche Prüftiefe. Keine Ressourcenoption darf eine erforderliche fachliche Prüfung, einen menschlichen Review oder den Transaktionsvertrag umgehen.

---

### 11.12 Arbeitssteuerung und Fortsetzung

Die ursprünglichen Fachbefehle bleiben der Einstieg. Der erste große Aufruf zerlegt sich bei Bedarf automatisch; `--work-dir` macht den externen Speicherort explizit. Die folgende zusätzliche Gruppe ist Bestandteil des CLI-Core:

| Befehl | Verbindlicher Vertrag |
|---|---|
| `work status <DIR>` | Nur Manifest und letzte gültige Checkpointgeneration prüfen; Zustand, Eingangsbindungen, Fortschritt, notwendige nächste Aktion und bekannte tatsächliche Blocker ausgeben. Keine Facharbeit und kein Projektwrite. |
| `work resume <DIR> [--project <PATH>]` | Genau einen bevorzugt begrenzten nächsten Arbeitsschritt des gebundenen Auftrags ausführen; `--project` nur als neue Rootlokalisierung, nicht als neue fachliche Basis. Dieselbe Aufgaben-/Actor-/Requestbindung bleibt erhalten. |
| `work prompt <DIR> [--max-prompt-chars <N>]` | Geprüften Fortsetzungstext oder JSON nach P.8 ausgeben; keine Nachricht senden und keine neue Arbeit starten. |
| `work export <DIR> --output <FILE>` | Selbstenthaltenes Arbeitspaket nach P.7 erstellen; optional nötige geordnete Teilarchive werden vollständig im Ausgabemanifest aufgeführt. Kein Projektvollbundle vortäuschen. |
| `work restore <FILE> --output <DIR>` | Paket und alle nötigen Teile prüfen, ausschließlich in fehlendes/leeres externes Work-Ziel extrahieren. Keine normativen Projektdateien überschreiben. |
| `work cancel <DIR> --reason <TEXT>` | Ohne aktive normative Transaktion explizit beenden; Kontrollbeleg erhalten. Kein Verwerfen notwendiger Recoverydaten. |

`work resume` akzeptiert die Ressourcenoptionen von Kapitel 11.3; sie verändern den fachlichen Operationshash nicht. Die übrigen Befehle nennen anwendbare Ausgabe-/Ressourcenoptionen in `command describe`. CLI- oder Profileingaben, die den Fachauftrag, Actor, Plan oder Freigabewirkung verändern würden, sind kein Resume, sondern ein neuer ausdrücklich zu bindender Auftrag. `work resume` kann keine andere Command-ID oder Shellzeichenkette ausführen. Für den inneren Befehl `recover.restore` konkretisiert 10.7.7 die passive Originalbindung und die getrennte aktuelle Recoveryautorisierung; dessen gebundene Herkunfts-/Projektroots dürfen durch `--project` nicht umgeschrieben werden.

```bash
python3 specroad.pyz validate --project ./projekt \
  --work-dir ./arbeit --resource-profile constrained --format json
python3 specroad.pyz work status ./arbeit --format json
python3 specroad.pyz work resume ./arbeit --project ./projekt --format json
python3 specroad.pyz work prompt ./arbeit --format pretty
python3 specroad.pyz work export ./arbeit --output ./arbeit.specroad-work.zip
```

Die Beispiele beschreiben mögliche aufeinanderfolgende Aufrufe, keinen automatisch laufenden Prozess. `work prompt`/`export` sind nur notwendig, solange noch Arbeit offen ist. Ein bereits abgeschlossenes `work resume` liefert ohne erneutes Rechnen das vollständige gespeicherte Resultat. Ein normaler Promptwechsel verändert weder Daten noch Request-ID.


---

### 11.13 Relationsreview als atomarer Fachvorgang

`relation review <SOURCE-ID> --relation-id <RELATION-ID> --decision confirmed|rejected` ist ein `normative_write`, kein Validierungskommando. Pflicht sind ein menschlicher Reviewer, eine nichtleere `--reason <TEXT>` (als gebundener Operationsgrund im Plan/Audit gespeichert) und eine erwartete Quellrevision oder ein erwarteter Quellhash; `--input` darf dieselben Angaben strukturiert liefern. Der Aufruf bindet den gesamten konsistenten Projektstand, Relations-ID/-inhalt und beide Endpunkt-Kontexthashes nach Anhang J. Eine strukturell ungültige Relation wird nicht durch ein Review legitimiert. Fehlender Endpunkt, ungültiger Typ, Pfadverletzung, unzulässiger Akteur oder stale Basis werden vor jedem normativen Write abgewiesen.

**Ergebnis und Freigabefolgen:** Der Planner erzeugt ein unveränderbares `relation_review` im Zustand `recorded`/`approved`, Revision 1. `approved` bezeichnet hier die Aufnahme des menschlichen Nachweises, nicht eine positive Entscheidung. Der neue Nachweis trägt `confirmed` oder `rejected`. Sein gebundener `planned_at` ist mindestens eine Mikrosekunde nach dem größten Zeitstempel eines bereits vorhandenen passenden Reviews; reguläre Planmetadaten folgen unverändert Anhang K. Damit ist eine bewusst neue Entscheidung für dieselbe Bindung die jüngste. Importierte Historien behalten die Auswahlregel J.3.

Der Planner berechnet den vollständigen Relationsstatus nach Einfügung des neuen Reviews. Er ermittelt die Menge aller bislang `approved` Standardartefakte, deren Approval-Gate nach den aktiven Profilen gerade wegen der geänderten Relation nicht mehr erfüllt ist. Diese Menge enthält insbesondere jedes Requirement, für das die Relation nach SR-REQ-0283 verpflichtend ist; berechnete inverse Sichten zählen gemäß derselben Profilpflichten. Jedes betroffene Artefakt wird im **selben** Plan von `approved` nach `proposed` gesetzt. Seine Fachfelder bleiben unverändert; seine Revision steigt nach Anhang K genau einmal. Der Auditdatensatz bindet betroffene ID, Basis-/Zielrevision, alten/neuen Reifegrad, Relation-ID, neue Review-ID und den Grund `mandatory_relation_not_current`.

Eine `confirmed`-Entscheidung stellt den Relationsstatus `current` her, aber erteilt **keine** automatische Artefaktfreigabe. Ein bereits `draft`, `proposed`, `in_review`, `rejected`, `superseded` oder `retired` vorliegendes Standardartefakt erhält allein durch die Review-Aufnahme keine neue Revision oder Reifegradänderung. Ein negatives Review einer optionalen Relation entzieht eine Freigabe nur, wenn das aktive Approval-Gate diese Relation tatsächlich voraussetzt. Immutable Evidence, Baselines, frühere Reviews und abgeschlossene Proposals bleiben bytegetreu erhalten. Historische Baselines bilden weiterhin ihren eigenen Snapshot ab.

**Keine zirkuläre Bindung:** Review-Erzeugung und Freigaberücknahmen werden vor Hashbildung vollständig geplant. Die allein geänderten Lifecycle-/Auditfelder sind aus `relation_context_hash-v1` ausgeschlossen. Das neue Review bleibt daher nach den gekoppelten Herabstufungen aktuell. Es ist unzulässig, in demselben Relationsreview-Plan außerdem Relationsinhalt, Endpunkt-Fachinhalt oder eine erneute `approved`-Transition der betroffenen Artefakte zu verändern. Eine solche Kombination wird vor Write mit Code 2 bei direkter CLI-Nutzung beziehungsweise Code 3 beim gespeicherten Plan abgewiesen.

**Vollständige Prüfung mit getrennten Gates:** Der Endstand wird vollständig validiert. Ein strukturell korrekt gespeichertes negatives Review erzeugt weiterhin `SRV027`, Schwere `error`, Zusatzgrund `current_review_rejected` und Kategorie `review_outcome`. Es wird nicht auf `warning` herabgestuft. Strukturelles `invalid` verwendet dieselbe Diagnosefamilie mit strukturellem Zusatzgrund und ist nie ausgenommen. Die in SR-REQ-0275 gespeicherten vollständigen Endpunkthashes und Revisionen bezeichnen den vor der gekoppelten Rücknahme beobachteten Stand und bleiben Auditdaten; die Gültigkeit verwendet ausschließlich die Kontexthashes nach Anhang J. Für genau den Review-Aufnahmevorgang sind korrekt gebundene `review_outcome`-Diagnosen fachliche Ergebnisdaten und kein Write-Gate. Das gilt auch für bereits gespeicherte gleichartige negative Reviews anderer Relationen, damit eine Reparatur oder weitere wahrheitsgemäße Ablehnung möglich bleibt. Jede andere strukturelle, Lifecycle-, Hash-, Scope-, Referenz-, Actor- oder Sicherheitsverletzung blockiert die Veröffentlichung; andere Qualitätsdiagnosen wirken gemäß der wirksamen Policy. Es darf kein `approved` Artefakt mit einer durch diesen Vorgang verletzten Pflichtrelationsinvariante verbleiben.

Diese eng begrenzte Ergebnisausnahme gilt nur für den typisierten Review-Aufnahmeplan einschließlich seiner Freigaberücknahmen. Sie ist kein frei setzbares `ignore_errors`, keine Erlaubnis zu anderen fachlichen Änderungen und keine Ausnahme für `validate`, `lint`, `release readiness`, eine neue Artefaktfreigabe oder `baseline create`. Diese Befehle behandeln ein aktuelles negatives Review weiterhin als Fehler. `--strict` oder `--fail-on` verändern weder eine menschliche Reviewentscheidung noch die Kategorie `review_outcome`; sie wirken für alle übrigen anwendbaren Gates. Im späteren Review der fachlichen Anforderung müssen wieder sämtliche Approval-Bedingungen erfüllt sein.

**Write-, Diagnose- und Exit-Ergebnis:** Nach erfolgreicher Speicherung ist der Prozesscode 0 und `status=success`, weil der angeforderte Review-Vorgang vollständig erledigt ist. Der Fachpayload enthält mindestens `review_id`, `decision`, `relation_status`, `assessment_status` (`passed` bei confirmed, `failed` bei rejected), `write_state=committed`, `approval_withdrawals`, Planhash, Zielmodellwurzel und Receipt. Sämtliche Diagnosen bleiben im Envelope oder seiner vollständigen Ergebnisdatei sichtbar. `assessment_status=failed` ist kein `verification_result` und niemals ein bestandenes Produktgate. Ein nachfolgendes `validate` liefert beim fortbestehenden negativen Review Code 1 und `status=failed`. Ein Dry-Run liefert `write_state=not_committed`, denselben Plan und dieselben voraussichtlichen Folgen; `--fail-on-change` wirkt unverändert. Bei tatsächlicher Ablehnung durch ein Write-Gate wird Code 1–7 mit `write_state=not_committed` geliefert; Code 8 bedeutet wie bisher noch nicht abgeschlossene Vorbereitung.

**Autorität, Proposal und Idempotenz:** Nur der menschliche Review-Fachbefehl darf die Spezialoperation `relation_review_record` planen. Deren Payload bindet Reviewer, Entscheidung, Grund, Relation, Kontexthashes und die vollständige Rücknahmemenge. Ein generisches `artifact create` oder ein freier JSON-Patch darf sie nicht ersetzen. Mit `--as-proposal` wird nur der vollständige, bereits menschlich begründete Plan vorgeschlagen; keine Ablehnung oder Herabstufung wird vor Apply veröffentlicht. Eine KI kann keinen menschlichen Relationsreview erzeugen. Sie darf einen bereits entsprechend freigegebenen und unverändert gebundenen Plan im bestehenden Proposal-Apply-Vertrag ausführen. Planprüfung, gespeicherte Freigabe und Apply verwenden denselben gekoppelten Endstand. Ein Writer, der unvollständige oder zusätzliche Operationen erkennt, weist den Plan zurück statt sie stillschweigend nachzutragen.

Review, Rücknahmen und Receipt bilden eine Transaktion. Bei gleichem Request und identischer Basisbindung wird nach verlorener Ausgabe dasselbe Receipt mit derselben Review-ID und denselben Artefaktrevisionen zurückgegeben, kein zweiter Nachweis. Crash-Recovery stellt entweder den gesamten Vorzustand oder den gesamten neuen Review-/Freigabezustand her. Aufteilung über Prompts betrifft nur die Vorbereitung, nicht die atomare Veröffentlichung.

**Normativer CLI-Sollablauf:** Ein Requirement R steht mit gültig bestätigter Pflichtrelation L auf `approved`, Revision 4. `relation review R --relation-id L --decision rejected --reason ...` plant die neue Review-ID und R Revision 5/`proposed`. Nach Commit: Code 0, Review unveränderbar, L=`invalid`, SRV027/error sichtbar; `validate` danach Code 1. Eine spätere aktuelle Bestätigung erzeugt eine andere Review-ID, L=`current`; R bleibt Revision 5/`proposed`. Erst explizites `lifecycle transition R --to in_review` und danach ein erfolgreiches `--to approved` führen zu Revision 6 und 7. Bei Ausgang R=`draft`/Revision 4 speichert dieselbe Ablehnung nur das Review; R bleibt `draft`/Revision 4. Die IDs R/L dienen hier nur als symbolische Bezeichnungen, nicht als gültige Eingabesyntax.

---

## 12. Normative Produktanforderungen

Dieser Katalog enthält **742** normative Produktanforderungen. Alle Anforderungen sind für das Zielrelease 0.2.0 verpflichtend, sofern ihr Wortlaut keine Bedingung nennt. Bis zur Freigabe erben sie `maturity = proposed`, `priority = mandatory` und `target_release = SpecRoad Single-Repository Workbench 0.2.0`.

Die Spalte `Quelle` verweist auf Stakeholder-Bedarfe; `Verifikation` nennt den primären Verification Contract. Querschnittsanforderungen dürfen zusätzlich durch andere Verträge geprüft werden. Eine Anforderung ist erst bestanden, wenn ihr primärer Vertrag und alle für sie anwendbaren Querschnittsgates bestehen.

### 12.1 Projektinitialisierung und Konfiguration

Diese Anforderungen definieren Projektroot, Grundstruktur und effektive Konfiguration.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0001 | Der Befehl `specroad init [PATH]` MUSS in `PATH` oder im aktuellen Verzeichnis ein neues SpecRoad-Projekt mit der in dieser Spezifikation definierten Mindeststruktur einschließlich genau eines Primärspezifikationsdokuments erzeugen. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0001 | SR-TC-0001 |
| SR-REQ-0002 | `specroad init` DARF NICHT eine bereits vorhandene normative Datei überschreiben. | SR-NEED-0001, SR-NEED-0011 | SR-VER-0001 | SR-TC-0002 |
| SR-REQ-0003 | `specroad init` MUSS bei einem Fehler entweder die vollständige gültige Grundstruktur oder den unveränderten Ausgangszustand hinterlassen. | SR-NEED-0001, SR-NEED-0011 | SR-VER-0001 | SR-TC-0003 |
| SR-REQ-0004 | Jedes SpecRoad-Projekt MUSS im Projektroot genau eine Konfigurationsdatei `specroad.json` besitzen. | SR-NEED-0001, SR-NEED-0012 | SR-VER-0001 | SR-TC-0004 |
| SR-REQ-0005 | SpecRoad MUSS ohne explizite Projektangabe vom aktuellen Verzeichnis aufwärts die nächstgelegene `specroad.json` als Projektroot verwenden. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0001 | SR-TC-0005 |
| SR-REQ-0006 | Die globale Option `--project <PATH>` MUSS die automatische Projekterkennung überschreiben. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0001 | SR-TC-0006 |
| SR-REQ-0007 | `specroad.json` MUSS mindestens `schema_version`, `project_id`, `project_name`, `id_prefix`, `default_locale`, `managed_paths`, `profiles`, `generated_path` und `validation_policy` enthalten. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0001 | SR-TC-0007 |
| SR-REQ-0008 | SpecRoad MUSS Projektpräfixe gegen das Muster `[A-Z][A-Z0-9]{1,7}` validieren. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0001 | SR-TC-0008 |
| SR-REQ-0009 | `specroad config show` MUSS die effektive Konfiguration einschließlich Defaultwerten und der Herkunft jedes überschriebenen Wertes ausgeben. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0001 | SR-TC-0009 |
| SR-REQ-0010 | `specroad format` MUSS ausschließlich die nach Kapitel 10.17 formatierbaren aktuellen JSON-Ressourcen in die definierte menschenlesbare Normalform überführen. | SR-NEED-0001, SR-NEED-0004 | SR-VER-0001 | SR-TC-0010 |

### 12.2 Kanonisches Modell und Speicherung

Normative Daten liegen im typisierten JSON-Modell; andere Darstellungen sind abgeleitet oder referenzierte Payloads.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0011 | SpecRoad MUSS das aktuelle normative semantische Modell ausschließlich aus `specroad.json`, den dafür vorgesehenen JSON-Dateien unter `spec/`, `profiles/`, `rules/` und `mappings/` sowie den von diesen Ressourcen referenzierten Payloads unter `attachments/` und `archive/objects/` laden. | SR-NEED-0001, SR-NEED-0012, SR-NEED-0014 | SR-VER-0002 | SR-TC-0011 |
| SR-REQ-0012 | Jede normative Artefaktdatei MUSS genau ein Artefakt als JSON-Objekt enthalten. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0002 | SR-TC-0012 |
| SR-REQ-0013 | Normative und generierte Textdateien MÜSSEN als UTF-8 gespeichert werden und für interne JSON-, Markdown-, HTML-, SARIF- und NDJSON-Dateien LF sowie für einen ausdrücklich referenzierten Austauschstandard dessen festgelegtes Zeilenende verwenden. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0014 | SR-VER-0002 | SR-TC-0013 |
| SR-REQ-0014 | Jeder Artefakttyp MUSS durch ein versioniertes JSON Schema beschrieben sein. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0002 | SR-TC-0014 |
| SR-REQ-0015 | Jede normative JSON-Datei MUSS eine unterstützte `schema_version` enthalten, wobei unveränderbare Legacy-Ressourcen ausdrücklich über das versionierte Manifest und die eingebauten Leser aus Anhang Q unterstützt werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0002 | SR-TC-0015 |
| SR-REQ-0016 | SpecRoad MUSS eine nicht unterstützte `schema_version` ablehnen und die höchste unterstützte Version in der Diagnose nennen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0002 | SR-TC-0016 |
| SR-REQ-0017 | Die Kernschemas MÜSSEN unbekannte Top-Level-Felder ablehnen. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0002 | SR-TC-0017 |
| SR-REQ-0018 | Erweiterungsdaten MÜSSEN ausschließlich im Objekt `extensions` unter einem namespaced Schlüssel der Form `<anbieter>.<name>` gespeichert werden. | SR-NEED-0012, SR-NEED-0008 | SR-VER-0002 | SR-TC-0018 |
| SR-REQ-0019 | SpecRoad MUSS unbekannte, schema-gültige Inhalte im Feld `extensions` beim Lesen, Formatieren, Rendern und Schreiben verlustfrei erhalten. | SR-NEED-0012, SR-NEED-0009 | SR-VER-0002 | SR-TC-0019 |
| SR-REQ-0020 | SpecRoad MUSS für Hashbildung JSON Canonicalization Scheme verwenden und den resultierenden Byte-String mit SHA-256 hashen. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0002 | SR-TC-0020 |
| SR-REQ-0021 | Die menschenlesbare JSON-Normalform MUSS zwei Leerzeichen Einrückung, eine abschließende Newline und eine stabile, dokumentierte Schlüsselreihenfolge verwenden. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0002 | SR-TC-0021 |
| SR-REQ-0022 | Der Standardpfad eines Artefakts MUSS aus Artefakttyp und ID deterministisch ableitbar sein. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0002 | SR-TC-0022 |
| SR-REQ-0023 | SpecRoad DARF NICHT normative Daten außerhalb von `specroad.json` und den konfigurierten `managed_paths` erzeugen oder verändern. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0002 | SR-TC-0023 |
| SR-REQ-0024 | Alle unter `generated_path` erzeugten Dateien MÜSSEN als nicht normativ und generiert gekennzeichnet sein. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0002 | SR-TC-0024 |
| SR-REQ-0025 | SpecRoad DARF NICHT Änderungen an generierten Ansichten als Änderung des kanonischen Modells zurückimportieren. | SR-NEED-0001, SR-NEED-0009 | SR-VER-0002 | SR-TC-0025 |

### 12.3 IDs, Revisionen und Provenienz

Stabile Identität, Revision und Herkunft tragen Diff, Merge, Baselines, Audit und Evidence.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0026 | Jedes Artefakt MUSS eine projektweit eindeutige ID der Form `<PROJECT>-<TYPE>-<IDENTIFIER>` besitzen. | SR-NEED-0001, SR-NEED-0009, SR-NEED-0016 | SR-VER-0018 | SR-TC-0026 |
| SR-REQ-0027 | Der `<PROJECT>`-Teil einer Artefakt-ID MUSS dem konfigurierten `id_prefix` entsprechen. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0003 | SR-TC-0027 |
| SR-REQ-0028 | Der `<TYPE>`-Teil einer Artefakt-ID MUSS dem registrierten Präfix des tatsächlichen Artefakttyps entsprechen. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0003 | SR-TC-0028 |
| SR-REQ-0029 | SpecRoad MUSS doppelt vergebene IDs als Fehler behandeln. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0003 | SR-TC-0029 |
| SR-REQ-0030 | Die ID und das Feld `id_scheme` eines existierenden Artefakts DÜRFEN NICHT nach der ersten Speicherung geändert werden, ausgenommen die Ergänzung eines zuvor fehlenden `id_scheme` während einer Migration bei unveränderter ID. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0018 | SR-TC-0030 |
| SR-REQ-0031 | Eine einmal vergebene ID DARF NICHT nach Retirement, Supersession oder Ablehnung erneut vergeben werden. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0003 | SR-TC-0031 |
| SR-REQ-0032 | Der Dateiname einer normativen Artefaktdatei MUSS exakt `<ARTIFACT-ID>.json` lauten. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0003 | SR-TC-0032 |
| SR-REQ-0033 | Jedes Artefakt MUSS eine positive ganzzahlige `revision` besitzen, die bei 1 beginnt. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0003 | SR-TC-0033 |
| SR-REQ-0034 | Jede semantische Änderung an einem Artefakt MUSS die für ihre Operationsart in Anhang K festgelegte Revisionsregel erfüllen; unveränderte Übernahmen einer bestehenden Historienrevision sind keine Neuerzeugung. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0003 | SR-TC-0034 |
| SR-REQ-0035 | Zeitstempel in normativen Artefakten MÜSSEN RFC-3339-konform in UTC mit dem Suffix `Z` gespeichert werden. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0003 | SR-TC-0035 |
| SR-REQ-0036 | Jedes Artefakt MUSS `created_at`, `created_by`, `updated_at` und `updated_by` enthalten. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0003 | SR-TC-0036 |
| SR-REQ-0037 | Jedes Artefakt MUSS seine fachliche Herkunft über `provenance` oder typisierte Beziehungen zu Goal, Need oder Source nachvollziehbar machen können. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0003 | SR-TC-0037 |

### 12.4 Artefakttypen und Lebenszyklus

Das Kernmetamodell trennt fachliche Aussagen, Planung, Dokumentation, Entscheidungen und Nachweise.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0038 | SpecRoad MUSS in Version 0.2 die Kernartefakttypen `goal`, `need`, `capability`, `requirement`, `scenario`, `decision`, `risk`, `assumption`, `component`, `interface`, `source`, `verification`, `test`, `evidence`, `release`, `milestone`, `task`, `term`, `proposal`, `baseline`, `issue`, `document`, `section`, `content_block`, `view`, `code_ref`, `relation_review` und `configuration` unterstützen. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0015, SR-NEED-0016 | SR-VER-0004 | SR-TC-0038 |
| SR-REQ-0039 | Jeder Kernartefakttyp MUSS ein unverwechselbares ID-Präfix besitzen. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0004 | SR-TC-0039 |
| SR-REQ-0040 | Jedes reguläre 0.2-Artefakt MUSS die gemeinsamen Pflichtfelder aus Kapitel 9.3 enthalten; historisch unveränderbare Ressourcen werden ausschließlich nach Anhang Q gelesen. | SR-NEED-0002, SR-NEED-0009, SR-NEED-0014 | SR-VER-0004 | SR-TC-0040 |
| SR-REQ-0041 | SpecRoad MUSS typspezifische Pflichtfelder zusätzlich zu den gemeinsamen Feldern validieren. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0004 | SR-TC-0041 |
| SR-REQ-0042 | Ein Standardartefakt nach Kapitel 9.6.1 MUSS einen Reifegrad aus `draft`, `proposed`, `in_review`, `approved`, `rejected`, `superseded` oder `retired` besitzen. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0004 | SR-TC-0042 |
| SR-REQ-0043 | SpecRoad MUSS Reifegradübergänge von Standardartefakten anhand Kapitel 9.6.1 prüfen. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0009 | SR-VER-0004 | SR-TC-0043 |
| SR-REQ-0044 | Eine Fachinhaltsänderung an einem `approved` Standardartefakt MUSS dessen neue Revision exakt auf `proposed` setzen; reine Lifecycle-Operationen und gemischte Änderungspläne werden nach Kapitel 9.6.3 unterschieden. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0004 | SR-TC-0044 |
| SR-REQ-0045 | Ein jemals `approved` gewesenes Artefakt DARF NICHT physisch aus dem normativen Modell entfernt werden. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0004 | SR-TC-0045 |
| SR-REQ-0046 | Ein Wechsel auf `retired` MUSS einen nichtleeren Grund und einen verantwortlichen Akteur erfassen. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0004 | SR-TC-0046 |
| SR-REQ-0047 | Ein Wechsel eines Artefakts auf `superseded` MUSS durch mindestens eine gespeicherte `supersedes`-Beziehung eines Nachfolgeartefakts gleichen Typs auf dieses Artefakt begründet sein. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0004 | SR-TC-0047 |
| SR-REQ-0048 | Ein Wechsel auf `rejected` MUSS einen nichtleeren Ablehnungsgrund enthalten. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0004 | SR-TC-0048 |
| SR-REQ-0049 | Artefakte der Typen `capability`, `requirement`, `component`, `interface` und `task` MÜSSEN den getrennten Umsetzungsstatus `not_started`, `in_progress`, `implemented`, `blocked` oder `not_applicable` verwenden. | SR-NEED-0004, SR-NEED-0006 | SR-VER-0004 | SR-TC-0049 |
| SR-REQ-0050 | Artefakte der Typen `capability`, `requirement` und `task` MÜSSEN den gespeicherten `verification_plan_status` aus Kapitel 10.5 verwenden. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0004 | SR-TC-0050 |
| SR-REQ-0051 | SpecRoad MUSS Statuskombinationen anhand der allgemeinen und typspezifischen Lifecycle-Matrizen in Kapitel 9.6 ablehnen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0004 | SR-TC-0051 |

### 12.5 Relationsgraph und Traceability

Beziehungen sind primäre normative Daten; inverse Sichten und Reviewzustände werden berechnet.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0052 | Jede gespeicherte Beziehung MUSS mindestens `relation_id`, `id_scheme`, `type`, `target`, `external_identities` und `extensions` enthalten und am Quellartefakt gespeichert werden. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0016 | SR-VER-0021 | SR-TC-0052 |
| SR-REQ-0053 | SpecRoad MUSS die gespeicherten Kernbeziehungstypen `addresses`, `refines`, `derived_from`, `depends_on`, `conflicts_with`, `constrains`, `allocated_to`, `implemented_by`, `verified_by`, `produces`, `mitigates`, `scheduled_for`, `part_of`, `supersedes`, `duplicates`, `contains` und `references` sowie die berechnete inverse Sicht `superseded_by` unterstützen. | SR-NEED-0003, SR-NEED-0012, SR-NEED-0015 | SR-VER-0005 | SR-TC-0053 |
| SR-REQ-0054 | SpecRoad MUSS jede Kernrelation gegen die vollständige Quell-/Zielmatrix in Kapitel 9.7 validieren. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0005 | SR-TC-0054 |
| SR-REQ-0055 | Das Ziel jeder Beziehung MUSS in einem Vollprojekt als Artefakt im geladenen Modell existieren. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0005 | SR-TC-0055 |
| SR-REQ-0056 | Eine Beziehung DARF NICHT ein Artefakt auf sich selbst beziehen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0005 | SR-TC-0056 |
| SR-REQ-0057 | Die symmetrischen Beziehungen `conflicts_with` und `duplicates` MÜSSEN genau einmal in lexikografisch kanonischer Quell-Ziel-Reihenfolge gespeichert werden; ihre `relation_id` bleibt bei der kanonischen Umordnung unverändert. | SR-NEED-0003, SR-NEED-0012, SR-NEED-0016 | SR-VER-0021 | SR-TC-0057 |
| SR-REQ-0058 | SpecRoad MUSS inverse Beziehungssichten einschließlich `superseded_by` berechnen, ohne inverse Beziehungen als zweite normative Kopie zu speichern. | SR-NEED-0003, SR-NEED-0010 | SR-VER-0005 | SR-TC-0058 |
| SR-REQ-0059 | Die gespeicherten Beziehungen `refines`, `part_of` und `supersedes` DÜRFEN NICHT in ihrer jeweiligen Hierarchie einen gerichteten Zyklus bilden. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0005 | SR-TC-0059 |
| SR-REQ-0060 | Bei `refines` MUSS die Beziehung vom detaillierteren zum allgemeineren Artefakt gerichtet sein. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0005 | SR-TC-0060 |
| SR-REQ-0061 | Ein `approved` Requirement MUSS mindestens eine Herkunftsbeziehung `derived_from`, `refines` oder `addresses` besitzen. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0005 | SR-TC-0061 |
| SR-REQ-0062 | Ein `approved` verifizierbares Requirement MUSS mindestens eine Beziehung `verified_by` zu einem Verification- oder Test-Artefakt besitzen. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0005 | SR-TC-0062 |
| SR-REQ-0063 | SpecRoad MUSS verwaiste Artefakte anhand profilabhängiger Mindestbeziehungen erkennen. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0005 | SR-TC-0063 |
| SR-REQ-0064 | SpecRoad MUSS für jedes Artefakt erklären können, über welche Beziehungspfade es auf Goals oder Needs zurückgeführt wird. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0005 | SR-TC-0064 |
| SR-REQ-0065 | SpecRoad MUSS profilabhängig fehlende erwartete Beziehungen als Diagnosen ausgeben. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0005 | SR-TC-0065 |

### 12.6 Requirements, Profile und Glossar

Anforderungen bleiben lesbar, erhalten aber maschinenprüfbare Typisierung, Semantik und Terminologie.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0066 | Ein Requirement MUSS genau einen `requirement_kind` aus `functional`, `quality`, `interface`, `data`, `constraint`, `security`, `safety` oder `compliance` besitzen. | SR-NEED-0001, SR-NEED-0002 | SR-VER-0006 | SR-TC-0066 |
| SR-REQ-0067 | Ein Requirement MUSS eine nichtleere normative Aussage im Feld `statement` enthalten. | SR-NEED-0001, SR-NEED-0002 | SR-VER-0006 | SR-TC-0067 |
| SR-REQ-0068 | Ein Requirement MUSS seine Verbindlichkeit im Pflichtfeld `normative_force` mit genau einem der Werte `must`, `must_not`, `should` oder `may` deklarieren. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0044 | SR-TC-0068 |
| SR-REQ-0069 | Die Anerkennung einer Requirement-Verbindlichkeit DARF NICHT das Vorkommen eines normativen Schlüsselworts im natürlichen `statement` voraussetzen. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0044 | SR-TC-0069 |
| SR-REQ-0070 | Die fachliche Freigabe eines Requirements MUSS die eindeutige Einheit aus genau einer Verpflichtungsart und einem eigenständig prüfbaren Sachverhalt nach Anhang S.2 bestätigen; eine bestandene Core-Strukturprüfung ersetzt diese menschliche Beurteilung nicht. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0006 | SR-TC-0070 |
| SR-REQ-0071 | Ein Requirement mit `normative_force=should` MUSS nichtleere `deviation_conditions` und `deviation_authority` nach Anhang S.2 definieren. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0044 | SR-TC-0071 |
| SR-REQ-0072 | Ein `approved` Requirement MUSS eine nichtleere Begründung im Feld `rationale` enthalten. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0006 | SR-TC-0072 |
| SR-REQ-0073 | Ein Requirement MUSS eine Priorität aus `mandatory`, `high`, `medium` oder `low` besitzen. | SR-NEED-0001, SR-NEED-0006 | SR-VER-0006 | SR-TC-0073 |
| SR-REQ-0074 | Ein Requirement MUSS eine Kritikalität aus `normal`, `important`, `critical` oder `safety_critical` besitzen. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0006 | SR-TC-0074 |
| SR-REQ-0075 | SpecRoad MUSS für Requirements strukturierte Semantikfelder für `scope`, `actor`, `trigger`, `preconditions`, `response`, `object`, `timing`, `thresholds` und `exceptions` unterstützen. | SR-NEED-0001, SR-NEED-0005 | SR-VER-0006 | SR-TC-0075 |
| SR-REQ-0076 | Zeitdauern in strukturierten Semantikfeldern MÜSSEN als ISO-8601-Duration oder als Wert mit expliziter UCUM-kompatibler Einheit gespeichert werden. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0006 | SR-TC-0076 |
| SR-REQ-0077 | Ein `approved` Quality-Requirement MUSS mindestens eine messbare Eigenschaft, Messmethode, Vergleichsoperation und Zielgrenze enthalten. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0006 | SR-TC-0077 |
| SR-REQ-0078 | Ein `approved` Interface-Requirement MUSS Quell- und Zielsystem beziehungsweise die betroffene Systemgrenze referenzieren. | SR-NEED-0002, SR-NEED-0004 | SR-VER-0006 | SR-TC-0078 |
| SR-REQ-0079 | Ein Profil MUSS als versioniertes deklaratives JSON-Dokument Pflichtfelder, zulässige Werte, Relation Rules, Lint-Regeln und Schweregradüberschreibungen definieren können. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0006 | SR-TC-0079 |
| SR-REQ-0080 | Version 0.2 MUSS die Fachprofile `core`, `software-de` und `software-en` ohne erzwungene gemeinsame Inhaltssprache gemäß Anhang S.6 bereitstellen. | SR-NEED-0001, SR-NEED-0012 | SR-VER-0045 | SR-TC-0080 |
| SR-REQ-0081 | Ein Term-Artefakt MUSS `term`, `definition`, `language`, `synonyms`, `forbidden_synonyms`, `owner` und `maturity` enthalten. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0006 | SR-TC-0081 |
| SR-REQ-0082 | SpecRoad MUSS explizit konfigurierte verbotene Glossarsynonyme und undefinierte Referenzen in der jeweils deklarierten Sprache als begrenzte literale Policyprüfungen auswerten, ohne daraus tiefes Sprachverständnis abzuleiten. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0045 | SR-TC-0082 |

### 12.7 Validierung und Diagnosen

Pass oder Fail beruht auf nachvollziehbaren deterministischen Regeln und nicht auf KI-Behauptungen.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0083 | `specroad validate` MUSS ohne Zugriff auf ein KI-Modell ausführbar sein. | SR-NEED-0007, SR-NEED-0008 | SR-VER-0007 | SR-TC-0083 |
| SR-REQ-0084 | `specroad validate` MUSS standardmäßig das vollständige geladene Projektmodell prüfen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0007 | SR-TC-0084 |
| SR-REQ-0085 | Eine auf Artefakt-IDs eingeschränkte Validierung MUSS alle für Typ-, Relation-, Lifecycle- und Profilregeln erforderlichen abhängigen Artefakte mitladen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0007 | SR-TC-0085 |
| SR-REQ-0086 | Die Validierung MUSS mindestens JSON-Parsing, JSON Schema, Typen, IDs, Referenzen, Relation Rules, Zyklen, Lifecycle, Profile, Baseline-Integrität und Evidence-Aktualität abdecken. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0007 | SR-TC-0086 |
| SR-REQ-0087 | SpecRoad MUSS JSON-Parsefehler mit Datei, Zeile und Spalte ausgeben. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0007 | SR-TC-0087 |
| SR-REQ-0088 | SpecRoad MUSS Schema- und Modellfehler mit Artefakt-ID und JSON Pointer auf das betroffene Feld ausgeben, soweit eine Artefakt-ID ermittelbar ist. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0007 | SR-TC-0088 |
| SR-REQ-0089 | Jede Diagnose MUSS `code`, `severity`, `category`, `message`, `origin`, `rule_id`, `artifact_id`, `path`, `location`, `rationale`, `remediation` und `related_ids` unterstützen. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0007 | SR-TC-0089 |
| SR-REQ-0090 | Der Diagnoseursprung MUSS einen der Werte `core_rule`, `profile_rule`, `import_rule`, `migration_rule`, `merge_rule`, `analyzer_observation` oder `ai_suggestion` besitzen. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0014 | SR-VER-0007 | SR-TC-0090 |
| SR-REQ-0091 | Die Diagnoseschwere MUSS einen der Werte `error`, `warning` oder `info` besitzen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0007 | SR-TC-0091 |
| SR-REQ-0092 | Diagnosen MÜSSEN bei identischen Eingaben in einer stabilen Reihenfolge nach Schwere, Datei, Artefakt-ID, Pfad und Code ausgegeben werden. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0007 | SR-TC-0092 |
| SR-REQ-0093 | Die globale Option `--fail-on error\|warning` MUSS bestimmen, ab welcher Schwere ein Prüfkommando fehlschlägt. | SR-NEED-0007, SR-NEED-0002 | SR-VER-0007 | SR-TC-0093 |
| SR-REQ-0094 | Die Option `--strict` MUSS `--fail-on warning` und die dokumentierten optionalen Core-Lint-Regeln aktivieren, ohne dadurch einen Analyzer zu starten oder nicht verfügbare Sprachanalyse als geprüft auszugeben. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0007 | SR-TC-0094 |
| SR-REQ-0095 | `specroad lint` MUSS deterministische Qualitätsregeln ausführen, die nicht für die strukturelle Modellgültigkeit erforderlich sind. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0007 | SR-TC-0095 |
| SR-REQ-0096 | Die eingebauten Lint-Regeln MÜSSEN fehlende Begründung, fehlende Verifikation, explizit konfigurierte literale Glossar-/Platzhalterverletzungen und fehlende Mindestbeziehungen diagnostizieren; semantische Modalitäts- oder Mehrdeutigkeitserkennung ist kein Core-Passkriterium. | SR-NEED-0002, SR-NEED-0005 | SR-VER-0007 | SR-TC-0096 |
| SR-REQ-0097 | Ein `approved` Artefakt DARF NICHT `TBD`, `TODO`, `FIXME` oder einen profildefinierten offenen Platzhalter in normativen Feldern enthalten. | SR-NEED-0002, SR-NEED-0003 | SR-VER-0007 | SR-TC-0097 |
| SR-REQ-0098 | Jeder Diagnosecode MUSS innerhalb einer Major-Formatversion stabil und dokumentiert sein. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0007 | SR-TC-0098 |
| SR-REQ-0099 | Jedes Prüfkommando MUSS eine Zusammenfassung mit Anzahl geprüfter Artefakte und Anzahl Diagnosen je Schwere ausgeben. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0007 | SR-TC-0099 |
| SR-REQ-0100 | Read-only-Prüfkommandos DÜRFEN NICHT normative oder generierte Projektdateien verändern. | SR-NEED-0007, SR-NEED-0011 | SR-VER-0007 | SR-TC-0100 |

### 12.8 Rendering, Abfragen, Trace, Impact und Diff

SpecRoad erzeugt zielgruppengerechte Sichten und erklärt Änderungen aus strukturierter Semantik.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0101 | `specroad render` MUSS die eingebauten Ansichten `specification`, `traceability`, `roadmap` und `verification` als Markdown erzeugen können; weitere deklarative Ansichten werden über `specroad view render` ausgeführt. | SR-NEED-0001, SR-NEED-0006, SR-NEED-0015 | SR-VER-0008 | SR-TC-0101 |
| SR-REQ-0102 | Gerenderte Markdown-Dateien MÜSSEN bei identischem Modell, identischer Konfiguration und identischer Toolversion byte-identisch sein. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0008 | SR-TC-0102 |
| SR-REQ-0103 | Jede gerenderte Datei MUSS im Kopf die Modellwurzel, Toolversion, Schema-Version, aktive Profile und den Hinweis `GENERATED — DO NOT EDIT` enthalten. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0008 | SR-TC-0103 |
| SR-REQ-0104 | Artefakte MÜSSEN in gerenderten Ansichten standardmäßig nach Artefakttyp und ID stabil sortiert werden. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0008 | SR-TC-0104 |
| SR-REQ-0105 | Jedes gerenderte Artefakt MUSS einen stabilen Markdown-Anker enthalten, der aus seiner ID abgeleitet ist. | SR-NEED-0001, SR-NEED-0009 | SR-VER-0008 | SR-TC-0105 |
| SR-REQ-0106 | Die Spezifikationsansicht MUSS Ziele, Needs, Scope, Begriffe, Anforderungen, Entscheidungen, Risiken, Verifikationen und offene Issues darstellen können. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0008 | SR-TC-0106 |
| SR-REQ-0107 | Die Traceability-Ansicht MUSS für jedes Requirement mindestens Herkunft, Umsetzung, Verifikation, Evidence und Release-Zuordnung darstellen. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0008 | SR-TC-0107 |
| SR-REQ-0108 | `specroad show <ID>` MUSS das vollständige Artefakt sowie berechnete eingehende und ausgehende Beziehungen anzeigen. | SR-NEED-0001, SR-NEED-0003 | SR-VER-0008 | SR-TC-0108 |
| SR-REQ-0109 | `specroad query` MUSS die in Kapitel 11.6 definierte Filter- und Projektionsgrammatik unterstützen. | SR-NEED-0003, SR-NEED-0010 | SR-VER-0008 | SR-TC-0109 |
| SR-REQ-0110 | Query MUSS wiederholte Werte derselben Wertfilterart als ODER, unterschiedliche Wertfilterarten als UND und davon getrennt alle wiederholten SRX-`--filter`-Ausdrücke untereinander sowie mit den Wertfiltern als UND nach Kapitel 11.6 auswerten. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0008 | SR-TC-0110 |
| SR-REQ-0111 | `specroad trace <ID>` MUSS gerichtete Traversierung mit `--direction in\|out\|both` und einer begrenzten `--depth` unterstützen. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0008 | SR-TC-0111 |
| SR-REQ-0112 | `specroad why <ID>` MUSS alle kürzesten gültigen Pfade des Artefakts zu Goals, Needs und Sources bis zur konfigurierten Maximaltiefe ausgeben. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0008 | SR-TC-0112 |
| SR-REQ-0113 | `specroad impact <ID>` MUSS mindestens alle direkt eingehend und ausgehend verbundenen Artefakte gruppiert nach Relationstyp ausgeben. | SR-NEED-0003, SR-NEED-0006 | SR-VER-0008 | SR-TC-0113 |
| SR-REQ-0114 | `specroad diff --against <BASE>` MUSS als Vergleichsbasis eine Baseline-ID, einen Git-Ref, ein verifiziertes Projektbundle oder ein lokales SpecRoad-Projektverzeichnis desselben Projekts akzeptieren. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0014 | SR-VER-0008 | SR-TC-0114 |
| SR-REQ-0115 | Der semantische Diff MUSS mindestens Hinzufügen, Retirement, Feldänderung, Grenzwertänderung, Timing-Verschärfung oder -Lockerung, Scope- oder Applicability-Änderung, Ausnahmeänderung, Relationsänderung, Dokumentstruktur- oder Positionsänderung, Statusänderung, Verifikationsänderung, Evidence-Aktualitätsänderung und Code-Referenzänderung unterscheiden, sofern strukturierte Felder diese Klassifikation erlauben. | SR-NEED-0003, SR-NEED-0006, SR-NEED-0015 | SR-VER-0008 | SR-TC-0115 |
| SR-REQ-0116 | Eine reine Änderung unstrukturierter Aussagefelder MUSS als `text_changed` ausgewiesen werden, wenn keine deterministische semantische Klassifikation möglich ist. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0008 | SR-TC-0116 |
| SR-REQ-0117 | Rendering, Query, Trace, Why, Impact und Diff DÜRFEN NICHT das normative Projektmodell verändern. | SR-NEED-0007, SR-NEED-0011 | SR-VER-0008 | SR-TC-0117 |

### 12.9 Release, Milestone, Task und Roadmap

Planung bleibt mit Anforderungen verbunden; Roadmap und Readiness sind berechnete Sichten.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0118 | Ein Release-Artefakt MUSS mindestens Name, Ziel, Reifegrad, optionales Zieldatum und Readiness-Policy enthalten. | SR-NEED-0006, SR-NEED-0010 | SR-VER-0009 | SR-TC-0118 |
| SR-REQ-0119 | Ein Milestone-Artefakt MUSS über `part_of` genau einem Release zugeordnet sein. | SR-NEED-0006, SR-NEED-0010 | SR-VER-0009 | SR-TC-0119 |
| SR-REQ-0120 | Ein Task-Artefakt MUSS mindestens Beschreibung, Owner, Umsetzungsstatus, Done-Kriterien und Beziehungen zu den erfüllten Anforderungen oder Entscheidungen enthalten. | SR-NEED-0004, SR-NEED-0006 | SR-VER-0009 | SR-TC-0120 |
| SR-REQ-0121 | Capabilities, Requirements und Tasks MÜSSEN über `scheduled_for` einem Release oder Milestone zugeordnet werden können. | SR-NEED-0006, SR-NEED-0010 | SR-VER-0009 | SR-TC-0121 |
| SR-REQ-0122 | Die Roadmap-Ansicht MUSS ausschließlich aus Artefakten, Beziehungen, Prioritäten, Risiken und Terminen des kanonischen Modells abgeleitet werden. | SR-NEED-0010, SR-NEED-0009 | SR-VER-0009 | SR-TC-0122 |
| SR-REQ-0123 | SpecRoad DARF NICHT eine separat gepflegte normative Roadmap-Datei neben dem Artefaktgraphen verlangen. | SR-NEED-0010, SR-NEED-0001 | SR-VER-0009 | SR-TC-0123 |
| SR-REQ-0124 | `specroad roadmap explain <ID>` MUSS Ziele, enthaltene Requirements, Abhängigkeiten, Risiken, Annahmen und den Ursprung der Zuordnung erklären. | SR-NEED-0010, SR-NEED-0003 | SR-VER-0009 | SR-TC-0124 |
| SR-REQ-0125 | `specroad release readiness <RELEASE-ID>` MUSS Freigabe, Umsetzung, Verifikation, Coverage, Blocker-Risiken, offene Issues und fehlende Evidenz des Release-Scopes nach dem versionierten Pflichtgate-, Entscheidungs- und Bestandsdatenvertrag in Kapitel 10.5.6 prüfen. | SR-NEED-0006, SR-NEED-0010 | SR-VER-0009 | SR-TC-0125 |
| SR-REQ-0126 | Die Readiness-Prüfung MUSS direkte `depends_on`-Abhängigkeiten des Release-Scopes einbeziehen und außerhalb des Releases liegende Pflichtabhängigkeiten melden. | SR-NEED-0006, SR-NEED-0003 | SR-VER-0009 | SR-TC-0126 |
| SR-REQ-0127 | Ein Task DARF den Umsetzungsstatus `implemented` nur besitzen, wenn seine Done-Kriterien erfüllt und durch Review oder Evidence nachgewiesen sind. | SR-NEED-0004, SR-NEED-0005 | SR-VER-0009 | SR-TC-0127 |
| SR-REQ-0128 | SpecRoad DARF NICHT in Version 0.2 automatisch berechnete Termine, Aufwandsschätzungen oder einen kritischen Pfad als normative Daten in das Projektmodell schreiben. | SR-NEED-0010, SR-NEED-0011 | SR-VER-0009 | SR-TC-0128 |

### 12.10 Verifikation, Tests, Evidenz und Coverage

Erfüllung folgt expliziten Verification Contracts und passender, aktueller Evidence.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0129 | Ein Verification-Artefakt MUSS eine Methode aus `inspection`, `review`, `analysis`, `simulation`, `automated_test`, `manual_test`, `formal_proof`, `monitoring`, `audit` oder `measurement` besitzen. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0010 | SR-TC-0129 |
| SR-REQ-0130 | Ein Verification-Artefakt MUSS Vorbedingungen, Prüfgegenstand, Verfahren, Oracle oder Pass-Kriterium, erforderliche Evidence-Arten, vollständige `evidence_slots` nach Kapitel 10.5.2 und eine Konfigurationspolicy `independent` oder `bound` definieren. | SR-NEED-0005, SR-NEED-0002, SR-NEED-0015 | SR-VER-0010 | SR-TC-0130 |
| SR-REQ-0131 | Ein Test-Artefakt MUSS einen stabilen externen Testbezeichner oder einen projektinternen Pfad, den Testtyp und das erwartete Oracle referenzieren. | SR-NEED-0005, SR-NEED-0004 | SR-VER-0010 | SR-TC-0131 |
| SR-REQ-0132 | Ein Evidence-Artefakt MUSS Ergebnis, Erzeugungszeit, Erzeuger, Werkzeug mit Version, Prüfumgebung, Subject-IDs mit Revision, Vollhash und `verification_context_hash-v1`, Origin, `run_context` gemäß Kapitel 10.5.2 und optionale Anhänge enthalten. | SR-NEED-0005, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0132 |
| SR-REQ-0133 | Ein als `recorded` gespeichertes Evidence-Artefakt MUSS einschließlich seiner ID unveränderbar sein, jede neue Messung unter einer neuen Evidence-ID speichern und identische Wiederholungen nach dem Idempotenzvertrag auf denselben Nachweis abbilden. | SR-NEED-0005, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0133 |
| SR-REQ-0134 | Jeder Evidence-Anhang MUSS einen relativen Projektpfad, Medientyp, Größe und SHA-256-Hash besitzen. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0010 | SR-TC-0134 |
| SR-REQ-0135 | Evidence-Anhänge DÜRFEN NICHT außerhalb des Projektroots liegen oder über Symlinks außerhalb des Projektroots aufgelöst werden. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0014 | SR-TC-0135 |
| SR-REQ-0136 | Ein Requirement DARF das berechnete `verification_result=passed` nur nach vollständiger Bewertungs- und Nachweisauswahl sowie erfolgreicher Aggregation nach Kapitel 10.5 besitzen. | SR-NEED-0005, SR-NEED-0006, SR-NEED-0015 | SR-VER-0010 | SR-TC-0136 |
| SR-REQ-0137 | SpecRoad MUSS Evidence bei einer Abweichung des aktuellen `verification_context_hash-v1` eines Subjects oder einer gebundenen Konfiguration als `stale` behandeln. | SR-NEED-0005, SR-NEED-0006, SR-NEED-0015 | SR-VER-0010 | SR-TC-0137 |
| SR-REQ-0138 | Der gespeicherte `verification_plan_status=waived` MUSS ein vollständiges `verification_waiver`-Objekt nach Kapitel 10.5 besitzen. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0010 | SR-TC-0138 |
| SR-REQ-0139 | Coverage MUSS mindestens positive Fälle, negative Fälle, Grenzwerte, Ausnahmen, zeitliches Verhalten, Fehlerzustände, Security-Aspekte, Performance-Aspekte, aktuelles Ergebnis und Evidence-Aktualität getrennt ausweisen können. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0010 | SR-TC-0139 |
| SR-REQ-0140 | `specroad coverage` MUSS Coverage nach Requirement, Requirement-Kind, Release und Verifikationsdimension aggregieren können. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0010 | SR-TC-0140 |
| SR-REQ-0141 | Eine Release-Coverage MUSS Requirements ohne Verification Contract, ohne Testbezug, ohne Evidence und mit veralteter Evidence getrennt ausweisen. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0010 | SR-TC-0141 |
| SR-REQ-0142 | Evidence MUSS ihren Erzeuger als `human`, `tool`, `ci`, `monitoring` oder `ai` kennzeichnen, ohne dass diese Herkunft das deterministische Prüfergebnis ersetzt. | SR-NEED-0005, SR-NEED-0008 | SR-VER-0010 | SR-TC-0142 |

### 12.11 Baselines

Baselines fixieren unveränderbar Modell, Regeln, Konfigurationen, Anhänge und Nachweise.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0143 | Eine Baseline MUSS eine benannte, unveränderbare Menge konkreter Artefaktrevisionen, Beziehungen, Profile, Regeln, Mappings, effektiver Konfiguration und referenzierter Anhänge samt content-addressierten Snapshotobjekten darstellen. | SR-NEED-0002, SR-NEED-0009, SR-NEED-0014 | SR-VER-0011 | SR-TC-0143 |
| SR-REQ-0144 | Ein Baseline-Artefakt MUSS die Art `working` oder `release` besitzen. | SR-NEED-0002, SR-NEED-0006 | SR-VER-0011 | SR-TC-0144 |
| SR-REQ-0145 | Eine Baseline MUSS für jedes enthaltene Artefakt ID, Revision, kanonischen SHA-256-Hash und den Pfad seines Snapshotobjekts im Baseline-Objektspeicher speichern. | SR-NEED-0009, SR-NEED-0007 | SR-VER-0011 | SR-TC-0145 |
| SR-REQ-0146 | Eine Baseline MUSS Schema-Version, aktive Profile mit Version, Regel- und Mappingressourcen, SpecRoad-Version sowie Snapshot und SHA-256-Hash der effektiven semantischen Konfiguration nach Kapitel 10.8–10.10 speichern. | SR-NEED-0009, SR-NEED-0012, SR-NEED-0014 | SR-VER-0011 | SR-TC-0146 |
| SR-REQ-0147 | Eine Baseline MUSS den Modellumfang und den vor dem Schreiben der Baseline berechneten kanonischen Modellwurzelhash über alle enthaltenen Inhalte speichern. | SR-NEED-0009, SR-NEED-0007 | SR-VER-0011 | SR-TC-0147 |
| SR-REQ-0148 | Ein erzeugtes Baseline-Artefakt und jedes von ihm referenzierte Snapshotobjekt DÜRFEN NICHT geändert oder unter derselben Identität mit anderem Inhalt neu erzeugt werden. | SR-NEED-0009, SR-NEED-0002 | SR-VER-0011 | SR-TC-0148 |
| SR-REQ-0149 | `specroad baseline create <NAME>` MUSS vor dem Schreiben die vollständige Projektvalidierung erfolgreich ausführen. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0011 | SR-TC-0149 |
| SR-REQ-0150 | Eine Release-Baseline DARF nur erzeugt werden, wenn die Readiness-Policy einschließlich einer im Release gespeicherten, gültigen Bewertungsauswahl nach Kapitel 10.5.4 erfüllt ist. | SR-NEED-0006, SR-NEED-0009 | SR-VER-0011 | SR-TC-0150 |
| SR-REQ-0151 | `specroad baseline verify <ID>` MUSS die Bytes aller referenzierten Snapshotobjekte gegen ihre Artefakt-, Profil-, Regel-, Mapping-, Konfigurations- und Anhangshashes sowie das rekonstruierte Manifest gegen den Modellwurzelhash prüfen, ohne den Arbeitsstand zu verändern. | SR-NEED-0009, SR-NEED-0007, SR-NEED-0014 | SR-VER-0011 | SR-TC-0151 |
| SR-REQ-0152 | `specroad baseline compare <A> <B>` MUSS die in den Baseline-Objektspeichern gesicherten Inhalte lesen und denselben strukturellen und semantischen Diffvertrag wie `specroad diff` verwenden. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0011 | SR-TC-0152 |
| SR-REQ-0153 | Eine Baseline MUSS aufgrund ihrer Snapshotobjekte ohne Git-Commit verifizierbar, materialisierbar und vergleichbar bleiben; ein zugehöriger Git-Commit ist ausschließlich optionale Provenienz. | SR-NEED-0004, SR-NEED-0009 | SR-VER-0011 | SR-TC-0153 |

### 12.12 KI-Proposals und isolierte Ausführung

Externe KI-Agenten können SpecRoad bedienen, ohne stillschweigend normative Daten zu verändern.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0154 | SpecRoad MUSS Proposal-Artefakte als versionierte JSON-Dokumente unterstützen. | SR-NEED-0008, SR-NEED-0003 | SR-VER-0012 | SR-TC-0154 |
| SR-REQ-0155 | Ein Proposal MUSS einen Status aus `draft`, `validated`, `checked`, `in_review`, `approved`, `rejected`, `applied` oder `stale` besitzen. | SR-NEED-0008, SR-NEED-0003 | SR-VER-0012 | SR-TC-0155 |
| SR-REQ-0156 | Ein Proposal MUSS Autor, Akteurtyp, Erstellungszeit und eine eindeutige Proposal-ID enthalten. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0012 | SR-TC-0156 |
| SR-REQ-0157 | Bei einem KI-Autor MUSS ein Proposal die Felder `provider`, `model_name`, `model_version_or_build`, `prompt_template_version` und `runner_version` enthalten und für jeden nicht ermittelbaren Wert `unknown` sowie eine Begründung speichern. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0012 | SR-TC-0157 |
| SR-REQ-0158 | Ein Proposal MUSS seine erwartete Basis durch den ausschließlich zulässigen Scope Descriptor aus Kapitel 10.8.1 und dessen Modellwurzelhash sowie optional durch zusätzliche Baseline- oder Git-Provenienz festlegen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0158 |
| SR-REQ-0159 | Ein Proposal MUSS Änderungen als geordnete Operationen des gemeinsamen Change-Plan-Modells beschreiben. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0013 | SR-VER-0012 | SR-TC-0159 |
| SR-REQ-0160 | Eine `update`-Operation MUSS einen RFC-6902-kompatiblen JSON Patch verwenden. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0013 | SR-VER-0012 | SR-TC-0160 |
| SR-REQ-0161 | Jede `update`- oder `retire`-Operation MUSS die erwartete Artefaktrevision und den erwarteten Artefakthash enthalten. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0161 |
| SR-REQ-0162 | Ein Proposal MUSS eine Gesamtbegründung sowie für jede Änderung Ziel, Begründung und betroffene Anforderungs- oder Issue-IDs enthalten. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0162 |
| SR-REQ-0163 | Ein KI-erzeugtes Proposal MUSS verwendete Quellen, offene Annahmen und eine Konfidenz zwischen 0 und 1 für jede Operation in `changes` dokumentieren. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0012 | SR-TC-0163 |
| SR-REQ-0164 | `specroad proposal validate <FILE>` MUSS ausschließlich das Proposal-Schema, interne Referenzen und die Anwendbarkeit gegen die deklarierte Basis prüfen. | SR-NEED-0008, SR-NEED-0007 | SR-VER-0012 | SR-TC-0164 |
| SR-REQ-0165 | `specroad proposal validate` DARF NICHT den Projektarbeitsstand verändern. | SR-NEED-0008, SR-NEED-0011 | SR-VER-0012 | SR-TC-0165 |
| SR-REQ-0166 | `specroad proposal check <FILE>` MUSS die deklarierte Basis in einem isolierten temporären Workspace materialisieren und das Proposal ausschließlich dort anwenden. | SR-NEED-0008, SR-NEED-0011 | SR-VER-0012 | SR-TC-0166 |
| SR-REQ-0167 | Der isolierte Proposal-Check MUSS ausschließlich interne SpecRoad-Validatoren, Renderer, Query-, Diff- und Impact-Funktionen ausführen. | SR-NEED-0008, SR-NEED-0011 | SR-VER-0012 | SR-TC-0167 |
| SR-REQ-0168 | Der isolierte Proposal-Check DARF NICHT eine Netzwerkverbindung initiieren oder Projektcode, einen Buildbefehl, einen Testbefehl oder einen externen Pluginprozess ausführen. | SR-NEED-0011, SR-NEED-0008 | SR-VER-0014 | SR-TC-0168 |
| SR-REQ-0169 | Der Proposal-Check MUSS mindestens vollständige Validierung, Linting, semantischen Diff, direkte Impact-Analyse und einen maschinenlesbaren Abschlussbericht erzeugen. | SR-NEED-0008, SR-NEED-0003 | SR-VER-0012 | SR-TC-0169 |
| SR-REQ-0170 | Der temporäre Proposal-Workspace MUSS nach erfolgreichem oder fehlgeschlagenem Check entfernt werden, sofern nicht ausdrücklich ein Debug-Aufbewahrungsmodus gewählt wurde. | SR-NEED-0011, SR-NEED-0008 | SR-VER-0012 | SR-TC-0170 |
| SR-REQ-0171 | Ein Proposal MUSS eine Review-Historie mit Akteurtyp, Reviewer-ID, Entscheidung, Zeitstempel und optionalem Kommentar unterstützen. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0012 | SR-TC-0171 |
| SR-REQ-0172 | Eine Review-Entscheidung eines Akteurs vom Typ `ai` DARF NICHT als menschliche Freigabe zählen. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0012 | SR-TC-0172 |
| SR-REQ-0173 | `specroad proposal apply <FILE>` MUSS mindestens die konfigurierte Anzahl gültiger menschlicher Freigaben nach dem Inhaltsbindungsvertrag aus Kapitel 10.3 und 11.10 verlangen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0173 |
| SR-REQ-0174 | `specroad proposal apply` MUSS das Proposal als `stale` ablehnen, wenn Modellwurzelhash, erwartete Revision oder erwarteter Artefakthash nicht mehr zur aktuellen Basis passen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0174 |
| SR-REQ-0175 | `specroad proposal apply` MUSS bei erfolgreicher Rückkehr entweder alle Operationen veröffentlichen oder den vollständigen normativen Ausgangszustand erhalten. | SR-NEED-0003, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0175 |
| SR-REQ-0176 | `specroad proposal apply` DARF NICHT einen Git-Commit, Branch, Tag oder Push erzeugen. | SR-NEED-0004, SR-NEED-0008 | SR-VER-0012 | SR-TC-0176 |
| SR-REQ-0177 | Eine KI-Aussage oder KI-Review DARF NICHT als Evidence oder menschliche Freigabe für ein berechnetes Verification Result oder eine Readiness-Bedingung gelten. | SR-NEED-0005, SR-NEED-0008 | SR-VER-0012 | SR-TC-0177 |
| SR-REQ-0178 | Jeder Proposal-Check und jedes Proposal-Apply MUSS einen Auditbericht mit Proposal-ID, Basis, Toolversion, Start- und Endzeit, Ergebnis, Diagnosen und erzeugten beziehungsweise geänderten Artefakten ausgeben. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0012 | SR-TC-0178 |

### 12.13 CLI, Git, CI und Agentenbedienung

Die CLI ist die verbindliche Mensch-, Agenten- und Automatisierungsschnittstelle.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0179 | Version 0.2 MUSS mindestens die Befehlsgruppen `init`, `config`, `format`, `change`, `artifact`, `relation`, `lifecycle`, `document`, `view`, `diagram`, `show`, `validate`, `lint`, `render`, `query`, `trace`, `why`, `impact`, `diff`, `coverage`, `roadmap`, `release`, `evidence`, `baseline`, `proposal`, `import`, `export`, `migrate`, `merge`, `bundle`, `recover`, `lock`, `capabilities`, `schema`, `command`, `project` und `version` bereitstellen. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0013 | SR-TC-0179 |
| SR-REQ-0180 | Jeder Befehl MUSS ausschließlich die für seine Befehlsklasse in Kapitel 11.7 und seinem Command Contract zugelassenen globalen Optionen unterstützen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0013 | SR-TC-0180 |
| SR-REQ-0181 | Jeder Befehl und Unterbefehl MUSS mit `--help` eine vollständige Nutzung, Optionen, Exit Codes und mindestens ein Beispiel ausgeben. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0013 | SR-TC-0181 |
| SR-REQ-0182 | Ergebnisdaten MÜSSEN auf stdout und betriebliche Fehlermeldungen, die nicht Teil eines strukturierten Ergebnisdokuments sind, auf stderr ausgegeben werden. | SR-NEED-0007, SR-NEED-0008 | SR-VER-0013 | SR-TC-0182 |
| SR-REQ-0183 | Das Ausgabeformat `json` MUSS ein versioniertes, einzelnes JSON-Ergebnisobjekt auf stdout erzeugen. | SR-NEED-0007, SR-NEED-0008 | SR-VER-0013 | SR-TC-0183 |
| SR-REQ-0184 | Validierungs- und Lint-Befehle MÜSSEN das Ausgabeformat `sarif` gemäß SARIF 2.1.0 unterstützen. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0013 | SR-TC-0184 |
| SR-REQ-0185 | SpecRoad MUSS die Exit Codes aus Kapitel 11.8 einschließlich Code 8 für einen gesicherten, noch unvollständigen Fortsetzungsstand verwenden. | SR-NEED-0007, SR-NEED-0008 | SR-VER-0013 | SR-TC-0185 |
| SR-REQ-0186 | SpecRoad MUSS Farbausgabe deaktivieren, wenn stdout kein TTY ist, `NO_COLOR` gesetzt ist oder `--no-color` verwendet wird. | SR-NEED-0007, SR-NEED-0001 | SR-VER-0013 | SR-TC-0186 |
| SR-REQ-0187 | Informationen DÜRFEN NICHT ausschließlich durch Farbe codiert werden. | SR-NEED-0001, SR-NEED-0007 | SR-VER-0013 | SR-TC-0187 |
| SR-REQ-0188 | Read-only-Befehle MÜSSEN ohne Schreibzugriff auf den Projektroot und ohne vorausgesetzte Cache-Dateien funktionieren, sofern keine unvollständige Transaktion Recovery erfordert und keine explizite Ausgabedatei innerhalb des Projektroots angefordert wird. | SR-NEED-0007, SR-NEED-0011 | SR-VER-0013 | SR-TC-0188 |
| SR-REQ-0189 | Jeder tatsächlich ausgeführte `normative_write` MUSS seine normativen Zieldateien ausschließlich über Staging, Synchronisation und die Journal-/Commit-Sequenz aus Anhang C veröffentlichen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0189 |
| SR-REQ-0190 | Git-unabhängige Befehle MÜSSEN in einem SpecRoad-Projekt ohne `.git`-Verzeichnis funktionieren. | SR-NEED-0001, SR-NEED-0011 | SR-VER-0013 | SR-TC-0190 |
| SR-REQ-0191 | Ein Vergleich oder Merge gegen einen Git-Ref MUSS dessen SpecRoad-Dateien über feste, shellfreie Git-Plumbing-Aufrufe lesen, ohne Hooks, Pager, externe Diff-/Filterprozesse, Checkout, Branch-, Index- oder Arbeitsbaumänderung. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0011 | SR-VER-0013 | SR-TC-0191 |
| SR-REQ-0192 | Ein schreibender Proposal-Befehl MUSS bei nicht zur erwarteten Basis passenden Änderungen innerhalb der `managed_paths` mit Exit Code 6 abbrechen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0013 | SR-TC-0192 |
| SR-REQ-0193 | Die Option `--changed-only --against <REF>` MUSS Validierung und Linting auf geänderte Artefakte einschließlich der für deren Regeln erforderlichen Abhängigkeiten begrenzen. | SR-NEED-0007, SR-NEED-0003 | SR-VER-0013 | SR-TC-0193 |
| SR-REQ-0194 | `specroad version --format json` MUSS mindestens Programmversion, Buildkennung, tatsächlich verwendete Python-Version, niedrigste unterstützte Python-Version, unterstützte Schema-Versionen und unterstützte Ausgabeformatversionen ausgeben. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0013 | SR-TC-0194 |

### 12.14 Qualitäts-, Sicherheits- und Performanceanforderungen

Diese Anforderungen definieren messbare Eigenschaften und Sicherheitsgrenzen auf der Referenzplattform.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0195 | Alle Core-Befehle und der ausdrücklich ausgelieferte py3langid-Adapter MÜSSEN nach Bereitstellung ihrer jeweils deklarierten Laufzeitpakete ohne Netzwerkverbindung nutzbar sein. | SR-NEED-0011, SR-NEED-0007 | SR-VER-0014 | SR-TC-0195 |
| SR-REQ-0196 | SpecRoad DARF NICHT in Version 0.2 Telemetrie erfassen oder übertragen. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0014 | SR-TC-0196 |
| SR-REQ-0197 | SpecRoad DARF NICHT Geheimnisse, Umgebungsvariablen oder vollständige Dateiinhalte außerhalb explizit angeforderter Ergebnisfelder in Logs oder Diagnosen ausgeben. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0014 | SR-TC-0197 |
| SR-REQ-0198 | Jeder gelesene oder geschriebene Projektpfad MUSS nach kanonischer Auflösung innerhalb des Projektroots liegen. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0014 | SR-TC-0198 |
| SR-REQ-0199 | SpecRoad MUSS Symlinks ablehnen, deren aufgelöstes Ziel außerhalb des Projektroots liegt. | SR-NEED-0011, SR-NEED-0009 | SR-VER-0014 | SR-TC-0199 |
| SR-REQ-0200 | SpecRoad DARF NICHT beliebige Shellbefehle oder ausführbaren Code aus Profilen, Regeln, Artefakten oder Anhängen starten. | SR-NEED-0011, SR-NEED-0008 | SR-VER-0014 | SR-TC-0200 |
| SR-REQ-0201 | SpecRoad MUSS nicht aus der vertrauenswürdigen eingebauten Ausführungsliste stammende Plugin- oder Analyzer-Ausführungsdeklarationen vor dem Laden oder Starten zurückweisen; reine Resultatdateien folgen dem Importvertrag aus Anhang T. | SR-NEED-0011, SR-NEED-0012 | SR-VER-0014 | SR-TC-0201 |
| SR-REQ-0202 | SpecRoad MUSS alle Größen- und Komplexitätsgrenzen nach der abschließenden Klassifikation in Anhang O.1 als weiches Arbeitsziel, expliziten Fachscope oder harte Sicherheits-/Formatgrenze behandeln. | SR-NEED-0011, SR-NEED-0007, SR-NEED-0012 | SR-VER-0014 | SR-TC-0202 |
| SR-REQ-0203 | Bei einer Überschreitung eines weichen Arbeitsbudgets MUSS SpecRoad die adaptive Fortsetzungsentscheidung aus Anhang O.4 statt eines budgetbedingten Fehlerabbruchs anwenden. | SR-NEED-0011, SR-NEED-0007 | SR-VER-0014 | SR-TC-0203 |
| SR-REQ-0204 | Ein Prozessabbruch oder interner Fehler während eines normativen Schreibbefehls DARF NICHT einen unvollständigen Zustand als regulär ladbaren Projektstand hinterlassen. | SR-NEED-0011, SR-NEED-0009, SR-NEED-0013 | SR-VER-0019 | SR-TC-0204 |
| SR-REQ-0205 | Normative Writes und Recovery-Writes MÜSSEN die ihrer Befehlsklasse zugeordnete exklusive Projektlockart nach Kapitel 11.7 verwenden. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0205 |
| SR-REQ-0206 | Ein Lock MUSS mindestens Lock-ID, Prozesskennung, Prozessstartkennung, Hostkennung, Erstellungszeit, Befehl, Request-ID und Transaktions-ID enthalten und ausschließlich durch den in Kapitel 11.2 und Anhang C definierten Recovery-Vertrag entfernbar sein. | SR-NEED-0011, SR-NEED-0009, SR-NEED-0013 | SR-VER-0019 | SR-TC-0206 |
| SR-REQ-0207 | Bei identischem normativem Modell, identischen expliziten Fachinputs, identischer semantischer Konfiguration, Toolversion und Profilen MÜSSEN abgeschlossene Fachoperationen dieselbe fachliche Ergebnisprojektion liefern; Live-Analyzer binden zusätzlich den Enginefingerprint nach Anhang T.9. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0015 | SR-TC-0207 |
| SR-REQ-0208 | Normative Verarbeitung und generierte Ausgaben MÜSSEN unabhängig von System-Locale und lokaler Zeitzone sein. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0015 | SR-TC-0208 |
| SR-REQ-0209 | Version 0.2 MUSS auf Linux x86-64 in einer nicht privilegierten Benutzerumgebung sowohl aus der entpackten Modul-Distribution als auch aus der Python-Zipapp ohne systemweite Installation ausführbar sein. | SR-NEED-0001, SR-NEED-0012, SR-NEED-0013 | SR-VER-0027 | SR-TC-0209 |
| SR-REQ-0210 | Auf der Referenzplattform im Ressourcenprofil `standard` MUSS `specroad validate` ein Projekt mit 1.000 Artefakten, 5.000 Beziehungen und 10 MiB normativen Daten in höchstens 2 Sekunden vollständig prüfen. | SR-NEED-0007, SR-NEED-0001 | SR-VER-0015 | SR-TC-0210 |
| SR-REQ-0211 | Auf der Referenzplattform im Ressourcenprofil `standard` MUSS `specroad validate` ein Projekt mit 10.000 Artefakten, 50.000 Beziehungen und 100 MiB normativen Daten in höchstens 10 Sekunden vollständig prüfen. | SR-NEED-0007, SR-NEED-0010 | SR-VER-0015 | SR-TC-0211 |
| SR-REQ-0212 | Bei dem definierten 10.000-Artefakte-Benchmark im Ressourcenprofil `standard` DARF der maximale Resident Set Size 1 GiB NICHT überschreiten. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0015 | SR-TC-0212 |
| SR-REQ-0213 | `specroad show`, `query`, `trace` mit Tiefe 3 und direkte `impact`-Analyse MÜSSEN im 10.000-Artefakte-Benchmark im Ressourcenprofil `standard` jeweils in höchstens 2 Sekunden antworten. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0015 | SR-TC-0213 |
| SR-REQ-0214 | Maschinenlesbare Ausgabeformate MÜSSEN eine eigene SemVer-kompatible `format_version` besitzen; inkompatible Änderungen erfordern eine neue Major-Version dieses Ausgabeformats. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0013 | SR-TC-0214 |
| SR-REQ-0215 | Die Referenztests des Projekts MÜSSEN mindestens Unit-, Schema-, Property-, Golden-File-, CLI-Integration-, Sicherheits- und End-to-End-Tests enthalten. | SR-NEED-0012, SR-NEED-0007 | SR-VER-0016 | SR-TC-0215 |

### 12.15 Ergänzende CLI-Operationsverträge

Diese Anforderungen schließen konkrete Authoring-, Review- und Recovery-Verträge mit stabilen IDs ab.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0216 | `specroad artifact create <TYPE> [options]` MUSS unter exklusivem Lock eine kryptografisch zufällige, noch nicht vergebene ID nach `random128-v1` auswählen. | SR-NEED-0001, SR-NEED-0009, SR-NEED-0016 | SR-VER-0018 | SR-TC-0216 |
| SR-REQ-0217 | `specroad artifact create` MUSS alle für den gewählten Typ erforderlichen Draft-Felder über typspezifische Optionen, stdin oder `--input <FILE>` verlangen, daraus über den gemeinsamen Change-Plan atomar ein schema-gültiges Artefakt im Reifegrad `draft` schreiben und dessen ID sowie projektrelativen Pfad ausgeben. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0013 | SR-VER-0018 | SR-TC-0217 |
| SR-REQ-0218 | `specroad lifecycle transition <ID> --to retired --reason <TEXT>` MUSS die atomare Stilllegung mit genau einer Revisionsänderung, dem Endzustand `retired`, unveränderter Fachprojektion und dem gebundenen Grund-/Akteursnachweis nach Kapitel 9.6.3 ausführen. | SR-NEED-0002, SR-NEED-0009, SR-NEED-0013 | SR-VER-0018 | SR-TC-0218 |
| SR-REQ-0219 | `specroad proposal review <FILE> --decision approved\|rejected` MUSS die Entscheidung an Proposal-ID, `content_revision`, `content_sha256`, Basis-Modellwurzel und Change-Plan-Hash binden. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0012 | SR-TC-0219 |
| SR-REQ-0220 | `specroad baseline show <ID>` MUSS das gespeicherte Baseline-Manifest und einen neu berechneten Integritätsstatus ausgeben, ohne den Arbeitsstand zu verändern. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0011 | SR-TC-0220 |
| SR-REQ-0221 | Die Befehlsgruppe `specroad lock` MUSS mit `status` die vollständigen Lock-Metadaten ausgeben und mit `recover --force` aktive Eigentümer desselben Hosts abweisen sowie bei fremdem oder nicht prüfbarem Host zusätzlich `--accept-remote-risk` verlangen. | SR-NEED-0011, SR-NEED-0007, SR-NEED-0013 | SR-VER-0019 | SR-TC-0221 |
| SR-REQ-0222 | Die Option `--quiet` MUSS ausschließlich Fortschritts- und Erfolgshinweise unterdrücken und Ergebnisdaten, Warnungen, Fehler sowie Pflichtfelder eines JSON- beziehungsweise SARIF-Dokuments vollständig erhalten. | SR-NEED-0007, SR-NEED-0008 | SR-VER-0013 | SR-TC-0222 |

### 12.16 Python-, Laufzeit- und Sandbox-Portabilität

Der vollständige Core bleibt in eingeschränkten Python-Linux-Umgebungen offline und installationsfrei ausführbar.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0223 | Der SpecRoad Core MUSS vollständig unter CPython 3.10 ausführbar sein; CPython 3.10 ist die niedrigste unterstützte Laufzeitversion. | SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0223 |
| SR-REQ-0224 | Die entpackte Core-Distribution und die Core-Zipapp DÜRFEN NICHT für eine nicht Git-spezifische Core-Funktion extern zu installierende Laufzeitpakete voraussetzen; die PatchHarbor-Runtime für das Transportprofil MUSS offline mitgeliefert und ausschließlich bei dessen Nutzung geladen werden, während Analyzer-Zusatzvoraussetzungen getrennt Anhang T.6 folgen. | SR-NEED-0008, SR-NEED-0011, SR-NEED-0012 | SR-VER-0027 | SR-TC-0224 |
| SR-REQ-0225 | Die zwingenden Umgebungsvoraussetzungen nicht Git-spezifischer Core-Funktionen DÜRFEN über eine unterstützte Python-Laufzeit, Leserechte für Distribution und Projekteingaben sowie die jeweils erforderlichen Schreibrechte für Projekt-, Ausgabe- und Temporärpfade nicht hinausgehen; die ausdrücklich Git-spezifische lokale Transportseite nach Anhang W MUSS ihre zusätzlichen Voraussetzungen getrennt ausweisen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0011 | SR-VER-0017 | SR-TC-0225 |
| SR-REQ-0226 | Jedes Release MUSS funktional äquivalente selbstenthaltene Modul- und Zipapp-Core-Distributionen bereitstellen, die ohne Installation zusätzlicher Pakete starten; die zusätzliche Language-Detection-Distribution folgt Anhang T.6. | SR-NEED-0001, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0226 |
| SR-REQ-0227 | Sämtliche in Kapitel 11.2 aufgeführten Kernfunktionen MÜSSEN vollständig über nichtinteraktive CLI-Aufrufe ausführbar sein und bei fehlenden Eingaben eine strukturierte Nutzungsdiagnose statt einer Rückfrage erzeugen. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0008 | SR-VER-0027 | SR-TC-0227 |
| SR-REQ-0228 | Der Mensch-KI-Roundtrip aus `SR-SCN-0013` MUSS KI-erzeugte normative Änderungen über die Folge `proposal create`, `proposal change`, `proposal validate`, `proposal check`, menschliches `proposal review` und `proposal apply` führen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0017 | SR-TC-0228 |
| SR-REQ-0229 | Nicht ausdrücklich Git-spezifische Kernbefehle DÜRFEN NICHT Bash, GNU-Utilities, eine aktivierte virtuelle Umgebung, einen Paketmanager, einen Compiler oder einen dauerhaft laufenden SpecRoad-Dienst voraussetzen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0012 | SR-VER-0017 | SR-TC-0229 |
| SR-REQ-0230 | Die Release-Abnahme MUSS beide portablen Distributionen in sauberen, nicht privilegierten, netzwerkisolierten Linux-x86-64-Umgebungen mit jeder als unterstützt deklarierten CPython-Minor-Version und ohne installierte Drittanbieter-Python-Pakete durch den vollständigen Sandbox-Roundtrip prüfen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0230 |

### 12.17 Vollständiges CLI-Authoring und gemeinsamer Change Plan

Jede normale Bearbeitung ist über erstklassige CLI-Befehle möglich und verwendet dieselbe Änderungsengine.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0231 | Jeder normative Schreibvorgang MUSS vor seiner Ausführung in einen Change Plan nach Kapitel 10.1 und 10.2 überführt werden. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0013 | SR-VER-0018 | SR-TC-0231 |
| SR-REQ-0232 | `specroad artifact update <ID>` MUSS RFC-6902-Patches sowie die Komfortoptionen `--set <JSON-POINTER>=<JSON-VALUE>` und `--unset <JSON-POINTER>` unterstützen und eine erwartete Revision oder einen erwarteten Hash verlangen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0013 | SR-VER-0018 | SR-TC-0232 |
| SR-REQ-0233 | `specroad relation add <SOURCE-ID> --type <TYPE> --target <TARGET-ID>` MUSS eine typgültige Beziehung mit eigener `relation_id` über den gemeinsamen Change Plan anlegen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0013 | SR-VER-0018 | SR-TC-0233 |
| SR-REQ-0234 | `specroad relation remove <SOURCE-ID> --relation-id <RELATION-ID> --reason <TEXT>` MUSS genau die bezeichnete Beziehung entfernen, die Quellrevision erhöhen und Grund sowie Akteur im Auditbericht erfassen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0009 | SR-VER-0018 | SR-TC-0234 |
| SR-REQ-0235 | `specroad lifecycle transition <ID> --to <MATURITY>` MUSS die Typ-, Übergangs-, Pflichtangaben- und Kombinationsregeln aus Kapitel 9.6.1 bis 9.6.3 auf den vollständigen Change Plan anwenden. | SR-NEED-0001, SR-NEED-0002, SR-NEED-0013 | SR-VER-0018 | SR-TC-0235 |
| SR-REQ-0236 | Ein direkter normativer Authoring-Befehl eines KI-Akteurs MUSS ohne `--as-proposal` mit Exit Code 7 abgewiesen werden, ausgenommen die in Kapitel 11.10 ausdrücklich erlaubte Proposal-Verwaltung und Übernahme eines bereits menschlich freigegebenen Proposals. | SR-NEED-0008, SR-NEED-0011, SR-NEED-0013 | SR-VER-0018 | SR-TC-0236 |
| SR-REQ-0237 | Die Option `--dry-run` MUSS den vollständigen gebundenen Change Plan, semantischen Diff, direkten Impact, Diagnosen und die erwartete Modellwurzel ausgeben. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0013 | SR-VER-0018 | SR-TC-0237 |
| SR-REQ-0238 | Jeder tatsächlich ausgeführte `normative_write` MUSS den vollständigen geplanten Endstand einschließlich aller abhängigen Regeln vor `prepared` gegen seine befehlsspezifischen Gates validieren; die eng begrenzte Review-Ergebnisausnahme ist ausschließlich in Kapitel 11.13 definiert. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0013 | SR-VER-0018 | SR-TC-0238 |
| SR-REQ-0239 | Operationen eines Change Plans MÜSSEN in deklarierter Reihenfolge gegen den jeweils vorherigen Zwischenstand ausgewertet werden. | SR-NEED-0003, SR-NEED-0011, SR-NEED-0013 | SR-VER-0018 | SR-TC-0239 |
| SR-REQ-0240 | Schreibende Authoring-Befehle MÜSSEN strukturierte Eingaben sowohl über `--input <FILE>` als auch über `--input -` von stdin akzeptieren und bei `--format json` ausschließlich ein versioniertes Ergebnisobjekt auf stdout ausgeben. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0008 | SR-VER-0018 | SR-TC-0240 |
| SR-REQ-0241 | Jeder tatsächlich ausgeführte oder abgewiesene `normative_write` MUSS den Auditbericht seiner Befehlsklasse nach Kapitel 11.7 ausgeben; ein noch offener Arbeitsschritt weist statt eines Erfolgsreceipts den Fortsetzungsstand aus. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0013 | SR-VER-0018 | SR-TC-0241 |
| SR-REQ-0242 | Jeder direkte Authoring-Befehl MUSS mit `--as-proposal` anstelle der sofortigen Ausführung ein semantisch gleichwertiges Proposal im Status `draft` erzeugen können. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0013 | SR-VER-0018 | SR-TC-0242 |
| SR-REQ-0243 | Die Option `--fail-on-change` MUSS für `diff`, `format --check`, `migrate plan`, `merge plan`, `import plan` und schreibende Dry-Runs Exit Code 1 liefern, wenn der Befehl eine Änderung feststellen oder erzeugen würde, und andernfalls Exit Code 0. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0018 | SR-TC-0243 |

### 12.18 Kollisionsresistente IDs und parallele Arbeitsstände

Identitäten dürfen bei paralleler Arbeit in Branches, Worktrees und Chatbot-Sandboxen nicht von einer zentralen Sequenz abhängen.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0244 | Das ID-Schema `random128-v1` MUSS `<IDENTIFIER>` als exakt 26 Zeichen des Crockford-Base32-Alphabets `0123456789ABCDEFGHJKMNPQRSTVWXYZ` codieren. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0018 | SR-TC-0244 |
| SR-REQ-0245 | Neue Artefakt- und Relations-IDs MÜSSEN mit einem kryptografisch sicheren Zufallszahlengenerator der unterstützten Python-Standardbibliothek erzeugt werden. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0016 | SR-VER-0018 | SR-TC-0245 |
| SR-REQ-0246 | SpecRoad MUSS eine zufällig erzeugte ID vor der Verwendung gegen alle aktuellen, archivierten und reservierten IDs des Projekts prüfen und bei einer Kollision ohne sichtbare Teiländerung erneut erzeugen. | SR-NEED-0002, SR-NEED-0009, SR-NEED-0016 | SR-VER-0018 | SR-TC-0246 |
| SR-REQ-0247 | Veränderbare migrierte Artefakte MÜSSEN `id_scheme=legacy-sequential-v1` in ihren 0.2-Daten tragen; bei unveränderbaren Legacy-Ressourcen wird diese Kennzeichnung ausschließlich im Manifest nach Anhang Q geführt. | SR-NEED-0002, SR-NEED-0014, SR-NEED-0016 | SR-VER-0018 | SR-TC-0247 |
| SR-REQ-0248 | Eine regulär neu erzeugte Beziehung MUSS eine unabhängig zufällig erzeugte `relation_id` nach `random128-v1` besitzen; migrierte Bestandsrelationen folgen ausschließlich SR-REQ-0273 und Anhang Q. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0018 | SR-TC-0248 |
| SR-REQ-0249 | Die Erzeugung neuer Identitäten DARF NICHT einen zentralen Zähler, Server, Netzwerkdienst, Git-Branch oder exklusiven projektübergreifenden Namensraum voraussetzen. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0016 | SR-VER-0018 | SR-TC-0249 |
| SR-REQ-0250 | SpecRoad MUSS beim Import und semantischen Merge unterscheiden, ob eine gleiche ID dieselbe Historie, eine zulässige identische Kopie oder eine fachlich kollidierende unabhängige Erzeugung bezeichnet. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0026 | SR-TC-0250 |
| SR-REQ-0251 | Ein Artefakt DARF ein optionales, nicht identitätsstiftendes `display_id` besitzen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0016 | SR-VER-0018 | SR-TC-0251 |

### 12.19 Transaktionsjournal und Recovery

Mehrdateiänderungen sind nach erfolgreicher Rückkehr vollständig und nach abnormalem Abbruch deterministisch wiederherstellbar.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0252 | Jeder tatsächlich ausgeführte `normative_write` MUSS vor der ersten normativen Veröffentlichung ein Journal nach Anhang C unter `.specroad/transactions/<TRANSACTION-ID>/journal.json` anlegen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0252 |
| SR-REQ-0253 | Das Transaktionsjournal MUSS für jede betroffene Datei logischen Pfad, Existenz vor der Operation, Vorher-Hash, Nachher-Hash, Staging-Pfad, optionalen Before-Image-Pfad und Veröffentlichungsstatus enthalten. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0253 |
| SR-REQ-0254 | Vor dem Wechsel in `prepared` MUSS SpecRoad alle neuen Dateien und erforderlichen Before Images vollständig schreiben, hashen, gegen den Change Plan prüfen und auf der Referenzplattform mittels `fsync` dauerhaft synchronisieren. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0254 |
| SR-REQ-0255 | Nach `prepared` MUSS SpecRoad den Journalzustand `committing` dauerhaft speichern und jede atomare Dateiveröffentlichung einzeln im Journal quittieren, bevor die nächste Datei veröffentlicht wird. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0255 |
| SR-REQ-0256 | Ein normaler Projektbefehl MUSS vor dem Laden des kanonischen Modells den begrenzten Transaktions-Preflight einschließlich der befehlsklassenabhängigen Recovery- oder Diagnoseentscheidung aus Anhang N.2–N.3 durchführen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0256 |
| SR-REQ-0257 | Eine Transaktion in `building` oder `prepared` MUSS ohne Veröffentlichung verworfen werden können. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0257 |
| SR-REQ-0258 | Wenn alle Nachher-Hashes einer unterbrochenen Transaktion vorhanden sind und dem Journal entsprechen, MUSS Recovery fehlende Audit- und Request-Receipts aus dem Journal rekonstruieren und die Transaktion anschließend als `committed` abschließen, statt den vollständig veröffentlichten Zustand zurückzurollen. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0258 |
| SR-REQ-0259 | Eine erfolgreich abgeschlossene oder zurückgerollte Transaktion MUSS einen unveränderbaren Abschlussbeleg unter `.specroad/transactions/receipts/` hinterlassen und danach das Entfernen temporärer Payloads erlauben. | SR-NEED-0009, SR-NEED-0013 | SR-VER-0019 | SR-TC-0259 |
| SR-REQ-0260 | Fehlende, manipulierte oder widersprüchliche notwendige Journal-, Before-Image- oder Staging-Daten MÜSSEN als `corrupt` diagnostiziert und nach dem Schreibberechtigungs- und Sperrvertrag aus Anhang N.3 behandelt werden. | SR-NEED-0011, SR-NEED-0009, SR-NEED-0013 | SR-VER-0019 | SR-TC-0260 |
| SR-REQ-0261 | Die Referenztests MÜSSEN einen kontrollierten Prozessabbruch nach jeder dauerhaften Journal- und Dateisystemgrenze injizieren und nach Recovery jeweils exakt die Basis- oder die vollständige Zielmodellwurzel nachweisen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0261 |
| SR-REQ-0262 | `specroad recover status` MUSS Zustand, Journalhash, Basiswurzel, erwartete Zielwurzel, veröffentlichte Einträge und zulässige Recovery-Aktionen jeder unvollständigen Transaktion ausgeben. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0019 | SR-TC-0262 |

### 12.20 Schema- und Datenmigration

Langlebige Projekte werden über geplante, verlustbewusste, gesicherte und verifizierbare Migrationen weiterentwickelt.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0263 | `specroad migrate plan [--to <SCHEMA-VERSION>]` MUSS aktuelle und Zielversion, geordnete Migrationsschritte, betroffene Dateien, erwartete Verluste, neue Pflichtfelder, einen ausführbaren Change Plan und die erwartete Zielmodellwurzel ausgeben, ohne Projektdateien zu verändern. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0014 | SR-VER-0020 | SR-TC-0263 |
| SR-REQ-0264 | `specroad migrate apply --to <SCHEMA-VERSION> [--plan <FILE>]` MUSS ausschließlich einen vollständig unterstützten, zusammenhängenden Pfad aus versionierten Migrationsschritten ausführen und ein übergebenes Planfile exakt an die aktuelle Basis und Zielversion binden. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0014 | SR-VER-0020 | SR-TC-0264 |
| SR-REQ-0265 | Jeder Migrationsschritt MUSS eindeutige Quell- und Zielversion, Vorbedingungen, Transformation, Nachbedingungen, Reversibilitätsangabe und eigene Testvektoren besitzen. | SR-NEED-0009, SR-NEED-0012, SR-NEED-0014 | SR-VER-0020 | SR-TC-0265 |
| SR-REQ-0266 | Vor einer Migration MUSS SpecRoad ein verifiziertes, deterministisches Projektbundle des vollständigen Ausgangszustands erzeugen und dessen Pfad und Hash im Migrationsbericht speichern. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0014 | SR-VER-0020 | SR-TC-0266 |
| SR-REQ-0267 | Eine Migration MUSS den gemeinsamen Change-Plan-, Lock-, Validierungs-, Journal- und Recovery-Vertrag verwenden, ohne einen teilweisen Schema-Mischzustand als regulären Projektstand zu veröffentlichen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0014 | SR-VER-0020 | SR-TC-0267 |
| SR-REQ-0268 | Eine als verlustfrei deklarierte Migration MUSS alle normativen Informationen, unbekannten schema-gültigen Erweiterungen, IDs, Provenienz, Anhänge und Auditbezüge semantisch erhalten. | SR-NEED-0009, SR-NEED-0012, SR-NEED-0014 | SR-VER-0020 | SR-TC-0268 |
| SR-REQ-0269 | Ein Migrationsschritt mit möglichem Informationsverlust MUSS ohne vollständige Angabe aller betroffenen `--accept-loss <LOSS-ID>` standardmäßig abbrechen. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0020 | SR-TC-0269 |
| SR-REQ-0270 | Eine wiederholte Migration auf dieselbe bereits erreichte Zielversion MUSS ohne semantische Änderung erfolgreich und idempotent enden oder eindeutig als nicht erforderlich gemeldet werden. | SR-NEED-0007, SR-NEED-0014 | SR-VER-0020 | SR-TC-0270 |
| SR-REQ-0271 | `specroad migrate verify` MUSS Quellbundle, Migrationsbericht, Zielschemas, Zielmodellwurzel, Referenzen, Anhänge und deklarierte Invarianten prüfen, ohne den Zielstand zu verändern. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0020 | SR-TC-0271 |
| SR-REQ-0272 | Version 0.2 MUSS eine verlustfreie Migration von Schema 0.1.0 nach 0.2.0 nach Anhang Q bereitstellen, die veränderbare Artefakte ergänzt und unveränderbare Nachweise unter Erhalt ihrer Originalbytes einbindet. | SR-NEED-0001, SR-NEED-0012, SR-NEED-0014 | SR-VER-0020 | SR-TC-0272 |
| SR-REQ-0273 | Die Migration 0.1.0 nach 0.2.0 MUSS Relations-IDs reproduzierbar nach der Ableitungs- und Legacy-Projektionsregel in Anhang Q bilden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0020 | SR-TC-0273 |
| SR-REQ-0274 | SpecRoad DARF ein Downgrade nur anbieten, wenn ein ausdrücklich implementierter verlustfreier Rückweg existiert. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0014 | SR-VER-0020 | SR-TC-0274 |

### 12.21 Suspect Relations und fachliche Relationsreviews

Relationsgültigkeit und fachliche Bestätigung werden an konkrete Endpunkthashes gebunden.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0275 | Ein `relation_review`-Artefakt MUSS die geprüfte `relation_id`, den kanonischen Relationsinhaltshash, Quell- und Ziel-ID, deren Revision und vollständigen Artefakthash, deren `relation_context_hash-v1`, Reviewer, Entscheidung, Zeitstempel und optionalen Kommentar enthalten. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0021 | SR-TC-0275 |
| SR-REQ-0276 | SpecRoad MUSS für jede gespeicherte Relation den berechneten Reviewstatus `unreviewed`, `current`, `suspect` oder `invalid` aus Relationsinhaltshash und den beiden `relation_context_hash-v1` bestimmen, ohne diesen Status als zweite normative Kopie in der Relation zu speichern. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0016 | SR-VER-0021 | SR-TC-0276 |
| SR-REQ-0277 | Eine strukturell gültige Relation MUSS ohne jedes frühere Review `unreviewed` und bei früherem, aber nicht mehr passendem Review `suspect` gemäß Anhang J.3 sein. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0021 | SR-TC-0277 |
| SR-REQ-0278 | `specroad relation review <SOURCE-ID> --relation-id <RELATION-ID> --decision confirmed\|rejected` MUSS den vollständig gebundenen menschlichen Review-Vorgang einschließlich atomarer Freigabefolgen, Diagnosen und Exit-Ergebnis nach Kapitel 11.13 ausführen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0016 | SR-VER-0021 | SR-TC-0278 |
| SR-REQ-0279 | Eine Änderung am reviewrelevanten Inhalt des Quell- oder Zielartefakts MUSS jedes zuvor `current` Relationsreview auf Basis abweichender `relation_context_hash-v1` als `suspect` erscheinen lassen. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0021 | SR-TC-0279 |
| SR-REQ-0280 | Eine Relation MUSS `invalid` sein, wenn ihr Ziel fehlt, ihre Quell-Ziel-Typkombination unzulässig ist, ihre kanonische Speicherung verletzt ist oder das jüngste aktuelle Review die Entscheidung `rejected` trägt. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0016 | SR-VER-0021 | SR-TC-0280 |
| SR-REQ-0281 | `specroad relation status [<ID>]` MUSS alle Relationsreviewzustände einschließlich auslösender Revisionen, letzter Reviewentscheidung und erforderlicher Reparatur stabil sortiert ausgeben. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0007 | SR-VER-0021 | SR-TC-0281 |
| SR-REQ-0282 | Aktive Profile MÜSSEN je Relationstyp und Artefaktreifegrad festlegen können, ob `unreviewed` oder `suspect` als `info`, `warning` oder `error` gilt. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0021 | SR-TC-0282 |
| SR-REQ-0283 | Ein Requirement DARF den Reifegrad `approved` nur bei durchgehend `current` bewerteten profilabhängigen Pflichtrelationen behalten; die atomare Rücknahme bei negativem Relationsreview folgt Kapitel 11.13. | SR-NEED-0003, SR-NEED-0006, SR-NEED-0016 | SR-VER-0021 | SR-TC-0283 |
| SR-REQ-0284 | `impact`, `diff`, `traceability`, `coverage` und `release readiness` MÜSSEN unreviewed, suspect und invalid Relations getrennt ausweisen und deren betroffene Artefakte erklären. | SR-NEED-0003, SR-NEED-0005, SR-NEED-0006 | SR-VER-0021 | SR-TC-0284 |
| SR-REQ-0285 | Import, Migration und Merge MÜSSEN erhaltene Relationsreviews nur dann als `current` übernehmen, wenn Relation sowie Quell- und Ziel-Kontextprojektion nach der Operation exakt den im Review gebundenen Hashes entsprechen; andernfalls erscheinen sie als `suspect` oder `unreviewed`. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0021 | SR-TC-0285 |

### 12.22 Deklarative Regelsprache SRX 1.0

Profile, Regeln, Views und Gültigkeitsbedingungen verwenden eine begrenzte, versionierte JSON-AST-Sprache.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0286 | Profil- und Lintbedingungen MÜSSEN in der versionierten, rein deklarativen JSON-AST-Sprache `SRX 1.0` gespeichert werden. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0014 | SR-VER-0022 | SR-TC-0286 |
| SR-REQ-0287 | SRX MUSS ausschließlich auf einem expliziten Auswertungskontext aus aktuellem Artefakt, effektiver Konfiguration, aktiven Profilen, berechneten Relationssichten und unveränderlichen Projektstatistiken arbeiten. | SR-NEED-0002, SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0287 |
| SR-REQ-0288 | SRX 1.0 MUSS mindestens die Operatoren `literal`, `field`, `exists`, `not`, `and`, `or`, `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `contains`, `starts_with`, `ends_with`, `length`, `count`, `any`, `all`, `none`, `add`, `subtract`, `multiply` und `divide` definieren. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0288 |
| SR-REQ-0289 | Der Operator `field` MUSS Werte ausschließlich über RFC-6901-JSON-Pointer in einem benannten Kontextobjekt lesen. | SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0289 |
| SR-REQ-0290 | SRX MUSS jeden Operator ausschließlich mit den in Anhang B zugelassenen Operandentypen auswerten. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0290 |
| SR-REQ-0291 | Ein fehlender Feldwert MUSS als interner Wert `missing` mit den in Anhang B.3 definierten Ergebnissen für `exists`, `eq`, `ne`, `lt`, `lte`, `gt` und `gte` behandelt werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0291 |
| SR-REQ-0292 | `any`, `all` und `none` MÜSSEN den in Anhang B.4 definierten geordneten Elementkontext und die dort bestimmten Ergebnisse für leere Arrays verwenden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0292 |
| SR-REQ-0293 | SRX MUSS die begrenzten Graphoperatoren `relation_count`, `has_relation`, `reachable` und `incoming_count` unterstützen. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0012 | SR-VER-0022 | SR-TC-0293 |
| SR-REQ-0294 | `and` und `or` MÜSSEN von links nach rechts kurzschließend auswerten. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0022 | SR-TC-0294 |
| SR-REQ-0295 | Die SRX-Konfiguration MUSS AST-Knoten und Strukturtiefe als explizite Strukturgrenzen sowie Iterations-, Graph- und Auswertungsschrittzahlen als weiche fortsetzbare Arbeitsziele nach Anhang O.1 unterscheiden. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0295 |
| SR-REQ-0296 | SRX DARF NICHT reguläre Ausdrücke, dynamische Importe, Reflection, Dateizugriffe, Netzwerkzugriffe, Zeit- oder Zufallsquellen, Shellbefehle, benutzerdefinierten Code oder nicht deterministische Operatoren enthalten. | SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0296 |
| SR-REQ-0297 | Ein SRX-Typ-, Versions-, Operator- oder Auswertungsfehler MUSS Regel-ID, JSON Pointer des Ausdrucksknotens, erwartete und tatsächliche Typen sowie eine Reparaturempfehlung ausgeben. | SR-NEED-0002, SR-NEED-0007 | SR-VER-0022 | SR-TC-0297 |
| SR-REQ-0298 | Die Referenzimplementierung MUSS die versionierten Positiv-, Negativ-, Grenzwert- und Fehlervektoren sämtlicher SRX-Operatoren einschließlich der expliziten Zahlenpolicy aus Anhang U nachweisen; freigegebene inkompatible Semantikänderungen verlangen eine neue SRX-Major-Version. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0014 | SR-VER-0022 | SR-TC-0298 |

### 12.23 Dokumente, Abschnitte und Inhaltsblöcke

Menschenlesbare Spezifikationen werden bewusst komponiert, ohne die fachliche Source of Truth zu duplizieren.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0299 | Ein `document`-Artefakt MUSS mindestens Zweck, Zielgruppe, Sprache und Render-Policy enthalten. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0299 |
| SR-REQ-0300 | Ein `section`-Artefakt MUSS über genau eine eingehende `contains`-Relation einem Dokument oder Elternabschnitt zugeordnet sein und Titel sowie ausgehende `contains`-Relationen mit `position` für Kindabschnitte und Inhaltsblöcke verwenden. | SR-NEED-0001, SR-NEED-0015 | SR-VER-0023 | SR-TC-0300 |
| SR-REQ-0301 | Ein `content_block`-Artefakt MUSS genau eine Art aus `prose`, `artifact_ref`, `query`, `table`, `admonition`, `page_break` oder `include_document` besitzen und die dafür definierten Pflichtfelder erfüllen. | SR-NEED-0001, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0301 |
| SR-REQ-0302 | Ein Inhaltsblock der Art `artifact_ref` MUSS genau eine ausgehende `references`-Relation zum Zielartefakt besitzen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0302 |
| SR-REQ-0303 | Die Reihenfolge von Abschnitten und Inhaltsblöcken MUSS ausschließlich aus `position` der gespeicherten `contains`-Relationen und bei Gleichstand aus Ziel-ID und Relation-ID deterministisch berechnet werden. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0303 |
| SR-REQ-0304 | Ein Prosa-Inhaltsblock MUSS UTF-8-Markdown im dokumentierten CommonMark-kompatiblen Kernsubset speichern. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0015 | SR-VER-0023 | SR-TC-0304 |
| SR-REQ-0305 | Ein Query-Inhaltsblock MUSS eine deklarative Query oder View-ID referenzieren und beim Rendern ausschließlich aus dem gebundenen Modellstand erzeugt werden. | SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0305 |
| SR-REQ-0306 | Ein Tabellen-Inhaltsblock MUSS Spalten, Sortierung und Zeilenquelle deklarativ definieren. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0306 |
| SR-REQ-0307 | Dokument-, Abschnitts- und Include-Beziehungen DÜRFEN NICHT einen Zyklus bilden. | SR-NEED-0002, SR-NEED-0015 | SR-VER-0023 | SR-TC-0307 |
| SR-REQ-0308 | Die Befehle `document create`, `section add`, `section move`, `section remove` und `block add`, `block update`, `block remove` MÜSSEN vollständiges nichtinteraktives Dokument-Authoring über den gemeinsamen Change Plan ermöglichen. | SR-NEED-0001, SR-NEED-0013, SR-NEED-0015 | SR-VER-0023 | SR-TC-0308 |
| SR-REQ-0309 | Das Verschieben oder Neuordnen eines Abschnitts DARF NICHT die IDs oder Revisionen der darin referenzierten fachlichen Artefakte ändern; neue Revisionen entstehen ausschließlich für tatsächlich geänderte Dokumentartefakte. | SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0309 |
| SR-REQ-0310 | Mehrere Dokumente DÜRFEN dasselbe fachliche Artefakt referenzieren. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0310 |
| SR-REQ-0311 | `specroad render --document <DOCUMENT-ID>` MUSS das komponierte Dokument mindestens als Markdown und HTML rendern und Modellwurzel, Dokumentrevision, Toolversion, Profile und Generierungshinweis im Kopf ausgeben. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0311 |
| SR-REQ-0312 | Die eingebaute Spezifikationsansicht MUSS in einem vollständigen Projekt aus dem Dokument mit `document_role=primary_specification` erzeugt werden. | SR-NEED-0001, SR-NEED-0015 | SR-VER-0023 | SR-TC-0312 |

### 12.24 Import, Export und Austauschformate

Offene Formate ermöglichen kontrollierten, verlustbewussten Datenaustausch ohne Server oder proprietäre Datenbank.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0313 | SpecRoad MUSS in Version 0.2 Import und Export für ReqIF 1.2 einschließlich ReqIFZ, CSV nach RFC 4180 und Newline-Delimited JSON bereitstellen. | SR-NEED-0001, SR-NEED-0014, SR-NEED-0015 | SR-VER-0024 | SR-TC-0313 |
| SR-REQ-0314 | `specroad import plan <FORMAT> <INPUT>` MUSS Eingabeformat, Mapping, neue und aktualisierte Artefakte, Konflikte, Informationsverluste, Anhänge, Diagnosen, einen ausführbaren Change Plan und die erwartete Zielmodellwurzel ausgeben, ohne den Projektstand zu verändern. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0014 | SR-VER-0024 | SR-TC-0314 |
| SR-REQ-0315 | `specroad import apply <FORMAT> <INPUT> [--plan <FILE>]` MUSS einen zuvor ausgegebenen oder im selben Aufruf erzeugten gültigen Importplan über den gemeinsamen Change-Plan-, Transaktions- und Recovery-Vertrag anwenden und ein übergebenes Planfile exakt an Eingabe und aktuelle Basis binden. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0014 | SR-VER-0024 | SR-TC-0315 |
| SR-REQ-0316 | Jeder Import MUSS eine versionierte Mapping-Datei oder ein eindeutig benanntes eingebautes Mappingprofil verwenden, das externe Typen, Attribute, Statuswerte, Beziehungen und Einheiten auf das SpecRoad-Modell abbildet. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0014 | SR-VER-0024 | SR-TC-0316 |
| SR-REQ-0317 | Ein importiertes Objekt MUSS seine externe Identität als Kombination aus `source_system`, `source_document`, `external_id` und optionaler `external_revision` verlustfrei speichern. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0317 |
| SR-REQ-0318 | Die Import-Policy MUSS für bereits bekannte externe Identitäten die Strategien `error`, `skip`, `update_if_unchanged` und `create_new_revision` unterstützen; stilles Überschreiben ist unzulässig. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0318 |
| SR-REQ-0319 | Ein Export MUSS Formatversion, Mappingversion, Modellwurzel, einen aus den enthaltenen normativen Zeitstempeln deterministisch abgeleiteten Snapshot-Zeitpunkt, Toolversion, enthaltene IDs, ausgeschlossene Inhalte und erkannte Informationsverluste in einem maschinenlesbaren Manifest dokumentieren; die tatsächliche Ausführungszeit gehört nur in den nicht exportierten Auditbericht. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0319 |
| SR-REQ-0320 | Der ReqIF-1.2-Export MUSS SpecRoad-Dokumente und -Abschnitte auf `SPECIFICATION` und `SPEC-HIERARCHY`, Artefakte auf `SPEC-OBJECT`, Beziehungen auf `SPEC-RELATION` und unterstützte Feldtypen auf passende ReqIF-Datentypen abbilden. | SR-NEED-0001, SR-NEED-0014, SR-NEED-0015 | SR-VER-0024 | SR-TC-0320 |
| SR-REQ-0321 | Der ReqIF-1.2-Import MUSS Spezifikationshierarchien, Objekte, Attribute, Relationen, Datentypen, XHTML-Kerninhalte und referenzierte Anhänge innerhalb des dokumentierten Unterstützungsprofils einlesen können. | SR-NEED-0001, SR-NEED-0014, SR-NEED-0015 | SR-VER-0024 | SR-TC-0321 |
| SR-REQ-0322 | ReqIF-Inhalte außerhalb des unterstützten Abbildungsprofils MÜSSEN entweder verlustfrei unter namespaced `extensions` erhalten oder als einzeln identifizierter Informationsverlust im Import- beziehungsweise Exportplan ausgewiesen werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0322 |
| SR-REQ-0323 | Ein ReqIFZ-Archiv MUSS als ZIP-Container nach dem Sicherheits- und Kanonisierungsprofil in Kapitel 10.16 verarbeitet werden. | SR-NEED-0011, SR-NEED-0014 | SR-VER-0024 | SR-TC-0323 |
| SR-REQ-0324 | Der XML-Import MUSS DTDs, externe Entitäten, externe Schemas und Netzwerkauflösung ablehnen sowie dokumentierte Grenzen für Tiefe, Elementanzahl, Textlänge und Gesamtbytes durchsetzen. | SR-NEED-0011, SR-NEED-0014 | SR-VER-0024 | SR-TC-0324 |
| SR-REQ-0325 | Der CSV-Import und -Export MUSS RFC-4180-konforme Felder, Anführungszeichen, eingebettete Zeilenumbrüche, CRLF-Dateizeilen und UTF-8 unterstützen sowie ein optionales BOM ausschließlich beim Import akzeptieren. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0014 | SR-VER-0024 | SR-TC-0325 |
| SR-REQ-0326 | Ein CSV-Mapping MUSS mindestens ID-/External-ID-Spalte, Artefakttyp, Feldzuordnung, Datentypkonvertierung, Listen-Trennregeln und Fehlerpolicy deklarieren. | SR-NEED-0002, SR-NEED-0014 | SR-VER-0024 | SR-TC-0326 |
| SR-REQ-0327 | NDJSON-Import und -Export MÜSSEN pro Zeile genau ein versioniertes SpecRoad-Artefakt oder Change-Plan-Objekt verarbeiten, leere Zeilen ignorieren und Kommentare ablehnen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0014 | SR-VER-0024 | SR-TC-0327 |
| SR-REQ-0328 | Ein Export MUSS bei identischem Modellumfang, Mapping, Optionen und Toolversion byte-identisch sein. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0328 |
| SR-REQ-0329 | Ein Export DARF NICHT normative Projektdateien verändern. | SR-NEED-0011, SR-NEED-0014 | SR-VER-0024 | SR-TC-0329 |
| SR-REQ-0330 | Für jedes unterstützte Austauschformat MUSS SpecRoad einen Roundtrip-Test bereitstellen, der alle im Schnittmengenprofil repräsentierbaren Identitäten, Hierarchien, Werte, Beziehungen und Anhänge semantisch erhält. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0330 |
| SR-REQ-0331 | Ein Importabschlussbericht MUSS Eingabehash, Mappinghash, Change-Plan-ID, erzeugte und aktualisierte IDs, übersprungene Objekte, Konflikte, Verluste, Anhänge, Diagnosen und Zielmodellwurzel enthalten. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0024 | SR-TC-0331 |
| SR-REQ-0332 | `specroad export` MUSS mindestens `--scope project\|document\|query\|release`, `--output`, `--mapping`, `--include-attachments` und `--fail-on-loss` unterstützen. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0014 | SR-VER-0024 | SR-TC-0332 |

### 12.25 Evidence-Import und Quellcode-Traceability

Testergebnisse und Codebezüge werden importiert beziehungsweise hashgebunden referenziert, ohne externe Werkzeuge auszuführen.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0333 | `specroad evidence record <VERIFICATION-ID>` MUSS einen manuellen oder werkzeuggestützten Nachweis einschließlich des Laufkontexts nach Kapitel 10.5 über den gemeinsamen Change Plan als neues unveränderbares Evidence-Artefakt erfassen. | SR-NEED-0005, SR-NEED-0013, SR-NEED-0016 | SR-VER-0025 | SR-TC-0333 |
| SR-REQ-0334 | `specroad evidence import junit <FILE>` MUSS das dokumentierte JUnit-XML-Kernprofil aus Testsuites, Testsuite, Testcase, Failure, Error, Skipped, System-out und System-err ohne Testausführung einlesen können. | SR-NEED-0005, SR-NEED-0014, SR-NEED-0016 | SR-VER-0025 | SR-TC-0334 |
| SR-REQ-0335 | Das JUnit-Mapping MUSS Testcase-Identitäten aus einer konfigurierbaren Kombination aus `classname`, `name`, `file` und externem Identifier auf SpecRoad-Test- oder Verification-IDs abbilden. | SR-NEED-0005, SR-NEED-0012, SR-NEED-0016 | SR-VER-0025 | SR-TC-0335 |
| SR-REQ-0336 | `specroad evidence import sarif <FILE>` MUSS SARIF 2.1.0 einlesen und nur ausdrücklich gemappte Results, Rules, Artifacts und Invocations als Evidence oder Evidence-Anhang übernehmen. | SR-NEED-0005, SR-NEED-0014, SR-NEED-0016 | SR-VER-0025 | SR-TC-0336 |
| SR-REQ-0337 | `specroad evidence import generic <FILE>` MUSS ein versioniertes SpecRoad-Evidence-Exchange-Schema mit Producer, Run, Subjects, Results, Environment und Attachments unterstützen. | SR-NEED-0005, SR-NEED-0012, SR-NEED-0016 | SR-VER-0025 | SR-TC-0337 |
| SR-REQ-0338 | Nicht gemappte, mehrdeutig gemappte oder widersprüchliche Testergebnisse MÜSSEN als getrennte Diagnosen erscheinen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0016 | SR-VER-0025 | SR-TC-0338 |
| SR-REQ-0339 | Jeder Evidence-Import MUSS Originaldatei, unveränderten SHA-256-Hash, Importformat, Mappinghash, Parserprofil und Toolversion als Provenienz oder unveränderbaren Anhang binden. | SR-NEED-0005, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0339 |
| SR-REQ-0340 | Der erneute Import derselben Ergebnisdatei mit demselben Mapping, identischem normalisiertem Laufkontext und derselben Request-ID MUSS idempotent denselben Evidence-Satz zurückgeben; eine veränderte gebundene Eingabe unter derselben Request-ID ist der bestehende Konfliktfall mit Code 6. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0016 | SR-VER-0025 | SR-TC-0340 |
| SR-REQ-0341 | Ein Evidence-Import MUSS vollständig geplant, validiert und als eine Transaktion veröffentlicht werden. | SR-NEED-0005, SR-NEED-0011, SR-NEED-0013 | SR-VER-0025 | SR-TC-0341 |
| SR-REQ-0342 | Ein `code_ref`-Artefakt MUSS mindestens projektrelativen Repository-Pfad, Referenzart und Rohdateihash sowie optionalen Git-Commit- und Blobhash enthalten. | SR-NEED-0004, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0342 |
| SR-REQ-0343 | Die Referenzart eines `code_ref` MUSS `file`, `line_range`, `text_anchor`, `symbol_hint` oder `generated_artifact` sein und `symbol_hint` ohne eingebauten Resolver ausschließlich informativ behandeln, sodass es allein keine Aktualität beweist. | SR-NEED-0004, SR-NEED-0012, SR-NEED-0016 | SR-VER-0025 | SR-TC-0343 |
| SR-REQ-0344 | SpecRoad MUSS Code-Referenzpfade und optionale Git-Objekte lesen, ohne den Arbeitsbaum auszuchecken oder Quellcode auszuführen, und dabei dieselben Projektroot- und Symlink-Grenzen wie für Anhänge anwenden. | SR-NEED-0004, SR-NEED-0011, SR-NEED-0016 | SR-VER-0025 | SR-TC-0344 |
| SR-REQ-0345 | SpecRoad MUSS den Zustand eines `code_ref` ausschließlich nach der disjunkten Entscheidungstabelle in Anhang H.3 berechnen. | SR-NEED-0004, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0345 |
| SR-REQ-0346 | Eine Code-Relokation DARF nur durch genau einen exakten Byte- oder normalisierten Texttreffer außerhalb der gespeicherten Position festgestellt werden. | SR-NEED-0004, SR-NEED-0007, SR-NEED-0016 | SR-VER-0025 | SR-TC-0346 |
| SR-REQ-0347 | Die Relation `implemented_by` MUSS `code_ref` als Zieltyp unterstützen. | SR-NEED-0003, SR-NEED-0004, SR-NEED-0006 | SR-VER-0025 | SR-TC-0347 |
| SR-REQ-0348 | Der Core DARF NICHT für Code-Traceability sprachspezifische Parser, Compiler, Language Server oder externe Indexer voraussetzen und behandelt spätere Resolver ausschließlich als nicht zum Core gehörende Adapter. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0016 | SR-VER-0025 | SR-TC-0348 |

### 12.26 Deklarative Ansichten, Berichte und Diagrammquellen

Benutzerdefinierte Sichten bleiben deterministisch, portabel und frei von ausführbarem Templatecode.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0349 | Ein `view`-Artefakt MUSS mindestens Titel, Eingabescope, SRX-Filter, Spalten, Sortierung, Gruppierung, Relationsprojektionen und unterstützte Ausgabeformate deklarieren. | SR-NEED-0003, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0349 |
| SR-REQ-0350 | View-Filter MÜSSEN ausschließlich SRX 1.0 verwenden. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0350 |
| SR-REQ-0351 | Eine View-Spalte MUSS Quelle, Überschrift, Datentyp, Formatierung und Verhalten bei fehlendem Wert deklarieren und als Quellen ausschließlich Artefaktfelder, berechnete Statuswerte oder begrenzte Relationsprojektionen zulassen. | SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0351 |
| SR-REQ-0352 | Sortierung und Gruppierung einer View MÜSSEN eine stabile Kollationsregel besitzen. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0352 |
| SR-REQ-0353 | Relationsprojektionen einer View MÜSSEN Richtung, zulässige Relationstypen, Maximaltiefe und Aggregationsart deklarieren und die konfigurierten Graphgrenzen einhalten. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0353 |
| SR-REQ-0354 | `specroad view render <VIEW-ID>` MUSS mindestens Markdown, selbstenthaltenes HTML ohne aktive Skripte, CSV und versioniertes JSON erzeugen können. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0354 |
| SR-REQ-0355 | HTML-Ausgaben MÜSSEN UTF-8, eingebettete sichere Styles, stabile Anker und escaped Nutzdaten verwenden. | SR-NEED-0011, SR-NEED-0015 | SR-VER-0023 | SR-TC-0355 |
| SR-REQ-0356 | CSV-Ausgaben von Views MÜSSEN den Vertrag aus `SR-REQ-0325` erfüllen und verschachtelte Werte nur über eine in der View deklarierte, verlustbewusste Serialisierung ausgeben. | SR-NEED-0007, SR-NEED-0014, SR-NEED-0015 | SR-VER-0023 | SR-TC-0356 |
| SR-REQ-0357 | Eine View-Ausgabe MUSS bei identischem Modellumfang, View-Artefakt, Profilen, Optionen und Toolversion byte-identisch sein. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0015 | SR-VER-0023 | SR-TC-0357 |
| SR-REQ-0358 | `specroad diagram trace`, `diagram architecture` und `diagram release` MÜSSEN aus dem Artefaktgraphen deterministische Diagrammquellen mindestens in Mermaid- und Graphviz-DOT-Syntax erzeugen. | SR-NEED-0003, SR-NEED-0006, SR-NEED-0015 | SR-VER-0023 | SR-TC-0358 |
| SR-REQ-0359 | Diagrammquellen MÜSSEN Knoten- und Kanten-IDs stabil aus Artefakt- beziehungsweise Relations-IDs ableiten, Labels sicher escapen und eine konfigurierbare Knoten-, Kanten- und Tiefengrenze beachten. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0015 | SR-VER-0023 | SR-TC-0359 |
| SR-REQ-0360 | SpecRoad DARF NICHT im Core Mermaid, Graphviz oder einen Browser starten; das Rendern grafischer Bildformate bleibt ein externer, nicht normativer Folgeschritt. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0360 |

### 12.27 Semantischer Dreiwege-Merge

Parallel entstandene Änderungen werden feld- und relationssemantisch zusammengeführt; Konflikte bleiben explizit.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0361 | `specroad merge plan --base <BASE> --ours <OURS> --theirs <THEIRS>` MUSS einen semantischen Dreiwege-Merge des vollständigen normativen Projektumfangs einschließlich Artefakten, Relationen, Profilen, Regeln, Mappings, Konfiguration und Anhängen auf Basis stabiler Identitäten erzeugen. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0016 | SR-VER-0026 | SR-TC-0361 |
| SR-REQ-0362 | Als Merge-Eingaben MÜSSEN Baseline-IDs, Git-Refs, verifizierte Projektbundles und lokale SpecRoad-Projektverzeichnisse unterstützt werden, sofern alle drei Eingaben dieselbe `project_id` und dieselbe unterstützte Schema-Version besitzen. | SR-NEED-0003, SR-NEED-0014, SR-NEED-0016 | SR-VER-0026 | SR-TC-0362 |
| SR-REQ-0363 | Ein Merge gegen Git-Refs MUSS deren Dateien lesen, ohne Branch, Index oder Arbeitsbaum auszuchecken oder zu verändern. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0016 | SR-VER-0026 | SR-TC-0363 |
| SR-REQ-0364 | Der Merge-Plan MUSS für jedes Artefakt, jede Relation, jede normative Ressource und jeden Anhang die Basis-, Ours- und Theirs-Hashes, automatisch übernommene Änderungen, Konflikte, vorgeschlagene Auflösung und erwartete Zielmodellwurzel enthalten. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0026 | SR-TC-0364 |
| SR-REQ-0365 | Unabhängige Änderungen an unterschiedlichen Objektfeldern desselben Artefakts oder derselben JSON-Ressource MÜSSEN rekursiv automatisch zusammengeführt werden, sofern keine Profil- oder Invarianzregel einen semantischen Konflikt feststellt; Anhänge werden ausschließlich anhand Pfad und Byte-Hash zusammengeführt. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0026 | SR-TC-0365 |
| SR-REQ-0366 | Abweichende Änderungen desselben skalaren Feldes gegenüber der Basis MÜSSEN als Konflikt behandelt werden, sofern beide Zielwerte nicht nach JSON-Semantik identisch sind. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0026 | SR-TC-0366 |
| SR-REQ-0367 | Ungeordnete Mengenfelder MÜSSEN elementweise nach ihrem schema-definierten stabilen Schlüssel zusammengeführt werden. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0026 | SR-TC-0367 |
| SR-REQ-0368 | Beziehungen MÜSSEN im Merge anhand ihrer `relation_id` verglichen werden; unabhängiges Hinzufügen unterschiedlicher Beziehungen ist zusammenführbar, während Ändern und Entfernen derselben Relation einen Konflikt erzeugt. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0026 | SR-TC-0368 |
| SR-REQ-0369 | Konkurrierende Lifecycle-Übergänge, Retirement gegen semantische Änderung, unterschiedliche Supersession-Ziele und Änderungen an recorded Evidence MÜSSEN als nicht automatisch lösbare Konflikte gelten. | SR-NEED-0002, SR-NEED-0005, SR-NEED-0016 | SR-VER-0026 | SR-TC-0369 |
| SR-REQ-0370 | Gleiche IDs mit voneinander unabhängiger Provenienz oder unterschiedlichem `id_scheme` MÜSSEN als Identitätskollision diagnostiziert und ohne automatische Umbenennung abgewiesen werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0026 | SR-TC-0370 |
| SR-REQ-0371 | `specroad merge conflicts <MERGE-PLAN>` MUSS Konflikte mit Artefakt-ID, JSON Pointer, drei Werten, Konfliktklasse, Impact und zulässigen Auflösungsarten ausgeben. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0016 | SR-VER-0026 | SR-TC-0371 |
| SR-REQ-0372 | `specroad merge resolve <MERGE-PLAN> --conflict <ID> --take ours\|theirs\|base` sowie `--value <JSON>` MUSS eine explizite, auditierte Auflösung binden und den restlichen Plan unverändert erhalten. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0016 | SR-VER-0026 | SR-TC-0372 |
| SR-REQ-0373 | `specroad merge apply <MERGE-PLAN>` MUSS nur einen vollständig aufgelösten, zur aktuellen Zielbasis passenden Plan über den gemeinsamen Change-Plan- und Transaktionsvertrag anwenden und anschließend vollständig validieren. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0016 | SR-VER-0026 | SR-TC-0373 |
| SR-REQ-0374 | Nach einem Merge MÜSSEN Relationsreviews, Evidence und Code-Referenzen gemäß Relationsinhalt-, Kontext-, Konfigurations-, Datei- und Auswahlhashes neu bewertet und nicht mehr passende Nachweise oder Reviews als nicht aktuell klassifiziert werden. | SR-NEED-0003, SR-NEED-0005, SR-NEED-0016 | SR-VER-0026 | SR-TC-0374 |
| SR-REQ-0375 | Merge-Plan, Konfliktauflösungen und Abschlussbericht MÜSSEN versionierte JSON-Formate besitzen. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0016 | SR-VER-0026 | SR-TC-0375 |

### 12.28 Agentenselbstbeschreibung, Idempotenz, Bundles und Kompatibilität

Agenten können die CLI zuverlässig erkunden, Requests sicher wiederholen und portable Projektstände austauschen.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0376 | `specroad capabilities --format json` MUSS Toolversion, Capability-IDs, Befehlsgruppen, aktivierte Ausgabe- und Austauschformate, unterstützte Schema-, SRX- und Proposal-Versionen sowie Laufzeitgrenzen maschinenlesbar ausgeben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0376 |
| SR-REQ-0377 | `specroad schema list --format json` MUSS alle verfügbaren Artefakt-, Konfigurations-, Mapping-, Ergebnis- und Austauschschemas mit Kennung, Version und Stabilitätsstatus auflisten. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0377 |
| SR-REQ-0378 | `specroad schema show <SCHEMA-ID> --format json` MUSS das vollständige Schema einschließlich Beschreibungen, Defaults, Beispielen, Enumwerten und deprecation-Hinweisen ausgeben. | SR-NEED-0001, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0378 |
| SR-REQ-0379 | `specroad command describe <COMMAND> --format json` MUSS Parameter, Datentypen, Pflichtangaben, gegenseitige Ausschlüsse, stdin-/stdout-Verträge, mögliche Diagnosen, Exit Codes, Schreibwirkung und mindestens ein maschinenlesbares Beispiel beschreiben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0379 |
| SR-REQ-0380 | `specroad project inspect --format json` MUSS sämtliche Pflichtangaben zu Projekt, Modell, Schema, Profilen, Artefakten, Migrationsbedarf, Diagnosen, Hauptdokumenten, Projektroot, Transaktion und Writer-Lock in den getrennten `semantic`-/`runtime`-Bereichen nach Kapitel 11.5.1 ausgeben. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0008 | SR-VER-0027 | SR-TC-0380 |
| SR-REQ-0381 | Die fachlichen Selbstbeschreibungen MÜSSEN bei identischen fachlichen Eingaben und identischer Toolversion in der exakt definierten Projektion nach Kapitel 11.5.1 identische JSON-Bytes liefern; Projektroot, Lock, Transaktion und sonstiger Laufzeitkontext sind keine Bestandteile dieser Gleichheitsgarantie. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0027 | SR-TC-0381 |
| SR-REQ-0382 | Jeder `normative_write` MUSS `--request-id <ID>` nach dem Idempotenzvertrag unterstützen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0027 | SR-TC-0382 |
| SR-REQ-0383 | SpecRoad MUSS für jede abgeschlossene Request-ID eines normativen Schreibauftrags einen unveränderbaren Receipt mit normalisiertem Operationshash, Akteur, Basiswurzel, Ergebnis, Zielwurzel, erzeugten IDs, Transaktions-ID und Ergebnisobjekt unter `.specroad/requests/` speichern. | SR-NEED-0009, SR-NEED-0013 | SR-VER-0027 | SR-TC-0383 |
| SR-REQ-0384 | Die Wiederholung derselben Request-ID eines normativen Schreibauftrags mit demselben normalisierten Operationshash MUSS ohne erneute normative Änderung dasselbe semantische Ergebnis und dieselben erzeugten IDs zurückgeben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0027 | SR-TC-0384 |
| SR-REQ-0385 | Die Wiederverwendung einer Request-ID im normativen Schreibnamensraum mit einem anderen Operationshash MUSS mit Exit Code 6 als Idempotenzkonflikt abgewiesen werden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0027 | SR-TC-0385 |
| SR-REQ-0386 | `specroad bundle create --scope project\|document\|release` MUSS ein selbstbeschreibendes Bundle mit der kanonischen Scope-/Kind-/Read-only-Kombination aus Anhang E.3 und allen für diesen Scope notwendigen Payloads erzeugen. | SR-NEED-0001, SR-NEED-0008, SR-NEED-0014 | SR-VER-0027 | SR-TC-0386 |
| SR-REQ-0387 | Ein Bundle-Manifest MUSS den vollständigen Metadaten- und nichtrekursiven Eintragsvertrag aus Anhang E.1 erfüllen, wobei seine Hashliste exakt die Payload ohne das Manifest selbst umfasst. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0027 | SR-TC-0387 |
| SR-REQ-0388 | Ein Projektbundle MUSS das kanonische ZIP-Profil aus Kapitel 10.16 erfüllen. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0027 | SR-TC-0388 |
| SR-REQ-0389 | `specroad bundle verify <FILE>` MUSS Formatkombination, ZIP-Struktur, nichtrekursive Manifest-/Payloadbindung, Scope, Hashes und Referenzen einschließlich einer angegebenen externen Voll-ZIP-Erwartung nach Anhang E prüfen, ohne das Bundle zu extrahieren oder das Projekt zu verändern. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0027 | SR-TC-0389 |
| SR-REQ-0390 | `specroad bundle extract <FILE> --output <DIR>` MUSS ausschließlich verifizierte Bundles unter den Pfad-, Ziel- und harten Sicherheitsregeln aus Kapitel 10.16, 11.7 und Anhang E extrahieren; weiche Arbeitsbudgets folgen Anhang O. | SR-NEED-0011, SR-NEED-0014 | SR-VER-0027 | SR-TC-0390 |
| SR-REQ-0391 | Jede Veröffentlichung MUSS Core und ausdrücklich unterstützte Analyzer-Paketkombinationen getrennt unter sämtlichen deklarierten CPython-Versionen testen; für das erste Zielrelease umfasst die Matrix CPython 3.10 bis 3.14. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0014 | SR-VER-0027 | SR-TC-0391 |
| SR-REQ-0392 | `specroad version --format json` MUSS die minimale, maximal getestete und vollständig unterstützte CPython-Minor-Matrix, Distributionsart, Buildhash und Ergebnisformatversionen ausgeben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0027 | SR-TC-0392 |
| SR-REQ-0393 | Ein SpecRoad-Projekt MUSS genau eine `project_id` und genau einen Projektroot besitzen. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0012 | SR-VER-0027 | SR-TC-0393 |
| SR-REQ-0394 | SpecRoad Version 0.2 MUSS als lokales Single-User-Werkzeug für genau ein Repository pro Projekt funktionieren. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0012 | SR-VER-0027 | SR-TC-0394 |

### 12.29 Konfigurationen, Varianten und Wiederverwendung

Produktvarianten innerhalb eines Repositorys werden ohne Kopien durch benannte Konfigurationen und Gültigkeitsausdrücke abgebildet.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0395 | Ein `configuration`-Artefakt MUSS einen eindeutigen Namen, deklarierte Dimensionen, je Dimension zulässige Werte, eine konkrete Wertauswahl und optional genau eine Elternkonfiguration enthalten. | SR-NEED-0002, SR-NEED-0010, SR-NEED-0015 | SR-VER-0028 | SR-TC-0395 |
| SR-REQ-0396 | Ein fachliches Artefakt außer `configuration` DARF ein optionales Feld `applicability` mit einer SRX-1.0-Bedingung besitzen, die ausschließlich auf die ausgewählte Konfiguration und konstante Artefaktmetadaten zugreift. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0015 | SR-VER-0028 | SR-TC-0396 |
| SR-REQ-0397 | Ohne ausgewählte Konfiguration MUSS ein Artefakt ohne `applicability` als anwendbar und ein Artefakt mit `applicability` als potenziell anwendbar behandelt werden. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0015 | SR-VER-0028 | SR-TC-0397 |
| SR-REQ-0398 | `specroad configuration evaluate <CONFIGURATION-ID>` MUSS den anwendbaren und ausgeschlossenen Artefaktumfang, die Auswertungsbegründung und alle inkonsistenten Abhängigkeiten deterministisch ausgeben. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0015 | SR-VER-0028 | SR-TC-0398 |
| SR-REQ-0399 | Wenn ein anwendbares Artefakt über eine zwingende Relation von einem ausgeschlossenen Artefakt abhängt, MUSS SpecRoad einen Konfigurationsfehler mit dem vollständigen kürzesten Abhängigkeitspfad ausgeben. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0016 | SR-VER-0028 | SR-TC-0399 |
| SR-REQ-0400 | `validate`, `render`, `view`, `coverage`, `release readiness`, `baseline create`, `export` und `bundle create` MÜSSEN `--configuration <ID>` unterstützen. | SR-NEED-0006, SR-NEED-0007, SR-NEED-0015 | SR-VER-0028 | SR-TC-0400 |
| SR-REQ-0401 | Eine konfigurationsgebundene Baseline MUSS Konfigurations-ID, -Revision, -Hash, Scope Descriptor und den resultierenden Artefaktumfang speichern. | SR-NEED-0006, SR-NEED-0009, SR-NEED-0015 | SR-VER-0028 | SR-TC-0401 |
| SR-REQ-0402 | Requirements, Verification Contracts, Tests, Code-Referenzen und Inhaltsblöcke MÜSSEN über dieselbe stabile ID in beliebig vielen Dokumenten, Releases und Konfigurationen wiederverwendbar sein, ohne normative Kopien anzulegen. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0028 | SR-TC-0402 |
| SR-REQ-0403 | Diff und Merge MÜSSEN Änderungen an Konfigurationen und `applicability` als eigene semantische Klassen ausweisen und den daraus resultierenden hinzugefügten oder entfernten Modellumfang berechnen. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0028 | SR-TC-0403 |
| SR-REQ-0404 | Die Referenztests MÜSSEN mindestens verschachtelte Konfigurationen, ungültige Dimensionswerte, zyklische Vererbung, anwendbare Artefakte mit ausgeschlossenen Pflichtabhängigkeiten und konfigurationsgebundene Baselines abdecken. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0015 | SR-VER-0028 | SR-TC-0404 |

---

### 12.30 Normative Modellumfänge und Scope-Closure

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0405 | Jede Operation mit einem Teil- oder Vollumfang MUSS einen kanonischen Scope Descriptor nach Kapitel 10.8 verwenden. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0014 | SR-VER-0029 | SR-TC-0405 |
| SR-REQ-0406 | Der Scope `specification` MUSS die Seed-Menge und den permanenten Ausschluss von Proposal- und Baseline-Artefakten einschließlich der Fehlerbehandlung aus Kapitel 10.8 und 10.8.1 anwenden. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0009 | SR-VER-0029 | SR-TC-0406 |
| SR-REQ-0407 | Der Scope `project` MUSS seine Seed-Menge exakt nach der Tabelle in Kapitel 10.8 bilden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0029 | SR-TC-0407 |
| SR-REQ-0408 | Ein Release-Scope MUSS Release, zugeordnete Milestones und eingehend darauf geplante Artefakte als Seed-Menge verwenden. | SR-NEED-0006, SR-NEED-0010, SR-NEED-0014 | SR-VER-0029 | SR-TC-0408 |
| SR-REQ-0409 | Ein Dokument-Scope MUSS das Dokument und seine rekursive `contains`-Komposition als Seed-Menge verwenden. | SR-NEED-0001, SR-NEED-0015 | SR-VER-0029 | SR-TC-0409 |
| SR-REQ-0410 | Ein Query-Scope MUSS die deterministisch geordnete Query-Ergebnismenge als Seed-Menge verwenden. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0029 | SR-TC-0410 |
| SR-REQ-0411 | Ein Konfigurationsscope MUSS `applicability` vor der Scope-Closure gegen die effektive Konfiguration auswerten. | SR-NEED-0006, SR-NEED-0015 | SR-VER-0029 | SR-TC-0411 |
| SR-REQ-0412 | Die Scope-Closure MUSS den kleinsten zulässigen Fixpunkt aus starken Relationen und Ressourcenbindungen unter Beachtung der permanenten Ausschlüsse und der Fehlerregeln aus Kapitel 10.8 berechnen. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0009 | SR-VER-0029 | SR-TC-0412 |
| SR-REQ-0413 | Der Scope-Hash MUSS Scope Descriptor, enthaltene Ressourcen und geordnete Boundary References binden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0029 | SR-TC-0413 |
| SR-REQ-0414 | Eine konfigurationsbedingt ausgeschlossene Pflichtabhängigkeit MUSS den Scope als inkonsistent diagnostizieren. | SR-NEED-0002, SR-NEED-0006, SR-NEED-0015 | SR-VER-0029 | SR-TC-0414 |

### 12.31 Relationsmatrix und Profilkomposition

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0415 | SpecRoad MUSS Quell- und Zieltypen ausschließlich anhand der vollständigen Relationsmatrix in Kapitel 9.7 akzeptieren. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0007 | SR-VER-0029 | SR-TC-0415 |
| SR-REQ-0416 | Ein partielles Bundle DARF ein fehlendes Relationsziel nur als im Manifest exakt passende Boundary Reference akzeptieren. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0033 | SR-TC-0416 |
| SR-REQ-0417 | Jede `contains`-Relation MUSS eine nichtnegative `position` besitzen, wobei die Ziel-ID gleiche Positionen deterministisch ordnet. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0015 | SR-VER-0029 | SR-TC-0417 |
| SR-REQ-0418 | Die Felder `relation_id`, `id_scheme`, `type` und `target` einer gespeicherten Relation DÜRFEN NICHT durch Update geändert werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0029 | SR-TC-0418 |
| SR-REQ-0419 | SpecRoad MUSS die exakte Core-Profilversion vor allen weiteren aktiven Profilen anwenden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0029 | SR-TC-0419 |
| SR-REQ-0420 | Eine nichtleere CLI-Profilliste MUSS die Projekt-Profilliste für den Aufruf vollständig ersetzen. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0029 | SR-TC-0420 |
| SR-REQ-0421 | Pflichtfelder und verbotene Felder mehrerer Profile MÜSSEN nach dem Mengenvertrag in Kapitel 10.10 zusammengesetzt werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0029 | SR-TC-0421 |
| SR-REQ-0422 | Zulässige Werte mehrerer Profile MÜSSEN durch Schnittmenge zusammengesetzt werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0029 | SR-TC-0422 |
| SR-REQ-0423 | Eine doppelte Regelidentität mit abweichender Version oder abweichendem Hash MUSS als Profilkonflikt gelten. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0012 | SR-VER-0029 | SR-TC-0423 |
| SR-REQ-0424 | Severity Overrides MÜSSEN nach dem Later-Wins-Vertrag mit unveränderlicher Core-Mindestschwere aufgelöst werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0029 | SR-TC-0424 |
| SR-REQ-0425 | Der effektive Profilhash MUSS die geordnete Profilkette und ihre vollständig materialisierte Mergeprojektion binden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0012 | SR-VER-0029 | SR-TC-0425 |

### 12.32 Proposal-Authoring, Change-Plan-Metadaten und Spezial-Lifecycles

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0426 | Die Proposal-Authoring-Befehlsgruppe MUSS den vollständigen Aufruf-, Eingabe-, Ausgabe-, Revisions-, Seiteneffekt- und Fehlervertrag aus Kapitel 11.10 erfüllen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0030 | SR-TC-0426 |
| SR-REQ-0427 | `specroad proposal change add` MUSS die Operation ohne `--position` anhängen und mit `--position N` am nullbasierten Index N der bestehenden Änderungsliste einfügen. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0030 | SR-TC-0427 |
| SR-REQ-0428 | `specroad proposal change update\|remove\|move` MUSS eine Änderung anhand ihrer stabilen Change-ID bearbeiten. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0030 | SR-TC-0428 |
| SR-REQ-0429 | `specroad proposal show` MUSS Proposal-Inhalt, Basis, Change-Plan-Hash und Wirksamkeit jedes Reviews ausgeben. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0009 | SR-VER-0030 | SR-TC-0429 |
| SR-REQ-0430 | Jede Änderung des Proposal-Fachinhalts MUSS `content_revision` erhöhen, den Kontrollstatus auf `draft` zurücksetzen und die Freigabewirkung älterer Inhaltsbindungen aufheben. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0030 | SR-TC-0430 |
| SR-REQ-0431 | Ein Proposal-Statusübergang MUSS `maturity` gemäß Kapitel 9.6.2 im selben Change Plan setzen. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0030 | SR-TC-0431 |
| SR-REQ-0432 | Ein Evidence-Artefakt MUSS atomar mit `evidence_state=recorded` und `maturity=approved` erzeugt werden. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0030 | SR-TC-0432 |
| SR-REQ-0433 | Ein Baseline-Artefakt MUSS atomar mit `baseline_state=sealed` und `maturity=approved` erzeugt werden. | SR-NEED-0002, SR-NEED-0009 | SR-VER-0030 | SR-TC-0433 |
| SR-REQ-0434 | Ein Relationsreview-Artefakt MUSS atomar mit `review_state=recorded` und `maturity=approved` erzeugt werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0030 | SR-TC-0434 |
| SR-REQ-0435 | Ein Change Plan MUSS seine zulässige `metadata_policy_version` nach Anhang K, `planned_at` und den kanonischen Planhash enthalten. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0435 |
| SR-REQ-0436 | Ein Change Plan MUSS für jede resultierende Artefaktressource Revision, Zeit-/Akteursmetadaten und erwarteten Ressourcenhash binden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0436 |
| SR-REQ-0437 | Ein vorhandenes semantisch geändertes Artefakt MUSS pro Plan genau eine resultierende Revision gemäß der ausgewählten Policy aus Anhang K erhalten. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0437 |
| SR-REQ-0438 | Ein regulär neu erzeugtes Artefakt MUSS `created_at=updated_at=planned_at` und den gebundenen Akteur erhalten; unveränderte Historienübernahmen durch Merge oder Migration folgen Anhang K beziehungsweise Q. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0438 |
| SR-REQ-0439 | Der resultierende `updated_at`-Wert MUSS nach der im Change Plan ausgewählten Metadatenpolicy aus Anhang K berechnet werden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0439 |
| SR-REQ-0440 | Mehrere Operationen auf demselben Artefakt MÜSSEN vor Hashbildung zu genau einem resultierenden Artefaktzustand gefaltet werden. | SR-NEED-0007, SR-NEED-0013 | SR-VER-0030 | SR-TC-0440 |
| SR-REQ-0441 | Eine `representation_normalize`-Operation DARF NICHT Artefaktrevision, semantische Werte oder Zeit-/Akteursmetadaten ändern. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0013 | SR-VER-0031 | SR-TC-0441 |
| SR-REQ-0442 | `specroad change apply` MUSS den unveränderten Planhash und alle gebundenen Metadaten gegen Basis und Ergebnis prüfen. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0030 | SR-TC-0442 |
| SR-REQ-0443 | Ein direkter Authoring-Befehl MUSS intern denselben speicherbaren Change Plan erzeugen wie sein entsprechender Dry-Run. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0013 | SR-VER-0030 | SR-TC-0443 |

### 12.33 Verifikationsplanung und berechnete Ergebnisse

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0444 | Capabilities, Requirements und Tasks MÜSSEN ausschließlich `verification_plan_status` als gespeicherten Verifikationsworkflowzustand verwenden. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0030 | SR-TC-0444 |
| SR-REQ-0445 | SpecRoad DARF NICHT `verification_result` als normatives Feld eines fachlichen Artefakts speichern. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0030 | SR-TC-0445 |
| SR-REQ-0446 | SpecRoad MUSS `verification_result` durch die vollständige Bewertungs-, Pflichtprüfungs- und Nachweisauswahl samt anschließender priorisierter Ergebnisaggregation aus Kapitel 10.5 berechnen. | SR-NEED-0005, SR-NEED-0006, SR-NEED-0007 | SR-VER-0030 | SR-TC-0446 |
| SR-REQ-0447 | Ein Waiver MUSS Grund, Scope Descriptor, Ablaufbedingung, menschliche Review-ID und gebundene Hashes enthalten. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0030 | SR-TC-0447 |
| SR-REQ-0448 | Evidence-Import DARF NICHT Revision, `verification_plan_status` oder fachlichen Inhalt eines Subjects verändern. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0031 | SR-TC-0448 |
| SR-REQ-0449 | Query MUSS getrennte Filter für `verification_plan_status` und das berechnete `verification_result` anbieten. | SR-NEED-0003, SR-NEED-0005, SR-NEED-0007 | SR-VER-0032 | SR-TC-0449 |
| SR-REQ-0450 | Release Readiness MUSS das berechnete Verification Result des Release-Scope Descriptors mit der nach Kapitel 10.5.4 gebundenen Bewertungsauswahl verwenden. | SR-NEED-0005, SR-NEED-0006 | SR-VER-0030 | SR-TC-0450 |
| SR-REQ-0451 | Konfigurationsgebundene Evidence MUSS exakt denselben Konfigurationshash wie der ausgewertete Scope binden, sofern der Contract sie nicht als unabhängig erklärt. | SR-NEED-0005, SR-NEED-0006, SR-NEED-0015 | SR-VER-0030 | SR-TC-0451 |
| SR-REQ-0452 | `verification_context_hash-v1` DARF NICHT Workflowstatus, berechnete Ergebnisse oder reine Auditfelder enthalten. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0030 | SR-TC-0452 |

### 12.34 External Identities, Importvergleich, Recovery und Formatierung

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0453 | Eine Relation MUSS External Identities und namespaced Extensions verlustfrei speichern können. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0031 | SR-TC-0453 |
| SR-REQ-0454 | Eine importgebundene External Identity MUSS Mapping-ID, letzte Importprojektion, letzte Quellprojektion, letzten Quellpayload-Hash und Importzeitpunkt speichern. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0031 | SR-TC-0454 |
| SR-REQ-0455 | Ein Mapping MUSS externe Typ-, Hierarchie- und Relationsidentitäten ohne eigenes SpecRoad-Artefakt in einem Registry erhalten können. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0031 | SR-TC-0455 |
| SR-REQ-0456 | `update_if_unchanged` MUSS den Dreifachvergleich aus Kapitel 10.12 verwenden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0031 | SR-TC-0456 |
| SR-REQ-0457 | Divergente lokale und externe Änderungen an derselben Mappingprojektion MÜSSEN als Importkonflikt ohne stille Auflösung enden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0031 | SR-TC-0457 |
| SR-REQ-0458 | `recover discard` DARF nur für `building` oder `prepared` ohne veröffentlichte Ziele und bei unveränderter Basiswurzel ausgeführt werden. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0031 | SR-TC-0458 |
| SR-REQ-0459 | Recovery aus `committing` oder `rolling_back` MUSS exakt die vollständige Basis- oder Zielwurzel herstellen. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0031 | SR-TC-0459 |
| SR-REQ-0460 | Eine Transaktion im Zustand `corrupt` MUSS jeden normalen Projektzugriff blockieren. | SR-NEED-0009, SR-NEED-0011 | SR-VER-0031 | SR-TC-0460 |
| SR-REQ-0461 | `recover restore` MUSS ausschließlich einen vollständig qualifizierten, zielhashgebundenen Restore-Plan nach Kapitel 10.7.1 aus einer unveränderten Vollprojekt-Baseline oder einem Vollprojektbundle ausführen. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0031 | SR-TC-0461 |
| SR-REQ-0462 | Jede ausgeführte Recovery-Aktion MUSS einen unveränderbaren lokalen Auditdatensatz einschließlich der für Restore nach Kapitel 10.7.1 gebundenen Quellen-, Erhaltungs- und Zielinventur erzeugen. | SR-NEED-0009, SR-NEED-0013 | SR-VER-0031 | SR-TC-0462 |
| SR-REQ-0463 | `specroad format` MUSS seinen Dateiumfang exakt nach Kapitel 10.17 bestimmen. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0013 | SR-VER-0031 | SR-TC-0463 |
| SR-REQ-0464 | Eine tatsächliche Formatierung MUSS jede geänderte Datei durch `representation_normalize` mit erwartetem und resultierendem Byte-Hash planen. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0031 | SR-TC-0464 |
| SR-REQ-0465 | `specroad format --check` DARF NICHT Projekt- oder Betriebsdateien verändern. | SR-NEED-0007, SR-NEED-0011 | SR-VER-0031 | SR-TC-0465 |
| SR-REQ-0466 | Recorded Evidence, sealed Baselines, recorded Relationsreviews und unveränderbare Proposal-Endstände DÜRFEN NICHT formatiert werden. | SR-NEED-0009, SR-NEED-0011 | SR-VER-0031 | SR-TC-0466 |

### 12.35 Dokumentpayloads, Query, JSON und Befehlsklassen

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0467 | Ein vollständiges Projekt MUSS genau ein nicht retirertes Dokument mit `document_role=primary_specification` besitzen. | SR-NEED-0001, SR-NEED-0015 | SR-VER-0032 | SR-TC-0467 |
| SR-REQ-0468 | Jeder `content_block` MUSS exakt das zu seiner Blockart gehörende Payload-Schema aus Kapitel 10.14 erfüllen. | SR-NEED-0001, SR-NEED-0007, SR-NEED-0015 | SR-VER-0032 | SR-TC-0468 |
| SR-REQ-0469 | Prose- und Admonition-Inhalte MÜSSEN auf das in Kapitel 10.14 definierte CommonMark-Kernsubset begrenzt sein. | SR-NEED-0011, SR-NEED-0015 | SR-VER-0032 | SR-TC-0469 |
| SR-REQ-0470 | Der durch `include_document` gebildete Graph MUSS vor jedem Rendern zyklusfrei sein. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0032 | SR-TC-0470 |
| SR-REQ-0471 | `section remove` MUSS für einen nichtleeren Abschnitt genau eine Strategie aus `--cascade` oder `--move-children-to` verlangen. | SR-NEED-0001, SR-NEED-0013, SR-NEED-0015 | SR-VER-0032 | SR-TC-0471 |
| SR-REQ-0472 | Die Rendersemantik für `admonition` und `page_break` MUSS für jedes unterstützte Ausgabeformat als Golden File versioniert sein. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0032 | SR-TC-0472 |
| SR-REQ-0473 | `specroad query` MUSS die vollständige CLI-Grammatik aus Kapitel 11.6 akzeptieren. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0032 | SR-TC-0473 |
| SR-REQ-0474 | Volltextsuche MUSS Unicode-NFC und Unicode-Casefold locale-unabhängig anwenden. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0032 | SR-TC-0474 |
| SR-REQ-0475 | Ein Query-Ergebnis MUSS `items`, `total`, `offset`, `limit`, `returned` und `truncated` enthalten. | SR-NEED-0003, SR-NEED-0007 | SR-VER-0032 | SR-TC-0475 |
| SR-REQ-0476 | Jede JSON-CLI-Ausgabe MUSS den Envelope aus Kapitel 11.5 erfüllen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0032 | SR-TC-0476 |
| SR-REQ-0477 | Jeder CLI-Befehl MUSS genau einer Befehlsklasse aus Kapitel 11.7 zugeordnet sein. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0032 | SR-TC-0477 |
| SR-REQ-0478 | Ein normativer Schreibbefehl MUSS Change Plan, Writer-Lock, Journal und Request-Receipt gemäß seiner Befehlsklasse verwenden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0013 | SR-VER-0032 | SR-TC-0478 |
| SR-REQ-0479 | Ein generierter Ausgabebefehl DARF NICHT das kanonische Modell oder `.specroad/` verändern. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0015 | SR-VER-0032 | SR-TC-0479 |
| SR-REQ-0480 | Ein Root-Erzeugungsbefehl MUSS die für ihn in Kapitel 11.7 festgelegte Zielvorbedingung prüfen und die geplante Root-Struktur vollständig oder gar nicht veröffentlichen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0013 | SR-VER-0032 | SR-TC-0480 |

### 12.36 Partielle Bundles, kanonisches ZIP und portable Idempotenz

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0481 | Ein `project`-Bundle MUSS nach Extraktion ein vollständiges schreibbares Projekt mit geschlossener Scope-Closure bilden. | SR-NEED-0008, SR-NEED-0014 | SR-VER-0033 | SR-TC-0481 |
| SR-REQ-0482 | Ein `document`- oder `release`-Bundle MUSS nach Extraktion als `partial` und `read_only` gekennzeichnet sein. | SR-NEED-0009, SR-NEED-0014, SR-NEED-0015 | SR-VER-0033 | SR-TC-0482 |
| SR-REQ-0483 | Ein partielles Bundle MUSS Ursprungmodellwurzel, partiellen Scope Descriptor, partielle Modellwurzel und Boundary References speichern. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0033 | SR-TC-0483 |
| SR-REQ-0484 | SpecRoad MUSS auf einem partiellen Bundle ausschließlich die in Kapitel 10.16 zugelassenen Befehle ausführen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0014 | SR-VER-0033 | SR-TC-0484 |
| SR-REQ-0485 | Projektbundles MÜSSEN alle Parameter des kanonischen ZIP-Profils aus Kapitel 10.16 bytegenau anwenden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0033 | SR-TC-0485 |
| SR-REQ-0486 | ReqIFZ-Exporte MÜSSEN dasselbe kanonische ZIP-Profil wie Projektbundles verwenden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0014 | SR-VER-0033 | SR-TC-0486 |
| SR-REQ-0487 | Ein vollständiges Projektbundle MUSS abgeschlossene Request- und Transaktionsreceipts standardmäßig in einer getrennten Betriebssektion enthalten. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0033 | SR-TC-0487 |
| SR-REQ-0488 | Die Option `--exclude-operational-receipts` MUSS im Bundlemanifest `idempotency_scope=local_only` setzen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0014 | SR-VER-0033 | SR-TC-0488 |
| SR-REQ-0489 | Ein Dry-Run DARF NICHT ein Request-Receipt schreiben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0033 | SR-TC-0489 |
| SR-REQ-0490 | Die Idempotenzentscheidung nach dem Transfer eines vollständigen Projektbundles MUSS dieselben Regeln wie `SR-REQ-0384` und `SR-REQ-0385` anwenden. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0033 | SR-TC-0490 |

### 12.37 Testfall-Traceability, Codezustand und reproduzierbare Performance

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0491 | Jede normative Produktanforderung MUSS genau einen stabilen primären Testfall `SR-TC-NNNN` mit derselben Nummer besitzen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0009 | SR-VER-0034 | SR-TC-0491 |
| SR-REQ-0492 | Jeder Requirement-Testfall MUSS Requirement-ID und -Revision, primären Verification Contract, Methode, Fixture, Schritte, Oracle, erwartete Diagnosen und Exit Codes, Umgebung und Evidence-Art deklarieren. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0009 | SR-VER-0034 | SR-TC-0492 |
| SR-REQ-0493 | Die Release-Abnahme MUSS für jeden im Release-Scope enthaltenen Requirement-Testfall aktuelle bestandene Evidence verlangen. | SR-NEED-0005, SR-NEED-0006, SR-NEED-0009 | SR-VER-0034 | SR-TC-0493 |
| SR-REQ-0494 | Jedes leitende Szenario MUSS den in Kapitel 15.6 angegebenen exakten Mindestumfang von Requirement-Testfällen als End-to-End-Kette ausführen. | SR-NEED-0007, SR-NEED-0009 | SR-VER-0034 | SR-TC-0494 |
| SR-REQ-0495 | Der Code-Referenzzustand MUSS ausschließlich durch die disjunkte Tabelle in Anhang H.3 bestimmt werden. | SR-NEED-0004, SR-NEED-0007, SR-NEED-0016 | SR-VER-0034 | SR-TC-0495 |
| SR-REQ-0496 | Jeder Performance-Nachweis MUSS ein versioniertes `benchmark-platform.json` mit Hardware-, Kernel-, Dateisystem-, Python- und Governor-Daten binden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0012 | SR-VER-0034 | SR-TC-0496 |
| SR-REQ-0497 | Der maximale Resident Set Size MUSS auf Linux als `Maximum resident set size` aus `/usr/bin/time -v` oder einem byteidentisch definierten Ersatzmesswert erfasst werden. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0034 | SR-TC-0497 |
| SR-REQ-0498 | Performance-Abnahmeläufe MÜSSEN ohne Swap, ohne konkurrierende Last, mit `LC_ALL=C`, `TZ=UTC` und festgelegtem CPU-Governor erfolgen. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0034 | SR-TC-0498 |
| SR-REQ-0499 | Die fachliche Spezifikationsprüfung MUSS durch menschliches Review bestätigte Compound Requirements als Freigabefehler melden, ohne eine automatische semantische Erkennung durch den Core vorauszusetzen. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0009 | SR-VER-0034 | SR-TC-0499 |
| SR-REQ-0500 | Der Release-Testbericht MUSS Dokumenthash, Testfallkataloghash, Requirement-zu-Testfall-Zuordnung und Evidence-IDs für sämtliche Anforderungen dieser Dokumentversion binden. | SR-NEED-0005, SR-NEED-0009 | SR-VER-0034 | SR-TC-0500 |

### 12.38 Atomisierte Nebenverträge bestehender Anforderungen

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0501 | Der `<IDENTIFIER>`-Teil einer Artefakt-ID MUSS entweder eine aus Version 0.1 migrierte vierstellige Legacy-Nummer oder ein nach `random128-v1` erzeugter Token sein. | SR-NEED-0001, SR-NEED-0009, SR-NEED-0016 | SR-VER-0018 | SR-TC-0501 |
| SR-REQ-0502 | Das gemeinsame Change-Plan-Modell MUSS mindestens die Operationen `create`, `update`, `relation_add`, `relation_remove`, `transition`, `retire` und `evidence_record` unterstützen. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0013 | SR-VER-0012 | SR-TC-0502 |
| SR-REQ-0503 | Jeder andere Operationstyp MUSS den für ihn in Kapitel 10 definierten typisierten Operationsvertrag verwenden. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0013 | SR-VER-0012 | SR-TC-0503 |
| SR-REQ-0504 | Für ein neu erzeugtes Artefakt DARF NICHT die nächste sequentielle Nummer als Identität verwendet werden. | SR-NEED-0001, SR-NEED-0009, SR-NEED-0016 | SR-VER-0018 | SR-TC-0504 |
| SR-REQ-0505 | Falls `specroad retire` bereitgestellt wird, MUSS der Befehl als kompatibler Alias exakt denselben Change Plan wie der entsprechende Lifecycle-Übergang erzeugen. | SR-NEED-0002, SR-NEED-0009, SR-NEED-0013 | SR-VER-0018 | SR-TC-0505 |
| SR-REQ-0506 | Ein Lock-Recovery-Befehl DARF NICHT ein vorhandenes Transaktionsjournal umgehen. | SR-NEED-0011, SR-NEED-0007, SR-NEED-0013 | SR-VER-0019 | SR-TC-0506 |
| SR-REQ-0507 | Eine fehlgeschlagene Change-Plan-Operation MUSS die Auswertung aller nachfolgenden Operationen verhindern. | SR-NEED-0003, SR-NEED-0011, SR-NEED-0013 | SR-VER-0018 | SR-TC-0507 |
| SR-REQ-0508 | Das erste Zeichen eines `random128-v1`-Tokens MUSS im Bereich `0` bis `7` liegen und dadurch genau 128 Zufallsbits ohne ungenutzte Mehrdeutigkeit repräsentieren. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0018 | SR-TC-0508 |
| SR-REQ-0509 | Eine regulär neu erzeugte `relation_id` DARF NICHT aus Quelle, Ziel oder Position abgeleitet werden; ausschließlich die Bestandsmigration nach SR-REQ-0273 verwendet `derived128-v1`. | SR-NEED-0003, SR-NEED-0016 | SR-VER-0018 | SR-TC-0509 |
| SR-REQ-0510 | Eine gleiche ID aus fachlich unabhängiger Erzeugung MUSS als Identitätskonflikt abgewiesen werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0026 | SR-TC-0510 |
| SR-REQ-0511 | Eine Transaktion in `committing` MUSS anhand der Hashes deterministisch vollständig zurückgerollt werden, sofern der vollständige Zielstand nicht nachweisbar veröffentlicht ist. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0019 | SR-TC-0511 |
| SR-REQ-0512 | Jeder ausdrücklich akzeptierte Migrationsverlust MUSS einzeln im Abschlussbericht ausgewiesen werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0014 | SR-VER-0020 | SR-TC-0512 |
| SR-REQ-0513 | Fehlt ein verlustfreier Downgrade-Pfad, MUSS SpecRoad auf das vor der Migration erzeugte Projektbundle als Wiederherstellungsweg verweisen. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0014 | SR-VER-0020 | SR-TC-0513 |
| SR-REQ-0514 | Eine reine Lifecycle-, Audit-, Status- oder Relationslistenänderung außerhalb der geprüften Relation DARF NICHT allein einen `suspect`-Status auslösen. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0021 | SR-TC-0514 |
| SR-REQ-0515 | Der Relationsreview-Status `invalid` MUSS unabhängig vom Profil als Fehler diagnostiziert werden; die Unterscheidung zwischen strukturellem Fehler und korrekt aufgenommenem negativem Fachurteil für den Write ist in Kapitel 11.13 festgelegt. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0021 | SR-TC-0515 |
| SR-REQ-0516 | Eine Release-Readiness-Beziehung DARF nur bei Reviewstatus `current` als erfüllt zählen. | SR-NEED-0003, SR-NEED-0006, SR-NEED-0016 | SR-VER-0021 | SR-TC-0516 |
| SR-REQ-0517 | Jede SRX-Bedingung MUSS ein Objekt mit `language = "srx"`, `version = "1.0"` und einem `expression`-Knoten sein. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0014 | SR-VER-0022 | SR-TC-0517 |
| SR-REQ-0518 | Der SRX-Operator `field` DARF NICHT relative Pfadsegmente, Dateioperationen oder dynamisch berechnete Feldnamen unterstützen. | SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0518 |
| SR-REQ-0519 | SRX DARF NICHT Strings, Zahlen, Booleans, Nullwerte, Arrays oder Objekte implizit ineinander umwandeln. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0519 |
| SR-REQ-0520 | Der interne Wert `missing` DARF NICHT als JSON-Nullwert behandelt werden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0022 | SR-TC-0520 |
| SR-REQ-0521 | Der SRX-Operator `reachable` MUSS Relationstypen, Richtung und eine explizite Maximaltiefe verlangen. | SR-NEED-0002, SR-NEED-0003, SR-NEED-0012 | SR-VER-0022 | SR-TC-0521 |
| SR-REQ-0522 | Alle übrigen SRX-Operatoren MÜSSEN ihre Argumente in der in Anhang B dokumentierten stabilen Reihenfolge auswerten. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0022 | SR-TC-0522 |
| SR-REQ-0523 | Die SRX-Auswertung MUSS eine harte Strukturverletzung als Fehler diagnostizieren und eine bloße Überschreitung weicher Rechenziele nach Anhang O/P fortsetzen. | SR-NEED-0007, SR-NEED-0011, SR-NEED-0012 | SR-VER-0022 | SR-TC-0523 |
| SR-REQ-0524 | Die Wurzelabschnitte eines Dokuments MÜSSEN ausschließlich durch ausgehende `contains`-Relationen mit `position` bestimmt werden. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0524 |
| SR-REQ-0525 | Ein `artifact_ref`-Payload DARF NICHT die Ziel-ID oder normative Felder des Zielartefakts als zweite manuell gepflegte Kopie speichern. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0525 |
| SR-REQ-0526 | Die Dateisystemreihenfolge DARF NICHT die Reihenfolge von Abschnitten oder Inhaltsblöcken beeinflussen. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0526 |
| SR-REQ-0527 | Ein Prosa-Inhaltsblock DARF NICHT ausführbares HTML, Skripte oder externe Includes enthalten. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0015 | SR-VER-0023 | SR-TC-0527 |
| SR-REQ-0528 | Ein Tabellen-Inhaltsblock DARF NICHT ausführbaren Templatecode enthalten. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0528 |
| SR-REQ-0529 | Ein Inhaltsblock DARF NICHT transitiv das Dokument einschließen, in dem er gerendert wird. | SR-NEED-0002, SR-NEED-0015 | SR-VER-0023 | SR-TC-0529 |
| SR-REQ-0530 | SpecRoad MUSS Mehrfachreferenzen aus Dokumenten als Ansichten derselben normativen Artefaktidentität behandeln. | SR-NEED-0001, SR-NEED-0003, SR-NEED-0015 | SR-VER-0023 | SR-TC-0530 |
| SR-REQ-0531 | In einem partiellen Bundle oder einem vor der Migration geladenen Legacy-Projekt ohne Primärspezifikationsdokument MUSS die deterministische typbasierte Fallback-Ansicht verfügbar bleiben. | SR-NEED-0001, SR-NEED-0015 | SR-VER-0023 | SR-TC-0531 |
| SR-REQ-0532 | Ein Import DARF NICHT eine externe Netzwerkverbindung initiieren oder einen ausführbaren Konverter starten. | SR-NEED-0011, SR-NEED-0014 | SR-VER-0024 | SR-TC-0532 |
| SR-REQ-0533 | Ein importiertes Testergebnis DARF NICHT allein den Reifegrad oder `verification_plan_status` eines Requirements auf einen Erfolgszustand setzen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0016 | SR-VER-0025 | SR-TC-0533 |
| SR-REQ-0534 | Ohne passende Request-ID MUSS SpecRoad ein semantisch dupliziertes Testergebnis diagnostizieren können. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0016 | SR-VER-0025 | SR-TC-0534 |
| SR-REQ-0535 | Die Importpolicy MUSS für einen ungültigen Pflichtnachweis genau eine Strategie aus `abort_import` oder `skip_invalid_with_diagnostic` festlegen. | SR-NEED-0005, SR-NEED-0011, SR-NEED-0013 | SR-VER-0025 | SR-TC-0535 |
| SR-REQ-0536 | Eine textbasierte Bereichsreferenz MUSS zusätzlich Encoding, Start-/Endzeile beziehungsweise erwartete Zeilenanzahl und Auswahlhash nach Anhang H speichern. | SR-NEED-0004, SR-NEED-0009, SR-NEED-0016 | SR-VER-0025 | SR-TC-0536 |
| SR-REQ-0537 | Impact, Traceability, Diff und Release Readiness MÜSSEN fehlende oder stale Code-Referenzen getrennt ausweisen. | SR-NEED-0003, SR-NEED-0004, SR-NEED-0006 | SR-VER-0025 | SR-TC-0537 |
| SR-REQ-0538 | Eine View DARF NICHT ausführbare Templates, Skripte oder dynamisch geladene Funktionen enthalten. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0015 | SR-VER-0023 | SR-TC-0538 |
| SR-REQ-0539 | Ohne expliziten letzten Sortierschlüssel MUSS die Artefakt-ID als deterministischer Tie-Breaker dienen. | SR-NEED-0007, SR-NEED-0015 | SR-VER-0023 | SR-TC-0539 |
| SR-REQ-0540 | HTML-Ausgaben DÜRFEN NICHT externe Ressourcen, Formulare, Skripte oder Netzwerkreferenzen enthalten. | SR-NEED-0011, SR-NEED-0015 | SR-VER-0023 | SR-TC-0540 |
| SR-REQ-0541 | Vor einem Merge von Eingaben mit unterschiedlichen unterstützten Schema-Versionen MUSS eine gemeinsame Zielversion durch Migration hergestellt werden. | SR-NEED-0003, SR-NEED-0014, SR-NEED-0016 | SR-VER-0026 | SR-TC-0541 |
| SR-REQ-0542 | Ein geordnetes Array ohne stabile Elementidentität MUSS bei konkurrierender Änderung als Merge-Konflikt gelten. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0016 | SR-VER-0026 | SR-TC-0542 |
| SR-REQ-0543 | Für einen tatsächlich ausgeführten `normative_write` eines Akteurs vom Typ `ai` oder `ci` MUSS eine Request-ID vorliegen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0013 | SR-VER-0027 | SR-TC-0543 |
| SR-REQ-0544 | Ein einzelner SpecRoad-Befehl DARF NICHT normative Artefakte aus mehreren Projektroots zu einem gemeinsamen Modell laden. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0012 | SR-VER-0027 | SR-TC-0544 |
| SR-REQ-0545 | SpecRoad DARF NICHT Benutzerkonten, Serverbetrieb, Echtzeit-Kollaboration oder einen Multi-Repository-Graphen als Voraussetzung für Kernfunktionen verlangen. | SR-NEED-0001, SR-NEED-0011, SR-NEED-0012 | SR-VER-0027 | SR-TC-0545 |
| SR-REQ-0546 | Die Elternkette von `configuration`-Artefakten MUSS azyklisch sein. | SR-NEED-0002, SR-NEED-0010, SR-NEED-0015 | SR-VER-0028 | SR-TC-0546 |
| SR-REQ-0547 | Ein `configuration`-Artefakt DARF NICHT ein Feld `applicability` besitzen. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0015 | SR-VER-0028 | SR-TC-0547 |
| SR-REQ-0548 | Ein konfigurationsspezifisches Gate MUSS eine explizite Konfiguration verlangen. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0015 | SR-VER-0028 | SR-TC-0548 |

---

### 12.39 Ephemeral Runtime Safety

Diese Anforderungen konkretisieren SR-DEC-0039. Die verbindlichen Ablauf-, Diagnose- und Recoveryverträge stehen in Anhang N.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0549 | Jeder CLI-Aufruf MUSS seinen benötigten Aufrufkontext nach Anhang N aus den aktuell vorhandenen Eingaben und Dateien neu bestimmen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0549 |
| SR-REQ-0550 | Ein späterer CLI-Aufruf DARF NICHT für korrekte Ergebnisse den Prozess-, Session-, Umgebungsvariablen- oder Arbeitsverzeichniszustand eines früheren Aufrufs voraussetzen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0550 |
| SR-REQ-0551 | Die dem Profil `bootstrap` zugeordneten Befehle MÜSSEN ohne vorhandenes SpecRoad-Projekt ausführbar sein. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0551 |
| SR-REQ-0552 | Jeder Command Contract MUSS die in Anhang N.2 festgelegten maschinenlesbaren Preflight- und Voraussetzungseigenschaften deklarieren. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0552 |
| SR-REQ-0553 | Der automatische Preflight MUSS ausschließlich den für den angeforderten Befehl definierten Prüfumfang aus Anhang N.2 ausführen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0553 |
| SR-REQ-0554 | Ein fehlender oder unzulässiger ausgewählter Projektroot MUSS ohne automatische Neuinitialisierung diagnostiziert werden. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0554 |
| SR-REQ-0555 | Ein Preflight DARF NICHT allein zur Startprüfung die vollständige Modellvalidierung, einen Indexneuaufbau oder einen rekursiven Repository-/Archivscan auslösen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0555 |
| SR-REQ-0556 | Nicht Git-spezifische Preflights DÜRFEN NICHT einen externen Prozess zur Ermittlung der Umgebungsvoraussetzungen starten. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0556 |
| SR-REQ-0557 | Ein normativer Write MUSS die aktuell gültigen Root-, Lock-, Recovery- und Change-Plan-Vorbedingungen unmittelbar vor Veröffentlichung unter dem Writer-Lock erneut prüfen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0557 |
| SR-REQ-0558 | Schreibfreie Aufrufe MÜSSEN einen gefundenen Recoverybedarf nach Anhang N.3 ohne Veränderung von Projektdateien oder deren Betriebsdaten melden; offengelegte externe Fortsetzungsdaten richten sich nach Anhang P. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0558 |
| SR-REQ-0559 | Eine automatische Recovery im Vorlauf eines schreibenden Aufrufs MUSS den getrennten Abschluss- und Wiederaufrufvertrag aus Anhang N.3 erfüllen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0559 |
| SR-REQ-0560 | Die Betriebsdiagnosen aus Anhang N.3 MÜSSEN notwendige verfügbare Metadaten eines blockierten Projekts ohne reguläres Laden seines Modells untersuchen können. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0560 |
| SR-REQ-0561 | Journal, Staging und Before Images einer nicht abschließend belegten Transaktion MÜSSEN unabhängig von jeder Cachebereinigung erhalten bleiben. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0561 |
| SR-REQ-0562 | Ein Wechsel des absoluten Projektpfads oder der kompatiblen Runtime DARF NICHT allein normative Inhalte, fachliche Hashes oder die gebundene Idempotenz abgeschlossener Requests verändern. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0562 |
| SR-REQ-0563 | Die Wiederaufnahme nach vollständigem Sandboxverlust MUSS auf extern erhaltene, verifizierbare Projektvollbundles beziehungsweise Arbeitspakete nach Anhang P begrenzt sein. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0563 |
| SR-REQ-0564 | Ein erfolgreicher Preflight DARF NICHT als Beweis für die Fortexistenz von Dateien, Berechtigungen oder Ressourcen während eines späteren Verarbeitungsschritts gelten. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0564 |
| SR-REQ-0565 | SpecRoad MUSS `environment check` vollständig nach dem Operations- und Ergebnisvertrag aus Anhang N.4 bereitstellen. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0565 |
| SR-REQ-0566 | Nicht nachweisbare Ressourcenquoten oder Runtimevoraussetzungen MÜSSEN in der Umgebungsdiagnose ausdrücklich als unbekannt statt als garantiert verfügbar ausgewiesen werden. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0566 |
| SR-REQ-0567 | `environment check` DARF NICHT Probe-Writes, Benchmarks, Netzwerkzugriffe oder eine fachliche Vollvalidierung ausführen. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0567 |
| SR-REQ-0568 | `bundle create` MUSS ungelöste Transaktionen als Projektvollbundle abweisen; ein separat gekennzeichnetes Arbeitspaket folgt dem Export- und Recoveryvertrag aus Anhang P. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0568 |
| SR-REQ-0569 | Ein neuer Hostname oder eine erneut vergebene Prozessnummer DARF NICHT allein die Übernahme eines unbekannten Lock-Eigentümers rechtfertigen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0569 |
| SR-REQ-0570 | Der automatische Preflight MUSS die Metadaten- und Journalgrenzen aus Anhang N.2 ohne Scannen der abgeschlossenen Receipt-Historie einhalten. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0012 | SR-VER-0038 | SR-TC-0570 |
| SR-REQ-0571 | Der dokumentierte Agentenvertrag MUSS einen verhinderten Prozessstart, eine unvollständige Ausgabe oder ein unbestätigtes Prozessende als unbestätigte Ausführung behandeln. | SR-NEED-0017, SR-NEED-0008 | SR-VER-0036 | SR-TC-0571 |
| SR-REQ-0572 | Ein read-only Aufruf DARF NICHT zur Wiederherstellung seiner Startfähigkeit notwendige oder vermeintlich veraltete Betriebsdaten automatisch löschen. | SR-NEED-0017, SR-NEED-0008, SR-NEED-0013 | SR-VER-0035 | SR-TC-0572 |

### 12.40 Resource-Constrained Runtime Design

Diese Anforderungen konkretisieren SR-DEC-0040. Die Budgets sind weiche SpecRoad-Arbeitsziele und keine behaupteten Anbietergrenzen; vollständige Fortsetzung und echte Blocker sind in Anhang O/P getrennt geregelt.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0573 | SpecRoad MUSS die Ressourcenprofile und weichen Default-Arbeitsziele von `runtime-budget-v2` nach Anhang O.1 bereitstellen. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0573 |
| SR-REQ-0574 | Ein Ressourcenprofil DARF NICHT den angeforderten fachlichen Scope, die Prüfstrenge oder erforderliche Nachweise stillschweigend verändern. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0574 |
| SR-REQ-0575 | Betriebliche Ressourcenoptionen MÜSSEN unabhängig von fachlicher Konfiguration, Aufgabenidentität und Operationshash nach Anhang O.1 aufgelöst werden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0575 |
| SR-REQ-0576 | Die Verbrauchsbilanz eines Arbeitsauftrags MUSS sämtliche Teilschritte und Verarbeitungsphasen kumuliert ausweisen, ohne diese Summe als automatische Abbruchgrenze zu verwenden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0576 |
| SR-REQ-0577 | SpecRoad MUSS verbrauchte CPU-Zeit und verstrichene Zeit als getrennte betriebliche Größen nach Anhang O.2 behandeln. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0577 |
| SR-REQ-0578 | Die Budgetüberwachung MUSS die begrenzten internen Kontrollintervalle aus Anhang O.2 ohne externe Überwachungsprozesse einhalten. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0578 |
| SR-REQ-0579 | Der Core DARF NICHT für Fachoperationen Worker-Pools, Watcher, Hintergrundindexer oder einen dauerhaft laufenden Hilfsdienst starten. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0579 |
| SR-REQ-0580 | Jeder von SpecRoad zulässig gestartete Kindprozess MUSS bei normalem oder von SpecRoad behandeltem Prozessende abgeschlossen beziehungsweise beendet und eingesammelt sein. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0580 |
| SR-REQ-0581 | Der CLI-Start MUSS auf die für Bootstrap und den konkreten Command Contract benötigten Subsysteme begrenzt bleiben. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0581 |
| SR-REQ-0582 | Selektives Laden MUSS alle für das zugesagte Ergebnis erforderlichen Abhängigkeiten und inversen Beziehungen nachweislich berücksichtigen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0582 |
| SR-REQ-0583 | Anhangs-, Archivpayload- und Dateihashverarbeitung MUSS den begrenzten Transferblockvertrag aus Anhang O.3 verwenden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0583 |
| SR-REQ-0584 | Vor bekannten großen Speicher- und Stagingallokationen MUSS SpecRoad die sparsame Alternative und tatsächliche Verfügbarkeit nach Anhang O.3 prüfen. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0584 |
| SR-REQ-0585 | Graphtraversierung und vollständige Pfadausgabe MÜSSEN bei Erreichen weicher Arbeitsschritt- oder Ausgabeschwellen ihren vollständigen Restauftrag nach Anhang P fortsetzbar erhalten. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0585 |
| SR-REQ-0586 | Eine allein wegen des Ausführungsfensters noch unvollständige Fachauswertung MUSS mit `continuation_required`, Exit Code 8 und gültigem Checkpoint statt mit Fehler oder falschem Erfolg enden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0586 |
| SR-REQ-0587 | Inkrementelle Prüfungen MÜSSEN ihren tatsächlich geprüften Umfang einschließlich notwendiger Abhängigkeiten korrekt ausweisen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0587 |
| SR-REQ-0588 | Fehlende oder gelöschte persistente Caches DÜRFEN NICHT die fachliche Ausführbarkeit eines zulässigen Auftrags verhindern. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0588 |
| SR-REQ-0589 | Ein verwendeter persistenter Cacheeintrag MUSS den vollständigen Inhaltshash- und Abhängigkeitsnachweis aus Anhang O.3 erfüllen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0589 |
| SR-REQ-0590 | Ungültige, inkompatible, unlesbare oder übergroße Cacheeinträge MÜSSEN nach Anhang O.3 als entbehrliche Beschleuniger ignoriert werden. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0590 |
| SR-REQ-0591 | Cachelesen, Memoisierung und zulässige Cachepflege MÜSSEN innerhalb der für den Aufruf geltenden Ressourcen- und Befehlsklassenverträge bleiben. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0591 |
| SR-REQ-0592 | Bei Erreichen eines weichen Arbeitsziels MUSS SpecRoad phasenabhängig sparsam weiterarbeiten oder einen sicheren Fortsetzungspunkt nach Anhang O.4 veröffentlichen. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0592 |
| SR-REQ-0593 | Eine Ressourcenbegrenzung DARF NICHT die Erhaltung bereits benötigter Wiederherstellungsdaten zugunsten neuer fachlicher Arbeit umgehen. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0593 |
| SR-REQ-0594 | Die Runtime-Diagnose MUSS gemessenen Gesamtverbrauch, verbuchten Eigenverbrauch und unbekannte Hostgrenzen entsprechend Anhang O.3 unterscheiden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0036 | SR-TC-0594 |
| SR-REQ-0595 | Explizite Verbrauchsmesswerte MÜSSEN ausschließlich über die betriebliche Ausgabe nach Anhang O.5 bereitgestellt werden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0036 | SR-TC-0595 |
| SR-REQ-0596 | Vollständig abgeschlossene Läufe mit verschiedenen Ressourcenprofilen und Cachezuständen MÜSSEN dieselben fachlichen Ergebnisse nach Anhang O.5 erzeugen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0596 |
| SR-REQ-0597 | Die Release-Abnahme MUSS die Start-, Preflight-, CPU- und Speichergrenzen aus Kapitel 14.6 für beide portablen Distributionen nachweisen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0012 | SR-VER-0038 | SR-TC-0597 |
| SR-REQ-0598 | Die Release-Abnahme MUSS weiche Budgetüberschreitungen und tatsächliche Hostabbrüche an den Veröffentlichungsgrenzen getrennt nach Kapitel 14.7 prüfen. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0037 | SR-TC-0598 |
| SR-REQ-0599 | Die Release-Abnahme MUSS die in Kapitel 14.7 definierten Prozess-, Pfad-, Sandbox- und Cachewechsel ohne notwendige Sessions nachweisen. | SR-NEED-0018, SR-NEED-0007, SR-NEED-0013 | SR-VER-0035 | SR-TC-0599 |
| SR-REQ-0600 | Die Runtime-Dokumentation MUSS weiche Arbeitsziele, gesicherte Fortsetzung, tatsächliche Blocker und nicht abfangbare Host-/Sandbox-Beendigung ausdrücklich unterscheiden. | SR-NEED-0018, SR-NEED-0007 | SR-VER-0036 | SR-TC-0600 |

---

### 12.41 Vollständige adaptive Arbeit und Mehrprompt-Fortsetzung

Diese Anforderungen ergänzen die bestehenden Runtime-, Sicherheits- und Änderungsverträge; alle bisherigen Funktionen bleiben Bestandteil des Zielrelease. Maßgeblich sind Anhang O bis R.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0601 | Eine Überschreitung eines weichen Arbeitsbudgets DARF NICHT allein einen fachlich ausführbaren Gesamtauftrag mit Fehler beenden. | SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0601 |
| SR-REQ-0602 | Der vollständige gebundene Auftrag MUSS bei jeder Aufteilung unverändert als offene beziehungsweise nachgewiesen erledigte Arbeit erhalten bleiben. | SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0602 |
| SR-REQ-0603 | Jeder aufgeteilte Auftrag MUSS ein gehashtes vollständiges Aufgaben- und Eingangsmanifest nach Anhang P besitzen. | SR-NEED-0007, SR-NEED-0019 | SR-VER-0039 | SR-TC-0603 |
| SR-REQ-0604 | Die adaptive Ausführung MUSS vor einer ressourcenbedingten Zurückstellung die sicheren sparsamen Alternativen nach Anhang O.3 prüfen. | SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0604 |
| SR-REQ-0605 | Jede potenziell große Verarbeitungsphase MUSS einen dokumentierten granularen Fortschritts- und Fortsetzungsvertrag nach Anhang P.5 besitzen. | SR-NEED-0012, SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0605 |
| SR-REQ-0606 | Ein Arbeitsschritt MUSS bevorzugt innerhalb seines gewählten Schrittfensters bis zum nächsten sicheren Checkpoint ausgeführt werden. | SR-NEED-0007, SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0606 |
| SR-REQ-0607 | Ein neuer Checkpoint MUSS erst nach vollständiger dauerhafter Sicherung aller referenzierten Bestandteile atomar als aktuelle Generation veröffentlicht werden. | SR-NEED-0009, SR-NEED-0013, SR-NEED-0019 | SR-VER-0039 | SR-TC-0607 |
| SR-REQ-0608 | Ein bestätigter Arbeitsstand MUSS ohne erforderlichen prozesslokalen Zustand in einer neuen kompatiblen Runtime fortsetzbar sein. | SR-NEED-0008, SR-NEED-0017, SR-NEED-0019 | SR-VER-0040 | SR-TC-0608 |
| SR-REQ-0609 | Die Fortsetzung MUSS fehlende, manipulierte oder inkompatible notwendige Checkpointbestandteile vor deren Verwendung erkennen. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0019 | SR-VER-0040 | SR-TC-0609 |
| SR-REQ-0610 | Jeder `work resume`-Aufruf MUSS den erforderlichen aktuellen Runtime-, Work-Root- und Berechtigungskontext neu prüfen. | SR-NEED-0008, SR-NEED-0017, SR-NEED-0019 | SR-VER-0040 | SR-TC-0610 |
| SR-REQ-0611 | Eine nicht mehr passende normative Zielbasis MUSS vor Apply als Konflikt ohne stilles Rebase behandelt werden. | SR-NEED-0003, SR-NEED-0013, SR-NEED-0019 | SR-VER-0041 | SR-TC-0611 |
| SR-REQ-0612 | Die Fortsetzung MUSS bestätigte fachliche Zwischenergebnisse wiederverwenden, statt den bereits abgeschlossenen vollständigen Präfix bei jedem Prompt erneut zu berechnen. | SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0612 |
| SR-REQ-0613 | Ein zu kleines weiches Schrittfenster MUSS nach Anhang P.5 einen sicheren kleinsten Fortschrittsversuch statt einer endlosen Folge leerer Checkpoints auslösen. | SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0613 |
| SR-REQ-0614 | Ein tatsächlicher Fortschrittsblocker MUSS Ursache, versuchte sparsame Alternativen, erhaltenen Fortschritt und eine konkrete notwendige Abhilfe ausweisen. | SR-NEED-0007, SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0614 |
| SR-REQ-0615 | Work-Daten DÜRFEN NICHT ausführbaren Code, Pickle-Objekte oder zur Fortsetzung zu ladende fremde Pythonobjekte enthalten. | SR-NEED-0011, SR-NEED-0012, SR-NEED-0019 | SR-VER-0040 | SR-TC-0615 |
| SR-REQ-0616 | Gebundene Änderungs-IDs, Planmetadaten und fachliche Operationsidentität MÜSSEN bei Fortsetzung unverändert erhalten bleiben. | SR-NEED-0008, SR-NEED-0009, SR-NEED-0013 | SR-VER-0040 | SR-TC-0616 |
| SR-REQ-0617 | Ein normativer Gesamtauftrag MUSS über alle seine Arbeitsschritte dieselbe fachliche Request-ID verwenden. | SR-NEED-0007, SR-NEED-0013, SR-NEED-0019 | SR-VER-0040 | SR-TC-0617 |
| SR-REQ-0618 | Ein noch nicht fachlich abgeschlossener Auftrag DARF NICHT ein semantisches Erfolgsreceipt erzeugen. | SR-NEED-0009, SR-NEED-0013, SR-NEED-0019 | SR-VER-0040 | SR-TC-0618 |
| SR-REQ-0619 | Eine planmäßige Promptpause vor fachlicher Veröffentlichung MUSS den Projektstand regulär lesbar und ohne gehaltenen Projektwriter-Lock hinterlassen. | SR-NEED-0011, SR-NEED-0017, SR-NEED-0019 | SR-VER-0039 | SR-TC-0619 |
| SR-REQ-0620 | Ein atomarer Change Plan DARF NICHT allein wegen kleiner Schrittfenster in unabhängige fachliche Teilcommits zerlegt werden. | SR-NEED-0009, SR-NEED-0013, SR-NEED-0019 | SR-VER-0041 | SR-TC-0620 |
| SR-REQ-0621 | Ein echter Prozessabbruch während Veröffentlichung MUSS ausschließlich über den vorhandenen Transaktions-/Recoveryvertrag behandelt werden. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0013 | SR-VER-0041 | SR-TC-0621 |
| SR-REQ-0622 | Die Abschlussprüfung eines aufgeteilten Auftrags MUSS sämtliche erforderlichen globalen Regeln und vollständig zusammengeführten Pflichtdiagnosen einbeziehen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0019 | SR-VER-0039 | SR-TC-0622 |
| SR-REQ-0623 | Eine zu große Inlineausgabe MUSS vollständig über den Ergebnisdatei-/Manifestvertrag nach Kapitel 11.5 geliefert werden. | SR-NEED-0007, SR-NEED-0015, SR-NEED-0019 | SR-VER-0039 | SR-TC-0623 |
| SR-REQ-0624 | `work prompt` MUSS einen aus dem geprüften Arbeitsmanifest abgeleiteten konkreten Fortsetzungstext nach Anhang P.8 ausgeben. | SR-NEED-0008, SR-NEED-0019 | SR-VER-0040 | SR-TC-0624 |
| SR-REQ-0625 | SpecRoad DARF NICHT selbst einen neuen Chat, einen LLM-Aufruf oder eine autonome Nachricht zur Fortsetzung starten. | SR-NEED-0008, SR-NEED-0011, SR-NEED-0019 | SR-VER-0040 | SR-TC-0625 |
| SR-REQ-0626 | Der Fortsetzungsprompt MUSS Geheimnisse und fremde Projektanweisungen nach Anhang P.8 als nicht zu übernehmende Inhalte behandeln. | SR-NEED-0008, SR-NEED-0011, SR-NEED-0019 | SR-VER-0040 | SR-TC-0626 |
| SR-REQ-0627 | Die Work-Befehlsgruppe MUSS die vollständigen Verträge aus Kapitel 11.12 erfüllen. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0019 | SR-VER-0040 | SR-TC-0627 |
| SR-REQ-0628 | Work-Export und -Restore MÜSSEN die selbstenthaltene sichere Paketsemantik nach Anhang P.7 erfüllen. | SR-NEED-0008, SR-NEED-0014, SR-NEED-0017 | SR-VER-0040 | SR-TC-0628 |
| SR-REQ-0629 | Ein bestätigter Checkpoint und seine notwendigen Snapshotdaten DÜRFEN NICHT durch eine Cachebereinigung entfernt werden. | SR-NEED-0009, SR-NEED-0017, SR-NEED-0019 | SR-VER-0040 | SR-TC-0629 |
| SR-REQ-0630 | Fehlende notwendige Fortsetzungsbytes MÜSSEN konkret benannt werden, statt sie allein aus Hashes oder einer alten Chatbeschreibung als vorhanden anzunehmen. | SR-NEED-0008, SR-NEED-0017, SR-NEED-0019 | SR-VER-0040 | SR-TC-0630 |
| SR-REQ-0631 | Ein erneut als fortsetzbar ausgegebener Arbeitsschritt MUSS einen neuen bestätigten Fortschritt oder einen konkret belegten Blocker gegenüber seiner Eingangscheckpointgeneration aufweisen. | SR-NEED-0007, SR-NEED-0018, SR-NEED-0019 | SR-VER-0039 | SR-TC-0631 |
| SR-REQ-0632 | `command describe` MUSS je Fachbefehl die Fortsetzungsfähigkeit, externen Work-Seiteneffekte, Mindestschrittgrenzen und unterstützten Checkpointalgorithmen deklarieren. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0012 | SR-VER-0040 | SR-TC-0632 |
| SR-REQ-0633 | Die Releaseabnahme MUSS die Endergebnisparität von Einzellauf und vollständigem Mehrschrittlauf nach Kapitel 14.8 nachweisen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0019 | SR-VER-0039 | SR-TC-0633 |
| SR-REQ-0634 | Die Runtime MUSS weiche Ziele, fachliche Scopes und harte Sicherheits-/Hostgrenzen nach Anhang O.1 getrennt behandeln. | SR-NEED-0011, SR-NEED-0018, SR-NEED-0019 | SR-VER-0041 | SR-TC-0634 |
| SR-REQ-0635 | Nicht bekannte Anbieterquoten DÜRFEN NICHT als bestimmte verfügbare Ressourcen oder als nachgewiesene Unausführbarkeit ausgegeben werden. | SR-NEED-0008, SR-NEED-0017, SR-NEED-0018 | SR-VER-0040 | SR-TC-0635 |
| SR-REQ-0636 | Ein Checkpoint DARF NICHT offene Closure-, Referenz- oder globale Konsistenzarbeit durch eine lokale Teilfreigabe als erledigt ersetzen. | SR-NEED-0002, SR-NEED-0007, SR-NEED-0019 | SR-VER-0039 | SR-TC-0636 |
| SR-REQ-0637 | Planner und Writer MÜSSEN für Merge-Ergebnisse dieselbe ausdrücklich gebundene `merge-metadata-v1`-Policy anwenden. | SR-NEED-0003, SR-NEED-0007, SR-NEED-0013 | SR-VER-0041 | SR-TC-0637 |
| SR-REQ-0638 | Eine unveränderte Übernahme einer bestehenden Historienrevision MUSS die Metadaten- und Konfliktregeln aus Anhang K.3 erfüllen. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0016 | SR-VER-0041 | SR-TC-0638 |
| SR-REQ-0639 | Die Migration MUSS die Originalbytes jeder als `immutable_legacy` klassifizierten Ressource unverändert erhalten. | SR-NEED-0009, SR-NEED-0014 | SR-VER-0042 | SR-TC-0639 |
| SR-REQ-0640 | Historische Baselines MÜSSEN mit ihrem gespeicherten historischen Hash-/Schemaalgorithmus verifizierbar bleiben. | SR-NEED-0009, SR-NEED-0012, SR-NEED-0014 | SR-VER-0042 | SR-TC-0640 |
| SR-REQ-0641 | Jede in ein 0.2-Modell eingebundene unveränderbare Legacy-Ressource MUSS durch das normative Manifest und die Originalhashbindung aus Anhang Q registriert sein. | SR-NEED-0009, SR-NEED-0012, SR-NEED-0014 | SR-VER-0042 | SR-TC-0641 |
| SR-REQ-0642 | Eine Legacy-Evidence DARF NICHT allein aufgrund einer neuen Pflichtfeldprojektion als aktueller bestandener Nachweis eines transformierten Subjects zählen. | SR-NEED-0005, SR-NEED-0009, SR-NEED-0014 | SR-VER-0042 | SR-TC-0642 |
| SR-REQ-0643 | Jede Proposal-Freigabe MUSS die Inhaltsrevision und den Inhaltshash nach Kapitel 10.3 statt einer durch Kontrollwrites veränderten Artefaktrevision binden. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0009 | SR-VER-0043 | SR-TC-0643 |
| SR-REQ-0644 | Ein reiner Proposal-Kontrollwrite MUSS die fachliche Inhaltsrevision und ihren Hash unverändert erhalten. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0009 | SR-VER-0043 | SR-TC-0644 |
| SR-REQ-0645 | `proposal validate` und `proposal check` DÜRFEN NICHT ihren festgestellten Prüfzustand als persistierten Proposal-Status schreiben. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0011 | SR-VER-0043 | SR-TC-0645 |
| SR-REQ-0646 | `proposal review start` MUSS die vollständig geprüfte Kontrollfolge nach Kapitel 10.3 atomar bis `in_review` veröffentlichen. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0013 | SR-VER-0043 | SR-TC-0646 |
| SR-REQ-0647 | Die Proposal-Fortsetzung MUSS dieselben echten menschlichen Freigabevoraussetzungen wie der nicht aufgeteilte Ablauf verlangen. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0011 | SR-VER-0043 | SR-TC-0647 |
| SR-REQ-0648 | Eine Änderung des Proposal-Fachinhalts MUSS sämtliche Freigaben älterer Inhaltsbindungen unwirksam machen. | SR-NEED-0003, SR-NEED-0008, SR-NEED-0009 | SR-VER-0043 | SR-TC-0648 |
| SR-REQ-0649 | Die Proposal-Positionsoperationen MÜSSEN die Indexgrenzen und Reihenfolgen aus Kapitel 11.10 exakt erfüllen. | SR-NEED-0001, SR-NEED-0008, SR-NEED-0013 | SR-VER-0043 | SR-TC-0649 |
| SR-REQ-0650 | Die vollständige Releaseabnahme MUSS die kontraktübergreifenden Fälle aus Anhang R mit an diese Spezifikationsversion gebundener Evidence nachweisen. | SR-NEED-0005, SR-NEED-0007, SR-NEED-0009 | SR-VER-0041 | SR-TC-0650 |

---

### 12.42 Explizite Verbindlichkeit und mehrsprachiger Inhalt

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0651 | Jedes regulär gespeicherte Requirement MUSS ab draft genau einen expliziten BCP-47-Sprach-Tag im Feld language besitzen. | SR-NEED-0001, SR-NEED-0020 | SR-VER-0044 | SR-TC-0651 |
| SR-REQ-0652 | Der Writer MUSS die Sprach-/Verbindlichkeitsparameter und den expliziten Sprachdefault nach Anhang S.2 im geplanten Ziel materialisieren. | SR-NEED-0001, SR-NEED-0013, SR-NEED-0020 | SR-VER-0044 | SR-TC-0652 |
| SR-REQ-0653 | SpecRoad DARF NICHT normative_force aus priority, requirement_kind, Detektorlabel oder Freitextschlüsselwort automatisch ableiten. | SR-NEED-0002, SR-NEED-0020 | SR-VER-0044 | SR-TC-0653 |
| SR-REQ-0654 | Der Renderer MUSS die deklarierte Verbindlichkeit und den unveränderten vollständigen Requirement-Sachverhalt getrennt nach Anhang S.2 darstellen. | SR-NEED-0015, SR-NEED-0020 | SR-VER-0044 | SR-TC-0654 |
| SR-REQ-0655 | Der Renderer DARF NICHT Requirement-Sätze zur Ergänzung von Modalverben, Negationen oder Übersetzungen automatisch umformulieren. | SR-NEED-0009, SR-NEED-0015, SR-NEED-0020 | SR-VER-0044 | SR-TC-0655 |
| SR-REQ-0656 | Die Metadatenprüfung MUSS die vier Verpflichtungsarten nach Anhang S.2 einschließlich ihrer Nichtgleichheit mit Prioritäten auswerten. | SR-NEED-0002, SR-NEED-0020 | SR-VER-0044 | SR-TC-0656 |
| SR-REQ-0657 | Eine Änderung von language oder normative_force MUSS als Fachinhaltsänderung nach dem bestehenden Lifecycle- und Kontextbindungsvertrag behandelt werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0020 | SR-VER-0044 | SR-TC-0657 |
| SR-REQ-0658 | Sprach-Tag-Syntax und Registerzustand MÜSSEN gemäß Anhang S.3 getrennt bestimmt werden. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0658 |
| SR-REQ-0659 | Jedes Release MUSS einen eingefrorenen und hashidentifizierten IANA-Registersnapshot nach Anhang S.3 für die offlinefähige Projektbindung liefern. | SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0659 |
| SR-REQ-0660 | Ein Wechsel des Sprachregisters DARF NICHT ohne expliziten fachlichen Change Plan den gebundenen Projektstand verändern. | SR-NEED-0009, SR-NEED-0014, SR-NEED-0020 | SR-VER-0045 | SR-TC-0660 |
| SR-REQ-0661 | Der Core MUSS alle syntaktisch gültigen BCP-47-Kennzeichnungen gemäß der Registry-/Private-use-Policy verarbeiten können, ohne seine Inhaltsverarbeitung auf die Mindestsprachenliste zu beschränken. | SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0661 |
| SR-REQ-0662 | Die Sprachzulässigkeit MUSS Basic Filtering mit den Grenz- und Aliasregeln aus Anhang S.5 verwenden. | SR-NEED-0002, SR-NEED-0020 | SR-VER-0045 | SR-TC-0662 |
| SR-REQ-0663 | Die Projekt-Sprachpolicy MUSS genau die vollständigen Felder, Defaults und Aktionswerte aus Anhang S.5 implementieren. | SR-NEED-0002, SR-NEED-0020 | SR-VER-0045 | SR-TC-0663 |
| SR-REQ-0664 | Mischungsdiagnosen MÜSSEN die exakte deklarationsbasierte Container-/Requirement-Auswahl aus Anhang S.5 verwenden. | SR-NEED-0015, SR-NEED-0020 | SR-VER-0045 | SR-TC-0664 |
| SR-REQ-0665 | Ein Tagvergleich MUSS den ausdrücklich konfigurierten Modus primary_language oder exact_tag gemäß Anhang S.5 berücksichtigen. | SR-NEED-0002, SR-NEED-0020 | SR-VER-0045 | SR-TC-0665 |
| SR-REQ-0666 | Eine Sprachpolicywarnung MUSS ihren Schweregrad erhalten und erst über den bestehenden Fail-Schwellwert in einen fehlschlagenden Aufruf eingehen. | SR-NEED-0007, SR-NEED-0020 | SR-VER-0045 | SR-TC-0666 |
| SR-REQ-0667 | Fachprofile und Sprachpakete MÜSSEN nach Anhang S.6 ohne globalen Gleichheitszwang der Inhaltssprachen zusammengesetzt werden. | SR-NEED-0002, SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0667 |
| SR-REQ-0668 | Fehlende Sprach-Lintcapabilities MÜSSEN als nicht verfügbar statt als bestanden ausgewiesen werden. | SR-NEED-0005, SR-NEED-0020 | SR-VER-0045 | SR-TC-0668 |
| SR-REQ-0669 | Die Core-Distribution MUSS die Metadaten-/Labelpakete und alle Mindestkennzeichnungen aus Anhang S.4 und S.6 bereitstellen. | SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0669 |
| SR-REQ-0670 | Die Verarbeitung natürlicher Fachtexte MUSS unabhängig von installierten Ubuntu-Locales und von der CLI-Anzeigesprache erfolgen. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0020 | SR-VER-0045 | SR-TC-0670 |
| SR-REQ-0671 | Normative Textbytes DÜRFEN NICHT beim Hashen, Formatieren oder Detektieren implizit Unicode-normalisiert werden. | SR-NEED-0009, SR-NEED-0020 | SR-VER-0044 | SR-TC-0671 |
| SR-REQ-0672 | HTML- und Markdownansichten MÜSSEN die Sprach-/Schreibrichtungsdarstellung aus Anhang S.3 ohne erfundene Richtungs- oder Regionsdetektion unterstützen. | SR-NEED-0015, SR-NEED-0020 | SR-VER-0045 | SR-TC-0672 |
| SR-REQ-0673 | Der Core DARF NICHT aus bloßen Wortlisten eine fachliche Modalitäts-, Widerspruchs- oder Übersetzungsprüfung als durchgeführt behaupten. | SR-NEED-0003, SR-NEED-0020, SR-NEED-0021 | SR-VER-0044 | SR-TC-0673 |
| SR-REQ-0674 | Die bestehende menschliche Freigabe MUSS die fachliche Bedeutung des Tupels aus normative_force und statement beurteilen, ohne einen Sprachdetektor als Ersatz anzuerkennen. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0020 | SR-VER-0044 | SR-TC-0674 |

### 12.43 Allgemeine Analyzer-Schnittstelle und Findings

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0675 | SpecRoad MUSS den Analyzer-Datenvertrag 1.0.0 aus Anhang T für unterschiedliche Analyzer, Capabilities und Subjectmodi implementieren. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0021 | SR-VER-0046 | SR-TC-0675 |
| SR-REQ-0676 | Analyzer-Descriptoren MÜSSEN das abschließende Feld-, Versions- und Identitätsschema aus Anhang T.2 erfüllen. | SR-NEED-0012, SR-NEED-0021 | SR-VER-0046 | SR-TC-0676 |
| SR-REQ-0677 | Ein Projekt- oder Importdescriptor DARF NICHT selbst eine Berechtigung zum Ausführen eines Workers erzeugen. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0046 | SR-TC-0677 |
| SR-REQ-0678 | Ein Analyzerrequest MUSS den vollständigen Identitäts- und Eingangsbindungsvertrag aus Anhang T.3 erfüllen. | SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0678 |
| SR-REQ-0679 | Der Request-Snapshothash MUSS die vollständige Subject-/Analyzer-/Settings- und Kontextauswahl ohne Betriebsmetadaten binden. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0679 |
| SR-REQ-0680 | Ein Analyzer MUSS ausschließlich die explizit exportierten Daten und deklarierte Kontextressourcen erhalten. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0046 | SR-TC-0680 |
| SR-REQ-0681 | Mehrere für Spracherkennung ausgewählte Statements MÜSSEN als eigenständige Subjects statt als zusammengefügter Text verarbeitet werden. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0046 | SR-TC-0681 |
| SR-REQ-0682 | Analyzerberichte MÜSSEN Runstatus und exakte Coverage nach Anhang T.4 ausweisen. | SR-NEED-0005, SR-NEED-0021 | SR-VER-0046 | SR-TC-0682 |
| SR-REQ-0683 | Jedes Finding MUSS die generischen Struktur- und Provenienzfelder aus Anhang T.4 erfüllen. | SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0683 |
| SR-REQ-0684 | SpecRoad MUSS unbekannte zulässige Finding-Namespaces und Extensions als Daten erhalten, ohne deren Semantik oder Ausführung zu erfinden. | SR-NEED-0012, SR-NEED-0021 | SR-VER-0046 | SR-TC-0684 |
| SR-REQ-0685 | Der Core DARF NICHT durch einen Analyzerbericht automatisch normative Artefaktfelder, Reifegrade, Reviews oder Verification Results verändern. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0685 |
| SR-REQ-0686 | Ein Analyzerbericht DARF NICHT allein durch Import als Evidence oder bestandener Produktnachweis gelten. | SR-NEED-0005, SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0686 |
| SR-REQ-0687 | Berechnete Reportaktualität MUSS die Zustände current, stale, unavailable und invalid gemäß Anhang T.8 unterscheiden. | SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0687 |
| SR-REQ-0688 | Eine Berichtsanzeige DARF NICHT die Originalbytes eines importierten Reports zur Aktualitätsfortschreibung verändern. | SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0688 |
| SR-REQ-0689 | SpecRoad MUSS die Analyzer-CLI-Befehle und vollständigen Seiteneffektklassen aus Anhang T.5 implementieren. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0021 | SR-VER-0046 | SR-TC-0689 |
| SR-REQ-0690 | Analyzerresultate MÜSSEN als explizite Dateien beziehungsweise stdout-Daten außerhalb des kanonischen Modells gespeichert werden. | SR-NEED-0009, SR-NEED-0011, SR-NEED-0021 | SR-VER-0046 | SR-TC-0690 |
| SR-REQ-0691 | Ein vollständiges Analyzer-Reportpackage MUSS seinen datentragenden Request und sämtliche ausgewählten Reports mit übereinstimmender Analysekennung und Snapshotbindung gemäß Anhang T.5 enthalten. | SR-NEED-0008, SR-NEED-0014, SR-NEED-0021 | SR-VER-0046 | SR-TC-0691 |
| SR-REQ-0692 | Die Importprüfung MUSS manipulierte Hashbindungen, unzulässige Felder sowie doppelte, fremde oder fehlende Pflichtsubjects entsprechend Anhang T.4 zurückweisen. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0046 | SR-TC-0692 |
| SR-REQ-0693 | Die Auswertung mehrerer gewählter Berichte MUSS abweichende Ergebnisse und Provenienzen sichtbar erhalten, statt nur erfolgreiche Findings auszuwählen. | SR-NEED-0003, SR-NEED-0021 | SR-VER-0046 | SR-TC-0693 |
| SR-REQ-0694 | Core-Validierung und strict-Linting DÜRFEN NICHT implizit eine Analyzer-Ausführung oder einen Modellimport starten. | SR-NEED-0007, SR-NEED-0018, SR-NEED-0021 | SR-VER-0048 | SR-TC-0694 |
| SR-REQ-0695 | Ein syntaktisch wie eine Anweisung aussehender Subjecttext MUSS als Analyseinhalt ohne Ausführungs- oder Rechtewirkung behandelt werden. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0046 | SR-TC-0695 |
| SR-REQ-0696 | Für ein nicht ausführbares externes Analyzer-Backend MUSS der Datenaustausch bereits funktionieren, während execution_supported ausdrücklich false bleibt. | SR-NEED-0012, SR-NEED-0021 | SR-VER-0046 | SR-TC-0696 |
| SR-REQ-0697 | Fachliche und betriebliche Analyzerresultatfelder MÜSSEN nach dem Hashprojektionsvertrag aus Anhang T.4 getrennt bleiben. | SR-NEED-0007, SR-NEED-0009, SR-NEED-0021 | SR-VER-0046 | SR-TC-0697 |

### 12.44 Implementierter py3langid-Adapter und vollständige Ausführung

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0698 | Das erste Zielrelease MUSS den realen, getesteten Adapter specroad.py3langid mit der Capability language_detection ausliefern. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0698 |
| SR-REQ-0699 | Der ausgelieferte Adapter MUSS py3langid 0.4.0 und das ausdrücklich gebundene mitgelieferte Modell als Referenzbackend nach Anhang T.6 verwenden. | SR-NEED-0012, SR-NEED-0021 | SR-VER-0047 | SR-TC-0699 |
| SR-REQ-0700 | Die Sprachdetektion MUSS als separate lokale Runtimekomponente verfügbar sein, ohne NumPy oder py3langid zur Voraussetzung der Core-Nutzung zu machen. | SR-NEED-0008, SR-NEED-0012, SR-NEED-0021 | SR-VER-0048 | SR-TC-0700 |
| SR-REQ-0701 | Jede Veröffentlichung MUSS die Offline-Zusatzpakete, ABI-/Pythonmatrix, Modellhashes und Lizenzdaten nach Anhang T.6 bereitstellen. | SR-NEED-0012, SR-NEED-0021 | SR-VER-0048 | SR-TC-0701 |
| SR-REQ-0702 | Der Core MUSS ausschließlich den vertrauenswürdigen bekannten Worker über den kontrollierten, shellfreien Startvertrag aus Anhang T.6 ausführen. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0048 | SR-TC-0702 |
| SR-REQ-0703 | Der Worker DARF NICHT Modelle, Importpfade, Shellkommandos oder Netzwerkziele aus Projekttexten beziehungsweise fremden Descriptoren ausführen. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0048 | SR-TC-0703 |
| SR-REQ-0704 | Der py3langid-Adapter DARF NICHT Netzwerk-, Trainings-, Webservice- oder automatische Installationsfunktionen bereitstellen. | SR-NEED-0011, SR-NEED-0021 | SR-VER-0048 | SR-TC-0704 |
| SR-REQ-0705 | Ein normaler Core-Aufruf und analyzer list MÜSSEN ohne Initialisierung von NumPy oder Sprachmodell auskommen. | SR-NEED-0008, SR-NEED-0018, SR-NEED-0021 | SR-VER-0048 | SR-TC-0705 |
| SR-REQ-0706 | Der erste Sprachadapter MUSS jeden ausgewählten vollständigen String nach dem Vorverarbeitungs- und Abstentionsvertrag aus Anhang T.7 verarbeiten. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0706 |
| SR-REQ-0707 | Die Erkennung MUSS den vollständigen Kandidatenraum des gebundenen Modells statt einer auf erlaubte Projektsprachen beschränkten Kandidatenliste verwenden. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0707 |
| SR-REQ-0708 | Publizierte Detektorscores MÜSSEN die normalisierte, quantisierte und ausdrücklich nicht kalibrierte Scoresemantik aus Anhang T.7 ausweisen. | SR-NEED-0003, SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0708 |
| SR-REQ-0709 | Die Entscheidung detected oder undetermined MUSS der geordneten Score-/Längen-/Abstentionstabelle aus Anhang T.7 entsprechen. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0709 |
| SR-REQ-0710 | Der Sprachvergleich MUSS die Vergleichs- und Grobkompatibilitätsregeln aus Anhang T.7 verwenden. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0710 |
| SR-REQ-0711 | Ein Detectorlabel DARF NICHT als Nachweis einer nicht tatsächlich erkannten Region, Schriftvariante oder Mandarin-Spezifizierung ausgegeben werden. | SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0711 |
| SR-REQ-0712 | Eine Sprachdetektion DARF NICHT die deklarierte language oder normative_force eines Requirements automatisch korrigieren. | SR-NEED-0003, SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0712 |
| SR-REQ-0713 | Die Analyzerpolicy MUSS die Defaults, Severityentscheidungen und getrennten Erfolgsbegriffe aus Anhang T.8 implementieren. | SR-NEED-0007, SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0713 |
| SR-REQ-0714 | Ein explizit angeforderter technisch nicht verfügbarer Analyzer MUSS einen vollständigen Verfügbarkeitsbericht und Exit Code 5 statt eines übersprungenen Erfolgs liefern. | SR-NEED-0007, SR-NEED-0008, SR-NEED-0021 | SR-VER-0048 | SR-TC-0714 |
| SR-REQ-0715 | Analyzerarbeit MUSS den Checkpoint- und Fortsetzungsvertrag aus Anhang T.5 und T.9 mit oder ohne ausdrücklich angegebenes `--work-dir` erfüllen. | SR-NEED-0017, SR-NEED-0018, SR-NEED-0019, SR-NEED-0021 | SR-VER-0048 | SR-TC-0715 |
| SR-REQ-0716 | Eine freiwillige Fortsetzung MUSS die identische Analysekennung, Request-Snapshot- und Enginebindung verwenden oder einen ausdrücklich neuen Analyseauftrag ausweisen. | SR-NEED-0017, SR-NEED-0019, SR-NEED-0021 | SR-VER-0048 | SR-TC-0716 |
| SR-REQ-0717 | Nach Abschluss oder Abbruch eines Analyzeraufrufs DARF NICHT ein von ihm gestarteter Worker als Hintergrundprozess weiterlaufen. | SR-NEED-0011, SR-NEED-0018, SR-NEED-0021 | SR-VER-0048 | SR-TC-0717 |
| SR-REQ-0718 | Der Standardlauf MUSS Analyzer seriell mit höchstens einem gleichzeitig geladenen Modell ausführen. | SR-NEED-0018, SR-NEED-0021 | SR-VER-0048 | SR-TC-0718 |
| SR-REQ-0719 | Ein tatsächlicher Hostblocker MUSS gemäß Anhang T.9 ohne stille Textkürzung und ohne endlosen fortschrittslosen Retry berichtet werden. | SR-NEED-0018, SR-NEED-0019, SR-NEED-0021 | SR-VER-0048 | SR-TC-0719 |
| SR-REQ-0720 | Die reale Adapterabnahme MUSS die eingefrorenen mehrsprachigen Korpus- und Fehlfallziele aus Anhang T.10 nachweisen. | SR-NEED-0005, SR-NEED-0020, SR-NEED-0021 | SR-VER-0047 | SR-TC-0720 |
| SR-REQ-0721 | Die Analyzer-Performanceabnahme MUSS den getrennten Gesamtprozess-CPU-/RSS-Vertrag aus Anhang T.10 messen. | SR-NEED-0005, SR-NEED-0018, SR-NEED-0021 | SR-VER-0048 | SR-TC-0721 |
| SR-REQ-0722 | Die Reproduzierbarkeitsprüfung MUSS Core-Determinismus, identische Engineprojektionen und sprachliche Cross-Runtime-Entscheidungstests nach Anhang T.9 unterscheiden. | SR-NEED-0007, SR-NEED-0012, SR-NEED-0021 | SR-VER-0048 | SR-TC-0722 |

### 12.45 Migration, Austausch und geschlossene SRX-Präzision

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0723 | Der Austausch von Requirements MUSS language und normative_force über die expliziten CSV-/NDJSON-/ReqIF-Attribute aus Anhang S.7 erhalten oder einen vorhandenen Verlust ausweisen. | SR-NEED-0014, SR-NEED-0020 | SR-VER-0049 | SR-TC-0723 |
| SR-REQ-0724 | Die Übernahme alter Entwurfsanforderungen MUSS ein autorisiertes explizites Mapping von Sprache, Verbindlichkeit und Zielaussage nach Anhang S.7 verlangen. | SR-NEED-0009, SR-NEED-0014, SR-NEED-0020 | SR-VER-0049 | SR-TC-0724 |
| SR-REQ-0725 | Die Migration DARF NICHT unveränderbare historische Nachweise zur Ergänzung neuer Sprach- oder Verbindlichkeitsfelder überschreiben. | SR-NEED-0009, SR-NEED-0014, SR-NEED-0020 | SR-VER-0049 | SR-TC-0725 |
| SR-REQ-0726 | Die Referenztests MÜSSEN den vollständigen Mehrsprachen-/Analyzer-Roundtrip mit erhaltenen Fachhashes und getrennten Reportdateien nach Anhang S/T abdecken. | SR-NEED-0008, SR-NEED-0014, SR-NEED-0021 | SR-VER-0049 | SR-TC-0726 |
| SR-REQ-0727 | Die SRX-Auswertung MUSS die explizite projektgebundene Zahlenpolicy aus Anhang U.1 mit Default 34 signifikanten Dezimalziffern verwenden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0050 | SR-TC-0727 |
| SR-REQ-0728 | SRX-Arithmetik MUSS die exakten Werte- und JCS-Roundtripgrenzen aus Anhang U.2 ohne stille Rundung anwenden. | SR-NEED-0002, SR-NEED-0012 | SR-VER-0050 | SR-TC-0728 |
| SR-REQ-0729 | Numerische Fehler MÜSSEN die disjunkten Diagnosegründe aus Anhang U.2 erzeugen, statt vom globalen Python-Decimal-Kontext abhängig zu sein. | SR-NEED-0007, SR-NEED-0012 | SR-VER-0050 | SR-TC-0729 |
| SR-REQ-0730 | Die SRX-Testabnahme MUSS sämtliche Entscheidungsvektoren aus Anhang U.3 einschließlich veränderter Prozessdefaults nachweisen. | SR-NEED-0005, SR-NEED-0012 | SR-VER-0050 | SR-TC-0730 |

### 12.46 Portabler Projekt-Rundweg über PatchHarbor

Anhang W legt den Transportvertrag für SR-SCN-0013 fest. Die neue
PatchHarbor-Version mit CPython-3.10-/3.11-Unterstützung ist die Produktbasis;
das ersetzt weder einen konkreten Distributionshash noch den Nachweis der
benötigten öffentlichen API-Fähigkeiten. Diese Anforderungen sind noch offen.

| ID | Normative Anforderung | Quelle | Verifikation | Testfall |
|---|---|---|---|---|
| SR-REQ-0731 | Die Transportintegration MUSS PatchHarbor ausschließlich über die dokumentierte öffentliche Python-API ansprechen und fehlende erforderliche API-Fähigkeiten ohne CLI-Fallback, private Core-Imports oder eigene Nachbildung des PatchHarbor-Formats als nicht verfügbar melden. | SR-NEED-0008, SR-NEED-0012 | SR-VER-0051 | SR-TC-0731 |
| SR-REQ-0732 | Das Transportprofil MUSS mit einer gebundenen, CPython 3.10 bis 3.14 unterstützenden PatchHarbor-Distribution offline nutzbar sein, ohne deren Laden oder Installation für die übrigen Core-Befehle vorauszusetzen. | SR-NEED-0008, SR-NEED-0012 | SR-VER-0051 | SR-TC-0732 |
| SR-REQ-0733 | Der Hinexport MUSS ein vollständiges Paket nach W.2 mit SpecRoad-Distribution, unverändertem PatchHarbor-Result einschließlich dessen Runtime, verifiziertem Vollprojektbundle und einem lückenlosen Größen-/Hashinventar erzeugen. | SR-NEED-0008, SR-NEED-0009 | SR-VER-0051 | SR-TC-0733 |
| SR-REQ-0734 | Der Hinexport MUSS Projekt-ID, Scope, Modellwurzel und alle Projektbytes an denselben vollständig geprüften Result-Zustand nach W.3 binden und bei Abweichung oder unvollständiger Closure ohne gültiges Hinpaket abbrechen. | SR-NEED-0003, SR-NEED-0009 | SR-VER-0051 | SR-TC-0734 |
| SR-REQ-0735 | Das Öffnen eines Hinpakets MUSS die Vertrauens-, Versions-, Plattform- und Integritätsprüfungen aus W.4 vor dem Laden einer mitgelieferten Runtime durchführen. | SR-NEED-0008, SR-NEED-0011 | SR-VER-0051 | SR-TC-0735 |
| SR-REQ-0736 | Die Materialisierung in der Sandbox MUSS ohne Git, Shell, Netzwerk oder Paketinstallation einen neuen, vollständig geprüften Projektroot nach W.4 erzeugen und vorhandene Ziele sowie Partial-Bundle-Schreibgrenzen erhalten. | SR-NEED-0008, SR-NEED-0011 | SR-VER-0051 | SR-TC-0736 |
| SR-REQ-0737 | Hin- und Rückexport MÜSSEN denselben Befehl `bundle create --profile ai-runtime` mit expliziter Richtung verwenden; der Rückexport MUSS seine PatchHarbor-Bindungswerte unverändert aus dem ursprünglichen Result übernehmen. | SR-NEED-0001, SR-NEED-0008 | SR-VER-0051 | SR-TC-0737 |
| SR-REQ-0738 | Der Rückexport MUSS nach W.5 ausschließlich einen vollständig ausgewiesenen Proposal samt benötigten passiven Daten und einem vertrauenswürdig vorgegebenen Entrypoint über `patchharbor.api.pack_patch` verpacken. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0051 | SR-TC-0738 |
| SR-REQ-0739 | Der lokale Integrationsadapter MUSS Paketintegrität, Referenzbindung, zulässigen Payload, Entrypoint und aktuelles Ziel vor dem ersten PatchHarbor-Payloadwrite prüfen und erst nach ausdrücklicher Übernahmeautorisierung die öffentliche `patchharbor.api.apply` aufrufen. | SR-NEED-0003, SR-NEED-0011 | SR-VER-0051 | SR-TC-0739 |
| SR-REQ-0740 | Die lokale Rückübernahme MUSS die normativen Fachänderungen bis zum gültigen menschlichen Review und transaktionalen Proposal-Apply unveröffentlicht lassen; Transporterfolg und importierter Proposal DÜRFEN NICHT als fachliche Freigabe oder angewendete Änderung gelten. | SR-NEED-0003, SR-NEED-0008 | SR-VER-0051 | SR-TC-0740 |
| SR-REQ-0741 | Wiederholung, geänderte Basis, Paketfehler und Abbruch MÜSSEN nach W.6 ohne doppelte Fachänderung, stilles Rebase, Verlust fremder Dateien oder fingierten Erfolg behandelt werden. | SR-NEED-0003, SR-NEED-0009, SR-NEED-0011 | SR-VER-0051 | SR-TC-0741 |
| SR-REQ-0742 | Die Featureabnahme MUSS den vollständigen API-basierten Rundweg, die negativen Sicherheits-/Zustandsfälle und jedes angebotene Runtimeprofil nach W.7 mit realen Paketartefakten und gebundener Laufzeit-Evidence nachweisen. | SR-NEED-0005, SR-NEED-0008, SR-NEED-0012 | SR-VER-0051 | SR-TC-0742 |

---

## 13. Diagnosekatalog Version 0.2

Die folgenden Codes sind der verbindliche Mindestkatalog. Weitere Codes dürfen innerhalb derselben Major-Ausgabeformatversion ergänzt werden, sofern bestehende Semantik nicht geändert wird.

| Code | Default-Schwere | Bedeutung |
|---|---|---|
| SRV001 | error | JSON kann nicht geparst werden. |
| SRV002 | error | JSON Schema ist verletzt. |
| SRV003 | error | Schema-Version wird nicht unterstützt oder benötigt Migration. |
| SRV010 | error | Artefakt-ID ist doppelt vergeben. |
| SRV011 | error | ID, ID-Schema, Typpräfix oder Dateiname stimmen nicht überein. |
| SRV012 | error | Revision wurde nicht korrekt erhöht. |
| SRV013 | error | ID-Erzeugung oder Identitätsprovenienz ist ungültig. |
| SRV020 | error | Relationsziel fehlt. |
| SRV021 | error | Relationstyp oder Quell-/Zielkombination ist unzulässig. |
| SRV022 | error | Verbotener Relations- oder Dokumentzyklus. |
| SRV023 | warning | Erwartete Traceability-Beziehung fehlt. |
| SRV024 | warning | Artefakt ist nach aktivem Profil verwaist. |
| SRV025 | warning | Relation ist unreviewed. |
| SRV026 | warning | Relation ist suspect. |
| SRV027 | error | Relation oder aktuelles Relationsreview ist invalid; Zusatzgrund unterscheidet strukturellen Fehler von `current_review_rejected`/Kategorie `review_outcome` nach 11.13. |
| SRV030 | error | Reifegrad- oder Statusübergang ist unzulässig. |
| SRV031 | error | Approved-Artefakt besitzt keine hinreichende Herkunft. |
| SRV032 | error | Approved Requirement besitzt keine gültige Verifikation. |
| SRV033 | error | Offener Platzhalter in approved Artefakt. |
| SRV034 | error | Projekt ist durch Writer-Lock oder Recovery-Zustand gesperrt. |
| SRV040 | error | Berechnetes `verification_result=passed` ohne gültige aktuelle Evidence. |
| SRV041 | warning | Evidence ist stale. |
| SRV042 | error | Recorded Evidence wurde verändert. |
| SRV043 | warning | Testergebnis ist nicht oder mehrdeutig gemappt. |
| SRV044 | warning | Code-Referenz ist stale, missing oder mehrdeutig relokalisiert. |
| SRV050 | warning | Unmessbarer oder mehrdeutiger Begriff. |
| SRV051 | warning | Expliziter menschlicher Reviewhinweis auf mehrere Verpflichtungen; keine automatische semantische Diagnose aus Wortzählung. |
| SRV052 | warning | normative_force=should ohne vollständige Abweichungsmetadaten; der Schemafehler bleibt unabhängig davon wirksam. |
| SRV053 | warning | Verbotenes oder undefiniertes Glossarwort. |
| SRV060 | error | Baseline-, Bundle- oder Modellwurzelhash stimmt nicht. |
| SRV061 | error | Migration hat keinen unterstützten Pfad oder verletzt eine Invariante. |
| SRV062 | warning | Migration oder Austausch würde Information verlieren. |
| SRV070 | error | Proposal- oder Change-Plan-Schema ist ungültig. |
| SRV071 | error | Basis ist stale oder eine Operation kollidiert. |
| SRV072 | error | Direkter normativer Schreibzugriff eines AI-Akteurs wurde verweigert. |
| SRV073 | error | Request-ID wurde mit abweichender Operation wiederverwendet. |
| SRV080 | error | Pfad oder Symlink verlässt den erlaubten Root. |
| SRV081 | error | Explizite harte Struktur-, Sicherheits- oder Formatgrenze überschritten; kein weiches Arbeitsziel. |
| SRV082 | error | Transaktionsjournal ist unvollständig oder corrupt. |
| SRV083 | error | Unsichere XML-, ZIP- oder Archivstruktur. |
| SRV090 | error | Importmapping oder externe Identität ist ungültig. |
| SRV091 | warning | Import- oder Exportobjekt wird übersprungen oder verlustbehaftet abgebildet. |
| SRV100 | error | Merge-Konflikt ist nicht aufgelöst. |
| SRV101 | error | Identitätskollision zwischen Merge- oder Importständen. |
| SRV110 | error | SRX-Version, Operator, Typ oder Ausdruck ist ungültig. |
| SRV111 | error | Harte SRX-AST-Strukturgrenze verletzt; reine Iterations- oder Rechenziele werden fortgesetzt. |
| SRV120 | error | Dokument-, Abschnitts- oder View-Komposition ist ungültig. |
| SRV130 | error | Konfiguration oder Applicability-Auswertung ist ungültig. |
| SRV131 | error | Anwendbares Artefakt hängt von ausgeschlossenem Pflichtartefakt ab. |
| SRV140 | error | Scope Descriptor oder Scope-Closure ist ungültig. |
| SRV141 | error | Erforderliches Scope-Ziel ist durch Konfiguration ausgeschlossen. |
| SRV142 | error | Aktive Profile sind nach dem Kompositionsvertrag unvereinbar. |
| SRV143 | error | Spezialstatus und `maturity` bilden eine unzulässige Kombination. |
| SRV144 | error | Ein berechnetes Verification Result wurde als normatives Feld gespeichert. |
| SRV145 | error | Proposal-Authoring-Operation oder Change-ID ist ungültig. |
| SRV146 | error | Gebundene Change-Plan-Metadaten oder Ergebnisressourcen stimmen nicht. |
| SRV147 | error | External Identity ist doppelt oder inkonsistent gebunden. |
| SRV148 | error | Lokale und externe Importprojektion wurden divergent geändert. |
| SRV149 | error | Recovery-Discard ist im aktuellen Transaktionszustand unsicher. |
| SRV150 | error | Schreibversuch auf einem partiellen Read-only-Bundle. |
| SRV151 | error | Boundary Reference fehlt oder stimmt nicht mit der Relation überein. |
| SRV152 | error | Query-Grammatik, Projektion, Sortierung oder Ergebnisgrenze ist ungültig. |
| SRV153 | error | Content-Block-Payload verletzt das Schema seiner Blockart. |
| SRV154 | error | Dokument-Include- oder Contains-Zyklus. |
| SRV155 | error | Kein oder mehr als ein aktives Primärspezifikationsdokument. |
| SRV156 | warning | Code-Anker ist mehrdeutig und deshalb stale. |
| SRV157 | error | ZIP-Eintrag verletzt das kanonische oder sichere Archivprofil. |
| SRV158 | error | Request- oder Transaktionsreceipt fehlt, ist korrupt oder widerspricht seinem gebundenen Operationshash. |
| SRV159 | error | Requirement besitzt keinen eindeutigen primären Testfall. |
| SRV160 | error | Szenario-Testkette deckt ihren festgelegten Requirement-Umfang nicht ab. |
| SRV161 | error | Performance-Evidence bindet keine passende Referenzplattform. |
| SRV162 | error | Durch fachliches Review bestätigtes Compound Requirement; keine Sprachverständnisfunktion des Core. |
| SRV163 | error | Ausführbare Runtime oder benötigte Distributionsvoraussetzung wird nicht unterstützt. |
| SRV164 | error | Der ausgewählte Aufrufkontext oder benötigte Runtime-/Projektpfad ist nicht verfügbar. |
| SRV165 | info | Eine angeforderte Umgebungsvoraussetzung oder Ressourcenbeobachtung ist nicht nachweisbar. |
| SRV166 | info | Weiches Arbeitsziel überschritten; sparsame Weiterarbeit oder gesicherte Fortsetzung, kein fachlicher Gate-Fehler. |
| SRV167 | info | Der kurze Preflight benötigt eine weitere begrenzte Metadatenphase; bis zur Klärung wird kein regulärer Projektzugriff freigegeben. |
| SRV168 | error | Fachoperation wegen Recoverybedarf nicht begonnen; Recoveryergebnis und notwendiger Wiederaufruf werden ausgewiesen. |
| SRV169 | info | Gesicherter Arbeitsstand erfordert einen weiteren Aufruf; noch keine vollständige fachliche Erfolgsaussage. |
| SRV170 | error | Notwendiger Checkpoint-/Work-Paketteil fehlt, ist manipuliert oder inkompatibel. |
| SRV171 | error | Ein tatsächlicher Ressourcen-/Dateisystemblocker verhindert auch den dokumentierten sparsamen Mindestschritt. |
| SRV172 | error | Legacy-Manifest oder unveränderbare Originalhashbindung ist ungültig. |
| SRV173 | error | Proposal-Inhaltsbindung oder erforderliche menschliche Freigabe ist nicht aktuell beziehungsweise nicht vorhanden. |
| SRV174 | error | Change-Plan-Metadatenpolicy ist unbekannt, für die Operation unzulässig oder widerspricht den Zielbytes. |
| SRV175 | error | Bewertungsdescriptor, Standbindung, Pflichtschlüssel oder Ablösungsstruktur ist ungültig; unzulässige Akteursentscheidung wird als Sicherheitsverweigerung behandelt. |
| SRV176 | warning | Bewertungsauswahl ist unvollständig oder eine Laufablösung ist nicht mehr wirksam; reason unterscheidet fehlende Auswahl, fehlenden Nachweis und geänderte Bindung. |
| SRV177 | error | BCP-47-Tag syntaktisch ungültig. |
| SRV178 | warning | Tag im gebundenen Register nicht verifiziert; Policy kann die Schwere festlegen. |
| SRV179 | error | Deklarierte Sprache verletzt Erlaubnisranges; Policy severity. |
| SRV180 | warning | Deklarierte Requirement-Sprachmischung im ausgewählten Container; Policy severity. |
| SRV181 | error | Unspezifische Requirement-Sprache und/mul/zxx gemäß Policy. |
| SRV182 | info | Sprachpaket- oder Lintcapability nicht verfügbar; keine behauptete Prüfung. |
| SRV183 | error | Normative-force-Feld oder bedingter Should-Vertrag ungültig. |
| SRV184 | error | Explizit angeforderter Analyzer nicht verfügbar; Code 5 bei Ausführungsauftrag. |
| SRV185 | error | Analyzerreport-/Requestschema oder Hashintegrität ungültig. |
| SRV186 | error | Gewählter Analyzerbericht ist für die aktuelle Bewertung stale oder nicht prüfbar. |
| SRV187 | warning | Detektierte Grundsprache weicht von der Deklaration ab; Policy severity. |
| SRV188 | info | Detektor trifft keine belastbare Entscheidung nach seiner Scorepolicy. |
| SRV189 | info | Nur grobe Sprachkompatibilität, keine Script-/Regions-/Mandarinbestätigung. |
| SRV190 | info | Deklaration für den Detektorvergleich nicht vergleichbar. |
| SRV191 | warning | Ausgewählte Analyzer melden voneinander abweichende Beobachtungen. |
| SRV192 | error | Backend liefert ungültigen Score oder inkonsistente Ergebnisdaten. |
| SRV193 | error | Nicht autorisierte Analyzer-Ausführungsart; keine dynamische Pluginfreigabe. |
| SRV194 | error | Analyzercoverage unvollständig oder zugeordnete Subjectmenge ungültig. |
| SRV195 | error | Analyzerdependency oder Modell verletzt die vertrauenswürdige Paket-/Hashbindung. |
| SRV196 | error | Explizites Sprach-/Verbindlichkeitsmapping für Migration oder Import fehlt. |
| SRV197 | error | SRX-Zahlenfehler nach Anhang U mit spezifischem, nicht stillschweigend gerundetem Grund. |

Jede konkrete Diagnose muss die in `SR-REQ-0089` festgelegten Felder bereitstellen, soweit sie für den Fehler bestimmbar sind. Eine Schweregradüberschreibung durch Profile darf einen strukturellen Sicherheits-, Integritäts-, Identitäts-, Recorded-Evidence-, Transaktions- oder Path-Traversal-Fehler nicht unter `error` absenken.

---

## 14. Verifikationsplan

| ID | Prüfbereich | Methode/Verfahren | Bestehenskriterium |
|---|---|---|---|
| SR-VER-0001 | Projektinitialisierung und Konfiguration | Automatisierte CLI-Integrationstests in leeren, bestehenden und fehlerhaften Verzeichnissen. | Sollstruktur und effektive Konfiguration sind korrekt; bestehende Daten bleiben unverändert; Fehler liefern definierte Exit Codes. |
| SR-VER-0002 | Kanonisches Datenmodell und Persistenz | Schema-, Roundtrip-, Canonicalization- und Golden-File-Tests. | Gültige Modelle bleiben verlustfrei; ungültige werden abgewiesen; Hashes und Normalformen entsprechen Referenzvektoren. |
| SR-VER-0003 | IDs, Revisionen und Provenienz | Property- und Baseline-Vergleichstests. | Duplikate, Wiederverwendung, unzulässige Revisionen und fehlende Provenienz werden erkannt. |
| SR-VER-0004 | Artefakttypen und Lebenszyklus | Zustands- und Pflichtfeldtests für jeden Artefakttyp. Ergänzend die reinen und gemischten Lifecycle-Sollfälle aus 9.6.3 und Anhang R prüfen. | Erlaubte Übergänge funktionieren; verbotene werden ohne Teiländerung abgewiesen. |
| SR-VER-0005 | Relationsgraph und Traceability | Graphfixtures mit gültigen, fehlenden, zyklischen, symmetrischen und typwidrigen Beziehungen. | Graphintegrität, inverse Sichten, fehlende Traces und Orphans entsprechen dem Vertrag. |
| SR-VER-0006 | Requirement-Profile und Glossar | Golden-File-Tests für deutsche und englische Profile, Semantik und Glossar. | Pflichtfelder, normative Schlüsselwörter, Messbarkeit und Terminologie werden reproduzierbar geprüft. |
| SR-VER-0007 | Validation und Diagnosen | Mindestens ein Fixture je Diagnosecode und Ausgabeformat. | Code, Schwere, Pfad, Position, Ursprung, Begründung und Remediation stimmen. |
| SR-VER-0008 | Rendering, Query, Trace, Impact und Diff | Golden-File- und Graphabfragetests gegen Arbeitsstand, Baseline, Git-Ref, Bundle und Projektpfad. | Ansichten sind deterministisch; Filter, Traversierungen, Impact und Diff liefern erwartete Mengen und Klassen. |
| SR-VER-0009 | Release, Milestone, Task und Roadmap | End-to-End-Fixtures mit mehreren Releases, Milestones, Abhängigkeiten, Risiken und Tasks. | Roadmap und Readiness werden ausschließlich aus dem Modell abgeleitet und vollständig erklärt. |
| SR-VER-0010 | Verification, Tests, Evidence und Coverage | Fixtures mit bestandener, fehlgeschlagener, veralteter und gewavter Evidence. | Status und Coverage entsprechen exakt Subjects, Revisionen, Contracts und Nachweisen. |
| SR-VER-0011 | Baselines | Erzeugen, Verifizieren, Manipulieren, Materialisieren und Vergleichen von Baselines. | Unveränderte Baselines bestehen; jede Manipulation wird erkannt; Vergleiche sind vollständig. |
| SR-VER-0012 | KI-Proposals und isolierter Check | Integrationstests für alle Change-Plan-Operationen, stale Bases, Reviews und Fehler während Apply. | Check verändert Arbeitsstand nicht; Apply benötigt gültige menschliche Freigabe und ist recoverbar. |
| SR-VER-0013 | CLI, Git, CI und Agentenbedienung | Black-box-Tests aller Befehle, Optionen, TTY-Modi, Exit Codes und Git-Ref-Fälle. | stdout, stderr, JSON, SARIF, Hilfen, Farben und Exit Codes erfüllen die Verträge. |
| SR-VER-0014 | Sicherheit und Robustheit | Tests mit Traversal, Symlinks, XML-/ZIP-Angriffen, übergroßen Eingaben, Fremdcode und konkurrierenden Schreibern. | Kein Zugriff außerhalb erlaubter Roots, kein Netzwerk/Fremdcode und kein stiller Ressourcenüberlauf. |
| SR-VER-0015 | Determinismus und Performance | Wiederholungen unter verschiedenen Locale-/Timezone-Einstellungen und Benchmarks. | Hashes und Ausgaben sind identisch; Zeit- und Speichergrenzen werden eingehalten. |
| SR-VER-0016 | Endabnahme | Durchführung aller leitenden Szenarien in einem Referenzprojekt. | Alle Szenarien bestehen; keine offenen Fehlerdiagnosen; vollständige Requirement-Traceability. |
| SR-VER-0017 | Python-, Abhängigkeits- und Sandbox-Portabilität | Black-box- und Importtests der portablen Distributionen in netzwerkisolierten Python-Sandboxen. | Der bisherige Core-Roundtrip funktioniert ohne Drittanbieterpaket, Root, TTY, Paketmanager, Compiler oder Dienst. |
| SR-VER-0018 | CLI-Authoring und kollisionsresistente Identitäten | Black-box-Tests aller direkten Schreibbefehle, Dry-Runs, AI-Verweigerung und massenhafte parallele ID-Erzeugung. Gekoppelte Review-Pläne einschließlich Dry-Run, verweigerter Feldkombinationen und eindeutiger Schreib-/Bewertungsergebnisse aus 11.13 prüfen. | Alle Authoring-Pfade erzeugen korrekte Change Plans; keine Kollision oder zentrale Sequenz; Dry-Run ist schreibfrei. |
| SR-VER-0019 | Transaktionen und Recovery | Crash-Injection nach jeder dauerhaften Grenze, Journalmanipulation und Lock-/Recovery-Tests. Crashgrenzen der atomaren Review-/Freigabeänderung und der vollständigen Restore-Transaktion aus 10.7.1 prüfen. | Nach Recovery entspricht die Modellwurzel exakt Basis oder vollständigem Ziel; inkonsistente Journale werden sicher verweigert. |
| SR-VER-0020 | Schema- und Datenmigration | Plan-, Apply-, Verify-, Idempotenz-, Verlust- und Restore-Tests einschließlich 0.1→0.2. | Migration ist gesichert, transaktional, nachvollziehbar und erhält alle nicht akzeptierten Informationen. |
| SR-VER-0021 | Relationsreviews und Suspect-Propagation | Fixtures mit Endpunktänderungen, Reviews, Import, Merge und Readiness. Den vollständigen negativen und später positiven Review-CLI-Verlauf aus 11.13 mit Revisionen, Diagnose und Approval-Rücknahme nachweisen. | current, unreviewed, suspect und invalid werden korrekt berechnet und in Gates berücksichtigt. |
| SR-VER-0022 | SRX 1.0 | Normative Operator-Testvektoren, Typ-, Missing-, Grenzwert-, Ressourcen- und Sicherheitsfälle. | Jeder Operator und Fehlerfall erfüllt exakt die versionierte Semantik; kein I/O oder nicht deterministisches Verhalten. |
| SR-VER-0023 | Dokumente, Views und Diagrammquellen | Kompositions-, Zyklus-, Rendering-, View- und Golden-File-Tests. | Dokumente und Sichten sind korrekt, sicher, byte-deterministisch und duplizieren keine normativen Inhalte. |
| SR-VER-0024 | Import und Export | ReqIF/ReqIFZ-, CSV- und NDJSON-Roundtrips, Mapping-, Verlust-, XML- und ZIP-Sicherheitstests. | Schnittmengeninhalte bleiben semantisch erhalten; Verluste und Konflikte sind vollständig ausgewiesen. |
| SR-VER-0025 | Evidence-Import und Code-Traceability | JUnit-, SARIF-, Generic-Import-, Mapping-, Duplikat- und Code-Relokationstests. | Evidence bindet korrekte Provenienz; Code-Referenzen werden als current, relocated, stale oder missing klassifiziert. |
| SR-VER-0026 | Semantischer Dreiwege-Merge | Feld-, Array-, Relations-, Lifecycle-, ID-Kollisions- und Konfliktauflösungstests. | Unabhängige Änderungen werden deterministisch gemerged; Konflikte werden nie still gelöst; Apply ist transaktional. |
| SR-VER-0027 | Selbstbeschreibung, Idempotenz, Bundles und Runtime-Matrix | Schema-/Command-Snapshots, Request-Retry-Tests, deterministische Bundle-Tests und Sandbox-Matrix CPython 3.10–3.14. Kanonische project-/partial-Roundtrips, Payload-Manifest-Bijektion und externe Voll-ZIP-Hashbindung aus Anhang E prüfen. | Agentenverträge sind vollständig; Retries duplizieren nichts; Bundles sind sicher; beide Distributionen bestehen die Matrix. |
| SR-VER-0028 | Konfigurationen und Wiederverwendung | Varianten-, Vererbungs-, Applicability-, Dependency-, Baseline-, Diff- und Merge-Tests. | Konfigurationsumfänge sind deterministisch und konsistent; Wiederverwendung erzeugt keine normativen Kopien. |
| SR-VER-0029 | Scope-Closure, Relationsmatrix und Profilkomposition | Testvektoren für jede Scope-Art, jeden Relationstyp und alle Profil-Mergefälle. | Seed-Mengen, Fixpunkte, Boundary References, Quell-/Zielakzeptanz, Konflikte und Profilhash entsprechen exakt den normativen Tabellen. |
| SR-VER-0030 | Proposal-Authoring, Change-Metadaten, Spezial-Lifecycle und Verification Result | Black-box-, Schema-, Golden-Plan- und Zustandsmatrix-Tests. | Proposal-Befehle sind vollständig; gespeicherte Pläne ergeben unabhängig vom Apply-Zeitpunkt denselben Zielhash; Spezialzustände und Verification Results sind korrekt. |
| SR-VER-0031 | External Identities, Import-Dreifachvergleich, Recovery und Formatierung | ReqIF-Relationsroundtrips, Dreiwege-Importfixtures, Crash-/Corrupt-Recovery und Byte-Normalisierungstests. Vollständige und unvollständige Restore-Quellen sowie unveränderte historische Zusatzressourcen nach 10.7.1 prüfen. | Externe Identitäten bleiben erhalten; Konflikte werden erkannt; Recovery endet nur in Basis/Ziel; Formatierung verändert keine Semantik. |
| SR-VER-0032 | Dokumentpayloads, Query, JSON und Befehlsklassen | Schema-, CommonMark-, Include-, Query-, Envelope- und Seiteneffekt-Golden-Tests. | Jede Blockart, Query, JSON-Ausgabe und Befehlsklasse erfüllt den vollständigen Vertrag. |
| SR-VER-0033 | Partielle Bundles, ZIP und portable Idempotenz | Bytevergleich über CPython-Versionen, Boundary-/Read-only-Tests und Receipt-Roundtrips. | Archive sind byteidentisch und sicher; partielle Bundles erlauben nur den festgelegten Umfang; Retries bleiben nach Projektbundle-Transfer idempotent. |
| SR-VER-0034 | Requirement-Testfälle, Szenarioketten, Codezustand und Performance | Vollständigkeitsprüfung aller `SR-TC-*`, End-to-End-Matrix, Code-Anker-Testvektoren und reproduzierbare Benchmarks. | Alle Requirements dieser Dokumentversion besitzen einen bestandenen Testfall; alle Szenarioketten bestehen; Codezustände und Performance-Evidence entsprechen den normativen Verträgen. |
| SR-VER-0035 | Unabhängige Runtimeaufrufe und sichere Fortsetzung | Prozess-/Pfad-/Sandboxwechsel, gelöschter Cache, verifizierter Vollbundle-Transfer, stale Locks und unterbrochene Journale. | Kein vorheriger Sessionzustand erforderlich; gleiche fachliche Hashes und Receiptwirkung bei erhaltenem Stand; keine Read-only-Recoverywrites oder erfundene Wiederherstellung verlorener Daten. |
| SR-VER-0036 | Umgebungsdiagnose und Betriebsbeobachtung | Black-box-Schema- und Seiteneffekttests mit fehlendem Projekt, unlesbaren Pfaden, unbekannten Quoten und simuliertem Prozessstartfehler. | Diagnosevertrag, null-/unknown-Werte, Exit Codes und Messwerttrennung stimmen; keine Probe-Writes, externen Healthchecks oder fachlichen Gültigkeitsbehauptungen. |
| SR-VER-0037 | Weiche Arbeitsbudgets und sichere Fortsetzung | Grenzwert-/Zählertests, weiche Budgetüberschreitung, große Payloads, viele Pfade, Arbeitsschrittwechsel und echte Crash-Injection. | Vollständiger Restauftrag bleibt erhalten; weiche Überschreitung allein erzeugt keinen Fehler; bei echten Abbrüchen Basis-/Zielzustand oder gesperrter erhaltener Recoveryzustand nach O.4. |
| SR-VER-0038 | Effizienter Start und Cache-/Profilparität | Benchmarks nach 14.6; identische vollständige Aufträge mit beiden Ressourcenprofilen sowie fehlenden, gültigen und manipulierten Caches. | Gemessene Start-/CPU-/RSS-Grenzen eingehalten; Preflight scannt keine Fachdaten/Historien; erfolgreiche Fachresultate sind identisch. |
| SR-VER-0039 | Vollständige adaptive Arbeit | Mehrschritttests mit sehr kleinen Arbeitszielen, globalen Graphfehlern, großen vollständigen Ausgaben und Fortschrittsinstrumentierung. | Einzellauf-/Mehrschrittparität, kein ausgelassener Restauftrag, keine rein budgetbedingte Fehlerblockade und kein endloser leerer Retry. |
| SR-VER-0040 | Portable Work-Steuerung und Agentenvertrag | Paket-Roundtrip, neuer Prozess/Host, falsche Checkpoints, verlorene Ausgaben, manipulierte Prompts und Actor-/Request-Tests. | Nur geprüfte Daten fortgesetzt; gleiche Aufgabenidentität; keine autonomen Nachrichten oder erweiterten Rechte; fehlende echte Voraussetzungen ehrlich ausgewiesen. |
| SR-VER-0041 | Kontraktübergreifende Regression | Fälle aus Anhang R, insbesondere Merge-Policy, echte Hostabbrüche, Klassen-/Journal- und Sicherheitsgrenzen. | Jeder Fall erfüllt sein exaktes Oracle ohne widersprüchliche Planner-/Writerentscheidung. |
| SR-VER-0042 | Unveränderbare Legacy-Migration | Reales 0.1-Projekt mit gespeicherter Evidence, Baselines und Archivpayloads migrieren und historische sowie aktuelle Prüfungen vergleichen. | Originalbytes unverändert, historische Hashes gültig, Manifest vollständig; keine fingierte aktuelle Evidence. |
| SR-VER-0043 | Durchgängiger Proposal-Lifecycle | CLI-Erfolgsvektor aus 11.10 einschließlich Positionsgrenzen, Kontrollwrites, Inhaltsänderung, Review, Apply und Retry. | Exakte Artefakt-/Inhaltsrevisionen, stabile gültige Inhaltsfreigaben und genau ein autorisiertes Apply. |
| SR-VER-0044 | Strukturierte Verbindlichkeit | Schema-, Authoring-, Renderer-, No-Guessing- und Lifecyclefälle aus S.2/S.7. | Keine Schlüsselwortpflicht; genaue Force-Semantik, keine Texteingriffe, alle Pflichtfelder und Should-Vorbedingungen korrekt. |
| SR-VER-0045 | Mehrsprachige Policies und Register | BCP-47-/Basic-Filtering-, Registersnapshot-, Private-use-, Mischungs- und Paketkompositionstests. | Alle Fälle aus S.3–S.6 einschließlich Region, Script, cmn/zh und fehlendem Lintpaket erfüllen die verbindlichen Oracles. |
| SR-VER-0046 | Generischer Analyzer-Datenvertrag | Echte Request-/Reportpackage-Roundtrips sowie fiktive externe Capability-Descriptoren, Integritäts- und Seiteneffekttests; Analyse-ID-Vergabe, projektlose Requests und Paarbindung nach 14.12. | Alle Bindungen, Coverage und Aktualitätszustände stimmen; getrennte Analyse- und Schreibkennungen; unbekannte Findings bleiben Daten; keine Freigabe, Receiptwirkung oder normative Mutation. |
| SR-VER-0047 | Reale py3langid-Integration | Ausgelieferten Worker mit tatsächlicher Library/Modell und dem versionierten Korpus aus T.10 ausführen. | Detektion ist implementiert; Sprache, Unsicherheit, grobe Auflösung und Default-Gates bestehen; Mocks ersetzen keine Sprachtests. |
| SR-VER-0048 | Analyzer-Portabilität und Ressourcen | Core ohne NumPy, separate Offlinepakete, Workerprozesskontrolle, Crash, Promptfortsetzung mit und ohne explizites Work-Verzeichnis nach 14.12 und reale CPU/RSS-Messung. | Kein versteckter Modellstart; gültige Checkpoints vor Code 8, volle Restmenge und konstante Analysekennung; keine Projektwrites oder Workerleaks; beide Laufzeitstufen und Ressourcenziele aus T.6/T.9/T.10 bestehen. |
| SR-VER-0049 | Sprach-/Force-Migration und Austausch | Explizite Entwurfsmigration mit negativen Aussagen, unveränderbaren Altnachweisen und CSV-/NDJSON-/ReqIF-Roundtrip. | Keine Inferenz aus Text/Priorität, alle Metadaten erhalten, keine alten Bytes verändert und keine fingierte aktuelle Evidence. |
| SR-VER-0050 | Explizite SRX-Zahlenpolicy | Vektoren aus Anhang U plus Precisionrange, JCS-Grenzen und absichtlich verschiedene Decimal-Prozessdefaults. | Alle exakten Ergebnisse und Fehlergründe unabhängig vom lokalen Pythonkontext; Policy in Fachhash gebunden. |
| SR-VER-0051 | Portabler PatchHarbor-Rundweg | Reale öffentliche Python-API, ausgelieferte PYZ-/Modulartefakte, vollständiger Hin-/Rückweg und negative Zustands-/Sicherheitsfälle nach W.7. | Bindung und Fachziel stimmen; Sandbox offline ohne Git/Shell/Installation; kein ungeprüfter Payloadwrite, keine vorgezogene Fachanwendung oder fingierte menschliche Freigabe; angebotene Runtimeprofile tatsächlich geprüft. |

### 14.1 Referenzplattform für Performance

Jeder Abnahmelauf bindet eine versionierte Datei `benchmark-platform.json`. Sie enthält mindestens CPU-Hersteller, exaktes Modell, Stepping, Microcode, Zahl physischer/logischer Kerne, RAM-Größe und -Takt soweit verfügbar, Kernelname und -version, Distribution, Dateisystemtyp und Mountoptionen, Blockgerät, CPython-Version und Buildkennung, SpecRoad-Build, CPU-Governor und SHA-256 der Benchmarkfixtures.

Verbindliche Laufbedingungen für die bestehenden Standardbenchmarks:

- Ressourcenprofil `standard`, kein persistenter SpecRoad-Cache (`--cache off`);
- Linux x86-64, mindestens vier logische Kerne und 8 GiB RAM;
- lokales SSD-Dateisystem und Projektroot auf demselben Dateisystem wie `.specroad/`;
- `LC_ALL=C`, `TZ=UTC`, kein Swap, keine konkurrierende Benchmark- oder SpecRoad-Last;
- festgehaltener CPU-Governor ohne thermisches oder batteriebedingtes Throttling;
- kalter Prozessstart, aber Benchmarkdateien nach einem Warm-up im Dateisystemcache;
- Wall-Clock als Median aus fünf Messläufen nach einem Warm-up; kein Einzellauf über dem Doppelten des Grenzwerts;
- Maximum Resident Set Size aus `/usr/bin/time -v`; ein Ersatzmesswerkzeug ist nur bei nachgewiesener identischer Byte-Einheit und Semantik zulässig.

Die Performance-Evidence bindet den SHA-256 von `benchmark-platform.json`, Fixturemanifest, Messskript und Rohmessdaten.

### 14.2 Referenz-Sandbox

Die verbindliche Sandbox für `SR-VER-0017`, `SR-VER-0027` und die neuen Runtime-Verifikationen besitzt:

- Linux x86-64 ohne Root-Rechte;
- jeweils eine saubere CPython-Minor-Version der unterstützten Matrix;
- keine installierten Drittanbieter-Python-Pakete;
- keinen Paketmanager-, Compiler-, TTY- oder Hintergrunddienst-Zwang;
- deaktivierten ausgehenden Netzwerkzugriff;
- ein beschreibbares temporäres Verzeichnis;
- die entpackte Modul-Distribution beziehungsweise die Zipapp und ein Projektbundle.

Der Test muss den Roundtrip Initialisierung beziehungsweise Bundle-Extraktion, Selbstbeschreibung, Validation, Query, direkte menschliche Dry-Runs, Proposal-Erzeugung und -Check, Rendering, Bundle-Erzeugung und Bundle-Verifikation ausführen.

### 14.3 Referenzdateisystem für Transaktionen

`SR-VER-0019` wird auf einem lokalen Linux-Dateisystem ausgeführt, das atomare Umbenennungen innerhalb eines Verzeichnisses und `fsync` auf Dateien und Verzeichnissen unterstützt. Die Tests injizieren einen harten Prozessabbruch nach jeder dauerhaft sichtbaren Grenze. Zusätzlich werden fehlende und manipulierte Journalbestandteile simuliert.

### 14.4 Austausch-Testkorpus

`SR-VER-0024` enthält mindestens:

- ReqIF 1.2 mit Dokumenthierarchie, Attributen, Relationen, XHTML und Anhängen;
- ReqIFZ mit gültigen und bösartigen Archivpfaden;
- RFC-4180-CSV mit Quotes, Kommas, CRLF und eingebetteten Zeilenumbrüchen;
- NDJSON mit gültigen, ungültigen und sehr großen Zeilen;
- Mappingkonflikte, unbekannte Attribute und absichtlich nicht darstellbare Inhalte;
- einen semantischen Roundtrip je Format.

### 14.5 Python-Kompatibilitätsmatrix

Für Zielrelease 0.2 ist die Release-Matrix CPython 3.10, 3.11, 3.12, 3.13 und 3.14. Die Mindestversion bleibt 3.10. Eine spätere Dokumentversion darf neuere Versionen ergänzen, aber die Mindestversion nur durch eine ausdrückliche Architektur- und Produktentscheidung erhöhen.

---

### 14.6 Referenzprofil für sparsamen Betrieb

Die folgenden zusätzlichen Grenzwerte sind verbindliche Abnahmeziele, keine bereits gemessenen Ergebnisse. Gemessen wird auf der Plattform nach 14.1, für beide portablen Distributionen und jede unterstützte CPython-Minor-Version, ohne persistenten SpecRoad-Cache. Die CPU-Evidence erfasst User- plus Systemzeit; die Wall-Clock erfasst den gesamten CLI-Prozess einschließlich Interpreterstart. Zeitgrenzen gelten als Median aus fünf Läufen nach einem Warm-up; kein Einzellauf darf das Doppelte überschreiten. RSS-Grenzen gelten für jeden Lauf.

| Prüffall | Umfang | Profil | CPU-Zeit | Wall-Clock | Peak-RSS |
|---|---|---|---:|---:|---:|
| Schlanker Bootstrap | jeweils `version --format json`, globale `--help`, projektlose `capabilities --format json` | `constrained` | höchstens 200 ms | höchstens 300 ms | höchstens 64 MiB |
| Reiner automatischer Preflight | saubere Projektmetadaten bis 64 KiB, keine aktive Transaktion; ohne Fachoperation, gemessen als interner Abschnitt | `constrained` | höchstens 100 ms | höchstens 150 ms | höchstens 16 MiB zusätzlicher RSS gegenüber demselben Bootstrap |
| Kleine vollständige Validierung | vorhandenes 1.000-Artefakte-/5.000-Relationen-/10-MiB-Fixture | `constrained` | höchstens 2000 ms | höchstens 3000 ms | höchstens 256 MiB |
| Große vollständige Validierung | vorhandenes 10.000-Artefakte-/50.000-Relationen-/100-MiB-Fixture | `standard` | höchstens 10000 ms | bestehende Grenze aus SR-REQ-0211 | bestehende Grenze aus SR-REQ-0212 |

Die beiden bestehenden Standardbenchmarks `SR-REQ-0210` und `SR-REQ-0211` bleiben unverändert anspruchsvoll; die zusätzliche Constrained-Abnahme ersetzt sie nicht. Der Preflight-Test wird außerdem mit 0 und 100.000 abgeschlossenen Receiptdateien wiederholt. Die Messinstrumentierung weist nach, dass diese Receipt-Historie sowie Artefakte, Anhänge, Code und Archivpayloads nicht durch den Preflight geöffnet oder rekursiv enumeriert werden.

Ein Low-Resource-Funktionstest verwendet eine durch den Testhost begrenzte CPU-Ausführung auf einem logischen Kern und ein Prozessspeicherlimit von 512 MiB; SpecRoads gewähltes Speicherbudget bleibt 256 MiB. Mindestens Bundle-Extraktion, Umgebungsdiagnose, Validierung, Query, Proposal-Check, Rendering, Vollbundle-Erzeugung und -Verifikation mit dem 1.000-Artefakte-Fixture müssen vollständig bestehen. Das Setzen der Testhostgrenzen und die Messwerkzeuge sind Testinfrastruktur, keine produktiven SpecRoad-Abhängigkeiten. Für eine kleinere beliebige Anbieter-Sandbox wird kein Funktionserfolg zugesagt.

### 14.7 Runtime-, Budget- und Cache-Testmatrix

`SR-VER-0035` bis `SR-VER-0038` prüfen zusätzlich mindestens:

- neue Prozesse mit bereinigter optionaler Umgebung, anderem Arbeitsverzeichnis und explizitem Projektpfad; beide Distributionsformen bleiben auffindbar;
- neue kompatible Sandbox mit vollständig verifiziertem Vollbundle einschließlich Receipts; Modellhash- und Requestparität;
- fehlende Distribution beziehungsweise fehlender Prozessstart als Fehler des aufrufenden Runners, nicht als erfundene SpecRoad-Erfolgsausgabe;
- aktive, fremde, unklare und tatsächlich verwaiste Locks; unterbrochene und korrupte Journale bei Read-only-, Dry-Run- und tatsächlichen Schreibaufrufen;
- vollständiger Cacheverlust, manipulierte Cachebytes, gleichbleibende Dateigröße und `mtime` bei verändertem Fachinhalt sowie unveränderte Inhalte mit geänderten Pfaden;
- knapp unter, genau an und über jeder Grenze liegende Budgetfixtures; `0` und negative Budgets als Nutzungsfehler;
- mehrschichtige Graphen mit vielen kürzesten Pfaden, große Payloads und exakte Query-Gesamtzahlen bei kleiner Pagination;
- weiche CPU-/Zeit-/Scratchüberschreitung sowie echte Hostabbrüche vor und an jeder dauerhaften Transaktionsgrenze; erneute Recovery mit erhaltener Verbrauchsbilanz und sicherem Journalabschluss;
- harten Prozessabbruch mit erhaltenem Journal und anschließende korrekte Recovery; vollständigen Dateiverlust nur durch Rückkehr zum externen Sicherungsstand;
- keine verbleibenden von SpecRoad gestarteten Hilfsprozesse nach normalem beziehungsweise behandeltem Ende;
- fachliche Byte-/Hashparität vollständig erfolgreicher Läufe mit `constrained`, `standard`, `--cache off` und verwendbarem Cache; Messwerte werden separat verglichen.

Testmanifest und Evidence binden neben den bisherigen Hashes `runtime-budget-v2`, gewähltes Profil, tatsächliche Budgetwerte, Messart und Fixturezustand. Ein bloß vorhandener Testfall oder eine formale Requirement-Zuordnung ist kein bestandener Performance- oder Recoverytest.

---

### 14.8 Fortsetzung, vollständiger Arbeitsumfang und Auditregression

Die bisherigen Performanceziele bleiben verbindlich. Ergänzend prüft die Releaseabnahme alle Fälle in Anhang R und insbesondere endliche Aufträge mit deutlich kleineren Schrittfenstern als ihrer vollständigen Laufzeit. Der Testhost ruft `work resume` so oft auf, bis der Auftrag abgeschlossen ist oder ein konkreter echter Blocker vorliegt. Er bricht nicht wegen einer bloßen Anzahl überschrittener Softbudgets ab.

Der Testkorpus enthält mindestens Vollvalidierung samt globaler Graphregeln, exakte Query-Gesamtzahl, vollständige `why`-Pfade, Diff, Merge-Plan, Import-/Migrationsplanung, Baseline-/Bundle-Prüfung, Rendering und Proposal-Zielvalidierung. Jede Phase wird an sämtlichen implementierten Checkpointgrenzen unterbrochen und in einem neuen Prozess wieder aufgenommen. Der abschließende normative Write wird zusätzlich an allen dauerhaften Journalgrenzen tatsächlich abgebrochen und recovered.

Als Oracle gelten identischer fachlicher Endpayload und identische gebundene Zielmodellwurzel gegenüber dem nicht unterbrochenen Lauf, keine verlorene/doppelte Ergebniseinheit, vollständig erhaltene Pflichtdiagnosen sowie genau ein semantisches Receipt pro Request. Unbekannte Gesamtarbeit wird bis zu ihrer Ermittlung als unbekannt ausgewiesen. Ein Checkpoint nach reiner wiederholter Startprüfung zählt nicht als dauerhafter fachlicher Fortschritt.

Mess-Evidence enthält Verbrauch je Schritt und kumuliert, maximalen Arbeitsspeicher/Scratch, bestätigte Fortschrittseinheiten, Zahl wiederverwendeter und neu berechneter Einheiten sowie tatsächliche Blocker. Damit wird eine formal fortsetzbare, aber bei jedem Prompt vollständig von vorn rechnende Implementierung als nicht konform erkannt. Die kleinen Algorithmen-/Metadatenorakel können bereits vor Implementierung geprüft werden; sie ersetzen nicht die späteren CLI-/Crash-/Performance-Nachweise.


---

### 14.9 Korrekturregression v0.2.4

Die Fälle R-23 bis R-32 sind verbindliche Teilfälle bestehender Verifikationsverträge und kommen zu R-01 bis R-22 hinzu. SR-VER-0029 und SR-VER-0012 prüfen R-23/R-24 einschließlich indirekter Kanten und Fehlerfreiheit vor jedem Write. SR-VER-0010, SR-VER-0025 und SR-VER-0030 prüfen R-25 bis R-28 mit neuen und gleichen Produktständen, mehreren Pflichtslots, neuen verspäteten Fehlernachweisen und allen Importpermutationen eines kleinen vollständigen Testkorpus. SR-VER-0027 prüft R-29 auf zwei frischen Projektroots sowie die Verweigerung eines scheinbar vollständigen Snapshots bei Writer/Recovery. SR-VER-0008 und SR-VER-0032 prüfen die Wahrheitstabelle R-30. SR-VER-0037, SR-VER-0041 und SR-VER-0011 prüfen R-31/R-32 für Fortsetzung und Baselines.

Die Orakel verwenden die präzisierten Requirement-Texte mit ihren unveränderten IDs. Geplante Testfallmanifeste müssen den neuen Spezifikationshash binden; frühere Testergebnisse werden nicht allein wegen gleicher IDs als Nachweis dieser Korrektur übernommen. Diese Ergänzung ist kein Bericht über ausgeführte Produkttests.

### 14.10 Korrekturregression v0.2.5

Die frühere Korrektur v0.2.5 ergänzte die weiterhin verbindliche Soll-Abnahme um die Fälle R-33 bis R-47; R-01 bis R-32 bleiben verpflichtend. Die Fallbeschreibungen stehen vollständig in Anhang R. Die damaligen 650 Requirement- und 38 E2E-Identitäten werden nicht umnummeriert; v0.2.6 ergänzt diesen Bestand auf 730 Requirements und 46 Szenario-/E2E-Identitäten. Zusätzliche gekoppelte Fixturevarianten sind Nachweise zu den bestehenden Verifikationsverträgen, keine Behauptung einer bereits ausgeführten Produktabnahme.

| Befund | Verbindliche Sollfälle | Primäre fachliche Zuordnung |
|---|---|---|
| B01 Lifecycle-Überlappung | R-33, R-34 | SR-REQ-0044, SR-REQ-0218, SR-REQ-0235; SR-VER-0004, SR-VER-0018 |
| B03 negativer Relationsreview | R-35 bis R-39 | SR-REQ-0238, SR-REQ-0278, SR-REQ-0283, SR-REQ-0514, SR-REQ-0515; SR-VER-0018, SR-VER-0019, SR-VER-0021 |
| B02 Bundle-Kennzeichnung | R-40, R-41 | SR-REQ-0386, SR-REQ-0389, SR-REQ-0390; SR-VER-0027 |
| H01 nichtrekursiver Manifestbereich | R-42, R-43 | SR-REQ-0387, SR-REQ-0388, SR-REQ-0389; SR-VER-0027 |
| H02 vollständige Restore-Quelle | R-44 bis R-47 | SR-REQ-0461, SR-REQ-0462, SR-REQ-0254, SR-REQ-0261; SR-VER-0019, SR-VER-0031 |

Ein begrenztes ausführbares Vertragsmodell darf diese Entscheidungstabellen verifizieren, ersetzt aber keine tatsächlichen CLI-, Dateisystem-, Crash- oder Ressourcentests. Vor technischer Gesamtfreigabe werden zusätzlich die bisherigen Proposal-, Evidence-, Merge-, Migrations-, Scope- und Mehrschrittregressionen gegen die konsolidierten Verträge geprüft.

---

### 14.11 Mehrsprachigkeits- und Analyzerabnahme

Die neue Matrix SR-VER-0044 bis SR-VER-0050 gilt zusätzlich, nicht anstelle der bestehenden 43 Prüfverträge. Der echte py3langid-Lauf ist im ersten Zielrelease zwingend; fehlende Abhängigkeiten sind nur in der gesonderten Core-ohne-Zusatzpakete-Prüfung ein erwarteter Befund. Subjectzuordnung, Statementvollständigkeit, Projekt-/Script-/Regionstrennung und Wiederaufnahme werden kontraktübergreifend geprüft. Der frühere Prüfungssatz zu v0.2.5 bleibt als Regression erhalten; neue ausgeführte Dokument-/Entwurfsmodelle werden nicht als bestandene Produkttests bezeichnet.

---

### 14.12 Korrekturregression v0.2.7

Die Befunde B01 und A02 aus der Prüfung v0.2.6 werden mit den bestehenden Verträgen SR-VER-0027, SR-VER-0040, SR-VER-0041, SR-VER-0046 und SR-VER-0048 geprüft. Die fachlichen Sollfälle R-64 bis R-75 ergänzen Anhang R. Sie sind verbindliche Abnahmevorgaben, keine Behauptung bereits implementierter Produkt- oder py3langid-Tests.

Die Implementierung führt mindestens einen großen Analyzerauftrag ohne `--work-dir` bis Code 8 aus, prüft sämtliche Checkpointpayloads, startet einen neuen Prozess und vervollständigt den Auftrag mit derselben Analysekennung und Enginebindung. Dasselbe erfolgt mit explizitem Work-Root. Vorher-/Nachher-Manifeste belegen unveränderte Projektbytes einschließlich `.specroad/`; Einzellauf und Mehrschrittvergleich haben identische fachliche Ergebnisprojektionen und vollständige Subjectmengen. Ein kleiner Auftrag hinterlässt keine Work-Dateien. Tatsächlich unmögliche Checkpointpublikation wird nicht als Code 8 quittiert.

Die Kennungsprüfung umfasst automatisch und manuell vergebene Analysekennungen, einen projektlosen datentragenden Request, einen unterbrochenen Requestaufbau, ungültige Overrides, Kennungs-/Snapshotmismatch sowie dieselbe Zeichenfolge im unabhängigen Schreibnamensraum. Normative Write-Retries müssen unverändert ihre bestehenden Receipts verwenden; Analysen dürfen diese weder erzeugen noch lesen oder ändern. Eine bloße Analysekennungswiederholung ersetzt weder den Snapshotvergleich noch ein ausdrückliches `work resume`.

### 14.13 PatchHarbor-Rundweg v0.2.8

SR-VER-0051 ergänzt SR-VER-0012, SR-VER-0017, SR-VER-0027 und SR-VER-0033.
Die konkrete Abnahme steht in W.7 und erweitert SR-SCN-0013 / SR-E2E-0013.
CPython-3.10-/3.11-Unterstützung der neuen PatchHarbor-Version ist die gesetzte
Produktbasis; öffentliche API-Verfügbarkeit, konkrete Artefakte und erfolgreiche
Integration bleiben gesondert nachzuweisen. Ein früherer SpecRoad- oder
PatchHarbor-Testlauf belegt die Erweiterung nicht durch bloße Hashaktualisierung.

## 15. Traceability und Vollständigkeitsnachweis

### 15.1 Ziel-zu-Bedarf-Matrix

| Goal | Stakeholder-Bedarfe |
|---|---|
| SR-GOAL-0001 | SR-NEED-0001, SR-NEED-0015, SR-NEED-0020 |
| SR-GOAL-0002 | SR-NEED-0001, SR-NEED-0002, SR-NEED-0003, SR-NEED-0005, SR-NEED-0007, SR-NEED-0018, SR-NEED-0020, SR-NEED-0021 |
| SR-GOAL-0003 | SR-NEED-0002, SR-NEED-0003, SR-NEED-0004, SR-NEED-0006, SR-NEED-0009, SR-NEED-0010, SR-NEED-0016 |
| SR-GOAL-0004 | SR-NEED-0004, SR-NEED-0007, SR-NEED-0008, SR-NEED-0011, SR-NEED-0012, SR-NEED-0016, SR-NEED-0017, SR-NEED-0019 |
| SR-GOAL-0005 | SR-NEED-0008, SR-NEED-0011, SR-NEED-0017, SR-NEED-0019, SR-NEED-0021 |
| SR-GOAL-0006 | SR-NEED-0004, SR-NEED-0005, SR-NEED-0006, SR-NEED-0009 |
| SR-GOAL-0007 | SR-NEED-0006, SR-NEED-0010, SR-NEED-0015 |
| SR-GOAL-0008 | SR-NEED-0002, SR-NEED-0011, SR-NEED-0012, SR-NEED-0014, SR-NEED-0017, SR-NEED-0018, SR-NEED-0020, SR-NEED-0021 |
| SR-GOAL-0009 | SR-NEED-0003, SR-NEED-0007, SR-NEED-0009, SR-NEED-0012, SR-NEED-0013, SR-NEED-0014, SR-NEED-0016, SR-NEED-0017, SR-NEED-0018, SR-NEED-0019, SR-NEED-0021 |
| SR-GOAL-0010 | SR-NEED-0001, SR-NEED-0008, SR-NEED-0013, SR-NEED-0014, SR-NEED-0015, SR-NEED-0018, SR-NEED-0019, SR-NEED-0020 |

### 15.2 Bedarfsabdeckung durch Anforderungen

| Need | Anzahl Anforderungen | Exakt abgedeckte IDs |
|---|---:|---|
| SR-NEED-0001 | 90 | `SR-REQ-0001`–`SR-REQ-0006`<br>`SR-REQ-0009`–`SR-REQ-0012`<br>`SR-REQ-0022`<br>`SR-REQ-0024`–`SR-REQ-0026`<br>`SR-REQ-0032`<br>`SR-REQ-0066`–`SR-REQ-0067`<br>`SR-REQ-0073`<br>`SR-REQ-0075`<br>`SR-REQ-0080`<br>`SR-REQ-0087`–`SR-REQ-0088`<br>`SR-REQ-0101`<br>`SR-REQ-0105`–`SR-REQ-0106`<br>`SR-REQ-0108`<br>`SR-REQ-0123`<br>`SR-REQ-0179`<br>`SR-REQ-0181`<br>`SR-REQ-0186`–`SR-REQ-0187`<br>`SR-REQ-0190`<br>`SR-REQ-0209`–`SR-REQ-0210`<br>`SR-REQ-0216`–`SR-REQ-0217`<br>`SR-REQ-0226`–`SR-REQ-0227`<br>`SR-REQ-0231`–`SR-REQ-0235`<br>`SR-REQ-0240`<br>`SR-REQ-0251`<br>`SR-REQ-0272`<br>`SR-REQ-0278`<br>`SR-REQ-0281`<br>`SR-REQ-0299`–`SR-REQ-0302`<br>`SR-REQ-0304`<br>`SR-REQ-0308`<br>`SR-REQ-0310`–`SR-REQ-0313`<br>`SR-REQ-0320`–`SR-REQ-0321`<br>`SR-REQ-0325`<br>`SR-REQ-0332`<br>`SR-REQ-0354`<br>`SR-REQ-0372`<br>`SR-REQ-0378`<br>`SR-REQ-0380`<br>`SR-REQ-0386`<br>`SR-REQ-0393`–`SR-REQ-0394`<br>`SR-REQ-0402`<br>`SR-REQ-0409`<br>`SR-REQ-0417`<br>`SR-REQ-0443`<br>`SR-REQ-0463`<br>`SR-REQ-0467`–`SR-REQ-0468`<br>`SR-REQ-0471`<br>`SR-REQ-0501`<br>`SR-REQ-0504`<br>`SR-REQ-0524`–`SR-REQ-0525`<br>`SR-REQ-0527`<br>`SR-REQ-0530`–`SR-REQ-0531`<br>`SR-REQ-0544`–`SR-REQ-0545`<br>`SR-REQ-0649`<br>`SR-REQ-0651`–`SR-REQ-0652`<br>`SR-REQ-0737` |
| SR-NEED-0002 | 116 | `SR-REQ-0007`–`SR-REQ-0008`<br>`SR-REQ-0014`–`SR-REQ-0017`<br>`SR-REQ-0027`–`SR-REQ-0029`<br>`SR-REQ-0031`<br>`SR-REQ-0037`–`SR-REQ-0043`<br>`SR-REQ-0046`<br>`SR-REQ-0051`–`SR-REQ-0052`<br>`SR-REQ-0054`–`SR-REQ-0056`<br>`SR-REQ-0059`–`SR-REQ-0061`<br>`SR-REQ-0063`<br>`SR-REQ-0065`–`SR-REQ-0072`<br>`SR-REQ-0074`<br>`SR-REQ-0076`–`SR-REQ-0079`<br>`SR-REQ-0081`–`SR-REQ-0082`<br>`SR-REQ-0084`–`SR-REQ-0086`<br>`SR-REQ-0091`<br>`SR-REQ-0093`–`SR-REQ-0097`<br>`SR-REQ-0130`<br>`SR-REQ-0143`–`SR-REQ-0144`<br>`SR-REQ-0148`–`SR-REQ-0149`<br>`SR-REQ-0218`<br>`SR-REQ-0235`<br>`SR-REQ-0238`<br>`SR-REQ-0244`<br>`SR-REQ-0246`–`SR-REQ-0247`<br>`SR-REQ-0264`<br>`SR-REQ-0276`<br>`SR-REQ-0280`<br>`SR-REQ-0282`<br>`SR-REQ-0286`–`SR-REQ-0288`<br>`SR-REQ-0290`–`SR-REQ-0293`<br>`SR-REQ-0297`<br>`SR-REQ-0307`<br>`SR-REQ-0316`<br>`SR-REQ-0326`<br>`SR-REQ-0367`<br>`SR-REQ-0369`<br>`SR-REQ-0395`–`SR-REQ-0397`<br>`SR-REQ-0399`<br>`SR-REQ-0406`<br>`SR-REQ-0414`–`SR-REQ-0415`<br>`SR-REQ-0419`<br>`SR-REQ-0421`–`SR-REQ-0424`<br>`SR-REQ-0431`<br>`SR-REQ-0433`<br>`SR-REQ-0499`<br>`SR-REQ-0505`<br>`SR-REQ-0508`<br>`SR-REQ-0515`<br>`SR-REQ-0517`<br>`SR-REQ-0519`–`SR-REQ-0521`<br>`SR-REQ-0529`<br>`SR-REQ-0542`<br>`SR-REQ-0546`–`SR-REQ-0548`<br>`SR-REQ-0636`<br>`SR-REQ-0653`<br>`SR-REQ-0656`<br>`SR-REQ-0658`<br>`SR-REQ-0662`–`SR-REQ-0663`<br>`SR-REQ-0665`<br>`SR-REQ-0667`<br>`SR-REQ-0727`–`SR-REQ-0728` |
| SR-NEED-0003 | 168 | `SR-REQ-0012`<br>`SR-REQ-0021`–`SR-REQ-0022`<br>`SR-REQ-0024`<br>`SR-REQ-0030`<br>`SR-REQ-0032`–`SR-REQ-0034`<br>`SR-REQ-0036`<br>`SR-REQ-0042`–`SR-REQ-0045`<br>`SR-REQ-0047`–`SR-REQ-0048`<br>`SR-REQ-0052`–`SR-REQ-0053`<br>`SR-REQ-0057`–`SR-REQ-0058`<br>`SR-REQ-0060`<br>`SR-REQ-0063`–`SR-REQ-0064`<br>`SR-REQ-0068`<br>`SR-REQ-0070`<br>`SR-REQ-0072`<br>`SR-REQ-0082`<br>`SR-REQ-0089`–`SR-REQ-0090`<br>`SR-REQ-0095`<br>`SR-REQ-0097`<br>`SR-REQ-0099`<br>`SR-REQ-0103`–`SR-REQ-0104`<br>`SR-REQ-0106`–`SR-REQ-0109`<br>`SR-REQ-0111`–`SR-REQ-0116`<br>`SR-REQ-0124`<br>`SR-REQ-0126`<br>`SR-REQ-0152`<br>`SR-REQ-0154`–`SR-REQ-0155`<br>`SR-REQ-0158`<br>`SR-REQ-0161`–`SR-REQ-0162`<br>`SR-REQ-0169`<br>`SR-REQ-0171`<br>`SR-REQ-0173`–`SR-REQ-0175`<br>`SR-REQ-0191`–`SR-REQ-0193`<br>`SR-REQ-0213`<br>`SR-REQ-0219`–`SR-REQ-0220`<br>`SR-REQ-0228`<br>`SR-REQ-0231`–`SR-REQ-0234`<br>`SR-REQ-0237`<br>`SR-REQ-0239`<br>`SR-REQ-0241`–`SR-REQ-0242`<br>`SR-REQ-0248`<br>`SR-REQ-0250`–`SR-REQ-0251`<br>`SR-REQ-0269`<br>`SR-REQ-0273`<br>`SR-REQ-0275`–`SR-REQ-0281`<br>`SR-REQ-0283`–`SR-REQ-0285`<br>`SR-REQ-0293`<br>`SR-REQ-0299`<br>`SR-REQ-0302`<br>`SR-REQ-0305`<br>`SR-REQ-0309`–`SR-REQ-0311`<br>`SR-REQ-0314`<br>`SR-REQ-0317`–`SR-REQ-0318`<br>`SR-REQ-0322`<br>`SR-REQ-0331`<br>`SR-REQ-0347`<br>`SR-REQ-0349`<br>`SR-REQ-0351`<br>`SR-REQ-0353`<br>`SR-REQ-0358`<br>`SR-REQ-0361`–`SR-REQ-0362`<br>`SR-REQ-0364`–`SR-REQ-0366`<br>`SR-REQ-0368`<br>`SR-REQ-0370`–`SR-REQ-0372`<br>`SR-REQ-0374`<br>`SR-REQ-0398`–`SR-REQ-0399`<br>`SR-REQ-0402`–`SR-REQ-0403`<br>`SR-REQ-0405`<br>`SR-REQ-0410`<br>`SR-REQ-0412`<br>`SR-REQ-0415`–`SR-REQ-0416`<br>`SR-REQ-0418`<br>`SR-REQ-0426`–`SR-REQ-0430`<br>`SR-REQ-0434`<br>`SR-REQ-0437`<br>`SR-REQ-0441`<br>`SR-REQ-0449`<br>`SR-REQ-0456`–`SR-REQ-0457`<br>`SR-REQ-0473`<br>`SR-REQ-0475`<br>`SR-REQ-0507`<br>`SR-REQ-0509`–`SR-REQ-0510`<br>`SR-REQ-0512`<br>`SR-REQ-0514`<br>`SR-REQ-0516`<br>`SR-REQ-0521`<br>`SR-REQ-0524`–`SR-REQ-0525`<br>`SR-REQ-0530`<br>`SR-REQ-0537`<br>`SR-REQ-0541`<br>`SR-REQ-0611`<br>`SR-REQ-0637`–`SR-REQ-0638`<br>`SR-REQ-0643`–`SR-REQ-0644`<br>`SR-REQ-0646`–`SR-REQ-0648`<br>`SR-REQ-0657`<br>`SR-REQ-0673`–`SR-REQ-0674`<br>`SR-REQ-0685`<br>`SR-REQ-0693`<br>`SR-REQ-0708`<br>`SR-REQ-0712`<br>`SR-REQ-0734`<br>`SR-REQ-0738`–`SR-REQ-0741` |
| SR-NEED-0004 | 17 | `SR-REQ-0010`<br>`SR-REQ-0049`<br>`SR-REQ-0078`<br>`SR-REQ-0120`<br>`SR-REQ-0127`<br>`SR-REQ-0131`<br>`SR-REQ-0153`<br>`SR-REQ-0176`<br>`SR-REQ-0342`–`SR-REQ-0347`<br>`SR-REQ-0495`<br>`SR-REQ-0536`–`SR-REQ-0537` |
| SR-NEED-0005 | 64 | `SR-REQ-0050`<br>`SR-REQ-0062`<br>`SR-REQ-0065`<br>`SR-REQ-0074`–`SR-REQ-0077`<br>`SR-REQ-0086`<br>`SR-REQ-0096`<br>`SR-REQ-0127`<br>`SR-REQ-0129`–`SR-REQ-0134`<br>`SR-REQ-0136`–`SR-REQ-0142`<br>`SR-REQ-0177`<br>`SR-REQ-0284`<br>`SR-REQ-0333`–`SR-REQ-0341`<br>`SR-REQ-0369`<br>`SR-REQ-0374`<br>`SR-REQ-0432`<br>`SR-REQ-0444`–`SR-REQ-0452`<br>`SR-REQ-0491`–`SR-REQ-0493`<br>`SR-REQ-0500`<br>`SR-REQ-0533`–`SR-REQ-0535`<br>`SR-REQ-0622`<br>`SR-REQ-0633`<br>`SR-REQ-0642`<br>`SR-REQ-0650`<br>`SR-REQ-0668`<br>`SR-REQ-0682`<br>`SR-REQ-0686`<br>`SR-REQ-0720`–`SR-REQ-0721`<br>`SR-REQ-0730`<br>`SR-REQ-0742` |
| SR-NEED-0006 | 35 | `SR-REQ-0049`–`SR-REQ-0050`<br>`SR-REQ-0073`<br>`SR-REQ-0101`<br>`SR-REQ-0113`<br>`SR-REQ-0115`<br>`SR-REQ-0118`–`SR-REQ-0121`<br>`SR-REQ-0125`–`SR-REQ-0126`<br>`SR-REQ-0136`–`SR-REQ-0137`<br>`SR-REQ-0139`–`SR-REQ-0141`<br>`SR-REQ-0144`<br>`SR-REQ-0150`<br>`SR-REQ-0283`–`SR-REQ-0284`<br>`SR-REQ-0347`<br>`SR-REQ-0358`<br>`SR-REQ-0400`–`SR-REQ-0401`<br>`SR-REQ-0408`<br>`SR-REQ-0411`<br>`SR-REQ-0414`<br>`SR-REQ-0444`<br>`SR-REQ-0446`<br>`SR-REQ-0450`–`SR-REQ-0451`<br>`SR-REQ-0493`<br>`SR-REQ-0516`<br>`SR-REQ-0537` |
| SR-NEED-0007 | 239 | `SR-REQ-0001`<br>`SR-REQ-0005`–`SR-REQ-0006`<br>`SR-REQ-0009`<br>`SR-REQ-0013`<br>`SR-REQ-0016`<br>`SR-REQ-0020`–`SR-REQ-0021`<br>`SR-REQ-0029`<br>`SR-REQ-0035`<br>`SR-REQ-0041`<br>`SR-REQ-0051`<br>`SR-REQ-0054`–`SR-REQ-0056`<br>`SR-REQ-0059`<br>`SR-REQ-0083`–`SR-REQ-0085`<br>`SR-REQ-0087`–`SR-REQ-0089`<br>`SR-REQ-0091`–`SR-REQ-0094`<br>`SR-REQ-0098`–`SR-REQ-0100`<br>`SR-REQ-0102`<br>`SR-REQ-0104`<br>`SR-REQ-0110`<br>`SR-REQ-0114`<br>`SR-REQ-0117`<br>`SR-REQ-0145`<br>`SR-REQ-0147`<br>`SR-REQ-0149`<br>`SR-REQ-0151`<br>`SR-REQ-0164`<br>`SR-REQ-0179`–`SR-REQ-0189`<br>`SR-REQ-0191`<br>`SR-REQ-0193`–`SR-REQ-0195`<br>`SR-REQ-0202`–`SR-REQ-0203`<br>`SR-REQ-0205`<br>`SR-REQ-0207`–`SR-REQ-0208`<br>`SR-REQ-0210`–`SR-REQ-0215`<br>`SR-REQ-0217`<br>`SR-REQ-0221`–`SR-REQ-0222`<br>`SR-REQ-0225`<br>`SR-REQ-0227`<br>`SR-REQ-0229`–`SR-REQ-0230`<br>`SR-REQ-0237`–`SR-REQ-0238`<br>`SR-REQ-0240`<br>`SR-REQ-0243`<br>`SR-REQ-0252`<br>`SR-REQ-0254`–`SR-REQ-0256`<br>`SR-REQ-0261`–`SR-REQ-0263`<br>`SR-REQ-0267`<br>`SR-REQ-0270`–`SR-REQ-0271`<br>`SR-REQ-0281`<br>`SR-REQ-0294`–`SR-REQ-0295`<br>`SR-REQ-0297`–`SR-REQ-0298`<br>`SR-REQ-0303`<br>`SR-REQ-0314`–`SR-REQ-0315`<br>`SR-REQ-0325`<br>`SR-REQ-0327`–`SR-REQ-0328`<br>`SR-REQ-0330`<br>`SR-REQ-0332`<br>`SR-REQ-0338`<br>`SR-REQ-0340`<br>`SR-REQ-0346`<br>`SR-REQ-0352`–`SR-REQ-0354`<br>`SR-REQ-0356`–`SR-REQ-0357`<br>`SR-REQ-0359`<br>`SR-REQ-0361`<br>`SR-REQ-0363`<br>`SR-REQ-0371`<br>`SR-REQ-0373`<br>`SR-REQ-0375`–`SR-REQ-0377`<br>`SR-REQ-0379`–`SR-REQ-0382`<br>`SR-REQ-0384`–`SR-REQ-0385`<br>`SR-REQ-0388`–`SR-REQ-0389`<br>`SR-REQ-0391`–`SR-REQ-0392`<br>`SR-REQ-0397`–`SR-REQ-0398`<br>`SR-REQ-0400`<br>`SR-REQ-0404`–`SR-REQ-0407`<br>`SR-REQ-0410`<br>`SR-REQ-0412`–`SR-REQ-0413`<br>`SR-REQ-0415`<br>`SR-REQ-0417`<br>`SR-REQ-0420`<br>`SR-REQ-0423`<br>`SR-REQ-0425`<br>`SR-REQ-0435`–`SR-REQ-0436`<br>`SR-REQ-0438`–`SR-REQ-0440`<br>`SR-REQ-0442`–`SR-REQ-0443`<br>`SR-REQ-0446`<br>`SR-REQ-0449`<br>`SR-REQ-0459`<br>`SR-REQ-0463`–`SR-REQ-0465`<br>`SR-REQ-0468`<br>`SR-REQ-0470`<br>`SR-REQ-0472`–`SR-REQ-0480`<br>`SR-REQ-0484`–`SR-REQ-0492`<br>`SR-REQ-0494`–`SR-REQ-0499`<br>`SR-REQ-0506`<br>`SR-REQ-0522`–`SR-REQ-0523`<br>`SR-REQ-0526`<br>`SR-REQ-0533`–`SR-REQ-0534`<br>`SR-REQ-0539`<br>`SR-REQ-0543`<br>`SR-REQ-0548`<br>`SR-REQ-0573`–`SR-REQ-0600`<br>`SR-REQ-0603`<br>`SR-REQ-0606`<br>`SR-REQ-0614`<br>`SR-REQ-0617`<br>`SR-REQ-0622`–`SR-REQ-0623`<br>`SR-REQ-0627`<br>`SR-REQ-0631`–`SR-REQ-0633`<br>`SR-REQ-0636`–`SR-REQ-0637`<br>`SR-REQ-0645`<br>`SR-REQ-0650`<br>`SR-REQ-0666`<br>`SR-REQ-0679`<br>`SR-REQ-0689`<br>`SR-REQ-0694`<br>`SR-REQ-0697`<br>`SR-REQ-0713`–`SR-REQ-0714`<br>`SR-REQ-0722`<br>`SR-REQ-0729` |
| SR-NEED-0008 | 130 | `SR-REQ-0018`<br>`SR-REQ-0083`<br>`SR-REQ-0090`<br>`SR-REQ-0116`<br>`SR-REQ-0142`<br>`SR-REQ-0154`–`SR-REQ-0170`<br>`SR-REQ-0172`–`SR-REQ-0174`<br>`SR-REQ-0176`–`SR-REQ-0180`<br>`SR-REQ-0182`–`SR-REQ-0183`<br>`SR-REQ-0185`<br>`SR-REQ-0192`<br>`SR-REQ-0200`<br>`SR-REQ-0219`<br>`SR-REQ-0222`–`SR-REQ-0228`<br>`SR-REQ-0230`<br>`SR-REQ-0236`<br>`SR-REQ-0240`<br>`SR-REQ-0242`<br>`SR-REQ-0327`<br>`SR-REQ-0376`–`SR-REQ-0380`<br>`SR-REQ-0382`<br>`SR-REQ-0384`<br>`SR-REQ-0386`<br>`SR-REQ-0392`<br>`SR-REQ-0426`–`SR-REQ-0429`<br>`SR-REQ-0476`–`SR-REQ-0477`<br>`SR-REQ-0481`<br>`SR-REQ-0487`–`SR-REQ-0490`<br>`SR-REQ-0502`–`SR-REQ-0503`<br>`SR-REQ-0543`<br>`SR-REQ-0549`–`SR-REQ-0572`<br>`SR-REQ-0608`<br>`SR-REQ-0610`<br>`SR-REQ-0616`<br>`SR-REQ-0624`–`SR-REQ-0628`<br>`SR-REQ-0630`<br>`SR-REQ-0632`<br>`SR-REQ-0635`<br>`SR-REQ-0643`–`SR-REQ-0649`<br>`SR-REQ-0670`<br>`SR-REQ-0675`<br>`SR-REQ-0689`<br>`SR-REQ-0691`<br>`SR-REQ-0700`<br>`SR-REQ-0705`<br>`SR-REQ-0714`<br>`SR-REQ-0726`<br>`SR-REQ-0731`–`SR-REQ-0733`<br>`SR-REQ-0735`–`SR-REQ-0738`<br>`SR-REQ-0740`<br>`SR-REQ-0742` |
| SR-NEED-0009 | 198 | `SR-REQ-0019`–`SR-REQ-0020`<br>`SR-REQ-0023`<br>`SR-REQ-0025`–`SR-REQ-0026`<br>`SR-REQ-0030`–`SR-REQ-0031`<br>`SR-REQ-0033`–`SR-REQ-0037`<br>`SR-REQ-0040`<br>`SR-REQ-0043`–`SR-REQ-0048`<br>`SR-REQ-0061`–`SR-REQ-0062`<br>`SR-REQ-0064`<br>`SR-REQ-0071`<br>`SR-REQ-0081`<br>`SR-REQ-0092`<br>`SR-REQ-0102`–`SR-REQ-0103`<br>`SR-REQ-0105`<br>`SR-REQ-0107`<br>`SR-REQ-0111`–`SR-REQ-0112`<br>`SR-REQ-0122`<br>`SR-REQ-0129`<br>`SR-REQ-0132`–`SR-REQ-0135`<br>`SR-REQ-0138`<br>`SR-REQ-0143`<br>`SR-REQ-0145`–`SR-REQ-0148`<br>`SR-REQ-0150`–`SR-REQ-0153`<br>`SR-REQ-0156`–`SR-REQ-0157`<br>`SR-REQ-0163`<br>`SR-REQ-0171`–`SR-REQ-0172`<br>`SR-REQ-0178`<br>`SR-REQ-0184`<br>`SR-REQ-0196`–`SR-REQ-0199`<br>`SR-REQ-0204`<br>`SR-REQ-0206`–`SR-REQ-0208`<br>`SR-REQ-0216`<br>`SR-REQ-0218`<br>`SR-REQ-0220`<br>`SR-REQ-0234`<br>`SR-REQ-0241`<br>`SR-REQ-0245`–`SR-REQ-0246`<br>`SR-REQ-0250`<br>`SR-REQ-0253`<br>`SR-REQ-0257`–`SR-REQ-0260`<br>`SR-REQ-0262`<br>`SR-REQ-0265`–`SR-REQ-0266`<br>`SR-REQ-0268`–`SR-REQ-0269`<br>`SR-REQ-0271`<br>`SR-REQ-0273`–`SR-REQ-0275`<br>`SR-REQ-0279`<br>`SR-REQ-0285`<br>`SR-REQ-0317`–`SR-REQ-0319`<br>`SR-REQ-0322`<br>`SR-REQ-0328`<br>`SR-REQ-0330`–`SR-REQ-0331`<br>`SR-REQ-0339`<br>`SR-REQ-0342`<br>`SR-REQ-0345`<br>`SR-REQ-0357`<br>`SR-REQ-0364`<br>`SR-REQ-0370`<br>`SR-REQ-0375`<br>`SR-REQ-0383`<br>`SR-REQ-0385`<br>`SR-REQ-0387`–`SR-REQ-0389`<br>`SR-REQ-0401`<br>`SR-REQ-0406`–`SR-REQ-0407`<br>`SR-REQ-0412`–`SR-REQ-0413`<br>`SR-REQ-0416`<br>`SR-REQ-0418`<br>`SR-REQ-0425`<br>`SR-REQ-0429`–`SR-REQ-0439`<br>`SR-REQ-0441`–`SR-REQ-0442`<br>`SR-REQ-0445`<br>`SR-REQ-0447`–`SR-REQ-0448`<br>`SR-REQ-0452`–`SR-REQ-0462`<br>`SR-REQ-0464`<br>`SR-REQ-0466`<br>`SR-REQ-0478`<br>`SR-REQ-0482`–`SR-REQ-0483`<br>`SR-REQ-0485`–`SR-REQ-0486`<br>`SR-REQ-0491`–`SR-REQ-0494`<br>`SR-REQ-0496`<br>`SR-REQ-0499`–`SR-REQ-0501`<br>`SR-REQ-0504`–`SR-REQ-0505`<br>`SR-REQ-0510`–`SR-REQ-0514`<br>`SR-REQ-0536`<br>`SR-REQ-0607`<br>`SR-REQ-0609`<br>`SR-REQ-0616`<br>`SR-REQ-0618`<br>`SR-REQ-0620`–`SR-REQ-0621`<br>`SR-REQ-0629`<br>`SR-REQ-0638`–`SR-REQ-0644`<br>`SR-REQ-0648`<br>`SR-REQ-0650`<br>`SR-REQ-0655`<br>`SR-REQ-0657`<br>`SR-REQ-0660`<br>`SR-REQ-0671`<br>`SR-REQ-0674`<br>`SR-REQ-0678`–`SR-REQ-0679`<br>`SR-REQ-0683`<br>`SR-REQ-0685`–`SR-REQ-0688`<br>`SR-REQ-0690`<br>`SR-REQ-0697`<br>`SR-REQ-0724`–`SR-REQ-0725`<br>`SR-REQ-0733`–`SR-REQ-0734`<br>`SR-REQ-0741` |
| SR-NEED-0010 | 14 | `SR-REQ-0058`<br>`SR-REQ-0109`<br>`SR-REQ-0118`–`SR-REQ-0119`<br>`SR-REQ-0121`–`SR-REQ-0125`<br>`SR-REQ-0128`<br>`SR-REQ-0211`<br>`SR-REQ-0395`<br>`SR-REQ-0408`<br>`SR-REQ-0546` |
| SR-NEED-0011 | 116 | `SR-REQ-0002`–`SR-REQ-0003`<br>`SR-REQ-0023`<br>`SR-REQ-0100`<br>`SR-REQ-0117`<br>`SR-REQ-0128`<br>`SR-REQ-0135`<br>`SR-REQ-0165`–`SR-REQ-0168`<br>`SR-REQ-0170`<br>`SR-REQ-0175`<br>`SR-REQ-0188`–`SR-REQ-0191`<br>`SR-REQ-0195`–`SR-REQ-0206`<br>`SR-REQ-0221`<br>`SR-REQ-0224`–`SR-REQ-0225`<br>`SR-REQ-0229`<br>`SR-REQ-0236`<br>`SR-REQ-0239`<br>`SR-REQ-0245`<br>`SR-REQ-0249`<br>`SR-REQ-0252`–`SR-REQ-0258`<br>`SR-REQ-0260`–`SR-REQ-0261`<br>`SR-REQ-0266`–`SR-REQ-0267`<br>`SR-REQ-0274`<br>`SR-REQ-0287`<br>`SR-REQ-0289`<br>`SR-REQ-0295`–`SR-REQ-0296`<br>`SR-REQ-0304`<br>`SR-REQ-0306`<br>`SR-REQ-0315`<br>`SR-REQ-0323`–`SR-REQ-0324`<br>`SR-REQ-0329`<br>`SR-REQ-0341`<br>`SR-REQ-0344`<br>`SR-REQ-0348`<br>`SR-REQ-0350`<br>`SR-REQ-0355`<br>`SR-REQ-0359`–`SR-REQ-0360`<br>`SR-REQ-0363`<br>`SR-REQ-0373`<br>`SR-REQ-0390`<br>`SR-REQ-0393`–`SR-REQ-0394`<br>`SR-REQ-0458`<br>`SR-REQ-0460`–`SR-REQ-0461`<br>`SR-REQ-0465`–`SR-REQ-0466`<br>`SR-REQ-0469`<br>`SR-REQ-0479`–`SR-REQ-0480`<br>`SR-REQ-0484`<br>`SR-REQ-0506`–`SR-REQ-0507`<br>`SR-REQ-0511`<br>`SR-REQ-0513`<br>`SR-REQ-0518`<br>`SR-REQ-0523`<br>`SR-REQ-0527`–`SR-REQ-0528`<br>`SR-REQ-0532`<br>`SR-REQ-0535`<br>`SR-REQ-0538`<br>`SR-REQ-0540`<br>`SR-REQ-0544`–`SR-REQ-0545`<br>`SR-REQ-0609`<br>`SR-REQ-0615`<br>`SR-REQ-0619`<br>`SR-REQ-0621`<br>`SR-REQ-0625`–`SR-REQ-0626`<br>`SR-REQ-0634`<br>`SR-REQ-0645`<br>`SR-REQ-0647`<br>`SR-REQ-0677`<br>`SR-REQ-0680`<br>`SR-REQ-0690`<br>`SR-REQ-0692`<br>`SR-REQ-0695`<br>`SR-REQ-0702`–`SR-REQ-0704`<br>`SR-REQ-0717`<br>`SR-REQ-0735`–`SR-REQ-0736`<br>`SR-REQ-0739`<br>`SR-REQ-0741` |
| SR-NEED-0012 | 145 | `SR-REQ-0004`<br>`SR-REQ-0007`–`SR-REQ-0008`<br>`SR-REQ-0011`<br>`SR-REQ-0013`–`SR-REQ-0015`<br>`SR-REQ-0017`–`SR-REQ-0019`<br>`SR-REQ-0027`–`SR-REQ-0028`<br>`SR-REQ-0038`–`SR-REQ-0039`<br>`SR-REQ-0053`<br>`SR-REQ-0057`<br>`SR-REQ-0069`<br>`SR-REQ-0079`–`SR-REQ-0080`<br>`SR-REQ-0098`<br>`SR-REQ-0110`<br>`SR-REQ-0146`<br>`SR-REQ-0159`–`SR-REQ-0160`<br>`SR-REQ-0194`<br>`SR-REQ-0201`–`SR-REQ-0202`<br>`SR-REQ-0209`<br>`SR-REQ-0212`<br>`SR-REQ-0214`–`SR-REQ-0215`<br>`SR-REQ-0223`–`SR-REQ-0224`<br>`SR-REQ-0226`<br>`SR-REQ-0229`–`SR-REQ-0230`<br>`SR-REQ-0243`–`SR-REQ-0244`<br>`SR-REQ-0249`<br>`SR-REQ-0263`–`SR-REQ-0265`<br>`SR-REQ-0268`<br>`SR-REQ-0272`<br>`SR-REQ-0282`<br>`SR-REQ-0286`–`SR-REQ-0296`<br>`SR-REQ-0298`<br>`SR-REQ-0301`<br>`SR-REQ-0306`<br>`SR-REQ-0316`<br>`SR-REQ-0335`<br>`SR-REQ-0337`<br>`SR-REQ-0343`<br>`SR-REQ-0348`–`SR-REQ-0350`<br>`SR-REQ-0360`<br>`SR-REQ-0367`<br>`SR-REQ-0376`–`SR-REQ-0379`<br>`SR-REQ-0381`<br>`SR-REQ-0391`–`SR-REQ-0394`<br>`SR-REQ-0396`<br>`SR-REQ-0404`<br>`SR-REQ-0419`–`SR-REQ-0425`<br>`SR-REQ-0474`<br>`SR-REQ-0476`–`SR-REQ-0477`<br>`SR-REQ-0496`–`SR-REQ-0498`<br>`SR-REQ-0502`–`SR-REQ-0503`<br>`SR-REQ-0508`<br>`SR-REQ-0515`<br>`SR-REQ-0517`–`SR-REQ-0523`<br>`SR-REQ-0528`<br>`SR-REQ-0538`<br>`SR-REQ-0542`<br>`SR-REQ-0544`–`SR-REQ-0545`<br>`SR-REQ-0547`<br>`SR-REQ-0570`<br>`SR-REQ-0581`–`SR-REQ-0582`<br>`SR-REQ-0587`–`SR-REQ-0591`<br>`SR-REQ-0596`–`SR-REQ-0597`<br>`SR-REQ-0605`<br>`SR-REQ-0615`<br>`SR-REQ-0632`<br>`SR-REQ-0640`–`SR-REQ-0641`<br>`SR-REQ-0658`–`SR-REQ-0659`<br>`SR-REQ-0661`<br>`SR-REQ-0667`<br>`SR-REQ-0669`–`SR-REQ-0670`<br>`SR-REQ-0675`–`SR-REQ-0676`<br>`SR-REQ-0684`<br>`SR-REQ-0696`<br>`SR-REQ-0699`–`SR-REQ-0701`<br>`SR-REQ-0722`<br>`SR-REQ-0727`–`SR-REQ-0732`<br>`SR-REQ-0742` |
| SR-NEED-0013 | 99 | `SR-REQ-0159`–`SR-REQ-0160`<br>`SR-REQ-0175`<br>`SR-REQ-0179`–`SR-REQ-0180`<br>`SR-REQ-0189`<br>`SR-REQ-0204`–`SR-REQ-0206`<br>`SR-REQ-0209`<br>`SR-REQ-0217`–`SR-REQ-0218`<br>`SR-REQ-0221`<br>`SR-REQ-0231`–`SR-REQ-0233`<br>`SR-REQ-0235`–`SR-REQ-0239`<br>`SR-REQ-0241`–`SR-REQ-0242`<br>`SR-REQ-0252`–`SR-REQ-0262`<br>`SR-REQ-0308`<br>`SR-REQ-0333`<br>`SR-REQ-0341`<br>`SR-REQ-0382`–`SR-REQ-0385`<br>`SR-REQ-0435`–`SR-REQ-0443`<br>`SR-REQ-0458`–`SR-REQ-0459`<br>`SR-REQ-0461`–`SR-REQ-0464`<br>`SR-REQ-0471`<br>`SR-REQ-0478`<br>`SR-REQ-0480`<br>`SR-REQ-0487`<br>`SR-REQ-0489`–`SR-REQ-0490`<br>`SR-REQ-0502`–`SR-REQ-0503`<br>`SR-REQ-0505`–`SR-REQ-0507`<br>`SR-REQ-0511`<br>`SR-REQ-0535`<br>`SR-REQ-0543`<br>`SR-REQ-0549`–`SR-REQ-0551`<br>`SR-REQ-0553`–`SR-REQ-0559`<br>`SR-REQ-0561`–`SR-REQ-0564`<br>`SR-REQ-0568`–`SR-REQ-0569`<br>`SR-REQ-0572`<br>`SR-REQ-0599`<br>`SR-REQ-0607`<br>`SR-REQ-0611`<br>`SR-REQ-0616`–`SR-REQ-0618`<br>`SR-REQ-0620`–`SR-REQ-0621`<br>`SR-REQ-0637`<br>`SR-REQ-0646`<br>`SR-REQ-0649`<br>`SR-REQ-0652` |
| SR-NEED-0014 | 87 | `SR-REQ-0011`<br>`SR-REQ-0013`<br>`SR-REQ-0030`<br>`SR-REQ-0040`<br>`SR-REQ-0090`<br>`SR-REQ-0114`<br>`SR-REQ-0143`<br>`SR-REQ-0146`<br>`SR-REQ-0151`<br>`SR-REQ-0247`<br>`SR-REQ-0263`–`SR-REQ-0274`<br>`SR-REQ-0286`<br>`SR-REQ-0298`<br>`SR-REQ-0313`–`SR-REQ-0332`<br>`SR-REQ-0334`<br>`SR-REQ-0336`<br>`SR-REQ-0356`<br>`SR-REQ-0362`<br>`SR-REQ-0386`–`SR-REQ-0391`<br>`SR-REQ-0405`<br>`SR-REQ-0407`–`SR-REQ-0408`<br>`SR-REQ-0413`<br>`SR-REQ-0416`<br>`SR-REQ-0453`–`SR-REQ-0457`<br>`SR-REQ-0481`–`SR-REQ-0486`<br>`SR-REQ-0488`<br>`SR-REQ-0512`–`SR-REQ-0513`<br>`SR-REQ-0517`<br>`SR-REQ-0532`<br>`SR-REQ-0541`<br>`SR-REQ-0628`<br>`SR-REQ-0639`–`SR-REQ-0642`<br>`SR-REQ-0660`<br>`SR-REQ-0691`<br>`SR-REQ-0723`–`SR-REQ-0726` |
| SR-NEED-0015 | 76 | `SR-REQ-0038`<br>`SR-REQ-0053`<br>`SR-REQ-0101`<br>`SR-REQ-0115`<br>`SR-REQ-0130`<br>`SR-REQ-0136`–`SR-REQ-0137`<br>`SR-REQ-0299`–`SR-REQ-0313`<br>`SR-REQ-0320`–`SR-REQ-0321`<br>`SR-REQ-0349`–`SR-REQ-0360`<br>`SR-REQ-0395`–`SR-REQ-0398`<br>`SR-REQ-0400`–`SR-REQ-0402`<br>`SR-REQ-0404`<br>`SR-REQ-0409`<br>`SR-REQ-0411`<br>`SR-REQ-0414`<br>`SR-REQ-0417`<br>`SR-REQ-0451`<br>`SR-REQ-0467`–`SR-REQ-0472`<br>`SR-REQ-0479`<br>`SR-REQ-0482`<br>`SR-REQ-0524`–`SR-REQ-0531`<br>`SR-REQ-0538`–`SR-REQ-0540`<br>`SR-REQ-0546`–`SR-REQ-0548`<br>`SR-REQ-0623`<br>`SR-REQ-0654`–`SR-REQ-0655`<br>`SR-REQ-0664`<br>`SR-REQ-0672` |
| SR-NEED-0016 | 72 | `SR-REQ-0026`<br>`SR-REQ-0038`<br>`SR-REQ-0052`<br>`SR-REQ-0057`<br>`SR-REQ-0132`–`SR-REQ-0133`<br>`SR-REQ-0216`<br>`SR-REQ-0244`–`SR-REQ-0251`<br>`SR-REQ-0275`–`SR-REQ-0280`<br>`SR-REQ-0282`–`SR-REQ-0283`<br>`SR-REQ-0285`<br>`SR-REQ-0333`–`SR-REQ-0340`<br>`SR-REQ-0342`–`SR-REQ-0346`<br>`SR-REQ-0348`<br>`SR-REQ-0361`–`SR-REQ-0375`<br>`SR-REQ-0399`<br>`SR-REQ-0403`<br>`SR-REQ-0418`<br>`SR-REQ-0434`<br>`SR-REQ-0495`<br>`SR-REQ-0501`<br>`SR-REQ-0504`<br>`SR-REQ-0508`–`SR-REQ-0510`<br>`SR-REQ-0514`–`SR-REQ-0516`<br>`SR-REQ-0533`–`SR-REQ-0534`<br>`SR-REQ-0536`<br>`SR-REQ-0541`–`SR-REQ-0542`<br>`SR-REQ-0638` |
| SR-NEED-0017 | 33 | `SR-REQ-0549`–`SR-REQ-0572`<br>`SR-REQ-0608`<br>`SR-REQ-0610`<br>`SR-REQ-0619`<br>`SR-REQ-0628`–`SR-REQ-0630`<br>`SR-REQ-0635`<br>`SR-REQ-0715`–`SR-REQ-0716` |
| SR-NEED-0018 | 46 | `SR-REQ-0573`–`SR-REQ-0602`<br>`SR-REQ-0604`–`SR-REQ-0606`<br>`SR-REQ-0612`–`SR-REQ-0614`<br>`SR-REQ-0631`<br>`SR-REQ-0634`–`SR-REQ-0635`<br>`SR-REQ-0694`<br>`SR-REQ-0705`<br>`SR-REQ-0715`<br>`SR-REQ-0717`–`SR-REQ-0719`<br>`SR-REQ-0721` |
| SR-NEED-0019 | 34 | `SR-REQ-0601`–`SR-REQ-0615`<br>`SR-REQ-0617`–`SR-REQ-0620`<br>`SR-REQ-0622`–`SR-REQ-0627`<br>`SR-REQ-0629`–`SR-REQ-0631`<br>`SR-REQ-0633`–`SR-REQ-0634`<br>`SR-REQ-0636`<br>`SR-REQ-0715`–`SR-REQ-0716`<br>`SR-REQ-0719` |
| SR-NEED-0020 | 38 | `SR-REQ-0651`–`SR-REQ-0674`<br>`SR-REQ-0681`<br>`SR-REQ-0698`<br>`SR-REQ-0706`–`SR-REQ-0713`<br>`SR-REQ-0720`<br>`SR-REQ-0723`–`SR-REQ-0725` |
| SR-NEED-0021 | 50 | `SR-REQ-0673`<br>`SR-REQ-0675`–`SR-REQ-0722`<br>`SR-REQ-0726` |

### 15.3 Anforderungsabdeckung durch Verifikation

| Verification | Anzahl Anforderungen | Exakt abgedeckte IDs |
|---|---:|---|
| SR-VER-0001 | 10 | `SR-REQ-0001`–`SR-REQ-0010` |
| SR-VER-0002 | 15 | `SR-REQ-0011`–`SR-REQ-0025` |
| SR-VER-0003 | 10 | `SR-REQ-0027`–`SR-REQ-0029`<br>`SR-REQ-0031`–`SR-REQ-0037` |
| SR-VER-0004 | 14 | `SR-REQ-0038`–`SR-REQ-0051` |
| SR-VER-0005 | 12 | `SR-REQ-0053`–`SR-REQ-0056`<br>`SR-REQ-0058`–`SR-REQ-0065` |
| SR-VER-0006 | 12 | `SR-REQ-0066`–`SR-REQ-0067`<br>`SR-REQ-0070`<br>`SR-REQ-0072`–`SR-REQ-0079`<br>`SR-REQ-0081` |
| SR-VER-0007 | 18 | `SR-REQ-0083`–`SR-REQ-0100` |
| SR-VER-0008 | 17 | `SR-REQ-0101`–`SR-REQ-0117` |
| SR-VER-0009 | 11 | `SR-REQ-0118`–`SR-REQ-0128` |
| SR-VER-0010 | 11 | `SR-REQ-0129`–`SR-REQ-0131`<br>`SR-REQ-0134`<br>`SR-REQ-0136`–`SR-REQ-0142` |
| SR-VER-0011 | 12 | `SR-REQ-0143`–`SR-REQ-0153`<br>`SR-REQ-0220` |
| SR-VER-0012 | 26 | `SR-REQ-0154`–`SR-REQ-0167`<br>`SR-REQ-0169`–`SR-REQ-0174`<br>`SR-REQ-0176`–`SR-REQ-0178`<br>`SR-REQ-0219`<br>`SR-REQ-0502`–`SR-REQ-0503` |
| SR-VER-0013 | 17 | `SR-REQ-0179`–`SR-REQ-0188`<br>`SR-REQ-0190`–`SR-REQ-0194`<br>`SR-REQ-0214`<br>`SR-REQ-0222` |
| SR-VER-0014 | 11 | `SR-REQ-0135`<br>`SR-REQ-0168`<br>`SR-REQ-0195`–`SR-REQ-0203` |
| SR-VER-0015 | 6 | `SR-REQ-0207`–`SR-REQ-0208`<br>`SR-REQ-0210`–`SR-REQ-0213` |
| SR-VER-0016 | 1 | `SR-REQ-0215` |
| SR-VER-0017 | 3 | `SR-REQ-0225`<br>`SR-REQ-0228`–`SR-REQ-0229` |
| SR-VER-0018 | 31 | `SR-REQ-0026`<br>`SR-REQ-0030`<br>`SR-REQ-0216`–`SR-REQ-0218`<br>`SR-REQ-0231`–`SR-REQ-0249`<br>`SR-REQ-0251`<br>`SR-REQ-0501`<br>`SR-REQ-0504`–`SR-REQ-0505`<br>`SR-REQ-0507`–`SR-REQ-0509` |
| SR-VER-0019 | 19 | `SR-REQ-0175`<br>`SR-REQ-0189`<br>`SR-REQ-0204`–`SR-REQ-0206`<br>`SR-REQ-0221`<br>`SR-REQ-0252`–`SR-REQ-0262`<br>`SR-REQ-0506`<br>`SR-REQ-0511` |
| SR-VER-0020 | 14 | `SR-REQ-0263`–`SR-REQ-0274`<br>`SR-REQ-0512`–`SR-REQ-0513` |
| SR-VER-0021 | 16 | `SR-REQ-0052`<br>`SR-REQ-0057`<br>`SR-REQ-0275`–`SR-REQ-0285`<br>`SR-REQ-0514`–`SR-REQ-0516` |
| SR-VER-0022 | 20 | `SR-REQ-0286`–`SR-REQ-0298`<br>`SR-REQ-0517`–`SR-REQ-0523` |
| SR-VER-0023 | 37 | `SR-REQ-0299`–`SR-REQ-0312`<br>`SR-REQ-0349`–`SR-REQ-0360`<br>`SR-REQ-0524`–`SR-REQ-0531`<br>`SR-REQ-0538`–`SR-REQ-0540` |
| SR-VER-0024 | 21 | `SR-REQ-0313`–`SR-REQ-0332`<br>`SR-REQ-0532` |
| SR-VER-0025 | 23 | `SR-REQ-0132`–`SR-REQ-0133`<br>`SR-REQ-0333`–`SR-REQ-0348`<br>`SR-REQ-0533`–`SR-REQ-0537` |
| SR-VER-0026 | 19 | `SR-REQ-0250`<br>`SR-REQ-0361`–`SR-REQ-0375`<br>`SR-REQ-0510`<br>`SR-REQ-0541`–`SR-REQ-0542` |
| SR-VER-0027 | 28 | `SR-REQ-0209`<br>`SR-REQ-0223`–`SR-REQ-0224`<br>`SR-REQ-0226`–`SR-REQ-0227`<br>`SR-REQ-0230`<br>`SR-REQ-0376`–`SR-REQ-0394`<br>`SR-REQ-0543`–`SR-REQ-0545` |
| SR-VER-0028 | 13 | `SR-REQ-0395`–`SR-REQ-0404`<br>`SR-REQ-0546`–`SR-REQ-0548` |
| SR-VER-0029 | 20 | `SR-REQ-0405`–`SR-REQ-0415`<br>`SR-REQ-0417`–`SR-REQ-0425` |
| SR-VER-0030 | 24 | `SR-REQ-0426`–`SR-REQ-0440`<br>`SR-REQ-0442`–`SR-REQ-0447`<br>`SR-REQ-0450`–`SR-REQ-0452` |
| SR-VER-0031 | 16 | `SR-REQ-0441`<br>`SR-REQ-0448`<br>`SR-REQ-0453`–`SR-REQ-0466` |
| SR-VER-0032 | 15 | `SR-REQ-0449`<br>`SR-REQ-0467`–`SR-REQ-0480` |
| SR-VER-0033 | 11 | `SR-REQ-0416`<br>`SR-REQ-0481`–`SR-REQ-0490` |
| SR-VER-0034 | 10 | `SR-REQ-0491`–`SR-REQ-0500` |
| SR-VER-0035 | 18 | `SR-REQ-0549`–`SR-REQ-0551`<br>`SR-REQ-0553`–`SR-REQ-0559`<br>`SR-REQ-0561`–`SR-REQ-0564`<br>`SR-REQ-0568`–`SR-REQ-0569`<br>`SR-REQ-0572`<br>`SR-REQ-0599` |
| SR-VER-0036 | 9 | `SR-REQ-0552`<br>`SR-REQ-0560`<br>`SR-REQ-0565`–`SR-REQ-0567`<br>`SR-REQ-0571`<br>`SR-REQ-0594`–`SR-REQ-0595`<br>`SR-REQ-0600` |
| SR-VER-0037 | 15 | `SR-REQ-0573`–`SR-REQ-0580`<br>`SR-REQ-0583`–`SR-REQ-0586`<br>`SR-REQ-0592`–`SR-REQ-0593`<br>`SR-REQ-0598` |
| SR-VER-0038 | 10 | `SR-REQ-0570`<br>`SR-REQ-0581`–`SR-REQ-0582`<br>`SR-REQ-0587`–`SR-REQ-0591`<br>`SR-REQ-0596`–`SR-REQ-0597` |
| SR-VER-0039 | 16 | `SR-REQ-0601`–`SR-REQ-0607`<br>`SR-REQ-0612`–`SR-REQ-0614`<br>`SR-REQ-0619`<br>`SR-REQ-0622`–`SR-REQ-0623`<br>`SR-REQ-0631`<br>`SR-REQ-0633`<br>`SR-REQ-0636` |
| SR-VER-0040 | 16 | `SR-REQ-0608`–`SR-REQ-0610`<br>`SR-REQ-0615`–`SR-REQ-0618`<br>`SR-REQ-0624`–`SR-REQ-0630`<br>`SR-REQ-0632`<br>`SR-REQ-0635` |
| SR-VER-0041 | 7 | `SR-REQ-0611`<br>`SR-REQ-0620`–`SR-REQ-0621`<br>`SR-REQ-0634`<br>`SR-REQ-0637`–`SR-REQ-0638`<br>`SR-REQ-0650` |
| SR-VER-0042 | 4 | `SR-REQ-0639`–`SR-REQ-0642` |
| SR-VER-0043 | 7 | `SR-REQ-0643`–`SR-REQ-0649` |
| SR-VER-0044 | 13 | `SR-REQ-0068`–`SR-REQ-0069`<br>`SR-REQ-0071`<br>`SR-REQ-0651`–`SR-REQ-0657`<br>`SR-REQ-0671`<br>`SR-REQ-0673`–`SR-REQ-0674` |
| SR-VER-0045 | 16 | `SR-REQ-0080`<br>`SR-REQ-0082`<br>`SR-REQ-0658`–`SR-REQ-0670`<br>`SR-REQ-0672` |
| SR-VER-0046 | 22 | `SR-REQ-0675`–`SR-REQ-0693`<br>`SR-REQ-0695`–`SR-REQ-0697` |
| SR-VER-0047 | 11 | `SR-REQ-0698`–`SR-REQ-0699`<br>`SR-REQ-0706`–`SR-REQ-0713`<br>`SR-REQ-0720` |
| SR-VER-0048 | 15 | `SR-REQ-0694`<br>`SR-REQ-0700`–`SR-REQ-0705`<br>`SR-REQ-0714`–`SR-REQ-0719`<br>`SR-REQ-0721`–`SR-REQ-0722` |
| SR-VER-0049 | 4 | `SR-REQ-0723`–`SR-REQ-0726` |
| SR-VER-0050 | 4 | `SR-REQ-0727`–`SR-REQ-0730` |
| SR-VER-0051 | 12 | `SR-REQ-0731`–`SR-REQ-0742` |

### 15.4 Anforderungskatalog nach Bereich

| Bereich | Anzahl | Requirements |
|---|---:|---|
| 12.1 Projektinitialisierung und Konfiguration | 10 | `SR-REQ-0001`–`SR-REQ-0010` |
| 12.2 Kanonisches Modell und Speicherung | 15 | `SR-REQ-0011`–`SR-REQ-0025` |
| 12.3 IDs, Revisionen und Provenienz | 12 | `SR-REQ-0026`–`SR-REQ-0037` |
| 12.4 Artefakttypen und Lebenszyklus | 14 | `SR-REQ-0038`–`SR-REQ-0051` |
| 12.5 Relationsgraph und Traceability | 14 | `SR-REQ-0052`–`SR-REQ-0065` |
| 12.6 Requirements, Profile und Glossar | 17 | `SR-REQ-0066`–`SR-REQ-0082` |
| 12.7 Validierung und Diagnosen | 18 | `SR-REQ-0083`–`SR-REQ-0100` |
| 12.8 Rendering, Abfragen, Trace, Impact und Diff | 17 | `SR-REQ-0101`–`SR-REQ-0117` |
| 12.9 Release, Milestone, Task und Roadmap | 11 | `SR-REQ-0118`–`SR-REQ-0128` |
| 12.10 Verifikation, Tests, Evidenz und Coverage | 14 | `SR-REQ-0129`–`SR-REQ-0142` |
| 12.11 Baselines | 11 | `SR-REQ-0143`–`SR-REQ-0153` |
| 12.12 KI-Proposals und isolierte Ausführung | 25 | `SR-REQ-0154`–`SR-REQ-0178` |
| 12.13 CLI, Git, CI und Agentenbedienung | 16 | `SR-REQ-0179`–`SR-REQ-0194` |
| 12.14 Qualitäts-, Sicherheits- und Performanceanforderungen | 21 | `SR-REQ-0195`–`SR-REQ-0215` |
| 12.15 Ergänzende CLI-Operationsverträge | 7 | `SR-REQ-0216`–`SR-REQ-0222` |
| 12.16 Python-, Laufzeit- und Sandbox-Portabilität | 8 | `SR-REQ-0223`–`SR-REQ-0230` |
| 12.17 Vollständiges CLI-Authoring und gemeinsamer Change Plan | 13 | `SR-REQ-0231`–`SR-REQ-0243` |
| 12.18 Kollisionsresistente IDs und parallele Arbeitsstände | 8 | `SR-REQ-0244`–`SR-REQ-0251` |
| 12.19 Transaktionsjournal und Recovery | 11 | `SR-REQ-0252`–`SR-REQ-0262` |
| 12.20 Schema- und Datenmigration | 12 | `SR-REQ-0263`–`SR-REQ-0274` |
| 12.21 Suspect Relations und fachliche Relationsreviews | 11 | `SR-REQ-0275`–`SR-REQ-0285` |
| 12.22 Deklarative Regelsprache SRX 1.0 | 13 | `SR-REQ-0286`–`SR-REQ-0298` |
| 12.23 Dokumente, Abschnitte und Inhaltsblöcke | 14 | `SR-REQ-0299`–`SR-REQ-0312` |
| 12.24 Import, Export und Austauschformate | 20 | `SR-REQ-0313`–`SR-REQ-0332` |
| 12.25 Evidence-Import und Quellcode-Traceability | 16 | `SR-REQ-0333`–`SR-REQ-0348` |
| 12.26 Deklarative Ansichten, Berichte und Diagrammquellen | 12 | `SR-REQ-0349`–`SR-REQ-0360` |
| 12.27 Semantischer Dreiwege-Merge | 15 | `SR-REQ-0361`–`SR-REQ-0375` |
| 12.28 Agentenselbstbeschreibung, Idempotenz, Bundles und Kompatibilität | 19 | `SR-REQ-0376`–`SR-REQ-0394` |
| 12.29 Konfigurationen, Varianten und Wiederverwendung | 10 | `SR-REQ-0395`–`SR-REQ-0404` |
| 12.30 Normative Modellumfänge und Scope-Closure | 10 | `SR-REQ-0405`–`SR-REQ-0414` |
| 12.31 Relationsmatrix und Profilkomposition | 11 | `SR-REQ-0415`–`SR-REQ-0425` |
| 12.32 Proposal-Authoring, Change-Plan-Metadaten und Spezial-Lifecycles | 18 | `SR-REQ-0426`–`SR-REQ-0443` |
| 12.33 Verifikationsplanung und berechnete Ergebnisse | 9 | `SR-REQ-0444`–`SR-REQ-0452` |
| 12.34 External Identities, Importvergleich, Recovery und Formatierung | 14 | `SR-REQ-0453`–`SR-REQ-0466` |
| 12.35 Dokumentpayloads, Query, JSON und Befehlsklassen | 14 | `SR-REQ-0467`–`SR-REQ-0480` |
| 12.36 Partielle Bundles, kanonisches ZIP und portable Idempotenz | 10 | `SR-REQ-0481`–`SR-REQ-0490` |
| 12.37 Testfall-Traceability, Codezustand und reproduzierbare Performance | 10 | `SR-REQ-0491`–`SR-REQ-0500` |
| 12.38 Atomisierte Nebenverträge bestehender Anforderungen | 48 | `SR-REQ-0501`–`SR-REQ-0548` |
| 12.39 Ephemeral Runtime Safety | 24 | `SR-REQ-0549`–`SR-REQ-0572` |
| 12.40 Resource-Constrained Runtime Design | 28 | `SR-REQ-0573`–`SR-REQ-0600` |
| 12.41 Vollständige adaptive Arbeit und Mehrprompt-Fortsetzung | 50 | `SR-REQ-0601`–`SR-REQ-0650` |
| 12.42 Explizite Verbindlichkeit und mehrsprachiger Inhalt | 24 | `SR-REQ-0651`–`SR-REQ-0674` |
| 12.43 Allgemeine Analyzer-Schnittstelle und Findings | 23 | `SR-REQ-0675`–`SR-REQ-0697` |
| 12.44 Implementierter py3langid-Adapter und vollständige Ausführung | 25 | `SR-REQ-0698`–`SR-REQ-0722` |
| 12.45 Migration, Austausch und geschlossene SRX-Präzision | 8 | `SR-REQ-0723`–`SR-REQ-0730` |
| 12.46 Portabler Projekt-Rundweg über PatchHarbor | 12 | `SR-REQ-0731`–`SR-REQ-0742` |

### 15.5 Qualitätskennzahlen dieser Spezifikation

| Kennzahl | Wert |
|---|---:|
| Produktziele | 10 |
| Stakeholder-Bedarfe | 21 |
| Nutzungsszenarien | 46 |
| Architekturentscheidungen | 53 |
| Normative Produktanforderungen | 742 |
| Primäre Requirement-Solltestfälle | 742 |
| Verifikationsverträge | 51 |
| Diagnosecodes | 107 |
| Kanonische Artefakttypen | 28 |
| Requirements ohne Need / Verification / Solltestfall | 0 / 0 / 0 |
| Doppelte Requirement-IDs | 0 |
| Formale Zuordnung Requirement → Need / Verification / Solltestfall | jeweils 100 % |

Diese Kennzahlen betreffen ausschließlich die Dokumentstruktur und geplante Traceability. Sie besagen weder, dass ein Produkt implementiert ist, noch dass dessen Tests bestanden sind.

### 15.6 Szenario-zu-Requirement-Testfall-Matrix

Die folgende Matrix ist der exakte Mindestumfang jedes End-to-End-Szenarios. Ein Szenariotest darf weitere Testfälle ausführen, aber keinen genannten Testfall auslassen.

| Szenario | Exakter Mindestumfang | Primäre End-to-End-Evidence |
|---|---|---|
| SR-SCN-0001 | `SR-TC-0001`–`SR-TC-0010`<br>`SR-TC-0179`–`SR-TC-0188`<br>`SR-TC-0223`–`SR-TC-0227`<br>`SR-TC-0480` | SR-E2E-0001 |
| SR-SCN-0002 | `SR-TC-0066`–`SR-TC-0082`<br>`SR-TC-0216`–`SR-TC-0218`<br>`SR-TC-0231`–`SR-TC-0243`<br>`SR-TC-0435`–`SR-TC-0443`<br>`SR-TC-0504`–`SR-TC-0505`<br>`SR-TC-0507` | SR-E2E-0002 |
| SR-SCN-0003 | `SR-TC-0083`–`SR-TC-0100`<br>`SR-TC-0286`–`SR-TC-0298`<br>`SR-TC-0499`–`SR-TC-0500`<br>`SR-TC-0517`–`SR-TC-0523` | SR-E2E-0003 |
| SR-SCN-0004 | `SR-TC-0052`–`SR-TC-0065`<br>`SR-TC-0108`–`SR-TC-0113`<br>`SR-TC-0275`–`SR-TC-0285`<br>`SR-TC-0415`–`SR-TC-0418`<br>`SR-TC-0514`–`SR-TC-0516` | SR-E2E-0004 |
| SR-SCN-0005 | `SR-TC-0114`–`SR-TC-0117`<br>`SR-TC-0361`–`SR-TC-0375`<br>`SR-TC-0476`–`SR-TC-0477`<br>`SR-TC-0541`–`SR-TC-0542` | SR-E2E-0005 |
| SR-SCN-0006 | `SR-TC-0118`–`SR-TC-0128`<br>`SR-TC-0136`–`SR-TC-0141`<br>`SR-TC-0400`–`SR-TC-0414`<br>`SR-TC-0450` | SR-E2E-0006 |
| SR-SCN-0007 | `SR-TC-0129`–`SR-TC-0142`<br>`SR-TC-0444`–`SR-TC-0452` | SR-E2E-0007 |
| SR-SCN-0008 | `SR-TC-0143`–`SR-TC-0153`<br>`SR-TC-0433`–`SR-TC-0481` | SR-E2E-0008 |
| SR-SCN-0009 | `SR-TC-0154`–`SR-TC-0170`<br>`SR-TC-0426`–`SR-TC-0430`<br>`SR-TC-0502`–`SR-TC-0503` | SR-E2E-0009 |
| SR-SCN-0010 | `SR-TC-0171`–`SR-TC-0178`<br>`SR-TC-0431`–`SR-TC-0443` | SR-E2E-0010 |
| SR-SCN-0011 | `SR-TC-0083`–`SR-TC-0100`<br>`SR-TC-0179`–`SR-TC-0194`<br>`SR-TC-0476`–`SR-TC-0477` | SR-E2E-0011 |
| SR-SCN-0012 | `SR-TC-0101`–`SR-TC-0107`<br>`SR-TC-0299`–`SR-TC-0312`<br>`SR-TC-0467`–`SR-TC-0472`<br>`SR-TC-0524`–`SR-TC-0531` | SR-E2E-0012 |
| SR-SCN-0013 | `SR-TC-0223`–`SR-TC-0230`<br>`SR-TC-0386`–`SR-TC-0394`<br>`SR-TC-0487`–`SR-TC-0490`<br>`SR-TC-0544`–`SR-TC-0545`<br>`SR-TC-0731`–`SR-TC-0742` | SR-E2E-0013 |
| SR-SCN-0014 | `SR-TC-0216`–`SR-TC-0218`<br>`SR-TC-0231`–`SR-TC-0243`<br>`SR-TC-0435`–`SR-TC-0443`<br>`SR-TC-0504`–`SR-TC-0505`<br>`SR-TC-0507` | SR-E2E-0014 |
| SR-SCN-0015 | `SR-TC-0244`–`SR-TC-0251`<br>`SR-TC-0361`–`SR-TC-0375`<br>`SR-TC-0508`–`SR-TC-0510`<br>`SR-TC-0541`–`SR-TC-0542` | SR-E2E-0015 |
| SR-SCN-0016 | `SR-TC-0252`–`SR-TC-0262`<br>`SR-TC-0458`–`SR-TC-0462`<br>`SR-TC-0511` | SR-E2E-0016 |
| SR-SCN-0017 | `SR-TC-0263`–`SR-TC-0274`<br>`SR-TC-0481`<br>`SR-TC-0512`–`SR-TC-0513` | SR-E2E-0017 |
| SR-SCN-0018 | `SR-TC-0275`–`SR-TC-0285`<br>`SR-TC-0415`–`SR-TC-0418`<br>`SR-TC-0514`–`SR-TC-0516` | SR-E2E-0018 |
| SR-SCN-0019 | `SR-TC-0299`–`SR-TC-0312`<br>`SR-TC-0467`–`SR-TC-0472`<br>`SR-TC-0524`–`SR-TC-0531` | SR-E2E-0019 |
| SR-SCN-0020 | `SR-TC-0313`–`SR-TC-0332`<br>`SR-TC-0453`–`SR-TC-0457`<br>`SR-TC-0486`<br>`SR-TC-0532` | SR-E2E-0020 |
| SR-SCN-0021 | `SR-TC-0333`–`SR-TC-0341`<br>`SR-TC-0444`–`SR-TC-0452`<br>`SR-TC-0533`–`SR-TC-0535` | SR-E2E-0021 |
| SR-SCN-0022 | `SR-TC-0342`–`SR-TC-0348`<br>`SR-TC-0495`<br>`SR-TC-0536`–`SR-TC-0537` | SR-E2E-0022 |
| SR-SCN-0023 | `SR-TC-0349`–`SR-TC-0360`<br>`SR-TC-0473`–`SR-TC-0476`<br>`SR-TC-0538`–`SR-TC-0540` | SR-E2E-0023 |
| SR-SCN-0024 | `SR-TC-0361`–`SR-TC-0375`<br>`SR-TC-0435`–`SR-TC-0443`<br>`SR-TC-0541`–`SR-TC-0542` | SR-E2E-0024 |
| SR-SCN-0025 | `SR-TC-0376`–`SR-TC-0394`<br>`SR-TC-0476`–`SR-TC-0490`<br>`SR-TC-0543`–`SR-TC-0545` | SR-E2E-0025 |
| SR-SCN-0026 | `SR-TC-0395`–`SR-TC-0414`<br>`SR-TC-0444`–`SR-TC-0452`<br>`SR-TC-0546`–`SR-TC-0548` | SR-E2E-0026 |
| SR-SCN-0027 | `SR-TC-0549`–`SR-TC-0557`<br>`SR-TC-0562`<br>`SR-TC-0564`<br>`SR-TC-0570` | SR-E2E-0027 |
| SR-SCN-0028 | `SR-TC-0487`–`SR-TC-0490`<br>`SR-TC-0561`–`SR-TC-0563`<br>`SR-TC-0568`<br>`SR-TC-0571`<br>`SR-TC-0599` | SR-E2E-0028 |
| SR-SCN-0029 | `SR-TC-0558`–`SR-TC-0561`<br>`SR-TC-0569`<br>`SR-TC-0572`<br>`SR-TC-0592`–`SR-TC-0593`<br>`SR-TC-0598` | SR-E2E-0029 |
| SR-SCN-0030 | `SR-TC-0573`–`SR-TC-0580`<br>`SR-TC-0583`–`SR-TC-0587`<br>`SR-TC-0592`–`SR-TC-0593`<br>`SR-TC-0596`<br>`SR-TC-0598` | SR-E2E-0030 |
| SR-SCN-0031 | `SR-TC-0582`<br>`SR-TC-0587`–`SR-TC-0591`<br>`SR-TC-0596`–`SR-TC-0597`<br>`SR-TC-0599` | SR-E2E-0031 |
| SR-SCN-0032 | `SR-TC-0552`<br>`SR-TC-0560`<br>`SR-TC-0565`–`SR-TC-0567`<br>`SR-TC-0570`–`SR-TC-0571`<br>`SR-TC-0581`<br>`SR-TC-0594`–`SR-TC-0595`<br>`SR-TC-0597`<br>`SR-TC-0600` | SR-E2E-0032 |
| SR-SCN-0033 | `SR-TC-0601`, `SR-TC-0602`, `SR-TC-0603`, `SR-TC-0604`, `SR-TC-0605`, `SR-TC-0606`, `SR-TC-0607`, `SR-TC-0608`, `SR-TC-0609`, `SR-TC-0610`, `SR-TC-0611`, `SR-TC-0612`, `SR-TC-0613`, `SR-TC-0614`, `SR-TC-0619`, `SR-TC-0622`, `SR-TC-0623`, `SR-TC-0631`, `SR-TC-0633`, `SR-TC-0636` | SR-E2E-0033 |
| SR-SCN-0034 | `SR-TC-0608`, `SR-TC-0609`, `SR-TC-0610`, `SR-TC-0624`, `SR-TC-0625`, `SR-TC-0626`, `SR-TC-0627`, `SR-TC-0628`, `SR-TC-0629`, `SR-TC-0630`, `SR-TC-0631`, `SR-TC-0632` | SR-E2E-0034 |
| SR-SCN-0035 | `SR-TC-0609`, `SR-TC-0615`, `SR-TC-0624`, `SR-TC-0625`, `SR-TC-0626`, `SR-TC-0627`, `SR-TC-0632`, `SR-TC-0635`, `SR-TC-0647` | SR-E2E-0035 |
| SR-SCN-0036 | `SR-TC-0611`, `SR-TC-0616`, `SR-TC-0617`, `SR-TC-0618`, `SR-TC-0620`, `SR-TC-0621`, `SR-TC-0638` | SR-E2E-0036 |
| SR-SCN-0037 | `SR-TC-0639`, `SR-TC-0640`, `SR-TC-0641`, `SR-TC-0642`, `SR-TC-0650` | SR-E2E-0037 |
| SR-SCN-0038 | `SR-TC-0637`, `SR-TC-0638`, `SR-TC-0643`, `SR-TC-0644`, `SR-TC-0645`, `SR-TC-0646`, `SR-TC-0647`, `SR-TC-0648`, `SR-TC-0649`, `SR-TC-0650` | SR-E2E-0038 |
| SR-SCN-0039 | `SR-TC-0651`–`SR-TC-0674` | SR-E2E-0039 |
| SR-SCN-0040 | `SR-TC-0658`–`SR-TC-0669` | SR-E2E-0040 |
| SR-SCN-0041 | `SR-TC-0698`–`SR-TC-0714` | SR-E2E-0041 |
| SR-SCN-0042 | `SR-TC-0706`–`SR-TC-0713` | SR-E2E-0042 |
| SR-SCN-0043 | `SR-TC-0675`–`SR-TC-0697` | SR-E2E-0043 |
| SR-SCN-0044 | `SR-TC-0700`–`SR-TC-0705` | SR-E2E-0044 |
| SR-SCN-0045 | `SR-TC-0715`–`SR-TC-0722` | SR-E2E-0045 |
| SR-SCN-0046 | `SR-TC-0723`–`SR-TC-0730` | SR-E2E-0046 |

### 15.7 Requirement-Testfall-Katalog

Der primäre Testfall zu `SR-REQ-NNNN` heißt `SR-TC-NNNN`. Im Implementierungsrepository liegt sein versioniertes Manifest unter `verification/requirements/SR-TC-NNNN.json`. Es enthält mindestens:

- `test_case_format_version`;
- `test_case_id`, `requirement_id` und erwartete Requirement-Revision beziehungsweise Spezifikationsdokumenthash;
- `primary_verification_id`;
- Methode, Fixture-IDs, Vorbedingungen, Schritte und Oracle;
- erwartete Diagnosen, Exit Codes und relevante JSON-Pointer;
- erforderliche Umgebung und Ressourcen;
- erzeugte Evidence-Art und Bindung an Plattform-/Konfigurationshash soweit anwendbar.

Ein Testfall gilt nur dann als bestanden, wenn seine aktuelle Evidence exakt Manifesthash, Requirement-ID, Spezifikationshash und Tool-Build bindet. Die 742 Zuordnungen in dieser Dokumentversion definieren Soll-Testfälle; sie sind kein Bericht über bereits ausgeführte Produkttests. Für SR-TC-0549 bis SR-TC-0650 gelten zusätzlich Kapitel 14.6–14.8 und Anhang N bis R.

---

## 16. Validation und Verification

SpecRoad verwendet die Begriffe getrennt:

| Begriff | Frage | Primäre Artefakte und Zustände |
|---|---|---|
| Requirements Validation | Ist die Anforderung fachlich richtig, verständlich, notwendig und freigabefähig? | Requirement-Reifegrad, menschliche Reviews, Herkunft, Qualitätsregeln und aktuelle Relationsreviews |
| Product Verification | Erfüllt das entwickelte oder untersuchte System die freigegebene Anforderung? | Verification Contract, Test, Evidence, Coverage und berechnetes Verification Result |
| Tool Validation | Arbeitet SpecRoad selbst gemäß dieser Produktspezifikation? | `SR-VER-*`, Referenzfixtures und Release-Evidence |

Ein `approved` Requirement kann unverifiziert sein. Ein technisch bestandener Test kann kein fachlich nicht freigegebenes Requirement freigeben. Requirements Validation und Product Verification dürfen deshalb nicht auf ein gemeinsames Statusfeld reduziert werden.

---

## 17. Release-Abnahmekriterien

Das Zielrelease `SpecRoad Single-Repository Workbench 0.2.0` gilt als abnahmefähig, wenn alle folgenden Bedingungen erfüllt sind:

1. Alle unbedingten Anforderungen `SR-REQ-0001` bis `SR-REQ-0742` besitzen den Umsetzungsstatus `implemented` und aktuelle bestandene Evidence für ihren primären Testfall.
2. Die Verifikationen `SR-VER-0001` bis `SR-VER-0050` bestehen; ein `waived`-Ergebnis erfüllt die Release-Abnahme nicht.
3. Die Szenarien `SR-SCN-0001` bis `SR-SCN-0046` führen mindestens ihren exakten Umfang aus Kapitel 15.6 aus und erzeugen aktuelle `SR-E2E-*`-Evidence.
4. `specroad validate --strict --format json` liefert für Vollprojekt, Referenzkonfigurationen und zulässige partielle Fixtures Exit Code 0.
5. Scope Descriptor, Closure, Relationsmatrix und Profilkomposition bestehen alle normativen Testvektoren.
6. Zwei identische Render-, View-, Diagramm-, Export- und Bundle-Läufe erzeugen byte-identische Ausgaben.
7. Crash-Injection an jeder dauerhaften Transaktionsgrenze stellt nach Recovery exakt die Basis- oder vollständige Zielmodellwurzel her.
8. Eine korrupte Transaktion blockiert normale Nutzung und kann ausschließlich aus verifizierter Quelle auditiert restored werden.
9. Ein reales 0.1-Referenzprojekt kann nach Sicherungsbundle verlustfrei auf 0.2 migriert und anschließend verifiziert werden.
10. Ein stale Proposal, ein AI-Direktschreibversuch, ein Proposal ohne menschliche Freigabe und ein fehlerhaftes Proposal werden ohne normative Änderung abgewiesen.
11. Proposal-Authoring und gespeicherte Change Plans erzeugen unabhängig vom Apply-Zeitpunkt dieselbe erwartete Zielwurzel.
12. Ein Dreiwege-Merge führt unabhängige Änderungen zusammen, weist alle definierten Konflikte aus und veröffentlicht nur einen vollständig gelösten validen Plan.
13. ReqIF/ReqIFZ-, CSV- und NDJSON-Roundtriptests erhalten alle Inhalte des jeweiligen Schnittmengenprofils einschließlich externer Relationsidentitäten und melden jeden Verlust.
14. `update_if_unchanged` besteht alle fünf Fälle des Dreifachvergleichs.
15. JUnit-, SARIF- und Generic-Evidence-Importe erzeugen korrekte Provenienz, ohne Subjects oder Planning Status zu verändern.
16. Verification Plan Status und Verification Result werden in allen Referenzkonfigurationen getrennt und korrekt behandelt.
17. Aktuelle, relokalisierte, stale, mehrdeutige und fehlende Code-Referenzen sowie current, unreviewed, suspect und invalid Relations werden korrekt klassifiziert.
18. Vollständige und partielle Bundles erfüllen Schreibbarkeits-, Boundary-, Receipt- und kanonische ZIP-Verträge.
19. Beide portablen **Core**-Distributionen bestehen den Sandbox-Roundtrip unter CPython 3.10 bis 3.14 ohne Drittanbieterpakete; die ergänzende Analyzer-Matrix wird separat nach Anhang T abgenommen.
20. Idempotente Wiederholung eines schreibenden Requests erzeugt lokal und nach vollständigem Projektbundle-Transfer keine Doppeländerung.
21. Konfigurationsumfänge, Abhängigkeiten, Coverage und Baselines bestehen für alle Referenzvarianten.
22. Die Performance- und Speichergrenzen aus `SR-REQ-0210` bis `SR-REQ-0213` werden mit gebundener `benchmark-platform.json` eingehalten.
23. Es existieren keine offenen Fehlerdiagnosen, ungültigen Referenzen, Profilkonflikte, unaufgelösten Merge-/Importkonflikte, korrupten Transaktionen, doppelten IDs oder offenen normativen Platzhalter in der Release-Baseline.
24. Traceability Requirements → Need, Requirements → Verification und Requirements → Testfall beträgt jeweils 100 Prozent.
25. Die unabhängigen Aufruf-, Pfad- und Sandboxwechsel nach Anhang N bestehen ohne erforderlichen Sessionzustand; vollständiger Datenverlust wird nur bis zum extern erhaltenen Sicherungsstand behandelt.
26. Read-only-/Dry-Run-Aufrufe verändern auch bei Recoverybedarf, Checkpoints und fehlendem Cache weder Projektdateien noch `.specroad/`; externe Work-Dateien sind nach Anhang P ausdrücklich ausgewiesen.
27. Die neuen Bootstrap-, Preflight-, CPU- und RSS-Grenzen nach 14.6 bestehen für beide Distributionen und die unterstützte Python-Matrix.
28. Jedes Ressourcenprofil liefert bei vollständigem Abschluss dieselben fachlichen Ergebnisse; weiche Budgetüberschreitungen führen nach Anhang O.4 zu sparsamer Fortsetzung ohne falsches Pass und ohne freigegebenen Mischzustand.
29. `environment check` und ausdrücklich angeforderte Messwerte erfüllen ihre Unknown-, Datenschutz-, Seiteneffekt- und Nicht-Determinismusverträge.

---

30. Ein vollständig gebundener Auftrag erreicht in den endlichen Testfixtures mit kleinen weichen Budgets über mehrere CLI-Aufrufe denselben fachlichen Endstand wie der Einzellauf.
31. Arbeitspakete lassen sich in einer frischen kompatiblen Runtime ohne Cache fortsetzen; fehlende oder manipulierte Checkpoints werden niemals als Fortschritt anerkannt.
32. Jedes noch offene Ergebnis besitzt einen ehrlichen Fortschrittsstand, vollständige offene Aufgaben und eine konkrete Fortsetzungsaktion; es existiert kein rein budgetbedingtes Deadlock oder automatischer unbegrenzter Retry.
33. Die kontraktübergreifenden Fälle aus Anhang R bestehen; insbesondere Merge-Metadaten, unveränderte Legacy-Bytes und vollständiger Proposal-Durchlauf.

34. Alle Mindestsprachen-/Tagfälle, Force-/Should-/Verbot-Konventionen und deterministischen Mischungsregeln aus Anhang S bestehen.
35. Der py3langid-Adapter ist tatsächlich implementiert, offline paketiert und auf dem eingefrorenen Sprachkorpus mit der echten Library abgenommen; eine bloße Schnittstelle oder ein Mock genügt nicht.
36. Der Core besteht seine Tests ohne NumPy/py3langid; ein ausdrücklich angeforderter nicht verfügbarer Detektor meldet den spezifizierten Status und Exit Code.
37. Generische Fremdberichte, abweichende Analyzerfindings, tamper-/stale-Fälle und Mehrpromptfortsetzung erhalten vollständige Coverage und ändern keine normativen Requirements.
38. Die SRX-Zahlenpolicy besteht die expliziten Rechen- und Fehlervektoren aus Anhang U.

---

## 18. Annahmen

| ID | Annahme | Festlegung |
|---|---|---|
| SR-ASM-0001 | Dateisystem | Der Referenzbetrieb hält Projektroot, alle Managed Paths und `.specroad/` auf demselben lokalen Dateisystem, das atomare Umbenennung innerhalb eines Verzeichnisses und dauerhaftes `fsync` unterstützt. |
| SR-ASM-0002 | Git | Git ist nur für Git-spezifische Vergleiche und Merge-Eingaben erforderlich; alle anderen Core-Funktionen arbeiten ohne `.git`. |
| SR-ASM-0003 | Zeit | Normative Zeitstempel werden in UTC bereitgestellt; lokale Zeitzone beeinflusst keine Semantik. |
| SR-ASM-0004 | Projektgröße | 10.000 Artefakte, 50.000 Beziehungen und 100 MiB normative Daten bilden den verbindlichen Benchmarkbereich, keine automatische Ablehnungsgrenze; größere zulässige Aufträge werden sparsam und fortsetzbar versucht. |
| SR-ASM-0005 | Single-User | Es gibt keinen koordinierten Mehrbenutzerschreibzugriff auf denselben Projektroot; parallele Branches und Kopien werden später semantisch gemerged. |
| SR-ASM-0006 | Bedrohungsmodell | Eingabedateien, Archive und XML können bösartig sein; ein lokaler Administrator mit Schreibzugriff auf Prozess und Projekt liegt außerhalb der Schutzgrenze. |
| SR-ASM-0007 | Zufallsquelle | Das Betriebssystem stellt der Python-Standardbibliothek eine kryptografisch geeignete Entropiequelle bereit. |
| SR-ASM-0008 | Akteursdeklaration | Single-User-SpecRoad authentifiziert Akteurtypen nicht kryptografisch; `actor_type` ist Audit- und Policyinformation des aufrufenden Workflows. |
| SR-ASM-0009 | Erhaltung kritischer Dateien | Crash-Recovery setzt erhaltene, integre Transaktionsdaten voraus; vollständiger Dateiverlust kann nur durch extern erhaltene Projektstände überbrückt werden. |
| SR-ASM-0010 | Beobachtbarkeit von Ressourcen | Hostquoten, RSS und freie Ressourcen sind nicht überall verlässlich ermittelbar; der Core kennzeichnet Unbekanntes und arbeitet ohne solche APIs mit begrenzter eigener Verarbeitung. |

---

Für einen vollständigen Abschluss über mehrere Aufrufe sind ein endlicher zulässiger Auftrag, erhaltene Eingangsdaten/Checkpoints, ausreichend realer Datenträgerplatz für Ergebnis und Sicherung, ein ausführbarer kleinster Arbeitsschritt sowie weitere Aufrufe durch Nutzer oder Runner erforderlich. Unbekannte Hostgrenzen sind keine bewiesene Unausführbarkeit. SpecRoad startet keine Chatnachrichten autonom und kann vollständig verlorene, nie extern gesicherte Daten nicht rekonstruieren.

---

## 19. Risiken und Gegenmaßnahmen

| ID | Risiko | Auswirkung | Gegenmaßnahme |
|---|---|---|---|
| SR-RISK-0001 | Modell- und CLI-Komplexität | Zu viele Pflichtfelder oder Befehle könnten Nutzer zu freier Dateibearbeitung treiben. | Draft-Minima, `command describe`, Dry-Runs, verständliche Diagnosen und Aliase. |
| SR-RISK-0002 | Falsch-positive Qualitätsdiagnosen | Heuristische Regeln können korrekte Aussagen beanstanden. | Deterministische Regelcodes, Profil-Schweregrade, begründete Waiver; keine KI als Pass/Fail-Instanz. |
| SR-RISK-0003 | Doppelte Source of Truth | Gerenderte Dokumente könnten manuell gepflegt werden. | Generierungsbanner, getrennter Ausgabeordner und keine Rückübernahme. |
| SR-RISK-0004 | KI-Halluzinationen | Plausible, aber unbelegte Inhalte könnten vorgeschlagen werden. | Proposal-Basis, Quellenpflicht, Check, menschliche Freigabe und Evidence-Gates. |
| SR-RISK-0005 | Veraltete Beziehungen und Nachweise | Änderungen können bisher gültige Traces oder Evidence entwerten. | Endpunkthashes, suspect Relations, stale Evidence und Readiness-Gates. |
| SR-RISK-0006 | Transaktionskorruption | Stromausfall oder manuelle Eingriffe können Journaldaten beschädigen. | Before Images, Hashes, fsync, Crash-Injection und sichere Verweigerung bei `corrupt`. |
| SR-RISK-0007 | Migrationsverlust | Schemawechsel können unbekannte oder nicht abbildbare Informationen verlieren. | Pre-Bundle, Plan, Verlust-IDs, explizites `--accept-loss` und Verify. |
| SR-RISK-0008 | Austauschformatverlust | ReqIF oder CSV können nicht alle SpecRoad-Inhalte darstellen. | Schnittmengenprofil, External Identity, namespaced Extensions und Verlustbericht. |
| SR-RISK-0009 | Bösartige XML-/ZIP-Eingaben | Archive oder XML können Ressourcen erschöpfen oder Pfadgrenzen verletzen. | DTD-/Entity-Verbot, Ressourcenlimits, ZIP_STORED-Prüfung und Traversal-Schutz. |
| SR-RISK-0010 | Merge-Fehlentscheidung | Automatisches Mergen könnte fachlich konkurrierende Änderungen übersehen. | Konservative Feldregeln, Konfliktklassen, Validation, Impact und explizite Auflösungen. |
| SR-RISK-0011 | ID-Fehler trotz Zufall | Implementierungsfehler oder defekte Zufallsquelle könnten Kollisionen erzeugen. | CSPRNG, 128 Bit, Kollisionsprüfung, Property- und Paralleltests. |
| SR-RISK-0012 | Python-3.10-Lebenszyklus | Die Mindestversion erhält nach ihrem Upstream-Lebenszyklus keine regulären Sicherheitsupdates mehr. | Offline-Kern, Release-Matrix bis zur neuesten unterstützten Version und spätere ausdrückliche Mindestversionsentscheidung. |
| SR-RISK-0013 | Dependency-freie Implementierungslast | JSON Schema, ReqIF, XML-Härtung und SARIF ohne externe Runtimepakete erhöhen Wartungsaufwand. | Begrenzte Profile, normative Testkorpora, kleine interne Module und klare Formatgrenzen. |
| SR-RISK-0014 | Variantenexplosion | Viele Konfigurationen können Coverage und Readiness unübersichtlich machen. | Benannte Dimensionen, SRX-Limits, explizite Konfigurationsbindung und keine Artefaktkopien. |
| SR-RISK-0015 | Vollständiger Sandboxverlust | Änderungen seit der letzten extern erhaltenen Sicherung können verloren gehen. | Verifizierte Vollbundles nach abgeschlossenen Arbeitsschritten extern sichern; kein automatisches Backupversprechen. |
| SR-RISK-0016 | Versteckte Quoten oder harter Abbruch | Der Host kann den Prozess vor einer kontrollierten Diagnose beenden. | Konservative Budgets, begrenzte Arbeit, Journal vor Veröffentlichung und Behandlung unbestätigter Ergebnisse durch den Agenten. |
| SR-RISK-0017 | Zu teurer Preflight | Ein Startcheck kann mehr kosten als der eigentliche kleine Befehl. | Befehlsspezifische Metadatenprüfung, kein Vollscan und eigene Start-/Preflight-Benchmarks. |
| SR-RISK-0018 | Falsche Cachegültigkeit | Zeitstempel- oder Pfadannahmen könnten veraltete Ergebnisse liefern. | Inhaltshash-/Abhängigkeitsnachweis, entbehrliche Caches und Paritätstests ohne Cache. |

---

## 20. Konsolidierung und Nachweisstatus

Rückblick auf die weiterhin übernommenen Korrekturen: v0.2.5 übernahm den gesamten Funktionsumfang der v0.2.4 und präzisierte ausschließlich die fünf Prüfpunkte B01, B02, B03, H01 und H02. Sie ersetzt die betroffenen Altverträge im Haupttext, in den Requirements und in den Anhängen; sie ist kein zusätzliches Änderungsblatt. Die vier Korrekturen der v0.2.4 bleiben erhalten. Frühere pauschale Schließungsbehauptungen werden nicht als Implementierungsbeweis fortgeschrieben.

### 20.1 Befunde aus der Implementierungsreifeprüfung v0.2.2

| Befund | Konsolidierte Festlegung | Zugehöriger Gegenbeispieltest | Nachweisstatus |
|---|---|---|---|
| Relations-ID und Migrationsausnahme | Reguläre Zufalls-ID versus eng begrenzte deterministische Migration; keine Änderung unveränderbarer Originalrelationen. | R-01; Anhang Q | normativ korrigiert; Produkttest ausstehend |
| Merge- und Change-Plan-Metadaten | Explizite Policywahl; Planner und Apply verwenden denselben Algorithmus. | R-02, R-03; Anhang K | normativ korrigiert; Produkttest ausstehend |
| `unreviewed` versus `suspect` | Noch nie geprüft versus früher geprüft und inzwischen verändert; neuestes passendes Review entscheidet. | R-04, R-05; Anhang J | normativ korrigiert; Produkttest ausstehend |
| Proposal-Einfügeposition | Ohne Position anhängen; mit Index exakt einfügen. | R-06; Kapitel 11.10 | normativ korrigiert; Produkttest ausstehend |
| Migration unveränderbarer Nachweise | Originalbytes erhalten; Manifest, eingebauter Legacy-Leser und getrennte Hashdomäne. | R-07, R-08; Anhang Q | normativ ergänzt; Produkttest ausstehend |
| Fehlender durchgängiger Proposal-Lifecycle | Read-only Checks; atomarer Reviewstart; Inhaltsfreigabe unabhängig von Kontrollrevision. | R-09; Kapitel 10.3 und 11.10 | normativ ergänzt; Produkttest ausstehend |
| Pauschale Schreibverträge | Journale/Projektwriter-Locks nur nach exakter Befehlsklasse; externe Work-Daten explizit getrennt. | R-10; Kapitel 11.7 | normativ korrigiert; Produkttest ausstehend |
| Veralteter Konfigurationsverweis | SR-REQ-0146 verweist auf Scope-, Modellwurzel- und Profilvertrag 10.8–10.10. | Referenzprüfung | redaktionell korrigiert |

### 20.2 Neue Nutzerentscheidung zur vollständigen ressourcensparsamen Arbeit

| Festlegung | Maßgebliche Stellen | Nachweisstatus |
|---|---|---|
| Weiche Ziele statt automatischem Budgetfehler | Kapitel 12.40–12.41; Anhang O | spezifiziert; Laufzeitnachweis ausstehend |
| Vollständiger Restauftrag und monotone Checkpoints | Kapitel 10.20 und 11.12; Anhang P | spezifiziert; Mehrschritttests ausstehend |
| Mehrere Prompts ohne eingebauten Chatbot | Anhang P.8 | spezifiziert; Agenten-Roundtrip ausstehend |
| Gleiche Freigaben und Atomarität in jedem Schritt | Kapitel 11.10; Anhang P.6 | spezifiziert; Missbrauchs-/Crash-Tests ausstehend |
| Neue fachliche Quelle | Dokumentkopf und Kapitel 2.1 | durch ausdrücklichen Nutzerauftrag festgelegt |

Diese Fassung erhebt keinen Anspruch auf einen erschöpfenden mathematischen Widerspruchsfreiheitsbeweis. Die Begleitprüfung dokumentiert tatsächlich ausgeführte Struktur-/Referenzprüfungen und ausgewählte konstruktive Vertragsorakel. Ein vollständiges Software-Release erfordert weiterhin die spezifizierten Implementierungs- und Evidence-Nachweise.

---

### 20.3 Korrekturen der Prüfung v0.2.3

| Befund | Verbindliche Korrektur | Abschlussorakel | Nachweisstatus |
|---|---|---|---|
| IR-023-01 Scope und Proposal-Hashbasis | Permanente Kontrollausschlüsse mit ausdrücklicher Verweigerung unzulässiger Referenzclosure; genau eine geschlossene unkonfigurierte Proposal-Basis. | R-23, R-24; 10.8.1 | normativ korrigiert; Produktnachweis ausstehend |
| IR-023-02 Evidence-Auswahl | Eigenständiger Produktstand und Pflichtmenge; alle maßgeblichen Läufe; menschlich gebundene Retest-Ablösung ohne Veränderung historischer Evidence. | R-25 bis R-28, R-31, R-32; 10.5 | normativ vervollständigt; Produktnachweis ausstehend |
| IR-023-03 Selbstbeschreibung | Exakte Fachprojektion gegenüber verpflichtenden aufrufaktuellen Betriebsfeldern. | R-29; 11.5.1 | normativ korrigiert; Produktnachweis ausstehend |
| IR-023-04 Query-Ausnahme | Abgeschlossene Liste von Wertfilterarten; wiederholte SRX-Ausdrücke ausdrücklich ausschließlich UND. | R-30; 11.6 | normativ präzisiert; Produktnachweis ausstehend |

Der damalige Bestand von 650 Requirement-IDs, 38 Szenarien, 43 Verifikationsverträgen und 28 Artefakttypen bleibt erhalten; der aktuelle Gesamtumfang einschließlich der Erweiterung v0.2.6 steht in Kapitel 15.5. Neue Pflichtfelder und Unteralgorithmen präzisieren bestehende Verträge; es wird weder ein Mehrbenutzersystem noch ein neuer Ausführungsdienst hinzugefügt. Die operative Wirksamkeit von Evidence-Auswahl und deterministischer Selbstbeschreibung ist in die bestehenden Import-, CLI-, Work-, Baseline- und Testverträge eingebunden. Die Begleitprüfung unterscheidet ausgeführte Dokument-/Orakeltests von noch ausstehenden Produktnachweisen und einer gesonderten menschlichen Baseline-Freigabe.

### 20.4 Konsolidierungsstand v0.2.5

Die Prüfpunkte B01, B02, B03, H01 und H02 sind durch die normativen Verträge 9.6.3, 10.7.1, 11.13 und Anhang E/J in dieser Fassung fachlich entschieden. Die zugehörigen Abnahmekriterien sind in 14.10 und R-33 bis R-47 dokumentiert. Dies bedeutet „Vertrag präzisiert“, nicht „Implementierung getestet“ oder „alle möglichen Kombinationen fehlerfrei bewiesen“. Die früheren Ressourcen-, Fortsetzungs- und Proposal-Regeln bleiben bindend. Eine erneute Gesamtfreigabeentscheidung ist getrennt zu dokumentieren.

---

### 20.5 Erweiterungsstand v0.2.6

Mehrsprachigkeit, explizite Verbindlichkeit und das generische Analyzer-Datenmodell sind nach den neuen Nutzerentscheidungen Bestandteil dieses ersten Zielreleases. Der py3langid-Adapter wird nicht in die Roadmap verschoben. Tiefes Textverständnis und das Starten beliebiger fremder Analyzer bleiben außerhalb des Releaseumfangs. Die bisher lokale SRX-Präzisionsauflage ist durch Anhang U als expliziter Entwurfsvertrag beantwortet. Diese Festlegungen erweitern den zu prüfenden Umfang und sind keine bloße Wiederholung der früheren bedingten Implementierungsfreigabe. Dokumentprüfungen und spätere echte Produkt-/Korpus-/Ressourcenabnahmen bleiben getrennt.


### 20.6 Korrekturstand v0.2.7

B01 (automatische Analyzer-Fortsetzung) wird durch den einheitlichen Vertrag in T.5/T.9/P.2 geschlossen. A02 (Analysekennung versus Schreib-Idempotenz) wird durch den eigenständigen Typ und Vergabevertrag in T.3, die CLI-Option `--analysis-id`, die Pair-Bindung in T.5 und die Beschränkung der Write-Receipts entschieden. Bestehende Requirement-IDs und Zielrelease bleiben unverändert. 14.12 und R-64 bis R-75 definieren die dazugehörigen Regressionen. „Geschlossen“ bezeichnet hier die ausdrücklich getroffene Vertragsentscheidung, nicht einen bereits ausgeführten Produktnachweis. Die technische Reviewentscheidung wird gesondert an die veröffentlichte PDF gebunden dokumentiert.

### 20.7 Nutzerbeauftragte Transporterweiterung v0.2.8

Die neue Sektion 12.46 und Anhang W konkretisieren den vorhandenen Sandbox-
Rundweg auf Basis der öffentlichen PatchHarbor-Python-API. Neu sind die
Anforderungen 0731–0742, SR-VER-0051 und SR-DEC-0053; bestehende IDs bleiben
erhalten. Die Portabilitätsverträge 0224/0225 unterscheiden mitgelieferte
Transportkomponenten und ausdrücklich lokale Git-Funktionen. Alle neuen
Testfallmanifeste bleiben `open`; aktuelle Katalogbindungen ersetzen keine
historische Evidence und erklären keine neue Produktfunktion als fertig.

### 20.8 Waiver-Präzisierung v0.2.9

Die Nutzerentscheidung vom 19. Oktober 2026 löst die fachliche Blockade vor
12.b.W durch den Vertrag 10.5.5: selbstreferenzfreier Inhaltshash, exakte Scope-/
Konfigurationsbindung, UTC-Frist und expliziter Bewertungszeitpunkt. Historische
Waiver bleiben lesbar, ohne automatische Ausnahmegewährung. Diese Präzisierung
ändert weder Requirement-IDs noch den Umfang des portablen PatchHarbor-Rundwegs.

### 20.9 Readiness-Präzisierung v0.2.10

Der nutzerbeauftragte OFF-PLAN-Schritt vor 13.f.W schließt die bisher offene
Bedeutung von Readiness-Policy, Risiko-Blockern und Issue-Erledigung durch
10.5.6. Pflichtgates sind fest, menschliche Entscheidungen explizit gebunden
und Altwerte ohne automatische Freigabe lesbar. Die Verifikationsprioritäten,
der Waiver-Vertrag und der Release-Scope bleiben erhalten. Die Umsetzung
erfolgt anschließend in 13.f.W/R/C und die gespeicherte Bewertungs-/Baseline-
Integration in 13.g.W/R/C. Diese Dokumentänderung implementiert kein Gate und
erhöht keinen abgeschlossenen Produktzähler. Aktuelle Katalog-Hashbindungen
sind keine neue Test-Evidence; historische Nachweise bleiben historisch.

### 20.10 Delegierte Spezifikationsklärung v0.2.11

Der ausdrückliche Nutzerauftrag vom 22. Oktober 2026 erteilt die begrenzte
Entwicklungsbefugnis `SPECROAD-DECISION-1` nach 2.4. Geeignete Detaillücken
werden begründet, normativ dokumentiert und innerhalb des bestehenden
Umfangs weiterbearbeitet. Echte Human-Reviews, fachliche Risikoakzeptanzen,
Sicherheits- und Kompatibilitätszusagen bleiben außerhalb dieser Befugnis.
Control-Bundle 014 liefert den gesonderten versionierten Übergabevertrag;
dieses Dokument ändert keine laufenden Jobs oder alten Antwortbelege.
Der Produktstand bleibt 561/900 mit offenem 13.f.W. Eine erfolgreiche
Dokumentübergabe ist weder Produktimplementierung noch End-to-End-Nachweis
eines künftig auftretenden Klärungsfalls.

### 20.11 Capability-/Task-Kontextpräzisierung v0.2.12

`READINESS-SUBJECT-CONTEXT`, delegiert gemäß `SPECROAD-DECISION-1`, ergänzt
in Anhang L die bisher fehlende genaue Inhaltsprojektion für Capabilities
und Tasks. Beide sind bereits Pflichtsubjects der Verification und der
Readiness nach 10.5.6; ihr Hash erhält keinen Ersatz durch Statuslabels oder
den vollständigen Audit-Hash. Die bestehende v1-Projektion der drei bisher
unterstützten Subjecttypen bleibt bytegleich. Gespeicherte Evidence wird
nicht umgeschrieben oder pauschal als aktuell erklärt. Umsetzung und
Verhaltensnachweise folgen im offenen 13.f.W/R/C; diese Dokumentübergabe
erhöht den Produktstand 561/900 nicht und verändert keinen Control-Zustand.

### 20.12 Austauschmapping-Präzisierung v0.2.13

`EXCHANGE-MAPPING-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, legt
die zuvor fehlenden Mapping-/Registrydetails in 10.12.1 fest. Beide sind
versionierte passive Ressourcen; ihre gebundene reine Auswertung ist von
Formatparsern und Projektwrites getrennt. Bestandsmappings, historische
Evidence und native Sicherheits-/Freigabegates bleiben erhalten. Umsetzung
und Verhaltensnachweise folgen im offenen 14.a.W/R/C; der Produktstand
570/900 bleibt bei dieser Dokumentübergabe unverändert. Die neue aktive
Katalogbindung bestätigt keine ausgeführten Produkttests. Control- und
Laufzeitkonfigurationen werden nicht verändert.

### 20.13 Importstrategie-Präzisierung v0.2.14

`IMPORT-CONFLICT-POLICY`, delegiert gemäß `SPECROAD-DECISION-1`, schließt
in 10.12.2 die Detailfrage der Strategie `create_new_revision` und ihrer
Grenzen gegenüber lokalem Verlust und divergentem Importkonflikt. Die
kleinste konsistente Regel verwendet dieselbe native Identität, die bestehende
Fünf-Fälle-Tabelle und K.2. Keine Force-Variante, zusätzliche Archivierung
oder automatische Historienmigration wird eingeführt. Umsetzung und
Verhaltensnachweise bleiben in 14.c.W/R/C offen; Produktstand 576/900 und
Control-Zustände werden durch die Dokumentübergabe nicht verändert.

### 20.14 CSV-Profilpräzisierung v0.2.15

`CSV-PROFILE-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, konkretisiert
in D.2.1 die bislang offene CSV-Typ-/Listen-/Null-/Fehlergrammatik. Ein
eigenes, exakt gebundenes passives Profil verwendet die bestehenden
Austauschmappingtabellen und die vorhandene typisierte JSON-Zellhülle.
Bestehende Mapping-/Registry- und Viewverträge werden nicht umgedeutet;
Rohbytes und historische Evidence bleiben erhalten. Umsetzung und
Verhaltensnachweise bleiben in 14.f.W/R/C offen. Produktstand 585/900 und
Control-/Laufzeitzustände ändern sich durch die Dokumentübergabe nicht.

### 20.15 NDJSON-Objektpräzisierung v0.2.16

`NDJSON-OBJECT-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, konkretisiert
in D.3.1 die bislang offene Zeilenhülle und das Verhältnis ihrer Version zu
nativen Artefakten und regulären Change Plans. Die Dreifeldhülle erhält
native Payloads und deren Hashverträge. Framing, tatsächlicher Stromabschluss,
passive Validierung und Fehlersignale sind explizit; kein Präfix ist ein
Gesamterfolg. Bestehende Daten, Evidence, Mapping-/Freigabe-/Writergrenzen
bleiben erhalten. Die aktive Dokumentfassung wird auch in 2.1 konsistent
benannt, ohne Änderung der Rangfolge. Umsetzung und Verhaltensnachweise
bleiben in 14.g.W/R/C offen; Produktstand 588/900 und Control-/Laufzeitzustände
ändern sich durch diese normative Übergabe nicht.

### 20.16 ReqIF-Objektpräzisierung v0.2.17

`REQIF-OBJECT-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, konkretisiert
in D.1.1 die bisher offene Grenze zwischen ReqIF-Typ-/Objektmodell und
den vorhandenen JSON-Mappingtabellen. Kennungsbasierte Selektoren,
unterscheidbare Default-Herkunft und verlustbewusste Wertprojektionen
vermeiden Namensinferenz, implizite Typkonvertierung und stilles Runden.
Die vollständigen weiteren Austauschpflichten bleiben erhalten. Es
entstehen weder ein neues natives Schema noch eine Freigabe oder ein
Interoperabilitätsnachweis. Umsetzung und Verhaltensevidence bleiben in
14.h.W/R/C offen; Produktstand 591/900 und Control-/Laufzeitzustände ändern
sich durch diese normative Übergabe nicht.

### 20.17 ReqIF-Struktur-/XHTML-Präzisierung v0.2.18

`REQIF-STRUCTURE-XHTML`, delegiert gemäß `SPECROAD-DECISION-1`, konkretisiert
in D.1.2 die bisher unbestimmte XHTML-Kernmenge und deren sichere native
Projektion. Geordnete Hierarchievorkommen bleiben von fachlichen Objekten
getrennt; Relationsrichtung, Identitäten und explizite Anhangbindungen
bleiben erhalten. Es entstehen weder ein neues natives Schema noch eine
Schreib-/Verlustfreigabe oder ein Fremdtool-Konformitätsnachweis. Umsetzung
und Verhaltensevidence bleiben in 14.i.W/R/C offen; Produktstand 594/900
und Control-/Laufzeitzustände ändern sich durch diese normative Übergabe
nicht. Die vollständigen weiteren Austauschpflichten bleiben verbindlich.

### 20.18 ReqIF-Erhaltungs-/Verlustpräzisierung v0.2.19

`REQIF-PRESERVATION-LOSS`, delegiert gemäß `SPECROAD-DECISION-1`, präzisiert
in D.1.3 den bisher fehlenden persistenten Quellträger und die Abgrenzung
zwischen Rohkopie, nativer Projektion und tatsächlich gebundenem Zielerhalt.
Ein versionierter passiver Erweiterungswert erhält originale XML-Bytes;
einzeln identifizierte Verluste und getrennte Vollständigkeitsangaben
verhindern pauschale Erfolge. Sicherheits-, Mapping-, Import- und Writegates
bleiben erhalten. Umsetzung und Verhaltensevidence folgen in 14.j.W/R/C;
Produktstand 597/900 und Control-/Laufzeitzustände bleiben bei dieser
Dokumentübergabe unverändert. Die neue Katalogbindung ist kein Produkttest.

### 20.19 ReqIFZ-Containerpräzisierung v0.2.20

`REQIFZ-CONTAINER-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, präzisiert
in D.1.4 die explizite Dokumentauswahl, dokumentrelative Anhangbindung und
das aus tatsächlichen Bytes abgeleitete Transportmanifest außerhalb des ZIP.
Alle Mitglieder bleiben erhalten; kein privates Pflichtmanifest oder zweiter
Archivcodec wird eingeführt. Die bestehenden ZIP-, XML-, Sicherheits-,
Import- und Writegrenzen bleiben wirksam. Umsetzung und Verhaltensevidence
folgen in 14.k.W/R/C; Produktstand 600/900 und Control-/Laufzeitzustände
bleiben bei dieser Dokumentübergabe unverändert. Die neue Katalogbindung
ist kein Produkttest oder Fremdtool-Nachweis.

### 20.20 Exportmanifestpräzisierung v0.2.21

`EXPORT-MANIFEST-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, präzisiert
in 10.12.3 die gemeinsame Manifestfeldmenge, vorhandene native Scope-/Mapping-
Bindungen, den aus enthaltenen Artefakten abgeleiteten Snapshotzeitpunkt,
konkrete Verluste und tatsächliche Anhang-/Ausgabebytes. Das Manifest bleibt
separat und selbstreferenzfrei; Query-/Closure-, Format-, Sicherheits- und
Freigabeverträge bleiben erhalten. Umsetzung und Verhaltensevidence folgen
in 14.l.W/R/C; Produktstand 603/900 und Control-/Laufzeitzustände bleiben bei
dieser Dokumentübergabe unverändert. Die neue Katalogbindung ist kein
Produkt-, Roundtrip-, Release- oder Fremdtool-Nachweis.

### 20.21 Bundlemanifestpräzisierung v0.2.22

`BUNDLE-MANIFEST-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, präzisiert
in E.1.1 die geschlossene Feldmenge und Version des Produktbundlemanifests,
die tatsächliche Payloadbindung, bewusste Ausschlüsse sowie die vorhandenen
Scope-/Modell- und Idempotenzgrenzen. Der gemeinsame Archivcodec und das
kanonische E.2-Profil bleiben Grundlage; bestehende Formate und historische
Originalbytes werden nicht migriert. Umsetzung und Verhaltensevidence folgen
in 15.a.W/R/C und den bestehenden nachfolgenden M15-Schritten. Produktstand
615/900 und Control-/Laufzeitzustände bleiben bei dieser Dokumentübergabe
unverändert. Die neue Katalogbindung ist kein Produkt-, Vollprojekt-,
Idempotenz-, Freigabe- oder Release-Nachweis.

### 20.22 Restoreplanpräzisierung v0.2.28

`RESTORE-PLAN-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, konkretisiert
in 10.7.2 das bereits verlangte Recovery-Fachformat aus 10.7.1: geschlossene
Hülle, tatsächliche Byteobjekte, Quell-/Bestands-/Erhaltungs-/Ziel-/Sicherungs-
bindungen und getrennte Hashdomänen. Quelle, Geschichte, Autorisierung,
Sicherungsdurabilität und vollständige Zielvalidierung bleiben Pflicht.
Die neue Dokument- und aktive Katalogbindung ist weder eine Restore-
Implementierung noch ein erfolgreicher Wiederherstellungs- oder Releasebeleg.
Produktstand 642/900 und der offene Schritt 15.j.W bleiben unverändert;
15.k/15.l werden nicht vorgezogen. Historische Nachweise bleiben unverändert.

### 20.23 Restore-Ausführungspräzisierung v0.2.29

`RESTORE-EXECUTION-CONTRACT`, delegiert gemäß `SPECROAD-DECISION-1`, bindet
in 10.7.3 die bereits geforderte Restore-Ausführung an unveränderte
Originalpläne, aktuelle Autorisierung, genaue eigene Betriebs-/Dateieffekte,
dauerhafte Originalbytes und überprüfte Abschlussaudits. Die bestehende
Abschluss-/Rollbackregel SR-REQ-0258/SR-REQ-0511 gilt auch bei später
veränderter Herkunft; fremde Änderungen und unbeweisbare Zustände bleiben
gesperrt. `restore-plan-v1` und alle Herkunfts-/Erhaltungs-/Reviewpflichten
bleiben unverändert. Die neue Dokument- und aktive Katalogbindung ist
kein Implementierungs-, Crash-, Wiederherstellungs- oder Releasebeleg.
Produktstand 648/900 und die offenen 15.l.W/R/C-Abnahmen bleiben unverändert.
Historische Nachweise behalten ihre ursprünglichen Bindungen.

### 20.24 Auswahl betroffener Restore-Journale v0.2.30

`RESTORE-JOURNAL-SELECTION`, ausdrücklich manuell beauftragt am
26. Oktober 2026, konkretisiert in 10.7.4 die Auswahl alter aktiver Journale
durch eine aktuell autorisierte Pfad-/Hashliste. Die Auswahl bindet pro
Eintrag die vollständige ursprüngliche Datei-/Verzeichnisinventur, bleibt
an Originalplan und Recovery-Auftrag gebunden und darf weder fremde Sperren
noch abgeschlossene Receipts neutralisieren. Leere Auswahl bedeutet keine
Auswahl. Bestehende Quellen-, Historien-, Lock-, Sicherungs-, Audit- und
Wiederanlaufgates bleiben zwingend. `restore-plan-v1` bleibt unverändert.
Der manuelle OFF-PLAN-Auftrag verändert kein automatisches Control-Budget.
Produktstand 648/900, offene 15.l.W/R/C-Abnahmen und historische Belege
bleiben erhalten; die Dokument- und Katalogbindung ist kein ausführbarer
Restore-, Crash-, Produkt- oder Release-Erfolgsnachweis.

### 20.25 Dreierregel für Control-Vertrag 3 v0.2.31

Der ausdrückliche manuelle Nutzerauftrag vom 26. Oktober 2026 erweitert
`SPECROAD-DECISION-1` gemäß 2.4.3 auf höchstens drei aufeinanderfolgende
Klärungsbundles unter gültigem Control-Vertrag 3. Typisierte Pflichtfelder,
positives Restbudget und ausdrückliche Freigabe, einmaliger Verbrauch auch
bei Apply-Fehler sowie erfolgreicher sauberer normaler Abschluss als einzige
Reset-/Versionsübergangsgrenze sind verbindlich. Version 2 behält die
Einerregel. Alte Aufträge, Antworten, Blockaden und Belege bleiben erhalten;
Retry, Overload, Pause, Neustart und Recovery erneuern kein Budget.
Die Grenzen aus 2.4.1, Entscheidungsbelege aus 2.4.2 und Blockerregeln aus
2.4.4 bleiben unverändert. Diese Dokumentfassung implementiert kein Control-
oder Produktverhalten und aktiviert keine Automatik. Produktstand 648/900
und der offene Schritt 15.l.W bleiben unverändert. Aktive Katalogbindungen
folgen den neuen Dokumentbytes; historische Nachweise bleiben historisch.

### 20.26 Explizite Restore-Ownerübergabe v0.2.32

Die delegierte Entscheidung RESTORE-OWNER-HANDOFF aus 10.7.5 trennt den
explizit autorisierten Übergang eines passend ausgewählten gewöhnlichen
Altowners an einen neuen Restore von der Fortsetzung derselben gebundenen
Restore-Ausführung. Beide Owner-/Auftragsseiten, tatsächlicher Root,
Originalbytes und Risikoentscheidung bleiben nachvollziehbar gebunden.
Native Mutex-, Owner-, Berechtigungs- und Journalgates werden nicht umgangen.
Der Produktstand bleibt 649/900, 15.l.R offen. Diese normative Präzisierung
ist kein Implementierungs- oder Produktabnahmenachweis. Aktive Kataloghashes
folgen den neuen Dokumentbytes; historische Belege bleiben unverändert.

### 20.27 Explizite Restore-Aufrufbindung v0.2.33

RESTORE-CLI-BINDING konkretisiert in 10.7.6 die beiden bereits vorgesehenen
Restoreaufrufe durch explizite Quellart, Root-/Dateipaare und operative
Baselinewerte. Der spezialisierte Recoverypreflight und die native
Wiederanlaufprüfung erhalten beschädigte Originalbytes und sämtliche
Autorisierungs-, Lock-, Erhaltungs- und Frischegates. Keine neue Autorität
oder Produktfreigabe entsteht. Umsetzung und Gesamt-Restoreabnahme bleiben
in 15.l.R offen, Produktstand 649/900. Aktive Kataloghashbindungen folgen
der neuen Dokumentfassung; historische Evidence bleibt unverändert.

### 20.28 Passive Restorebindung in Workfortsetzungen v0.2.34

RESTORE-WORK-BINDING konkretisiert in 10.7.7 die passive Originalplan-/
Auswahlbindung im vorhandenen Workmanifest. Beschädigter Bestand erhält
keine erfundene Modellbasis; ursprünglicher Auftrag, aktuelle Autorisierung
und native Journalwahrheit bleiben getrennt. Worktransport bindet keine
Herkunfts-/Projektroots um und ersetzt keine lokale Transaktionssicherung.
Die bestehenden Einzellauf-, Crash-, Erhaltungs- und menschlichen Freigabegates
bleiben Pflicht. Umsetzung und Nachweise bleiben in 15.l.R offen; Produktstand
649/900 unverändert. Nur aktive Kataloghashbindungen werden nachgeführt.

## 21. Entscheidungsstatus und nicht blockierende Restpunkte

| ID | Thema | Stand |
|---|---|---|
| SR-ISSUE-0001 | Implementierungssprache | **Geschlossen:** Python, Mindestlaufzeit CPython 3.10. |
| SR-ISSUE-0002 | Vollständiges CLI-Authoring | **Geschlossen:** gemeinsamer Change Plan und direkte Authoring-Befehle. |
| SR-ISSUE-0003 | Branchfähige IDs | **Geschlossen:** `random128-v1` für neue Artefakte und Relationen. |
| SR-ISSUE-0004 | Mehrdatei-Atomarität | **Geschlossen:** Journal, Staging, Before Images und Recovery. |
| SR-ISSUE-0005 | Schema-Migration | **Spezifiziert:** versionierte Plan-/Apply-/Verify-Migration einschließlich Legacy-Vertrag in Anhang Q; Nachweis durch die Implementierung ausstehend. |
| SR-ISSUE-0006 | Plugin-Prozessmodell | Offen für eine spätere Version; ausführbare Plugins sind kein Bestandteil des 0.2-Core. |
| SR-ISSUE-0007 | MCP-Server | Offen für eine spätere Version; die maschinenlesbare CLI-Selbstbeschreibung ist die 0.2-Agentenschnittstelle. |
| SR-ISSUE-0008 | Web- und IDE-Oberfläche | Außerhalb des Single-User-CLI-Zielrelease. |
| SR-ISSUE-0009 | Externe ALM-/API-Adapter | GitHub, GitLab, Jira, OpenAPI und ähnliche Adapter sind nicht Bestandteil des Core; offene Dateiformate sind vorhanden. |
| SR-ISSUE-0010 | Formale Backends | LTL, TLA+ und andere formale Sprachen bleiben nachgelagert. |
| SR-ISSUE-0011 | Weitere Abnahmeplattformen | Windows- und macOS-Abnahmeziele werden gesondert entschieden; Formate bleiben plattformneutral. |
| SR-ISSUE-0012 | PDF- und DOCX-Ausgabe | Der Core erzeugt Markdown und selbstenthaltenes HTML; native PDF-/DOCX-Erzeugung bleibt ein späterer Exportadapter. |
| SR-ISSUE-0013 | Sprachspezifische Code-Resolver | Der Core ist hash- und pfadbasiert; AST-/LSP-Resolver bleiben optionale spätere Adapter. |
| SR-ISSUE-0014 | Kryptografische Signaturen | Hashes und unveränderbare Receipts sind enthalten; organisatorische Signaturen und PKI sind nicht Teil von 0.2. |
| SR-ISSUE-0015 | Multi-Repository und Serverbetrieb | Bewusst außerhalb des vereinbarten Single-Repository- und Single-User-Scopes. |
| SR-ISSUE-0016 | Kurzlebige Runtime und ressourcensparsame Ausführung | **Entschieden:** SR-DEC-0039 und SR-DEC-0040; verbindliche Ablauf-, Budget- und Abnahmeverträge in Anhang N/O und Kapitel 14.6–14.7. Umsetzung und Messnachweise sind Releasearbeit, keine durch dieses Dokument behauptete Erfüllung. |
| SR-ISSUE-0017 | Mehrsprachigkeit und Verbindlichkeit | **Entschieden:** Anhang S; Pflichtfelder language/normative_force und getrennte deterministische Policies. |
| SR-ISSUE-0018 | Analyzer und py3langid im ersten Release | **Entschieden:** Anhang T; echter ausgelieferter Adapter, optionale Runtimepakete, generischer Datenaustausch. |
| SR-ISSUE-0019 | Semantisches Textverständnis | **Bewusst später:** kein eingebauter Bedeutungs-, Übersetzungs- oder Modalitätsanalyzer; spätere Erweiterungen nutzen den generischen Vertrag. |
| SR-ISSUE-0020 | SRX-Zahlenpräzision | **Entschieden:** Anhang U; Default 34 signifikante Dezimalziffern, explizite Konfiguration und exakte Fehlersemantik. |

---

## 22. Geplante Weiterentwicklung nach 0.2

Die folgende Roadmap ist informativ und erzeugt keine Anforderungen an 0.2:

- **0.3 — Weitere technische Contracts und Analyzer:** optionale semantische Analyse, zusätzliche Sprachdetektoren und Transportadapter auf dem bereits vorhandenen Datenvertrag; OpenAPI, AsyncAPI, GraphQL, Protobuf, Contract-Diffs sowie optionale GitHub-/GitLab-/Jira-Adapter.
- **0.4 — Agenten- und Plugin-Schnittstellen:** MCP, capability-basierter isolierter Plugin Runner und signierte Adapter.
- **0.5 — Progressive Formalisierung:** Gherkin, Zustandsmodelle und erste formale Backends.
- **1.0 — Governance:** optionale Signaturen, Organisationsprofile, plattformübergreifende Abnahme und gegebenenfalls getrenntes Multi-Repository-Modul.

---

## 23. Änderungsverlauf

| Version | Datum | Status | Änderung |
|---|---|---|---|
| 0.2.34 | 2026-10-27 | Delegiert gemäß SPECROAD-DECISION-1 | RESTORE-WORK-BINDING: passive Originalplan-/Auswahlbindung für Restore in Work, getrennte aktuelle Recoveryautorisierung und Vorrang nativer Journale; offene Umsetzung und unveränderte Schutzgates. |
| 0.2.33 | 2026-10-27 | Delegiert gemäß SPECROAD-DECISION-1 | RESTORE-CLI-BINDING: explizite Restoremodi, Quellart, operative Baselinewerte und Root-/Dateipaare; spezialisierter Preflight mit unveränderten nativen Autorisierungs- und Recoverygates. |
| 0.2.32 | 2026-10-26 | Delegiert gemäß SPECROAD-DECISION-1 | RESTORE-OWNER-HANDOFF: explizite zweitseitige Owner-/Auftragsbindung für neuen oder fortgesetzten Restore; native Lock-/Risikogates, Originalerhaltung und Produktstand bleiben erhalten. |
| 0.2.31 | 2026-10-26 | Ausdrücklicher manueller Nutzerauftrag zur Erweiterung der Projektregel | SPECROAD-DECISION-1-V3: höchstens drei Klärungsbundles unter gültigem Vertrag 3 mit dauerhaftem Budget; Version 2 behält die Einerregel. Fachliche Grenzen, Nachweise und Betriebszustände bleiben erhalten. |
| 0.2.30 | 2026-10-26 | Ausdrücklicher manueller Nutzerauftrag | RESTORE-JOURNAL-SELECTION: autorisierte Pfad-/Inventurhashliste für betroffene alte aktive Journale, übrige Sperren bleiben erhalten; Umsetzung und Crashabnahme in 15.l offen. |
| 0.2.29 | 2026-10-26 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | RESTORE-EXECUTION-CONTRACT: genaue eigene Betriebswrites, dauerhafte Originalbytes und konservativer Abschluss/Rollback der Restore-Ausführung; Umsetzung und Crashabnahme in 15.l bleiben offen. |
| 0.2.28 | 2026-10-26 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | RESTORE-PLAN-CONTRACT: geschlossener bytegebundener Restoreplan mit getrennten Quell-, Bestands-, Ziel- und Sicherungshashes; Umsetzung in 15.j–15.l bleibt offen. |
| 0.2.27 | 2026-10-25 | PARTIAL-READ-GRAPH.C | Bereits festgelegte gemeinsame Grenzen und Abfragedomänen strukturell ordnen; Fachverhalten unverändert, 15.f.R bleibt offen. |
| 0.2.26 | 2026-10-25 | PARTIAL-READ-GRAPH.R | Fehler-, Kontext- und Randfallgrenzen des Partial-Lesevertrags ergänzen; 15.f.R bleibt offen. |
| 0.2.25 | 2026-10-25 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | PARTIAL-READ-GRAPH: tatsächliche Mitglieder, bekannte Außenkanten und lokale Traversierung für zulässige Partial-Lesebefehle; maschinenlesbare Scopegrenze, keine zusätzlichen Prüfobjekte, Produktumsetzung in 15.f.R offen. |
| 0.2.23 | 2026-10-25 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | PARTIAL-CONFIGURATION-CONTEXT: exakte Parent-Kette als bytegebundener Auflösungskontext konfigurierter Teilbundles, getrennt von unveränderter fachlicher Closure; keine zusätzlichen Scope-Mitglieder oder Hashalgorithmen. Umsetzung bleibt in 15.c.R offen, unabhängige Prüfung und Extraktion in 15.d/15.e. |
| 0.2.22 | 2026-10-24 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | BUNDLE-MANIFEST-CONTRACT: geschlossene Feldmenge, exakte Payloadbijektion, bewusste Ausschlüsse und getrennte Modell-/Idempotenzbindungen auf dem vorhandenen Archivprofil; Scope-, Sicherheits-, Kompatibilitäts- und Freigabeverträge bleiben erhalten, Umsetzung bleibt in 15.a und den folgenden M15-Schritten offen. |
| 0.2.21 | 2026-10-24 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | EXPORT-MANIFEST-CONTRACT: gebundener Exportumfang, exakte deterministische Zeitprojektion, separate Manifestfelder und tatsächliche Verlust-/Anhang-/Ausgabehashbindung; bestehende Scope-, Format- und Freigabeverträge bleiben erhalten, Umsetzung bleibt in 14.l offen. |
| 0.2.20 | 2026-10-24 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | REQIFZ-CONTAINER-CONTRACT: explizite Dokumentauswahl, dokumentrelative Anhangbindungen, abgeleitetes Transportmanifest und gemeinsame sichere ZIP-Grenze; bestehende Import-/Sicherheitsverträge bleiben erhalten, Umsetzung bleibt in 14.k offen. |
| 0.2.19 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | REQIF-PRESERVATION-LOSS: passiver Originalquellträger, überprüfter Zielerhalt, konkrete Verlustidentitäten und fail-on-loss-Grenze; bestehende Sicherheits-/Importverträge bleiben erhalten, Umsetzung bleibt in 14.j offen. |
| 0.2.18 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | REQIF-STRUCTURE-XHTML: geordnete Vorkommensidentität, explizite Relationsabbildung und sichere XHTML-/Anhangschnittmenge; bestehende Sicherheits-/Mappingverträge bleiben erhalten, Umsetzung bleibt in 14.i offen. |
| 0.2.17 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | REQIF-OBJECT-CONTRACT: typisierte Objekterhaltung, identitätsbasierte Selektoren, Default-Herkunft und verlustbewusste JSON-Schnittmenge; bestehende Sicherheits-/Mappingverträge bleiben erhalten, Umsetzung bleibt in 14.h offen. |
| 0.2.16 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | NDJSON-OBJECT-CONTRACT: geschlossene versionierte Transporthülle, native Payload-/Hash-Erhaltung und eindeutiges Framing/EOF; passive Grenzen bleiben erhalten, Umsetzung bleibt in 14.g offen. |
| 0.2.15 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | CSV-PROFILE-CONTRACT: separates gebundenes CSV-Profil mit expliziten Zellcodecs, JSON-Listenregel, Null-/Abwesenheits- und Reject-Vertrag; bestehende Formate bleiben erhalten, Umsetzung bleibt in 14.f offen. |
| 0.2.14 | 2026-10-23 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | IMPORT-CONFLICT-POLICY: vier explizite Importstrategien, gemeinsame verlusterhaltende Übernahmegrenzen, reguläre Revision derselben Identität, sichtbare Divergenz und unveränderte Legacy-Historien; Umsetzung bleibt in 14.c offen. |
| 0.2.13 | 2026-10-22 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | EXCHANGE-MAPPING-CONTRACT: geschlossene passive v1-Mappingtabellen, getrennte hashgebundene Registry und deterministische Auswertung nach 10.12.1; Bestandsdaten bleiben erhalten, Umsetzung bleibt in 14.a offen. |
| 0.2.12 | 2026-10-22 | Delegierte Detailklärung nach SPECROAD-DECISION-1 | READINESS-SUBJECT-CONTEXT: exakte additive v1-Projektion für Capability-/Task-Subjects, unveränderte bestehende Hashes und gebundene Bewertung von Bestands-Evidence; Umsetzung bleibt in 13.f offen. |
| 0.2.11 | 2026-10-22 | Nutzerbeauftragte Entwicklungsdelegation | SPECROAD-DECISION-1: begrenzte eigenständige Detailklärung, dokumentierte Alternativen und normative Abnahmen; Control-Vertrag 2 mit höchstens einem Klärungsbundle in Folge. Produktfreigaben, Tests, Runtimezustand und Requirement-IDs bleiben unverändert. |
| 0.2.9 | 2026-10-19 | Nutzerbeauftragte Waiver-Präzisierung | Exakte versionierte Inhaltsprojektion, Scope-/Konfigurationsbindung, explizite UTC-Frist und Bewertungszeit, gebundener menschlicher Review und lesbarer unwirksamer Legacy-Bestand; bestehende Requirements bleiben erhalten. |
| 0.2.10 | 2026-10-22 | Nutzerbeauftragte OFF-PLAN-Readiness-Präzisierung | Geschlossene v1-Policy, feste typbezogene Pflichtgates, strikte Risiko-/Issue-Regeln mit gebundenem menschlichem Abschlussnachweis, explizite Ergebniszustände und lesbarer Legacy-Bestand; Umsetzung folgt in 13.f/13.g. |
| 0.2.8 | 2026-10-14 | Nutzerbeauftragte Featureplanung | PatchHarbor-Python-API als Basis für portablen Projekt-/PYZ-Hinweg, gebundenen Proposal-Rückweg und kontrollierte lokale Übernahme; zwölf neue Requirements und explizite öffentliche API-Abhängigkeit, keine Implementierungs-/Freigabebehauptung. |
| 0.2.7 | 2026-09-14 | Fachliche Korrekturfassung | B01/A02 aus der Prüfung v0.2.6: automatische externe Analyzer-Checkpoints auch ohne --work-dir; explizite Analysekennung mit eigener Vergabe, Paarbindung und Resume-Erhaltung statt Schreib-Idempotenz; 730 Requirement-IDs unverändert; zwölf gekoppelte Sollfälle ergänzt. |
| 0.2.6 | 2026-09-14 | Fachlich erweiterte Spezifikation | Explizite Requirement-Sprache und Verbindlichkeit, Mehrsprachenpolicies, getrennte Sprachpakete, allgemeines Analyzer-Protokoll samt realem py3langid-Lieferumfang, sichere optionale Worker-Ausführung, vollständige Analysefortsetzung und SRX-Zahlenpolicy; neue fachliche Quelle bei unverändertem ersten Zielrelease. |
| 0.2.5 | 2026-09-13 | Fachliche Korrekturfassung | B01/B02/B03/H01/H02 aus der Prüfung v0.2.4 eingearbeitet: explizite Lifecycle-Ausnahme und Mischfallregel, negative Reviews mit atomarem Freigabeentzug, project/partial-Bundlevertrag, nichtrekursive Manifestliste, vollständiger erhaltender Restore mit gebundenem Ziel; 650 Requirement-IDs unverändert; 47 kontraktübergreifende Sollfälle. |
| 0.2.4 | 2026-09-13 | Fachliche Korrekturfassung | Vier Restbefunde konsolidiert: nichtrekursive Proposal-Basis, bewertungsgebundene Evidence und Retest-Ablösung, getrennte Selbstbeschreibungsprojektion sowie eindeutige Query-Logik. Unverändert 650 Requirements; bestehende Verifikation um R-23 bis R-32 ergänzt. |
| 0.2.3 | 2026-09-06 | Neue fachliche Arbeitsgrundlage | Konsolidierung der acht Auditbefunde; weiche Arbeitsziele statt Budgetfehler; adaptive vollständige Verarbeitung, Checkpoints, portable Arbeitspakete und Mehrprompt-Fortsetzung; Quellenwechsel auf diese PDF. |
| 0.2.2 | 2026-09-05 | Draft | Ephemeral Runtime Safety und Resource-Constrained Runtime Design mit begrenztem Preflight, Runtime-Diagnose, Recovery-/Cache-Trennung, endlichen Betriebsbudgets, sicheren Ressourcenabbrüchen und eigenen Benchmarks ergänzt; betroffene CLI-, Determinismus- und Recoveryverträge konsolidiert; 600 Requirements. |
| 0.2.1 | 2026-09-01 | Draft | Konsolidierungsfassung: Scope-Closure, exakte Relationsmatrix, Profilkomposition, Proposal-Authoring, Change-Metadaten, getrennte Verification-Zustände, Spezial-Lifecycles, Import-Dreifachvergleich, sichere Recovery, vollständige Dokumentpayloads, Query-/JSON-Verträge, Befehlsklassen, partielle Bundles, kanonisches ZIP, portable Idempotenz, Requirement-Testfälle und reproduzierbare Performance geschlossen; 548 Requirements. |
| 0.2.0 | 2026-08-31 | Draft | Vollständige Neufassung als moderne Single-User-/Single-Repository-Workbench; alle identifizierten P0-/P1-Lücken und die in-scope Ergänzungen Varianten, Diagrammquellen, Bundles und Runtime-Matrix geschlossen; 404 Requirements. |
| 0.1.1 | 2026-08-01 | Draft | Python 3.10, dependency-freier Core, nichtinteraktive CLI und Sandbox-Roundtrip; 230 Requirements. |
| 0.1.0 | 2026-07-27 | Draft | Erste vollständige Produktspezifikation mit 222 Requirements. |

---
# Anhang A — Prüfliste für einzelne Requirements

Vor der Freigabe eines Requirements sind alle Fragen zu bejahen:

1. Beschreibt es genau eine normative Verpflichtung?
2. Ist der verantwortliche Systemteil oder Actor eindeutig?
3. Sind Trigger, Bedingungen, Scope und Ausnahmen eindeutig?
4. Ist das Ergebnis beobachtbar oder messbar?
5. Sind Grenzwerte und Einheiten normalisiert?
6. Sind unbestimmte Begriffe vermieden oder definiert?
7. Ist eine nichtleere Begründung vorhanden?
8. Ist die Herkunft über Need, Goal oder Source nachvollziehbar?
9. Existiert ein Verification Contract mit eindeutigem Pass-Kriterium?
10. Sind alle verwendeten Begriffe definiert oder allgemein eindeutig?
11. Widerspricht das Requirement keinem anderen Requirement?
12. Sind alle profilabhängigen Pflichtrelationen vorhanden, gültig und `current`?
13. Existiert kein offener Platzhalter?
14. Ist bei `normative_force=should` die Abweichung vollständig geregelt?
15. Ist `applicability` für alle relevanten Konfigurationen konsistent?
16. Ist die Anforderung in mindestens einem Dokument oder einer begründet dokumentfreien Query auffindbar?
17. Sind betroffene Code-, Test- und Evidence-Bezüge aktuell oder bewusst offen ausgewiesen?
18. Sind Sprache und Verbindlichkeit explizit deklariert, ohne die Textbedeutung aus Detektor- oder Keywordheuristik zu erfinden?

---

# Anhang B — Normative SRX-1.0-Semantik

## B.1 Ausdrucksform

Jeder Ausdrucksknoten ist ein JSON-Objekt mit `op`. Unbekannte Felder werden durch das SRX-Schema abgewiesen, sofern der jeweilige Operator sie nicht ausdrücklich erlaubt. Operatorargumente dürfen verschachtelte Ausdrucksknoten oder operatorabhängige Literalfelder sein. Ein Ausdruck darf nur einen JSON-Wert oder `missing` zurückgeben.

## B.2 Operatoren

| Operator | Operanden | Semantik |
|---|---|---|
| `literal` | `value` | Gibt den JSON-Wert unverändert zurück; Zahlen müssen endlich und RFC-8259-konform sein. |
| `field` | `context`, `pointer` | Liest per RFC-6901-Pointer; nicht vorhandener Pfad ergibt `missing`. |
| `exists` | `arg` | `false` nur für `missing`, sonst `true`, einschließlich JSON `null`. |
| `not` | `arg` Boolean | Boolesche Negation. |
| `and` | `args` Boolean-Array | Links-nach-rechts, kurzschließend; leeres Array ergibt `true`. |
| `or` | `args` Boolean-Array | Links-nach-rechts, kurzschließend; leeres Array ergibt `false`. |
| `eq` | zwei Werte gleichen Typs | Ist mindestens ein Operand `missing`, ergibt der Vergleich `false`; sonst tiefe JSON-Gleichheit. |
| `ne` | zwei Werte | Ist mindestens ein Operand `missing`, ergibt der Vergleich `true`; sonst boolesche Negation von `eq`. |
| `lt`, `lte`, `gt`, `gte` | zwei Zahlen oder zwei Strings | Zahlen numerisch; Strings nach Unicode-Codepoint-Reihenfolge; `missing`, andere oder verschiedene Typen sind Fehler beziehungsweise gemäß SR-REQ-0291 `false` für `missing`. |
| `in` | Wert, Array | `true`, wenn ein Arrayelement nach `eq` gleich ist. |
| `contains` | String/String oder Array/Wert | Substring nach Codepoints beziehungsweise Elementgleichheit nach `eq`. |
| `starts_with`, `ends_with` | zwei Strings | Präfix-/Suffixvergleich ohne Locale oder Normalisierung. |
| `length` | String, Array oder Objekt | Anzahl Unicode-Codepoints, Arrayelemente oder Objektschlüssel. |
| `count` | Array | Anzahl Arrayelemente; identisch zu `length` für Arrays. |
| `any` | Arrayausdruck, Prädikat | Bindet jedes Element als `item`; leeres Array ergibt `false`. |
| `all` | Arrayausdruck, Prädikat | Bindet jedes Element als `item`; leeres Array ergibt `true`. |
| `none` | Arrayausdruck, Prädikat | `not any`; leeres Array ergibt `true`. |
| `add`, `subtract`, `multiply` | zwei Zahlen | Exakte dezimale Arithmetik mit der projektgebundenen Präzisions- und JCS-Roundtrip-Policy aus Anhang U. |
| `divide` | zwei Zahlen | Exakte Division nach Anhang U; Nullteiler, nicht endlicher Dezimalquotient, Präzisionsüberschreitung oder verlustreicher JCS-Roundtrip erzeugen eine spezifische Diagnose. |
| `relation_count` | Richtung, Typfilter | Anzahl unmittelbarer passender Relationen des aktuellen Artefakts. |
| `incoming_count` | Typfilter | Anzahl berechneter eingehender passender Relationen. |
| `has_relation` | Richtung, Typfilter, optional Zieltyp/ID | Boolesche unmittelbare Relationsprüfung. |
| `reachable` | Richtung, Typfilter, Zielprädikat, `max_depth` | Breitensuche in stabiler ID-Reihenfolge; Ergebnis ist boolesch. |

## B.3 Typ- und Fehlerregeln

- Es gibt die Typen `missing`, `null`, Boolean, Number, String, Array und Object.
- Keine implizite Konvertierung ist zulässig.
- JSON-Objektschlüssel werden bei tiefer Gleichheit lexikografisch verglichen; ihre ursprüngliche Reihenfolge ist bedeutungslos.
- Strings werden nicht automatisch Unicode-normalisiert.
- `missing` darf nicht serialisiert werden.
- Ein Typfehler beendet die jeweilige Regelauswertung mit einer Diagnose; er wird nicht als `false` verschluckt.
- Division und arithmetische Überläufe erzeugen Diagnosen.
- Graphoperatoren dürfen ausschließlich auf dem bereits geladenen Modell arbeiten.
- Gleiche Eingaben müssen dasselbe Ergebnis und dieselbe Diagnosefolge liefern.

## B.4 Quantoren

Ein Quantor besitzt mindestens:

```json
{
  "op": "any",
  "array": {"op": "field", "context": "artifact", "pointer": "/relations"},
  "where": {
    "op": "eq",
    "args": [
      {"op": "field", "context": "item", "pointer": "/type"},
      {"op": "literal", "value": "verified_by"}
    ]
  }
}
```

Der `item`-Kontext existiert nur innerhalb des zugehörigen Prädikats. Verschachtelte Quantoren schatten den inneren `item`-Kontext; der äußere darf nicht über dynamische Pfade referenziert werden.

## B.5 Graphoperatoren

Graphoperatoren müssen Relationstypen als explizite Liste oder `*` verwenden. `reachable` benötigt `max_depth >= 0`. Tiefe 0 prüft ausschließlich das Ausgangsartefakt gegen das Zielprädikat. Besuchte IDs werden einmal verarbeitet; Nachbarn werden nach Relationstyp, Ziel-ID und Relation-ID stabil sortiert.

## B.6 Versionsregel

Die Semantik dieses Anhangs gehört zu `SRX 1.0`. Neue rückwärtskompatible Operatoren dürfen in 1.x ergänzt werden. Änderung bestehender Ergebnisse, Typregeln, Missing-Semantik oder Traversierungsreihenfolge erfordert SRX 2.0.

---

# Anhang C — Normativer Transaktions- und Recovery-Algorithmus

## C.1 Vorbereitung

1. Writer-Lock erwerben und Recovery-Vorprüfung durchführen.
2. Change-Plan-Hash, Basiswurzel, Request-ID und gebundene Ergebnisressourcen prüfen.
3. Journal im Zustand `building` mit null veröffentlichten Einträgen erzeugen und `fsync` ausführen.
4. Before Images und gestagte Zielbytes mit Pfad, Länge und Hash sichern.
5. Den vollständigen Endstand aus den gestagten Bytes materialisieren, validieren und gegen die erwartete Zielwurzel prüfen.
6. Journal mit vollständigem Pfadmanifest auf `prepared` setzen und Datei sowie Elternverzeichnis synchronisieren.

## C.2 Veröffentlichung

1. Journal auf `committing` setzen und synchronisieren.
2. Ziele in kanonischer Pfadreihenfolge durch atomare Umbenennung veröffentlichen.
3. Nach jedem Ziel den veröffentlichten Index und Zielhash im Journal synchronisieren.
4. Zielwurzel erneut berechnen.
5. Request- und Transaktionsreceipt dauerhaft schreiben.
6. Journal auf `committed` setzen und synchronisieren.

## C.3 Recovery

| Zustand | Automatische Aktion | Manuell zulässige Aktion |
|---|---|---|
| `building` | bei nachweislich null Veröffentlichungen Basis beibehalten und `rolled_back` setzen | `discard` nur unter derselben Bedingung |
| `prepared` | bei null Veröffentlichungen und nachweisbarer Basis auf `rolled_back` abschließen; keine neue Fachoperation beginnen | `discard` nur bei null Veröffentlichungen und passender Basiswurzel |
| `committing` | bei bereits vollständigem Ziel nach SR-REQ-0258 Receipts ergänzen; andernfalls nach SR-REQ-0511 vollständig auf Basis zurückrollen | kein Discard |
| `rolling_back` | Basisrestauration vervollständigen | kein Discard |
| `corrupt` | keine automatische Änderung | ausschließlich vorgeprüfter `recover restore --plan` nach 10.7.1; Hashintegrität allein qualifiziert keine Quelle |

Ist weder Basis noch Ziel mit vorhandenen, hashgültigen Bytes sicher herstellbar, wird `corrupt` im zulässigen Recovery-Write gesetzt; schreibfreie Befehle diagnostizieren denselben beobachteten Zustand ohne Journaländerung. Für den Aufruf einer Recovery, ihre Budgetreserve und die Trennung von einer neuen Fachoperation gelten Anhang N.3 und O.4. Bis zum erfolgreichen Restore sind normale Projektbefehle gesperrt. Das korrupte Journal wird niemals gelöscht, sondern nach Restore content-addressiert in `.specroad/recovery/archive/` gesichert.

---

# Anhang D — Normative Austauschprofile

## D.1 ReqIF 1.2

Das unterstützte Profil umfasst:

- `REQ-IF-HEADER`, `REQ-IF-CONTENT`, Datentyp- und Spec-Type-Definitionen;
- `SPEC-OBJECT`, `SPEC-RELATION`, `SPECIFICATION`, `SPEC-HIERARCHY`;
- Boolean, Integer, Real, String, DateTime, Enumeration und XHTML;
- eingebettete oder referenzierte Anhänge innerhalb ReqIFZ;
- External Identity und Mapping auf SpecRoad-Typen und -Felder;
- `CREATION-TIME` als Maximum der enthaltenen normativen `updated_at`-Zeitstempel oder `1970-01-01T00:00:00Z` bei leerem Scope.

ReqIF-Tool-Extensions werden nicht ausgeführt. Nicht verstandene Extensions werden als Payload erhalten oder als Verlust gemeldet.

### D.1.1 ReqIF-Objekte und Mappinggrenze v1

**Entscheidung REQIF-OBJECT-CONTRACT, delegiert gemäß SPECROAD-DECISION-1:**
`reqif-object-profile-v1` präzisiert für 14.h die Grenze zwischen ReqIF-
Objektmodell und den unveränderten Austauschmappings nach 10.12.1.
Dies ist eine SpecRoad-Profilkennung, keine neue ReqIF-Version, Mapping-
Ressource oder native Artefaktversion. Der vollständige Umfang von D.1
und SR-REQ-0320–0324/0330 bleibt verpflichtend; Hierarchien, Relationen,
XHTML und ReqIFZ behalten ihre zugeordneten weiteren Umsetzungsschritte.

**Externe Grundlage:** Maßgeblich bleibt [OMG ReqIF 1.2,
formal/2016-07-01](https://www.omg.org/spec/ReqIF/1.2/PDF), insbesondere
9.2.3, 10.2, 10.5 und 10.8. ReqIF unterscheidet Kennungen, Typdefinitionen,
Attributdefinitionen und Werte; Definitionen können Standardwerte tragen.
Die Standardfassung 1.2 ist nicht mit dem Headerwert gleichzusetzen:
`REQ-IF-VERSION` lautet dort `1.0`. Die folgenden Abbildungsregeln sind
ausdrückliche SpecRoad-Entscheidungen, keine behaupteten zusätzlichen OMG-
Vorgaben oder Interoperabilitätsnachweise.

**Zwei getrennte Ergebnisse.** Ein passiver ReqIF-Objektcodec MUSS
Datentypen, Spec-Object-Typen, Attributdefinitionen und Spec-Objects samt
Kennungen, Typ-/Definitionsreferenzen, Werten und vorhandenen Metadaten
erhalten. Er MUSS die unveränderten Eingangsbytes und deren SHA-256 für
die spätere gebundene Verarbeitung verfügbar halten. Rohwerterhaltung
allein ist keine erfolgreiche native Abbildung. Ein nachgeschalteter
reiner Mappingadapter MUSS die ausdrückliche Ressource aus 10.12.1
verwenden; Parser oder Serializer DÜRFEN weder ein Mapping erraten noch
einen Change Plan ausführen oder Projektdateien veröffentlichen.

Das Objektmodell MUSS deklarierte Werte von Abwesenheit unterscheiden,
Definitions-Standardwerte getrennt erhalten und Datentypgrenzen sowie
Enum-Definitionen unverändert transportieren. Numerische XML-Lexeme
MÜSSEN neben ihrer Typzuordnung verlustfrei verfügbar bleiben, auch wenn
keine native JSON-Zahl daraus gebildet werden kann. Diese typisierte
Transporterhaltung ist kein String-Fallback für ein numerisches
SpecRoad-Feld. Auch Zeit-/Namens-/Beschreibungs- und Editierbarkeitsdaten
DÜRFEN NICHT still verschwinden oder als Produktfreigabe interpretiert
werden. Die konkrete interne Klassen-/Containerstruktur ist eine
Implementierungswahl; daraus entsteht kein weiteres öffentliches JSON-
Dateiformat mit impliziten Pflichtfeldern.

**Eindeutige Identitäts- und Feldzuordnung.** Für die Artefaktabbildung
ist `external_type` exakt die Kennung des referenzierten
`SPEC-OBJECT-TYPE`; jeder `external_field` ist exakt die Kennung der
zugehörigen Attributdefinition. `LONG-NAME`, Beschreibungen, Positionen
und AlternativeIDs sind keine Ersatzschlüssel. Zwei gleich benannte
Definitionen mit verschiedenen Kennungen bleiben verschieden; Änderungen
des Namens ändern die Zuordnung nicht. Kennungen werden nach der XML-
Dekodierung ohne eigene Normalisierung, Trimmen oder Case-Folding
verglichen. Fehlende, doppelte oder syntaktisch ungültige Kennungen,
unaufgelöste oder typfremde Referenzen und eine Attributdefinition, die
nicht zum Objekttyp gehört, MÜSSEN vor einer erfolgreichen Objektprojektion
abgewiesen werden. Wo die ReqIF-Struktur Vorwärtsreferenzen erlaubt,
entscheidet die vollständige Eingabe über ihre Auflösbarkeit; die
vorgeschriebene XML-Struktur wird dadurch nicht gelockert.

Die externe Objektidentität MUSS die unveränderte `SPEC-OBJECT`-Kennung
als `external_id` verwenden. `source_system`, `source_document` und eine
gegebenenfalls verwendete `external_revision` werden ausdrücklich vom
Aufrufer gebunden. Ein Dateipfad, Toolname, Header-Identifier oder
`LAST-CHANGE` DARF NICHT unbemerkt einen dieser Kontextwerte ersetzen.
Die bestehende externe Identitätsregistry und Importhistorie bleiben
maßgeblich; ein ReqIF-Identifier wird nicht zur nativen SpecRoad-ID.

Beim erstmaligen Export eines nativen Artefakts ohne externe Kennung im
ausdrücklich gewählten Zielkontext MUSS die neue ReqIF-Objektkennung
deterministisch als `_sr_` plus kleingeschriebene SHA-256 der RFC-8785-
Bytes des Objekts `{"project_id": P, "artifact_type": T, "id": I}` gebildet
werden. P, T und I sind die vorhandenen validierten nativen Werte;
Revision, Name, Scope-Reihenfolge und Ausführungszeit gehören nicht in
diese Projektion. Eine vorhandene eindeutige externe Kennung im Zielkontext
hat Vorrang. Mehrere passende externe Kennungen, eine unzulässige Kennung
oder eine Kollision im Ausgabedokument sind Konflikte, keine Erlaubnis zum
Umbenennen. Die Kennungsableitung schreibt keine Registry ins Projekt.
Typ- und Attributdefinitionen kommen weiterhin aus der ausdrücklich
gebundenen Definition/Mappingsicht; Feldnamen werden nicht zu Typen erraten.

**Wirksamer Wert und Herkunft.** Eine explizite Attributbelegung hat
Vorrang vor dem Definitions-Standardwert, auch bei `false`, numerischer
Null, leerem String oder leerer Enum-Auswahl. Fehlt die Belegung, wird
ein tatsächlich deklarierter und gültiger Standardwert für die
Mappingprojektion verwendet; ohne solchen Standard fehlt das Quellfeld.
Ein ungültiger expliziter Wert DARF NICHT durch den Standard ersetzt
werden. Der Adapter MUSS die Herkunft pro Definition unterscheidbar
ausweisen: `explicit`, `default` oder `absent`. Er DARF beim Export einer
unveränderten Objektprojektion keine zuvor fehlende Belegung allein wegen
ihres wirksamen Standards materialisieren. JSON-Null ist kein erfundener
ReqIF-Nullwert. Native Nullwerte außerhalb einer explizit darstellbaren
Abbildung sind nicht repräsentierbar.

**Wertprojektion für 10.12.1.** Erst nach der jeweiligen ReqIF-Typprüfung
MUSS die folgende Schnittstelle verwendet werden. Ein `value_map` arbeitet
auf diesem Wert; es ersetzt keine Typ-, Referenz- oder Sicherheitsprüfung.

| ReqIF-Wertfamilie | SpecRoad-Quellwert des Mappingadapters |
|---|---|
| Boolean | JSON-Boolean; kein Integer und kein Wahrheitswert aus beliebigem Text. |
| Integer | JSON-Zahl mit unverändertem ganzzahligem Wert, nur wenn der bestehende Zahlen-/JCS-Roundtripvertrag ihn akzeptiert. |
| Real | JSON-Zahl nur innerhalb der bestehenden endlichen Zahlen-/JCS-Schnittmenge; keine zusätzliche Rundung auf Datentypgenauigkeit oder Prozess-Decimal-Kontext. |
| String | Der durch XML bestimmte Stringwert unverändert, einschließlich Leerstring, Leerraum und Unicode; kein Splitten, Trimmen oder Enum-Raten. |
| Date/DateTime | Der geprüfte XML-dateTime-Wert als String mit erhaltener Zeitzonenangabe beziehungsweise erhaltener Zeitzonenabwesenheit und Bruchteilspräzision; keine lokale Zeitzone oder Epochensekunden ergänzen. |
| Enumeration | Immer ein JSON-Array der ausgewählten EnumValue-Kennungen, auch bei einfacher Auswahl. Für diese Projektion nach UTF-8-Bytes sortieren; keine Labels oder numerischen EmbeddedValue-Schlüssel verwenden. |

Für Enumeration MÜSSEN ausgewählte Kennungen zur referenzierten Definition
gehören; doppelte Auswahlkennungen werden als mehrdeutige Eingabe abgewiesen.
Die Einzel-/Mehrfachauswahl wird nach der Definition geprüft. Das Objektmodell
erhält die ursprüngliche Reihenfolge unabhängig von der sortierten
Mappingprojektion. Eine leere Auswahl ist von einem fehlenden Attribut
unterscheidbar. Es gibt keinen automatischen Wechsel zwischen String und
Array. Eine gewünschte native Status- oder Enum-Abbildung MUSS ausdrücklich
im vorhandenen `value_map` stehen.

Für Zahlen bleiben 9.5 und Anhang U unverändert. Ein gültiger ReqIF-Wert,
der diese native Schnittmenge nicht trifft, MUSS als nicht repräsentierbar
mit Objekt- und Definitionskennung ausgewiesen und im typisierten
Quellmodell erhalten werden. Das gilt insbesondere für nicht endliche
Werte, verworfene Präzision und eine im konkreten Roundtrip nicht erhaltene
numerische Eigenschaft wie das Vorzeichen einer negativen Null. Verboten
sind stilles Runden, Unterlauf auf Null, Stringifikation, Defaults oder das
Auslassen der betroffenen Belegung mit anschließendem uneingeschränktem
Erfolgsstatus. Ein ungemapptes Feld und ein nicht darstellbarer Wert bleiben
unterscheidbar. Die native Zielvalidierung entscheidet weiterhin über den
vollständigen Zieltyp, auch bei gemappten Datums- oder Statusstrings.

**Rückweg und Erhalt.** Ein unverändert gelesener unterstützter
Objektausschnitt MUSS seine Identitäten, Referenzen, Typdefinitionen,
expliziten Werte, Standardwerte und deren Herkunft semantisch erhalten.
Der Encoder DARF unterstützte Quelldaten nicht aus nativen Feldern neu
erraten. Bei nativer Abbildung MUSS der Rückweg deshalb die ausdrücklich
gebundene Typ-/Definitionsinformation und externe Identität verwenden.
Ein `value_map` darf nur bei eindeutigem inversen Treffer rückwärts benutzt
werden; keine Auswahl des ersten Treffers bei Mehrdeutigkeit. Ohne
eindeutige Darstellung MUSS der Export einen konkreten Verlust/Konflikt
ausweisen, statt eine Ersatzkennung oder einen Typ aus dem Feldnamen zu
erfinden. Diese Regel erweitert das vorhandene Mappingformat nicht.

Für identische Objektdaten und ausdrücklich gelieferte Metadaten MUSS die
Ausgabe byte-identisch sein. XML-Escapes, Namespace-Präfixe und Quote-Stil
sind keine fachliche Identität; der Encoder MUSS sie deterministisch und
sicher ausgeben. Der Projekt-Export verwendet weiterhin den in D.1
festgelegten `CREATION-TIME` und das Manifest nach SR-REQ-0319. Weder
Wanduhrzeit noch Zufall ersetzen fehlende notwendige Angaben.

**Sicherheit, Unvollständigkeit und Fehler.** Die vorhandene sichere
XML-Ereignisverarbeitung ist wiederzuverwenden. SR-REQ-0324 und Anhang O
gelten unverändert für die ganze Eingabe, auch für nicht gemappte oder
unbekannte Inhalte; keine DTD-, Entity-, Schema-, XInclude-, Netzwerk-
oder Codeauflösung. Eine Teilprojektion darf keine vollständige
ReqIF-/Importabnahme behaupten. XHTML bleibt strukturierter Inhalt nach
14.i, keine automatische Plaintext-Konvertierung. Andere nicht verstandene
Inhalte werden gemäß SR-REQ-0322 erhalten oder einzeln als Verlust benannt;
sie werden nicht still übersprungen. Das vollständige Verlust-/Manifest-
und ReqIFZ-Verhalten bleibt in 14.j/14.k und den Integrationsschritten
verpflichtend. Bis es ausgeführt werden kann, bleibt die entsprechende
Integration offen, statt einen uneingeschränkten Importerfolg zu melden.

Fehler MÜSSEN maschinenlesbar mindestens Grund und verfügbaren Objekt-/
Definitionsbezug oder XML-Position tragen, ohne komplette Nutztexte zu
kopieren. Syntax-, Typ- und Referenzfehler innerhalb der ReqIF-Eingabe
haben Code 3. Ein Konflikt mit einem gebundenen Quellstand oder eine
mehrdeutige inverse Exportzuordnung hat Code 6; reale Sicherheitsgrenzen
behalten Code 7, ungültige Aufrufkonfiguration Code 2. Bestehende
Mappingdiagnosen aus 10.12.1 behalten ihre Fehlerklasse und ihren Code.
Ressourcenfehler werden nicht in normale
Formatfehler oder partielle Erfolge umgedeutet. Dieser Vertrag führt keine
zusätzliche harte Gesamtauftragsgrenze, Freigabe oder Writer-Ausnahme ein.


### D.1.2 ReqIF-Struktur und XHTML-Schnittmenge v1

**Entscheidung REQIF-STRUCTURE-XHTML, delegiert gemäß SPECROAD-DECISION-1:**
`reqif-structure-xhtml-v1` präzisiert für 14.i die bisher unbestimmte
XHTML-Schnittmenge und deren Verbindung mit Hierarchien, Relationen und
Dokumentdaten. Es ist eine SpecRoad-Profilkennung, kein neues ReqIF-,
Mapping- oder Artefaktformat. D.1.1, 10.12.1, 10.14 und sämtliche späteren
Import-, Verlust-, ReqIFZ- und Freigabepflichten bleiben wirksam.

**Externe Grundlage und eigene Profilentscheidung.** [OMG ReqIF 1.2,
formal/2016-07-01](https://www.omg.org/spec/ReqIF/1.2/PDF), 10.4,
10.6.3 und 10.8.20, beschreibt Hierarchieeinträge, gerichtete
Objektbeziehungen und XHTML einschließlich externer Objekte und
Vereinfachungskennzeichnung. Die folgende sichere native Schnittmenge
ist eine eigene SpecRoad-Regel. Sie behauptet weder Unterstützung aller
XHTML-Module noch einen nachgewiesenen Roundtrip mit einem Fremdwerkzeug.

**Strukturerhaltung vor nativer Abbildung.** Der passive Codec MUSS
`SPECIFICATION`, `SPECIFICATION-TYPE`, `SPEC-HIERARCHY`, `SPEC-RELATION`
und `SPEC-RELATION-TYPE` zusätzlich zum Objektprofil erfassen. Er erhält
Kennungen, Typ-/Objekt-/Quell-/Zielreferenzen, geordnete Hierarchiekinder,
zugehörige Attributdefinitionen und Werte sowie vorhandene Metadaten.
Typisierte Belegungen und Defaults folgen D.1.1 auch bei Spezifikationen
und Relationen. XML-/Referenzprüfung und die bestehende globale
Identifier-Eindeutigkeit gelten für den gesamten erfassten Bestand.

Ein Hierarchieeintrag ist ein eigenes **Vorkommen** mit eigener Kennung,
genau einem Besitzer (Spezifikation oder übergeordnetes Vorkommen) und
der referenzierten Objektkennung. Zwei Einträge desselben Objekts bleiben
zwei Vorkommen, auch unter verschiedenen Dokumenten oder Vorfahren.
Die Kinderreihenfolge ist fachlich; sie DARF NICHT nach Objekt-ID, Titel
oder Typ umsortiert werden. Wiederholte Objektverweise allein sind kein
Hierarchiezyklus. Ein tatsächlicher Besitzzyklus, ein mehrdeutiger
Besitzer, doppelte Kennungen oder fehlende/falschartige Referenzziele
sind Fehler. Eine leere Spezifikation bleibt zulässig.

Eine Relation erhält ihre eigene Kennung und die Unterscheidung von
Quelle und Ziel. Gleiche Endpunkte ersetzen keine Relationsidentität;
entgegengesetzte Kanten werden nicht verschmolzen. Ein Zyklus in einer
beliebigen ReqIF-Relationsmenge ist nicht automatisch ungültig: Nach der
nativen Abbildung gilt die vorhandene Zyklusregel des gewählten
Core-Relationstyps. Fremde Editierbarkeits- oder Hierarchiemetadaten sind
passive Quelldaten, keine Schreibberechtigung oder menschliche Freigabe.

**Ausdrückliche native Bindung.** Für Spezifikationsfelder ist
`external_type` die referenzierte `SPECIFICATION-TYPE`-Kennung; die
Feldschlüssel bleiben Attributdefinitionskennungen. Für Relationen ist
der Selektor der `relations`-Tabelle die referenzierte
`SPEC-RELATION-TYPE`-Kennung. Da ein Hierarchieeintrag keinen eigenen
SpecType besitzt, ist der Selektor der `hierarchies`-Tabelle die
`SPEC-OBJECT-TYPE`-Kennung seines referenzierten Objekts. Der Aufrufer
liefert die nativen Bindungen für Besitzer und Kindvorkommen ausdrücklich;
`parent_to_child`/`child_to_parent` wirken auf diese Endpunkte. Bei
Relationen wirken `forward`/`reverse` auf die gebundenen Quell- und
Zielobjekte. Weder ein Name noch eine Position ersetzt eine Bindung.

Die Dokumentabbildung verwendet vorhandene `document`-, `section`- und
`content_block`-Daten samt `contains`/`references` und den M11-Prüfungen.
Ein referenziertes fachliches Objekt wird nicht allein wegen seines
Hierarchieplatzes in eine Section umgetypt oder kopiert. Vorkommen,
Objekt und native Darstellungsartefakte bleiben unterscheidbar; benötigte
native IDs, Pflichtmetadaten und Typzuordnungen müssen ausdrücklich
vorliegen. Eine passive Strukturbeobachtung ist bereits nutzbar, ersetzt
aber weder eine vollständige native Projektion noch einen Import-Apply.

Der Rückweg MUSS Spezifikations-, Vorkommens- und Relationsidentitäten
samt Reihenfolge und Richtung erhalten. Nichtartefaktidentitäten gehören
weiterhin in die ausdrücklich gebundene externe Registry nach 10.12.1;
Hierarchievorkommen verwenden `object_class=hierarchy`, Relationen
`object_class=relation`. Vorhandene Kennungen haben Vorrang; fehlende
Exportkennungen solcher Nichtartefakte müssen ausdrücklich geliefert
werden. Eine Reihenfolge, ein Objektname oder ein Endpunktpaar DARF
NICHT als Ersatzkennung dienen. D.1.1 bleibt für native Artefaktkennungen
unverändert. Ein Parser/Mapper schreibt keine Registry oder Projektdatei.

**Zwei Ebenen für XHTML.** Die Quelle bleibt ein namespaceaufgelöster,
geordneter Baum mit Text, Attributen und Originalbytes/SHA-256. `THE-VALUE`,
ein vorhandenes `THE-ORIGINAL-VALUE` und die Anwesenheit/Werte von
`IS-SIMPLIFIED` bleiben getrennt erhalten und unterliegen derselben
Sicherheitsprüfung. Eine fehlende Vereinfachungskennzeichnung ist kein
Beweis für Verlustfreiheit. Ein bereits vereinfachter Quellwert darf
nicht still als vollständig originalgetreu bezeichnet oder sein Flag
gelöscht werden; der Originalwert wird nicht ungeprüft als Ersatz gewählt.

Die **nativ darstellbare Kernmenge** verwendet ausschließlich den
Namespace `http://www.w3.org/1999/xhtml` und folgende Elemente:

| Elemente | Semantische Abbildung nach 10.14 |
|---|---|
| `div`, `p` | Inhaltsgruppe beziehungsweise Absatz. Gruppen erhalten die Reihenfolge ihrer Blöcke; sie erzeugen keine Section. |
| `span`, `em`, `i`, `strong`, `b` | Inline-Gruppe, Emphasis beziehungsweise Strong. Die Quellschreibweise bleibt zusätzlich im Quellbaum erhalten. |
| `br`, `hr` | Harter Zeilenumbruch beziehungsweise thematische Trennlinie; beide sind inhaltsleer. |
| `code`, `pre` | Inline-Code beziehungsweise Codeblock. `pre` enthält Text oder genau ein `code` mit Text; keine aktive Sprache/Interpreter-Auswahl. |
| `blockquote`, `ul`, `ol`, `li` | Blockquote, ungeordnete/geordnete Liste und Listeneintrag. Listen enthalten `li`; deren Reihenfolge bleibt erhalten. |
| `a` | Link auf einen ausdrücklich gebundenen projektinternen Anhang; der Linkinhalt bleibt Inline-Inhalt. |
| `object` | Passive Anhangreferenz; die verlustfreie Prose-Schnittmenge ist ein gebundenes PNG-Bild mit alternativem reinem Text. Andere Objektarten und Fallbackstrukturen bleiben im Quellmodell erhalten und als nicht vollständig nativ darstellbar ausgewiesen. |

Es gilt die ReqIF/XHTML-Struktur, keine HTML-Fehlerkorrektur. Das Profil
verlangt genau einen äußeren `div` oder `p` je XHTML-Wert. Blockelemente
stehen nicht in einem Absatz oder Inline-Element; verschachtelte Links
und texttragende `br`/`hr` sind unzulässig. Listen enthalten mindestens
ein `li`. Inline-Gruppen dürfen nicht
in Code oder in das reine alternative Textfeld eingeschleust werden.
Eine `div`-Gruppe mit direkt enthaltenem Inline-Inhalt wird als Absatz
geführt; gemischte Folgen werden in ihrer Reihenfolge in Absatz- und
Blockanteile zerlegt. Leere Gruppen bleiben im Quellmodell erkennbar.

Die Attributmenge der nativen Schnittmenge ist geschlossen:
`href` und optional `title` bei `a`, `data` und `type` bei `object`;
sonst keine fachlichen Attribute. `href`/`data` und `type` sind bei ihrem
jeweiligen Element erforderlich. Geordnete Listen der Schnittmenge
beginnen bei 1. Ein anderer nativer Startwert ist hier nicht darstellbar;
es wird weder ein `start`-/`value`-Attribut aus einem anderen XHTML-Modul
ergänzt noch eine abweichende Nummerierung still auf 1 zurückgesetzt.
`object` ist in der Prose-Schnittmenge exakt `type="image/png"` und
besitzt keine weiteren Attribute oder Kindelemente. Namespacebindungen
sind XML-Syntax, keine fachlichen Attribute; bloß gleiche Localnames
aus anderen Namespaces erfüllen dieses Profil nicht.

Weitere zulässige ReqIF-/XHTML-Inhalte wie Tabellen, Überschriften,
Sprache/Richtung, IDs, Abmessungen oder Formatattribute werden nicht
gelöscht, als Prose behauptet oder durch vermeintlich gleichwertigen
Plaintext ersetzt. Sie bleiben typisierte/passive Quelle und führen
zu konkreter Nichtrepräsentierbarkeit, soweit keine andere ausdrücklich
gebundene native Abbildung sie erhält. Insbesondere bleibt die native
Überschriftenquelle `section` unverändert. Das eingeschränkte Proseprofil
ändert weder das native Table-Block-Schema noch die ReqIF-Quellerhaltung.

**CommonMark-Projektion und Rückweg.** Ein ausdrücklich angeforderter
XHTML-Feldadapter liefert für einen vollständig darstellbaren Wert einen
CommonMark-String nach 10.14; dies ergänzt die Wertfamilien aus D.1.1.
Der allgemeine Mapper verwendet weiterhin die gebundene Feldzeile und
`value_map`; er entscheidet nicht selbst, ob ein Feld XHTML oder String
ist. Der strukturierte Quellbaum und alle Herkunftsangaben bleiben neben
der Projektion erhalten. Es gibt keinen automatischen Plaintext-Fallback.

Text wird nach der XML-Dekodierung behandelt, nicht erneut als Markup
oder Entity ausgewertet. XML-Zeilenendennormalisierung bleibt maßgeblich;
Unicode und Text innerhalb von Code/Pre bleiben erhalten. Außerhalb von
Code sind XML-Leerraumzeichen zwischen reinen Blockkindern Strukturraum,
in Inline-Inhalten bleiben sie Text beziehungsweise weiche Umbrüche.
Das Zusammenfassen benachbarter Textknoten darf deren Text nicht ändern.
Ein harter Umbruch bleibt von einem weichen Umbruch verschieden.
Der Serializer MUSS Markdown-Sonderzeichen und Delimiter so behandeln,
dass das erneute native Prose-Parsing dieselbe Knotenbedeutung, Texte,
Listennummerierung und Anhangbindung liefert. Kann ein konkreter Wert
diese Schnittmenge nicht verlustfrei treffen, ist er nicht repräsentierbar;
eine unbemerkte Textkürzung oder Strukturänderung ist unzulässig.

Der inverse Adapter verwendet das native Prosemodell sowie ausdrücklich
gebundene ReqIF-Definitionen und Anhangzuordnungen. Unveränderte importierte
Werte erhalten ihren Quellbaum einschließlich Default-Herkunft und
Vereinfachungsmetadaten. Für neu gebildete Werte ist die obige Kernmenge
deterministisch zu serialisieren; Präfix-/Escape-Schreibweisen sind keine
Identität. Fehlende oder mehrdeutige Rückbindungen sind konkrete Konflikte.
Identische Eingaben und Bindungen erzeugen identische Ausgabebytes.

**Anhänge, Grenzen und Nichtrepräsentierbarkeit.** `href` und `data`
lösen niemals selbst I/O aus. Zulässige relative Referenzen werden mit
ihrem nach XML-Dekodierung unveränderten Wert gegen eine ausdrücklich
gelieferte eindeutige Zuordnung auf tatsächliche Anhangbytes, SHA-256
und einen validierten nativen `attachments/`-Pfad geprüft. Fehlende
Bytes, abweichender Hash, konkurrierende Zuordnungen oder unaufgelöste
Referenzen verhindern eine erfolgreiche vollständige Projektion.
Ein behaupteter MIME-Typ beweist weder Byteformat noch Sicherheit.
Das vorhandene Anhangprofil bleibt maßgeblich; kein Decoder, Renderer
oder externes Programm wird zur Prüfung gestartet.

Unzulässig für die Auflösung sind absolute/Netzwerk-/Datei-/Daten-URLs,
Schemes, Laufwerks-/UNC-Pfade, Backslashes, Query/Fragment und leere,
`.`- oder `..`-Segmente. Prozentkodierungen dürfen solche Grenzen nicht
umgehen: höchstens eine strikte UTF-8-Dekodierung, danach keine übrigen
Prozentzeichen und erneute Pfadprüfung. Ein relativer ReqIF-Pfad muss
nicht bereits mit `attachments/` beginnen; erst sein ausdrücklich
gebundenes natives Ziel hat diese Wurzel. Es gibt keine Auflösung gegen
Arbeitsverzeichnis, Dateinamenraten, Netzwerk oder automatisches Nachladen.
ReqIFZ liefert dieselben Bindungen erst über den eigenen sicheren
Archivvertrag in 14.k; hier entsteht kein zweiter Entpacker.

Die sichere XML-Verarbeitung und Ressourcenfehler aus D.1.1/Anhang O
gelten für alle Teilbäume, auch Originalwerte, unbekannte Elemente und
Fallbacks. Skripte, Ereignisattribute, aktive URLs, externe Includes,
Style-Ausführung und DTD-/Entity-/Schemaauflösung sind keine zulässige
Projektion oder Ausweichlösung. Passive Erhaltung unbekannter Daten
erlaubt niemals deren Ausführung oder unkontrollierte HTML-Ausgabe.
Unsichere oder externe Inhalte und unaufgelöste Anhangreferenzen müssen
vor einem Import-Apply erkannt werden; eine Loss-Akzeptanz hebt keine
Sicherheitsgrenze auf.

Jede nicht vollständig darstellbare Struktur/Attributstelle MUSS einen
maschinenlesbaren Grund und den verfügbaren Element-/Definitionsbezug
oder XML-Pfad liefern, ohne komplette Nutztexte in Diagnosen zu kopieren.
Der Quellstand bleibt erhalten. Reine Projektionen dürfen keinen
uneingeschränkten Import-, Freigabe- oder Verlustfreiheitserfolg melden.
Fehlerklassen und Codes bleiben die aus D.1.1/10.12.1; nicht unterstützte
Darstellung wird nicht mit einer tatsächlich verletzten Sicherheitsgrenze
verwechselt. Der vollständige Verlustbericht, Erweiterungserhalt und
`fail-on-loss` bleiben gesonderte Abnahmen von 14.j, keine implizite
Datenverlustfreigabe dieses Profils.


### D.1.3 ReqIF-Erweiterungserhalt und Verlustbewertung v1

**Entscheidung REQIF-PRESERVATION-LOSS, delegiert gemäß SPECROAD-DECISION-1:**
Diese Regel präzisiert für 14.j den persistenten Erhalt aus SR-REQ-0322
und die dazugehörige Verlustbewertung. Sie ergänzt D.1.1/D.1.2 und 10.12.1;
SR-REQ-0018/0019, 0314, 0319, 0324 und 0332 bleiben wirksam. Es entsteht
kein neues natives Artefaktformat, kein neuer Mappingtabellentyp und keine
Loss-Akzeptanz oder Schreibfreigabe. Die folgenden Träger- und Berichtsregeln
sind SpecRoad-Entscheidungen, keine behauptete OMG-Erweiterung oder bereits
nachgewiesene Fremdtool-Kompatibilität.

**Drei getrennte Aussagen.** Unveränderte Bytes im Speicher des Decoders
sind zunächst nur Quellerhaltung. Persistenter Erweiterungserhalt erfordert
einen tatsächlich mitgeführten, validierten namespaced Nutzinhalt; native
Abbildung erfordert zusätzlich die fachliche Projektion. Eine Rohkopie DARF
NICHT als Beweis für ausgeführtes Mapping, gelöste Referenzen, vollständigen
Import oder erfolgreichen Apply gelten. Ein ausschließlich als Erweiterung
erhaltener Wert MUSS weiterhin als nicht nativ abgebildet erkennbar bleiben.

**Passiver Quellträger.** Für originale ReqIF-XML-Bytes wird der Schlüssel
`extensions["specroad.reqif"]` mit genau folgendem geschlossenen Wert
verwendet: `{"format_version":"reqif-preservation-v1","sources":[...]}`.
`sources` ist ein Array der folgenden geschlossenen Einträge. Andere
namespaced Extensions bleiben unverändert; ihre Werte werden weder als
ReqIF ausgelegt noch in diesen Schlüssel umbenannt.

| Feld | Vertrag |
|---|---|
| `source_system`, `source_document` | Ausdrücklich gelieferte nichtleere Strings des externen Quellkontexts, unverändert nach 10.12.1. Keine Ableitung aus Dateipfad, Header oder Arbeitsverzeichnis. |
| `external_revision` | Nichtleerer String oder ausdrücklich `null`; keine erfundene Revision und keine Änderung der externen Identitätsregel. |
| `source_sha256` | Vollständige kleingeschriebene SHA-256 der tatsächlichen originalen XML-Bytes. |
| `source_size` | Exakte Byteanzahl als nichtnegativer Integer, kein Boolean. |
| `source_base64` | Kanonische Standard-Base64-Kodierung dieser Bytes mit erforderlichem Padding, ohne Leerraum oder zusätzliche Daten. Strikte Dekodierung und erneute Kodierung müssen denselben String ergeben. |

Die Eintragskennung für Speicherung und Referenzierung ist das Tupel
`(source_system, source_document, external_revision, source_sha256)`.
Ein Träger enthält höchstens einen Eintrag je Tupel; doppelte eingehende
Einträge sind Fehler. Neue Ausgaben sortieren die Einträge nach den
RFC-8785-Bytes des Arrays dieser vier Tupelwerte. Bei einem ausdrücklich
angeforderten Zusammenführen mit vorhandenen Extensions ist ein bereits
vorhandener identischer Eintrag ein No-op; alle anderen bisherigen Einträge
und fremden Schlüssel bleiben erhalten. Unterschiedliche Quellstände,
auch bei gleicher oder fehlender externer Revision, werden nicht gegenseitig
überschrieben. Die Quellstandsliste ist eine passive Erhaltung, keine zweite
Identitätsregistry oder neue Importstrategie.

Ein vorhandener inkompatibler Wert unter `specroad.reqif`, konkurrierende
Eintragsdaten oder eine geänderte erwartete Zielbindung sind Konflikte.
Es gibt weder automatische Migration noch First-/Last-Wins oder Ausweichen
auf einen neu erfundenen Schlüssel. Die allgemeine native Extensions-
Validierung bleibt passiv: Ein solcher unbekannter Wert wird beim normalen
Lesen/Schreiben nicht allein wegen seines Namens ausgeführt oder umgeformt.
Die spezielle Prüfung erfolgt nur beim ausdrücklich angeforderten Gebrauch
des Trägervertrags.

Der Träger enthält das vollständige ursprüngliche XML-Dokument. Dadurch
bleiben auch unbekannte Namespacebindungen, Präfixe in fremden Werten,
Mischtext, Reihenfolge und Metadaten erhalten, ohne ihre Bedeutung zu raten.
Es gibt keine Fragment-Neuserialisierung unter geratenen Namespacebindungen.
Länge, Hash und ursprüngliche Bytes MÜSSEN vor erfolgreicher Erzeugung oder
Nutzung übereinstimmen. Für die XML-Prüfung ist derselbe sichere, begrenzte
Reader und das explizite Strukturprofil aus D.1.1/D.1.2 wiederzuverwenden;
der Aufrufer liefert die bestehenden Grenzen. Ein Träger umgeht keine
XML-, Typ-, Referenz-, Anhang- oder Sicherheitsprüfung. Die erwartete
Dekodiergröße ist vor einer unnötigen großen Base64-Allokation zu prüfen.
Reale Ressourcenfehler bleiben Fehler; es entsteht keine neue harte
Gesamtauftragsgrenze und kein Erfolg durch abgeschnittene Daten.

Der reine v1-Erhaltungsweg deckt diese beiden nachprüfbaren Formen ab:
einen vollständigen Quellträger in JSON-Zielbytes und die bytegleiche
Wiedergabe der ganzen XML-Quelle. Er behauptet keine allgemeine Prüfung
fremder XML-Fragmente in beliebig geänderten Ausgaben. Weitere fachliche
Abbildungen brauchen ihre bestehenden eigenen Vergleichsnachweise; fehlt
dieser Nachweis, wird Erhalt nicht geraten.

Die reine Trägerfunktion liefert Nutzdaten oder validierte Originalbytes;
sie schreibt weder Projektdateien noch Registries. Die spätere Einbindung
in ein vorhandenes `extensions`-Objekt verlangt einen ausdrücklich gebundenen
Besitzer und den gewöhnlichen Change Plan samt Zielvalidierung. Besitzer,
ID und Metadaten werden nicht aus einem ReqIF-Namen erraten. Bestehende
Extensions, Native-Payload-Hashes und historische Evidence werden durch die
Einführung des Formats nicht automatisch geändert.

**Rückweg und tatsächlicher Erhalt.** Ein unveränderter Quellstand kann
nach erneuter Bindungs- und Sicherheitsprüfung bytegleich wieder ausgegeben
werden. Das beweist einen originalen Quellroundtrip, keine Übertragung
zwischenzeitlicher nativer Änderungen. Geänderte native Felder dürfen nicht
stillschweigend durch den alten XML-Stand ersetzt werden. Für einen neuen
Export muss geprüft werden, welche Inhalte der konkrete Zielkandidat wirklich
transportiert. Eine nur in Dev, einem Cache, dem Auditbericht oder der alten
Quelldatei verbliebene Kopie zählt dabei nicht als Zielerhalt. Ist eine
verstandene und sicher gebundene Rückintegration in geänderte XML-Ausgabe
nicht möglich, bleiben die Ursprungsdaten erhalten und der betroffene
Zielverlust wird konkret ausgewiesen; keine automatische rohe XML-Injektion.

Referenzierte Anhangbytes sind nicht in XML-Base64 enthalten. Ihr Erhalt
verlangt die tatsächlichen, nach D.1.2 gebundenen Bytes und das vorgesehene
Zieltransportmittel. Ein erhaltener Pfad oder Hash allein ist kein erhaltener
Anhang. Fehlende oder unsichere Auflösung wird nicht als akzeptierter Verlust
übergangen. ReqIFZ verwendet weiterhin ausschließlich 14.k/Anhang O.

**Einzelbewertung und Identität.** Der Verlustbericht MUSS für den ausdrücklich
gebundenen Import- beziehungsweise Exportumfang jede nicht nativ abgebildete
Fachinformation entweder als tatsächlich erhalten oder als Verlust ausweisen.
Dazu gehören auch Mapping-Restfelder, nicht darstellbare Werte, fremde
Attribute/Teilbäume, Metadaten, Struktur-/Relationsdaten, XHTML-Originale und
nicht mitgeführte Anhänge. Eine Sammelmeldung „unbekannte Inhalte“ genügt nicht.
Ein vollständig opaker, zusammenhängend behandelter Teilbaum ist eine Einheit
mit allen seinen Attributen und Nachfahren. Bei teilweise abgebildeten
Containern werden unabhängige ausgelassene Attribute, Felder und Kindteilbäume
einzeln aufgeführt. Dieselbe Stelle wird für denselben Grund nicht doppelt
gezählt; verschiedene Gründe dürfen nicht still zusammenfallen.

Ein maschinenlesbarer Eintrag enthält mindestens `item_id`, `direction`
(`import` oder `export`), `source_sha256`, `source_context`, `location`,
`reason` und `disposition` (`preserved` oder `lost`). `source_context` ist
genau das Objekt mit `source_system`, `source_document`, `external_revision`
nach obigem Kontextvertrag. `source_sha256` bindet die vollständigen
Quellbytes der betreffenden Eingabeeinheit, auch bei nativen Exportquellen.
`reason` ist ein nichtleerer stabiler Maschinengrund, kein übersetzter Text.
Vorhandene Parser-/Mappinggründe werden nicht anhand ihrer Meldung klassifiziert.

`location` ist genau eine dieser geschlossenen Formen:

- XML: `{"kind":"xml","path":[...],"attribute":null}` bezeichnet einen
  Elementteilbaum. `path` enthält die nullbasierten Elementkind-Indizes vom
  Dokumentelement aus; `[]` bezeichnet die Wurzel. Text, Kommentare und
  Processing Instructions werden nicht als Elementkinder gezählt. Für ein
  einzelnes Attribut ist `attribute` stattdessen genau
  `{"namespace":"...","name":"..."}` mit expandiertem Namespace-URI
  (leer bei keinem Namespace) und tatsächlichem Localname. Die Stelle muss
  in den gebundenen, sicher geparsten Quellbytes vorhanden sein.
- Native JSON-Quelle: `{"kind":"json","pointer":"..."}` mit einem
  tatsächlichen RFC-6901-Pointer in der gebundenen Eingabeeinheit; `""`
  bezeichnet deren Wurzel. Metadaten dürfen nicht aus einem anderen Objekt
  oder Hash unter demselben Pointer übernommen werden.

`item_id` ist `reqif-item-` plus kleingeschriebene SHA-256 der RFC-8785-Bytes
des Objekts mit genau `direction`, `source_sha256`, `source_context`,
`location` und `reason`. Im Verlustfall ist `loss_id` identisch zu `item_id`.
Disposition, Berichtssortierung, Ausführungszeit und menschliche Texte sind
nicht Teil dieser Identität. Gleiche Eingabe/Bindung/Stelle/Grund ergibt
dieselbe Kennung; neue Quellbytes verlangen eine neue Bewertung und können
neue Kennungen ergeben. Es wird keine globale revisionsübergreifende
Loss-Identität behauptet. Einträge werden nach `item_id` sortiert.

`preserved` verlangt einen überprüften `preservation_ref` mit genau
`target_sha256`, `location` und `source_key`. Der Hash bindet die tatsächlichen
vollständigen Zielbytes der betreffenden Ausgabeeinheit; `location` verwendet
die obige XML-/JSON-Ortsform, jetzt bezogen auf diese Zielbytes. Bei einem
Quellträger zeigt der JSON-Pointer auf den konkreten `sources`-Eintrag und
`source_key` ist das Array seiner vier Tupelwerte; bei direkter unveränderter
Quellwiedergabe ist die XML-Position die Dokumentwurzel und `source_key=null`.
Der Prüfer MUSS die tatsächliche Byte-/Trägerübereinstimmung nachweisen;
übereinstimmende Hashfelder oder vom Aufrufer behauptete Statuswerte allein
genügen nicht. Bei einem noch nicht angewendeten Plan bezieht sich
dies ausschließlich auf dessen exakt gebundenen Kandidaten, nicht auf einen
behaupteten schon ausgeführten Write. Eine Quellkopie ohne diese Zielbindung
darf keine `lost`-Position in `preserved` umwandeln. Einträge und Diagnosen
enthalten keine kompletten Quelltexte oder Base64-Nutzinhalte; diese gehören
nur in den vorgesehenen Träger. Verfügbare Objekt-/Definitionskennungen dürfen
als Diagnosebezug ergänzt werden, ersetzen aber nicht die genaue Quellstelle.

**Vollständigkeit und fail-on-loss.** Berichte trennen mindestens die
maschinenlesbaren Aussagen `assessment_complete`, `loss_free` und
`native_projection_complete`. `assessment_complete` darf nur wahr sein,
wenn der gesamte ausdrücklich angegebene Umfang einschließlich seiner
Restdaten geprüft ist. Die Inventarisierung stammt aus den tatsächlich
gebundenen Quellen und der ausgeführten Abbildung, nicht ausschließlich aus
einer ungeprüften vom Aufrufer gelieferten Liste angeblich verlorener oder
erhaltener Stellen; eine Teilprojektion oder fehlende Voraussetzung
ergibt keine vollständige Bewertung. `loss_free` ist nur bei vollständiger
Bewertung und leerer Verlustmenge wahr. Ausschließlich im passiven Träger
erhaltene Inhalte können einen Verlust vermeiden, machen aber die native
Projektion nicht vollständig. Der Umfang und die Eingangs-/Mapping-/Zielbindung
müssen im Bericht sichtbar sein; ein Quellroundtrip wird nicht auf einen
Projektimport oder anders gebundenen Export verallgemeinert.

Bei `fail-on-loss=true` MUSS eine nichtleere Verlustmenge oder unvollständige
Bewertung mit Code 3 vor Veröffentlichung des Exportnutzinhalts abbrechen;
der maschinenlesbare Bericht bleibt verfügbar. Tatsächlich und sicher im
gebundenen Ziel erhaltene unbekannte Inhalte lösen allein keinen Verlustfehler
aus. Ein nicht gesetztes `--fail-on-loss` darf einen Export mit vollständig
ausgewiesenen Verlusten erlauben, aber keinen Verlust verschweigen oder
`loss_free=true` melden. Es akzeptiert weder einen Importverlust noch einen
Konflikt und autorisiert keinen Write. Die bisherigen strengeren Importplan-
und Apply-Grenzen bleiben unverändert. Passive Funktionen liefern weiterhin
keine `execution_ready`-/`write_authorized`-Freigabe.

Syntax-/Träger- und nicht repräsentierbare Formatfehler haben Code 3,
gebundene Quell-/Zielkonflikte Code 6, ungültige Aufrufkonfiguration Code 2
und Sicherheitsverletzungen Code 7. Bestehende spezifische Mappingfehler
behalten ihren Vertrag. Aktive Inhalte, DTD/Entities, externe Schemas,
Includes, Netzwerk-/Pfadauflösung und Host-Ressourcenfehler werden nicht
als gewöhnlicher Verlust umetikettiert. Keine Loss-Kennung, Rohkopie oder
Flag-Einstellung hebt diese Grenzen auf.

**Umsetzungsgrenze.** 14.j.W stellt zuerst einen nutzbaren passiven
Erhaltungs-/Rückweg mit überprüfbarer Zielbindung und Einzelbewertung bereit;
14.j.R vervollständigt Verlustabdeckung, Konflikt-/Sicherheitsränder und
fail-on-loss. Alle Zustände bleiben durch Verhaltenstests abgesichert.
14.j.C bereinigt nur die Struktur. Die vollständige CLI-/Projektintegration
und ReqIFZ behalten ihre Planstellen und bleiben bis zu ihren tatsächlichen
Nachweisen offen. Dieser Dokumentvertrag selbst ist keine Implementierung,
Loss-Akzeptanz, Produktabnahme oder Fremdtool-Konformitätsbescheinigung.

### D.1.4 ReqIFZ-Container und Anhangbindungen v1

**Entscheidung REQIFZ-CONTAINER-CONTRACT, delegiert gemäß SPECROAD-DECISION-1:**
Der folgende Vertrag konkretisiert `SR-REQ-0323` und `SR-REQ-0486` für
14.k.W/R/C. Er ergänzt D.1.1–D.1.3 um die Transporthülle und ihre expliziten
Byte-/Pfadbindungen. Das kanonische ZIP-Profil aus 10.16, die sicheren XML-
und Anhangregeln sowie alle Import-, Verlust- und Writegates bleiben wirksam.
Ein erfolgreicher Containerroundtrip ist kein vollständiger nativer Import.

**Container und Dokumentauswahl.** Ein ReqIFZ besteht aus genau den
übergebenen regulären Dateimitgliedern im gemeinsamen kanonischen ZIP-Profil.
Ein zusätzliches SpecRoad-JSON-Manifest im ZIP ist weder erforderlich noch
wird es automatisch ergänzt. Es gibt keinen reservierten Manifestnamen
und keinen vorgeschriebenen Namen wie `content.reqif`. Ein manifestartig
benanntes Mitglied bleibt gewöhnlicher passiver Nutzinhalt; seine Angaben
werden nicht als vertrauenswürdiges Containerinventar übernommen.
Die Manifestpflichten anderer Archivformate bleiben unverändert.

Der Aufrufer bindet eine nichtleere, duplikatfreie Liste exakter
Dokumentmitgliedpfade. Jedes gewählte Mitglied muss vorhanden sein und
mit dem bestehenden begrenzten ReqIF-Strukturparser nach D.1.1/D.1.2
erfolgreich geprüft werden. Dateiendung, ZIP-Reihenfolge und erster Treffer
ersetzen diese Auswahl nicht. Mehrere und in Unterverzeichnissen liegende
Dokumente sind zulässig. Ihre IDs, Quellkontexte und nativen Zuordnungen
werden nicht dokumentübergreifend geraten oder zusammengeführt.

Alle übrigen Mitglieder bleiben mit ihren vollständigen Originalbytes im
Inventar und im Byte-Rückweg erhalten, auch wenn kein gewähltes Dokument
sie referenziert. Sie werden nicht ausgeführt, gerendert, rekursiv entpackt
oder allein wegen ihrer Endung als weitere ReqIF-Dokumente interpretiert.
Die explizite Dokumentauswahl begrenzt die fachliche XML-Bewertung; sie
erlaubt keine Behauptung einer nativen Vollprojektion aller Archivdaten.

**Dokumentrelative Referenzen.** Für jedes gewählte Dokument werden alle
Anhang-/URI-Referenzen des bestehenden Sicherheitsprofils einschließlich
der entsprechenden Stellen in Originalwerten, Fallbacks und passiven
Erweiterungsteilbäumen geprüft. Schlüssel einer Bindung ist das Paar aus
Dokumentmitgliedpfad und nach XML-Dekodierung unverändertem Referenzwert.
Die strikte einmalige Prozent-/UTF-8-Dekodierung und die Verbote aus D.1.2
gelten unverändert. Der resultierende relative Pfad wird an das Verzeichnis
des ausgewählten XML-Mitglieds angehängt; bei einem Wurzeldokument an die
Archivwurzel. Der so gebildete sichere Pfad muss exakt und unter Beachtung
der Groß-/Kleinschreibung auf ein vorhandenes reguläres Mitglied zeigen.

Beispiel: `docs/a.reqif` mit `images/p.png` bindet ausschließlich
`docs/images/p.png`; weder `images/p.png` in der Archivwurzel noch ein
gleichnamiges Mitglied in einem anderen Verzeichnis ist ein Ersatz.
Eine Referenz `../images/p.png` bleibt auch dann unzulässig, wenn eine
Normalisierung innerhalb des Archivs enden würde. Es gibt keine Auflösung
gegen CWD, Netzwerk, externe Dateien, Basename-Suche oder Casefold-Fallback.
Fehlende beziehungsweise konkurrierende Bytebindungen sind Konflikte,
keine still akzeptierten Verluste. Ein als Dokument ausgewähltes Mitglied
darf zugleich als passive Anhangbytes referenziert sein; dies startet
keine rekursive Interpretation.

Containerbindungen liefern tatsächliche Mitgliedbytes, Größe und SHA-256.
Für eine native Anhangprojektion muss der Aufrufer zusätzlich die bereits
vorgeschriebene eindeutige Bindung auf einen validierten nativen
`attachments/`-Pfad und Anhangdeskriptor liefern. Besitzer, native Identität,
Zielpfad und MIME-Typ werden nicht aus ZIP-Namen oder XML-Behauptungen
erfunden. Die nativen Byte-/Hash-/MIME-Prüfungen aus D.1.2 bleiben erhalten.

**Abgeleitetes Transportmanifest.** Der reine Codec liefert neben den
geprüften Nutzbytes ein maschinenlesbares Manifest mit genau diesen Feldern:

| Feld | Verbindlicher Inhalt |
|---|---|
| `format_version` | Exakt `reqifz-container-v1`. |
| `archive_sha256` | Kleingeschriebene SHA-256 der tatsächlichen vollständigen ZIP-Bytes. |
| `entries` | Liste aller Mitglieder; jeder Eintrag besitzt genau `path`, `size` und `sha256`. `size` ist die tatsächliche nichtnegative Byteanzahl, `sha256` der Hash dieser vollständigen Mitgliedbytes. Sortierung nach UTF-8-Bytes von `path`. |
| `documents` | Liste der ausdrücklich ausgewählten und erfolgreich geprüften Dokumentpfade, nach UTF-8-Bytes sortiert. |
| `references` | Liste mit genau `document_path`, `reference` und `member_path` je Bindung. `reference` bleibt der XML-dekodierte Originalwert, `member_path` das exakt aufgelöste Ziel. Sortierung nach den UTF-8-Bytes dieses Feldtupels. |

Mehrfaches Auftreten derselben Referenz im selben Dokument erzeugt eine
Bindung; gleich geschriebene Referenzen verschiedener Dokumente bleiben
getrennt. Die Einträge und Referenzen entstehen aus der tatsächlichen
Byteprüfung und XML-Auswertung. Kein vom Aufrufer behauptetes Inventar
ersetzt diese Ableitung. Eine JSON-Repräsentation dieses Manifests verwendet
die bestehende kanonische JSON-Kodierung. Das Manifest liegt außerhalb des
ZIP-Byteumfangs, inventarisiert sich nicht selbst und erzeugt keinen
rekursiven Archivhash. Es ist vom fachlichen Exportmanifest aus 14.l und
vom Projektbundlemanifest getrennt. Zeitstempel, absolute Hostpfade,
erfundene Projektidentitäten und Freigabeflags gehören nicht hinein.

Der Leser verlangt die erwartete SHA-256 des vollständigen Archivs als
explizite Eingangsbindung; der Schreiber berechnet sie erst aus seinen
tatsächlichen Ausgabebytes. Die Auswahl und die abgeleiteten Bindungen
bleiben zusätzlich im Transportmanifest sichtbar. Gleiche Mitglieder,
Dokumentauswahl und Prüfparameter ergeben dieselben ZIP- und Manifestbytes.
Ein unveränderter, gültiger kanonischer Container wird beim Byte-Rückweg
ohne Umbenennen, XML-Neuserialisierung oder Entfernen von Mitgliedern
identisch reproduziert. Zurückgegebene Daten dürfen nicht durch spätere
Mutation einer übergebenen Sammlung ihre geprüfte Bindung verlieren.

**Sicherheits- und Ressourcengrenze.** Vor Rückgabe von Mitgliednutzinhalt
oder einer Materialisierung müssen das gesamte Inventar, alle Pfade,
Header und tatsächlichen Byteumfänge geprüft sein. Traversal und doppelte
oder kollidierende Ziele, einschließlich Datei-/Elternpfadkonflikten und
Casefold-Kollisionen im portablen Zielnamensraum, sind unzulässig. Die
bestehenden portablen Pfadregeln gelten auch für nicht referenzierte
Mitglieder. Directory Entries, Symlinks und Sonderdateien sind verboten.
Nichtkanonische Metadaten, Verschlüsselung, Kompression, widersprüchliche
lokale/zentrale Header, überlappende Datenbereiche, fremde Vor-/Nachlaufbytes
oder falsche CRC-/Größenwerte werden nicht durch Neupacken repariert.
Maßgeblich bleibt das gemeinsame Profil aus 10.16, keine zweite ZIP-Variante.

Der Aufrufer liefert eine positive ganzzahlige harte Grenze
`max_uncompressed_bytes` für die Summe der unkomprimierten Bytes aller
Mitglieder; boolesche Werte sind keine Größenangabe. Die Summe schließt
ausgewählte Dokumente, referenzierte Anhänge und übrige Mitglieder ein;
genau die Grenze ist zulässig, eine Überschreitung nicht. Behauptete Größen
werden vor einer daraus abgeleiteten großen Allokation geprüft und mit
den tatsächlichen Datenumfängen abgeglichen. Je ausgewähltem XML-Dokument
gelten zusätzlich die ausdrücklich gelieferten bestehenden `ReqIFLimits`.
Diese Archiv-/Parsergrenzen sind harte Sicherheitsgrenzen nach Anhang O,
kein still eingeführtes Gesamtauftragslimit. Weiche Arbeitsbudgets bleiben
fortsetzbar; echte Host-/Speicherfehler dürfen weder maskiert noch als
normaler Datenverlust oder erfolgreicher Teilcontainer ausgegeben werden.

Ungültige Aufrufparameter oder Dokumentauswahl haben Code 2; ein gewählter
Pfad ohne vorhandenes Mitglied, eine geänderte erwartete Archivbindung
oder eine fehlende Referenz-/native Bytebindung sind Konflikte mit Code 6.
Ungültiges ZIP-/ReqIF-Format und nichtkanonische Transportdaten haben
Code 3. Unsichere Pfade, Sonderdateien, aktive/externe XML-Inhalte und
überschrittene harte Expansions-/Parsergrenzen haben Code 7. Reale I/O-
und Hostfehler behalten ihre bisherigen Fehlerverträge. Bereits bestehende
Archiv-/Mapping-APIs ändern ihre Fehlerklassen durch diese Ergänzung nicht.
Kein Fehlerfall führt zu Extraktion, nativen Writes oder externem Nachladen.

**Umsetzungsgrenze.** 14.k.W liefert den nutzbaren reinen Container-
Roundtrip mit expliziter Dokumentauswahl, geprüften relativen Bindungen
und abgeleitetem Manifest; vorhandene Sicherheitsgates gelten schon in W.
14.k.R vervollständigt die negativen und Ressourcen-Grenzfälle, 14.k.C
bereinigt ausschließlich die gemeinsame Struktur. ReqIFZ und andere
Archivformate verwenden denselben kanonischen ZIP-Kern; ihre jeweiligen
fachlichen Manifestregeln bleiben darüber getrennt. Es entsteht kein
zweiter Entpacker. Vollständiger Exportumfang und Snapshotzeitpunkt bleiben
in 14.l, CLI-/Projektübernahme an ihren bisherigen Planstellen. Dieser
Dokumentvertrag ist keine Implementierung oder Fremdtool-Abnahme.


## D.2 CSV

- UTF-8;
- RFC-4180-Feldregeln;
- CRLF als Export-Zeilenende;
- Headerzeile verpflichtend;
- Mappingdatei bestimmt Typen und Listen;
- leere Zelle, fehlende Spalte und JSON-Null sind unterscheidbar zu konfigurieren.

### D.2.1 Explizites CSV-Profil v1

**Entscheidung CSV-PROFILE-CONTRACT, delegiert gemäß SPECROAD-DECISION-1:**
Dieser additive Vertrag konkretisiert SR-REQ-0325/0326 für 14.f. Die
Feld-/Quote-/Datensatzsyntax folgt [RFC 4180, Abschnitt 2](https://www.rfc-editor.org/rfc/rfc4180#section-2),
ergänzt um das bereits vorgeschriebene UTF-8-Profil und den verpflichtenden
Header. Konvertierung, Null-/Abwesenheitsregeln und Ressourcenbindung unten
sind SpecRoad-Regeln, keine behaupteten Vorgaben des RFC.

**Ressource und Auswahl.** `csv-profile-v1` ist eine eigene passive
JSON-Mappingressource unter `mappings/`, kein neues Feld und keine
Interpretation beliebiger Extensions in `exchange-mapping-v1`.
Ihr geschlossenes Objekt enthält genau folgende Pflichtfelder:

| Feld | Exakter Vertrag |
|---|---|
| `schema_version` | exakt `0.2.0` |
| `mapping_format_version` | exakt `csv-profile-v1` |
| `mapping_id`, `mapping_version` | dieselbe Kennungs-/SemVer-Syntax wie 10.12.1 |
| `mapping` | geschlossenes Objekt mit genau `mapping_id`, `mapping_version`, `sha256`; bindet eine tatsächlich gelieferte `exchange-mapping-v1`-Ressource mit `source_format: "csv"` nach 10.12.1 |
| `external_type` | exakt eine vorhandene externe Typkennung dieser Mappingressource; deren `artifact_type` ist der native Artefakttyp |
| `identity` | geschlossenes Objekt mit genau `column` und `kind`; `column` ist ein nichtleerer literaler Headername, `kind` exakt `native_id` oder `external_id` |
| `columns` | geordnetes Array der unten definierten Spaltenzeilen |
| `error_policy` | für v1 ausschließlich der ausdrücklich angegebene Wert `reject`; keine implizite Fehlerpolicy |
| `extensions` | namespaced, ausschließlich passive Daten nach dem bestehenden Extensionsvertrag |

Die Profilkennung `mapping_id@mapping_version` und der erwartete
RFC-8785-/SHA-256-Hash des gesamten Profils werden ausdrücklich ausgewählt;
Originalbytes erhalten zusätzlich ihren eigenen Bytehash. Auswahl und
Duplikatprüfung folgen 10.12.1: kein höchstes Profil, Dateinamenraten,
Netzwerkzugriff oder Default. Profil und gebundene Mappingressource haben
verschiedene exakte Schlüssel; sie dürfen vorhandene Ressourcen oder
Registry-Schlüssel nicht verdrängen. Beide tatsächlich geprüften
Ressourcenbindungen und Bytehashes sowie der Hash der unveränderten
CSV-Eingabebytes gehören zur Codec-Beobachtung. Eine Änderung des Profils
ist eine andere gebundene Eingabe, auch bei gleicher Inhaltsversionsnummer.
Ein späterer gespeicherter CSV-Importplan muss diese zusätzlichen Eingaben
ausdrücklich mitbinden; ein alter Plan ohne diese Bindung autorisiert keinen
neuen CSV-Import. Es gibt keine stillschweigende Änderung alter Planformate.

Jede Spaltenzeile hat exakt `column`, `external_field`, `codec`,
`empty_cell`, `missing_column`. Die ersten beiden sind nichtleere literale
Unicode-Strings. `column` und `external_field` sind jeweils eindeutig;
die Menge der `external_field` entspricht exakt den Quellfeldern der
ausgewählten Typzeile in `mapping.fields`. Reihenfolge wird allein durch
`columns` festgelegt. Feldnamen sind keine Pfade, Ausdrücke oder Muster.
Die bestehende Feldzuordnung und `value_map` bleiben ausschließlich in
der gebundenen Austauschmappingressource. CSV-Konvertierung erfolgt vorher,
nicht als neuer ausführbarer Mapping-Ausdruck.

`identity.column` darf zusätzlich als Feldspalte vorkommen, dann nur mit
dem String-Codec und `empty_cell: "value"`; ihr Wert bleibt trotzdem eine
nichtleere Identität. Sonst ist sie eine eigene Header-/Datenspalte. Native
IDs müssen das vorhandene ID-Profil erfüllen und bleiben unverändert;
externe IDs sind nichtleere exakte Strings. Es werden keine Identitäten
erzeugt oder aus Zeilennummern, Text oder Dateinamen geraten. Bei externen
Identitäten liefert die spätere Importplanung `source_system` und
`source_document` ausdrücklich nach 10.12; der Codec erfindet sie nicht.

**Zellcodecs.** `codec` ist genau eines der folgenden geschlossenen Objekte:

| Objekt | Konvertierung und Export |
|---|---|
| `{"kind":"string"}` | Exakte Zeichenfolge ohne Trimmen oder Unicode-Normalisierung; keine Auswertung von Formeln oder Pfaden. |
| `{"kind":"boolean"}` | Ausschließlich die Textwerte `true` und `false`; Export derselben Schreibweise. `1`, `0` oder lokalisierte Wörter sind keine Booleschen Werte. |
| `{"kind":"integer"}` | JSON-Ganzzahltext gemäß `-?(0\|[1-9][0-9]*)`, ohne zusätzliche Leerzeichen; Wert muss dem bestehenden kanonischen Zahlenvertrag genügen. Boolesche Werte sind keine Ganzzahlen. |
| `{"kind":"number"}` | Genau ein JSON-Zahlentoken ohne zusätzliche Leerzeichen; endliche Werte nach dem bestehenden JSON-/RFC-8785-Zahlenvertrag, keine lokalisierte Dezimalnotation, NaN oder Infinity. Export mit dem vorhandenen kanonischen Serializer. |
| `{"kind":"list","list_rule":"json-array-v1"}` | Genau ein striktes JSON-Array nach dem bestehenden JSON-/Zahlenvertrag. Die deklarierte Trennregel ist die JSON-Array-Grammatik mit Komma und JSON-Stringescaping. Kein heuristisches Splitten an Semikolon, Pipe oder Leerzeichen. Reihenfolge, Duplikate, leere Liste, leere Elemente und verschachtelte gültige JSON-Werte bleiben erhalten. Export als RFC-8785-Arraytext innerhalb einer regulären CSV-Zelle. |
| `{"kind":"typed-json-v1"}` | Die bereits für View-Zellen verwendete explizite Typhülle, siehe unten; Export ihrer RFC-8785-Bytes als Zelltext. |

`typed-json-v1` hat exakt `{"type":"missing"}` für ein fehlendes Feld,
sonst exakt `type` und `value`. `type` ist `null`, `boolean`, `number`,
`string`, `array` oder `object`, und `value` hat genau diesen JSON-Typ;
`null` verlangt `value: null`. Die bestehende kanonische Zahlen-/String-
und strikte JSON-Policy gilt auch rekursiv. Es gibt keine zusätzlichen
Member, doppelten JSON-Schlüssel, NaN oder Typkoerzision. Arrays in einer
Typhülle verwenden ebenfalls die JSON-Array-Trennregel; ein nackter
String `null` ist keine solche Hülle. `missing` wird als wirklich fehlender
Member in der dekodierten Feldmenge dargestellt, niemals als JSON-Null.
Diese Wiederverwendung verändert weder `view-csv-v1` noch vorhandene
View-Exportbytes oder deren gesonderte Metadaten-/Generated-Kennzeichnung.

`empty_cell` ist ausdrücklich `value`, `null` oder `error`. Nach dem
CSV-Unquoting gelten unquoted leer und `""` als dieselbe leere Zelle.
`null` liefert JSON-Null ohne anschließende Codec-Konvertierung; `error`
weist sie zurück. `value` führt den ausgewählten Codec aus: beim String
entsteht `""`, bei Boolean/Zahl/Liste ist leer kein gültiger Wert. Für
`typed-json-v1` ist ausschließlich `error` zulässig; Null, fehlend und der
leere String benötigen dort ihre exakten unterschiedlichen Typhüllen.
Es gibt keinen impliziten Nulltext und keine Nullbehandlung aufgrund der
CSV-Quoteform. `missing_column` ist ausdrücklich `error` oder `absent`;
`absent` lässt den zugehörigen externen Feldmember vollständig weg. Dies
betrifft eine im Header fehlende Feldspalte, keine zu kurze Datenzeile.
Die Identitätsspalte muss unabhängig davon immer vorhanden sein.

**Datei, Header und Zeilen.** Der Codec akzeptiert nur gültige UTF-8-Bytes;
ein einzelnes UTF-8-BOM ist ausschließlich ganz am Eingabeanfang erlaubt
und bleibt Teil des Eingabebytehashs. Export erzeugt niemals ein BOM.
Eine weitere oder innere U+FEFF-Zeichenfolge wird nicht als Signatur
entfernt, sondern wie gewöhnlicher Feld-/Headerinhalt behandelt. Kein
Encoding-, Separator- oder Header-Sniffing. Das Trennzeichen ist Komma,
das Quotezeichen `"`; Quotes innerhalb gequoteter Felder werden verdoppelt.
Datensatztrenner außerhalb von Quotes sind CRLF; der letzte Eingabedatensatz
darf ohne abschließendes CRLF enden. Export endet auch den letzten Satz
mit CRLF. Beginnt das erste Headerfeld mit U+FEFF, wird dieses Feld
beim Export zusätzlich gequotet; das echte Zeichen darf beim Rückimport
nicht mit einer BOM-Signatur kollidieren. Eingebettete CR, LF und CRLF in gequoteten Feldern bleiben exakt
erhalten, ohne Universal-Newline-Übersetzung. Die Textgrammatik folgt RFC
4180 mit UTF-8 statt Beschränkung auf druckbares ASCII; weitere C0-
Steuerzeichen und DEL sind keine rohen Textzeichen dieses Profils. Solche
Stringwerte sind über JSON-Escapes in expliziten JSON-Zellcodecs darstellbar.

Der erste Datensatz ist immer ein Header mit nichtleeren, exakt eindeutigen
Namen; leere Eingabe ist ungültig. Headernamen werden nicht getrimmt oder
normalisiert. Zusätzliche nicht im Profil genannte Spalten werden abgewiesen,
nicht still verworfen. Die Eingabe darf Profilspalten umordnen. Ein fehlender
Headername wird nur nach der zugehörigen `missing_column`-Regel behandelt.
Jeder weitere Datensatz hat exakt die Breite des tatsächlich vorhandenen
Headers. Auch eine leere Zeile wird nicht als Kommentar übersprungen.
Ein ausschließlich vorhandener Header repräsentiert null Datensätze.
Doppelte Identitätswerte in einer Datei sind Fehler; Zeilenreihenfolge
bleibt erhalten. Export schreibt die Identitätsspalte zuerst, danach die
Profilspalten in deklarierter Reihenfolge, ohne eine mitbenutzte Identitäts-
spalte zu verdoppeln. Er verwendet minimales RFC-Quoting für Komma, Quote,
CR und LF; ein einzelnes leeres Feld als vollständiger Satz wird gequotet.

**Semantik und Fehlergrenze.** Lesen liefert ausschließlich eigene passive
Datensätze mit expliziter Identitätsart/-wert, festem externem Typ und
typisierten externen Feldern. Schreiben erhält genau solche Datensätze
und dieselbe gebundene Profilauswahl; weder unbekannte Felder noch fehlende
Identitäten dürfen verschwinden. Ein Wert ist nur repräsentierbar, wenn
die gewählte Kodierung ihn beim Dekodieren mit gleichem Typ und gleicher
Feldpräsenz reproduziert. Insbesondere darf ein fehlender Member nicht als
leere Zelle exportiert werden; per Zeile fehlende Werte benötigen den
`missing`-Tag. Null ist nur über `empty_cell: "null"` oder den Null-Tag
darstellbar. Bei `empty_cell: "null"` ist ein leerer String im String-Codec
nicht repräsentierbar und muss abgewiesen werden. Exportfehler erzeugen
keine teilweise veröffentlichten Ausgaben. Es wird keine Rundreise aller
SpecRoad-Inhalte behauptet, sondern nur des expliziten Schnittmengenprofils.

Die native Projektion verwendet anschließend unverändert 10.12.1. Ein vom
Codec korrekt als fehlend erkanntes, im Austauschmapping erforderliches
Quellfeld bleibt dessen Fehler; es wird nicht mit null ergänzt. Ein nativer
Export in diesen externen Mappingraum darf eine `value_map` nur invertieren,
wenn der konkrete Zielwert genau einen kanonisch passenden externen Wert
hat. Kein Treffer oder mehrere Treffer sind nicht repräsentierbar; auch
hier kein Raten und keine stille Auswahl der ersten Tabellenzeile.
Verluste außerhalb des deklarierten Schnittmengenprofils bleiben Gegenstand
des bestehenden Verlustberichts und gewähren keine Verlustzustimmung.

Ungültiges Profil, falsche Bindung, UTF-8-/CSV-/Header-/Breitenfehler,
ungültige Typkonvertierung, Identitätskollision und nicht repräsentierbarer
Export werden unter `reject` als `SRV090`/Code 3 diagnostiziert. Der Bericht
benennt einen maschinenlesbaren Grund sowie die betroffene Ressourcenbindung
und, soweit ermittelbar, logische Datensatznummer (Header 1) und
Spaltennummer (erste Spalte 1);
rohe Zellen, sensible Werte oder vollständige Eingaben werden nicht als
Fehlermeldung gespiegelt. Es gibt keinen erfolgreichen Teilerfolg, Skip,
Defaultwert, Reparaturversuch, implizite Verlustannahme oder automatischen
Retry. Bereits gebundene Rohbytes bleiben erhalten. Sicherheit, adaptive
Ressourcenbudgets und notwendige vollständige Verarbeitung nach Anhang O/P gelten
unverändert; eine technische Grenze darf nicht als vollständiger Import
ausgegeben werden. Unerwartete Programmierfehler werden nicht maskiert.

Der Codec liest keine aus Daten abgeleiteten Pfade und führt keine
Formeln, Hooks oder Fremdprogramme aus. Er erzeugt keinen Change Plan,
keine IDs, Revisionen, Autorisierung, Projektwrites oder Recoveryaktionen.
Die spätere CSV-Anbindung an Import/Export behält alle bisherigen aktuellen
Ziel-/Gate-/Actor-/Request-/Verlust- und Transaktionsgrenzen. Bestehende
Mapping- und Registrybytes bleiben gültig für ihren bisherigen Vertrag;
ohne ausdrücklich bereitgestelltes CSV-Profil sind sie keine Erlaubnis zu
CSV-Typinferenz. Es findet keine automatische Datenmigration statt.


## D.3 NDJSON

- UTF-8 und LF;
- genau ein JSON-Objekt pro nichtleerer Zeile;
- jede Zeile besitzt `format_version` und `object_kind`;
- Kommentare, trailing commas und mehrzeilige JSON-Objekte sind unzulässig.

### D.3.1 Versionierte Objekthülle und Stromabschluss v1

**Entscheidung NDJSON-OBJECT-CONTRACT, delegiert gemäß SPECROAD-DECISION-1:**
Der folgende additive Vertrag konkretisiert SR-REQ-0327 und D.3 für den
passiven Transport nativer Artefakte und regulärer Change Plans. Er erweitert
weder deren native Schemata noch die Berechtigung zu Import oder Ausführung.

**Geschlossene Zeilenhülle.** Jede nichtleere Zeile MUSS genau ein
JSON-Objekt mit exakt den folgenden drei Pflichtfeldern enthalten:

| Feld | Vertrag |
|---|---|
| `format_version` | String, exakt `1.0.0`; eigenständige Version der NDJSON-Hülle, keine Produkt-, Artefakt- oder Change-Plan-Version |
| `object_kind` | String, exakt `artifact` oder `change_plan` |
| `object` | Genau ein vollständiges natives JSON-Objekt der ausdrücklich gewählten Art |

Weitere Hüllenfelder, fehlende Felder, andere Versionen, andere
Discriminatorwerte, Arrays oder Skalare anstelle der Hülle oder von `object`
sind Fehler. Ein direktes natives Objekt ohne Hülle ist kein v1-Datensatz.
Weder Feldähnlichkeit noch Dateiname, Reihenfolge, ID oder Mapping erlauben
es, `object_kind` zu erraten. Eine Payload erhält keine Kopie der äußeren
Transportfelder; die Hülle wird beim Entpacken vollständig entfernt.

Für `artifact` MUSS `object` ein natives Artefakt einschließlich
`schema_version`, `artifact_type` und aller gemäß dessen bestehendem
Common-/Domain-/Record-Vertrag erforderlichen Felder sein. Der Decoder
MUSS die vorhandene projektfreie, typspezifische Feld- und lokale
Konsistenzvalidierung anwenden; allein die Common-Field-Prüfung reicht
nicht aus. Alle im Core unterstützten Artefakttypen bleiben darstellbar;
nicht unterstützte Typen oder Schemaversionen werden nicht migriert.

Für `change_plan` MUSS `object` ein vollständiger regulärer Change Plan
nach 10.1/10.2 und K.2 einschließlich seiner eigenen `format_version`,
`metadata_policy_version` und `change_plan_sha256` sein. Der vorhandene
passive Change-Plan-Validator MUSS Feldverträge, lokale Bindungen,
Operationen, Ergebnishashes und Selbsthash prüfen. Die äußere Version
`1.0.0` ersetzt insbesondere nicht die innere Planversion `1.2.0`.
Ein Planentwurf ohne Selbsthash, ein Import-/Merge-/Restore-/Work-Plan
oder ein Proposal anstelle des regulären Plans wird nicht durch
Transport in einen ausführbaren Change Plan umgewandelt. Ein natives
Proposal darf weiterhin als `artifact` transportiert werden.

**Erhaltung und Determinismus.** Der Codec MUSS sämtliche nativen Werte
und ihre Feldpräsenz erhalten, einschließlich verschachtelter Extensions,
Sprach-/Verbindlichkeitsangaben, geordneter Beziehungen und Operationen,
externer Identitäten, IDs, Revisionen, Akteure und normativer Zeitstempel.
Er ergänzt keine Defaults, keine neue Identität, keine Revisions-/Zeitwerte,
keine Provenienz und keinen erneuerten Selbsthash. Abwesenheit und `null`
bleiben verschieden. Strings werden nicht Unicode-normalisiert und nicht
als Ausdruck, Loader oder Befehl interpretiert. Es gelten die bestehenden
JSON-/Zahlen- und RFC-8785-Verträge; keine tolerante Ersatzkonvertierung.

Ein Export MUSS je Objekt die RFC-8785-Bytes der vollständigen Hülle plus
genau ein LF ausgeben, ohne BOM, Header-, Manifest- oder Kommentarzeile.
Er MUSS die ausdrücklich gelieferte Objektreihenfolge und Mehrfachvorkommen
erhalten; insbesondere wird nicht nach ID sortiert, dedupliziert oder
zusammengeführt. Ein leerer Objektstrom erzeugt null Bytes. Dieselben
zulässigen Objekte in derselben Reihenfolge ergeben dieselben Ausgabebytes.
Der semantische Roundtrip erhält die nativen Objekte; er verspricht nicht,
eine nichtkanonische Eingabe mit ihrer ursprünglichen Einrückung zu exportieren.
Originale Eingabebytes und ihr Bytehash bleiben für Provenienz und spätere
Planbindung separat erhalten. Der native Change-Plan-Selbsthash wird
weiterhin ausschließlich über den inneren Plan nach 10.1 geprüft; die
Transporthülle gehört weder zu diesem Hash noch zur nativen Modellwurzel.

**Framing und Ende.** Eingabe ist strikt UTF-8 ohne BOM. Nur das Byte LF
trennt Zeilen; CR beziehungsweise CRLF als physische Zeilenenden sind in
diesem LF-Profil nicht zulässig. Escaped CR/LF innerhalb von JSON-Strings
und andere zulässige Unicode-Zeichen innerhalb von Strings bleiben Daten.
Ein U+FEFF innerhalb eines JSON-Strings ist kein Transport-BOM. Eine leere
Zeile enthält vor ihrem LF null Bytes und MUSS ignoriert werden; eine nur
aus Leerzeichen oder Tabs bestehende Zeile enthält kein JSON-Objekt und
ist ein Fehler. Führende/nachgestellte Leerzeichen (U+0020) oder Tabs (U+0009)
einer ansonsten gültigen Objektzeile sind zulässig; rohe CR-Bytes bleiben
ausgeschlossen. Kommentare, nachgestellte Kommata,
doppelte Schlüssel in beliebiger Tiefe, mehr als ein Objekt auf einer
Zeile, rohe Zeilenumbrüche innerhalb eines Objekts und ungültige JSON-Werte
MÜSSEN abgewiesen werden. Kommentarähnlicher Inhalt in Strings bleibt Text.

Der letzte Datensatz DARF beim tatsächlichen Ende der Eingabe ohne LF
enden, sofern er ein vollständiges gültiges Hüllenobjekt ist. Ein offener
String, ein unvollständiges UTF-8-Zeichen oder sonstiges unvollständiges
letztes Objekt ist ein Fehler, kein still ignorierter Rest. Ein leerer
Transportblock, eine vorübergehende Pause oder eine Blockgrenze ist kein
Eingabeende. Kleine Transferblöcke dürfen UTF-8-Zeichen, Escape-Sequenzen,
Zahlen und Zeilen beliebig teilen; erst eine vollständige Zeile oder das
explizite tatsächliche Ende entscheidet über den Datensatz. Zeilennummern
zählen physische Zeilen ab eins, einschließlich ignorierter Leerzeilen.

**Passive Verarbeitung und Vollständigkeit.** Ein Stream DARF Artefakte
und Change Plans mischen. Ein bereits gelesenes gültiges Präfix ist nur
eine partielle Beobachtung und DARF NICHT als erfolgreicher Gesamtimport,
vollständige Ausgabe, gültiger Gesamtplan oder Schreibberechtigung gelten.
Ein Fehler in einer späteren Zeile bleibt ein Fehler des Gesamtstroms;
es gibt keine Skip-/Reparaturpolicy für fehlerhafte Objekte. Der Decoder
MUSS einen maschinenlesbaren Grund und die physische Fehlerzeile ausweisen,
für Feldfehler zusätzlich einen JSON-Pointer relativ zur gesamten Hülle
(innere Felder beginnen mit `/object`). Er kopiert keine Payloadwerte in
Diagnosen. Format-/Schema-/lokale Bindungsfehler sind Code 3;
Sicherheits-, Ressourcen- und aktuelle Modellkonflikte behalten ihre
bestehenden gesonderten Klassen nach 11.8.

Die Transportprüfung löst keine Referenzen aus dem Projekt oder Netz auf,
lädt keine Schemas über Nutzdaten-URLs und führt keine Operation aus.
Sie schreibt keine normativen Dateien, Journale oder Receipts und erzeugt
keine Freigabe. Globale Graph-/Scope-, Basis-, Lifecycle-, Actor-,
Review-, Verlust-, Importmapping- und Transaktionsprüfungen bleiben vor
einem tatsächlichen Import beziehungsweise Apply unverändert erforderlich.
Gleichlautende IDs mehrerer Datensätze dürfen vom Codec nicht versteckt
werden; ein etwaiger Konflikt wird in der nachgelagerten Fachstufe erkannt.
SR-REQ-0316/0319/0328–0332 und 0723 bleiben verbindlich. Insbesondere
bleibt ein vollständiges Exportmanifest Pflicht; seine separate Lieferung
berechtigt nicht zu einer zusätzlichen Manifestzeile im Objektstrom.
Diese Präzisierung führt weder ein neues Manifestformat noch eine
CLI-Option oder eine implizite Mappingauswahl ein.

Gesamtobjektzahl und Gesamtbytes sind keine neuen harten Grenzen. Große
Zeilen und Ströme sind gemäß Anhang O/P vollständig und sparsam zu
verarbeiten; vorhandene Sicherheits-/Parsergrenzen bleiben wirksam.
Gesicherte Fortsetzung MUSS den unveränderten Eingabestand, die nächste
physische Zeile und noch unvollständige Zeilenbytes binden. Bestätigte
Objekte dürfen weder doppelt geliefert noch übersprungen werden. Eine
Fortsetzung oder ein benötigtes gesichertes Präfix ersetzt keinen
Stromabschluss; eine Datei wird erst nach vollständiger Prüfung atomar
als erfolgreiche generierte Ausgabe veröffentlicht. Eine Umsetzung darf
bestehende Work-/Streamingmechanismen verwenden, aber keinen ungebundenen
Cursor oder eine neue Nebenwirkung im reinen Codec einführen.

**Bestand und Umsetzung.** Native Artefakte, reguläre Pläne und bestehende
Austauschmappingressourcen bleiben byte- und semantikgebunden nach ihren
bisherigen Verträgen. Es gibt keine automatische Migration oder neue
Interpretation historischer Daten. Das neue Zeilenformat wird ausdrücklich
als v1 verwendet. Diese normative Festlegung behauptet noch keinen
verfügbaren NDJSON-Codec, Schemaeintrag, CLI-Befehl oder Produktnachweis;
die Implementierung und ihre W/R/C-Abnahmen bleiben in 14.g offen.

## D.4 JUnit-Kernprofil

Unterstützt werden `testsuites`, `testsuite`, `testcase`, `failure`, `error`, `skipped`, `system-out`, `system-err` sowie die Attribute `name`, `classname`, `file`, `line`, `time`, `timestamp`, `tests`, `failures`, `errors`, `skipped`. Unbekannte Elemente werden nicht normativ interpretiert und können als Originalanhang erhalten werden.

## D.5 SARIF-Evidence-Profil

Unterstützt werden SARIF 2.1.0 `runs`, `tool.driver`, `invocations`, `artifacts`, `rules` und `results`. Nur ein Mapping darf bestimmen, welche Resultate welchen Test-, Verification- oder Requirement-IDs zugeordnet werden. Ein SARIF-`level` allein beweist kein Pass-Kriterium.

---

# Anhang E — Normatives Bundle- und ZIP-Profil

## E.1 Manifest

Jedes Bundle enthält genau einmal die kanonisch nach RFC 8785 serialisierte UTF-8-Datei `bundle-manifest.json` an der durch die lexikografische ZIP-Eintragsreihenfolge bestimmten Position. Sie besitzt die geschlossene Feldmenge nach E.1.1: `bundle_format_version`, `bundle_kind`, `read_only`, `project_id`, Tool- und Schema-Version, `scope_descriptor`, Ursprungmodellwurzel, Bundlemodellwurzel, Profil-/Konfigurationshash, `entries`, Boundary References, bewusste Ausschlüsse und `idempotency_scope`. Projekt- und partielle Kennzeichnung folgen ausschließlich E.3.

Die **Hashdomänen sind nicht rekursiv**. `entries` listet genau alle tatsächlichen regulären ZIP-Dateieinträge **außer `bundle-manifest.json`**. Für jeden gelisteten Eintrag stehen `path`, `size`, `media_type` und `sha256` fest. Fachliche Dateien und separat transportierte Betriebsdateien gehören beide in diese Liste; ungebündelte Inhalte dagegen nur in die Ausschlussdeklaration. Die Liste ist nach Pfad-UTF-8-Bytes sortiert, duplikatfrei und eine exakte Bijektion zur Payloadmenge. Das Manifest enthält weder seinen eigenen Bytehash oder seine eigene Größe noch den Hash der gesamten ZIP-Datei. Der Voll-ZIP-Hash wird ausschließlich außerhalb des Bundles geführt, etwa im Versandbeleg oder als erwarteter Eingangsparameter.

Ein extrahiertes Manifest wird beim erneuten Bündeln nicht als normale Projektpayload aufgenommen; das neue Manifest wird aus dem tatsächlich ausgewählten aktuellen Stand erzeugt. Die Modellwurzel umfasst ausschließlich die in 10.8–10.9 definierten normativen Inhalte, niemals Manifest, ZIP-Container oder Betriebssektion. Eine in einem manifestierten Snapshot erforderliche Archivdatei bleibt normale gehashte Payload.

`bundle verify` vergleicht die ZIP-Eintragsmenge mit `entries` plus genau diesem einen Manifest und prüft für jede Payload die tatsächliche Bytelänge und SHA-256. Danach werden semantische Projektwurzel, Scope Descriptor, Typkombination und Closure unabhängig aus den Payloadbytes rekonstruiert. Der exakt abgeleitete Prüfkontext nach E.3.2 gehört zur Transportprüfung, nicht zu Seeds oder fachlichen Modellressourcen. Ein selbstreferenzierender `entries`-Eintrag für das Manifest, fehlende/zusätzliche Payload, Dubletten oder inkonsistente Metadaten sind Fehler. Der manifestlose oder mehrfach manifeste Container ist ungültig.

Das optionale `--expected-sha256 <HASH>` bei `bundle verify`, `bundle extract` und einer Bundle-Restore-Quelle vergleicht zusätzlich vor Extraktion beziehungsweise Veröffentlichung den Voll-ZIP-Hash mit einem außerhalb der Datei erhaltenen erwarteten Wert. Eine Manifeständerung kann durch interne Widersprüche auffallen; eine konsistente Neubeschreibung samt passenden Nutzdaten ist ohne externe Erwartungsbindung **nicht** als Manipulation einer bestimmten früheren Datei erkennbar. Selbstkonsistenz ist kein Authentizitätsnachweis. Bereits an Auftrag, Work-Manifest oder Restore-Plan gebundene Bundle-Hashes sind verpflichtend, nicht optional. Unpassende erwartete Bytes werden als Integritätsfehler Code 3/SRV060 abgewiesen.

### E.1.1 Geschlossener Manifestvertrag v1

**Entscheidung BUNDLE-MANIFEST-CONTRACT, delegiert gemäß
SPECROAD-DECISION-1:** Die folgenden Regeln präzisieren die bereits geforderten
Metadaten und Hashdomänen für 15.a. Sie ersetzen weder die Scope-/Closure-
Prüfung noch die vollständige Projekt-/Teilbundleprüfung in E.3. Das
Projektbundlemanifest ist kein Exportmanifest nach 10.12.3, kein Work-Manifest
nach P.3 und kein äußeres Transportmanifest nach Anhang W.

**Form und Version.** `bundle-manifest.json` ist genau ein UTF-8-JSON-Objekt
in RFC-8785-kanonischen Bytes, ohne BOM, Kommentare oder zusätzliche Daten.
Doppelte JSON-Schlüssel, unbekannte Felder, falsche JSON-Typen und nicht
kanonisch darstellbare Zahlen werden abgewiesen. Alle folgenden Felder sind
Pflicht; ein fehlender Wert wird nicht durch einen geratenen Default ersetzt.
Die geschlossene Feldmenge für `bundle_format_version=1.0.0` lautet exakt:

| Feld | Exakter Vertrag |
|---|---|
| `bundle_format_version` | String `1.0.0`. Andere Formatversionen liegen außerhalb dieses v1-Supports. |
| `bundle_kind` | String `project` oder `partial`, ausschließlich mit der Kombination aus E.3. |
| `read_only` | JSON-Boolean gemäß E.3, keine Zahl und kein String. |
| `project_id` | Unveränderte gültige Projekt-ID der enthaltenen `specroad.json`; kein Hostpfad und keine neue Transfer-ID. |
| `tool_version` | Nichtleerer UTF-8-String mit der tatsächlichen Version des erzeugenden SpecRoad-Builds. Die Version ist Provenienz, keine Freigabe. Eine andere Toolversion allein macht ein ansonsten unterstütztes Format nicht ungültig. |
| `schema_version` | String `0.2.0` für diesen Bundlevertrag. Dies bezeichnet das native Projekt-Zielschema, nicht die Dokumentversion dieser Spezifikation und nicht eine Umschreibung geschützter Legacy-Ressourcen. |
| `scope_descriptor` | Vollständiger kanonischer Descriptor nach 10.8 und E.3 einschließlich aller dort vorgeschriebenen Felder; keine eigenen Kurzformen oder Aliase. |
| `origin_model_root_sha256` | Vollständiger kleingeschriebener 64-stelliger SHA-256 der nach 10.8–10.9 berechneten unkonfigurierten, geschlossenen Projektwurzel des Ursprungsstands. |
| `bundle_model_root_sha256` | Vollständiger kleingeschriebener 64-stelliger SHA-256 der nach 10.8–10.9 berechneten normativen Modellwurzel des vollständig aufgelösten `scope_descriptor`. |
| `profile_sha256` | Vollständiger kleingeschriebener 64-stelliger SHA-256 des effektiven Profilwerts, der auch in dieser Bundlemodellwurzel gebunden ist; Komposition unverändert nach 10.10 und Anhang S. |
| `configuration_sha256` | Vollständiger kleingeschriebener 64-stelliger SHA-256 der effektiven semantischen Konfiguration dieser Bundlemodellwurzel. Bei ausgewählter Produktkonfiguration sind deren Werte und Parent-Kette nach 10.18 gebunden; sonst gilt die semantische Projektkonfiguration nach 10.9. Nicht der rohe Dateihash von `specroad.json`. |
| `entries` | Die unten festgelegte vollständige, nach Pfad-UTF-8-Bytes sortierte Payloadliste. |
| `boundary_references` | Geordnete, duplikatfreie Liste der tatsächlich aus der Closure nach 10.8 erzeugten Boundary References. Ihre vorhandenen Feld-, Identitäts- und Zielhashverträge bleiben unverändert; ein `project`-Bundle hat die leere Liste. |
| `excluded_contents` | Die unten festgelegte geordnete Liste tatsächlich bewusst ausgelassener Quellpayloads, auch leer zulässig. |
| `idempotency_scope` | String `portable` oder `local_only` mit den nachfolgenden Bedingungen; kein aus Dateimenge oder ZIP-Größe erratener Wert. |

Für ein `project`-Bundle sind Ursprungs- und Bundlemodellwurzel gleich. Ein
`partial`-Bundle bindet die tatsächlich berechnete Ursprungswurzel und seine
getrennte Teilmodellwurzel. Der Reader rekonstruiert seine Bundlemodellwurzel
und die enthaltenen Profil-/Konfigurationsbindungen aus den Payloadbytes.
Die vollständige Ursprungswurzel eines Teilbundles lässt sich aus den bewusst
fehlenden Ursprungsbytes allein nicht erneut berechnen; sie bleibt eine
Provenienzbindung, kein Vollprojektnachweis. Boundary References ersetzen nur
die nach 10.8 zulässigen schwachen Außenkanten. Fehlende starke Ziele oder
notwendige Ressourcen bleiben Fehler, auch bei vorhandener Ausschlusszeile.

**Payloadinventar.** Jeder `entries`-Eintrag hat exakt `path`, `size`,
`media_type` und `sha256`. `path` ist der tatsächliche sichere ZIP-Mitgliedspfad
nach E.2; er wird nicht normalisiert, um einen ungültigen Namen zu reparieren.
`size` ist eine nichtnegative, RFC-8785-exakt darstellbare JSON-Ganzzahl, kein
Boolean. Sie und der kleingeschriebene 64-stellige `sha256` werden über die
unveränderten tatsächlichen Payloadbytes ermittelt. Die E.1-Bijektion gilt
auch für leere Dateien, benötigte Archivobjekte und separat transportierte
Betriebsdateien. Ein behaupteter Hash ohne seine erforderlichen Bytes genügt
nicht. Jeder Pfad kommt genau einmal vor.

Für diese Transportliste gilt die bereits vom gemeinsamen Archivcodec
verwendete deterministische Medientypklassifikation: exakt
`application/json` bei der groß-/kleinschreibungssensitiven Pfadendung `.json`,
sonst `application/octet-stream`. Dies ist keine MIME-Erkennung oder Änderung
des Inhalts. Fachlich deklarierte Anhangmedientypen bleiben unverändert in
ihren nativen Deskriptoren und in der Modellwurzel gebunden; die gröbere
Transportklassifikation ersetzt diese Deskriptoren nicht.

Das Manifest selbst erscheint weder in `entries` noch in `excluded_contents`.
Ein ausdrücklich als normale Payload angeliefertes Rootmanifest ist ein
rekursiver Manifestfehler. Bei erneuter Bündelung eines extrahierten Projekts
wird dessen bisheriges Rootmanifest bereits bei der Auswahl als nicht
fachliche Metadatei ausgeschlossen und das neue Manifest aus dem aktuellen
geprüften Stand erzeugt. Das ist keine Erlaubnis, notwendige Archivdateien
oder geschützte historische Originalbytes zu entfernen. Es gibt im Manifest
kein Feld für den eigenen Bytehash, die eigene Größe oder den Voll-ZIP-Hash.

**Bewusste Ausschlüsse.** Jeder `excluded_contents`-Eintrag hat exakt `path`
und `reason`. Der Pfad bezeichnet eine tatsächlich bekannte, nicht als Payload
aufgenommene Quelldatei, folgt denselben sicheren relativen Pfadregeln und ist
in dieser Liste eindeutig. Die Liste wird nach Pfad-UTF-8-Bytes sortiert.
Zulässige Gründe sind `outside_scope` für einen nach dem vollständigen
Descriptor ausgeschlossenen normativen Inhalt eines Teilbundles,
`operational_receipts_excluded` für bewusst nicht transportierte abgeschlossene
Receipts und `unreferenced_archive_object` für ausdrücklich optimierte,
nachweislich unreferenzierte Archivobjekte. Eine Ausschlusszeile darf nicht
zugleich in `entries` vorkommen. Fehlende Pflichtpayload wird niemals durch
einen Ausschluss geheilt. Beliebige Repositorydateien außerhalb des gewählten
Projekt-/Betriebsumfangs, lokale Konfigurationen fremder Werkzeuge, Caches,
aktive Journale, Locks und Staging werden dafür nicht inventarisiert oder
als erfolgreiche portable Daten aufgenommen. Ungelöste Transaktionen bleiben
der Blocker aus 10.16.

**Idempotenzgrenze.** Ein vollständiges `project`-Bundle verwendet
standardmäßig `portable`: Es muss alle nach 10.16 und SR-REQ-0487 erforderlichen
abgeschlossenen Request- und Transaktionsreceipts in der getrennten
Betriebssektion mit exakten Payloadhashes enthalten. Eine tatsächlich vollständig
geprüfte leere Receiptmenge ist zulässig; fehlende Prüfung ist keine leere Menge.
Bei `--exclude-operational-receipts` ist der Wert zwingend `local_only`; die
bewusst ausgelassenen vorhandenen Receipts werden deklariert. Ein `partial`-
Bundle verwendet ebenfalls `local_only` und übernimmt keine portable
Write-Idempotenz oder abgeschlossene Projekt-Receipts als solche. Das ändert
weder sein Writeverbot noch die Pflicht zur erneuten Projekt-/Request-/Hashprüfung
bei Übernahme gültiger Receipts aus einem verifizierten Vollbundle. Das Flag
allein beweist keine erfolgreiche Übernahme. Auswahl und Transfer der
Betriebssektion werden in den bestehenden nachfolgenden M15-Schritten umgesetzt.

**Deterministik, Sicherheit und Nachweisgrenze.** Derselbe tatsächliche
Payloadsatz mit denselben vollständig gebundenen Fachmetadaten ergibt dieselben
Manifest- und Voll-ZIP-Bytes, unabhängig von Eingabeaufzählung, Hostpfad,
Dateimtime, Laufzeit oder Ressourcenprofil. Arrayreihenfolgen des Descriptors
und nativer fachlicher Payloads werden nicht willkürlich umgeordnet.
Containerparameter folgen ausschließlich E.2 und dem gemeinsamen Archivcodec;
kein zweiter ZIP-Writer und kein zweites Entpackverfahren werden eingeführt.

Für den Bundlepfadraum werden vor Payloadverwendung auch Casefold-Kollisionen
von Dateien und Verzeichnispräfixen sowie Datei-/Verzeichnis-Präfixkonflikte
abgewiesen, entsprechend den bestehenden sicheren Projekt-/ReqIFZ-Pfadgrenzen.
Eine andere Schreibweise wird nicht still auf ein vorhandenes Ziel abgebildet.
Unbekannte Manifestfelder, falsche Typen oder widersprüchliche Kind-/Scopewerte
sind Code 3/SRV002; eine nicht unterstützte Format-/Schemaversion ist Code
3/SRV003. Fehler der kanonischen Container-/Manifestbytes, der Payloadbijektion,
Größe oder Hashbindung einschließlich einer vorhandenen externen ZIP-Erwartung
sind Code 3/SRV060. Gefährliche Pfade, Kollisionen oder Sonderdateien bleiben
Code 7; echte Host-/I/O-Probleme bleiben Code 5. Anhang L und die bestehenden
Sicherheitsgrenzen werden nicht durch eine pauschale Formatdiagnose ersetzt.

Ein reiner Container-/Manifestcodec prüft Struktur, Typkombination,
Kanonizität und tatsächliche Payloadbindung. Er darf damit keine erfolgreich
rekonstruierte Modellwurzel, vollständige Closure, authentische Herkunft,
menschliche Freigabe, portable Idempotenzwirkung oder sichere Extraktion
bescheinigen. Diese Nachweise benötigen die nach E.1/E.3 vorgeschriebenen
Fachprüfungen auf den echten Bytes. Ein äußerer erwarteter ZIP-Hash bleibt
außerhalb des Manifests und, wo bereits an Auftrag oder Plan gebunden,
verpflichtend. Bestehende Work-/ReqIFZ-/Archivformate werden weder umbenannt
noch migriert; ihr bisheriger Byte- und Fehlervertrag bleibt erhalten.


## E.2 Kanonische ZIP-Bytes

Für jeden Eintrag gelten exakt:

| Feld | Wert |
|---|---|
| Entry-Typ | reguläre Datei; keine Directory Entries, Symlinks oder Spezialdateien |
| Pfad | NFC-normalisierter relativer POSIX-UTF-8-Pfad ohne leere, `.`- oder `..`-Segmente |
| Reihenfolge | lexikografisch nach UTF-8-Bytes |
| DOS-Zeit | `1980-01-01 00:00:00` |
| `create_system` | `3` |
| benötigte ZIP-Version | `20` |
| Methode | `ZIP_STORED` |
| General-Purpose-Flags | UTF-8-Namen konsistent; Data-Descriptor-Bit aus |
| Extra Fields | leer |
| Datei-/Archivkommentar | leer |
| externe Attribute | `0o100644 << 16` |
| interne Attribute | `0` |

Doppelte oder nach Normalisierung kollidierende Pfade sind Fehler. Das Archiv darf nach Ende des zentralen Verzeichnisses keine Fremdbytes enthalten. Die Bundle-SHA-256 ist der Hash über die vollständigen ZIP-Bytes.

## E.3 Voll- und Teilbundle

Das Feld `bundle_kind` besitzt exakt die kanonischen Werte `project` und `partial`. Auswahlart und Vollständigkeit werden nicht im selben Feld vermischt:

| CLI-Auswahl | `bundle_kind` | `scope_descriptor.scope_kind` | `boundary_policy` | `read_only` |
|---|---|---|---|---|
| `--scope project` | `project` | `project`; Selector `{}`, `configuration_id=null` | `closed` | `false` |
| `--scope document` mit vorhandener Dokument-ID | `partial` | `document`; Selector mit dieser ID | `partial` | `true` |
| `--scope release` mit vorhandener Release-ID | `partial` | `release`; Selector mit dieser ID | `partial` | `true` |

Der Descriptor wird vollständig nach 10.8 gebunden. Das Vollbundle umfasst auch alle noch benötigten historischen Objekte; eine optionale Objektoptimierung darf nur unreferenzierte Daten auslassen. Teilbundles bleiben auch dann `partial`, wenn die konkrete Closure zufällig alle aktuellen Fachartefakte erreicht. Ein boolesches `read_only` wird nicht aus Dateirechten, einem Verzeichnisnamen oder der Zahl der Boundary References erraten.

Der kanonische Reader dieses Zielreleases akzeptiert **keine** Aliase `bundle_kind=document` oder `bundle_kind=release`, keine unbekannten Werte und keine widersprüchlichen Kombinationen der Tabelle. Er liefert dafür Code 3/SRV002 vor der Extraktion. Eine Formatversion außerhalb des deklarierten Supports ergibt Code 3/SRV003. Ein unzulässiger Pfad oder ein gefährlicher ZIP-Eintrag bleibt Code 7. Die Dokumentkorrektur v0.2.5 ist keine Behauptung einer bereits ausgelieferten Bundle-Formatmigration.

`bundle verify` prüft zuerst Format, kanonische Kennzeichnung und Hashdomänen, danach Scope-Closure und Inhalte. `bundle extract` übernimmt das unveränderte Manifest als nicht fachliche Root-Metadatei, sodass jeder neue Aufruf die Teilständigkeit erneut erkennt. Das Manifest ist kein Artefakt, wird weder als fachliche Ressource gehasht noch formatiert. Bei dokument-/releaseförmiger oder unvollständiger Projektstruktur ohne gültigen Vollprojektnachweis darf das Entfernen des Markers keinen schreibbaren Vollstand erzeugen. Teilbundle-Root und Boundary References werden vor jedem zulässigen Befehl geprüft; Widerspruch oder fehlende notwendige Daten verweigern einen Write.

Für Teilbundles gelten exakt die in 10.16 erlaubten Read-only-Funktionen. Ein Writeversuch, eine Baseline-Erzeugung oder ein Re-Export als Vollprojekt ergibt Code 7. Im Produktumfang existiert kein stiller Rehydrationsbefehl: Ein schreibbarer Stand entsteht erst aus dem separat beschafften, vollständig verifizierten Ursprungsprojekt beziehungsweise Vollbundle in einem getrennten Zielroot. Übernahmen aus einem Teilstand unterliegen dort wieder den normalen Change-Plan-/Proposal-Regeln.

### E.3.1 Konfigurationskontext eines Teilbundles

**Entscheidung PARTIAL-CONFIGURATION-CONTEXT, delegiert gemäß
SPECROAD-DECISION-1.** Dieser Vertrag präzisiert die nach E.1.1 zur
Rekonstruktion erforderlichen Konfigurationsbytes für `document`-/`release`-
Teilbundles mit `configuration_id != null`. Er ändert weder die Seed-Mengen
und Closure aus 10.8 noch `scope-v1`, `core-closure-v1`, die Modellprojektion
10.9 oder die Konfigurationsauflösung 10.18/Anhang I. Der Auflösungskontext
ist keine neue Artefaktart, kein neues Manifestfeld und kein zweiter Scope.

**Exakte Payloadmenge.** Der Erzeuger löst im tatsächlich beobachteten
vollständigen Ursprung die ausgewählte Konfiguration einschließlich ihrer
vollständigen Parent-Kette auf. Zusätzlich zu den fachlichen Closurepayloads
MUSS das Teilbundle genau die unveränderten nativen JSON-Quelldateien dieser
Kette an ihren regulären `configuration`-Artefaktpfaden enthalten. Eine
berechnete Wertetabelle, ein behaupteter Hash oder eine neu serialisierte
Ersatzkonfiguration ersetzt die erforderlichen Originalbytes nicht.
`specroad.json` und die für die effektive Profilbindung benötigten nativen
Ressourcen bleiben ebenfalls Pflicht. Unbeteiligte Konfigurationen werden
nicht allein wegen ihres Typs mitgenommen; sind sie reguläre Closuremitglieder,
gelten für sie unverändert die normalen Mitgliedschaftsregeln.

Die Transportmenge ist die Vereinigung der benötigten Closurepayloads,
dieses exakt abgeleiteten Konfigurationskontexts und des gegebenenfalls
erforderlichen getrennten Prüfkontexts nach E.3.2. Überlappende Pfade werden
einmal transportiert. Alle diese Bytes sind normale, vollständig inventarisierte
Payloads nach E.1; sie dürfen nicht zugleich als `outside_scope` ausgeschlossen
sein. Es gibt keine vom Absender frei deklarierbare Kontext-Ausnahmeliste.
Weitere Konfigurationsdateien ohne Closuremitgliedschaft oder Bedarf in der
ausgewählten Parent-Kette sind zusätzliche unerwartete Payloads.

**Mitgliedschaft und Hashdomänen.** Nur durch Seeds und Closure nach 10.8
erreichte Artefakte bilden den fachlichen Teilumfang. Die bloße Mitnahme einer
Konfiguration als Auflösungskontext macht sie nicht zu einem zusätzlichen
Seed oder Artefakteintrag der Teilmodellwurzel. Ihr vollständiger kanonischer
Inhalt, ihre ID und Revision sind bereits über die Parent-Kette im effektiven
Konfigurationsmanifest nach I.2 gebunden; dessen Hash und die semantische
Projektkonfiguration bilden unverändert `configuration_sha256` nach 10.9.
Eine Änderung eines Parents MUSS diese Bindung auch dann verändern, wenn die
effektiven Auswahlwerte gleich bleiben. Byteformatierungsänderungen verändern
die Transporthashes, nicht die kanonischen Fachhashes.

Erreicht die fachliche Closure eine solche Konfiguration zusätzlich regulär,
ist sie zugleich ein normales Mitglied. Dann werden auch ihre starken Kanten,
gebundenen Ressourcen und schwachen Grenzen vollständig nach 10.8 verarbeitet.
Eine dafür fehlende starke Zielressource kann nicht als bloßer Kontext deklariert
werden. Kanten einer ausschließlich als Konfigurationskontext transportierten
Datei erweitern dagegen nicht den gewählten fachlichen Scope; sie erhalten
keine erfundenen Boundary References. Das behauptet keine lokale Vollständigkeit
dieses außerhalb des Scopes liegenden Graphteils. Der Erzeuger muss dennoch
den vollständigen Ursprung einschließlich seiner Referenzen prüfen; ein bereits
dort fehlendes Ziel wird nicht durch diese Transportregel zulässig.

**Prüfung und Fehlergrenzen.** Erzeuger und unabhängiger Reader bestimmen
dieselbe Kette erneut aus den tatsächlichen Bytes, prüfen native Identität,
Schema, Parent-Verweise, Zyklusfreiheit, Dimensionen und Auswahl nach Anhang I
und berechnen die Konfigurationsbindung selbst. Danach bestimmen sie die
fachliche Mitgliedschaft und prüfen die exakte Payloadvereinigung. Der Reader
darf den behaupteten `configuration_sha256` nicht als Ersatz für die Auflösung
übernehmen. Fehlende, falsche oder zusätzliche Kontextdateien sowie eine
widersprüchliche Konfigurationsbindung ergeben Code 3; gefährliche Pfade oder
Dateitypen bleiben Code 7. Ein konfigurationsbedingt ausgeschlossener starker
Fachabhängiger bleibt ein Fehler nach 10.8, keine schwache Boundary.

Das ausdrücklich ausgewählte Dokument beziehungsweise Release muss vorhanden,
vom passenden Typ und in der gewählten Konfiguration anwendbar sein. Ist dieser
Auswahlanker ausgeschlossen, ergibt die Bundleerzeugung Code 3, bevor eine
Ausgabedatei veröffentlicht wird; es wird weder ein anderer Anker gewählt noch
ein scheinbar gültiges ankerloses Teilbundle erzeugt. Diese Prüfung verändert
nicht die Seed-Filterung anderer Operationen. Fehlende Parentbytes, ungültige
Konfigurationswerte und ein ungültiger Ursprung werden ebenso schreibfrei
abgewiesen. Die bestehenden Frische-, Transaktions- und Ausgabepfadprüfungen
gelten weiterhin bis zur Veröffentlichung.

**Lesen, Kompatibilität und Nachweisgrenze.** Ein Kontextartefakt außerhalb der
fachlichen Closure wird nicht als zusätzliches Query-/Trace-/Show-Objekt des
Teilumfangs angeboten. Die erforderlichen Bytes bleiben zur erneuten
Konfigurationsprüfung verfügbar. Extraktion erhält sie und das unveränderte
Rootmanifest; daraus entsteht keine Schreibberechtigung. `partial`,
`read_only=true` und `local_only` bleiben auch bei zufällig vollständiger
Closure verbindlich. Die Ursprungswurzel bleibt die getrennte Provenienzbindung
aus E.1.1 und kein aus den Teilbytes ableitbarer Vollprojektnachweis.

Diese Konfigurationsregel allein verändert keine unkonfigurierten Teilbundles,
Vollbundles, Export- oder Baselineprojektionen. Für erforderliche
Relationsreview-Prüfbytes gilt zusätzlich E.3.2. Bereits gebundene Artefakte,
Reviews, Evidence und historische Hashes werden nicht umgeschrieben oder
nachträglich als neu geprüft bezeichnet. Bei konfigurierten Teilbundles werden
keine neuen semantischen Mitglieder nur für den Transport erfunden. Die
Produktumsetzung der Erzeugung bleibt in 15.c.R, die unabhängige Bundleprüfung
in 15.d und der extrahierte Read-only-Umfang in 15.e offen. Diese Festlegung
behauptet weder eine implementierte Funktion noch eine Freigabe oder Abnahme.

### E.3.2 Getrennter Prüfkontext für Relationsreviews an Außenkanten

**Entscheidung BOUNDARY-REVIEW-CONTEXT.** Der Nutzer hat am 25. Oktober
2026 nach Benennung der Nachweis- und Transportgrenze ausdrücklich
hashgebundene Zielbytes als separaten Prüfkontext ohne zusätzliche
Scope-Mitgliedschaft beauftragt. Die folgenden Detailregeln konkretisieren
diese Entscheidung gemäß SPECROAD-DECISION-1. Sie ändern weder die
Reviewentscheidung eines Menschen noch die Aktualitätsregeln aus Anhang J.
Der Kontext ist kein Review, keine Freigabe und kein Rehydrationsvorgang.

**Notwendigkeit und minimale Auswahl.** Die Closure nach 10.8 nimmt aktuelle
Relationsreviews auch zu enthaltenen schwachen Relationen auf. Ob ein Review
passt, hängt nach J.1–J.3 vom wirklichen Relations- und Endpunktkontext ab.
Der Vollhash eines ausgelassenen Ziels allein liefert dessen Kontextbytes
nicht. Ein gespeicherter historischer Review-Vollhash ersetzt diese Prüfung
auch dann nicht, wenn er zufällig mit dem Boundary-Zielhash übereinstimmt.

Für ein `partial`-Bundle wird die Prüfzielmenge ausschließlich so bestimmt:
Aus seinen nach 10.8 tatsächlich erforderlichen Boundary References werden
jene ausgewählt, deren `relation_id` in wenigstens einem enthaltenen nativen
`relation_review` referenziert wird. Die Prüfzielmenge enthält genau die
verschiedenen `target_id` dieser Boundaries. Maßgeblich ist die Relations-ID,
nicht eine frei wählbare Kontextliste oder eine schon als aktuell behauptete
Reviewentscheidung. Auch ein durch andere reguläre Closurepfade enthaltenes
historisches oder abgelehntes Review löst diese Auswahl aus. Seine fachliche
Bewertung erfolgt erst anhand der tatsächlichen Kontexte. Ohne solchen
Reviewbezug wird kein Ziel allein für diese Regel zusätzlich transportiert.

Für jedes Prüfziel MUSS der Erzeuger genau einmal dessen vollständige,
unveränderte native JSON-Quelldatei aus demselben geprüften Ursprungsstand
unter `bundle-context/boundary-targets/<TARGET-ID>.json` mitliefern.
`<TARGET-ID>` ist die vollständige, bereits nach nativer Identitätsregel
geprüfte Artefakt-ID, keine Eingabe für freie Pfadbildung. Der reservierte
Namensraum `bundle-context/` erlaubt ausschließlich diese unmittelbar darin
festgelegten Prüfdateien. Keine Verzeichnis-Einträge, Metadateien,
Unterverzeichnisvarianten, Symlinks oder fremden Payloads sind zulässig.
Mehrere betroffene Boundaries mit demselben Ziel verwenden dieselbe Datei.
Sie MÜSSEN dieselbe Zielidentität, denselben Typ und denselben aktuellen
kanonischen Vollhash binden. Das Rootmanifest erhält kein neues Feld;
`bundle_format_version=1.0.0` und die sieben Boundary-Felder bleiben erhalten.

Ist dasselbe Prüfziel bereits ausschließlich als Konfigurationskontext nach
E.3.1 am nativen Pfad vorhanden, bleibt der feste getrennte Prüfpfad bestehen.
Beide Rollen MÜSSEN dieselben unveränderten Originalbytes enthalten; eine
abweichende Kopie ist ein Eingabefehler. Daraus entstehen keine zweite
Artefaktidentität und keine Scope-Mitgliedschaft. Der feste Pfad vermeidet
zusätzliche, vom Absender wählbare Speicher- oder Auflösungsvarianten.

**Transport- und Hashbindung.** Jede Prüfdatei ist reguläre Payload mit
exaktem Pfad, tatsächlicher Bytelänge, `application/json` und Byte-SHA-256
in `entries`. Der Reader MUSS unabhängig native Identität, Artefakttyp,
Schema und kanonische Darstellbarkeit des enthaltenen Originaldokuments
prüfen. Der ID-basierte Dateiname, `target_id`, `target_type` und der aus
den wirklichen JSON-Werten berechnete RFC-8785-Vollhash MÜSSEN zu allen
betroffenen Boundaries und deren `origin_target_sha256` passen. Bloße
Kontexthashes, Projektionen, Ersatzartefakte oder neu erzeugte Reviewrecords
sind kein Ersatz für die erforderlichen Originalbytes.

Die Prüfdatei ist keine zweite fachliche Kopie am nativen Artefaktpfad.
Ihre native Quelldatei wird nicht zusätzlich als `outside_scope` in
`excluded_contents` ausgewiesen: Deren vollständige Bytes werden hier in
einer anderen Transportrolle tatsächlich mitgeliefert. Der native Quellpfad
ist aus Typ und ID eindeutig ableitbar. Für andere tatsächlich ausgelassene
Quellpayloads bleiben E.1.1 und ihre Ausschlussgründe unverändert. Das
Prüfziel bleibt trotz dieser Transportrolle außerhalb des fachlichen Scopes;
diese Grenze bezeichnet weiterhin die Boundary Reference.

**Unabhängige Rekonstruktion.** Der Reader verwendet Prüfbytes ausschließlich
als Endpunktbeobachtung für die zugehörigen enthaltenen Boundary-Relationen.
Er berechnet die Relations- und beide Endpunktkontexte nach J.1/J.2 und wendet
J.3 auf die enthaltene Reviewhistorie an. Er leitet die gebundenen aktuellen
Reviewressourcen selbst ab und prüft anschließend den kleinsten fachlichen
Closurefixpunkt, dessen Modellwurzel und die exakte Payloadvereinigung aus
Closure, E.3.1-Konfiguration und dieser Prüfzielmenge. Ein vom Manifest
behaupteter Scope- oder Modellhash ersetzt keinen dieser Schritte.

Historische Vollrevisionen und Vollhashes der Reviews bleiben unverändert.
Eine Änderung allein an nach J.2 ausgeschlossenen Zielwerten darf ein weiterhin
passendes Review nicht stale machen; fachlich veränderte Zielkontexte dürfen
nicht als aktuell ausgegeben werden. Abgelehnte passende Reviews bleiben
abgelehnt. Fehlende Reviewhistorie wird weder erfunden noch durch den
Prüfkontext ersetzt. Die Prüfung belegt keine unbekannte Vollständigkeit der
ursprünglichen Reviewhistorie und keine menschliche Authentizität; der
vollständige Ursprung bleibt die getrennte Provenienzgrenze aus E.1.1.

**Keine zusätzliche Mitgliedschaft.** Prüfziele werden weder Seeds noch
normale Closuremitglieder. Ihre ausgehenden Kanten, Anhänge und sonstigen
Ressourcen werden nicht transitiv in den Teilumfang aufgenommen. Sie erhalten
keine eigenen erfundenen Boundary References. Das behauptet keine Prüfung
dieser außerhalb des Scopes liegenden Ressourcen. Der Erzeuger MUSS weiterhin
den vollständigen Ursprung einschließlich seiner benötigten Referenzen und
Ressourcen prüfen; dort fehlende Daten bleiben Fehler.

Wird dasselbe Ziel regulär durch einen Seed, eine starke Kante oder eine
gebundene Ressource erreicht, MUSS es als normales Closuremitglied am nativen
Artefaktpfad vorhanden sein. Die betreffende Relation hat dann kein äußeres
Ziel und keine Boundary. Eine zusätzliche Prüfkopie für dieses Ziel ist
unzulässig. Ein starkes Ziel, das nur im Prüfnamensraum vorliegt, fehlt weiterhin;
es wird nicht stillschweigend in den fachlichen Bestand übernommen.

Prüfdateien werden nicht als Query-, Show-, Trace-, Render- oder andere
Fachobjekte angeboten. Extraktion erhält ihre Originalbytes getrennt und
das unveränderte Manifest für erneute Prüfungen. Sie vermittelt weder Writes,
Re-Export als Vollprojekt, Release Readiness noch Rehydration. `partial`,
`read_only=true` und `local_only` bleiben wirksam. Die Modellwurzel bindet
unverändert die wirklichen fachlichen Mitglieder, Profile, Konfiguration und
Boundaries; Prüfbytes werden nicht als zusätzliche Modellressourcen gehasht.
Ihr Transporthash bindet die Originalbytes, der vorhandene Boundary-Vollhash
bindet den semantischen Zielwert. Der Voll-ZIP-Hash bleibt extern.

**Fehler und Bestandsgrenze.** Nach erfolgreicher ZIP-Sicherheitsprüfung
ergeben fehlende benötigte Prüfbytes, unerwartete oder inhaltlich redundante
Prüfdateien, falsche Identität, Typ- oder Schemakonflikte sowie eine
widersprüchliche Payloadrolle Code 3. Byte-/Vollhashwidersprüche bleiben
Code 3/SRV060. Unsichere Pfade, Pfadkollisionen einschließlich doppelter
ZIP-Mitgliedsnamen und gefährliche Dateitypen behalten vorrangig Code 7. Keine dieser
Situationen darf einen verifizierten Closure- oder Freigabestatus erzeugen.
Ein altes Bundle ohne nun erforderlichen Prüfkontext wird nicht stillschweigend
repariert oder als vollständig verifiziert ausgegeben. Eine Neuherstellung
erfolgt nur ausdrücklich aus dem vollständigen geprüften Ursprung; bestehende
ZIP-Bytes, Reviews, Evidence und deren alte Hashbindungen bleiben erhalten.

Projektbundles und Teilbundles ohne den beschriebenen Review-/Boundarybedarf
benötigen keine Prüfdateien und behalten ihre bisherigen Transport- und
Hashdomänen. Unnötige Kontextdateien sind auch dort Fehler. Bestehende CLI-
Aufrufe bleiben erhalten; es gibt keinen neuen Ursprungspfad-Fallback, kein
Nachladen und keine neue Freigabeoption. Diese Fortschreibung erklärt einen
Sollvertrag. Seine Erzeuger-/Readerintegration und Verhaltensnachweise in
15.d.R sowie der spätere Erhalt und Sichtbarkeitsschutz in 15.e/15.f bleiben
offen; die Spezifikationsklärung ist kein Produktabschluss.

### E.3.3 Lesebeobachtung und Graphgrenze eines Teilbundles

**Entscheidung PARTIAL-READ-GRAPH, delegiert gemäß SPECROAD-DECISION-1.**
Dieser Vertrag konkretisiert für die nach 10.16 erlaubten Lesebefehle die
Unterscheidung zwischen geladenen Fachobjekten und bekannten Außenkanten.
Er erweitert weder die Befehlsliste noch die Transportmenge nach E.3.1/E.3.2.
Ein neuer SRX-Operator, ein externes Nachladen und eine neue Hashdomäne
werden nicht eingeführt. Die Regeln für vollständige geladene Modelle,
SRX-Typen, Missing, Reihenfolge und Fehler nach Anhang B bleiben erhalten.

**Mitglieder und beobachtete Relationen.** M bezeichnet ausschließlich die
aus den Originalbytes unabhängig verifizierte fachliche Closure nach 10.8.
Nur M ist die Artefaktpopulation der Abfrage. Eine außerhalb von M liegende
Konfiguration oder Review-Prüfdatei bleibt Kontext; selbst vorhandene Bytes
machen ihr Ziel nicht zum auswählbaren Artefakt, Startknoten oder Suchtreffer.
Für jedes Mitglied sind seine tatsächlich gespeicherten Relationen bekannt:
lokale Kanten haben beide Endpunkte in M; jede erlaubte schwache Außenkante
besitzt genau die nach E.3 exakt geprüfte Boundary Reference. Sie ist eine
beobachtete Relation mit Ziel-ID und Zieltyp, kein geladenes Zielartefakt.
Eingehende Relationen und inverse Sichten werden nur aus gespeicherten
Relationen von Mitgliedern abgeleitet. Weder Außenquellen noch deren
Relationen werden aus Prüfdateien oder aus der bloßen Symmetrie eines
Relationstyps ergänzt. Die bestehenden kanonischen Orientierungsregeln gelten.

**Gemeinsame Fehler-, Kontext- und Randfallgrenzen.** Ein gültig gebundenes Außenziel
ist kein unbekanntes Mitglied mit leeren Feldern. Ein ausdrücklich verlangtes
Show-/Trace-/Why-/Impact-Startartefakt außerhalb von M wird als fehlendes
Fachobjekt mit Code 3 abgewiesen, auch wenn Prüfbytes vorhanden sind.
Dies betrifft keine gewöhnlichen Wertfilter auf Mitgliedern: eine leere
Treffermenge bleibt eine gültige begrenzte Antwort. Fehlende, zusätzliche,
typwidrige oder nicht exakt gebundene Boundaries ergeben Code 3; ein
fehlendes starkes Ziel wird durch keine Boundary oder Prüfdatei ersetzt.
Gefährliche Pfade/Dateitypen und Partial-Writes bleiben Code 7; ein
unaufgelöstes Journal behält Code 5, eine nach Beobachtung veränderte
gebundene Eingabe den bestehenden Konfliktvertrag mit Code 6. Frische
Marker- und Sicherheitsprüfungen bleiben vorrangig; kein Fehler wird als
erfolgreiches `partial` verborgen. Konfigurationsauflösung nach E.3.1 und
Relationsreviews nach E.3.2/J.1–J.3 erfolgen weiterhin aus ihren notwendigen
Originalbytes. Diese Kontextrollen erzeugen keine weiteren Objektpopulationen.
Verlangt eine zugelassene Operation weitere echte Inputs, gelten deren
bestehende Prüf- und Fehlerverträge; es gibt keinen Nachladefallback,
keine erfundene Evidence und keinen Ersatz einer Pflichtfreigabe durch
das Ergebnis einer lokalen Graphabfrage.

**Maschinenlesbare Abgrenzung.** Ein erfolgreich vollständig abgearbeiteter
fachlicher Leseauftrag auf M (Show, Query, Trace, Why, Impact sowie darauf
aufbauende Render-/View-/Diagrammabfragen) verwendet den vorhandenen
Envelope `status=partial`,
`complete=true` und `summary.partial_scope=partial_bundle_artifacts`.
Seine Zusammenfassung bindet `bundle_kind=partial`, `read_only=true`,
`project_complete=false`, den unveränderten `scope_descriptor`, die geordneten
`boundary_references`, `bundle_model_root_sha256`, `origin_model_root_sha256`
und `origin_root_verified=false`. Die Ursprungswurzel bleibt Provenienz.
Vorhandene Abdeckungsfelder dürfen keine Vollprojektpopulation behaupten;
eine Quell-/Artefaktzahl zählt nur M, eine Relationszahl nur beobachtete
gespeicherte Relationen, nicht zusätzlich deren inverse Sichten. Query behält
die sechs Pflichtfelder aus 11.6; Scopeangaben stehen im Envelope. Eine leere
Treffermenge oder zufällig geschlossene Closure ändert den Partialstatus nicht.
Unterbrochene Arbeit, ungültige Inputs, fehlende notwendige Providerdaten und
Policyfehler behalten ihre bestehenden Fehler-/Fortsetzungsverträge; sie
werden nicht durch `partial` zu einem erfolgreichen Teilauftrag umgedeutet.
Reine Metadatendiagnosen, projektlose Befehle und die eigenständige
Bundleprüfung behalten ihre jeweiligen Ergebnisverträge. Auch
`validate --partial` und `project inspect` behalten ihre spezifischen
Prüf-/Ergebnisschemas; die Mitglieder- und Kontextgrenze gilt dort, wo sie
fachliche Modellobjekte auswerten. Diese Regel ersetzt keinen dieser
Verträge durch das Ergebnisschema einer Graphabfrage.

**Unmittelbare Abfragen.** Show und direkte Relationsbeobachtungen behalten
die bekannten Außenkanten mit ihrer originalen Relations-ID und Zielidentität.
Query-Wertfilter `has_relation`/`missing_relation` sowie die unmittelbaren
SRX-Operatoren `relation_count`, `incoming_count` und `has_relation` arbeiten
auf diesen beobachteten Relationssichten, gemäß ihrer Richtung und Typfiltern.
Eine ausgehende Boundary zählt daher als bekannte Relation; ihr Zieltyp und
ihre Ziel-ID dürfen die dafür vorgesehenen unmittelbaren Filter erfüllen.
Das liefert keine fremden Zielfelder und erfindet keine eingehende Außenquelle.
Query-Items, `total`, Projektion, Sortierung und Pagination beziehen sich
ausschließlich auf M nach den unveränderten Filtern aus 11.6.

**Traversierung und Zielprädikate.** Trace, Why, deklarative Graphansichten
und SRX `reachable` besuchen ausschließlich Mitglieder von M. Traversierbare
Kanten haben beide Endpunkte in M; Richtung, Typfilter, stabile Reihenfolge,
Tiefenvertrag und Zyklusbehandlung gelten unverändert. Eine Außenkante darf
als begrenzte Relationsbeobachtung mit Boundary-Bindung sichtbar bleiben,
wird aber nicht zu einem Zielknoten, Pfadschritt oder expandierbaren Frontiereintrag.
Ein `reachable`-Zielprädikat wird niemals auf einem erfundenen Stub oder auf
E.3.2-Prüfbytes ausgewertet. Tiefe 0 prüft nur das wirkliche Startmitglied.
`false` bedeutet keine passende Erreichbarkeit im gewählten Teilmodell,
nicht Unerreichbarkeit im Ursprung. Auch ein unmittelbarer Relationstreffer
auf eine Boundary-ID und `reachable=false` auf dieselbe ID sind damit
widerspruchsfrei. Bestehende Typ-/Auswertungsfehler werden nicht zu `false`.

Die Anzeige ist keine Vollprojektvalidierung, Release Readiness oder Freigabe.
E.3.2 bleibt ausschließlich der begrenzte Endpunktnachweis für enthaltene
Relationsreviews nach J.1–J.3; daraus entsteht keine zusätzliche Lese- oder
Schreibautorität. Die gemeinsamen Grenzen dieses Abschnitts gelten.
Die Umsetzung und ausführbare Abnahme dieses Lesevertrags bleiben in 15.f.R
offen; die Dokumentänderung allein erklärt keine implementierte Funktion.


---

# Anhang F — CLI-Kompatibilität von 0.1 nach 0.2

| 0.1-Aufruf | 0.2-Ziel | Status |
|---|---|---|
| `specroad create <TYPE>` | `specroad artifact create <TYPE>` | kompatibler Alias zulässig |
| `specroad show <ID>` | `specroad artifact show <ID>` | kompatibler Alias zulässig |
| `specroad retire <ID>` | `specroad lifecycle transition <ID> --to retired` | kompatibler Alias zulässig |
| `specroad proposal validate/check/review/apply` | gleichnamige 0.2-Unterbefehle | kompatibel, intern Change Plan |
| `specroad render --view ...` | unverändert | kompatibel |
| sequentielle neue IDs | `random128-v1` | bewusst geändert; Migration erhält vorhandene IDs |
| direkte Dateibearbeitung | kein kontrollierter Authoring-Pfad | weiterhin lesbar, aber ohne Transaktions-/Auditgarantie |
| Modul-Distribution | Modul-Distribution plus Zipapp | erweitert |

---

# Anhang G — Abgrenzung zu Implementierungs- und Repository-Agenten

SpecRoad ist ein Spezifikations- und Traceability-Werkzeug. Run-Zustände eines separaten Implementierungsagenten wie `task`, `retry`, `abort`, `done` oder `done --no-commit` sind nicht Bestandteil dieser Spezifikation.

`specroad proposal apply`, `merge apply`, `migrate apply` und `import apply` verändern ausschließlich das kanonische SpecRoad-Projekt nach ihren kontrollierten Verträgen. Sie erzeugen keinen Git-Commit und führen keinen Projektcode aus.

---

# Anhang H — Normative Code-Referenz-Normalisierung

## H.1 Dateihash

Der Rohdateihash ist SHA-256 über die unveränderten Dateibytes. Ein nicht auffindbarer oder außerhalb des erlaubten Roots aufgelöster Pfad liefert keinen Hash.

## H.2 Zeilen und Auswahlhash

Für `line_range` und textbasierte `text_anchor` wird die Datei im gespeicherten Encoding dekodiert. CRLF und CR werden zu LF normalisiert; andere Zeichen und ein vorhandener abschließender Zeilenumbruch bleiben erhalten. Start- und Endzeile sind 1-basiert und inklusiv. Der Auswahlhash ist SHA-256 über die UTF-8-Bytes des normalisierten ausgewählten Texts. Bytebasierte Anker verwenden unveränderte Bytes und deklarieren dies ausdrücklich.

## H.3 Disjunkte Statusentscheidung

Die erste zutreffende Zeile entscheidet:

| Bedingung | Zustand | Zusatzdiagnose |
|---|---|---|
| Pfad oder gebundenes Git-Objekt nicht auffindbar | `missing` | Grund `target_missing` |
| Referenzart `file` und Rohdateihash stimmt | `current` | keine |
| Referenzart `file` und Rohdateihash weicht ab | `stale` | Grund `file_changed` |
| Bereichs-/Textreferenz und Auswahl an der gespeicherten Position stimmt | `current` | bei abweichendem Rohdateihash optional `file_changed_outside_selection` |
| gespeicherte Position stimmt nicht und der Auswahlhash wird genau einmal an einer anderen Position gefunden | `relocated` | neue Position wird berichtet, aber nicht automatisch gespeichert |
| gespeicherte Position stimmt nicht und der Auswahlhash wird keinmal gefunden | `stale` | Grund `selection_missing` |
| gespeicherte Position stimmt nicht und der Auswahlhash wird mehrfach gefunden | `stale` | Grund `selection_ambiguous` |

Ein Treffer an der gespeicherten Position ist niemals `relocated`. Eine Dateiänderung außerhalb eines unveränderten ausgewählten Bereichs macht die Bereichsreferenz nicht stale.

---

# Anhang I — Normative Konfigurationsauflösung

## I.1 Dimensionen

Eine Wurzelkonfiguration deklariert Dimensionen als:

```json
{
  "name": "platform",
  "allowed_values": ["linux", "windows"],
  "default": "linux"
}
```

Kindkonfigurationen dürfen neue Dimensionen ergänzen, aber Namen, zulässige Werte oder Defaults geerbter Dimensionen nicht ändern. Eine konkrete `selection` darf ausschließlich deklarierte Werte verwenden.

## I.2 Vererbung

1. Die Parent-Kette wird von der Wurzel zum Kind aufgelöst.
2. Geerbte Dimensionen werden vereinigt.
3. Die Auswahl des Kindes überschreibt die Auswahl des Parents für dieselbe Dimension.
4. Fehlt nach der Kette eine Auswahl, wird der deklarierte Default verwendet.
5. Fehlen Auswahl und Default, ist die Konfiguration ungültig.
6. Der effektive Konfigurationshash wird über ein kanonisches Manifest aus Konfigurations-IDs, Revisionen, Hashes, Dimensionen und effektiver Auswahl gebildet.

## I.3 Applicability

Der `configuration`-SRX-Kontext enthält ausschließlich:

```json
{
  "configuration_id": "...",
  "effective_values": {
    "platform": "linux"
  }
}
```

Ein `applicability`-Ausdruck muss Boolean ergeben. Typfehler oder `missing` als Endergebnis sind Konfigurationsfehler und werden nicht als `false` interpretiert.

---

# Anhang J — Normativer Relationsreview-Status

## J.1 Relationsinhaltshash

Der Relationsinhaltshash wird nach RFC 8785 und SHA-256 über die Relation ohne die rein auditiven Felder `created_at` und `created_by` gebildet. Er enthält insbesondere `relation_id`, `id_scheme`, `type`, `target`, `rationale` und bei `contains` die `position`.

## J.2 Endpunkt-Kontextprojektion `relation_context_hash-v1`

Für Quelle und Ziel wird eine kanonische Artefaktprojektion gebildet. Ausgeschlossen sind ausschließlich:

- `revision`;
- `created_at`, `created_by`, `updated_at`, `updated_by`;
- `maturity`;
- `implementation_status`, `verification_plan_status`, `risk_status`, `validation_status`, `issue_status`, `proposal_status`, `evidence_state`, `baseline_state`, `review_state`;
- `relations`;
- `tags`.

Alle anderen Felder einschließlich ID, Typ, Titel, fachlichem Inhalt, `applicability`, Owner, Provenienz und Extensions bleiben enthalten. Die Projektion wird nach RFC 8785 kanonisiert und mit SHA-256 gehasht.

Damit machen Workflow-, Audit- oder unabhängige Relationsänderungen ein Review nicht zirkulär ungültig. Eine Änderung der fachlichen Aussage, Gültigkeit, Herkunft oder anderer reviewrelevanter Inhalte tut dies.

## J.3 Statusalgorithmus

1. Eine strukturell ungültige Relation ist unabhängig von Reviews `invalid`; ihr Zusatzgrund ist strukturell und blockiert den Review-Write.
2. Für eine strukturell gültige Relation werden nur Reviews mit gleicher `relation_id`, aktuellem Relationsinhaltshash und beiden aktuellen `relation_context_hash-v1` ausgewählt.
3. Gibt es solche aktuellen Reviews, entscheidet ausschließlich das zeitlich neueste; bei gleichem Zeitstempel entscheidet die lexikografisch höchste Review-ID. Dessen Entscheidung `confirmed` ergibt `current`, `rejected` ergibt `invalid` mit Zusatzgrund `current_review_rejected`. Die Diagnose bleibt ein Fehler; der Aufnahme-Write und seine Freigabefolgen folgen 11.13.
4. Gibt es kein aktuelles Review, aber irgendein früheres Review dieser Relations-ID, ergibt sich `suspect`.
5. Ohne jedes Review dieser Relations-ID ergibt sich `unreviewed`.

Damit ist eine Begründungsänderung an einer zuvor bestätigten Relation `suspect`, nicht `unreviewed`. Ein späteres aktuelles `confirmed` kann ein früheres aktuelles `rejected` ersetzen. Reviews selbst bleiben unveränderbar; eine neue Entscheidung erhält eine neue Review-ID.

---

# Anhang K — Deterministische Metadaten für Change Plans und Merge

## K.1 Explizite Policyauswahl

Jeder Plan wählt genau eine `metadata_policy_version`. Der Writer prüft die Auswahl gegen die autorisierte Operationsart; der Aufrufer kann nicht durch eine frei erfundene Policy Revisionen oder Freigaben umgehen.

| Policy | Zulässige Quelle | Revisions-/Zeitregel |
|---|---|---|
| `change-metadata-v1` | reguläres Authoring, Importänderung, Proposal-Authoring und Proposal-Kontrollwrite | Regeln aus K.2 |
| `merge-metadata-v1` | vollständig gebundener Dreiwege-Merge | Regeln aus K.3 |
| `migration-metadata-v1` | unterstützter Schema-Migrationsplan | Regeln aus K.4 und Anhang Q |

Unknown Policies werden mit Code 3 abgewiesen. Die Planformatversion lautet `1.2.0`; die zusätzlichen Policykennungen und Proposal-Kontrollpayloads sind Bestandteil des unterstützten 0.2-Zielschemas. Der Review-Fachbefehl bindet seinen nach 11.13 monoton bestimmten `planned_at` bereits bei Planung; seine neuen Nachweise und gekoppelten Herabstufungen verwenden danach unverändert K.2. Alle Ergebnisbytes, Metadaten und Hashes stehen vor Apply im gespeicherten Plan. Apply-Datum, Ressourcenprofil und Zahl der Fortsetzungsschritte ändern sie nicht.

## K.2 Regulärer Change Plan

Für ein vorhandenes semantisch geändertes Artefakt gilt `revision = base.revision + 1`, genau einmal pro Plan. `updated_at = max(planned_at, base.updated_at + 1 Mikrosekunde)`. `updated_by` ist der gebundene Akteur; `created_at` und `created_by` bleiben unverändert. Operationen derselben ID werden vor Hashbildung in Planreihenfolge gefaltet. Reguläre neue Artefakte erhalten Revision 1 und `created_at=updated_at=planned_at`, `created_by=updated_by=actor`.

`representation_normalize` verändert keine Artefaktwerte. Proposal-Kontrollwrites erhöhen die physische Artefaktrevision nach dieser Regel; Inhaltsrevision und Inhaltshash folgen unabhängig davon Kapitel 10.3. Eine gespeicherte Freigabe bindet den Inhalt und nicht die durch den eigenen Kontrollwrite veränderte Artefaktrevision.

## K.3 Semantischer Merge

Ours ist der bei Apply erwartete aktuelle Arbeitsstand. Base, Ours und Theirs sind über ihre Ressourcenhashes unveränderbar gebunden. Der Plan klassifiziert jede Ressource exakt als `unchanged_ours`, `adopt_existing`, `combined` oder `conflict`:

- `unchanged_ours`: unveränderte Ours-Bytes bleiben vollständig erhalten.
- `adopt_existing`: eine vollständige bereits existierende Historienrevision von Theirs wird bytegetreu übernommen, wenn Ours seit der gemeinsamen Basis unverändert ist. Ihre Revision und Auditmetadaten bleiben erhalten; sie gilt nicht als reguläre neue Erzeugung. Eine Revision kleiner als die bereits bei Ours bekannte höchste Revision derselben Historie wird nicht automatisch übernommen, sondern als Konflikt behandelt.
- `combined`: neues Ergebnis aus beiden Seiten oder eine ausdrücklich aufgelöste fachliche Änderung. `revision=max(ours.revision,theirs.revision)+1`. `updated_at` ist der größte vorhandene Zeitstempel aus Base, Ours und Theirs plus eine Mikrosekunde. Fehlende Seiten liefern keinen Zeit-/Revisionswert.
- `conflict`: kein Apply vor vollständiger Auflösung.

Für kombinierte Ressourcen ist `updated_by` bei automatischer Zusammenführung `{ "actor_type": "tool", "actor_id": "specroad-merge" }`, bei expliziter Auflösung der im Plan gebundene Auflösungsakteur. Erstellungsmetadaten stammen aus der gemeinsamen Identitätshistorie; abweichende Ursprünge sind Identitätskonflikte. Unveränderbare Evidence, Baselines, Relationsreviews und abgeschlossene Proposals werden niemals kombiniert: gleiche ID und abweichende Originalbytes sind Konflikt. Ein identischer Nachweis darf unverändert übernommen werden.

**Normativer Gegenbeispieltest:** Bei Ours-Revision 3 und Theirs-Revision 7 hat ein kombiniertes Artefakt Revision 8, nicht 4. Planner und Writer wenden ausschließlich `merge-metadata-v1` an und müssen denselben Ressourcen-/Modellhash erhalten. Ein bloß unverändert von Theirs übernommener Stand bleibt Revision 7.

## K.4 Migration

Veränderbare, fachlich oder schema-semantisch transformierte Bestandsartefakte erhalten je Migrationsplan `base.revision+1` und die reguläre deterministische Zeit-/Akteursbindung aus K.2. Neue Begleitartefakte erhalten Revision 1. Ein ausschließlich unverändert übernommener Inhalt wird nicht neu gestempelt. Unveränderbare Legacy-Ressourcen einschließlich der historischen IDs, Revisionen, Zeitstempel und Originalbytes folgen ausschließlich Anhang Q; eine Read-only-Projektion verändert weder Datei noch Originalhash.

---

# Anhang L — Normativer Verification-Context-Hash

## L.1 Zweck

Der vollständige Artefakthash dient Audit, Baselines und Diffs. Für Evidence-Aktualität wird zusätzlich `verification_context_hash-v1` verwendet, damit eine Änderung des Verification Plan Status oder ein reiner Lifecycle-Übergang die Evidence nicht zirkulär entwertet.

## L.2 Projektion

Für Capabilities, Requirements, Tasks, Verification Contracts und Tests wird
eine kanonische Projektion gebildet. Die additive Zulassung von Capabilities
und Tasks ändert weder Algorithmuskennung noch Projektionsbytes der bisher
unterstützten Requirements, Verification Contracts und Tests. Ausgeschlossen sind:

- `revision`;
- `created_at`, `created_by`, `updated_at`, `updated_by`;
- `maturity`;
- `implementation_status`, `verification_plan_status`;
- `verification_waiver` als getrennt gebundene Ausnahmeentscheidung;
- `relations`;
- `tags`;
- reine Lauf- und Ergebnisfelder, die nicht den Prüfgegenstand oder das Oracle definieren.

Enthalten bleiben insbesondere:

- ID und Artefakttyp;
- bei Capabilities Beschreibung, Outcome und Priorität; bei Tasks Beschreibung und sämtliche Done-Kriterien;
- Requirement-Aussage, strukturierte Semantik, Grenzen, Ausnahmen, Applicability und fachliche Extensions;
- beim Verification Contract Vorbedingungen, Verfahren, Oracle, Pass-Kriterium, Evidence-Arten, `evidence_slots` und Konfigurationspolicy;
- beim Test Testidentität, Testtyp, Eingaben, erwartetes Oracle und gemappte Prüfdimensionen;
- Provenienz und fachliche Owner-Felder.

Die Projektion wird nach RFC 8785 kanonisiert und mit SHA-256 gehasht.

### L.2.1 Exakte Capability-/Task-Projektion

**Entscheidung `READINESS-SUBJECT-CONTEXT`, delegiert gemäß
`SPECROAD-DECISION-1`:** Für die nativen, vollständig schemavalidierten
Artefakte `capability` und `task` der Schemaversion `0.2.0` gilt folgende
abschließende Feldliste. Ein untypisiertes Objekt oder ein anderer Artefakttyp
wird nicht in einen dieser Typen umgedeutet.

| Subject | Auf oberster Ebene enthaltene Felder |
|---|---|
| Beide Typen | `schema_version`, `id`, `id_scheme`, `artifact_type`, `title`, `language`, `text_direction`, `owner`, `applicability`, `extensions`, `provenance`, `external_identities`, `display_id` |
| Zusätzlich `capability` | `description`, `outcome`, `priority` |
| Zusätzlich `task` | `description`, `done_criteria` |

Aufgenommen werden ausschließlich tatsächlich vorhandene Felder dieser
Liste mit ihren vollständigen Werten. Optionale fehlende Felder werden
nicht durch `null`, leere Werte oder Defaults ersetzt. Verlangte Felder,
gültige Werte und unbekannte Felder prüft zuvor das native geschlossene
Artefaktschema; eine Hashprojektion repariert keine ungültigen Daten.
Objekte werden nur nach RFC 8785 kanonisiert; Arrays behalten ihre Reihenfolge.

Die vollständig ausgeschlossenen obersten Felder sind `revision`,
`created_at`, `created_by`, `updated_at`, `updated_by`, `maturity`,
`implementation_status`, `verification_plan_status`, `verification_waiver`,
`relations` und `tags`. Ein `verification_result` oder sonstiges berechnetes
Ergebnis ist weiterhin kein zulässiges gespeichertes Subjectfeld.

Innerhalb jedes nativen `provenance`-Eintrags entfällt ausschließlich das
reine Auditfeld `captured_at`. Vorhandene `source_id`, `locator`, `excerpt`,
`content_sha256` und `extensions` bleiben vollständig enthalten. Alle
anderen verschachtelten Inhalte bleiben unverändert, insbesondere
gleichnamige Schlüssel wie `revision`, `maturity` oder `captured_at` in
fachlichen Extensions. Es gibt keine rekursive Namensfilterung.

Gehasht wird das so projizierte Objekt selbst, ohne zusätzlichen Wrapper
oder Domainpräfix, mit RFC-8785-Kanonisierung und SHA-256. Die Kennung bleibt
`verification_context_hash-v1`. Dieselbe native Projektion gilt für die
Herstellung einer Subjectbindung und die spätere Aktualitätsbewertung;
Readiness führt keinen eigenen Hash- oder Verification-Algorithmus ein.
Nicht genannte Subjecttypen erhalten durch diese Erweiterung keine
Unterstützungs- oder Freigabeerklärung.

Die vorhandene Requirement-/Contract-/Test-Projektion einschließlich der
bereits verwendeten Waiver- und Provenienz-Audit-Ausnahmen bleibt bytegleich.
Die Capability-/Task-Erweiterung ergänzt deren bisherigen Definitionsbereich,
sie verlangt keine Migration und keine Umbenennung bestehender v1-Hashes.
Änderungen von Beschreibung, Outcome, Priorität, Done-Kriterien, Applicability
oder anderen eingeschlossenen Feldern ändern den jeweiligen Kontext;
Änderungen allein an ausgeschlossenen Workflow-/Auditwerten tun dies nicht.
Relations-, Freigabe-, Task-Done- und Scopeprüfungen bleiben eigenständige
Pflichten; ein unveränderter Kontexthash bestätigt sie nicht automatisch.

## L.3 Aktualität

Evidence ist bezüglich eines Subjects fachlich aktuell, wenn ID und `verification_context_hash-v1` übereinstimmen; ihre Maßgeblichkeit für ein Verification Result verlangt zusätzlich die Stand-, Pflichtprüfungs-, Konfigurations- und Laufauswahl nach Kapitel 10.5. Vollrevision und Vollhash bleiben als historischer Auditbezug gespeichert, entscheiden aber nicht allein über Aktualität. Eine Änderung der ausgeschlossenen Workflow- oder Auditfelder darf Evidence nicht stale machen. Eine Änderung des Prüfgegenstands, Oracles, Verfahrens, Applicability oder einer gebundenen Konfiguration muss Evidence stale machen.

### L.3.1 Bestandsdaten und Pflichtbewertung

Vorhandene Capability-/Task-Subjects und ihre Evidence bleiben bytegetreu
lesbar, soweit sie die bestehenden Eingabeschemata erfüllen. Die Erweiterung
schreibt keine historischen Subjectbindungen, Vollhashes, Revisionen,
Kontexthashes, Run-Identitäten oder Reviews um. Ein vorheriges
`subject_context_unsupported` ist ein historischer Auswertungsbefund, kein
dauerhaft im Subject gespeicherter Verifikationsstatus.

Eine neue explizite Bewertung berechnet den aktuellen Kontext nach L.2.1
aus den wirklichen Subjectbytes. Vorhandene, exakt passende v1-Bindungen
dürfen unter den unveränderten Regeln aus 10.5 berücksichtigt werden;
abweichende Hashes bleiben stale. Fehlende oder ungültige Pflichtbindungen
erhalten weder einen erfundenen Kontexthash noch einen erfolgreichen Ersatz
durch Revision oder Vollhash. Schemaverletzungen bleiben Eingabefehler;
fehlende verwertbare Nachweise bleiben in der Aggregation unvollständig.

Auch ein übereinstimmender Kontexthash ist allein kein `passed`: vollständige
Pflichtprüfungen, Slots, Dimensionen, maßgebliche Runs, genaue Konfiguration
beziehungsweise ausdrückliche Unabhängigkeit und die Ergebnisprioritäten
aus 10.5 gelten für Capabilities und Tasks ebenso wie für Requirements.
Ein vorhandener `failed`-Nachweis wird nicht wegen der neuen Typunterstützung
zu `passed`; ein Waiver bleibt eine Ausnahme und erfüllt das Readiness-Gate
`verification` nicht. Alle acht Gates aus 10.5.6 bleiben verbindlich.

---

# Anhang M — Normativer Requirement-Testfall-Manifestvertrag

```json
{
  "test_case_format_version": "1.0.0",
  "test_case_id": "SR-TC-0001",
  "requirement_id": "SR-REQ-0001",
  "specification_document_id": "SR-SPEC-0001",
  "specification_document_version": "0.2.3",
  "specification_sha256": "...",
  "primary_verification_id": "SR-VER-0001",
  "method": "automated_cli_test",
  "fixtures": [],
  "preconditions": [],
  "steps": [],
  "oracle": {},
  "expected_diagnostics": [],
  "expected_exit_codes": [0],
  "environment": {},
  "evidence_kind": "test_result"
}
```

`test_case_id` und `requirement_id` besitzen dieselbe vierstellige Nummer. Das Manifest ist nach RFC 8785 kanonisch hashbar. Eine fachliche Änderung des Requirements oder seines primären Verification Contracts verlangt eine neue Testfallmanifestrevision und macht frühere Test-Evidence stale.

---

# Anhang N — Ephemeral Runtime Safety und aufrufbezogener Preflight

## N.1 Geltungsbereich und Wiederherstellungsgrenze

Jeder CLI-Aufruf ist ein unabhängiger Prozesslauf. Eingaben sind die aktuell auffindbare Distribution, die expliziten Aufrufparameter und der aktuell vorhandene Projekt- beziehungsweise Bundleinhalt. Der laufende Prozess darf interne Objekte halten; kein späterer Aufruf benötigt diese Objekte. Die automatische Projektsuche nach Kapitel 12.1 verwendet ausschließlich das aktuelle Arbeitsverzeichnis dieses Aufrufs. Ein in einem früheren Aufruf gewählter Root ist keine implizite Eingabe.

Ein Prozessneustart bei erhaltenen Dateien, ein Wechsel des absoluten Projektpfads und eine neue kompatible Sandbox sind getrennte Testfälle. Für einen abgeschlossenen Stand sind normative Ressourcen, referenzierte Anhänge, benötigte Archivobjekte und die nach dem Bundlevertrag transportierten abgeschlossenen Receipts ausreichend. Eine laufende Transaktion benötigt zusätzlich ihr vollständiges Journal, Staging und Before Images. Diese Wiederherstellungsdaten sind keine entbehrlichen temporären Dateien.

Wird die gesamte Sandbox einschließlich aller ungesicherten Dateien verworfen, kann SpecRoad dort weder starten noch Daten wiederherstellen. Der externe Nutzer beziehungsweise Agent stellt in einer neuen Umgebung die Distribution und das zuletzt außerhalb der verlorenen Umgebung gesicherte, verifizierbare Vollbundle bereit. Danach gelten `bundle verify`, `bundle extract`, Preflight und die normale Projektvalidierung. Änderungen nach diesem Sicherungsstand sind ohne erhaltene Dateien nicht rekonstruierbar. Diese Produktgrenze ist keine automatische Backup-, Upload- oder Cloudfunktion.

Fehlende Python-Laufzeit, fehlende Distribution oder ein vom Host verhinderter Prozessstart liegen vor dem SpecRoad-Preflight. Der aufrufende Agent muss solche Ausführungsfehler erkennen; SpecRoad verspricht dafür keine eigene JSON-Ausgabe. Nach ausführbarem Bootstrap meldet SpecRoad eine unzulässige Laufzeit, unlesbare Eingabe oder fehlende Voraussetzung kontrolliert, soweit der Host dies zulässt.

## N.2 Preflight-Profil und Prüfaufwand

Jeder Command Contract enthält zusätzlich `preflight_profile`, `requires_project`, `requires_git`, `requires_write_paths` und `budget_policy_version`. Das Profil richtet sich nach der tatsächlichen Operation, nicht nur nach dem Gruppennamen.

| Profil | Zugeordnete Aufrufe | Prüfung vor der Fachoperation | Nicht Bestandteil dieses Preflights |
|---|---|---|---|
| `bootstrap` | `--help`, `version`, projektlose `capabilities`, `schema list/show`, `command describe` | ausführbare unterstützte Runtime; lesbare benötigte Distributionsressourcen; gültige Aufrufsyntax | Projektsuche, Projektvalidierung, Git-Prüfung, Modellhash und Indexaufbau |
| `input_read` | `bundle verify <FILE>` ohne Projektauswahl | Runtime, unterstützte Eingabeart und lesbarer expliziter Eingabepfad innerhalb seiner Pfadpolicy | bestehender Projektroot; die vollständige Bundleprüfung ist erst die Fachoperation |
| `project_metadata` | `config show`, `profile explain`, `environment check --project` | aktuelle Root-Auswahl, begrenztes Lesen der benötigten Konfiguration, aktuelle Pfadgrenzen, Betriebsstatus soweit angefordert | vollständiges Artefaktmodell, Anhänge, Quellcode, Baseline-Archiv und Receipt-Historie |
| `project_read` | modelllesende Befehle einschließlich Read-only-Prüfung, Planerzeugung und generierter Ausgabe | Runtime, aktuelle Root-/Schema-Auswahl, ungelöste Transaktion oder Writer-Konflikt, benötigte Eingabe- und ausdrücklich gewählte Ausgabepfade | zusätzliche Vollvalidierung, vollständiges Hashen aller Ressourcen oder Cache-Neuaufbau allein für den Startcheck |
| `project_write` | tatsächliche normative Writes; kein Dry-Run | `project_read`; Schreibvoraussetzungen der konkreten Ziele; Wiederprüfung von Root, Basis, Lock und Recovery-Zustand unmittelbar vor Veröffentlichung | automatisches Reparieren fachlicher Fehler oder Freigeben von Proposals |
| `root_creation` | `init`, `bundle extract` | Runtime und Zielsicherheit nach 11.7; vorhandenes Bootstrap-Journal; benötigte Eingaben; Speicherbedarf der geplanten Erzeugung | bestehendes Projekt als Voraussetzung; eigenmächtiges Überschreiben |
| `recovery` | `recover status/run/discard/restore`, `lock status/recover` | die zur jeweiligen Diagnose oder Recovery erforderlichen Betriebsdateien, Eigentümernachweise und zulässigen Ziele | reguläres Laden eines inkonsistenten Modells als gültiger Arbeitsstand |

`environment check` ohne `--project` benutzt `bootstrap` und sucht keinen Root. `--for-command` ergänzt die angeforderten Voraussetzungen nach N.4. Git-unabhängige Befehle prüfen Git weder durch Prozessstart noch durch Repositoryscan. Der Dry-Run eines normativen Befehls erbt dessen fachliche Planung, benutzt aber den schreibfreien Preflight.

Der normale Startcheck enumeriert keine Artefakte, Quellcodedateien, Anhänge, Archivobjekte oder historischen Receipts. Er liest nur die unmittelbar benötigten Metadaten und prüft den aktiven Transaktionsbereich. Abgeschlossene Journale werden nach dauerhaftem Abschlussbeleg aus dem aktiven Bereich entfernt beziehungsweise in den beleggebundenen Archivbereich überführt; der Receiptvertrag bleibt erhalten. Ein während dieser Bereinigung unterbrochener Lauf wird konservativ als noch zu untersuchender Betriebszustand behandelt.

Der kurze automatische Preflight untersucht höchstens 1 MiB Metadaten und 16 aktive Journale beziehungsweise unklare Journaleinträge. Diese Grenzen begrenzen allein die unmittelbare Startphase, nicht den Gesamtauftrag. Ist dadurch noch keine sichere Entscheidung möglich, liefert er `preflight_detail_required` mit SRV167 und wechselt in eine ausdrücklich ausgewiesene, nach Anhang P fortsetzbare Metadatenphase. Ein Aufruf kann diese Phase gleich beginnen oder mit gesichertem Cursor und Exit Code 8 übergeben. Jede weitere Phase untersucht einen neuen begrenzten Bereich; ein stets neu gestarteter identischer Präfix ist unzulässig. Das reguläre Modell bleibt bis zur Klärung gesperrt. Es gibt allein wegen dieser Startschwelle keinen Code 5.

Ein größeres Journal muss nicht vollständig gelesen werden, um tatsächlichen Recoverybedarf festzustellen. Ein eindeutig erkannter Recoverybedarf folgt sofort N.3; die Detailphase führt keine implizite Recovery durch. Ein konkreter beschädigter Deskriptor, tatsächlicher I/O-Mangel oder nachgewiesener Konflikt erhält die jeweilige Fehlerklasse statt endloser Detailphasen. Auch der explizite Recovery-Befehl verwendet sparsame Verarbeitung; weiche Arbeitsziele gelten nach O.4. Weder kurzer Preflight noch Detailphase dürfen eine fachliche Vollvalidierung oder einen rekursiven Repository-/Archivscan als bloße Startprüfung auslösen.

Ein erfolgreicher Preflight ist eine Momentaufnahme, keine Garantie für später fortbestehende Dateien, Berechtigungen oder freie Ressourcen. Beim tatsächlichen Öffnen, Schreiben, Sperren und Veröffentlichen bleiben die entsprechenden Fehlerprüfungen verbindlich. Vor einer normativen Veröffentlichung werden die im Change Plan gebundenen Vorbedingungen unter dem Writer-Lock erneut geprüft. Zeitstempel, Pfadgleichheit oder ein früherer Preflight ersetzen diese Prüfung nicht.

## N.3 Recovery ohne Read-only-Verletzung

| Aufruf und vorgefundener Zustand | Verbindliches Verhalten |
|---|---|
| Normaler Aufruf; kein Konflikt und keine unvollständige Transaktion | Nach bestandenem Preflight Fachoperation ausführen. |
| Read-only-, Plan-, generierter Ausgabe- oder Dry-Run-Aufruf; ungelöste Transaktion | Exit Code 5, `recovery_required=true`, keine Fachoperation und keine Veränderung von Projekt oder Betriebsdaten. |
| Normativer Write ohne Dry-Run; ungelöste Transaktion; `transaction_policy.auto_recover=false` | Derselbe diagnostische Abbruch; explizite Recovery erforderlich. |
| Normativer Write ohne Dry-Run; ungelöste, nachweislich nicht mehr aktive und automatisch lösbare Transaktion; `auto_recover=true` | Ausschließlich Recovery nach Anhang C ausführen. Danach Exit Code 5 mit `normal_operation_started=false`, tatsächlich erreichtem Recovery-Ergebnis und Hinweis auf erneuten Aufruf. Die ursprünglich angeforderte Änderung wird in diesem Lauf nicht begonnen. |
| Fremder, aktiver oder nicht sicher beurteilbarer Lock-Eigentümer | Keine automatische Übernahme; Eigentümer-/Risikonachweis nach dem bestehenden Lockvertrag verlangen. Ein neuer Hostname oder eine wiederverwendete PID beweist keinen verwaisten Lock. |
| Korrupte oder fehlende notwendige Recovery-Daten | Normale Nutzung blockieren; Diagnose im Read-only-Aufruf, dauerhafte Statusänderung nur durch zulässigen Recovery-Write. Restore nur aus verifizierter Quelle. |
| `environment check`, `recover status` oder `lock status` bei blockiertem Projekt | Begrenzte Diagnose der verfügbaren Metadaten erlauben, ohne das Modell als gültig zu laden oder ein Journal zu ändern. |

Eine automatische Recovery verbraucht weder die Request-ID noch ein Erfolgsreceipt der noch nicht begonnenen Fachoperation. Für die wiederhergestellte frühere Transaktion gelten deren bestehende Request-ID und Receipts. Bereits vollständig veröffentlichte Transaktionen werden entsprechend `SR-REQ-0258` abgeschlossen; ein nur teilweise veröffentlichter `committing`-Stand wird entsprechend `SR-REQ-0511` auf die Basis zurückgerollt. Fehlende Erhaltung der Recovery-Daten darf nicht durch Neuinitialisierung oder stillschweigende Annahme eines gültigen Mischstands übergangen werden.

## N.4 `environment check`

```text
specroad environment check
  [--project <PATH>]
  [--for-command <COMMAND-ID>]
  [--resource-profile constrained|standard]
  [--format pretty|json]
```

`COMMAND-ID` ist die durch `command describe` ausgewiesene kanonische, punktgetrennte Befehlskennung, beispielsweise `validate`, `artifact.update` oder `proposal.check`; Kurzaliase werden vor der Prüfung aufgelöst. Die Option prüft die Voraussetzungen der bezeichneten Befehlsart, führt diese aber nicht aus. Fehlen dafür konkrete Fachargumente oder eine ausdrücklich benötigte Projektauswahl, ist die betroffene Voraussetzung `unknown`; es werden keine Eingaben erfunden.

Der Befehl ist `read_only`. Er startet keine externen Programme, erzeugt keine Probedatei, initialisiert kein Projekt und führt weder einen Benchmark noch eine Modellvalidierung aus. Schreibbarkeit und Dateisystemfähigkeiten, die ohne schreibenden Versuch nicht nachweisbar sind, werden als `unknown` ausgewiesen. Die tatsächliche Schreiboperation muss ihre eigenen Dateisystemoperationen weiterhin prüfen.

Das JSON verwendet den Envelope aus 11.5. `result.environment_format_version` ist `1.0.0`; `result` besitzt folgende Pflichtfelder:

| Feld | Typ und Bedeutung |
|---|---|
| `compatible` | `true`, `false` oder `null`; Ergebnis ausschließlich der angeforderten Runtime-/Metadatenvoraussetzungen. Ein fehlgeschlagener Pflichtcheck ergibt `false`, ein ungeklärter Pflichtcheck ohne Fehler `null`, sonst `true`. |
| `operation_readiness` | `not_requested`, `ready`, `blocked` oder `unknown`; keine Aussage über fachliche Modellgültigkeit. |
| `python` | Objekt mit Version, Implementierung und Supportstatus der laufenden Runtime. |
| `distribution` | Distributionsart und Buildkennung; kein rekursives erneutes Hashen der gesamten Distribution. |
| `checks` | nach `check_id` sortierte Objekte mit `check_id`, `required`, `state=passed\|failed\|unknown\|not_applicable` und begründender Diagnose. |
| `recovery_required` | Boolean oder `null`, falls kein Projekt ausgewählt beziehungsweise keine sichere Feststellung möglich ist. |
| `resource_policy` | Policy-Version, gewähltes Ressourcenprofil, effektive Budgets und jeweilige Herkunft nach Anhang O. |
| `observations` | Werte für CPU-Kapazität, Memory-Limit und Speicherbeobachtung jeweils mit `value`, `unit`, `source`, `state=observed\|unknown`; nicht ermittelbare Werte sind `null`. |
| `semantic_validation_performed` | immer `false`. |

Ohne festgestellten Fehler ist ein vollständig erstellter Diagnosebericht Exit Code 0, auch wenn einzelne Voraussetzungen ungeklärt sind; `compatible=null` ist ausdrücklich keine Kompatibilitätsbestätigung. Ein festgestellter Runtime-, Zugriffs- oder Recoveryblocker ergibt Exit Code 5; Nutzungs-, Modellformat- und Sicherheitsfehler behalten die Codes 2, 3 und 7. Das jeweilige Ergebnis bleibt maschinenlesbar. Optionale, nicht verfügbare Ressourcenbeobachtungen erzeugen keinen Kompatibilitätsfehler.

Gesamtspeicher oder CPU-Anzahl eines Hosts werden nicht als garantierte Sandbox-Zuteilung bezeichnet. Nicht vorhandene oder nicht vertrauenswürdig zuordenbare Quoten bleiben unbekannt. Messwerte und Pfade enthalten keine vollständige Umgebung, Benutzergeheimnisse oder fremde Dateiinhalte. Betriebssystembeobachtung ist auf notwendige, verfügbare Runtime-APIs beziehungsweise eng begrenzte Prozess-/Quotenmetadaten beschränkt; sie ist keine neue Laufzeitabhängigkeit.

Der Bericht kann sich bei identischem Projektinhalt durch die Umgebung verändern. Er ist deshalb eine betriebliche Diagnose, kein deterministisches fachliches Artefakt. Er geht weder in Modell-, Scope-, Profil-, Change-Plan- noch in Operationshashes ein.

---

# Anhang O — Ressourcensparsame vollständige Verarbeitung

## O.1 `runtime-budget-v2`: Arbeitsziele statt automatischer Fehlergrenzen

Ohne Auswahl gilt `constrained`. Die beiden Profile bieten denselben fachlichen Funktionsumfang, dieselben Nachweise und dieselbe Prüfstrenge. Die folgenden Werte sind **weiche Optimierungsziele**, keine Anbieterquoten und keine Obergrenze für den vollständigen Auftrag.

| Größe | `constrained` | `standard` | Verhalten bei Erreichen |
|---|---:|---:|---|
| CPU-Arbeitsziel je Aufruf | 30000 ms | 120000 ms | Bilanzieren, sparsamer weiterarbeiten oder Checkpoint; kein Budgetfehler. |
| verstrichene Zielzeit je Aufruf | 60000 ms | 300000 ms | Fortsetzungspunkt vor langem Weiterlauf bevorzugen. |
| Zielwert eigener Speicherbelegung | 256 MiB | 1024 MiB | Puffer/Memoisierung reduzieren, streamen oder auslagern; reale Hostgrenze gesondert prüfen. |
| Zielwert eigener Scratch-Spitze | 512 MiB | 4096 MiB | Daten deduplizieren, in kleinen Chargen verarbeiten; zulässige Überschreitung nur bedarfsbezogen. |
| Grapharbeit je Aufruf | 2000000 Schritte | 10000000 Schritte | Offene Frontier und exakte Ausgabearbeit fortsetzbar speichern. |
| vollständige Beziehungspfade je Ausgabecharge | 4096 | 16384 | Weitere Pfade in vollständigen Folgechargen erzeugen. |
| Inline-stdout-Zielgröße | 16777216 Bytes | 67108864 Bytes | Vollständiges Resultat extern liefern; keine stille Kürzung. |
| gelesener persistenter Cache je Aufruf | 32 MiB | 128 MiB | Zusätzliche Cachearbeit unterlassen, originäre Eingaben korrekt weiterverarbeiten. |
| bevorzugter I/O-Transferblock | 65536 Bytes | 65536 Bytes | Große Payloads weiterhin blockweise, nicht vollständig im Speicher halten. |
| bevorzugter CPU-Teilschritt | 5000 ms | 30000 ms | Größere Aufträge in mehrere Aufrufe teilen. |
| bevorzugte Wall-Clock je Teilschritt | 10000 ms | 60000 ms | Zum nächsten sicheren Fortschrittspunkt zurückkehren. |

Die vorhandenen Optionen `--cpu-budget-ms`, `--wall-budget-ms`, `--memory-budget-mib` und `--scratch-budget-mib` setzen diese weichen Ziele. `--step-cpu-ms` und `--step-wall-ms` setzen die bevorzugten Aufteilungsfenster; sie müssen positive Ganzzahlen sein. Ein expliziter Teilschrittwert darf das übergeordnete weiche Ziel überschreiten, wenn der Aufrufer dies bewusst verlangt; die effektive Auswahl und Herkunft werden ausgewiesen. Werte `0`, negative Zahlen und `unlimited` bleiben Nutzungsfehler. Ein vollständiger Auftrag hat keine automatische maximale Summe an Schritten, Prompts oder kumulierter CPU-Zeit.

Die Runtime erhöht nicht heimlich die deklarierten Ziele, sondern meldet `soft_budget_exceeded` und begründet eine nötige Fortsetzung darüber hinaus. Sie aktiviert dadurch weder weitere Worker noch teurere Parallelität. Kurze fertige Aufträge werden nicht künstlich verlangsamt oder auf mehrere Prompts verteilt. Ein CPU-Zeitwert bezeichnet verbrauchte Rechenzeit, keine garantierte momentane CPU-Prozentquote.

### Abschließende Grenzklassifikation

| Klasse | Zugeordnete Werte | Verbindliche Wirkung |
|---|---|---|
| `soft_work_target` | alle obigen Arbeitsziele; Gesamtmodellgröße, gesamte Relationenzahl, gesamte Importobjekte, Merge-Konfliktanzahl, Diagnoseanzahl und kumulierte Graph-/SRX-Auswertungsarbeit | Charge verkleinern, streamen, auslagern oder fortsetzen; vollständigen Restauftrag erhalten. |
| `semantic_scope` | explizite Queryfilter, Offset/Limit, angeforderte Tracetiefe, ausgewählte Konfiguration und gebundener Scope Descriptor | Exakt den gewählten Fachvertrag erfüllen; keine stille Verkleinerung durch ein Ressourcenprofil. |
| `hard_safety_or_format` | Verbot von Codeausführung/Netzwerk; Pfad-/Symlinkgrenzen; zulässige Archivtypen und kanonisches ZIP-Format; XML-/JSON-/SRX-Strukturtiefe; zulässige Syntax/Operatoren; ausdrücklich begrenzte Einzelobjekt-/Archivexpansion zum Schutz des Parsers; Actor- und Freigabepolicies | Vor gefährlicher Verarbeitung ablehnen, Originaldaten und Diagnose erhalten; niemals automatisch lockern. |
| `observed_host_limit` | tatsächlich verfügbare Speicher-/Datenträgerkapazität, Betriebssystemquota, Prozessende, nicht ausführbarer Start, Zugriffsrechte | Sparsame Alternative versuchen, sofern sicher; bei wirklicher Unausführbarkeit konkreten Blocker ausweisen. Keine Umgehung von Hostrestriktionen. |

Frühere pauschale Formulierungen „Ressourcengrenze überschritten“ werden ausschließlich nach dieser Klassifikation ausgelegt. Ein Gesamtmengenzähler ist kein Sicherheitsverbot. Ein Struktur-/Sicherheitslimit ist kein frei überziehbares Budget. Profile komponieren nur ihre semantischen und Sicherheitswerte nach Kapitel 10.10. Beim Lesen historischer `resource_limits` werden weiche Gesamtmengen-/Rechenwerte als Betriebsvorgaben ausgewiesen und aus der effektiven semantischen Konfigurationsprojektion ausgeschlossen; fachliche Paginationdefaults, explizite Scopes und harte Strukturgrenzen bleiben darin. Eine Policyumstellung erzeugt einen neuen aktuellen Konfigurations-/Modellhash, ohne ältere Baselines umzuschreiben. Die Überführung wird im Migrationsplan genannt; betriebliche Ziele bleiben anschließend außerhalb der fachlichen Modellwurzel. Eine im Benchmark genannte Projektgröße ist keine zulässige automatische Ablehnungsgrenze.

## O.2 Verbrauch, Fortschritt und Kontrollen

Verbrauch umfasst Bootstrap, Preflight, Laden, notwendige Validierung, Hashing, Scope-Closure, Staging, Ausgabe und zulässige Git-Unterprozesse. Der Arbeitsstand speichert Verbrauch je Aufruf und kumuliert über den Auftrag. Ein weiterer Prompt setzt die Gesamtsumme nicht auf null; die neue sichere Ausführungszeit ist aber ein neues Arbeitsfenster und kein verbotenes Budget-Umgehen.

CPU- und Wall-Clock werden getrennt gemessen. Wo Messwerte fehlen, ist der Wert `null` mit Messart `unknown`; verbuchte eigene Bytes werden nicht als gemessener Gesamt-RSS ausgegeben. Der Core braucht keine externen Monitoringprozesse. Kontrollpunkte liegen mindestens nach 128 Graphschritten, 512 SRX-Auswertungsschritten, 64 KiB gestreamten Payloadbytes sowie vor/nach großen Lade-, Sortier-, Hashing- und Veröffentlichungsphasen. Betriebssystemaufrufe können erst bei Rückgabe oder unterstützter Unterbrechung kontrolliert werden; keine universelle präemptive Millisekundengarantie.

Ein Graphschritt ist Knotenentnahme, Kantenprüfung oder Erweiterung eines auszugebenden Pfads. Alle kürzesten Pfade von `why` bleiben Teil des Auftrags; eine kompakte Vorgängerdarstellung darf die interne Berechnung beschleunigen, ersetzt aber die versprochene vollständige Ausgabe nicht. `query --limit 1` berechnet weiterhin das exakte `total`. Diagnose-Spooling erhält sämtliche Pflichtdiagnosen und deren endgültige Reihenfolge. Eine Pause nach einem Präfix ist kein fachliches Endergebnis.

## O.3 Adaptiver sparsamer Versuch

Vor einer großen Allokation oder erneuten Ausführung prüft SpecRoad die günstigste semantisch gleichwertige Variante: nicht benötigte Memoisierung freigeben, kleinere Puffer/Chargen, Streaming, dateibasierte Sortierläufe, persistierte Frontier, Wiederverwendung nachweislich gültiger Zwischenergebnisse. Der Vollauftrag wird nicht pauschal wegen einer Schätzung als zu groß abgelehnt. Ist ein kleinster erforderlicher Schritt voraussichtlich sicher ausführbar, wird er auch bei überschrittenem weichem Ziel versucht.

Ein deklarierter Arbeitszielwert ist keine Erlaubnis zur unbegrenzten RAM-Allokation. Bekannte kleinere Hostgrenzen sind maßgeblich. Bei unbekannter Quota werden konservative Blöcke verwendet; unbekannt bedeutet weder garantiert verfügbar noch erwiesenermaßen unmöglich. Ein nicht mehr passender Datensatz wird nach Möglichkeit token-/blockweise geparst und verarbeitet. Für nicht weiter teilbare Kernel dokumentiert `command describe` minimale Eingaben und einen Fortsetzungs-/Blockerpfad. Ein tatsächlich nicht ausführbarer Mindestschritt erfordert einen belegten Blocker, nicht eine Endlosschleife.

Before Images, aktive Journale, bestätigte Checkpoints und für deren Fortsetzung benötigte Snapshots sind keine entbehrlichen Caches. Sie werden nicht gelöscht, um einen neuen Auftrag zu beginnen. Die eigentlichen fertigen Ergebnisse benötigen realen Speicherplatz; Aufteilung erschafft keinen zusätzlichen Datenträgerplatz. Erkennt die Runtime einen echten Mangel, bleiben gesicherter Fortschritt und eine konkrete Abhilfe erhalten.

`--cache read` nutzt ausschließlich vorhandene, durch Inhaltshash, Tool-/Schema-/Policy-/Abhängigkeitsbindung bestätigte Einträge. `--cache off` ignoriert sie. `mtime`, Dateigröße, Pfad oder Hostname allein beweisen keine Gültigkeit. Fehlende, ungültige oder zu teure Caches werden ignoriert. Read-only-Fachbefehle schreiben keine Projektcaches. Externe Work-Zwischenergebnisse nach Anhang P sind ausdrücklich gebundene Arbeitsdaten, nicht implizite Caches.

## O.4 Entscheidung bei Überschreitung und Veröffentlichung

| Situation | Verbindliche Reaktion |
|---|---|
| Auftrag vollständig | Fachresultat und tatsächlichen Gate-Ausgang liefern. |
| Weiches Ziel erreicht, kleiner sicherer Rest | Sparsam zu Ende arbeiten, Überschreitung betrieblich ausweisen. |
| Weiches Ziel erreicht, erhebliche Restarbeit | Kleinste sinnvolle Charge verarbeiten, Checkpoint sicher veröffentlichen; `continuation_required`, Code 8. |
| Winziges Ziel verhindert jeden Fortschritt | Mindestens eine sicher ausführbare kleinste Einheit auch oberhalb des weichen Ziels erledigen; andernfalls konkreten Mindestressourcenblocker belegen. |
| Bereits bestätigter Checkpoint | Fortsetzen statt wieder von vorne zu rechnen; nur unbestätigte letzte Einheit erneut ausführen. |
| Geplante Pause vor normativer Veröffentlichung | Fachlicher Ausgangsstand bleibt regulär lesbar; externe Work-Daten erhalten, keinen Projektwriter-Lock über die Pause halten. |
| Weiches Ziel während `committing` überschritten | Keine freiwillige Promptpause; sicheren Commit oder Recoveryabschluss bevorzugt über das weiche Ziel hinaus fortführen. |
| Echter Host-/I/O-Abbruch während Commit | Bestehendes Journal, Staging und Before Images erhalten; kein regulär ladbarer Mischstand. Weiterer Aufruf folgt ausschließlich Recoveryvertrag. |
| Vollständiges Ziel und Receipt bereits dauerhaft | Commit gilt als erfolgt; Output-/Cachefehler erzeugen kein erneutes fachliches Apply. |
| Sicherheitspolicy verletzt | Code 7 und konkrete Diagnose; keine automatische Aufweichung. |
| Reale Ressourcen verhindern auch sparsame kleinste Einheit | Code 5 mit `blocked_reason`, bereits versuchten Alternativen, gesichertem Arbeitsstand und genau benannter nötiger Voraussetzung. |

Die bisherigen 10000 ms CPU und 30000 ms Wall-Clock für einen sicheren Abschluss sind nun bevorzugte Abschlussreserven, keine Ursache für das Abbrechen einer noch sicher ausführbaren Recovery. Vor neuen großen Allokationen werden 4 MiB eigener Metadatenspeicher und 16 MiB Scratch als bevorzugte Kontrollreserve berücksichtigt; auch diese Zahlen garantieren nichts bei hartem OOM-Kill oder Dateiverlust. SpecRoad hält zwischen regulären Promptschritten keine laufende Transaktion offen. Eine infolge echten Abbruchs ungelöste Transaktion ist eine ausdrücklich ausgewiesene Recoveryausnahme, kein normaler Checkpoint.

Ein Resultat ist erst vollständig, wenn jede Pflichtarbeit des gebundenen Scopes geprüft, jede erforderliche globale Konsistenzregel ausgewertet und jedes Pflichtartefakt vollständig veröffentlicht beziehungsweise geliefert ist. Ein kleineres Budget erlaubt weder weniger Prüfung noch automatische Zustimmung noch `passed` für nicht erledigte Arbeit.

## O.5 Metriken, Determinismus und Wiederholung

Für die Projektselbstbeschreibung ist ausschließlich `{format_version,semantic}` nach Kapitel 11.5.1 die deterministische Fachprojektion. Das verpflichtende `runtime`-Objekt bleibt korrekt und aufrufaktuell, gehört aber nicht zu dieser Projektion. Die Bewertungsauswahl nach 10.5 ist dagegen fachlicher Input und darf nicht als Betriebsmetrik aus der Ergebnisbindung entfernt werden.

`--metrics` ergänzt `summary.runtime` mit Profil, `runtime-budget-v2`, Verbrauch je Aufruf und kumuliert, Messarten, Scratchpeak und Überschreitungsereignissen. Die Pflichtfelder einer Fortsetzung enthalten auch ohne Metrikoption deren Identität, Fortschritt und nächste Aktion. Laufzeitmesswerte und Chunkreihenfolge gehören nicht in Modellwurzel, fachliche Ergebnisbytes oder semantische Requesthashes.

Ein vollständiger Lauf über viele kleine Schritte und derselbe vollständige Einzellauf liefern identische fachliche Ergebnisse. Normative Änderungs-IDs, Akteur, Planmetadaten und Request-ID werden einmal gebunden, nicht pro Prompt neu erzeugt. Eine Änderung des Ressourcenprofils oder Schrittfensters ändert nicht den Auftrag. Fachliche Eingabeänderungen ergeben dagegen stale/conflict nach Anhang P.

## O.6 Herkunft und Geltung

Die Arbeitsziele und Algorithmen sind neue SpecRoad-Produktvorgaben aus der Nutzerentscheidung vom 6. September 2026: trotz weicher Budgetüberschreitung möglichst sparsam weiterarbeiten, den vollständigen Auftrag erhalten und nötigenfalls mehrere Prompts verwenden. Sie behaupten weder bestimmte Chatbot-Laufzeitgrenzen noch bereits gemessene Implementierungsergebnisse. Die unveränderten Referenzbenchmarks aus Kapitel 14 bleiben harte **Abnahmekriterien für die Implementierungsqualität**, sind aber keine versteckte automatische Laufzeit-Abbruchpolicy.


# Anhang P — Vollständige Arbeitsaufträge, Checkpoints und mehrere Prompts

## P.1 Systemgrenze und Zustände

SpecRoad verarbeitet Daten über CLI-Aufrufe. Es besitzt keinen LLM-Client, eröffnet keine Chats und verschickt keine Prompts selbst. Es kann einen maschinenlesbaren Fortsetzungsauftrag und daraus einen begrenzten Textprompt ausgeben. Nutzer oder externer Agent führen die nächste Nachricht beziehungsweise den nächsten CLI-Aufruf aus. Ein Prompt ist eine Bedienhilfe, nicht die fachliche Source of Truth; maßgeblich bleiben gebundene Spezifikation, Projekt und Arbeitspaket.

Ein Arbeitsauftrag trägt eine zufällige 128-Bit-ID `WORK-<TOKEN>` und einen dieser Zustände:

| Zustand | Bedeutung | Zulässige Folge |
|---|---|---|
| `running` | aktiver Prozess verarbeitet eine sicher abgegrenzte Einheit | `ready_to_resume`, `completed`, `blocked`, `recovery_required`, `cancelled` |
| `ready_to_resume` | konsistenter Checkpoint; offene Arbeit vollständig beschrieben | `running`, `cancelled` |
| `blocked` | tatsächlich fehlende Voraussetzung oder belegter Konflikt | nach behebender externer Änderung `running` oder neu gebundener Auftrag; sonst `cancelled` |
| `recovery_required` | unterbrochene normative Transaktion | ausschließlich Recovery; danach Receipt prüfen und Auftrag abschließen oder verbliebene Vorbereitung fortsetzen |
| `completed` | alle Arbeit und Ergebnislieferung abgeschlossen; fachlicher Ausgang separat gespeichert | Endzustand; Retry liefert dasselbe Resultat |
| `cancelled` | Nutzer hat den noch unveröffentlichten Auftrag ausdrücklich beendet | Endzustand; kein fingierter Erfolg |

`completed` bedeutet technisch abgeschlossen, nicht notwendigerweise fachlich bestanden. Beispielsweise ist eine vollständig durchgeführte Validierung mit Fehlern `completed` und hat fachlichen Exit Code 1. Ein bloßes Budgetereignis setzt nicht `blocked`.

## P.2 Externer Work-Root und Schreibrechte

Ein umfangreicher Fachbefehl kann `--work-dir <DIR>` erhalten. Das Verzeichnis muss fehlen, leer sein oder zu exakt demselben Auftrag gehören. Ohne expliziten Pfad legt die Runtime beim ersten erforderlichen Checkpoint einen exklusiv erzeugten externen Work-Root im verfügbaren temporären Verzeichnis an und gibt seinen tatsächlichen Pfad aus. Ein kleiner Befehl erzeugt keinen Work-Root. Standardmäßig ist kein Schreibzugriff auf den Projektroot nötig, um Read-only-Arbeit fortzusetzen.

Der Work-Root liegt außerhalb des normativen Projekts und seiner `.specroad/`-Betriebsdaten. Symlinks, Spezialdateien, Traversal und Pfadüberschneidungen mit Eingaben oder fachlichen Ausgabezielen werden abgewiesen. Work-Dateien werden mit möglichst eingeschränkten Benutzerrechten erzeugt. Die gleiche Schutzpflicht wie für die Projektdaten gilt für dort gespeicherte Kopien.

Snapshots, Checkpoints und externe fachliche Ausgaben sind ausdrücklich ausgewiesene Seiteneffekte. Sie erlauben Read-only-/Dry-Run-Befehlen keine Änderung des Projekts. Ist kein externer Arbeits-/Ausgabepfad schreibbar, versucht der Befehl eine sichere kleinere In-Memory-Variante; ist auch diese tatsächlich nicht ausführbar, nennt er den fehlenden Schreibplatz als realen Blocker statt Erfolg zu behaupten.

Ein planmäßiger Schrittwechsel löst den Work-Lock und hält keinen Projektwriter-Lock. Der nächste Aufruf prüft Work-Identität und Lock-Eigentümer neu. PID oder Hostname allein berechtigen nicht zur Lockübernahme. Nach echtem Prozessabbruch wird nur der letzte vollständig veröffentlichte Checkpoint anerkannt.

## P.3 Datenvertrag `work-v1`

Der Work-Root enthält mindestens `work.json`, `checkpoints/`, `objects/` und `results/`. `work.json` bezeichnet atomar die letzte vollständige Checkpointgeneration. Alle Nutzdaten sind JSON oder rohe datengehashte Payloads. `pickle`, ausführbare Skripte, serialisierte Pythonobjekte und aus Eingabedaten geladener Code sind unzulässig.

| Feld | Verbindliche Bedeutung |
|---|---|
| `work_format_version` | `1.0.0`; unbekannte inkompatible Version wird vor Fortsetzung abgewiesen. |
| `work_id`, `checkpoint_generation` | feste Identität und monoton steigende veröffentlichte Generation. |
| `command_id`, `command_class`, `normalized_arguments` | geprüfter eingebauter Command Contract, normalisierte Fachargumente und ausdrücklich gebundene Schreibklasse; keine Shellzeichenkette. |
| `actor`, `request_id`, `operations_sha256` | ursprüngliche Berechtigung und Schreib-Idempotenzbindung bei normativen Aufträgen; keine automatische Actoränderung beim Resume. Bei Analyzerarbeit sind diese drei Work-Felder `null`; die getrennte Analysekennung steht im gebundenen Analyzerrequest und gegebenenfalls in `normalized_arguments.analysis_id` nach T.3. |
| `tool_build`, `algorithm_versions`, `schema_versions` | nachgewiesene Kompatibilität der Checkpointdaten. Ein neues Tool darf nur mit explizitem kompatiblen Leser fortsetzen. |
| `source_bindings`, `input_manifest_sha256` | Projekt-ID, benötigte Scopes, Quellmodelle, eingefrorene Daten-/Profil-/Konfigurations-/Mappinghashes und externe Eingabepayloads. |
| `plan_binding` | vorhandene Change-/Merge-/Import-/Migrationspläne einschließlich fixer IDs, Zielmetadaten, Basis und Freigabebindungen; solange noch nicht planbar ausdrücklich `null`. |
| `phase`, `frontier`, `cursors` | konkrete offen gebliebene Arbeit; ein Text wie „weitermachen“ reicht nicht. |
| `completed_manifest_sha256`, `remaining_manifest_sha256` | gehashte Nachweise über abgeschlossene Einheiten und vollständigen offenen Auftrag, einschließlich noch zu expandierender deterministischer Arbeit. |
| `result_parts`, `diagnostic_parts` | vollständig geschriebene, gehashte und geordnete Teile; keine stillen verworfenen Befunde. |
| `progress`, `consumption` | bestätigte Einheiten, bekannte Gesamtzahl oder `null`, Summen je Phase und über alle Schritte; unbekannte Arbeit bleibt offen. |
| `state`, `blocked_reason`, `next_action` | aktueller Zustand, tatsächlicher Blocker oder `null`, konkrete nächste Operation. |
| `checkpoint_sha256` | SHA-256 der kanonischen Checkpointprojektion ohne dieses Feld. |

Große Listen werden als versionierte gehashte Manifestsegmente abgelegt, nicht als unbegrenzt großes Kontroll-JSON. Jedes Segment hat ID, Größe, Hash und Eintragszahl. Fehlende Segmente, Hashabweichungen, doppelt anerkannte Einheiten und unbekannte notwendige Felder verhindern ein unbemerktes Resume. Der alte vollständige Checkpoint bleibt gültig, bis die neue Generation mit allen referenzierten Teilen dauerhaft und atomar veröffentlicht ist.

Für `recover.restore` gilt die geschlossene Workbindung aus 10.7.7. Sie ergänzt ausschließlich diesen inneren Recoverybefehl: keine erfundene Ausgangsmodellwurzel, keine Change-Plan-Operationsfolge und keine gespeicherte Autorität. Die dort ausdrücklich gebundenen Originalplanfelder werden durch die folgende allgemeine Lokalisierungsregel nicht umgeschrieben.

Absolute Laufzeitpfade sind Lokalisierungsdaten und nicht Teil der semantischen Aufgabenidentität. Bei Restore werden sie durch überprüfte Rootzuordnung ersetzt. Daten- und Inhaltshashes, Actor, Operationen und Freigabebindungen ändern sich dabei nicht.

## P.4 Bindung der Eingaben und Snapshotaufbau

Aufwendige Läufe arbeiten auf einem gebundenen Eingangssnapshot. Dessen Aufbau selbst ist aufteilbar: deterministische Enumeration, blockweises Lesen/Hashen, abschließende Validierung des Manifests. Vor einem vollständigen Manifest darf die Runtime bereits gesicherte Arbeit bilanzieren, aber noch keine vollständig gebundene Modellwurzel erfinden. Änderung oder Verlust einer noch benötigten Quelldatei wird konkret gemeldet.

Ein aktiver SpecRoad-Writer beziehungsweise ungelöste Transaktion verhindert eine falsche Snapshotbestätigung. Ändern sich Quellen während des Aufbaus, werden die betroffenen Einträge neu gelesen; es erfolgt keine stillschweigende Mischung als angeblich aktuelle Momentaufnahme. Dateigröße oder `mtime` allein reichen als Inhaltsbeweis nicht. Nicht kooperierende externe Dateibearbeitung kann nicht vollständig verhindert werden; eine inkonsistente oder nicht nachweisbare Eingangsbindung ist ein Konflikt.

Nach Versiegelung verwendet der Auftrag seine unveränderbaren, content-addressierten Snapshotbytes; eine neue Projektwurzel führt nicht zum Wiederholen bereits gültig abgeschlossener Analyse. Read-only-Resultate bezeichnen die tatsächlich geprüfte Snapshotwurzel und behaupten nicht, einen später veränderten Arbeitsstand geprüft zu haben. Vor jedem normativen Apply werden die aktuelle Basis, erwarteten Artefakthashes und Berechtigungen unter dem Writer-Lock erneut mit dem gebundenen Plan verglichen. Eine Abweichung ist Code 6, niemals automatisches Rebase oder stille Scopeänderung.

Ein vollständiger Eingangssnapshot ist zur Fortsetzung auch nach Pfad-/Sandboxwechsel ausreichend, soweit der konkrete Auftrag keine neu zu überprüfenden Write-Ziele benötigt. Hashes allein rekonstruieren keine fehlenden Bytes. Bei fehlendem unersetzbarem Snapshot nennt die Runtime die konkrete Ressource; eine sichere Neuberechnung ist nur aus erneut vorhandenen, hashidentischen Originaldaten zulässig.

## P.5 Vollständigkeit und monotones Vorankommen

Der Aufgabenplan enthält jede verpflichtende Phase des gebundenen Commands: zum Beispiel Eingangsbindung, Validierung, globale Graphregeln, Auswertung, Zielplanung, Nachprüfung und Ergebnislieferung. Einheiten besitzen stabile Schlüssel aus Phase, Eingangsbindung und deterministischem Bereich. Grenzen dürfen nur dort liegen, wo eine Einheit vollständig bestätigt oder mit ausreichend Cursorzustand präzise fortgesetzt werden kann.

Für Graphen bleiben Frontier, besuchte Zustände und noch auszugebende Pfade erhalten. Für Sortieren bleiben sortierte Läufe und Mergecursor erhalten. Für große Payloads bleiben Byteoffset und ein standardbibliothekskompatibel rekonstruierbarer Hash-/Verarbeitungszustand erhalten; ein plattformspezifisches Hashobjekt wird nicht serialisiert. Wo ein Hashzustand nicht portabel gespeichert werden kann, werden unveränderbare Blockhashes plus Cursor gesichert und der betroffene Endhash einmal abschließend rekonstruiert, statt bei jedem Prompt den gesamten Präfix erneut zu hashen.

Ein vollständiger globaler Test darf nicht durch die Summe lokal bestandener Teilprüfungen ersetzt werden, wenn diese die globale Eigenschaft nicht beweisen. Der Plan reserviert dafür einen ausdrücklich verbleibenden Reduktions-/Closure-Schritt. Diagnoseteile werden am Ende deterministisch zusammengeführt; Duplikatbehandlung folgt dem ursprünglichen Command Contract. Alle Diagnoseeinheiten und Outputteile werden entweder vollständig berücksichtigt oder als nicht abgeschlossen ausgewiesen.

Jeder erfolgreiche Fortsetzungsschritt bestätigt mindestens eine neue fachliche Einheit oder einen neuen notwendigen Cursor-/Snapshot-/Reduktionsfortschritt. Ein schon abgearbeiteter vollständiger Präfix wird nicht bei jedem Resume erneut verarbeitet. Eine erneute Preflight-/Berechtigungs-/Hashprüfung notwendiger aktueller Grenzen ist zulässig, darf aber nicht die einzige unbegrenzt wiederholte Arbeit sein. Bei identischem Checkpoint ohne möglichen Fortschritt wird sofort die Ursache und Abhilfe ausgegeben. Es gibt keine automatische Schleife unveränderter Versuche.

Ein sehr kleiner weicher Budgetwert führt nicht zu unendlich vielen leeren Checkpoints. Kann ein kleinster Schritt sicher ausgeführt werden, wird er oberhalb des weichen Wertes versucht. Eine weiter teilbare Einheit wird zuvor zerlegt. Existiert tatsächlich keine ausführbare sichere Minimaleinheit, bleibt der Auftrag `blocked` mit belastbarer Begründung. Ein endlicher Auftrag unter unveränderten Eingaben und ausreichender realer Mindestausstattung muss bei wiederholtem Resume schließlich enden; die Releasefixtures weisen dies konstruktiv nach.

## P.6 Normative Writes, Dry-Run, Idempotenz und Recovery

Vorbereitung, Change-Plan-Aufbau und vollständige Zielprüfung dürfen über beliebig viele Arbeitsschritte erfolgen. Ihre Zwischenstände verändern das normative Projekt nicht. Ein einzelner fachlich atomarer Change Plan wird niemals stillschweigend in mehrere unabhängige Teilcommits aufgeteilt. Erst der vollständige, gültige und autorisierte Plan wird dem bestehenden Writer übergeben.

Vor Veröffentlichung erfolgt eine aktuelle vollständige Basis-/Precondition-Prüfung unter dem Writer-Lock. Sie ist keine weglassbare Performanceoptimierung. Bei großen Projekten darf die interne Arbeit granular sein; falls ein echter Prozessabbruch während dieser geschützten Phase eintritt, gilt ausschließlich das Journal-/Recoveryverfahren, nicht ein gewöhnlicher freigegebener Promptcheckpoint. Ein kooperativer Leser erhält keinen Mischstand. Eine bloße weiche Überschreitung rechtfertigt keine freiwillige Pause mitten in `committing`.

Die Request-ID gehört zum gesamten normativen Auftrag. Teilschritte besitzen eigene betriebliche Schrittkennungen, aber keine neuen fachlichen Request-IDs. Solange der fachliche Commit fehlt, gibt es kein semantisches Erfolgsreceipt. Nach bereits erfolgreichem Commit wird bei Wiederholung zuerst dessen vorhandenes Receipt geprüft und das gespeicherte Ergebnis geliefert. Ein Outputverlust erzeugt keine zweite Änderung.

Eine `work resume`-Operation darf den gebundenen Actor nicht erweitern. Ein KI-Proposal wird nicht durch die Wiederaufnahme zum menschlich freigegebenen Direktwrite. Fehlende menschliche Freigabe bleibt eine tatsächliche Voraussetzung; der Prompt benennt sie und erfindet kein `approved`. Dry-Runs dürfen ihren vollständigen Plan über Work-Dateien liefern, aber weder Fachdateien noch Projektbetriebsdaten verändern.

`work cancel` ist nur ohne laufende normative Transaktion zulässig. Es beendet den offenen Auftrag, erhält einen Kontrollbeleg und berechtigt nicht zur Löschung von Recoverydaten. Nach Prozessabbruch in `committing` muss zunächst Recovery erfolgen; ein Arbeitspaket kann ein beschädigtes Projekt nicht durch bloße Statusänderung entsperren.

## P.7 Portabler Export und Wiederherstellung

`work export` erzeugt ein eigenes Paket mit `package_kind=work`, nicht ein Projektvollbundle. Es enthält Kontrollmanifest, letzte vollständige Checkpointgeneration, alle zur Fortsetzung benötigten Eingangssnapshotbytes, referenzierte Plan-/Outputteile und eigene Operations-/Receiptbindungen. Ein selbstenthaltenes Paket nennt keine benötigte Ressource als bloßen lokalen Pfad. Die portable SpecRoad-Distribution wird separat bereitgestellt; ausführbare Programme aus dem Paket werden nicht geladen.

Archivpfade, Hashprüfung, keine Symlinks und die kanonische Byteordnung folgen Anhang E. Fehlen notwendige Bytes, gibt es keinen scheinbar selbstenthaltenen Export. Ein sehr großer Paketaufbau ist selbst fortsetzbare Ausgabe mit stabilem Manifestcursor. Ein Work-Paket darf nicht rekursiv unbegrenzt sich selbst oder weitere Work-Pakete einbetten. Ein über die unterstützte Archivformatgrenze hinausgehender Export verwendet eine explizit im Paketmanifest angegebene geordnete Folge kanonischer Teilarchive; jedes Teilarchiv enthält Manifest-ID und Teilnummer. Ein separates kanonisches Indexmanifest listet Teilnummer, Dateiname, Byte-Länge und SHA-256 der vollständigen Teilarchivbytes. Der Index wird nicht in diese Teile eingebettet; dadurch entstehen keine rekursiven Hashbindungen. Vollständigkeit wird erst nach Prüfung aller Teile bestätigt.

Bei `recovery_required` wird kein Arbeitspaket als Ersatz für eine sichere Kopie der aktiven Projekttransaktion ausgegeben. Zuerst wird das erhaltene Projekt recovered; vollständiger Verlust mitten im Commit kann nur aus tatsächlich extern erhaltenen Transaktionsdaten oder einer älteren Sicherung behandelt werden. Der normale Exportpfad liegt deshalb an sauberen Checkpointgrenzen vor fachlicher Veröffentlichung beziehungsweise nach gesichertem Abschluss.

`work restore` prüft vor Extraktion Paketart, alle Teilarchive, Hashes, Checkpointschema, Tool-/Algorithmuskompatibilität und Pfadregeln. Ziel muss fehlen oder leer sein. Normative Projektdateien werden nicht überschrieben. Für einen späteren Write muss der Nutzer den aktuellen Projektroot ausdrücklich zuordnen; dessen ID und Modellbindung werden erneut geprüft. Ein Snapshotkopiepfad ist nicht automatisch das autorisierte Originalziel.

## P.8 Konkreter Prompt- und Agentenvertrag

`work prompt` erzeugt aus dem geprüften Manifest einen kurzen Fortsetzungstext und dieselbe Aktion strukturiert als JSON. Pflichtinhalt: Work-ID, Checkpointhash/-generation, benötigtes Paket beziehungsweise benötigte Distribution, tatsächlich bestätigter Fortschritt, offene Gesamtaufgabe als Manifestreferenz, genaue nächste CLI-Aktion, erforderliche echte Freigaben und die Regel, erst nach vollständigem Gate-/Receiptabschluss Erfolg zu melden.

Standardobergrenze sind 6000 Unicode-Zeichen; `--max-prompt-chars` erlaubt Werte ab 1000. Dies ist eine Textlängenvorgabe, keine angeblich genaue Tokenmessung eines bestimmten Anbieters. Passt der informative Fortschritt nicht hinein, verweist der Prompt auf vollständige strukturierte Dateien. Notwendige Aktionen und Integritätsbindungen werden nicht abgeschnitten. Die vollständige fachliche Aufgabe bleibt im Arbeitspaket, nicht allein im komprimierten Prompt.

Der Prompt kopiert keine Geheimnisse, Umgebungsvariablen, vollständigen Quelltexte oder ungeprüfte Anweisungen aus Projektdokumenten. Dateiinhalt bleibt Dateninhalt. Der Runner verwendet nur bekannte `command_id` und typgeprüfte Argumente; keine Shellauswertung einer aus dem Projekt kopierten Befehlszeile. Ein manipulierter Prompt ersetzt keine erneute Checkpointprüfung.

Ein Agent kann im selben Chat mehrere CLI-Schritte ausführen, solange sein Ausführungsfenster dies erlaubt. Ist ein weiterer Prompt nötig, übergibt er Paket und Fortsetzungstext. SpecRoad selbst wartet nicht interaktiv und startet keinen neuen Chat. Ein vollständiger Sandboxverlust nach nicht extern gesichertem Checkpoint kann nicht behoben werden; der letzte extern erhaltene Paketstand ist dann die Wiederaufsetzgrenze.

## P.9 Ergebnislieferung und Betriebsdatenbereinigung

Ein großer vollständiger Bericht wird nicht im Chatfenster abgeschnitten. SpecRoad erzeugt ihn in einer externen Datei beziehungsweise einer vollständigen geordneten Ergebnisliste mit Größen und Hashes; der Runner stellt diese Artefakte bereit. Das Resultatschema des ursprünglichen Commands gilt unverändert für den vollständigen Payload. Offene Arbeit und fehlende Ergebnisbytes verhindern `success`.

Erst nach bestätigt vollständigem Ergebnis oder ausdrücklicher Nutzerstornierung dürfen entbehrliche externe Scratchteile entfernt werden. Bestätigte Checkpoints bleiben bis zur Ablösung durch eine neue vollständige Generation erhalten. Eine automatische Cachebereinigung erfasst niemals Work-Daten. Zwischen Aufrufen läuft kein SpecRoad-Prozess weiter.


# Anhang Q — Migration ohne Veränderung historischer Nachweise

## Q.1 Exakte Einteilung der Bestandsdaten

`migrate plan` teilt jeden Quellpfad vor der Transformation in `mutable`, `immutable_legacy` oder `referenced_payload` ein. `immutable_legacy` umfasst aufgezeichnete Evidence, erzeugte Baselines, vorhandene unveränderbare Relationsreviews sowie Proposals in einem nach ihrer Quellversion abgeschlossenen unveränderbaren Zustand. Alle von historischen Baselines oder Evidence referenzierten Archiv-/Anhangsbytes bleiben ebenfalls unverändert. Eine unklare oder ungültige Quellversion ist ein Migrationsfehler, keine Erlaubnis zur mutmaßlichen Reparatur.

Veränderbare 0.1-Artefakte behalten ihre Artefakt-ID und werden nach `migration-metadata-v1` zu regulären 0.2-Artefakten mit neuen Pflichtfeldern transformiert. Unveränderbare Ressourcen behalten **Originaldateibytes, ID, Schema-Version, Revision, Erstellungs-/Änderungsmetadaten und historische Hashbindungen**. Neue Pflichtfelder werden nicht in ihre Datei geschrieben. Der unterstützte 0.1-Leser ist Bestandteil des dependency-freien Core; weder Netzwerkzugriff noch Plugin ist erforderlich.

## Q.2 Normatives Legacy-Manifest

`mappings/legacy-manifest.json` ist eine versionierte normative Mappingressource nach dem allgemeinen Ressourcenvertrag. Es enthält `schema_version=0.2.0`, `mapping_id=legacy-preservation`, `mapping_version=1.0.0`, `legacy_manifest_version=1.0.0`, Quell-/Zielprojektbindung und nach Pfad sortierte Einträge. Pro unveränderbarer Ressource sind Pflicht:

```text
path, artifact_id, artifact_type, source_schema_version,
original_size, original_byte_sha256, original_canonical_sha256,
source_model_root_sha256, original_revision,
legacy_reader_id, identity_projection, relation_projections,
referenced_payloads, migration_provenance
```

`identity_projection` nennt das abgeleitete `id_scheme`, ohne es der Originaldatei zuzuschreiben. `relation_projections` bindet nur die für aktuelle Navigation benötigten reproduzierbaren Relations-IDs und die unveränderten ursprünglichen Relationswerte. `referenced_payloads` nennt Originalpfad, Größe und Hash; historische Archivobjekte bleiben über ihre gespeicherte Hashidentität adressierbar. Der Manifesthash fließt in jede neue Modellwurzel ein, die solche Ressourcen verwendet.

Der Loader kennzeichnet diese Ressourcen als `legacy_immutable`. Er validiert ihre Bytes mit dem gebundenen eingebauten Quellschema und prüft Originalhash sowie Manifestbindung. Eine in-memory Projektion dient ausschließlich Navigation und Darstellung. Sie ist kein 0.2-Originalartefakt und darf weder vom Writer noch vom Formatter zurückgeschrieben werden. Der 0.2-Loader akzeptiert nicht beliebige alte Dateien allein wegen einer alten `schema_version`; die intakte Manifestregistrierung ist Pflicht.

## Q.3 Reproduzierbare Relations-ID und Hashbindung

Für jede bereits vorhandene 0.1-Relation wird die Ableitungseingabe als RFC-8785-JSON gebildet:

```text
["specroad-relation-migration-0.1-to-0.2-v1",
 project_id, source_artifact_id, original_zero_based_array_index,
 original_relation_json]
```

Der SHA-256-Hash dieser UTF-8-Bytes wird auf die ersten 16 Bytes begrenzt und als 26-stelliges Crockford-Base32-Token nach Kapitel 9.2 codiert. Daraus entsteht `REL-<TOKEN>` mit `id_scheme=derived128-v1`. In veränderbaren Artefakten wird es gespeichert, in unveränderbaren Legacy-Artefakten ausschließlich im Manifest. Identische Quellbytes führen über Wiederholung und Sandboxwechsel zu identischen Ergebnissen. Gleiche abgeleitete ID für unterschiedliche Ableitungseingaben ist ein Konflikt; sie wird nicht zufällig umbenannt.

Regulär neu angelegte Relationen verwenden unverändert `random128-v1`. Das reguläre Ableitungsverbot gilt nicht für diese eng begrenzte Bestandsmigration. Ein späterer Import darf die Migrationsausnahme nicht zur freien Erzeugung von abgeleiteten Identitäten nutzen.

In einer neuen 0.2-Modellwurzel wird ein Legacy-Eintrag mit Rolle, ID, ursprünglicher Revision, `hash_domain=legacy-original-bytes-v1`, Originalbytehash und Manifestbindung aufgeführt. Ein regulärer 0.2-Eintrag verwendet seine bisherige JCS-Hashdomäne. Diese getrennte Domäne verhindert das Verwechseln einer abgeleiteten Projektion mit einem historischen Originalhash. Ein vorhandener historischer Baseline-Hash bleibt unverändert; `baseline verify` verwendet dafür den in der Baseline gespeicherten Quellalgorithmus, nicht rückwirkend die 0.2-Hashformel.

## Q.4 Evidence und Baselines nach Migration

Eine erhaltene Legacy-Evidence bleibt ein beweiskräftiger Nachweis ihres **historischen** Subjects und kann historisch verifiziert werden. Sie zählt nicht allein aufgrund ergänzter Projektionen als aktuelle bestandene Evidence eines nach 0.2 transformierten Subjects. Bis zu einem neuen, aktuellen Verification-Context-Nachweis wird sie für das transformierte Subject als `stale` mit Grund `migration_context_unverified` ausgewiesen. Eine neue Prüfung erhält eine neue Evidence-ID; das Original wird weder ersetzt noch aufgehübscht.

Neue 0.2-Baselines dürfen erhaltene Legacy-Originalobjekte und deren Manifestbindung aufnehmen. Dabei werden neue Baseline-ID und neues Manifest erzeugt, ohne eine historische Baseline umzuschreiben. Ein doppelter Identitätseintrag mit unterschiedlichen Originalbytes verhindert Migration und Merge. `format`, freie Updates und normale Lifecycle-Befehle lehnen `legacy_immutable`-Writes ab.

Die Migration ist verlustfrei in Bezug auf erhaltene Inhalte, IDs, Originalbytes und Provenienz. Sie verspricht nicht, dass historische Freigaben automatisch die fachliche Gültigkeit aller neuen 0.2-Anforderungen beweisen. Erforderliche neue Reviews und Evidence bleiben sichtbar offen.

## Q.5 Vollständiger Migrationsablauf

Planung identifiziert unveränderbare Ressourcen und alle Referenzpayloads, erzeugt ein vollständiges Quell-Sicherungsbundle, berechnet die Transformation der veränderbaren Daten sowie das Legacy-Manifest und prüft Referenzen/Identitäten. Erst danach folgt der gemeinsame Writer mit `migration-metadata-v1`.

`migrate verify` prüft mindestens byteidentische Originalressourcen vor/nach Migration, identische historische Baseline-Hashes, vollständige Manifestreferenzen, unveränderte Legacy-IDs und neue gültige 0.2-Ressourcen. Jede unbeabsichtigte Originaländerung ist Fehler. Wiederholung nach erfolgreicher Migration ist No-op beziehungsweise liefert das gespeicherte Request-Ergebnis. Der Migrationsauftrag kann während Planung und Prüfung nach Anhang P aufgeteilt werden; die abschließende Veröffentlichung bleibt eine Transaktion.


# Anhang R — Kontraktübergreifende Abnahmefälle

Diese Fälle sind Solltests für die spätere Implementierung. Die bloße Aufnahme in die Spezifikation ist kein bestandener Produktnachweis. Die kleinen Orakel sind vollständig bestimmbar und ergänzen die einzelnen Requirement-Testfälle.

| Fall | Ausgang / Operation | Verbindliches Oracle |
|---|---|---|
| R-01 Reguläre und migrierte Relation | Dieselbe Bestandsrelation zweimal migrieren; unabhängig davon reguläre Relation erzeugen. | Migration liefert gleiche `derived128-v1`-ID; reguläre ID ist `random128-v1`. Kein Konflikt mit SR-REQ-0509. |
| R-02 Merge-Metadaten | Ours Revision 3; Theirs Revision 7; kombiniertes Artefakt. | Planner und Writer erzeugen Revision 8 und identische durch `merge-metadata-v1` gebundene Zielbytes. |
| R-03 Unveränderte Übernahme | Ours unverändert gegenüber Base; gültige vorhandene Theirs Revision 7. | Revision 7 unverändert übernommen; kein fiktiver neuer Zeitstempel und kein allgemeines `base+1`. |
| R-04 Relationsreview | Bestätigte Relation erhält andere Begründung; später neu bestätigt. | Zuerst `suspect`, dann `current`; ohne irgendein historisches Review `unreviewed`. |
| R-05 Review-Auswahl | Zwei passende Reviews derselben Bindung, zuerst rejected, später confirmed. | Nur neuestes passendes Review entscheidet; `current`. Tie-Breaker ID wird gesondert geprüft. |
| R-06 Proposal-Einfügen | Bestehende Changes `[A,B]`, neues `C`. | Ohne Position `[A,B,C]`; mit 0 `[C,A,B]`; mit 1 `[A,C,B]`; mit 2 anhängen; 3 und negative Werte abweisen. |
| R-07 Legacy-Unveränderbarkeit | 0.1-Evidence, Baseline und Archivbytes migrieren. | Alle Originalbytehashes und historischen Baselinehashes unverändert; neue Pflichtfeldprojektionen nur im Legacy-Manifest. |
| R-08 Historische Evidence | Subject wird durch Migration schema-semantisch transformiert. | Historischer Nachweis bleibt lesbar; kein automatisches aktuelles `passed`; `migration_context_unverified`. |
| R-09 Proposal-Komplettlauf | Create, Change add, Validate, Check, Review start, Human approved, Apply. | Revisionsfolge und Inhaltsbindungen exakt wie Kapitel 11.10; Checks schreiben nicht; freigegebener Inhalt bleibt bei Kontrollwrites gültig; genau ein Apply. |
| R-10 Befehlsklassen | Read-only-/Render-/Dry-Run-Auftrag mit externem Checkpoint. | Weder Projektdateien noch `.specroad/` ändern sich; nur deklarierte externe Arbeitsdaten. |
| R-11 Überzogenes Arbeitsziel | Endlicher Auftrag benötigt mehr CPU/Bytes als weiches Ziel. | Sparsame Fortsetzung beziehungsweise Code 8, kein Budgetfehler; vollständiges Ergebnis entspricht Einzellauf. |
| R-12 Sehr kleine Schritte | Teilschrittwert liegt unter Aufwand einer sicher ausführbaren kleinsten Einheit. | Mindestens ein bestätigter Fortschritt je Resume oder konkreter realer Blocker; keine endlose Folge identischer Checkpoints. |
| R-13 Globaler Graph | Zyklus oder Referenzfehler liegt über Chargengrenze; `why` hat mehr Pfade als eine Ausgabecharge. | Globaler Fehler wird erkannt; alle versprochenen Pfade werden erzeugt; keine unprüfte Restmenge. |
| R-14 Query und Diagnose-Spooling | Viele Treffer und Befunde; Inlinebudget klein. | `total` exakt; fachliche Pagination unverändert; vollständige Resultats-/Diagnosedatei mit Hash; Anzeigeausschnitt markiert. |
| R-15 Frische Sandbox | Arbeitspaket extern sichern, alte Umgebung löschen, Paket mit kompatibler Distribution wiederherstellen. | Fortsetzung ab bestätigtem Cursor ohne alte Session/Cache; identische fachliche Endhashes. |
| R-16 Veränderte Zielbasis | Vorbereitung abgeschlossen, aktuelles Projekt vor Apply verändert. | Code 6 ohne normative Teiländerung; kein stilles Rebase und keine neue Freigabe. |
| R-17 Beschädigter Checkpoint | Fehlendes Segment, veränderte Bytes oder falscher Algorithmus. | Kein Anerkennen falschen Fortschritts; vorherige gültige Generation verwenden oder konkreten Fehler melden. |
| R-18 Retry nach Ausgabeabbruch | Commit/Receipt vorhanden, Abschlussausgabe verloren; Resume mit gleicher Request-ID. | Bestehendes Receipt und dieselben IDs; kein zweiter Commit. |
| R-19 Echter Commitabbruch | Host beendet Prozess nach beliebiger Dateiveröffentlichung. | Journalvertrag blockiert Mischstand; Recovery stellt vollständige Basis oder Ziel her. Ein weiches Ziel allein löst diesen Pfad nicht aus. |
| R-20 Prompt-/Actorgrenze | Fortsetzungsprompt wird verändert oder fordert direkte KI-Freigabe. | Runner prüft Manifest/Command/Actor erneut; kein Erzeugen oder Überspringen menschlicher Freigabe. |
| R-21 Kein Platz / harte Policy | Echter Datenträgermangel beziehungsweise unzulässige Archivstruktur. | Sparsame sichere Alternative oder konkreter Blocker; keine stillen Verluste, keine Sicherheitsumgehung. |
| R-22 Unbekannte Quota | Host meldet kein verlässliches Memorylimit. | Wert bleibt unbekannt; konservativer realer Arbeitsversuch statt pauschaler Ablehnung oder fingierter Garantie. |
| R-23 Permanente Scope-Grenze | Inhaltsblock referenziert direkt oder indirekt ein Proposal beziehungsweise eine Baseline. | `specification` liefert SRV140/scope_control_dependency und Code 3 ohne Wurzel/Write; kein Wiederaufnehmen durch Closure. `project` darf dieselbe gültige Referenz enthalten. |
| R-24 Proposal-Basiszulässigkeit | Create mit project-, explicit-, partial- oder konfiguriertem Descriptor; danach normaler Proposal-Komplettlauf. | Unzulässige CLI-Auswahl Code 2 ohne ID/Receipt/Journal; einzig kanonische specification-Basis zulässig. Reine Kontrollen erhalten deren Wurzel; fachliche Änderung macht die alte Basis stale. |
| R-25 Neuer Produktstand | Stand A hat failed; korrigierter Stand B zunächst ohne Evidence, danach mit passed für alle Pflichten. | B zunächst incomplete, danach passed; alte A-Evidence unverändert als historical_other_state. Ein alter A-Erfolg allein lässt B nicht bestehen. |
| R-26 Retest desselben Stands | Derselbe Stand hat failed in Lauf 1 und passed in Lauf 2. | Ohne Ablösung failed. Mit vollständig gebundener menschlicher Ablösung von Lauf 1 durch aktuellen vollständigen Lauf 2 passed; kein Umschreiben des historischen Fehlschlags. |
| R-27 Pflichtmenge und widersprechende Läufe | Zwei Pflichtslots; einer fehlt oder schlägt fehl. Mehrere Nachweise eines maßgeblichen Laufs widersprechen sich. | Fehlende Pflicht incomplete; aktueller maßgeblicher Fehlschlag failed, auch bei anderem fehlendem Slot. Keine Auswahl des neuesten Erfolgs; gleiche Auswahl bei beliebiger Importreihenfolge. |
| R-28 Ungültige Ablösung | Zyklische Entscheidung, KI als Freigabeautor, fehlender Ersatzlauf oder später hinzugekommene Evidence des abgelösten Laufs. | Struktur-/Akteursverletzung Code 3/7; fehlende oder veränderte Bindung incomplete; kein passed durch versteckte Zusatznachweise. |
| R-29 Selfdescription-Projektion | Identische konsistente Kopien unter verschiedenen absoluten Pfaden. | Kanonische semantic-Projektion identisch; runtime.project_root verschieden und korrekt. Bei aktivem Writer/Recovery kein erfundener vollständiger Snapshot. |
| R-30 Query-Wahrheitstabelle | Titel A und B; wiederholte Wertfilter; zwei disjunkte SRX-Ausdrücke; gemischte Filtergruppen. | Wertfilter innerhalb einer Art ODER, verschiedene Arten UND, SRX-Ausdrücke immer UND. Leere Filtergruppe true; Evaluation ist gebundener Input, kein ODER-Filter. |
| R-31 Bewertung und Fortsetzung | Bewerteter Auftrag wird checkpointiert, später mit anderem Descriptor oder neuer Inputdatei fortgesetzt. | Hashabweichung führt zu stale/Konflikt, kein stiller Bewertungswechsel. Identische gebundene Inputs ergeben gleiche fachliche Auswahl und Aggregation. |
| R-32 Bewertung und Release-Baseline | Read-only mit ungespeicherter Auswahl; Baselineversuch; danach Auswahl im Release genehmigt speichern. | Vorläufiger Bericht möglich; Baseline erst mit gespeicherter gültiger Auswahl. Sealed Manifest bindet genau diese Auswahl, historische Baselinebytes bleiben unverändert. |
| R-33 Reiner Abschluss | R approved/4; zulässiges retire bzw. superseded mit vorhandener Nachfolge. | R endet retired/5 bzw. superseded/5; kein Reset auf proposed; reine Auditdaten außerhalb Fachprojektion. |
| R-34 Fachinhalt und gemischter Lifecycle | R approved/4; Inhalt ändern; optional Transition proposed; alternativ retired/superseded/approved im selben Plan. | Inhalt bzw. Inhalt+proposed ergibt proposed/5. Andere gemischte Ziele vor Write Code 2/3; keine Revision und kein Teilwrite. |
| R-35 Pflichtrelation ablehnen | R approved/4; aktuelle bestätigte Pflichtrelation; neuer menschlicher rejected-Review. | Review recorded/approved/1; Relation invalid; R proposed/5; Code 0 mit assessment_status failed und SRV027/error; separates validate Code 1. |
| R-36 Erneut bestätigen | Stand R-35; neue aktuelle confirmed-Entscheidung; anschließend explizite Reifegradfolge. | Neue Review-ID; Relation current; R bleibt proposed/5. Explizit in_review/6 und approved/7 erst nach erfülltem Gate. |
| R-37 Draft, optionale Relation und Authority | Rejected bei draft/4 oder nicht gatepflichtiger Relation; alternativ AI-Reviewer oder fehlendes Ziel. | Keine unbegründete Quellrevision/Herabstufung; fachlicher Befund bleibt sichtbar. AI Code 7, struktureller Fehler Code 3, jeweils kein Write. |
| R-38 Review-Transaktion und Retry | Hostabbruch zwischen Review- und Quellwrite; verlorene Erfolgsantwort; gleicher Request. | Ausschließlich vollständiger alter/neuer Zustand nach Recovery; ein Review und einmalige Rücknahme; identisches Receipt bei Retry. |
| R-39 Review-Kontextstabilität | Quelle wird allein durch gekoppelten Freigabeentzug herabgestuft; Relations-/Fachinhalt bleibt gleich. | Kontext-/Relationshash unverändert; negative Entscheidung bleibt aktuell und wird nicht durch den eigenen Write suspect. |
| R-40 Bundle-Arten | Project-, Dokument- und Releasebundle erzeugen, verifizieren, extrahieren. | project/false/project/closed oder partial/true/document bzw. release/partial exakt nach E.3; passende Read-only-Nutzung möglich. |
| R-41 Nichtkanonisches Teilbundle | bundle_kind document/release, unknown oder partial mit read_only=false; Write auf verifiziertem Teilbundle. | Formatfehler Code 3 vor Extraktion; echter Partial-Write Code 7. Keine Aliasannahme und kein stiller Vollprojektstatus. |
| R-42 Manifest-Hashdomäne | Bundle mit Manifest, Konfiguration, Fachpayload und Receipt; zusätzliche/unaufgeführte Datei oder Manifest in entries. | entries exakt Payload ohne Manifest; Byte-/Mengendifferenz fällt auf. Modellwurzel unabhängig von Betriebssektion und Container. |
| R-43 Manipulationsabgrenzung | Payloadbit ändern; Manifest allein inkonsistent ändern; anschließend konsistent neu erzeugtes Archiv mit altem externem Hash prüfen. | Interne Hash-/Scopeprüfung weist erste Fälle ab. Externe Voll-ZIP-Bindung weist konsistente Ersatzdatei ab; ohne externe Bindung kein Authentizitätsversprechen. |
| R-44 Vollständiger Baseline-Restore | Projekt-Baseline geschlossen/unfiltriert und alle Bytes gültig; Restore dry-run, gebundener Plan und bestätigter Zielroot. | Quellsnapshot rekonstruiert; Quellbaseline samt Objektclosure erhalten; volle Zielwurzel nach Historienergänzungen geprüft; Audit dauerhaft. |
| R-45 Unvollständige Restore-Quelle | Hashgültige release-/specification-Baseline, gefiltertes Vollbundle oder fehlendes Objekt/Primärdokument. | Code 3 ohne normative oder betriebliche Vorprüfungsänderung; kein Auffüllen aus zufälligen aktuellen Dateien. |
| R-46 Geschützte Geschichte | Jüngere gültige unveränderbare Evidence/Baseline vorhanden; gleicher ID-Inhalt konfliktbehaftet oder notwendige Referenz nicht verfügbar. | Bytegleiche Historienobjekte explizit im Ziel erhalten; Konflikt Code 6 bzw. fehlende Zielbytes Code 3; kein stilles Löschen oder erfundene Fachressource. |
| R-47 Restore-Atomarität | Quellenwechsel nach Planung, echter Speicherfehler bei Sicherung oder Crash beim Restore. | Stale Quelle Code 6; Sicherung nicht fertig: kein Commit. Nach Crash gesperrter Originalstand oder gesamtes geprüftes Ziel; korruptes Journal bleibt archiviert. |

Die zugehörigen Testfixtures liegen versioniert im Implementierungsrepository. Jeder Nachweis bindet Spezifikationshash, Tool-Build, Fixturehash, verwendete Policy-/Algorithmusversionen und komplette Ergebnis-/Receiptmanifeste. Der Vergleich der Einzellauf- und Mehrschrittergebnisse verwendet den fachlichen Payload ohne operative Pfade, Laufzeiten und Checkpointkennungen. Die Zahl von Prompts ist keine Eigenschaft des fachlichen Ergebnisses.


---

---

## R.1 Ergänzende Mehrsprachen- und Analyzer-Sollfälle

| Fall | Vorgang | Oracle |
|---|---|---|
| R-48 Force ohne Keyword | Zwei sprachverschiedene Requirements mit must und vollständigem Indikativsatz erzeugen. | Keine Keywordpflicht; language und Force explizit, keine automatische Satzumformung. |
| R-49 Verbot | Positiver Telemetriesachverhalt plus must_not; alternativ negativer Sachverhalt plus must. | Getrennte Labeldarstellung; Core erfindet keine doppelte Negation oder semantische Gleichheitszusage. |
| R-50 Tag-Policy | en-IN bei erlaubtem en; cmn-Hans-CN bei ausschließlich erlaubtem zh. | Erster Fall erlaubt, zweiter nicht automatisch per Makroalias erlaubt. |
| R-51 Mischung | en-US/en-IN und de-DE in unterschiedlichen Containeransichten. | Primary-/Exact-Modus und Containeroverride liefern genau die in S.5 definierte Menge. |
| R-52 Echte Erkennung | Gelieferten py3langid-Worker mit langen Referenzstatements je Mindestlabel starten. | Reale Detektion nach T.10, keine fingierte Modellleistung. |
| R-53 Unsicherheit | Leerer, sehr kurzer und codeartiger Text; Score exakt an der Grenze und direkt darunter. | Nichtentscheidung beziehungsweise definierte inklusive Schwelle; keine falsche Bestätigung. |
| R-54 Grobe Sprache | en-IN mit detected=en; cmn-Hans-CN mit detected=zh. | Keine Region erkannt; Mandarinfall nur compatible_coarse. |
| R-55 Verbotene Sprache | Französischen Text in einem Projekt mit ausschließlich erlaubtem de/en analysieren. | Kandidatenraum bleibt vollständig; keine erzwungene Zuordnung zu de oder en. |
| R-56 Fremdanalyzer | Datenrequest an zwei externe Testanalyzer geben, unterschiedliche Findings importieren. | Provenienz/Coverage erhalten; keine Ausführung eines importierten Descriptors und keine normative Mutation. |
| R-57 Alter Bericht | Subjectrevision oder ein gebundenes Setting nach Analyse ändern. | Bericht stale; Originalbytes unverändert; kein aktueller Pass. |
| R-58 Fehlende Library | Core ohne Analyzerpakete; validate und dann ausdrückliches analyzer run. | Core funktioniert; Detektion unavailable/Code 5, kein skipped-Erfolg. |
| R-59 Promptfortsetzung | Kleine Workschritte, neue Runtime, gleicher Enginefingerprint. | Vollständige Restmenge und bereits bearbeitete Subjects erhalten; vollständiger Endbericht. |
| R-60 Echter Hostblocker | Modell nicht ladbar oder Einzeltextoperation nicht möglich. | Konkreter Blocker, keine Endlosschleife oder Stichprobe als vollständiger Ersatz. |
| R-61 Migration | Ältere approved-Requirements mit expliziten Sprach-/Force-/Textmappings migrieren. | Neue Fachrevisionen; historische Evidencebytes und ursprüngliche Hashbindungen erhalten. |
| R-62 SRX-Präzision | 1/8 mit Präzision 2 und 3 sowie 1/3 mit 34 auswerten. | precision_exceeded; 0.125; non_terminating. |
| R-63 Output-Sicherheit | Berichte mit HTML-/Prompttext, fremder ID oder doppeltem Subject importieren. | Nutzdaten escaped, Rechte unverändert, strukturelle Fremd-/Doppelbindung zurückgewiesen. |

---

## R.2 Analyzer-Fortsetzungs- und Kennungsregression v0.2.7

| Fall | Vorbedingung / Aktion | Verbindliches Oracle |
|---|---|---|
| R-64 Automatischer Work-Root | Großer Analyzerlauf ohne `--work-dir`, weiches Ziel erreicht, externes Tempverzeichnis beschreibbar. | Gültiger atomarer Checkpoint vor Code 8; Pfad, Work-ID, Analysekennung und Restbindung sichtbar; neuer Prozess setzt vollständig fort; Projektbytes unverändert. |
| R-65 Expliziter Work-Root | Derselbe Auftrag mit zulässigem `--work-dir`. | Genau dieser Work-Root, kein alternativer versteckter Speicher; identische fachliche Ergebnisse wie R-64. |
| R-66 Kleiner Auftrag | Vollständige Ausführung ohne erforderliche Pause. | Kein Work-Root; vollständiger Bericht und normaler Gate-/Exitvertrag aus T.8. |
| R-67 Automatische Analysekennung | Request ohne `--analysis-id` erzeugen; in einem getrennten Fall impliziter Request in `analyzer run`. | Je neuer Auftrag genau eine gültige AN-/random128-Kennung; im Request beziehungsweise Package sichtbar; keine Schreib-Receipts. |
| R-68 Manuelle Analysekennung | Beide erzeugenden Befehle mit gültigem `--analysis-id`; separat ungültiger Optionswert. | Wert unverändert; ungültiger Wert Code 2 vor Ausführung; keine normative Autorisierung. |
| R-69 Projektloser Request | Vollständigen Request mit gültiger Kennung ohne Projekt ausführen. | Kennung übernommen; keine erfundene fachliche Basis oder `.specroad/`-Ablage; vollständiger technischer Bericht, keine fingierte Aktualität zu fehlendem Arbeitsstand. |
| R-70 Getrennte Namensräume | Analysekennung und bestehende Schreib-Request-ID haben dieselbe Zeichenfolge. | Keine Kollision und kein Zugriff auf das Schreib-Receipt durch die Analyse; normativer Write-Retry unverändert idempotent. |
| R-71 Work-Bindung | Gesicherten Analyzerauftrag mit abweichender Analysekennung oder verändertem Snapshot fortsetzen. | Konflikt Code 6; kein vermischter Lauf, ursprünglicher Checkpoint unverändert. |
| R-72 Expliziter Request und Override | `--request` zusammen mit `--analysis-id`; separat Request ohne Pflichtkennung. | Override Code 2; fehlende/ungültige Datenkennung Code 3; keine stille Korrektur oder Neugenerierung. |
| R-73 Request-/Report-Paar | Gleicher Snapshothash, aber unterschiedliche Analysekennung im Report; separat gleiche Kennung bei falschem Hash. | Beide Kombinationen Code 3 bei Import/Evaluation; keine stillschweigende Umbenennung oder Zuordnung. |
| R-74 Echter Speicherblocker | Kein zulässiger Checkpointplatz und kein sicherer sparsamer Abschluss; vorhandenen Checkpoint erhalten. | Code 5 mit konkretem Blocker statt Code 8; keine verlorenen abgeschlossenen Einheiten und keine Projektwrites. |
| R-75 Unterbrochener Requestaufbau | Nach Vergabe der Analysekennung, aber vor vollständigem Snapshot checkpointen und neu starten. | Kennung aus `normalized_arguments.analysis_id` erhalten; offene Snapshotarbeit vollständig; kein unvollständiger Erfolgsrequest und keine neue Schreibkennung. |

---

# Anhang S — Mehrsprachige Anforderungen und explizite Verbindlichkeit

## S.1 Umfang, Ausführungsmodell und Grenzen

Das erste spezifizierte Produktrelease enthält bereits mehrsprachige Anforderungen **und einen ausführbaren py3langid-Adapter**. Der Adapter ist keine bloße Zukunftsankündigung. Die dependency-freie Core-Distribution und die zusätzliche Analyzer-Distribution werden getrennt geprüft. Kein Sprachmodell, Übersetzer, allgemeiner Semantikprüfer oder neuer Mehrbenutzerserver wird Bestandteil des Core.

Drei unterschiedliche Informationen bleiben getrennt: `language` ist die vom Autor deklarierte Inhaltssprache; `normative_force` legt die Verbindlichkeit fest; ein Analyzer-Ergebnis ist eine versionsgebundene Beobachtung. Keine dieser Informationen wird automatisch aus einer der anderen hergeleitet. `requirement_kind` klassifiziert weiterhin den Anforderungstyp; `priority` steuert weiterhin die Planung. Insbesondere impliziert `priority=mandatory` weder `normative_force=must` noch umgekehrt.

Die Großschreibung normativer Vertragssätze in diesem Spezifikationsdokument ist eine redaktionelle Darstellungsform. Sie bedeutet nicht, dass das ausführbare Requirement-Datenmodell künftig ein Schlüsselwort im Freitext verlangt. Die bestehenden redaktionellen Requirement-IDs bleiben erhalten. Eine spätere Übernahme dieses Dokuments in das ausführbare Modell benötigt dieselbe explizite Metadaten- und Inhaltszuordnung wie jeder andere Import.

## S.2 Requirement-Vertrag

Jedes regulär neu gespeicherte Requirement besitzt ab `draft` die Pflichtfelder `language` und `normative_force`. `language` enthält genau einen BCP-47-Tag. `normative_force` ist exakt einer der vier Werte aus dieser Tabelle:

| Feldwert | Bedeutung für den beschriebenen Sachverhalt | Darstellung ohne Satzumbau |
|---|---|---|
| `must` | Die Aussage ist verpflichtend zu erfüllen. | Muss-Kriterium |
| `must_not` | Das Eintreten des beschriebenen Sachverhalts ist verboten. | Verbotener Sachverhalt |
| `should` | Die Aussage ist eine Empfehlung mit expliziten Abweichungsbedingungen und zuständiger Autorität. | Soll-Kriterium |
| `may` | Der Sachverhalt ist erlaubt; sein Nichtgebrauch ist für sich kein Verstoß. | Erlaubnis |

`statement` enthält einen vollständigen, eigenständig verständlichen Sachverhalt mit Scope, Bedingungen und Ausnahmen soweit erforderlich. Das Feld ist nicht auf einen Infinitiv oder ein Satzfragment reduziert. Modale Schlüsselwörter sind nicht vorgeschrieben. Der Renderer zeigt Verbindlichkeit und Originaltext getrennt und fügt weder ein Verb noch eine Negation oder Übersetzung in den Satz ein.

Informative Beispiele, keine vollständigen Artefakte:

```json
{
  "language": "de-DE",
  "normative_force": "must",
  "statement": "Das System funktioniert ohne Netzwerkverbindung."
}
```

```json
{
  "language": "en-IN",
  "normative_force": "must_not",
  "statement": "The system transmits telemetry to an external service."
}
```

Das zweite Beispiel verbietet die positive Aussage über Telemetrie. Ein negativ formulierter Sachverhalt mit `must` ist ebenfalls möglich. Autoren dürfen aber nicht eine modal negierte Anweisung und `must_not` kombinieren und vom Tool eine automatische Entflechtung doppelter Negationen erwarten. Die fachliche Reviewrolle prüft, ob das Tupel aus Sachverhalt und Verbindlichkeit die Absicht eindeutig ausdrückt. Der Core erfindet keine Textsemantik und löst einen vermuteten Konflikt nicht durch automatischen Vorrang oder Umschreiben.

`should` verlangt ab dem ersten Speichern nichtleere `deviation_conditions` und `deviation_authority`. Ein nachweislich zulässiges Abweichen folgt weiterhin dem geregelten Nachweis-/Freigabevertrag; es ist nicht automatisch ein bestandenes Verification Result. Änderungen an `language`, `normative_force` oder `statement` sind Fachinhaltsänderungen nach 9.6.3; Kontext- und Reviewhashes berücksichtigen diese Felder. Bereits freigegebene Anforderungen werden auf `proposed` zurückgesetzt. Es gibt keine automatische Freigabe durch einen Sprachdetektor.

Bei `artifact create requirement` und beim Proposal-Authoring ist `--normative-force` beziehungsweise der entsprechende Inputwert Pflicht. Es gibt keinen stillen Muss-Default. `--language` darf fehlen, wenn `language_policy.default_language` vorhanden ist; der Writer materialisiert diesen expliziten Projektdefault im neuen Artefakt und zeigt ihn im Dry-Run. Konflikte zwischen CLI und Inputdatei werden mit Code 2 zurückgewiesen. Host-Locale, Detektoroutput und Anzeigename eines Benutzers sind niemals Defaults für Fachmetadaten.

## S.3 Sprachkennzeichnung, Register und Unicode

Tag-Syntax und Registerregeln verwenden RFC 5646; die Tag-Erlaubnisprüfung verwendet ausschließlich Basic Filtering aus RFC 4647, Abschnitt 3.3.1. Sprach-Tags sind ASCII, ihr Vergleich ist nicht von einer Ubuntu-Locale abhängig. Die Speicherung verwendet die übliche Groß-/Kleinschreibung: Sprache klein, Script Title Case, Region groß; sonstige Subtags klein. Diese reine Schreibweisenkanonisierung erfolgt beim geplanten Write. Sie verändert niemals unbemerkt eine geladene Datei. Register-`Preferred-Value`-Ersetzungen oder Makrosprachenzusammenfassungen erfolgen nicht automatisch.

Das Release liefert einen eingefrorenen IANA-Language-Subtag-Registry-Snapshot samt Dateidatum, SHA-256 und Validatorversion mit. Der beim `init` gewählte Snapshot wird als deklarative Ressource unter `profiles/language-data/` materialisiert und in der Projektkonfiguration über Identität und Hash gebunden. Er wird mit dem Projekt transportiert. Eine neue Toolversion ersetzt ihn nicht stillschweigend. Ein Update ist ein expliziter fachlicher Change Plan. Der Parser unterscheidet `invalid_syntax`, `registered`, `private_use` und `unverified_registry`; gültige private-use-Tags sind nicht syntaktisch fehlerhaft. Syntaktisch gültige, im gebundenen Snapshot nicht registrierte Tags werden erhalten und als `unverified_registry` gemäß Policy diagnostiziert. Sie werden nicht als registriert ausgegeben. Der Core kennt keine geschlossene Liste zulässiger natürlicher Sprachen.

Ein Requirement ohne `language` ist ein Schemafehler. Die Tags `und`, `mul` und `zxx` sind als Tags grundsätzlich lesbar; für einen Requirement-Sachverhalt lösen sie die gesonderte Policy `unspecified_language` aus. Ein privater Tag oder ein unbekannter Tag erhält nicht automatisch ein linguistisches Regelpaket oder eine statistische Erkennbarkeitszusage.

Normative Texte werden unverändert als UTF-8 gespeichert; Surrogate und ungültige UTF-8-Bytes sind unzulässig. JCS ergänzt keine Unicode-Normalisierung. Suche, Darstellung und Analyzer dürfen klar bezeichnete abgeleitete Textansichten bilden, aber keine gespeicherten Textbytes heimlich ersetzen. Ein fehlender Terminalfont ist kein Speichervalidierungsfehler. HTML verwendet bei vorhandenem Tag `lang`; Schreibrichtung ist unabhängig davon als `text_direction=ltr|rtl|auto` optional deklarierbar, Default `auto`. Markdown behält Unicode und kennzeichnet Sprache und Verbindlichkeit; eine korrekte Glyphendarstellung durch jeden externen Viewer wird nicht zugesagt.

Die vollständig aufgelöste Konfiguration enthält zusätzlich `language_registry` mit genau `registry_id`, `registry_version`, `path` und `sha256`. `registry_id` ist `iana-language-subtags`; `registry_version` ist das `File-Date` des tatsächlich mitgelieferten Registers im Format YYYY-MM-DD, `path` ein verwalteter relativer Dateipfad und `sha256` dessen tatsächlicher Bytehash. Ein Release darf keinen erfundenen Registerstand eintragen. `init` materialisiert die vom Distributionmanifest gebundenen Werte; Projekte lesen ausschließlich ihre gebundene Kopie. Diese Referenz und die verwendeten Paketversionen sind Teil der effektiven semantischen Konfiguration und sämtlicher relevanter Modellmanifeste. Bei fehlender oder beschädigter Registerkopie erfolgt Code 3 statt einer stillen Onlineabfrage.

## S.4 Verbindlicher Mindestumfang

Folgende Kennzeichnungen gehören zum Abnahmekorpus. Sie sind keine abschließende Erlaubnisliste für andere Projekte:

| Sprache / Verwendung | Deklarierter Tag | Vom ersten Adapter erwartbare Auflösung |
|---|---|---|
| Englisch, USA | `en-US` | `en`; keine Regionsbestimmung |
| Englisch, Indien | `en-IN` | `en`; keine Regionsbestimmung |
| Hindi, Indien | `hi-IN` | `hi` |
| Indonesisch, Indonesien | `id-ID` | `id` |
| Portugiesisch, Brasilien | `pt-BR` | `pt`; keine Regionsbestimmung |
| Spanisch, Mexiko | `es-MX` | `es`; keine Regionsbestimmung |
| Russisch, Russland | `ru-RU` | `ru` |
| Japanisch, Japan | `ja-JP` | `ja` |
| Deutsch, Deutschland | `de-DE` | `de` |
| Chinesisch, vereinfachte Schrift, China | `zh-Hans-CN` | `zh`; keine Script-/Regionsbestimmung |
| Ausdrücklich Mandarin, vereinfachte Schrift, China | `cmn-Hans-CN` | gegebenenfalls `zh`; nur grobe Kompatibilität, kein Mandarin-Nachweis |

Zusätzlich gehören `zh-Hant`, `ar`, `ur-IN`, ein privater Tag, `und` und ein syntaktisch korrekter unregistrierter Testtag zu den Metadaten-/Transporttests. Diese Zusatzfälle begründen keine zusätzliche garantierte Detektorqualität.

Die zehn regionalen Hauptfälle einschließlich `zh-Hans-CN` und der ausdrückliche Mandarin-Fall werden getrennt nach **Content Support**, **Metadata Policy**, **Detector Capability** und **verfügbaren Lint-Regeln** ausgewiesen. Es gibt keine Behauptung eines vollständigen linguistischen Verständnisses für diese Sprachen. Aufwändige Grammatik-, Bedeutungs- oder Übersetzungsprüfung bleibt einem späteren Analyzer vorbehalten.

## S.5 Sprachpolicies und Mischung

Die effektive Projektkonfiguration enthält folgenden vollständigen Defaultvertrag `language-policy-v1`; alle Werte werden von `config show` materialisiert:

```json
{
  "version": "language-policy-v1",
  "default_language": "de-DE",
  "allowed_ranges": ["*"],
  "disallowed_language": "error",
  "unverified_registry": "warning",
  "unspecified_language": "error",
  "mixed_languages": {
    "comparison": "primary_language",
    "project": "allow",
    "document": "warning",
    "section": "warning"
  }
}
```

Aktionswerte sind exakt `allow|warning|error`. `allow` erzeugt keine Diagnose; Warnung und Fehler behalten ihren Schweregrad. Erst die bestehende Fail-Policy beziehungsweise `--strict` entscheidet über den Exit Code. Syntax-/Schema- und Sicherheitsfehler sind nicht durch diese Policy absenkbar. Eine leere Erlaubnisliste ist zulässig und verbietet jede konkrete Requirement-Sprache; eine ungültige Range ist dagegen Konfigurationsfehler. `*` erlaubt jeden syntaktisch gültigen Tag, hebt aber die unabhängigen Registry- und Unspecified-Prüfungen nicht auf.

Basic Filtering arbeitet case-insensitiv an Subtaggrenzen: `en` erfasst `en-US` und `en-IN`, nicht etwa `enm`. Ein konkreter erlaubter Range `en-US` erlaubt nicht automatisch den gröberen Tag `en`. `zh` und `cmn` werden in der Erlaubnisprüfung nicht als Alias gleichgesetzt. Der Detektorvergleich aus T.7 ist ausdrücklich eine andere Operation.

Die Mischung wird anhand **deklarierter** Requirement-Sprachen, niemals anhand eines Detektorergebnisses, berechnet. Der Projektscope betrachtet alle nicht `retired`, `superseded` oder `rejected` Requirements im ausgewählten Konfigurationsumfang. Dokument und Abschnitt betrachten die in der aufgelösten Darstellung tatsächlich referenzierten oder durch eingebettete Queries enthaltenen Requirements, einschließlich eingebundener Unterabschnitte und Dokumente. Es wird nicht die gesamte fachliche Trace-Closure betrachtet. Ein Requirement wird je Container höchstens einmal gezählt; identische Einbindungen erzeugen keine künstliche Mischung. Explizit referenzierte historische Requirements werden mitgezählt. Reine Prosa, Quellenauszüge, IDs und Codeblöcke werden nicht statistisch nach Teilsprachen zerlegt und begründen in Version 0.2 kein Mischungsurteil.

`comparison=primary_language` vergleicht den ersten Sprachsubtag; `en-US` und `en-IN` sind dann keine Mischung. `comparison=exact_tag` vergleicht vollständige normalisierte Tags. Andere Werte sind unzulässig. Private-use- oder unregistrierte Tags werden im primary-Modus als vollständiger normalisierter Tag behandelt, statt alle unter `x` zusammenzufassen. `und`, `mul` und `zxx` ergeben kein falsches Urteil über die Anzahl konkreter Sprachen; ihre gesonderte Diagnose bleibt erhalten. Eine Mischung liegt bei mehr als einem verschiedenen auswertbaren Vergleichsschlüssel vor. Der Bericht nennt die vollständig sortierte Tagliste, die verwendeten Requirement-IDs, den Container und die Policy. Leere Mengen sind keine Mischung.

Ein Dokument beziehungsweise Abschnitt darf optional `language_policy_override.mixed_languages` mit `allow|warning|error` setzen. Der nächste explizite Containerwert gilt nur für seinen eigenen Mischungscheck, nicht als Änderung der Projekterlaubnisliste. Der Check des übergeordneten Dokuments bleibt unabhängig bestehen. Bei mehreren Einbindungspfaden wird jede Containerprüfung auf dessen aufgelöster Darstellung durchgeführt. Es werden keine neuen Rechte oder Autoritäten aus einer solchen Darstellungsregel abgeleitet.

## S.6 Projektprofile, Sprachpakete und Bedienoberfläche

Projektprofile bestimmen weiterhin Struktur, Lifecycle und fachliche Regeln. Sie dürfen nicht mehr verlangen, dass alle Inhaltsartefakte dieselbe Sprache haben. Die bisherige Kompositionszeile „normative Sprache und Primärlocale müssen gleich sein“ entfällt. `software-de` und `software-en` bleiben kompatible Fachprofile und enthalten keine exklusive globale Inhaltssprache. Default für neue Requirements ist allein `language_policy.default_language`; `default_locale` bezeichnet nur die Darstellung von CLI-Hilfen und Standardlabels. Technische Feldnamen, Befehle und Diagnosecodes bleiben Englisch und stabil.

Sprachpakete sind deklarative Ressourcen mit `package_id`, SemVer-`version`, `language_ranges`, `labels`, `literal_rules` und `capabilities`. Sie dürfen weder Importpfade noch ausführbare Callbacks enthalten. Das aktuelle Release liefert die Metadaten-/Labelpakete `de`, `en`, `hi`, `id`, `pt`, `es`, `ru`, `ja` und `zh-Hans`; letzteres deklariert sowohl `zh-Hans` als auch `cmn-Hans` als unterstützte Inhaltsbereiche, ohne beide Tags gleichzusetzen. Fehlende übersetzte Labels verwenden die unveränderten englischen Enumwerte, keine automatische Übersetzung.

Alle nach Basic Filtering passenden, ausdrücklich aktivierten Pakete werden in ihrer gebundenen Reihenfolge angewendet. Gleiche Regelidentität und Version darf nur bei gleichem Ressourcenhash zusammenfallen; unterschiedliche Definitionen sind ein Konflikt. Fehlendes Paket verhindert weder das Speichern einer erlaubten Sprache noch die strukturelle Validierung. Der Bericht weist `not_available` statt `passed` für nicht vorhandene Sprachprüfungen aus. Sprachpakete werden nur für die betroffenen Artefakte geladen.

In dieser Version existiert **keine eingebaute Prüfung der Bedeutung des Textes gegen `normative_force`**. Insbesondere löst das bloße Auftreten von „sollte“ nicht automatisch eine Behauptung semantischer Unvereinbarkeit aus. Zulässig bleiben exakte, explizit konfigurierte Glossar-/Platzhaltervergleiche ohne Interpretation ihrer Bedeutung. Die fachliche Einzelforderungs- und Widerspruchsprüfung bleibt ein Reviewkriterium; eine strukturierte Regel darf lediglich das von ihr tatsächlich geprüfte Teilkriterium als geprüft melden.

## S.7 Austausch, Revisionen und Migration von Entwurfsständen

`language`, `normative_force` und die Sprachpolicy sind normative Werte und Teil von Diff, Change Plan, Profil-/Konfigurationshash, Verification Context und Relationskontext. Sie werden durch CSV-, NDJSON-, ReqIF-Mapping und generierte Ansichten erhalten. Im ReqIF-Kernmapping werden `specroad.language` als Stringattribut und `specroad.normative_force` als Enum mit den vier exakten Werten exportiert. CSV/NDJSON verwenden die gleichnamigen Felder. Fehlende Werte verlangen ein explizites Mapping; sie werden nicht aus Priorität oder Textschlüsselwörtern abgeleitet. Ein Austauschziel, das diese Attribute nicht erhält, erzeugt den bestehenden Verlustbericht und keine behauptete verlustfreie Rückübertragung.

Diese Dokumentversion erweitert den noch nicht freigegebenen Entwurf des Zielreleases 0.2.0. Sie behauptet keine rückwärtskompatible Änderung eines bereits veröffentlichten produktiven 0.2.0-Schemas. Daten, die nach einer älteren SpecRoad-Entwurfsspezifikation erzeugt wurden, werden vor regulärer neuer Nutzung über `migrate plan --from-spec 0.2.5 --mapping <FILE>` beziehungsweise den bestehenden 0.1-Migrationspfad behandelt. `--from-spec` ist nur für die dokumentierten 0.2.0–0.2.5-Entwurfssnapshots zulässig; die exakte Quellschema- und Profilsammlung wird im Plan gebunden. Ohne diese ausdrückliche Herkunftsauswahl werden fehlende Pflichtfelder nicht als kompatibel akzeptiert.

Das Mapping benennt für jedes zu migrierende Requirement dessen ID, erwarteten alten Vollhash, explizite Zielsprache, explizite Zielverbindlichkeit und den geprüften vollständigen Zielsachverhalt. Ein Autor darf eine gemeinsame Sprache ausdrücklich als Mappingdefault bestimmen; eine normative Stärke wird immer pro Requirement festgelegt. `statement` darf nur mit einem im Mapping gelieferten, autorisierten Zieltext verändert werden. Es gibt weder automatische Schlüsselwortentfernung noch py3langid als migrationsentscheidende Quelle.

Bereits unveränderbare Evidence, Baselines und Relationsreviews behalten Originalbytes und ihre früheren Schema-/Profilbindungen nach Anhang Q. Der Migrationsnachweis bindet zusätzlich die Quellspezifikationsversion, damit gleiche frühere Entwurfs-Schemaetiketten keine falsche Gleichheit behaupten. Neue Fachfelder erzeugen neue fachliche Kontextbindungen; alte Nachweise werden nicht zur aktuellen Erfüllung umgedeutet. Unvollständige Mappings blockieren nur den Apply, nicht eine ehrliche Plan-/Konfliktausgabe. Vollständige Migration erfolgt weiterhin gesichert, transaktional und ohne autonome menschliche Freigabe.

## S.8 Rückverfolgbare fachliche Grenzen

Sprachmischung im selben Repository begründet keinen Mehrbenutzerserver. Autoren können unterschiedliche Sprachen verwenden, aber ein zuständiger Reviewer muss den freizugebenden Inhalt beurteilen können. Automatische Übersetzung, die Bewertung von Übersetzungsäquivalenz und mehrere gleichrangige normative Originalfassungen werden nicht neu eingeführt. Der generische Analyzer-Vertrag kann später auch solche Beobachtungen transportieren. Ihre Einführung benötigt eine weitere fachliche Entscheidung und keinen verdeckten Funktionswechsel des py3langid-Adapters.

---

# Anhang T — Allgemeiner Analyzer-Vertrag und erster py3langid-Adapter

## T.1 Pflichtumfang und Erweiterungsgrenze

Das erste Zielrelease liefert den generischen **`analyzer-contract` 1.0.0** sowie den implementierten, integrierten und getesteten Adapter `specroad.py3langid` 1.0.0 mit Capability `language_detection`. Der py3langid-Adapter ist ein verpflichtender Releasebestandteil, seine Laufzeitabhängigkeiten sind jedoch keine Voraussetzung für den dependency-freien Core. Eine Veröffentlichung nur mit Schnittstellen-Stubs erfüllt die Abnahme nicht.

Analyzer können unterschiedliche Fähigkeiten und unterschiedliche Eingabetypen beschreiben: einzelne Statements, mehrere Statements mit gemeinsamer Bindung, Metadaten, Graphprojektionen oder explizite Kontextressourcen. Der Core kennt den generischen Umschlag und die beim jeweiligen Adapter deklarierten Payload-Verträge, nicht die Fachsemantik aller zukünftigen Findings. Er leitet aus einer Capability keine Freigabeberechtigung ab.

Für das erste Release ist ausschließlich der fest ausgelieferte lokale Worker für `specroad.py3langid` durch `analyzer run` ausführbar. Ergebnisse anderer Analyzer werden bereits über `analyzer request`, den dateibasierten Austausch und `analyzer import/show/evaluate` verarbeitet. Weitere automatisch gestartete Bibliotheken, frei konfigurierbare Prozesskommandos und Remote-Aufrufe sind noch kein Ausführungsumfang. Die Betriebsarten `library`, `external_process` und `remote_service` können als Herkunftsmetadaten vorkommen; sie sind keine Ausführungserlaubnis. Der erste Adapter ist eine Library-Integration innerhalb eines kontrolliert gestarteten mitgelieferten Workerprozesses.

## T.2 Descriptor

Ein Descriptor enthält genau `contract_version`, `analyzer_id`, `adapter_version`, `capabilities`, `subject_modes`, `result_schema_version`, `execution_mode`, `determinism`, `dependency_requirements` und `extensions`. Versionsfelder sind SemVer. `analyzer_id` und Capability-IDs sind ASCII-Strings nach `[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*` mit höchstens 128 Zeichen. Ein Descriptor enthält keine frei ausführbaren Befehle. Unbekannte Top-Level-Felder sind Fehler; unbekannte Namespaces unter `extensions` bleiben verlustfrei erhalten.

`capabilities` und `subject_modes` sind nichtleere sortierte Arrays ohne Dubletten. `subject_modes` kennt `single_text`, `multi_subject` und `structured`. `determinism` ist `pinned_engine` oder `not_guaranteed`. `execution_mode` ist `builtin_worker`, `external_result_only` oder `future_unsupported`. Ein fremder Descriptor kann sich nicht selbst `builtin_worker`-Rechte erteilen. Die tatsächliche Ausführungsliste stammt ausschließlich aus der signierten beziehungsweise hashgebundenen vertrauenswürdigen Distribution, nicht aus Projektdateien.

Für `specroad.py3langid` gelten `single_text`, Capability `language_detection` und `pinned_engine`. Ein Mehrfachauftrag ist die vollständige Menge einzelner Textsubjects; der Adapter setzt Texte unterschiedlicher Anforderungen nicht zu einem künstlichen Gesamttext zusammen.

## T.3 Request und Eingangsbindung

Ein Request enthält `contract_version`, `request_id`, `analyzers`, `subjects`, `context`, `settings`, `snapshot_sha256` und `extensions`. `request_id` ist ausschließlich eine **Analysekennung (`AnalysisRequestId`)**. Sie korreliert Request, Reports und Fortsetzung; sie ist keine Request-ID eines normativen Schreibbefehls. Nur die Zeichenketten-Syntax `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}` wird wiederverwendet. Weder die Akteurspflicht noch Operationshash, Projekttransaktion, Write-Idempotenz oder Receipts werden dadurch übernommen. Die Regeln SR-REQ-0383 bis SR-REQ-0385 gelten ausschließlich im normativen Schreibnamensraum.

Die Vergabe ist abschließend festgelegt:

| Eingang | Vergabe und Verhalten |
|---|---|
| `analyzer request` oder `analyzer run --analyzer ...`, ohne `--analysis-id` | Die Runtime erzeugt vor dem ersten Bearbeitungsschritt genau einmal `AN-` plus einen unabhängig zufälligen Token nach `random128-v1` aus 9.2. Sie veröffentlicht die Kennung im Request beziehungsweise Reportpackage; bei Checkpointbedarf zusätzlich in der Work-Bindung. |
| dieselben Befehle mit `--analysis-id <ID>` | Der syntaktisch gültige Wert wird unverändert als Analysekennung verwendet; ein ungültiger Optionswert ergibt Code 2 vor Ausführung. |
| `analyzer run --request <FILE>` | Die enthaltene gültige Analysekennung wird unverändert übernommen. Eine fehlende oder syntaktisch ungültige Pflichtkennung ergibt Code 3; keine stillschweigende Erzeugung oder Reparatur des Requests. `--analysis-id` ist in diesem Modus unzulässig und ergibt Code 2. |
| `work resume` / `work restore` | Die bereits gebundene Analysekennung bleibt erhalten. Ein Resume darf sie weder neu erzeugen noch überschreiben. |
| `analyzer import`, `show`, `evaluate` | Kennungen werden nur aus den gebundenen Daten gelesen; diese Befehle vergeben keine neue Analysekennung. |

Die Zeichenfolge allein ist weder eine Inhaltsadresse noch ein globaler Deduplizierungsschlüssel. Für die Zuordnung eines Berichts zu einem Request müssen **Analysekennung und `snapshot_sha256`** übereinstimmen. Gleichlautende Analyse- und Schreibkennungen kollidieren nicht und berechtigen nicht zum Lesen, Erzeugen oder Ändern von `.specroad/requests/`. Getrennte Analyseaufträge dürfen dieselbe manuell gewählte Kennung besitzen; ihre Snapshot-/Enginebindungen bleiben maßgeblich. Ein neuer Start ist kein automatischer Ergebnis-Retry, auch nicht bei identischer Kennung und identischem Snapshot. Für das Fortsetzen eines vorhandenen Auftrags wird ausdrücklich dessen Work-Root verwendet. Dort ist eine abweichende Kennung oder Snapshotbindung ein Konflikt mit Code 6; der vorhandene Checkpoint bleibt unverändert. Bestehende Ausgabedateien behalten unabhängig davon ihren No-op-/Konfliktvertrag aus T.5.

Bei beginnender Request-Erzeugung wird die einmal vergebene Kennung in `normalized_arguments.analysis_id` gebunden. Muss bereits der Snapshotaufbau pausieren, sichert Anhang P diese Kennung und den noch offenen Snapshotaufbau; ein unvollständiger Request wird nicht als fertig ausgegeben. Sobald der datentragende Request vorliegt, wird er einschließlich seiner Analysekennung als externe Eingabepayload in `source_bindings` / `input_manifest_sha256` gebunden. Der Analyzerrequest enthält weiterhin keine zusätzlichen betrieblichen Top-Level-Felder. Die Work-Felder `actor`, `request_id` und `operations_sha256` bleiben für diesen nicht normativen Auftrag `null`; sie werden nicht mit der Analysekennung oder erfundener Autorisierung gefüllt.

`analyzers` bindet pro Eintrag Descriptor, dessen Hash und gewünschte Capabilities. `subjects` ist eine nichtleere geordnete Liste; jeder Eintrag enthält `subject_key`, `artifact_id`, `artifact_revision`, `artifact_sha256`, `field_pointer`, `value`, `value_sha256`, `declared_language` und optional `normative_force`.

`subject_key` ist SHA-256 über die JCS-Objekt mit genau den Schlüsseln `artifact_id`, `artifact_revision`, `artifact_sha256` und `field_pointer` und den gleichnamigen Subjectwerten. Die Artefaktbindung meint den vollständigen gespeicherten Artefakthash. `value_sha256` ist SHA-256 über den JCS-Wert des selektierten Felds, nicht über eine localeabhängige Darstellung. `field_pointer` ist ein RFC-6901-Pointer. Nicht vorhandene oder typwidrige Pflichtfelder werden als Eingabefehler berichtet, nicht durch leere Texte ersetzt. Für Spracherkennung ist genau ein Stringwert pro Subject erforderlich.

`context` enthält explizite weitere `{resource_id, sha256, value}`-Bindings und die vollständige ausgewählte Subjectmenge. Der Caller exportiert nur die angeforderten Felder, nicht automatisch das gesamte Repository. Kontext enthält niemals Secrets, freie Host-Umgebungsvariablen oder beliebige absolute Pfade. Der Request-Snapshothash ist SHA-256 über das JCS-Objekt mit genau `contract_version`, `analyzers`, `subjects`, `context`, `settings` und `extensions`. `request_id` und `snapshot_sha256` sind ausgeschlossen; Requests enthalten keine weiteren betrieblichen Top-Level-Felder. Auch die sortierte vollständige Menge der Analyzer/Capabilities, die Textauswahl, Kandidatenklasse, Vergleichspolicy und Vorverarbeitungsparameter werden gebunden. Eine neue Subjectmenge ist ein anderer Auftrag.

Der py3langid-Default ist `/statement` für Requirements. Zusätzliche `--field`-Pointer erzeugen eigenständige Subjects in sortierter ID-/Pointer-Reihenfolge. Der gemeinsame Request ist ein vollständiger datentragender Snapshot; zukünftige externe Analyzer müssen nicht eigenständig Projektdateien öffnen. Ein Text kann wie eine Systemanweisung aussehen und bleibt trotzdem reiner Analyseinhalt.

## T.4 Resultate, Findings und Unabhängigkeit von Evidence

Ein `analysis-report` enthält `contract_version`, `report_version`, `run_id`, `request_id`, `snapshot_sha256`, `analyzer`, `engine`, `subjects`, `coverage`, `run_status`, `findings`, `operational`, `result_sha256` und `extensions`. `run_id` ist `AR-` plus ein Token nach `random128-v1`. `analyzer` bindet die Descriptoridentität; `engine` bindet Adapter-/Libraryversionen, Modellhash, Kandidatenmenge, Vorverarbeitungsversion, verwendete Unicode-Datenversion und numerisch relevante Runtime-/NumPy-Fingerprints. Unbekannte technische Daten sind `null` mit Grund; ein unvollständig identifizierter Engine-Fingerprint darf keine reproduzierbare Qualitätszusage erhalten.

`run_status` ist exakt `complete|partial|failed|unavailable`. `coverage` nennt erwartete, bearbeitete, nicht entscheidbare, fehlgeschlagene und noch offene Subjectschlüssel. Jedes Subject besitzt genau ein Ergebnis mit seinen ursprünglichen Bindungen, `status`, `payload` und optionalen Findings. Ein vollständiger Lauf kann nicht entscheidbare Subjects enthalten; `complete` bedeutet vollständig abgearbeitet, nicht Sprache bestätigt. Die Summen und Mengen müssen exakt zum Request passen. Doppelte oder fremde Subjectschlüssel sind ungültig.

Ein Finding enthält `finding_id`, namespaced `code`, `severity=info|warning|error`, `subject_keys`, `message`, `rationale`, `details` und optional `suggestion`. `finding_id` ist ein innerhalb des Berichts eindeutiger String. Eine Konfidenz ist nur als typed Detail mit benannter Scoresemantik erlaubt. Ein empfohlenes Update ist untrusted Dateninhalt, niemals ein unmittelbar ausführbarer Change Plan. Mehrere Analyzer dürfen für dasselbe Subject unterschiedliche Findings liefern; ihre Provenienz bleibt getrennt. Es gibt keine automatische Mehrheitsentscheidung und keine Auswahl nur des erfolgreichen Analyzers.

`result_sha256` ist SHA-256 über das JCS-Objekt mit genau `contract_version`, `report_version`, `snapshot_sha256`, `analyzer`, `engine`, `subjects`, `coverage`, `run_status`, `findings` und `extensions`. Alle Werte werden unverändert aus dem Bericht übernommen. Zufällige Run-ID, Erfassungszeit, PID, Hostpfad und Laufzeitmessungen unter `operational` sind ausgeschlossen. Ein Full-File-Hash bindet bei Transport zusätzlich die unveränderten Berichtsbytes. Ein Hash beweist keine Echtheit eines fremden Analyzers.

Ein Analyzerbericht ist **kein neues kanonisches Artefakt und keine Evidence**. Er verändert keine Anforderung, keine Verbindlichkeit, keinen Reifegrad, keine Relationsfreigabe und kein `verification_result`. Fremde Resultate bleiben gekennzeichnete Beobachtungen; ein Import setzt sie nicht auf `passed`. Ein Mensch kann einen Bericht über bestehende Source-/Attachment-/Evidence-Verfahren ausdrücklich referenzieren, wobei sämtliche dafür geltenden Autorisierungs- und Verification-Verträge unverändert gelten. Automatische Textkorrekturen durch Detector oder Importer sind ausgeschlossen.

## T.5 Speicher- und CLI-Vertrag

Analyzerrequests und -berichte sind explizite Dateien oder stdout-Daten. Standardablage bei angefordertem Dateiziel ist `generated/analysis/`; alternative explizite Ausgabeziele folgen dem bestehenden Root-/Symlink-Vertrag. Sie gehören nicht zum kanonischen Modell, verändern keine Modellwurzel und werden nicht automatisch als erforderliche Daten in das Projekt importiert. Ein Originalbericht wird nicht überschrieben: bei vorhandenem Ziel sind identische Bytes ein No-op, unterschiedliche Bytes Code 6. Der Aufrufer wählt für einen neuen Lauf eine neue Datei. Reportveraltung wird bei Anzeige berechnet, nicht in der Originaldatei nachgetragen.

| Befehl | Vollständiger Mindestvertrag | Klasse |
|---|---|---|
| `analyzer list` | Statische Descriptoren und tatsächliche Verfügbarkeit ausgeben; keine Modellinitialisierung. | `read_only` |
| `analyzer describe <ID>` | Descriptor, Capabilities, Input-/Outputschemas, bekannte Laufzeitvoraussetzungen und `execution_supported` ausgeben. | `read_only` |
| `analyzer request --analyzer <ID>... [--subject <ID>...] [--field <POINTER>...] [--analysis-id <ID>] [--output <FILE>]` | Expliziten Snapshot erstellen; ohne Subjects alle Requirements des gewählten Konfigurationsumfangs; ohne Field nur `/statement`; ohne Output stdout. | `generated_output` |
| `analyzer run --analyzer <ID>... [--subject <ID>...] [--field <POINTER>...] [--analysis-id <ID>] [--output <FILE>]` | Request bilden und nur autorisierte mitgelieferte Adapter ausführen; vollständiger Mehranalyzer-Envelope, auch bei Einzelproblemen. | `generated_output` |
| `analyzer run --request <FILE> [--output <FILE>]` | Vollständig gebundenen Request ohne erneute Feldselektion ausführen; Selektions-/Settings-Overrides sind Code 2. | `generated_output` |
| `analyzer import <FILE> [--output <FILE>]` | Fremden JSON-Bericht strukturell und kryptografisch gegen seinen enthaltenen Request/Snapshot oder einen expliziten `--request <FILE>` prüfen; Original und lokale Bewertung getrennt ausgeben; keinen Analyzer starten. | `generated_output` |
| `analyzer show <FILE> [--request <FILE>]` | Bericht und lokale Aktualitätsbewertung ohne Ausführung anzeigen. | `read_only` |
| `analyzer evaluate <FILE>... [--request <FILE>]` | Explizit ausgewählte Berichte gemeinsam prüfen; kein impliziter „neuester Erfolg“, keine unterdrückten Fehler eines gewählten Berichts. | `read_only` |

Ein Reportpaket für eigenständigen Austausch enthält `package_version=1.0.0`, `request` und `reports`; das Package ist ein einzelnes JSON-Dokument. Jeder Bericht muss dieselbe Analysekennung und denselben `snapshot_sha256` wie der enthaltene beziehungsweise explizit gewählte Request besitzen. Eine Verletzung dieser Paarbindung ist Code 3; ein gleichlautender Snapshot ersetzt nicht die fehlende Kennungsübereinstimmung. `run --output` schreibt dieses Package atomar; bei stdout ist es das `result` des bestehenden CLI-Envelopes. `import`, `show` und `evaluate` akzeptieren das Package oder einen Einzelbericht mit explizitem Request. Das Namespaced-Findingformat ist offen, seine JSON-Struktur nicht beliebig: deklarierte Version, Typen, Größen, vollständige Bindungen und XSS-/Pfadgrenzen bleiben verbindlich.

`--project` ist bei aus Projekt erzeugten Requests Pflicht oder über bestehende Root-Erkennung auflösbar. Beim vollständig datentragenden `--request` darf die Ausführung ohne Projekt erfolgen. Ein fremdes Ergebnis kann dann strukturell geprüft, aber nicht als `current` zu einem nicht verfügbaren Arbeitsstand ausgewiesen werden. `current|stale|unavailable|invalid` sind berechnete Bewertungszustände, keine Behauptung über die Wahrheit des Findings.

Keiner dieser Befehle ist `normative_write`. Sie setzen keine fachlichen Request-Receipts und keine menschlichen Reviews. Für jeden erforderlichen Checkpoint gilt ohne Analyzer-Ausnahme Anhang P.2: Mit `--work-dir` wird das ausdrücklich gewählte zulässige externe Verzeichnis verwendet; ohne die Option erzeugt die Runtime beim ersten notwendigen Checkpoint einen exklusiven externen Work-Root im verfügbaren temporären Verzeichnis. Ein kleiner vollständig abgeschlossener Aufruf erzeugt keinen Work-Root. Diese externen Betriebsdaten sind weder normative Projektwrites noch Seiteneffekte in `.specroad/`.

Code 8 ist erst nach dauerhaft und atomar veröffentlichter gültiger Checkpointgeneration zulässig. Die Ausgabe enthält den tatsächlichen Work-Pfad, Work-ID, Analysekennung soweit für den Befehl vorhanden, Checkpointhash, vollständige Restbindung und konkrete nächste Aktion nach Anhang P. Das ist offengelegter Arbeitszustand, kein versteckter Sessionzustand. Ist weder ein zulässiger externer Speicherort noch ein sicherer sparsamer Abschluss möglich, gilt der tatsächliche Blockervertrag aus O.4/T.9 mit Code 5 statt eines erfundenen Code-8-Checkpoints. Ein weiches Budget allein ist kein solcher Blocker. Ein automatisch angelegter Work-Root wird bei Code 8 erhalten; seine Bereinigung folgt ausschließlich P.9.

Work-Pakete enthalten den gebundenen Request beziehungsweise seinen fortsetzbaren Aufbau, bereits erzeugte Berichtsteile und offene Subjects. Reguläre Projektbundles bleiben ohne explizite normativ referenzierte Anhänge frei von generierten Berichten. Für einen Chatbot-Roundtrip werden Reportpackage und Projektbundle beziehungsweise das Work-Paket gemeinsam übergeben. Ein temporärer Work-Root innerhalb einer verlorenen Sandbox ist keine externe Sicherung; für diesen Fall bleibt der verifizierte Work-Export erforderlich.

Die Commands unterstützen `--format pretty|json`, `--quiet`, `--no-color`, `--fail-on error|warning` sowie die Betriebs-/Work-Optionen aus N–P; `--strict` ändert nur den vorhandenen Fail-Schwellwert, nicht den Kandidatenraum. `--actor-*`, `--request-id`, `--as-proposal` und `--dry-run` sind auf ihnen unzulässig, weil sie keine Fachänderung planen. Die ausschließlich für Request-Erzeugung zugelassene Option `--analysis-id` folgt T.3 und ist kein Alias von `--request-id`. `--help` und `command describe` nennen sämtliche Ausnahmen. Nicht genannte CLI-Optionen sind Code 2.

## T.6 Erster Adapter, Distribution und kontrollierte Ausführung

Die spezifizierte Referenz ist `py3langid==0.4.0` mit dessen mitgeliefertem Modell. Die Upstream-Paketbeschreibung dokumentiert Python ab 3.10, eine normalisierte Rangliste und eine mögliche Nichtentscheidung; die Paketmetadaten nennen NumPy als Zusatzabhängigkeit [EXT-001, EXT-002]. Der Adapter stellt keine eigene Sprachverständnisfunktion bereit.

Die ausführbare Zusatzdistribution heißt funktional **SpecRoad Language Detection**. Lokal kann sie über das deklarierte Extra `specroad[language]` installiert werden; das ist ein zu implementierender Packagingvertrag, keine Aussage über ein heute bereits veröffentlichtes SpecRoad-Paket. Jede Freigabe liefert zusätzlich ein nach Python-ABI und Linux-x86-64-Plattform getrenntes Offlinepaket mit Adapter, py3langid, passendem NumPy-Wheel, Modell, Lizenzen und Hashmanifest. Die Paketkombinationen für CPython 3.10 bis 3.14 werden jeweils getestet; ein einziger NumPy-Pin muss nicht für alle Interpreter behauptet werden. Ein nicht vorhandenes passendes Paket wird ausdrücklich gemeldet. Die Core-Zipapp enthält kein verdecktes NumPy-Binary.

Bei `analyzer run` wird der bekannte Worker über einen kontrollierten Subprozess gestartet. Interpreter und Workerpfad stammen aus der vertrauenswürdigen Distribution beziehungsweise aus einer ausdrücklich vom lokalen Nutzer gewählten Installationsumgebung, niemals aus Projektinhalt. Start ohne Shell, ohne fremde entry-point-Autodiscovery und ohne Imports aus dem Projekt-CWD. Der Adapter wird erst für die explizite Analyse initialisiert; `help`, `version`, `validate`, `show` und `analyzer list` laden weder NumPy noch das Sprachmodell. Der Worker erhält den datentragenden Request über stdin und liefert genau einen JSON-Bericht über stdout; Laufzeitdiagnosen gehen nach stderr. Das Protokoll enthält keine Netzadresse oder ausführbare Projektdatei.

Netzwerk, Telemetrie, Modelltraining, Webservice-Modus, URL-Klassifikation, automatische Paketinstallation, beliebige Fremdmodelle und Hintergrundworker sind im ausgelieferten Adapter deaktiviert beziehungsweise nicht exponiert. Es wird ausschließlich das hashgeprüfte mitgelieferte Modell geladen. Ein Projekt kann keinen alternativen deserialisierten Modellblob einschleusen. Die Kontrollgrenze ist keine allgemeine Betriebssystem-Sandbox für beliebigen untrusted Code: ausgeführt wird nur der ausgelieferte vertrauenswürdige Adapter. Fremde Analyzer werden im ersten Release ausschließlich außerhalb von SpecRoad vom Nutzer/Agenten betrieben und über Dateien angebunden.

Nach Abschluss werden Kindprozesse eingesammelt. Ein Fehler oder Abbruch beendet den Worker, erhält abgeschlossene Work-Ergebnisse und hinterlässt keinen dauerhaft laufenden Dienst. Gleichzeitige Workerzahl ist im Default 1. Die initiale Modellladung erfolgt höchstens einmal je Worker; Subjects werden in stabiler Reihenfolge innerhalb desselben Aufrufs abgearbeitet. Multi-Analyzer-Aufträge behalten je Adapter einen eigenen Status. Das Scheitern eines Adapters ist keine Erlaubnis, unbemerkt die übrigen angeforderten Analysen wegzulassen.

## T.7 Textvorbereitung, Scores und Sprachvergleich

Der Adapter übergibt jeden vollständigen ausgewählten String separat. Eine Analyse des Anfangs oder eines Stichprobenausschnitts darf nicht als Analyse des vollständigen Statements ausgegeben werden. Für die Entscheidung `insufficient_text` wird ausschließlich die Länge nach Entfernung führender/abschließender ASCII-Leerzeichen `U+0009..U+000D` und `U+0020` verwendet. `min_text_codepoints` hat Default 20 und Wertebereich 1 bis 10000. Diese Zahl ist eine versionierte technische Abstentionspolicy, keine empirisch belegte universelle Grenze für alle Sprachen.

Die py3langid-interne NFC-/Großschreibungsnormalisierung bleibt auf dessen Arbeitskopie begrenzt und wird über Library- und Unicode-Datenversion im Enginefingerprint gebunden [EXT-001]. Originalwert, Originalhash und deklarierter Sprach-Tag bleiben unverändert. Unterschiedliche Requirements oder Pointer werden nicht zusammengefügt. Interne Code-, Zitat- und Sprachwechsel werden nicht semantisch segmentiert; ein kompletter gemischter Text darf `undetermined` ergeben.

Der Kandidatenraum ist standardmäßig **das vollständige mitgelieferte Modell**, nicht nur die laut Projekt erlaubten Sprachen. Dadurch wird ein verbotener französischer Text nicht zwangsweise einer erlaubten Sprache zugeschlagen. Die erste Adapterversion exponiert keinen Kandidatenfilter, der diese Eigenschaft verändert. Das geordnete Kandidatenverzeichnis und sein Hash stehen im Request/Enginefingerprint.

Der Adapter nutzt die normalisierte Rangliste (`norm_probs=True`) und serialisiert die beiden besten Scores als Dezimalstrings mit 12 Nachkommastellen, Rundung half-even. Ranggleichstand wird nach Sprachcode aufgelöst. Die Entscheidung arbeitet ausschließlich mit diesen publizierten quantisierten Werten. `min_score` ist der Dezimalstring `"0.900000000000"`, `min_margin` ist `"0.100000000000"`; beide sind in `[0,1]` konfigurierbar, maximal 12 Dezimalstellen, in der Requestpolicy materialisiert. Rohscores wie negative Log-Likelihoods sind keine Wahrscheinlichkeiten. Auch normalisierte Scores werden ausdrücklich als **nicht kalibrierte Modellscores** bezeichnet, nicht als „90 Prozent sicher korrekt“.

| Voraussetzung, in dieser Reihenfolge geprüft | Beobachtung |
|---|---|
| ausgewählter String fehlt oder ist typwidrig | Eingabefehler; keine Detektion |
| String nach der definierten Randentfernung leer oder kürzer als `min_text_codepoints` | `undetermined`, Grund `insufficient_text` |
| Worker/Dependency/Modell nicht verfügbar | `unavailable`, niemals sprachlich passend |
| Score ist nicht endlich, außerhalb `[0,1]` oder Rangliste widersprüchlich | `failed`, Grund `invalid_backend_output` |
| Top-Label ist `und` oder `zxx` | `undetermined`, Grund `backend_abstention` beziehungsweise `non_linguistic` |
| Topscore kleiner als `min_score` oder Abstand zum zweitbesten Score kleiner als `min_margin` | `undetermined`, Grund `low_score_or_margin` |
| übriger Fall | `detected`; publizierter Top-Sprachcode, Scores und vollständige Bindung |

Die Grenzen sind inklusiv: Score und Abstand genau auf ihrer jeweiligen Grenze genügen. `undetermined` ist weder Treffer noch Fehlkennzeichnung. Ein gleich hoher Topscore ist mit dem Defaultabstand keine Entscheidung.

Für eine entschiedene Beobachtung gilt `language-comparison-v1`. Stimmt der erkannte Code mit dem primären deklarierten Sprachsubtag überein, ist das Ergebnis `compatible`; Region und Script sind **nicht geprüft**. Die einzige zusätzliche Zuordnung der ersten Version ist `declared primary=cmn`, `detected=zh`: Ergebnis `compatible_coarse`, `language_resolution=macrolanguage_only`. Dieses Ergebnis bestätigt ausdrücklich nicht Mandarin. Für die Erlaubnisliste werden diese Tags weiterhin getrennt behandelt. Andere Kombinationen sind `mismatch`, sofern beide Seiten vergleichbare bekannte Sprachcodes sind; private/unbekannte oder unspezifische Tags liefern `unverifiable`. Es gibt keine vermutete Ableitung von `zh-Hans-CN`, `zh-Hant-TW`, `en-US` oder `en-IN` aus einem groben Detectorlabel.

## T.8 Policy, Aktualität und Ergebnisaggregation

Der erste Adapter verwendet folgende materialisierten Defaults unter `analyzer_policy.language_detection`:

```json
{
  "adapter": "specroad.py3langid",
  "adapter_version": "1.0.0",
  "mismatch": "warning",
  "undetermined": "info",
  "compatible_coarse": "info",
  "unverifiable": "info",
  "min_text_codepoints": 20,
  "min_score": "0.900000000000",
  "min_margin": "0.100000000000"
}
```

Für diese Ergebnisaktionen sind `ignore|info|warning|error` zulässig. Ignorieren verändert weder Coverage noch den dokumentierten Beobachtungsstatus. `unavailable` und Backendfehler sind keine absenkbaren fachlichen Scores: ein ausdrücklich angeforderter, technisch nicht ausführbarer Analyzerauftrag meldet Code 5. Ein korrekt ausgeführter Lauf mit Findings am Fail-Schwellwert liefert Code 1. Vollständige Ausführung ohne solche Findings liefert Code 0, auch wenn ausdrücklich als `info` behandelte Nichtentscheidungen vorliegen. Der Envelope trennt `execution_complete`, `all_languages_confirmed` und `gate_passed`; diese Werte sind nicht synonym. `compatible_coarse` und `undetermined` dürfen `all_languages_confirmed` nicht auf true setzen.

Eine gespeicherte Beobachtung ist `current`, wenn alle Subject-ID-/Revisions-/Vollhash-/Pointer-/Value-Bindungen sowie die gebundenen Kontext- und Settingsressourcen unverändert sind. Bei Abweichung ist sie `stale`. Fehlt der benötigte Arbeitsstand oder Request, ist sie `unavailable`; fehlerhafte Integritäts-/Schemawerte sind `invalid`. `current` besagt nur „passt zu diesen Eingaben“. Für `analyzer evaluate` ist ein alter oder nicht prüfbarer Bericht kein bestandener aktueller Analysecheck. Das Original wird dabei nicht verändert.

`validate` und `lint` prüfen im Default die deklarierten Sprachen und die deterministischen Metadaten-/Strukturregeln; sie starten **keinen** Analyzer und behaupten auch nicht, die Textsprache geprüft zu haben. `--strict` aktiviert ebenfalls keine Zusatzabhängigkeit. Eine lokale CI kann zusätzlich `analyzer run` beziehungsweise `analyzer evaluate` ausdrücklich als Gate aufrufen. Das erste Release führt keine implizite Analyzerpflicht in den Artefakt-Approval-/Evidence-Gates ein. So bleibt ein Core-Projekt auch ohne NumPy vollständig bearbeitbar, während eine ausdrücklich angeforderte Detektion nicht durch stilles Überspringen erfolgreich erscheint.

Bei mehreren ausgewählten Berichten werden sämtliche Findings mit Analyzerprovenienz erhalten. Unterschiedliche Aussagen über dasselbe Subject ergeben eine sichtbare `analyzer_disagreement`-Information; sie werden nicht zusammen als bestätigte Sprache ausgegeben. Die erste Version leitet aus mehreren statistischen Scores keine gemeinsame Wahrscheinlichkeit ab. Nicht ausgeführte Capabilities stehen in der Coverage, nicht in einer leeren Liste angeblich bestandener Findings.

## T.9 Ressourcen, Fortsetzung und Determinismus

Der Analyzerauftrag ist ein vollständiger Work-Auftrag nach Anhang P, unabhängig davon, ob `--work-dir` angegeben wurde. Die automatische beziehungsweise explizite Work-Root-Wahl und Veröffentlichung folgen T.5/P.2. Die Analysekennung nach T.3 bleibt über sämtliche Schritte erhalten; die Schreib-Request-ID-Felder des Work-Auftrags bleiben `null`. Arbeitseinheiten sind `(Analyzerfingerprint, Subjectschlüssel)`. Bei weicher Budgetüberschreitung werden bereits abgeschlossene Einheiten erhalten, weitere Einheiten seriell und sparsam bearbeitet oder über Code 8 mit vollständiger Restmenge fortgesetzt. Native Libraryaufrufe dürfen bei einem weichen Ziel nicht automatisch mitten im Ergebnis abgeschnitten und als bestanden verbucht werden. Ein tatsächlicher Hostabbruch wird als fehlende Einheit behandelt, nicht als Textfehlklassifikation.

Default ist eine Workerinstanz und ein Modell gleichzeitig. Opaque native Rechenzeit und Kindprozessverbrauch werden separat beobachtet, soweit verfügbar, andernfalls `unknown`; reine Parent-CPU-Zählung darf nicht als Gesamtverbrauch gelten. Ein für einen einzelnen legalen Text benötigter native Aufruf kann nicht durch mehrere Chatprompts magisch kleiner gemacht werden. Ist er auch mit serieller Verarbeitung und freigegebenem sparsamen Versuch technisch unmöglich, bleibt der konkrete Host-/RAM-Blocker sichtbar und der übrige Auftrag fortsetzbar. Es wird weder dauerhaft ohne Fortschritt neu gestartet noch eine Stichprobe als voller Ersatz genommen.

Wiederaufnahme verwendet identischen Request und Enginefingerprint. Fehlt der exakte Adapter/Modellstand in der neuen Runtime, wird die Einheit als `unavailable` gemeldet; ein Wechsel erzeugt eine neue gebundene Analyse und mischt nicht unbemerkt Scores verschiedener Modelle. Checkpoints enthalten keine pickled Pythonobjekte, keine ausführbaren Prompts und kein serialisiertes Fremdmodell, sondern ausschließlich geprüfte JSON-Daten und Hashbindungen. Der Detector wird bei einem neuen Worker aus dem vertrauenswürdigen Offlinepaket erneut geladen.

Die globale deterministische Fachverarbeitung des Core bleibt unverändert. Live-Analyzerergebnisse haben zusätzliche explizite semantische Inputs: Modell-, Library-, Unicode-, numerischer Backend- und Vorverarbeitungsfingerprint. Bytegleichheit wird für dieselbe gebundene Engine, dieselben Eingaben und denselben Ergebnisprojektionsvertrag geprüft, nicht pauschal für beliebige NumPy-/CPU-Kombinationen. Unterschiede zwischen unterstützten Interpreterpaketen dürfen nicht versteckt werden. Das Release verlangt gesonderte Übereinstimmung von Labels und Entscheidungszuständen auf dem festen Akzeptanzkorpus; Scores werden dabei nicht ohne Nachweis als plattformübergreifend bitidentisch ausgegeben. Rendering bereits gespeicherter identischer Reports ist wieder vollständig deterministisch.

## T.10 Verbindliche Abnahme des ersten Adapters

Abnahme besteht aus getrennten Nachweisen: Protokoll-/Sicherheitstests ohne Detektor, echte Bibliotheksintegration, festes mehrsprachiges Korpus, Fehlkennzeichnungen, Unsicherheit, Core-ohne-Abhängigkeiten und Wiederaufnahme. Mocks allein erfüllen die Adapterabnahme nicht. Das Korpus wird vor dem Release versioniert, durch sprachkundige Reviewer geprüft und nach Datenherkunft/Lizenz dokumentiert. Je Hauptsprachlabel `de,en,hi,id,pt,es,ru,ja,zh` enthält es mindestens 20 eigenständig formulierte Requirement-Sachverhalte mit 80 bis 500 Codepoints; mindestens fünf zusätzliche kurze/technische Fälle je Label werden separat bewertet. Die englischen Regionalfälle und beiden chinesischen Deklarationsarten erhalten eigene Metadatentests.

Für das feste lange Korpus müssen mit der Defaultpolicy je Label mindestens 18 von 20 erwartete Grundsprachen entschieden korrekt erkannt werden; die übrigen Fälle dürfen nur als Nichtentscheidung, nicht als entschiedene andere Sprache enden. Dies ist ein **Abnahmeziel auf dem veröffentlichten Testkorpus**, keine generelle Genauigkeitszusage. Ein verfehltes Ziel verlangt Modell-/Policy-Review und neu gebundene Tests; es darf nicht nachträglich durch heimlichen Korpuswechsel bestanden werden. Kurze, mehrsprachige, Code-, Zitat-, Leer- und reine Zifferntexte werden mit ausgewiesener Fehl-/Nichtentscheidungsquote geprüft; sie müssen insbesondere ohne Absturz und ohne gefälschte Sicherheit verarbeitet werden.

Auf der bestehenden Referenzplattform wird zusätzlich ein serieller Lauf mit 1000 Strings von jeweils 100–500 Codepoints gemessen: maximal 120 CPU-Sekunden und 512 MiB gleichzeitig gemessener Gesamt-RSS von Parent und Worker nach dokumentierter Messmethode. Core-Startziele aus 14.6 schließen Modellinitialisierung weiterhin aus. Das sind Zielwerte an die spätere Implementierung; diese Spezifikationsfassung behauptet keine erfolgte Bibliotheks-, Sprachkorpus-, CPU- oder RSS-Abnahme.

---

# Anhang U — Präzisierung der SRX-Zahlenpolicy

## U.1 Explizite projektgebundene Präzision

Die in der Prüfung v0.2.5 offen gebliebene „konfigurierte Präzision“ wird durch `specroad.json.srx_policy.decimal_precision` festgelegt. Es ist eine Ganzzahl von 1 bis 1000, Default **34 signifikante Dezimalziffern**. Die vollständig materialisierte Policy gehört zur semantischen Projektkonfiguration und damit zu Plan-/Modell-/Prüfbindungen. Sie ist weder ein weiches Rechenbudget noch vom Python-Decimal-Prozessdefault oder einer Ubuntu-Locale abhängig.

Die Policy trägt `numeric_policy_version=srx-decimal-v1`. Ausgeschriebene Werte werden auf Typ und Bereich geprüft; unbekannte Policywerte sind Code 2. Änderungen erzeugen einen fachlichen Konfigurationsdiff und verlangen Neubewertung der davon abhängigen Regelresultate. Die Implementierung benutzt einen explizit aufgebauten lokalen Rechenkontext und hinterlässt keinen global veränderten Decimal-Kontext.

## U.2 Exakte Zahlen und JCS-Grenze

SRX-Zahlen werden aus ihrer kanonischen JCS-Dezimalschreibweise in eine exakte dezimale beziehungsweise rationale Zwischendarstellung überführt, nicht aus der vollständigen Binärfloat-Expansion. Die unveränderte JCS-Zahlenschnittstelle bleibt auf endlich darstellbare IEEE-754-Binary64-Werte mit kanonischem Roundtrip begrenzt; größere beziehungsweise präzisere fachliche Zahlen benötigen einen ausdrücklich stringbasierten Vertrag und werden nicht still gerundet.

`add`, `subtract`, `multiply` und `divide` berechnen mathematisch exakt. Nach Entfernung wertneutraler abschließender Koeffizientennullen darf das endliche Ergebnis höchstens `decimal_precision` signifikante Ziffern besitzen; Null hat eine signifikante Ziffer. Ein nicht endlich dezimal darstellbarer Quotient, ein zu präzises Ergebnis oder ein Ergebnis, dessen erneute JCS-Binary64-Konvertierung einen anderen Dezimalwert ergäbe, ist ein expliziter Regelfehler. `1/3` wird somit nicht zu einem gerundeten Näherungswert. Ein durch Potenzen von 10 skaliertes Ergebnis verbraucht durch die Exponentenschreibweise keine künstlich zusätzlichen signifikanten Ziffern. Die Originaldaten werden nicht umgeschrieben.

Division durch null, nichtendliche Operanden und numerische Repräsentationsfehler erzeugen `SRV197` mit Grund `division_by_zero`, `non_finite`, `precision_exceeded`, `non_terminating` oder `jcs_roundtrip_loss`. Eine gebundene Regelprüfung mit diesem Fehler schlägt nach dem bestehenden Diagnosevertrag fehl. Größere Rechenbudgets beseitigen keinen mathematischen Nichtdarstellbarkeitsfehler. Harte Parser-/Formatgrenzen und die fortsetzbare allgemeine Arbeitssteuerung bleiben getrennt.

## U.3 Normative Entscheidungsvektoren

| Ausdruck | Präzision | Soll |
|---|---:|---|
| `1 / 8` | 3 | `0.125` |
| `1 / 8` | 2 | `precision_exceeded` |
| `1 / 3` | 34 | `non_terminating` |
| `1 / 0` | 34 | `division_by_zero` |
| `0.1 + 0.2` | 34 | `0.3` |
| `1.20 + 0.30` | 2 | `1.5` |
| `999 + 1` | 1 | `1000` als exakt eine signifikante Koeffizientenziffer |
| `1 / 16` | 3 | `0.0625` |
| `9007199254740992 + 1` | 34 | `jcs_roundtrip_loss` |
| gültiger Ausdruck nach Änderung des Prozess-Decimal-Defaults | gleiche Projektpolicy | identisches fachliches Ergebnis |

Diese Präzisierung schließt einen bisher unterbestimmten Entwurfsvertrag; sie ist keine Behauptung einer unveränderten Semantik bereits veröffentlichter SRX-Implementierungen. Ein implementierter SRX-Stand mit abweichenden freigegebenen Ergebnissen benötigt nach Anhang B.6 eine neue inkompatible Sprachversion, nicht eine stille Umdeutung.

---

# Anhang V — Quellen und Entscheidungsprovenienz der Erweiterung

## V.1 Fachliche Herkunft

Grundlage der funktionalen Erweiterung v0.2.6 war die veröffentlichte SpecRoad-Spezifikation v0.2.5 mit den im Chat getroffenen Nutzerentscheidungen vom 14. September 2026: explizite Requirement-Sprache; sprachunabhängige Verbindlichkeit; mehrere erlaubte Inhaltssprachen; generische Analyzer statt eingebautem Textverständnis; bereits im ersten Zielrelease ein realer py3langid-Adapter; portable, ressourcensparsame und vollständig fortsetzbare Ausführung. Die numerische Präzisionsauflage stammt aus dem Implementierungsreife-Prüfbericht v0.2.5. Die damalige Korrekturfassung v0.2.7 übernahm den vollständigen Umfang v0.2.6 und setzte ausschließlich dessen Reviewempfehlungen B01/A02 um; Quelle sind der Implementierungsreife-Prüfbericht v0.2.6 und der anschließende Nutzerauftrag.

Detaillierte Feldnamen, Defaultschwellen, Auswahl-/Vergleichsalgorithmen, CLI-Verträge, Paketgrenzen und Korpus-/Leistungsziele dieses Dokuments sind **neue Entwurfsfestlegungen**, keine vom Vorgängerdokument oder von Herstellerbenchmarks bereits bewiesenen Eigenschaften. Für sie sind eigene Abnahmen definiert. Frühere pauschale Aussagen über „zuverlässiges Verständnis“ oder „vollständig erkannte Locale“ werden nicht übernommen.

## V.2 Externe Primärquellen, abgerufen am 14. September 2026

| Kennung | Primärquelle | Verwendung und Grenze |
|---|---|---|
| EXT-001 | PyPI, `py3langid` 0.4.0: https://pypi.org/project/py3langid/0.4.0/ | API-, Versions-, Modell- und Vorverarbeitungsbeschreibung des gewählten Detektors; keine Übernahme von Performancewerbung als SpecRoad-Nachweis. |
| EXT-002 | Upstream-Paketmetadaten: https://github.com/adbar/py3langid/blob/master/pyproject.toml | Python-/NumPy-Abhängigkeit und Paketmodell; beweglicher Entwicklungszweig, daher verlangt die Releaseabnahme zusätzlich den exakten gehashten Wheel-/Modell-/Dependency-Lock. |
| EXT-003 | RFC 5646: https://www.rfc-editor.org/rfc/rfc5646.html | Sprachkennzeichnung, Syntax und registerbezogene Validierung. |
| EXT-004 | RFC 4647: https://www.rfc-editor.org/rfc/rfc4647.html | Basic Filtering; keine automatische Gleichsetzung von Makrosprachen oder Detectorlabels. |
| EXT-005 | IANA Language Subtag Registry: https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry | Quelle für einen im Release eingefrorenen, projektgebundenen Snapshot; kein Netzwerkzugriff zur Laufzeit. |
| EXT-006 | RFC 8785: https://www.rfc-editor.org/rfc/rfc8785.html | Unveränderte Unicode-Strings und kanonische JSON-Zahlenschnittstelle. |
| EXT-007 | Python 3.10 `decimal`: https://docs.python.org/3.10/library/decimal.html | Implementierungshilfe für explizite lokale Dezimal-Kontexte; die SpecRoad-Präzision ist eine eigene Policy, nicht der Python-Default. |

---

## V.3 Quelle der Transportentscheidung v0.2.8

Der Nutzer legte PatchHarbor und ausdrücklich dessen öffentliche Python-API als
Basis fest und beauftragte anschließend diese Spezifikations-/Planänderung.
Geprüfte lokale Quelle: `patch-harbor-dev (1).zip`, SHA-256
`78467d627994a7d6175dea4a3bffcf5f840a79f0fd7914dc709393e6d9f269da`;
maßgeblich für die Schnittstellenabgrenzung sind `docs/python-api.md`,
`docs/runtime-bootstrap.md`, `docs/result-format-3.md`, `docs/pack.md` und
`src/patchharbor/api.py`. Der Quellstand ist eine Entwurfsgrundlage, kein
behaupteter Release- oder SpecRoad-Integrationsnachweis. Für die Umsetzung wird
die neue CPython-3.10-/3.11-kompatible Version verwendet; die tatsächliche
Runtime-/API- und Artefaktbindung erfolgt im Implementierungsschritt.

---

# Anhang W — Portabler SpecRoad-/PatchHarbor-Rundweg

## W.1 Verantwortungsgrenzen und öffentliche API

SpecRoad bestimmt Projektclosure, fachliche Validierung, Proposals, menschliche
Reviews und transaktionale Änderungen. PatchHarbor bestimmt seine Result- und
Patchformate, Zustandsbindung und lokale Paketübernahme. Die Integration verwendet
`from patchharbor import api`; CLI-Subprozesse und private PatchHarbor-Module sind
kein Ersatz. Die separat verteilte, mit CPython 3.10 bis 3.14 kompatible Runtime
wird versions- und hashgebunden ausgeliefert. Normaler Core-Start lädt sie nicht.

Die Zuständigkeiten der öffentlichen Aufrufe sind fest:

| Aufgabe | API und Grenze |
|---|---|
| Lokalen Referenzstand erfassen | `api.bundle(repository=..., output_directory=...)`; bereits registriertes Git-Repository mit vorhandenem HEAD, explizite absolute Pfade und Ausgabe außerhalb des Projekts. Keine implizite Registrierung oder Remoteaktion. |
| Rückpaket erzeugen | `api.pack_patch(..., reference_bundle=..., entrypoint=...)`; SpecRoad bereitet den vollständigen Payload und den festen Entrypoint vor. PatchHarbor wählt keine Änderungen aus und erzeugt keinen Proposal. |
| Rückpaket prüfen | `api.inspect_patch` und `api.validate_patch` mit ursprünglichem Result; lokale Zielbindung wird zusätzlich gegen das registrierte Ziel geprüft. Ein gültiges Paket ist keine Freigabe seiner Fachänderungen. |
| Lokal übernehmen | Ausschließlich der bewusst aufgerufene lokale Integrationsadapter verwendet `api.apply` mit explizitem geprüftem Paket und Repository. Keine automatische Auswahl fremder Pakete, Watcher oder rekursiven Apply-/Bundle-Aufrufe. |
| Result prüfen und Snapshot liefern | Erforderlicher **öffentlicher** API-Vertrag für vollständige Resultprüfung und schreibfreie Ausgabe des exakten effektiven Snapshotinventars. Diese Fähigkeit ist in der geprüften API noch nicht öffentlich vorhanden; ihr Name wird erst durch PatchHarbor festgelegt. |

Die letzte Zeile ist eine ausdrückliche Integrationsvoraussetzung. Sie umfasst
Manifest, Kontext, Runtime, Base, staged/unstaged Änderungen und untracked Daten
einschließlich Pfad-/Typ-/Hashprüfung. Eine Versionsangabe allein oder ein
erfolgreicher Runtime-Bootstrap beweist diese Vollprüfung nicht. Vor Freigabe des
Hinexports muss die Fähigkeit in PatchHarbor öffentlich dokumentiert, ausgeliefert
und mit SpecRoad nachgewiesen sein. SpecRoad baut keinen privaten Resultreader,
Patchinterpreter oder eigenen PatchHarbor-Formatvalidator als Umgehung.

## W.2 Paketformat und Runtimeprofile

Das Hinpaket ist ein eigenes äußeres ZIP mit Formatkennung
`specroad-ai-handoff-v1`. Es ist weder ein PatchHarbor-Result noch ein
SpecRoad-Projektbundle. Es enthält genau:

- `handoff.json`, das Manifest des äußeren Pakets;
- `runtime/specroad.pyz`, eine vertrauenswürdig ausgelieferte SpecRoad-Zipapp;
- `reference/result.zip`, die unveränderten Bytes des maßgeblichen Results;
- `project/project.zip`, ein kanonisches `kind=project`, `scope=project`,
  `closure_mode=closed`, schreibbares Vollprojektbundle nach Anhang E;
- nur bei explizit gewähltem, unterstütztem Profil `python-bundled` zusätzlich
  `runtime/python-runtime.zip`, eine vollständig gebundene CPython-Distribution.

Die PatchHarbor-PYZ bleibt innerhalb ihres ursprünglichen Result-Runtimeeintrags.
Fremde SpecRoad-Dateien werden nicht in den geschlossenen PatchHarbor-Result-
Memberraum eingefügt. Gewöhnliche Projekt-/Teilbundles nach Anhang E behalten ihre
eigene Bedeutung und enthalten durch diese Erweiterung keine ausführbare Runtime.
Die Moduldistribution kann dasselbe Hinpaket bedienen wie `specroad.pyz`.

`handoff.json` bindet mindestens Formatversion, Paket-ID, `project_id`, relativen
Projektpfad im Result, Scope Descriptor, Modellwurzel, die vollständige Result-
SHA-256 sowie unveränderte `repo_id`, `base_commit`, `state_fingerprint` und
`fingerprint_algorithm`. Für alle äußeren Payloads stehen Pfad, Größe und SHA-256
in einer exakten, sortierten Inventarliste; das Manifest nimmt sich nicht selbst
auf. Runtimeeinträge binden Toolversion, Artefakthash, unterstützte CPython-
Versionen, Plattformprofil und gegebenenfalls den inneren Result-Memberpfad.
Der vollständige äußere ZIP-Hash wird außerhalb des ZIP ausgegeben.

Die zugehörigen Optionen sind `--runtime-profile python-present|python-bundled`
(Default `python-present`) beim Hinexport und `--expected-sha256 <HEX>` für
Prüfung und Öffnen. Ohne extern übergebenen Hash darf reine Datenprüfung einen
Integritätsbefund liefern, aber keine vertrauenswürdige Herkunft behaupten oder
mitgelieferte Runtime laden; dafür ist eine bereits fest gebundene
vertrauenswürdige Distributionsidentität oder der externe Erwartungshash nötig.

Für die äußeren ZIP-Bytes gelten die sicheren kanonischen Containerregeln aus
E.2; das äußere Manifest ersetzt dort nur den Namen `bundle-manifest.json`.
Der Inhalt eingebetteter Archive bleibt byteidentisch und hat seinen eigenen
Formatvertrag. Jedes Archiv wird vor seiner jeweiligen Extraktion vollständig
geprüft; ein korrekter äußerer Hash überspringt keine innere Prüfung. Absolute
Pfade, Traversal, Namenskollisionen, Links, Sonderdateien und nicht inventarisierte
Member sind unzulässig. Runtime-/Transportdaten gehen nicht in die Modellwurzel
ein; notwendige Projektressourcen bleiben Teil der Closure.

Das verpflichtende Profil `python-present` benötigt einen vorhandenen kompatiblen
CPython-Interpreter. Eine PYZ ist kein Python-Interpreter und keine universelle
Binärdistribution. Das zusätzliche Profil `python-bundled` darf nur angeboten
werden, wenn ein vollständiger Interpreter samt Standardbibliothek, notwendigen
nativen Bibliotheken, Lizenzen und sicherem Extraktions-/Startvertrag für genau
das deklarierte OS-/Architektur-/ABI-Profil geliefert und geprüft wird. Eine
einzelne kopierte Python-Binärdatei genügt nicht. Nicht verfügbare Profile werden
vor Veröffentlichung abgewiesen; automatisches Herunterladen oder Installieren
ist ausgeschlossen. Analyzer-/NumPy-Pakete werden dadurch nicht vorausgesetzt
oder stillschweigend mitgeliefert.

## W.3 Einheitlicher Ausgangsstand

Der Hinexport erfasst das Result über W.1 und erzeugt das Projektbundle aus
**dessen geprüftem effektivem Snapshot**, nicht durch einen zweiten ungebundenen
Scan des veränderlichen Working Tree. Die Zuordnung umfasst genau einen
Projektroot und dessen vollständige normative und portable betriebliche Closure
einschließlich erforderlicher Receipts und Objektbytes nach Anhang E.
Gitignorierte Pflichtdaten fehlen gegebenenfalls im Result; der Export darf sie
nicht nachträglich aus einem anderen Stand ergänzen oder als optional ausgeben.
Er meldet die fehlende Abdeckung und erzeugt kein erfolgreiches Hinpaket.

Ein Result mit staged/unstaged/untracked Inhalten ist nur zulässig, wenn die
öffentliche Snapshot-API alle diese Schichten vollständig und deterministisch
rekonstruiert. Git-Metadaten, Hooks und Laufzeitcaches werden nicht zum
Projektinhalt. Offene Transaktionen, unklare Snapshotzustände, falsche Projekt-ID,
abweichende Dateihashes oder fehlende geschützte Geschichte verhindern den
Abschluss. Die API-Runtime muss zum deklarierten Versions-/Fähigkeitsvertrag passen.
Die Bestandteile bleiben während der Prüfung an stabile Bytes gebunden.

## W.4 Öffnen in der internen Python-Laufzeitumgebung

Der Nutzer startet die aus einer vertrauenswürdigen Verteilung bezogene
SpecRoad-PYZ mit dem vorhandenen Python. Ein erwarteter Paket-/Runtimehash muss
aus einer bereits vertrauenswürdigen Quelle stammen; Selbsthashes innerhalb
eines beliebig austauschbaren ZIP sind kein Herkunftsbeweis. Prüfung von Manifest,
Runtimehashes, Plattform und Pythonversion geht jedem Laden mitgelieferten Codes
voraus. Der dokumentierte verifizierte PatchHarbor-PYZ-Bootstrap darf die öffentliche
API bereitstellen; Projektpfade dürfen dabei keine Module unterschieben.

`bundle verify --profile ai-runtime` verändert keine Projekt- oder Runtimepfade.
`bundle extract --profile ai-runtime` prüft zuerst das vollständige Hinpaket,
Result und Projektbundle und veröffentlicht anschließend ausschließlich einen
neuen Zielroot mit getrennten `runtime/`, `reference/` und `project/`-Bereichen.
Die Referenz wird byteidentisch aufbewahrt und bei jedem Rückexport neu geprüft;
ein kopierter Marker genügt nicht. Das Modell im Projektbereich muss dieselbe
ID, Wurzel, Ressourceninventur und Receiptwirkung wie die Ausgangsprojektion
haben. Rechte entstehen nicht durch Entpacken: partielle Bundles werden weder
hier noch durch Entfernen einer Kennzeichnung zu schreibbaren Vollprojekten.

Diese Sandboxseite benutzt ausschließlich Python und gelieferte Dateien; weder
Git noch Shell, Netzwerk, Paketmanager oder administrativer Zugriff ist nötig.
Die KI bedient das Projekt über die vorhandene SpecRoad-CLI, erzeugt und prüft
Proposals und erhält keine menschliche Freigabekompetenz. Ein neuer Prozess oder
Sandboxpfad benötigt keinen alten Chat-/Prozesszustand. Work-Fortsetzung bleibt
ein gesonderter, nach Anhang P geprüfter Vertrag.

## W.5 Rückexport, Transportübernahme und fachliche Freigabe

`bundle create --profile ai-runtime --direction return` verlangt das ursprüngliche
Hinpaket und einen explizit ausgewählten Proposal. Der Befehl prüft Referenz,
Projekt-ID und Proposalbasis erneut. Das Ergebnis ist genau eine native
PatchHarbor-Patch-ZIP, kein neues Result und keine erneute äußere Runtime-ZIP.
Alle PatchHarbor-Bindungswerte stammen unverändert aus dem Referenzresult. Das
Hinpaket darf nicht anhand späterer KI-Änderungen neu gebunden werden.

SpecRoad erzeugt vor `pack_patch` ein vollständiges passives Rückgabeinventar:
Proposalinhalt, geordnete Operationen, referenzierte neue Daten und deren Hashes,
Basis-/Zielbindungen sowie ausdrücklich ausgewiesene Löschungen und Umbenennungen.
Keine automatische Dateiauswahl durch PatchHarbor, keine beliebige Working-Tree-
Kopie und keine losgelösten Fachänderungen außerhalb des Proposals. Immutable
historische Nachweise werden nicht neu geschrieben. Nicht benötigte Caches,
Runtimebinärdateien, Gitdaten und Sandboxgeheimnisse gehören nicht in den Rückweg.
Der Entrypoint stammt aus einer gebundenen SpecRoad-Verteilung; der KI-Payload
darf weder seinen Code noch lokale Test-/Commit-/Pushbefehle vorgeben.

**Payload wird von PatchHarbor vor dem Entrypoint ausgebracht.** Daher liegen
Rückdaten ausschließlich in einem frischen, eindeutig zum Paket gehörenden
Stagingpfad außerhalb normativer Projektressourcen. Ein Verzeichnis namens
`payload/` ist kein Schutzmechanismus. Der lokale Integrationsadapter prüft vor
`api.apply` das vollständige Pfadinventar, fehlende Zielkollisionen und Links,
Referenz-/Zielbindung sowie den exakten zugelassenen Entrypoint. Ohne diese
Prüfung darf das Paket nicht an einen allgemeinen Auto-Apply-Workflow übergeben
werden. Prüfung und Apply müssen dieselben unveränderbaren Paketbytes und die
gesperrte Zielbasis verwenden; fehlt eine öffentliche Möglichkeit zur sicheren
Bindung dieser Grenze, bleibt die automatische Hostintegration gesperrt.

Die ausdrücklich autorisierte Hostübernahme nimmt zunächst nur den Proposal
über die kontrollierten SpecRoad-Authoringoperationen als lokalen Entwurf auf.
Sie veröffentlicht seine fachlichen Zieländerungen nicht. Kollidierende IDs
oder unpassende Basisdaten werden nicht überschrieben. Fremde Reviewbehauptungen
werden nicht als lokale menschliche Zustimmung übernommen. Der anschließend
sichtbare Zustand heißt `proposal_received`; `applied` wird erst nach lokalem
`proposal validate`, `proposal check`, gültigem menschlichem `proposal review`
und erfolgreichem transaktionalem `proposal apply` ausgegeben. Diese Trennung
verhindert, dass vorab eingebrachte normative Dateien das Review umgehen.

Die Aufnahme des Proposal-Artefakts ist selbst ein kontrollierter normativer
Write; für seine nichtrekursive fachliche Basis gilt 10.8.1. Deshalb kann der
normale lokale Proposal-Lifecycle nach dem Empfang fortgesetzt werden. Die
Transportreferenz bleibt dennoch die historische Eingangsbindung und wird nicht
für einen zweiten Transport-Apply umgeschrieben. Der Proposal-Kern führt keine
Git-Commits, Branches oder Pushes aus. Externe Git-/Entwicklungsautomatisierung
bleibt getrennt und erhält durch ein Paket keine zusätzliche Autorisierung.

## W.6 Fehler, Wiederholung und Aussagen über Erfolg

Falsche `repo_id`, Projekt-ID, Modellwurzel, Result-SHA oder geänderte Zielbasis
verhindern eine schreibende Übernahme. Es gibt kein stilles Rebase und kein
Ersetzen der Referenz. Benutzer können einen neuen aktuellen Hinexport erstellen
und Änderungen über die vorhandenen Merge-/Proposalverträge erneut bewerten.
Ein unverändert wiederholtes, nachweislich empfangenes Paket führt weder zu einem
zweiten Proposal noch zu einer zweiten Fachänderung; bei unklarem Replayzustand
wird blockiert statt Erfolg erfunden. PatchHarbor-Replayprüfung und SpecRoad-
Request-Receipts bleiben getrennte, gemeinsam zu prüfende Nachweise.

Abbruch vor Veröffentlichung eines Exports hinterlässt keine als fertig
ausgewiesene ZIP. Bei Abbruch während Übernahme oder Proposal-Apply bleiben
der tatsächliche Zustand und notwendige Diagnose-/Recoverydaten erhalten;
bereits erfolgreiche Arbeit wird nicht blind zurückgesetzt. Bereinigung darf
nur nachweislich eigene temporäre Pfade betreffen. Eine fehlgeschlagene Result-
Veröffentlichung nach erfolgreicher Fachänderung wird als genau dieser
Teilzustand berichtet und darf keinen ungeprüften zweiten Apply auslösen.

Maschinenlesbare Resultate unterscheiden Paketprüfung, Transportempfang,
Proposalprüfung, menschliche Freigabe, Fachanwendung und Result-Veröffentlichung.
Sie binden jeweils die tatsächlich verwendeten Paket-, Projekt-, Runtime- und
Zustandswerte. SpecRoad-Exitcodes folgen 11.8: inkompatible API/Optionen 2,
ungültige Daten 3, I/O/Host/Recovery 5, stale-/Replay-/Zielkonflikt 6 und
Sicherheitsverweigerung 7. PatchHarbor-Statuswerte werden zusätzlich erhalten,
nicht numerisch als SpecRoad-Exitcode umgedeutet. Ein Erfolg eines Teilgates
beweist keines der übrigen Gates.

Die tatsächlichen harten Format-/Größenlimits der gebundenen PatchHarbor-Version
bleiben wirksam. Eine Überschreitung darf weder zum Weglassen von Pflichtdaten
noch zum ungeprüften Zerlegen eines logisch gebundenen Pakets führen. Weiche
SpecRoad-Arbeitsbudgets und sichere Fortsetzung ändern diese Formatgrenzen nicht.

## W.7 Verbindliche Verhaltensabnahme

SR-VER-0051 und SR-E2E-0013 prüfen reale ausgelieferte SpecRoad- und
PatchHarbor-Artefakte, keine nachgebaute Transportimplementierung:

1. Registriertes lokales Repository → Hinexport → frische netzwerkisolierte
   Linux-x86-64-Sandbox → Proposal erstellen/ändern/prüfen → Rückexport →
   Paketprüfung und bewusst autorisierter Empfang → menschliches Reviewfixture
   → transaktionales Apply mit unabhängig erwartetem Zielhash.
2. Derselbe Ablauf mit Modul- und PYZ-Core unter CPython 3.10, 3.11, 3.12, 3.13
   und 3.14; in der Sandbox keine installierten Drittanbieterpakete, kein Git,
   keine Shell, kein Netzwerk. Lokale Git-/Entrypointvoraussetzungen werden
   ausschließlich auf der Hostseite gemessen und ausgewiesen.
3. Snapshotfälle clean sowie staged/unstaged/untracked, fehlende ignorierte
   Pflichtdatei, offene Transaktion, partielle Quelle und veränderte Eingabe;
   keine erfolgreiche Auslassung oder Vermischung von Ständen.
4. Manipulierte äußere/innere Bytes, Manifest, Runtime, Referenz und Entrypoint,
   fremde API-Version, Importpfadunterschiebung, Traversal, Links und belegte
   Ziel-/Stagingpfade; keine Codeausführung oder Writes vor den erlaubten Gates.
5. Unvollständige oder zusätzliche Rückdaten, Löschung/Umbenennung, stale Basis,
   wiederholter Empfang, ID-Konflikt, fehlende/fingierte/geänderte Freigabe und
   harte Abbrüche einschließlich gescheiterter Result-Veröffentlichung nach Apply.
6. Ein unverändertes Projekt kann ohne Fachdelta zurückgegeben werden; die
   strukturierte Meldung `no_changes` erzeugt keinen leeren Änderungs-Apply.
   Normale Projekt-/Teilbundles, Core ohne Transportnutzung und bestehende
   Idempotenz-/Recoveryverträge bleiben durch echte Regression nachgewiesen.
7. Jedes zusätzlich angebotene `python-bundled`-Profil wird auf der exakt
   deklarierten Plattform ohne vorhandenes Python geprüft; fehlende Profile
   bleiben als nicht verfügbar erkennbar und werden nicht als bestanden gezählt.

Alle Kriterien sind Sollabnahmen. Die Dokumentation dieser Erweiterung ist
kein ausgeführter Rundweg. Die externe öffentliche API-Erweiterung aus W.1
und gegebenenfalls die sichere Hostgrenze aus W.5 müssen vor den davon abhängigen
Implementierungsschritten nachgewiesen sein.

---

**Ende der SpecRoad-Produktspezifikation v0.2.34.**
