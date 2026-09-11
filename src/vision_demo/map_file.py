"""Validated JSON maps and axis-aligned road/sidewalk geometry (world metres)."""

from dataclasses import dataclass
import json
import math
from pathlib import Path

from .buildings import BuildingPlacement
from .road_map import ASPHALT, CURB, SIDEWALK, WHITE, YELLOW, MapTile
from .trees import TreePlacement


DEFAULT_MAP = Path(__file__).with_name("maps") / "default.json"
ASSET_TYPES = {"house": ("house.obj", (1.8, 1.4)),
               "building": ("building.obj", (1.6, 1.6)),
               "market": ("market.obj", (2.6, 1.5))}
Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Road:
    start: tuple[float, float]
    end: tuple[float, float]
    width: float
    stripe_width: float = 0.1
    dash_length: float = 0.6
    dash_gap: float = 0.6

    @property
    def horizontal(self) -> bool:
        return self.start[1] == self.end[1]

    @property
    def rectangle(self) -> Rect:
        a, b = self.start, self.end
        if self.horizontal:
            return min(a[0], b[0]), a[1]-self.width/2, max(a[0], b[0]), a[1]+self.width/2
        return a[0]-self.width/2, min(a[1], b[1]), a[0]+self.width/2, max(a[1], b[1])


@dataclass(frozen=True)
class MapDefinition:
    roads: tuple[Road, ...]
    surrounds: tuple[MapTile, ...]
    buildings: tuple[BuildingPlacement, ...]
    trees: tuple[TreePlacement, ...]


def _object(value, where, allowed, required=()):
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object")
    if unknown := set(value) - set(allowed):
        raise ValueError(f"{where}: unknown fields {', '.join(sorted(unknown))}")
    if missing := set(required) - set(value):
        raise ValueError(f"{where}: missing fields {', '.join(sorted(missing))}")
    return value


