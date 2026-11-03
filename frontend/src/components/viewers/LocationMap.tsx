import { geoEqualEarth, geoPath } from "d3-geo";
import { useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import countries50 from "world-atlas/countries-50m.json";
import { fmtUtc, type Artifact } from "../../api";
import { latLon } from "./fields";

const W = 900, H = 520;
// Bundled Natural Earth data (public domain): fully offline, no tile server.
const land = feature(countries50 as unknown as Topology, (countries50 as unknown as Topology).objects.land);
const borders = feature(countries50 as unknown as Topology, (countries50 as unknown as Topology).objects.countries);

export default function LocationMap({ items, selectedId, onSelect }: {
  items: Artifact[]; selectedId?: string; onSelect: (a: Artifact) => void;
}) {
  const points = useMemo(() => items.flatMap((a) => {
    const ll = latLon(a.data);
    return ll ? [{ a, lat: ll[0], lon: ll[1] }] : [];
  }), [items]);
  const [zoomOut, setZoomOut] = useState(false);

  const projection = useMemo(() => {
    const p = geoEqualEarth();
    if (points.length && !zoomOut) {
      // Keep at least ~4° of context so the coastline stays readable around a single point.
      const lats = points.map((x) => x.lat), lons = points.map((x) => x.lon);
      const cLat = (Math.min(...lats) + Math.max(...lats)) / 2, cLon = (Math.min(...lons) + Math.max(...lons)) / 2;
      const hLat = Math.max(2, (Math.max(...lats) - Math.min(...lats)) * 0.6);
      const hLon = Math.max(3, (Math.max(...lons) - Math.min(...lons)) * 0.6);
      const box = {
        type: "MultiPoint" as const,
        coordinates: [[cLon - hLon, cLat - hLat], [cLon + hLon, cLat + hLat]],
      };
      p.fitExtent([[40, 40], [W - 40, H - 40]], box);
    } else p.fitSize([W, H], { type: "Sphere" });
    return p;
  }, [points, zoomOut]);
  const path = geoPath(projection);

  return (
    <div className="flex min-h-0 flex-1 flex-col p-4">
      <div className="mb-2 flex items-center gap-3 text-xs text-slate-400">
        <span>{points.length} of {items.length} artifacts have coordinates · offline basemap (Natural Earth)</span>
        <button className="btn-ghost ml-auto" onClick={() => setZoomOut((z) => !z)}>{zoomOut ? "Fit to points" : "World view"}</button>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="min-h-0 w-full flex-1 rounded-lg border border-ink-700 bg-[#0d1726]" role="img" aria-label="Map of location artifacts">
        <path d={path({ type: "Sphere" }) ?? ""} fill="#0d1726" />
        <path d={path(land) ?? ""} fill="#1a2438" />
        <path d={path(borders) ?? ""} fill="none" stroke="#26324a" strokeWidth={0.5} />
        {points.map(({ a, lat, lon }) => {
          const xy = projection([lon, lat]);
          if (!xy) return null;
          const sel = a.id === selectedId;
          return (
            <g key={a.id} transform={`translate(${xy[0]},${xy[1]})`} className="cursor-pointer" onClick={() => onSelect(a)}>
              <title>{`${fmtUtc(a.timestamp)} — ${a.title} (${lat.toFixed(5)}, ${lon.toFixed(5)})`}</title>
              <circle r={sel ? 7 : 4.5} fill={sel ? "#f59e0b" : "#2dd4bf"} fillOpacity={0.85} stroke="#0b1220" strokeWidth={1} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
