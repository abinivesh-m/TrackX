"""
tests/test_alert_frontend_labeling.py

SIH26127 "Final Data Integrity" audit (2026-09-11): pins AlertsPage.tsx's
SyntheticDataBadge, added alongside intelligence/alerts.py's
evidence.data_source field (see tests/test_alert_data_provenance.py for the
backend half). Plain regex checks over the real .tsx source, matching this
repo's established pattern for frontend checks with no JS test runner
(tests/test_gis_coimbatore_location.py, tests/test_route_anomaly_frontend_labeling.py).
"""
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "frontend", "src")


def _read(relpath):
    with open(os.path.join(FRONTEND_SRC, relpath), "r", encoding="utf-8") as f:
        return f.read()


class TestAlertsPageShowsSyntheticBadge:
    def test_page_defines_a_shared_synthetic_badge_component(self):
        src = _read("pages/AlertsPage.tsx")
        assert "function SyntheticDataBadge" in src
        assert "evidence?.data_source !== 'DEMO_SYNTHETIC'" in src or \
               "evidence.data_source !== 'DEMO_SYNTHETIC'" in src

    def test_badge_text_matches_the_warning_used_elsewhere(self):
        src = _read("pages/AlertsPage.tsx")
        vehicles_src = _read("pages/VehiclesPage.tsx")
        match = re.search(r"badge-warning\">([^<]*SYNTHETIC DEMO SCENARIO[^<]*)</span>", vehicles_src)
        assert match, "could not find the reference badge text in VehiclesPage.tsx"
        warning_text = match.group(1)
        assert warning_text in src, (
            f"AlertsPage.tsx's synthetic-data badge text {warning_text!r} "
            "does not match VehiclesPage.tsx's - keep the wording consistent"
        )

    def test_alert_evidence_renders_the_shared_badge_for_every_alert_type(self):
        # Guards against the badge being defined but never actually
        # rendered inside AlertEvidence (the component that renders each
        # alert card's per-type evidence block).
        src = _read("pages/AlertsPage.tsx")
        match = re.search(
            r"function AlertEvidence\([^)]*\)\s*\{(.*?)\n\}", src, re.DOTALL
        )
        assert match, "could not locate the AlertEvidence component"
        assert "<SyntheticDataBadge" in match.group(1), (
            "AlertEvidence must render <SyntheticDataBadge .../> so every "
            "alert type (not just one case) can show the warning"
        )
