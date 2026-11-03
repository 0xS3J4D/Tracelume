import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type Artifact, type AssistantMessage, type AssistantPolicy, type Tag } from "../../api";
import ArtifactDetail from "../../components/ArtifactDetail";
import RichText from "../../components/RichText";
import { ErrorNote } from "../../components/ui";

const PRESETS: [string, string][] = [
  ["plan", "Suggest an investigation plan"],
  ["summary", "Summarise the case"],
  ["deleted", "What deleted or recovered data is there?"],
];

export default function AssistantTab({ caseId }: { caseId: string }) {
  const [msgs, setMsgs] = useState<AssistantMessage[]>([]);
  const [policy, setPolicy] = useState<AssistantPolicy | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cited, setCited] = useState<Artifact>();
  const [caseTags, setCaseTags] = useState<Tag[]>([]);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.assistantMessages(caseId).then(setMsgs);
    api.policy(caseId).then(setPolicy);
    api.tags(caseId).then(setCaseTags);
  }, [caseId]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [msgs, busy]);

  const ask = async (question: string, label = question) => {
    if (!question.trim() || busy) return;
    setBusy(label); setError(null);
    try {
      await api.ask(caseId, question);
      setMsgs(await api.assistantMessages(caseId));
      setQ("");
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };
  const submit = (e: FormEvent) => { e.preventDefault(); ask(q); };
  const blocked = policy && !policy.endpoint_local && !policy.allow_remote;

  return (
    <div className="flex min-h-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-ink-700 px-4 py-2 text-xs">
          {policy && (policy.endpoint_local
            ? <span className="rounded bg-emerald-950 px-2 py-0.5 text-emerald-300">Local model · {policy.model} · data stays on this machine</span>
            : <span className="rounded bg-red-950 px-2 py-0.5 text-red-200">Remote model · {policy.model} · case data is sent off this machine</span>)}
          {policy && !policy.endpoint_local && (
            <label className="flex items-center gap-1.5 text-slate-300">
              <input type="checkbox" checked={policy.allow_remote}
                onChange={async (e) => setPolicy(await api.setPolicy(caseId, e.target.checked))} />
              Allow remote processing for this case
            </label>
          )}
          <Link to="/settings" className="ml-auto text-slate-400 hover:text-slate-200">Assistant settings</Link>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-auto p-4" aria-live="polite">
          {!msgs.length && !busy && (
            <div className="mx-auto mt-6 max-w-xl text-center text-sm text-slate-400">
              <p className="mb-1 text-base text-slate-200">Ask about this case</p>
              <p>The assistant searches artifacts and extracted databases with read-only tools, shows each step it takes,
                and cites the artifacts it relies on. Always verify its answers against the evidence.</p>
            </div>
          )}
          {msgs.map((m) => m.role === "user" ? (
            <div key={m.id} className="flex justify-end"><p className="max-w-[75%] rounded-2xl bg-accent/15 px-3 py-2 text-sm text-slate-100">{m.content}</p></div>
          ) : (
            <article key={m.id} className="max-w-[85%] rounded-xl border border-ink-700 bg-ink-850 p-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Assistant · AI-generated · {m.model}</p>
              <RichText text={m.content} onCite={async (id) => setCited(await api.artifact(id))} />
              {m.steps.length > 0 && (
                <details className="mt-2 text-xs text-slate-400">
                  <summary className="cursor-pointer hover:text-slate-200">{m.steps.length} tool {m.steps.length === 1 ? "step" : "steps"}</summary>
                  <ol className="mt-1 space-y-1">
                    {m.steps.map((s, i) => (
                      <li key={i} className="rounded bg-ink-950 p-2 font-mono">
                        <span className="text-accent">{s.tool}</span>({JSON.stringify(s.args)})
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all text-slate-400">{typeof s.result === "string" ? s.result : JSON.stringify(s.result, null, 1)}</pre>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
            </article>
          ))}
          {busy && <p className="text-sm text-slate-400">Working on “{busy}” — searching the case…</p>}
          <div ref={end} />
        </div>
        <ErrorNote error={error} />
        <form onSubmit={submit} className="border-t border-ink-700 p-3">
          <div className="mb-2 flex flex-wrap gap-2">
            {PRESETS.map(([k, label]) => (
              <button key={k} type="button" className="rounded-full border border-ink-700 px-3 py-1 text-xs text-slate-300 hover:border-accent disabled:opacity-50"
                disabled={!!busy || !!blocked} onClick={() => ask(k, label)}>{label}</button>
            ))}
          </div>
          <div className="flex gap-2">
            <label htmlFor="ask" className="sr-only">Question</label>
            <textarea id="ask" rows={2} className="input" value={q} onChange={(e) => setQ(e.target.value)} disabled={!!blocked}
              placeholder={blocked ? "Remote processing is not allowed for this case." : "e.g. Who did the device owner talk to on 1 May? Any messages about money?"}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q); } }} />
            <button className="btn-primary self-end" disabled={!q.trim() || !!busy || !!blocked}>Ask</button>
          </div>
        </form>
      </section>
      <aside aria-label="Artifact details" className="w-[26rem] shrink-0 overflow-auto border-l border-ink-700 bg-ink-900">
        {cited ? <ArtifactDetail artifact={cited} caseTags={caseTags} onTagsChanged={() => api.tags(caseId).then(setCaseTags)} />
          : <p className="p-4 text-sm text-slate-400">Click a numbered citation to inspect the artifact here.</p>}
      </aside>
    </div>
  );
}
