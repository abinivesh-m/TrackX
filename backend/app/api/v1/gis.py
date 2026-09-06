from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any

try:
    from app.core.database import get_db
    from app.api.v1.deps import get_current_user
    from app.models.user import User
except ImportError:
    from backend.app.core.database import get_db
    from backend.app.api.v1.deps import get_current_user
    from backend.app.models.user import User
from database.observation_store import ObservationStore
from database.blacklist_store import BlacklistStore
from network.camera_network import CAMERAS, ROAD_GRAPH
from intelligence.trajectory import build_trajectories
from analytics.analytics import (
    vehicles_per_camera,
    congestion_hotspots,
    cross_camera_route_frequency,
    route_frequency
)

router = APIRouter()

@router.get('/cameras')
def get_gis_cameras(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    counts = vehicles_per_camera(obs)
    res = []
    for cid, cinfo in CAMERAS.items():
        res.append({
            'camera_id': cid,
            'name': cinfo.get('name', cid),
            'lat': cinfo.get('lat', 18.5204),
            'lng': cinfo.get('long', 73.8567),
            'road': cinfo.get('road', 'Main Corridor'),
            'direction': cinfo.get('direction', 'Northbound'),
            'observation_count': counts.get(cid, 0),
            'status': 'ACTIVE',
            'reliability': cinfo.get('reliability', 1.0)
        })
    return res

@router.get('/heatmap')
def get_gis_heatmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    store = ObservationStore()
    obs = store.all_observations()
    store.close()

    counts = vehicles_per_camera(obs)
    max_count = max(counts.values()) if counts else 1

    points = []
    for cid, count in counts.items():
        if cid in CAMERAS:
            cinfo = CAMERAS[cid]
            weight = round(min(count / max_count, 1.0), 2)
            points.append([cinfo['lat'], cinfo['long'], max(weight, 0.15)])

    if not points:
        for cid, cinfo in CAMERAS.items():
            points.append([cinfo['lat'], cinfo['long'], 0.2])

    return {'points': points, 'max_intensity': max_count}

@router.get('/congestion')
def get_gis_congestion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    store = ObservationStore()
    obs = store.all_observations()
    store.close()
    trajectories = build_trajectories(obs)

    analysis = congestion_hotspots(obs, trajectories)
    scores = analysis.get("congestion_scores", {}) or {}
    congested = analysis.get("congested_cameras", []) or []
    congested_ids = {cid for cid, _ in congested}
    res = []
    for cid, cinfo in CAMERAS.items():
        if cid not in scores:
            continue
        level = "CONGESTED" if cid in congested_ids else "MODERATE"
        res.append({
            'camera_id': cid,
            'camera_name': cinfo.get('name', cid),
            'lat': cinfo.get('lat', 18.5204),
            'lng': cinfo.get('long', 73.8567),
            'level': level,
            'score': round(float(scores.get(cid, 0.0)), 3),
            'vehicle_count': int(analysis.get("density_by_camera", {}).get(cid, 0)),
            'unique_vehicles': int(analysis.get("density_by_camera", {}).get(cid, 0)),
            'description': f"{cinfo.get('name', cid)} - {level} Traffic Density (score {scores.get(cid, 0.0):.2f})"
        })
    res.sort(key=lambda x: x['score'], reverse=True)
    return res

@router.get('/od_flow')
def get_gis_od_flow(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    store = ObservationStore()
    obs = store.all_observations()
    store.close()
    trajectories = build_trajectories(obs)

    routes = cross_camera_route_frequency(trajectories)
    flows = []
    for route_key, count in routes.items():
        # keys look like "CAM_01 -> CAM_04"
        if " -> " not in route_key:
            continue
        cam_a, cam_b = route_key.split(" -> ", 1)
        if cam_a in CAMERAS and cam_b in CAMERAS:
            ca = CAMERAS[cam_a]
            cb = CAMERAS[cam_b]
            flows.append({
                'origin_camera': cam_a,
                'origin_name': ca.get('name', cam_a),
                'origin_lat': ca['lat'],
                'origin_lng': ca['long'],
                'dest_camera': cam_b,
                'dest_name': cb.get('name', cam_b),
                'dest_lat': cb['lat'],
                'dest_lng': cb['long'],
                'count': count
            })

    flows.sort(key=lambda x: x['count'], reverse=True)
    return flows
