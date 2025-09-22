# src/route_planner.py
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple, Dict

import networkx as nx
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree
from pyproj import Transformer

# ---------- Config / paths ----------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FAIRWAY_FILE = DATA_DIR / "fairway.geojson"
GRAPHML_OUT = DATA_DIR / "fairway_grid.graphml"
ROUTE_OUT = DATA_DIR / "route.geojson"

SRC_CRS = "EPSG:4326"   # your GeoJSON lon/lat
METRIC_CRS = "EPSG:3857"  # Web Mercator (meters), good enough for routing over city/regional scales


# ---------- Helpers ----------
def read_fairways(path: Path) -> MultiPolygon:
    """Read polygons from a GeoJSON file (CRS: EPSG:4326)."""
    gj = json.loads(path.read_text(encoding="utf-8"))
    polys = []
    for f in gj.get("features", []):
        geom = shape(f["geometry"])  # shapely geometry in lon/lat
        if isinstance(geom, (Polygon, MultiPolygon)):
            polys.append(geom)
    if not polys:
        raise ValueError("No Polygon/MultiPolygon features found in GeoJSON.")
    return unary_union(polys)  # MultiPolygon or Polygon


def project_geom(geom: BaseGeometry, src: str, dst: str) -> BaseGeometry:
    """Project a shapely geometry between CRSs."""
    transformer = Transformer.from_crs(src, dst, always_xy=True)
    return shapely_transform(transformer.transform, geom)


def shapely_transform(func, geom: BaseGeometry) -> BaseGeometry:
    """Apply a coordinate function (x,y -> x',y') to all coords in a shapely geometry."""
    # Local import to avoid requiring shapely.ops for users that already have it
    from shapely.ops import transform as _transform
    return _transform(func, geom)


@dataclass(frozen=True)
class GridSpec:
    spacing_m: float = 200.0  # grid spacing in meters
    connectivity: int = 8     # 4 or 8

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


def build_grid_graph(
    fairway_m: BaseGeometry,
    grid: GridSpec,
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



def to_lonlat_dict(xy_m: Dict[Tuple[int, int], Tuple[float, float]]) -> Dict[Tuple[int, int], Tuple[float, float]]:
    """Inverse project x,y meters to lon,lat for export/visualization."""
    to_ll = Transformer.from_crs(METRIC_CRS, SRC_CRS, always_xy=True).transform
    return {k: to_ll(x, y) for k, (x, y) in xy_m.items()}


def nearest_node_xy(G: nx.Graph, xy: Dict[Tuple[int, int], Tuple[float, float]], x: float, y: float):
    """Find nearest grid node in projected (meter) coords."""
    # Simple linear scan; for large graphs you could build a KDTree
    best = None
    best_d2 = float("inf")
    for n, (nxm, nym) in xy.items():
        d2 = (nxm - x) ** 2 + (nym - y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = n
    return best


def shortest_path_between(
    G: nx.Graph,
    xy_m: Dict[Tuple[int, int], Tuple[float, float]],
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
) -> Tuple[Iterable[Tuple[int, int]], float]:
    """Compute a shortest path in meters between two lon/lat points snapped to the nearest grid nodes."""
    fwd = Transformer.from_crs(SRC_CRS, METRIC_CRS, always_xy=True).transform
    s_x, s_y = fwd(start_lon, start_lat)
    t_x, t_y = fwd(end_lon, end_lat)

    s = nearest_node_xy(G, xy_m, s_x, s_y)
    t = nearest_node_xy(G, xy_m, t_x, t_y)
    if s is None or t is None:
        raise RuntimeError("Could not snap start/end to the navigable grid. Are they inside the fairway?")

    # A* with Euclidean heuristic in meters
    def h(u, v):
        ux, uy = xy_m[u]
        vx, vy = xy_m[v]
        return ((ux - vx) ** 2 + (uy - vy) ** 2) ** 0.5

    path = nx.astar_path(G, s, t, heuristic=h, weight="weight")
    length = nx.path_weight(G, path, weight="weight")
    return path, length


def path_to_geojson(
    path: Iterable[Tuple[int, int]],
    xy_m: Dict[Tuple[int, int], Tuple[float, float]],
    out_path: Path,
) -> None:
    """Write a path (sequence of grid nodes) to a GeoJSON LineString in lon/lat."""
    to_ll = Transformer.from_crs(METRIC_CRS, SRC_CRS, always_xy=True).transform
    coords_ll = [to_ll(*xy_m[n]) for n in path]
    gj = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "grid_route", "crs": SRC_CRS},
            "geometry": {"type": "LineString", "coordinates": coords_ll},
        }],
    }
    out_path.write_text(json.dumps(gj, ensure_ascii=False, indent=2), encoding="utf-8")

