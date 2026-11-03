import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmtUtc, type Artifact, type Histogram, type Tag } from "../../api";
import ArtifactDetail from "../../components/ArtifactDetail";
import { typeColor, typeLabel } from "../../components/typeColors";

const W = 1000, H = 140, PAD = 4;

export default function TimelineTab({ caseId, types }: { caseId: string; types: string[] }) {
  const [params, setParams] = useSearchParams();
  const since = params.get("since") ?? undefined;
  const until = params.get("until") ?? undefined;
  const hidden = useMemo(() => new Set((params.get("hide") ?? "").split(",").filter(Boolean)), [params]);
  const shown = types.filter((t) => !hidden.has(t));
  const [hist, setHist] = useState<Histogram | null>(null);
  const [items, setItems] = useState<{ total: number; items: Artifact[] }>({ total: 0, items: [] });
  const [selected, setSelected] = useState<Artifact>();
  const [caseTags, setCaseTags] = useState<Tag[]>([]);
  const [drag, setDrag] = useState<{ x0: number; x1: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const loadTags = useCallback(() => api.tags(caseId).then(setCaseTags), [caseId]);
  useEffect(() => { loadTags(); }, [loadTags]);
  useEffect(() => {
    const filter = { type: shown.length ? shown : ["__none__"], since, until };
    api.histogram(caseId, { ...filter, buckets: 160 }).then(setHist);
    api.artifacts(caseId, { ...filter, order: "asc", limit: 500 }).then(setItems);
  }, [caseId, since, until, shown.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const update = (patch: Record<string, string | undefined>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) { if (v) p.set(k, v); else p.delete(k); }
    setParams(p, { replace: true });
  };
  const toggleType = (t: string) => {
    const next = new Set(hidden);
    if (next.has(t)) next.delete(t); else next.add(t);
    update({ hide: [...next].join(",") });
  };

  const buckets = hist?.buckets ?? [];
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const bw = buckets.length ? (W - PAD * 2) / buckets.length : 0;
  const toX = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return Math.max(PAD, Math.min(W - PAD, ((e.clientX - r.left) / r.width) * W));
  };
  const zoomTo = (x0: number, x1: number) => {
    const [a, b] = [Math.min(x0, x1), Math.max(x0, x1)];
    if (!buckets.length || b - a < 3) return;
    const i0 = Math.floor((a - PAD) / bw), i1 = Math.min(buckets.length - 1, Math.floor((b - PAD) / bw));
    update({ since: buckets[i0].start, until: buckets[i1].end });
  };

  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-ink-700 p-4">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {types.map((t) => (
              <button key={t} onClick={() => toggleType(t)} aria-pressed={!hidden.has(t)}
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs ${hidden.has(t) ? "border-ink-700 text-slate-500" : "border-ink-700 text-slate-200"}`}>
                <span className="h-2 w-2 rounded-full" style={{ background: hidden.has(t) ? "transparent" : typeColor(t), border: `1px solid ${typeColor(t)}` }} />{typeLabel(t)}
              </button>
            ))}
            <span className="ml-auto text-xs text-slate-400">
              {since || until ? <>{fmtUtc(since ?? null)} → {fmtUtc(until ?? null)} <button className="btn-ghost" onClick={() => update({ since: undefined, until: undefined })}>Reset zoom</button></>
                : <>{fmtUtc(hist?.min ?? null)} → {fmtUtc(hist?.max ?? null)}</>}
            </span>
          </div>
          <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="h-36 w-full cursor-crosshair touch-none select-none rounded border border-ink-700 bg-ink-950"
            role="img" aria-label="Event density over time. Drag to zoom."
            onPointerDown={(e) => { const x = toX(e); setDrag({ x0: x, x1: x }); (e.target as Element).setPointerCapture?.(e.pointerId); }}
            onPointerMove={(e) => drag && setDrag({ ...drag, x1: toX(e) })}
            onPointerUp={() => { if (drag) zoomTo(drag.x0, drag.x1); setDrag(null); }}>
            {buckets.map((b, i) => {
              let y = H - PAD;
              return (
                <g key={i}>
                  <title>{`${fmtUtc(b.start)} – ${b.count} events`}</title>
                  {Object.entries(b.by_type).map(([t, n]) => {
                    const h = (n / max) * (H - PAD * 2);
                    y -= h;
                    return <rect key={t} x={PAD + i * bw + 0.5} y={y} width={Math.max(bw - 1, 1)} height={h} fill={typeColor(t)} />;
                  })}
                </g>
              );
            })}
            {drag && <rect x={Math.min(drag.x0, drag.x1)} y={0} width={Math.abs(drag.x1 - drag.x0)} height={H} fill="#2dd4bf" fillOpacity={0.15} stroke="#2dd4bf" />}
          </svg>
          <p className="mt-1 text-[11px] text-slate-500">Drag across the chart to zoom. All times UTC.</p>
        </div>
        <ol className="min-h-0 flex-1 overflow-auto" aria-label="Events">
          {items.items.map((a) => (
            <li key={a.id}>
              <button onClick={() => setSelected(a)}
                className={`grid w-full grid-cols-[11rem_7rem_1fr] items-center gap-3 border-b border-ink-700 px-4 py-1.5 text-left text-sm ${selected?.id === a.id ? "bg-ink-800" : "hover:bg-ink-850"}`}>
                <span className="font-mono text-xs">{fmtUtc(a.timestamp)}</span>
                <span className="flex items-center gap-1.5 text-xs"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: typeColor(a.type) }} /><span className="truncate">{typeLabel(a.type)}</span></span>
                <span className="truncate">{a.title}</span>
              </button>
            </li>
          ))}
          {items.total > items.items.length && <li className="p-3 text-center text-xs text-slate-500">Showing first {items.items.length} of {items.total}. Zoom in to see more.</li>}
          {!items.total && <li className="p-6 text-sm text-slate-400">No timestamped events in this range.</li>}
        </ol>
      </section>
      <aside aria-label="Artifact details" className="w-[26rem] shrink-0 overflow-auto border-l border-ink-700 bg-ink-900">
        <ArtifactDetail artifact={selected} caseTags={caseTags} onTagsChanged={loadTags} />
      </aside>
    </div>
  );
}
