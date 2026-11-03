import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmtUtc, type Artifact, type Tag } from "../../api";
import ArtifactDetail from "../../components/ArtifactDetail";
import { typeColor, typeLabel } from "../../components/typeColors";
import { ErrorNote } from "../../components/ui";
import Conversation from "../../components/viewers/Conversation";
import LocationMap from "../../components/viewers/LocationMap";
import Gallery from "../../components/viewers/Gallery";

const PAGE = 200;
type View = "table" | "conversation" | "map" | "gallery";

export default function ArtifactsTab({ caseId, types }: { caseId: string; types: string[] }) {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const q = params.get("q") ?? "";
  const tag = params.get("tag") ?? "";
  const view = (params.get("view") as View) || (type === "message" ? "conversation" : type === "location" ? "map" : type === "media" ? "gallery" : "table");
  const [query, setQuery] = useState(q);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; items: Artifact[] }>({ total: 0, items: [] });
  const [sel, setSel] = useState(0);
  const [caseTags, setCaseTags] = useState<Tag[]>([]);
  const [focus, setFocus] = useState<{ kind: "tag" | "note"; n: number }>();
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<HTMLTableSectionElement>(null);

  const loadTags = useCallback(() => api.tags(caseId).then(setCaseTags), [caseId]);
  useEffect(() => { loadTags(); }, [loadTags]);
  useEffect(() => { setOffset(0); setQuery(q); }, [type, q, tag]);
  useEffect(() => {
    api.artifacts(caseId, {
      type: type ? [type] : undefined, q, tag: tag || undefined, limit: view === "table" ? PAGE : 1000,
      offset: view === "table" ? offset : 0, order: view === "conversation" ? "asc" : "desc",
    }).then((d) => { setData(d); setSel(0); }).catch((e) => setError(e.message));
  }, [caseId, type, q, tag, offset, view]);

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    if (k === "type") p.delete("view");
    setParams(p, { replace: true });
  };

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).closest("input,textarea,select")) return;
    if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, data.items.length - 1)); }
    else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "t") { e.preventDefault(); setFocus({ kind: "tag", n: Date.now() }); }
    else if (e.key === "n") { e.preventDefault(); setFocus({ kind: "note", n: Date.now() }); }
  };
  useEffect(() => {
    tableRef.current?.querySelector<HTMLElement>(`[data-row="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  const current = data.items[sel];
  const select = (a: Artifact) => setSel(data.items.findIndex((x) => x.id === a.id));
  const views: [View, string][] = [["table", "Table"], ["conversation", "Conversation"], ["gallery", "Gallery"], ["map", "Map"]];

  return (
    <div className="flex min-h-0 flex-1" onKeyDown={onKey}>
      <section className="flex min-w-0 flex-1 flex-col">
        <form className="flex flex-wrap items-center gap-2 border-b border-ink-700 p-3" role="search"
          onSubmit={(e) => { e.preventDefault(); set("q", query); }}>
          <label className="sr-only" htmlFor="art-q">Search artifacts</label>
          <input id="art-q" className="input max-w-xs" placeholder="Search title and content…  ( / )" value={query} onChange={(e) => setQuery(e.target.value)} />
          <label className="sr-only" htmlFor="art-type">Type</label>
          <select id="art-type" className="input w-40" value={type} onChange={(e) => set("type", e.target.value)}>
            <option value="">All types</option>
            {types.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}
          </select>
          <label className="sr-only" htmlFor="art-tag">Tag</label>
          <select id="art-tag" className="input w-40" value={tag} onChange={(e) => set("tag", e.target.value)}>
            <option value="">Any tag</option>
            {caseTags.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.count})</option>)}
          </select>
          <div role="tablist" aria-label="View" className="flex rounded-md border border-ink-700 p-0.5">
            {views.map(([v, label]) => (
              <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => set("view", v)}
                className={`rounded px-2.5 py-1 text-xs ${view === v ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:text-slate-200"}`}>{label}</button>
            ))}
          </div>
          <span className="ml-auto text-xs text-slate-400">{data.total} artifacts</span>
        </form>
        <ErrorNote error={error} />
        {view === "conversation" && <Conversation items={data.items} selectedId={current?.id} onSelect={select} />}
        {view === "gallery" && <Gallery items={data.items} selectedId={current?.id} onSelect={select} />}
        {view === "map" && <LocationMap items={data.items} selectedId={current?.id} onSelect={select} />}
        {view === "table" && (
          <>
            <div className="min-h-0 flex-1 overflow-auto" tabIndex={0} aria-label="Artifact table">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-ink-900 text-xs uppercase text-slate-400">
                  <tr><th className="px-3 py-2">Time (UTC)</th><th>Type</th><th>Title</th><th className="pr-3">Source</th></tr>
                </thead>
                <tbody ref={tableRef}>
                  {data.items.map((a, i) => (
                    <tr key={a.id} data-row={i} onClick={() => setSel(i)} aria-selected={i === sel}
                      className={`cursor-pointer border-t border-ink-700 ${i === sel ? "bg-ink-800" : "hover:bg-ink-850"}`}>
                      <td className="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{fmtUtc(a.timestamp)}</td>
                      <td className="whitespace-nowrap pr-3 text-xs" style={{ color: typeColor(a.type) }}>{typeLabel(a.type)}</td>
                      <td className="max-w-xl truncate">{a.title}</td>
                      <td className="pr-3 text-xs text-slate-400">{a.source_plugin}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.items.length && <p className="p-6 text-sm text-slate-400">No artifacts match these filters.</p>}
            </div>
            <footer className="flex items-center justify-end gap-2 border-t border-ink-700 p-2 text-xs">
              <span className="mr-auto pl-2 text-slate-400"><kbd>j</kbd>/<kbd>k</kbd> move · <kbd>t</kbd> tag · <kbd>n</kbd> note</span>
              <button className="btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
              <span>{data.total ? `${offset + 1}–${Math.min(offset + PAGE, data.total)} of ${data.total}` : "0"}</span>
              <button className="btn-ghost" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
            </footer>
          </>
        )}
      </section>
      <aside aria-label="Artifact details" className="w-[26rem] shrink-0 overflow-auto border-l border-ink-700 bg-ink-900">
        <ArtifactDetail artifact={current} caseTags={caseTags} onTagsChanged={loadTags} focus={focus} />
      </aside>
    </div>
  );
}
