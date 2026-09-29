"""
tests/test_route_anomaly_frontend_labeling.py

SIH26127 "Final Data Integrity" audit (2026-09-11): RouteAnomalyPage.tsx
used to render every persisted route anomaly identically, with no warning
when the underlying observations came from demo/seed_demo_data.py's
DEMO_SYNTHETIC seed scenario - unlike VehiclesPage.tsx and TrajectoryMap.tsx,
which both already show a "SYNTHETIC DEMO SCENARIO" badge keyed on
hop.data_source. See backend/tests/test_route_anomaly_data_provenance.py for
the backend half (schema + label derivation); this file pins the frontend
half the same way tests/test_gis_coimbatore_location.py pins map source -
plain regex checks over the real .tsx/.ts source, no JS test runner needed.
"""
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "frontend", "src")


def _read(relpath):
    with open(os.path.join(FRONTEND_SRC, relpath), "r", encoding="utf-8") as f:
        return f.read()


class TestRouteAnomalyDataSourceType:
    def test_route_anomaly_type_declares_data_source_field(self):
        src = _read("types/index.ts")
        # find the RouteAnomaly interface block specifically, not just
        # anywhere in the file (data_source appears on other interfaces too)
        match = re.search(r"export interface RouteAnomaly \{(.*?)\n\}", src, re.DOTALL)
        assert match, "RouteAnomaly interface not found in types/index.ts"
        body = match.group(1)
        assert "data_source" in body, (
            "RouteAnomaly interface must declare a data_source field - "
            "the API now returns one (see database/route_anomaly_store.py)"
        )


class TestRouteAnomalyPageShowsSyntheticBadge:
    def test_page_checks_data_source_equals_demo_synthetic(self):
        src = _read("pages/RouteAnomalyPage.tsx")
        assert "anomaly.data_source === 'DEMO_SYNTHETIC'" in src, (
            "RouteAnomalyPage.tsx must gate a warning badge on "
            "anomaly.data_source === 'DEMO_SYNTHETIC', matching "
            "VehiclesPage.tsx's hop.data_source === 'DEMO_SYNTHETIC' pattern"
        )

    def test_badge_text_matches_the_warning_used_elsewhere(self):
        src = _read("pages/RouteAnomalyPage.tsx")
        vehicles_src = _read("pages/VehiclesPage.tsx")
        # Extract the exact warning string VehiclesPage.tsx already uses so
        # this test breaks if the two ever drift out of sync, rather than
        # hardcoding the string twice.
        match = re.search(r"badge-warning\">([^<]*SYNTHETIC DEMO SCENARIO[^<]*)</span>", vehicles_src)
        assert match, "could not find the reference badge text in VehiclesPage.tsx"
        warning_text = match.group(1)
        assert warning_text in src, (
            f"RouteAnomalyPage.tsx's synthetic-data badge text {warning_text!r} "
            "does not match VehiclesPage.tsx's - keep the wording consistent "
            "across pages"
        )

    def test_badge_is_inside_the_anomaly_card_render_loop(self):
        # Guards against the badge condition being added somewhere in the
        # file (e.g. a dead/unused component) but not actually inside the
        # anomalies.map(...) card that's rendered to the user.
        src = _read("pages/RouteAnomalyPage.tsx")
        loop_match = re.search(r"anomalies\.map\(\(anomaly\) =>(.*?)\n {12}\)\)", src, re.DOTALL)
        assert loop_match, "could not locate the anomalies.map(...) render loop"
        assert "anomaly.data_source === 'DEMO_SYNTHETIC'" in loop_match.group(1), (
            "the DEMO_SYNTHETIC badge check must be inside the anomaly card "
            "render loop, not just somewhere else in the file"
        )
