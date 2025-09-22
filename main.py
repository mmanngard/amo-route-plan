# main.py (project root)

#from __future__ import annotations
from pathlib import Path
import sys

# --- config: edit these three values for quick tests ---
START = (21.7070, 60.1916)   # (lon, lat)
END   = (21.7877, 60.2272)   # (lon, lat)
GRID_SPACING_M = 50.0   # meters; larger = fewer nodes/faster
# ensure we can import from src/
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# import your planner (support both rout_planner.py and route_planner.py)
try:
    from route_planner import (  # your file name
        read_fairways, project_geom, build_grid_graph, shortest_path_between,
        path_to_geojson, GridSpec, SRC_CRS, METRIC_CRS,
    )
except ModuleNotFoundError:
    # fallback if the file is actually named route_planner.py
    from route_planner import (
        read_fairways, project_geom, build_grid_graph, shortest_path_between,
        path_to_geojson, GridSpec, SRC_CRS, METRIC_CRS,
    )

DATA_DIR = ROOT / "data"
FAIRWAY_FILE = DATA_DIR / "fairway.geojson"
ROUTE_FILE = DATA_DIR / "route.geojson"

def main():
    if not FAIRWAY_FILE.exists():
        raise SystemExit(f"Missing fairway file: {FAIRWAY_FILE}")

    # config (edit if you like)
    #START = (21.72, 60.21)    # (lon, lat)
    #END   = (21.89, 60.26)    # (lon, lat)
    #GRID_SPACING_M = 200.0

    # 1) load fairways and project to meters
    fair_ll = read_fairways(FAIRWAY_FILE)
    fair_m = project_geom(fair_ll, SRC_CRS, METRIC_CRS)

    # 2) build grid
    grid = GridSpec(spacing_m=GRID_SPACING_M, connectivity=8)
    G, xy_m = build_grid_graph(fair_m, grid)
    print(f"Grid built → nodes: {G.number_of_nodes():,}, edges: {G.number_of_edges():,} "
          f"(spacing={GRID_SPACING_M:g} m)")

    if G.number_of_nodes() == 0:
        raise SystemExit("No navigable grid nodes were created. Increase spacing or check fairway geometry.")

    # 3) run A*
    (s_lon, s_lat), (e_lon, e_lat) = START, END
    path, length_m = shortest_path_between(G, xy_m, s_lon, s_lat, e_lon, e_lat)
    path = list(path)  # materialize generator, if any
    print(f"A* result → length: {length_m:,.0f} m, steps: {len(path)}")

    # 4) export route as GeoJSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path_to_geojson(path, xy_m, ROUTE_FILE)
    print(f"Saved GeoJSON route → {ROUTE_FILE}")

    # 5) also export as CSV of lon,lat
    from csv import writer
    from route_planner import path_coords_lonlat
    coords_ll = path_coords_lonlat(path, xy_m)
    csv_path = DATA_DIR / "route.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = writer(f)
        w.writerow(["lon", "lat"])
        w.writerows(coords_ll)
    print(f"Saved CSV route → {csv_path}")

    # 6) quick Folium map for visual check
    try:
        import folium, json
        from pyproj import Transformer

        # set up map
        m = folium.Map(location=[(s_lat+e_lat)/2, (s_lon+e_lon)/2],
                    zoom_start=11, tiles="OpenStreetMap")

        # --- Fairways layer (always on) ---
        fairways_layer = folium.FeatureGroup(name="Fairways", show=True)
        fairways_layer.add_child(folium.GeoJson(
            json.load(open(FAIRWAY_FILE, encoding="utf-8"))
        ))
        fairways_layer.add_to(m)

        # --- Route layer (toggleable) ---
        route_layer = folium.FeatureGroup(name="Route", show=True)
        route_layer.add_child(folium.GeoJson(
            json.load(open(ROUTE_FILE, encoding="utf-8")),
            style_function=lambda f: {"color": "red", "weight": 5}
        ))
        route_layer.add_to(m)

        # --- Grid nodes layer (toggleable, off by default) ---
        transformer = Transformer.from_crs(METRIC_CRS, SRC_CRS, always_xy=True)
        grid_lonlat = [transformer.transform(x, y) for (x, y) in xy_m.values()]

        grid_layer = folium.FeatureGroup(name=f"Grid nodes ({len(grid_lonlat)})", show=False)

        # draw every node as a tiny circle
        for lon, lat in grid_lonlat:
            folium.CircleMarker(
                location=[lat, lon],
                radius=1,          # pixel size of the dot
                color="blue",
                fill=True,
                fill_opacity=0.6,
                weight=0
            ).add_to(grid_layer)

        grid_layer.add_to(m)

        # add a layer control toggle
        folium.LayerControl().add_to(m)

        map_out = ROOT / "route_map.html"
        m.save(map_out)
        print(f"Saved HTML preview → {map_out}")
    except Exception as e:
        print(f"(Skipping HTML preview) {e}")

if __name__ == "__main__":
    main()
