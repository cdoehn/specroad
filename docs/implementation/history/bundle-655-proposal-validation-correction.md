# Bundle 655 — Korrektur der Proposal-Strukturvalidierung

9. November 2026. Maßgeblich ist das fehlgeschlagene Result
`526b75994af633f83019e60e16252ffda07c9e233ff8b6369b292c8fbb016d65` zum unveränderten HEAD
`051fac80a82dfa2f577591e9920614c42a7c4ad0`. Bundle 654 scheiterte vor dem Commit 18.f.W:
8.827 ausgewählte Tests bestanden, vier scheiterten. Kein Commit wurde erzeugt;
der vollständige uncommittete W-Zustand bleibt die Korrekturbasis. Bestätigt sind
weiterhin 744/900 Planpositionen. Alle offenen IDs 18.f.W, 18.f.R und 18.f.C
behalten ihre Rolle implementation und ihren vollständigen angekündigten Umfang.

## Fehler und Korrektur

Die relative Proposal-Datei wurde bei einem expliziten Aufrufverzeichnis am
Prozessverzeichnis gesucht: Der gemeinsame Optionsresolver übergab diesem neuen
Lesebefehl noch kein working_directory. Er reicht nun wie bei den bestehenden
Lesebefehlen das tatsächliche Aufrufverzeichnis weiter. --project wählt weiterhin
das Projekt und ersetzt nicht den Ursprung eines ausdrücklich übergebenen
relativen Dateipfads. Absolute Dateien und Proposal-IDs behalten ihren Vertrag.
Der bereits fehlgeschlagene relative argv-/CommandRequest-Test bleibt unverändert.

Drei ältere geschlossene Inventartests erwarteten noch den Stand vor 18.f.W.
Die expliziten Befehls- und Ergebnisschemalisten enthalten nun proposal.validate
beziehungsweise proposal-validation-v1. Die Capability-Prüfung verlangt genau
den implementierten read_only-Befehl; ohne ihn verschwindet die Proposal-Gruppe.
Das reine Proposal-Datenschema und dieser Strukturleser behaupten weiterhin
keinen vollständigen Review-/Apply-Workflow. Die supported_versions-Angabe bleibt
leer; die bisherigen negativen Writer- und übrigen Inventarprüfungen bleiben.

R ergänzt sechs öffentliche Pfadregressionen: argv und CommandRequest prüfen
relative externe Dateien bei explizitem und tatsächlichem Prozessverzeichnis
sowie verwaltete Dateien aus einem verschachtelten Aufrufverzeichnis. Eine
ungültige gleichnamige Projektdatei macht die falsche --project-Auflösung
sichtbar. Originalhash beziehungsweise Basisbindung, vollständige Inventare,
Schreibverbote und unverändertes Arbeitsverzeichnis werden geprüft. Eigene kleine
vollständige native Projekte isolieren die Fälle; die vorhandene vollständige
Integrationsreferenz und alle früheren Tests bleiben erhalten.

Die angekündigte R-Vervollständigung und die reine C-Modultrennung aus Bundle
654 bleiben vollständig bestehen. C übernimmt alle W-/R-Testbytes unverändert.
Die sechs neuen R-Identitäten werden erst nach allen bereits angekündigten
Testnummern angehängt. Keine Nummer wird geändert, wiederverwendet oder vorgezogen.

## Gebundene Fortsetzung

Der öffentliche Vorgängerplan mit SHA-256
`48abb67863df0e295131c677447e82cec84b918b58b71a9fff683791915a0baa`
und sein nativer Fehlerfortschritt begründen den vollständigen Rest. Die erste
Stage enthält auch alle unverändert übernommenen schmutzigen W-Dateien samt
vollständigen Vorherbytes aus diesem neuen Result. W, R und C erhalten jeweils
ein eigenes Apply-Testgate vor ihrem echten Commit. Der Endstand wird nicht
vorab ausgebracht. Der historische Bericht 654 bleibt in seinen tatsächlichen
Resultbytes erhalten; seine vorbereiteten Zielaussagen sind kein Apply-Erfolg.

Vorbereiteter W-Zustand: Seine Fortschrittswerte gelten erst nach
dem erfolgreichen eigenen Apply-Gate und Commit. R und C bleiben offen.

Keine neue normative Lücke, Detailklärung oder Budgetänderung. Spezifikation,
Entwicklungsvertrag und der offene spätere vollständige Proposal-Check bleiben
unverändert. Die ursprünglichen Pflichtauswahlen werden beibehalten und um alle
geänderten Inventar-/Capabilitytests, Options- und Pfadregressionen ergänzt.
Dev führt keine Verhaltenstests aus. Syntax, reine Collection und native
Paket-/Stufenprüfung belegen keine Verhaltensabnahme. Nach atomarer Übergabe
endet dieser Auftrag; die gefilterte fällige N=3-Gruppe plus ungefilterte
Pflichtunion läuft ausschließlich im jeweiligen Apply-Gate.
