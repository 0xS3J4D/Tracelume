import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  api, EVIDENCE_KINDS, fmtBytes, fmtUtc, uploadEvidence, type Evidence, type EvidenceKind, type PluginInfo,
} from "../../api";
import RunMenu from "../../components/RunMenu";
import AcquireIos from "../../components/AcquireIos";
import { ErrorNote, VerifyBadge } from "../../components/ui";

export default function EvidenceTab({ caseId, onChange }: { caseId: string; onChange: () => void }) {
  const [items, setItems] = useState<Evidence[]>([]);
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<EvidenceKind>("android_fs");
  const [acquiredBy, setAcquiredBy] = useState("");
  const [notes, setNotes] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [last, setLast] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<"upload" | "folder">("upload");
  const [folderFiles, setFolderFiles] = useState<{ path: string; size: number }[]>([]);
  const [folderPick, setFolderPick] = useState("");
  const navigate = useNavigate();

  const load = () => api.evidence(caseId).then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); api.plugins().then(setPlugins); }, [caseId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (source === "folder") api.importFolder().then((f) => { setFolderFiles(f); setFolderPick(f[0]?.path ?? ""); });
  }, [source]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (source === "folder") {
      if (!folderPick) return;
      setError(null); setLast(null); setProgress(1);
      try {
        const ev = await api.importEvidence(caseId, { path: folderPick, kind, acquired_by: acquiredBy || undefined, notes: notes || undefined });
        setLast(ev); load(); onChange();
      } catch (err) { setError((err as Error).message); } finally { setProgress(null); }
      return;
    }
    if (!file) return;
    setError(null); setLast(null); setProgress(0);
    const form = new FormData();
    form.append("file", file); form.append("kind", kind);
    if (acquiredBy) form.append("acquired_by", acquiredBy);
    if (notes) form.append("notes", notes);
    try {
      const ev = await uploadEvidence(caseId, form, (sent, total) => setProgress(total ? sent / total : 0));
      setLast(ev); setFile(null); load(); onChange();
    } catch (err) { setError((err as Error).message); } finally { setProgress(null); }
  };

  const run = async (ev: Evidence, plugin: string, params?: Record<string, string>) => {
    try { const job = await api.createJob(caseId, ev.id, plugin, params); navigate(`/jobs/${job.id}`); }
    catch (err) { setError((err as Error).message); }
  };
  const runAll = async (ev: Evidence, names: string[]) => {
    try {
      for (const n of names) await api.createJob(caseId, ev.id, n);
      navigate(`/cases/${caseId}/jobs`);
    } catch (err) { setError((err as Error).message); }
  };
  const verify = async (ev: Evidence) => { await api.verify(ev.id); load(); };

  return (
    <div className="overflow-auto p-6">
      <form onSubmit={submit} className="card mb-6 grid gap-3 p-4 md:grid-cols-2" aria-label="Register evidence">
        <div className="md:col-span-2">
          <div role="radiogroup" aria-label="Evidence source" className="mb-2 flex gap-4 text-sm">
            <label className="flex items-center gap-1.5"><input type="radio" checked={source === "upload"} onChange={() => setSource("upload")} /> Upload a file</label>
            <label className="flex items-center gap-1.5"><input type="radio" checked={source === "folder"} onChange={() => setSource("folder")} /> From the import folder (large images)</label>
          </div>
          {source === "upload" ? (
            <>
              <label className="label" htmlFor="ev-file">Evidence file</label>
              <input id="ev-file" type="file" className="input" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </>
          ) : (
            <>
              <label className="label" htmlFor="ev-folder">File in the import folder</label>
              <select id="ev-folder" className="input" value={folderPick} onChange={(e) => setFolderPick(e.target.value)}>
                {folderFiles.map((f) => <option key={f.path} value={f.path}>{f.path} ({fmtBytes(f.size)})</option>)}
              </select>
              {!folderFiles.length && <p className="mt-1 text-xs text-mark">The import folder is empty. Copy files into the <code>import</code> folder next to Tracelume.</p>}
            </>
          )}
          <p className="mt-1 text-xs text-slate-400">
            Tracelume copies the file, hashes it (SHA-256 and MD5) and stores the copy read-only. The original is never changed.
          </p>
        </div>
        <div>
          <label className="label" htmlFor="ev-kind">Type</label>
          <select id="ev-kind" className="input" value={kind} onChange={(e) => setKind(e.target.value as EvidenceKind)}>
            {EVIDENCE_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="ev-by">Acquired by</label>
          <input id="ev-by" className="input" value={acquiredBy} onChange={(e) => setAcquiredBy(e.target.value)} />
        </div>
        <div className="md:col-span-2">
          <label className="label" htmlFor="ev-notes">Notes</label>
          <textarea id="ev-notes" className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="flex items-center gap-4 md:col-span-2">
          <button className="btn-primary" disabled={(source === "upload" ? !file : !folderPick) || progress !== null}>Register evidence</button>
          {progress !== null && (
            <div className="flex flex-1 items-center gap-3" aria-live="polite">
              <div className="h-2 flex-1 rounded bg-ink-700" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-2 rounded bg-accent transition-all" style={{ width: `${progress * 100}%` }} />
              </div>
              <span className="text-xs text-slate-400">
                {progress < 1 ? `Uploading and hashing… ${Math.round(progress * 100)}%` : "Finalising hashes…"}
              </span>
            </div>
          )}
        </div>
        {last && (
          <div className="rounded-md border border-emerald-800 bg-emerald-950/40 p-3 md:col-span-2" aria-live="polite">
            <p className="mb-1 text-sm text-emerald-200">Registered {last.original_filename} ({fmtBytes(last.size)})</p>
            <p className="hash">SHA-256 {last.sha256}</p><p className="hash">MD5&nbsp;&nbsp;&nbsp;&nbsp;{last.md5}</p>
          </div>
        )}
      </form>
      <AcquireIos caseId={caseId} />
      <ErrorNote error={error} />
      <ul className="space-y-3">
        {items.map((ev) => {
          return (
            <li key={ev.id} className="card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-slate-100">{ev.original_filename}</p>
                  <p className="text-xs text-slate-400">{ev.kind} · {fmtBytes(ev.size)} · ingested {fmtUtc(ev.ingested_at)}
                    {ev.acquired_by && ` · acquired by ${ev.acquired_by}`}</p>
                </div>
                <div className="flex items-center gap-2">
                  <VerifyBadge status={ev.verify_status} />
                  <button className="btn-ghost" onClick={() => verify(ev)}>Re-verify</button>
                  <RunMenu ev={ev} plugins={plugins} onRun={(name, params) => run(ev, name, params)}
                    onRunAll={(names) => runAll(ev, names)} />
                </div>
              </div>
              <p className="hash mt-2">SHA-256 {ev.sha256}</p>
              <p className="hash">MD5&nbsp;&nbsp;&nbsp;&nbsp;{ev.md5}</p>
              {ev.notes && <p className="mt-2 text-sm text-slate-300">{ev.notes}</p>}
            </li>
          );
        })}
        {items.length === 0 && <li className="text-sm text-slate-400">No evidence registered.</li>}
      </ul>
    </div>
  );
}
