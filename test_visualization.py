#!/usr/bin/env python3
"""
Test script to demonstrate the fairway multiplier visualization.
This script shows how the system works without running the full main.py.
"""

from pathlib import Path
from src.route_planner import Fairway, RoutePlan, Visualization

def test_multiplier_visualization():
    """Test the multiplier visualization functionality."""
    
    # Test coordinates
    START = (21.7070, 60.1916)
    END = (21.7877, 60.2272)
    
    # Test multipliers
    test_multipliers = {
        111930: 1.0,  # Normal cost
        111938: 2.0,  # 2x more expensive (should be red)
        154835: 0.5,  # Half cost (should be green)
    }
    
    print("Testing Fairway Multiplier Visualization")
    print("=" * 50)
    
    # Test 1: Uniform weights
    print("\n1. Creating fairway with uniform weights...")
    fairway_uniform = Fairway(
        Path("data/fairway.geojson"), 
        spacing_m=200.0, 
        connectivity=8,
        fairway_multipliers={}
    )
    print(f"   Fairway areas loaded: {len(fairway_uniform.fairway_features)}")
    print(f"   Multipliers set: {len(fairway_uniform.fairway_multipliers)}")
    
    # Test 2: Weighted areas
    print("\n2. Creating fairway with weighted areas...")
    fairway_weighted = Fairway(
        Path("data/fairway.geojson"), 
        spacing_m=200.0, 
        connectivity=8,
        fairway_multipliers=test_multipliers
    )
    print(f"   Fairway areas loaded: {len(fairway_weighted.fairway_features)}")
    print(f"   Multipliers set: {len(fairway_weighted.fairway_multipliers)}")
    print(f"   Multiplier values: {fairway_weighted.fairway_multipliers}")
    
    # Test 3: Check multiplier assignment
    print("\n3. Testing multiplier assignment...")
    for feature in fairway_weighted.fairway_features:
        fairway_id = feature["properties"].get("id")
        if fairway_id:
            multiplier = fairway_weighted.fairway_multipliers.get(fairway_id, 1.0)
            if multiplier < 1.0:
                color = "GREEN (preferred)"
            elif multiplier == 1.0:
                color = "BLUE (normal)"
            else:
                color = "RED (avoided)"
            print(f"   Fairway {fairway_id}: multiplier={multiplier} -> {color}")
    
    # Test 4: Route planning
    print("\n4. Testing route planning...")
    try:
        route_planner_uniform = RoutePlan(fairway_uniform)
        path_uniform, length_uniform = route_planner_uniform.find_route(*START, *END)
        print(f"   Uniform route: {length_uniform:,.0f} m, {len(path_uniform)} steps")
        
        route_planner_weighted = RoutePlan(fairway_weighted)
        path_weighted, length_weighted = route_planner_weighted.find_route(*START, *END)
        print(f"   Weighted route: {length_weighted:,.0f} m, {len(path_weighted)} steps")
        
        if length_uniform != length_weighted:
            diff = length_weighted - length_uniform
            pct = (diff / length_uniform) * 100
            print(f"   Difference: {diff:+.0f} m ({pct:+.1f}%)")
        else:
            print("   Routes are identical!")
            
    except Exception as e:
        print(f"   Route planning error: {e}")
    
    # Test 5: Visualization setup
    print("\n5. Testing visualization setup...")
    try:
        # Create test route files
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        uniform_route_file = data_dir / "test_uniform_route.geojson"
        weighted_route_file = data_dir / "test_weighted_route.geojson"
        
        if 'path_uniform' in locals():
            route_planner_uniform.export_route_geojson(path_uniform, uniform_route_file)
            print(f"   Created uniform route file: {uniform_route_file}")
        
        if 'path_weighted' in locals():
            route_planner_weighted.export_route_geojson(path_weighted, weighted_route_file)
            print(f"   Created weighted route file: {weighted_route_file}")
        
        # Test visualization creation
        viz = Visualization(fairway_weighted, Path("data/fairway.geojson"), weighted_route_file)
        print("   Visualization object created successfully")
        
        # Test comparison map creation (without actually creating the file)
        print("   Comparison map method available")
        
    except Exception as e:
        print(f"   Visualization error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed! The system is ready for visualization.")
    print("\nTo create the actual map, run:")
    print("  python main.py")
    print("\nThis will create route_map.html with both routes and colored fairways.")

if __name__ == "__main__":
    test_multiplier_visualization()
