# Software Requirements Specification
## VigiTrack: AI Unattended-Object Detection and Surveillance Hub

| Field | Value |
|---|---|
| Document version | 1.0 (draft for review) |
| Date | 13 November 2026 |
| Status | Baseline reflecting the code as of commit `4558ce5` |
| Prepared for | Capstone defense and school deployment |
| Format | Based on IEEE 830-1998 structure |

**Status legend used in this document**
- **Implemented**: built and covered by at least one automated test or a documented manual check.
- **Partial**: built, but with a known gap noted in the requirement.
- **Planned**: required but not yet built.

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for VigiTrack. It is the reference for developers, testers, the capstone panel, and the school IT office that will deploy the system.

### 1.2 Scope
VigiTrack is a software system that reads video from one or more cameras, detects people and bags in the video, and raises an alert when a bag is left without its owner nearby.

The system includes:
- A detection and tracking backend (Python, YOLOv8, ByteTrack, OpenCV, OpenVINO).
- An ownership and state engine that links each bag to a person and tracks separation over time.
- An incident store with snapshots, timelines and an audit log (SQLite).
- A web hub (React, TypeScript, Vite, shadcn/ui) with a live feed, alerts, incidents, accounts and settings.
- A desktop wrapper that runs the backend on the local PC and shows the hub in a native window.

The system does **not** include:
- Face recognition or identity matching of any kind.
- Cloud processing or cloud storage.
- Automatic physical response (for example, locking doors or calling security).

### 1.3 Definitions

| Term | Meaning |
|---|---|
| Bag | A backpack, handbag or suitcase, as detected by the model. |
| Owner | The person track linked to a bag. |
| Canonical ID | A stable ID given to each object by the identity stabilizer. |
| Separation | The owner is farther than the distance threshold from the bag. |
| Unattended alert | A bag has been separated from its owner, or has had no owner, for longer than the time threshold. |
| Incident | A stored record of one unattended alert, with snapshot and state history. |
| FSM | Finite state machine. The state engine for each bag. |
| Operator | A user with read access to the hub and incidents. |
| Admin | A user who can also change settings, manage accounts and delete incidents. |
| Setup code | A one-time code printed in the backend terminal, used to create the first admin on a network install. |
| Desktop mode | The backend listens on `127.0.0.1` only and the hub opens in its own window. |
| RTSP | Real-Time Streaming Protocol, used by IP cameras and NVRs. |

### 1.4 References
- IEEE Std 830-1998, Recommended Practice for Software Requirements Specifications.
- Ultralytics YOLOv8 documentation.
- ByteTrack (Zhang et al.), multi-object tracking.
- Republic Act No. 10173, Data Privacy Act of 2012 (Philippines).
- Project files: `backend/app/detection/detector.py`, `backend/app/detection/fsm_tracker.py`, `backend/app/stream/camera_manager.py`, `backend/app/stream/routes.py`, `backend/app/database/users.py`, `backend/app/database/models.py`, `backend/desktop.py`.

### 1.5 Overview
Section 2 describes the product context and constraints. Section 3 lists the specific requirements. Section 4 explains how each requirement is verified. Section 5 lists open issues.

---

## 2. Overall Description

### 2.1 Product perspective
VigiTrack is a standalone system. It takes input from an existing CCTV camera (USB webcam or RTSP IP camera) and produces alerts, snapshots and a web interface. It does not replace the camera or NVR. It runs on one PC in a school or office.

```
Camera (USB or RTSP)
   -> Backend (Python, detection + state engine)
        -> SQLite database and incident snapshots
        -> HTTP API (Flask) -> Web hub (React, browser)
   -> Desktop wrapper (pywebview) -> Hub in its own window
```

