import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, CartesianGrid, ComposedChart, Line, Legend,
} from "recharts";

const COLORS = ["#0d6efd", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#06b6d4", "#f97316", "#84cc16", "#64748b"];
const NIVEL_LABEL: Record<string, string> = {
  "1": "N1 Ejemplar (≤100L)", "2": "N2 Responsable (≤180L)", "3": "N3 Moderado (≤250L)",
  "4": "N4 Elevado (≤300L)", "5": "N5 Inconsciente (≤400L)", "6": "N6 Crítico (>400L)",
};
const NIVEL_COLOR: Record<string, string> = {
  "1": "#16a34a", "2": "#84cc16", "3": "#eab308", "4": "#f97316", "5": "#ef4444", "6": "#7f1d1d",
};

function Kpi({ label, value, hint, accent }: { label: string; value: any; hint?: string; accent?: string }) {
  return (
    <div className="bg-white p-5 rounded-lg shadow-sm border">
      <div className="text-xs uppercase text-slate-500 font-semibold">{label}</div>
      <div className={`text-3xl font-bold mt-2 ${accent || "text-semapa-900"}`}>{value ?? "—"}</div>
      {hint && <div className="text-[11px] text-slate-400 mt-1">{hint}</div>}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white p-5 rounded-lg shadow-sm border">
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const rol = useAuthStore((s) => s.rol);
  const { data, isLoading } = useQuery({
    queryKey: ["dash", rol],
    queryFn: async () => (await api.get("/dashboard/kpis")).data,
  });
  const { data: usd } = useQuery({
    queryKey: ["usd"],
    queryFn: async () => (await api.get("/usd/cotizacion")).data,
  });

  if (isLoading) return <div className="p-4">Cargando KPIs...</div>;

  const titulo =
    rol === "ALCALDIA" ? "Dashboard Estratégico — Alcaldía (ODS / Smart City)" :
    rol === "GERENCIA" ? "Dashboard Táctico — Gerencia SEMAPA" :
    rol === "CONTABILIDAD" ? "Dashboard Financiero — Contabilidad" :
    "Dashboard";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{titulo}</h1>

      {/* Base KPIs (todos los roles) */}
      <div className="grid grid-cols-5 gap-4">
        <Kpi label="Medidores IoT" value={data?.medidores_total?.toLocaleString()} />
        <Kpi label="Activos" value={data?.medidores_activos?.toLocaleString()} accent="text-green-600"
          hint="Operativo+Reacond.+Nuevo" />
        <Kpi label="Con falla" value={data?.medidores_falla?.toLocaleString()} accent="text-red-600" hint="Dañado" />
        <Kpi label="% sensores falla" value={`${data?.pct_sensores_falla ?? 0}%`} accent="text-orange-500" />
        <Kpi label="USD → BOB" value={usd?.rate?.toFixed(2)} hint={`fuente: ${usd?.source}`} />
      </div>

      {rol === "ALCALDIA" && <Alcaldia data={data} />}
      {rol === "GERENCIA" && <Gerencia data={data} />}
      {rol === "CONTABILIDAD" && <Contabilidad data={data} />}
    </div>
  );
}

// ── Dashboard 1: Alcaldía ──────────────────────────────────────────────────
function Alcaldia({ data }: { data: any }) {
  const { data: clima } = useQuery({
    queryKey: ["clima"],
    queryFn: async () => (await api.get("/consultas/consumo-vs-clima")).data,
  });
  const climaSerie = (clima?.serie || []).map((s: any) => ({
    periodo: s.periodo,
    consumo: s.consumo_m3,
    temp: s.temp_media,
    sequia: s.sequia_indice,
  }));

  const niveles = data?.distribucion_niveles_onu || {};
  const nivelData = Object.entries(niveles).map(([k, v]) => ({
    name: NIVEL_LABEL[k] || k, value: v as number, key: k,
  }));
  const perCapita = (data?.consumo_per_capita_distrito || []).map((d: any) => ({
    distrito: `D${d.distrito_id}`, litros: d.litros_persona_dia, nivel: d.nivel_onu,
  }));

  return (
    <>
      <div className="grid grid-cols-3 gap-4">
        <Kpi label="Población beneficiaria" value={data?.poblacion_beneficiaria?.toLocaleString()} />
        <Kpi label="Consumo total (3 meses)" value={`${data?.consumo_total_m3?.toLocaleString()} m³`} />
        <Kpi label="Cobertura urbana" value={`${data?.cobertura_pct ?? 0}%`} accent="text-green-600" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card title="Clasificación ODS — Niveles de consumo ONU (litros/persona/día)">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={nivelData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={95} label>
                {nivelData.map((d) => <Cell key={d.key} fill={NIVEL_COLOR[d.key] || "#64748b"} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Equidad territorial — Litros/persona/día por distrito">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={perCapita}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distrito" /><YAxis /><Tooltip />
              <Bar dataKey="litros" name="L/persona/día" fill="#06b6d4" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Impacto climático — Consumo vs Temperatura vs Sequía (Open-Meteo)">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={climaSerie}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="periodo" />
            <YAxis yAxisId="left" label={{ value: "m³", angle: -90, position: "insideLeft" }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: "°C / sequía", angle: 90, position: "insideRight" }} />
            <Tooltip /><Legend />
            <Bar yAxisId="left" dataKey="consumo" name="Consumo m³" fill="#0d6efd" />
            <Line yAxisId="right" dataKey="temp" name="Temp media °C" stroke="#f97316" strokeWidth={2} />
            <Line yAxisId="right" dataKey="sequia" name="Índice sequía" stroke="#ef4444" strokeWidth={2} strokeDasharray="4 2" />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="text-xs text-slate-400 mt-2">Fuente: {clima?.fuente || "Open-Meteo"}</p>
      </Card>
    </>
  );
}

// ── Dashboard 2: Gerencia ──────────────────────────────────────────────────
function Gerencia({ data }: { data: any }) {
  const modelos = data?.medidores_por_modelo || {};
  const modeloData = Object.entries(modelos).map(([k, v]) => ({ modelo: `M${k}`, medidores: v as number }));
  const top10 = (data?.top10_zonas_consumo || []).map((z: any) => ({ zona: z.zona, consumo: z.consumo_m3 }));

  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <Kpi label="Consumo acumulado" value={`${data?.consumo_acumulado_m3?.toLocaleString()} m³`} />
        <Kpi label="Mantenimiento" value={data?.medidores_mantenimiento?.toLocaleString()} accent="text-yellow-600" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card title="Top 10 zonas por consumo">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={top10} layout="vertical" margin={{ left: 60 }}>
              <XAxis type="number" /><YAxis type="category" dataKey="zona" width={120} fontSize={11} />
              <Tooltip />
              <Bar dataKey="consumo" name="m³" fill="#0d6efd" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Parque de medidores por modelo">
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={modeloData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="modelo" /><YAxis /><Tooltip />
              <Bar dataKey="medidores" fill="#22c55e" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </>
  );
}

// ── Dashboard 3: Contabilidad ──────────────────────────────────────────────
function Contabilidad({ data }: { data: any }) {
  const porDistrito = data?.facturado_por_distrito || {};
  const distData = Object.entries(porDistrito).map(([k, v]) => ({ distrito: `D${k}`, bs: v as number }));
  const cat = data?.medidores_activos_por_categoria || {};
  const catData = Object.entries(cat).map(([k, v]) => ({ name: k, value: v as number }));

  return (
    <>
      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Facturado Bs" value={data?.facturado_bs?.toLocaleString()} />
        <Kpi label="Recaudado Bs" value={data?.recaudado_bs?.toLocaleString()} accent="text-green-600" />
        <Kpi label="Cartera vencida Bs" value={data?.cartera_vencida_bs?.toLocaleString()} accent="text-red-600" />
        <Kpi label="% recuperación" value={`${data?.pct_recuperacion ?? 0}%`} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Card title="Facturación por distrito (Bs)">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={distData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="distrito" /><YAxis /><Tooltip />
              <Bar dataKey="bs" name="Bs" fill="#f97316" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Medidores activos por categoría tarifaria">
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={catData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={95} label>
                {catData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>
      <Card title="Contratos morosos">
        <div className="text-3xl font-bold text-red-600">{data?.contratos_morosos?.toLocaleString() ?? 0}</div>
        <div className="text-xs text-slate-400">Facturas en estado PENDIENTE (ver detalle en Anomalías)</div>
      </Card>
    </>
  );
}
