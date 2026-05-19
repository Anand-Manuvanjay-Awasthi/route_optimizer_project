import requests
from django.conf import settings


ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"

METERS_TO_MILES = 0.000621371


def geocode_place(place_name):
    params = {
        "api_key": settings.ORS_API_KEY,
        "text": place_name,
        "boundary.country": "US",
        "size": 1,
    }
    resp = requests.get(ORS_GEOCODE_URL, params=params, timeout=10)

    if not resp.ok:
        raise ValueError(f"Geocoding failed for '{place_name}': {resp.status_code} {resp.text}")

    features = resp.json().get("features", [])
    if not features:
        raise ValueError(f"No location found for '{place_name}'. Try a more specific name.")

    coords = features[0]["geometry"]["coordinates"]
    label = features[0]["properties"].get("label", place_name)
    return coords, label


def get_route(start_coords, end_coords):
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json",
    }
    payload = {
        "coordinates": [start_coords, end_coords]
    }

    resp = requests.post(ORS_DIRECTIONS_URL, json=payload, headers=headers, timeout=20)

    if not resp.ok:
        raise ValueError(f"Routing API error {resp.status_code}: {resp.text}")

    data = resp.json()
    feature = data["features"][0]

    route_coords = feature["geometry"]["coordinates"]
    distance_meters = feature["properties"]["segments"][0]["distance"]
    distance_miles = round(distance_meters * METERS_TO_MILES, 2)

    return route_coords, distance_miles


def sample_route_coords(coords, max_points=50):
    if len(coords) <= max_points:
        return coords
    step = len(coords) // max_points
    sampled = coords[::step]
    if coords[-1] not in sampled:
        sampled.append(coords[-1])
    return sampled
