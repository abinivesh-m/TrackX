"""
tests/test_alert_data_provenance.py

SIH26127 "Final Data Integrity" audit (2026-09-11) - regression tests for a
real Class D gap found while auditing Alerts: SUSPICIOUS_ROUTE and
REPEATED_CAMERA alerts (and BLACKLISTED_VEHICLE too) carried no indication
of whether the trajectory that triggered them contained
demo/seed_demo_data.py's DEMO_SYNTHETIC observations - unlike Vehicle
Search/Trajectory (hop.data_source) and, after this same audit's earlier
fix, Route Anomalies. AlertsPage.tsx had nothing to key a warning badge on
for these two/three alert types; a demo-seeded "impossible transition" or
"blacklisted vehicle" scenario (e.g. plate TN77IM9999, TN38AB1234 - see
demo/seed_demo_data.py) could appear in the live Alerts feed with no
indication it wasn't a genuine detection.

Fixed by intelligence/alerts.py's _trajectory_data_source(), stored in
each alert's `evidence.data_source` field (no new DB column needed - the
`alerts` table already has a JSON `evidence` column for exactly this kind
of per-alert-type proof), and a shared SyntheticDataBadge component in
AlertsPage.tsx (pinned separately by
tests/test_alert_frontend_labeling.py's regex scan, since this repo has no
JS test runner).

No ultralytics/paddleocr/torch dependency.
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence.alerts import _trajectory_data_source, scan_trajectories_for_alerts
from intelligence.trajectory import build_trajectories

BASE_TIME = datetime(2026, 1, 1, 9, 0, 0)


def _obs(plate, camera_id, ts, data_source=None, track_id=None):
    obs = {
        "plate_text": plate,
        "normalized_plate": plate,
        "confidence": 0.9,
        "camera_id": camera_id,
        "timestamp": ts.isoformat(),
        "lat": 11.0205,
        "long": 76.9667,
    }
    if data_source is not None:
        obs["data_source"] = data_source
    if track_id:
        obs["track_id"] = track_id
    return obs


class TestTrajectoryDataSourceHelper:
    def test_all_real_observations_yields_real_inference(self):
        traj = {"observations": [
            _obs("TN10AB1234", "CAM_01", BASE_TIME, data_source="REAL_INFERENCE"),
            _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(minutes=3), data_source="REAL_INFERENCE"),
        ]}
        assert _trajectory_data_source(traj) == "REAL_INFERENCE"

    def test_any_synthetic_observation_yields_demo_synthetic(self):
        traj = {"observations": [
            _obs("TN10AB1234", "CAM_01", BASE_TIME, data_source="REAL_INFERENCE"),
            _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(minutes=3), data_source="DEMO_SYNTHETIC"),
        ]}
        assert _trajectory_data_source(traj) == "DEMO_SYNTHETIC"

    def test_all_synthetic_observations_yields_demo_synthetic(self):
        traj = {"observations": [
            _obs("TN77IM9999", "CAM_01", BASE_TIME, data_source="DEMO_SYNTHETIC"),
            _obs("TN77IM9999", "CAM_05", BASE_TIME + timedelta(seconds=2), data_source="DEMO_SYNTHETIC"),
        ]}
        assert _trajectory_data_source(traj) == "DEMO_SYNTHETIC"

    def test_unlabeled_observations_yield_none_not_real(self):
        traj = {"observations": [
            _obs("TN10AB1234", "CAM_01", BASE_TIME),
            _obs("TN10AB1234", "CAM_02", BASE_TIME + timedelta(minutes=3)),
        ]}
        assert _trajectory_data_source(traj) is None


class TestAlertEvidenceCarriesDataSource:
    def test_repeated_camera_alert_evidence_labels_synthetic_trajectory(self):
        plate = "TN99ZZ0000"
        obs = [
            _obs(plate, "CAM_03", BASE_TIME, data_source="DEMO_SYNTHETIC"),
            _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=90), data_source="DEMO_SYNTHETIC"),
            _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=200), data_source="DEMO_SYNTHETIC"),
        ]
        trajs = build_trajectories(obs)
        alerts = scan_trajectories_for_alerts(trajs, all_observations=obs, persist_to_db=False)
        repeated = [a for a in alerts if a["type"] == "REPEATED_CAMERA_SIGHTING"]
        assert len(repeated) == 1
        assert repeated[0]["evidence"]["data_source"] == "DEMO_SYNTHETIC"

    def test_repeated_camera_alert_evidence_labels_real_trajectory(self):
        plate = "TN99ZZ0000"
        obs = [
            _obs(plate, "CAM_03", BASE_TIME, data_source="REAL_INFERENCE"),
            _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=90), data_source="REAL_INFERENCE"),
            _obs(plate, "CAM_03", BASE_TIME + timedelta(seconds=200), data_source="REAL_INFERENCE"),
        ]
        trajs = build_trajectories(obs)
        alerts = scan_trajectories_for_alerts(trajs, all_observations=obs, persist_to_db=False)
        repeated = [a for a in alerts if a["type"] == "REPEATED_CAMERA_SIGHTING"]
        assert len(repeated) == 1
        assert repeated[0]["evidence"]["data_source"] == "REAL_INFERENCE"
