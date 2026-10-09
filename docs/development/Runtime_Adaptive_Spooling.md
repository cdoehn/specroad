# Gemessene Arbeitsfenster für lebende Spool-Aufträge

`runtime.adaptive_spooling.advance_spool_sort(task, call, max_units=256)` verbindet
einen vorhandenen `DiagnosticSort` oder `PathSort` mit einer aktiven
`InvocationConsumption`. Der Aufrufer erstellt den Task mit ausdrücklich
geschützten Projektwurzeln und einem neuen externen Spoolverzeichnis, verwaltet
seine Lebensdauer und schließt jedes Messfenster mit `call.finish()` ab.

Der Treiber misst vor und nach jeder tatsächlich ausgeführten Sortiereinheit.
Sobald ein weiches Arbeitsziel überschritten ist, endet das Fenster nach
mindestens einer versuchten Einheit. Ein bereits vor der ersten Einheit
überschrittenes Ziel verweigert diesen Fortschrittsversuch nicht. Ohne beobachtete
Überschreitung läuft der Treiber bis zum vollständigen Abschluss oder bis zur
ausdrücklich gewählten positiven Zahl `max_units`. Unbekannte Messwerte werden
nicht als erschöpfte Kapazität interpretiert.

Bei weichem Druck begrenzt er die zukünftige kodierte Charge auf höchstens
64 KiB; bei einer beobachteten Überschreitung des verbuchten Speicherziels auf
einen Record. `DiagnosticSort.reduce_batch_bytes()` verkleinert das Ziel nur.
Bereits gepufferte Records und eine vorausgelesene Eingabe bleiben erhalten,
bis der bestehende Flush sie verarbeitet hat. Ein einzelner großer Record kann
den weichen Bytewert überschreiten. Die Änderung verspricht keine sofortige
Speicherfreigabe, RSS-Obergrenze oder garantierte Hostkapazität.

Der existierende Sortierer liest den Quelliterator einmal, schreibt externe
Läufe und führt sie paarweise zusammen. Ein offener Merge wird am lebenden
Cursor fortgesetzt. Ein kleines Fenster verwirft keine Pflichtdiagnosen,
vorbereiteten Pfade, Duplikate oder deren Reihenfolge. Vollständige Ausgaben
werden weiterhin ausschließlich über `task.result` und dessen Ausgabecursor
zugänglich. `PathSort` verarbeitet vorbereitete Pfade; er berechnet keine neue
Why-Suche.

Die abgelöste Projektion `spool-work-window-v1` nennt tatsächliche Fortschritte,
Cursor, gewählte Anpassung und nächste Operation. `state=active` erfordert
einen weiteren Aufruf desselben lebenden Tasks; `state=completed` bezeichnet den
fertigen Spool. Ein bereits fertiger gültiger Task behauptet keinen zusätzlichen
Fortschritt. Die Projektion ist ausdrücklich an den aktuellen Prozess gebunden,
mit `checkpoint=null` und `durable_checkpoint=false`. Sie ist kein CLI-Resultat
und vergibt keinen Exitcode 8. Persistente Work-Identität und Wiederaufnahme
folgen ab 6.i.

`advance_spool_sort` behält den vorhandenen nativen Ausnahmevertrag. Der Task bewahrt
bereits geschriebene Spooldateien, schließt eigene Handles und zählt eine
fehlgeschlagene Einheit nicht als abgeschlossen. Es gibt keinen automatischen
Retry, keine Löschung von Projekt-/Recoverydaten und keinen Writer-Lock auf
einem geschützten Projekt. Die vorhandenen Schutz- und Eingabeprüfungen bleiben
wirksam.

`advance_spool_sort_outcome(task, call, max_units=256)` ergänzt einen ausdrücklich
konservativen Einstieg. Er wählt vor dem Fortschrittsversuch eine zukünftige
Charge von einem Record, verwendet die vorhandenen externen Sortierläufe und
versucht jeweils eine Einheit am bestehenden Cursor. Eine schon vorhandene
größere Charge wird dadurch nicht rückwirkend freigegeben oder neu eingelesen.
Diese Wahl kann mehr externe Läufe erzeugen; sie ändert die vollständigen
fachlichen Ergebnisse nicht.

