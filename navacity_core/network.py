"""The (fictional) NavaCity public transport network.

NavaCity is a SIMULATED city.  The lines, stations, stops and schedules
defined here are invented for this project; they do not correspond to any
real operator, city or dataset.

Layout of the network
---------------------
* 6 metro lines (M1 - M6) with 42 stations in total.
* 18 bus routes (B01 - B18) serving 42 distinct stops.
* Some bus stops are co-located with metro stations; these are flagged as
  ``interchange`` places and are used to build alternative-route suggestions.

Every place sits on a schematic 0-100 coordinate grid so the frontend can
render a transit map without needing any external map tile server.
"""

from __future__ import annotations

from .config import BASE_OCCUPANCY

# --------------------------------------------------------------------------
# Metro lines: (line_id, name, colour, [station names])
# --------------------------------------------------------------------------
METRO_LINES: list[dict] = [
    {
        "id": "M1",
        "name": "Blue Line",
        "color": "#2563eb",
        "stations": [
            "NavaCity Central",
            "Mahatma Nagar",
            "City Park",
            "Saraswati Junction",
            "Tech Park Gate",
            "Aerodrome Interchange",
            "Whitefield Depot",
        ],
    },
    {
        "id": "M2",
        "name": "Red Line",
        "color": "#dc2626",
        "stations": [
            "Riverfront",
            "Gandhi Chowk",
            "Lalbagh",
            "Vidhana Soudha",
            "NavaCity Central",
            "Market Yard",
            "Old Town Gate",
            "Hill View",
        ],
    },
    {
        "id": "M3",
        "name": "Green Line",
        "color": "#16a34a",
        "stations": [
            "Hebbal Farm",
            "Yelahanka New Town",
            "Kogilu Cross",
            "Indira Nagar 2nd Stage",
            "Domlur Flyover",
            "Laxmi Road",
            "NavaCity Central",
            "Chinnaswamy Park",
        ],
    },
    {
        "id": "M4",
        "name": "Yellow Line",
        "color": "#ca8a04",
        "stations": [
            "Peenya Industrial Area",
            "Jnanabharathi Circle",
            "Yeshwanthpur",
            "Majestic",
            "KR Market",
            "NavaCity Central",
            "Hosahalli",
            "Silk Board",
        ],
    },
    {
        "id": "M5",
        "name": "Purple Line",
        "color": "#7c3aed",
        "stations": [
            "Bannerghatta Road",
            "HSR Layout Sector 2",
            "BTM Layout",
            "Jayanagar 4th Block",
            "South End",
            "NavaCity Central",
            "Banashankari",
            "Padmanabha Nagar",
        ],
    },
    {
        "id": "M6",
        "name": "Aqua Line",
        "color": "#0891b2",
        "stations": [
            "Devanahalli",
            "Kempegowda Intl Airport",
            "Hebbal Flyover",
            "Bellandur Lake",
            "Kadugodi Tree Park",
            "Marathahalli Bridge",
            "Silk Board",
            "NavaCity Central",
        ],
    },
]

