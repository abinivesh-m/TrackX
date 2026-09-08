import math
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

# Phase 14: no longer falls back to "backend.app.X" imports (see
# app/main.py's import block for why - that fallback duplicated model
# registration under a second SQLAlchemy Base and crashed the first real
# ORM write anywhere in the process).
from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from database.observation_store import ObservationStore
from network.camera_network import CAMERAS
from intelligence.trajectory import build_trajectories
from recognition.plate_matcher import normalize_plate

router = APIRouter()

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@router.get('/search')
def get_trajectory_search(
    plate: str = Query(..., description='License plate to trace'),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    clean_search = normalize_plate(plate)
    store = ObservationStore()
    all_obs = store.all_observations()
    store.close()

    matching = []
    for o in all_obs:
        p = normalize_plate(o.get('normalized_plate') or o.get('plate_text') or '')
        if p == clean_search or clean_search in p or p in clean_search:
            matching.append(o)

    if not matching:
        return {
            'plate': plate,
            'trajectory': [],
            'total_distance_km': 0.0,
            'total_duration_min': 0.0,
            'average_speed_kmh': 0.0,
            'anomaly_flags': [],
            'observation_count': 0
        }

    matching.sort(key=lambda x: x['timestamp'])

    hops = []
    total_dist = 0.0
    anomalies = []

    for idx, obs in enumerate(matching):
        cid = obs.get('camera_id')
        cam_info = CAMERAS.get(cid, {})
        lat = obs.get('lat') or cam_info.get('lat', 18.5204)
        lng = obs.get('long') or cam_info.get('long', 73.8567)
        cname = cam_info.get('name', cid)

        hop = {
            'hop_index': idx + 1,
            'camera_id': cid,
            'camera_name': cname,
            'lat': float(lat),
            'lng': float(lng),
            'timestamp': obs.get('timestamp'),
            'confidence': float(obs.get('confidence', 0.85)),
            'plate_text': obs.get('normalized_plate') or obs.get('plate_text'),
            'vehicle_type': obs.get('vehicle_type', 'car')
        }

        if idx > 0:
            prev_hop = hops[-1]
            dist = haversine_km(prev_hop['lat'], prev_hop['lng'], hop['lat'], hop['lng'])
            total_dist += dist
            hop['distance_from_prev_km'] = round(dist, 2)

            t_prev = datetime.fromisoformat(prev_hop['timestamp'])
            t_curr = datetime.fromisoformat(hop['timestamp'])
            dt_hours = max((t_curr - t_prev).total_seconds() / 3600.0, 0.0001)
            hop_speed = dist / dt_hours
            hop['speed_kmh'] = round(hop_speed, 1)

            if hop_speed > 130.0:
                p_cam = prev_hop["camera_id"]
                anomalies.append(f"Unrealistic speed of {hop_speed:.1f} km/h between {p_cam} and {cid}")

        hops.append(hop)

    t_start = datetime.fromisoformat(hops[0]['timestamp'])
    t_end = datetime.fromisoformat(hops[-1]['timestamp'])
    total_dur_min = (t_end - t_start).total_seconds() / 60.0
    avg_speed = (total_dist / (total_dur_min / 60.0)) if total_dur_min > 0.5 else 0.0

    return {
        'plate': plate.upper(),
        'normalized_plate': clean_search,
        'trajectory': hops,
        'total_distance_km': round(total_dist, 2),
        'total_duration_min': round(total_dur_min, 1),
        'average_speed_kmh': round(avg_speed, 1),
        'anomaly_flags': anomalies,
        'observation_count': len(hops)
    }

@router.get('/recent')
def get_recent_trajectories(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    store = ObservationStore()
    all_obs = store.all_observations()
    store.close()

    plate_groups = {}
    for obs in all_obs:
        p = normalize_plate(obs.get('normalized_plate') or obs.get('plate_text') or '')
        if not p or p == 'UNAVAILABLE':
            continue
        if p not in plate_groups:
            plate_groups[p] = []
        plate_groups[p].append(obs)

    multi_cam = []
    for p, obs_list in plate_groups.items():
        cams = set(o['camera_id'] for o in obs_list)
        if len(cams) >= 2 or len(obs_list) >= 2:
            obs_list.sort(key=lambda x: x['timestamp'])
            first = obs_list[0]
            last = obs_list[-1]
            t0 = datetime.fromisoformat(first['timestamp'])
            t1 = datetime.fromisoformat(last['timestamp'])
            dur = round((t1 - t0).total_seconds() / 60.0, 1)

            multi_cam.append({
                'plate': p,
                'observation_count': len(obs_list),
                'unique_cameras': len(cams),
                'start_camera': first['camera_id'],
                'end_camera': last['camera_id'],
                'start_time': first['timestamp'],
                'last_seen': last['timestamp'],
                'duration_minutes': dur,
                'vehicle_type': first.get('vehicle_type', 'car')
            })

    multi_cam.sort(key=lambda x: x['last_seen'], reverse=True)
    return multi_cam[:limit]
