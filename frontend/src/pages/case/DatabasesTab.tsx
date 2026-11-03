import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtBytes, type DbInfo, type DbTable, type QueryResult } from "../../api";
import { ErrorNote } from "../../components/ui";

const quote = (n: string) => `"${n.replace(/"/g, '""')}"`;

function Cell({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <span className="text-slate-400">NULL</span>;
  if (typeof v === "object") {
    const b = v as { blob_hex?: string; blob_len?: number };
    return <span className="text-slate-400" title={b.blob_hex}>BLOB {fmtBytes(b.blob_len ?? 0)}</span>;
  }
  return <>{String(v)}</>;
}

export default function DatabasesTab({ caseId }: { caseId: string }) {
  const [dbs, setDbs] = useState<DbInfo[] | null>(null);
  const [filter, setFilter] = useState("");
  const [db, setDb] = useState<DbInfo | null>(null);
  const [schema, setSchema] = useState<DbTable[]>([]);
  const [sql, setSql] = useState("");
  const [result, setResult] = useState<QueryResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.databases(caseId).then(setDbs).catch((e) => setError(e.message)); }, [caseId]);
  useEffect(() => {
    if (!db) return;
    setResult(null); setError(null);
    api.dbSchema(caseId, db.id).then((s) => {
      setSchema(s);
      const first = s.find((t) => t.type === "table");
      if (first) setSql(`SELECT * FROM ${quote(first.name)} LIMIT 100`);
    });
  }, [caseId, db]);

  const shown = useMemo(() => (dbs ?? []).filter((d) => d.path.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => Object.values(b.recovered).reduce((x, y) => x + y, 0) - Object.values(a.recovered).reduce((x, y) => x + y, 0)), [dbs, filter]);

  const run = async (q = sql) => {
    if (!db) return;
    setBusy(true); setError(null);
    try { setResult(await api.dbQuery(caseId, db.id, q)); } catch (e) { setError((e as Error).message); setResult(null); }
    finally { setBusy(false); }
  };

  if (dbs && !dbs.length) {
    return (
      <div className="p-6 text-sm text-slate-400">
        No databases extracted yet. On the <Link className="text-accent hover:underline" to={`/cases/${caseId}/evidence`}>Evidence</Link> tab,
        run <b>Tracelume SQLite carver</b> on a phone dump to extract every SQLite database and recover deleted records.
      </div>
    );
  }
  return (
    <div className="flex min-h-0 flex-1">
      <aside className="flex w-80 shrink-0 flex-col border-r border-ink-700" aria-label="Databases">
        <div className="p-2"><label htmlFor="db-filter" className="sr-only">Filter databases</label>
          <input id="db-filter" className="input" placeholder={`Filter ${dbs?.length ?? 0} databases…`} value={filter} onChange={(e) => setFilter(e.target.value)} /></div>
        <ul className="min-h-0 flex-1 overflow-auto">
          {shown.map((d) => {
            const rec = Object.values(d.recovered).reduce((x, y) => x + y, 0);
            return (
              <li key={d.id}>
                <button onClick={() => setDb(d)} className={`block w-full px-3 py-2 text-left ${db?.id === d.id ? "bg-ink-800" : "hover:bg-ink-850"}`}>
                  <span className="block truncate text-sm text-slate-100" title={d.path}>{d.path.split("/").pop()}</span>
                  <span className="block truncate text-xs text-slate-400" title={d.path}>{d.path}</span>
                  <span className="text-xs text-slate-400">{Object.keys(d.tables).length} tables · {fmtBytes(d.size)}
                    {rec > 0 && <span className="ml-1 text-mark">· {rec} recovered</span>}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>
      {db ? (
        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex min-h-0 flex-[0_0_auto] gap-3 border-b border-ink-700 p-3">
            <div className="w-56 shrink-0 overflow-auto" style={{ maxHeight: 220 }}>
              <p className="label">Tables</p>
              <ul className="space-y-0.5 text-xs">
                {schema.map((t) => (
                  <li key={t.name}>
                    <button className="w-full truncate rounded px-1.5 py-0.5 text-left hover:bg-ink-800" title={t.columns.map((c) => `${c.name} ${c.type}`).join("\n")}
                      onClick={() => { const q = `SELECT * FROM ${quote(t.name)} LIMIT 100`; setSql(q); run(q); }}>
                      {t.name} <span className="text-slate-400">{t.rows ?? ""}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <label htmlFor="sql" className="sr-only">SQL query</label>
              <textarea id="sql" value={sql} onChange={(e) => setSql(e.target.value)} spellCheck={false} rows={6}
                onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } }}
                className="input flex-1 font-mono text-xs" />
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <button className="btn-primary" onClick={() => run()} disabled={busy}>{busy ? "Running…" : "Run"} <span className="opacity-60">Ctrl+Enter</span></button>
                <span>Read-only · copy of the original (SHA-256 <span className="font-mono">{db.sha256.slice(0, 16)}…</span>) · every query is audit-logged</span>
                {result && <span className="ml-auto">{result.rows.length}{result.truncated ? "+" : ""} rows · {result.elapsed_ms} ms</span>}
              </div>
            </div>
          </div>
          <ErrorNote error={error} />
          <div className="min-h-0 flex-1 overflow-auto">
            {result && (
              <table className="w-max min-w-full text-left font-mono text-xs">
                <thead className="sticky top-0 bg-ink-900 text-slate-400">
                  <tr>{result.columns.map((c, i) => <th key={i} className="border-b border-ink-700 px-2 py-1.5">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {result.rows.map((r, i) => (
                    <tr key={i} className="border-b border-ink-800 hover:bg-ink-850">
                      {r.map((v, j) => <td key={j} className="max-w-md truncate px-2 py-1"><Cell v={v} /></td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {result?.truncated && <p className="p-2 text-xs text-slate-400">Showing the first 2,000 rows. Add a WHERE or LIMIT clause to narrow the result.</p>}
          </div>
        </section>
      ) : (
        <p className="p-6 text-sm text-slate-400">Select a database. Databases with recovered (deleted) records are listed first.</p>
      )}
    </div>
  );
}