### 2.2 Product functions (summary)
1. Capture video from a camera and keep the feed current.
2. Detect people and bags in each frame.
3. Link each bag to its nearest owner and track separation over time.
4. Raise and record an unattended alert when the time threshold is reached.
5. Show the live annotated feed, alerts and status in the hub.
6. Store incidents with snapshots and state timelines, and let admins review and delete them.
7. Manage user accounts, roles and sessions, with lockout and audit logging.
8. Allow admins to change detection and camera settings.
9. Run as a desktop application on a single PC without exposing the service to the network.

### 2.3 User classes

| User class | Description | Main tasks |
|---|---|---|
| Administrator | IT staff or the system owner. Sets up the system and manages accounts. | Create and manage accounts, change settings, delete incidents, read the audit log. |
| Operator | Security or reception staff who watch the feed. | View the live feed, alerts and incidents, change their own password. |
| Developer or tester | Project team, for testing and maintenance. | Run the test scripts, change the code, measure detection quality. |
| Capstone panel | Evaluators, for review and demonstration. | Observe live operation, review the design and evidence. |

### 2.4 Operating environment
- **Operating system:** Windows 10 or 11 (primary target). The camera code selects the Windows DirectShow backend when available.
- **Hardware (standard tier):** Intel Core i5 class PC with no dedicated GPU. Runs YOLOv8-Nano with OpenVINO on the CPU.
- **Hardware (GPU tier):** PC with an NVIDIA CUDA GPU. Uses YOLOv8-Medium.
- **Browsers (hub):** current versions of Chrome, Edge or Firefox.
- **Runtime:** Python 3.11 with the packages in `backend/requirements.txt`; Node.js 20 or later for building the hub.
- **Cameras:** USB webcam (device index) or RTSP IP camera or NVR. RTSP has not yet been tested on real hardware (see Section 5).

### 2.5 Design constraints
- **C1.** Detection must use the Python stack already in the project (YOLOv8, ByteTrack, OpenCV, OpenVINO). The frontend must be TypeScript with React.
- **C2.** The UI must follow the Studio Admin template (MIT licence).
- **C3.** The project layout must be `frontend/` and `backend/`.
- **C4.** No self-registration. Accounts are created by an admin, or by the one-time first-run setup.
- **C5.** No face recognition or identity matching.
- **C6.** Password hashes use Werkzeug. Passwords are never stored or returned in plain text.
- **C7.** The backend currently handles one camera per process.

### 2.6 Assumptions and dependencies
- The camera is mounted at a fixed position and angle, so distance thresholds stay consistent.
- The camera has enough resolution and light for the model to see people and bags.
- The school or office has permission to record video and has informed the people in view, as required by the Data Privacy Act.
- The PC is physically secured. Anyone with access to the PC can read the database and settings file.
- YOLOv8 model weights are available locally (the OpenVINO export is in the repository).

---

## 3. Specific Requirements

### 3.1 Video capture

| ID | Requirement | Status |
|---|---|---|
| FR-01 | The system shall open a camera by device index or RTSP URL, as set in the settings. | Implemented (webcam tested; RTSP not yet tested) |
| FR-02 | The system shall read frames on a dedicated thread and keep only the newest frame, so that processing does not build up a backlog. | Implemented |
| FR-03 | The system shall try to reconnect after repeated read failures (about 40 failed reads), and retry if the camera cannot be opened. | Implemented |
| FR-04 | The system shall allow an admin to switch the camera source while the system is running. A new source that cannot be opened shall leave the previous source running. | Implemented |
| FR-05 | The system shall request a 1280×720 capture and a single-frame buffer. | Implemented |
| FR-06 | The system shall report a camera's status (online, reconnecting, offline) to the hub. | Implemented (online within 3 s of a frame, reconnecting to 10 s, offline after; shown on the dashboard) |

### 3.2 Detection and tracking

