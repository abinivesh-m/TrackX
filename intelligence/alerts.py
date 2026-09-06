"""
alerts.py

blacklist is sourced from BlacklistStore (a real, persisted table - see
database/blacklist_store.py) instead of a hardcoded Python list. This means
blacklisted plates can be added/removed without editing source code.

check_blacklist() and scan_trajectories_for_alerts() both accept an optional
`blacklist_store` argument. If you don't pass one, a store is opened lazily
against the default project database.

Enhanced with route anomaly detection using the anomaly_scoring module.
"""

from recognition.plate_matcher import plate_similarity
from database.blacklist_store import BlacklistStore
from database.alert_store import AlertStore
from intelligence.anomaly_scoring import analyze_trajectory_anomalies, AnomalyType

BLACKLIST_MATCH_THRESHOLD = 0.85  # allow for minor OCR variation

_default_store = None


def _get_default_store():
    global _default_store
    if _default_store is None:
        _default_store = BlacklistStore()
    return _default_store


def check_blacklist(plate_text, blacklist_store=None):
    """
    checks plate_text against every ACTIVE entry in BlacklistStore.
    returns (is_flagged, matched_plate, similarity).

    does a fuzzy scan against all_active() rather than a single normalized
    lookup, because OCR misreads of a blacklisted plate should still trigger
    the alert - see BLACKLIST_MATCH_THRESHOLD.
    """
    store = blacklist_store or _get_default_store()

    for entry in store.all_active():
        sim = plate_similarity(plate_text, entry["plate"])
        if sim >= BLACKLIST_MATCH_THRESHOLD:
            return True, entry["plate"], sim
    return False, None, 0.0


