# ⚠️ STALE — DO NOT USE THIS DOCUMENT

**This file is outdated and contradicts the current project state. Do not show it to judges or reference it during the SIH-26127 demo.**

Specifically, as of 2026-09-17 this file:

- Instructs running `streamlit run dashboard/dashboard.py` — **there is no Streamlit dashboard in this repo anymore** (see `README.md`). The real app is the FastAPI backend + React frontend (`RUNNING.md`).
- Claims trained plate-detector weights (`.pt`/`.pth`) are bundled in `models/` — **they are git-ignored and not guaranteed present in a checkout** (see `README.md`).
- Quotes an OCR exact-match accuracy of **72.4%** on a 551-sample set, with no methodology comparable to the project's other, more rigorous measurements. This is the most favorable of several different OCR numbers that exist across this project's docs and should **not** be quoted to judges.

**For an accurate, current compliance summary, use `docs/SIH_26127_COMPLIANCE.md` instead** — it honestly marks each SIH-26127 requirement as IMPLEMENTED / PARTIAL / NOT MET and states plainly what must not be presented as achieved (e.g. >90% OCR accuracy).

**For the current, honestly-measured OCR accuracy number, use `docs/OCR_REAL_ACCURACY_AUDIT.md`** (42.9% exact-match, 15/35 real hand-graded samples) — this is the number reflected in `TRACKX_DEMO_SCRIPT.md`'s scripted answer ("around 40–43%").

This file has been left in place (rather than deleted) only so its history isn't lost; its content below this point is retained for reference but should be treated as historical, not current.

---

*(Original content intentionally not reproduced here to avoid accidental reuse of its stale numbers. See git history / your own backup if you need the original text.)*
