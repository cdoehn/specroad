# OFF-PLAN – Explizite Restore-Aufrufbindung (Bundle 504)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Explizite Restore-Aufrufbindung (Bundle 504)

Revision 28 konkretisiert **RESTORE-CLI-BINDING** in Spezifikation
**0.2.33 / 10.7.6**. Autorität: **delegiert gemäß SPECROAD-DECISION-1**.
Produktstand **649/900**, zuletzt **15.l.W**, nächstens **15.l.R**; keine
Produktposition oder menschliche Einzelfreigabe wird daraus abgeleitet.

- [x] **RESTORE-CLI-BINDING:** Restoremodi und explizite CLI-Eingabebindungen
  präzisieren. Commit: `docs(spec): Explizite Restore-Aufrufbindung präzisieren`.

**Maßgebliche Basis.** Vollständig geprüftes, eindeutig aktuelles Result
`specroad-apply_Result_005804_1027_1c9246.zip`, SHA-256
`8dfee6d5e9741cafd09b4993ca08e38694b00a8db18a3a5146a8a71f9698b775`.
Repository `a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Commit
`618d89bd55cf45f5195683904d8bb5ffd190ee23`, Fingerprint
`7c9d2a24e397e0e5`, Algorithmus `patchharbor-state-v1`.
Root-Anleitung, Kontext, Umgebung, Manifest, Run-/Ausführungslogs sowie alle
**2.307** Snapshotdateien einschließlich Blob-IDs und Modi wurden geprüft.
Der tatsächliche Apply-Stand ist sauber und stimmt mit dem Snapshot überein.
Der zugehörige technische Korrekturabschluss **15.l.R-FIX1**, Bundle **503**,
Paket-SHA-256 `e88f9c855c4ee5fd1d560d3432c3dff512fa878faaad459c1bc7739c7e620760`,
ist durch passenden Abschlusscommit, Payloadvergleich, **7.269/7.269**
bestandene Apply-Tests, **Sequenz 209 / Gruppe 2**, vier parallele Worker
und **2680.44 s** belegt. Auswahlbindung und Einzeloutcomes wurden geprüft.

§2.4 erlaubt Vertrag 3 ausdrücklich. Der aktuelle Auftrag enthält gültig
`version=3`, `clarification_limit=3`, `clarifications_remaining=3`,
`clarification_allowed=true`. Das vorliegende Bundle wird ausschließlich
als `spec_clarification` übergeben; Control verbucht seinen Platz bei Übernahme
des Folge-Results. Die technische Korrektur 503 wurde als `patch_ready`
übergeben und sauber abgeschlossen. Dieser Dokumentstand erneuert kein
Budget und ändert keine alten Aufträge, Blockaden oder Laufzeitdaten.

**Lücke und geprüfte Grundlagen.** 10.7.1 nennt zwei schematische Aufrufe,
10.7.2 verlangt explizite Quellart, Herkunftsroot und relative Datei sowie
operative Baselinewerte. Ihre eindeutige CLI-Zuordnung ist noch nicht
festgelegt. Der gemeinsame CLI-Vertrag lässt die für Restore benötigten
Dry-Run-/Actoroptionen derzeit nur für `normative_write` zu; seine allgemeine
Projektauswahl liest Konfiguration, bevor der Restore beschädigte Bytes
unabhängig qualifizieren kann. Ein gewöhnlicher Projektpreflight würde
außerdem einen eigenen Wiederanlauf vor dessen spezialisierter Prüfung
abweisen. Diese technischen Ist-Grenzen dürfen die zugesagte Recovery nicht
als dauerhafte Scopeausnahme ersetzen.

Geprüft wurden 1.2, 2.1/2.4, 10.7.1–10.7.5, 11.7 und N/O/P,
SR-REQ-0258/0461/0462/0511/0550, R-44/R-47 sowie die offenen Abnahmen von
15.l.R. Technisch wurden `recovery/planning.py`, `_sources.py`, `_inventory.py`,
`files.py`, `execution.py`, `changes/recovery_values.py` und die CLI-Verträge
in `contracts.py`, `options.py`, `project_selection.py`, `application.py`
und `registry.py` abgeglichen. Die vorhandenen nativen Adapter benötigen
bereits getrennte Root-/Dateiargumente; externe Planpublikation und passive
Originaldateilektüre sind getrennt von aktueller Recoveryautorisierung.

**Alternativen und Auswahl.**

1. Art und Objektroot aus Endung, Dateiparent oder beschädigter Konfiguration
   erraten: mehrdeutig, insbesondere für rekursive Baselineobjekte; würde
   die expliziten Herkunfts- und operativen Bindungen umgehen.
2. Ein weiteres Requestdateiformat oder ein neues CLI-spezifisches
   Planformat einführen: zusätzliche Parser-/Hashdomäne ohne Bedarf;
   bestehender Plan und Auswahl erfüllen den fachlichen Datentransport.
3. Restore als gewöhnlichen normativen Writer registrieren oder globale
   Preflight-/Optionsgrenzen lockern: falsche Klassifikation und Gefahr
   unbeabsichtigter Recoverybefugnisse für andere Befehle.
4. **Gewählt:** zwei streng getrennte Modi mit expliziten Root-/Dateipaaren,
   Quellart und nur bei Baselines operativen Werten; befehlsspezifischer
   Recoverypreflight und gemeinsame native Adapter. Autorisierung bleibt
   ein gesondertes aktuelles Gate, nicht ein neues Aufrufflag.

**Abgleich mit 2.4.1.** (1) Die Änderung liegt innerhalb der bereits offenen
CLI-/Restoreintegration von 15.l.R. (2) Sie konkretisiert die gleichzeitige
Erfüllung der Quellen-, Root-, Recovery- und CLI-Verträge; kein Requirement
wird ausgewählt oder abgeschwächt. (3) Die schematischen Aufrufe erhalten
explizite Bindungsoptionen, ihre beiden fachlichen Modi und bestehenden
Plan-/Auswahlbytes bleiben erhalten. Es existiert noch kein veröffentlichter
`recover.restore`-CLI-Handler, dessen Aufrufe umgedeutet würden. Andere
Befehle, menschliche Freigaben und Sicherheitsgrenzen bleiben unverändert.
(4) Die eigene versionierte Detailregel kann später explizit fortgeschrieben
werden; keine Bestandsdatei oder historische Evidence wird migriert oder
gelöscht. (5) Die Zuordnung der bereits notwendigen Eingaben benötigt keine
externen Geheimnisse oder erfundene Berechtigungen. Die echte Hostautorität
und erforderliche Risikoentscheidungen sind damit ausdrücklich nicht erteilt.
Der verwendbare Autorisierungsadapter bleibt eine offene Implementierungs-
und Nachweispflicht; ein dauerhaft unbenutzbarer CLI-Befehl genügt nicht.

**Normative Zielregel und offene Verhaltensabnahmen.** 10.7.6 gehört zur
bestehenden R-Abnahme, zusätzlich zu allen vorherigen W-/R-/C-Kriterien:

- Explizite Bundle- und Baselineaufrufe erstellen denselben vollständig
  qualifizierten Plan wie die nativen APIs. Geändertes Arbeitsverzeichnis
  und neuer Prozess ändern bei identischen absoluten Roots kein Ergebnis.
  Baselineobjekte werden genau unter dem angegebenen Quellroot gelesen;
  operative Pflichtwerte sind in Zielbytes gebunden, Bundlebytes unverändert.
- Fehlende, doppelte oder gemischte Optionen, falsche Quellart, unzulässige
  Baselineoverrides und halbe Auswahlpaare werden mit der vorgesehenen
  Fehlerklasse vor Projektwrite abgewiesen. Pfad-/Rootabweichungen, Links,
  Aliase, fremde Roots und ein bestehendes Planziel erhalten getrennte Befunde.
- Die Planung funktioniert bei beschädigter oder fehlender Konfiguration
  nur mit unabhängig nachgewiesener Identität und Bestandsabdeckung. Weder
  Erfolg noch Ablehnung verändern Projekt, Journale, Owner oder `.specroad/`.
  Normalen Readern/anderen Dry-Runs wird kein Recoverydurchgang eingeräumt.
- Ausführung verlangt denselben expliziten Projektroot und separat bestätigten
  Zielroot, unveränderte Originalplandatei und gegebenenfalls exakte Auswahl.
  Quelle/Bestand werden vor Neupublikation frisch geprüft; nach tatsächlicher
  Unterbrechung erreichen Vollzielabschluss und Teilziel-Rollback ihre
  jeweiligen nativen Gates auch bei inzwischen fehlender externer Herkunft.
- CLI und strukturierter Aufruf haben gleiche Ergebnisse/Fehler/Seiteneffekte.
  Fehlende oder ablehnende aktuelle Autorität, Actorlabels allein und alte
  gespeicherte Zustimmung ermöglichen keinen Write. AI/CI ohne Request-ID,
  lebender Owner und unbelegte Übernahme bleiben abgewiesen; der positive
  autorisierte Weg und die getrennte Auditidentität sind nachzuweisen.
- Selbstbeschreibung nennt beide Modi und deren Bindungen. Einzellauf und
  Workfortsetzung erhalten identische Fachparameter, explizite Ausgabeziele
  und erneute Berechtigungs-/Frischegates. Alle noch offenen historischen
  Provider, vollständige I/O-/Crashmatrix und Workparität bleiben verpflichtend.

**Umsetzung und Übergabe.** Ausschließlich Spezifikation, Plan und notwendige
aktive Spezifikationshashbindungen ändern sich. Produktcode, Tests, Fixtures,
Runner, Workflow, Testnummern und historische Nachweise bleiben bytegleich.
Keine Dokumentationstests, kein zusätzlicher Volltest, keine künstliche
W/R/C-Folge. SR-TC-0461/0462 bleiben `partial`, 15.l.R/C offen.
Der Entrypoint führt vor genau einem OFF-PLAN-Dokumentcommit ausschließlich
**Sequenz 210 / Gruppe 0 von 3** mit vier parallelen Workern aus. Erst nach
erfolgreichem Gate werden der Klärungsmarker und Bundle-Nummer **504** gesetzt;
Produktzähler und reguläre W/R/C-Checkboxen bleiben erhalten. Apply und Commit
sind bei Übergabe ausstehend. Einmalige atomare Veröffentlichung, danach Ende;
keine Dienste, eigene Apply-, Warte- oder Modellschleife.

**Beobachtete gezielte Dev-Prüfung.** Die Dokument- und Katalogfassung
besteht **54/54** bestehende Verhaltenstests aus `tests/test_catalog_check.py`
und `tests/test_catalog_check_right.py` in **6.54 s**, mit **vier
parallelen Workern**, CPython **3.14.4**, Exit **0** und ausschließlich
`passed`-Einzeloutcomes. Ausgeführt wurde `tools/run_selected_tests.py
--workers 4 --expected-tests 54` mit den beiden genannten vollständigen
Dateien in einem frischen ignorierten Berichtsroot. Geprüft werden die von
der Spezifikationshashbindung betroffenen maschinenlesbaren Katalog- und
Auswahlverträge; keine Dokumentation, Darstellung oder externe Control-Ausführung.

Die vollständige Collection-/Katalogprüfung bestätigt **21.803** aktive
Tests, **0** Katalogfehler, Exit **0** und **0** ausgeführte Testkörper.
Die **21.807** dauerhaft reservierten Nummern einschließlich vier historisch
entfernter Identitäten bleiben bytegleich. Produktcode, Testdateien,
Fixtures, Oracles, Runner, Workflows und historische Evidence ändern sich
nicht. Die **743** aktiven Katalogdateien ändern ausschließlich
`specification_sha256`; einschließlich Spezifikation und Plan sind es
**745** geänderte Bestandsdateien, keine neuen Produktdateien oder Löschungen.

Gebundener Entwicklungsquellhash:
`2179dcac50da85c4b4001d55caac7bc583e6654cb1fec5e9b1c25d3a03718709`;
Katalogvertrag-SHA-256:
`81c2c7c06390d1cea509e003dd546a24cce0b23ddfa862fedd7ff7dcc5131b22`;
Auswahlbericht-SHA-256:
`e7b2fa2fe9527e7a49656a6c54ab0ede86072f303a2f560f89ae05cb58df09ca`;
Einzeloutcomes-SHA-256:
`41450a8fedb19e2d6cdeeed72080a0b62b348f3d15304e717dd2f4e4dc8c9f63`.
Dies ist ausdrücklich eine Teilprüfung mit `full_suite_passed=null`;
kein vollständiger oder serieller Testlauf und kein Releasebeleg.

Der bestätigte vorherige Apply-Nachweis für die echte technische
Korrektur 15.l.R-FIX1 (Bundle 503) ist davon getrennt:
Auswahlbindungs-SHA-256 `4e73f788b6e258ee6d827901de918bf8e630113621200703408a48bcc8492daa`,
Bericht-SHA-256 `91c08d0f02f6aef02017b0ff994459ff35632e172bedbb4b5733897e23201d1a` und
Einzeloutcomes-SHA-256 `7cc7d84195e620654a15d40d985d5d8667d3d2767ea787062bb2b1914e57e553`.
Die vorgesehene neue Apply-Gruppe und der OFF-PLAN-Commit sind bei dieser
Übergabe noch nicht ausgeführt. Native ZIP-Prüfung und atomare Veröffentlichung
beenden den Einzelauftrag; 15.l.R bleibt offen.
