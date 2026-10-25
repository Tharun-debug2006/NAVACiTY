# NavaCity Smart City — AI-Based Public Transport Demand & Overcrowding Prediction

> **All data in this project is SIMULATED.**
> NavaCity is a **fictional city**. Every route, station, passenger count, crowd level
> and forecast produced here comes from a rule-based simulator and a scikit-learn model
> trained on that simulated data. **Nothing in this repository describes a real city,
> operator, passenger survey or real-world validation.** The reported metrics are genuine
> measurements of the models *on the simulated data* — they say nothing about how such a
> system would perform on real data.

A complete smart-city transport platform with two dashboards:

| Interface | Purpose |
|---|---|
| **Public dashboard** | Check the expected crowd level of a bus or metro line, see the predicted passenger demand, the waiting time, the crowd level by hour, and less crowded alternative routes. |
| **Transport authority dashboard** | Monitor demand forecasts, spot overcrowded routes and stations, compare bus vs metro demand, review peak-hour and route analytics, and review suggested service-frequency adjustments. |

---

## 1. Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3, Recharts 2, React Router 6, Axios |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2 |
| Database | SQLite (file at `data/navacity.db`) |
| Machine learning | pandas, NumPy, scikit-learn (Random Forest + Histogram Gradient Boosting), joblib, matplotlib |
| Dataset generation | Python (custom rule-based simulator in `navacity_core/simulator.py`) |

Everything is free and open source. **No paid API, no cloud service, no API key and no
external AI service is required.** The transit map is drawn as plain SVG from
coordinates stored in the project — there is no map-tile provider to sign up for.

---

## 2. Project structure

```
c:\AI\NavaCity
├── navacity_core/            # Shared core: used by the ML pipeline AND the backend
│   ├── config.py             #   paths, crowd thresholds, hour-of-day profiles
│   ├── network.py            #   the fictional NavaCity network (lines, stops, coords)
│   ├── events.py             #   simulated holidays and special events
│   ├── simulator.py          #   the rule-based demand simulator
│   └── features.py           #   feature engineering (single source of truth)
│
├── ml/                       # Machine learning pipeline
│   ├── generate_dataset.py   #   step 1: build the synthetic dataset
│   ├── train_model.py        #   step 2: train + evaluate + save artifacts
│   ├── requirements.txt
│   └── artifacts/            #   model_bundle.joblib, metrics.json, *.png
│
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           #   application factory, lifespan, CORS, startup checks
│   │   ├── api.py            #   every HTTP endpoint
│   │   ├── auth.py           #   authority authentication (sessions, dependencies)
│   │   ├── security.py       #   password hashing and session-token signing
│   │   ├── schemas.py        #   Pydantic request/response models
│   │   ├── database.py       #   SQLAlchemy models (places, routes, records)
│   │   ├── config.py         #   settings (all optional env vars)
│   │   └── services/         #   model_service, analytics_service, alternatives_service
│   ├── tests/                #   pytest suite
│   │   ├── conftest.py       #   fixtures (temporary database, authority token)
│   │   ├── test_api.py       #   the public endpoints
│   │   ├── test_auth.py      #   the authority protection
│   │   ├── test_network.py   #   the simulated network
│   │   ├── test_prediction.py#   the prediction pipeline
│   │   └── test_journey.py   #   journey, date range, alternatives, wait formula
│   ├── seed_database.py      #   step 3: load the dataset into SQLite
│   ├── requirements.txt
│   ├── test_api.py           #   manual smoke test of every endpoint
│   └── test_live_api.py      #   end-to-end check against a running server
│
├── frontend/                 # React application
│   ├── src/
│   │   ├── pages/            #   PublicDashboard, AuthorityDashboard, AuthorityLogin
│   │   ├── components/       #   CrowdBadge, TransitMap, States, AnswerCard, …
│   │   ├── lib/format.js     #   the one number-formatting helper of the app
│   │   ├── styles/tokens.css#   the design tokens (single source of truth)
│   │   ├── context/          #   AuthContext (the authority session)
│   │   ├── api/client.js     #   the single place that talks to the backend
│   │   ├── App.jsx
│   │   └── vite.config.js    #   proxies /api -> http://127.0.0.1:8000
│   ├── package.json
│   ├── tailwind.config.js    #   the Tailwind colours that mirror the tokens
│   └── index.html
│
├── data/
│   ├── generated/            #   navacity_transport.csv, navacity_network.json
│   └── navacity.db           #   SQLite database (created by the seeder)
│
└── README.md
```

---

## 3. Setup on Windows (exact commands)

### 3.1 Prerequisites

* **Python 3.12** — check with `python --version`
* **Node.js 20+** and **npm** — check with `node --version` and `npm --version`

### 3.2 Open the project

```powershell
cd c:\AI\NavaCity
```

### 3.3 Install the Python dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

