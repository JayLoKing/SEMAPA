import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import { Droplet, Gauge, LayoutDashboard, Map, Receipt, LogOut, Search, AlertTriangle, Monitor } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";

export default function Layout() {
  const { rol, nombre, logout } = useAuthStore();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);

  async function buscar() {
    if (!q || q.length < 2) return;
    const r = await api.get("/buscar", { params: { q } });
    setResults(r.data.results || []);
  }

  return (
    <div className="min-h-full grid grid-cols-[240px_1fr]">
      <aside className="bg-semapa-900 text-white p-4 flex flex-col">
        <div className="flex items-center gap-2 mb-6">
          <Droplet size={28} className="text-semapa-50" />
          <span className="text-xl font-bold">SEMAPA</span>
        </div>
        <nav className="flex flex-col gap-1 text-sm">
          <Link className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700" to="/">
            <LayoutDashboard size={16} /> Dashboard
          </Link>
          <Link className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700" to="/mapa">
            <Map size={16} /> Mapa
          </Link>
          <Link className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700" to="/consultas">
            <Gauge size={16} /> Consultas
          </Link>
          <Link className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700" to="/facturacion">
            <Receipt size={16} /> Facturación
          </Link>
          <Link className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700" to="/anomalias">
            <AlertTriangle size={16} /> Anomalías
          </Link>
          <a
            href="/kiosk"
            target="_blank"
            rel="noopener noreferrer"
            className="flex gap-2 items-center py-2 px-3 rounded hover:bg-semapa-700 text-semapa-200"
          >
            <Monitor size={16} /> Autoservicio ↗
          </a>
        </nav>
        <div className="mt-auto pt-4 border-t border-semapa-700 text-xs">
          <div className="font-semibold">{nombre}</div>
          <div className="opacity-75">{rol}</div>
          <button
            onClick={() => { logout(); navigate("/login"); }}
            className="mt-2 flex items-center gap-1 text-semapa-100 hover:text-white"
          >
            <LogOut size={14} /> Salir
          </button>
        </div>
      </aside>

      <main className="overflow-auto">
        <div className="sticky top-0 z-10 flex items-center gap-3 bg-white border-b px-6 py-3">
          <Search size={18} className="text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && buscar()}
            placeholder="Buscar por contrato, MAC, serie o documento..."
            className="flex-1 outline-none text-sm"
          />
          {results.length > 0 && (
            <div className="absolute top-12 left-12 bg-white border rounded shadow-lg w-[600px] max-h-80 overflow-y-auto z-20">
              {results.map((r, i) => (
                <div key={i} className="p-2 border-b text-xs hover:bg-slate-50">
                  <div className="font-semibold">{r.tipo}</div>
                  <div className="font-mono">{JSON.stringify(r.payload).slice(0, 140)}…</div>
                </div>
              ))}
              <button className="w-full p-2 text-xs text-semapa-600" onClick={() => setResults([])}>cerrar</button>
            </div>
          )}
        </div>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
