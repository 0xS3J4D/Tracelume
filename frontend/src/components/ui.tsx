import type { ReactNode } from "react";
import type { JobStatus } from "../api";

export function PageHeader({ title, sub, actions }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex items-end justify-between gap-4 border-b border-ink-700 px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
        {sub && <p className="text-sm text-slate-400">{sub}</p>}
      </div>
      {actions}
    </header>
  );
}

const STATUS: Record<JobStatus, string> = {
  queued: "bg-slate-700 text-slate-200",
  running: "bg-sky-900 text-sky-200",
  succeeded: "bg-emerald-900 text-emerald-200",
  failed: "bg-red-900 text-red-200",
  cancelled: "bg-slate-800 text-slate-400",
};
export function StatusBadge({ status }: { status: JobStatus }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS[status]}`}>{status}</span>;
}

export function VerifyBadge({ status }: { status: string }) {
  const cls = status === "ok" ? "bg-emerald-900 text-emerald-200" : "bg-red-900 text-red-200";
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
    {status === "ok" ? "hash verified" : `hash ${status}`}</span>;
}

export function ErrorNote({ error }: { error: string | null }) {
  return error ? <p role="alert" className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-200">{error}</p> : null;
}