# --------------------------------------------------------------------------
# Bus routes: (route_id, name, [stop names], base frequency per hour)
# --------------------------------------------------------------------------
BUS_ROUTES: list[dict] = [
    {
        "id": "B01",
        "name": "Airport Express",
        "base_frequency": 4,
        "stops": [
            "Kempegowda Intl Airport",
            "Hebbal Flyover",
            "Bellandur Lake",
            "Marathahalli Bridge",
            "Domlur Flyover",
            "Laxmi Road",
            "Vidhana Soudha",
            "Majestic",
        ],
    },
    {
        "id": "B02",
        "name": "Old Town Circular",
        "base_frequency": 5,
        "stops": [
            "Old Town Gate",
            "Hill View",
            "Gandhi Chowk",
            "Riverfront",
            "Market Yard",
            "Gandhi Chowk",
            "Old Town Gate",
        ],
    },
    {
        "id": "B03",
        "name": "Whitefield Commuter",
        "base_frequency": 6,
        "stops": [
            "Whitefield Depot",
            "Brookefield Gate",
            "Kundalahalli Gate",
            "Brookefield Circle",
            "ITPL Tech Park",
            "Tech Park Gate",
            "Saraswati Junction",
            "City Park",
        ],
    },
    {
        "id": "B04",
        "name": "Airport Feeder",
        "base_frequency": 3,
        "stops": [
            "Devanahalli",
            "Kempegowda Intl Airport",
            "Bellandur Lake",
            "Kadugodi Tree Park",
            "Marathahalli Bridge",
        ],
    },
    {
        "id": "B05",
        "name": "South City Link",
        "base_frequency": 5,
        "stops": [
            "Bannerghatta Road",
            "HSR Layout Sector 2",
            "BTM Layout",
            "Jayanagar 4th Block",
            "South End",
            "Banashankari",
            "Padmanabha Nagar",
        ],
    },
    {
        "id": "B06",
        "name": "North Corridor",
        "base_frequency": 5,
        "stops": [
            "Hebbal Farm",
            "Yelahanka New Town",
            "Kogilu Cross",
            "Indira Nagar 2nd Stage",
            "Domlur Flyover",
            "Laxmi Road",
        ],
    },
    {
        "id": "B07",
        "name": "Market Shuttle",
        "base_frequency": 4,
        "stops": [
            "KR Market",
            "NavaCity Central Bus Depot",
            "Vidhana Soudha",
            "Lalbagh",
            "Jayanagar 4th Block",
            "KR Market",
        ],
    },
    {
        "id": "B08",
        "name": "Industrial Belt Route",
        "base_frequency": 3,
        "stops": [
            "Peenya Industrial Area",
            "Jnanabharathi Circle",
            "Yeshwanthpur",
            "Majestic",
            "NavaCity Central Bus Depot",
        ],
    },
    {
        "id": "B09",
        "name": "Lake View Nightline",
        "base_frequency": 2,
        "stops": [
            "Kadugodi Tree Park",
            "Bellandur Lake",
            "Marathahalli Bridge",
            "Silk Board",
            "Jayanagar 4th Block",
            "Banashankari",
        ],
    },
    {
        "id": "B10",
        "name": "University Loop",
        "base_frequency": 4,
        "stops": [
            "Jnanabharathi Circle",
            "Yeshwanthpur",
            "KR Market",
            "NavaCity Central Bus Depot",
            "Vidhana Soudha",
            "Jnanabharathi Circle",
        ],
    },
    {
        "id": "B11",
        "name": "Airport Link Nightline",
        "base_frequency": 2,
        "stops": [
            "Kempegowda Intl Airport",
            "Hebbal Flyover",
            "Bellandur Lake",
            "Kadugodi Tree Park",
            "Marathahalli Bridge",
            "Silk Board",
        ],
    },
    {
        "id": "B12",
        "name": "Old Town Heritage Route",
        "base_frequency": 4,
        "stops": [
            "Old Town Gate",
            "Riverfront",
            "Gandhi Chowk",
            "Lalbagh",
            "Vidhana Soudha",
            "KR Market",
            "NavaCity Central Bus Depot",
        ],
    },
    {
        "id": "B13",
        "name": "Whitefield Extension",
        "base_frequency": 4,
        "stops": [
            "Whitefield Depot",
            "Brookefield Circle",
            "Kundalahalli Gate",
            "Brookefield Gate",
            "ITPL Tech Park",
        ],
    },
    {
        "id": "B14",
        "name": "Peenya Workers Shuttle",
        "base_frequency": 3,
        "stops": [
            "Peenya Industrial Area",
            "Jnanabharathi Circle",
            "Yeshwanthpur",
            "Majestic",
            "NavaCity Central Bus Depot",
            "KR Market",
        ],
    },
    {
        "id": "B15",
        "name": "South West Connector",
        "base_frequency": 3,
        "stops": [
            "Bannerghatta Road",
            "BTM Layout",
            "Jayanagar 4th Block",
            "South End",
            "Silk Board",
        ],
    },
    {
        "id": "B16",
        "name": "Indira Nagar Feeder",
        "base_frequency": 5,
        "stops": [
            "Hebbal Farm",
            "Yelahanka New Town",
            "Kogilu Cross",
            "Indira Nagar 2nd Stage",
            "Domlur Flyover",
            "Chinnaswamy Park",
        ],
    },
    {
        "id": "B17",
        "name": "Airport Terminal Loop",
        "base_frequency": 3,
        "stops": [
            "Devanahalli",
            "Kempegowda Intl Airport",
            "Hebbal Flyover",
            "Whitefield Depot",
        ],
    },
    {
        "id": "B18",
        "name": "City Centre Rapid Bus",
        "base_frequency": 6,
        "stops": [
            "NavaCity Central Bus Depot",
            "KR Market",
            "Vidhana Soudha",
            "Lalbagh",
            "Gandhi Chowk",
            "Riverfront",
        ],
    },
]

