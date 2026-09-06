"""
trajectory.py

reconstructs per-vehicle trajectories from raw observations.

v2 fix: the old version processed observations one at a time in arrival
order and immediately locked each one into whichever trajectory scored
highest AT THAT MOMENT. problem: a mediocre match could get committed
before a better candidate for that same observation shows up later.

this version instead:
  1. generates ALL candidate (obs_i -> obs_j) pairs within a time window
  2. scores every candidate with the fusion engine
  3. sorts all candidates by score, HIGHEST FIRST
  4. greedily links the strongest pairs first, skipping anything whose
     endpoints are already claimed

this is a standard greedy approximation for this kind of matching problem -
not a perfect global optimum (that would need the Hungarian algorithm / an
actual solver), but much better than committing in arrival order, and easy
to explain in a demo.
"""

import json
from datetime import datetime

from intelligence.fusion import is_match

MAX_CANDIDATE_GAP_SECONDS = 2 * 60 * 60  # don't even consider pairs more than 2 hours apart


def _decode_appearance(obs):
    """
    each observation row already carries its own appearance_vector as a
    JSON string (see database/observation_store.py) - decode it directly
    instead of relying on a separately-passed lookup dict, which every
    caller in this codebase (dashboard.py, alerts.py, analytics.py,
    gis_map.py) was omitting, silently zeroing out the appearance signal
    in every match score.
    """
    raw = obs.get("appearance_vector")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _consolidate_track_sessions(observations):
    """Merge observations that share the same (track_id, camera) — i.e. multiple
    frames of the same vehicle within ONE camera session — into a single
    representative unit.

    A track id never spans cameras in the real pipeline (ByteTrack is per-camera
    session scoped), so consolidation is keyed on (track_id, camera_id).
    Observations that share a track id across different cameras are kept as
    separate units and linked later by the fusion engine, so multi-camera
    linking is never short-circuited by track ids.
    """
    groups = {}
    order = []
    for obs in observations:
        tid = obs.get("track_id")
        cam = obs.get("camera_id")
        if tid and cam:
            groups.setdefault((tid, cam), []).append(obs)
        else:
            order.append(obs)
    merged = []
    for (tid, cam), group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        # keep the highest-confidence reading; earliest timestamp as the event time
        best = max(group, key=lambda o: (o.get("confidence") or 0.0, o.get("ocr_confidence") or 0.0))
        unit = dict(best)
        unit["timestamp"] = min(o["timestamp"] for o in group)
        unit["track_id"] = tid
        unit["camera_id"] = cam
        unit["_session_obs_count"] = len(group)
        # average the appearance vectors so the session keeps a stable fingerprint
        import numpy as np
        vecs = []
        for o in group:
            raw = o.get("appearance_vector")
            v = _decode_appearance(o) if isinstance(raw, str) else raw
            if v:
                try:
                    vecs.append(np.asarray(v, dtype=float))
                except (TypeError, ValueError):
                    pass
        if vecs:
            mean = np.mean(vecs, axis=0)
            unit["appearance_vector"] = json.dumps(mean.tolist())
        merged.append(unit)
    return merged + order


