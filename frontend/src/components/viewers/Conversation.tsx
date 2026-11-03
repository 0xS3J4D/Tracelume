import { useMemo, useState } from "react";
import { fmtUtc, type Artifact } from "../../api";
import { body, counterpart, isOutgoing } from "./fields";

/** Message artifacts grouped into threads, shown as a chat transcript. */
export default function Conversation({ items, selectedId, onSelect }: {
  items: Artifact[]; selectedId?: string; onSelect: (a: Artifact) => void;
}) {
  const threads = useMemo(() => {
    const m = new Map<string, Artifact[]>();
    for (const a of items) {
      const key = `${String(a.data.module ?? a.source_plugin)} · ${counterpart(a.data)}`;
      m.set(key, [...(m.get(key) ?? []), a]);
    }
    for (const list of m.values()) list.sort((x, y) => (x.timestamp ?? "").localeCompare(y.timestamp ?? ""));
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [items]);
  const [active, setActive] = useState<string | null>(null);
  const current = threads.find(([k]) => k === active) ?? threads[0];

  if (!threads.length) return <p className="p-6 text-sm text-slate-400">No messages in this view.</p>;
  return (
    <div className="flex min-h-0 flex-1">
      <ul className="w-64 shrink-0 overflow-auto border-r border-ink-700" aria-label="Threads">
        {threads.map(([k, list]) => (
          <li key={k}>
            <button onClick={() => setActive(k)}
              className={`block w-full px-3 py-2 text-left text-sm ${current?.[0] === k ? "bg-ink-800" : "hover:bg-ink-850"}`}>
              <span className="block truncate text-slate-100">{k.split(" · ").slice(1).join(" · ")}</span>
              <span className="text-xs text-slate-400">{k.split(" · ")[0]} · {list.length} messages</span>
            </button>
          </li>
        ))}
      </ul>
      <ol className="min-w-0 flex-1 space-y-2 overflow-auto p-4" aria-label="Messages">
        {current?.[1].map((a) => {
          const out = isOutgoing(a.data);
          return (
            <li key={a.id} className={`flex ${out ? "justify-end" : "justify-start"}`}>
              <button onClick={() => onSelect(a)}
                className={`max-w-[70%] rounded-2xl px-3 py-2 text-left text-sm ${out ? "bg-accent/20 text-slate-100" : "bg-ink-800 text-slate-200"} ${selectedId === a.id ? "ring-2 ring-mark" : ""}`}>
                <span className="block whitespace-pre-wrap break-words">{body(a.data) || <em className="text-slate-400">(no text)</em>}</span>
                <span className="mt-1 block text-xs text-slate-400">{fmtUtc(a.timestamp)} · {out ? "sent" : "received"}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