| ID | Requirement | Status |
|---|---|---|
| FR-07 | The system shall detect the classes person, backpack, handbag and suitcase, using YOLOv8 with ByteTrack. | Implemented |
| FR-08 | The system shall use the OpenVINO model on CPU-only PCs and the CUDA model when a CUDA GPU is available. | Implemented |
| FR-09 | The system shall apply a per-class minimum confidence: person 0.60, backpack 0.22, handbag 0.18, suitcase 0.25. | Implemented |
| FR-10 | The system shall reject person detections whose box is squarish (height/width under 0.90) or shorter than 55 px, unless confidence is very high. | Implemented |
| FR-11 | When a person box overlaps a bag box strongly, the system shall treat the detection as the bag and drop the person detection. | Implemented |
| FR-12 | The system shall remove duplicate boxes of the same kind (IoU above 0.45). | Implemented |
| FR-13 | The system shall keep a stable canonical ID for each object across tracker ID changes, using IoU and centre-distance matching. An established bag shall not become a person. | Implemented |
| FR-14 | The system shall keep an object's ID for up to about 45 missed frames, so brief detector dropouts do not reset it. | Implemented |
| FR-15 | The system shall allow monitored classes to be chosen in the settings. The person class is always monitored. | Implemented |

### 3.3 Ownership and state engine

| ID | Requirement | Status |
|---|---|---|
| FR-16 | The system shall link a bag to the nearest person whose centre is within the distance threshold (default 150 px), once the link is seen in two consecutive frames. | Implemented |
| FR-17 | The system shall record each bag's state as one of: UNASSIGNED, CARRIED, STATIC_ATTENDED, SEPARATED, OWNER_OUT_OF_VIEW, UNATTENDED_ALERT. | Implemented |
| FR-18 | The system shall consider a bag attended when its owner is within the distance threshold for at least three consecutive frames. | Implemented |
| FR-19 | When the owner moves beyond the distance threshold, the system shall start a separation timer. The timer shall reset when the owner returns within range. | Implemented |
| FR-20 | When the owner leaves the frame, the system shall keep the owner link and run the timer. If the owner is still missing after the timer expires, the system shall raise an alert. | Implemented |
| FR-21 | If a bag has no owner, the system shall run a timer and raise an alert when it expires. | Implemented |
| FR-22 | The system shall raise an unattended alert when the separation timer reaches the time threshold (default 10 s). | Implemented |
| FR-23 | The system shall allow a different person to take over ownership of a moving bag only when the original owner is out of view and that person stays within half the distance threshold of the bag for 10 consecutive frames. A passer-by who only walks by shall not take over. | Implemented (tests: `test_fsm.py`) |
| FR-24 | The system shall keep a state history for each bag, with timestamps, for display in the incident timeline. | Implemented |
| FR-25 | The system shall apply the distance threshold and time threshold to each bag, using values from the settings. | Implemented |
| FR-26 | The system shall create at most one incident per separation episode. A new separation of the same bag, after the owner has returned, shall raise a new incident. | Implemented (tests: `test_fsm.py`) |

### 3.4 Visual output

| ID | Requirement | Status |
|---|---|---|
| FR-27 | The system shall draw person boxes labelled with track ID and confidence. | Implemented |
| FR-28 | The system shall draw each bag box in a colour that matches its state: green (attended), orange (timer running), red (alert), grey (other). | Implemented |
| FR-29 | The system shall draw a line between each bag and its owner, green within the distance threshold and red beyond it, with the distance in px. | Implemented |
| FR-30 | The system shall show a red alert banner while any bag is in alert. | Implemented |
| FR-31 | The system shall show the processing frame rate (FPS, averaged over the last 30 frames) on the feed. | Implemented |
| FR-32 | The system shall stream the annotated feed as JPEG frames to authenticated users. | Implemented |

### 3.5 Incidents and evidence

