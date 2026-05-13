import { useParams } from "react-router-dom";

export default function DetalleMedidor() {
  const { id } = useParams();
  return (
    <div>
      <h1 className="text-2xl font-bold">Medidor {id}</h1>
      <p className="text-slate-500 mt-2">Detalle pendiente (gráficas de consumo, alertas, etc.).</p>
    </div>
  );
}
