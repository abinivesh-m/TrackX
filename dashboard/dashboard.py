"""
dashboard.py

simple demo UI for TrackX using streamlit. no backend/API needed for this -
streamlit runs the python code directly and renders a web page.

run with:
    streamlit run dashboard.py

(run from the project root, same as everything else)
"""

import os
import sys
from datetime import datetime

# dashboard.py lives in dashboard/, but its imports (database.*, intelligence.*,
# analytics.*, network.*) are package-qualified relative to the PROJECT ROOT,
# not this folder. Streamlit only adds this script's own directory to
# sys.path, so without this line "streamlit run dashboard/dashboard.py"
# would fail with ModuleNotFoundError. This inserts the project root
# (one level up from this file) so the imports resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib.util
import json
import glob

import streamlit as st
import pandas as pd
import folium

from dashboard import theme

from database.observation_store import ObservationStore, database_file_exists
from database.blacklist_store import BlacklistStore
from database.alert_store import AlertStore

# Optional intelligence imports (may fail if torch unavailable)
try:
    from intelligence.trajectory import build_trajectories
    from intelligence.alerts import scan_trajectories_for_alerts
    _intelligence_available = True
except (ImportError, OSError):
    # torch may fail to load on some systems (e.g., Windows DLL issues)
    build_trajectories = None
    scan_trajectories_for_alerts = None
    _intelligence_available = False

from analytics.analytics import (
    vehicles_per_camera, busiest_camera,
    cross_camera_route_frequency, repeated_camera_sightings,
    average_vehicle_speed, origin_destination_patterns, congestion_hotspots
)
from network.camera_network import CAMERAS
from demo.camera_simulator import get_camera_feed, CameraFeedNotFound, STANDARD_CAMERA_IDS
from config import RESULTS_DIR

st.set_page_config(
    page_title="TRACKX - City-Wide Vehicle Intelligence Engine",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🚗"
)
theme.inject_base_css()

from config import DB_PATH_STR, PROJECT_ROOT
DB_PATH = DB_PATH_STR

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_observations_cached():
    """Load all observations from database with caching to avoid repeated full table scans."""
    if not database_file_exists(DB_PATH):
        return []
    try:
        store = ObservationStore(db_path=DB_PATH)
        observations = store.all_observations()
        store.close()
        return observations
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        return []

@st.cache_data(ttl=300)  # Cache for 5 minutes
def build_trajectories_cached(obs_count):
    """Build trajectories with caching. obs_count is used as cache key to invalidate when data changes."""
    observations = load_observations_cached()
    if build_trajectories is not None and observations:
        return build_trajectories(observations)
    return []

@st.cache_data(ttl=300)
def get_vehicles_per_camera_cached(obs_count):
    """Cache vehicle counts by camera."""
    observations = load_observations_cached()
    return vehicles_per_camera(observations) if observations else {}

@st.cache_data(ttl=300)
def get_busiest_camera_cached(obs_count):
    """Cache busiest camera calculation."""
    observations = load_observations_cached()
    return busiest_camera(observations) if observations else None

@st.cache_data(ttl=300)
def get_cross_camera_routes_cached(traj_count):
    """Cache cross-camera route frequency."""
    trajectories = build_trajectories_cached(len(load_observations_cached()))
    return cross_camera_route_frequency(trajectories) if trajectories else {}

@st.cache_data(ttl=300)
def get_congestion_cached(obs_count):
    """Cache congestion hotspots calculation."""
    observations = load_observations_cached()
    return congestion_hotspots(observations) if observations else {}

@st.cache_data(ttl=300)
def get_average_speed_cached(traj_count):
    """Cache average vehicle speed calculation."""
    trajectories = build_trajectories_cached(len(load_observations_cached()))
    return average_vehicle_speed(trajectories) if trajectories else 0

# Load data with caching
if not database_file_exists(DB_PATH):
    st.info(
        "No observation database yet. Run a camera through the AI engine "
        "in the **Monitor** tab below to create one."
    )
    observations, trajectories = [], []
else:
    try:
        observations = load_observations_cached()
        # Use len(observations) as cache key so trajectories rebuild when obs count changes
        trajectories = build_trajectories_cached(len(observations)) if observations else []
    except Exception as e:
        st.error(f"Error loading database: {str(e)}")
        observations, trajectories = [], []

# ---- real system status for the header (no fake state) ----
_db_ready = database_file_exists(DB_PATH)
_processing_now = st.session_state.get("_processing_active", False)
if _processing_now:
    _proc_label = f"PROCESSING {st.session_state.get('_processing_camera', '')}".strip()
elif st.session_state.get("last_run"):
    _proc_label = "IDLE — LAST RUN COMPLETE"
else:
    _proc_label = "IDLE — WAITING FOR INPUT"

_system_ok = _db_ready and _intelligence_available
theme.top_header(
    system_status=("OPERATIONAL" if _system_ok else "LIMITED MODE", _system_ok),
    camera_count=len(CAMERAS),
    processing_status=_proc_label,
)

