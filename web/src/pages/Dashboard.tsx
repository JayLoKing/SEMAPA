import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#0d6efd", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#06b6d4", "#f97316", "#84cc16", "#64748b"];

function Kpi({ label, value, hint }: { label: string; value: any; hint?: string }) {
  return (
    <div className="bg-white p-5 rounded-lg shadow-sm border">
      <div className="text-xs uppercase text-slate-500 font-semibold">{label}</div>
      <div className="text-3xl font-bold text-semapa-900 mt-2">{value ?? "—"}</div>
      {hint && <div className="text-[11px] text-slate-400 mt-1">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const rol = useAuthStore((s) => s.rol);
  const { data, isLoading } = useQuery({
    queryKey: ["dash"],
    queryFn: async () => (await api.get("/dashboard/kpis")).data,
  });
  const { data: usd } = useQuery({
    queryKey: ["usd"],
    queryFn: async () => (await api.get("/usd/cotizacion")).data,
  });
  const { data: cobertura } = useQuery({
    queryKey: ["cobertura"],
    queryFn: async () => (await api.get("/consultas/cobertura-antenas")).data,
  });
  const { data: dist } = useQuery({
    queryKey: ["dist"],
    queryFn: async () => (await api.get("/consultas/distribucion-categorias")).data,
  });

  if (isLoading) return <div>Cargando KPIs...</div>;

  const pieData = dist ? Object.entries(dist).map(([k, v]) => ({ name: k, value: v as number })) : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard {rol && <span className="text-base text-slate-400">({rol})</span>}</h1>

      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Medidores totales" value={data?.medidores_total?.toLocaleString()} />
        <Kpi label="Activos" value={data?.medidores_activos?.toLocaleString()} hint="estado=ACTIVO" />
        <Kpi label="Fuera de servicio" value={data?.medidores_fuera_servicio?.toLocaleString()} />
        <Kpi label="USD → BOB" value={usd?.rate?.toFixed(2)} hint={`fuente: ${usd?.source}`} />
      </div>

      {rol === "ALCALDIA" && data?.poblacion_beneficiaria && (
        <div className="grid grid-cols-2 gap-4">
          <Kpi label="Población beneficiaria" value={data.poblacion_beneficiaria.toLocaleString()} />
          <Kpi label="Cobertura" value={data.cobertura} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-5 rounded-lg shadow-sm border">
          <h2 className="text-lg font-semibold mb-3">Distribución de categorías</h2>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white p-5 rounded-lg shadow-sm border">
          <h2 className="text-lg font-semibold mb-3">Cobertura por gateway</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={cobertura || []}>
              <XAxis dataKey="gateway_id" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="medidores" fill="#0d6efd" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