> If PowerShell blocks the activation script, run once:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### 3.4 Install the frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 3.5 Generate the dataset, train the model, seed the database

Run these three commands **in this order** (each depends on the previous one):

```powershell
python ml\generate_dataset.py
python ml\train_model.py
python backend\seed_database.py
```

* `generate_dataset.py` writes `data/generated/navacity_transport.csv` (95,568 rows) and
  `data/generated/navacity_network.json`, and prints a quality report.
* `train_model.py` trains the models, prints the evaluation metrics and writes
  `ml/artifacts/model_bundle.joblib`, `ml/artifacts/metrics.json` and the plots.
* `seed_database.py` creates and fills `data/navacity.db`.

### 3.6 Configure the authority password

The transport-authority area is **protected by the backend**. Set a password
before you start the server:

```powershell
# a local demo run (the default) - accepts the password "dumpme"
$env:NAVACITY_ENV = "local"
$env:NAVACITY_AUTH_PASSWORD = "dumpme"

# a real deployment - the server REFUSES to start without a secure password
$env:NAVACITY_ENV = "production"
$env:NAVACITY_AUTH_PASSWORD = "a-strong-unique-password"
```

| Variable | Default | Meaning |
|---|---|---|
| `NAVACITY_ENV` | `local` | `local` allows the well-known demo password; `production` refuses it and refuses to start without a configured password. |
| `NAVACITY_AUTH_PASSWORD` | `dumpme` | The authority password. It is **never stored**: only a PBKDF2-HMAC-SHA256 hash of it is kept in memory, and it is never returned by any endpoint. |
| `NAVACITY_AUTH_PASSWORD_HASH` | *(empty)* | Optional `salt_hex:hash_hex` pair, used instead of the plain password. |
| `NAVACITY_AUTH_SESSION_MINUTES` | `60` | Lifetime of an authority session. |
| `NAVACITY_AUTH_SECRET` | *(random)* | The HMAC secret used to sign the session tokens. A random one is generated when this is empty, so restarting the server invalidates every session. |