def create_folium_map(search_plate=None):
    """Create an interactive Folium map for the dashboard with optimized performance."""
    # Center map roughly on the camera network. Use OpenStreetMap tiles
    # which are free and don't require API keys
    if CAMERAS:
        # Calculate center of all camera locations
        avg_lat = sum(cam["lat"] for cam in CAMERAS.values()) / len(CAMERAS)
        avg_long = sum(cam["long"] for cam in CAMERAS.values()) / len(CAMERAS)
        # Use slightly lower zoom for city-wide view when no specific plate is searched
        zoom_level = 13 if not search_plate else 14
        m = folium.Map(
            location=[avg_lat, avg_long],
            zoom_start=zoom_level,
            tiles="OpenStreetMap",
            control_scale=True,
            max_bounds=True,
            min_zoom=12,
            max_zoom=16,
            prefer_canvas=True  # Use canvas renderer for better performance with many markers
        )
    else:
        m = folium.Map(
            location=[11.0168, 76.9558],  # Coimbatore center
            zoom_start=14,
            tiles="OpenStreetMap",
            max_bounds=True,
            prefer_canvas=True
        )  # Default to Coimbatore
    
    # Restrained camera markers — small filled dots in the accent color
    # rather than the default multi-color Folium pin/icon set, so the map
    # reads as one coherent "command center" surface instead of a generic
    # mapping-demo.
    for cam_id, info in CAMERAS.items():
        folium.CircleMarker(
            [info["lat"], info["long"]],
            radius=7,
            popup=f"{cam_id} - {info['name']}",
            color=theme.ACCENT,
            weight=2,
            fill=True,
            fill_color=theme.ACCENT,
            fill_opacity=0.9,
        ).add_to(m)

    # Add traffic heatmap if observations exist — optimized for performance
    # Only show heatmap on city-wide view and when not searching for specific plate
    if observations and not search_plate:  # Only show heatmap on city-wide view
        camera_counts = get_vehicles_per_camera_cached(len(observations))
        if camera_counts:
            from folium.plugins import HeatMap
            heat_data = []
            max_count = max(camera_counts.values()) if camera_counts else 1

            for cam_id, info in CAMERAS.items():
                count = camera_counts.get(cam_id, 0)
                if count > 0:
                    intensity = count / max_count
                    # Further reduced number of points for better performance
                    num_points = min(int(count * 0.2) + 1, 3)  # Cap at 3 points per camera
                    for _ in range(num_points):
                        heat_data.append([info["lat"], info["long"], intensity])

            if heat_data:
                HeatMap(
                    heat_data,
                    min_opacity=0.3,
                    max_opacity=0.7,
                    radius=20,  # Further reduced radius for performance
                    blur=12,   # Further reduced blur for performance
                    gradient={0.3: theme.ACCENT, 1.0: theme.BAD},
                    show=False  # Hidden by default to improve load time
                ).add_to(m)

    # Add vehicle trajectory lines showing real camera-to-camera connections
    # Only show top 5 trajectories on city-wide view to prevent lag (reduced from 10)
    if trajectories and not search_plate:
        top_trajectories = sorted(trajectories, key=lambda t: len(t["observations"]), reverse=True)[:5]
        for traj in top_trajectories:
            if len(traj["observations"]) >= 2:  # Only show multi-camera trajectories
                coords = [(o["lat"], o["long"]) for o in traj["observations"]]
                plate_text = traj.get("plate_text", "Unknown")

                # Draw trajectory line with arrows showing direction
                folium.PolyLine(
                    coords,
                    color=theme.ACCENT,
                    weight=1,  # Further reduced weight for performance
                    opacity=0.4,  # Further reduced opacity for performance
                    popup=f"Vehicle: {plate_text}<br>Route: {' → '.join([o['camera_id'] for o in traj['observations']])}"
                ).add_to(m)
    
    # Plot trajectory if search plate is provided — the searched vehicle's
    # path is the one thing that should visually dominate the map.
    if search_plate and trajectories:
        matches = [t for t in trajectories
                   if any(o["plate_text"] == search_plate.upper() or
                          o.get("normalized_plate") == search_plate.upper()
                          for o in t["observations"])]

        for traj in matches:
            coords = [(o["lat"], o["long"]) for o in traj["observations"]]
            if coords:
                # Main trajectory line
                folium.PolyLine(
                    coords,
                    color=theme.BAD,
                    weight=3,  # Further reduced for performance
                    opacity=0.85,
                    popup=f"Vehicle: {traj.get('plate_text', 'Unknown')}<br>Complete Route"
                ).add_to(m)

                # Origin point (first camera)
                origin = traj["observations"][0]
                folium.CircleMarker(
                    [origin["lat"], origin["long"]],
                    radius=6,  # Further reduced for performance
                    popup=f"🚩 ORIGIN: {origin['camera_id']}<br>Time: {origin['timestamp']}<br>Plate: {origin.get('plate_text', 'Unknown')}",
                    color=theme.ACCENT,
                    weight=2,
                    fill=True,
                    fill_color=theme.ACCENT,
                    fill_opacity=1.0,
                ).add_to(m)

                # Destination point (last camera)
                dest = traj["observations"][-1]
                folium.CircleMarker(
                    [dest["lat"], dest["long"]],
                    radius=6,  # Further reduced for performance
                    popup=f"🏁 DESTINATION: {dest['camera_id']}<br>Time: {dest['timestamp']}<br>Plate: {dest.get('plate_text', 'Unknown')}",
                    color=theme.BAD,
                    weight=2,
                    fill=True,
                    fill_color=theme.BAD,
                    fill_opacity=1.0,
                ).add_to(m)

                # Intermediate waypoints - heavily simplified for performance
                # Only show every 3rd waypoint to reduce marker count
                for i, obs in enumerate(traj["observations"]):
                    if i == 0 or i == len(traj["observations"]) - 1:
                        continue  # Skip origin and destination (already shown)
                    if i % 3 != 0:  # Only show every 3rd waypoint
                        continue
                        
                    # Add camera marker
                    folium.CircleMarker(
                        [obs["lat"], obs["long"]],
                        radius=4,  # Further reduced for performance
                        popup=f"{obs['camera_id']} @ {obs['timestamp']}<br>Plate: {obs['plate_text']}",
                        color=theme.BAD,
                        weight=1,
                        fill=True,
                        fill_color=theme.BAD,
                        fill_opacity=0.9,
                    ).add_to(m)

                    # Add simple directional indicators (even fewer arrows for performance)
                    if i < len(traj["observations"]) - 1 and i % 3 == 0:  # Every 3rd point
                        next_obs = traj["observations"][i + 1]
                        mid_lat = (obs["lat"] + next_obs["lat"]) / 2
                        mid_long = (obs["long"] + next_obs["long"]) / 2

                        # Simple arrow marker
                        folium.CircleMarker(
                            [mid_lat, mid_long],
                            radius=2,  # Further reduced for performance
                            popup=f"{obs['camera_id']} → {next_obs['camera_id']}",
                            color=theme.ACCENT,
                            weight=1,
                            fill=True,
                            fill_color=theme.ACCENT,
                            fill_opacity=0.8,
                        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    return m

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["01 · SEARCH", "02 · CITY INTELLIGENCE", "03 · ALERTS", "04 · MONITOR", "05 · SYSTEM"]
)

