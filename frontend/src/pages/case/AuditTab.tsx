import { useEffect, useState } from "react";
import { api, fmtUtc, type AuditEntry } from "../../api";

export default function AuditTab({ caseId }: { caseId: string }) {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [chain, setChain] = useState<boolean | null>(null);
  useEffect(() => {
    api.audit(caseId).then(setRows);
    fetch("/api/audit/verify").then((r) => r.json()).then((r) => setChain(r.ok));
  }, [caseId]);
  return (
    <div className="overflow-auto p-6">
      <p className="mb-4 text-sm" aria-live="polite">
        Chain of custody:{" "}
        {chain === null ? "checking…" : chain
          ? <span className="text-emerald-300">hash chain intact</span>
          : <span className="text-red-300">hash chain BROKEN — the audit log has been altered</span>}
      </p>
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-slate-400">
          <tr><th className="py-2">Time (UTC)</th><th>Actor</th><th>Action</th><th>Details</th><th>Hash after</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-ink-700 align-top">
              <td className="py-2 font-mono text-xs">{fmtUtc(r.ts)}</td>
              <td>{r.actor}</td><td className="font-mono text-xs">{r.action}</td>
              <td className="font-mono text-xs text-slate-400">{JSON.stringify(r.details)}</td>
              <td className="hash max-w-48">{r.hash_after ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
