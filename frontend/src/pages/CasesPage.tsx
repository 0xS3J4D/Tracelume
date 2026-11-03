import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, fmtUtc, type Case } from "../api";
import { ErrorNote, PageHeader } from "../components/ui";

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [name, setName] = useState("");
  const [number, setNumber] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () => api.cases().then(setCases).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await api.createCase({ name, number: number || undefined });
      setName(""); setNumber(""); load();
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <>
      <PageHeader title="Cases" sub="All cases on this workstation" />
      <div className="flex-1 overflow-auto p-6">
        <form onSubmit={submit} className="card mb-6 flex flex-wrap items-end gap-3 p-4" aria-label="New case">
          <div className="min-w-64 flex-1">
            <label className="label" htmlFor="case-name">Case name</label>
            <input id="case-name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Operation Lantern" />
          </div>
          <div className="w-48">
            <label className="label" htmlFor="case-number">Case number</label>
            <input id="case-number" className="input" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="optional" />
          </div>
          <button className="btn-primary" type="submit">Create case</button>
        </form>
        <ErrorNote error={error} />
        {cases.length === 0 ? (
          <p className="text-sm text-slate-400">No cases yet. Create one to start registering evidence.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr><th className="py-2">Name</th><th>Number</th><th>Examiner</th><th>Created</th><th>Status</th></tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} className="border-t border-ink-700 hover:bg-ink-850">
                  <td className="py-2"><Link className="font-medium text-accent hover:underline" to={`/cases/${c.id}`}>{c.name}</Link></td>
                  <td>{c.number ?? "—"}</td><td>{c.examiner}</td>
                  <td className="font-mono text-xs">{fmtUtc(c.created_at)}</td><td>{c.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
