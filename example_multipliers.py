#!/usr/bin/env python3
"""
Example script showing how to use fairway area multipliers for route planning.

This demonstrates how different multipliers affect route planning:
- Multiplier < 1.0: Makes areas cheaper to traverse (preferred routes)
- Multiplier = 1.0: Normal cost
- Multiplier > 1.0: Makes areas more expensive to traverse (avoided routes)
"""

from pathlib import Path
from src.route_planner import Fairway, RoutePlan

# Example route
START = (21.7070, 60.1916)   # (lon, lat)
END = (21.7877, 60.2272)     # (lon, lat)

# Different multiplier scenarios
scenarios = {
    "No multipliers (uniform)": {},
    "Prefer deeper areas": {
        154835: 0.5,  # Deeper area (7m design depth) - half cost
        240209: 0.5,  # Deeper area (10m design depth) - half cost
    },
    "Avoid shallow areas": {
        111930: 2.0,  # Shallow area (3m design depth) - double cost
        111938: 2.0,  # Shallow area (3m design depth) - double cost
    },
    "Mixed preferences": {
        154835: 0.5,  # Prefer this area
        111930: 2.0,  # Avoid this area
        111938: 1.5,  # Slightly avoid this area
    }
}

def run_scenario(name: str, multipliers: dict):
    """Run route planning with given multipliers."""
    print(f"\n=== {name} ===")
    print(f"Multipliers: {multipliers if multipliers else 'None (uniform)'}")
    
    # Create fairway with multipliers
    fairway = Fairway(
        Path("data/fairway.geojson"), 
        spacing_m=100.0,  # Larger spacing for faster demo
        connectivity=8,
        fairway_multipliers=multipliers
    )
    
    # Plan route
    route_planner = RoutePlan(fairway)
    path, length_m = route_planner.find_route(*START, *END)
    
    print(f"Route length: {length_m:,.0f} meters")
    print(f"Route steps: {len(path)}")
    
    return length_m

def main():
    print("Fairway Area Multiplier Demo")
    print("=" * 50)
    
    results = {}
    for name, multipliers in scenarios.items():
        try:
            length = run_scenario(name, multipliers)
            results[name] = length
        except Exception as e:
            print(f"Error in {name}: {e}")
            results[name] = None
    
    # Compare results
    print("\n" + "=" * 50)
    print("COMPARISON:")
    print("=" * 50)
    
    valid_results = {k: v for k, v in results.items() if v is not None}
    if valid_results:
        baseline = valid_results.get("No multipliers (uniform)")
        for name, length in valid_results.items():
            if length is not None:
                if baseline and name != "No multipliers (uniform)":
                    diff = length - baseline
                    pct = (diff / baseline) * 100
                    print(f"{name:25}: {length:8,.0f}m ({diff:+.0f}m, {pct:+.1f}%)")
                else:
                    print(f"{name:25}: {length:8,.0f}m")

if __name__ == "__main__":
    main()
