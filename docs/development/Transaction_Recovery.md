# Recoverystatus und unveröffentlichter Discard

Planabschnitt 5.p, SR-REQ-0257 / 0262 / 0458, SR-VER-0019 / 0031.

## W: sicherer nutzbarer Kern

`inspect_recovery(root, expected_project_id=..., preflight=...)` liest aktive
Transaktionsjournale ohne regulären Modellload. Der maschinenlesbare Status
enthält Zustand, Journalhash, Basis-/Zielwurzel, bestätigte Veröffentlichungen
und nachgewiesene Discard-Kandidaten. Ohne unabhängigen Basisnachweis wird keine
Discard-Erlaubnis behauptet. Defekte Konfigurationen verhindern die reine
Journaldiagnose nicht. Die Diagnose erzeugt keine Dateien und erwirbt keinen
Writer-Lock; sie ist keine wiederverwendbare Schreibberechtigung.

`discard_unpublished_transaction(preflight, transaction_id, held_lock=...,
authority=..., actor=..., reason=..., expected_journal_sha256=...)` benötigt einen
aktuell gehaltenen nativen Recovery-Lock für `recover discard`, eine explizite
Host-Autorisierung und den erwarteten Journalhash. Ein Akteursname ist keine
Authentifizierung. Ein verwaister Lock wird nicht automatisch übernommen.

Der unabhängige `PublicationPreflight` enthält die bereits geprüften, eigenen
Basisbytes und die exakte geplante Inventur. Recovery prüft diese gegen ALLE
aktuellen Basisdateien und die aktuelle Inventur, ohne neu zu planen oder das
normale kanonische Modell vom Dateisystem zu laden. Eine bloß selbstkonsistente
Hashangabe aus dem Journal reicht nicht. Basisabweichung, nicht nachgewiesene
Inventur, veröffentlichte Einträge oder ein späterer Journalzustand sperren
Discard bereits im W-Kern.

W unterstützt eine alleinige `building`-Vorbereitung mit Journal und eine
vollständige `prepared`-Vorbereitung samt exakten Before-/Staging-Images.
Unbekannte oder unterbrochene Work-Inventuren bleiben zunächst erhalten und
blockieren die Mutation.

## Dauerhafte Beweise statt rekursiver Löschung

Unter `.specroad/recovery/transaction-audit/<event-id>/` werden zuerst das
Originaljournal und eine immutable `intent.json` exklusiv geschrieben und
synchronisiert. Erst danach wird das aktive Journal auf `rolled_back` gesetzt
und synchronisiert. Die gesamte geprüfte Vorbereitung wird innerhalb desselben
Projekts atomar nach `work/` im Audit verschoben; keine Zielbytes oder Beweisdatei
werden gelöscht. `completed.json` bindet den Abschluss an Originaljournal,
Intent, terminalen Journalhash und Basiswurzel. Frühere Audits werden niemals
überschrieben. Dateien und Verzeichnisse werden synchronisiert und zurückgelesen.

Die ausdrücklich reservierte passive Audit-Namensstelle blockiert nach dem
Discard keine normalen Modellleser oder neuen Writer. Aktive Journale und
unbekannte Recovery-Einträge bleiben dagegen Blocker. Ein später Fehler kann
bereits einen terminalen Journalstand oder ein archiviertes Work-Verzeichnis
hinterlassen; er wird nie als erfolgreicher Abschluss oder als „nichts passiert“
umgedeutet. Es gibt keinen automatischen destruktiven Rollback.

## Geltungsbereich und Nachweise

Native lokale Linux-Dateisysteme und kooperierende Writer gemäß bestehendem
Lock-/Storage-Kern. Descriptor- und Hashprüfungen erkennen beobachtete Änderungen;
sie sind kein Sandbox- oder CAS-Versprechen gegen böswillige gleichzeitige
Dateisystemmanipulation. Ein Ergebnis behauptet daher kein atomares Modellsnapshot.

Dies ist die fachliche Bibliotheksgrundlage, noch kein neu verdrahteter CLI-Befehl
oder vollständiger ChangeBackend. Eine Rekonstruktion des unabhängigen
Basisnachweises nach Prozessneustart, automatischer Transaktions-Preflight,
Zielabschluss, Restore und Rollback bleiben in ihren späteren Planabschnitten.

Lokale Gates verwenden nur neue/direkt betroffene Verhaltenstests, parallel mit
maximal vier Workern auf dem Pixel. Keine lokale Vollsuite oder Fünferregel.
Vollständige Python-Matrix einschließlich seriell/parallel/Vergleich bleibt
bewusst manuell. Darstellungs- oder Dokumentationstests werden nicht eingeführt.
