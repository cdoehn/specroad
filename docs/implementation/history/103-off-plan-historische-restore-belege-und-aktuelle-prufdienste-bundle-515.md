# OFF-PLAN – Historische Restore-Belege und aktuelle Prüfdienste (Bundle 515)

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN – Historische Restore-Belege und aktuelle Prüfdienste (Bundle 515)

**RESTORE-HISTORICAL-VALIDATION**, ausdrücklicher manueller Nutzerauftrag
vom 29. Oktober 2026: „Ja mache das bundle für die Klärung nach deiner
Empfehlung!“ Die zuvor vorgelegte Empfehlung wird damit normativ in
Spezifikation **0.2.37 / 10.7.9** übernommen. Dieser Dokumentauftrag folgt
unmittelbar aus der Nutzeranweisung und 2.4.3; er beansprucht kein aus alten
Control-Verträgen abgeleitetes Budget. Control, Watcher und Laufzeitdaten
bleiben unverändert. Die Entwicklungsentscheidung ist kein menschlicher
Reviewnachweis für ein verwaltetes Artefakt.

- [x] **RESTORE-HISTORICAL-VALIDATION:** Aktuelle vollständige Restore-Qualifikation und passive historische Ergebnisprüfung verbindlich trennen; aktive Katalogbindungen fortschreiben. Commit: `docs(spec): Historische Restore-Belege und aktuelle Prüfdienste trennen`.

**Geprüfte Basis und Lücke.** Maßgeblich ist das erfolgreiche saubere Result
von Bundle 514, `specroad-apply_Result_215320_1028_59c44a.zip`, SHA-256
`d33219d1211569e8a2510829c21c724e84267a1d39641956c1b67ac98cb1d287`,
Abschlusscommit `bb2a55dbf5f2b46afe3b6c4701bc2087284605db`, Repository-ID
`a33ed6cf-0a97-4b73-b11a-d4239e7a2145`, Fingerprint `7c9d2a24e397e0e5`,
Algorithmus `patchharbor-state-v1`. Root-Anleitung, Metadaten, Run- und
Ausführungslogs, vollständiger Snapshot und tatsächliche technische Basis
wurden geprüft. Die drei erfolgreichen OFF-PLAN-Commits von 514 endeten
mit 7.399, 5.946 und 5.915 bestandenen parallelen Apply-Tests, zuletzt
Sequenz 222 / Gruppe 0. Dies sind getrennte Teiltests auf getrennten
Zwischenständen, kein gemeinsamer Vollsuite- oder Produktfreigabenachweis.

10.7.1 fordert vollständige Fachprüfung, 10.7.2 bindet unabhängig prüfbare
Originalbytes, 10.7.7/11.12 verlangen zugleich die passive Rückgabe eines
vollständig abgeschlossenen Work-Ergebnisses. Die vorhandenen nativen
Requirement-Approval- und Task-Done-Prüfkerne erwarten explizite vollständige
Hosteingaben und tatsächliche Reviewverifikation. `approval_values.py`
definiert ausdrücklich kein persistiertes Reviewformat. Die bisherige
Restore-Qualifikation besitzt dafür keinen vollständigen Eingang; ihre
Provider-Sperren dürfen nicht durch Erfolgslabels oder leere Callbacks
entfernt werden. `restore_delivery.py` unterscheidet bereits native
Ausführung von historischer Rückgabe. Zu klären waren Herkunft/Bindung
der notwendigen Belege und die Grenze zwischen diesen beiden Prüfwegen.

**Alternativen und Entscheidung.** Statuswerte, Hashes oder frühere grüne
Tests als Freigabeersatz scheiden aus: Sie authentifizieren keinen Review.
Eine neue Qualifikation des heutigen Projekts für jede terminale Rückgabe
widerspräche 10.7.7/11.12 und würde Rootverlust falsch als neue fachliche
Aufgabe behandeln. Dauerhaftes Ablehnen historischer Ressourcen erfüllt
den beauftragten R-Umfang nicht. Gewählt ist deshalb die kleinste Trennung:
explizit angebundene vorhandene native Dienste für aktuelle Qualifikation;
vollständige passive Original-/Abschlussbindung ausschließlich für die
Rückgabe bereits abgeschlossener Arbeit. Es entsteht kein neues persistiertes
Reviewformat. Bestehende native Hosteingaben bleiben Hosteingaben; gespeicherte
Originalbelege werden nur in ihrem bereits definierten Vertrag gelesen.
Fehlende Pflichtfakten bleiben sperrend und werden nicht erfunden.

