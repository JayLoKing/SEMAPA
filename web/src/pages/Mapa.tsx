import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useThemeStore } from "../store/theme";

const CENTRO: [number, number] = [-17.39, -66.13];

// CARTO basemaps minimalistas (sin API key)
const TILES = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};

interface DistritoGeo {
  distrito_id: number; nombre: string; medidores: number; consumo_m3: number;
}
interface Medidor {
  mac: string; numero_contrato: string; titular: string; categoria: string;
  subcategoria: string; estado: string; activo: boolean; zona: string;
  lat: number; lon: number;
}

function colorEstado(activo: boolean, estado: string): string {
  if (estado === "Dañado") return "#ef4444";
  if (estado === "Mantenimiento") return "#eab308";
  return activo ? "#22c55e" : "#94a3b8";
}
function colorConsumo(v: number, max: number): string {
  const t = max ? v / max : 0;
  if (t > 0.8) return "#0f172a";
  if (t > 0.6) return "#1e3a8a";
  if (t > 0.4) return "#1d4ed8";
  if (t > 0.2) return "#3b82f6";
  return "#93c5fd";
}

function MapRef({ onReady }: { onReady: (m: L.Map) => void }) {
  const map = useMap();
  useEffect(() => { onReady(map); }, [map, onReady]);
  return null;
}

