import json

from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from analytics.analytics import (
    vehicles_per_camera,
    busiest_camera,
    cross_camera_route_frequency,
    repeated_camera_sightings,
    average_vehicle_speed,
    origin_destination_patterns,
    congestion_hotspots,
)

store = ObservationStore("outputs/results/observations.db")
observations = store.all_observations()
trajectories = build_trajectories(observations)

lines = []
lines.append("total_observations: %d" % len(observations))
lines.append("total_trajectories: %d" % len(trajectories))

multi_cam = [t for t in trajectories if len(getattr(t, "camera_sequence", None) or []) > 1]
if not multi_cam:
    for t in trajectories:
        cams = getattr(t, "cameras", None) or []
        if isinstance(cams, dict):
            cams = list(cams)
        if len(cams) > 1:
            multi_cam.append(t)
            break
lines.append("multi_camera_trajectories: %d" % len(multi_cam))

counts = vehicles_per_camera(observations)
lines.append("vehicles_per_camera: %s" % json.dumps(counts, sort_keys=True))
lines.append("busiest_camera: %s" % json.dumps(busiest_camera(observations)))

routes = cross_camera_route_frequency(trajectories)
lines.append("top_cross_camera_routes: %s" % json.dumps(dict(list(routes.items())[:5]) if hasattr(routes, "items") else routes[:5], default=str))

speeds = average_vehicle_speed(trajectories)
lines.append("average_speed: %s" % json.dumps(speeds, default=str))

od = origin_destination_patterns(trajectories)
lines.append("od_patterns: %s" % json.dumps(od, default=str)[:600])

hot = congestion_hotspots(observations, trajectories)
lines.append("congestion: %s" % json.dumps(hot, default=str)[:600])

rep = repeated_camera_sightings(trajectories)
lines.append("repeated_sightings: %s" % json.dumps(rep, default=str)[:300])

import sqlite3
conn = sqlite3.connect("outputs/results/observations.db")
alerts = conn.execute("SELECT alert_type, COUNT(*) FROM alerts GROUP BY alert_type").fetchall()
lines.append("alerts_by_type: %s" % json.dumps(dict(alerts)))
lines.append("alerts_total: %d" % conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0])
lines.append("blacklist_total: %d" % conn.execute("SELECT COUNT(*) FROM blacklist").fetchone()[0])
conn.close()

import pathlib
pathlib.Path("_analytics_now.txt").write_text("\n".join(str(x) for x in lines), encoding="utf-8")
print("DONE")
