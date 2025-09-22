# src/route_planner.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, Dict, Literal

import networkx as nx
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree
from pyproj import Transformer


@dataclass(frozen=True)
class GridSpec:
    spacing_m: float = 200.0  # grid spacing in meters
    connectivity: Literal[4, 8] = 8     # 4 or 8

    def neighbors(self) -> Iterable[Tuple[int, int, float]]:
        """Return neighbor relative offsets and their step cost multipliers (1 for N/E/S/W, sqrt(2) for diagonals)."""
        if self.connectivity == 4:
            return [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0)]
        elif self.connectivity == 8:
            return [
                (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                (-1, -1, 2**0.5), (-1, 1, 2**0.5), (1, -1, 2**0.5), (1, 1, 2**0.5)
            ]
        else:
            raise ValueError("connectivity must be 4 or 8")


class Fairway:
    """Main class for managing fairway data, grid generation, and routing operations."""
    
    # Class constants
    SRC_CRS = "EPSG:4326"   # GeoJSON lon/lat
    METRIC_CRS = "EPSG:3857"  # Web Mercator (meters)
    
    def __init__(self, fairway_path: Path, spacing_m: float = 200.0, connectivity: int = 8):
        """
        Initialize a Fairway instance.
        
        Args:
            fairway_path: Path to the GeoJSON fairway file
            spacing_m: Grid spacing in meters
            connectivity: Grid connectivity (4 or 8)
        """
        self.fairway_path = fairway_path
        self.fairway_ll = self._load_fairway()
        self.fairway_m = self._project_geom(self.fairway_ll, self.SRC_CRS, self.METRIC_CRS)
        self.grid = GridSpec(spacing_m=spacing_m, connectivity=connectivity)
        self.G, self.xy_m = self._get_grid_graph(self.fairway_m, self.grid)

    def _load_fairway(self) -> MultiPolygon:
        """Read polygons from a GeoJSON file (CRS: EPSG:4326)."""
        gj = json.loads(self.fairway_path.read_text(encoding="utf-8"))
        polys = []
        for f in gj.get("features", []):
            geom = shape(f["geometry"])  # shapely geometry in lon/lat
            if isinstance(geom, (Polygon, MultiPolygon)):
                polys.append(geom)
        if not polys:
            raise ValueError("No Polygon/MultiPolygon features found in GeoJSON.")
        return unary_union(polys)  # MultiPolygon or Polygon

    def _project_geom(self, geom: BaseGeometry, src: str, dst: str) -> BaseGeometry:
        """Project a shapely geometry between CRSs."""
        transformer = Transformer.from_crs(src, dst, always_xy=True)
        return self._apply_coord_transform(transformer.transform, geom)

    def _apply_coord_transform(self, coord_func, geom: BaseGeometry) -> BaseGeometry:
        """
        Apply a coordinate transformation function to all coordinates in a shapely geometry.

        Args:
            coord_func: Function that takes (x, y) and returns (x', y')
            geom: Shapely geometry to transform

        Returns:
            Transformed shapely geometry
        """
        from shapely.ops import transform as shapely_transform
        return shapely_transform(coord_func, geom)

    def _get_grid_graph(
        self, fairway_m: BaseGeometry, grid: GridSpec
) -> Tuple[nx.Graph, Dict[Tuple[int, int], Tuple[float, float]]]:
        """
        Discretize the fairway polygon(s) in metric coordinates (meters) into a grid graph.
        Returns:
            G: networkx.Graph where nodes are (i,j) grid indices; edges weighted by meters
            xy: dict mapping (i,j) -> (x_m, y_m) projected coordinates
        """
        # Bounding box (meters)
        minx, miny, maxx, maxy = fairway_m.bounds

        # Build integer grid index ranges
        nx_cells = int((maxx - minx) // grid.spacing_m) + 1
        ny_cells = int((maxy - miny) // grid.spacing_m) + 1

        # Prepared geometry for fast point-in-polygon checks
        prepared = prep(fairway_m)

        # STRtree of polygon(s) for quick reject (speeds up for many polygons)
        geometries = [fairway_m] if isinstance(fairway_m, Polygon) else list(fairway_m.geoms)
        tree = STRtree(geometries)

        # Create nodes for cells whose centers lie inside (or on boundary of) the fairway
        xy: Dict[Tuple[int, int], Tuple[float, float]] = {}
        for i in range(nx_cells + 1):
            x = minx + i * grid.spacing_m
            for j in range(ny_cells + 1):
                y = miny + j * grid.spacing_m
                pt = Point(x, y)

                # Quick reject using spatial index (Shapely 2.x returns a NumPy array)
                cand = tree.query(pt)
                if len(cand) == 0:
                    continue

                # Use covers() to include boundary points (contains() would exclude them)
                if prepared.covers(pt):
                    xy[(i, j)] = (x, y)

        # Build the graph
        G = nx.Graph()
        for node, (x, y) in xy.items():
            G.add_node(node, x=x, y=y)

        # Add edges to neighbors that also exist
        for (i, j), (x, y) in xy.items():
            for di, dj, mult in grid.neighbors():
                nb = (i + di, j + dj)
                if nb in xy and not G.has_edge((i, j), nb):
                    # Euclidean distance in meters based on spacing and multiplier
                    dist = grid.spacing_m * mult
                    G.add_edge((i, j), nb, weight=dist)

        return G, xy

    def to_lonlat_dict(self, xy_m: Dict[Tuple[int, int], Tuple[float, float]]) -> Dict[Tuple[int, int], Tuple[float, float]]:
        """Inverse project x,y meters to lon,lat for export/visualization."""
        to_ll = Transformer.from_crs(self.METRIC_CRS, self.SRC_CRS, always_xy=True).transform
        return {k: to_ll(x, y) for k, (x, y) in xy_m.items()}

    def path_to_geojson(self, path: Iterable[Tuple[int, int]], out_path: Path) -> None:
        """Write a path (sequence of grid nodes) to a GeoJSON LineString in lon/lat."""
        to_ll = Transformer.from_crs(self.METRIC_CRS, self.SRC_CRS, always_xy=True).transform
        coords_ll = [to_ll(*self.xy_m[n]) for n in path]
        gj = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "grid_route", "crs": self.SRC_CRS},
                "geometry": {"type": "LineString", "coordinates": coords_ll},
            }],
        }
        out_path.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")

    def path_coords_lonlat(self, path: list[tuple[int, int]]) -> list[tuple[float, float]]:
        """Return the route as a list of (lon, lat) coords."""
        to_ll = Transformer.from_crs(self.METRIC_CRS, self.SRC_CRS, always_xy=True).transform
        return [to_ll(*self.xy_m[n]) for n in path]

    def export_graphml(self, out_path: Path) -> None:
        """Export the grid graph as GraphML with lon/lat coordinates."""
        # Store lon/lat on nodes for convenience
        to_ll = Transformer.from_crs(self.METRIC_CRS, self.SRC_CRS, always_xy=True).transform
        for n in self.G.nodes:
            x, y = self.xy_m[n]
            lon, lat = to_ll(x, y)
            self.G.nodes[n]["lon"] = float(lon)
            self.G.nodes[n]["lat"] = float(lat)
        nx.write_graphml(self.G, out_path)

    def get_stats(self) -> Dict[str, int]:
        """Get basic statistics about the grid graph."""
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "spacing_m": self.grid.spacing_m,
            "connectivity": self.grid.connectivity
        }


