import { NavLink, Outlet } from "react-router-dom";
import logo from "../logo.svg";

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2">Skip to content</a>
      <nav aria-label="Main" className="flex w-56 shrink-0 flex-col border-r border-ink-700 bg-ink-900">
        <div className="px-4 py-4"><img src={logo} alt="Tracelume" className="h-7" /></div>
        <ul className="flex-1 space-y-1 px-2 text-sm">
          <li>
            <NavLink to="/" end className={({ isActive }) =>
              `block rounded-md px-3 py-2 ${isActive ? "bg-ink-800 text-accent" : "text-slate-300 hover:bg-ink-800"}`}>
              Cases
            </NavLink>
          </li>
        </ul>
        <p className="px-4 py-3 text-[11px] leading-snug text-slate-500">
          Offline · local only<br />Use only on data you are authorised to examine.
        </p>
      </nav>
      <main id="main" className="flex min-w-0 flex-1 flex-col overflow-hidden"><Outlet /></main>
    </div>
  );
}
