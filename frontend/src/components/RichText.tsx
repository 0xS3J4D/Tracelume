import { Fragment, type ReactNode } from "react";

/** Minimal, safe Markdown subset (headings, lists, bold, code) + [a:<id>] citation chips.
 *  Builds React elements only; never injects HTML. */
export default function RichText({ text, onCite }: { text: string; onCite: (id: string, n: number) => void }) {
  const order: string[] = [];
  const inline = (s: string, key: string): ReactNode[] =>
    s.split(/(\[a:[0-9a-f-]{36}\]|\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
      const k = `${key}-${i}`;
      const cite = part.match(/^\[a:([0-9a-f-]{36})\]$/);
      if (cite) {
        if (!order.includes(cite[1])) order.push(cite[1]);
        const n = order.indexOf(cite[1]) + 1;
        return <button key={k} onClick={() => onCite(cite[1], n)} title="Open cited artifact"
          className="mx-0.5 rounded bg-accent/15 px-1 align-super text-[10px] font-semibold text-accent hover:bg-accent/30">{n}</button>;
      }
      if (part.startsWith("**") && part.endsWith("**")) return <strong key={k}>{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`")) return <code key={k} className="rounded bg-ink-950 px-1 font-mono text-xs">{part.slice(1, -1)}</code>;
      return <Fragment key={k}>{part}</Fragment>;
    });

  const blocks: ReactNode[] = [];
  let list: ReactNode[] = [];
  const flush = (i: number) => { if (list.length) { blocks.push(<ul key={`l${i}`} className="my-1 list-disc space-y-0.5 pl-5">{list}</ul>); list = []; } };
  text.split("\n").forEach((line, i) => {
    const t = line.trim();
    const li = t.match(/^(?:[-*•]|\d+[.)]|- \[[ x]\])\s+(.*)$/);
    if (li) { list.push(<li key={i}>{inline(li[1], `li${i}`)}</li>); return; }
    flush(i);
    if (!t) return;
    const h = t.match(/^#{1,4}\s+(.*)$/);
    if (h) blocks.push(<p key={i} className="mt-2 font-semibold text-slate-100">{inline(h[1], `h${i}`)}</p>);
    else blocks.push(<p key={i} className="my-1">{inline(t, `p${i}`)}</p>);
  });
  flush(-1);
  return <div className="text-sm leading-relaxed">{blocks}</div>;
}
