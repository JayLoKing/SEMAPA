import { useState, useCallback } from "react";
import axios from "axios";
import { Droplet, Search, Printer, RefreshCw, AlertCircle } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────
interface Factura {
  periodo: string;
  consumo_m3: number;
  monto_bs: number;
  estado: "PENDIENTE" | "PAGADA" | "VENCIDA" | string;
}

interface TitularObj {
  razon_social?: string;
  nombre?: string;
  apellido?: string;
  apellidos?: string;
}

interface KioskData {
  contrato: number;
  titular: TitularObj | string;
  direccion?: string;
  categoria_tarifa: string;
  estado_medidor: string;
  facturas: Factura[];
}

function titularNombre(t: TitularObj | string): string {
  if (!t) return "—";
  if (typeof t === "string") return t;
  if (t.razon_social) return t.razon_social;
  return `${t.nombre || ""} ${t.apellido || t.apellidos || ""}`.trim() || "—";
}

// ── Helpers ────────────────────────────────────────────────────────────────────
const BASE_URL = (import.meta as any).env?.VITE_API_URL || "/api/v1";

function estadoColor(estado: string) {
  switch (estado.toUpperCase()) {
    case "PENDIENTE":
      return "bg-yellow-100 text-yellow-800 border border-yellow-300";
    case "PAGADA":
      return "bg-green-100 text-green-800 border border-green-300";
    case "VENCIDA":
      return "bg-red-100 text-red-800 border border-red-300";
    default:
      return "bg-slate-100 text-slate-700 border border-slate-300";
  }
}

// ── Idle / Input State ─────────────────────────────────────────────────────────
function IdleScreen({
  onSearch,
}: {
  onSearch: (contrato: string) => void;
}) {
  const [contrato, setContrato] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = contrato.trim();
    if (trimmed) onSearch(trimmed);
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-950 via-blue-800 to-cyan-700 px-8">
      {/* Branding */}
      <div className="flex flex-col items-center mb-14 select-none">
        <div className="flex items-center gap-4 mb-3">
          <Droplet className="text-cyan-300 drop-shadow-lg" size={72} strokeWidth={1.8} />
          <span className="text-7xl font-black text-white tracking-widest drop-shadow-xl">
            SEMAPA
          </span>
        </div>
        <p className="text-2xl text-blue-200 font-medium tracking-wide">
          Servicio Municipal de Agua Potable y Alcantarillado
        </p>
        <p className="text-lg text-blue-300 mt-1">Cochabamba — Bolivia</p>
      </div>

      {/* Input card */}
      <form
        onSubmit={handleSubmit}
        className="bg-white/10 backdrop-blur-md border border-white/20 rounded-3xl shadow-2xl px-14 py-12 flex flex-col items-center w-full max-w-2xl"
      >
        <p className="text-3xl font-bold text-white mb-2 text-center">
          Consulta tu estado de cuenta
        </p>
        <p className="text-blue-200 text-xl mb-10 text-center">
          Ingresa tu número de contrato para ver tus facturas
        </p>

        <input
          type="text"
          inputMode="numeric"
          autoFocus
          value={contrato}
          onChange={(e) => setContrato(e.target.value)}
          placeholder="Ej: 12345678"
          className="w-full text-center text-4xl font-bold tracking-widest bg-white text-blue-900 rounded-2xl px-8 py-6 outline-none shadow-inner border-4 border-transparent focus:border-cyan-400 placeholder:text-blue-200 transition-all mb-8"
        />

        <button
          type="submit"
          disabled={!contrato.trim()}
          className="flex items-center gap-4 bg-cyan-400 hover:bg-cyan-300 disabled:bg-blue-700 disabled:cursor-not-allowed text-blue-950 disabled:text-blue-400 font-black text-3xl uppercase tracking-widest px-16 py-6 rounded-2xl shadow-xl transition-all active:scale-95"
        >
          <Search size={36} strokeWidth={2.5} />
          CONSULTAR
        </button>
      </form>

      <p className="text-blue-400 text-base mt-10 select-none">
        Toque la pantalla para comenzar
      </p>
    </div>
  );
}