def _generate_identity_candidates(observations):
    """Candidate generation for linking hops of the same physical vehicle.

    Returns (plausible_candidates, suspect_candidates):
      - plausible: pairs whose fusion score passes the match threshold
      - suspect:    high plate/appearance identity pairs that fusion rejected
        for physical reasons (impossible travel time, no road connection,
        same-camera repeats) - these are kept so the anomaly engine can flag
        cloned plates / impossible transitions / loitering instead of the
        evidence silently disappearing.
    """
    n = len(observations)
    if n < 2:
        return [], []

    parsed_ts = []
    for obs in observations:
        try:
            parsed_ts.append(datetime.fromisoformat(obs["timestamp"]))
        except Exception:
            parsed_ts.append(datetime.min)
    app_vecs = [_decode_appearance(obs) for obs in observations]

    plate_map = {}
    for i, obs in enumerate(observations):
        p = obs.get("normalized_plate") or obs.get("plate_text")
        if p and str(p).strip().upper() not in ("", "UNAVAILABLE", "UNKNOWN"):
            plate_map.setdefault(str(p).strip().upper(), []).append(i)

    def _plate_of(obs):
        return obs.get("normalized_plate") or obs.get("plate_text") or ""

    from recognition.plate_matcher import plate_similarity

    plausible, suspect = [], []
    seen = set()

    # 1. same-normalized-plate candidates
    same_plate_pairs = []
    for p_clean, indices in plate_map.items():
        if len(indices) > 1:
            for a_i in range(len(indices)):
                for b_i in range(a_i + 1, len(indices)):
                    i, j = indices[a_i], indices[b_i]
                    if parsed_ts[i] > parsed_ts[j]:
                        i, j = j, i
                    if (i, j) not in seen:
                        seen.add((i, j))
                        same_plate_pairs.append((i, j))

    # 2. windowed fuzzy-plate candidates (confusable OCR reads, e.g. B/8)
    window_limit = 200
    for i in range(n):
        for j in range(i + 1, min(n, i + window_limit)):
            if (i, j) in seen:
                continue
            seen.add((i, j))
            gap = (parsed_ts[j] - parsed_ts[i]).total_seconds()
            if gap > MAX_CANDIDATE_GAP_SECONDS:
                break
            pa, pb = _plate_of(observations[i]), _plate_of(observations[j])
            if not pa or not pb:
                continue
            if plate_similarity(pa, pb) < 0.85:
                continue
            same_plate_pairs.append((i, j))

    for i, j in same_plate_pairs:
        gap = (parsed_ts[j] - parsed_ts[i]).total_seconds()
        if gap > MAX_CANDIDATE_GAP_SECONDS:
            continue
        try:
            matched, score, breakdown = is_match(
                observations[i], observations[j], app_vecs[i], app_vecs[j]
            )
        except Exception:
            continue
        if matched:
            plausible.append((gap, score, i, j, breakdown))
        else:
            reason = breakdown.get("rejected_reason", "rejected by fusion")
            suspect.append((gap, i, j, reason))

    return plausible, suspect


def _link_greedy(observations, candidates, suspect_links):
    """Build chains. Links are applied chronologically first (shortest time
    gap between two hops wins, so adjacent hops of a route always chain
    before a long skip over intermediate cameras); within the same gap the
    higher fusion score wins. Plausible edges are processed first, then
    SUSPECT identity edges (impossible/cloned/loitering evidence) between
    any remaining endpoints so the anomaly engine can flag them."""
    n = len(observations)
    # (gap, -score) ordering: adjacent-in-time hops first
    candidates.sort(key=lambda c: (c[0], -c[1]))
    suspect_links.sort(key=lambda c: c[0])

    next_link = {}
    has_predecessor = set()
    labels = {}

    def _try_link(i, j, label):
        if i in next_link or j in has_predecessor or i == j:
            return False
        next_link[i] = j
        has_predecessor.add(j)
        labels[(i, j)] = label
        return True

    for gap, score, i, j, breakdown in candidates:
        label = {"confidence_label": breakdown.get("confidence_label", "MATCH"),
                 "score": score,
                 "plate": breakdown.get("plate", 0.0),
                 "appearance": breakdown.get("appearance", 0.0),
                 "temporal": breakdown.get("temporal", 0.0),
                 "spatial": breakdown.get("spatial", 0.0),
                 "total": breakdown.get("total", score)}
        _try_link(i, j, label)

    for gap, i, j, reason in suspect_links:
        label = {"confidence_label": "SUSPECT",
                 "rejected_reason": reason,
                 "plate": 0.0,
                 "appearance": 0.0,
                 "temporal": 0.0,
                 "spatial": 0.0,
                 "total": 0.0}
        _try_link(i, j, label)

    trajectories = []
    visited = set()
    for start in range(n):
        if start in has_predecessor or start in visited:
            continue
        chain = [start]
        scores = []
        breakdowns = []
        cur = start
        while cur in next_link:
            nxt = next_link[cur]
            chain.append(nxt)
            scores.append(labels.get((cur, nxt), {}).get("score", 1.0))
            breakdowns.append(labels.get((cur, nxt), {}))
            visited.add(nxt)
            cur = nxt
        visited.add(start)
        traj_obs = [observations[k] for k in chain]
        plate_texts = []
        for obs in traj_obs:
            if obs.get("plate_text"):
                plate_texts.append(obs["plate_text"])
            elif obs.get("normalized_plate"):
                plate_texts.append(obs["normalized_plate"])
        from collections import Counter
        plate_text = Counter(plate_texts).most_common(1)[0][0] if plate_texts else "Unknown"
        trajectories.append({
            "global_id": 0,  # set by caller
            "plate_text": plate_text,
            "observations": traj_obs,
            "match_scores": scores,
            "match_breakdowns": breakdowns,
        })
    return trajectories


