import type { DistrictData } from '../api/events';

export type ScreenPoint = [number, number];
export type DistrictFeature = DistrictData['features'][number];

export interface ProjectionFrame {
  anchor: [number, number];
  anchorPoint: ScreenPoint;
  eastPoint: ScreenPoint;
  northPoint: ScreenPoint;
  mapOffset: ScreenPoint;
  delta: number;
}

const LAT_LIMIT = 85.05112878;
const MORPH_VERTICES = 48;

function mercatorY(lat: number) {
  const radians = Math.max(-LAT_LIMIT, Math.min(LAT_LIMIT, lat)) * Math.PI / 180;
  return Math.log(Math.tan(Math.PI / 4 + radians / 2));
}

export function projectCoordinate(coordinate: number[], frame: ProjectionFrame): ScreenPoint {
  const [lng, lat] = coordinate;
  const xScale = (frame.eastPoint[0] - frame.anchorPoint[0]) / frame.delta;
  const yScale = (frame.northPoint[1] - frame.anchorPoint[1]) /
    (mercatorY(frame.anchor[1] + frame.delta) - mercatorY(frame.anchor[1]));
  return [frame.mapOffset[0] + frame.anchorPoint[0] + (lng - frame.anchor[0]) * xScale,
    frame.mapOffset[1] + frame.anchorPoint[1] + (mercatorY(lat) - mercatorY(frame.anchor[1])) * yScale];
}

function area(points: ScreenPoint[]) {
  let sum = 0;
  for (let i = 0; i < points.length; i++) {
    const next = points[(i + 1) % points.length];
    sum += points[i][0] * next[1] - next[0] * points[i][1];
  }
  return sum / 2;
}

function outerRings(feature: DistrictFeature): number[][][] {
  return feature.geometry.type === 'Polygon'
    ? [feature.geometry.coordinates[0]]
    : feature.geometry.coordinates.map(polygon => polygon[0]);
}

export function districtBounds(feature: DistrictFeature): [number, number, number, number] {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
  for (const ring of outerRings(feature)) for (const [lng, lat] of ring) {
    west = Math.min(west, lng); south = Math.min(south, lat);
    east = Math.max(east, lng); north = Math.max(north, lat);
  }
  return [west, south, east, north];
}

/** One recognisable outer silhouette; official GeoJSON remains untouched in MapLibre. */
export function districtScreenRing(feature: DistrictFeature, frame: ProjectionFrame): ScreenPoint[] {
  const rings = outerRings(feature).map(ring => {
    const open = ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
      ? ring.slice(0, -1) : ring;
    return open.map(point => projectCoordinate(point, frame));
  });
  return rings.reduce((largest, ring) => Math.abs(area(ring)) > Math.abs(area(largest)) ? ring : largest, [] as ScreenPoint[]);
}

export function resampleRing(points: ScreenPoint[], count = MORPH_VERTICES): ScreenPoint[] {
  if (points.length < 3 || count < 3) return [];
  const edges = points.map((point, index) => Math.hypot(
    points[(index + 1) % points.length][0] - point[0],
    points[(index + 1) % points.length][1] - point[1]));
  const perimeter = edges.reduce((sum, edge) => sum + edge, 0);
  if (!Number.isFinite(perimeter) || perimeter < 1) return [];
  const samples: ScreenPoint[] = [];
  let edgeIndex = 0, edgeStart = 0;
  for (let i = 0; i < count; i++) {
    const distance = perimeter * i / count;
    while (edgeIndex < edges.length - 1 && edgeStart + edges[edgeIndex] < distance) {
      edgeStart += edges[edgeIndex++];
    }
    const fraction = edges[edgeIndex] ? (distance - edgeStart) / edges[edgeIndex] : 0;
    const first = points[edgeIndex], second = points[(edgeIndex + 1) % points.length];
    samples.push([first[0] + (second[0] - first[0]) * fraction,
      first[1] + (second[1] - first[1]) * fraction]);
  }
  return samples;
}

export function districtHeaderHeight(viewportHeight: number) {
  return Math.min(196, Math.max(174, viewportHeight * .22));
}

/** The destination page draws this same contour, so the morph has no shape swap. */
function headerSurfacePoints(width: number, height: number): ScreenPoint[] {
  const radius = 18;
  const edge = height - 18;
  const points: ScreenPoint[] = [[0, 0], [width, 0], [width, edge - radius]];
  for (let i = 1; i <= 5; i++) {
    const angle = Math.PI * i / 10;
    points.push([width - radius + radius * Math.cos(angle), edge - radius + radius * Math.sin(angle)]);
  }
  for (let i = 1; i <= 28; i++) {
    const t = i / 28;
    points.push([width - radius - (width - 2 * radius) * t,
      edge + 18 * Math.sin(Math.PI * t) - 2 * Math.sin(2 * Math.PI * t)]);
  }
  for (let i = 1; i <= 5; i++) {
    const angle = Math.PI / 2 + Math.PI * i / 10;
    points.push([radius + radius * Math.cos(angle), edge - radius + radius * Math.sin(angle)]);
  }
  return points;
}

export function headerSurfacePath(width: number, height: number) {
  const ring = resampleRing(headerSurfacePoints(width, height));
  return interpolateRingPath(ring, ring, 1);
}

function rotateTowardTopLeft(points: ScreenPoint[]) {
  const index = points.reduce((best, point, i) => point[0] + point[1] < points[best][0] + points[best][1] ? i : best, 0);
  return [...points.slice(index), ...points.slice(0, index)];
}

export function morphRings(feature: DistrictFeature, frame: ProjectionFrame, viewport: {width: number; height: number; headerHeight: number}) {
  const target = resampleRing(headerSurfacePoints(viewport.width, viewport.headerHeight));
  let source = districtScreenRing(feature, frame);
  if (Math.sign(area(source)) !== Math.sign(area(target))) source = [...source].reverse();
  source = resampleRing(rotateTowardTopLeft(source));
  if (source.length !== MORPH_VERTICES || target.length !== MORPH_VERTICES ||
      source.some(point => !point.every(Number.isFinite))) return null;
  return {source, target, bounds: districtBounds(feature)};
}

export function interpolateRingPath(source: ScreenPoint[], target: ScreenPoint[], progress: number) {
  'worklet';
  let path = '';
  const smooth = .14 * Math.sin(Math.PI * progress);
  for (let i = 0; i < source.length; i++) {
    const x = source[i][0] + (target[i][0] - source[i][0]) * progress;
    const y = source[i][1] + (target[i][1] - source[i][1]) * progress;
    if (i === 0) path = `M${x.toFixed(1)},${y.toFixed(1)}`;
    const next = (i + 1) % source.length;
    const before = (i + source.length - 1) % source.length;
    const after = (i + 2) % source.length;
    const nx = source[next][0] + (target[next][0] - source[next][0]) * progress;
    const ny = source[next][1] + (target[next][1] - source[next][1]) * progress;
    const bx = source[before][0] + (target[before][0] - source[before][0]) * progress;
    const by = source[before][1] + (target[before][1] - source[before][1]) * progress;
    const ax = source[after][0] + (target[after][0] - source[after][0]) * progress;
    const ay = source[after][1] + (target[after][1] - source[after][1]) * progress;
    path += `C${(x + (nx - bx) * smooth).toFixed(1)},${(y + (ny - by) * smooth).toFixed(1)}` +
      ` ${(nx - (ax - x) * smooth).toFixed(1)},${(ny - (ay - y) * smooth).toFixed(1)}` +
      ` ${nx.toFixed(1)},${ny.toFixed(1)}`;
  }
  return path + 'Z';
}
