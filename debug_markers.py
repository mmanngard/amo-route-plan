#!/usr/bin/env python3
"""
Debug script to test marker visibility.
"""

from pathlib import Path
from src.route_planner import Fairway, RoutePlan, Visualization

def debug_markers():
    """Debug marker visibility issues."""
    
    print("Debugging Marker Visibility")
    print("=" * 35)
    
    # Test coordinates
    START = (21.7070, 60.1916)
    END = (21.7877, 60.2272)
    
    print(f"Start coordinates: {START}")
    print(f"End coordinates: {END}")
    
    try:
        # Create fairway
        print("\n1. Creating fairway...")
        fairway = Fairway(
            Path("data/fairway.geojson"), 
            spacing_m=200.0, 
            connectivity=8,
            fairway_multipliers={}
        )
        
        # Plan route
        print("\n2. Planning route...")
        route_planner = RoutePlan(fairway)
        path, length_m = route_planner.find_route(*START, *END)
        print(f"   Route length: {length_m:,.0f} m, {len(path)} steps")
        
        # Export route
        print("\n3. Exporting route...")
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        route_file = data_dir / "debug_route.geojson"
        route_planner.export_route_geojson(path, route_file)
        print(f"   Route saved: {route_file}")
        
        # Test marker creation directly
        print("\n4. Testing marker creation...")
        viz = Visualization(fairway, Path("data/fairway.geojson"), route_file)
        
        # Create a simple map with just markers
        import folium
        
        # Create map centered on start point
        m = folium.Map(
            location=[START[1], START[0]],  # lat, lon
            zoom_start=15,  # Higher zoom to see markers clearly
            tiles="OpenStreetMap"
        )
        
        # Add markers directly
        folium.Marker(
            [START[1], START[0]], 
            popup=f"Start<br>Lon: {START[0]:.6f}<br>Lat: {START[1]:.6f}", 
            icon=folium.Icon(color="green", icon="play", prefix="fa"),
            tooltip="Start Point"
        ).add_to(m)
        
        folium.Marker(
            [END[1], END[0]], 
            popup=f"End<br>Lon: {END[0]:.6f}<br>Lat: {END[1]:.6f}", 
            icon=folium.Icon(color="red", icon="stop", prefix="fa"),
            tooltip="End Point"
        ).add_to(m)
        
        # Save debug map
        debug_map = Path("debug_markers.html")
        m.save(debug_map)
        print(f"   Debug map saved: {debug_map}")
        
        # Now test the full visualization
        print("\n5. Testing full visualization...")
        full_map = Path("debug_full_map.html")
        success = viz.create_and_save_map(START, END, full_map)
        
        if success:
            print(f"   ✓ Full map created: {full_map}")
            print(f"   ✓ Check both maps for marker visibility")
            print(f"   ✓ Debug map should show markers clearly")
            print(f"   ✓ Full map should show all layers")
        else:
            print("   ✗ Full map creation failed")
        
        print("\n" + "=" * 35)
        print("Debug completed!")
        print("\nCheck these files:")
        print(f"• {debug_map} - Simple map with just markers")
        print(f"• {full_map} - Full map with all layers")
        print("\nIf markers are visible in debug_map but not full_map,")
        print("there might be a layer ordering or visibility issue.")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_markers()