| ID | Requirement | Status |
|---|---|---|
| FR-33 | When an alert is raised, the system shall create an incident record with: object class, bag track ID, owner track ID, distance, distance threshold, time threshold, camera name, detection time, status, and state history. | Implemented |
| FR-34 | When an alert is raised, the system shall save the annotated frame as a JPEG snapshot linked to the incident. | Implemented |
| FR-35 | Operators and admins shall be able to list incidents (newest first), view one incident with its timeline and snapshot. | Implemented |
| FR-36 | Only admins shall be able to delete one incident or clear all incidents. Deleting an incident shall also delete its snapshot file. | Implemented |
| FR-37 | The system shall show recent alerts on the dashboard. | Implemented |
| FR-38 | Operators shall be able to acknowledge, verify or dismiss an incident, with a note. Dismissing as a false alarm requires a reason. | Implemented (review fields in the database, POST /api/incidents/<id>/review, audited) |
| FR-39 | The system shall allow an incident to be exported (CSV for the list, PDF for one incident). | Planned |
| FR-40 | The system shall delete snapshots older than a configured retention period. | Implemented (default 30 days, 1–3650 configurable; checked hourly, each run audited) |

### 3.6 Accounts, roles and sessions

| ID | Requirement | Status |
|---|---|---|
| FR-41 | The system shall have two roles: admin and operator. | Implemented |
| FR-42 | Users shall not be able to self-register. Accounts shall be created by an admin, or by the first-run setup. | Implemented |
| FR-43 | On a fresh install with no accounts, the system shall show a setup page. Network installs shall require the one-time setup code printed in the backend terminal. Desktop installs shall not require the code. | Implemented |
| FR-44 | The setup page shall stop accepting setup after the first admin is created. | Implemented |
| FR-45 | After five wrong setup codes, the system shall refuse setup until the backend restarts. | Implemented |
| FR-46 | Usernames shall be 3 to 32 characters, using letters, numbers, dot, dash or underscore. Usernames shall be unique regardless of case. | Implemented |
| FR-47 | Passwords shall be at least 8 characters. | Implemented |
| FR-48 | An account shall be locked for 15 minutes after five consecutive wrong passwords. | Implemented |
| FR-49 | An admin shall be able to unlock an account, reset a password, change a role, and enable or disable an account. | Implemented |
| FR-50 | An admin shall not be able to disable, demote or delete their own account. The last active admin shall not be removable. | Implemented (self-protection checked in the route code; last-admin rule covered by the account tests) |
| FR-51 | A new account, or an account whose password was reset by an admin, shall be required to change its password at first login. Until it does, the user shall only reach the My account page and the account endpoints. | Implemented |
| FR-52 | Users shall be able to change their own password, by entering the current password. | Implemented |
| FR-53 | Sessions shall last up to 8 hours and use HttpOnly and SameSite=Lax cookies. | Implemented |
| FR-54 | Sessions shall end after an idle period. | Implemented (30 minutes, set by VIGITRACK_IDLE_MINUTES. Background polling does not count as activity) |
| FR-55 | The system shall log logins, failed logins, lockouts, account changes, password resets, setting changes, incident deletions, and setup events to an audit log. | Implemented |
| FR-56 | Admins shall be able to view the audit log, newest first. | Implemented |

### 3.7 Settings

| ID | Requirement | Status |
|---|---|---|
| FR-57 | Admins shall be able to change the distance threshold, time threshold, monitored classes, audio alert on or off, and camera source. | Implemented |
| FR-58 | Operators shall be able to read the settings but not change them. | Implemented |
| FR-59 | Changed settings shall be saved and applied without restarting the backend, where the camera and monitor allow it. | Implemented (monitored classes update the running detector) |
| FR-60 | The system shall play an audible alert on the PC when a bag is in alert, when audio is enabled. | Implemented (server-side sound) |
| FR-61 | The hub shall show an alert notification to operators in the browser. | Implemented (toast with a link to the incident, plus a tone when audio alerts are on. Operating-system notifications are not included) |
| FR-62 | Camera credentials (RTSP usernames and passwords) shall be stored encrypted and not in plain text. | Implemented (full RTSP URL encrypted with Windows DPAPI; the settings file keeps a masked copy; logs and API responses are masked) |

### 3.8 Desktop application