**Abgleich mit 2.4.1.** (1) Betroffen ist nur der bestätigte Rest von 15.l.R,
kein neues Feature oder vorgezogener Schritt. (2) Die beiden Prüfzwecke werden
nach 10.7.9 explizit getrennt; keine gleichrangige Pflicht wird gestrichen.
(3) Vollständige Fachgates, menschliche Reviews, Autorisierung, Scope,
Sicherheitsgrenzen und Bestandskompatibilität bleiben erhalten. (4) Die Regel
ist dokumentversioniert und ohne Datenmigration korrigierbar; bestehende
Plan-, Work-, Ergebnis- und Nachweisbytes bleiben unverändert. (5) Die
Definition der expliziten Eingänge behauptet weder vorhandene reale Reviews
noch externe Fakten. Bei fehlenden tatsächlichen Eingaben bleibt der
betroffene Aufruf mit konkretem Befund gesperrt. §2.4.2/2.4.4, §2.5 und
BD-001 sowie sämtliche Produktfreigabegrenzen bleiben unverändert.

**Zusätzliche verbindliche R-Abnahmen, noch nicht ausgeführt:**

1. Aktuelle Planung und neue Vorwärtspublikation verwenden vollständige native
   Fachgates auf tatsächlichen Originalbytes samt Modell-/Konfigurations- und
   Projektionsbindung. Positive synthetische Testfälle benutzen echte native
   Review-/Task-Prüfverträge; Testdaten werden nicht als reale Nutzerfreigabe
   ausgegeben. Fehlende, stale, gefälschte, nichtmenschliche, abgelehnte und
   kontextfremde Belege sperren mit dem passenden fachlichen Befund.
2. CLI, strukturierter Aufruf, Planungsmodus und Work besitzen dieselben
   erforderlichen Prüfdienste und Ablehnungen. Projekt-/Plan-/Workdaten können
   keinen Prüfdienst oder Grant einschleusen. Aktuelle Autorisierung und
   externe Verifierbeobachtungen werden bei Bedarf frisch geprüft, auch wenn
   identische reine Byteprüfungen innerhalb des Aufrufs wiederverwendet werden.
3. Vollständig abgeschlossene Workaufträge liefern nach Prüfung ihrer
   Originalbindung, vollständigen Kette, Abschluss- und Ergebnisbytes das
   gespeicherte Ergebnis ohne Projekt-/Quellroot und ohne neue Facharbeit oder
   Writes. Die aktuelle Antwort weist `native_execution_checked=false` und
   `checkpoint_changed=false` aus; gespeicherte fachliche Ergebnisbytes
   ändern sich nicht. Manipulierte oder unvollständige Belege werden abgewiesen.
4. Noch nicht abgeschlossene Arbeit und verlorener äußerer Abschluss nutzen
   ausschließlich die passende native Journal-/Recovery-/Lieferregel, niemals
   den historischen Rückgabepfad als Abkürzung. Vollzielabschluss, Teilzielrollback,
   frische Writeautorisierung und getrennte Ownerübernahme bleiben belegt.
5. Alte geschlossene Plan-/Work-/Journalformate und historische Nachweise
   behalten ihre Originalbytes und Verträge. Keine zusätzlichen Belegfelder,
   stillen Migrationen oder aus Daten geladenen Prüffunktionen. Relevante
   bestehende Regressionen bleiben grün.

**Vollständiger Rest und Liefergrenze.** 15.l.R bleibt insgesamt offen:
öffentliche Command-/CLI-Integration, Planungsmodus und Work-Parität,
vollständige historische Receipt-/Recovery-Audit-Faltung, Lifecycle- und
Spezialistenbelege, unabhängige Evidence-Policy, weitere geschützte Ressourcen,
Konfigurations-/Dokumentprüfungen, partitionierbarer Planungs-Snapshot,
Workstatus-/Cancel-/Exportgrenzen und die vollständigen Crash-/I/O- und
Sicherheitsabnahmen einschließlich Integration und gezielter paralleler
Regression. 15.l.C folgt erst nach vollständigem R-Abschluss. Vorhandene
unfertige Produktarbeit wird erhalten und ist nicht Bestandteil dieser ZIP.
Die Klärung ist ein ausdrücklich beauftragter Dokumentauftrag, keine weitere
R-Teilimplementierung und keine durch Laufzeit oder Komplexität begründete
Halbierung. Produktstand bleibt **649/900**, zuletzt **15.l.W**, nächstens
**15.l.R**; SR-TC-0461 und SR-TC-0462 bleiben `partial`.

**Prüfung und Übergabe.** Nur Spezifikation, Plan und aktive Katalogbindungen
werden ausgeliefert. Kein neues Dokumentationstestprogramm und kein Dev-
Volltest; vollständige Collection/Katalogprüfung, Payload-/Syntax- und native
ZIP-Prüfung bleiben Pflicht. Beim Apply gilt unverändert die nächste
parallele N=3-Gruppe minus eingefrorener Ausschlussliste: Sequenz 223 /
Gruppe 1. Erst nach deren Erfolg wird der OFF-PLAN-Marker gesetzt und der
eine Dokumentcommit erzeugt; R/C und Produktzähler bleiben offen. Der
Paketstatus ist `spec_clarification`. Veröffentlichung der einzigen geprüften
ZIP erfolgt atomar über Exchange; danach endet der Auftrag ohne Applystart,
Warteschleife oder Fortsetzung der Automatik. Historische Nachweise bleiben
unverändert an ihre ursprüngliche Spezifikation gebunden.
