import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend,
} from "recharts";

const COLORS = ["#0d6efd", "#22c55e", "#eab308", "#ef4444", "#a855f7", "#06b6d4",
  "#f97316", "#84cc16", "#64748b", "#ec4899"];
const DISTRITOS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
const CATS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"];

type Filtro = { key: string; tipo: "distrito" | "categoria" | "number" | "text"; label: string; def: any };
type Norm =
  | { kind: "bar"; data: any[]; x: string; y: string; yLabel?: string }
  | { kind: "line"; data: any[]; x: string; y: string }
  | { kind: "pie"; data: { name: string; value: number }[] }
  | { kind: "kpi"; pairs: [string, any][] }
  | { kind: "table"; columns: string[]; rows: any[][] };

type Consulta = {
  slug: string; label: string; filtros?: Filtro[];
  transform: (d: any) => Norm;
};

const objPie = (o: Record<string, any>): { name: string; value: number }[] =>
  Object.entries(o || {}).map(([name, value]) => ({ name, value: Number(value) }));

const CONSULTAS: Consulta[] = [
  { slug: "consumo-promedio-distrito", label: "1. Consumo total por distrito",
    transform: (d) => ({ kind: "bar", data: d, x: "distrito_id", y: "consumo_total_m3", yLabel: "m³" }) },
  { slug: "comparativa-semanas", label: "2. Comparativa por periodo entre distritos",
    filtros: [{ key: "distritos", tipo: "text", label: "Distritos (csv)", def: "1,3,5" }],
    transform: (d) => ({ kind: "bar", data: d, x: "periodo", y: "consumo_m3", yLabel: "m³" }) },
  { slug: "consumos-excesivos", label: "3. Consumos excesivos",
    filtros: [{ key: "umbral_m3", tipo: "number", label: "Umbral m³", def: 150 }],
    transform: (d) => ({ kind: "bar", data: (d || []).slice(0, 15).map((r: any) => ({ mac: r.mac.slice(0, 8), consumo_m3: r.consumo_m3 })), x: "mac", y: "consumo_m3", yLabel: "m³" }) },
  { slug: "medidores-activos", label: "4. Medidores por estado",
    transform: (d) => ({ kind: "pie", data: objPie(d.por_estado) }) },
  { slug: "medidores-fuera-servicio", label: "5. Medidores dañados",
    transform: (d) => ({ kind: "table", columns: ["mac", "distrito_id", "zona", "estado"], rows: (d || []).slice(0, 50).map((r: any) => [r.mac, r.distrito_id, r.zona, r.estado]) }) },
  { slug: "modelos-mas-fallas", label: "6. Modelos con más fallas",
    transform: (d) => ({ kind: "bar", data: d.map((r: any) => ({ modelo: `M${r.modelo_id}`, tasa_falla: r.tasa_falla })), x: "modelo", y: "tasa_falla" }) },
  { slug: "consumo-por-tarifa-distrito", label: "7. Consumo por categoría tarifaria",
    transform: (d) => { const m: any = {}; (d || []).forEach((r: any) => m[r.categoria] = (m[r.categoria] || 0) + r.consumo_m3); return { kind: "pie", data: objPie(m) }; } },
  { slug: "zonas-anomalas", label: "8. Top 20 zonas por consumo",
    transform: (d) => ({ kind: "bar", data: (d || []).map((r: any) => ({ zona: r.zona, consumo_m3: r.consumo_m3 })), x: "zona", y: "consumo_m3", yLabel: "m³" }) },
  { slug: "lecturas-fallidas-mes", label: "9. Lecturas fallidas (por status)",
    transform: (d) => ({ kind: "pie", data: objPie(d.por_status) }) },
  { slug: "medidores-mas-4-anios", label: "10. Medidores +4 años",
    transform: (d) => ({ kind: "kpi", pairs: [["Total +4 años", d.total], ["Corte", d.cutoff]] }) },
  { slug: "per-capita-residencial", label: "11. Per cápita residencial (L/persona/día)",
    transform: (d) => ({ kind: "bar", data: (d || []).map((r: any) => ({ distrito: `D${r.distrito_id}`, litros: r.litros_persona_dia })), x: "distrito", y: "litros", yLabel: "L/p/día" }) },
  { slug: "top3-consumidores-distrito", label: "12. Top 3 consumidores por distrito",
    transform: (d) => { const rows: any[][] = []; Object.entries(d || {}).forEach(([dist, arr]: any) => (arr as any[]).forEach((x) => rows.push([`D${dist}`, x.mac, x.consumo_m3]))); return { kind: "table", columns: ["Distrito", "MAC", "m³"], rows: rows.slice(0, 60) }; } },
  { slug: "zonas-renovacion", label: "13. Zonas que requieren renovación",
    transform: (d) => ({ kind: "bar", data: (d || []).slice(0, 20).map((r: any) => ({ zona: `D${r.distrito_id}-${r.zona}`, tasa_falla: r.tasa_falla })), x: "zona", y: "tasa_falla" }) },
  { slug: "zonas-errores-por-distrito", label: "14. Zonas con errores por distrito",
    filtros: [{ key: "distrito", tipo: "distrito", label: "Distrito", def: 1 }],
    transform: (d) => ({ kind: "bar", data: (d || []).map((r: any) => ({ zona: r.zona, fallas: r.fallas, total: r.total })), x: "zona", y: "fallas" }) },
  { slug: "cobertura-antenas", label: "15. Cobertura de antenas (gateway)",
    transform: (d) => ({ kind: "bar", data: (d || []).map((r: any) => ({ gateway: `GW${r.gateway_id}`, medidores: r.medidores })), x: "gateway", y: "medidores" }) },
  { slug: "proyeccion-demanda-5anios", label: "16. Proyección de demanda",
    transform: (d) => ({ kind: "line", data: (d.historico_mensual_m3 || []).map(([periodo, v]: any) => ({ periodo, consumo: v })), x: "periodo", y: "consumo" }) },
  { slug: "impacto-cambio-tarifa", label: "17. Impacto cambio de tarifa",
    filtros: [{ key: "desde", tipo: "categoria", label: "Desde", def: "P" }, { key: "hacia", tipo: "categoria", label: "Hacia", def: "R4" }],
    transform: (d) => ({ kind: "kpi", pairs: [["Medidores afectados", d.medidores_afectados], ["Desde", d.desde], ["Hacia", d.hacia]] }) },
  { slug: "medidores-sin-reporte", label: "18. Medidores sin reporte",
    transform: (d) => ({ kind: "pie", data: [{ name: "Con lectura", value: d.con_lectura }, { name: "Sin reporte", value: d.sin_reporte }] }) },
  { slug: "proyeccion-ingresos-mes", label: "19. Proyección de ingresos del mes",
    transform: (d) => ({ kind: "bar", data: objPie(d.medidores_por_categoria).map((x) => ({ categoria: x.name, medidores: x.value })), x: "categoria", y: "medidores" }) },
  { slug: "consumo-minimo-residencial", label: "20. Consumo mínimo residencial",
    transform: (d) => ({ kind: "kpi", pairs: [["Mínimo m³", d.minimo_m3], ["Nota", d.nota]] }) },
  { slug: "ingresos-pies3", label: "21. Consumo en pies³",
    transform: (d) => ({ kind: "kpi", pairs: [["Total m³", d.consumo_total_m3], ["Total pies³", d.consumo_pies3]] }) },
  { slug: "distribucion-categorias", label: "22. Distribución de categorías",
    transform: (d) => ({ kind: "pie", data: objPie(d) }) },
  { slug: "horas-pico", label: "23. Horas pico",
    transform: (d) => ({ kind: "line", data: (d || []).map((r: any) => ({ hora: r.hora, consumo: r.consumo_m3 })), x: "hora", y: "consumo" }) },
  { slug: "medidores-por-modelo", label: "24. Medidores por modelo",
    transform: (d) => ({ kind: "bar", data: (d || []).map((r: any) => ({ modelo: `M${r.modelo_id}`, medidores: r.medidores })), x: "modelo", y: "medidores" }) },
  { slug: "resumen-cobertura-poblacional", label: "25. Cobertura poblacional",
    transform: (d) => ({ kind: "kpi", pairs: [["Población", d.poblacion_total], ["Medidores", d.medidores_total], ["Med/1000 hab", d.medidores_por_1000_hab]] }) },
];