// ── Loading Spinner ────────────────────────────────────────────────────────────
function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-950 via-blue-800 to-cyan-700">
      <div className="animate-spin rounded-full h-28 w-28 border-[8px] border-blue-300 border-t-cyan-300 mb-8" />
      <p className="text-3xl text-white font-semibold animate-pulse">Consultando...</p>
    </div>
  );
}

// ── Error Screen ───────────────────────────────────────────────────────────────
function ErrorScreen({
  message,
  onReset,
}: {
  message: string;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-950 via-blue-800 to-cyan-700 px-8">
      <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-3xl px-14 py-12 flex flex-col items-center max-w-xl w-full shadow-2xl">
        <AlertCircle className="text-red-300 mb-6" size={80} strokeWidth={1.5} />
        <p className="text-4xl font-black text-white mb-4 text-center">{message}</p>
        <p className="text-blue-200 text-xl mb-10 text-center">
          Verifica el número e intenta nuevamente.
        </p>
        <button
          onClick={onReset}
          className="flex items-center gap-4 bg-cyan-400 hover:bg-cyan-300 text-blue-950 font-black text-2xl uppercase tracking-widest px-12 py-5 rounded-2xl shadow-xl transition-all active:scale-95"
        >
          <RefreshCw size={30} strokeWidth={2.5} />
          NUEVA CONSULTA
        </button>
      </div>
    </div>
  );
}

