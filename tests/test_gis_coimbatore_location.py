"""
tests/test_gis_coimbatore_location.py

SIH26127 "Critical GIS Location Fix" (2026-09-11): regression tests for the
real bug where GISPage.tsx and TrajectoryPage.tsx each independently
hardcoded [18.5204, 73.8567] (Pune, Maharashtra) as their Leaflet map's
initial center, while every camera in network/camera_network.py's CAMERAS
dict (and the OTHER three map components - CameraMap.tsx, TrafficHeatmap.tsx,
CongestionMap.tsx) already used real Coimbatore, Tamil Nadu coordinates.
Camera markers were placed correctly; the map viewport itself just opened
~800km away from every marker on it.

No frontend test runner (vitest/jest) is set up in this repo - these are
plain, real Python checks that parse the actual .tsx/.ts source text, the
same way this repo's other cross-file consistency checks work. They fail
loudly on the exact literal regression (a Pune-area coordinate reappearing
anywhere in a map component) rather than only checking that today's fix
compiles.
"""
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "frontend", "src")

# Generous real-world bounding box around Coimbatore district, Tamil Nadu -
# wide enough to comfortably contain every camera TrackX currently models
# and any reasonable future addition in the same city, while safely
# excluding other Indian metros this bug could plausibly regress to
# (Pune ~18.5/73.8, Bangalore ~12.97/77.59, Chennai ~13.08/80.27, Mumbai
# ~19.07/72.87).
COIMBATORE_LAT_RANGE = (10.8, 11.3)
COIMBATORE_LONG_RANGE = (76.7, 77.3)

MAP_TSX_FILES = [
    "pages/GISPage.tsx",
    "pages/TrajectoryPage.tsx",
    "components/maps/CameraMap.tsx",
    "components/maps/TrafficHeatmap.tsx",
    "components/maps/CongestionMap.tsx",
]

# Any [lat, lng]-shaped numeric pair literal appearing in map source files -
# used to catch a stray hardcoded coordinate anywhere, not just at the
# specific "center:" call sites this bug happened to appear in.
_COORD_PAIR_RE = re.compile(r"\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]")


def _in_coimbatore(lat, lng):
    return COIMBATORE_LAT_RANGE[0] <= lat <= COIMBATORE_LAT_RANGE[1] and \
        COIMBATORE_LONG_RANGE[0] <= lng <= COIMBATORE_LONG_RANGE[1]


class TestCameraNetworkCoordinatesAreCoimbatore:
    """The backend camera configuration (the actual single source of truth
    for camera geography) was never wrong - this pins it down explicitly
    so a future edit can't silently move a camera out of Coimbatore."""

    def test_every_camera_is_within_the_coimbatore_bounding_box(self):
        from network.camera_network import CAMERAS

        assert len(CAMERAS) > 0
        out_of_bounds = []
        for cam_id, cam in CAMERAS.items():
            if not _in_coimbatore(cam["lat"], cam["long"]):
                out_of_bounds.append((cam_id, cam["lat"], cam["long"]))
        assert not out_of_bounds, (
            f"camera(s) outside the Coimbatore bounding box: {out_of_bounds}"
        )


class TestNoPuneOrOtherOutOfCityCoordinatesInMapSource:
    """Direct regression test for the confirmed bug: scans the exact
    source files a Leaflet map is built in for ANY hardcoded [lat, lng]
    literal outside the Coimbatore bounding box - not just the specific
    [18.5204, 73.8567] value this bug happened to use."""

    def test_no_out_of_city_coordinate_literals_in_map_components(self):
        offenders = []
        for rel_path in MAP_TSX_FILES:
            path = os.path.join(FRONTEND_SRC, rel_path)
            assert os.path.isfile(path), f"expected map source file missing: {path}"
            text = open(path, encoding="utf-8").read()
            for lat_str, lng_str in _COORD_PAIR_RE.findall(text):
                lat, lng = float(lat_str), float(lng_str)
                if not _in_coimbatore(lat, lng):
                    offenders.append((rel_path, lat, lng))
        assert not offenders, (
            f"found coordinate literal(s) outside the Coimbatore bounding box in map "
            f"source files - this is exactly the Pune-map-center regression fixed "
            f"2026-09-11: {offenders}"
        )

    def test_gis_page_and_trajectory_page_use_the_shared_default_center(self):
        """These two pages are exactly the ones that had their own
        independent (and wrong) hardcoded center - pin them to the shared
        constant so they can never again drift to a separate literal."""
        for rel_path in ("pages/GISPage.tsx", "pages/TrajectoryPage.tsx"):
            path = os.path.join(FRONTEND_SRC, rel_path)
            text = open(path, encoding="utf-8").read()
            assert "DEFAULT_MAP_CENTER" in text, (
                f"{rel_path} no longer imports/uses DEFAULT_MAP_CENTER from "
                f"@/config/mapTiles - it may have regressed to a separately "
                f"hardcoded map center."
            )
            assert "center: DEFAULT_MAP_CENTER" in text, (
                f"{rel_path} imports DEFAULT_MAP_CENTER but its Leaflet map's "
                f"'center' option isn't actually set to it."
            )


class TestMapTilesConfigDefinesOneCoimbatoreCenter:
    def test_default_map_center_constant_is_in_coimbatore(self):
        path = os.path.join(FRONTEND_SRC, "config", "mapTiles.ts")
        text = open(path, encoding="utf-8").read()
        m = re.search(
            r"DEFAULT_MAP_CENTER:\s*\[number,\s*number\]\s*=\s*\[\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\]",
            text,
        )
        assert m, "DEFAULT_MAP_CENTER constant not found (or not typed as [number, number]) in mapTiles.ts"
        lat, lng = float(m.group(1)), float(m.group(2))
        assert _in_coimbatore(lat, lng), (
            f"DEFAULT_MAP_CENTER=[{lat}, {lng}] is outside the Coimbatore bounding box"
        )