| ID | Requirement | Status |
|---|---|---|
| FR-63 | The desktop application shall run the backend on `127.0.0.1` only, on a free port chosen at start-up. | Implemented |
| FR-64 | The desktop application shall open the hub in a native window of at least 1100×700, default 1400×900. | Implemented (confirmed on the developer PC) |
| FR-65 | The desktop application shall show the VigiTrack logo as the window icon and group the window under VigiTrack in the taskbar. | Implemented (icon file verified; visual check pending) |
| FR-66 | The desktop application shall stop when its window is closed. | Implemented (by design; to be confirmed in testing) |
| FR-67 | The desktop application shall stop with a clear message if the hub has not been built. | Implemented |

---

### 3.9 Non-functional requirements

#### 3.9.1 Performance
| ID | Requirement | Status |
|---|---|---|
| NFR-01 | On the standard tier (Core i5, no GPU), the system shall process frames in real time, with a target of at least 15 FPS. | Target. Not yet measured on the school PC. |
| NFR-02 | An unattended alert shall be raised within about 1 second after the time threshold is reached. | Target. Not yet measured. |
| NFR-03 | The hub shall show the live feed without a noticeable delay of more than about 1 second. | Target. Not yet measured. |
| NFR-04 | The system shall not block the video feed while it writes an incident. | Implemented (snapshot is written by the worker thread; review for large loads) |

#### 3.9.2 Reliability and availability
| ID | Requirement | Status |
|---|---|---|
| NFR-05 | The system shall recover from a camera read failure without restarting the backend. | Implemented |
| NFR-06 | The system shall keep running if one detection frame fails, and log the error. | Implemented |
| NFR-07 | If the worker thread stops unexpectedly, the system shall restart it automatically. | Planned |
| NFR-08 | Each incident shall survive a backend restart. | Implemented (stored in SQLite) |

#### 3.9.3 Security
| ID | Requirement | Status |
|---|---|---|
| NFR-09 | Every API route except login, setup, setup status and the landing page shall require an authenticated session. | Implemented |
| NFR-10 | Admin-only actions shall be enforced on the server, not only hidden in the interface. | Implemented |
| NFR-11 | State-changing requests shall require a JSON body, which prevents simple cross-site form submissions. | Implemented |
| NFR-12 | Passwords shall be stored only as hashes. | Implemented |
| NFR-13 | The session secret key shall be random and stored locally, and may be overridden by the `VIGITRACK_SECRET_KEY` environment variable. | Implemented |
| NFR-14 | Attempts to read files outside the hub folder through the web server shall be refused. | Implemented (tested) |
| NFR-15 | The hub shall send security headers (Content-Security-Policy, X-Content-Type-Options, Referrer-Policy). | Implemented (CSP `default-src 'self'`, nosniff, X-Frame-Options DENY, Referrer-Policy same-origin, on every response) |
| NFR-16 | Browser-mode deployments on a network shall use HTTPS. | Planned |
| NFR-17 | Login attempts shall be rate-limited per IP address, in addition to per-account lockout. | Implemented (10 failed sign-ins per address in 60 s, then 429) |
| NFR-18 | The audit log shall be tamper-evident (each entry linked to the previous). | Implemented (SHA-256 hash chain; `GET /api/audit/verify` reports the first broken entry) |
| NFR-19 | The project shall run a dependency vulnerability audit before each release. | Partial. First audit run in Phase 2: no high or critical advisories in runtime npm dependencies (4 moderate, 2 low, in template tooling). `pip-audit` not yet installed for the Python packages. |

#### 3.9.4 Privacy
| ID | Requirement | Status |
|---|---|---|
| NFR-20 | The system shall not use face recognition or any biometric identity matching. | Implemented (by design; no such code exists) |
| NFR-21 | The system shall not send video or incident data to any external service. | Implemented |
| NFR-22 | Snapshots shall be kept only as long as the retention period allows. | Implemented (retention worker deletes old snapshots with their incidents) |
| NFR-23 | Snapshots shall, by default, blur people's faces, with unblurred copies available only to admins with a logged reason. | Planned. Needs accuracy testing before adoption. |
| NFR-24 | The hub shall show a notice on the login page describing what is recorded and for how long. | Implemented (fetched from the public `GET /api/notice`; the period follows the retention setting) |
| NFR-25 | The system shall support deleting all data for a given period, to meet data subject requests. | Implemented (admin deletes a date range from the incidents page, `POST /api/incidents/purge`, audited) |

