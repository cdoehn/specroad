# OFF-PLAN CONTROL-INTEGRATION-CORRECTION-558 — Release-Selbstprüfung

Vollständig übernommener Entscheidungs-/Ausführungsstand. Enthaltene fachliche Präzisierungen und Abnahmen bleiben über die Grundlagenrangfolge wirksam; tatsächliche Abläufe und Erfolgsangaben gelten ausschließlich für die jeweils benannten damaligen Quellen. Dieser Datensatz ist kein aktueller Fortschrittsblock und kein Betriebsauftrag.

[Verzeichnis](../history/README.md) · [Aktiver Plan](../SpecRoad_Implementierungsplan.md)

## OFF-PLAN CONTROL-INTEGRATION-CORRECTION-558 — Release-Selbstprüfung

Ausdrücklicher Korrekturauftrag vom 3. November 2026. Maßgeblich ist das
nativ geprüfte Fehler-Result ef506d, SHA-256
`6154aadc6411a99e2b7af5c7eaade1d571bd07ba7f5c78866cd95d6fd01f8d3f`,
Basiscommit `0883e7f919c6c1fbce921db59802e1813e330173`,
Arbeitsstand-Fingerprint `21fff3a4221b58a1`. Bundle 557 erzeugte keinen
Commit: 7108 Tests bestanden, 66 scheiterten. Die früheren TMPDIR- und
Importpfadkorrekturen samt ihren Abnahmen bleiben vollständig erhalten.
Der vollständige W-Arbeitsstand wird übernommen; alle drei offenen IDs
CONTROL-INTEGRATION-556.W/R/C behalten Reihenfolge, Pflichtsuite und eigenes
N=3-Gate. Kein Produktfortschritt: 669/900, nächster Produktcommit 16.d.W.

58 Workerfehler melden dieselbe Codepfadsperre; vier weitere Worker enden
vorzeitig mit Exit 1 über denselben Startpfad. Der installierte Prozess prüft
seine Releasebytes bisher mit Betriebsdatenhelfern, die korrekt den aktuell
laufenden Codebaum sperren. Ein gesonderter rein lesender Zugriff auf die
gebundene Release-Inventur ersetzt diese Verwechslung. Der externe Release-
Elternordner bleibt Git-/Symlink-geprüft; relative Verzeichnisdeskriptoren,
private Rechte/Eigentümer, Dateityp, Hardlink-/Größen-/Inventargrenzen und
Dateihashes werden geprüft. Fehlende Verzeichnisse werden nicht angelegt.
Die Betriebsdatenhelfer bleiben unverändert und erlauben keine Schreibzugriffe
in den laufenden Code. Alternative, die Codepfadsperre generell zu öffnen,
wird verworfen. R behält sämtliche ursprünglichen Release-/Recovery-Härtungen.

Vier weitere Fehler entstehen beim Versand von Subtest-Berichten im parallelen
Runner: Funktionen, Ausnahmen und Path-Objekte sind nicht transportierbar.
Nur ihre Diagnoseparameter werden durch eindeutige primitive Kennzeichnungen
ersetzt. Ausgeführte Fälle, Aufrufe und fachliche Assertions bleiben erhalten.

W-Abnahmen: echter installierter Worker startet und stoppt ohne Codeänderung,
Selbstprüfung erlaubt keine Betriebsdatenschreibzugriffe, fehlendes Release
wird nicht repariert. R-Abnahmen: Hash-/Inventar-/Receipt-Manipulation,
Datei-/Verzeichnis-/Root-Symlinks, FIFO, Hardlinks, Rechte, Dateigröße und
Git-Verzeichnis bleiben gesperrt. Die komplette Control-Suite einschließlich
der vier Subtest-Fälle läuft verpflichtend parallel in jeder Stage.
C bleibt reine Strukturarbeit, R/C-Tests und Testnummern bytegleich.

Spezifikation 0.2.53 und aktive Katalogbindungen unverändert; keine neue
fachliche Entscheidung. Dev führt keine Verhaltenstests aus. Collection,
Syntax- und native Paketprüfung ersetzen keine Apply-Abnahme. Betriebsmigration,
Dienste, Automatik und lokale Konfigurationen bleiben außerhalb der Payload.
