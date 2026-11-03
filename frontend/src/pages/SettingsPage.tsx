import { useEffect, useState, type FormEvent } from "react";
import { api, type Settings } from "../api";
import { ErrorNote, PageHeader } from "../components/ui";

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [examiner, setExaminer] = useState("");
  const [ai, setAi] = useState<Settings["assistant"] | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [test, setTest] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.settings().then((x) => { setS(x); setExaminer(x.examiner.name); setAi(x.assistant); })
      .catch((e) => setError(e.message));
  }, []);
  if (!s || !ai) return <div className="p-6"><ErrorNote error={error} /></div>;

  const saveExaminer = async (e: FormEvent) => {
    e.preventDefault(); await api.saveExaminer(examiner); setSaved("Examiner saved");
  };
  const saveAi = async (e: FormEvent) => {
    e.preventDefault(); setAi(await api.saveAssistant(ai)); setSaved("Assistant settings saved");
  };
  const runTest = async () => {
    setTest("Testing…");
    const r = await api.testAssistant();
    setTest(r.ok ? `Connected — model replied: “${r.reply}”` : `Failed: ${r.error}`);
  };

  return (
    <>
      <PageHeader title="Settings" sub="Workstation settings. Every change is written to the audit log." />
      <div className="max-w-3xl space-y-6 overflow-auto p-6">
        {saved && <p role="status" className="text-sm text-emerald-300">{saved}</p>}
        <form onSubmit={saveExaminer} className="card space-y-3 p-4">
          <h2 className="font-medium text-slate-100">Examiner</h2>
          <div><label className="label" htmlFor="ex">Name recorded in the audit log and reports</label>
            <input id="ex" className="input" value={examiner} onChange={(e) => setExaminer(e.target.value)} placeholder="e.g. J. Examiner" /></div>
          <button className="btn-primary">Save</button>
        </form>

        <form onSubmit={saveAi} className="card space-y-3 p-4">
          <h2 className="font-medium text-slate-100">Case assistant (AI)</h2>
          <p className="text-sm text-slate-400">
            Any OpenAI-compatible chat endpoint works. The default is a <b>local</b> Ollama server started with
            <code className="mx-1 rounded bg-ink-950 px-1">./tracelume ai</code>, so case data never leaves this machine.
            For a remote endpoint, each case must separately allow remote processing.
          </p>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ai.enabled} onChange={(e) => setAi({ ...ai, enabled: e.target.checked })} /> Enable the assistant</label>
          <div><label className="label" htmlFor="url">Endpoint (base URL)</label>
            <input id="url" className="input font-mono" value={ai.base_url} onChange={(e) => setAi({ ...ai, base_url: e.target.value })} />
            <p className={`mt-1 text-xs ${ai.local ? "text-emerald-300" : "text-mark"}`}>{ai.local ? "Local endpoint" : "Remote endpoint: case data will leave this machine"}</p></div>
          <div className="grid gap-3 md:grid-cols-2">
            <div><label className="label" htmlFor="model">Model</label>
              <input id="model" className="input font-mono" value={ai.model} onChange={(e) => setAi({ ...ai, model: e.target.value })} /></div>
            <div><label className="label" htmlFor="key">API key (remote only)</label>
              <input id="key" type="password" autoComplete="off" className="input" value={ai.api_key} onChange={(e) => setAi({ ...ai, api_key: e.target.value })} /></div>
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-primary">Save</button>
            <button type="button" className="btn-ghost" onClick={runTest}>Test connection</button>
            {test && <span className="text-xs text-slate-400" role="status">{test}</span>}
          </div>
        </form>
      </div>
    </>
  );
}
