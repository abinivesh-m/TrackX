"""
config.py

Phase 0 audit (SIH26127): single source of truth for project paths.

Every module that touches the database or generated outputs used to default
to a *relative* path string like "outputs/results/observations.db" or
"outputs/results/city_map.html". That works fine as long as you always run
commands from the project root (as the README instructs), but it's a
foot-gun: run the same command from a different working directory (a judge's
shell, a different terminal tab, a task runner) and you silently get a
second, empty database next to a not-found file, instead of a clear error.

This module computes every path relative to THIS FILE's location (the
project root), not the current working directory, using pathlib. It doesn't
change any behavior - the directory layout and filenames are unchanged - it
just makes the defaults robust to "what folder was I in when I ran this."

Every store / CLI module still accepts an explicit path argument that
overrides these defaults (e.g. for tests, which intentionally use /tmp
paths), so nothing here is a hard-coded requirement.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"

DB_PATH = RESULTS_DIR / "observations.db"
CITY_MAP_PATH = RESULTS_DIR / "city_map.html"

# str versions for the (many) callers written against sqlite3.connect(str) /
# os.path-style code, so nobody has to sprinkle str(...) everywhere.
DB_PATH_STR = str(DB_PATH)
CITY_MAP_PATH_STR = str(CITY_MAP_PATH)
