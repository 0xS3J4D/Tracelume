import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtUtc, type Job } from "../../api";
import { StatusBadge } from "../../components/ui";

export default function JobsTab({ caseId }: { caseId: string }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    const load = () => api.jobs(caseId).then(setJobs);
    load();
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [caseId]);
  return (
    <div className="overflow-auto p-6">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr><th className="py-2">Plugin</th><th>Status</th><th>Created</th><th>Finished</th><th className="text-right">Artifacts</th></tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-t border-ink-700 hover:bg-ink-850">
              <td className="py-2"><Link className="text-accent hover:underline" to={`/jobs/${j.id}`}>{j.plugin} {j.plugin_version}</Link></td>
              <td><StatusBadge status={j.status} /></td>
              <td className="font-mono text-xs">{fmtUtc(j.created_at)}</td>
              <td className="font-mono text-xs">{fmtUtc(j.finished_at)}</td>
              <td className="text-right font-mono">{j.artifact_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {jobs.length === 0 && <p className="text-sm text-slate-400">No jobs yet.</p>}
    </div>
  );
}
