# Route Optimizer API

A Django REST API that takes a start and end location by name, fetches the driving route using OpenRouteService, finds the cheapest fuel stops along the way, and returns an estimated total trip cost. Built as a backend assessment project.

---

## What It Does

You give it two place names. It figures out the drive route between them, determines how many fuel stops a vehicle would need (assuming a 500-mile tank range and 10 MPG), finds the cheapest station near each stop point from a local CSV dataset, and hands back everything in a single JSON response.

The whole thing runs on one POST endpoint.

---

## Tech Stack

- Python 3.12
- Django 5.0 + Django REST Framework 3.15
- pandas + numpy (fuel data processing)
- requests (HTTP calls to ORS)
- python-dotenv (environment config)
- OpenRouteService API (geocoding + routing)
- SQLite (Django internals only, no application data stored)

---

## Architecture Diagram 

<img width="976" height="727" alt="image" src="https://github.com/user-attachments/assets/aff86a8e-1775-4f0a-bc32-63cf379ba489" />



## Project Structure

```
project/
├── manage.py
├── requirements.txt
├── .env.example
├── fuel-prices-for-be-assessment.csv   <-- you provide this
├── geocode_cache.json                  <-- auto-generated on first run
│
├── project/
│   ├── settings.py
│   └── urls.py
│
└── core/
    └── route_optimizer/
        ├── views.py                    <-- request entry point
        ├── urls.py
        ├── services/
        │   ├── routing_service.py      <-- ORS geocoding + directions
        │   └── fuel_service.py         <-- CSV loading, stop finding, cost calc
        └── utils/
            └── serializers.py          <-- input validation
```

The services folder does the actual work. `views.py` just wires things together and handles errors. There are no models because nothing gets persisted.

---

## API Reference

### POST /api/optimize-route/

**Request body:**

```json
{
  "start": "New York, NY",
  "end": "Chicago, IL"
}
```

Both fields are plain text location names. The API resolves them to coordinates internally using ORS geocoding before fetching the route.

**Success response (200):**

```json
{
  "start": "New York, New York, USA",
  "end": "Chicago, Illinois, USA",
  "distance_miles": 789.4,
  "estimated_total_cost": 232.76,
  "fuel_stops": [
    {
      "name": "LOVES TRAVEL STOP #452",
      "address": "1234 I-80 W",
      "city": "Toledo",
      "state": "OH",
      "price_per_gallon": 3.012,
      "lat": 41.663800,
      "lon": -83.555200,
      "distance_from_route_miles": 1.2
    }
  ],
  "route_coordinates": [
    [-74.0060, 40.7128],
    "..."
  ]
}
```

**Error responses:**

| Status | Meaning |
|--------|---------|
| 400 | Missing or invalid input fields |
| 400 | Place name could not be geocoded |
| 502 | ORS API returned an error |
| 500 | Internal error during fuel processing |

Errors always include an `"error"` key with a plain English description of what went wrong.

---

## How the Fuel Stop Logic Works

### Step 1 -- Determine how many stops are needed

```
num_stops = ceil(total_miles / 500)
```

A 789-mile trip needs `ceil(789 / 500) = 2` stops.

### Step 2 -- Place waypoints evenly along the route

The route is divided into equal segments. For 2 stops, waypoints are placed at the 33% and 66% marks of the full route coordinate array. This gives us geographic points on the road where the vehicle would ideally refuel.

### Step 3 -- Find the cheapest station near each waypoint

For each waypoint coordinate:

1. A bounding box is applied -- only stations within roughly 20 miles (converted to degrees: `20 / 69 = 0.29 degrees`) are considered. This is a cheap pandas comparison, not a distance calculation.
2. If the box is empty, it expands to 40 miles, then 60 miles.
3. From the filtered set, `nsmallest(1, "price")` picks the single cheapest station.

### Step 4 -- Calculate total estimated cost

```
total_gallons = total_miles / 10
avg_price = average of chosen stop prices
estimated_cost = total_gallons * avg_price
```

### Why the CSV has no coordinates (and how it is handled)

The fuel dataset only has addresses, no latitude/longitude. The first time any station is looked up, its address is sent to the ORS geocoding API to get coordinates. The result is saved to `geocode_cache.json` on disk.

Every subsequent request reads from the cache. The actual API call happens once per unique address, ever. You can pre-warm the cache (see below) so the first production request is not slow.

---

## Setup and Running Locally

**Requirements:**

- Python 3.10 or later
- An OpenRouteService API key (free tier works fine -- sign up at openrouteservice.org)
- The fuel prices CSV file placed in the project root

**Steps:**

```bash
# 1. Clone and enter the project
cd project

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and fill in your ORS_API_KEY and SECRET_KEY

# 5. Place the CSV file in the project root
# Expected filename: fuel-prices-for-be-assessment.csv

# 6. Run migrations (Django internals only)
python manage.py migrate

# 7. Start the server
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000`.

**Pre-warming the geocode cache (recommended):**

On a large CSV this avoids a slow first request in production:

```bash
python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'
django.setup()
from core.route_optimizer.services.fuel_service import get_fuel_data_with_coords
df = get_fuel_data_with_coords()
print(f'Geocoded {len(df)} stations successfully')
"
```

---

## Sample Request

Using curl:

```bash
curl -X POST http://127.0.0.1:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "end": "Los Angeles, CA"}'
```

Using Python requests:

```python
import requests

resp = requests.post(
    "http://127.0.0.1:8000/api/optimize-route/",
    json={"start": "New York, NY", "end": "Chicago, IL"}
)
print(resp.json())
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ORS_API_KEY` | Yes | Your OpenRouteService API key |
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No | Set to `False` in production (default: `True`) |

See `.env.example` for the template.

---

## Design Decisions

**Why no database?** The assessment does not require storing trips or users. Adding a database would be over-engineering for the current scope. If this needed trip history or user accounts, Postgres would be the natural next step.

**Why a flat service structure instead of classes?** The logic in each service file is simple enough that plain functions are easier to read and test than a class hierarchy. Classes would add ceremony without clarity here.

**Why geocode station addresses via API instead of hardcoding coordinates?** The CSV has no lat/lon columns. Hardcoding coordinates manually would work for a fixed dataset, but breaks the moment the CSV changes. The API approach with a disk cache handles any dataset size automatically and follows the same pattern used in real data pipelines. After the cache is warm, performance is equivalent to hardcoded data.

**Why sample route coordinates to 50 points?** ORS can return hundreds of coordinate pairs for long routes. Running a proximity search against the fuel dataset for every single point would be slow. 50 evenly sampled points gives accurate waypoint placement while keeping processing time reasonable.

**Why a bounding box before haversine distance?** Computing the haversine formula (spherical distance) is relatively expensive when done against hundreds of stations. A pandas `.between()` filter on lat/lon columns is essentially free by comparison. The bounding box eliminates 90-95% of candidates instantly, and the precise distance check only runs on the small remaining set.

---

## Known Limitations

- Route optimization assumes a fixed 500-mile range and 10 MPG for all vehicles. These are hardcoded constants and not yet user-configurable.
- Fuel cost is an estimate based on average stop price across the full trip, not per-segment calculation.
- The geocode cache is a flat JSON file. For a multi-process or multi-server deployment, this would need to move to Redis or a database.
- No authentication on the API endpoint. Fine for assessment purposes, would need API keys or JWT in production.

---

## Requirements

```
Django==5.0.4
djangorestframework==3.15.1
requests==2.31.0
pandas==2.2.2
python-dotenv==1.0.1
numpy>=2.0
```
