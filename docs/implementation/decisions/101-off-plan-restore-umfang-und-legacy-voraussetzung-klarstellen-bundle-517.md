# OFF-PLAN – Restore-Umfang und Legacy-Voraussetzung klarstellen (Bundle 517)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Restore-Umfang und Legacy-Voraussetzung klarstellen (Bundle 517)

**RESTORE-SCHEMA-SCOPE**, ausdrückliche Nutzerfreigabe vom 29. Oktober 2026:
„Ich erteile die Freigabe. Mache den weiteren Schritt.“ Genehmigt wurde der
zuvor konkret vorgeschlagene Umfang: vollständiges 15.l.R für das vorhandene
0.2-Format; sichere Abweisung nicht unterstützter deklarierter Altformate;
positive 0.1-Unterstützung erst auf verbindlicher Quellgrundlage, Migration
weiter in M16; Korrektur der pauschalen Forderung nach echten historischen
Produktivdaten. Dies ist eine manuelle Scope-/Kompatibilitätsentscheidung,
keine aus SPECROAD-DECISION-1 abgeleitete Detailvollmacht. Die vorherige
Freigabe zur Vorziehung eines lesenden Legacy-Kerns wird insoweit ersetzt.
RESTORE-PROPOSAL-PREREQUISITE und alle übrigen R-Pflichten bleiben bestehen.

- [x] **RESTORE-SCHEMA-SCOPE:** Unterstützten Restoreumfang und Legacy-Voraussetzung verbindlich korrigieren und aktive Katalogbindungen fortschreiben. Commit: `docs(spec): Restore-Umfang und Legacy-Voraussetzung klarstellen`.

**Geprüfte technische Basis.** Sauberes erfolgreiches Result von Bundle 516:
`specroad-apply_Result_104417_1029_a7a40a.zip`, SHA-256
`61940e56d3f08058fe3d69a05999b25d883794fdcb87a18f052aa269097920f2`,
Abschlusscommit `df045ed438e1fed317da7c6e7ea1c919b06c4835`, Repository-ID
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint `7c9d2a24e397e0e5`,
Algorithmus `patchharbor-state-v1`. Metadaten, Logs, Snapshot und tatsächliche
Basis wurden nativ geprüft; 516 bestand 5.946 parallele Apply-Teiltests,
Sequenz 224 / Gruppe 2. Das ist kein Prüferfolg des offenen R-Arbeitsstands.
Im geprüften Result ist ausschließlich Schema 0.2.0 implementiert; der
Legacy-Anzeigeadapter erklärt selbst, kein validierender Quellleser zu sein.
0.1-Dokumentversionen belegen keine veröffentlichte Datenformatversion.
Über externe 0.1-Installationen wird keine Existenzbehauptung getroffen.

**Lücke und Alternativen.** Die bisherige Spezifikation verlangte positive
Legacy-Erhaltung, ohne den benötigten vollständigen 0.1-Quellvertrag
bereitzustellen. Die unmittelbare lesende Vorziehung beseitigte diese
fehlende Definition nicht. (a) Historische Felder/Hashalgorithmen aus 0.2 zu
erfinden würde unbelegte Kompatibilität behaupten. (b) Auf vermeintlich
vorhandene Produktivdaten zu warten wäre ohne Beleg keine belastbare
Voraussetzung. (c) Den Quellvertrag in M16 explizit vorauszusetzen und den
aktuellen R-Abnahmeumfang auf das definierte 0.2-Format zu beziehen ist die
gewählte begrenzte, versionierte und rücknehmbare Korrektur. Die bestehende
0.1-Zusage wird dabei ausdrücklich geändert; sie wird nicht als unverändert
ausgegeben. Eine spätere Unterstützung erfordert Leser, Migration und
Restore-Integration mit vollständigen positiven und negativen Nachweisen.

