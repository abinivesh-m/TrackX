"""
system_health.py

System Health page for TrackX - Component status and diagnostics.
This is a separate page from the main dashboard.

run with:
    streamlit run dashboard/system_health.py
"""

import os
import sys
import importlib.util
import glob

import streamlit as st
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.observation_store import ObservationStore, database_file_exists
from config import DB_PATH_STR, PROJECT_ROOT

st.set_page_config(page_title="TrackX System Health", layout="wide")
st.title("🏥 TrackX — System Health & Diagnostics")

# Link back to main dashboard
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")
st.sidebar.markdown("Open Main Dashboard at **http://localhost:8501**")

DB_PATH = DB_PATH_STR

# --------------------------------------------------------------------------
# System Health & Diagnostics
# --------------------------------------------------------------------------

st.subheader("System Health & Diagnostics")
st.caption("Check the status of all TrackX components and dependencies.")
    
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

st.dataframe(pd.DataFrame(health_rows, columns=["Component", "Status"]),
             hide_index=True, use_container_width=True)

st.divider()

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
                st.caption(f"📷 {obs.get('camera_id')} | 🚗 {obs.get('plate_text') or 'No plate'} | ⏰ {obs.get('timestamp')}")
    except Exception as e:
        st.error(f"Database error: {e}")
else:
    st.warning("No database found. Run the visual pipeline to create one.")
