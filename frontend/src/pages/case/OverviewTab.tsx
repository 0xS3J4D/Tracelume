import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtUtc, type CaseSummary, type Job } from "../../api";
import { StatusBadge } from "../../components/ui";
import { typeColor, typeLabel } from "../../components/typeColors";

export default function OverviewTab({ caseId, summary }: { caseId: string; summary: CaseSummary }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => { api.jobs(caseId).then(setJobs); }, [caseId]);
  const counts = Object.entries(summary.artifact_counts).sort((a, b) => b[1] - a[1]);
  const total = counts.reduce((n, [, v]) => n + v, 0);
  const max = Math.max(1, ...counts.map(([, v]) => v));

  return (
    <div className="grid gap-4 overflow-auto p-6 lg:grid-cols-3">
      {[["Evidence items", summary.evidence_count, "evidence"], ["Jobs", summary.job_count, "jobs"],
        ["Artifacts", total, "artifacts"]].map(([label, n, to]) => (
        <Link key={label} to={`/cases/${caseId}/${to}`} className="card p-4 hover:border-accent">
          <p className="label">{label}</p><p className="text-3xl font-semibold text-slate-100">{n}</p>
        </Link>
      ))}
      <section className="card p-4 lg:col-span-2" aria-labelledby="by-type">
        <h2 id="by-type" className="label">Artifacts by type</h2>
        {counts.length === 0 ? <p className="text-sm text-slate-400">No artifacts yet. Run a plugin from the Evidence tab.</p> : (
          <ul className="space-y-2">
            {counts.map(([type, n]) => (
              <li key={type}>
                <Link to={`/cases/${caseId}/artifacts?type=${type}`} className="grid grid-cols-[13rem_1fr_4rem] items-center gap-3 text-sm hover:text-accent">
                  <span>{typeLabel(type)}</span>
                  <span className="h-2 rounded bg-ink-700"><span className="block h-2 rounded" style={{ width: `${(n / max) * 100}%`, background: typeColor(type) }} /></span>
                  <span className="text-right font-mono tabular-nums">{n}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="card p-4" aria-labelledby="recent-jobs">
        <h2 id="recent-jobs" className="label">Recent jobs</h2>
        <ul className="space-y-2 text-sm">
          {jobs.slice(0, 6).map((j) => (
            <li key={j.id} className="flex items-center justify-between gap-2">
              <Link to={`/jobs/${j.id}`} className="hover:text-accent">{j.plugin}</Link>
              <span className="text-xs text-slate-500">{fmtUtc(j.created_at)}</span>
              <StatusBadge status={j.status} />
            </li>
          ))}
          {jobs.length === 0 && <li className="text-slate-400">None yet.</li>}
        </ul>
      </section>
    </div>
  );
}
