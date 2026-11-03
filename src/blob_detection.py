import cv2
import time
from pathlib import Path
import numpy as np

BLUR_KERNEL = 15
SMOOTH_KERNEL = 5
THRESHOLD = 10
MIN_AREA = 15
PARAM_WINDOW = "parameter"

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
    _, binary = cv2.threshold(img, thresh, 255, cv2.THRESH_BINARY)
    return binary

def find_contours(binary):
    """Binärbild -> nur äußere Konturen (keine Löcher)."""
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:        # keine Konturen im Bild
        return []
    outer = []
    for i, c in enumerate(contours):
        parent = hierarchy[0][i][3]
        if parent == -1:         # -1 = kein Eltern-Element -> äußere Kontur
            outer.append(c)
    return outer

def filter_blobs(contours, min_area):
    """Behält nur Konturen, die groß genug sind und genug Punkte haben."""
    blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area >= min_area and len(c) >= 5 :
            blobs.append(c)
    return blobs

def blob_info(contour):
    """Kontur -> Mittelpunkt (x, y), Größe (Breite, Höhe), Winkel."""
    (cx, cy), (w, h), angle = cv2.fitEllipse(contour)
    return (cx, cy), (w, h), angle

def draw_blob(image, contour):
    """Zeichnet Ellipse und Mittelpunkt eines Blobs ins Bild."""
    ellipse = cv2.fitEllipse(contour)
    (cx, cy), (w, h), angle = ellipse
    cv2.ellipse(image, ellipse, (0, 0, 255), 2)                   # rote Ellipse
    cv2.circle(image, (int(cx), int(cy) ), 2, (255, 0, 0), -1)            # blauer Punkt in der Mitte

def nothing(x):
    """Leere Funktion. createTrackbar braucht eine, wir brauchen sie nicht."""
    pass

def create_trackbars():
    """Erstellt ein Fenster mit einem Schieberegler pro Parameter."""
    cv2.namedWindow(PARAM_WINDOW)
    cv2.createTrackbar("blur",      PARAM_WINDOW, BLUR_KERNEL,   101, nothing)
    cv2.createTrackbar("smooth",    PARAM_WINDOW, SMOOTH_KERNEL,  31, nothing)
    cv2.createTrackbar("threshold", PARAM_WINDOW, THRESHOLD,     255, nothing)
    cv2.createTrackbar("min_area",  PARAM_WINDOW, MIN_AREA,      500, nothing)

def read_trackbars():
    """Liest die aktuellen Werte der Schieberegler."""
    blur      = max(1, cv2.getTrackbarPos("blur", PARAM_WINDOW))
    smooth    = max(1, cv2.getTrackbarPos("smooth", PARAM_WINDOW))
    threshold = cv2.getTrackbarPos("threshold", PARAM_WINDOW)
    min_area  = cv2.getTrackbarPos("min_area", PARAM_WINDOW)
    return blur, smooth, threshold, min_area

def run():
    # time
    frame_time_start = 0
    frame_time_ms = 0

    # framecounter
    frame_counter = 0

    # create window and make it full-screen capable, set to 720p default
    cv2.namedWindow("multi-touch", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("multi-touch", 720, 480)

    background = make_background(cap, 20)
    create_trackbars()

    # loop through the video frames
    while True:

        # start time
        frame_time_start = time.time()

        # if the last frame of the video is reached, reset the frame_counter and start again
        if frame_counter == cap.get(cv2.CAP_PROP_FRAME_COUNT):
            frame_counter = 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        success, frame = cap.read()

        if success:
            blur_k, smooth_k, thresh, min_area = read_trackbars()

            # make a copy of the original frame
            image = frame.copy()
            gray = to_gray(image)
            diff = substract_background(gray, background)
            cv2.imshow("diff", diff)

            hp = highpass(diff, blur_k)
            smooth = cv2.blur(hp, (smooth_k, smooth_k))
            cv2.imshow("highpass", hp)
            #cv2.imshow("highpass x4", cv2.convertScaleAbs(hp, alpha=4))  # nur zum Anschauen

            binary = binarize(smooth, thresh)
            cv2.imshow("binary", binary)

            contours = find_contours(binary)
            blobs = filter_blobs(contours, min_area)
            cv2.drawContours(image, contours, -1, (0, 255, 0), 1)  # alle Konturen: grün
            for c in blobs:
                draw_blob(image, c)

            if frame_counter == 100:
                print("diff max:", diff.max(), " diff mean:", round(diff.mean(), 2))
                print("smooth max:", smooth.max())
                print("Anzahl Konturen:", len(contours))
                flaechen = sorted([cv2.contourArea(c) for c in contours], reverse=True)
                print("Flächen:", flaechen)
                print("Anzahl Blobs:", len(blobs))
                for c in blobs:
                    (cx, cy), (w, h), angle = blob_info(c)
                    print(f"x={cx:.0f}  y={cy:.0f}  w={w:.1f}  h={h:.1f}  Winkel={angle:.0f}")
            #cv2.waitKey(0)
            if frame_counter == 0:
                print("shape:", image.shape)
                print("dtype:", image.dtype)

                # show framecounter and frametime
            cv2.putText(image, "frame #" + str(frame_counter), (0, 15), cv2.FONT_HERSHEY_PLAIN, 1, (255, 255, 255), 1,
                        cv2.LINE_8)
            cv2.putText(image, "time per frame: " + str(frame_time_ms) + "ms", (0, 30), cv2.FONT_HERSHEY_PLAIN, 1,
                        (255, 255, 255), 1, cv2.LINE_8)

            # display frame
            cv2.imshow("multi-touch", image)

            # need this!
            k = cv2.waitKey(50)
            if k == 27:  # Esc key to stop
                break;
            if k == ord('p'):  # Taste für Pause
                cv2.waitKey(0)

            # count the frame
            frame_counter += 1

            # calculate time in milliseconds
            frame_time_ms = round((time.time() - frame_time_start) * 1000)

if __name__ == '__main__':
    run()
    cv2.destroyAllWindows()