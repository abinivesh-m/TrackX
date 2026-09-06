"""City-wide traffic analytics API backed by persisted ANPR observations."""

from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from analytics.analytics import (
    average_vehicle_speed,
    congestion_hotspots,
    hourly_density,
    origin_destination_patterns,
    vehicles_per_camera,
)
from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from database.observation_store import ObservationStore
from intelligence.trajectory import build_trajectories
from network.camera_network import CAMERAS

router = APIRouter()


def _parse_timestamp(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/summary")
def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate density, OD movement, speeds, congestion, and GIS heat points."""
    store = ObservationStore()
    try:
        observations = store.all_observations()
    finally:
        store.close()

    try:
        trajectories = build_trajectories(observations)
        counts = vehicles_per_camera(observations)
        density = hourly_density(observations)
        od = origin_destination_patterns(trajectories)
        speed = average_vehicle_speed(trajectories)
        congestion = congestion_hotspots(observations, trajectories)

        hourly_totals = Counter()
        hourly_data = []
        for camera_id, buckets in density.items():
            for hour, count in buckets.items():
                hourly_data.append({"hour": hour, "camera_id": camera_id, "count": count})
                hourly_totals[hour] += count

        vehicle_counts = [
            {
                "camera_id": camera_id,
                "camera_name": config["name"],
                "location": config["location"],
                "vehicle_count": counts.get(camera_id, 0),
            }
            for camera_id, config in CAMERAS.items()
        ]

        top_routes = []
        for route, vehicle_count in od["top_od_pairs"]:
            origin, destination = route.split(" -> ", 1)
            top_routes.append({
                "route": route,
                "origin": origin,
                "destination": destination,
                "vehicle_count": vehicle_count,
                "unique_vehicles": vehicle_count,
            })

        hotspots = []
        for camera_id, score in congestion["congested_cameras"]:
            config = CAMERAS[camera_id]
            factors = congestion["congestion_factors"][camera_id]
            hotspots.append({
                "camera_id": camera_id,
                "name": config["name"],
                "location": config["location"],
                "latitude": config["lat"],
                "longitude": config["long"],
                "observation_count": counts.get(camera_id, 0),
                "congestion_score": score,
                "average_speed": factors["raw_speed"],
                "level": factors["congestion_level"],
            })

        heatmap_points = [
            {
                "camera_id": camera_id,
                "latitude": config["lat"],
                "longitude": config["long"],
                "intensity": counts.get(camera_id, 0),
                "average_speed": congestion["congestion_factors"].get(camera_id, {}).get("raw_speed"),
            }
            for camera_id, config in CAMERAS.items()
        ]

        unique_plates = {
            observation.get("normalized_plate") or observation.get("plate_text")
            for observation in observations
            if observation.get("normalized_plate") or observation.get("plate_text")
        }
        return {
            "total_vehicles": len(unique_plates),
            "total_observations": len(observations),
            "active_cameras": sum(count > 0 for count in counts.values()),
            "avg_vehicles_per_camera": round(len(observations) / len(CAMERAS), 2) if CAMERAS else 0,
            "average_speed": speed["overall_avg_speed"],
            "hourly_density": {
                "hourly_data": sorted(hourly_data, key=lambda item: item["hour"]),
                "hourly_totals": [
                    {"hour": hour, "count": count} for hour, count in sorted(hourly_totals.items())
                ],
            },
            "top_routes": top_routes,
            "congestion_hotspots": hotspots,
            "vehicle_counts_per_camera": vehicle_counts,
            "heatmap_points": heatmap_points,
            "generated_at": datetime.now().isoformat(),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Unable to compute analytics from stored observations") from exc


@router.get("/speed")
def get_analytics_speed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Average vehicle speeds across camera corridors and overall network."""
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    trajectories = build_trajectories(obs)
    speed_data = average_vehicle_speed(trajectories)
    return speed_data


@router.get("/density")
def get_analytics_density(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hourly traffic density trends across the camera network."""
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    density = hourly_density(obs)
    hourly_totals = Counter()
    for camera_id, buckets in density.items():
        for hour, count in buckets.items():
            hourly_totals[hour] += count

    return {
        "hourly_totals": [{"hour": h, "count": hourly_totals[h]} for h in range(24)],
        "by_camera": density
    }


@router.get("/flow")
def get_analytics_flow(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cross-camera route flow and corridor volume."""
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    trajectories = build_trajectories(obs)
    od = origin_destination_patterns(trajectories)
    return od


@router.get("/od")
def get_analytics_od_matrix(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Origin-Destination pattern matrix between all camera pairs."""
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    trajectories = build_trajectories(obs)
    od = origin_destination_patterns(trajectories)
    return {
        "od_pairs": od.get("top_od_pairs", []),
        "total_cross_camera_trips": od.get("total_routes", 0)
    }
