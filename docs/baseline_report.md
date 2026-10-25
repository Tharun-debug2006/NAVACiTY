# NavaCity — Baseline report

**Date:** 2026-10-21
**Commit:** no git repository is initialised in `c:\AI\NavaCity` (`git rev-parse` → *not a git repository*), so no commit id is available.
**Environment:** Windows, Python 3.12 in `c:\AI\NavaCity\.venv`, Node 20+ / npm, SQLite.

> All data in this project is **SIMULATED**. NavaCity is a fictional city.

---

## 1. Baseline commands and their results

| # | Command | Result |
|---|---------|--------|
| 1 | `python -m pytest backend\tests -q` | **PASS** — `112 passed` |
| 2 | `python verify_setup.py` | **PASS** — `61/61 verification checks passed` |
| 3 | `python backend\test_live_api.py` (backend on `:8000`) | **PASS** — all live API checks passed |
| 4 | `python frontend_check.py` (Vite dev server on `:5173`) | **PASS** — `13/13 frontend checks passed` |

The baseline is **fully green**: no test, verification or live check failed.

The issues in the task list were therefore *not* produced by a broken build — they are
behavioural, documentation and UI defects that the existing test suite does not cover.

## 2. Facts measured from the code and the data (not from the screenshots)

| Fact | Value | Where it comes from |
|------|-------|---------------------|
| Simulated window | `2025-01-01` → `2025-06-30` (181 days) | `navacity_core/config.py:31-32` |
| Dataset rows | `95,568` | `data/generated/navacity_transport.csv` |
| Rows per (segment, day) | **exactly 4** for every one of the 132 segments | CSV scan: `PER_SEGMENT_DAY_VALUES = [4]` |
| Distinct hours present in the CSV | 24 (every hour of the day appears) | CSV scan: `HOURS_PRESENT = 24` |
| Distinct segments | 132 | CSV scan |
| Distinct stations | 41 | `places` table: `kind='station'` → 41 |
| Distinct bus-only stops | 5 | `places` table: `kind='stop'` → 5 |
| Places served by at least one bus route | **42** | `places` table: `bus_routes != ''` → 42 |
| Metro lines / bus routes | 6 / 18 | `routes` table |
| Vehicle capacity | metro 320, bus 48 | `navacity_core/network.py:451` |
| Wait formula | `headway × 0.45` (metro) / `× 0.50` (bus) | `navacity_core/network.py:464`, `model_service.py:149-154` |
| Wait at 14 veh/h | metro `1.93` min, bus `2.14` min | computed from the formula |
| Model metrics (time-ordered split) | metro MAE 223.18 / RMSE 351.35 / R² 0.9443; bus MAE 16.45 / RMSE 28.05 / R² 0.9539 | `ml/artifacts/metrics.json` |

### 2.1 The data-granularity contradiction (issue C3)

The README says *"4 observations per segment per day"*; the authority dashboard says
*"95,568 simulated hourly observations"*. **Both are about the same 95,568 rows, but
only one of them describes the granularity correctly.**

* The simulator samples **4 hours per segment per day** (`SAMPLES_PER_SEGMENT_DAY = 4`,
  `navacity_core/config.py:37`; the loop at `navacity_core/simulator.py:259-265` draws
  08:00 and 18:00 plus two uniformly chosen hours).
* The 24 distinct hour values in the CSV are the *union* over 181 days, not a
  complete hourly time series of any single day.
* Therefore the correct description is:
  **95,568 simulated observations, 4 per route-segment per day (hourly samples, not a complete hourly series).**

## 3. Issues found in the baseline code (Phase 1 verification)

