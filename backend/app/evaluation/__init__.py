"""
Evaluation harness for Phase 3: run VigiTrack's ownership FSM and a naive
stationary-timer baseline over the same labelled clips, then score both
(false alarms per hour, recall, detection latency).

Entry points:
    python -m app.evaluation.cli evaluate            # built-in synthetic set
    python -m app.evaluation.cli evaluate a.json b.json
    python -m app.evaluation.cli synthetic --out dir # write the synthetic set
    python -m app.evaluation.cli record-video --video clip.mp4 --out clip.json
    python -m app.evaluation.cli benchmark           # camera FPS on this PC
    python -m app.evaluation.cli soak --url rtsp://... --hours 2
"""
