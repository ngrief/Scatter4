#!/usr/bin/env python3
"""
viz.py – build a static Plotly dashboard from generated charge data
───────────────────────────────────────────────────────────────────
Only std‑lib + pandas + plotly (+ optional selenium for PNG).
Edit **nothing** below the CFG block to reuse for another project.
"""

# ── PROJECT CONFIG ─────────────────────────────────────────────
CFG = {
    # Dashboard metadata --------------------------------------------------
    "dashboard_title": "Alabama Medical‑Charges Dashboard",
    "output_name"    : "golden_image",          # basename for HTML + PNG

    # Which visuals to include (order matters) ---------------------------
    # Supported keys: "sankey", "treemap", "heatmap"  (add more later)
    "figures": ["sankey", "treemap", "heatmap"],

    # Simple theming ------------------------------------------------------
    "theme": {
        "page_bg"  : "#f5f5f7",
        "header_bg": "#2D63C8",
        "card_bg"  : "#ffffff"
    }
}

# ─────────────────────────────────────────────────────────────────────────
# imports
# ─────────────────────────────────────────────────────────────────────────
import json, sys, re, time
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Any

# ─────────────────────────────────────────────────────────────────────────
# 1. Paths
# ─────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR     = PROJECT_ROOT / "data"
OUT_DIR      = PROJECT_ROOT / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PATH_CHARGES = DATA_DIR / "charges.csv"
PATH_LOC     = DATA_DIR / "provider_locations.csv"
PATH_KPI     = DATA_DIR / "kpi.json"          # optional but nice

for p in (PATH_CHARGES, PATH_LOC):
    if not p.exists():
        sys.exit(f"Required file missing: {p}")

# ─────────────────────────────────────────────────────────────────────────
# 2. Load + harmonise data (schema‑agnostic)
# ─────────────────────────────────────────────────────────────────────────
charges = pd.read_csv(PATH_CHARGES)
loc     = pd.read_csv(PATH_LOC)

# detect charge column
charge_col = next((c for c in charges.columns if "charge" in c.lower()), None)
if not charge_col:
    sys.exit("No column containing the word 'charge' found.")
charges.rename(columns={charge_col: "charge"}, inplace=True)

# verify provider_id
if "provider_id" not in charges.columns or "provider_id" not in loc.columns:
    sys.exit("Both CSVs must contain provider_id for merging.")

df = charges.merge(loc, on="provider_id", how="left")

# attempt to normalise key columns

def _first(cols, pat):
    return next((c for c in cols if re.fullmatch(pat, c, flags=re.I)), None)

if "provider_city" not in df.columns:
    c = _first(df.columns, r"city(_[xy])?")
    if c:
        df.rename(columns={c: "provider_city"}, inplace=True)
    else:
        df["provider_city"] = "Unknown City"

for want, pat in [("lat", r"lat(_[xy])?"), ("lon", r"(lon|lng)(_?[xy])?")]:
    if want not in df.columns:
        alt = _first(df.columns, pat)
        if alt:
            df.rename(columns={alt: want}, inplace=True)

df.rename(columns={
    "procedure_category": "proc_category",
    "procedure_sub":      "proc_subcategory"
}, inplace=True, errors="ignore")