| ID | Severity | Status | Summary |
|----|----------|--------|---------|
| C1 | Critical | **confirmed** | The origin/destination selection never reaches `/api/predict`. `PublicDashboard.jsx:134-139` posts only `{route_id, hour, date, mode}`; `PredictionRequest` (`backend/app/schemas.py`) has no `origin_id`/`destination_id`; `model_service.predict()` resolves the segment with `_resolve_segment(index, route_id, segment_id)` (`model_service.py:144`, `238-250`), which **ignores the journey** and falls back to the segment with the highest `segment_index`. The alternatives panel title is built from `alternatives.origin`/`alternatives.destination` while each row shows `item.origin_name → item.dest_name` of the *candidate's* busiest segment — so the title and the rows can disagree. |
| C2 | Critical | **confirmed** | The public date picker has no `min`/`max` and the default is `tomorrowISO()` (`PublicDashboard.jsx:32-36, 47`), i.e. 2026-10-22 — outside the 2025-01-01→2025-06-30 training window. `navacity_core/features.py:100-115` clips `day_index` but `month_sin`/`month_cos` still encode month 10, which never occurred in training. |
| C3 | Critical | **confirmed** | See §2.1. The README (§5) and the authority KPI text (`analytics_service.py:558`) contradict each other. |
| C4 | Critical | **confirmed** | The "Predicted demand by hour" chart plots `predicted_passengers` (model forecast for the *busiest* segment of the route) while "Simulated crowd level by hour" plots `mean_occupancy_pct` (a *percentage* of capacity) from `/api/history/hourly`. Two different units, two different scopes, no axis units on either. |
| C5 | Critical | **confirmed** | `TransitMap.jsx:92-113` colours the selected line with `crowdColor(crowd)` — a **crowd** colour (green/amber/orange/red) — and falls back to the network colour otherwise. Metro lines keep their own per-line colours (`#2563eb`, `#dc2626`, `#16a34a`, …) and bus lines are always `#f59e0b`, so "bus-coloured route highlighted while M1 is selected" is the crowd colour bleeding onto the wrong line. The legend says "Metro line" (blue) / "Bus route" (amber) but the actual metro colours are per-line. |
| C6 | Critical | **confirmed** | `App.jsx:73-115` renders the "Authority signed in" badge and the "Sign out" button in the **global** header, which is shared by the public page. |
| C7 | Critical | **confirmed** | `.gitignore` has no `.env` entry. `.env.example:15` ships `NAVACITY_AUTH_PASSWORD=dumpme` uncommented. `backend/app/config.py:53` also defaults `auth_password = "dumpme"`. |
| I1 | Important | **confirmed** | `model_service.py:157` returns `travel_time_min` = the travel time of **one** segment; the public card labels it "Journey time" (`PublicDashboard.jsx:474-481`). |
| I2 | Important | **confirmed** | `alternatives_service.py:98-105` ranks by *(crowd level, waiting time, occupancy)*. `AlternativeRoute` (`schemas.py:337-353`) has no total-time field at all, and the frontend shows "wait" and "ride" separately (`PublicDashboard.jsx:675-677`) with no comparison against the chosen route. |
| I3 | Important | **confirmed** | `analytics_service.py:62-66` counts `Place.kind == "stop"`, and `navacity_core/network.py:530-554` marks a place as a "stop" **only** when it is not already a metro station. Result: **5** bus stops. The real number of places served by a bus route is **42** (37 of which are also metro stations). The README counts "46 stations and stops". |
| I4 | Important | **confirmed** | The authority demand chart draws a purple dashed `total` line (`AuthorityDashboard.jsx:234-242`) with `name="total"`; Recharts renders it in the legend, but the series is not named in human terms anywhere and several charts have no axis units. |
| I5 | Important | **confirmed** | `TransitMap.jsx:116-136` draws a `<circle>` with a `<title>` (a tooltip) but **no visible station labels**. |
| I6 | Important | **confirmed** | `ModeComparison` (`schemas.py:270-277`) and the "Bus vs metro" card compare `total_passengers` and `mean_passengers` — absolute passengers per segment-hour — even though a metro vehicle seats 320 and a bus 48. |
| I7 | Important | **confirmed** | The wait formula is `headway × MODE_WAIT_PER_HEADWAY[mode]` plus a `+1.2` min penalty above 85 % occupancy and a `+0.8` min penalty for heavy/severe bus traffic (`model_service.py:149-154`). It is **not documented in the README** and has **no test**. 60/14 × 0.45 = 1.93 min for metro, 60/14 × 0.50 = 2.14 min for bus. |
| I8 | Important | **confirmed** | README lines 399-404: `expires_at: 1750000060` and `session.issued_at: 1750000060` are identical, while `expires_in` is 3600. |
| I9 | Important | **confirmed** | `PublicDashboard.jsx:506-508` renders `prediction.model_name` ("gradient_boosting") in the public view. |
| I10 | Important | **confirmed** | The CSV contains only months 2025-01 … 2025-06. `month_sin`/`month_cos` are model features (`features.py:40-55`) and are **not** documented as out-of-range for months 7-12. |
| O1 | Optional | **confirmed** | `formatNumber()` is duplicated in `PublicDashboard.jsx:24-26` and `AuthorityDashboard.jsx:20-22`; both use `Intl.NumberFormat('en-IN')`, which produces Indian lakh grouping but is not a single shared helper. |
| O2 | Optional | **confirmed** | README §8.1 ends at line 509 and is followed by a second `### 7.2 Error handling` (line 510) and a second `## 8. Architecture` (line 522) while `### 9.1`/`### 9.2` follow it. The project tree lists `frontend/src/package.json` (line 76) — the real file is `frontend/package.json`. The tree lists `backend/test_api.py` (line 66) but the pytest suite lives in `backend/tests/test_api.py` (both exist; `backend/test_api.py` is a manual smoke script). |
| O3 | Optional | **confirmed** | The public page mixes controls, KPI cards, two charts, a map and a long crowd-level explainer in one flat column of `card` elements. |

### 3.1 Items that are *not* reproduced exactly as worded

* **C5 (partly)** — the selected route is not deliberately painted in the bus colour; the
  *crowd* colour is applied to whichever line is selected (`TransitMap.jsx:95`). The
  underlying defect is real — the map mixes three colour systems (per-line metro
  colours, a single bus amber and the crowd palette) and the legend does not describe
  what is on screen. Treated as **confirmed** and fixed with a single colour system.
* **I3** — the issue text says "The network has 18 bus routes and 132 segments, so this
  is almost certainly a counting error." Correct: the "5" is a genuine *kind* count
  (bus-only stops). The defect is that the label "Bus stops" implies the number of
  places a bus can stop at, which is **42**. The fix is to report the bus-served places
  (42) and label it correctly, while keeping the metro-station count (41) separate.

## 4. Baseline conclusion

* The **code is healthy**: 112 unit/API tests, 61 setup checks, the live API script and
  the 13 frontend wiring checks all pass.
* All 23 reported items were **traced to a concrete file and line**; none of them is a
  regression, all of them are gaps in behaviour, labelling, documentation or layout that
  the existing suite never asserted.
* No security defect was found: the authority endpoints already answer **401** without a
  token (`frontend_check.py` asserts it), the demo password is never echoed by any
  endpoint, and the token is held in memory only.
