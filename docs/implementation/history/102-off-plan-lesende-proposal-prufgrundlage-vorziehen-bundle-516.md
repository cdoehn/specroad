# OFF-PLAN – Lesende Proposal-Prüfgrundlage vorziehen (Bundle 516)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Lesende Proposal-Prüfgrundlage vorziehen (Bundle 516)

**RESTORE-PROPOSAL-PREREQUISITE**, ausdrückliche Nutzerentscheidung vom
29. Oktober 2026. Auf die konkrete Frage, ob die benötigte Prüfgrundlage
aus M18 für 15.l.R vorgezogen und die Planabhängigkeit korrigiert werden
soll, wurde „Benötigte Prüfgrundlage vorziehen (Empfohlen)“ gewählt.
Diese Befugnis stammt unmittelbar vom Nutzer; §2.4.1 allein hätte die
Vorziehung nicht erlaubt. Pflichtabnahmen und menschliche Freigaben bleiben
erhalten. Der manuelle Auftrag erweitert kein Control-Restbudget und
verändert weder Control, Watcher noch externe Konfiguration/Laufzeitdaten.

- [x] **RESTORE-PROPOSAL-PREREQUISITE:** Lesende native Proposal-Prüfgrundlage als Voraussetzung des vollständigen 15.l.R-Abschlusses festlegen und aktive Katalogbindungen anpassen. Commit: `docs(spec): Lesende Proposal-Prüfgrundlage für Restore vorziehen`.

**Geprüfte Basis und konkrete Lücke.** Maßgeblich ist das erfolgreich und
sauber angewendete Bundle 515: `specroad-apply_Result_092336_1029_66d7e4.zip`,
SHA-256 `b147c8fb79646dd290269358ccc74ed2ac7099de596b3263dcc2c70e69732929`,
Abschlusscommit `494ca4ee5f39d5e3770aed502bd9bd6b010f7c7c`, Repository-ID
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint `7c9d2a24e397e0e5`,
Algorithmus `patchharbor-state-v1`. Die generierte Root-Anleitung,
Metadaten, Run-/Ausführungslogs, der vollständige Snapshot und die tatsächliche
technische Basis wurden geprüft. Sein Dokumentcommit bestand 5.950 Tests
parallel, Sequenz 223 / Gruppe 1. Das ist ein Apply-Teiltestnachweis für
515, kein Erfolg der noch unfertigen R-Umsetzung.

10.7.1 verlangt erhaltene abgeschlossene Proposals und vollständige
Lifecycle-/Fachprüfung; 10.7.9 verlangt tatsächlich native Belege und
Prüfdienste. Der Basisstand besitzt für Proposal in `record_contracts.py`
nur `record_fields_only`; `record_schemas.py` prüft lokal zusätzlich
`content_revision <= revision`. `plan_contract.py` bindet deklarierte
Kontrollresultate, prüft aber keine wirkliche Reviewherkunft oder vollständige
historische Freigabewirkung. Die benötigten lesenden Vertragsanteile aus
10.3/10.4/10.8.1/11.10 sind bislang erst mit M18 geplant, insbesondere
18.b/18.d/18.f und den Historien-/Reviewanteilen von 18.h/18.i/18.j/18.k.
Das ist die konkrete Abhängigkeit; nicht jede öffentliche M18-Funktion
ist damit Voraussetzung von Restore.

**Alternativen und gewählte Lösung.** Ein Status-/Hashlabel als Freigabe
oder ein dauerhafter Ausschluss aller abgeschlossenen Proposals würde die
R-Abnahmen abschwächen. Den gesamten öffentlichen Proposalworkflow vor
M15 umzusetzen wäre größer als die benötigte Voraussetzung. Gewählt ist
der kleinste gemeinsame lesende Kern gemäß **Spezifikation 0.2.38 / 10.7.10**:
volle Original-, Inhalts-, Basis-, Plan-, Kontroll- und Reviewprüfung für
Restore; spätere Wiederverwendung in M18. Die bestehende Entwicklung wird
erhalten. Keine öffentliche Proposal-Schreiboperation wird vorgezogen.

**Abgleich mit den Entscheidungsgrenzen.** (1) Die Ausnahme vom Verbot der
Vorziehung beruht ausschließlich auf der ausdrücklichen Nutzerentscheidung
für diese Prüfgrundlage. Alle übrigen Grenzen bleiben wirksam. (2) Vorhandene
fachliche Verträge werden gemeinsam umgesetzt; kein Requirement wird
gestrichen. (3) Scope, menschliche Entscheidungen, Quorum, Originalbytes,
Unveränderbarkeit, aktuelle Autorisierung, Crashschutz und Kompatibilität
bleiben vollständig. (4) Die Vorziehung ist versioniert und ohne Migration
historischer Formate rücknehmbar; Bestandsbelege werden nicht umgeschrieben.
(5) Die Definition nativer Eingänge erfindet keine tatsächlichen Reviews,
externen Fakten oder Risikoakzeptanzen. Fehlende zwingende Belege bleiben
konkrete Datenblocker. §§2.4.2/2.4.4, §2.5 und BD-001 bleiben verbindlich.

**Korrigierte Abhängigkeit.** Der lesende Kern ist Bestandteil des noch
offenen vollständigen **15.l.R** und muss vor dessen Abschluss geprüft sein.
R wartet dafür nicht auf den Abschluss der öffentlichen M18-Schritte.
M18 verwendet den in R abgenommenen Kern weiter und führt danach seinen
gesamten zusätzlichen Umfang samt W/R/C-Abnahmen aus. Alle 900 Positionen,
ihre Kennungen und Committexte bleiben erhalten; keine M18-Checkbox wird
durch die Klärung oder die spätere R-Implementierung geschlossen.