// ── Result Screen ──────────────────────────────────────────────────────────────
function ResultScreen({
  data,
  onReset,
}: {
  data: KioskData;
  onReset: () => void;
}) {
  return (
    <>
      {/* Print-only receipt styles */}
      <style>{`
        @media print {
          body { background: white !important; }
          .no-print { display: none !important; }
          .print-full { box-shadow: none !important; border: none !important; }
        }
      `}</style>

      <div className="min-h-screen bg-gradient-to-br from-blue-950 via-blue-800 to-cyan-700 flex flex-col items-center justify-start px-6 py-10 print-full">
        {/* Header */}
        <div className="no-print flex items-center gap-3 mb-6 select-none">
          <Droplet className="text-cyan-300" size={44} strokeWidth={1.8} />
          <span className="text-5xl font-black text-white tracking-widest drop-shadow-xl">
            SEMAPA
          </span>
        </div>

        {/* Print-only header */}
        <div className="hidden print:flex flex-col items-center mb-6">
          <p className="text-3xl font-black">SEMAPA</p>
          <p className="text-base">Servicio Municipal de Agua Potable y Alcantarillado — Cochabamba</p>
          <hr className="w-full mt-2" />
        </div>

        {/* Account card */}
        <div className="bg-white rounded-3xl shadow-2xl w-full max-w-4xl print-full">
          {/* Titular */}
          <div className="bg-blue-700 rounded-t-3xl px-10 py-8 flex flex-col items-center print:bg-blue-100">
            <p className="text-blue-200 text-xl font-semibold uppercase tracking-widest mb-1 print:text-blue-600">
              Titular de la cuenta
            </p>
            <p className="text-5xl font-black text-white text-center leading-tight print:text-blue-900">
              {titularNombre(data.titular)}
            </p>
          </div>

          {/* Details grid */}
          <div className="grid grid-cols-3 gap-0 border-b border-slate-200">
            <DetailCell label="N° Contrato" value={String(data.contrato)} />
            <DetailCell label="Categoría Tarifa" value={data.categoria_tarifa || "—"} />
            <DetailCell label="Estado Medidor" value={data.estado_medidor || "—"} last />
          </div>

          {/* Invoices table */}
          <div className="px-8 py-6">
            <p className="text-xl font-bold text-blue-800 uppercase tracking-widest mb-4">
              Últimas Facturas
            </p>
            {data.facturas && data.facturas.length > 0 ? (
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-blue-50">
                    <th className="px-5 py-4 text-base font-bold text-blue-700 uppercase tracking-wide border-b-2 border-blue-200">
                      Periodo
                    </th>
                    <th className="px-5 py-4 text-base font-bold text-blue-700 uppercase tracking-wide border-b-2 border-blue-200 text-right">
                      Consumo m³
                    </th>
                    <th className="px-5 py-4 text-base font-bold text-blue-700 uppercase tracking-wide border-b-2 border-blue-200 text-right">
                      Monto Bs
                    </th>
                    <th className="px-5 py-4 text-base font-bold text-blue-700 uppercase tracking-wide border-b-2 border-blue-200 text-center">
                      Estado
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.facturas.map((f, i) => (
                    <tr
                      key={i}
                      className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}
                    >
                      <td className="px-5 py-4 text-xl font-semibold text-slate-800 border-b border-slate-100">
                        {f.periodo}
                      </td>
                      <td className="px-5 py-4 text-xl text-slate-700 border-b border-slate-100 text-right font-mono">
                        {f.consumo_m3}
                      </td>
                      <td className="px-5 py-4 text-xl text-slate-700 border-b border-slate-100 text-right font-mono font-bold">
                        {Number(f.monto_bs).toFixed(2)}
                      </td>
                      <td className="px-5 py-4 border-b border-slate-100 text-center">
                        <span
                          className={`inline-block px-4 py-1 rounded-full text-base font-bold uppercase tracking-wide ${estadoColor(f.estado)}`}
                        >
                          {f.estado}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-slate-400 text-xl text-center py-8">
                No hay facturas registradas.
              </p>
            )}
          </div>

          {/* Action buttons */}
          <div className="no-print flex gap-6 px-8 pb-8 pt-2">
            <button
              onClick={() => window.print()}
              className="flex-1 flex items-center justify-center gap-3 bg-blue-700 hover:bg-blue-600 text-white font-black text-2xl uppercase tracking-widest py-6 rounded-2xl shadow-lg transition-all active:scale-95"
            >
              <Printer size={32} strokeWidth={2} />
              IMPRIMIR RECIBO
            </button>
            <button
              onClick={onReset}
              className="flex-1 flex items-center justify-center gap-3 bg-slate-200 hover:bg-slate-300 text-slate-800 font-black text-2xl uppercase tracking-widest py-6 rounded-2xl shadow-lg transition-all active:scale-95"
            >
              <RefreshCw size={32} strokeWidth={2} />
              NUEVA CONSULTA
            </button>
          </div>
        </div>

        {/* Print footer */}
        <div className="hidden print:block text-center text-sm mt-6 text-slate-500">
          <p>Impreso desde kiosco SEMAPA — {new Date().toLocaleString("es-BO")}</p>
        </div>
      </div>
    </>
  );
}

// ── Helper sub-component ───────────────────────────────────────────────────────
function DetailCell({
  label,
  value,
  last = false,
}: {
  label: string;
  value: string;
  last?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center py-6 px-4 ${
        !last ? "border-r border-slate-200" : ""
      }`}
    >
      <p className="text-sm font-bold uppercase tracking-widest text-slate-400 mb-1">
        {label}
      </p>
      <p className="text-2xl font-black text-slate-800 text-center">{value}</p>
    </div>
  );
}

// ── Main Kiosk Page ────────────────────────────────────────────────────────────
type Screen = "idle" | "loading" | "result" | "error";

export default function Kiosk() {
  const [screen, setScreen] = useState<Screen>("idle");
  const [data, setData] = useState<KioskData | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSearch = useCallback(async (contrato: string) => {
    setScreen("loading");
    try {
      const res = await axios.get<KioskData>(
        `${BASE_URL}/kiosk/${encodeURIComponent(contrato)}`
      );
      setData(res.data);
      setScreen("result");
    } catch (err: any) {
      if (err.response?.status === 404) {
        setErrorMsg("Contrato no encontrado");
      } else {
        setErrorMsg("Error de conexión");
      }
      setScreen("error");
    }
  }, []);

  const handleReset = useCallback(() => {
    setData(null);
    setErrorMsg("");
    setScreen("idle");
  }, []);

  if (screen === "idle") return <IdleScreen onSearch={handleSearch} />;
  if (screen === "loading") return <LoadingScreen />;
  if (screen === "error") return <ErrorScreen message={errorMsg} onReset={handleReset} />;
  if (screen === "result" && data) return <ResultScreen data={data} onReset={handleReset} />;

  return null;
}
