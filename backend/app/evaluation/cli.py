"""
Command-line entry points for the Phase 3 evaluation.

Run from the backend folder, e.g.:
    python -m app.evaluation.cli evaluate
    python -m app.evaluation.cli evaluate data/eval/my_clip.json
    python -m app.evaluation.cli synthetic --out data/eval
    python -m app.evaluation.cli record-video --video clip.mp4 --out data/eval/clip.json
    python -m app.evaluation.cli benchmark --seconds 30
    python -m app.evaluation.cli soak --url rtsp://user:pass@cam/stream1 --hours 2

record-video, benchmark and soak need the model/camera (ultralytics, OpenCV) and are
only run on the machine with the camera. evaluate/synthetic are pure Python.
"""

import argparse
import json
import sys


def cmd_evaluate(args) -> int:
    from app.evaluation.evaluate import evaluate_scenarios, format_report, load_scenario

    if args.files:
        scenarios = [load_scenario(p) for p in args.files]
    else:
        from app.evaluation.synthetic import build_synthetic_set
        scenarios = build_synthetic_set()
        print("(no files given: using the built-in synthetic scenario set)\n")

    results = evaluate_scenarios(scenarios,
                                 distance_threshold=args.distance,
                                 time_threshold=args.time_threshold)
    print(format_report(results))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
        print(f"\nDetailed results written to {args.json_out}")
    return 0


def cmd_synthetic(args) -> int:
    import os
    from app.evaluation.evaluate import save_scenario
    from app.evaluation.synthetic import build_synthetic_set

    os.makedirs(args.out, exist_ok=True)
    for sc in build_synthetic_set():
        path = os.path.join(args.out, f"{sc['name']}.json")
        save_scenario(sc, path)
        print(f"wrote {path}")
    return 0


def cmd_record_video(args) -> int:
    """Runs the real detector + ByteTrack over a video and dumps per-frame detections."""
    import cv2
    from app.detection.detector import ObjectDetector

    source = int(args.video) if args.video.isdigit() else args.video
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"ERROR: could not open {args.video}", file=sys.stderr)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    detector = ObjectDetector()

    frames = []
    max_seconds = args.max_seconds or float("inf")
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok or idx / fps >= max_seconds:
            break
        dets = detector.detect_and_track(frame)
        frames.append({
            "t": round(idx / fps, 3),
            "dets": [{"id": d["id"], "class_name": d["class_name"],
                      "box": [round(b, 1) for b in d["box"]]} for d in dets],
        })
        idx += 1
        if idx % 300 == 0:
            print(f"  {idx} frames ({idx / fps:.0f} s)...")
    cap.release()

    if not frames:
        print("ERROR: no frames read.", file=sys.stderr)
        return 1

    scenario = {
        "name": args.name or ("clip_" + str(abs(hash(args.video)) % 100000)),
        "fps": fps,
        "description": f"Recorded from {args.video}. Add ground-truth 'events' before evaluating.",
        "events": [],
        "frames": frames,
    }
    from app.evaluation.evaluate import save_scenario
    save_scenario(scenario, args.out)
    print(f"\nRecorded {len(frames)} frames ({frames[-1]['t']:.1f} s at {fps:.1f} fps) to {args.out}")
    print("Now add ground-truth events, e.g.:")
    print('  "events": [{"label": "unattended", "start": 13.6, "end": 45.0, "bag_id": 2}]')
    print(f"Then score it with: python -m app.evaluation.cli evaluate {args.out}")
    return 0