Die Projektion `spool-work-outcome-v1` enthält bei Erfolg das normale `window`.
`active` hat `exit_code=null`, `completed` hat `exit_code=0`. Ausschließlich
beobachtete `MemoryError` und bekannte native I/O-Fehler innerhalb des tatsächlichen
`spool_advance` ergeben `blocked`, `exit_code=5`, `window=null`. Das ist ein
betrieblicher Adaptervertrag, kein bereits integriertes CLI-Resultat.
Ein weiches Ziel oder unbekannte Kapazität allein erzeugt keinen Blocker.
Ungültige Eingaben, Schutzverletzungen, Messkontrollfehler, unbekannte Fehler und
Unterbrechungen behalten ihren Ausnahmevertrag.

`blocker` nennt Fehlerklasse, natives `errno`, fehlgeschlagene Phase, die tatsächlich
gewählte kleinere Charge und den kleinsten Fortschrittsversuch. Eine konkrete
`required_action` unterscheidet zum Beispiel fehlende Deskriptoren, Speicher,
Datenträgerplatz, Schreibrechte, Dateigrößenlimit und unzuverlässige I/O.
Es gibt keine erfundene Zahl für benötigte Mindestressourcen. `retained_progress`
enthält den zuletzt beobachteten Cursor und abgeschlossene Einheiten; vorhandene
externe Spooldateien werden nicht gelöscht. Eine kurze native Schreiboperation
kann außerdem einen unbestätigten Teilrecord hinterlassen. Die Cursorprojektion
beweist dessen Hash, vollständige Veröffentlichung oder Wiederaufnehmbarkeit
nicht. Sie wird nach dem Fehler nicht als neuer Checkpoint revalidiert.

Ein fehlgeschlagener Task schließt seine Handles und seinen Generator. Gepufferte
oder vorausgelesene Werte im flüchtigen Generator sind danach nicht fortsetzbar;
`live_task_resumable` und `buffered_input_resumable` sind ausdrücklich `false`.
Die nächste Aktion verlangt deshalb Abhilfe, erneute Eingangsprüfung und einen
neuen Task in einem neuen externen Spool. Der Adapter führt diesen Neustart nie
automatisch aus. Die erhaltenen Dateien bleiben zur Prüfung verfügbar. Eine
Wiederaufnahme ihrer Daten ohne Präfixwiederholung benötigt erst den persistenten
Work-/Snapshotvertrag ab 6.i; ein Code 8 wird hier weiterhin nicht vergeben.

Die Tests verwenden echte externe Spooldateien und ausdrücklich markierte
Zählerfixtures für CPU-/Wall-Ziele. Sie vergleichen vollständige Ergebnisse und
Recordbytes, monotonen Fortschritt, Quellverbrauch, offene Mergecursor sowie
erhaltene Projekt-/Spooldateien bei injizierten Speicher-/Datenträgerfehlern.
Es wird keine allgemeine präemptive Millisekundengarantie behauptet: native
I/O-Aufrufe, Recordverarbeitung und notwendige Hashprüfungen bleiben innerhalb
ihrer bestehenden Einheit unteilbar. Andere Fachalgorithmen, persistente
Checkpoints und die vollständige Runtime-/Plattformabnahme bleiben offen.

Die R-Nachweise ergänzen reale native Ablehnungen unter isoliertem Linux
`RLIMIT_NOFILE` beziehungsweise `RLIMIT_FSIZE`, einen echten kurzen Schreibpräfix
vor einer markiert injizierten Platzverweigerung und eine echte fehlgeschlagene
Allokation unter `RLIMIT_AS` in einem ausdrücklich markierten Ersatzinitialisierer.
Letztere ist kein Benchmark des tatsächlichen Speicherbedarfs des Spool-Hashers.
Weitere klassifizierte I/O-/Speicherfehler sind markierte Injektionen in einen
bereits laufenden Merge. Before Images, Journal, Checkpoint-/Snapshotfixtures
und vorhandene Spoolbytes bleiben erhalten. Harte OOM-Kills und Dateiverlust
lassen sich durch diese Python-Fehlerprojektion nicht auffangen.

Die interne Struktur trennt in 6.h.C die reine Chargenwahl, die unveränderte
Zuordnung nativer Fehler und den Aufbau der Blockerwerte in
`runtime._spool_work_policy` ab. Dieses Modul greift weder auf einen Task noch
auf Hostmessungen oder Dateien zu. `adaptive_spooling` behält Validierung,
Messreihenfolge, Fortschrittsversuche und den genauen Ausnahmebereich. Sortier-
und Spoolalgorithmen bleiben in ihren vorhandenen Modulen. Die öffentlichen
Einstiege, Betriebswerte, Fehlergrenzen und zulässigen Seiteneffekte bleiben
gleich.
