"""
gis_map.py

generates an interactive HTML map showing camera locations and a
searched vehicle's route across them. uses folium (built on leaflet),
no api key needed, opens directly in a browser — good enough for demo.

usage (run from project root):
    python -m gis.gis_map TN38AB1234
"""

import sys
import os
import folium
from folium.plugins import HeatMap

from network.camera_network import CAMERAS
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from analytics.analytics import vehicles_per_camera
from config import RESULTS_DIR


def plot_camera_network(m):
    for cam_id, info in CAMERAS.items():
        folium.Marker(
            [info["lat"], info["long"]],
            popup=f"{cam_id} - {info['name']}",
            icon=folium.Icon(color="blue", icon="camera"),
        ).add_to(m)


def plot_trajectory(m, traj):
    coords = [(o["lat"], o["long"]) for o in traj["observations"]]

    folium.PolyLine(coords, color="red", weight=4, opacity=0.8).add_to(m)

    for obs in traj["observations"]:
        folium.CircleMarker(
            [obs["lat"], obs["long"]],
            radius=6,
            popup=f"{obs['camera_id']} @ {obs['timestamp']} (plate: {obs['plate_text']})",
            color="red",
            fill=True,
        ).add_to(m)


def plot_traffic_heatmap(m, observations):
    """
    Add a traffic heatmap layer based on vehicle density at camera locations.
    
    Args:
        m: Folium map object
        observations: List of observation dicts
    """
    # Calculate vehicle counts per camera
    camera_counts = vehicles_per_camera(observations)
    
    # Create heatmap data points with intensity based on vehicle count
    heat_data = []
    max_count = max(camera_counts.values()) if camera_counts else 1
    
    for cam_id, info in CAMERAS.items():
        count = camera_counts.get(cam_id, 0)
        if count > 0:
            # Normalize intensity (0-1) and use as weight
            intensity = count / max_count
            # Add multiple points for higher intensity
            num_points = int(count * 0.5) + 1  # Scale factor for visual effect
            for _ in range(num_points):
                heat_data.append([info["lat"], info["long"], intensity])
    
    if heat_data:
        HeatMap(
            heat_data,
            min_opacity=0.3,
            max_opacity=0.8,
            radius=25,
            blur=15,
            gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'orange', 1: 'red'}
        ).add_to(m)


def generate_map(search_plate=None, out_path=None, include_heatmap=True):
    """
    Generate an interactive map with camera network, trajectories, and optional heatmap.
    
    Args:
        search_plate: Optional plate number to highlight specific trajectory
        out_path: Output path for HTML map (defaults to config RESULTS_DIR)
        include_heatmap: Whether to include traffic heatmap layer
    """
    if out_path is None:
        out_path = str(RESULTS_DIR / "city_map.html")
    
    # center map roughly on the camera network
    center = list(CAMERAS.values())[0]
    m = folium.Map(location=[center["lat"], center["long"]], zoom_start=14)

    plot_camera_network(m)

    store = ObservationStore()
    obs = store.all_observations()
    trajs = build_trajectories(obs)

    # Add traffic heatmap if requested and data exists
    if include_heatmap and obs:
        plot_traffic_heatmap(m, obs)

    if search_plate:
        # find the trajectory containing this plate (fuzzy-ish: exact match on
        # any observation's plate_text within a trajectory)
        matches = [t for t in trajs
                   if any(o["plate_text"] == search_plate or 
                          o.get("normalized_plate") == search_plate 
                          for o in t["observations"])]
        for t in matches:
            plot_trajectory(m, t)
        print(f"plotted {len(matches)} trajectory(ies) for plate {search_plate}")
    else:
        # no specific plate -> just show all trajectories with more than 1 hit
        multi_hop = [t for t in trajs if len(t["observations"]) > 1]
        for t in multi_hop:
            plot_trajectory(m, t)
        print(f"plotted {len(multi_hop)} multi-camera trajectory(ies)")

    # Add layer control for toggling different layers
    folium.LayerControl().add_to(m)

    store.close()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    m.save(out_path)
    print(f"map saved to {out_path}")
    return out_path


if __name__ == "__main__":
    plate = sys.argv[1] if len(sys.argv) > 1 else None
    generate_map(search_plate=plate)
