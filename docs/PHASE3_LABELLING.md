# Phase 3: Real-footage labelling protocol

This is the manual step behind the Phase 3 exit test: a table of false alarms per hour and recall for VigiTrack and the stationary-timer baseline, on the same real clips.

Run the recording on the machine with the camera. The commands are run from the `backend` folder with the venv active.

## 1. Set up the scene

- Use the camera you will deploy with (USB webcam or RTSP camera), mounted where it will be used.
- Use a fixed camera position. Do not move it between clips.
- Use the default settings: distance threshold 150 px, time threshold 10 s. Record the values shown on the Dashboard before you start.
- Check the Dashboard shows "Online" before recording.

## 2. Record the five scenarios

Each scenario is one clip. Record each clip in one take, with the people and bag doing the actions below. Times are approximate: write down the real time the owner stops being near the bag, as this is your ground truth.

| # | Scenario | What happens | Duration | Expected label |
|---|---|---|---|---|
| 1 | `seated_reader` | Owner sits beside a bag for the whole clip. | 3 min | No unattended event |
| 2 | `owner_walks_away` | Owner stands and walks away, staying in frame. Bag stays. | 2 min | Unattended from when the owner passes the distance threshold |
| 3 | `owner_leaves_frame` | Owner walks out of frame, leaving the bag. | 2 min | Unattended from when the owner leaves frame |
| 4 | `passer_by` | Owner sits beside the bag. A stranger walks past, close to it. | 3 min | No unattended event |
| 5 | `abandoned_bag` | Owner carries the bag in, puts it down, and walks off. | 2 min | Unattended from when the owner walks away |

Add one more clip per scenario if time allows: another person, lighting, or bag. The more clips, the more reliable the false-alarm rate.

**Why the longer seated clips matter:** false alarms come from background time, so the seated and passer-by clips carry most of the false-alarm measurement. Three minutes is the minimum; ten minutes is better.

Record each clip as an MP4 file, for example `data/eval/seated_reader_1.mp4`.

## 3. Turn each clip into a scenario file

```
python -m app.evaluation.cli record-video --video data/eval/seated_reader_1.mp4 --out data/eval/seated_reader_1.json --annotated-out data/eval/seated_reader_1_annotated.mp4
```

For a live camera, use the camera index instead of a file (for example `--video 0`).

This runs the real detector over the clip and writes the detections. It runs at the detector's own speed, which is not yet measured on this PC; it may take longer than the clip itself. Note the time it takes for the first clip.

The annotated MP4 shows the clip time (`t=12.30s`) and each track's ID (`backpack #2`). Use it to find the bag ID and the times for step 4.

## 4. Add the ground truth

Open each `.json` file and set `events`. Use the annotated video to find:

- `bag_id`: the ID shown on the bag in the annotated video.
- `start`: the clip time when the bag became unattended, as defined in step 2. For scenarios 2 and 3 this is when the owner first went beyond the distance threshold, or left the frame.
- `end`: the clip time when the bag is picked up or the clip ends.

Scenario 1 and 4 have no events: leave `"events": []`.

Example for scenario 5:

```json
"events": [{"label": "unattended", "start": 19.1, "end": 120.0, "bag_id": 2}]
```

Write down the rule you used for `start` in a notes file next to the clips, so the labels can be checked later.

## 5. Evaluate

```
python -m app.evaluation.cli evaluate data/eval/seated_reader_1.json data/eval/owner_walks_away_1.json data/eval/owner_leaves_frame_1.json data/eval/passer_by_1.json data/eval/abandoned_bag_1.json --json-out data/eval/results.json
```

This prints one row per scenario and method, and totals for each method. Copy the totals into the table below for the defense handbook.

## 6. Results

Fill this in after step 5. Record the date, the camera, the hours of footage, and the threshold settings.

| Method | Events | Detected | Recall | False alarms | FA per hour | Mean latency (s) |
|---|---|---|---|---|---|---|
| VigiTrack | | | | | | |
| Stationary timer | | | | | | |

Footage: ___ hours in ___ clips. Camera: ___. Date: ___. Thresholds: distance ___ px, time ___ s.

## Rules for the result

- Report the numbers from real footage only. Do not mix them with the synthetic results in `app/evaluation/synthetic.py`.
- A few minutes of footage gives very noisy false-alarm rates. Say how many hours it covers next to the rate.
- If a clip was recorded with a changed setting, say so, and keep it in a separate row.
