# TrackX — Data Retention & Privacy Policy (Draft v0.1)

> Draft for discussion with BEL / the problem-statement owner. Not legal advice.
> Companion to the SIH26127 submission ("City-Wide AI Engine for Multi-Camera ANPR
> Trajectory Tracking and Urban Traffic Analytics").

## 1. What TrackX collects

TrackX processes CCTV/ANPR camera feeds and persists, per observation:

- License plate text (raw + normalized) and OCR confidence
- Camera ID, timestamp, lat/long
- Vehicle type, track ID, vehicle appearance embedding (512-dim ResNet-18 feature, not a raw image)
- Plate crop image (saved to disk for evidence)
- Alert records (blacklist matches, route anomalies)

TrackX does **not** store full video frames by default, does not perform face recognition, and does not attempt to identify drivers or passengers.

## 2. Who can access what (RBAC)

| Role | Can view observations/trajectories | Can resolve alerts | Can edit blacklist | Can export data | Can manage users |
|---|---|---|---|---|---|
| Operator | ✅ | ✅ | ❌ | ❌ | ❌ |
| Supervisor | ✅ | ✅ | ✅ | ✅ (scoped) | ❌ |
| Auditor | ✅ (read-only, logged) | ❌ | ❌ | ✅ (audit exports) | ❌ |
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |

Every access to a vehicle's trajectory or plate data is written to the audit log
(`backend/app/models/audit_log.py`) with user, timestamp, and the queried plate.

## 3. Retention periods (proposed defaults)

| Data class | Default retention | Rationale |
|---|---|---|
| Raw plate-crop images | 30 days | Evidence for active investigations; disk cost |
| Observation records (plate, camera, time, location) | 90 days | Supports trajectory reconstruction windows; longer retention needs legal basis |
| Alert records (blacklist/route-anomaly) | 1 year | Audit trail for security incidents |
| Audit-log entries | 2 years | Accountability for data access |
| Aggregated analytics (density, OD, heatmaps) | Indefinite (anonymized) | No plate-level data; safe for long-term trend analysis |
| Blacklist entries | Until manually removed | Operational necessity |

Retention is enforced by a scheduled cleanup job (to be implemented; today manual).

## 4. Privacy principles

1. **Purpose limitation** — data is used only for traffic management, law enforcement and public safety, as authorized by the deploying authority (BEL / city police). No commercial use, no resale.
2. **Data minimization** — only plate-level identifiers are stored; no driver/passenger biometrics, no full-frame video by default.
3. **Access control** — RBAC + audit log; no anonymous access to plate data.
4. **Synthetic vs. real discipline** — every observation is tagged `REAL_INFERENCE` or `DEMO_SYNTHETIC`; synthetic data is never presented as real (UI badges).
5. **Transparency** — operators see which camera, when, and why a read was used; confidence tiers (VERIFIED/TENTATIVE/LOW_CONFIDENCE/UNKNOWN) prevent over-trusting low-quality reads.
6. **Right to erasure (on request)** — a plate's observations can be purged on a verified request from the authorized authority, subject to legal hold.

## 5. Known gaps (honest)

- Raw RTSP credentials live in `.env` (plaintext) in the prototype — production deployment must use a secrets manager / encrypted store.
- Retention cleanup is manual today (scheduled job planned).
- No automated anonymization of aggregated exports yet.
- Cross-border / inter-agency data sharing is out of scope for the prototype and needs a data-sharing agreement.

## 6. Alignment with BEL / government deployment

This policy is designed to be finalized jointly with BEL's legal/policy team and the deploying city authority. The prototype demonstrates the *mechanisms* (tagging, RBAC, audit log, confidence tiers); the *policy values* (retention days, roles, erasure rules) are configuration, not code.