class RoutePlan:
    """Handles route planning and optimization using fairway data."""
    
    def __init__(self, fairway: Fairway):
        """
        Initialize route planner with fairway data.
        
        Args:
            fairway: Fairway instance containing grid and routing data
        """
        self.fairway = fairway

    def _nearest_node_xy(self, x: float, y: float):
        """Find nearest grid node in projected (meter) coords."""
        # Simple linear scan; for large graphs you could build a KDTree
        best = None
        best_d2 = float("inf")
        for n, (nxm, nym) in self.fairway.xy_m.items():
            d2 = (nxm - x) ** 2 + (nym - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = n
        return best

    def shortest_path_between(
            self, start_lon: float, start_lat: float, end_lon: float, end_lat: float
    ) -> Tuple[Iterable[Tuple[int, int]], float]:
        """Compute a shortest path in meters between two lon/lat points snapped to the nearest grid nodes."""
        fwd = Transformer.from_crs(self.fairway.SRC_CRS, self.fairway.METRIC_CRS, always_xy=True).transform
        s_x, s_y = fwd(start_lon, start_lat)
        t_x, t_y = fwd(end_lon, end_lat)

        s = self._nearest_node_xy(s_x, s_y)
        t = self._nearest_node_xy(t_x, t_y)
        if s is None or t is None:
            raise RuntimeError("Could not snap start/end to the navigable grid. Are they inside the fairway?")

        # A* with Euclidean heuristic in meters
        def h(u, v):
            ux, uy = self.fairway.xy_m[u]
            vx, vy = self.fairway.xy_m[v]
            return ((ux - vx) ** 2 + (uy - vy) ** 2) ** 0.5

        path = nx.astar_path(self.fairway.G, s, t, heuristic=h, weight="weight")
        length = nx.path_weight(self.fairway.G, path, weight="weight")
        return path, length

    def find_route(self, start_lon: float, start_lat: float, end_lon: float, end_lat: float) -> tuple[list[tuple[int, int]], float]:
        """
        Find the shortest route between two coordinates.
        
        Args:
            start_lon: Start longitude
            start_lat: Start latitude
            end_lon: End longitude
            end_lat: End latitude
            
        Returns:
            Tuple of (path, length_m) where path is list of grid nodes and length_m is distance in meters
        """
        path, length_m = self.shortest_path_between(start_lon, start_lat, end_lon, end_lat)
        return list(path), length_m

    def export_route_geojson(self, path: list[tuple[int, int]], output_path: Path) -> None:
        """Export route as GeoJSON file."""
        self.fairway.path_to_geojson(path, output_path)

    def export_route_csv(self, path: list[tuple[int, int]], output_path: Path) -> None:
        """Export route coordinates as CSV file."""
        from csv import writer
        coords_ll = self.fairway.path_coords_lonlat(path)
        with output_path.open("w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["lon", "lat"])
            w.writerows(coords_ll)

    def get_route_coordinates(self, path: list[tuple[int, int]]) -> list[tuple[float, float]]:
        """Get route coordinates as list of (lon, lat) tuples."""
        return self.fairway.path_coords_lonlat(path)

    def plan_and_export(self, start_coords: tuple[float, float], end_coords: tuple[float, float], 
                    geojson_path: Path, csv_path: Path) -> tuple[list[tuple[int, int]], float]:
        """
        Plan route and export to both GeoJSON and CSV formats.
        
        Args:
            start_coords: (lon, lat) of start point
            end_coords: (lon, lat) of end point
            geojson_path: Path to save GeoJSON route
            csv_path: Path to save CSV route
            
        Returns:
            Tuple of (path, length_m)
        """
        start_lon, start_lat = start_coords
        end_lon, end_lat = end_coords
        
        # Find route
        path, length_m = self.find_route(start_lon, start_lat, end_lon, end_lat)
        
        # Export formats
        self.export_route_geojson(path, geojson_path)
        self.export_route_csv(path, csv_path)
        
        return path, length_m

class Visualization:
    """Handles all visualization-related functionality for fairway routing."""
    
    def __init__(self, fairway: Fairway, fairway_file: Path, route_file: Path):
        """
        Initialize visualization with fairway data and file paths.
        
        Args:
            fairway: Fairway instance containing grid and routing data
            fairway_file: Path to the original fairway GeoJSON file
            route_file: Path to the route GeoJSON file
        """
        self.fairway = fairway
        self.fairway_file = fairway_file
        self.route_file = route_file

    def export_route_csv(self, path: list[tuple[int, int]], output_path: Path) -> None:
        """Export route coordinates as CSV file."""
        from csv import writer
        coords_ll = self.fairway.path_coords_lonlat(path)
        with output_path.open("w", newline="", encoding="utf-8") as f:
            w = writer(f)
            w.writerow(["lon", "lat"])
            w.writerows(coords_ll)

    def create_folium_map(self, start_coords: tuple[float, float], end_coords: tuple[float, float], 
                         output_path: Path, show_grid: bool = False) -> None:
        """
        Create an interactive Folium map with fairways, route, and optional grid.
        
        Args:
            start_coords: (lon, lat) of start point
            end_coords: (lon, lat) of end point  
            output_path: Path to save the HTML map
            show_grid: Whether to show grid nodes layer
        """
        try:
            import folium
            import json
            from pyproj import Transformer
        except ImportError as e:
            raise ImportError(f"Folium not available: {e}")

        s_lon, s_lat = start_coords
        e_lon, e_lat = end_coords

        # Set up map centered between start and end
        m = folium.Map(
            location=[(s_lat + e_lat) / 2, (s_lon + e_lon) / 2],
            zoom_start=11, 
            tiles="OpenStreetMap"
        )

        # Add fairways layer
        self._add_fairways_layer(m)

        # Add route layer
        self._add_route_layer(m)

        # Add grid layer if requested
        if show_grid:
            self._add_grid_layer(m)

        # Add layer control
        folium.LayerControl().add_to(m)

        # Save map
        m.save(output_path)

    def _add_fairways_layer(self, map_obj) -> None:
        """Add fairways as a GeoJSON layer to the map."""
        import folium
        import json
        
        fairways_layer = folium.FeatureGroup(name="Fairways", show=True)
        fairways_layer.add_child(folium.GeoJson(
            json.load(open(self.fairway_file, encoding="utf-8"))
        ))
        fairways_layer.add_to(map_obj)

    def _add_route_layer(self, map_obj) -> None:
        """Add route as a GeoJSON layer to the map."""
        import folium
        import json
        
        route_layer = folium.FeatureGroup(name="Route", show=True)
        route_layer.add_child(folium.GeoJson(
            json.load(open(self.route_file, encoding="utf-8")),
            style_function=lambda f: {"color": "red", "weight": 5}
        ))
        route_layer.add_to(map_obj)

    def _add_grid_layer(self, map_obj) -> None:
        """Add grid nodes as circle markers to the map."""
        import folium
        from pyproj import Transformer
        
        transformer = Transformer.from_crs(
            self.fairway.METRIC_CRS, 
            self.fairway.SRC_CRS, 
            always_xy=True
        )
        grid_lonlat = [transformer.transform(x, y) for (x, y) in self.fairway.xy_m.values()]

        grid_layer = folium.FeatureGroup(name=f"Grid nodes ({len(grid_lonlat)})", show=False)

        for lon, lat in grid_lonlat:
            folium.CircleMarker(
                location=[lat, lon],
                radius=1,
                color="blue",
                fill=True,
                fill_opacity=0.6,
                weight=0
            ).add_to(grid_layer)

        grid_layer.add_to(map_obj)

    def create_simple_map(self, start_coords: tuple[float, float], end_coords: tuple[float, float], 
                         output_path: Path) -> None:
        """Create a simple map with just fairways and route (no grid)."""
        self.create_folium_map(start_coords, end_coords, output_path, show_grid=False)

    def create_detailed_map(self, start_coords: tuple[float, float], end_coords: tuple[float, float], 
                           output_path: Path) -> None:
        """Create a detailed map with fairways, route, and grid nodes."""
        self.create_folium_map(start_coords, end_coords, output_path, show_grid=True)

    def create_and_save_map(self, start_coords: tuple[float, float], end_coords: tuple[float, float], 
                           output_path: Path) -> bool:
        """
        Create and save an interactive map with error handling.
        
        Args:
            start_coords: (lon, lat) of start point
            end_coords: (lon, lat) of end point  
            output_path: Path to save the HTML map
            
        Returns:
            True if map was created successfully, False otherwise
        """
        try:
            self.create_simple_map(start_coords, end_coords, output_path)
            return True
        except Exception as e:
            print(f"(Skipping HTML preview) {e}")
            return False


