"""
Synthetic medical‑charge data generator (re‑usable template)
────────────────────────────────────────────────────────────
• Only uses Python ≥3.8 std‑lib + pandas + json
• All project‑specific choices live in the CFG dict — edit that block only.

Generated files (under ./data):
  │─ provider_locations.csv
  │─ charges.csv
  └─ kpi.json (average charge KPI)
"""

# ── imports ────────────────────────────────────────────────
import json, os, random
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

# ── PROJECT CONFIG ─────────────────────────────────────────
CFG = {
    "state"      : "Alabama",
    "seed"       : 42,

    # folders will be created relative to this script’s parent dir
    "data_dir"   : "data",         # subfolder name only

    # timeline
    "year_start" : 2023,            # first year (Jan‑1 start)
    "n_months"   : 12,              # number of monthly periods

    # geography (city, latitude, longitude)
    "cities"     : [
        ("Birmingham",  33.5207, -86.8025),
        ("Montgomery",  32.3792, -86.3077),
        ("Mobile",      30.6954, -88.0399),
        ("Huntsville",  34.7304, -86.5861),
        ("Tuscaloosa",  33.2098, -87.5692),
        ("Dothan",      31.2232, -85.3905),
        ("Auburn",      32.6099, -85.4808),
        ("Decatur",     34.6059, -86.9833),
        ("Gadsden",     34.0143, -86.0066),
        ("Florence",    34.7998, -87.6773)
    ],

    # healthcare business dimensions
    "payers"     : ["Medicare", "Medicaid", "Private", "Self-Pay"],

    "proc_cats"  : {
        "Cardiology"     : ["Stent", "CABG", "Angiogram"],
        "Orthopedics"    : ["Knee Replacement", "Hip Replacement", "Arthroscopy"],
        "Oncology"       : ["Chemo Session", "Radiation", "Immunotherapy"],
        "Diagnostic"     : ["MRI", "CT Scan", "Ultrasound"],
        "General Surgery": ["Appendectomy", "Cholecystectomy", "Hernia Repair"],
    },
}

# ── derived constants ─────────────────────────────────────
random.seed(CFG["seed"])
BASE_DIR   = Path(__file__).resolve().parents[1]   # project root
DATA_DIR   = BASE_DIR / CFG["data_dir"]
DATA_DIR.mkdir(exist_ok=True)

CITIES       = CFG["cities"]
PAYERS       = CFG["payers"]
PROC_CATS    = list(CFG["proc_cats"].keys())
SUB_BY_CAT   = CFG["proc_cats"]

START_DATE   = date(CFG["year_start"], 1, 1)
MONTHS       = [START_DATE + timedelta(days=30 * i) for i in range(CFG["n_months"])]

# ── provider location table ───────────────────────────────
providers = []
prov_id = 1
for city, lat, lon in CITIES:
    for _ in range(random.randint(3, 4)):
        providers.append({
            "provider_id"  : prov_id,
            "provider_name": f"{city[:3].upper()}-Med {prov_id}",
            "city"         : city,
            "lat"          : round(lat + random.uniform(-0.12, 0.12), 4),
            "lon"          : round(lon + random.uniform(-0.12, 0.12), 4),
        })
        prov_id += 1
prov_df = pd.DataFrame(providers)
prov_df.to_csv(DATA_DIR / "provider_locations.csv", index=False)

# ── transactional charge rows ─────────────────────────────
records = []
for month in MONTHS:
    month_str = month.strftime("%Y-%m")
    for p in providers:
        sampled_cats = random.sample(PROC_CATS, k=random.randint(3, 5))
        for cat in sampled_cats:
            sub_proc = random.choice(SUB_BY_CAT[cat])
            for _ in range(random.randint(8, 15)):
                payer = random.choices(PAYERS, weights=[0.35, 0.25, 0.30, 0.10])[0]

                base = random.uniform(2_000, 25_000)
                if cat == "Oncology":
                    base *= 1.8          # oncology premium
                if payer == "Private":
                    base *= 1.15         # commercial up‑charge
                charge = round(base, 2)

                records.append([
                    p["provider_id"], p["provider_name"], p["city"], p["lat"], p["lon"],
                    payer, cat, sub_proc,
                    month_str, charge
                ])

cols = [
    "provider_id", "provider_name", "city", "lat", "lon",
    "payer_type", "procedure_category", "procedure_sub",
    "month", "charge_amount",
]
charges_df = pd.DataFrame(records, columns=cols)
charges_df.to_csv(DATA_DIR / "charges.csv", index=False)

# ── headline KPI ─────────────────────────────────────────--
avg_charge = round(charges_df["charge_amount"].mean(), 2)
with open(DATA_DIR / "kpi.json", "w") as f:
    json.dump({"average_charge": avg_charge, "state": CFG["state"]}, f)

print(f"✅  Synthetic data for {CFG['state']} written to {DATA_DIR}\n"  \
      f"   – provider_locations.csv\n   – charges.csv\n   – kpi.json  (avg charge: ${avg_charge:,.2f})")
