import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtUtc, type Job } from "../api";
import { PageHeader, StatusBadge } from "../components/ui";

export default function JobPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [follow, setFollow] = useState(true);
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    setLines([]);
    api.job(jobId).then(setJob);
    const es = new EventSource(`/api/jobs/${jobId}/log`);
    es.onmessage = (e) => setLines((l) => [...l, e.data]);
    es.addEventListener("end", () => { es.close(); api.job(jobId).then(setJob); });
    const t = setInterval(() => api.job(jobId).then(setJob), 2000);
    return () => { es.close(); clearInterval(t); };
  }, [jobId]);

  useEffect(() => {
    if (follow && logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [lines, follow]);

  if (!job) return <div className="p-6 text-sm text-slate-400">Loading…</div>;
  return (
    <>
      <PageHeader title={<>Job · {job.plugin} <StatusBadge status={job.status} /></>}
        sub={<>Started {fmtUtc(job.started_at)} · finished {fmtUtc(job.finished_at)} · {job.artifact_count} artifacts</>}
        actions={<Link className="btn-ghost" to={`/cases/${job.case_id}/artifacts`}>View artifacts →</Link>} />
      {job.error && <p role="alert" className="mx-6 mt-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-200">{job.error}</p>}
      <div className="flex items-center gap-2 px-6 pt-4 text-xs text-slate-400">
        <input id="follow" type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
        <label htmlFor="follow">Follow log</label>
      </div>
      <pre ref={logRef} aria-live="polite" aria-label="Job log"
        className="m-6 mt-2 flex-1 overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-4 font-mono text-xs leading-relaxed text-slate-300">
        {lines.join("\n") || "Waiting for output…"}
      </pre>
    </>
  );
}
