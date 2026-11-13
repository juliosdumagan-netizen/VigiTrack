# VigiTrack Development Roadmap

This roadmap orders the planned work from the Software Requirements Specification (`docs/SRS_VigiTrack.md`). Each phase has a goal, the requirements it covers, and an exit test. A phase is finished only when its exit test passes.

Effort is relative: **S** = a few days, **M** = about a week, **L** = two weeks or more.

---

## Phase 0: Stabilise

**Goal:** fix the correctness issues in the core contribution and clean up the project, so later work builds on a sound base.

| Item | Source | Effort |
|---|---|---|
| Tighten ownership takeover: require several consecutive frames near the bag; never reassign while the original owner is visible | O-1, FR-23 | M |
| Re-arm alerts per separation episode instead of once per run | O-2, FR-26 | S |
| Correct the README claim that passers-by cannot take over a bag | O-1 | S |
| Rotate the session secret key | O-7, NFR-13 | S |
| Move the test scripts into `backend/tests/` and commit them | Section 4.1 of SRS | S |
| Commit the SRS and roadmap | — | S |

**Exit test:**
- All existing test scripts pass (accounts 65/65, setup 28/28, incidents 24/24, desktop 7/7).
- New scenario cases for takeover and re-arm pass.
- `docs/SRS_VigiTrack.md` status updated for FR-23 and FR-26.

---

## Phase 1: Operator workflow

**Goal:** make alerts something an operator can act on, and make the hub usable during a live shift. This is the phase to show in a demo.

| Item | Source | Effort |
|---|---|---|
| Acknowledge, verify or dismiss an incident, with a note | FR-38 | M |
| Browser notification and sound when a new incident arrives | FR-61 | S |
| Camera status: online, reconnecting, offline, shown on the dashboard | FR-06 | S |
| Idle session timeout (about 30 minutes) | FR-54 | S |
| Monitored-class changes apply without restart | FR-59 | S |

**Exit test:**
- An operator can acknowledge and dismiss an incident, and the status and note are saved and shown in the audit log.
- A new incident shows a notification in the hub without a page refresh.
- Unplugging the camera shows "offline" within about 10 seconds, and replugging returns it to "online".
- A logged-in session ends after the idle period.

---

## Phase 2: Security and privacy

**Goal:** meet the privacy and security requirements that a school deployment will need to approve.

| Item | Source | Effort |
|---|---|---|
| Snapshot and incident retention, with configurable period and logged deletions | FR-40, NFR-22 | M |
| Encrypt camera credentials with Windows DPAPI | FR-62, O-6 | S |
| Security headers and Content-Security-Policy on the hub | NFR-15 | S |
| Per-IP login rate limiting | NFR-17 | S |
| Tamper-evident audit log (hash chain) | NFR-18 | M |
| Privacy notice on the login page | NFR-24 | S |
| Delete all data for a date range (data subject requests) | NFR-25 | M |
| Dependency audit (`npm audit`, `pip-audit`) | NFR-19 | S |

**Exit test:**
- Snapshots older than the retention period are removed and each removal appears in the audit log.
- The settings file contains no plain-text camera password.
- The hub returns the security headers, checked in the browser's developer tools.
- Ten wrong logins from one IP in a minute are throttled, even across different accounts.
- Altering one audit entry is detected by the verification check.

---

## Phase 3: Evaluation and real-world proof

**Goal:** produce the evidence the panel asked for: that the system works in real time, on real hardware and camera, and that the person-bag logic reduces false alarms.

This phase has the most influence on the defense, and most of it can run in parallel with Phases 1 and 2, since it needs a camera and footage rather than code changes.

| Item | Source | Effort |
|---|---|---|
| Record and label a scenario set: seated reader, owner walks away, passer-by, owner leaves frame, abandoned bag | NFR-31 | M |
| Build a stationary-timer baseline and run both on the same clips | Section 4.2 | M |
| Report false alarms per hour, detection latency and recall | FR-16 to FR-26 | S |
| Test with a real RTSP camera or NVR, including TCP transport | O-10, FR-01 | M |
| Measure FPS and alert latency on the school's Core i5 PC | NFR-01, NFR-02 | S |
| Normalise distance by the owner's box height and re-measure | O-3 | M |

**Exit test:**
- A table in the defense handbook shows both methods' false alarms per hour and recall on the same clips.
- RTSP stream runs for at least 2 hours without a crash or manual restart.
- Measured FPS and alert latency are recorded for the target hardware.

**Note on the normalisation item:** change it only after the baseline comparison exists, so any improvement can be measured against the same clips.

---

## Phase 4: Zones and reporting

**Goal:** reduce false alarms in known areas, and give admins a way to share results.

