# Python-3.10-Kompatibilitaet: Missing-Kopien und I/O-Testschutz

## Beobachteter CI-Lauf

Das vom Nutzer bereitgestellte Archiv `logs_96733892513.zip` gehoert zum
GitHub-Lauf 35728312516 fuer Commit 5f078a56f285ee4e5b62e45999643c75e90ba0c0.
3.10.21: 2.762 passed / 2 failed; 3.11, 3.12, 3.13 und 3.14: jeweils
2.764 passed. Katalogvorpruefung: auf allen fuenf Versionen erfolgreich.
Dies ist ein neuer Lauf nach der Katalogkorrektur, kein noch offener alter
Test-ID-Fehler. Das neue Result bestaetigt nur den lokalen Bundle-011-Apply.

## W: Gezielte Korrektur

`_Missing.TOKEN` hat einen opaken object()-Wert. Ohne eigene Kopierprotokolle
kann eine Enum auf 3.10 beim deepcopy per Pickle-Reduktion rekonstruiert werden;
der kopierte object()-Wert ist nicht mehr das originale Enum-Mitglied.
Die Klasse definiert deshalb __copy__ und __deepcopy__ als identitaetserhaltend.
Der interne Wert wird nicht auf einen JSON-Wert umgestellt. Missing bleibt
von null getrennt, ohne impliziten Wahrheitswert und ohne JSON-Serialisierung.
Dies fuehrt keinen neuen Pickle-/Transportvertrag ein.

Der Metadaten-Sicherheitstest blockierte __import__, bevor ein weiterer
String-Patcher sein Ziel `builtins.open` aufloesen konnte. Auf 3.10 scheiterte
damit die Testvorbereitung, nicht die Metadatenverarbeitung. Beide Zielobjekte
werden jetzt direkt an patch.object uebergeben. Import- und Dateisperre bleiben
waehrend der eigentlichen Produktoperation wirksam. Positive Kontrollen
pruefen, dass absichtliche Import-/Open-Versuche weiterhin scheitern.

## Abnahmegrenze

Neue lokale Gates pruefen ausgewaehlte Regressionen, keine Produktsuite.
Ein lokaler Apply oder Push bestaetigt keinen gruenen GitHub-Lauf. Erst der
neue CI-Lauf prueft die vollstaendige Matrix. Die Viererpolicy fordert fuer
Bundle 012 beide Volltestmodi samt fachlichem Nachweisvergleich.

## Primaerquellen

- https://docs.python.org/3.10/library/copy.html (Kopierprotokolle, memo)
- https://docs.python.org/3.10/library/unittest.mock.html#patch-object

Keine Abhaengigkeiten, Workflows, Sicherheitsregeln oder Laufzeitmatrix entfernt.

## R: Regressionen

Zusammenhaengende Datenkopien behalten Missing-Identitaet, geteilte Referenzen,
Zyklen und unabhaengige mutable Container. Der memo-Vertrag bleibt unveraendert.
Eine isolierte Kindprozessregression entfernt neuere Enum-Kopierhilfen, damit
diese das eigene Singleton-Protokoll nicht versehentlich ersetzen; dies ist
eine Simulation der relevanten Bibliotheksvoraussetzung, kein echter 3.10-Lauf.
Portable Modul-/Zipapp-Ausfuehrungen pruefen denselben Kopiervertrag.

Testschutzregressionen zeigen die Wirksamkeit beider Sperren und korrekte
Wiederherstellung nach Fehlern sowie verschachtelte Nutzung. Kein globaler
Zustand wird zwischen Tests hinterlassen. Keine Skip-/Xfail-Ausnahme.
