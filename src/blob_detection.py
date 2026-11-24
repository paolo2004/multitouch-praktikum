import cv2
import time
from pathlib import Path
import numpy as np
from blob_tracking import update_tracks
from tuio_sender import create_server, send_tracks, clear

# --- Parameter der Pipeline (Startwerte der Trackbars) ---
BLUR_KERNEL = 15
SMOOTH_KERNEL = 5
THRESHOLD = 10
MIN_AREA = 2
MAX_DIST = 60
MAX_MISSED = 3              # so viele Frames darf ein Finger fehlen (bei 10 FPS = 300 ms)
NB_FRAMES = 20              # Anzahl Frames für das Hintergrundbild
FIRST_ID = 1                # erste vergebene Blob-ID
MIN_KERNEL = 1              # Kernel 0 führt bei cv2.blur zu einem Fehler

# --- Maximalwerte der Trackbars ---
BLUR_MAX = 101
SMOOTH_MAX = 31
THRESHOLD_MAX = 255
MIN_AREA_MAX = 500

# --- Bildverarbeitung ---
WHITE = 255                 # Wert für "weiß" im Binärbild (uint8)
MIN_ELLIPSE_POINTS = 5      # fitEllipse braucht mindestens 5 Punkte
HIERARCHY_PARENT = 3        # Index des Eltern-Elements in hierarchy[0][i]
NO_PARENT = -1              # kein Eltern-Element -> äußere Kontur

# --- Fenster ---
MAIN_WINDOW = "multi-touch"
PARAM_WINDOW = "parameter"
WINDOW_WIDTH = 720
WINDOW_HEIGHT = 480

# --- Farben (BGR) ---
RED = (0, 0, 255)
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)
WHITE_BGR = (255, 255, 255)

# --- Zeichnen ---
ELLIPSE_THICKNESS = 2
CENTER_RADIUS = 2
CONTOUR_THICKNESS = 1
FONT = cv2.FONT_HERSHEY_PLAIN
FONT_SCALE = 1
FONT_THICKNESS = 1
ID_OFFSET_X = 8             # ID-Text rechts neben dem Blob
ID_OFFSET_Y = -8            # ID-Text über dem Blob
TEXT_POS_FRAME = (0, 15)    # Position "frame #..."
TEXT_POS_TIME = (0, 30)     # Position "time per frame..."

# --- Ablauf und Tasten ---
FRAME_DELAY_MS = 50       # Wartezeit pro Frame in waitKey
KEY_ESC = 27
KEY_PAUSE = ord('p')
DEBUG_FRAME = 100           # Frame, für den Debug-Infos ausgegeben werden

VIDEO_PATH = Path(__file__).parent.parent / "Video" / "mt_camera_raw.AVI"

# open video stream
# cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) # open camera
cap = cv2.VideoCapture(str(VIDEO_PATH), cv2.CAP_FFMPEG)  # open video file (complete PATH might be needed!)
if not cap.isOpened():
    print('Unable to load the video, please check path and filename!')
    quit()

def to_gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

def make_background(cap, nb_frames):
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    summe = None
    for i in range(nb_frames):
        success, frame = cap.read()
        if not success:
            break
        gray = to_gray(frame).astype(np.float32)
        if summe is None:
            summe = np.zeros_like(gray)
        summe += gray
    background = summe / nb_frames
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return background.astype(np.uint8)

def substract_background(gray, background):
    """Differenzbild: |gray - background|, Typ uint8."""
    return cv2.absdiff(background, gray)

def highpass(img, ksize):
    """Entfernt große, gleichmäßige Flächen. Kleine helle Details bleiben."""
    blurred = cv2.blur(img, (ksize,ksize))
    return cv2.absdiff(img, blurred)

def binarize(img, thresh):
    """Graustufenbild -> Binärbild (nur 0 und 255)."""
    _, binary = cv2.threshold(img, thresh, WHITE, cv2.THRESH_BINARY)
    return binary

def find_contours(binary):
    """Binärbild -> nur äußere Konturen (keine Löcher)."""
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:        # keine Konturen im Bild
        return []
    outer = []
    for i, c in enumerate(contours):
        parent = hierarchy[0][i][HIERARCHY_PARENT]
        if parent == NO_PARENT:  # kein Eltern-Element -> äußere Kontur
            outer.append(c)
    return outer

def filter_blobs(contours, min_area):
    """Behält nur Konturen, die groß genug sind und genug Punkte haben."""
    blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area >= min_area and len(c) >= MIN_ELLIPSE_POINTS:
            blobs.append(c)
    return blobs

def blob_info(contour):
    """Kontur -> Mittelpunkt (x, y), Größe (Breite, Höhe), Winkel."""
    (cx, cy), (w, h), angle = cv2.fitEllipse(contour)
    return (cx, cy), (w, h), angle


def get_centers(blobs):
    """Liste von Konturen -> Liste von Mittelpunkten [(x, y), ...]."""
    centers = []
    for c in blobs:
        (cx, cy), _, _ = blob_info(c)
        centers.append((cx, cy))
    return centers

def draw_blob(image, contour):
    """Zeichnet Ellipse und Mittelpunkt eines Blobs ins Bild."""
    ellipse = cv2.fitEllipse(contour)
    (cx, cy), (w, h), angle = ellipse
    cv2.ellipse(image, ellipse, RED, ELLIPSE_THICKNESS)                      # rote Ellipse
    cv2.circle(image, (int(cx), int(cy)), CENTER_RADIUS, BLUE, cv2.FILLED)   # blauer Punkt in der Mitte