for col in ("charge", "lat", "lon"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ─────────────────────────────────────────────────────────────────────────
# 3. Build Plotly figures conditionally
# ─────────────────────────────────────────────────────────────────────────
figs = []              # (figure_object, takes_full_width?)

if "sankey" in CFG["figures"]:
    sankey_dims = ["payer_type", "proc_category", "provider_city"]
    nodes = pd.concat([df[c] for c in sankey_dims]).unique().tolist()
    idx   = {n: i for i, n in enumerate(nodes)}

    src, trg, val = [], [], []
    for a, b in zip(sankey_dims[:-1], sankey_dims[1:]):
        g = df.groupby([a, b], as_index=False)["charge"].sum()
        src += g[a].map(idx).tolist()
        trg += g[b].map(idx).tolist()
        val += g["charge"].tolist()

    f = go.Figure(go.Sankey(
            node=dict(label=nodes, pad=15, thickness=15,
                      color="rgba(44,160,101,0.8)"),
            link=dict(source=src, target=trg, value=val)))
    f.update_layout(title="Medical‑Charge Flow: Payer → Procedure → City",
                    font_size=12, height=550)
    figs.append((f, True))      # span full grid width

if "treemap" in CFG["figures"]:
    f = px.treemap(df, path=["proc_category", "proc_subcategory", "payer_type"],
                   values="charge", color="proc_category",
                   title="Charge Distribution by Procedure Hierarchy",
                   height=550)
    f.update_traces(root_color="lightgrey")
    f.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    figs.append((f, False))

if "heatmap" in CFG["figures"]:
    pivot = (df.groupby(["provider_city", "proc_category"])["charge"].median()
               .reset_index()
               .pivot(index="provider_city", columns="proc_category", values="charge")
               .fillna(0))
    f = px.imshow(pivot, aspect="auto", color_continuous_scale="Viridis",
                  labels=dict(color="Median Charge (USD)"),
                  title="Median Charge by City & Procedure Category", height=550)
    f.update_layout(yaxis_title="", xaxis_title="",
                    margin=dict(t=50, l=25, r=25, b=25))
    figs.append((f, False))

# ─────────────────────────────────────────────────────────────────────────
# 4.  KPI snippet (optional)
# ─────────────────────────────────────────────────────────────────────────
try:
    kpi = json.loads((DATA_DIR / "kpi.json").read_text())
    rows = "".join(
        f"<tr><td><strong>{k}</strong></td><td style='text-align:right'>{v:,}</td></tr>"
        for k, v in kpi.items())
    KPI_DIV = (f"<div class='card' style='grid-column: span 2;'>"
               f"<h3>Key Metrics</h3><table style='width:100%; border-collapse:collapse;'>{rows}</table></div>")
except Exception:
    KPI_DIV = ""

# ─────────────────────────────────────────────────────────────────────────
# 5.  Assemble HTML
# ─────────────────────────────────────────────────────────────────────────

def _plot_div(fig: Any) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": True, "displaylogo": False})

cards_html = []
if KPI_DIV:
    cards_html.append(KPI_DIV)

for i, (fig, full) in enumerate(figs):
    span = "2" if (i == 0 and full) else "1"
    cards_html.append(f"<div class='card' style='grid-column:span {span}'>{_plot_div(fig)}</div>")

THEME = CFG["theme"]
html = f"""
<!DOCTYPE html><html lang='en'><head>
<meta charset='utf-8'><title>{CFG['dashboard_title']}</title>
<script src='https://cdn.plot.ly/plotly-2.26.0.min.js'></script>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:{THEME['page_bg']}}}
 header{{background:{THEME['header_bg']};color:#fff;padding:1rem 2rem}}
 h1{{margin:0;font-size:1.75rem}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;padding:1.5rem}}
 .card{{background:{THEME['card_bg']};border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.1);padding:1.25rem}}
 @media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>{CFG['dashboard_title']}</h1></header>
<section class='grid'>
 {''.join(cards_html)}
</section></body></html>
"""

# ─────────────────────────────────────────────────────────────────────────
# 6.  Write outputs (HTML + optional PNG)
# ─────────────────────────────────────────────────────────────────────────
html_path = OUT_DIR / f"{CFG['output_name']}.html"
png_path  = OUT_DIR / f"{CFG['output_name']}.png"
html_path.write_text(html, encoding="utf-8")
print("✓", html_path.relative_to(PROJECT_ROOT))

# save PNG if selenium is available --------------------------------------

def save_png(src_html: Path, dst_png: Path, width=1600, height=900, delay=2):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        opts = Options(); opts.add_argument("--headless=new");
        opts.add_argument("--window-size=%d,%d" % (width, height))
        opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox")
        drv = webdriver.Chrome(options=opts)
        drv.get("file://" + src_html.resolve().as_posix())
        time.sleep(delay)  # allow Plotly CDN to load
        full_h = drv.execute_script("return document.body.scrollHeight")
        drv.set_window_size(width, full_h)
        drv.save_screenshot(str(dst_png)); drv.quit()
        print("✓", dst_png.relative_to(PROJECT_ROOT))
    except Exception as e:
        print("⚠  PNG not created:", e)

save_png(html_path, png_path)

# ─────────────────────────────────────────────────────────────────────────
# 7.  Auto‑open in browser unless --no-browser flag
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__" and "--no-browser" not in sys.argv:
    import webbrowser
    webbrowser.open(html_path.as_uri())