def _number(value, where, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{where}: expected a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{where}: must be >= {minimum}")
    return float(value)


def _pair(value, where, minimum=None):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{where}: expected [x, y]")
    return tuple(_number(v, f"{where}[{i}]", minimum) for i, v in enumerate(value))


def _entries(data, name):
    values = data.get(name, [])
    if not isinstance(values, list):
        raise ValueError(f"{name}: expected an array")
    return enumerate(values)


def _tile(rect: Rect, material: str, height=0.01) -> MapTile:
    x0, y0, x1, y1 = rect
    return MapTile(((x0+x1)/2, (y0+y1)/2), (x1-x0, y1-y0), material, height_m=height)


def parse_map(data) -> MapDefinition:
    _object(data, "map", ("version", "roads", "sidewalks", "buildings", "trees"), ("version", "roads"))
    if type(data["version"]) is not int or data["version"] != 1:
        raise ValueError("version: only version 1 is supported")
    roads = []
    for index, value in _entries(data, "roads"):
        label = f"roads[{index}]"
        r = _object(value, label, ("from", "to", "width", "stripe_width", "dash_length", "dash_gap"), ("from", "to", "width"))
        a, b = _pair(r["from"], label+".from"), _pair(r["to"], label+".to")
        if (a[0] == b[0]) == (a[1] == b[1]):
            raise ValueError(f"{label}: use a nonzero horizontal or vertical road")
        width = _number(r["width"], label+".width", 0.001)
        stripe = _number(r.get("stripe_width", 0.1), label+".stripe_width", 0.001)
        if stripe * 4 >= width:
            raise ValueError(f"{label}: width must exceed 4 * stripe_width")
        roads.append(Road(a, b, width, stripe,
                          _number(r.get("dash_length", 0.6), label+".dash_length", 0.01),
                          _number(r.get("dash_gap", 0.6), label+".dash_gap", 0.01)))
    if not roads or len(roads) > 128:
        raise ValueError("roads: supply between 1 and 128 roads")
    for index, road in enumerate(roads):
        for other in roads[:index]:
            if road.horizontal == other.horizontal and _intersection(road.rectangle, other.rectangle):
                raise ValueError(f"roads[{index}]: parallel road areas overlap; combine them into one road")

    surrounds = []
    for index, value in _entries(data, "sidewalks"):
        label = f"sidewalks[{index}]"
        s = _object(value, label, ("position", "size", "height", "curb_width", "curb_height"), ("position", "size"))
        x, y = _pair(s["position"], label+".position")
        w, h = _pair(s["size"], label+".size", 0.001)
        curb = _number(s.get("curb_width", 0.12), label+".curb_width", 0.001)
        height = _number(s.get("height", 0.03), label+".height", 0.001)
        curb_height = _number(s.get("curb_height", 0.05), label+".curb_height", height)
        if min(w, h) <= 2 * curb:
            raise ValueError(f"{label}: size must exceed twice curb_width")
        x0, y0, x1, y1 = x-w/2, y-h/2, x+w/2, y+h/2
        surrounds.append(_tile((x0+curb, y0+curb, x1-curb, y1-curb), SIDEWALK, height))
        for rect in ((x0, y0, x0+curb, y1), (x1-curb, y0, x1, y1),
                     (x0+curb, y0, x1-curb, y0+curb), (x0+curb, y1-curb, x1-curb, y1)):
            surrounds.append(_tile(rect, CURB, curb_height))

    buildings = []
    for index, value in _entries(data, "buildings"):
        label = f"buildings[{index}]"
        b = _object(value, label, ("type", "position", "rotation", "scale", "base_z"), ("type", "position"))
        if not isinstance(b["type"], str) or b["type"] not in ASSET_TYPES:
            raise ValueError(f"{label}.type: use house, building, or market")
        asset, footprint = ASSET_TYPES[b["type"]]
        position = _pair(b["position"], label+".position")
        angle = math.radians(_number(b.get("rotation", 0), label+".rotation"))
        scale = _number(b.get("scale", 0.6), label+".scale", 0.001)
        c, s = abs(math.cos(angle)), abs(math.sin(angle))
        bounds = ((footprint[0]*c+footprint[1]*s)*scale, (footprint[0]*s+footprint[1]*c)*scale)
        buildings.append(BuildingPlacement(asset, position, bounds, angle, scale,
                                           _number(b.get("base_z", 0.03), label+".base_z", 0)))
    trees = []
    for index, value in _entries(data, "trees"):
        label = f"trees[{index}]"
        t = _object(value, label, ("position", "base_z"), ("position",))
        trees.append(TreePlacement(_pair(t["position"], label+".position"),
                                   _number(t.get("base_z", 0.03), label+".base_z", 0)))
    return MapDefinition(tuple(roads), tuple(surrounds), tuple(buildings), tuple(trees))


def load_map(path: Path) -> MapDefinition:
    try:
        return parse_map(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Map {path}: {exc}") from exc


def _intersection(a: Rect, b: Rect) -> Rect | None:
    rect = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return rect if rect[0] < rect[2] and rect[1] < rect[3] else None


def _subtract(a: Rect, b: Rect) -> list[Rect]:
    intersection = _intersection(a, b)
    if intersection is None:
        return [a]
    x0, y0, x1, y1 = intersection
    candidates = [(a[0], a[1], x0, a[3]), (x1, a[1], a[2], a[3]),
                  (x0, a[1], x1, y0), (x0, y1, x1, a[3])]
    return [r for r in candidates if r[0] < r[2] and r[1] < r[3]]


def _road_union(roads: tuple[Road, ...]) -> list[Rect]:
    """Sweep horizontal bands, merging equal spans vertically without overlap."""
    rectangles = [r.rectangle for r in roads]
    ys = sorted({v for r in rectangles for v in (r[1], r[3])})
    result = []
    active = {}
    for y0, y1 in zip(ys, ys[1:]):
        spans = sorted((r[0], r[2]) for r in rectangles if r[1] <= y0 and r[3] >= y1)
        merged = []
        for x0, x1 in spans:
            if merged and x0 <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], x1))
            else:
                merged.append((x0, x1))
        following = {}
        for x0, x1 in merged:
            previous = active.get((x0, x1))
            if previous is None:
                previous = len(result)
                result.append((x0, y0, x1, y1))
            else:
                old = result[previous]
                result[previous] = (x0, old[1], x1, y1)
            following[(x0, x1)] = previous
        active = following
    return result


def road_tiles(definition: MapDefinition) -> tuple[MapTile, ...]:
    """Union road beds; clip paint at perpendicular crossings, including T junctions."""
    tiles = [_tile(r, ASPHALT) for r in _road_union(definition.roads)]
    for road in definition.roads:
        axis = 0 if road.horizontal else 1
        start, end = sorted((road.start[axis], road.end[axis]))
        lateral = road.start[1-axis]
        junctions = [rect for other in definition.roads if other.horizontal != road.horizontal
                     if (rect := _intersection(road.rectangle, other.rectangle)) is not None]

        def paint(a, b, offset, material):
            low, high = lateral+offset-road.stripe_width/2, lateral+offset+road.stripe_width/2
            pieces = [(a, low, b, high) if road.horizontal else (low, a, high, b)]
            for junction in junctions:
                pieces = [p for piece in pieces for p in _subtract(piece, junction)]
            tiles.extend(_tile(piece, material) for piece in pieces)

        paint(start, end, 0, YELLOW)
        dash = start
        while dash < end:
            for offset in (-(road.width+road.stripe_width)/4, (road.width+road.stripe_width)/4):
                paint(dash, min(dash+road.dash_length, end), offset, WHITE)
            dash += road.dash_length + road.dash_gap
    return tuple(tiles)