export default function Mapa() {
  const theme = useThemeStore((s) => s.theme);
  const [map, setMap] = useState<L.Map | null>(null);
  const [distritoSel, setDistritoSel] = useState<number | null>(null);
  const [macSel, setMacSel] = useState<string | null>(null);

  // GeoJSON real de límites distritales (WGS84)
  const { data: geojson } = useQuery({
    queryKey: ["distritos-geojson"],
    queryFn: async () => (await fetch("/distritos.geojson")).json(),
  });

  // Consumo + medidores por distrito (para choropleth)
  const { data: geo } = useQuery<DistritoGeo[]>({
    queryKey: ["mapa-geo"],
    queryFn: async () => (await api.get("/mapa/distritos-geo")).data,
  });

  const { data: medidores, isFetching } = useQuery({
    queryKey: ["mapa-medidores", distritoSel],
    queryFn: async () => (await api.get(`/mapa/distrito/${distritoSel}/medidores?limite=3000`)).data,
    enabled: distritoSel !== null,
  });

  const { data: detalle } = useQuery({
    queryKey: ["mapa-detalle", macSel],
    queryFn: async () => (await api.get(`/mapa/medidor/${macSel}`)).data,
    enabled: macSel !== null,
  });

  const consumoMap = useMemo(() => {
    const m: Record<number, DistritoGeo> = {};
    (geo || []).forEach((d) => (m[d.distrito_id] = d));
    return m;
  }, [geo]);
  const maxCons = Math.max(1, ...(geo || []).map((d) => d.consumo_m3));

  function styleFeature(feature: any) {
    const id = feature.properties.distrito;
    const cons = consumoMap[id]?.consumo_m3 || 0;
    const selected = distritoSel === id;
    return {
      color: selected ? "#0ea5e9" : (theme === "dark" ? "#64748b" : "#475569"),
      weight: selected ? 3 : 1.2,
      fillColor: colorConsumo(cons, maxCons),
      fillOpacity: selected ? 0.55 : 0.3,
    };
  }

  function onEachFeature(feature: any, layer: any) {
    const id = feature.properties.distrito;
    const info = consumoMap[id];
    layer.bindTooltip(
      `Distrito ${id} · ${(info?.consumo_m3 || 0).toLocaleString()} m³ · ${info?.medidores || 0} med.`,
      { sticky: true });
    layer.on("click", () => {
      setDistritoSel(id);
      setMacSel(null);
      if (map) map.fitBounds(layer.getBounds(), { padding: [30, 30] });
    });
  }

  // Pinta medidores del distrito seleccionado
  useEffect(() => {
    if (!map || !medidores?.medidores) return;
    // @ts-ignore
    const cluster = L.markerClusterGroup({ maxClusterRadius: 50 });
    const pts: Medidor[] = medidores.medidores;
    pts.forEach((m) => {
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:13px;height:13px;border-radius:50%;background:${colorEstado(m.activo, m.estado)};border:2px solid white;box-shadow:0 0 3px rgba(0,0,0,.4)"></div>`,
        iconSize: [13, 13],
      });
      const mk = L.marker([m.lat, m.lon], { icon });
      mk.bindPopup(
        `<b>${m.mac}</b><br/>${m.numero_contrato || "s/contrato"}<br/>${m.titular || ""}<br/>` +
        `${m.subcategoria} · ${m.estado}<br/><a href="#" data-mac="${m.mac}" class="ver-med">Ver info →</a>`
      );
      mk.on("popupopen", () => {
        document.querySelectorAll<HTMLAnchorElement>(".ver-med").forEach((a) => {
          a.onclick = (e) => { e.preventDefault(); setMacSel(a.dataset.mac || null); };
        });
      });
      cluster.addLayer(mk);
    });
    map.addLayer(cluster);
    return () => { map.removeLayer(cluster); };
  }, [map, medidores]);

  function seleccionarDesdeePanel(id: number) {
    setDistritoSel(id);
    setMacSel(null);
    // zoom: busca el layer geojson por id via bounds del feature
    if (map && geojson) {
      const ft = geojson.features.find((f: any) => f.properties.distrito === id);
      if (ft) {
        const layer = L.geoJSON(ft);
        map.fitBounds(layer.getBounds(), { padding: [30, 30] });
      }
    }
  }

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-bold">Mapa interactivo — Cochabamba (Cercado)</h1>
      <p className="text-sm text-slate-500">
        Límites distritales reales (D1–D15). Selecciona un distrito → zoom + carga de medidores.
        Click en medidor → info de contrato, persona y consumo.
      </p>

      <div className="grid grid-cols-[240px_1fr_320px] gap-3">
        {/* Panel distritos */}
        <div className="bg-white rounded-lg border shadow-sm overflow-y-auto max-h-[74vh]">
          <div className="px-3 py-2 border-b font-semibold text-sm bg-slate-50">Distritos</div>
          {(geo || []).slice().sort((a, b) => a.distrito_id - b.distrito_id).map((d) => (
            <button key={d.distrito_id} onClick={() => seleccionarDesdeePanel(d.distrito_id)}
              className={`w-full text-left px-3 py-2 border-b text-xs hover:bg-slate-50 ${distritoSel === d.distrito_id ? "bg-semapa-50 border-l-4 border-l-semapa-600" : ""}`}>
              <div className="flex justify-between font-semibold items-center">
                <span><span className="inline-block w-3 h-3 rounded mr-1 align-middle"
                  style={{ background: colorConsumo(d.consumo_m3, maxCons) }} />{d.nombre}</span>
                <span className="text-slate-500">{d.medidores.toLocaleString()}</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">{d.consumo_m3.toLocaleString()} m³</div>
            </button>
          ))}
        </div>

        {/* Mapa */}
        <div className="h-[74vh] rounded-lg overflow-hidden shadow border relative">
          {isFetching && (
            <div className="absolute top-2 right-2 z-[1000] bg-white px-3 py-1 rounded shadow text-xs">Cargando medidores...</div>
          )}
          <MapContainer center={CENTRO} zoom={12} style={{ height: "100%", width: "100%" }}>
            <MapRef onReady={setMap} />
            <TileLayer key={theme} url={theme === "dark" ? TILES.dark : TILES.light}
              subdomains="abcd" attribution='&copy; OpenStreetMap &copy; CARTO' />
            {geojson && (
              <GeoJSON
                key={`${distritoSel}-${theme}-${!!geo}`}
                data={geojson}
                style={styleFeature as any}
                onEachFeature={onEachFeature}
              />
            )}
          </MapContainer>
          <div className="absolute bottom-2 left-2 z-[1000] bg-white/90 px-3 py-2 rounded shadow text-[11px] space-y-1">
            <div className="font-semibold">Consumo distrito</div>
            <div><span className="inline-block w-3 h-3 mr-1" style={{ background: "#93c5fd" }} />bajo</div>
            <div><span className="inline-block w-3 h-3 mr-1" style={{ background: "#1e3a8a" }} />alto</div>
            <hr className="my-1" />
            <div><span className="inline-block w-3 h-3 rounded-full bg-green-500 mr-1" />Operativo</div>
            <div><span className="inline-block w-3 h-3 rounded-full bg-red-500 mr-1" />Dañado</div>
          </div>
        </div>

        {/* Panel detalle medidor */}
        <div className="bg-white rounded-lg border shadow-sm p-4 max-h-[74vh] overflow-y-auto">
          {!detalle && <p className="text-sm text-slate-400">Selecciona un distrito y haz click en un medidor.</p>}
          {detalle && (
            <div className="space-y-3 text-sm">
              <div>
                <div className="text-xs uppercase text-slate-400 font-semibold">Medidor</div>
                <div className="font-mono font-bold">{detalle.medidor?.mac}</div>
                <div className="text-xs">Estado: {detalle.medidor?.estado} · Modelo {detalle.medidor?.tipo_medidor_id}</div>
              </div>
              {detalle.contrato && (
                <div>
                  <div className="text-xs uppercase text-slate-400 font-semibold">Contrato</div>
                  <div className="font-bold">{detalle.contrato.numero_contrato}</div>
                  <div>{detalle.contrato.titular_contrato}</div>
                  <div className="text-xs text-slate-500">CI: {detalle.contrato.ci_titular}</div>
                  <div className="text-xs">{detalle.contrato.categoria} ({detalle.contrato.subcategoria})</div>
                </div>
              )}
              {detalle.infraestructura && (
                <div>
                  <div className="text-xs uppercase text-slate-400 font-semibold">Infraestructura</div>
                  <div className="text-xs">{detalle.infraestructura.direccion}</div>
                  <div className="text-xs text-slate-500">{detalle.infraestructura.zona}</div>
                </div>
              )}
              <div>
                <div className="text-xs uppercase text-slate-400 font-semibold mb-1">Consumo reciente</div>
                <table className="w-full text-xs">
                  <thead><tr className="text-slate-400"><th className="text-left">Periodo</th><th className="text-right">m³</th><th>Pago</th></tr></thead>
                  <tbody>
                    {(detalle.lecturas || []).map((l: any, i: number) => (
                      <tr key={i} className="border-t">
                        <td>{l.periodo}</td>
                        <td className="text-right font-mono">{l.consumo_m3}</td>
                        <td className="text-center">{l.pagado ? "✓" : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
