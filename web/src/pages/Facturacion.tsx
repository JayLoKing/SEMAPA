import { useState } from "react";
import { api } from "../api/client";
import { Mail, MessageSquare, FileText, Send } from "lucide-react";

export default function Facturacion() {
  const [contrato, setContrato] = useState("100000001");
  const [periodo, setPeriodo] = useState("2025-05");
  const [factura, setFactura] = useState<any>(null);
  const [canales, setCanales] = useState({ email: true, sms: false, whatsapp: false });
  const [toast, setToast] = useState("");

  async function buscar() {
    setToast("");
    try {
      const r = await api.get(`/facturas/${contrato}/${periodo}`);
      setFactura(r.data);
    } catch (e: any) {
      setFactura(null);
      setToast(e.response?.data?.detail || "Sin resultados");
    }
  }

  async function enviar() {
    const enviados: string[] = [];
    for (const canal of Object.keys(canales) as Array<keyof typeof canales>) {
      if (!canales[canal]) continue;
      try {
        await api.post("/notify", {
          formato: canal,
          identificador: "contrato",
          valor: contrato,
          periodo,
        });
        enviados.push(canal);
      } catch (e) {
        // continuar
      }
    }
    setToast(enviados.length ? `Encolado: ${enviados.join(", ")}` : "Sin canales");
  }

  async function generarLote() {
    const r = await api.post(`/facturas/generar?periodo=${periodo}&limite=100`);
    setToast(`Generadas: ${r.data.generadas}, cambio: ${r.data.tipo_cambio}`);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Facturación</h1>

      <div className="bg-white p-4 rounded-lg shadow-sm border space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs uppercase text-slate-500">Contrato</label>
            <input className="w-full border rounded px-3 py-2" value={contrato} onChange={(e) => setContrato(e.target.value)} />
          </div>
          <div>
            <label className="text-xs uppercase text-slate-500">Periodo (YYYY-MM)</label>
            <input className="w-full border rounded px-3 py-2" value={periodo} onChange={(e) => setPeriodo(e.target.value)} />
          </div>
          <div className="flex items-end gap-2">
            <button className="bg-semapa-600 hover:bg-semapa-700 text-white px-4 py-2 rounded" onClick={buscar}>
              Buscar
            </button>
            <button className="bg-slate-700 hover:bg-slate-800 text-white px-4 py-2 rounded" onClick={generarLote}>
              Generar lote
            </button>
          </div>
        </div>
      </div>

      {factura && (
        <div className="bg-white p-5 rounded-lg shadow-sm border space-y-3">
          <h2 className="text-lg font-semibold">Factura {factura.periodo}</h2>
          <div className="grid grid-cols-4 gap-3 text-sm">
            <div><b>Contrato:</b> {factura.numero_contrato}</div>
            <div><b>Categoría:</b> {factura.categoria_tarifa}</div>
            <div><b>Consumo:</b> {factura.consumo_m3} m³</div>
            <div><b>Estado:</b> {factura.estado}</div>
            <div><b>Total USD:</b> {factura.monto_usd}</div>
            <div><b>Total Bs.:</b> {factura.monto_bs}</div>
          </div>
          <div className="flex gap-2 mt-3">
            <a className="bg-semapa-50 text-semapa-700 border border-semapa-600 px-3 py-2 rounded text-sm flex items-center gap-1"
               href={`/pdf?numero_contrato=${factura.numero_contrato}&periodo=${factura.periodo}&formato=medicarta`}
               target="_blank">
              <FileText size={14} /> PDF media carta
            </a>
            <a className="bg-semapa-50 text-semapa-700 border border-semapa-600 px-3 py-2 rounded text-sm flex items-center gap-1"
               href={`/pdf?numero_contrato=${factura.numero_contrato}&periodo=${factura.periodo}&formato=rollo`}
               target="_blank">
              <FileText size={14} /> PDF rollo térmico
            </a>
          </div>

          <div className="border-t pt-4 mt-4">
            <h3 className="font-semibold mb-2">Enviar recibo</h3>
            <div className="flex gap-4 items-center">
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={canales.email}
                       onChange={(e) => setCanales({ ...canales, email: e.target.checked })} />
                <Mail size={14} /> Email
              </label>
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={canales.sms}
                       onChange={(e) => setCanales({ ...canales, sms: e.target.checked })} />
                <MessageSquare size={14} /> SMS
              </label>
              <label className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={canales.whatsapp}
                       onChange={(e) => setCanales({ ...canales, whatsapp: e.target.checked })} />
                <MessageSquare size={14} /> WhatsApp
              </label>
              <button className="ml-auto bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded flex items-center gap-1"
                      onClick={enviar}>
                <Send size={14} /> Enviar
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="bg-slate-900 text-green-300 text-sm p-3 rounded">{toast}</div>}
    </div>
  );
}