with tab1:
    theme.section_header(
        "Vehicle Investigation",
        f"Search a license plate across {len(CAMERAS)} camera(s).",
    )

    # Hero search bar — this is the primary action on the page, so it comes
    # first and full-width, not buried inside an options expander.
    col_plate, col_btn = st.columns([5, 1])
    with col_plate:
        search_plate = st.text_input(
            "Plate number",
            placeholder="e.g. TN10AB1234",
            label_visibility="collapsed",
        )
    with col_btn:
        st.button("SEARCH →", type="primary", use_container_width=True)

    with st.expander("Filters — camera, date range"):
        col_search2, col_search3 = st.columns(2)
        with col_search2:
            search_camera = st.selectbox("Camera (optional)", ["All"] + list(STANDARD_CAMERA_IDS))
        with col_search3:
            date_range = st.date_input("Date range", value=None)

    
    if search_plate:
        search_plate_upper = search_plate.upper()
        
        # Filter by camera if specified
        filtered_trajectories = trajectories
        if search_camera != "All":
            filtered_trajectories = [t for t in trajectories 
                                   if any(o["camera_id"] == search_camera for o in t["observations"])]
        
        matches = [t for t in filtered_trajectories
                   if any(o["plate_text"] == search_plate_upper or 
                          o.get("normalized_plate") == search_plate_upper for o in t["observations"])]

        if not matches:
            theme.empty_state(
                "NO VEHICLE FOUND",
                f"No trajectory in the database matches plate \"{search_plate_upper}\". "
                f"Try a different plate, or run AI processing on a camera first.",
            )
        else:
            # ---- Vehicle Intelligence Summary (real, derived from `matches`) ----
            all_obs = [o for t in matches for o in t["observations"]]
            all_obs_sorted = sorted(all_obs, key=lambda o: o["timestamp"])
            cams_visited = sorted({o["camera_id"] for o in all_obs})

            try:
                _bl_store = BlacklistStore()
                _bl_entry = _bl_store.get_active_entry(search_plate_upper)
                _bl_store.close()
            except Exception:
                _bl_entry = None
            risk_status = f"BLACKLISTED ({_bl_entry['severity']})" if _bl_entry else "NO WATCHLIST MATCH"

            theme.kpi_row([
                {"label": "First Seen", "value": all_obs_sorted[0]["timestamp"].split("T")[1][:8],
                 "hint": all_obs_sorted[0]["camera_id"]},
                {"label": "Last Seen", "value": all_obs_sorted[-1]["timestamp"].split("T")[1][:8],
                 "hint": all_obs_sorted[-1]["camera_id"]},
                {"label": "Cameras Visited", "value": len(cams_visited)},
                {"label": "Total Observations", "value": len(all_obs)},
                {"label": "Risk Status", "value": risk_status},
            ])

            st.write("")

            # Show Origin-Destination Summary with better layout
            origin = all_obs_sorted[0]
            destination = all_obs_sorted[-1]
            total_time = (datetime.fromisoformat(destination['timestamp']) - datetime.fromisoformat(origin['timestamp'])).total_seconds()

            st.markdown("**Vehicle Route Summary**")
            col_route = st.columns(4)
            with col_route[0]:
                st.metric("🚩 Origin", f"{origin['camera_id']}", delta=f"{origin['timestamp'].split('T')[1][:5]}", help=f"First seen at {origin['timestamp']}")
            with col_route[1]:
                st.metric("🏁 Destination", f"{destination['camera_id']}", delta=f"{destination['timestamp'].split('T')[1][:5]}", help=f"Last seen at {destination['timestamp']}")
            with col_route[2]:
                st.metric("⏱️ Total Time", f"{total_time/3600:.1f} hours", help="Time between first and last sighting")
            with col_route[3]:
                st.metric("📍 Cameras", f"{len(cams_visited)}", help="Number of cameras visited")

            st.write("")
            col_evidence, col_map = st.columns([1, 2], gap="large", vertical_alignment="top")

            with col_evidence:
                st.markdown("**Latest Evidence**")
                latest = all_obs_sorted[-1]
                st.markdown(
                    theme.plate_evidence_card_html(
                        plate_text=latest.get("plate_text"),
                        ocr_confidence=latest.get("ocr_confidence"),
                        camera_id=latest.get("camera_id"),
                        timestamp=latest.get("timestamp"),
                    ),
                    unsafe_allow_html=True,
                )
                _crop_path = latest.get("plate_crop_path")
                if _crop_path and os.path.isfile(_crop_path):
                    try:
                        st.image(_crop_path, caption="Plate crop (evidence)")
                    except Exception as e:
                        st.warning(f"Could not load plate image: {str(e)}")
                        st.info("Image file may be corrupted or missing. Add actual car images to fix this.")

            with col_map:
                st.markdown("**Vehicle Trajectory Map**")
                map_obj = create_folium_map(search_plate_upper)
                # Use a container with better responsive behavior
                map_container = st.container()
                with map_container:
                    import streamlit.components.v1 as components
                    components.html(map_obj._repr_html_(), height=450)

            st.write("")
            for traj in matches:
                st.markdown(f"**Global Vehicle #{traj['global_id']} — Timeline**")

                obs_list = traj["observations"]
                timeline_parts = []
                for i, obs in enumerate(obs_list):
                    if i > 0:
                        timeline_parts.append(
                            f'<span style="color:{theme.TEXT_MUTED}; margin:0 10px;">→</span>'
                        )
                    timeline_parts.append(
                        f'<div style="display:inline-block; text-align:center; padding:8px 14px;'
                        f'background:{theme.SURFACE_2}; border:1px solid {theme.BORDER}; border-radius:8px;">'
                        f'<div style="font-size:0.8rem; font-weight:700; color:{theme.TEXT};">{obs["camera_id"]}</div>'
                        f'<div style="font-size:0.68rem; color:{theme.TEXT_MUTED};">{obs["timestamp"].split("T")[1][:8]}</div>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div style="white-space:nowrap; overflow-x:auto; padding:6px 0;">{"".join(timeline_parts)}</div>',
                    unsafe_allow_html=True,
                )

                if traj["match_breakdowns"]:
                    with st.expander("Why we believe these are the same vehicle"):
                        for i, breakdown in enumerate(traj["match_breakdowns"]):
                            cam_a = obs_list[i]["camera_id"]
                            cam_b = obs_list[i + 1]["camera_id"]
                            st.write(f"**{cam_a} → {cam_b}** — confidence: "
                                     f"{breakdown['total']} ({breakdown['confidence_label']})")

                            ev_cols = st.columns(4)
                            ev_cols[0].progress(breakdown["plate"], text=f"Plate {breakdown['plate']:.0%}")
                            ev_cols[1].progress(breakdown["appearance"], text=f"Appearance {breakdown['appearance']:.0%}")
                            ev_cols[2].progress(breakdown["temporal"], text=f"Temporal {breakdown['temporal']:.0%}")
                            ev_cols[3].progress(breakdown["spatial"], text=f"Spatial {breakdown['spatial']:.0%}")
    else:
        theme.empty_state(
            "NO VEHICLE SELECTED",
            "Search for a license plate above to view its city-wide movement history.",
        )

