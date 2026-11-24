# Verständnisfragen mit Lösungen

## Git

### Warum hat `git switch -c praktikum-2` die nicht committeten Änderungen mitgenommen, statt sie auf `main` zu lassen?

Ein Branch ist nur ein **Zeiger auf einen Commit**. Nicht committete Änderungen gehören zu keinem Branch, sie liegen im **Arbeitsverzeichnis** bzw. im **Index** (Staging-Bereich).
Der neue Branch zeigte auf denselben Commit wie `main`, also musste Git beim Wechsel keine Datei anfassen. Die Änderungen blieben einfach liegen. Erst mit dem Commit gehören sie zum Branch.

---

## Praktikum 2: Blob-Tracking

### 1. Was würde passieren, wenn man die Paare (Abstand, alte ID, neuer Blob) **nicht** sortiert und jedem alten Track einfach seinen nächsten Blob gibt?

Das Ergebnis hängt dann von der **Reihenfolge** der Tracks ab. Der Track, der zuerst drankommt, schnappt sich seinen nächsten Blob, auch wenn dieser Blob zu einem anderen Track viel näher wäre. Der zweite Track bekommt dann einen schlechteren Blob oder gar keinen. Folge: **vertauschte IDs** (Finger A hat plötzlich die ID von Finger B).
Durch die Sortierung wird immer zuerst das global kürzeste Paar zugewiesen.

### 2. Warum werden Tracks mit `missed > 0` in `draw_ids` nicht gezeichnet, aber trotzdem weiter gematcht?

- **Nicht gezeichnet:** Sie wurden im aktuellen Frame nicht gesehen. Es gibt keine aktuelle Position, nur die alte.
- **Weiter gematcht:** Taucht der Finger innerhalb von `MAX_MISSED` Frames in der Nähe wieder auf, bekommt er seine **alte ID zurück** statt einer neuen. Ein kurzes Flackern der Erkennung erzeugt so keinen neuen Touch Down.

---

## Praktikum 3: TUIO

### 1. Was ist der Vorteil, wenn der Tracker die Touches übers Netzwerk an eine andere Anwendung schickt, statt selbst die App zu sein?

