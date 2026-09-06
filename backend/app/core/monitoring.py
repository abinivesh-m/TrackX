"""Prometheus metrics and monitoring for TrackX."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from datetime import datetime
import time

# Request metrics
request_count = Counter(
    'trackx_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'trackx_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

# Database metrics
db_query_duration = Histogram(
    'trackx_db_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)
)

db_observations_count = Gauge(
    'trackx_observations_total',
    'Total observations in database'
)

db_trajectories_count = Gauge(
    'trackx_trajectories_total',
    'Total trajectories computed'
)

# Trajectory metrics
trajectory_search_duration = Histogram(
    'trackx_trajectory_search_duration_seconds',
    'Trajectory search duration',
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
)

trajectory_fusion_score = Histogram(
    'trackx_trajectory_fusion_score',
    'Trajectory fusion score distribution',
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# Alert metrics
alerts_generated = Counter(
    'trackx_alerts_generated_total',
    'Total alerts generated',
    ['alert_type']
)

alerts_active = Gauge(
    'trackx_alerts_active',
    'Currently active alerts'
)

# ML model metrics
ocr_processing_duration = Histogram(
    'trackx_ocr_processing_duration_seconds',
    'OCR processing duration',
    ['ocr_engine'],
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0)
)

detection_processing_duration = Histogram(
    'trackx_detection_processing_duration_seconds',
    'Vehicle detection duration',
    buckets=(0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
)

detection_count = Counter(
    'trackx_detections_total',
    'Total vehicle detections',
    ['detector_type', 'class']
)

# Cache metrics
cache_hits = Counter(
    'trackx_cache_hits_total',
    'Cache hits',
    ['cache_type']
)

cache_misses = Counter(
    'trackx_cache_misses_total',
    'Cache misses',
    ['cache_type']
)

cache_size = Gauge(
    'trackx_cache_size_bytes',
    'Cache size in bytes',
    ['cache_type']
)

# System metrics
system_ready = Gauge(
    'trackx_system_ready',
    'System readiness (1=ready, 0=not ready)'
)

components_healthy = Gauge(
    'trackx_components_healthy',
    'Number of healthy components'
)

components_total = Gauge(
    'trackx_components_total',
    'Total system components'
)