#### 3.9.5 Usability
| ID | Requirement | Status |
|---|---|---|
| NFR-26 | A new user shall be able to complete first-run setup from the browser or the desktop window without reading the documentation. | Implemented (desktop path verified; browser path awaiting user test) |
| NFR-27 | The hub shall follow the Studio Admin layout and include a sidebar that shows only the pages the user can use. | Implemented |
| NFR-28 | Error messages shown to users shall say what went wrong and what to do next. | Partial |

#### 3.9.6 Maintainability
| ID | Requirement | Status |
|---|---|---|
| NFR-29 | The detection, state engine, storage and API shall be separate modules. | Implemented |
| NFR-30 | Automated tests shall cover accounts, setup, incidents and the desktop server. | Implemented (see Section 4) |
| NFR-31 | Detection changes shall be measured against a labelled scenario set before release. | Partial. Evaluation harness built (`app/evaluation/`): FSM vs stationary-timer baseline scored on a five-scenario synthetic set with ground truth (`test_evaluation.py` 27/27). The labelled real-footage set is still to be recorded. |

#### 3.9.7 Portability
| ID | Requirement | Status |
|---|---|---|
| NFR-32 | The backend shall run on Windows. Other platforms are not a requirement. | Implemented (Windows only tested) |

---

### 3.10 External interface requirements

#### 3.10.1 User interfaces
- Hub pages: Login, First-run setup, Dashboard, Cameras, Incidents, Users (admin), Settings, My account, Landing (`/`).
- Desktop window: the same hub in a native window, without an address bar.

#### 3.10.2 Camera interfaces
- USB or built-in webcam, opened through OpenCV (DirectShow on Windows).
- RTSP video stream, opened through OpenCV, given as a URL in the settings.

#### 3.10.3 Software interfaces
- HTTP API (JSON) served by Flask. Main routes:

| Method | Route | Access |
|---|---|---|
| GET | `/api/setup/status` | Public |
| POST | `/api/setup` | Public, only before the first account exists |
| POST | `/api/login` | Public |
| POST | `/api/logout` | Logged in |
| GET | `/api/me` | Logged in |
| POST | `/api/me/password` | Logged in |
| GET, POST | `/api/users` | Admin |
| PATCH, DELETE | `/api/users/<id>` | Admin |
| GET | `/api/audit` | Admin |
| GET | `/api/audit/verify` | Admin |
| GET | `/api/notice` | Public |
| GET | `/video_feed` | Logged in |
| GET | `/api/alerts` | Logged in |
| GET | `/api/camera/status` | Logged in |
| POST | `/api/incidents/<id>/review` | Logged in (operators and admins) |
| GET | `/api/incidents` | Logged in |
| GET | `/api/incidents/<id>` | Logged in |
| GET | `/api/incidents/<id>/image` | Logged in |
| DELETE | `/api/incidents/<id>` | Admin |
| POST | `/api/incidents/clear` | Admin |
| POST | `/api/incidents/purge` | Admin (date range) |
| GET | `/api/settings` | Logged in |
| POST | `/api/settings` | Admin |

- Storage: SQLite database file `backend/data/vigitrack.db`, with tables `users`, `audit_log`, `incidents`.
- Snapshot files: `backend/data/incidents/<id>.jpg`.

#### 3.10.4 Hardware interfaces
- Camera (see 3.10.2).
- Speaker, for the audible alert.
- Intel CPU (OpenVINO) or NVIDIA GPU (CUDA), for inference.

### 3.11 Data requirements