function ChartRender({ norm }: { norm: Norm }) {
  if (norm.kind === "kpi")
    return (
      <div className="grid grid-cols-3 gap-4">
        {norm.pairs.map(([k, v], i) => (
          <div key={i} className="bg-white border rounded-lg p-5">
            <div className="text-xs uppercase text-slate-500 font-semibold">{k}</div>
            <div className="text-2xl font-bold text-semapa-900 mt-1">{typeof v === "number" ? v.toLocaleString() : v}</div>
          </div>
        ))}
      </div>
    );
  if (norm.kind === "table")
    return (
      <div className="overflow-auto max-h-[55vh] bg-white border rounded-lg">
        <table className="w-full text-sm">
          <thead><tr className="bg-slate-50 text-xs uppercase text-slate-500">
            {norm.columns.map((c) => <th key={c} className="text-left px-3 py-2">{c}</th>)}
          </tr></thead>
          <tbody>
            {norm.rows.map((row, i) => (
              <tr key={i} className="border-t hover:bg-slate-50">
                {row.map((cell, j) => <td key={j} className="px-3 py-2">{String(cell)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  if (norm.kind === "pie")
    return (
      <ResponsiveContainer width="100%" height={360}>
        <PieChart>
          <Pie data={norm.data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={120} label>
            {norm.data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip /><Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  if (norm.kind === "line")
    return (
      <ResponsiveContainer width="100%" height={360}>
        <LineChart data={norm.data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={norm.x} /><YAxis /><Tooltip />
          <Line dataKey={norm.y} stroke="#0d6efd" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    );
  // bar
  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={norm.data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={norm.x} angle={-30} textAnchor="end" height={70} interval={0} fontSize={11} />
        <YAxis /><Tooltip />
        <Bar dataKey={norm.y} fill="#0d6efd" />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Consultas() {
  const [sel, setSel] = useState<Consulta>(CONSULTAS[0]);
  const [filtros, setFiltros] = useState<Record<string, any>>({});

  const params: Record<string, any> = {};
  (sel.filtros || []).forEach((f) => { params[f.key] = filtros[f.key] ?? f.def; });

  const { data, isLoading, error } = useQuery({
    queryKey: ["consulta", sel.slug, params],
    queryFn: async () => (await api.get(`/consultas/${sel.slug}`, { params })).data,
  });

  let norm: Norm | null = null;
  let parseErr: string | null = null;
  if (data) { try { norm = sel.transform(data); } catch (e: any) { parseErr = String(e); } }

  return (
    <div className="grid grid-cols-[320px_1fr] gap-4">
      {/* Lista consultas */}
      <div className="bg-white border rounded-lg overflow-y-auto max-h-[82vh]">
        <div className="px-3 py-2 border-b font-semibold text-sm bg-slate-50">Consultas analíticas</div>
        {CONSULTAS.map((c) => (
          <button key={c.slug}
            onClick={() => { setSel(c); setFiltros({}); }}
            className={`w-full text-left px-3 py-2 border-b text-xs hover:bg-slate-50 ${sel.slug === c.slug ? "bg-semapa-50 border-l-4 border-l-semapa-600 font-semibold" : ""}`}>
            {c.label}
          </button>
        ))}
      </div>

      {/* Panel resultado */}
      <div className="space-y-3">
        <h1 className="text-xl font-bold">{sel.label}</h1>

        {/* Filtros */}
        {sel.filtros && sel.filtros.length > 0 && (
          <div className="flex flex-wrap gap-3 bg-white border rounded-lg p-3">
            {sel.filtros.map((f) => (
              <div key={f.key}>
                <label className="text-xs uppercase text-slate-500 block mb-1">{f.label}</label>
                {f.tipo === "distrito" ? (
                  <select className="border rounded px-3 py-1.5 text-sm"
                    value={filtros[f.key] ?? f.def}
                    onChange={(e) => setFiltros({ ...filtros, [f.key]: Number(e.target.value) })}>
                    {DISTRITOS.map((d) => <option key={d} value={d}>Distrito {d}</option>)}
                  </select>
                ) : f.tipo === "categoria" ? (
                  <select className="border rounded px-3 py-1.5 text-sm"
                    value={filtros[f.key] ?? f.def}
                    onChange={(e) => setFiltros({ ...filtros, [f.key]: e.target.value })}>
                    {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                ) : (
                  <input
                    type={f.tipo === "number" ? "number" : "text"}
                    className="border rounded px-3 py-1.5 text-sm w-40"
                    value={filtros[f.key] ?? f.def}
                    onChange={(e) => setFiltros({ ...filtros, [f.key]: f.tipo === "number" ? Number(e.target.value) : e.target.value })}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Resultado */}
        <div className="bg-white border rounded-lg p-4 min-h-[400px]">
          {isLoading && <div className="text-slate-400 py-20 text-center">Cargando...</div>}
          {error && <div className="text-red-500 py-20 text-center">Error al cargar la consulta.</div>}
          {parseErr && <div className="text-amber-600 py-20 text-center">Sin datos para graficar.</div>}
          {norm && !isLoading && <ChartRender norm={norm} />}
        </div>
      </div>
    </div>
  );
}
