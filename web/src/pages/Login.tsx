import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import { Droplet } from "lucide-react";

export default function Login() {
  const [username, setU] = useState("alcaldia");
  const [password, setP] = useState("Alcaldia2025!");
  const [err, setErr] = useState("");
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await api.post("/auth/login", { username, password });
      login(r.data.access_token, r.data.rol, r.data.nombre);
      navigate("/");
    } catch (e: any) {
      setErr(e.response?.data?.detail || "Error de autenticación");
    }
  }

  return (
    <div className="min-h-full grid place-items-center bg-gradient-to-br from-semapa-900 to-semapa-600">
      <form onSubmit={submit} className="bg-white p-8 rounded-xl shadow-xl w-[380px]">
        <div className="flex items-center gap-2 mb-6">
          <Droplet className="text-semapa-600" size={32} />
          <h1 className="text-2xl font-bold text-semapa-900">SEMAPA</h1>
        </div>
        <p className="text-sm text-slate-500 mb-6">
          Gestión Inteligente de Agua Potable — Cochabamba
        </p>
        <label className="block text-xs font-semibold uppercase mb-1">Usuario</label>
        <input className="w-full border rounded px-3 py-2 mb-4 text-sm"
               value={username} onChange={(e) => setU(e.target.value)} />
        <label className="block text-xs font-semibold uppercase mb-1">Contraseña</label>
        <input type="password" className="w-full border rounded px-3 py-2 mb-4 text-sm"
               value={password} onChange={(e) => setP(e.target.value)} />
        {err && <div className="text-red-600 text-xs mb-3">{err}</div>}
        <button className="w-full bg-semapa-600 hover:bg-semapa-700 text-white py-2 rounded font-semibold">
          Ingresar
        </button>
        <div className="text-[10px] text-slate-400 mt-4 text-center">
          Roles disponibles: alcaldia · gerencia · contabilidad
        </div>
      </form>
    </div>
  );
}