def build_trajectories(observations):
    """
    observations: list of obs dicts, sorted by timestamp
    returns: list of trajectories = {
        "global_id": int,
        "observations": [...],
        "match_scores": [...],
        "match_breakdowns": [...]
    }

    Matching is identity-based, NOT "same OCR string => same vehicle": hops are
    linked by the fusion engine (plate similarity weighted by OCR confidence,
    appearance similarity, temporal and spatial feasibility). Pairs whose plate
    identity is high but whose physical transition is impossible are still
    chained as SUSPECT links so anomaly detection can flag cloned plates and
    impossible transitions rather than silently dropping the evidence.
    """
    units = _consolidate_track_sessions(observations)
    n = len(units)
    if n == 0:
        return []
    if n == 1:
        traj_obs = units
        plate_text = (traj_obs[0].get("plate_text")
                      or traj_obs[0].get("normalized_plate") or "Unknown")
        return [{"global_id": 1, "plate_text": plate_text,
                 "observations": traj_obs, "match_scores": [], "match_breakdowns": []}]

    # sort chronologically before candidate generation
    def _ts(o):
        try:
            return datetime.fromisoformat(o["timestamp"])
        except Exception:
            return datetime.min
    units = sorted(units, key=_ts)

    plausible, suspect = _generate_identity_candidates(units)
    trajectories = _link_greedy(units, plausible, suspect)
    for idx, traj in enumerate(trajectories):
        traj["global_id"] = idx + 1
    return trajectories


def trajectory_summary(traj):
    obs_list = traj["observations"]
    plate_text = traj.get("plate_text", "Unknown")
    
    # Also collect individual plate reads for reference
    plates = set()
    for o in obs_list:
        if o.get("plate_text"):
            plates.add(o["plate_text"])
        if o.get("normalized_plate"):
            plates.add(o["normalized_plate"])
    
    lines = [f"Global Vehicle #{traj['global_id']} "
              f"(plate: {plate_text}, individual reads: {plates})"]

    for i, obs in enumerate(obs_list):
        plate_display = obs.get("normalized_plate") or obs.get("plate_text") or plate_text
        lines.append(f"  {obs['timestamp']}  {obs['camera_id']}  "
                      f"plate={plate_display} conf={obs['confidence']}")
        if i > 0:
            score = traj["match_scores"][i - 1]
            label = traj["match_breakdowns"][i - 1]["confidence_label"]
            lines.append(f"      -> matched to previous hop: {score} ({label})")

    return "\n".join(lines)


if __name__ == "__main__":
    from database.observation_store import ObservationStore

    store = ObservationStore()
    obs = store.all_observations()
    print(f"loaded {len(obs)} observations")

    trajs = build_trajectories(obs)
    print(f"reconstructed {len(trajs)} vehicle trajectories\n")

    for t in trajs:
        print(trajectory_summary(t))
        print()

    store.close()
