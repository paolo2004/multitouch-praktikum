import math

def distance(p1, p2):
    """Euklidischer Abstand zwischen zwei Punkten (x, y)."""
    x1, y1 = p1
    x2, y2 = p2
    return math.hypot(x1 - x2, y1 - y2)


def update_tracks(old_tracks, centers, next_id, max_dist, max_missed):
    """
    old_tracks: dict {id: (x, y, missed)} vom letzten Frame
    missed = wie viele Frames in Folge der Track keinen Blob hatte
    centers:    Liste [(x, y), ...] vom aktuellen Frame
    max_dist:   maximaler Abstand für "derselbe Finger"
    max_missed: so viele Frames darf ein Track fehlen, bevor er gelöscht wird
    Rückgabe:   (new_tracks, next_id)
    """
    new_tracks = {}
    used = set()  # Indizes der centers, die schon eine ID bekommen haben

    # 1. Alle möglichen Paare sammeln: (Abstand, alte ID, Index des neuen Blobs)
    pairs = []
    for old_id, (ox, oy, _) in old_tracks.items():
        for i, p in enumerate(centers):
            d = distance((ox, oy), p)
            if d <= max_dist:
                pairs.append((d, old_id, i))

    # 2. Sortieren: kleinster Abstand zuerst
    pairs.sort()

    # 3. Zuweisen (Touch Move): alte ID bleibt, Position ist neu, Zähler auf 0
    for d, old_id, i in pairs:
        if old_id in new_tracks or i in used:
            continue
        x, y = centers[i]
        new_tracks[old_id] = (x, y, 0)
        used.add(i)

    # 4. Tracks ohne Partner: noch nicht löschen, nur Zähler erhöhen
    #    Erst wenn missed >= max_missed ist, wird der Track weggelassen (Touch Up)
    for old_id, (ox, oy, missed) in old_tracks.items():
        if old_id not in new_tracks and missed < max_missed:
            new_tracks[old_id] = (ox, oy, missed + 1)

    # 5. Neue IDs für alle centers ohne Partner (Touch Down)
    for i, (x, y) in enumerate(centers):
        if i not in used:
            new_tracks[next_id] = (x, y, 0)
            next_id += 1

    return new_tracks, next_id

if __name__ == "__main__":
    # Test mit den Werten aus Folie 6
    print(distance((650, 70), (680, 120)))   # erwartet: ca. 58.31
    print(distance((650, 70), (600, 90)))    # erwartet: ca. 53.85