# Bus-only places (not served by any metro line).
BUS_ONLY_PLACES: list[dict] = [
    {"id": "S-B01", "name": "Brookefield Gate", "kind": "stop", "x": 74, "y": 34},
    {"id": "S-B02", "name": "Kundalahalli Gate", "kind": "stop", "x": 78, "y": 31},
    {"id": "S-B03", "name": "Brookefield Circle", "kind": "stop", "x": 80, "y": 29},
    {"id": "S-B04", "name": "ITPL Tech Park", "kind": "stop", "x": 72, "y": 27},
    {"id": "S-B05", "name": "NavaCity Central Bus Depot", "kind": "stop", "x": 50, "y": 63},
]

# --------------------------------------------------------------------------
# Schematic coordinates for metro stations (0-100 grid, y grows downward).
# --------------------------------------------------------------------------
METRO_COORDS: dict[str, tuple[float, float]] = {
    # M1 Blue Line
    "NavaCity Central": (50.0, 50.0),
    "Mahatma Nagar": (42.0, 44.0),
    "City Park": (35.0, 38.0),
    "Saraswati Junction": (28.0, 31.0),
    "Tech Park Gate": (22.0, 25.0),
    "Aerodrome Interchange": (30.0, 17.0),
    "Whitefield Depot": (38.0, 12.0),
    # M2 Red Line
    "Riverfront": (16.0, 62.0),
    "Gandhi Chowk": (24.0, 57.0),
    "Lalbagh": (31.0, 53.0),
    "Vidhana Soudha": (38.0, 51.0),
    "Market Yard": (60.0, 55.0),
    "Old Town Gate": (12.0, 74.0),
    "Hill View": (19.0, 70.0),
    # M3 Green Line
    "Hebbal Farm": (8.0, 18.0),
    "Yelahanka New Town": (14.0, 14.0),
    "Kogilu Cross": (21.0, 20.0),
    "Indira Nagar 2nd Stage": (30.0, 25.0),
    "Domlur Flyover": (38.0, 30.0),
    "Laxmi Road": (45.0, 40.0),
    "Chinnaswamy Park": (58.0, 45.0),
    # M4 Yellow Line
    "Peenya Industrial Area": (5.0, 36.0),
    "Jnanabharathi Circle": (11.0, 34.0),
    "Yeshwanthpur": (18.0, 40.0),
    "Majestic": (24.0, 46.0),
    "KR Market": (43.0, 44.0),
    "Hosahalli": (57.0, 60.0),
    "Silk Board": (66.0, 72.0),
    # M5 Purple Line
    "Bannerghatta Road": (34.0, 88.0),
    "HSR Layout Sector 2": (40.0, 82.0),
    "BTM Layout": (46.0, 76.0),
    "Jayanagar 4th Block": (50.0, 68.0),
    "South End": (55.0, 61.0),
    "Banashankari": (48.0, 60.0),
    "Padmanabha Nagar": (44.0, 66.0),
    # M6 Aqua Line
    "Devanahalli": (88.0, 8.0),
    "Kempegowda Intl Airport": (82.0, 12.0),
    "Hebbal Flyover": (75.0, 16.0),
    "Bellandur Lake": (80.0, 26.0),
    "Kadugodi Tree Park": (70.0, 24.0),
    "Marathahalli Bridge": (68.0, 34.0),
}

