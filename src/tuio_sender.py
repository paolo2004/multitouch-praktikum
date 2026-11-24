from pythontuio import TuioServer, Cursor

TUIO_IP = "127.0.0.1"
TUIO_PORT = 3333
NORM_MIN = 0.0
NORM_MAX = 1.0

def normalize(x, y, width, height):
    """Pixelkoordinaten -> TUIO-Koordinaten im Bereich 0..1."""
    nx = x / width
    ny = y / height
    # Sicherheitshalber begrenzen (fitEllipse kann knapp außerhalb liegen)
    #nx = min(max(nx, NORM_MIN), NORM_MAX)
    #ny = min(max(ny, NORM_MIN), NORM_MAX)
    return nx, ny

def create_server():
    """Erstellt den TUIO-Server (sendet per UDP an ip:port)."""
    return TuioServer(TUIO_IP, TUIO_PORT)

def send_tracks(server, cursors, tracks, width, height):
    """
    Gleicht die TUIO-Cursor mit den Tracks ab und sendet ein Bundle.
    server:  TuioServer
    cursors: dict {blob_id: Cursor}, wird hier verändert
    tracks:  dict {blob_id: (x, y, missed)} aus update_tracks
    width, height: Größe des Kamerabildes in Pixeln
    """
    # 1. fingerUp: Cursor, deren Track gelöscht wurde, entfernen
    for blob_id in list(cursors):        # list(), weil wir im Loop löschen
        if blob_id not in tracks:
            cursor = cursors.pop(blob_id)
            server.cursors.remove(cursor)

    # 2. fingerDown / fingerMoved
    for blob_id, (x, y, missed) in tracks.items():
        if blob_id not in cursors:       # neuer Finger
            cursor = Cursor(blob_id)     # eigene ID als session_id
            server.cursors.append(cursor)
            cursors[blob_id] = cursor
        cursors[blob_id].position = normalize(x, y, width, height)

    # 3. Jeden Frame senden (alive + set + fseq)
    server.send_bundle()


def clear(server, cursors):
    """Alle Cursor entfernen, z. B. beim Neustart des Videos."""
    server.cursors.clear()
    cursors.clear()
    server.send_bundle()