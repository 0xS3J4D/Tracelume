import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import logo from "../logo.svg";
import CommandPalette from "./CommandPalette";
import ShortcutHelp from "./ShortcutHelp";

const typing = (e: KeyboardEvent) =>
  (e.target as HTMLElement | null)?.closest("input,textarea,select,[contenteditable]") !== null;

export default function Layout() {
  const [palette, setPalette] = useState(false);
  const [help, setHelp] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); }
      else if (e.key === "Escape") { setPalette(false); setHelp(false); }
      else if (!typing(e) && e.key === "?") { e.preventDefault(); setHelp(true); }
      else if (!typing(e) && e.key === "/") {
        const box = document.querySelector<HTMLInputElement>("[role=search] input");
        if (box) { e.preventDefault(); box.focus(); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2">Skip to content</a>
      <nav aria-label="Main" className="flex w-56 shrink-0 flex-col border-r border-ink-700 bg-ink-900">
        <div className="px-4 py-4"><img src={logo} alt="Tracelume" className="h-7" /></div>
        <button onClick={() => setPalette(true)}
          className="mx-2 mb-3 flex items-center gap-2 rounded-md border border-ink-700 px-3 py-1.5 text-left text-sm text-slate-400 hover:border-slate-500">
          Search… <kbd className="ml-auto rounded bg-ink-800 px-1.5 text-[10px]">Ctrl K</kbd>
        </button>
        <ul className="flex-1 space-y-1 px-2 text-sm">
          <li>
            <NavLink to="/" end className={({ isActive }) =>
              `block rounded-md px-3 py-2 ${isActive ? "bg-ink-800 text-accent" : "text-slate-300 hover:bg-ink-800"}`}>
              Cases
            </NavLink>
          </li>
          <li>
            <NavLink to="/settings" className={({ isActive }) =>
              `block rounded-md px-3 py-2 ${isActive ? "bg-ink-800 text-accent" : "text-slate-300 hover:bg-ink-800"}`}>
              Settings
            </NavLink>
          </li>
        </ul>
        <button onClick={() => setHelp(true)} className="mx-4 mb-1 text-left text-[11px] text-slate-500 hover:text-slate-300">Keyboard shortcuts <kbd>?</kbd></button>
        <p className="px-4 py-3 text-[11px] leading-snug text-slate-500">
          Offline · local only<br />Use only on data you are authorised to examine.
        </p>
      </nav>
      <main id="main" className="flex min-w-0 flex-1 flex-col overflow-hidden"><Outlet /></main>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
      <ShortcutHelp open={help} onClose={() => setHelp(false)} />
    </div>
  );
}
