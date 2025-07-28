# ───────────────────────────── scripts/viz.py ─────────────────────────────
#!/usr/bin/env python3
"""
viz.py – cleaner NYC-Uber dashboard with new bottom visuals
"""

import json, sys, time
from pathlib import Path
import pandas as pd
import plotly.express as px

# ── paths ----------------------------------------------------------------
ROOT      = Path(__file__).resolve().parents[1]
DATA_DIR  = ROOT / "data"
OUT_DIR   = ROOT / "outputs"; OUT_DIR.mkdir(exist_ok=True)

for fp in (DATA_DIR / "rides.csv", DATA_DIR / "driver_profiles.csv"):
    if not fp.exists():
        sys.exit(f"Missing {fp}")

rides = pd.read_csv(DATA_DIR / "rides.csv", parse_dates=["timestamp"])
kpi   = json.loads((DATA_DIR / "kpi.json").read_text())

# ── FIGURE 1 – map -------------------------------------------------------
sample = rides.sample(n=min(2_000, len(rides)), random_state=1)
fig_map = px.scatter_mapbox(
    sample, lat="pickup_lat", lon="pickup_lon",
    color="product", size="fare_usd",
    hover_data={"fare_usd":":.2f","distance_km":True,"is_surge":True},
    zoom=9, height=520
).update_layout(mapbox_style="open-street-map",
                title="Sample Pick-ups (bubble ∝ fare)",
                margin=dict(t=40,l=0,r=0,b=0))

# ── FIGURE 2 – fare distribution by product -----------------------------
fig_box = px.box(
    rides, x="product", y="fare_usd", color="product",
    points="outliers", height=520,
    title="Fare Distribution by Product",
    labels={"fare_usd":"Fare (USD)", "product":""}
).update_layout(showlegend=False,
                margin=dict(t=50,l=40,r=40,b=40))

# ── FIGURE 3 – surge probability by hour --------------------------------
rides["hour"] = rides["timestamp"].dt.hour
surge_hour = (rides.groupby("hour")["is_surge"]
                   .mean()
                   .mul(100)        # percentage
                   .reset_index(name="pct_surge"))
fig_line = px.line(
    surge_hour, x="hour", y="pct_surge", markers=True,
    height=520, title="Surge Probability by Hour",
    labels={"pct_surge":"Surge rides (%)","hour":"Hour of day"}
).update_traces(line_shape="hv") \
 .update_layout(margin=dict(t=50,l=40,r=40,b=40))

# ── KPI tiles ------------------------------------------------------------
tiles = []
for k,v in kpi.items():
    tiles.append(f"""
      <div class='kpi-card' data-kpi='{k}:{v}'>
        <span class='kpi-value'>{v:,}</span>
        <span class='kpi-label'>{k.replace('_',' ').title()}</span>
      </div>
    """)
KPI_DIV = "<div class='kpi-grid' style='grid-column:span 2;'>" + "".join(tiles) + "</div>"

def plot_div(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar":True,"displaylogo":False})

cards = [
    KPI_DIV,
    f"<div class='card' style='grid-column:span 2'>{plot_div(fig_map)}</div>",
    f"<div class='card'>{plot_div(fig_box)}</div>",
    f"<div class='card'>{plot_div(fig_line)}</div>",
]

# ── theme / HTML shell ---------------------------------------------------
THEME = {"page_bg":"#f8fafc","header_bg":"#1e293b","accent":"#2563eb","card_bg":"#ffffff"}
html = f"""<!DOCTYPE html><html lang='en'><head>
<meta charset='utf-8'><title>NYC Uber Dashboard</title>
<script src='https://cdn.plot.ly/plotly-2.26.0.min.js'></script>
<style>
 body{{margin:0;background:{THEME['page_bg']};font-family:Segoe UI,Arial,sans-serif;color:#0f172a}}
 header{{background:{THEME['header_bg']};color:#fff;padding:1rem 2rem}}
 h1{{margin:0;font-size:1.8rem;letter-spacing:0.5px}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;padding:1.5rem}}
 .card{{background:{THEME['card_bg']};border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,.08);padding:1.25rem}}
 .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem}}
 .kpi-card{{background:{THEME['accent']}1a;border:1px solid {THEME['accent']}40;
            border-radius:6px;padding:1.25rem;text-align:center}}
 .kpi-value{{display:block;font-size:1.6rem;font-weight:600;color:{THEME['accent']}}}
 .kpi-label{{display:block;font-size:0.9rem;margin-top:0.25rem;color:#475569}}
 @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>NYC Uber Dashboard</h1></header>
<section class='grid'>
 {''.join(cards)}
</section></body></html>"""

out = OUT_DIR / "uber_dashboard.html"
out.write_text(html, encoding="utf-8")
print("✓", out.relative_to(ROOT))

# optional PNG (same as before) ------------------------------------------
if "--png" in sys.argv:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options(); opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1600,900")
        drv = webdriver.Chrome(options=opts)
        drv.get("file://" + out.resolve().as_posix())
        time.sleep(2)
        h = drv.execute_script("return document.body.scrollHeight")
        drv.set_window_size(1600, h)
        png = OUT_DIR / "uber_dashboard.png"
        drv.save_screenshot(str(png)); drv.quit()
        print("✓", png.relative_to(ROOT))
    except Exception as e:
        print("⚠ PNG not created:", e)

if __name__ == "__main__" and "--no-browser" not in sys.argv:
    import webbrowser; webbrowser.open(out.as_uri())
