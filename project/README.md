# Route Optimizer API

## Setup

```bash
cd project
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

Place `fuel-prices-for-be-assessment.csv` in the project root (same folder as `manage.py`).

Run migrations (only needed once for Django internals):
```bash
python manage.py migrate
```

Start the server:
```bash
python manage.py runserver
```

---

## Sample Request

```bash
curl -X POST http://127.0.0.1:8000/api/optimize-route/ \
  -H "Content-Type: application/json" \
  -d '{"start": [-74.0060, 40.7128], "end": [-87.6298, 41.8781]}'
```

## Sample Response

```json
{
  "distance_miles": 789.4,
  "estimated_total_cost": 241.57,
  "fuel_stops": [
    {
      "name": "LOVES TRAVEL STOP #452",
      "address": "1234 I-80 W",
      "city": "Toledo",
      "state": "OH",
      "price_per_gallon": 3.459,
      "lat": 41.6638,
      "lon": -83.5552,
      "distance_from_route_miles": 1.2
    }
  ],
  "route_coordinates": [
    [-74.006, 40.7128],
    "..."
  ]
}
```

---

## Notes

- `MAX_RANGE_MILES = 500` — vehicle won't need a stop if the trip is under 500 miles
- `MPG = 10` — fuel cost calculated based on this
- Fuel stops are selected from the CSV by finding the cheapest station within ~20 miles of evenly-spaced route waypoints
- Route coordinates are returned as `[longitude, latitude]` pairs (GeoJSON standard)