def scan_trajectories_for_alerts(trajectories, blacklist_store=None, all_observations=None, persist_to_db=True):
    """
    Scan trajectories for both blacklist matches and route anomalies.
    
    Args:
        trajectories: Output of trajectory.build_trajectories()
        blacklist_store: Optional BlacklistStore instance
        all_observations: Optional full observation set for anomaly detection
        persist_to_db: If True, save alerts to AlertStore database
    
    Returns:
        List of alert dicts with type, details, and severity
    """
    store = blacklist_store or _get_default_store()
    alerts = []

    # Severity of each active blacklist entry is read from the persisted store
    # (a watchlist entry's own severity is respected, not hardcoded HIGH).
    severity_by_plate = {}
    try:
        for entry in store.all_active():
            severity_by_plate[str(entry["plate"]).upper()] = entry.get("severity", "HIGH")
    except Exception:
        pass

    # Initialize AlertStore if persistence is enabled
    alert_store = AlertStore() if persist_to_db else None

    for traj in trajectories:
        # Blacklist detection
        plates_seen = set()
        for o in traj["observations"]:
            if o.get("plate_text"):
                plates_seen.add(o["plate_text"])
            if o.get("normalized_plate"):
                plates_seen.add(o["normalized_plate"])
        
        for plate in plates_seen:
            is_flagged, matched_blacklist_plate, sim = check_blacklist(plate, store)
            if is_flagged:
                severity = severity_by_plate.get(str(matched_blacklist_plate).upper(), "HIGH")
                alert = {
                    "type": "BLACKLIST_MATCH",
                    "global_id": traj["global_id"],
                    "plate_text": plate,
                    "matched_against": matched_blacklist_plate,
                    "similarity": sim,
                    "camera_hits": [o["camera_id"] for o in traj["observations"]],
                    "timestamp": traj["observations"][0]["timestamp"],
                    "severity": severity
                }
                alerts.append(alert)
                
                # Persist to database
                if alert_store:
                    try:
                        alert_store.add_alert(
                            plate=plate,
                            alert_type="BLACKLISTED_VEHICLE",
                            timestamp=traj["observations"][0]["timestamp"],
                            severity=severity,
                            camera_id=traj["observations"][0]["camera_id"],
                            description=f"Blacklist match: {plate} matched against {matched_blacklist_plate} (similarity: {sim:.2f})",
                            confidence=sim
                        )
                    except Exception as e:
                        print(f"[alerts] Failed to persist blacklist alert: {e}")

        # Repeated camera detection
        cams = [o["camera_id"] for o in traj["observations"]]
        if len(cams) >= 3 and len(set(cams)) == 1:
            alert = {
                "type": "REPEATED_CAMERA_SIGHTING",
                "global_id": traj["global_id"],
                "camera_id": cams[0],
                "count": len(cams),
                "timestamp": traj["observations"][0]["timestamp"],
                "severity": "MEDIUM"
            }
            alerts.append(alert)
            
            # Persist to database
            if alert_store:
                try:
                    plate_text = traj["observations"][0].get("plate_text") or traj["observations"][0].get("normalized_plate") or "UNKNOWN"
                    alert_store.add_alert(
                        plate=plate_text,
                        alert_type="REPEATED_CAMERA",
                        timestamp=traj["observations"][0]["timestamp"],
                        severity="MEDIUM",
                        camera_id=cams[0],
                        description=f"Vehicle seen {len(cams)} times at same camera {cams[0]} - possible loitering"
                    )
                except Exception as e:
                    print(f"[alerts] Failed to persist repeated camera alert: {e}")
        
        # Route anomaly detection using anomaly_scoring module
        try:
            anomaly_analysis = analyze_trajectory_anomalies(traj)
            # The function returns a dict with nested anomaly_analysis
            anomaly_data = anomaly_analysis.get("anomaly_analysis", {})
            anomaly_type = anomaly_data.get("anomaly_type", AnomalyType.NORMAL)
            anomaly_score = anomaly_data.get("anomaly_score", 0.0)
            
            if anomaly_type != AnomalyType.NORMAL:
                severity = "HIGH" if anomaly_score >= 70 else "MEDIUM"
                primary_reason = anomaly_data.get("primary_reason", "Unknown anomaly")
                alert = {
                    "type": "ROUTE_ANOMALY",
                    "global_id": traj["global_id"],
                    "anomaly_type": anomaly_type,
                    "anomaly_score": anomaly_score,
                    "reason": primary_reason,
                    "description": primary_reason,  # Add description field for demo output
                    "details": anomaly_data.get("signal_breakdown", {}),
                    "timestamp": traj["observations"][0]["timestamp"],
                    "severity": severity
                }
                alerts.append(alert)
                
                # Persist to database
                if alert_store:
                    try:
                        plate_text = traj["observations"][0].get("plate_text") or traj["observations"][0].get("normalized_plate") or "UNKNOWN"
                        alert_store.add_alert(
                            plate=plate_text,
                            alert_type="SUSPICIOUS_ROUTE",
                            timestamp=traj["observations"][0]["timestamp"],
                            severity=severity,
                            camera_id=traj["observations"][0]["camera_id"],
                            description=f"Route anomaly: {anomaly_type} - {anomaly_data.get('primary_reason', 'Unknown')}",
                            confidence=anomaly_score / 100.0
                        )
                    except Exception as e:
                        print(f"[alerts] Failed to persist route anomaly alert: {e}")
        except Exception as e:
            # Don't let anomaly detection break the entire alert system
            print(f"[alerts] Anomaly detection failed for trajectory {traj['global_id']}: {e}")

    # Close alert store if it was opened
    if alert_store:
        try:
            alert_store.close()
        except:
            pass

    return alerts


if __name__ == "__main__":
    from database.observation_store import ObservationStore
    from intelligence.trajectory import build_trajectories

    store = ObservationStore()
    obs = store.all_observations()
    trajs = build_trajectories(obs)

    alerts = scan_trajectories_for_alerts(trajs)
    print(f"{len(alerts)} alert(s) found")
    for a in alerts:
        print(a)

    store.close()
