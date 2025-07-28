# ─────────────────────────── scripts/generate_data.py ───────────────────────────
#!/usr/bin/env python3
import json, random
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

CFG = {             # trimmed for brevity – unchanged logic
    "seed": 42, "n_rides": 25_000, "n_drivers": 1_000,
    "start_date": datetime(2025, 1, 1), "end_date": datetime(2025, 6, 30),
    "products": ["UberX", "UberXL", "Comfort", "Black", "Green"],
    "surge_prob": 0.30,
    "bbox": {"lat_min": 40.55, "lat_max": 40.92, "lon_min": -74.15, "lon_max": -73.70}
}
random.seed(CFG["seed"])

ROOT      = Path(__file__).resolve().parents[1]
DATA_DIR  = ROOT / "data";  DATA_DIR.mkdir(exist_ok=True)

# driver_profiles.csv
drivers = [
    {"driver_id": i, "name": f"DRV-{i:04}",
     "rating": round(random.uniform(4.6, 5.0), 2),
     "onboard_dt": (datetime(2018, 1, 1) + timedelta(days=random.randint(0, 2555))).date()}
    for i in range(1, CFG["n_drivers"] + 1)
]
pd.DataFrame(drivers).to_csv(DATA_DIR / "driver_profiles.csv", index=False)

# rides.csv
def pick_coord():
    lat = random.uniform(CFG["bbox"]["lat_min"], CFG["bbox"]["lat_max"])
    lon = random.uniform(CFG["bbox"]["lon_min"], CFG["bbox"]["lon_max"])
    return lat, lon

span = (CFG["end_date"] - CFG["start_date"]).total_seconds()
rides = []
for r in range(1, CFG["n_rides"] + 1):
    ts = CFG["start_date"] + timedelta(seconds=random.randint(0, int(span)))
    d_id = random.randint(1, CFG["n_drivers"])
    product = random.choice(CFG["products"])
    p_lat, p_lon = pick_coord()
    d_lat, d_lon = pick_coord()
    dist = round(random.uniform(1, 25), 2)
    base = 2.5 + dist * 1.75
    surge = random.random() < CFG["surge_prob"]
    fare = round(base * (1 + (random.uniform(0.5, 2.0) if surge else 0)), 2)
    rides.append([r, ts.isoformat(), d_id, product,
                  p_lat, p_lon, d_lat, d_lon, dist, surge, fare])

cols = ["ride_id","timestamp","driver_id","product",
        "pickup_lat","pickup_lon","drop_lat","drop_lon",
        "distance_km","is_surge","fare_usd"]
pd.DataFrame(rides, columns=cols).to_csv(DATA_DIR / "rides.csv", index=False)

# kpi.json
df = pd.DataFrame(rides, columns=cols)
kpi = {
    "total_rides": len(df),
    "avg_fare_usd": round(df["fare_usd"].mean(), 2),
    "avg_distance_km": round(df["distance_km"].mean(), 2),
    "pct_surge": round(100 * df["is_surge"].mean(), 1)
}
(DATA_DIR / "kpi.json").write_text(json.dumps(kpi, indent=2))
print("✅  Data written to", DATA_DIR.relative_to(ROOT))

# ─────────────────────────── scripts/build_dashboard.py ─────────────────────────
#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
import pandas as pd, plotly.express as px

ROOT      = Path(__file__).resolve().parents[1]
DATA_DIR  = ROOT / "data"
OUT_DIR   = ROOT / "outputs"; OUT_DIR.mkdir(exist_ok=True)

rides_fp  = DATA_DIR / "rides.csv"
dr_fp     = DATA_DIR / "driver_profiles.csv"
for p in (rides_fp, dr_fp):
    if not p.exists():
        sys.exit(f"Missing {p}")

rides = pd.read_csv(rides_fp, parse_dates=["timestamp"])
kpi   = json.loads((DATA_DIR / "kpi.json").read_text())

# ── Map
sample = rides.sample(n=min(2000, len(rides)), random_state=1)
fig_map = px.scatter_mapbox(sample, lat="pickup_lat", lon="pickup_lon",
                            color="product", size="fare_usd",
                            zoom=9, height=550,
                            hover_data={"fare_usd":":.2f","distance_km":True,"is_surge":True})
fig_map.update_layout(mapbox_style="open-street-map",
                      title="Sample Pick-ups (size ∝ fare)",
                      margin=dict(t=40,l=0,r=0,b=0))

# ── Hour×Weekday heat-map
rides["hour"] = rides["timestamp"].dt.hour
rides["weekday"] = rides["timestamp"].dt.day_name()
hm = rides.groupby(["weekday","hour"]).s