with tab2:
    theme.section_header(
        "City Traffic Intelligence",
        "Live traffic patterns and movement intelligence across the camera network.",
    )

    # ---- Top KPI row (real data, trimmed to what a viewer needs at a glance) ----
    _active_cams = len(CAMERAS)
    _veh_counts = get_vehicles_per_camera_cached(len(observations))
    _total_vehicles = sum(_veh_counts.values()) if _veh_counts else 0
    _speed_preview = get_average_speed_cached(len(trajectories))
    _avg_speed_str = (f"{_speed_preview['overall_avg_speed']:.0f} km/h"
                       if _speed_preview and _speed_preview.get("status") == "calculated"
                       else "N/A")

    theme.kpi_row([
        {"label": "Vehicles Detected", "value": _total_vehicles},
        {"label": "Active Cameras", "value": _active_cams},
        {"label": "Avg Speed", "value": _avg_speed_str},
        {"label": "Observations", "value": len(observations)},
    ])
    st.write("")

    # ---- 3 headline insights (real data, same underlying calls as before) ----
    busy = get_busiest_camera_cached(len(observations))
    routes = get_cross_camera_routes_cached(len(trajectories))
    top_route = next(iter(routes.items()), None)
    congestion_result = get_congestion_cached(len(observations))
    congested = (congestion_result.get("congested_cameras")
                 if congestion_result and congestion_result.get("status") == "calculated" else None)

    _ic1, _ic2, _ic3 = st.columns(3)
    with _ic1:
        st.markdown("**Busiest Camera**")
        st.markdown(f"### {busy or 'N/A'}")
        st.caption("Highest observed traffic")
    with _ic2:
        st.markdown("**Top Route**")
        if top_route:
            st.markdown(f"### {top_route[0]}")
            st.caption(f"{top_route[1]} vehicle(s)")
        else:
            st.markdown("### N/A")
            st.caption("No cross-camera trajectories yet")
    with _ic3:
        st.markdown("**Congestion**")
        if congested:
            st.markdown(f"### {congested[0][0]}")
            st.caption(f"HIGH — {len(congested)} camera(s) over threshold")
        elif congestion_result and congestion_result.get("status") == "calculated":
            st.markdown("### Clear")
            st.caption("No congestion detected")
        else:
            st.markdown("### N/A")
            st.caption("Insufficient data")

    st.write("")

    # ---- City Traffic Map ----
    st.markdown("**City Traffic Map**")
    st.caption("Real-time camera network and traffic heatmap with vehicle routes")

    # Show route statistics before the map
    if routes:
        st.markdown("**Top Vehicle Routes (Origin → Destination)**")
        route_cols = st.columns(3)
        for i, (route, count) in enumerate(list(routes.items())[:6]):
            with route_cols[i % 3]:
                st.info(f"**{route}**\n{count} vehicle(s)")

    city_map = create_folium_map()  # Create map without specific plate search
    # Use container for better map rendering
    map_container = st.container()
    with map_container:
        import streamlit.components.v1 as components
        components.html(city_map._repr_html_(), height=500)

    st.write("")

    with st.expander("View detailed analytics"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Vehicles per camera**")
            counts = get_vehicles_per_camera_cached(len(observations))
            if counts:
                df = pd.DataFrame(counts.items(), columns=["Camera", "Vehicle Count"])
                st.bar_chart(df.set_index("Camera"))
            else:
                st.info("No observations yet.")

        with col2:
            st.markdown("**Cross-Camera Routes**")
            if routes:
                for route, count in list(routes.items())[:5]:
                    st.write(f"{route} — {count} vehicle(s)")
            else:
                st.info("No cross-camera trajectories yet.")

            st.markdown("**Repeated Camera Sightings** (same camera, not a route)")
            repeats = repeated_camera_sightings(trajectories)
            if repeats:
                for cam, info in repeats.items():
                    st.write(f"{cam} — {info['repeat_transitions']} repeat(s), "
                             f"Global Vehicle(s): {info['global_vehicle_ids']}")
            else:
                st.info("No repeated-camera activity yet.")

        st.divider()

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**Average Vehicle Speed — Detail**")
            speed_result = average_vehicle_speed(trajectories)
            if speed_result and speed_result.get("status") == "calculated":
                st.caption(f"Based on {speed_result['num_valid_speeds']} valid speed calculation(s) "
                           f"across camera-to-camera transitions.")
                if speed_result['speeds_by_camera_pair']:
                    st.markdown("**Speed by camera pair:**")
                    for pair, avg_speed in list(speed_result['speeds_by_camera_pair'].items())[:3]:
                        st.write(f"{pair}: {avg_speed:.1f} km/h")
            else:
                st.info("Insufficient data for speed calculation")

        with col4:
            st.markdown("**Origin-Destination Patterns**")
            od_result = origin_destination_patterns(trajectories)
            if od_result and od_result.get("top_od_pairs"):
                st.markdown("**Top OD pairs:**")
                for od_pair, count in od_result['top_od_pairs'][:3]:
                    st.write(f"{od_pair}: {count} vehicle(s)")
            else:
                st.info("Insufficient data for OD analysis")

        st.markdown("**Congestion Hotspots**")
        if congested:
            st.warning(f"Congested cameras (>= {congestion_result['threshold']:.1f} vehicles):")
            for cam, count in congested:
                st.write(f"{cam}: {count} vehicles")
        elif congestion_result and congestion_result.get("status") == "calculated":
            st.success("No congestion detected")
        else:
            st.info("Insufficient data for congestion analysis")

        st.divider()

        st.markdown("**Export**")
        if st.button("Export to CSV"):
            try:
                export_data = []
                for obs in observations:
                    export_data.append({
                        "Plate": obs.get("plate_text", "N/A"),
                        "Camera": obs.get("camera_id", "N/A"),
                        "Timestamp": obs.get("timestamp", "N/A"),
                        "Confidence": obs.get("confidence", 0),
                        "Vehicle Type": obs.get("vehicle_type", "N/A"),
                        "Latitude": obs.get("lat", 0),
                        "Longitude": obs.get("long", 0)
                    })

                if export_data:
                    export_df = pd.DataFrame(export_data)
                    csv = export_df.to_csv(index=False)
                    st.download_button(
                        label="Download Analytics CSV",
                        data=csv,
                        file_name=f"trackx_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning("No data to export")
            except Exception as e:
                st.error(f"Export failed: {e}")

with tab3:
    theme.section_header(
        "Alert Operations Center",
        "Blacklist matches, anomalous routes, and repeated sightings detected from live trajectories.",
    )

    # Alert Management Sub-tabs
    alert_tab1, alert_tab2, alert_tab3 = st.tabs(["Active Alerts", "Manage Watchlist", "Alert History"])

    with alert_tab1:
        if scan_trajectories_for_alerts is not None:
            alerts = scan_trajectories_for_alerts(trajectories)
        else:
            alerts = []
            st.warning("Alert system unavailable (torch not loaded)")

        _sev_rank = {"HIGH": 0, "CRITICAL": 0, "MEDIUM": 1, "LOW": 2}
        alerts_sorted = sorted(alerts, key=lambda a: _sev_rank.get((a.get("severity") or "").upper(), 3))

        st.markdown(theme.alerts_hero_header(len(alerts)), unsafe_allow_html=True)

        if not alerts:
            theme.empty_state("NO ACTIVE ALERTS", "Nothing in the current trajectory data has triggered a rule.")
        else:
            def _alert_card_fields(alert):
                """Map an alert dict to (title, plate, detail_line, meta_line, severity)."""
                if alert["type"] == "BLACKLIST_MATCH":
                    return (
                        "BLACKLIST MATCH", alert['plate_text'],
                        f"Matched against {alert['matched_against']} — similarity {alert['similarity']:.2f}",
                        alert.get('camera_hits'), alert.get('severity', 'HIGH'),
                    )
                elif alert["type"] == "REPEATED_CAMERA_SIGHTING":
                    return (
                        f"REPEATED SIGHTING · {alert['camera_id']}", f"Global Vehicle #{alert['global_id']}",
                        f"{alert['count']} repeat visits", None, alert.get('severity', 'MEDIUM'),
                    )
                elif alert["type"] == "ROUTE_ANOMALY":
                    return (
                        f"ROUTE ANOMALY · {alert.get('anomaly_type', 'UNKNOWN')} "
                        f"(score {alert.get('anomaly_score', 0):.1f})",
                        f"Global Vehicle #{alert['global_id']}",
                        alert.get("reason", "Unknown reason"), None, alert.get("severity", "MEDIUM"),
                    )
                return (f"UNKNOWN ALERT TYPE · {alert.get('type')}", None, None, None, "MEDIUM")

            # The single most severe alert gets the big hero treatment —
            # this is the "something needs attention right now" moment.
            top_alert = alerts_sorted[0]
            title, plate, detail, meta, severity = _alert_card_fields(top_alert)
            st.markdown(
                theme.hero_alert_card_html(title, plate, detail, meta, severity),
                unsafe_allow_html=True,
            )
            if top_alert.get("details"):
                with st.expander("Details"):
                    st.json(top_alert["details"])

            # Everything else renders as a compact list underneath so it
            # doesn't compete visually with the hero alert above.
            for alert in alerts_sorted[1:]:
                title, plate, detail, meta, severity = _alert_card_fields(alert)
                st.markdown(
                    theme.alert_banner_html("", title, plate, meta, detail, severity, compact=True),
                    unsafe_allow_html=True,
                )
                if alert.get("details"):
                    with st.expander("Details"):
                        st.json(alert["details"])

    with alert_tab2:
        st.markdown("### Blacklist Management")
        st.caption("Add or remove vehicles from the watchlist")
        
        col_add, col_view = st.columns([1, 2])
        
        with col_add:
            st.markdown("**Add to Blacklist**")
            new_plate = st.text_input("Plate Number", placeholder="e.g. TN10AB1234")
            new_description = st.text_input("Description", placeholder="e.g. Stolen vehicle")
            new_severity = st.selectbox("Severity", ["LOW", "MEDIUM", "HIGH"])
            
            if st.button("Add to Blacklist", type="primary"):
                if new_plate:
                    try:
                        blacklist_store = BlacklistStore()
                        plate_id = blacklist_store.add_plate(
                            new_plate,
                            description=new_description,
                            severity=new_severity
                        )
                        blacklist_store.close()
                        st.success(f"Added {new_plate} to blacklist (ID: {plate_id})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add plate: {e}")
                else:
                    st.warning("Please enter a plate number")
        
        with col_view:
            st.markdown("**Current Blacklist**")
            try:
                blacklist_store = BlacklistStore()
                active_blacklist = blacklist_store.all_active()
                blacklist_store.close()
                
                if active_blacklist:
                    for entry in active_blacklist:
                        with st.container(border=True):
                            c1, c2, c3 = st.columns([2, 3, 1])
                            c1.markdown(f"**{entry['plate']}**")
                            c2.caption(entry.get('description', 'No description'))
                            c3.markdown(theme.severity_badge(entry['severity']), unsafe_allow_html=True)
                            
                            if st.button(f"Remove", key=f"remove_{entry['id']}"):
                                try:
                                    blacklist_store = BlacklistStore()
                                    blacklist_store.deactivate_plate(entry['plate'])
                                    blacklist_store.close()
                                    st.success(f"Removed {entry['plate']} from blacklist")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to remove: {e}")
                else:
                    st.info("No plates in blacklist")
                    
            except Exception as e:
                st.error(f"Failed to load blacklist: {e}")
    
    with alert_tab3:
        st.markdown("### Alert History")
        st.caption("View and manage historical alerts from the database")
        
        try:
            alert_store = AlertStore()
            historical_alerts = alert_store.list_alerts()
            alert_store.close()
            
            if historical_alerts:
                # Enhanced filter options
                col_filter1, col_filter2, col_filter3 = st.columns(3)
                with col_filter1:
                    status_filter = st.selectbox("Filter by Status", ["All", "OPEN", "RESOLVED"])
                with col_filter2:
                    severity_filter = st.selectbox("Filter by Severity", ["All", "HIGH", "MEDIUM", "LOW"])
                with col_filter3:
                    if st.button("Refresh"):
                        st.rerun()
                
                # Apply filters
                if status_filter != "All":
                    historical_alerts = [a for a in historical_alerts if a['status'] == status_filter]
                if severity_filter != "All":
                    historical_alerts = [a for a in historical_alerts if a['severity'] == severity_filter]
                
                st.markdown(f"**{len(historical_alerts)} alert(s) found**")
                
                # Export alerts
                if st.button("Export Alerts to CSV"):
                    try:
                        export_df = pd.DataFrame(historical_alerts)
                        csv = export_df.to_csv(index=False)
                        st.download_button(
                            label="Download Alerts CSV",
                            data=csv,
                            file_name=f"trackx_alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error(f"Export failed: {e}")
                
                for alert in historical_alerts:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])

                        c1.markdown(
                            f"{theme.severity_badge(alert['severity'])} &nbsp; **{alert['alert_type']}** — {alert['plate']}",
                            unsafe_allow_html=True,
                        )
                        c2.caption(alert['timestamp'])
                        
                        if alert['status'] == 'OPEN':
                            if c3.button("Resolve", key=f"resolve_{alert['alert_id']}"):
                                try:
                                    alert_store = AlertStore()
                                    alert_store.resolve_alert(alert['alert_id'])
                                    alert_store.close()
                                    st.success(f"Alert {alert['alert_id']} resolved")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to resolve: {e}")
                        else:
                            c3.markdown("`RESOLVED`")
                        
                        if alert.get('description'):
                            st.caption(alert['description'])
                        
                        if alert.get('camera_id'):
                            st.caption(f"Camera: {alert['camera_id']}")
            else:
                st.info("No historical alerts found. Run the demo to generate alerts.")
                
        except Exception as e:
            st.error(f"Failed to load alert history: {e}")

# --------------------------------------------------------------------------
# TAB 4: Monitor — AI Processing Engine
#
# This is the real processing trigger: picking a camera + clicking "Start AI
# Processing" calls demo.visual_pipeline.run_camera() directly - actual
# YOLO vehicle detection, actual plate detector (if trained weights are
# present), actual PaddleOCR, actual appearance embedding from the vehicle
# crop, and a real write into observations.db via the bridge added in
# database/observation_store.py. Nothing here is synthetic or hand-typed;
# if the heavy vision libraries (ultralytics/paddleocr/torch) aren't
# installed in this environment, that surfaces as an explicit error message,
# never a silently faked result.
# --------------------------------------------------------------------------

with tab4:
    theme.section_header(
        "Live Monitoring — AI Processing Engine",
        "Camera folder → real YOLO vehicle detection → plate detector (if a trained model is "
        "available) → PaddleOCR → structured observation → observations.db → trajectory / alerts / analytics.",
    )

    # ---- Camera network status strip (real folder/media state per camera) ----
    _cam_status_cols = st.columns(len(STANDARD_CAMERA_IDS))
    for _cc, _cam in zip(_cam_status_cols, STANDARD_CAMERA_IDS):
        try:
            _f = get_camera_feed(_cam)
            _online = _f.has_media
            _detail = f"{len(_f.images)} img · {len(_f.videos)} vid"
        except CameraFeedNotFound:
            _online = False
            _detail = "no folder"
        with _cc:
            st.markdown(
                f"""
                <div style="background:{theme.SURFACE}; border:1px solid {theme.BORDER}; border-radius:8px;
                            padding:8px 10px; text-align:center;">
                    <div style="font-size:0.78rem; font-weight:700; color:{theme.TEXT};">{_cam}</div>
                    {theme.status_badge("ONLINE" if _online else "OFFLINE")}
                    <div style="font-size:0.66rem; color:{theme.TEXT_MUTED}; margin-top:4px;">{_detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.write("")

    col_select, col_status = st.columns([1, 1])

    with col_select:
        camera_id = st.selectbox("Camera", STANDARD_CAMERA_IDS)

        try:
            feed = get_camera_feed(camera_id)
            if feed.has_media:
                st.success(
                    f"{len(feed.images)} image(s), {len(feed.videos)} video(s) available for {camera_id}."
                )
            else:
                st.warning(f"{camera_id}: folder exists but has no images/videos yet — no input available.")
        except CameraFeedNotFound:
            st.warning(f"{camera_id}: no input available (camera folder not set up).")
            feed = None

        frame_sample = st.number_input(
            "Process every Nth video frame", min_value=1, value=10, step=1,
            help="Lower = more thorough but slower. Only affects video input. Higher = faster but less coverage.",
        )
        max_frames = st.number_input(
            "Max frames to process (0 = whole video)", min_value=0, value=10, step=5,
            help="Limit total frames for faster testing. 0 = process entire video (slow).",
        )

        can_run = feed is not None and feed.has_media
        if st.button("START AI PROCESSING", type="primary", disabled=not can_run):
            st.session_state["_processing_active"] = True
            st.session_state["_processing_camera"] = camera_id
            with st.spinner(f"Running real detection pipeline on {camera_id}..."):
                try:
                    import time as _time
                    from demo.visual_pipeline import run_camera
                    _t0 = _time.time()
                    obs, out_json, weights_used, n_written = run_camera(
                        camera_id,
                        frame_sample=int(frame_sample),
                        max_frames=(int(max_frames) or None),
                        write_to_db=True,
                        db_path=DB_PATH,
                    )
                    _elapsed = _time.time() - _t0
                    # Real throughput: distinct (source_file, frame_index) pairs actually
                    # processed by the pipeline for this run, divided by real wall-clock time.
                    _frames_seen = len({(o.get("source_file"), o.get("frame_index")) for o in obs}) or 1
                    _fps = _frames_seen / _elapsed if _elapsed > 0 else 0.0
                    st.session_state["last_run"] = {
                        "camera_id": camera_id, "observations": obs,
                        "out_json": out_json, "weights_used": weights_used,
                        "n_written": n_written, "elapsed_sec": _elapsed,
                        "frames_processed": _frames_seen, "fps": _fps,
                    }
                    st.success(
                        f"Processed {camera_id}: {len(obs)} vehicle observation(s), "
                        f"{n_written} written to the database."
                    )
                    st.info("Switch to Search / City Intelligence / Alerts above and "
                            "reload the page to see the updated data.")
                except ImportError as e:
                    st.error(
                        f"AI processing is unavailable in this environment: {e}. "
                        f"The real vision stack (ultralytics/paddleocr/torch) is not "
                        f"installed here — this is a genuine environment gap, not "
                        f"simulated or worked around."
                    )
                except Exception as e:
                    st.error(f"Processing failed: {e}")
                finally:
                    st.session_state["_processing_active"] = False

    with col_status:
        st.markdown("**Latest AI Result**")
        last_run = st.session_state.get("last_run")

        # Show ALL vehicle observations from the CURRENT processing run only -
        # never a database re-query. run_camera() already returns one flat
        # record per detected vehicle, each with its OWN annotated_output and
        # plate_crop_path (see demo/visual_pipeline.py: process_image/
        # process_video annotate per-vehicle, not per-frame), so looping over
        # last_run["observations"] directly is both correct AND simpler than
        # re-deriving "which observations belong to this run" from the DB.
        #
        # Deliberately scoped to last_run["camera_id"] == camera_id: if the
        # user switches the camera dropdown after running, we must NOT show
        # a previous run's results under a different camera's selection -
        # that would silently mix data from two different runs/cameras.
        if last_run and last_run.get("camera_id") == camera_id and last_run.get("observations"):
            run_obs = last_run["observations"]

            _kpis = [
                {"label": "Vehicles Found", "value": len(run_obs)},
                {"label": "Frames Processed", "value": last_run.get("frames_processed", "N/A")},
            ]
            if last_run.get("fps") is not None:
                _kpis.append({"label": "Processing Speed", "value": f"{last_run['fps']:.1f} FPS",
                              "hint": f"{last_run.get('elapsed_sec', 0):.2f}s elapsed"})
            _kpis.append({"label": "Written to DB", "value": last_run.get("n_written", "N/A")})
            theme.kpi_row(_kpis)
            st.write("")

            for i, obs in enumerate(run_obs, start=1):
                with st.container(border=True):
                    plate_status = obs.get("plate_status")
                    plate_detected = plate_status in ("detected", "detected_no_ocr")
                    plate_read = plate_status == "detected"

                    theme.pipeline_stage_tracker([
                        ("Vehicle detected", True),
                        ("Plate detected", plate_detected),
                        ("Plate recognized (OCR)", plate_read),
                        ("Written to database", bool(last_run.get("n_written"))),
                    ])

                    # This vehicle's OWN annotated frame - not shared with any
                    # other vehicle in this run, even if they came from the
                    # same source image/frame.
                    annotated_path = obs.get("annotated_output")
                    if annotated_path and not os.path.isabs(annotated_path):
                        annotated_path = str(PROJECT_ROOT / annotated_path)
                    if annotated_path and os.path.isfile(annotated_path):
                        st.image(annotated_path, use_container_width=True,
                                  caption=f"Vehicle {i} — {obs.get('camera_id')}")
                    elif annotated_path:
                        st.caption(f"(annotated image not found on disk: {annotated_path})")

                    col_ev, col_crop = st.columns([2, 1])
                    with col_ev:
                        if plate_read:
                            extra = f"Raw OCR: {obs.get('raw_plate_text')}"
                        elif plate_status == "detected_no_ocr":
                            extra = "Plate detected — OCR unavailable"
                        elif plate_status == "ocr_failed":
                            extra = "Plate detected — OCR failed, no text produced"
                        elif plate_status == "unavailable":
                            extra = "Plate detector not configured"
                        else:
                            extra = "Plate not detected"
                        st.markdown(
                            theme.plate_evidence_card_html(
                                plate_text=obs.get("normalized_plate_text") if plate_read else None,
                                ocr_confidence=obs.get("ocr_confidence") if plate_read else None,
                                camera_id=obs.get("camera_id"),
                                timestamp=obs.get("timestamp"),
                                extra_line=extra,
                            ),
                            unsafe_allow_html=True,
                        )
                        st.caption(f"Vehicle class: {obs.get('vehicle_class', '?')} "
                                   f"(confidence {obs.get('vehicle_confidence')}) · "
                                   f"Track ID: {obs.get('track_id', 'unavailable')} · "
                                   f"Frame: {obs.get('frame_index')}")

                    with col_crop:
                        plate_crop_path = obs.get("plate_crop_path")
                        if plate_crop_path and os.path.isfile(plate_crop_path):
                            st.image(plate_crop_path, caption="Plate crop")

        elif last_run and last_run.get("camera_id") != camera_id:
            st.caption(f"Last run was for {last_run.get('camera_id')}. "
                       f"Click START AI PROCESSING to run {camera_id} now.")
        elif last_run and not last_run.get("observations"):
            st.caption(f"Last run on {camera_id} found no vehicles.")
        else:
            theme.empty_state(
                "NO VIDEO PROCESSING YET",
                "Select a camera and click START AI PROCESSING to begin ANPR analysis.",
            )

# --------------------------------------------------------------------------
# TAB 5: System Health
# --------------------------------------------------------------------------

with tab5:
    theme.section_header(
        "System Status",
        f"Live status of every TrackX component. Last checked {datetime.now().strftime('%H:%M:%S')}.",
    )

    def _lib_status(module_name):
        return "READY" if importlib.util.find_spec(module_name) is not None else "NOT INSTALLED"

    def _plate_detector_status():
        candidates = [
            "models/plate_detector.pt", "models/best.pt",
            "detection/runs/detect/plate_train/weights/best.pt",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return f"READY ({c})"
        if glob.glob("detection/runs/**/weights/best.pt", recursive=True):
            return "READY"
        return "NOT CONFIGURED — no trained plate-detector weights found"

    def _db_status():
        try:
            s = ObservationStore(db_path=DB_PATH)
            s.close()
            return "CONNECTED"
        except Exception as e:
            return f"ERROR ({e})"

    def _torch_status():
        try:
            import torch
            return "READY"
        except (ImportError, OSError):
            return "NOT AVAILABLE (DLL loading error or not installed)"

    health_rows = [
        ("YOLO (ultralytics)", _lib_status("ultralytics")),
        ("PaddleOCR", _lib_status("paddleocr")),
        ("PyTorch", _torch_status()),
        ("Plate Detector", _plate_detector_status()),
        ("Database", _db_status()),
        ("Camera Input", "READY" if os.path.isdir("data/cameras") else "NOT CONFIGURED"),
        ("Visual Pipeline", "READY" if importlib.util.find_spec("demo.visual_pipeline") else "NOT FOUND"),
        ("Intelligence Engine (trajectory/fusion/alerts)",
         "READY" if importlib.util.find_spec("intelligence.trajectory") else "NOT FOUND"),
    ]

    _health_cols = st.columns(2)
    for _idx, (_component, _status) in enumerate(health_rows):
        with _health_cols[_idx % 2]:
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            background:{theme.SURFACE}; border:1px solid {theme.BORDER}; border-radius:8px;
                            padding:10px 14px; margin-bottom:8px;">
                    <span style="font-size:0.82rem; color:{theme.TEXT};">{_component}</span>
                    {theme.status_badge(_status)}
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")

    # ---- Live processing status (real, from the last AI-processing run this session) ----
    st.markdown("**Processing Status**")
    _lr = st.session_state.get("last_run")
    if _lr:
        _proc_kpis = [
            {"label": "Last Camera Run", "value": _lr.get("camera_id", "N/A")},
            {"label": "Vehicles Found", "value": len(_lr.get("observations", []))},
            {"label": "Written to DB", "value": _lr.get("n_written", "N/A")},
        ]
        if _lr.get("fps") is not None:
            _proc_kpis.append({"label": "Last Run Speed", "value": f"{_lr['fps']:.1f} FPS"})
        theme.kpi_row(_proc_kpis)
    else:
        theme.empty_state("NO RUNS THIS SESSION", "Process a camera from Monitor to see performance here.")

    st.divider()

    # ---- Everything below is admin/diagnostic detail, not needed for a demo
    # audience -- collapsed by default so the primary view stays a clean
    # command center. Nothing here is new logic, only regrouped. ----
    with st.expander("Advanced diagnostics & admin"):
        # Database info
        st.markdown("**Database Information**")
        if database_file_exists(DB_PATH):
            try:
                store = ObservationStore(db_path=DB_PATH)
                observations = store.all_observations()
                store.close()
            
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Observations", len(observations))
                col2.metric("Database Path", DB_PATH[:50] + "..." if len(DB_PATH) > 50 else DB_PATH)
                col3.metric("Database Size", f"{os.path.getsize(DB_PATH) / 1024:.1f} KB")
            
                # Show recent observations
                if observations:
                    st.markdown("**Recent Observations**")
                    recent_obs = sorted(observations, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]
                    for obs in recent_obs:
                        st.caption(f"{obs.get('camera_id')} · {obs.get('plate_text') or 'No plate'} · {obs.get('timestamp')}")
            except Exception as e:
                st.error(f"Database error: {e}")
        else:
            st.warning("No database found. Run the visual pipeline to create one.")
    
        st.divider()
    
        # Backup and Restore functionality
        st.markdown("**Database Backup & Restore**")
        st.caption("Safely backup and restore your database.")
    
        try:
            from database.backup_manager import BackupManager
            backup_manager = BackupManager()
        
            col_backup1, col_backup2, col_backup3 = st.columns(3)
        
            with col_backup1:
                if st.button("Create Backup", type="primary"):
                    try:
                        backup_path = backup_manager.create_backup()
                        st.success(f"Backup created: {backup_path}")
                    except Exception as e:
                        st.error(f"Backup failed: {e}")
        
            with col_backup2:
                backups = backup_manager.list_backups()
                if backups:
                    backup_names = [b["name"] for b in backups]
                    selected_backup = st.selectbox("Select backup to restore", backup_names)
                
                    if st.button("Restore Backup"):
                        try:
                            selected_backup_path = next(b["path"] for b in backups if b["name"] == selected_backup)
                            backup_manager.restore_backup(selected_backup_path)
                            st.success(f"Database restored from {selected_backup}")
                            st.info("Please refresh the page to see changes.")
                        except Exception as e:
                            st.error(f"Restore failed: {e}")
                else:
                    st.info("No backups available")
        
            with col_backup3:
                if st.button("Cleanup Old Backups"):
                    try:
                        deleted = backup_manager.cleanup_old_backups(keep_count=3)
                        st.success(f"Cleaned up {deleted} old backup(s)")
                    except Exception as e:
                        st.error(f"Cleanup failed: {e}")
        
            # Show backup list
            if backups:
                st.markdown("**Available Backups**")
                for backup in backups[:5]:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.markdown(f"**{backup['name']}**")
                        c2.caption(f"{backup['size'] / 1024:.1f} KB")
                        c3.caption(backup['modified'].strftime("%Y-%m-%d %H:%M"))
        except Exception as e:
            st.error(f"Backup system unavailable: {e}")
    
        st.divider()
    
        # System Performance Metrics
        st.markdown("**System Performance Metrics**")
        st.caption("Real-time system performance monitoring.")
    
        try:
            import psutil
            import platform
        
            # System info
            col_perf1, col_perf2, col_perf3 = st.columns(3)
            with col_perf1:
                st.metric("CPU Usage", f"{psutil.cpu_percent()}%")
            with col_perf2:
                mem = psutil.virtual_memory()
                st.metric("Memory Usage", f"{mem.percent}%")
            with col_perf3:
                disk = psutil.disk_usage('/')
                st.metric("Disk Usage", f"{disk.percent}%")
        
            # Detailed system info
            with st.expander("Detailed System Information"):
                st.markdown("**Platform Information**")
                st.json({
                    "System": platform.system(),
                    "Platform": platform.platform(),
                    "Python Version": platform.python_version(),
                    "Processor": platform.processor()
                })
            
                st.markdown("**Resource Usage**")
                st.json({
                    "CPU Count": psutil.cpu_count(),
                    "Total Memory": f"{mem.total / (1024**3):.2f} GB",
                    "Available Memory": f"{mem.available / (1024**3):.2f} GB",
                    "Total Disk Space": f"{disk.total / (1024**3):.2f} GB",
                    "Free Disk Space": f"{disk.free / (1024**3):.2f} GB"
                })
        except ImportError:
            st.info("Install psutil for detailed system metrics: pip install psutil")
        except Exception as e:
            st.error(f"System metrics unavailable: {e}")
    
        st.divider()
    
        # Configuration Management
        st.markdown("**Configuration Management**")
        st.caption("View and manage system configuration.")
    
        try:
            from config import PROJECT_ROOT, RESULTS_DIR, DB_PATH
        
            with st.expander("Current Configuration"):
                st.json({
                    "Project Root": str(PROJECT_ROOT),
                    "Results Directory": str(RESULTS_DIR),
                    "Database Path": str(DB_PATH),
                    "Database Exists": os.path.exists(DB_PATH),
                    "Virtual Environment": str(PROJECT_ROOT / ".venv"),
                    "Python Version": platform.python_version()
                })
        
            # Configuration suggestions
            with st.expander("Configuration Suggestions"):
                st.markdown("""
                **Performance Optimization:**
                - Use CPU-only PyTorch for inference (currently installed)
                - Consider GPU acceleration for production deployment
                - Optimize database indexes for large datasets
            
                **Data Management:**
                - Regular database backups recommended
                - Clean old observation data periodically
                - Archive old alerts for long-term storage
            
                **Security:**
                - Enable database encryption for production
                - Implement user authentication for dashboard
                - Regular security updates for dependencies
                """)
        except Exception as e:
            st.error(f"Configuration system unavailable: {e}")
