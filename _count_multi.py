import io

from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories

store = ObservationStore("outputs/results/observations.db")
observations = store.all_observations()
trajectories = build_trajectories(observations)

multi = 0
for t in trajectories:
    cams = {o.get("camera_id") for o in t["observations"]}
    if len(cams) > 1:
        multi += 1

lines = [
    "total_trajectories: %d" % len(trajectories),
    "multi_camera_trajectories: %d" % multi,
]
io.open("_multi_count.txt", "w", encoding="utf-8").write("\n".join(lines))
print("DONE")
