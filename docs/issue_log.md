# NavaCity — Issue log

Every issue from the review, with the status that the **code** gave it (not
the screenshot), the file and line where it was found, the root cause and the
fix. The measurements behind the statuses are in
[`docs/baseline_report.md`](baseline_report.md).

Legend: **confirmed** = reproduced in the code; **partly true** = the symptom
was real but the stated cause was different.

---

## Critical

### C1 — The origin and the destination were ignored

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:134-139` (old),
  `backend/app/schemas.py` (`PredictionRequest`), `backend/app/services/model_service.py:144,238-250`
* **Root cause:** the frontend sent only `{route_id, hour, date, mode}`.
  `PredictionRequest` had no `origin_id`/`destination_id`, and
  `_resolve_segment()` fell back to the segment with the **highest
  `segment_index`** — the busiest stretch of the line, regardless of the
  journey. The alternatives panel built its title from
  `alternatives.origin`/`alternatives.destination` while every row showed the
  *candidate's* busiest stretch, so the title and the rows could disagree.
* **Fix:**
  * `navacity_core/network.py`: new `segment_between()`, `route_path_segments()`
    and `journey_ride_minutes()` resolve an (origin, destination) pair into the
    stretch of the journey that carries the peak demand.
  * `model_service.predict()` accepts `origin_id`/`destination_id`, resolves
    the journey, forecasts on that stretch and reports the ride time of the
    **whole** journey (`travel_time_min`), the single-stretch time
    (`segment_travel_time_min`) and the total (`total_journey_time_min`).
  * `POST /api/predict`, `GET /api/predict` and `GET /api/predict/day` accept
    the journey; the response carries a `journey` object.
  * The alternatives are now computed **for the same journey**, so the title
    always describes the query that was executed.
  * The public interface shows the two station names instead of a segment id.
* **Tests:** `backend/tests/test_journey.py` — 6 new tests.

### C2 — The default date was outside the training window

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:32-36,47` (old),
  `navacity_core/features.py:100-115`
* **Root cause:** the default was `tomorrowISO()` (2026-10-22) and the date
  picker had no `min`/`max`. The `day_index` feature is clipped to the
  simulated period, but `month_sin`/`month_cos` still encoded month 10, which
  never occurred in the training data.
* **Fix:**
  * The date picker is limited to `2025-01-01 … 2025-06-30` and the default is
    a typical weekday inside that window (`2025-06-30`, a Monday).
  * A "Typical weekday" button sets it back in one click.
  * The backend reports `is_extrapolation`, `extrapolation_notice` and
    `supported_date_range` with every forecast, and the forecast card shows a
    visible warning for a date outside the range.
  * The README (§6.8) documents what the model can and cannot extrapolate.
* **Tests:** `backend/tests/test_journey.py` — 4 new tests.

### C3 — The data documentation contradicted itself

* **Status:** confirmed
* **Files:** `README.md` §5, `backend/app/services/analytics_service.py:558`
  (old), `backend/app/database.py:7`
* **Root cause:** the README said "4 observations per segment per day" (true)
  while the authority dashboard said "95,568 simulated **hourly** observations"
  (the same 95,568 rows, but the wrong granularity — they are *samples*, not a
  complete hourly series).
* **Fix:**
  * The canonical description is now: **95,568 simulated observations, 4 per
    route-stretch per day** (hourly samples, not a complete hourly series).
  * The README gained a dedicated §5.0 that spells the granularity out.
  * The KPI text says "Sum over N simulated observations (4 per route-stretch
    per day)".
  * Every chart caption states the data period *and* the granularity.
  * `database.py` no longer calls the table "hourly demand observations".
* **Tests:** `verify_setup.py` — 3 new checks.