# Bus stops that are physically the same place as a metro station.
INTERCHANGE_NAMES = {
    "Kempegowda Intl Airport", "Hebbal Flyover", "Bellandur Lake",
    "Marathahalli Bridge", "Domlur Flyover", "Laxmi Road",
    "Vidhana Soudha", "Old Town Gate", "Hill View", "Gandhi Chowk",
    "Riverfront", "Market Yard", "Whitefield Depot", "Tech Park Gate",
    "Saraswati Junction", "City Park", "Devanahalli",
    "Kadugodi Tree Park", "Bannerghatta Road", "HSR Layout Sector 2",
    "BTM Layout", "Jayanagar 4th Block", "South End", "Banashankari",
    "Padmanabha Nagar", "Hebbal Farm", "Yelahanka New Town",
    "Kogilu Cross", "Indira Nagar 2nd Stage", "Peenya Industrial Area",
    "Jnanabharathi Circle", "Yeshwanthpur", "KR Market", "Silk Board",
    "Lalbagh",
}




# --------------------------------------------------------------------------
# Relative busyness of a route (used to build realistic demand differences).
# These are SIMULATED popularity weights, not measurements.
# --------------------------------------------------------------------------
ROUTE_POPULARITY: dict[str, float] = {
    "M1": 1.00, "M2": 1.12, "M3": 0.92, "M4": 1.05, "M5": 0.80, "M6": 0.88,
    "B01": 1.18, "B02": 0.72, "B03": 1.10, "B04": 0.95, "B05": 0.85,
    "B06": 0.68, "B07": 0.90, "B08": 0.62, "B09": 0.55, "B10": 0.75,
    "B11": 0.58, "B12": 0.83, "B13": 0.66, "B14": 0.60, "B15": 0.64,
    "B16": 0.88, "B17": 0.52, "B18": 1.04,
}

# Vehicle capacity of a single unit (passengers per trip).
VEHICLE_CAPACITY = {"metro": 320, "bus": 48}

# Nominal end-to-end journey time of a route, in minutes.
ROUTE_TRAVEL_MINUTES = {
    "M1": 34, "M2": 41, "M3": 38, "M4": 36, "M5": 33, "M6": 45,
    "B01": 52, "B02": 28, "B03": 44, "B04": 31, "B05": 37,
    "B06": 35, "B07": 24, "B08": 29, "B09": 26, "B10": 22,
    "B11": 47, "B12": 33, "B13": 25, "B14": 30, "B15": 27,
    "B16": 34, "B17": 38, "B18": 23,
}

# Average time passengers spend waiting for the next vehicle, in minutes,
# per minute of headway.  Used to turn the service frequency into a wait time.
MODE_WAIT_PER_HEADWAY = {"metro": 0.45, "bus": 0.50}


def _slug(name: str) -> str:
    keep = [c for c in name.lower() if c.isalnum()]
    return "".join(keep)[:18]


