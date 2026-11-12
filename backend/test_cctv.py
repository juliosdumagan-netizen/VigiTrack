import sys
import time
import cv2


def test_source(source=1):
    print("=" * 60)
    print(f"  VigiTrack: CCTV / Virtual Camera Test (Source: {source})")
    print("=" * 60)

    # Convert numeric strings to int
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    print(f"[CCTV Test] Attempting to open source {source}...")
    if isinstance(source, int):
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(source)
    else:
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[FAIL] Could not connect to source {source}.")
        print("Tips:")
        print("  - If testing OBS Virtual Camera: Make sure 'Start Virtual Camera' is clicked in OBS.")
        print("  - If testing an IP camera: Check the RTSP URL, IP, and Wi-Fi network.")
        return False

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[SUCCESS] Connected! Resolution: {width}x{height} | Reported FPS: {fps}")
    print("Press 'Q' or 'ESC' to exit the test preview.\n")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[Warning] Missed frame from CCTV source...")
            time.sleep(0.05)
            continue

        cv2.putText(frame, f"CCTV Source: {source} ({width}x{height})", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow(f"VigiTrack - CCTV Source {source} Test", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), ord('Q'), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[CCTV Test] Test ended.")
    return True


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else 1
    test_source(src)