**Zusätzliche verbindliche R-Abnahmen; derzeit noch offen:**

1. Gültige synthetische Proposaloriginale werden mit vollständigen nativen
   Originalkontexten, Reviewbelegen und Verifiern qualifiziert. Kontrollrevision
   ohne Inhaltsänderung erhält die Freigabebindung; Inhalt, gleichnamige
   Unterfelder und Extensions gehen vollständig in die Hashprüfung ein.
2. Manipulierte Inhalts-/Basis-/Planhashes, fehlende Originalkontexte,
   widersprüchliche Kontrollketten, falsche Status-/Reifegradzuordnung und
   fehlender passender `applied`-Abschluss werden konkret abgewiesen.
   Prüfergebnis-Hashes ohne die vorgeschriebenen ursprünglichen Belege
   oder ein Host-`passed` ersetzen keine Prüfung.
3. Echte unterschiedliche menschliche Testakteure erfüllen das gebundene
   Quorum; doppelte Akteure und KI-Akteure erhöhen es nicht. Unzureichendes
   Quorum, wirksamer Widerruf, Inhaltsänderung und stale Basis verhindern
   unzulässige aktuelle Freigabe unabhängig von gespeicherten Labels.
   Synthetische Testfreigaben werden nicht als reale Nutzerreviews ausgegeben.
4. Korrekt gespeicherte `rejected`-, `stale`- und `applied`-Originale bleiben
   bytegleich erhalten und liefern ihre getrennten historischen Befunde.
   Ein später anderer Zielstand macht einen gültigen historischen Abschluss
   nicht zu einem neuen Apply oder zu einer aktuellen Freigabe. Konflikte
   geschützter Originale sowie verletzte aktuelle `approved`-Invarianten
   bleiben sperrend; kein künstlicher Statuswechsel löst sie auf.
5. CLI, strukturierter Aufruf, Planungsmodus und Work benutzen dieselbe
   native Grundlage mit frischen Pflichtbeobachtungen bei aktiver Arbeit.
   Eingabedaten können weder Prüfdienste noch Schreibrechte einschleusen.
   Passive terminale Rückgabe und unvollständige Recovery bleiben nach
   10.7.9 unterscheidbar; alte gespeicherte Formate bleiben unverändert.
6. Die gemeinsamen lesenden Prüfungen erzeugen keine Projektwrites und
   führen keinen Projektcode, Proposal-Apply oder Review-start aus. Die
   bestehenden und zusätzlichen relevanten Verhaltenstests laufen gezielt
   parallel. Diese Liste ersetzt keine andere Pflichtabnahme von 15.l.R.

**Erhaltener Versuch und vollständiger Rest.** Der tatsächliche R-Versuch
hat native Fachdienste, öffentliche/Work-Anbindung, inkrementelle
Snapshotvorbereitung und erste Historienprüfungen erweitert. Ein defektes
Reviewfixture-Präfix wurde diagnostiziert und korrigiert (danach 11 gezielte
Tests bestanden). Der Work-Startfehler durch große Stat-Zeitwerte in JSON
wurde durch eine vollständige gehashte Dateisignatur repariert (gezielter
Status-/Prompt-/Cancel-Test bestanden). Ein weiterer Diagnoseversuch mit
13 ausgewählten Tests wurde vor Abschluss mit Exit 130 beendet und zählt
nicht als Erfolgsnachweis. Diese Einzelbefunde belegen keinen vollständigen
R-Abschluss. Alle 47 unfertigen Produkt-/Testdateien sind gesichert und
werden unverändert erhalten; diese ZIP enthält sie nicht.

Offen bleiben der gemeinsame Proposal-Kern, alle übrigen Standard-Lifecycle-
und Spezialistenbelege, historische Receipt-/Recovery-Audit-Faltung,
geschützte Relationsreview-/Proposal-/gegebenenfalls Legacy-Originale,
unabhängige Evidence-Policy und negative historische Befunde, vollständige
öffentliche CLI-/strukturierte Integration, Planungsmodus und Work-Parität,
partitionierbarer Snapshot mit vollständiger Abschlussprüfung,
Status-/Cancel-/Export-/Rootverlustgrenzen, alle fehlenden Crash-/I/O-/
Manipulationsabnahmen samt gezielter paralleler Regression und die
Collection-/Katalog-/Testnummernprüfung. Kein Rest wird nach M18 verschoben.
15.l.C folgt erst nach vollständigem R und erhält seinen eigenen geprüften
Zustand und Commit. Das ist eine Voraussetzungsklärung, keine Halbierung
wegen Laufzeit, Kontextdruck oder vermuteter Komplexität.

**Prüfung und Übergabe.** Ein reiner OFF-PLAN-Dokumentcommit mit Spezifikation,
Plan und erforderlichen aktiven Katalogbindungen. Keine neuen Dokumentationstests
und kein zusätzlicher Dev-Volltest; vollständige Collection/Katalogprüfung,
Payload-/Syntax-/Bindungsprüfung und native Paketprüfung bleiben Pflicht.
Apply prüft unverändert parallel die fällige N=3-Gruppe minus eingefrorener
Ausschlussliste: Sequenz **224 / Gruppe 2**. Nur nach erfolgreichem Testlauf
setzt der Entrypoint den OFF-PLAN-Marker und die Bundlezahl 516 und erzeugt
den Dokumentcommit. Produktstand bleibt **649/900**, zuletzt **15.l.W**,
nächstens **15.l.R**; R/C und M18 bleiben offen, SR-TC-0461/0462 `partial`.
Historische Nachweise behalten ihre ursprünglichen Spezifikationsbindungen.
Genau eine nativ gepackte/geprüfte ZIP wird atomar über Exchange übergeben,
Status `spec_clarification`; danach Ende ohne Applystart oder Warteschleife.
