# VigiTrack — Capstone Study Guide & Progress README

> **VigiTrack: AI-Based Unattended Object Detection and Monitoring System Using Computer Vision**
> Academic Year 2025–2026 · Author/Module owner: Gary Luis Alquiza
>
> This README brings together **everything discussed, built and decided** across our capstone conversations, so you can study it in one place.
> I checked every number and name in it against the **current source code** in `C:\Users\garya\Desktop\VigiTrack` (as of Nov 11, 2026).
> Where an earlier answer or the PDF handbook got something wrong, the correction is in [Section 16](#16-fact-check-corrections-to-earlier-answers--the-pdf-handbook).

---

## Table of Contents
1. [The System in 10 Seconds](#1-the-system-in-10-seconds)
2. [Progress Timeline — What Has Been Done](#2-progress-timeline--what-has-been-done)
3. [Project Structure (Every File Explained)](#3-project-structure-every-file-explained)
4. [How the Whole System Works (Simple → Technical)](#4-how-the-whole-system-works-simple--technical)
5. [Where AI Is Used (and Where It Is Not)](#5-where-ai-is-used-and-where-it-is-not)
6. [Detection Layer — `detector.py`](#6-detection-layer--detectorpy)
7. [Person-Object Association & the 6-State FSM — `fsm_tracker.py`](#7-person-object-association--the-6-state-fsm--fsm_trackerpy)
8. [Supporting Subsystems (Camera, Display Pipeline, Database, Alerts, Settings, API)](#8-supporting-subsystems)
9. [CCTV Integration (Sir Serge's Questions)](#9-cctv-integration-sir-serges-questions)
10. [Deployment: Local Edge vs Cloud, and Hardware Tiers](#10-deployment-local-edge-vs-cloud-and-hardware-tiers)
11. [The Contribution of the Study](#11-the-contribution-of-the-study)
12. [Ideas We Evaluated (and the Verdicts)](#12-ideas-we-evaluated-and-the-verdicts)
13. [Secure Design Concept Paper (Submitted Deliverable)](#13-secure-design-concept-paper-submitted-deliverable)
14. [Defense Q&A Cheat Sheet](#14-defense-qa-cheat-sheet)
15. [Glossary (Plain English)](#15-glossary-plain-english)
16. [Fact-Check: Corrections to Earlier Answers & the PDF Handbook](#16-fact-check-corrections-to-earlier-answers--the-pdf-handbook)
17. [Known Limitations (Be Honest About These)](#17-known-limitations-be-honest-about-these)
18. [Pending Work / Next Steps](#18-pending-work--next-steps)
19. [How to Run](#19-how-to-run)
20. [Deliverables & File Locations](#20-deliverables--file-locations)

---

## 1. The System in 10 Seconds

> *"VigiTrack watches CCTV video and detects people and bags. It doesn't look at the bag alone. It links each bag to the person nearest to it. If that person walks away, or leaves the camera view, for longer than a set time (default 10 seconds), it sounds an alarm, shows a warning on screen and saves the incident to a database."*

**Key words to remember:** Detect → Track → Associate → Time → Alert.

---

## 2. Progress Timeline — What Has Been Done

### Phase A — Build & bug-fixing (Oct 8 – Oct 30, conversation `b5d56986…`)
| # | Work done | File(s) |
|---|---|---|
| 1 | Dashboard / incidents / settings pages reviewed. Added HTML escaping (`escapeHtml`), timestamp fixes, fetch error handling and a Refresh button | `app/stream/templates/*.html` |
| 2 | Fixed a JS bug: numbers were sent as strings (`"150"`), which crashed Python with a `TypeError` | `settings.html` |
| 3 | Crash guard for when a person leaves the frame, thread-safe alert list (`threading.Lock`), camera auto-reconnect | `camera_manager.py` |
| 4 | Fixed a **100% CPU spike** in the video generator by adding `time.sleep(0.03)` (~30 FPS pacing) | `routes.py` |
| 5 | Compared old backup (`vigitrack.zip`) with new code. Kept the new one (YOLOv8m on GPU + ByteTrack + FSM) | — |
| 6 | Merged useful old features: **settings saved to disk** (`settings.json`) and **class filtering** (backpack/handbag/suitcase, person always on) | `config/settings_store.py`, `data/settings.json` |
| 7 | Fixed duplicate/split boxes: per-class confidence gates, NMS `iou=0.45` and box de-duplication | `detector.py` |
| 8 | Fixed **false "ABANDONED" while seated next to bag**: changed to centroid-proximity association | `fsm_tracker.py` |
| 9 | Fixed video lag: separate reader thread plus `CAP_PROP_BUFFERSIZE = 1` | `camera_manager.py` |
| 10 | Removed the "Detection Confidence" sliders from the UI | `settings.html` |
| 11 | Rewrote `test_detector.py` to use the production classes, with camera fallback (index 1 → 0) | `test_detector.py` |

### Phase B — Documentation & defense prep (Nov 5 – Nov 11, this conversation)
| Date | Work done |
|---|---|
| Nov 5 | **Secure Design Concept Paper** (3-page PDF) written for your module (`app/stream/`: dashboard, video feed, REST API) |
| Nov 10 | Explained the models used, the owner/person association pipeline, and where OpenCV is used |
| Nov 10 | Reviewed your **background-subtraction idea**. Verdict: keep the current pipeline (see §12) |
| Nov 10 | Answered **Sir Serge's CCTV integration questions** (RTSP, standalone vs plugin, deployment architecture) |
| Nov 10 | Cloud vs local server analysis. Verdict: **local edge server** |
| Nov 10 | **Code change:** `detector.py` now **picks the model to match the hardware** (GPU → `yolov8m.pt`; no GPU → `yolov8n_openvino_model`). Exported `yolov8n` to OpenVINO. **Both modes tested OK** |
| Nov 10 | Hardware tiers renamed to vendor-neutral names ("Dedicated GPU Tier" vs "Standard Office Tier") |
| Nov 10 | Contribution defined. Renamed **"Owner Association" → "Person-Object Association"** |
| Nov 10 | Evaluated fine-tuning YOLOv8 and adding a new class. Verdict: optional. The **single main contribution = Person-Object Association** |
| Nov 11 | **Capstone Defense Handbook PDF** generated (4 pages). ⚠️ Has some errors, see §16 |
| Nov 11 | Clarified that the "video streaming engine" is a **local display pipeline**, not internet streaming |
| Nov 11 | This README |

---

## 3. Project Structure (Every File Explained)

```
VigiTrack/
├── run.py                      ← START HERE. Creates the Flask app, initializes DB, serves on port 5000
├── requirements.txt            ← Python dependencies (⚠️ incomplete — see §18)
├── test_detector.py            ← Desktop test window (cv2.imshow) using the real detector + FSM
├── test_cctv.py                ← Tests if a camera/RTSP source can be opened (python test_cctv.py <source>)
├── scan_cctv.py                ← Scans camera indices 0–5 and reports which ones work
├── yolov8m.pt                  ← YOLOv8 Medium weights (≈52 MB) — Dedicated GPU Tier
├── yolov8n.pt                  ← YOLOv8 Nano weights (≈6.5 MB)
├── yolov8n_openvino_model/     ← Nano converted to Intel OpenVINO — Standard Office Tier
├── config/
│   ├── settings_store.py       ← load_settings() / save_settings() + safe DEFAULTS
│   ├── bytetrack_custom.yaml   ← Tuned ByteTrack parameters
│   └── config.py
├── data/
│   ├── settings.json           ← Saved thresholds, camera source, audio toggle
│   └── vigitrack.db            ← SQLite database (incidents table)
└── app/
    ├── detection/
    │   ├── detector.py         ← AI: YOLOv8 + ByteTrack + filters + ID stabilizer
    │   └── fsm_tracker.py      ← Person-Object Association + 6-state FSM + timer
    ├── stream/
    │   ├── camera_manager.py   ← Orchestrator: reader thread, worker thread, drawing, logging
    │   ├── routes.py           ← Flask pages + REST API + /video_feed
    │   └── templates/          ← dashboard.html, incidents.html, settings.html
    ├── alerts/notifier.py      ← Beep (threaded, rate-limited) + red banner overlay
    ├── database/db.py, models.py ← SQLite connection, schema, insert/read/delete
    └── static/css/             ← Styles
```

---

## 4. How the Whole System Works (Simple → Technical)

### 4.1 The "security guard" analogy
| Step | Guard analogy | What the system does | Tech |
|---|---|---|---|
| 1. Detect | "There's a student and a backpack." | Draws boxes around people & bags | YOLOv8 |
| 2. Track | "That's the same student as before." | Gives each object an ID number that persists | ByteTrack + ID stabilizer |
| 3. Associate | "That backpack is with that student." | Links bag to nearest person within 150 px | Euclidean distance |
| 4. Time | "The student left 10 seconds ago…" | Starts a countdown when the person separates | FSM + timer |
| 5. Alert | "Call it in!" | Beep, red banner, database log, dashboard alert | Notifier, SQLite, Flask |

### 4.2 The "invisible leash" (simplest explanation)
- The system measures the distance between the **center of the bag** and the **center of the nearest person**.
- If the person stays close for a couple of frames, an invisible **leash** ties them together (a random passer-by can't "steal" it afterwards).
- Close = **GREEN** leash, stopwatch at 0.
- Person walks away (> 150 px) = **RED** leash, **10-second stopwatch** starts.
- Comes back in time → green again, stopwatch resets, **no alarm**.
- Stays away or leaves the camera view past 10 s → **ALARM**.

### 4.3 Technical data flow
```mermaid
flowchart LR
    CAM["Camera / CCTV<br/>(webcam index, OBS, or RTSP URL)"] --> R["Reader Thread<br/>cv2.VideoCapture, buffer=1"]
    R --> W["Worker Thread"]
    subgraph W_["Worker Thread (camera_manager.py)"]
        D["detector.py<br/>YOLOv8 + ByteTrack + filters"] --> F["fsm_tracker.py<br/>Association + FSM + timer"]
        F --> O["OpenCV drawing<br/>boxes, lines, timers, banner"]
        O --> J["cv2.imencode JPEG q=75"]
    end
    W --> D
    F -->|alert| DB[("SQLite<br/>vigitrack.db")]
    F -->|alert| BEEP["Notifier beep (thread)"]
    J --> FL["Flask /video_feed<br/>MJPEG"]
    FL --> UI["Dashboard UI<br/>(app window / browser)"]
```

---

## 5. Where AI Is Used (and Where It Is Not)

> **One-liner for the panel:** *"We use **AI for perception** (seeing and tracking), and **deterministic rules for decisions** (distance, timer, alarm). That way alerts are predictable, transparent and easy for security staff to adjust."*

| Part | AI? | What it actually is | File |
|---|---|---|---|
| Object detection | ✅ **Yes** | YOLOv8 Convolutional Neural Network, pre-trained on MS COCO | `detector.py` |
| Multi-object tracking | ⚙️ Algorithmic (part of the AI pipeline) | ByteTrack: Kalman filter (motion prediction) + Hungarian matching. *No neural network inside*, so call it "tracking algorithm" if pressed | `detector.py` + `bytetrack_custom.yaml` |
| Distance / association | ❌ No | Geometry: `math.hypot` (Pythagorean distance) | `fsm_tracker.py` |
| States & timer | ❌ No | Rule-based Finite State Machine | `fsm_tracker.py` |
| Drawing, JPEG, camera reading | ❌ No | OpenCV image processing | `camera_manager.py`, `notifier.py` |
| Dashboard, DB, settings | ❌ No | Flask, SQLite, JSON | `routes.py`, `models.py`, `settings_store.py` |

**Where is OpenCV?** It does the camera reading (`cv2.VideoCapture`), drawing (`cv2.rectangle`, `cv2.line`, `cv2.putText`), the semi-transparent banner (`cv2.addWeighted`) and JPEG encoding (`cv2.imencode`). YOLO only outputs numbers. OpenCV is the "eyes and paintbrush".

---

## 6. Detection Layer — `detector.py`

### 6.1 Models (hardware-adaptive, tested Nov 10)
```python
self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
if cuda:   model = "yolov8m.pt"                 # Dedicated GPU Tier
else:      model = "yolov8n_openvino_model/"    # Standard Office Tier (falls back to yolov8n.pt)
```
| | YOLOv8 Medium | YOLOv8 Nano |
|---|---|---|
| Parameters | ~25 M | ~3 M |
| Used when | A CUDA-capable (NVIDIA) GPU is detected | No CUDA GPU (e.g., office Core i5) |
| Engine | PyTorch on GPU | Intel OpenVINO on CPU |

> `torch.cuda.is_available()` detects **NVIDIA (CUDA)** GPUs only. AMD/Intel GPUs currently go to the OpenVINO CPU path. In the defense, describe this in **vendor-neutral tiers** (§10.2).

### 6.2 Target classes (COCO IDs) & calibrated confidence
| COCO ID | Class | Min. confidence |
|---|---|---|
| 0 | person | **0.60** |
| 24 | backpack | **0.22** |
| 26 | handbag | **0.18** |
| 28 | suitcase | **0.25** |

Inference settings: `imgsz=640`, base `conf=0.15` (the per-class filters above are applied afterwards), `iou=0.45`, `persist=True`, tracker = `config/bytetrack_custom.yaml`.

### 6.3 Accuracy refinements already in the code (good "we refined detection" talking points)
1. **Person geometry filter.** Rejects "person" boxes that are too squat (height/width < 0.90) or too short (< 55 px) unless confidence is very high. This stops bags being detected as people.
2. **Person-vs-bag conflict resolution.** If a "person" box heavily overlaps a similar-sized bag box, the bag wins (removes "phantom people").
3. **Box de-duplication (IoU 0.45).** One box per physical object.
4. **Spatial Identity Stabilizer.** Gives **stable canonical IDs** (1, 2, 3…) even when ByteTrack switches IDs. Matching works in two tiers: box overlap (IoU ≥ 0.30) first, then centroid distance (≤ 85 px). Tracks are remembered for 45 frames. Bags and people can never swap IDs (anti-morphing).

### 6.4 ByteTrack configuration (`bytetrack_custom.yaml`)
`track_high_thresh 0.30`, `track_low_thresh 0.10`, `new_track_thresh 0.40`, `track_buffer 60` (~2 s of memory during occlusion), `match_thresh 0.80`.

---

## 7. Person-Object Association & the 6-State FSM — `fsm_tracker.py`

> **Terminology rule:** Always say **"Person-Object Association"** and **"associated person"**, never "owner". The camera can't prove ownership; it only measures **who is physically with the item**. (The code still uses the variable name `owner_id`. That's just a name. The database column is already `person_track_id`.)

### 7.1 The math
- **Centroid:** `cx = (x1 + x2) / 2`, `cy = (y1 + y2) / 2`
- **Euclidean distance:** `d = √((x_person − x_bag)² + (y_person − y_bag)²)` (code: `math.hypot`)
- **Threshold:** `distance_threshold = 150 px` (adjustable in Settings)
- **Timer:** `time_threshold = 10 s` (adjustable in Settings)
- **Static check:** a bag counts as "stationary" when the variance of its last 15 centroid positions is < 12.

### 7.2 Association lock (bystander rejection)
1. For a bag with no associated person, find the **nearest person within 150 px**.
2. That person must stay nearest for **2 consecutive frames** (`streak >= 2`). Then they are **locked** (`owner_id = person_id`).
3. Once locked, **other people walking closer do not replace them**, so passers-by can't reset the alarm.
4. To cancel a running countdown, the associated person must be back within range for **3 consecutive frames** (`attended_confirm_frames = 3`). This hysteresis stops flicker.

### 7.3 The 6 states (exact names in code)
| State | Meaning | Screen color |
|---|---|---|
| `UNASSIGNED` | Bag seen, no person associated yet (if no one ever comes near, the timer still runs) | Grey / Orange if timer active |
| `CARRIED` | Associated person nearby **and** bag is moving | Green |
| `STATIC_ATTENDED` | Associated person nearby, bag stationary (e.g., seated student) | Green |
| `SEPARATED` | Associated person visible but > 150 px away. Countdown running | Orange + red line |
| `OWNER_OUT_OF_VIEW` | Associated person left the camera frame. Countdown keeps running | Orange |
| `UNATTENDED_ALERT` | Countdown reached `time_threshold` → **ALARM** | Red + banner |

```mermaid
stateDiagram-v2
    [*] --> UNASSIGNED: bag detected
    UNASSIGNED --> CARRIED: person within 150px (2 frames), bag moving
    UNASSIGNED --> STATIC_ATTENDED: person within 150px (2 frames), bag still
    UNASSIGNED --> UNATTENDED_ALERT: nobody near for 10s
    CARRIED --> STATIC_ATTENDED: bag stops moving
    STATIC_ATTENDED --> SEPARATED: person > 150px
    SEPARATED --> STATIC_ATTENDED: person back (3 frames) - timer resets
    SEPARATED --> UNATTENDED_ALERT: 10s elapsed
    STATIC_ATTENDED --> OWNER_OUT_OF_VIEW: person leaves frame
    OWNER_OUT_OF_VIEW --> STATIC_ATTENDED: person re-appears and comes back
    OWNER_OUT_OF_VIEW --> CARRIED: bag moving and a person within 75px (picked up)
    OWNER_OUT_OF_VIEW --> UNATTENDED_ALERT: 10s elapsed
```

### 7.4 Robustness features
- **Cross-class recovery:** if YOLO flips between "handbag" and "backpack", the same track is kept (spatial match ≤ 85 px).
- **Temporal persistence:** a bag stays on screen for up to 15 missed frames (thin box) and is forgotten after 45.
- **Pick-up handling:** if the associated person is gone and the bag **starts moving** with someone within 75 px, it's treated as picked up (`CARRIED`).

---

## 8. Supporting Subsystems

### 8.1 Camera Manager — `camera_manager.py` (the orchestrator)
| Thread | Job |
|---|---|
| **Reader thread** (`VigiTrack-Reader`) | Reads frames non-stop with `CAP_PROP_BUFFERSIZE = 1`, so the AI always gets the **newest** frame (no lag build-up). Auto-reconnects after ~40 failed reads |
| **Worker thread** (`VigiTrack-Worker`) | YOLO + ByteTrack → FSM → OpenCV drawing → JPEG encoding |
| **Flask request threads** (`threaded=True`) | Serve pages, API, and the video feed to each viewer |

**Locks (the "traffic light"):** `raw_frame_lock`, `jpeg_lock`, `alerts_lock` (+ notifier `_lock`). They make sure two threads never touch the same frame or list at the same time.

Camera resolution requested: 1280×720. JPEG quality: 75.

### 8.2 Local Video Display Pipeline (formerly called "video streaming engine")
> ⚠️ **Important for defense:** This is **NOT internet streaming**. It is the **local** link between the Python AI backend and the dashboard screen.

- How it works (flipbook): OpenCV encodes each annotated frame as JPEG → Flask sends it on `GET /video_feed` as `multipart/x-mixed-replace` (MJPEG) → the dashboard shows it in `<img src="/video_feed">`, replacing the picture ~30 times per second.
- **Why a web UI instead of `cv2.imshow`/Tkinter?**
  1. **LAN access:** a guard on another PC can open `http://<server-ip>:5000` with no Python/GPU installed.
  2. **Crash resilience:** closing or refreshing the dashboard doesn't stop detection or logging.
  3. **Richer UI:** live alert list, incident table and settings beside the video.
- **Why MJPEG?** Browsers can't play RTSP natively. MJPEG works everywhere with no plugins and low latency.
- **Say it this way:** *"Local Video Feed Pipeline. The backend serves annotated frames to the local dashboard over low-latency HTTP."*

### 8.3 Database — SQLite (`data/vigitrack.db`)
- Plain Python `sqlite3` (no ORM), **WAL journal mode**, 15 s timeout, **parameterized queries** (`?` placeholders → SQL-injection safe).
- Table **`incidents`**:

| Column | Type | Example |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | 12 |
| `object_class` | TEXT NOT NULL | backpack |
| `object_track_id` | INTEGER | 4 |
| `person_track_id` | INTEGER | 2 (or NULL if no one was ever associated) |
| `distance` | REAL | 200.0 |
| `camera_name` | TEXT | BUILT-IN WEBCAM |
| `status` | TEXT (default `'unattended'`) | unattended |
| `detected_at` | TEXT (ISO timestamp) | 2026-11-10T14:57:22 |

- **No duplicate rows:** `camera_manager.py` keeps a set `self.logged_bag_ids`. Each bag ID is logged **once** even if the alarm stays on for minutes.
- **Why SQLite?** Serverless, a single file, zero configuration, works offline. Ideal for one edge PC. (For multi-site/central reporting you'd migrate to PostgreSQL/MySQL.)

### 8.4 Alerts — `notifier.py`
- **Audio:** `winsound.Beep(1200 Hz, 350 ms)` in a **background thread** (video never freezes). **Rate-limited** to once every 3 s while an alert is active. Can be toggled in Settings.
- **Visual:** a semi-transparent red banner `"WARNING: UNATTENDED OBJECT DETECTED"` drawn with `cv2.addWeighted`, plus a red box and `UNATTENDED BACKPACK #4` label.
- **Dashboard:** latest 25 alerts via `GET /api/alerts`.

### 8.5 Settings persistence — `settings_store.py` + `data/settings.json`
- Defaults: `distance_threshold 150`, `time_threshold 10`, `audio_alert_enabled true`, `camera_source 0`, `camera_name "BUILT-IN WEBCAM"`.
- Changes from the Settings page take effect **immediately without restart** and are saved to JSON.
- If the JSON file is missing or corrupt → **factory defaults are restored automatically**.
- `camera_source` can be a webcam index (`0`, `1`) **or an RTSP URL string**. Switching it in Settings re-opens the camera live.

### 8.6 REST API — `routes.py`
| Method & route | Purpose |
|---|---|
| `GET /` | Dashboard page |
| `GET /incidents` | Incident history page |
| `GET /settings` | Settings page |
| `GET /video_feed` | Live MJPEG feed |
| `GET /api/alerts` | Recent alerts (JSON) |
| `GET /api/incidents` | Incident list (newest 100) |
| `DELETE /api/incidents/<id>` | Delete one incident |
| `POST /api/incidents/clear` | Clear all incidents |
| `GET /api/settings` | Current thresholds/camera/audio |
| `POST /api/settings` | Update thresholds, audio, camera source |

Server: `app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)`. `debug=False` prevents the reloader from opening the camera twice.

---

## 9. CCTV Integration (Sir Serge's Questions)

| Question | Answer |
|---|---|
| **Plugin or standalone?** | **Standalone application.** It does not install inside NVR software (Hikvision iVMS, Dahua SmartPSS) and does not modify camera firmware |
| **How does it talk to existing CCTV?** | **RTSP (Real-Time Streaming Protocol)** over the LAN, standard **port 554**. Supported by virtually all IP cameras/NVRs (ONVIF) |
| **How does it receive the live feed?** | `cv2.VideoCapture("rtsp://user:pass@<NVR_IP>:554/...")`. OpenCV/FFmpeg decodes H.264/H.265 into frames |

**Example RTSP URLs**
```
Hikvision (Ch1 sub-stream): rtsp://admin:PASS@192.168.1.100:554/Streaming/Channels/102
Dahua (Ch1 sub-stream):     rtsp://admin:PASS@192.168.1.100:554/cam/realmonitor?channel=1&subtype=1
```

**Dual-stream strategy:** the NVR keeps recording the **main stream** (1080p/4K) for evidence. VigiTrack reads the lighter **sub-stream**, because YOLO resizes to 640 px anyway, so this saves bandwidth and CPU.

**3 physical pieces (deployment architecture)**
```
[1] Existing CCTV (cameras + switch + NVR)  ──RTSP──▶  [2] VigiTrack PC (AI + DB + Flask)  ──HTTP──▶  [3] Guard's screen (app window/browser + speaker)
       untouched — keeps recording                      does all the processing                      no install needed on LAN viewers
```

**Script:** *"Sir, VigiTrack is a standalone edge analytics application. It connects to the school's existing cameras or NVR over RTSP on the local network, processes the video on a local PC, and shows the results on a dashboard. The school does not need to replace cameras, flash firmware, or change their recordings."*

> **Honesty note:** So far it has been tested with a **laptop webcam (index 0)** and an **OBS Virtual Camera (index 1)** that simulates CCTV. RTSP works through the same `cv2.VideoCapture` code path, and `test_cctv.py` accepts an RTSP URL. Test it on a real IP camera before the defense if you can.

---

## 10. Deployment: Local Edge vs Cloud, and Hardware Tiers

### 10.1 Why a local (edge) server, not cloud
| Reason | Explanation |
|---|---|
| Bandwidth | One camera 24/7 ≈ 2–4 Mbps upload (hundreds of GB/month). Many cameras would choke school internet |
| Cost | Cloud GPU VMs cost roughly \$150–\$350+/month. A local PC is a one-time cost |
| Reliability | If the internet goes down, a local system **keeps working** on the LAN |
| Latency | LAN takes milliseconds. A cloud round-trip adds delay to alerts |
| Privacy | **RA 10173 (Data Privacy Act of 2012)**: video of students and minors stays inside the campus network |

**Hybrid option (future work):** keep the AI local, and send only small incident records (JSON) to the cloud so admins can view reports remotely.

### 10.2 Two hardware tiers (vendor-neutral wording)
| Tier | Hardware | Model | Purpose |
|---|---|---|---|
| **Tier 1 — Dedicated GPU Tier** | PC with a dedicated graphics card | YOLOv8 Medium | Maximum accuracy on small or far bags |
| **Tier 2 — Standard Office Tier** | Ordinary Core i5 office PC, no dedicated GPU | YOLOv8 Nano + Intel OpenVINO | Real-time on existing school PCs, no hardware purchase |

The switch is **automatic** at startup (`detector.py`). The pipeline after detection is **identical** in both tiers.

> **Performance numbers:** the figures from our discussion (Medium on i5 ≈ 3–7 FPS; Nano ≈ 15–22 FPS; Nano + OpenVINO ≈ 25–30 FPS) are **typical estimates, not your measurements**. Measure the real FPS on the school's PC and use those numbers in Chapter 4.

### 10.3 Packaging for the school (decided direction, not yet built)
- The goal: the school installs VigiTrack on **their** PC, and your laptop stays with you.
- Plan: (1) Nano + OpenVINO ✅ done → (2) one-click `Start_VigiTrack.bat` launcher that starts the server and opens Edge/Chrome in **`--app` mode** (no address bar, looks like a desktop app) ⏳ → (3) optional PyInstaller/Inno Setup installer ⏳.

---

## 11. The Contribution of the Study

### 11.1 The single main contribution (use this)
> **Context-Aware Person-Object Association Pipeline, which removes the "seated person" false alarm.**

**Paper version (Chapter 1):**
> *"The primary contribution of this study is the design and implementation of a Context-Aware Person-Object Association Pipeline that reduces false abandonment alarms in institutional surveillance. Unlike conventional systems that rely only on stationary-object timers, VigiTrack links belongings to the nearest person through spatial-temporal tracking. Items kept beside seated persons are recognized as attended, and alerts are triggered only when the associated person actually leaves."*

**Spoken version:**
> *"Our main contribution is solving the false-alarm problem of conventional CCTV. Our system knows when a bag is attended by a nearby person, and only starts the countdown when that person actually walks away."*

### 11.2 "Why use yours instead of existing systems?"
> *"Many existing CCTV analytics only check whether an object has stayed in one spot for X seconds. A student reading on a bench with their bag beside them triggers an alarm. Guards get tired of these false alarms and turn the feature off. VigiTrack:*
> 1. *tracks the **person with the bag**, so no alarm while someone is with it;*
> 2. ***ignores passers-by**: a stranger walking past can't reset or take over the association;*
> 3. ***keeps counting when the person leaves the frame**;*
> 4. *runs on **existing cameras and ordinary school PCs**, with no expensive GPU or enterprise license.*
> *Existing systems detect stationary pixels. VigiTrack detects human separation."*

### 11.3 Careful wording
- ❌ Don't say *"No existing system associates people with bags. We invented it."* Person-bag association exists in research papers (e.g., airport surveillance).
- ✅ Say *"We contribute a practical, lightweight, privacy-preserving implementation (no face recognition) that fixes the false-alarm problem and runs on commodity campus hardware."*

---

## 12. Ideas We Evaluated (and the Verdicts)

| Idea | Verdict | Why |
|---|---|---|
| **Background subtraction** (capture a base image, detect pixel changes, then identify the object) | Works with current models, but **not as a replacement** | Lighting changes, shadows and camera vibration cause false triggers. Most importantly, **it can't tell a seated person is next to the bag** (the same false alarm). Possible future use: an **energy-saving gate** (run YOLO slowly when nothing changes) |
| **Fine-tuning YOLOv8** (transfer learning on overhead CCTV images) | Valid **optional** contribution | COCO photos are mostly eye-level. CCTV looks down from the ceiling. Needs ~300–1,000 labeled images (Roboflow/LabelImg) plus before/after mAP, precision and recall |
| **New object class** (e.g., `parcel_box`, `tote_bag`, `laptop_bag`) | Valid **optional** add-on | COCO has no box/parcel class. Requires a custom dataset and training: `model.train(data=..., epochs=40, imgsz=640)` |
| **Pick one contribution** | ✅ **Person-Object Association** | Training a class is mostly data labeling. A detector that knows 100 bag types still causes false alarms if it ignores the seated person |

---

## 13. Secure Design Concept Paper (Submitted Deliverable)
- File: `C:\Users\garya\.gemini\antigravity\scratch\vigitrack-docs\Secure_Design_Concept_Paper_Alquiza.pdf` (3 pages)
- Module: **Web Monitoring Dashboard, MJPEG Video Feed & Configuration REST API (`app/stream/`)**
- Principles: **Fail-Safe Defaults & Complete Mediation** (default-deny login guard, loopback binding behind HTTPS proxy, safe settings fallback), **Least Privilege** (Operator vs Administrator roles), **Defense in Depth** (server-side range checks, CSRF tokens, `escapeHtml` + CSP, parameterized SQL)
- Risks: stream snooping, threshold tampering, log wiping, session hijacking/CSRF, MJPEG DoS, SQLi/XSS
- Compliance: RA 10173 + NPC CCTV guidelines, ISO/IEC 27001:2022 Annex A, OWASP API Top 10 (2023)

> ⚠️ This paper describes the **planned** security design. The current code does **not** yet have login, roles, CSRF or HTTPS, and binds to `0.0.0.0`. If asked, say it is "designed and planned, not yet implemented in the prototype".

---

## 14. Defense Q&A Cheat Sheet

| Panel question | Short answer |
|---|---|
| What does it do? | Detects people and bags, links each bag to the nearest person, and alerts when that person leaves the bag longer than the time limit |
| Main contribution? | Person-Object Association, which removes false alarms for seated or nearby people |
| Why "person" not "owner"? | The camera can't verify ownership. It only measures who is physically with the item |
| Which part is AI? | YOLOv8 (detection) with ByteTrack tracking. The rest is rules and math, kept deterministic so it is transparent and adjustable |
| How is association done? | Centroid distance ≤ 150 px, locked after 2 consecutive frames. Others can't take it over. 10 s countdown on separation |
| Stranger walks past? | The association is locked to the first person, so passers-by are ignored |
| Person leaves the frame? | `OWNER_OUT_OF_VIEW` state. The countdown keeps running |
| Person comes back at 8 s? | Back within range for 3 frames → timer resets, no alarm |
| Bag never had anyone near it? | Timer runs from detection and alerts after 10 s |
| Why not background subtraction? | Breaks with lighting changes and can't see a seated person next to the bag |
| How does it connect to CCTV? | Standalone app reading RTSP (port 554) from cameras/NVR over LAN. Uses the sub-stream. NVR untouched |
| Plugin? | No, standalone |
| Cloud? | Possible, but local is better: bandwidth, cost, works offline, privacy (RA 10173) |
| Need an RTX GPU? | No. Auto-switches to YOLOv8 Nano + OpenVINO on an ordinary Core i5 |
| Why two models? | Deliberate: two hardware tiers, same pipeline |
| Why "video streaming" if it's an app? | It's a local display pipeline (localhost/LAN), not internet streaming. It also lets other LAN PCs view without installing anything |
| Why MJPEG? | Browsers can't play RTSP. MJPEG is native, plugin-free and low-latency |
| Why SQLite? | Serverless single file, zero config, offline. Ideal for an edge PC |
| Duplicate DB rows? | No. `logged_bag_ids` logs each bag once |
| Does the beep freeze video? | No. It plays in a background thread, rate-limited to every 3 s |
| Settings lost on restart? | No. Saved to `settings.json`, with automatic defaults if the file is corrupt |
| Why threads + locks? | The reader keeps frames fresh, the worker runs AI. Locks prevent two threads touching the same frame |
| Someone steals the bag? | If the associated person is gone and the bag starts moving with a new person, the system treats it as picked up (`CARRIED`). If the alarm had already fired, the incident is **already logged**. Theft detection is a limitation and future work (§17) |
| Face recognition? | None. Only box geometry, which preserves privacy |

---

## 15. Glossary (Plain English)
| Term | Plain meaning |
|---|---|
| **YOLOv8** | AI that finds objects in an image in one quick pass |
| **CNN** | The type of neural network inside YOLO that learns visual patterns |
| **MS COCO** | The 80-class photo dataset YOLO was pre-trained on |
| **ByteTrack** | Keeps the same ID on the same object across frames |
| **Kalman filter** | Predicts where an object will be in the next frame |
| **Centroid** | The center point of a box |
| **Euclidean distance** | Straight-line distance between two points |
| **FSM (Finite State Machine)** | A fixed set of statuses plus rules for moving between them |
| **Debounce / streak** | Waiting a few frames before deciding, so one bad frame doesn't change anything |
| **Hysteresis** | Needing extra confirmation to switch back, so the status doesn't flicker |
| **NMS / IoU** | Removing overlapping duplicate boxes / how much two boxes overlap |
| **RTSP** | The standard protocol cameras use to send live video over a network |
| **NVR** | The recorder box that stores CCTV footage |
| **Sub-stream** | A lower-resolution copy of the camera feed |
| **MJPEG** | Video sent as a fast series of JPEG pictures (a flipbook) |
| **OpenVINO** | Intel's tool for making AI run fast on Intel CPUs |
| **Edge computing** | Processing data on-site instead of in the cloud |
| **WAL mode** | SQLite setting that allows reading while writing |
| **Thread / Lock** | Tasks running at the same time / a "traffic light" so they don't collide |

---

## 16. Fact-Check: Corrections to Earlier Answers & the PDF Handbook

Some earlier chat answers and the generated **`VigiTrack_Capstone_Defense_Handbook.pdf`** contain details that **don't match the current code**. If a panelist looks at your code, use the **actual** values.

| Topic | What was said earlier / in the PDF | **Actual (in code)** |
|---|---|---|
| FSM state names (PDF) | `IN_TRANSIT → ASSOCIATED → UNATTENDED → ALERT_PENDING → ALARM_ACTIVE → CLEARED` | `UNASSIGNED, CARRIED, STATIC_ATTENDED, SEPARATED, OWNER_OUT_OF_VIEW, UNATTENDED_ALERT` |
| Association lock | "5 consecutive frames (`DEBOUNCE_COMMIT_FRAMES = 5`)" | **2 frames** (`streak >= 2`) to lock. **3 frames** (`attended_confirm_frames`) to confirm the person is back |
| Confidence thresholds | person 0.55, bags 0.28 / 0.30 | person **0.60**, backpack **0.22**, handbag **0.18**, suitcase **0.25** |
| Dedup set name | `self.logged_ids` | `self.logged_bag_ids` |
| Beep | 1000 Hz, 400 ms | **1200 Hz, 350 ms**, rate-limited every **3 s** |
| Banner text | "UNATTENDED BAGGAGE ALERT ACTIVE" | "WARNING: UNATTENDED OBJECT DETECTED" |
| Database code | `person_track_id = Column(Integer)` (ORM style) | Plain `sqlite3` with `CREATE TABLE`. Also has a `status` column. WAL mode |
| Tier 1 optimization (PDF) | "TensorRT / FP16" | Plain **PyTorch on CUDA**. TensorRT not used |
| Tier 2 optimization (PDF) | "INT8 quantization" | **Default OpenVINO export**. INT8 not applied |
| Stream resolution | "Downscaled to 960p" | Camera requested at **1280×720**, JPEG quality 75. No 960p resize in the current code |
| Threads | "3 threads" | Reader + Worker threads, plus Flask's per-request threads |
| Project path | `C:\Users\garya\OneDrive\Desktop\VigiTrack` | **`C:\Users\garya\Desktop\VigiTrack`** |
| "Video Streaming Engine" | Sounded like internet streaming | **Local Video Feed Pipeline** (localhost/LAN only) |
| FPS on Core i5 | Stated as facts | **Estimates**. Measure on the real PC |

> **Recommendation:** regenerate the PDF handbook with these corrections (just ask), or study from this README, which matches the code.

---

## 17. Known Limitations (Be Honest About These)
1. **Pixel distance, not real-world distance.** 150 px means different real distances depending on camera height and angle. Calibrate per camera in Settings.
2. **Nearest ≠ owner.** That's why it's called *Person-Object Association*.
3. **Theft isn't detected as theft.** If someone else picks up the bag after the person leaves, it's treated as `CARRIED`.
4. **Occlusion.** Heavily hidden bags may be missed. ByteTrack's 60-frame buffer and the stabilizer's 45-frame memory help with short occlusions.
5. **One camera per running instance** (multi-camera would need several `CameraManager` instances).
6. **No authentication yet** on the dashboard/API (planned in the Secure Design paper).
7. **COCO limitations.** Only backpack, handbag and suitcase. Overhead angles reduce confidence (fine-tuning = future work).
8. **Tested on webcam/OBS, not yet a real RTSP camera.**

---

## 18. Pending Work / Next Steps
| Priority | Task | Status |
|---|---|---|
| 🔴 High | Fix **`requirements.txt`**: add `torch` and `openvino` (currently only ultralytics, opencv-python, flask, numpy) | ⏳ |
| 🔴 High | Test with a **real RTSP** camera/NVR (`python test_cctv.py "rtsp://..."`) | ⏳ |
| 🔴 High | **Measure FPS** on the school's Core i5 for Chapter 4 | ⏳ |
| 🟠 Med | Create **`Start_VigiTrack.bat`** one-click launcher (Edge/Chrome `--app` mode) | ⏳ Offered, not created |
| 🟠 Med | Regenerate the **Defense Handbook PDF** with §16 corrections + "Local Video Feed Pipeline" wording | ⏳ |
| 🟡 Low | Rename `owner_*` variables/labels to `person_*` in code/UI for consistency (e.g., the "No Owner" label) | Optional |
| 🟡 Low | Implement planned security (login, roles, CSRF, input range checks) | Optional / future |
| 🟡 Low | Fine-tune YOLOv8 / add custom class | Optional / future |
| ⚪ Other | Lab 6 — Phase 1 Server Requirement Specification (separate conversation `c0f792f1…`) | Waiting for team names & VM choice |

---

## 19. How to Run
```powershell
cd C:\Users\garya\Desktop\VigiTrack
.\venv\Scripts\activate
python run.py
# Open http://127.0.0.1:5000   (other LAN PCs: http://<this-PC-IP>:5000)
```
Useful tools:
```powershell
python scan_cctv.py                      # which camera indices work
python test_cctv.py 1                    # preview a camera (index or RTSP URL)
python test_detector.py                  # desktop test window with detection + FSM
```
> Don't run `run.py` and `test_detector.py` at the same time. Windows only lets one program use a camera at a time.

---

## 20. Deliverables & File Locations
| Deliverable | Location |
|---|---|
| This README | `C:\Users\garya\Desktop\VigiTrack\README.md` |
| Defense Handbook PDF (needs §16 corrections) | `C:\Users\garya\Desktop\VigiTrack\VigiTrack_Capstone_Defense_Handbook.pdf` (also in `Downloads`) |
| Secure Design Concept Paper | `C:\Users\garya\.gemini\antigravity\scratch\vigitrack-docs\Secure_Design_Concept_Paper_Alquiza.pdf` |
| Source code | `C:\Users\garya\Desktop\VigiTrack\` |
