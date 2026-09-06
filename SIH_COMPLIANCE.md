# SIH-26127 Compliance Matrix — TrackX (Bharat Electronics Ltd.)

Verification date: 2026-09-05. Status values: PASS / PARTIAL / FAIL / NOT VERIFIED.
"PASS" is only claimed where a measurement or an end-to-end run in this session
demonstrates it.

| # | SIH Requirement | Implementation | Evidence | Test | Measured result | Status |
|---|---|---|---|---|---|---|
| 1 | High-accuracy ANPR/OCR (>90% target, Indian plates) | LPRNet (`recognition/lprnet_ocr.py`) + PaddleOCR + fusion | `data/ocr_eval/authoritative_benchmark.json` (731 real crops, 673 unique plates) | exact-match on 731-image benchmark | LPRNet 34.2%, PaddleOCR 46.8%, fusion 50.2% exact; 90% not reached — resolution-limited crop set (see blocker) | **FAIL** (target attempted, measured honestly) |
| 1b | Varying lighting/weather/angle robustness | Adaptive pre-processing in `ocr_reader.preprocess_plate_crop` (CLAHE, gamma, sharpening, threshold variants) | code | unit tests + benchmark includes night/day crops | included in benchmark; no separate marginal measurement | PARTIAL |
| 2 | Single-plate trajectory across distributed cameras | `intelligence/trajectory.py` fusion linking + `backend /trajectory`, `/vehicles` | demo network run | `python -m intelligence.trajectory`; browser Vehicle Intelligence | TN10AB1234 → CAM_01→02→03→05, 4 hops HIGH confidence; TN45BS9012 links a 0.58-conf confusable read | **PASS** |
| 3 | Macro traffic analytics | `analytics/analytics.py` + `/analytics/*` | Operations pages render charts from observation rows | browser walkthrough | density 56 vehicles/7 cams, per-camera counts, hourly profile, OD top routes, congestion scores (CAM_02 0.74) | **PASS** |
| 4 | Centralized scalable platform | FastAPI backend + SQLite store + React SPA | running stack | manual QA | all APIs 200 after fixes | PASS |
| 5 | High-precision OCR module | LPRNet primary + PaddleOCR secondary + format validation | benchmark (above) | 731-image run | 50.2% fusion exact — see row 1 | FAIL |
| 6 | Query trajectory interface | Vehicle Intelligence + Trajectory Search pages, `/vehicles/search` | browser | search TN10AB1234 | 4 observations rendered chronologically with map; summary fields fixed this session | PASS |
| 7 | GIS-integrated dashboard | `/gis/*`, Leaflet layers (cameras, heatmap, bottlenecks, OD) | browser | `GET /gis/cameras|congestion|od_flow` | 7 nodes, 7 bottleneck rows, 11 OD corridors; endpoints 200 (were 500, fixed) | PASS |
| 8 | Real-time blacklist alerts | `BlacklistStore` + `intelligence/alerts.py` + Alerts page | demo DB | `python -m intelligence.alerts` + browser | BLACKLIST_MATCH TN38AB1234 (HIGH) & DL8CAG4321 (MEDIUM, severity from store) | PASS |
| 9 | Suspicious route anomaly alerts | `anomaly_scoring.py` (impossible speed, cloned plate, loitering) | demo DB | scan + browser Alerts | ROUTE_ANOMALY 420/504 km/h cloned-plate with explainable reasons; REPEATED_CAMERA loitering | PASS |
| 10 | No EasyOCR anywhere | code search for easyocr | grep whole repo | — | zero references outside historical .md reports of its removal | PASS |
| 11 | Only LPRNet + PaddleOCR engines | `ocr_reader.py` | code read | — | zero Tesseract/EasyOCR references after removal this session; only LPRNet + PaddleOCR paths remain | PASS |
| 12 | Dataset audited; junk excluded; duplicates handled | `scripts/build_authoritative_benchmark.py`, audit manifests | manifest JSON | re-run builder | 731 kept / 6 junk-GT rejects documented (not deleted) | PASS |
| 13 | No train/test leakage | sha256 dedupe at benchmark level; GT-grouped splits exist | manifests | — | authoritative benchmark is single-file (no internal leakage); training splits not retrained this session | PARTIAL |
| 14 | Ground truth verified | visual spot-checks of crops + GT (OLX, video-filename) | contact sheets under `outputs/contact_sheets/` | human review of samples | sample GT matched plate text on review; junk labels excluded | PASS (sampled) |
| 15 | Demo mode clearly labelled | DEMO MODE banners on every page | browser | QA walkthrough | labelled on Operations/Cameras/Vehicles/Alerts/GIS/Analytics | PASS |
| 16 | Failure recovery | try/except + `try_init_ocr` SystemExit guard, degraded camera statuses | code | existing tests (`test_day1_visual_pipeline.py` etc.) | suite exercised historically; not all re-run this session | PARTIAL |
| 17 | Security | JWT auth, RBAC, admin-only pages, CORS, seeded dev credentials documented | backend core/security.py | manual login + roles | admin login OK; security warnings printed for default creds | PASS (dev) |
| 18 | Performance/latency measurement | instrumentation scripts | `measure_trajectory_latency.py` | not re-run this session | — | NOT VERIFIED (this session) |

### Honest blocker statement (Requirement 1 / 5)

The OCR benchmark is a genuine, unmodified set of 731 real Indian-plate crops
with verified ground truth. Measured exact-match accuracy is 50.2% with the
LPRNet+PaddleOCR fusion. The dominant technical blocker is input resolution:
most crops are 9–25 px tall plate excerpts from listings/recorded footage; error
histogram shows 310/731 errors are within 1–2 characters of the truth, and an
ideal single-character corrector would cap the benchmark near 59%. Reaching 90%
requires training a recognizer on legible, ANPR-resolution Indian plates and
multi-frame voting per vehicle — listed as the required next step, not claimed
as done.
