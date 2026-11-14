# RECOVERY-REMOVAL-006 — Abbruchsperre und manueller Git-Wiederanlauf

**Datum:** 14. November 2026. **Befugnis:** ausdrücklicher manueller Nutzerauftrag
nach Abschluss von 18.k, einschließlich Spezifikation, Planung und Übergabe an
Apply2. Keine durch Control delegierte Detailklärung; kein Automatikstart.

Der Nutzer verzichtet auf automatische Rücknahme, Wiederaufnahme unterbrochener
Projektwrites und Restore in beschädigte Roots. Zuverlässige Erkennung,
dauerhafte Sperre und manueller Wiederanlauf aus einem bekannten gültigen
Git-Stand bleiben erforderlich. Bis zu seiner ausdrücklichen Benutzungsfreigabe
ist SpecRoad nicht in Verwendung; eine Live-Migration oder doppelte alte/neue
Implementierung ist nicht gefordert. Normative Einzelheiten stehen ausschließlich
in Spezifikation 1.4, 10.6/10.7, Anhang C/N/P und den geänderten Requirements.

## Entscheidung und Grenzen

Eine einzelne neue Sperrdatei ohne Writer-/Receiptintegration würde den Auftrag
nicht erfüllen: sie könnte zu spät angelegt oder zu früh entfernt werden.
Deshalb wird der gemeinsame Writevertrag einschließlich Rooterzeugung geändert.
Der Marker ist zugleich die dauerhafte Sperre; ein schreibfreier Folgeaufruf
muss kein `corrupted`-Flag persistieren. `corrupted` bedeutet unbestätigte
Konsistenz, nicht nachgewiesene Beschädigung jeder Datei. Ein aktiver Writer
und ein unprüfbarer Eigentümer werden getrennt behandelt und nicht übernommen.

Der unterstützte Wiederanlauf ist ein frischer separater vollständiger
Git-Checkout. Ein Reset im alten Root würde ignorierte/untracked Betriebsdaten
nicht zuverlässig ausschließen. SpecRoad selbst führt keine Git-Rettung aus.
Fehlende Anhänge, Archiv-/Legacyobjekte oder benötigte Originalreceipts werden
nicht rekonstruiert. Uncommittete Arbeit kann verloren gehen; Idempotenz gilt
für nachgewiesene Abschlüsse im erhaltenen Bestand, nicht über bewusst
zurückgesetzte Historien hinweg. Vor dem ersten gültigen Git-Stand wird eine
abgebrochene Rooterzeugung in einem anderen leeren Ziel neu begonnen.

Control-Recovery, normale Vorbereitungs-Workfortsetzung, sichere Dateipublikation,
Autorisierung und fachliche Validierung bleiben erhalten. Ebenso die Prüfung
historischer Daten als historische Daten. Keine pauschale Löschung der History,
Testnummern, Runtime-Messungen, fremden Daten oder abgeschlossenen Evidence.

## Abhängigkeiten und Reihenfolge

| Bereich | Erhalten und herauslösen | Ablösen beziehungsweise entfernen | Umsetzung |
|---|---|---|---|
| `recovery/services.py`, `_validation.py`, `_specialists.py`, `_owned_checks.py`, `_inventory.py`, `_evidence_history.py`, `values.py` | Fachliche Dienste, Archiv-/Projektprüfung, Approval-/Proposal-/Taskgates, sichere Lesefunktionen | Restore-spezifische Planung/Mutation und Namen | 18.s |
| `changes/locking.py`, `_publication_io.py`, staging, committing, receipt-* | Exklusive Eigentümersperre, Pfadsicherheit, Zielvalidierung, echte normale Receipts | Before-Image-Rückspielung, Journalpräfixe, Rekonstruktion, Auto-Recovery/Discard | 18.t |
| Normales Authoring, Reviews, Formatierung, Import, Baseline, Proposal | Gemeinsame Fachpläne, Autorität, exakte Kontroll-/Fachdaten, erfolgreiche Requestwiederholung | Recoveryabhängige Preflights und Abschlussprüfer | 18.u |
| `schema_transition_recovery.py`, Merge-Publikation, `_bootstrap_recovery.py`, Bundle-/Sandbox-Extraktion | `completion_proof`/`historical_request` als normale lesende Abschlussprüfung; externe Sicherung und Fachgates | Replaying, Spezialjournale, Bootstrap-Vervollständigung/-Rollback | 18.v |
| CLI, `work/restore*`, `_restore*`, Workdispatch/Manifest/Transport | Normale Workpakete, `_resume_restore.py` als Checkpointleser, `package_restoration.py` | `recover.*`, `RECOVERY_WRITE`, Restore-Work-/Ownerübergaben | 18.w |
| Model-/Result-/Commandschemas, Konfiguration, Bundle-Betriebssektion, Distribution und Katalog | Geschlossene validierte Formate, portable normale Receipts, Legacy-Originale | `auto_recover`, aktive Altformatunterstützung, unbenutzte Reparaturmodule und ausschließlich obsolete Tests | 18.x |

Die frühere statische Analyse fand 51 direkte externe Produktverbraucher der
Recovery-/Restore-Bereiche. Das ist eine Orientierung am damaligen Stand,
keine behauptete aktuelle Löschliste oder Zeileneinsparung. 18.s inventarisiert
am dann gebundenen Result erneut direkte und dynamische Imports/Reexports.
Die gemeinsame Prüfung muss vor dem Entfernen der bisherigen Module umziehen.

## Plan- und Nachweisführung

Sechs neue Schritte mit 18 echten W/R/C-Commits stehen im vorhandenen M18
zwischen 18.k.C und 18.l.W. Neue Kennungen 18.s bis 18.x nutzen unbesetzte
Buchstaben; bestehende Kennungen und erfolgreiche Commitidentitäten bleiben
erhalten. Die ausführbare Reihenfolge ist die Position/Voraussetzung, nicht
alphabetische Sortierung. Gesamt: 306 Schritte, 918 Produktcommits; 762
historisch abgeschlossen. Der OFF-PLAN-Spezifikationscommit zählt nicht dazu.

Alte abgeschlossene Recoveryabnahmen bleiben als damalige Leistung sichtbar.
Sie beweisen den neuen Vertrag nicht. Änderungen an Requirements und
Verifikationsverträgen werden im aktiven Katalog als offen/teilweise umgesetzt
geführt; alte Evidence bleibt an ihren ursprünglichen Hash gebunden.
Tests werden erst mit der jeweiligen Implementierungsphase umgestellt oder
entfernt, nicht mit diesem Dokumentationsbundle. Stabile Testnummern bleiben
reserviert. Gemischte Tests behalten ihre weiterhin benötigten Sicherheits-,
Fach- und Idempotenzoracles. Keine Dokumentations-/Markdowntests nach TD-001.

Jede W/R/C-Phase erhält das normale Apply-Gate aus N=3 und begründeter
ungefilterter Pflichtauswahl. Dev führt keine Verhaltenstests aus. M20 bleibt
für die vollständige Release-/Plattformabnahme verantwortlich; ein Teilgate
ist keine Benutzungsfreigabe. Hauptlinienvorbereitungen wie WORKER-LIMIT-12
werden getrennt auf den neuen Spec-/Planstand rebasiert, nicht hineingemischt.