def cmd_benchmark(args) -> int:
    """Measures detection + monitor frame rate on this machine (NFR-01, NFR-02)."""
    import time
    import cv2
    from app.detection.detector import ObjectDetector
    from app.detection.fsm_tracker import AdvancedBaggageMonitor

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"ERROR: could not open camera {args.camera}", file=sys.stderr)
        return 1
    detector = ObjectDetector()
    monitor = AdvancedBaggageMonitor()

    det_ms, total_ms = [], []
    started = time.perf_counter()
    last = started
    while time.perf_counter() - started < args.seconds:
        ok, frame = cap.read()
        if not ok:
            continue
        t0 = time.perf_counter()
        dets = detector.detect_and_track(frame)
        t1 = time.perf_counter()
        monitor.update(dets, now=time.perf_counter())
        t2 = time.perf_counter()
        det_ms.append((t1 - t0) * 1000)
        total_ms.append((t2 - t0) * 1000)
        last = t2
    cap.release()

    elapsed = last - started
    if not det_ms:
        print("ERROR: no frames read.", file=sys.stderr)
        return 1
    det_ms.sort()
    total_ms.sort()

    def pct(vals, p):
        return vals[min(len(vals) - 1, int(len(vals) * p))]

    print(f"Frames processed : {len(det_ms)} in {elapsed:.1f} s")
    print(f"End-to-end FPS   : {len(det_ms) / elapsed:.1f}")
    print(f"Detection ms     : p50 {pct(det_ms, 0.50):.1f}, p95 {pct(det_ms, 0.95):.1f}, max {det_ms[-1]:.1f}")
    print(f"Detection+monitor: p50 {pct(total_ms, 0.50):.1f}, p95 {pct(total_ms, 0.95):.1f} ms")
    print("\nAlert latency in the hub = time threshold (default 10 s after separation) "
          "plus at most one frame interval above.")
    return 0


def cmd_soak(args) -> int:
    """Runs an RTSP (or camera) stream for hours and reports stability (Phase 3 exit test)."""
    import time
    import cv2

    from config.secret_store import redact
    url = redact(args.url)
    started = time.time()
    deadline = started + args.hours * 3600
    frames = 0
    reconnects = 0
    last_report = started

    print(f"Soak test: {url} for {args.hours} h (Ctrl+C to stop early)")
    while time.time() < deadline:
        cap = cv2.VideoCapture(args.url)
        if not cap.isOpened():
            reconnects += 1
            print(f"  [{time.strftime('%H:%M:%S')}] open failed (#{reconnects}), retrying in 5 s")
            time.sleep(5)
            continue
        while time.time() < deadline:
            ok, _ = cap.read()
            if not ok:
                reconnects += 1
                print(f"  [{time.strftime('%H:%M:%S')}] stream lost (#{reconnects}), reconnecting...")
                break
            frames += 1
            if time.time() - last_report >= 60:
                up = time.time() - started
                print(f"  [{time.strftime('%H:%M:%S')}] {frames} frames, "
                      f"{frames / up:.1f} fps, {reconnects} reconnect(s), "
                      f"{up / 60:.0f} min elapsed")
                last_report = time.time()
        cap.release()

    up = time.time() - started
    fps = frames / up if up else 0
    print(f"\nSoak summary: {up / 3600:.2f} h, {frames} frames, {fps:.1f} fps, {reconnects} reconnect(s).")
    ok = frames > 0 and reconnects == 0
    print("RESULT: PASS - ran without a stream interruption" if ok
          else f"RESULT: FAIL - {reconnects} stream interruption(s)")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.evaluation.cli",
                                     description="VigiTrack evaluation harness")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("evaluate", help="score one or more scenario files (default: synthetic set)")
    p.add_argument("files", nargs="*", help="scenario JSON files")
    p.add_argument("--distance", type=float, default=150.0, help="VigiTrack distance threshold (px)")
    p.add_argument("--time-threshold", type=float, default=10.0, help="alert time threshold (s), both methods")
    p.add_argument("--json-out", help="write detailed results to this JSON file")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("synthetic", help="write the built-in synthetic scenario set to a folder")
    p.add_argument("--out", default="data/eval", help="output folder")
    p.set_defaults(func=cmd_synthetic)

    p = sub.add_parser("record-video", help="run the real detector over a video file (or camera index) "
                                            "and dump detections for labelling")
    p.add_argument("--video", required=True, help="video path or camera index (e.g. 0)")
    p.add_argument("--out", required=True, help="output scenario JSON")
    p.add_argument("--name", help="scenario name (default derived from source)")
    p.add_argument("--max-seconds", type=float, help="stop after this many seconds of video")
    p.set_defaults(func=cmd_record_video)

    p = sub.add_parser("benchmark", help="measure detection FPS on this machine (NFR-01)")
    p.add_argument("--camera", type=int, default=0, help="camera index")
    p.add_argument("--seconds", type=float, default=30.0)
    p.set_defaults(func=cmd_benchmark)

    p = sub.add_parser("soak", help="run an RTSP/camera stream for hours and report stability")
    p.add_argument("--url", required=True, help="RTSP URL (or camera index as a string)")
    p.add_argument("--hours", type=float, default=2.0)
    p.set_defaults(func=cmd_soak)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
