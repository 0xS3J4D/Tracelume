import { useCallback, useEffect, useState } from "react";
import { NavLink, useParams } from "react-router-dom";
import { api, type CaseSummary } from "../api";
import { ErrorNote, PageHeader } from "../components/ui";
import OverviewTab from "./case/OverviewTab";
import EvidenceTab from "./case/EvidenceTab";
import JobsTab from "./case/JobsTab";
import ArtifactsTab from "./case/ArtifactsTab";
import AuditTab from "./case/AuditTab";
import TimelineTab from "./case/TimelineTab";
import DatabasesTab from "./case/DatabasesTab";

const TABS = [
  ["", "Overview"], ["evidence", "Evidence"], ["jobs", "Jobs"],
  ["timeline", "Timeline"], ["artifacts", "Artifacts"], ["databases", "SQL"], ["audit", "Audit log"],
] as const;

export default function CasePage() {
  const { caseId = "", tab = "" } = useParams();
  const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(
    () => api.caseSummary(caseId).then(setSummary).catch((e) => setError(e.message)), [caseId]);
  useEffect(() => { refresh(); }, [refresh]);

  if (error) return <div className="p-6"><ErrorNote error={error} /></div>;
  if (!summary) return <div className="p-6 text-sm text-slate-400">Loading…</div>;
  const c = summary.case;
  return (
    <>
      <PageHeader title={c.name} sub={[c.number, `Examiner: ${c.examiner}`].filter(Boolean).join(" · ")}
        actions={
          <div className="flex gap-2">
            <a className="btn-ghost" href={`/api/cases/${caseId}/report.html`} download>Report (HTML)</a>
            <a className="btn-primary" href={`/api/cases/${caseId}/report.pdf`} download>Export PDF report</a>
          </div>
        } />
      <nav aria-label="Case sections" className="flex gap-1 border-b border-ink-700 px-4">
        {TABS.map(([path, label]) => (
          <NavLink key={path} end to={`/cases/${caseId}${path ? `/${path}` : ""}`}
            className={({ isActive }) => `border-b-2 px-3 py-2 text-sm ${isActive
              ? "border-accent text-slate-100" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {tab === "" && <OverviewTab caseId={caseId} summary={summary} />}
        {tab === "evidence" && <EvidenceTab caseId={caseId} onChange={refresh} />}
        {tab === "jobs" && <JobsTab caseId={caseId} />}
        {tab === "artifacts" && <ArtifactsTab caseId={caseId} types={Object.keys(summary.artifact_counts)} />}
        {tab === "timeline" && <TimelineTab caseId={caseId} types={Object.keys(summary.artifact_counts)} />}
        {tab === "databases" && <DatabasesTab caseId={caseId} />}
        {tab === "audit" && <AuditTab caseId={caseId} />}
      </div>
    </>
  );
}
