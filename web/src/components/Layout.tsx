import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { useThemeStore } from "../store/theme";
import {
  Droplet, Gauge, LayoutDashboard, Map, Receipt, LogOut, Search,
  AlertTriangle, Sun, Moon, X,
} from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";

// Menú según rol (cada rol ve solo lo que le compete)
const NAV_BY_ROLE: Record<string, { to: string; label: string; icon: JSX.Element }[]> = {
  ALCALDIA: [
    { to: "/", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
    { to: "/mapa", label: "Mapa", icon: <Map size={18} /> },
    { to: "/consultas", label: "Consultas", icon: <Gauge size={18} /> },
  ],
  GERENCIA: [
    { to: "/", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
    { to: "/mapa", label: "Mapa", icon: <Map size={18} /> },
    { to: "/consultas", label: "Consultas", icon: <Gauge size={18} /> },
    { to: "/anomalias", label: "Anomalías", icon: <AlertTriangle size={18} /> },
  ],
  CONTABILIDAD: [
    { to: "/", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
    { to: "/facturacion", label: "Facturación", icon: <Receipt size={18} /> },
    { to: "/anomalias", label: "Morosos / Anomalías", icon: <AlertTriangle size={18} /> },
    { to: "/consultas", label: "Consultas", icon: <Gauge size={18} /> },
  ],
};

const ROL_LABEL: Record<string, string> = {
  ALCALDIA: "Alcaldía Municipal",
  GERENCIA: "Gerencia SEMAPA",
  CONTABILIDAD: "Contabilidad",
};

export default function Layout() {
  const { rol, nombre, logout } = useAuthStore();
  const { theme, toggle } = useThemeStore();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const navItems = NAV_BY_ROLE[rol || ""] || NAV_BY_ROLE.GERENCIA;

  async function buscar() {
    if (!q || q.length < 2) return;
    const r = await api.get("/buscar", { params: { q } });
    setResults(r.data.results || []);
  }

  const initials = (nombre || "U").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="min-h-full grid grid-cols-[260px_1fr]">
      {/* ── Sidebar ── */}
      <aside className="relative flex flex-col p-5
        bg-gradient-to-b from-white to-slate-50 border-r border-slate-200
        dark:from-ink-900 dark:to-ink-800 dark:border-ink-700">
        {/* Brand */}
        <div className="flex items-center gap-3 mb-8 px-1">
          <div className="grid place-items-center w-10 h-10 rounded-xl
            bg-gradient-to-br from-semapa-500 to-semapa-700 shadow-lg shadow-semapa-500/30">
            <Droplet size={22} className="text-white" />
          </div>
          <div>
            <div className="text-lg font-extrabold tracking-tight text-slate-900 dark:text-white leading-none">
              SEMAPA
            </div>
            <div className="text-[10px] uppercase tracking-widest text-slate-400">Cochabamba</div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex flex-col gap-1.5">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === "/"}
              className={({ isActive }) =>
                `group flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all
                 ${isActive
                  ? "bg-semapa-600 text-white shadow-md shadow-semapa-600/30"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-ink-700"}`
              }
            >
              {it.icon}
              <span>{it.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="mt-auto pt-4 border-t border-slate-200 dark:border-ink-700">
          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="w-full flex items-center justify-between px-3.5 py-2.5 mb-3 rounded-xl text-sm
              bg-slate-100 hover:bg-slate-200 text-slate-700
              dark:bg-ink-700 dark:hover:bg-ink-600 dark:text-slate-200 transition-colors"
          >
            <span className="flex items-center gap-2">
              {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
              {theme === "dark" ? "Modo oscuro" : "Modo claro"}
            </span>
            <span className={`relative w-9 h-5 rounded-full transition-colors ${theme === "dark" ? "bg-semapa-500" : "bg-slate-300"}`}>
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${theme === "dark" ? "left-4.5" : "left-0.5"}`}
                style={{ left: theme === "dark" ? "1.125rem" : "0.125rem" }} />
            </span>
          </button>

          {/* User */}
          <div className="flex items-center gap-3 px-1">
            <div className="grid place-items-center w-9 h-9 rounded-full
              bg-semapa-100 text-semapa-700 dark:bg-ink-700 dark:text-semapa-200 text-xs font-bold">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate text-slate-800 dark:text-slate-100">{nombre}</div>
              <div className="text-[11px] text-slate-400 truncate">{ROL_LABEL[rol || ""] || rol}</div>
            </div>
            <button
              onClick={() => { logout(); navigate("/login"); }}
              title="Salir"
              className="ml-auto p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-ink-700 transition-colors"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="overflow-auto">
        {/* Topbar */}
        <div className="sticky top-0 z-20 px-6 py-3 backdrop-blur
          bg-white/80 border-b border-slate-200
          dark:bg-ink-900/80 dark:border-ink-700">
          <div className="relative flex items-center gap-3 max-w-2xl">
            <div className="flex items-center gap-2 flex-1 px-4 py-2 rounded-xl
              bg-slate-100 dark:bg-ink-800 focus-within:ring-2 ring-semapa-500/40 transition">
              <Search size={18} className="text-slate-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && buscar()}
                placeholder="Buscar por contrato (CT-…), MAC o CI…"
                className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400
                  text-slate-800 dark:text-slate-100"
              />
            </div>
            {results.length > 0 && (
              <div className="absolute top-12 left-0 w-full max-h-96 overflow-y-auto z-30 rounded-xl shadow-glow
                bg-white border border-slate-200 dark:bg-ink-800 dark:border-ink-700">
                <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 dark:border-ink-700">
                  <span className="text-xs font-semibold text-slate-500">{results.length} resultados</span>
                  <button className="text-slate-400 hover:text-slate-600" onClick={() => setResults([])}>
                    <X size={14} />
                  </button>
                </div>
                {results.map((r, i) => (
                  <div key={i} className="p-3 border-b border-slate-100 dark:border-ink-700 text-xs hover:bg-slate-50 dark:hover:bg-ink-700">
                    <div className="font-semibold text-semapa-600 dark:text-semapa-200 uppercase">{r.tipo}</div>
                    <div className="font-mono text-slate-500 mt-0.5">{JSON.stringify(r.payload).slice(0, 160)}…</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