def path_coords_lonlat(
    path: list[tuple[int, int]],
    xy_m: dict[tuple[int, int], tuple[float, float]],
    src_crs: str = SRC_CRS,
    metric_crs: str = METRIC_CRS,
) -> list[tuple[float, float]]:
    """Return the route as a list of (lon, lat) coords."""
    to_ll = Transformer.from_crs(metric_crs, src_crs, always_xy=True).transform
    return [to_ll(*xy_m[n]) for n in path]
    
# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Discretize fairways to a grid and build a NetworkX graph.")
    p.add_argument("--spacing", type=float, default=200.0, help="Grid spacing in meters (default: 200)")
    p.add_argument("--connectivity", type=int, default=8, choices=[4, 8], help="Grid connectivity (4 or 8)")
    p.add_argument("--start", type=str, default=None, help="Start lon,lat (e.g. 21.70,60.20)")
    p.add_argument("--end", type=str, default=None, help="End lon,lat (e.g. 21.89,60.26)")
    p.add_argument("--export-graphml", action="store_true", help="Save the graph as GraphML to data/")
    p.add_argument("--export-route", action="store_true", help="Save the computed route (if any) to data/route.geojson")
    return p.parse_args()


def main():
    args = parse_args()

    # 1) Read fairways in lon/lat, project to meters
    fair_ll = read_fairways(FAIRWAY_FILE)
    fair_m = project_geom(fair_ll, SRC_CRS, METRIC_CRS)

    # 2) Build the grid graph
    grid = GridSpec(spacing_m=args.spacing, connectivity=args.connectivity)
    G, xy_m = build_grid_graph(fair_m, grid)

    print(f"Built grid graph with {G.number_of_nodes():,} nodes and {G.number_of_edges():,} edges "
          f"(spacing={args.spacing} m, connectivity={args.connectivity}).")

    # 3) Optionally export graph
    if args.export_graphml:
        # Store lon/lat on nodes for convenience
        to_ll = Transformer.from_crs(METRIC_CRS, SRC_CRS, always_xy=True).transform
        for n in G.nodes:
            x, y = xy_m[n]
            lon, lat = to_ll(x, y)
            G.nodes[n]["lon"] = float(lon)
            G.nodes[n]["lat"] = float(lat)
        nx.write_graphml(G, GRAPHML_OUT)
        print(f"Saved graph to {GRAPHML_OUT}")

    # 4) Optional routing if start/end provided
    if args.start and args.end:
        try:
            s_lon, s_lat = (float(v) for v in args.start.split(","))
            e_lon, e_lat = (float(v) for v in args.end.split(","))
        except Exception:
            raise SystemExit("Start/End must be 'lon,lat' (e.g. --start 21.70,60.20 --end 21.88,60.26)")

        path, length_m = shortest_path_between(G, xy_m, s_lon, s_lat, e_lon, e_lat)
        print(f"Shortest path length: {length_m:,.0f} m over {len(list(path))} grid nodes.")

        if args.export_route:
            path_to_geojson(path, xy_m, ROUTE_OUT)
            print(f"Saved route to {ROUTE_OUT}")


if __name__ == "__main__":
    # Avoid slow imports at module import-time in other contexts
    import shapely  # noqa: F401 (ensures shapely is present)
    main()
