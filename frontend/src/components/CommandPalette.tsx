import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtUtc, type Case, type SearchHit } from "../api";

type Item = { id: string; label: string; hint?: string; group: string; go: () => void };

/** Ctrl/Cmd+K: jump to cases and views, or search artifacts across all cases. */
export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [cases, setCases] = useState<Case[]>([]);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    setQ(""); setHits([]); setActive(0);
    api.cases().then(setCases);
    setTimeout(() => input.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); return; }
    const t = setTimeout(() => api.search(q.trim()).then(setHits).catch(() => setHits([])), 180);
    return () => clearTimeout(t);
  }, [q]);

  const items = useMemo<Item[]>(() => {
    const go = (path: string) => () => { navigate(path); onClose(); };
    const needle = q.toLowerCase();
    const list: Item[] = [{ id: "home", label: "All cases", group: "Go to", go: go("/") }];
    for (const c of cases) {
      for (const [tab, name] of [["", "Overview"], ["timeline", "Timeline"], ["artifacts", "Artifacts"], ["evidence", "Evidence"]]) {
        list.push({ id: `${c.id}-${tab}`, label: `${c.name} — ${name}`, hint: c.number ?? undefined, group: "Go to", go: go(`/cases/${c.id}${tab ? `/${tab}` : ""}`) });
      }
    }
    const nav = list.filter((i) => !needle || i.label.toLowerCase().includes(needle)).slice(0, needle ? 8 : 6);
    const found = hits.map((h) => ({
      id: h.artifact.id, label: h.artifact.title, group: "Artifacts",
      hint: `${h.case_name} · ${h.artifact.type} · ${fmtUtc(h.artifact.timestamp)}`,
      go: go(`/cases/${h.artifact.case_id}/artifacts?q=${encodeURIComponent(q.trim())}`),
    }));
    return [...nav, ...found];
  }, [cases, hits, q, navigate, onClose]);

  useEffect(() => { setActive(0); }, [items.length]);
  if (!open) return null;

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter") items[active]?.go();
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[12vh]" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-2xl overflow-hidden rounded-xl border border-ink-700 bg-ink-900 shadow-2xl">
        <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey}
          aria-label="Search cases, views and artifacts" placeholder="Search everything — cases, views, artifact content…"
          className="w-full border-b border-ink-700 bg-transparent px-4 py-3 text-base text-slate-100 outline-none placeholder:text-slate-500" />
        <ul role="listbox" className="max-h-[50vh] overflow-auto py-1">
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? (lastGroup = it.group) : null;
            return (
              <li key={it.id + i}>
                {header && <p className="px-4 pb-1 pt-2 text-[11px] uppercase tracking-wide text-slate-500">{header}</p>}
                <button role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={it.go}
                  className={`flex w-full items-baseline gap-3 px-4 py-2 text-left text-sm ${i === active ? "bg-ink-800 text-slate-100" : "text-slate-300"}`}>
                  <span className="truncate">{it.label}</span>
                  {it.hint && <span className="ml-auto shrink-0 text-xs text-slate-500">{it.hint}</span>}
                </button>
              </li>
            );
          })}
          {q.trim().length >= 2 && !hits.length && <li className="px-4 py-3 text-sm text-slate-500">No artifact matches yet…</li>}
        </ul>
        <p className="border-t border-ink-700 px-4 py-2 text-[11px] text-slate-500">↑↓ navigate · Enter open · Esc close</p>
      </div>
    </div>
  );
}
