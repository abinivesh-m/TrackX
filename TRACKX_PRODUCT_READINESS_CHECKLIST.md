# TrackX — Prototype → Product Checklist (for BEL / SIH26127 screening)

**Context that changes the strategy here:** your problem statement is confirmed as **SIH26127 — "City-Wide AI Engine for Multi-Camera ANPR Trajectory Tracking and Urban Traffic Analytics," owned by BEL (Bharat Electronics Limited)**. A web search just now turned up a dozen+ other public repos nationally building essentially the same baseline — YOLO + PaddleOCR + multi-camera trajectory tracking on FastAPI/React (`atharapawar7-web/City-Wide-Multi-Camera-ANPR`, `Mrunalpatil100/SIH26127-ANPR-Traffic-Analytics`, `SarthakJain350/NEXUS`, `rat7050/city-anpr`, `yita-droid/TrackCam`, `Vanusshka/Yuva_SIH26127`, and more). **This means "we detect plates across multiple cameras" is table stakes for this problem statement nationally, not a differentiator anymore.** The idea-screening PPT needs to lead with what's *above* that baseline, not the baseline itself. Everything below is organized around that.

BEL is a defense-electronics PSU, not a software company — they build and deploy real hardware into government/police/military command infrastructure. When they screen a software submission, they're implicitly asking "could this actually sit in a real command center," not just "does the demo work." That lens is why RBAC, secrets handling, scalability, and privacy show up below even though none of them make the demo video flashier.

---

## DONE ✅ — already real, and your actual differentiators (lead the PPT with these, not "we do ANPR")

- **Three-stage OCR temporal fusion** (`recognition/ocr_reader.py: vote_plate_text()`): whole-string voting → confidence-weighted confusable-character correction → fragment clustering. Most baseline SIH26127 submissions will just take the single highest-confidence OCR read; you fuse multiple readings of the same track into one answer.
- **Honest, ANDed 3-tier plate-state confidence system** (`pipeline.py`): VERIFIED requires both 3+ readings *and* ≥70% confidence — not just "OCR said so once." This is a real trust/reliability layer, which is exactly the kind of thing a government-adjacent evaluator cares about more than a hobbyist judge would.
- **4-signal weighted multi-camera identity fusion** (`intelligence/fusion.py`): plate text (45%) + visual appearance embedding (25%) + temporal plausibility (15%) + spatial plausibility (15%), with impossible-speed transitions explicitly rejected. Most competing teams will match on plate text alone.
- **Real road-graph-aware trajectory math** — actual per-segment distances and travel-time plausibility from a real Coimbatore road graph, not straight-line haversine distance.
- **`data_source` REAL_INFERENCE / DEMO_SYNTHETIC tagging discipline** across the database and most read endpoints, with UI badges. This is a genuine data-integrity feature almost no hackathon prototype bothers building — it's a strong "we understand production trust requirements" signal if you narrate it well.
- **Working auth (JWT), PBKDF2 password hashing, audit logging, basic per-IP rate limiting** — real, not decorative.
- **Tested deployment path** — `render.yaml`, 251/251 backend tests passing per your own `FEATURES.md`.

---

## BROKEN ⚠️ — known issues, be ready to answer honestly (fix the cheap ones before Sep 30)

- **RTSPS has no auto-reconnect** on a camera drop. Cheap-ish to add a basic retry loop; worth doing only if you have a day to spare and can test it — don't risk it in the final 48 hours.
- **OCR exact-match accuracy is ~40–43%**, below target. Don't hide it — screening judges (and definitely the Grand Finale panel) will ask, and "confidence-gated system that's honest about a 43% base OCR rate" reads far better than a suspiciously perfect number.
- **One detection job at a time, no queue** — starting a second job while one runs looks silently frozen. Documented, not hidden, in your demo script — keep it that way for the PPT too.
- **`CAMERA_RELIABILITY` weights are hand-tuned**, not learned from real match outcomes. Fine to say "current version," bad to imply it's a trained model.
- Minor: `TrajectoryPage.tsx` doesn't color-code `plate_state` the way `VehiclesPage.tsx` does. Cosmetic, low priority.

---

## MISSING ❌ — this is the actual prototype → product gap, and where "uniqueness" for BEL specifically should come from

