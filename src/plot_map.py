from pathlib import Path
import json
import folium

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FAIRWAY_FILE = DATA_DIR / "fairway.geojson"

def draw_fairways_interactive():
    gj = json.loads(FAIRWAY_FILE.read_text(encoding="utf-8"))

    # Compute bounds for fitting map view
    xs, ys = [], []
    for f in gj["features"]:
        g = f["geometry"]
        if g["type"] == "Polygon":
            for ring in g["coordinates"]:
                for x, y in ring:
                    xs.append(x); ys.append(y)
        elif g["type"] == "MultiPolygon":
            for poly in g["coordinates"]:
                for ring in poly:
                    for x, y in ring:
                        xs.append(x); ys.append(y)
    bounds = [[min(ys), min(xs)], [max(ys), max(xs)]]

    # Make folium map centered on fairways
    m = folium.Map(location=[sum(ys)/len(ys), sum(xs)/len(xs)], zoom_start=11, tiles="OpenStreetMap")

    # Add fairways as GeoJSON overlay
    folium.GeoJson(
        gj,
        name="Fairways",
        style_function=lambda feat: {
            "color": "blue",
            "weight": 2,
            "fillOpacity": 0.3,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["id", "tyyppi", "mitoitussyvays", "haraussyvyys"],
            aliases=["ID", "Type", "Design depth", "Dredged depth"]
        )
    ).add_to(m)

    m.fit_bounds(bounds)
    out = Path("fairways_map.html")
    m.save(out)
    print(f"Interactive map saved to {out.resolve()}")

if __name__ == "__main__":
    draw_fairways_interactive()