### C4 — The two charts disagreed

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:518-597` (old)
* **Root cause:** the left chart plotted `predicted_passengers` (an absolute
  number for the busiest stretch) and the right chart plotted
  `mean_occupancy_pct` (a percentage of capacity, averaged over the whole
  simulated period). Different units, different scopes, no axis units.
* **Fix:** the public interface now has **one** 24-hour chart, "Expected crowd
  by hour", in passengers per hour for the selected route, day and journey.
  Both axes carry a unit, the chosen hour is marked with a vertical line, the
  bar colour is the crowd level and the legend names the four levels. The
  second, mismatched chart was removed. The authority charts also carry axis
  units and captions.

### C5 — The map highlighted the wrong route

* **Status:** partly true (see the baseline report)
* **Files:** `frontend/src/components/TransitMap.jsx:92-113,139-152` (old)
* **Root cause:** the map mixed **three** colour systems: a per-line colour
  for every metro line, a single amber for every bus route, and the *crowd*
  palette, which was applied to the selected line. The legend described
  neither the per-line metro colours nor the crowd colours.
* **Fix:** one colour system for the whole application.
  * Metro lines are **solid indigo**, bus routes are **dashed amber**, the
    selected route is drawn thicker and every other route is dimmed.
  * The crowd palette is never used on the map, so a crowd colour can never be
    mistaken for a route colour.
  * The legend describes exactly what is on screen, and the same colours are
    used by the mode switch, the route tables and the charts.

### C6 — The public page showed the authority session

* **Status:** confirmed
* **Files:** `frontend/src/App.jsx:73-115` (old)
* **Root cause:** the "Authority signed in" badge and the "Sign out" button
  were rendered in the **global** header, which the public page shares.
* **Fix:** the global header now shows only the product name, a "Simulated
  data" pill, the navigation and the API status. The session state and the
  sign-out button moved into the authority area
  (`frontend/src/pages/AuthorityDashboard.jsx`), which is the only place that
  can be reached with a valid session.

### C7 — `.env` was not ignored and the demo password was shipped

* **Status:** confirmed
* **Files:** `.gitignore`, `.env.example:15` (old)
* **Root cause:** `.gitignore` had no `.env` entry, and `.env.example` shipped
  an active `NAVACITY_AUTH_PASSWORD=dumpme` line.
* **Fix:**
  * `.gitignore` now lists `.env`, `.env.*` and `!.env.example`.
  * The demo password line in `.env.example` is **commented out** and marked
    as a local-only default.
  * `verify_setup.py` asserts all three facts, so the mistake cannot come back.
  * The **behaviour** of the password is unchanged: the local demo password
    `dumpme` still works in the `local` environment, it is still never
    returned by any endpoint, and it is still refused in `production`.

---

## Important

### I1 — "Journey time" was one stretch

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:474-481` (old),
  `backend/app/services/model_service.py:157`
* **Root cause:** `travel_time_min` is the travel time of **one** segment, but
  the card called it "Journey time".
* **Fix:** the forecast now reports three separate numbers: the **wait**, the
  **ride time of the whole journey** (`travel_time_min`, the sum of every
  stretch of the journey) and the **total journey time**
  (`total_journey_time_min`). The single-stretch time stays available as
  `segment_travel_time_min`. The card shows wait / ride / total.

### I2 — The alternatives were not compared by journey time

* **Status:** confirmed
* **Files:** `backend/app/services/alternatives_service.py:98-105` (old),
  `backend/app/schemas.py:337-353` (old)
* **Root cause:** the candidates were ranked by *(crowd level, waiting time,
  occupancy)*. `AlternativeRoute` had no total-time field at all, so a
  passenger could not see whether an alternative was actually faster.
* **Fix:**
  * `AlternativeRoute` gained `total_journey_time_min`; the response gained
    `requested_total_journey_time_min` and `requested_crowd_level`.
  * A one-transfer alternative is now built from **both legs** (the wait and
    the ride of each leg) plus a transfer penalty of 4 minutes
    (`TRANSFER_PENALTY_MIN`).
  * The ranking is *same mode first, then by the total journey time, then by
    the crowd level*.
  * The public panel states the total of the chosen route and shows, for every
    alternative, "N min faster/slower than your route".

### I3 — "5 bus stops" was a counting error

* **Status:** confirmed (the label was wrong, not the query)
* **Files:** `backend/app/services/analytics_service.py:62-66` (old),
  `navacity_core/network.py:530-554`
* **Root cause:** `count_places(kind="stop")` counted the places that are
  **not** metro stations — only 5 of them. A bus also stops at 37 metro
  stations, so the number of places a bus can stop at is **42**.
* **Fix:** `count_bus_served_places()` (every place with a bus route) and
  `count_metro_served_places()` (every place with a metro line) replace the
  kind-based count. The KPIs now report **42 bus stops** and **41 metro
  stations**, each with a label that says what it counts.

### I4 — Charts had unlabelled series

* **Status:** confirmed
* **Files:** `frontend/src/pages/AuthorityDashboard.jsx:200-244` (old)
* **Root cause:** the purple dashed "total" line had no human name, and
  several charts had no axis unit and no data-period note.
* **Fix:** every chart is now wrapped in `ChartCard`, which renders a title,
  a subtitle, a **visible legend** (`LegendItem`), the axis titles with their
  units inside the plot, and a **caption** with the data period and the
  granularity. The three series of the demand chart are named "Metro",
  "Bus" and "All modes".

### I5 — The map had no station labels

* **Status:** confirmed
* **Files:** `frontend/src/components/TransitMap.jsx:116-136` (old)
* **Root cause:** the stations were drawn as circles with an SVG `<title>`
  (a tooltip) and nothing else.
* **Fix:** the station name is now drawn as a visible SVG label for the
  stations of the selected route, for the interchanges and for the place under
  the pointer. The `<title>` tooltip is kept.

### I6 — The bus/metro comparison used incomparable numbers

* **Status:** confirmed
* **Files:** `backend/app/schemas.py:270-277` (old),
  `backend/app/services/analytics_service.py:263-291` (old)
* **Root cause:** the comparison showed the absolute passengers per
  segment-hour, although a metro vehicle seats 320 and a bus 48.