def nothing(x):
    """Leere Funktion. createTrackbar braucht eine, wir brauchen sie nicht."""
    pass

def create_trackbars():
    """Erstellt ein Fenster mit einem Schieberegler pro Parameter."""
    cv2.namedWindow(PARAM_WINDOW)
    cv2.createTrackbar("blur",      PARAM_WINDOW, BLUR_KERNEL,   BLUR_MAX,      nothing)
    cv2.createTrackbar("smooth",    PARAM_WINDOW, SMOOTH_KERNEL, SMOOTH_MAX,    nothing)
    cv2.createTrackbar("threshold", PARAM_WINDOW, THRESHOLD,     THRESHOLD_MAX, nothing)
    cv2.createTrackbar("min_area",  PARAM_WINDOW, MIN_AREA,      MIN_AREA_MAX,  nothing)

def read_trackbars():
    """Liest die aktuellen Werte der Schieberegler."""
    blur      = max(MIN_KERNEL, cv2.getTrackbarPos("blur", PARAM_WINDOW))
    smooth    = max(MIN_KERNEL, cv2.getTrackbarPos("smooth", PARAM_WINDOW))
    threshold = cv2.getTrackbarPos("threshold", PARAM_WINDOW)
    min_area  = cv2.getTrackbarPos("min_area", PARAM_WINDOW)
    return blur, smooth, threshold, min_area

def draw_ids(image, tracks):
    """Schreibt die ID neben jeden sichtbaren Blob (gelb)."""
    for blob_id, (x, y, missed) in tracks.items():
        if missed > 0:
            continue
        cv2.putText(image, str(blob_id), (int(x) + ID_OFFSET_X, int(y) + ID_OFFSET_Y),
                    FONT, FONT_SCALE, YELLOW, FONT_THICKNESS)

def run():

    frame_time_ms = 0
    tracks = {}
    next_id = FIRST_ID
    frame_counter = 0

    # create window and make it full-screen capable, set to 720p default
    cv2.namedWindow(MAIN_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(MAIN_WINDOW, WINDOW_WIDTH, WINDOW_HEIGHT)

    background = make_background(cap, NB_FRAMES)
    create_trackbars()
    server = create_server()
    cursors = {}

    # loop through the video frames
    while True:

        # start time
        frame_time_start = time.time()

        # if the last frame of the video is reached, reset the frame_counter and start again
        if frame_counter == cap.get(cv2.CAP_PROP_FRAME_COUNT):
            frame_counter = 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            tracks = {}
            next_id = FIRST_ID
            clear(server, cursors)

        success, frame = cap.read()

        if success:
            blur_k, smooth_k, thresh, min_area = read_trackbars()
            height, width = frame.shape[:2]
            # make a copy of the original frame
            image = frame.copy()
            gray = to_gray(image)
            diff = substract_background(gray, background)
            #cv2.imshow("diff", diff)

            hp = highpass(diff, blur_k)
            smooth = cv2.blur(hp, (smooth_k, smooth_k))
            #cv2.imshow("highpass", hp)
            #cv2.imshow("highpass x4", cv2.convertScaleAbs(hp, alpha=4))  # nur zum Anschauen

            binary = binarize(smooth, thresh)
            #cv2.imshow("binary", binary)

            contours = find_contours(binary)
            blobs = filter_blobs(contours, min_area)
            centers = get_centers(blobs)
            tracks, next_id = update_tracks(tracks, centers, next_id, MAX_DIST,MAX_MISSED)
            send_tracks(server,cursors, tracks, width, height)
            draw_ids(image, tracks)
            cv2.drawContours(image, contours, -1, GREEN, CONTOUR_THICKNESS)  # alle Konturen: grün (-1 = alle zeichnen)
            for c in blobs:
                draw_blob(image, c)

            if frame_counter == DEBUG_FRAME:
                print("diff max:", diff.max(), " diff mean:", round(diff.mean(), 2))
                print("smooth max:", smooth.max())
                print("Anzahl Konturen:", len(contours))
                flaechen = sorted([cv2.contourArea(c) for c in contours], reverse=True)
                print("Flächen:", flaechen)
                print("Mittelpunkte:", centers)
                print("Anzahl Blobs:", len(blobs))
                for c in blobs:
                    (cx, cy), (w, h), angle = blob_info(c)
                    print(f"x={cx:.0f}  y={cy:.0f}  w={w:.1f}  h={h:.1f}  Winkel={angle:.0f}")
                #cv2.waitKey(0)

                # show framecounter and frametime
            cv2.putText(image, "frame #" + str(frame_counter), TEXT_POS_FRAME, FONT, FONT_SCALE,
                        WHITE_BGR, FONT_THICKNESS, cv2.LINE_8)
            cv2.putText(image, "time per frame: " + str(frame_time_ms) + "ms", TEXT_POS_TIME, FONT, FONT_SCALE,
                        WHITE_BGR, FONT_THICKNESS, cv2.LINE_8)

            # display frame
            cv2.imshow(MAIN_WINDOW, image)

            # need this!
            k = cv2.waitKey(FRAME_DELAY_MS)
            if k == KEY_ESC:  # Esc key to stop
                break
            if k == KEY_PAUSE:  # Taste für Pause
                cv2.waitKey(0)

            # count the frame
            frame_counter += 1

            # calculate time in milliseconds
            frame_time_ms = round((time.time() - frame_time_start) * 1000)

if __name__ == '__main__':
    run()
    cv2.destroyAllWindows()