| Data item | Stored in | Contents | Protection |
|---|---|---|---|
| User account | `users` | username, password hash, role, active flag, lockout state, last login, must-change flag | Hashed password; admin-only management |
| Audit entry | `audit_log` | time, actor, action, detail, previous-entry hash, entry hash | Admin-only read; tamper-evident SHA-256 chain |
| Incident | `incidents` | class, track IDs, distance, thresholds, camera name, time, status, state history, snapshot file name, review status, review note, reviewer, review time | Authenticated read; admin-only delete |
| Snapshot | `backend/data/incidents/` | annotated JPEG frame | Authenticated read; deleted with its incident by retention or range purge |
| Settings | `backend/data/settings.json` | thresholds, classes, camera source (masked if a URL), camera name, audio, retention days, session secret key | File is git-ignored; RTSP URLs encrypted with DPAPI, with a secret token and a masked copy in the file |

---

## 4. Verification

### 4.1 Test evidence available

| Area | Test | Result |
|---|---|---|
| Accounts, roles, lockout, audit | Account test script | 65 / 65 checks passed |
| First-run setup | Setup test script | 28 / 28 checks passed |
| Incidents and API | Incident test script | 24 / 24 checks passed |
| Original backend | Initial test script | 26 / 26 checks passed |
| Extended backend | Second extended script | 63 / 63 checks passed |
| Desktop server | Desktop server test | 7 / 7 checks passed |
| Ownership and alert logic (simulated clock) | `test_fsm.py` | 16 / 16 checks passed |
| Incident review, idle timeout, camera status, live monitored classes | `test_phase1.py` | 31 / 31 checks passed |
| Credential encryption, retention, purge, rate limit, headers, audit chain | `test_phase2.py` | 42 / 42 checks passed |
| Evaluation harness: baseline vs FSM, synthetic set, scoring math | `test_evaluation.py` | 27 / 27 checks passed |
| Hub build | `npm run build` | Passes |
| Desktop start-up | Manual on developer PC | Window opens; setup page appears without code |

The test scripts are now in `backend/tests/` and run from the backend folder with `python tests/<name>.py`. They use a stubbed camera and detector where needed, so they run without the camera or model.

### 4.2 Verification not yet done
- **Detection accuracy on real footage.** The evaluation harness is built (`app/evaluation/`) and scored on a synthetic five-scenario set (VigiTrack 3/3 recall, 0 false alarms; stationary-timer baseline 3/3 recall, 4 false alarms). No *labelled real* footage has been measured yet; precision, recall and false alarms per hour on real clips are still unknown.
- **Real RTSP camera.** Not yet tested. A soak command exists (`python -m app.evaluation.cli soak --url rtsp://... --hours 2`).
- **Performance on the school PC.** FPS and alert latency are not measured on the target hardware. A benchmark command exists (`python -m app.evaluation.cli benchmark`).
- **Desktop camera feed.** Confirmed that the window opens. Confirmation that the live feed and detection run inside the window is pending.
- **Browser-mode first-run setup.** Awaiting user test.

### 4.3 Requirement-to-verification mapping

| Requirements | Verified by |
|---|---|
| FR-41 to FR-56, NFR-09, NFR-10, NFR-12 | Accounts and setup test scripts |
| FR-33 to FR-36 | Incident test script |
| FR-63 to FR-67 | Desktop server test and manual start-up |
| FR-16 to FR-26 | `backend/tests/test_fsm.py` (16 / 16 checks) and `backend/tests/test_evaluation.py` (27 / 27 checks, FSM vs baseline on the synthetic scenario set). The labelled real-footage scenario set is still to be recorded (NFR-31). |
| NFR-01 to NFR-03 | Planned performance measurement |

---

## 5. Open Issues and Known Gaps