# --------------------------------------------------------------------------
# Journey (segment) resolution
#
# A "segment" is the stretch of a route between two consecutive stations.  A
# journey from A to B on a route therefore covers one or more consecutive
# segments.  The helpers below turn an (origin, destination) pair into the
# segment that carries the peak demand of that journey, so that the forecast
# really depends on where the traveller is going.
# --------------------------------------------------------------------------
def segment_between(route_id: str, origin_id: str, dest_id: str) -> dict | None:
    """Return the segment of ``route_id`` that lies on the origin->dest path.

    The path is the contiguous run of segments between the two places.  When the
    origin and the destination are the same place, or when they are not both
    served by the route, ``None`` is returned.
    """
    network = build_network()
    segments = sorted(
        (s for s in network["segments"] if s["route_id"] == route_id),
        key=lambda s: s["segment_index"],
    )
    if not segments:
        return None

    # The places of the route in the order the route serves them.
    route_order = [s["origin_id"] for s in segments] + [segments[-1]["dest_id"]]

    if origin_id not in route_order or dest_id not in route_order:
        return None
    i, j = route_order.index(origin_id), route_order.index(dest_id)
    if i == j:
        return None

    lo, hi = (i, j) if i < j else (j, i)
    # The peak segment of the path is the one with the highest segment index
    # (the central segments of a line carry the most passengers).
    path = [s for s in segments if lo <= s["segment_index"] < hi]
    if not path:
        return None
    return max(path, key=lambda s: s["segment_index"])


def route_path_segments(route_id: str, origin_id: str, dest_id: str) -> list[dict]:
    """Return every segment of the origin->dest path, in travel order.

    The list is empty when the route does not serve both places, or when the
    two places are the same.
    """
    network = build_network()
    segments = sorted(
        (s for s in network["segments"] if s["route_id"] == route_id),
        key=lambda s: s["segment_index"],
    )
    if not segments:
        return []
    route_order = [s["origin_id"] for s in segments] + [segments[-1]["dest_id"]]
    if origin_id not in route_order or dest_id not in route_order:
        return []
    i, j = route_order.index(origin_id), route_order.index(dest_id)
    if i == j:
        return []
    lo, hi = (i, j) if i < j else (j, i)
    path = [s for s in segments if lo <= s["segment_index"] < hi]
    if i > j:
        path = list(reversed(path))
    return path


def journey_ride_minutes(
    route_id: str, origin_id: str, dest_id: str, traffic_factor: float = 1.0
) -> float | None:
    """Total in-vehicle time of the whole origin->dest journey, in minutes.

    This is the sum of the travel times of every segment on the path, which is
    what a passenger actually spends riding.  ``None`` is returned when the
    route does not serve both places.
    """
    path = route_path_segments(route_id, origin_id, dest_id)
    if not path:
        return None
    total = sum(float(seg["travel_minutes"]) for seg in path)
    return round(total * traffic_factor, 1)


