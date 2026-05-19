import pandas as pd
import numpy as np
import requests
import json
import os
from django.conf import settings


MAX_RANGE_MILES = 500
MPG = 10
SEARCH_RADIUS_MILES = 30
MILES_TO_DEG = 1 / 69.0

GEOCODE_CACHE_PATH = os.path.join(settings.BASE_DIR, "geocode_cache.json")
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"


def load_geocode_cache():
    if os.path.exists(GEOCODE_CACHE_PATH):
        with open(GEOCODE_CACHE_PATH, "r") as f:
            return json.load(f)
    return {}


def save_geocode_cache(cache):
    with open(GEOCODE_CACHE_PATH, "w") as f:
        json.dump(cache, f)


def geocode_address(address, city, state, cache):
    key = f"{address},{city},{state}"
    if key in cache:
        return cache[key]

    query = f"{address}, {city}, {state}, USA"
    params = {
        "api_key": settings.ORS_API_KEY,
        "text": query,
        "boundary.country": "US",
        "size": 1,
    }

    try:
        resp = requests.get(ORS_GEOCODE_URL, params=params, timeout=5)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"]
            cache[key] = {"lat": lat, "lon": lon}
            return cache[key]
    except Exception:
        pass

    cache[key] = None
    return None


def load_fuel_data():
    df = pd.read_csv(settings.FUEL_CSV_PATH)
    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "OPIS Truckstop ID": "id",
        "Truckstop Name": "name",
        "Address": "address",
        "City": "city",
        "State": "state",
        "Rack ID": "rack_id",
        "Retail Price": "price",
    })

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price", "address", "city", "state"])
    return df


def get_fuel_data_with_coords():
    df = load_fuel_data()
    cache = load_geocode_cache()

    lats, lons = [], []
    cache_dirty = False

    for _, row in df.iterrows():
        coords = geocode_address(row["address"], row["city"], row["state"], cache)
        if coords:
            lats.append(coords["lat"])
            lons.append(coords["lon"])
        else:
            lats.append(None)
            lons.append(None)
        cache_dirty = True

    if cache_dirty:
        save_geocode_cache(cache)

    df["lat"] = lats
    df["lon"] = lons
    df = df.dropna(subset=["lat", "lon"])
    return df


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def find_stops_along_route(route_coords, total_distance_miles):
    df = get_fuel_data_with_coords()

    num_stops_needed = int(np.ceil(total_distance_miles / MAX_RANGE_MILES))
    if num_stops_needed == 0:
        return [], round((total_distance_miles / MPG) * float(df["price"].median()), 2)

    segment_length = total_distance_miles / (num_stops_needed + 1)
    total_coords = len(route_coords)

    stop_indices = []
    for i in range(1, num_stops_needed + 1):
        frac = (i * segment_length) / total_distance_miles
        idx = int(frac * (total_coords - 1))
        stop_indices.append(min(idx, total_coords - 1))

    fuel_stops = []
    for idx in stop_indices:
        lon, lat = route_coords[idx]

        nearby = pd.DataFrame()
        for multiplier in [1, 2, 3]:
            lat_margin = SEARCH_RADIUS_MILES * MILES_TO_DEG * multiplier
            lon_margin = SEARCH_RADIUS_MILES * MILES_TO_DEG * multiplier
            nearby = df[
                (df["lat"].between(lat - lat_margin, lat + lat_margin)) &
                (df["lon"].between(lon - lon_margin, lon + lon_margin))
            ].copy()
            if not nearby.empty:
                break

        if nearby.empty:
            continue

        nearby["dist"] = haversine_miles(lat, lon, nearby["lat"].values, nearby["lon"].values)
        cheapest = nearby.nsmallest(1, "price").iloc[0]

        fuel_stops.append({
            "name": cheapest.get("name", ""),
            "address": cheapest.get("address", ""),
            "city": cheapest.get("city", ""),
            "state": cheapest.get("state", ""),
            "price_per_gallon": round(float(cheapest["price"]), 3),
            "lat": round(float(cheapest["lat"]), 6),
            "lon": round(float(cheapest["lon"]), 6),
            "distance_from_route_miles": round(float(cheapest["dist"]), 2),
        })

    total_gallons = total_distance_miles / MPG
    avg_price = (
        sum(s["price_per_gallon"] for s in fuel_stops) / len(fuel_stops)
        if fuel_stops else float(df["price"].median())
    )
    estimated_cost = round(total_gallons * avg_price, 2)
    return fuel_stops, estimated_cost
