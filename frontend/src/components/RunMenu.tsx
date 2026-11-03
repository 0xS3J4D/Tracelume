import { useState } from "react";
import type { Evidence, PluginInfo } from "../api";

/** Lists every analysis that applies to an evidence item; asks for parameters when needed. */
export default function RunMenu({ ev, plugins, onRun, onRunAll }: {
  ev: Evidence; plugins: PluginInfo[];
  onRun: (plugin: string, params?: Record<string, string>) => void;
  onRunAll: (plugins: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<PluginInfo | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const usable = plugins.filter((p) => p.supported_evidence.includes(ev.kind));
  const auto = usable.filter((p) => !Object.values(p.params_schema ?? {}).some((x) => x.required));
  if (!usable.length) return <span className="text-xs text-slate-500">No analyses for this type</span>;

  return (
    <div className="relative">
      <div className="flex gap-2">
        <button className="btn-primary" onClick={() => onRunAll(auto.map((p) => p.name))}
          title={auto.map((p) => p.tool_name).join(", ")}>Run all ({auto.length})</button>
        <button className="btn-ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>Choose… ▾</button>
      </div>
      {open && (
        <ul role="menu" className="absolute right-0 z-20 mt-1 w-96 overflow-hidden rounded-lg border border-ink-700 bg-ink-900 shadow-xl">
          {usable.map((p) => (
            <li key={p.name}>
              <button role="menuitem" className="block w-full px-3 py-2 text-left hover:bg-ink-800"
                onClick={() => {
                  setOpen(false);
                  if (Object.keys(p.params_schema ?? {}).length) { setValues({}); setForm(p); } else onRun(p.name);
                }}>
                <span className="text-sm text-slate-100">{p.tool_name}</span>
                <span className="block text-xs text-slate-400">{p.description}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onMouseDown={() => setForm(null)}>
          <form role="dialog" aria-modal="true" aria-label={`${form.tool_name} options`} onMouseDown={(e) => e.stopPropagation()}
            onSubmit={(e) => { e.preventDefault(); onRun(form.name, values); setForm(null); }}
            className="w-full max-w-2xl space-y-3 rounded-xl border border-ink-700 bg-ink-900 p-5">
            <h2 className="font-semibold text-slate-100">{form.tool_name}</h2>
            <p className="text-sm text-slate-400">{form.description}</p>
            {Object.entries(form.params_schema).map(([key, spec]) => (
              <div key={key}>
                <label className="label" htmlFor={`p-${key}`}>{spec.label}</label>
                {spec.type === "text"
                  ? <textarea id={`p-${key}`} rows={10} className="input font-mono text-xs" required={spec.required}
                      placeholder={spec.placeholder} value={values[key] ?? ""} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />
                  : <input id={`p-${key}`} className="input" required={spec.required} placeholder={spec.placeholder}
                      value={values[key] ?? ""} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />}
              </div>
            ))}
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost" onClick={() => setForm(null)}>Cancel</button>
              <button className="btn-primary">Run</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