def build_network() -> dict:
    """Build the static NavaCity network description.

    Returns a dictionary with the keys ``metro_lines``, ``bus_routes``,
    ``places`` (all stations and stops), ``segments`` and ``line_segments``.
    """
    places: dict[str, dict] = {}
    by_id: dict[str, dict] = {}
    segments: list[dict] = []

    # ---------------- Metro ----------------
    for line in METRO_LINES:
        line_station_ids: list[str] = []
        for name in line["stations"]:
            if name not in places:
                coords = METRO_COORDS.get(name, (50.0, 50.0))
                places[name] = {
                    "id": f"ST-{_slug(name)}",
                    "name": name,
                    "kind": "station",
                    "x": coords[0],
                    "y": coords[1],
                    "metro_lines": [],
                    "bus_routes": [],
                    "is_interchange": False,
                    "zone": 1 if (coords[0] < 33 or coords[1] < 33 or coords[1] > 67) else 2,
                }
            place = places[name]
            if line["id"] not in place["metro_lines"]:
                place["metro_lines"].append(line["id"])
            by_id[place["id"]] = place
            line_station_ids.append(place["id"])

        for idx in range(len(line_station_ids) - 1):
            origin = line_station_ids[idx]
            dest = line_station_ids[idx + 1]
            seg = {
                "segment_id": f"{line['id']}-S{idx + 1:02d}",
                "mode": "metro",
                "route_id": line["id"],
                "route_name": line["name"],
                "route_color": line["color"],
                "segment_index": idx,
                "origin_id": origin,
                "origin_name": by_id[origin]["name"],
                "dest_id": dest,
                "dest_name": by_id[dest]["name"],
                "num_stops": len(line["stations"]),
                "travel_minutes": round(
                    ROUTE_TRAVEL_MINUTES[line["id"]] / (len(line["stations"]) - 1), 1
                ),
            }
            segments.append(seg)

        for pid in line_station_ids:
            by_id[pid]["is_interchange"] = True

    # ---------------- Bus ----------------
    for route in BUS_ROUTES:
        route_stop_ids: list[str] = []
        for name in route["stops"]:
            if name in places:
                place = places[name]
            else:
                extra = next((p for p in BUS_ONLY_PLACES if p["name"] == name), None)
                if extra is None:  # pragma: no cover - defensive
                    extra = {"id": f"ST-{_slug(name)}", "x": 50.0, "y": 50.0}
                place = {
                    "id": extra["id"],
                    "name": name,
                    "kind": "stop",
                    "x": extra["x"],
                    "y": extra["y"],
                    "metro_lines": [],
                    "bus_routes": [],
                    "is_interchange": False,
                    "zone": 2,
                }
                places[name] = place
            if route["id"] not in place["bus_routes"]:
                place["bus_routes"].append(route["id"])
            by_id[place["id"]] = place
            route_stop_ids.append(place["id"])

        for idx in range(len(route_stop_ids) - 1):
            origin = route_stop_ids[idx]
            dest = route_stop_ids[idx + 1]
            seg = {
                "segment_id": f"{route['id']}-S{idx + 1:02d}",
                "mode": "bus",
                "route_id": route["id"],
                "route_name": route["name"],
                "route_color": "#f59e0b",
                "segment_index": idx,
                "origin_id": origin,
                "origin_name": by_id[origin]["name"],
                "dest_id": dest,
                "dest_name": by_id[dest]["name"],
                "num_stops": len(route["stops"]),
                "travel_minutes": round(
                    ROUTE_TRAVEL_MINUTES[route["id"]] / max(1, len(route["stops"]) - 1), 1
                ),
            }
            segments.append(seg)

    # ---------------- Payload ----------------
    place_list = list(places.values())
    for place in place_list:
        place["metro_lines"] = sorted(set(place["metro_lines"]))
        place["bus_routes"] = sorted(set(place["bus_routes"]))

    metro_lines = []
    for line in METRO_LINES:
        station_ids = [places[n]["id"] for n in line["stations"]]

        metro_lines.append(
            {
                "id": line["id"],
                "name": line["name"],
                "color": line["color"],
                "stations": station_ids,
                "station_names": list(line["stations"]),
                "base_frequency": 8,
                "vehicle_capacity": VEHICLE_CAPACITY["metro"],
                "travel_minutes": ROUTE_TRAVEL_MINUTES[line["id"]],
                "popularity": ROUTE_POPULARITY[line["id"]],
            }
        )

    bus_routes = []
    for route in BUS_ROUTES:
        stop_ids = [places[n]["id"] for n in route["stops"]]
        bus_routes.append(
            {
                "id": route["id"],
                "name": route["name"],
                "color": "#f59e0b",
                "stops": stop_ids,
                "stop_names": list(route["stops"]),
                "base_frequency": route["base_frequency"],
                "vehicle_capacity": VEHICLE_CAPACITY["bus"],
                "travel_minutes": ROUTE_TRAVEL_MINUTES[route["id"]],
                "popularity": ROUTE_POPULARITY[route["id"]],
            }
        )

    return {
        "city": "NavaCity",
        "data_notice": (
            "SIMULATED DATA - NavaCity is a fictional city. All passenger "
            "figures are produced by a rule-based simulator."
        ),
        "metro_lines": metro_lines,
        "bus_routes": bus_routes,
        "places": place_list,
        "segments": segments,
        "vehicle_capacity": VEHICLE_CAPACITY,
    }
