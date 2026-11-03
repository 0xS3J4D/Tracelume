import { Fragment } from "react";

const KEYS: [string, string][] = [
  ["Ctrl / ⌘ + K", "Command palette and global search"],
  ["/", "Focus the search box"],
  ["j / k  or  ↓ / ↑", "Next / previous artifact"],
  ["t", "Tag the selected artifact"],
  ["n", "Add a note to the selected artifact"],
  ["Ctrl + Enter", "Save note"],
  ["?", "Show this help"],
  ["Esc", "Close dialogs"],
];

export default function ShortcutHelp({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onMouseDown={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-ink-700 bg-ink-900 p-5 shadow-2xl">
        <h2 className="mb-3 font-semibold text-slate-100">Keyboard shortcuts</h2>
        <dl className="grid grid-cols-[10rem_1fr] gap-y-2 text-sm">
          {KEYS.map(([k, v]) => (<Fragment key={k}><dt><kbd className="rounded border border-ink-700 bg-ink-950 px-1.5 py-0.5 font-mono text-xs">{k}</kbd></dt><dd className="text-slate-300">{v}</dd></Fragment>))}
        </dl>
        <button className="btn-ghost mt-4" onClick={onClose} autoFocus>Close</button>
      </div>
    </div>
  );
}
