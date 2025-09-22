# main.py (project root)

from pathlib import Path
import sys
from src.route_planner import Fairway, RoutePlan, Visualization

# ensure we can import from src/
ROOT = Path(__file__).resolve().parent

# --- config: edit these values for quick tests ---
START = (21.7070, 60.1916)   # (lon, lat)
END   = (21.7877, 60.2272)   # (lon, lat)
GRID_SPACING_M = 50.0   # meters; larger = fewer nodes/faster

# Fairway multipliers - higher values make areas more expensive to traverse
# Example: make some areas 2x more expensive (multiplier=2.0) or half as expensive (multiplier=0.5)
FAIRWAY_MULTIPLIERS = {
    111930: 1.0,  # Normal cost
    111938: 99.0,  # 2x more expensive
    111930: 99.0,
    246342: 99.0,
    246318: 0.5,  # Half cost (preferred)
    # Add more fairway IDs and multipliers as needed
}

DATA_DIR = ROOT / "data"
FAIRWAY_FILE = DATA_DIR / "fairway.geojson"
ROUTE_FILE = DATA_DIR / "route.geojson"

MAP_FILE = ROOT / "route_map.html"

def main():
    if not FAIRWAY_FILE.exists():
        raise SystemExit(f"Missing fairway file: {FAIRWAY_FILE}")

    # Create Fairway instance with multipliers and build grid
    fairway = Fairway(FAIRWAY_FILE, spacing_m=GRID_SPACING_M, connectivity=8, 
                     fairway_multipliers=FAIRWAY_MULTIPLIERS)
    
    stats = fairway.get_stats()
    print(f"Grid built → nodes: {stats['nodes']:,}, edges: {stats['edges']:,} "
          f"(spacing={stats['spacing_m']:g} m)")
    
    if FAIRWAY_MULTIPLIERS:
        print(f"Using fairway multipliers: {FAIRWAY_MULTIPLIERS}")
    else:
        print("No fairway multipliers set - using uniform costs")

    if stats['nodes'] == 0:
        raise SystemExit("No navigable grid nodes were created. Increase spacing or check fairway geometry.")

    # Create route planner and plan route
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    route_planner = RoutePlan(fairway)
    
    # Plan route and export to both formats
    csv_path = DATA_DIR / "route.csv"
    path, length_m = route_planner.plan_and_export(START, END, ROUTE_FILE, csv_path)
    print(f"A* result → length: {length_m:,.0f} m, steps: {len(path)}")
    print(f"Saved GeoJSON route → {ROUTE_FILE}")
    print(f"Saved CSV route → {csv_path}")

    # Create visualization
    viz = Visualization(fairway, FAIRWAY_FILE, ROUTE_FILE)
    if viz.create_and_save_map(START, END, MAP_FILE):
        print(f"Saved HTML preview → {MAP_FILE}")

if __name__ == "__main__":
    main()
