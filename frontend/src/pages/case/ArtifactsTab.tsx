import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, fmtUtc, type Artifact } from "../../api";
import { ErrorNote } from "../../components/ui";

const PAGE = 100;

export default function ArtifactsTab({ caseId, types }: { caseId: string; types: string[] }) {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const q = params.get("q") ?? "";
  const [query, setQuery] = useState(q);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; items: Artifact[] }>({ total: 0, items: [] });
  const [sel, setSel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const tableRef = useRef<HTMLTableSectionElement>(null);

  useEffect(() => { setOffset(0); }, [type, q]);
  useEffect(() => {
    api.artifacts(caseId, { type, q, limit: PAGE, offset })
      .then((d) => { setData(d); setSel(0); }).catch((e) => setError(e.message));
  }, [caseId, type, q, offset]);

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p, { replace: true });
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, data.items.length - 1)); }
    if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
  };
  useEffect(() => {
    tableRef.current?.querySelector<HTMLElement>(`[data-row="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  const current = data.items[sel];
  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        <form className="flex flex-wrap gap-2 border-b border-ink-700 p-3" role="search"
          onSubmit={(e) => { e.preventDefault(); set("q", query); }}>
          <label className="sr-only" htmlFor="art-q">Search artifacts</label>
          <input id="art-q" className="input max-w-sm" placeholder="Search title and content…" value={query} onChange={(e) => setQuery(e.target.value)} />
          <label className="sr-only" htmlFor="art-type">Type</label>
          <select id="art-type" className="input w-44" value={type} onChange={(e) => set("type", e.target.value)}>
            <option value="">All types</option>
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <span className="ml-auto self-center text-xs text-slate-400">
            {data.total} artifacts · <kbd>j</kbd>/<kbd>k</kbd> to move
          </span>
        </form>
        <ErrorNote error={error} />
        <div className="min-h-0 flex-1 overflow-auto" tabIndex={0} onKeyDown={onKey} aria-label="Artifact table">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-ink-900 text-xs uppercase text-slate-400">
              <tr><th className="px-3 py-2">Time (UTC)</th><th>Type</th><th>Title</th><th className="pr-3">Source</th></tr>
            </thead>
            <tbody ref={tableRef}>
              {data.items.map((a, i) => (
                <tr key={a.id} data-row={i} onClick={() => setSel(i)} aria-selected={i === sel}
                  className={`cursor-pointer border-t border-ink-700 ${i === sel ? "bg-ink-800" : "hover:bg-ink-850"}`}>
                  <td className="whitespace-nowrap px-3 py-1.5 font-mono text-xs">{fmtUtc(a.timestamp)}</td>
                  <td className="text-xs text-accent">{a.type}</td>
                  <td className="max-w-xl truncate">{a.title}</td>
                  <td className="pr-3 text-xs text-slate-400">{a.source_plugin}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <footer className="flex items-center justify-end gap-2 border-t border-ink-700 p-2 text-xs">
          <button className="btn-ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
          <span>{data.total ? `${offset + 1}–${Math.min(offset + PAGE, data.total)} of ${data.total}` : "0"}</span>
          <button className="btn-ghost" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
        </footer>
      </section>
      <aside aria-label="Artifact details" className="w-96 shrink-0 overflow-auto border-l border-ink-700 bg-ink-900 p-4">
        {current ? (
          <>
            <p className="label">{current.type}</p>
            <h2 className="mb-3 break-words font-medium text-slate-100">{current.title}</h2>
            <dl className="mb-4 grid grid-cols-[6rem_1fr] gap-x-2 gap-y-1 text-xs">
              <dt className="text-slate-400">Time</dt><dd className="font-mono">{fmtUtc(current.timestamp)}</dd>
              <dt className="text-slate-400">Time field</dt><dd>{current.timestamp_kind ?? "—"}</dd>
              <dt className="text-slate-400">Plugin</dt><dd>{current.source_plugin}</dd>
              <dt className="text-slate-400">Source path</dt><dd className="break-all font-mono">{current.source_path ?? "—"}</dd>
            </dl>
            <p className="label">Data</p>
            <pre className="whitespace-pre-wrap break-all rounded bg-ink-950 p-3 font-mono text-xs text-slate-300">
              {JSON.stringify(current.data, null, 2)}
            </pre>
          </>
        ) : <p className="text-sm text-slate-400">Select an artifact.</p>}
      </aside>
    </div>
  );
}
