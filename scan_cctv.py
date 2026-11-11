import cv2


def scan_cameras(max_indices=6):
    print("=" * 60)
    print("  VigiTrack: Video Device & Camera Scanner")
    print("=" * 60)
    print(f"Scanning indices 0 to {max_indices - 1} via cv2.CAP_DSHOW...\n")

    found = []
    for idx in range(max_indices):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            ret, _ = cap.read()
            status = "Working (Frame read OK)" if ret else "Opened (No frame)"
            print(f"  [Index {idx}] AVAILABLE -> {w}x{h} @ {fps:.1f} FPS ({status})")
            found.append(idx)
            cap.release()
        else:
            print(f"  [Index {idx}] Not available")

    print("\n" + "=" * 60)
    if found:
        print(f"Found active camera devices at indices: {found}")
        print("Note: Index 0 is typically your built-in laptop webcam.")
        print("      Index 1 or 2 is typically OBS Virtual Camera or external USB camera.")
    else:
        print("No camera devices detected. Check Windows camera privacy permissions.")
    print("=" * 60)


if __name__ == "__main__":
    scan_cameras()