| Item | Source | Effort |
|---|---|---|
| Ignore and watch zones, drawn on the camera view | Roadmap idea | L |
| Export incidents as CSV | FR-39 | S |
| Single-incident PDF with snapshot and timeline | FR-39 | M |
| Add laptop class to the monitored set, tested in an office scene | O-9 | S |

**Exit test:**
- An alert inside an ignore zone is not raised, and one inside a watch zone is.
- The CSV opens in Excel with the same values as the hub.
- The PDF of one incident includes the snapshot, timeline and settings used.
- Laptop detections are measured on the scenario set, and the false-alarm change is recorded.

---

## Phase 5: Multi-camera

**Goal:** more than one camera in one installation, with a failure in one camera not affecting the others.

| Item | Source | Effort |
|---|---|---|
| One worker per camera, under a supervisor that restarts a failed worker | O-5, NFR-07 | L |
| Per-camera thresholds, monitored classes and zones | O-5 | M |
| Hub shows each camera's feed and status | O-5 | M |
| Test with two cameras running together | — | S |

**Exit test:**
- Two cameras run together for 2 hours, and the FPS of each stays at or above the single-camera figure from Phase 3, within a set margin.
- Disconnecting one camera leaves the other running, and the first recovers when reconnected.

**Decision point:** if the deployment is a single PC with one camera, this phase can be deferred. Confirm the deployment before starting it.

---

## Phase 6: Packaging and deployment

**Goal:** install VigiTrack on a school PC without Python or a terminal.

| Item | Source | Effort |
|---|---|---|
| Package the desktop app with PyInstaller | O-12, FR-63 to FR-67 | L |
| Inno Setup installer with Start menu entry and uninstaller | O-12 | M |
| Test the installer on a clean PC without Python | O-12 | S |
| HTTPS reverse proxy for browser-mode network deployments | O-11, NFR-16 | M |

**Exit test:**
- The installer runs on a clean Windows PC and the desktop window opens with the hub, setup page and camera feed working.
- Uninstalling leaves the user's data folder in place, unless the user chooses to delete it.

**Note:** the installer will be large (roughly 1 to 2 GB) because of PyTorch and the model. Plan for this on the school's network and storage.

---

## Dependencies and sequence

```
Phase 0 (stabilise)
  ├── Phase 1 (operator workflow)  ──┐
  ├── Phase 2 (security, privacy)  ──┤
  └── Phase 3 (evaluation)  ─────────┤  (can run alongside 1 and 2)
                                     ▼
                         Phase 4 (zones, reporting)
                                     ▼
                         Phase 5 (multi-camera)   [only if deployment needs it]
                                     ▼
                         Phase 6 (packaging)
```

- Phase 0 comes first, since everything else depends on correct alert logic.
- Phase 3 measures the logic, so the logic fixes in Phase 0 must be done first. Otherwise the baseline numbers will change again.
- Phase 4 zones should only be built after Phase 3, so the effect of each zone can be measured.
- Phase 6 packaging should come after Phase 2, since the installer should not ship with plain-text credentials.

## Suggested defense milestones

| Milestone | Phases complete | What the panel sees |
|---|---|---|
| Demo-ready | 0, 1 | Live operator workflow, acknowledgement, notifications, camera status |
| Evidence-ready | 0, 3 | Measured false-alarm comparison, real RTSP results, target-hardware FPS |
| Deployment-ready | 2, 6 | Privacy controls, installer, clean-PC install |
| Full scope | 4, 5 | Zones, reporting, multi-camera |

If time is short, complete **Phase 0, Phase 1 and Phase 3** before the defense. Those three deliver the working behaviour, the operator workflow and the evidence the panel asked for.

## Status

| Phase | Status |
|---|---|
| 0. Stabilise | Complete, not yet committed. All six test suites pass (`python tests/run_all.py`). |
| 1. Operator workflow | Built and tested in code (all 8 suites pass, frontend builds). Not yet checked in the live hub on the school PC. |
| 2. Security and privacy | Built and tested in code (`test_phase2.py` 42/42; all 8 suites pass, frontend builds). Dependency audit and a live header check still to do. |
| 3. Evaluation | Harness built and tested in code: stationary-timer baseline, five-scenario synthetic set, scorer (FA/h, recall, latency), CLI (`record-video`, `benchmark`, `soak`); `test_evaluation.py` 27/27, all 9 suites pass, frontend builds. Real-footage labelling, school-PC FPS numbers and the 2-hour RTSP soak test still to be run by hand. |
| 4. Zones and reporting | Not started |
| 5. Multi-camera | Not started |
| 6. Packaging | Not started |