| ID | Issue | Impact | Related requirement | Planned fix |
|---|---|---|---|---|
| O-1 | ~~Ownership takeover accepted a passer-by on the first frame.~~ | Closed in Phase 0. Takeover now needs 10 consecutive frames within half the threshold, and the README wording is corrected. | FR-23 | Closed |
| O-2 | ~~Each bag ID raised at most one incident per process run.~~ | Closed in Phase 0. Incidents are keyed by separation episode. | FR-26 | Closed |
| O-3 | Distances are in pixels, so the same threshold means different real distances at different camera positions. | Results differ between cameras. | FR-16, FR-19 | Normalise distance by the owner's box height. |
| O-4 | Accuracy has not been measured on real footage. | The contribution claim is not yet evidenced. | Section 4.2 | Harness built in Phase 3 (`app/evaluation/`): baseline comparison scored on a synthetic set (27/27 checks). Remaining: record and label real clips with `record-video`, then re-run `evaluate`. |
| O-5 | One camera per backend process. | The hub's multi-camera pages cannot show more than one camera. | FR-01, FR-06 | Per-camera workers under a supervisor. |
| O-6 | ~~Camera credentials are stored in plain text in the settings file.~~ | Closed in Phase 2. RTSP URLs are encrypted with Windows DPAPI; the settings file and every log line keep only a masked copy. | FR-62 | Closed |
| O-7 | ~~The session secret key was stored in git history.~~ | Closed in Phase 0: the key was regenerated on 13 Nov 2026, so the old value no longer works. It still appears in old commits. | NFR-13 | Closed (history not rewritten) |
| O-8 | Snapshots have no retention limit and show people unblurred. | Privacy compliance risk. | FR-40, NFR-22, NFR-23 | Retention closed in Phase 2 (configurable retention, hourly purge, admin range delete). Face blurring still needs accuracy testing. |
| O-9 | Object list covers only the COCO classes. Parcels and boxes are not detected; laptops are not in the monitored set. | Limits the scope of what can be reported. | FR-07, FR-15 | Add laptop (COCO class 63); fine-tune for parcels if needed. |
| O-10 | RTSP has not been tested on real hardware. | Unknown behaviour with IP cameras. | FR-01 | Test with a real camera or NVR; consider TCP transport. |
| O-11 | Browser-mode deployment has no HTTPS. | Credentials and video cross the network unencrypted. | NFR-16 | HTTPS reverse proxy before any network deployment. |
| O-12 | Installer not yet built. Desktop mode requires Python and the built hub. | Not yet deployable to non-technical staff. | FR-63 to FR-67 | PyInstaller and Inno Setup packaging. |

---

## 6. Requirements Summary

| Category | Total | Implemented | Partial | Planned |
|---|---|---|---|---|
| Video capture (FR-01 to FR-06) | 6 | 6 | 0 | 0 |
| Detection and tracking (FR-07 to FR-15) | 9 | 9 | 0 | 0 |
| Ownership and state (FR-16 to FR-26) | 11 | 11 | 0 | 0 |
| Visual output (FR-27 to FR-32) | 6 | 6 | 0 | 0 |
| Incidents (FR-33 to FR-40) | 8 | 7 | 0 | 1 |
| Accounts and sessions (FR-41 to FR-56) | 16 | 16 | 0 | 0 |
| Settings and alerts (FR-57 to FR-62) | 6 | 6 | 0 | 0 |
| Desktop (FR-63 to FR-67) | 5 | 5 | 0 | 0 |
| **Functional total (FR-01 to FR-67)** | **67** | **66** | **0** | **1** |
| Non-functional (NFR-01 to NFR-32) | 32 | 23 | 3 | 6 |

Of the 6 non-functional requirements counted as Planned, three (NFR-01 to NFR-03) are performance targets that are not yet measured, and the rest (NFR-07 worker restart, NFR-16 HTTPS, NFR-23 face blurring) are planned work. Three more (NFR-19 dependency audit, NFR-28 error-message quality, NFR-31 labelled scenario set) are Partial.

---

## 7. Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 13 Nov 2026 | Project team | Initial baseline, based on commit `4558ce5`. |