**Normative Fortschreibung.** Spezifikation **0.2.39**, 10.7.1/10.7.11,
10.19, SR-REQ-0272 und Anhang Q.0 sind maßgeblich. Q.0 gilt vorrangig für
positive 0.1-Aussagen in Requirements, Szenarien, Verifikation und M16.
Die pauschale Forderung nach echten historischen Daten im unveröffentlichten
Legacy-Entwurf wird nicht übernommen. Synthetische Fixtures gegen einen
verbindlich definierten Quellvertrag sind zulässig und bleiben als solche
gekennzeichnet. Historische Nachweise, existierende Originale, menschliche
Freigaben, Risikoentscheidungen und aktuelle 0.2-Verträge bleiben erhalten.

**Verbindliche Abnahmen für den vollständigen R-Abschluss:**

1. Sämtliche positiven 0.2-Restorefälle und übrigen Pflichten aus
   10.7.1–10.7.10 erfüllen: Quelle/Ziel, unveränderbare Historien samt Closure,
   Receipts/Audits, native Review-/Proposalprüfungen und aktuelle Freigaben.
2. Deklarierte 0.1-/unbekannte Schema-Versionen und nicht unterstützte
   Legacy-Manifestregistrierungen vor Änderungen an Projekt, projektinternen
   Betriebsdaten oder vorhandenen Originalen mit Code 3
   und präzisem Befund abweisen; keine stille Auslassung oder Migration.
   Identitäts-, Sicherheits- und I/O-Fehler behalten ihre bisherigen Klassen.
3. Dieselben Grenzen in öffentlichem Command/CLI, strukturiertem Aufruf,
   Planung und Work nachweisen; Originalbytes bei Abweisung unverändert
   lassen. Passive terminale Work-Rückgabe bleibt nach 10.7.9 getrennt.
4. Alle übrigen W-/R-Regressionen, Owner-/Autorisierungs-, vollständigen
   Crash-/I/O- und Wiederherstellungsabnahmen erfüllen. Die Scopekorrektur
   schließt keine dieser Pflichten und ersetzt keine Verhaltensprüfung.
5. Für M16 bleibt vor positiver 0.1-Unterstützung der vollständige versionierte
   Quellvertrag aus Q.0 samt Leser-/Migrations-/Restore-Integration und
   nachweislich passenden Testvektoren erforderlich. Ohne ihn wird weder
   Kompatibilität behauptet noch M16 als erledigt markiert.

**Arbeitsstand und Übergabe.** Vorhandene unfertige R-Implementierung,
separat geprüfte Reparaturen und auch fehlgeschlagene/unterbrochene Diagnosen
bleiben erhalten. Diese reine OFF-PLAN-Dokumentlieferung übernimmt keinen
Produktcode und behauptet keinen grünen R-Abschluss. Produktstand bleibt
**649/900**, zuletzt **15.l.W**, nächstens **15.l.R**; **15.l.C** bleibt offen.
Aktive Katalogbindungen folgen dem neuen Spezifikationshash, historische
Nachweise bleiben bytegebunden. Keine neuen Dokumentationstests, keine
Dev-Vollsuite, keine künstliche W/R/C-Folge. Der einzelne Dokumentcommit
folgt in Apply nach erfolgreicher fälliger paralleler N=3-Auswahl,
**Sequenz 225 / Gruppe 0**, **5.915** Tests aus **22.263** gesammelten Fällen
nach Abzug der unveränderten eingefrorenen Laufzeitenliste von der fälligen
Gruppe (7.422 vor Filterung, davon 1.507 ausgeschlossen). Auswahl, Identitäten,
Listenhash und Testzahl werden nativ
gebunden; erst der erfolgreiche Commit setzt die OFF-PLAN-Checkbox und die
Bundlezählung. Control/Watcher, Dienste, externe Konfiguration und
Laufzeitdaten bleiben unverändert. Nach geprüfter atomarer ZIP-Übergabe
endet dieser Auftrag; ein Folgeauftrag setzt nach zugeordnetem Result den
vollständigen R-Rest fort.