* **Fix:** `ModeComparison` gained the comparable figures:
  `mean_occupancy_pct`, `overcrowded_share_pct`, `passengers_per_vehicle`,
  `mean_vehicles_per_hour` and `share_of_records_pct`. The Overview shows the
  occupancy and the passengers per vehicle as the **primary** numbers and
  keeps the absolute totals as clearly-labelled secondary information.

### I7 — The waiting-time formula was undocumented and untested

* **Status:** confirmed
* **Files:** `backend/app/services/model_service.py:149-154` (old),
  `navacity_core/network.py:464`
* **Root cause:** the formula existed only in the code:
  `headway × 0.45` (metro) / `× 0.50` (bus), plus `+1.2` min above 85 %
  occupancy and `+0.8` min for a bus in heavy traffic.
* **Fix:** the formula was moved into a named, documented function
  (`expected_wait_minutes`), documented in the README (§6.7) and covered by
  three tests that check the value at 14 vehicles per hour (1.9 min for a
  metro, 2.1 min for a bus) and both penalties.

### I8 — The README login example had `issued_at == expires_at`

* **Status:** confirmed
* **Files:** `README.md:399-404` (old)
* **Root cause:** the example showed `expires_at: 1750000060` and
  `session.issued_at: 1750000060` while `expires_in` was 3600.
* **Fix:** `expires_at` is now `1750003660` (= `issued_at + 3600`), and the
  README explains that the session lasts
  `NAVACITY_AUTH_SESSION_MINUTES` minutes (60 by default).

### I9 — The public page showed the model name

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:506-508` (old)
* **Root cause:** the "Service" card of the public forecast rendered
  `prediction.model_name` ("gradient_boosting").
* **Fix:** the public page no longer shows the model name, the raw metrics or
  any other internal jargon. The model name stays on the authority
  Model & Data tab, where it belongs.

### I10 — The month features were not covered for months 7–12

* **Status:** confirmed
* **Files:** `navacity_core/features.py:40-55,100-115`,
  `navacity_core/config.py`
* **Root cause:** `month_sin`/`month_cos` are model features, but the
  simulated data only covers January to June, and nothing said so.
* **Fix:**
  * `navacity_core/config.py` gained `OBSERVED_MONTHS`,
    `is_within_simulated_window()` and `is_within_observed_months()`, derived
    from the simulated window so they can never drift apart.
  * The backend reports the extrapolation and the observed months with every
    forecast.
  * The README (§6.8) documents the limitation.
  * The model was **not** retrained: the tests did not show a data bug, only a
    documentation and labelling gap.

---

## Optional

### O1 — One number format everywhere

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx:24-26` and
  `frontend/src/pages/AuthorityDashboard.jsx:20-22` (old)
* **Root cause:** `formatNumber()` was duplicated in two files.
* **Fix:** a single helper, `frontend/src/lib/format.js`, now formats every
  number in the application with **Indian grouping** (`6,48,66,540`,
  `2,408`). It also provides `formatDecimal`, `formatPercent`, `formatHour`
  and `formatMinutes`.

### O2 — The README had broken numbering and wrong paths

* **Status:** confirmed
* **Files:** `README.md`
* **Root cause:**
  * a second `### 7.2 Error handling` after the API reference, and a second
    `## 8. Architecture` while `### 9.1`/`### 9.2` followed it,
  * the project tree listed `frontend/src/package.json` instead of
    `frontend/package.json`,
  * the tree listed `backend/test_api.py` without saying that the pytest suite
    lives in `backend/tests/`.
* **Fix:** the error-handling section is now `### 8.2`, the architecture
  section is `## 9`, the tree is correct and complete (it now also lists the
  new test file, the design tokens and the shared components), and the two
  kinds of test file are labelled separately.

### O3 — The public page was cluttered

* **Status:** confirmed
* **Files:** `frontend/src/pages/PublicDashboard.jsx` (old)
* **Root cause:** controls, four result cards, two charts, a map and a long
  explainer were all in one flat column of equal weight.
* **Fix:** the public page was rebuilt around the passenger's question, in the
  order asked for: the **answer card first** (above the controls once a
  result exists), then a compact summary bar that expands into the controls,
  then the alternatives, the 24-hour chart, the map in a collapsible section
  and the crowd-level explainer in another collapsible section.

---

## Summary

| Severity | Count | Confirmed | Partly true | Not reproduced |
|---|---|---|---|---|
| Critical | 7 | 6 | 1 (C5) | 0 |
| Important | 10 | 10 | 0 | 0 |
| Optional | 3 | 3 | 0 | 0 |
| **Total** | **20** | **19** | **1** | **0** |

No issue was "not reproduced": every reported symptom was traced to a
concrete line of code. The one *partly true* item (C5) had a different cause
than described, but the defect was real and was fixed.

**New tests added:** 18 in `backend/tests/test_journey.py`, plus 9 new checks
in `verify_setup.py` and 11 new module checks in `frontend_check.py`.