See [section 7](#7-authority-authentication) for the details.

### 3.7 Start the backend (terminal 1)

```powershell
cd c:\AI\NavaCity
python -m uvicorn backend.app.main:app --reload --port 8000
```

* API: <http://localhost:8000>
* **Swagger UI: <http://localhost:8000/docs>**
* ReDoc: <http://localhost:8000/redoc>
* Health check: <http://localhost:8000/api/health>

### 3.8 Start the frontend (terminal 2)

```powershell
cd c:\AI\NavaCity\frontend
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the backend, so
there is no CORS configuration to change.

---

## 4. Running the tests

```powershell
# Unit + API test suite (uses a temporary SQLite database, never touches data/navacity.db)
python -m pytest backend\tests -q

# End-to-end check against a running backend (start the backend first)
python backend\test_live_api.py

# Frontend wiring check (start the frontend dev server first)
python frontend_check.py
```

---

## 5. The dataset

`python ml\generate_dataset.py` produces **95,568 observations** over 181 days
(2025-01-01 → 2025-06-30) for 24 routes (6 metro lines + 18 bus routes),
46 stations/stops and 132 route segments.
The generation is **fully deterministic**: the same seed always produces a
byte-identical CSV, so the model metrics are reproducible.

### 5.0 The granularity of the data (read this before quoting a number)

The dataset contains **95,568 simulated observations**, and every one of them
belongs to one (route, stretch, hour) triple. The important detail is how many
observations there are per stretch and per day:

> **4 observations per route-stretch per day.**
> They are *hourly samples*, not a complete hourly time series: the two
> commuter peaks (08:00 and 18:00) are always present, plus two other hours
> that are drawn from the day. Over the 181 simulated days the 24 hours of the
> day are all represented, but **no single day has a complete 24-hour series**
> for a stretch.

This is why the charts are labelled "mean … per route-stretch-hour" and never
"passengers per hour on a real day": an hourly chart interpolates between the
four sampled hours of a day, and the mean of a stretch-hour is an average over
181 days of four samples each.

### 5.1 Columns

| Column | Type | Meaning |
|---|---|---|
| `timestamp` | string | ISO timestamp of the observation |
| `date`, `hour`, `day_of_week`, `day_name` | int / string | Calendar context |
| `is_weekend`, `is_holiday`, `holiday_name`, `day_type` | bool / string | Calendar flags (`holiday_name` is `"Not a holiday"` on a working day) |
| `mode` | string | `metro` or `bus` |
| `route_id`, `route_name`, `segment_id` | string | Which line / route / segment |
| `origin_id`, `origin_name`, `dest_id`, `dest_name` | string | The two ends of the segment |
| **`passenger_count`** | int | **The prediction target** |
| `vehicle_capacity` | int | Seats in one vehicle (metro 320, bus 48) |
| `service_frequency` | int | Vehicles per hour in that hour's timetable |
| `hourly_capacity` | int | `vehicle_capacity × service_frequency` |
| `occupancy_pct` | float | `passenger_count / hourly_capacity × 100` |
| `crowd_level` | string | Low / Moderate / High / Critical |
| `weather` | string | clear, cloudy, light_rain, heavy_rain, fog |
| `traffic_level` | string | light, moderate, heavy, severe |
| `special_event` | bool | A simulated event affects this route/hour |
| `waiting_time_min` | float | Expected wait for the next vehicle |
| `travel_time_min` | float | Segment travel time incl. the traffic effect |
| `is_overcrowded` | bool | Occupancy ≥ 80 % |

### 5.2 The patterns that were built into the simulator

* **Peak hours** — a clear morning peak (08:00) and a stronger evening peak (18:00),
  with a secondary lunch bump around 13:00.
* **Weekends** — flatter profile, lower morning peak, more midday and evening leisure
  travel.
* **Holidays** — about 28 % less demand than a normal working day.
* **Route popularity** — each route has a fixed relative weight (e.g. the Red Line
  1.12, the Lake View Nightline 0.55).
* **Segment taper** — central segments of a line carry more passengers than the outer
  ones (a sine-shaped taper).
* **Weather** — rain pushes people out of private cars onto public transport
  (+6 % to +12 % occupancy); fog suppresses trips and slows traffic.
* **Traffic** — congestion peaks in the rush hours, worsens towards the end of the
  simulated period, and lengthens bus journey times.
* **Special events** — 7 invented events (a derby final, a music festival, a tech
  expo, a marathon …) that boost the demand of the affected stations and lines by
  30–55 % during their time window. In the generated data, event rows average
  **74.8 % occupancy vs 45.2 % for normal rows**.
* **Seasonal growth** — the network grows slowly (about 0.055 %/day) over the six
  simulated months.

### 5.3 Leakage policy

`navacity_core/features.py` is the single source of truth for the model's input
format, and it explicitly **excludes** the target and everything derived from it:

```
passenger_count, occupancy_pct, crowd_level, is_overcrowded,
waiting_time_min, travel_time_min
```

Only information that is known *before* the trip happens is used as a model input:
the timetable, the calendar, the weather forecast and the traffic forecast.
`train_model.py` asserts at start-up that the feature matrix and the leaky-column
list do not overlap, and the test suite asserts the same.

---

## 6. The model

### 6.1 Features (14 numeric + 9 categorical)

**Numeric:** `hour`, `day_of_week`, `month_sin`, `month_cos`, `day_index`,
`is_weekend`, `is_holiday`, `is_peak_hour`, `vehicle_capacity`, `service_frequency`,
`hourly_capacity`, `segment_index`, `num_stops`, `route_popularity`

**Categorical:** `mode`, `route_id`, `segment_id`, `origin_id`, `dest_id`, `day_type`,
`weather`, `traffic_level`, `special_event`

The month is encoded cyclically (sin/cos) so that December and January are adjacent
instead of at opposite ends of a numeric range, and the `day_index` is **clipped to
the simulated window** so a forecast for a date far in the future cannot extrapolate
a growth trend that was never observed.

### 6.2 Split strategy

The dataset is split **in time order**: the last 20 % of the *dates* (2025-05-25 →
2025-06-30) form the test set, everything before forms the training set. No
training row is later than a test row, so the evaluation reflects a real forecasting
situation rather than an interpolation task. For reference, the script also reports a
random-split result in `ml/artifacts/metrics.json`.

### 6.3 Models

Two scikit-learn baselines are trained **per transport mode** (metro and bus have
very different demand scales, so one global model would be dominated by the metro
rows):

* `RandomForestRegressor` (220 trees, max depth 18)
* `HistGradientBoostingRegressor` (400 iterations, learning rate 0.08)

Both are wrapped in a `Pipeline` with a `ColumnTransformer` (one-hot encoding with
`min_frequency=2` for the categorical columns). The model with the lower RMSE wins
per mode and is the one that is saved and served.

### 6.4 Measured results

These are the numbers produced by `python ml\train_model.py` on the **simulated**
data, using the time-ordered split:

| Mode | Best model | MAE | RMSE | R² | Test rows |
|---|---|---|---|---|---|
| Metro | `gradient_boosting` | 236.26 | 375.60 | 0.9379 | 6,068 |
| Bus | `gradient_boosting` | 17.30 | 28.86 | 0.9537 | 7,992 |

> **Reminder:** these are measurements on synthetic data generated by the same
> simulator that produced the training set. A high R² here means *the model learned
> the simulator's rules well* — it is **not** evidence of real-world accuracy, and it
> must not be presented as such.

### 6.5 Artefacts written by `train_model.py`

| File | Content |
|---|---|
| `ml/artifacts/model_bundle.joblib` | Both trained pipelines + the feature list + the crowd thresholds (loaded by the backend) |
| `ml/artifacts/metrics.json` | Every metric, the split description, the excluded leaky columns and the feature importances |
| `ml/artifacts/actual_vs_predicted_metro.png` | Actual vs predicted scatter with the identity line |
| `ml/artifacts/actual_vs_predicted_bus.png` | Same for the bus model |
| `ml/artifacts/residuals_metro.png` / `_bus.png` | Residual histogram and residuals over the test set |
| `ml/artifacts/feature_importance.png` | Aggregated feature importance across both modes |
| `ml/artifacts/forecast_vs_history.png` | Model forecast vs simulated history, by hour of day |

Feature importance is the model's own `feature_importances_` for the Random Forest
and a **permutation importance** for the gradient boosting model (which does not
expose one). Both are summed back onto the original feature columns.

### 6.6 Crowd level thresholds and the assumptions behind them

Occupancy is defined as **the share of the hourly capacity offered by the planned
service**: `passengers / (vehicle_capacity × service_frequency)`.

| Level | Occupancy | Rationale |
|---|---|---|
| **Low** | 0 – 40 % | Plenty of room; passengers rarely wait for a second vehicle. |
| **Moderate** | 40 – 65 % | Comfortable; a few passengers may wait for the next service. |
| **High** | 65 – 85 % | Crowded; boarding is slow and queues form. |
| **Critical** | 85 % + | Overcrowded; passengers are left behind or denied boarding. |

The 85 % cut-off is the point at which a standing passenger has roughly 0.85 m² of
space in a crush-loaded vehicle — the level at which operators normally describe a
service as "overcrowded". The **overcrowding alert threshold is 80 %**, slightly
below the Critical level, so that a planner is warned before the situation becomes
critical. The same values are exposed by `GET /api/crowd-levels` and used by the
frontend, so there is a single definition everywhere.

### 6.7 The expected waiting time

The expected wait for the next vehicle is **not** a measured value: it is a
simple, documented formula that the backend applies to the planned timetable
(`backend/app/services/model_service.py::expected_wait_minutes`):

```
headway = 60 / vehicles_per_hour          (minutes)

wait = headway x MODE_WAIT_PER_HEADWAY[mode]

MODE_WAIT_PER_HEADWAY = { "metro": 0.45, "bus": 0.50 }
```

Two penalties are added on top of it:

| Condition | Extra wait | Why |
|---|---|---|
| occupancy above 85 % | **+1.2 min** | boarding is slow and a queue forms |
| a **bus** in heavy or severe traffic | **+0.8 min** | the vehicle is late and the queue is longer |

With **14 vehicles per hour** (a headway of 4.29 min) this gives:

* **metro:** 4.29 × 0.45 = **1.9 min**
* **bus:** 4.29 × 0.50 = **2.1 min**

The simple "half the headway" estimate would give 2.1 min for both; the metro
factor of 0.45 reflects that a metro has a more reliable timetable and a
shorter boarding time. The formula is covered by
`backend/tests/test_journey.py::test_the_waiting_time_formula` and
`::test_the_waiting_time_penalties`.

### 6.8 What the model can and cannot extrapolate

The model was trained on the simulated period **2025-01-01 → 2025-06-30**.

* The **day index** feature is clipped to the length of the simulated period,
  so the model cannot extrapolate a growth trend it never observed.
* The **month** features (`month_sin`, `month_cos`) are cyclical. The simulated
  data only covers **January to June**, so a forecast for a month in
  **July to December** is an extrapolation of a seasonal pattern that was never
  observed.

The backend therefore answers every forecast with

```json
"is_extrapolation": true,
"extrapolation_notice": "… is outside the simulated period …",
"supported_date_range": { "start": "2025-01-01", "end": "2025-06-30", "observed_months": [1,2,3,4,5,6] }
```

and the public dashboard limits the date picker to the supported range and
shows a visible warning on the forecast card when a date outside it is used.

---

## 7. Authority authentication

The transport-authority area is protected **by the FastAPI backend**, not by
the React app. A request without a valid session token is answered with
`401 Unauthorized` no matter which client sends it — a browser, `curl` or a
script.

### 7.1 What is protected

| Method | Endpoint | Public? |
|---|---|---|
| `GET` | `/api/health` | public |
| `GET` | `/api/network`, `/api/routes`, `/api/places`, `/api/events`, `/api/crowd-levels` | public |
| `GET` | `/api/history`, `/api/history/hourly` | public |
| `POST` `GET` | `/api/predict`, `/api/predict/day` | public |
| `GET` | `/api/alternatives` | public |
| `GET` | `/api/auth/config` | public (describes the setup, no secrets) |
| `POST` | `/api/auth/login` | public (the sign-in itself) |
| `POST` | `/api/auth/logout` | **authority** |
| `GET` | `/api/auth/session` | **authority** |
| `GET` | `/api/authority/stats` | **authority** |
| `GET` | `/api/authority/recommendations` | **authority** |
| `GET` | `/api/crowd-summary` | **authority** |
| `GET` | `/api/alerts` | **authority** |
| `GET` | `/api/model/metrics` | **authority** |

### 7.2 The sign-in flow

```powershell
# 1. sign in -> a session token
curl -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"password\": \"dumpme\"}"
```

```json
{
  "access_token": "eyJzaWQiOi...In0.s0m3s1gn4tur3",
  "token_type": "bearer",
  "expires_at": 1750003660,
  "expires_in": 3600,
  "session": {
    "role": "authority",
    "issued_at": 1750000060,
    "expires_at": 1750003660,
    "session_id": "n3Kc0P0d..."
  },
  "demo_mode": true,
  "message": "Signed in to the transport-authority dashboard. ..."
}
```

The session lasts `NAVACITY_AUTH_SESSION_MINUTES` minutes (60 by default), so
`expires_at` is always `issued_at + 3600` in this example.

```powershell
# 2. use the token
curl http://localhost:8000/api/authority/stats -H "Authorization: Bearer <token>"

# 3. sign out -> the token is rejected from now on
curl -X POST http://localhost:8000/api/auth/logout -H "Authorization: Bearer <token>"
```

### 7.3 How it works

* **The password is never stored.** Only a salted PBKDF2-HMAC-SHA256 hash of
  it is kept in memory, and the comparison uses `hmac.compare_digest`, so it
  is not vulnerable to a timing side channel. The project deliberately uses
  the Python standard library only — no `bcrypt`/`passlib` dependency.
* **The session token is signed.** It is
  `base64url(payload).base64url(HMAC-SHA256(payload))`, so a tampered token
  is rejected before the payload is even read.
* **The server keeps a session registry.** A token is only accepted while its
  session is alive, so a sign-out (or a restart of the server, when the
  signing secret is regenerated) invalidates it immediately instead of waiting
  for the expiry.
* **The browser keeps nothing.** The React app holds the token in a module
  variable — it is never written to `localStorage` or `sessionStorage`. The
  operator has to sign in again after a page reload.
* **Production refuses to start insecurely.** With `NAVACITY_ENV=production`
  the server raises an error and exits when no password is configured or when
  the configured password is the demo password `dumpme`.
* **No public response ever contains a password.** `GET /api/auth/config` is
  deliberately unauthenticated (the sign-in screen needs it before a token
  exists), so it reports only *whether* the server runs in demo mode. It never
  echoes the configured password back — neither in the `notice` text nor in the
  `error` text — and the login screen says "the well-known local demo password"
  instead of printing it. A regression test enforces this.

---

## 8. API reference

All endpoints are under `/api`. The interactive documentation is at
<http://localhost:8000/docs>.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Status of the API, database, dataset and model |
| `GET` | `/api/network` | The complete network: metro lines, bus routes, all places with map coordinates |
| `GET` | `/api/routes?mode=metro\|bus` | List of routes, optionally filtered by mode |
| `GET` | `/api/places?mode=&kind=station\|stop` | Stations and stops, optionally filtered |
| `GET` | `/api/events` | The simulated special events |
| `GET` | `/api/crowd-levels` | The crowd thresholds and the assumptions behind them |
| `GET` | `/api/history?route_id=&mode=&date=&hour=&limit=` | The simulated historical records |
| `GET` | `/api/history/hourly?route_id=&mode=&date=` | Mean simulated demand per hour of the day |
| `POST` | `/api/predict` | **Demand forecast** for a route, day and hour (JSON body) |
| `GET` | `/api/predict?route_id=&hour=&date=&segment_id=` | Same, with query parameters |
| `GET` | `/api/predict/day?route_id=&date=` | All 24 hourly forecasts of a route |
| `GET` | `/api/alternatives?route_id=&origin_id=&destination_id=&hour=` | **Less crowded alternative routes** |
| `GET` | `/api/auth/config` | The authentication setup (environment, demo mode, session length) |
| `POST` | `/api/auth/login` | Exchange the authority password for a session token |
| `POST` | `/api/auth/logout` | Invalidate the current session immediately |
| `GET` | `/api/auth/session` | The identity of the current session |
| `GET` | `/api/authority/stats` | **All authority dashboard statistics** (authority) |
| `GET` | `/api/authority/recommendations?limit=` | Suggested service-frequency changes (authority) |
| `GET` | `/api/crowd-summary?mode=&route_id=` | Distribution of the crowd levels (authority) |
| `GET` | `/api/alerts?mode=&date=&threshold=&limit=` | **Overcrowding alerts** (authority) |
| `GET` | `/api/model/metrics` | The measured evaluation metrics of the trained models (authority) |

### 8.1 Example — predict the demand

```powershell
curl -X POST http://localhost:8000/api/predict `
  -H "Content-Type: application/json" `
  -d "{\"route_id\": \"M1\", \"hour\": 8, \"date\": \"2025-06-30\"}"
```

```json
{
  "route_id": "M1",
  "route_name": "Blue Line",
  "mode": "metro",
  "segment_id": "M1-S06",
  "origin_name": "Aerodrome Interchange",
  "dest_name": "Whitefield Depot",
  "date": "2025-06-30",
  "hour": 8,
  "predicted_passengers": 2490,
  "predicted_occupancy_pct": 55.58,
  "crowd_level": "Moderate",
  "is_overcrowded": false,
  "service_frequency": 14,
  "vehicle_capacity": 320,
  "hourly_capacity": 4480,
  "waiting_time_min": 1.9,
  "travel_time_min": 5.7,
  "model_name": "gradient_boosting",
  "assumptions": "Forecast assumes the published timetable ...",
  "data_notice": "SIMULATED DATA - NavaCity is a fictional city. ..."
}
```

### 8.2 Error handling

| Situation | Status | Body |
|---|---|---|
| Unknown route id | `404` | `{"detail": "Unknown route 'ZZ9'. Use /api/network to list the available routes."}` |
| Route exists but the mode does not match | `400` | `{"detail": "Route M1 is a metro route, not a bus route."}` |
| Hour outside 0–23, unknown mode in a query | `422` | FastAPI validation detail |
| Unknown origin/destination place id | `404` | `{"detail": "Unknown origin place id: ..."}` |
| The model bundle is missing | `503` | `{"detail": "The demand model is not available. Run 'python ml\\train_model.py' ..."}` |

---

## 9. Architecture

```
                    ┌──────────────────────────┐
  browser  ───────► │  React + Vite (5173)     │
                    │  PublicDashboard         │
                    │  AuthorityDashboard      │
                    └────────────┬─────────────┘
                                 │  fetch('/api/...')  →  Vite dev proxy
                                 ▼
                    ┌──────────────────────────┐
                    │  FastAPI (8000)          │
                    │  api.py  (routers)       │
                    │  schemas.py (pydantic)   │
                    │  services/               │
                    └──────┬────────────┬──────┘
                           │            │
              ┌────────────▼───┐   ┌────▼──────────────────┐
              │ SQLite          │   │ joblib model bundle   │
              │ places/routes/  │   │ (metro + bus          │
              │ records         │   │  pipelines)           │
              └─────────────────┘   └───────────────────────┘
                           ▲            ▲
                           │            │
                    ┌──────┴────────────┴──────┐
                    │  navacity_core            │
                    │  simulator / network /    │
                    │  events / features        │
                    └────────────▲──────────────┘
                                 │
                    ┌────────────┴──────────────┐
                    │  ml/generate_dataset.py    │
                    │  ml/train_model.py         │
                    └───────────────────────────┘
```

**The important design decision** is that `navacity_core` is shared by the ML
pipeline and the backend. The feature engineering, the crowd thresholds and the
network definition exist exactly once, so the model can never be fed a different
input format at prediction time than the one it was trained on. The
`test_prediction.py` suite asserts this explicitly.

### 9.1 The database

| Table | Content |
|---|---|
| `places` | The 46 stations and stops with their map coordinates, zone and served lines/routes |
| `routes` | The 24 routes with their colour, base frequency, capacity, travel time and popularity |
| `records` | The 95,568 simulated observations (4 per route-stretch per day), indexed on date, hour, route, mode and crowd level |

### 9.2 Configuration

The project runs with **no environment variables at all**. If you need to change
something, every setting has a `NAVACITY_`-prefixed environment variable
(see `backend/app/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `NAVACITY_DB_PATH` | `data/navacity.db` | SQLite database file |
| `NAVACITY_DATASET_CSV` | `data/generated/navacity_transport.csv` | The generated dataset |
| `NAVACITY_MODEL_BUNDLE` | `ml/artifacts/model_bundle.joblib` | The trained models |
| `NAVACITY_CORS_ORIGINS` | `http://localhost:5173,...` | Allowed frontend origins |
| `NAVACITY_ENV` | `local` | `local` or `production` (see section 7) |
| `NAVACITY_AUTH_PASSWORD` | `dumpme` | The authority password (see section 7) |
| `NAVACITY_AUTH_PASSWORD_HASH` | *(empty)* | `salt_hex:hash_hex` instead of the plain password |
| `NAVACITY_AUTH_SESSION_MINUTES` | `60` | Lifetime of an authority session |
| `NAVACITY_AUTH_SECRET` | *(random)* | HMAC secret used to sign the session tokens |
| `VITE_API_BASE_URL` | `/api` | Frontend → backend base URL |

---

## 10. Interface guide

The application has two interfaces. They share one design system
(`docs/design_system.md`) and one number formatter
(`frontend/src/lib/format.js`), so they look like one product.

### 10.1 The public interface — "Plan a journey"

The question the page answers is *"Is my trip crowded, and how long will I
wait?"*, and it is answered **first**.

| Order | What the passenger sees |
|---|---|
| 1 | **The answer card** — the crowd level as a large badge with an icon shape *and* a text label, one plain sentence ("Expect a moderately crowded train at 08:00. You may wait a few minutes for space."), the expected wait, the ride time, the total journey time and the occupancy bar with the 40 / 65 / 85 % thresholds marked. |
| 2 | **The controls** — a Metro \| Bus switch, the route list of that mode only ("M1 · Blue Line"), a From / To station picker with a swap button, a "Leave at" hour and a date picker limited to the supported range, plus a "Typical weekday" button. Once a result exists they collapse into a one-line summary. |
| 3 | **Less crowded alternatives** — up to three options from the same mode first, then the cross-mode options, each with the total journey time, the crowd level, the number of changes and how much faster or slower it is than the route that was chosen. |
| 4 | **"Expected crowd by hour"** — a 24-hour chart in passengers per hour, with the chosen hour marked and the bar colour carrying the crowd level. |
| 5 | **The network map** — a collapsible section with the station names and the selected route highlighted. |
| 6 | **"How crowd levels are defined"** — a collapsible explanation in plain language. |
| 7 | **The simulated-data notice** — on every page, in the same place. |

The public page never shows the model name, a raw metric, a segment id or the
authority session state.

### 10.2 The authority interface — four sections

The sign-in screen is unchanged: the password is checked by the backend and the
session token is kept in memory only. After signing in the page has a header
with *"Signed in as transport authority"*, a **Sign out** button and the
simulated-data notice, and a **sticky left sidebar** with four sections.

| Section | What it contains |
|---|---|
| **Overview** | Six KPI cards (routes, metro stations, bus stops, simulated passengers, average occupancy, overcrowded observations) and one card per mode comparing the figures that can be compared: mean occupancy, overcrowded share, peak load per vehicle and the busiest route. |
| **Metro** | The same page as the Bus section, filtered to the metro lines: a weekday/weekend occupancy profile, a peak-hours table, a sortable route table, the overcrowding alerts and the service-frequency recommendations. |
| **Bus** | The same page, filtered to the bus routes. |
| **Model & Data** | The metrics per mode (MAE, RMSE, R²) with the test period and the sample size, a plain statement that the numbers are measured on simulated data, the shape of the dataset and the feature importance. |

Every section has a page title, a one-line description and the same
right-aligned filter bar (date, route, severity). Every chart has a visible
legend, axis titles with their units and a caption with the data period and the
granularity. Every number comes from one endpoint and one function — there is
no hard-coded figure in the React code.

### 10.3 The API the two interfaces use

| Interface | Endpoints |
|---|---|
| Public | `GET /api/network`, `GET /api/routes`, `GET /api/places`, `POST /api/predict`, `GET /api/predict/day`, `GET /api/alternatives` |
| Authority | `GET /api/authority/stats`, `GET /api/authority/mode-summary`, `GET /api/authority/alerts`, `GET /api/authority/recommendations`, `GET /api/crowd-summary`, `GET /api/model/metrics` |

The public endpoints are open; the authority endpoints need a session token and
answer **401** without one.

---

## 11. Demo script (5 minutes)

1. **Start the backend and the frontend** using the commands in section 3.
2. **Open <http://localhost:5173>** — the public dashboard loads with the Blue Line
   (M1) selected and the 08:00 forecast for tomorrow. The amber banner and the header
   badge state that the data is simulated.
3. **Change the time to 18:00** — the predicted demand, the occupancy bar, the crowd
   badge and the charts all update. This is a live call to `POST /api/predict` and
   `GET /api/predict/day`, not a hard-coded number.
4. **Switch the mode to "bus" and pick B01 (Airport Express)** — the route list, the
   map highlight and the forecast all change.
5. **Click a line on the map** — it becomes the selected route.
6. **Look at "Less crowded alternatives"** — the backend searched the simulated
   network for other routes that serve the same origin and destination (directly or
   with one transfer) and scored each one with the *same* model, ranked by crowd
   level and waiting time.
7. **Open the authority dashboard** — you are redirected to the sign-in screen
   (<http://localhost:5173/authority/login>). Enter the authority password
   (`dumpme` in the local demo). The password is verified by the **backend**;
   the browser only receives a short-lived session token.
8. **Try to open the authority dashboard without signing in** — the API answers
   `401` and the frontend sends you back to the sign-in screen. The public
   dashboard keeps working, because only the authority endpoints are protected.
9. **Once signed in**, the authority dashboard shows the KPI cards (routes,
   stations, stops, simulated passengers, average occupancy, overcrowded
   observations), the bus-vs-metro comparison, the peak hours, the busiest-routes
   chart, the per-route analytics table, the overcrowding alerts (filterable by
   mode, route and severity) and the crowd-level distribution.
10. **Read the recommendations panel** — each suggestion states the current and the
    recommended vehicles per hour, the reason, a confidence level and an explicit
    disclaimer that it is a recommendation and not a guaranteed optimal decision.
11. **Scroll to "Model evaluation"** — the MAE / RMSE / R² of both models, as
    measured by `train_model.py`, clearly labelled as results on **synthetic**
    data.
12. **Sign out** (the button in the header) — the session is revoked on the server
    and the token is rejected from that moment on.
13. **Open <http://localhost:8000/docs>** — the Swagger UI with every endpoint, its
    parameters, the response schemas and the example payloads.

---

## 12. Limitations and honest caveats

* **The data is synthetic.** NavaCity is invented. The lines, stations, holidays and
  events were written for this project. No real operator, city or passenger survey
  is involved.
* **The metrics are not real-world accuracy.** R² ≈ 0.94 means the model reproduces
  the *simulator* well. A model trained on the same generator will always score
  highly; the real test would be real APC (automatic passenger count) data from an
  actual operator, which would be noisier, contain drift and missing values, and
  score considerably lower.
* **No external validation was performed.** There is no hold-out city, no
  cross-operator transfer test and no comparison against a published baseline.
* **The simulator is a rule base, not a behavioural model.** It does not model
  passenger route choice, transfer behaviour, day-to-day incidents, ticket
  integration between modes or feedback loops between crowding and demand. Real
  crowding is self-reinforcing in a way this dataset cannot express.
* **The crowd thresholds are engineering choices**, not measured standards. The
  40/65/85 % boundaries are documented and configurable in
  `navacity_core/config.py`, but they have not been validated against operator data.
* **The service-frequency recommendations are a simple, explainable heuristic**
  (± one vehicle per hour when the simulated occupancy is far outside the band), not
  an optimisation. They ignore fleet availability, driver rosters, depot capacity
  and the effect of a change on the other hours of the day.
* **Forecasts for dates far outside the simulated window** (January–June 2025) are
  extrapolations. The seasonal trend feature is clipped to the observed window and
  the weather/traffic defaults are climatological, so such a forecast should be
  read as "a typical day of that weekday", not as a real prediction.
* **The dataset is 4 observations per segment per day** (2 of them the commuter
  peaks) to keep the CSV a reasonable size. A production system would use every
  hour of every segment.
* **The frontend is a local development setup.** The Vite dev server proxies `/api`;
  a production deployment would serve the built assets behind a reverse proxy.

---

## 13. Possible extensions

* Add APC-style noise and a "demand follows crowding" feedback loop to the simulator.
* Add a proper hyper-parameter search (GridSearchCV on the time-ordered split).
* Add a LightGBM/XGBoost baseline if the environment allows the extra dependency.
* Add a Poisson/negative-binomial GLM as a statistically motivated baseline.
* Extend the alternatives service to multi-leg journeys with a transfer penalty.
* Add per-station boarding/alighting counts so the authority dashboard can show
  station-level rather than segment-level crowding.
* Add a small forecast-history table so the authority dashboard can show how the
  predictions evolved over time.

---

## 14. Quick reference — every command

```powershell
# from c:\AI\NavaCity

# 1. install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
cd frontend ; npm install ; cd ..

# 2. data + model + database
python ml\generate_dataset.py
python ml\train_model.py
python backend\seed_database.py

# 3. configure the authority password (see section 7)
$env:NAVACITY_ENV = "local"          # "production" refuses the demo password
$env:NAVACITY_AUTH_PASSWORD = "dumpme"

# 4. run (two terminals)
python -m uvicorn backend.app.main:app --reload --port 8000
cd frontend ; npm run dev ; cd ..

# 5. test
python -m pytest backend\tests -q
python backend\test_live_api.py      # needs the backend running
python frontend_check.py             # needs the frontend running

# 6. production frontend build
cd frontend ; npm run build ; cd ..
```

| URL | What it is |
|---|---|
| <http://localhost:5173> | Public dashboard (default route) |
| <http://localhost:5173/authority> | Transport authority dashboard (sign-in required) |
| <http://localhost:5173/authority/login> | Authority sign-in screen |
| <http://localhost:8000/docs> | Swagger UI |
| <http://localhost:8000/redoc> | ReDoc |
| <http://localhost:8000/api/health> | Health check |

---

*Built for a VTU B.E. Artificial Intelligence & Machine Learning mini-project.
All data is simulated.*