- **Trennung von Erkennung und Anwendung:** Der Tracker kümmert sich nur um Kamera, Blobs und IDs. Die App bekommt fertige Touch-Events und muss nichts über die Bildverarbeitung wissen.
- **Unabhängig von Sprache und Plattform:** Jede Anwendung, die TUIO versteht (Java, C++, C#, Python, …), kann die Touches nutzen. Der Tracker muss dafür nicht angepasst werden.
- **Verteilbar:** Tracker und App können auf verschiedenen Rechnern laufen, und mehrere Clients können gleichzeitig zuhören.
- **Austauschbar:** Man kann den Tracker (z. B. eine andere Kamera oder ein anderer Algorithmus) oder die App wechseln, ohne die jeweils andere Seite zu ändern.

### 2. Warum ist es wichtig, die eigene Tracking-ID als `session_id` mitzugeben (Folie 15)?

Die ID-Zuordnung (welcher Finger ist welcher) passiert in **unserem** Tracking (Praktikum 2). Nur so bleibt die `session_id` eines Fingers über alle Frames gleich, und der Client kann `add`, `set` und `remove` korrekt einem Finger zuordnen.
Würde der Server selbst IDs vergeben, ginge die Verbindung zwischen unserem Track und dem TUIO-Cursor verloren, und es wäre nicht mehr klar, welcher Cursor beim nächsten Frame aktualisiert werden muss.

### 3. Sollen Tracks mit `missed > 0` als Cursor weiter gesendet werden?

**Ja**, und zwar an ihrer letzten bekannten Position. Würde man sie sofort entfernen, bekäme der Client bei jedem kurzen Flackern ein `fingerUp` und gleich danach ein `fingerDown`. Das wirkt in der App z. B. wie ein ungewollter Doppelklick oder ein abgebrochener Drag.
Erst wenn der Track nach `MAX_MISSED` Frames wirklich gelöscht wird, wird auch der Cursor entfernt (`fingerUp`). Das ist dieselbe Idee wie die Toleranz in Praktikum 2.

### 4. Warum `width` und `height` aus `frame.shape` und nicht aus `WINDOW_WIDTH` und `WINDOW_HEIGHT`?

Die Blob-Koordinaten `x` und `y` sind Pixel im **Kamerabild**. Teilen muss man durch die Größe des Koordinatensystems, aus dem die Werte stammen. Das Fenster zeigt das Bild nur skaliert an.
Würde man durch die Fenstergröße teilen, die vom Video abweicht, käme ein Finger am rechten Rand nie auf 1.0, und beim Vergrößern des Fensters wären die Werte falsch.
Achtung: `frame.shape` liefert `(höhe, breite, kanäle)`.

### 5. Warum steht in `send_tracks` `for blob_id in list(cursors):` und nicht `for blob_id in cursors:`?

Man darf ein Dict **nicht verändern, während man darüber iteriert**:

```python
for blob_id in cursors:
    cursors.pop(blob_id)
# RuntimeError: dictionary changed size during iteration
```

`list(cursors)` erstellt vorher eine **Kopie der Schlüssel**. Die Schleife läuft über diese Kopie, und im echten Dict kann man gefahrlos löschen. (`pop` selbst funktioniert auf einem Dict problemlos.)

### 6. Ist `cursors` beim Aufruf von `send_tracks` leer?

Nur im **ersten Frame** und direkt nach `clear(...)`. `cursors = {}` steht **vor** der Schleife, es ist also jeden Frame **dasselbe Dict**.
Python übergibt eine **Referenz auf das Objekt**, keine Kopie. Was `send_tracks` mit `cursors[blob_id] = cursor` oder `cursors.pop(blob_id)` ändert, sieht auch `run()`. Das Dict ist das Gedächtnis zwischen den Frames: Es merkt sich, welche Cursor schon existieren.

| Frame | `cursors` beim Aufruf | `send_tracks` macht | danach |
|---|---|---|---|
| 1 | `{}` | `Cursor(1)` anlegen (fingerDown) | `{1: Cursor}` |
| 2 | `{1: Cursor}` | nur `position` setzen (fingerMoved) | `{1: Cursor}` |
| n | `{1: Cursor}` | Track weg: `pop` (fingerUp) | `{}` |

Anders bei `tracks`: `update_tracks` baut ein **neues** Dict und gibt es zurück. Deshalb ist die Zuweisung `tracks, next_id = update_tracks(...)` nötig.

### 7. Was passiert, wenn `send_tracks` am Anfang `cursors = {}` schreibt statt `cursors.clear()`?

`cursors = {}` **bindet nur den lokalen Namen neu**. Das Dict in `run()` bleibt unverändert, also **für immer leer**. Die Folgen:
- fingerUp läuft über ein leeres Dict, und alte Cursor werden **nie** aus `server.cursors` entfernt.
- Jeder Track gilt in jedem Frame als neu, und jedes Mal kommt ein weiterer `Cursor(blob_id)` dazu. `server.cursors` wird dadurch immer größer und enthält doppelte `session_id`s.

**Merksatz:**
- `name = …` ändert nur, worauf der Name zeigt, und wirkt **lokal**.
- `name[...] = …`, `name.pop()`, `name.clear()`, `name.append()` und `obj.attr = …` ändern **das Objekt selbst** und sind überall sichtbar.

### 8. Warum muss `update_tracks` `next_id` zurückgeben?

`int` ist **immutable**. `next_id += 1` in der Funktion erzeugt ein **neues** int-Objekt und bindet den lokalen Namen daran (wie `cursors = {}` oben). `run()` merkt davon nichts, deshalb Rückgabe und neue Zuweisung.

### 9. Was wäre in `clear()` mit `server.cursors = []` bzw. `cursors = {}`?

- **`server.cursors = []` funktioniert.** Das ist eine Zuweisung an ein **Attribut** des gemeinsamen `TuioServer`-Objekts, kein lokaler Name. `send_bundle()` liest `self.cursors` und sendet ein leeres `alive`, also fingerUp für alle.
- **`cursors = {}` geht kaputt.** `run()` behält die alten Einträge, aber `server.cursors` ist leer. Die beiden Strukturen sind **nicht mehr synchron**:
  1. **Absturz:** Eine alte ID steht in `cursors`, aber nicht in `tracks`. Dann scheitert `server.cursors.remove(cursor)` mit `ValueError: list.remove(x): x not in list`.
  2. **Unsichtbarer Finger:** `next_id` beginnt wieder bei `FIRST_ID`. Bekommt ein neuer Track eine alte ID, legt `send_tracks` keinen neuen Cursor an. Es setzt nur `position` auf das alte Objekt, und das wird nie gesendet.

Lehre: `cursors` und `server.cursors` müssen **immer gemeinsam** verändert werden (`pop` + `remove`, `append` + `cursors[...] = cursor`).

### 10. Warum ruft `clear()` am Ende `server.send_bundle()` auf?

Damit der Client **sofort** ein leeres `alive` bekommt und für alle Finger ein fingerUp auslöst. So ist klar: Das alte Video ist vorbei.
- **Ohne Finger nach dem Neustart:** Ohne diesen Aufruf passiert kaum etwas Schlimmes. `send_tracks` sendet im selben Schleifendurchlauf ein Bundle mit leerem `alive`. Die Cursor verschwinden also nur einen Frame später.
- **Der eigentliche Fall:** Nach dem Neustart vergibt `update_tracks` wieder IDs ab `FIRST_ID`. Ist im ersten Frame schon ein Finger da und bekommt eine ID, die vorher benutzt wurde, sieht der Client **dieselbe `session_id`** weiter im `alive`. Er erkennt kein fingerUp/fingerDown, sondern ein fingerMoved: Der Cursor **springt** von der alten an die neue Position. In der App sieht das z. B. wie ein riesiger Drag aus.
  Das zusätzliche Bundle trennt beide Durchläufe sauber, weil der Client zwischendurch einmal „keine Finger“ sieht.
