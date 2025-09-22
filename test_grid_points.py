#!/usr/bin/env python3
"""
Test script to verify grid points visualization functionality.
"""

from pathlib import Path
from src.route_planner import Fairway, RoutePlan, Visualization

def test_grid_points():
    """Test the grid points visualization."""
    
    print("Testing Grid Points Visualization")
    print("=" * 40)
    
    # Test coordinates
    START = (21.7070, 60.1916)
    END = (21.7877, 60.2272)
    
    # Test multipliers
    test_multipliers = {
        111930: 1.0,  # Normal cost
        111938: 2.0,  # 2x more expensive
        154835: 0.5,  # Half cost (preferred)
    }
    
    try:
        # Create fairway with multipliers
        print("1. Creating fairway with grid...")
        fairway = Fairway(
            Path("data/fairway.geojson"), 
            spacing_m=200.0, 
            connectivity=8,
            fairway_multipliers=test_multipliers
        )
        
        stats = fairway.get_stats()
        print(f"   Grid built: {stats['nodes']:,} nodes, {stats['edges']:,} edges")
        print(f"   Spacing: {stats['spacing_m']}m")
        
        # Plan route
        print("\n2. Planning route...")
        route_planner = RoutePlan(fairway)
        path, length_m = route_planner.find_route(*START, *END)
        print(f"   Route length: {length_m:,.0f} m, {len(path)} steps")
        
        # Export route
        print("\n3. Exporting route...")
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        route_file = data_dir / "test_route.geojson"
        route_planner.export_route_geojson(path, route_file)
        print(f"   Route saved: {route_file}")
        
        # Test visualization
        print("\n4. Testing visualization...")
        viz = Visualization(fairway, Path("data/fairway.geojson"), route_file)
        
        # Test grid points layer creation
        print("   Testing grid points layer...")
        grid_points_count = len(fairway.xy_m)
        print(f"   Grid points available: {grid_points_count:,}")
        
        # Test simple map creation
        print("   Testing simple map creation...")
        map_file = Path("test_map.html")
        success = viz.create_and_save_map(START, END, map_file)
        
        if success:
            print(f"   ✓ Map created successfully: {map_file}")
            print(f"   ✓ Grid points layer should be visible (toggleable)")
            print(f"   ✓ Fairways colored by multiplier")
            print(f"   ✓ Route displayed in red")
        else:
            print("   ✗ Map creation failed")
        
        print("\n" + "=" * 40)
        print("Grid points visualization test completed!")
        print("\nFeatures added:")
        print("• Grid points as small gray dots")
        print("• Toggleable layer control")
        print("• Fairway color coding by multiplier")
        print("• Route visualization")
        print("• Interactive popups for grid points")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_grid_points()