1. **No role-based access control.** Right now it's one admin login. A real command-center deployment needs operator vs supervisor vs auditor roles — who can add to a blacklist, who can resolve an alert, who can export data. This is one of the first things a PSU evaluator will ask about, because they've deployed real systems with real accountability requirements.
2. **No secrets encryption at rest.** The RTSP camera password lives in a plaintext `.env` file. Fine for a hackathon laptop, not fine as an answer to "how would this deploy."
3. **No horizontal scalability story.** Single SQLite file, single detection worker, one job at a time. If asked "what happens at 50 cameras across a city" (a very BEL-shaped question given the problem statement literally says "city-wide"), the honest current answer is "it doesn't yet, and here's our plan" — see Optional #6.
4. **No standards-based camera onboarding.** Cameras are a hardcoded Python dict; there's no ONVIF-style discovery/onboarding flow for adding a new camera without a code change. BEL builds and deploys real camera hardware — this gap is directly in their wheelhouse to notice.
5. **No data retention / privacy policy.** A system that tracks vehicle movement city-wide needs a stated policy on how long raw footage and plate data are kept, and ideally something about non-vehicle privacy (faces/pedestrians incidentally captured). Zero cost to write, meaningful signal that you understand this isn't just a toy.
6. **`intelligence/route_hypothesis.py` is real but wired to nothing.** Either connect it to one real endpoint so it's a demonstrable feature, or stop it from being a talking point at all — don't leave it in an ambiguous middle state.
7. **No integration story for existing command-and-control systems.** BEL's own products likely already feed into some command center — a documented (even if unbuilt) plan for "alerts/observations exportable via API to an existing VMS/C2 system" would land well.

---

## OPTIONAL 💤 — highest-leverage additions if you have spare hours before Sep 30, in priority order

1. **A single "Productionization Roadmap" slide in the PPT** — RBAC, encrypted secrets, horizontal scaling, ONVIF onboarding, data retention policy — presented explicitly as *known next steps*, not hidden gaps. This costs zero code and is the single highest-leverage thing on this list: judges consistently reward teams who can articulate the gap between prototype and deployable product over teams who pretend there isn't one.
2. **Minimal RBAC** — just two roles (admin/operator) gating a couple of destructive actions (blacklist edits, alert resolution). Small surface area, strong signal.
3. **A one-page data retention & privacy note** — an hour of writing, not code.
4. **Wire `route_hypothesis.py` into one real GET endpoint** so it's a live, demonstrable feature.
5. **`TrajectoryPage` plate_state color-coding** — cheap UI polish, consistency win.
6. **A basic in-process job queue** (not Redis/Celery — just enough to let two cameras process without one blocking the other) — directly answers the "does it scale past one camera at a time" question your own demo script already has scripted.

---

## Bottom line for the PPT/video specifically

Don't spend your remaining PPT slides re-explaining "we detect plates on multiple cameras" — a dozen+ other teams nationally are submitting that exact sentence for this exact problem statement. Spend them on: the confidence-tiering and multi-signal fusion (your real technical depth), the honest real/demo data discipline (rare, and speaks directly to trustworthiness for a defense-linked evaluator), and one slide that names the production gaps above as a known roadmap rather than something to hide. That combination — genuine algorithmic depth plus engineering honesty about what's not done yet — is a stronger differentiator against this specific, crowded problem statement than any amount of extra UI polish.

---

*Compiled 2026-09-23, ahead of the Sep 30 idea-submission deadline. Pairs with `TRACKX_FINAL_PRE_SIH_AUDIT_2026-09-17.md` and `TRACKX_FILE_BY_FILE_GUIDE.md`.*

Sources checked for the SIH26127/BEL confirmation and competitive landscape:
- [SIH26127 — City-Wide Multi-Camera ANPR, BEL (GitHub)](https://github.com/atharapawar7-web/City-Wide-Multi-Camera-ANPR)
- [SIH26127-ANPR-Traffic-Analytics (GitHub)](https://github.com/Mrunalpatil100/SIH26127-ANPR-Traffic-Analytics)
- [NEXUS — City-Wide AI Engine for Multi-Camera ANPR (GitHub)](https://github.com/SarthakJain350/NEXUS)
