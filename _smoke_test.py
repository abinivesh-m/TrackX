"""End-to-end smoke test for TrackX intelligence chain on a temp database."""
import os
import sys
import tempfile
from datetime import datetime, timedelta

from database.observation_store import ObservationStore
from database.blacklist_store import BlacklistStore
from network.camera_network import CAMERAS

tmp = os.path.join(tempfile.gettempdir(), "trackx_smoke.db")
if os.path.exists(tmp):
    os.remove(tmp)
store = ObservationStore(db_path=tmp)

base = datetime(2026, 9, 1, 8, 0, 0)

def rec(plate, cam, ts, conf=0.9, vec=None):
    c = CAMERAS[cam]
    return {
        "plate_text": plate,
        "confidence": conf,
        "camera_id": cam,
        "timestamp": ts.isoformat(),
        "lat": c["lat"],
        "long": c["long"],
        "track_id": "t1",
        "vehicle_type": "car",
    }

rows = [
    (rec("TN10AB1234", "CAM_01", base), [0.1] * 512),
    (rec("TN10AB1234", "CAM_02", base + timedelta(seconds=200)), [0.1] * 512),
    (rec("TN10AB1234", "CAM_03", base + timedelta(seconds=420)), [0.1] * 512),
    (rec("TN38AB1234", "CAM_01", base + timedelta(minutes=10)), [0.2] * 512),
    (rec("TN38AB1234", "CAM_02", base + timedelta(minutes=13)), [0.2] * 512),
]
store.add_many([r for r, _ in rows], [v for _, v in rows])
store.close()

black = BlacklistStore(db_path=tmp)
black.add_plate("TN38AB1234", description="smoke", severity="HIGH")
black.close()

from intelligence.trajectory import build_trajectories
from intelligence.alerts import scan_trajectories_for_alerts
from analytics.analytics import (
    vehicles_per_camera,
    hourly_density,
    origin_destination_patterns,
    average_vehicle_speed,
    congestion_hotspots,
)

store = ObservationStore(db_path=tmp)
obs = store.all_observations()
store.close()

trajs = build_trajectories(obs)
alerts = scan_trajectories_for_alerts(trajs, blacklist_store=BlacklistStore(db_path=tmp))
counts = vehicles_per_camera(obs)
od = origin_destination_patterns(trajs)
speed = average_vehicle_speed(trajs)
cong = congestion_hotspots(obs, trajs)
print("observations:", len(obs))
print("trajectories:", len(trajs))
print("alerts:", len(alerts), [a.get("type") for a in alerts])
print("counts:", counts)
print("od pairs:", od.get("top_od_pairs"))
print("speed status:", speed.get("status"))
print("congested:", len(cong.get("congested_cameras", [])))

from gis.gis_map import generate_map

out = os.path.join(tempfile.gettempdir(), "trackx_smoke_map.html")
generate_map(out_path=out, include_heatmap=True)
print("map exists:", os.path.exists(out))
print("SMOKE_OK")