import { useState } from "react";
import { api } from "../api/client";
import { Play } from "lucide-react";

const CONSULTAS: { slug: string; label: string; params?: Record<string, string> }[] = [
  { slug: "consumo-promedio-distrito", label: "1. Consumo promedio por distrito (rango horario)" },
  { slug: "comparativa-semanas", label: "2. Comparativa de semanas entre distritos" },
  { slug: "consumos-excesivos", label: "3. Consumos excesivos" },
  { slug: "medidores-activos", label: "4. Medidores activos / inactivos / fuera de servicio" },
  { slug: "medidores-fuera-servicio", label: "5. Medidores fuera de servicio" },
  { slug: "modelos-mas-fallas", label: "6. Modelos con más fallas" },
  { slug: "consumo-por-tarifa-distrito", label: "7. Consumo por tarifa y distrito" },
  { slug: "zonas-anomalas", label: "8. Zonas anómalas" },
  { slug: "lecturas-fallidas-mes", label: "9. Lecturas fallidas del mes" },
  { slug: "medidores-mas-4-anios", label: "10. Medidores con +4 años instalados" },
  { slug: "per-capita-residencial", label: "11. Consumo per cápita residencial" },
  { slug: "top3-consumidores-distrito", label: "12. Top 3 consumidores por distrito" },
  { slug: "zonas-renovacion", label: "13. Zonas que requieren renovación" },
  { slug: "zonas-errores-por-distrito", label: "14. Zonas con errores por distrito", params: { distrito: "1" } },
  { slug: "cobertura-antenas", label: "15. Cobertura de antenas" },
  { slug: "proyeccion-demanda-5anios", label: "16. Proyección de demanda a 5 años" },
  { slug: "impacto-cambio-tarifa", label: "17. Impacto de cambio tarifa", params: { desde: "P", hacia: "R4" } },
  { slug: "medidores-sin-reporte", label: "18. Medidores sin reporte" },
  { slug: "proyeccion-ingresos-mes", label: "19. Proyección de ingresos del mes" },
  { slug: "consumo-minimo-residencial", label: "20. Consumo mínimo residencial" },
  { slug: "ingresos-pies3", label: "21. Ingresos en pies cúbicos" },
  { slug: "distribucion-categorias", label: "22. Distribución de categorías (extra)" },
  { slug: "horas-pico", label: "23. Horas pico (extra)" },
  { slug: "medidores-por-modelo", label: "24. Medidores por modelo (extra)" },
  { slug: "resumen-cobertura-poblacional", label: "25. Cobertura poblacional (extra)" },
];

export default function Consultas() {
  const [resultado, setResultado] = useState<any>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function ejecutar(c: typeof CONSULTAS[number]) {
    setBusy(c.slug);
    setResultado(null);
    try {
      const r = await api.get(`/consultas/${c.slug}`, { params: c.params });
      setResultado({ slug: c.slug, data: r.data });
    } catch (e: any) {
      setResultado({ slug: c.slug, error: e.response?.data || e.message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">25 consultas analíticas</h1>
      <div className="grid grid-cols-2 gap-2">
        {CONSULTAS.map((c) => (
          <button
            key={c.slug}
            onClick={() => ejecutar(c)}
            disabled={busy === c.slug}
            className="flex items-center justify-between bg-white border rounded p-3 text-sm hover:bg-semapa-50 disabled:opacity-60"
          >
            <span>{c.label}</span>
            <Play size={14} className="text-semapa-600" />
          </button>
        ))}
      </div>

      {resultado && (
        <div className="bg-slate-900 text-green-300 p-4 rounded text-xs overflow-auto max-h-[60vh]">
          <div className="text-slate-400 mb-2">/consultas/{resultado.slug}</div>
          <pre>{JSON.stringify(resultado.data || resultado.error, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
