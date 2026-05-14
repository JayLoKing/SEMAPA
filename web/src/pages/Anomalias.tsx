import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { AlertTriangle, Clock, DollarSign, Loader2, RefreshCw } from "lucide-react";

type Anomalia = {
  medidor_id: string;
  consumo_litros: number;
  leido_en: string;
  estado: string;
  tipo_anomalia: string;
};

type Moroso = {
  numero_contrato: number;
  periodos_vencidos: number;
  monto_total_bs: string;
  periodos: string[];
};

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${color}`}>
      {text}
    </span>
  );
}

export default function Anomalias() {
  const [tab, setTab] = useState<"anomalias" | "morosos">("anomalias");

  const anomaliasQ = useQuery({
    queryKey: ["anomalias"],
    queryFn: async () => (await api.get("/anomalias?limite=200")).data,
    enabled: tab === "anomalias",
  });

  const morososQ = useQuery({
    queryKey: ["morosos"],
    queryFn: async () => (await api.get("/anomalias/morosos?limite=300&meses=2")).data,
    enabled: tab === "morosos",
  });

  const anomalias: Anomalia[] = anomaliasQ.data?.anomalias || [];
  const morosos: Moroso[] = morososQ.data?.morosos || [];

  function severityColor(tipo: string) {
    if (tipo === "ANOMALIA_CONSUMO") return "bg-red-100 text-red-700";
    if (tipo === "ERROR_SENSOR") return "bg-orange-100 text-orange-700";
    return "bg-yellow-100 text-yellow-700";
  }

  function morosoColor(periodos: number) {
    if (periodos >= 6) return "bg-red-100 text-red-700";
    if (periodos >= 3) return "bg-orange-100 text-orange-700";
    return "bg-yellow-100 text-yellow-800";
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <AlertTriangle className="text-orange-500" size={24} />
          Monitoreo y Alertas
        </h1>
        <button
          onClick={() => { anomaliasQ.refetch(); morososQ.refetch(); }}
          className="flex items-center gap-1 text-sm text-semapa-600 hover:text-semapa-800"
        >
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      {/* KPI summary row */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="text-xs text-red-600 uppercase font-semibold">Anomalías sensor</div>
          <div className="text-3xl font-bold text-red-700">
            {anomaliasQ.isLoading ? "…" : anomalias.filter(a => a.tipo_anomalia === "ANOMALIA_CONSUMO").length}
          </div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="text-xs text-orange-600 uppercase font-semibold">Errores IoT</div>
          <div className="text-3xl font-bold text-orange-700">
            {anomaliasQ.isLoading ? "…" : anomalias.filter(a => a.tipo_anomalia === "ERROR_SENSOR").length}
          </div>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="text-xs text-yellow-600 uppercase font-semibold">Cuentas morosas</div>
          <div className="text-3xl font-bold text-yellow-700">
            {morososQ.isLoading ? "…" : morosos.length}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b flex gap-0">
        <button
          onClick={() => setTab("anomalias")}
          className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "anomalias"
              ? "border-semapa-600 text-semapa-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <AlertTriangle size={14} className="inline mr-1" />
          Anomalías de consumo
        </button>
        <button
          onClick={() => setTab("morosos")}
          className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === "morosos"
              ? "border-semapa-600 text-semapa-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Clock size={14} className="inline mr-1" />
          Cuentas incobrables / morosos
        </button>
      </div>

      {/* Anomalías table */}
      {tab === "anomalias" && (
        <div>
          {anomaliasQ.isLoading && (
            <div className="flex items-center gap-2 text-slate-500 py-8 justify-center">
              <Loader2 className="animate-spin" size={20} /> Cargando anomalías...
            </div>
          )}
          {!anomaliasQ.isLoading && anomalias.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              No se detectaron anomalías recientes.
            </div>
          )}
          {anomalias.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-xs uppercase text-slate-500">
                    <th className="text-left px-3 py-2">Medidor ID</th>
                    <th className="text-left px-3 py-2">Tipo</th>
                    <th className="text-right px-3 py-2">Consumo (L)</th>
                    <th className="text-left px-3 py-2">Fecha lectura</th>
                    <th className="text-left px-3 py-2">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalias.map((a, i) => (
                    <tr key={i} className="border-t hover:bg-slate-50">
                      <td className="px-3 py-2 font-mono text-xs">{a.medidor_id?.slice(0, 8)}…</td>
                      <td className="px-3 py-2">
                        <Badge text={a.tipo_anomalia} color={severityColor(a.tipo_anomalia)} />
                      </td>
                      <td className="px-3 py-2 text-right font-semibold text-red-600">
                        {a.consumo_litros?.toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-slate-500 text-xs">
                        {a.leido_en ? new Date(a.leido_en).toLocaleString("es-BO") : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          text={a.estado || "DESCONOCIDO"}
                          color={a.estado === "ERROR" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-400 mt-2 px-3">
                Umbral configurado: consumo diferencial &gt; 50,000 L por lectura = anomalía.
                Status 8 = reset de medidor · Status 9 = salto imposible.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Morosos table */}
      {tab === "morosos" && (
        <div>
          {morososQ.isLoading && (
            <div className="flex items-center gap-2 text-slate-500 py-8 justify-center">
              <Loader2 className="animate-spin" size={20} /> Cargando morosos...
            </div>
          )}
          {!morososQ.isLoading && morosos.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              No se encontraron cuentas morosas.
            </div>
          )}
          {morosos.length > 0 && (
            <div className="overflow-x-auto">
              <p className="text-xs text-slate-500 mb-2">
                Ordenados por antigüedad de deuda (mayor → menor). Mayor antigüedad = mayor riesgo incobrable.
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 text-xs uppercase text-slate-500">
                    <th className="text-left px-3 py-2">Contrato</th>
                    <th className="text-center px-3 py-2">Períodos vencidos</th>
                    <th className="text-right px-3 py-2">Monto total Bs</th>
                    <th className="text-left px-3 py-2">Períodos</th>
                    <th className="text-left px-3 py-2">Riesgo</th>
                  </tr>
                </thead>
                <tbody>
                  {morosos.map((m, i) => (
                    <tr key={i} className="border-t hover:bg-slate-50">
                      <td className="px-3 py-2 font-mono font-semibold">{m.numero_contrato}</td>
                      <td className="px-3 py-2 text-center font-bold text-orange-600">
                        {m.periodos_vencidos}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold">
                        <DollarSign size={12} className="inline" />
                        {parseFloat(m.monto_total_bs).toLocaleString("es-BO", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        {(m.periodos || []).join(", ")}
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          text={m.periodos_vencidos >= 6 ? "INCOBRABLE" : m.periodos_vencidos >= 3 ? "ALTO" : "MEDIO"}
                          color={morosoColor(m.periodos_vencidos)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-400 mt-2 px-3">
                Cuentas incobrables = 6+ períodos pendientes. Art. 18 reglamento tarifario.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
